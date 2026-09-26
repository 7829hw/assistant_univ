# -*- coding: utf-8 -*-
"""GeoFlowPlan(의미 graph) → ExecutionPlan(실행 단계) 변환(lowering).

여기서 처음으로 semantic operator가 실제 Tool 이름과 argument 이름에 묶인다.
Planner도 template도 Tool argument 이름을 직접 지정하지 않는다.

대부분의 변환은 Tool 호출 하나가 된다. 구간별 집계는 두 가지로 내려간다.

1. **호출 하나로 합침.** TIMS operator가 ``bucket_rollup``을 선언했고 구간별 값을
   합치는(REDUCE_GROUPS) 경우다. 구간 안 집계 변환과 합치는 변환이 호출 하나가
   되고, 인자마다 어느 의미 단계에서 왔는지 ``argument_sources``에 남긴다.
2. **기간을 나눠 호출한 뒤 로컬 계산.** 합칠 수 없는 경우다(구간을 고르는
   SELECT_GROUP, bucket을 받지 않는 Tool). 기간을 명시 날짜 구간으로 나누어
   구간마다 같은 조건으로 호출하고, 결과(구간별 값 자체)를 로컬에서 합치거나
   고른다. 기간을 날짜로 풀 수 없으면 계획을 만들지 않는다.

끝에 ``verify_lowering``이 실행 단계를 의미 graph와 다시 대조한다. 조건이 빠지거나
구간 안/밖 집계가 뒤바뀐 lowering은 실행하지 않는다.
"""

from geoflow import analysis_ops, periods, tims_contract
from geoflow.errors import CompilerError
from geoflow.operator_registry import TOOL_DEFAULT_REDUCER, get_operator
from geoflow.types import (
    STEP_LOCAL,
    WHOLE_RESULT,
    ExecutionPlan,
    GeoFlowPlan,
    NodeSource,
    ToolStep,
    ValueRef,
)

#: 기간 인자 처리 방식.
#: - legacy: 의미 graph의 기간 값을 그대로 요청 인자로 쓴다. provider 의미 확인 상태는
#:   ``date_semantics``에 기록만 한다(기본 경로, 기존 동작).
#: - guaranteed: 요청 인자의 기간 의미가 TIMS 계약으로 확인될 때만 실행한다. 확인되지
#:   않으면 계약이 허용하는 다른 요청(명시 범위, 하루 단위 합성)으로 바꾸고, 그것도
#:   없으면 ``DATE_EXECUTION_UNVERIFIED``로 멈춘다(condition_check 경로).
DATE_POLICY_LEGACY = "legacy"
DATE_POLICY_GUARANTEED = "guaranteed"

#: 실행 시점에 Tool이 채우는 node source.
PRODUCED_SOURCES = frozenset({NodeSource.TOOL, NodeSource.DERIVED})


def producer_map(plan: GeoFlowPlan):
    """concept id → 그 값을 만드는 transformation id."""
    producers: dict[str, str] = {}
    for transformation in plan.transformations:
        for output_id in transformation.outputs:
            producers.setdefault(output_id, transformation.id)
    return producers


def topological_order(plan: GeoFlowPlan):
    """(정렬된 transformation id, cycle에 남은 id)를 반환한다."""
    producers = producer_map(plan)
    pending: dict[str, set[str]] = {}
    for transformation in plan.transformations:
        deps = set()
        for ref in transformation.inputs.values():
            producer = producers.get(ref.node_id)
            if producer is not None and producer != transformation.id:
                deps.add(producer)
        pending[transformation.id] = deps

    declared = [transformation.id for transformation in plan.transformations]
    order: list[str] = []
    resolved: set[str] = set()
    while pending:
        # 실행 가능한 것들 사이에서는 template 선언 순서를 유지해 trace를 읽기 쉽게 한다.
        ready = [
            identifier for identifier in declared
            if identifier in pending and pending[identifier] <= resolved
        ]
        if not ready:
            return order, [
                identifier for identifier in declared if identifier in pending
            ]
        for identifier in ready:
            order.append(identifier)
            resolved.add(identifier)
            pending.pop(identifier)
    return order, []


def compile_plan(plan: GeoFlowPlan, *, reference_date=None,
                 contract=tims_contract.DEFAULT_CONTRACT,
                 date_policy=DATE_POLICY_LEGACY):
    """검증을 통과한 plan을 topological order의 실행 단계로 만든다.

    ``reference_date``는 상대 기간(last_month 등)을 날짜로 풀 기준일이다. 기간을
    로컬에서 나눠야 할 때만 쓰며, 없으면 그런 계획은 만들지 않는다.
    ``contract``는 TIMS 계약의 확인 상태다. 구간별 집계를 어떤 호출로 내릴지는
    이 계약이 허용하는 전략 중에서만 고른다(``geoflow/tims_contract.py``).
    ``date_policy``는 위 ``DATE_POLICY_*`` 설명을 따른다.
    """
    if date_policy not in (DATE_POLICY_LEGACY, DATE_POLICY_GUARANTEED):
        raise ValueError(f"알 수 없는 date_policy: {date_policy!r}")
    order, cycle = topological_order(plan)
    if cycle:
        raise CompilerError(
            f"transformation dependency에 cycle이 있어 순서를 정할 수 "
            f"없습니다: {', '.join(cycle)}",
            code="CYCLE",
            context={"template": plan.template, "cycle": cycle},
        )

    nodes = {node.id: node for node in plan.concepts}
    by_id = {item.id: item for item in plan.transformations}
    consumers = {}
    for item in plan.transformations:
        for ref in item.inputs.values():
            consumers.setdefault(ref.node_id, []).append(item)

    execution = ExecutionPlan(
        template=plan.template,
        final_node=plan.final_node,
        seed_state={
            node.id: node.value
            for node in plan.concepts
            if node.source not in PRODUCED_SOURCES
        },
    )
    fused = set()
    for identifier in order:
        if identifier in fused:
            continue
        transformation = by_id[identifier]
        if analysis_ops.is_analysis_operator(transformation.operator):
            execution.steps.append(_local_step(transformation))
            continue
        output = nodes.get(transformation.outputs[0]) if transformation.outputs else None
        if not analysis_ops.is_grouped(output):
            execution.steps.extend(_lower_period(
                transformation, _compile_step(transformation, nodes, plan), output, plan,
                execution, reference_date=reference_date, contract=contract,
                date_policy=date_policy,
            ))
            continue
        combine = _single_combiner(transformation, output, consumers, plan)
        spec = get_operator(transformation.operator)
        strategy, rejected = choose_group_strategy(
            transformation, output, combine, spec, contract,
            require_day_records=date_policy == DATE_POLICY_GUARANTEED,
        )
        execution.lowering[transformation.id] = {
            "strategy": None if strategy is None else strategy.name,
            "rejected": rejected,
        }
        if strategy is None:
            raise CompilerError(
                f"{transformation.id}: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 "
                "확인되지 않았습니다. "
                + "; ".join(f"{item['strategy']}: {item['reason']}" for item in rejected),
                code="UNVERIFIED_TIMS_CONTRACT",
                user_message=(
                    "이 구간별 계산은 TIMS의 동작이 문서로 확인되지 않아 정확한 값을 "
                    "보장할 수 없으므로 수행하지 않았습니다."
                ),
                context={"template": plan.template, "rejected": rejected},
            )
        if strategy is tims_contract.FUSED_BUCKET_ROLLUP:
            execution.steps.append(_fused_step(
                transformation, combine, output, spec, nodes, plan,
            ))
            fused.add(combine.id)
            execution.unobserved[output.id] = (
                "TIMS bucket/rollup 호출 안에서 계산되어 구간별 값은 반환되지 않습니다."
            )
            continue
        execution.steps.extend(_partition_steps(
            transformation, output, spec, nodes, plan, execution,
            reference_date=reference_date, strategy=strategy,
        ))

    for step in execution.steps:
        for covered in step.covers:
            execution.semantic_map.setdefault(covered, []).append(step.id)
    verify_lowering(plan, execution, reference_date=reference_date,
                    contract=contract)
    return execution


def _interpreted_range(value, reference_date):
    """기간 값을 코드의 해석(Asia/Seoul 달력, 양 끝 포함)으로 푼다. 풀 수 없으면 None."""
    kind = tims_contract.date_argument_kind(value)
    if kind not in (tims_contract.DATE_SINGLE, tims_contract.DATE_RANGE,
                    tims_contract.DATE_RELATIVE):
        return None
    if kind == tims_contract.DATE_RELATIVE and reference_date is None:
        return None
    return periods.resolve_period(value, reference_date=reference_date)


def _lower_period(transformation, step, output, plan, execution, *, reference_date,
                  contract, date_policy):
    """한 단계 집계 호출의 기간 인자를 정책에 따라 내린다. 실행 단계 목록을 돌려준다.

    기록(``execution.date_semantics``)은 네 층을 나눈다: 의미 graph의 기간 값, 코드가 푼
    범위, 실제 요청 인자, 그 요청 인자의 provider 의미가 계약으로 확인되었는지.
    """
    spec = get_operator(transformation.operator)
    if spec is None or not spec.accepts_period:
        return [step]
    value = transformation.params.get(spec.PERIOD_PARAM)
    semantics = tims_contract.date_argument_semantics(value, contract)
    try:
        span = _interpreted_range(value, reference_date)
    except CompilerError:
        span = None
    record = {
        "value": value,
        "kind": semantics["kind"],
        "interpreted_range": None if span is None else periods.describe_period(*span),
        "reference_date": (None if reference_date is None
                           or semantics["kind"] != tims_contract.DATE_RELATIVE
                           else reference_date.strftime("%Y%m%d")),
        "policy": date_policy,
        "lowering": "passthrough",
        "request": [value] if value is not None else [],
        "provider": semantics["status"],
        "requires": semantics["requires"],
        "missing": semantics["missing"],
    }
    execution.date_semantics[transformation.id] = record
    if (date_policy == DATE_POLICY_LEGACY
            or semantics["status"] != tims_contract.SEMANTICS_UNVERIFIED):
        return [step]

    def unverified(reason):
        return CompilerError(
            f"{transformation.id}: 기간 {value!r}의 실행 의미를 TIMS 계약으로 확인할 수 "
            f"없습니다. {reason}",
            code="DATE_EXECUTION_UNVERIFIED",
            user_message=(
                "질문의 기간을 해석했지만, TIMS가 이 기간을 같은 뜻으로 조회한다는 계약이 "
                "확인되지 않아 계산하지 않았습니다."
                + (f" (해석한 기간: {record['interpreted_range']})"
                   if record["interpreted_range"] else "")
            ),
            context={"template": plan.template, "date_semantics": dict(record),
                     "reason": reason},
        )

    if span is None:
        raise unverified("연속 기간으로 풀 수 없는 값이라 다른 요청으로 바꿀 수 없습니다.")
    start, end = span
    if contract.satisfied("range_inclusive"):
        explicit = periods.describe_period(start, end)
        step.arguments[spec.PERIOD_PARAM] = explicit
        record.update(lowering="explicit_range", request=[explicit],
                      provider=tims_contract.SEMANTICS_CONFIRMED,
                      requires=["range_inclusive"], missing=[])
        return [step]
    days = (end - start).days + 1
    reducer = (step.arguments.get(spec.REDUCER_PARAM) if spec.accepts_reducer
               else spec.inherent_reducer)
    if reducer is None and spec.accepts_reducer:
        reducer = TOOL_DEFAULT_REDUCER
    listed = [name for name in ("dimension", "order", "limit")
              if step.arguments.get(name) is not None]
    ok, reason, requires = tims_contract.daily_composition(
        spec.tool_name, reducer, grouped_arguments=listed, days=days, contract=contract,
    )
    record["composition"] = {"reducer": reducer, "days": days, "ok": ok,
                             "reason": reason, "requires": requires}
    if not ok:
        raise unverified(
            f"명시 범위에는 range_inclusive가, 하루 단위 합성에는 {reason}")
    steps, keys = [], []
    for index, day in enumerate(periods.days_of({
            "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
            "label": record["interpreted_range"]}), start=1):
        daily = ToolStep(
            id=f"{transformation.id}#d{index}", operator=step.operator,
            tool_name=step.tool_name, arguments=dict(step.arguments),
            output_bindings={spec.output.extraction: f"{output.id}#d{index}"},
            covers=[transformation.id],
            argument_sources=dict(step.argument_sources),
            assumptions=list(requires),
        )
        daily.arguments[spec.PERIOD_PARAM] = day["start"]
        daily.argument_sources[spec.PERIOD_PARAM] = (
            f"{transformation.id}.params.{spec.PERIOD_PARAM}[{day['start']}]")
        steps.append(daily)
        keys.append(f"{output.id}#d{index}")
    steps.append(ToolStep(
        id=f"{transformation.id}.combine_days", operator=analysis_ops.COMBINE_DAYS,
        tool_name=f"local:{analysis_ops.COMBINE_DAYS}",
        arguments={"reducer": tims_contract.COMPOSABLE_REDUCERS[reducer],
                   "days": [item.arguments[spec.PERIOD_PARAM] for item in steps]},
        output_bindings={WHOLE_RESULT: output.id}, kind=STEP_LOCAL,
        covers=[transformation.id], inputs=keys,
        argument_sources={"reducer": f"{transformation.id}.params.{spec.REDUCER_PARAM}"},
    ))
    record.update(lowering="daily_composition",
                  request=[item.arguments[spec.PERIOD_PARAM] for item in steps[:-1]],
                  provider=tims_contract.SEMANTICS_CONFIRMED, requires=requires,
                  missing=[])
    return steps


#: 의미 graph가 정한 구간의 정의. 호출 하나로 합치려면 TIMS의 확인된 값이 이것과
#: 같아야 한다. 상대 기간은 compiler가 Asia/Seoul 기준일로 푼다(pipeline clock).
SEMANTIC_GROUP_DEFINITION = {
    "bucket_week_start": "monday",
    "bucket_partial": "clip_to_period",
    "bucket_empty": "undefined",
    "relative_date_reference": "Asia/Seoul calendar",
}


def choose_group_strategy(transformation, output, combine, spec, contract, *,
                          require_day_records=False):
    """구간별 집계를 내릴 전략과, 쓰지 않은 전략의 이유를 돌려준다.

    순서: 호출 하나로 합침 → 구간 범위 호출 → 일 단위 호출. 앞의 것일수록 호출
    수가 적다. 전략마다 필요한 계약 항목이 확인되지 않으면 쓰지 않는다.

    ``require_day_records``가 참이면(condition_check 경로) 일 단위 전략은 Tool의 기록이
    하루 하나에만 속한다는 계약(``day_records:<tool>``)도 요구한다. 기본 경로는 이 항목을
    가정으로만 기록한다(기존 동작).
    """
    rejected = []

    def reject(strategy, reason):
        rejected.append({"strategy": strategy.name, "reason": reason})

    fused = tims_contract.FUSED_BUCKET_ROLLUP
    if not _fusable_shape(spec, output, combine):
        reject(fused, "Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다")
    else:
        missing = contract.missing(fused)
        differing = [
            key for key, value in SEMANTIC_GROUP_DEFINITION.items()
            if key in fused.requires and key not in missing
            and contract.items[key].value != value
        ]
        if missing:
            reject(fused, "확인되지 않은 계약: " + ", ".join(missing))
        elif differing:
            reject(fused, "의미 graph의 구간 정의와 다른 계약: " + ", ".join(differing))
        else:
            return fused, rejected

    if spec is None or not spec.accepts_period:
        reject(tims_contract.RANGE_PARTITION, "Tool이 기간을 받지 않습니다")
        reject(tims_contract.DAILY_PARTITION, "Tool이 기간을 받지 않습니다")
        return None, rejected

    ranged = tims_contract.RANGE_PARTITION
    missing = contract.missing(ranged)
    if not missing:
        return ranged, rejected
    reject(ranged, "확인되지 않은 계약: " + ", ".join(missing))

    daily = tims_contract.DAILY_PARTITION
    inner = transformation.params.get(spec.REDUCER_PARAM)
    missing = contract.missing(daily)
    if missing:
        reject(daily, "확인되지 않은 계약: " + ", ".join(missing))
    elif inner not in tims_contract.DECOMPOSABLE_INNER:
        reject(daily, f"구간 안 집계 {inner}는 하루 값들로 정확히 다시 만들 수 없습니다")
    elif require_day_records and not tims_contract.daily_composition(
            spec.tool_name, inner, contract=contract)[0]:
        reject(daily, tims_contract.daily_composition(
            spec.tool_name, inner, contract=contract)[1])
    else:
        return daily, rejected
    return None, rejected


def _sources_for(transformation):
    sources = {}
    spec = get_operator(transformation.operator)
    for port in transformation.inputs:
        port_spec = spec.input(port) if spec else None
        if port_spec is not None and not port_spec.semantic_only:
            sources[port_spec.arg_name] = f"{transformation.id}.inputs.{port}"
    for name in transformation.params:
        sources[name] = f"{transformation.id}.params.{name}"
    return sources


def _single_combiner(transformation, output, consumers, plan):
    users = consumers.get(output.id) or []
    if len(users) != 1 or not analysis_ops.is_analysis_operator(users[0].operator):
        raise CompilerError(
            f"{transformation.id}: 구간별 값 {output.id}를 소비하는 분석 연산자가 "
            "하나여야 합니다.",
            code="UNCONSUMED_GROUPS",
            context={"template": plan.template, "node": output.id},
        )
    return users[0]


def _fusable_shape(spec, output, combine):
    """Tool이 이 구간·집계 조합을 호출 하나의 인자로 받을 수 있는가.

    인자 모양만 본다. 같은 계산인지는 ``choose_group_strategy``가 계약으로 본다.
    """
    capability = getattr(spec, "bucket_rollup", None)
    if capability is None or combine.operator != analysis_ops.REDUCE_GROUPS:
        return False
    bucket = output.attributes[analysis_ops.GROUP_BY].get("bucket")
    return (
        bucket in spec.param_enums.get(capability.bucket_param, frozenset())
        and combine.params.get("reducer")
        in spec.param_enums.get(capability.rollup_param, frozenset())
    )


def _fused_step(transformation, combine, output, spec, nodes, plan):
    capability = spec.bucket_rollup
    step = _compile_step(transformation, nodes, plan)
    bucket = output.attributes[analysis_ops.GROUP_BY]["bucket"]
    step.id = f"{transformation.id}+{combine.id}"
    step.arguments[capability.bucket_param] = bucket
    step.arguments[capability.rollup_param] = combine.params["reducer"]
    step.argument_sources[capability.bucket_param] = f"{output.id}.group_by.bucket"
    step.argument_sources[capability.rollup_param] = f"{combine.id}.params.reducer"
    step.output_bindings = {spec.output.extraction: combine.outputs[0]}
    step.covers = [transformation.id, combine.id]
    step.assumptions = list(tims_contract.FUSED_BUCKET_ROLLUP.requires)
    return step


def _partition_steps(transformation, output, spec, nodes, plan, execution, *,
                     reference_date, strategy):
    """기간을 나눠 같은 조건으로 호출하고, 구간별 값을 모으는 로컬 단계를 붙인다.

    ``range_partition``은 구간마다 날짜 범위로 한 번, ``daily_partition``은 하루마다
    한 번 부른다. 일 단위일 때는 COLLECT_GROUPS가 구간 안 집계를 하루 값들에 다시
    적용해 구간 값을 만든다(sum, max, min만 허용).
    """
    bucket = output.attributes[analysis_ops.GROUP_BY]["bucket"]
    period = transformation.params.get(spec.PERIOD_PARAM)
    start, end = periods.resolve_period(period, reference_date=reference_date)
    groups = periods.partition(start, end, bucket)
    daily = strategy is tims_contract.DAILY_PARTITION
    if daily and (end - start).days + 1 > tims_contract.MAX_DAILY_CALLS:
        raise CompilerError(
            f"{transformation.id}: 일 단위 호출이 {(end - start).days + 1}번 필요해 "
            f"상한 {tims_contract.MAX_DAILY_CALLS}을 넘습니다.",
            code="UNSUPPORTED_PARTITION_SIZE",
            user_message="기간이 길어 구간별 계산에 필요한 조회 수가 너무 많습니다.",
            context={"template": plan.template, "period": period},
        )
    execution.periods[transformation.id] = {
        "period": period,
        "resolved": periods.describe_period(start, end),
        "reference_date": (
            reference_date.strftime("%Y%m%d")
            if reference_date is not None and period in periods.RELATIVE_PERIODS
            else None
        ),
        "bucket": bucket,
        "boundary": periods.BOUNDARY_RULES[bucket],
        "groups": [group["label"] for group in groups],
        "strategy": strategy.name,
    }
    steps = []
    members = []
    inner = transformation.params.get(spec.REDUCER_PARAM)
    for group_index, group in enumerate(groups, start=1):
        spans = periods.days_of(group) if daily else [group]
        keys = []
        for day_index, span in enumerate(spans, start=1):
            step = _compile_step(transformation, nodes, plan)
            suffix = f"{group_index}.{day_index}" if daily else f"{group_index}"
            key = f"{output.id}#{suffix}"
            step.id = f"{transformation.id}#{suffix}"
            step.arguments[spec.PERIOD_PARAM] = (
                span["start"] if daily else periods.date_argument(span)
            )
            step.argument_sources[spec.PERIOD_PARAM] = (
                f"{output.id}.group_by.bucket[{group['label']}] "
                f"⊂ {transformation.id}.params.{spec.PERIOD_PARAM}"
            )
            step.output_bindings = {spec.output.extraction: key}
            step.group = dict(group)
            step.assumptions = list(strategy.requires) + (
                [tims_contract.day_records_key(spec.tool_name)] if daily else [])
            steps.append(step)
            keys.append(key)
        members.append(keys)
    steps.append(ToolStep(
        id=f"{transformation.id}.collect",
        operator=analysis_ops.COLLECT_GROUPS,
        tool_name=f"local:{analysis_ops.COLLECT_GROUPS}",
        arguments={
            "groups": [dict(group) for group in groups],
            "members": members,
            "reducer": tims_contract.DECOMPOSABLE_INNER[inner] if daily else None,
        },
        output_bindings={WHOLE_RESULT: output.id},
        kind=STEP_LOCAL,
        covers=[transformation.id],
        argument_sources={"groups": f"{output.id}.group_by.bucket",
                          "reducer": f"{transformation.id}.params.{spec.REDUCER_PARAM}"},
        inputs=[key for keys in members for key in keys],
    ))
    return steps


def _local_step(transformation):
    return ToolStep(
        id=transformation.id,
        operator=transformation.operator,
        tool_name=f"local:{transformation.operator}",
        arguments=dict(transformation.params),
        output_bindings={WHOLE_RESULT: transformation.outputs[0]},
        kind=STEP_LOCAL,
        covers=[transformation.id],
        argument_sources={
            name: f"{transformation.id}.params.{name}"
            for name in transformation.params
        },
        inputs=[ref.node_id for ref in transformation.inputs.values()],
    )


def _compile_step(transformation, nodes, plan):
    spec = get_operator(transformation.operator)
    if spec is None:
        raise CompilerError(
            f"{transformation.id}: 등록되지 않은 operator입니다: "
            f"{transformation.operator}",
            code="UNKNOWN_OPERATOR",
            context={"template": plan.template},
        )

    arguments = {}
    for port, ref in transformation.inputs.items():
        port_spec = spec.input(port)
        if port_spec is None:
            raise CompilerError(
                f"{transformation.id}: {spec.name}에 없는 input port입니다: "
                f"{port}",
                code="UNKNOWN_PORT",
                context={"template": plan.template},
            )
        node = nodes.get(ref.node_id)
        if node is None:
            raise CompilerError(
                f"{transformation.id}.{port}가 존재하지 않는 concept를 "
                f"참조합니다: {ref.describe()}",
                code="UNKNOWN_REFERENCE",
                context={"template": plan.template},
            )

        if port_spec.semantic_only:
            # EVENT처럼 Tool 인자로 나타나지 않는 의미 port. graph와 검증에는
            # 남지만 호출 인자는 만들지 않는다.
            continue

        if node.source in PRODUCED_SOURCES:
            # Tool이 만들 값이므로 실행 직전에 해소할 참조로 남긴다.
            arguments[port_spec.arg_name] = ValueRef(ref.node_id, ref.field)
            continue

        value = _literal_value(transformation, port, node, ref, plan)
        if value is None or (value == "" and not port_spec.required):
            if port_spec.required:
                raise CompilerError(
                    f"{transformation.id}.{port}에 필요한 값이 비어 "
                    f"있습니다: {ref.describe()}",
                    code="EMPTY_REQUIRED_INPUT",
                    context={"template": plan.template},
                )
            continue
        arguments[port_spec.arg_name] = value

    for name, value in transformation.params.items():
        if name not in spec.params:
            raise CompilerError(
                f"{transformation.id}: {spec.name}이 지원하지 않는 "
                f"parameter입니다: {name}",
                code="UNKNOWN_PARAM",
                context={"template": plan.template},
            )
        if value is None:
            continue
        arguments[name] = value

    return ToolStep(
        id=transformation.id,
        operator=spec.name,
        tool_name=spec.tool_name,
        arguments=arguments,
        output_bindings=_output_bindings(transformation, spec, plan),
        covers=[transformation.id],
        argument_sources={
            name: source for name, source in _sources_for(transformation).items()
            if name in arguments
        },
    )


def _literal_value(transformation, port, node, ref, plan):
    if ref.field is None:
        return node.value
    if not isinstance(node.value, dict):
        raise CompilerError(
            f"{transformation.id}.{port}가 {node.id}의 field "
            f"{ref.field!r}를 요구하지만 값이 object가 아닙니다.",
            code="INVALID_FIELD_REFERENCE",
            context={"template": plan.template},
        )
    return node.value.get(ref.field)


def _output_bindings(transformation, spec, plan):
    if spec.output is None:
        if transformation.outputs:
            raise CompilerError(
                f"{transformation.id}: {spec.name}은 output을 만들지 않습니다.",
                code="UNEXPECTED_OUTPUT",
                context={"template": plan.template},
            )
        return {}
    if len(transformation.outputs) != 1:
        raise CompilerError(
            f"{transformation.id}: {spec.name}은 output concept가 정확히 "
            f"1개여야 합니다. (현재 {len(transformation.outputs)}개)",
            code="OUTPUT_ARITY",
            context={"template": plan.template},
        )
    return {spec.output.extraction: transformation.outputs[0]}


# -- lowering 검증 ------------------------------------------------------------


def _mismatch(message, plan, **context):
    return CompilerError(
        f"실행 단계가 의미 graph와 다릅니다: {message}",
        code="LOWERING_MISMATCH",
        user_message="계산 계획을 만드는 중 조건이 어긋나 실행하지 않았습니다.",
        context={"template": plan.template, **context},
    )


def verify_lowering(plan, execution, *, reference_date=None,
                    contract=tims_contract.DEFAULT_CONTRACT):
    """실행 단계가 의미 graph의 조건과 집계를 빠짐없이 옮겼는지 확인한다.

    compiler의 결과를 다시 읽는 방어선이다. 인자 형식은 Tool schema가, 계획의
    구조는 validator가 보지만, "이 호출이 질문의 그 계산인가"는 둘 다 보지 않는다.

    검증하는 것(내부 일관성)
    - 모든 의미 단계가 실행 단계로 수행된다.
    - 각 호출이 그 의미 단계의 조건(기간·범위·택시 유형 등)을 그대로 갖는다.
    - 구간별 집계에 쓴 전략이 ``contract``에서 허용된 것이다.
    - 기간 분할이 기간을 빈틈과 겹침 없이 덮고, 구간 안/밖 집계가 뒤바뀌지 않았다.

    검증할 수 없는 것(외부 계약): TIMS가 실제로 각 단계의 ``assumptions``에 적힌
    항목대로 동작하는지. 예를 들어 단일 날짜가 정말 그 하루를 뜻하는지는 호출
    결과만으로 알 수 없다.
    """
    nodes = {node.id: node for node in plan.concepts}
    steps = {step.id: step for step in execution.steps}
    for transformation in plan.transformations:
        covering = [
            steps[step_id]
            for step_id in execution.semantic_map.get(transformation.id, [])
        ]
        if not covering:
            raise _mismatch(f"{transformation.id}를 수행하는 단계가 없습니다.", plan,
                            transformation=transformation.id)
        if analysis_ops.is_analysis_operator(transformation.operator):
            _verify_combination(transformation, covering, plan)
            continue
        tools = [step for step in covering if not step.is_local]
        output = nodes.get(transformation.outputs[0]) if transformation.outputs else None
        if not tools:
            raise _mismatch(f"{transformation.id}에 Tool 호출이 없습니다.", plan,
                            transformation=transformation.id)
        grouped = analysis_ops.is_grouped(output)
        partitioned = grouped and any(step.group is not None for step in tools)
        date_record = execution.date_semantics.get(transformation.id) or {}
        relowered = date_record.get("lowering", "passthrough") != "passthrough"
        for step in tools:
            for name, value in transformation.params.items():
                if value is None:
                    continue
                if (partitioned or relowered) and name == "date":
                    continue
                if step.arguments.get(name) != value:
                    raise _mismatch(
                        f"{step.id}의 {name}가 {transformation.id}의 값과 다릅니다: "
                        f"{step.arguments.get(name)!r} != {value!r}",
                        plan, step=step.id, param=name,
                    )
            for port in transformation.inputs:
                spec = get_operator(transformation.operator)
                port_spec = spec.input(port) if spec else None
                if port_spec is None or port_spec.semantic_only:
                    continue
                if port_spec.arg_name not in step.arguments and port_spec.required:
                    raise _mismatch(f"{step.id}에 {port} 입력이 없습니다.", plan,
                                    step=step.id, port=port)
        if not grouped:
            if relowered:
                _verify_relowered_period(transformation, date_record, tools, covering,
                                         plan, reference_date, contract)
            elif len(tools) != 1:
                raise _mismatch(f"{transformation.id}가 여러 호출로 나뉘었습니다.",
                                plan, transformation=transformation.id)
            continue
        strategy = (execution.lowering.get(transformation.id) or {}).get("strategy")
        allowed = {
            item.name: contract.allows(item)
            for item in (tims_contract.FUSED_BUCKET_ROLLUP,
                         tims_contract.RANGE_PARTITION,
                         tims_contract.DAILY_PARTITION)
        }
        if not allowed.get(strategy):
            raise _mismatch(
                f"{transformation.id}의 lowering 전략 {strategy!r}은 계약에서 허용되지 "
                "않습니다.",
                plan, transformation=transformation.id,
            )
        if partitioned:
            _verify_partition(transformation, output, tools, covering, plan,
                              reference_date, strategy)
        else:
            if strategy != tims_contract.FUSED_BUCKET_ROLLUP.name:
                raise _mismatch(f"{transformation.id}의 호출이 전략과 다릅니다.", plan,
                                transformation=transformation.id)
            _verify_fused(transformation, output, tools, plan)


def _verify_relowered_period(transformation, record, tools, covering, plan,
                             reference_date, contract):
    """기간 인자를 명시 범위나 하루 단위로 바꾼 호출이 원래 기간과 같은지 다시 본다."""
    value = transformation.params.get("date")
    start, end = periods.resolve_period(value, reference_date=reference_date)
    actual = [step.arguments.get("date") for step in tools]
    lowering = record.get("lowering")
    if lowering == "explicit_range":
        if not contract.satisfied("range_inclusive") or actual != [
                periods.describe_period(start, end)]:
            raise _mismatch(f"{transformation.id}의 명시 범위 요청이 기간 {value}와 "
                            f"다릅니다: {actual}", plan, transformation=transformation.id)
        return
    if lowering != "daily_composition":
        raise _mismatch(f"{transformation.id}의 기간 lowering {lowering!r}을 알 수 없습니다.",
                        plan, transformation=transformation.id)
    expected = [day["start"] for day in periods.days_of({
        "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"), "label": value})]
    if actual != expected:
        raise _mismatch(f"{transformation.id}의 하루 단위 호출이 기간 {value}를 빈틈없이 "
                        f"덮지 않습니다: {actual}", plan, transformation=transformation.id)
    spec = get_operator(transformation.operator)
    reducer = (transformation.params.get(spec.REDUCER_PARAM) if spec.accepts_reducer
               else spec.inherent_reducer) or TOOL_DEFAULT_REDUCER
    ok, reason, _ = tims_contract.daily_composition(
        spec.tool_name, reducer, days=len(expected), contract=contract)
    combine = [step for step in covering if step.operator == analysis_ops.COMBINE_DAYS]
    keys = [key for step in tools for key in step.output_bindings.values()]
    if not ok or len(combine) != 1 or combine[0].inputs != keys or combine[0].arguments.get(
            "reducer") != tims_contract.COMPOSABLE_REDUCERS.get(reducer):
        raise _mismatch(f"{transformation.id}의 하루 값 합성이 계약·집계와 맞지 않습니다. "
                        f"{reason}", plan, transformation=transformation.id)


def _verify_fused(transformation, output, tools, plan):
    (step,) = tools
    spec = get_operator(transformation.operator)
    capability = spec.bucket_rollup
    combine_ids = [item for item in step.covers if item != transformation.id]
    combine = next(
        (item for item in plan.transformations if item.id in combine_ids), None,
    )
    bucket = output.attributes[analysis_ops.GROUP_BY]["bucket"]
    expected = {
        capability.bucket_param: bucket,
        capability.inner_param: transformation.params.get(capability.inner_param),
        capability.rollup_param: None if combine is None else combine.params.get("reducer"),
    }
    for name, value in expected.items():
        if value is None or step.arguments.get(name) != value:
            raise _mismatch(
                f"{step.id}의 {name}가 의미 graph와 다릅니다: "
                f"{step.arguments.get(name)!r} != {value!r}",
                plan, step=step.id, param=name,
            )


def _verify_partition(transformation, output, tools, covering, plan,
                      reference_date, strategy):
    spec = get_operator(transformation.operator)
    period = transformation.params.get(spec.PERIOD_PARAM)
    start, end = periods.resolve_period(period, reference_date=reference_date)
    bucket = output.attributes[analysis_ops.GROUP_BY]["bucket"]
    groups = periods.partition(start, end, bucket)
    daily = strategy == tims_contract.DAILY_PARTITION.name
    if daily:
        expected_members = [[day["start"] for day in periods.days_of(group)]
                            for group in groups]
    else:
        expected_members = [[periods.date_argument(group)] for group in groups]
    expected = [item for members in expected_members for item in members]
    actual = [step.arguments.get(spec.PERIOD_PARAM) for step in tools]
    if actual != expected:
        raise _mismatch(
            f"{transformation.id}의 구간 호출이 기간 {period}를 빈틈없이 나누지 "
            f"않습니다: {actual}",
            plan, transformation=transformation.id,
        )
    for step in tools:
        if step.arguments.get(spec.REDUCER_PARAM) != transformation.params.get(
            spec.REDUCER_PARAM,
        ):
            raise _mismatch(f"{step.id}의 구간 안 집계가 다릅니다.", plan,
                            step=step.id)
    collect = [step for step in covering if step.operator == analysis_ops.COLLECT_GROUPS]
    if len(collect) != 1 or collect[0].output_bindings.get(WHOLE_RESULT) != output.id:
        raise _mismatch(f"{output.id}를 모으는 단계가 없습니다.", plan,
                        node=output.id)
    by_key = {key: step for step in tools for key in step.output_bindings.values()}
    members = collect[0].arguments.get("members") or []
    member_dates = [
        [by_key[key].arguments.get(spec.PERIOD_PARAM) if key in by_key else None
         for key in keys]
        for keys in members
    ]
    if member_dates != expected_members:
        raise _mismatch(f"{output.id}의 구간 구성이 기간 분할과 다릅니다.", plan,
                        node=output.id)
    inner = transformation.params.get(spec.REDUCER_PARAM)
    expected_reducer = tims_contract.DECOMPOSABLE_INNER.get(inner) if daily else None
    if daily and expected_reducer is None:
        raise _mismatch(f"{transformation.id}의 구간 안 집계 {inner}는 일 단위로 "
                        "다시 만들 수 없습니다.", plan, transformation=transformation.id)
    if collect[0].arguments.get("reducer") != expected_reducer:
        raise _mismatch(f"{output.id}를 모으는 집계가 구간 안 집계와 다릅니다.", plan,
                        node=output.id)


def _verify_combination(transformation, covering, plan):
    local = [step for step in covering if step.is_local]
    tools = [step for step in covering if not step.is_local]
    if tools:
        # 호출 하나로 합쳐진 경우. 인자는 _verify_fused가 본다.
        if transformation.operator != analysis_ops.REDUCE_GROUPS:
            raise _mismatch(
                f"{transformation.id}({transformation.operator})는 Tool 호출로 "
                "합칠 수 없습니다.",
                plan, transformation=transformation.id,
            )
        return
    if len(local) != 1:
        raise _mismatch(f"{transformation.id}의 로컬 단계가 하나가 아닙니다.", plan,
                        transformation=transformation.id)
    step = local[0]
    expected_inputs = [ref.node_id for ref in transformation.inputs.values()]
    if (step.operator != transformation.operator
            or step.arguments != transformation.params
            or step.inputs != expected_inputs):
        raise _mismatch(f"{step.id}가 {transformation.id}와 다릅니다.", plan,
                        step=step.id)
