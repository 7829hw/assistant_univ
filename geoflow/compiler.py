# -*- coding: utf-8 -*-
"""GeoFlowPlan(의미 graph) → ExecutionPlan(실행 단계) 변환(lowering).

여기서 처음으로 semantic operator가 실제 Tool 이름과 argument 이름에 묶인다.
Planner도 template도 Tool argument 이름을 직접 지정하지 않는다.

대부분의 변환은 Tool 호출 하나가 된다. 구간별 집계는 책임이 다른 두 경로로 내려간다
(``tims_contract.PATH_*``).

1. **업체 Tool에 계산을 위임(provider_delegated).** TIMS operator가 ``bucket_rollup``을
   선언했고 구간별 값을 합치는(REDUCE_GROUPS) 경우다. 구간 안 집계 변환과 합치는
   변환이 bucket/aggregation/rollup 호출 하나가 되고, 인자마다 어느 의미 단계에서
   왔는지 ``argument_sources``에 남긴다. 검증하는 것은 Tool 선택, 집계 단계 ↔ 인자
   매핑, 인자 조합, 조건 보존이다(scope 출처와 반환값 ↔ 답변은 실행기·답변이 본다).
   질문이 정하지 않은 구간 정의(주 시작일, 부분 구간, 빈 구간, 상대 날짜 기준)는
   제공자의 정의를 따르고 ``lowering``에 그렇게 남긴다. GeoFlow의 로컬 정책과 같다는
   증명은 요구하지 않는다. 질문이 정의를 명시했으면 계약이 그 정의를 보장할 때만 쓴다.
2. **기간을 나눠 호출한 뒤 로컬 재계산(local_recomputation).** 위임할 수 없는 경우다
   (구간을 고르는 SELECT_GROUP, bucket을 받지 않는 Tool, 질문이 정한 구간 정의를 Tool이
   보장하지 못함). 기간을 명시 날짜 구간으로 나누어 구간마다 같은 조건으로 호출하고,
   결과(구간별 값 자체)를 로컬에서 합치거나 고른다. 분해 전후 계산이 같다는 근거(날짜
   경계 계약, 기록의 날짜 귀속, 집계·측정값의 합성 가능성)가 모두 있어야 한다. 기간을
   날짜로 풀 수 없으면 계획을 만들지 않는다. 구간 정의는 애플리케이션 정책
   (``geoflow/periods.py``)이거나 질문이 정한 것이다.

두 경로는 서로의 근거를 대신하지 않는다. 로컬 재계산이 불가능해도 위임 호출은 막지
않고, 위임 호출이 가능해도 로컬 재계산이 같은 값이라고 보지 않는다.

끝에 ``verify_lowering``이 실행 단계를 의미 graph와 다시 대조한다. 조건이 빠지거나
구간 안/밖 집계가 뒤바뀐 lowering은 실행하지 않는다.
"""

from geoflow import analysis_ops, calendar_terms, measures, periods, tims_contract
from geoflow.errors import CompilerError
from geoflow.operator_registry import TOOL_DEFAULT_REDUCER, get_operator
from geoflow.types import (
    STEP_LOCAL,
    WHOLE_RESULT,
    CoreConcept,
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
                 date_policy=DATE_POLICY_LEGACY, delegation=None):
    """검증을 통과한 plan을 topological order의 실행 단계로 만든다.

    ``reference_date``는 상대 기간(last_month 등)을 날짜로 풀 기준일이다. 기간을
    로컬에서 나눠야 할 때만 쓰며, 없으면 그런 계획은 만들지 않는다.
    ``contract``는 TIMS 계약의 확인 상태다. 구간별 집계를 어떤 호출로 내릴지는
    이 계약이 허용하는 전략 중에서만 고른다(``geoflow/tims_contract.py``).
    ``date_policy``는 위 ``DATE_POLICY_*`` 설명을 따른다.
    ``delegation``은 질문이 정하지 않은 구간 정의를 제공자에게 맡기는 위임 경로를 허용하는가.
    None이면 ``date_policy``를 따른다(legacy는 허용, guaranteed는 애플리케이션 정의와 같다는
    계약이 있을 때만 호출 하나로 합침).
    """
    if date_policy not in (DATE_POLICY_LEGACY, DATE_POLICY_GUARANTEED):
        raise ValueError(f"알 수 없는 date_policy: {date_policy!r}")
    if delegation is None:
        delegation = date_policy == DATE_POLICY_LEGACY
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
            transformation, output, combine, spec, contract, delegation=delegation,
        )
        execution.lowering[transformation.id] = lowering_record(
            strategy, rejected, transformation, output, spec, contract,
            delegation=delegation,
        )
        if strategy is None:
            raise _no_strategy_error(transformation, output, combine, spec, contract,
                                     rejected, plan, delegation=delegation)
        if strategy is tims_contract.FUSED_BUCKET_ROLLUP:
            execution.steps.append(_fused_step(
                transformation, combine, output, spec, nodes, plan,
            ))
            fused.add(combine.id)
            execution.unobserved[output.id] = (
                "TIMS bucket/rollup 호출 안에서 계산되어 구간별 값은 반환되지 않습니다."
            )
            # 기간 인자는 그대로 넘긴다. 상대 기간의 경계는 제공자가 정한다.
            _record_passthrough_date(transformation, output, spec, execution, reference_date,
                                     contract, date_policy)
            continue
        execution.steps.extend(_partition_steps(
            transformation, output, spec, nodes, plan, execution,
            reference_date=reference_date, strategy=strategy, contract=contract,
        ))

    for step in execution.steps:
        for covered in step.covers:
            execution.semantic_map.setdefault(covered, []).append(step.id)
    verify_lowering(plan, execution, reference_date=reference_date,
                    contract=contract, delegation=delegation)
    return execution


#: 주 시작 요일에 따라 기간이 달라지는 상대 기간.
WEEK_PERIODS = frozenset({"last_week", "this_week"})

#: 기간 인자를 누가 해석하는가. passthrough는 제공자, 명시 범위·하루 합성은 애플리케이션.
DATE_BY_PROVIDER = "provider"
DATE_BY_APPLICATION = "application"


def _interpreted_range(value, reference_date, week_start=periods.DEFAULT_WEEK_START):
    """기간 값을 코드의 해석(Asia/Seoul 달력, 양 끝 포함)으로 푼다. 풀 수 없으면 None."""
    kind = tims_contract.date_argument_kind(value)
    if kind not in (tims_contract.DATE_SINGLE, tims_contract.DATE_RANGE,
                    tims_contract.DATE_RELATIVE):
        return None
    if kind == tims_contract.DATE_RELATIVE and reference_date is None:
        return None
    return periods.resolve_period(value, reference_date=reference_date,
                                  week_start=week_start)


def _date_record(value, *, reference_date, contract, date_policy,
                 week_start=periods.DEFAULT_WEEK_START):
    """기간 인자 하나의 기록. 의미 graph의 값, 코드가 푼 범위, 요청 인자, provider 의미 확인."""
    semantics = tims_contract.date_argument_semantics(value, contract)
    try:
        span = _interpreted_range(value, reference_date, week_start)
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
        # 요청 인자를 그대로 넘기면 그 기간의 정확한 경계는 제공자가 정한다.
        "responsibility": DATE_BY_PROVIDER,
        "request": [value] if value is not None else [],
        "provider": semantics["status"],
        "requires": semantics["requires"],
        "missing": semantics["missing"],
    }
    if value in periods.RELATIVE_PERIOD_POLICY:
        # interpreted_range를 만든 규칙. TIMS가 토큰을 같은 기간으로 읽는다는 계약은 없다.
        record["interpretation"] = relative_interpretation(value, week_start)
    return record, span


def relative_interpretation(value, week_start=periods.DEFAULT_WEEK_START):
    """상대 기간을 로컬에서 푼 규칙과 그 출처. 질문이 주 시작 요일을 정했으면 그 요일로 푼다."""
    rule = periods.RELATIVE_PERIOD_POLICY[value]
    if value in WEEK_PERIODS and week_start != periods.DEFAULT_WEEK_START:
        day = calendar_terms.VALUE_LABELS[week_start]
        return {"source": "question+" + periods.RELATIVE_PERIOD_POLICY_SOURCE,
                "rule": rule.replace("월요일", day), "week_start": week_start}
    return {"source": periods.RELATIVE_PERIOD_POLICY_SOURCE, "rule": rule}


def stated_period_week(calendar, period):
    """기간이 last_week·this_week이고 질문이 주 시작 요일을 정했으면 그 요일. 아니면 None."""
    return calendar.get(calendar_terms.WEEK_START) if period in WEEK_PERIODS else None


def period_week_guaranteed(contract, period, week_start):
    """토큰을 그대로 넘겨도 질문이 정한 주 시작 요일이 보장되는가.

    토큰의 기간 의미가 계약으로 확인되고(``date_argument_semantics``, 값 대조 포함), 제공자의 주
    정의(``bucket_week_start``)가 그 요일로 확인되어야 한다.
    """
    return (tims_contract.date_argument_semantics(period, contract)["status"]
            == tims_contract.SEMANTICS_CONFIRMED
            and tims_contract.requirement_guaranteed(
                contract, calendar_terms.WEEK_START, week_start)[0])


def _record_passthrough_date(transformation, output, spec, execution, reference_date, contract,
                             date_policy):
    """위임 호출의 기간 인자 기록. 호출은 바꾸지 않는다(condition 기록·검증 요약이 읽는다)."""
    if spec is None or not spec.accepts_period:
        return
    value = transformation.params.get(spec.PERIOD_PARAM)
    week = stated_period_week(group_calendar(output), value)
    record, _ = _date_record(value, reference_date=reference_date, contract=contract,
                             date_policy=date_policy,
                             week_start=week or periods.DEFAULT_WEEK_START)
    if week:
        record["calendar"] = {calendar_terms.WEEK_START: week}
    execution.date_semantics[transformation.id] = record


def _lower_period(transformation, step, output, plan, execution, *, reference_date,
                  contract, date_policy):
    """한 단계 집계 호출의 기간 인자를 정책에 따라 내린다. 실행 단계 목록을 돌려준다.

    기록(``execution.date_semantics``)은 네 층을 나눈다: 의미 graph의 기간 값, 코드가 푼
    범위, 실제 요청 인자, 그 요청 인자의 provider 의미가 계약으로 확인되었는지.

    질문이 주 시작 요일을 정했고 기간이 last_week·this_week이면, 토큰을 그대로 넘기는
    호출은 제공자의 주 정의를 쓰게 되므로 정책과 무관하게 넘기지 않는다. 계약이 허용하는
    다른 요청(그 요일로 푼 명시 범위, 하루 단위 합성)으로 바꾸고, 없으면 멈춘다.
    """
    spec = get_operator(transformation.operator)
    if spec is None or not spec.accepts_period:
        return [step]
    value = transformation.params.get(spec.PERIOD_PARAM)
    week_start = (plan.calendar or {}).get(calendar_terms.WEEK_START)
    stated_week = week_start if value in WEEK_PERIODS else None
    record, span = _date_record(
        value, reference_date=reference_date, contract=contract, date_policy=date_policy,
        week_start=stated_week or periods.DEFAULT_WEEK_START)
    execution.date_semantics[transformation.id] = record
    if stated_week:
        record["calendar"] = {calendar_terms.WEEK_START: stated_week}
        if period_week_guaranteed(contract, value, stated_week):
            return [step]
    elif (date_policy == DATE_POLICY_LEGACY
            or record["provider"] != tims_contract.SEMANTICS_UNVERIFIED):
        return [step]

    def unverified(reason):
        if stated_week:
            label = calendar_terms.describe(calendar_terms.WEEK_START, stated_week)
            return CompilerError(
                f"{transformation.id}: 질문이 정한 {label}로 기간 {value!r}를 조회할 방법이 "
                f"계약으로 확인되지 않았습니다. {reason}",
                code="CALENDAR_REQUIREMENT_UNSUPPORTED",
                user_message=(
                    f"질문에서 정한 {label}을 TIMS 조회가 보장하지 않아 계산하지 않았습니다. "
                    "TIMS 기본 주 정의로 바꿔 계산하지 않습니다."
                    + (f" (해석한 기간: {record['interpreted_range']})"
                       if record["interpreted_range"] else "")
                ),
                context={"template": plan.template, "date_semantics": dict(record),
                         "reason": reason, "calendar": dict(plan.calendar)},
            )
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
                      responsibility=DATE_BY_APPLICATION,
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
        measure=_measure_of(output),
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
                   "days": [item.arguments[spec.PERIOD_PARAM] for item in steps],
                   "empty_parts": empty_day_policy(contract)},
        output_bindings={WHOLE_RESULT: output.id}, kind=STEP_LOCAL,
        covers=[transformation.id], inputs=keys,
        argument_sources={"reducer": f"{transformation.id}.params.{spec.REDUCER_PARAM}"},
    ))
    record.update(lowering="daily_composition",
                  responsibility=DATE_BY_APPLICATION,
                  request=[item.arguments[spec.PERIOD_PARAM] for item in steps[:-1]],
                  provider=tims_contract.SEMANTICS_CONFIRMED, requires=requires,
                  missing=[])
    return steps


#: GeoFlow가 로컬 재계산에 쓰는 구간 정의(애플리케이션 정책, ``geoflow/periods.py``).
#: 질문의 뜻이 아니다. 위임 경로에는 쓰지 않는다. 위임을 허용하지 않는 프로필(strict)만
#: 제공자 호출이 이 정의와 같다는 계약이 있을 때 호출 하나로 합친다.
APPLICATION_GROUP_DEFINITION = {
    "bucket_week_start": "monday",
    "bucket_partial": "clip_to_period",
    "bucket_empty": "undefined",
    "relative_date_reference": "Asia/Seoul calendar",
}

#: 전략 선택 순서. 위임 호출이 가장 적은 호출이고 업체가 정한 인터페이스다.
GROUP_STRATEGIES = (tims_contract.FUSED_BUCKET_ROLLUP, tims_contract.RANGE_PARTITION,
                    tims_contract.DAILY_PARTITION)


def group_calendar(output):
    """구간별 node에 적힌, 질문이 명시한 구간 정의. 없으면 빈 dict."""
    return dict((output.attributes.get(analysis_ops.GROUP_BY) or {}).get(
        analysis_ops.CALENDAR) or {})


def strategy_problems(strategy, transformation, output, combine, spec, contract, *,
                      delegation=True):
    """전략을 이 구간별 집계에 쓸 수 없는 이유 목록. 비어 있으면 쓸 수 있다.

    위임(provider_delegated)과 로컬 재계산(local_recomputation)은 기준이 다르다.

    - 위임: Tool이 이 구간·집계 조합을 인자로 받고, 인자가 질문의 집계 단계를 뜻한다는
      계약(``strategy.requires``)이 확인될 것. 질문이 정의를 명시했다면 계약이 그 정의를
      보장할 것. 질문이 정하지 않은 정의(``strategy.delegates``)는 요구하지 않는다.
      ``delegation``이 거짓이면(위임을 허용하지 않는 프로필) 그 정의도 계약으로 확인되고
      애플리케이션 정의와 같아야 한다.
    - 로컬: 분해 전후가 같은 계산이라는 근거가 모두 있을 것(계약, 집계·측정값의 합성).
      위임 가능 여부와 무관하게 판단한다.
    """
    calendar = group_calendar(output)
    period = transformation.params.get(getattr(spec, "PERIOD_PARAM", "date"))
    if strategy.path == tims_contract.PATH_PROVIDER:
        if not _fusable_shape(spec, output, combine):
            return ["Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다"]
        problems = []
        missing = contract.missing(strategy)
        if missing:
            problems.append("확인되지 않은 계약: " + ", ".join(missing))
        bucket = output.attributes[analysis_ops.GROUP_BY]["bucket"]
        for key, value in calendar.items():
            if key == calendar_terms.WEEK_START and bucket != "week":
                continue   # 월 구간이면 주 시작 요일은 기간(last_week·this_week)에만 걸린다(아래).
            ok, reason = tims_contract.requirement_guaranteed(contract, key, value)
            if not ok:
                problems.append(f"질문이 정한 {calendar_terms.describe(key, value)}을 Tool "
                                f"호출이 표현하거나 보장하지 않습니다({reason})")
        week = stated_period_week(calendar, period)
        if week and not period_week_guaranteed(contract, period, week):
            problems.append(f"상대 기간 {period}를 질문이 정한 "
                            f"{calendar_terms.describe(calendar_terms.WEEK_START, week)}로 "
                            "조회한다는 계약이 없습니다(relative_date_reference·"
                            "bucket_week_start)")
        if not delegation:
            stated_items = {tims_contract.REQUIREMENT_ITEMS[key] for key in calendar}
            relevant = [key for key in strategy.delegates if key not in stated_items
                        and not (key == "bucket_week_start" and bucket != "week")
                        and not (key == "relative_date_reference"
                                 and period not in periods.RELATIVE_PERIODS)]
            unmet = [key for key in relevant if not contract.satisfied(key)]
            differing = [key for key in relevant if key not in unmet
                         and contract.items[key].value != APPLICATION_GROUP_DEFINITION[key]]
            if (period is not None and tims_contract.date_argument_semantics(
                    period, contract)["status"] == tims_contract.SEMANTICS_UNVERIFIED):
                problems.append(f"위임을 허용하지 않는 프로필이며 기간 인자 {period!r}의 뜻이 "
                                "계약으로 확인되지 않았습니다")
            if unmet:
                problems.append("위임을 허용하지 않는 프로필이며 확인되지 않은 계약: "
                                + ", ".join(unmet))
            if differing:
                problems.append("위임을 허용하지 않는 프로필이며 애플리케이션 구간 정의와 "
                                "다른 계약: " + ", ".join(differing))
        return problems

    if spec is None or not spec.accepts_period:
        return ["Tool이 기간을 받지 않습니다"]
    problems = []
    if calendar_terms.EMPTY in calendar:
        # 로컬 재계산은 값이 없는 구간을 0으로 넣거나 빼지 않고 멈춘다(EMPTY_GROUP_VALUE).
        problems.append(
            "질문이 정한 " + calendar_terms.describe(
                calendar_terms.EMPTY, calendar[calendar_terms.EMPTY])
            + "을 로컬 재계산이 구현하지 않습니다(값이 없는 구간이 있으면 멈춤)")
    if strategy is tims_contract.DAILY_PARTITION:
        inner = transformation.params.get(spec.REDUCER_PARAM)
        measure = _measure_of(output)
        if inner not in tims_contract.DECOMPOSABLE_INNER:
            problems.append(f"구간 안 집계 {inner}는 하루 값들로 정확히 다시 만들 수 없습니다")
        elif not measures.day_composable(measure, inner):
            # 계약 확인 여부와 무관한 수학 조건이다.
            problems.append(tims_contract.daily_composition(
                spec.tool_name, inner, contract=contract, measure=measure)[1])
    missing = contract.missing(strategy, spec.tool_name)
    if missing:
        problems.append("확인되지 않은 계약: " + ", ".join(missing))
    return problems


def choose_group_strategy(transformation, output, combine, spec, contract, *,
                          delegation=True):
    """구간별 집계를 내릴 전략과, 쓰지 않은 전략의 이유를 돌려준다.

    순서: 위임 호출 하나 → 구간 범위 호출 → 일 단위 호출. 각 전략은 자기 기준
    (``strategy_problems``)으로만 판단한다.
    """
    rejected = []
    for strategy in GROUP_STRATEGIES:
        problems = strategy_problems(strategy, transformation, output, combine, spec,
                                     contract, delegation=delegation)
        if not problems:
            return strategy, rejected
        rejected.append({"strategy": strategy.name, "path": strategy.path,
                         "reason": "; ".join(problems)})
    return None, rejected


#: 위임 경로가 검증하는 것. 앞의 넷은 compile(``verify_lowering``), 뒤의 둘은 실행기와 답변.
PROVIDER_CHECKS = (
    ("tool_selection", "측정값 subtype → operator → Tool(operator mapping)"),
    ("stage_mapping", "구간 안 집계 → aggregation, 구간 → bucket, 구간별 값의 집계 → rollup "
                      "(계약 inner_is_aggregation, rollup_unweighted)"),
    ("argument_combination", "bucket·rollup 짝, 구간 안 집계를 명시(기본값 미사용), "
                             "목록 인자(dimension·order·limit) 없음, schema enum"),
    ("condition_preservation", "기간·범위·택시 유형 등 조건이 호출 인자에 그대로 있음"),
    ("scope_provenance", "scope 인자가 사용자 입력이나 앞선 Tool 결과에서 옴(실행기)"),
    ("result_to_answer", "답변 수치가 Tool 반환값 그대로임(답변 생성)"),
)
#: 로컬 재계산 경로가 검증하는 것.
LOCAL_CHECKS = (
    ("tool_selection", "측정값 subtype → operator → Tool(operator mapping)"),
    ("partition_cover", "구간 분할이 기간을 빈틈·겹침 없이 덮음(질문이 정한 구간 제외 반영)"),
    ("boundary_contract", "날짜 경계 계약(single_date / range_inclusive) 확인"),
    ("record_attribution", "하루 단위 분할은 기록이 하루 하나에만 속한다는 계약 확인"),
    ("composability", "구간 안 집계와 측정값이 하루 값들로 정확히 다시 만들어짐"),
    ("empty_result", "값이 없는 날·구간은 0으로 채우지 않음(계약이 없으면 멈춤)"),
    ("condition_preservation", "모든 분할 호출이 같은 조건을 가짐"),
    ("scope_provenance", "scope 인자가 사용자 입력이나 앞선 Tool 결과에서 옴(실행기)"),
)


def lowering_record(strategy, rejected, transformation, output, spec, contract, *,
                    delegation=True):
    """어떤 경로를 썼고, 무엇을 검증했고, 어떤 의미를 누구에게 맡겼는지.

    ``semantics``는 구간 정의마다 값과 출처를 적는다: question(질문이 명시),
    provider(제공자 정의에 위임, 값은 provider_defined), application(애플리케이션 정책),
    contract(계약으로 확인된 제공자 값).
    """
    calendar = group_calendar(output)
    record = {"strategy": None if strategy is None else strategy.name,
              "path": None if strategy is None else strategy.path,
              "rejected": rejected}
    if strategy is None:
        record["calendar"] = calendar
        return record
    period = transformation.params.get(getattr(spec, "PERIOD_PARAM", "date"))
    relative = period in periods.RELATIVE_PERIODS
    semantics = {}
    bucket = output.attributes[analysis_ops.GROUP_BY]["bucket"]
    if strategy.path == tims_contract.PATH_PROVIDER:
        for key, item_key in tims_contract.REQUIREMENT_ITEMS.items():
            if key == calendar_terms.WEEK_START and bucket != "week":
                continue
            if key in calendar:
                semantics[key] = {"value": calendar[key], "source": "question",
                                  "guaranteed_by": item_key}
            elif contract.satisfied(item_key):
                semantics[key] = {"value": contract.items[item_key].value,
                                  "source": "contract", "contract": item_key}
            else:
                semantics[key] = {"value": "provider_defined", "source": "provider",
                                  "contract": item_key,
                                  "status": contract.items[item_key].status}
        if relative:
            week = stated_period_week(calendar, period)
            if tims_contract.date_argument_semantics(period, contract)["status"] == \
                    tims_contract.SEMANTICS_CONFIRMED:
                semantics["relative_date"] = {
                    "value": contract.items["relative_date_reference"].value,
                    "source": "contract", "contract": "relative_date_reference",
                    **({"week_start": week, "guaranteed_by": "bucket_week_start"}
                       if week else {})}
            else:
                semantics["relative_date"] = {
                    "value": "provider_defined", "source": "provider",
                    "contract": "relative_date_reference",
                    "status": contract.items["relative_date_reference"].status}
        record.update(
            requires=list(strategy.requires),
            delegated=[key for key, item in semantics.items() if item["source"] == "provider"],
            semantics=semantics,
            checks=[name for name, _ in PROVIDER_CHECKS],
            not_verified=["provider_calculation: 제공자 내부의 구간 경계·부분 구간·빈 구간·"
                          "상대 날짜 기준·평균의 분모(위임한 의미)"],
        )
        return record
    week_start = calendar.get(calendar_terms.WEEK_START)
    partial = calendar.get(calendar_terms.PARTIAL)
    if bucket == "week" or week_start:
        semantics["week_start"] = (
            {"value": week_start, "source": "question"} if week_start
            else {"value": periods.DEFAULT_WEEK_START, "source": "application"})
    semantics["partial"] = ({"value": partial, "source": "question"} if partial
                            else {"value": "include", "source": "application",
                                  "rule": "기간 경계에서 잘린 구간도 한 구간으로 셈"})
    empty = empty_day_policy(contract) if strategy is tims_contract.DAILY_PARTITION else "fail"
    semantics["empty"] = {"value": empty,
                          "source": "contract" if empty == "skip" else "application",
                          "rule": ("null = 기록 없음(계약)이면 그 날을 뺌" if empty == "skip"
                                   else "값이 없으면 0으로 채우지 않고 멈춤")}
    if relative:
        interpretation = relative_interpretation(
            period, stated_period_week(calendar, period) or periods.DEFAULT_WEEK_START)
        semantics["relative_date"] = {
            "value": interpretation["rule"],
            "source": ("question+application" if "week_start" in interpretation
                       else "application"),
            "policy": periods.RELATIVE_PERIOD_POLICY_SOURCE}
    record.update(
        requires=list(tims_contract.strategy_requires(strategy, spec.tool_name)),
        delegated=[],
        semantics=semantics,
        checks=[name for name, _ in LOCAL_CHECKS],
        not_verified=["provider_contract_behavior: 제공자가 requires의 계약대로 동작하는지"
                      "(호출 결과만으로 확인할 수 없음)"],
    )
    return record


def _no_strategy_error(transformation, output, combine, spec, contract, rejected, plan, *,
                       delegation):
    detail = "; ".join(f"{item['strategy']}: {item['reason']}" for item in rejected)
    calendar = group_calendar(output)
    if calendar and delegation and _fusable_shape(spec, output, combine) \
            and not contract.missing(tims_contract.FUSED_BUCKET_ROLLUP):
        # 질문이 구간 정의를 말하지 않았다면 위임 호출이 쓰였을 경우. 제공자 기본 정의로
        # 조용히 바꾸지 않았다는 것을 드러낸다.
        labels = ", ".join(calendar_terms.describe(key, value)
                           for key, value in calendar.items())
        return CompilerError(
            f"{transformation.id}: 질문이 정한 구간 정의({labels})를 보장하는 계산 경로가 "
            "없습니다. " + detail,
            code="CALENDAR_REQUIREMENT_UNSUPPORTED",
            user_message=(
                f"질문에서 정한 구간 기준({labels})을 TIMS 호출이 보장하지 않고, 직접 나눠 "
                "계산할 근거도 없어 계산하지 않았습니다. TIMS 기본 구간 정의로 바꿔 계산하지 "
                "않습니다."
            ),
            context={"template": plan.template, "rejected": rejected, "calendar": calendar},
        )
    return CompilerError(
        f"{transformation.id}: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 "
        "확인되지 않았습니다. " + detail,
        code="UNVERIFIED_TIMS_CONTRACT",
        user_message=(
            "이 구간별 계산은 TIMS의 동작이 문서로 확인되지 않아 정확한 값을 "
            "보장할 수 없으므로 수행하지 않았습니다."
        ),
        context={"template": plan.template, "rejected": rejected},
    )


def _measure_of(node):
    """측정값 subtype. 측정 node가 아니면 None(측정값 조건을 보지 않는다)."""
    if node is None or node.concept not in (CoreConcept.AMOUNT, CoreConcept.PROPORTION):
        return None
    return node.subtype


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


def empty_day_policy(contract):
    """하루 단위 합성에서 값이 없는(null) 날을 어떻게 다룰지. 계약이 정한다.

    provider가 "null = 조건에 맞는 기록 없음"을 계약으로 확인했다면 그날은 합(max·min 포함)에
    아무것도 더하지 않으므로 빼도 같은 계산이다(skip). 확인되지 않았다면 null이 결측인지
    0인지 오류인지 모르므로 멈춘다(fail). 모든 날이 비면 어느 쪽이든 멈춘다.
    """
    if contract.satisfied("null_result") and contract.items["null_result"].value == "null":
        return "skip"
    return "fail"


def _partition_steps(transformation, output, spec, nodes, plan, execution, *,
                     reference_date, strategy, contract=tims_contract.DEFAULT_CONTRACT):
    """기간을 나눠 같은 조건으로 호출하고, 구간별 값을 모으는 로컬 단계를 붙인다.

    ``range_partition``은 구간마다 날짜 범위로 한 번, ``daily_partition``은 하루마다
    한 번 부른다. 일 단위일 때는 COLLECT_GROUPS가 구간 안 집계를 하루 값들에 다시
    적용해 구간 값을 만든다(sum, max, min만 허용).
    """
    bucket = output.attributes[analysis_ops.GROUP_BY]["bucket"]
    period = transformation.params.get(spec.PERIOD_PARAM)
    start, end, groups, dropped, rule = _local_groups(
        transformation, output, spec, reference_date, plan)
    daily = strategy is tims_contract.DAILY_PARTITION
    calls = sum(len(periods.days_of(group)) for group in groups)
    if daily and calls > tims_contract.MAX_DAILY_CALLS:
        raise CompilerError(
            f"{transformation.id}: 일 단위 호출이 {calls}번 필요해 "
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
        "boundary": rule,
        "groups": [group["label"] for group in groups],
        "strategy": strategy.name,
        "path": strategy.path,
    }
    if dropped:
        execution.periods[transformation.id]["dropped_groups"] = [
            group["label"] for group in dropped]
    calendar = group_calendar(output)
    if calendar:
        execution.periods[transformation.id]["calendar"] = calendar
    if period in periods.RELATIVE_PERIOD_POLICY:
        execution.periods[transformation.id]["interpretation"] = relative_interpretation(
            period, stated_period_week(group_calendar(output), period)
            or periods.DEFAULT_WEEK_START)
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
            **({"empty_parts": empty_day_policy(contract)} if daily else {}),
        },
        output_bindings={WHOLE_RESULT: output.id},
        kind=STEP_LOCAL,
        covers=[transformation.id],
        argument_sources={"groups": f"{output.id}.group_by.bucket",
                          "reducer": f"{transformation.id}.params.{spec.REDUCER_PARAM}"},
        inputs=[key for keys in members for key in keys],
    ))
    return steps


def _local_groups(transformation, output, spec, reference_date, plan):
    """로컬 재계산의 구간. (시작, 끝, 쓰는 구간, 뺀 구간, 경계 설명).

    구간 정의는 질문이 명시한 것(주 시작 요일, 온전한 구간만)이 우선이고, 없으면 애플리케이션
    정책(월요일 시작, 기간 경계에서 자름)이다. compile과 ``verify_lowering``이 같이 쓴다.
    """
    bucket = output.attributes[analysis_ops.GROUP_BY]["bucket"]
    calendar = group_calendar(output)
    week_start = calendar.get(calendar_terms.WEEK_START, periods.DEFAULT_WEEK_START)
    partial = calendar.get(calendar_terms.PARTIAL, "include")
    period = transformation.params.get(spec.PERIOD_PARAM)
    start, end = periods.resolve_period(period, reference_date=reference_date,
                                        week_start=week_start)
    groups = periods.partition(start, end, bucket, week_start=week_start)
    dropped = []
    if partial == "exclude":
        dropped = [group for group in groups if not group["complete"]]
        groups = [group for group in groups if group["complete"]]
        if not groups:
            raise CompilerError(
                f"{transformation.id}: 기간 {period}에 온전한 {bucket} 구간이 없습니다.",
                code="NO_COMPLETE_GROUP",
                user_message="질문의 기간 안에 온전한 구간이 없어 계산할 구간이 없습니다.",
                context={"template": plan.template, "period": period,
                         "dropped": [group["label"] for group in dropped]},
            )
    rule = periods.boundary_rule(bucket, week_start, partial=partial)
    return start, end, groups, dropped, rule


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
                    contract=tims_contract.DEFAULT_CONTRACT, delegation=True):
    """실행 단계가 의미 graph의 조건과 집계를 빠짐없이 옮겼는지 확인한다.

    compiler의 결과를 다시 읽는 방어선이다. 인자 형식은 Tool schema가, 계획의
    구조는 validator가 보지만, "이 호출이 질문의 그 계산인가"는 둘 다 보지 않는다.

    검증하는 것(내부 일관성)
    - 모든 의미 단계가 실행 단계로 수행된다.
    - 각 호출이 그 의미 단계의 조건(기간·범위·택시 유형 등)을 그대로 갖는다.
    - 구간별 집계에 쓴 전략이 그 경로의 기준(``strategy_problems``)을 만족한다. 위임
      경로는 인자 매핑 계약과 질문이 명시한 구간 정의의 보장, 로컬 경로는 분해 전후
      동등성의 근거다. 한 경로의 근거로 다른 경로를 허용하지 않는다.
    - 기간 분할이 기간을 빈틈과 겹침 없이 덮고, 구간 안/밖 집계가 뒤바뀌지 않았다.
    - 위임 호출은 구간 안 집계를 명시하고(Tool 기본값 미사용) 목록 인자를 갖지 않는다.

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
        record = execution.lowering.get(transformation.id) or {}
        strategy = record.get("strategy")
        chosen = next((item for item in GROUP_STRATEGIES if item.name == strategy), None)
        combine = next((item for item in plan.transformations
                        if any(ref.node_id == output.id for ref in item.inputs.values())),
                       None)
        problems = (["알 수 없는 전략"] if chosen is None else strategy_problems(
            chosen, transformation, output, combine, get_operator(transformation.operator),
            contract, delegation=delegation))
        if problems or record.get("path") != chosen.path:
            raise _mismatch(
                f"{transformation.id}의 lowering 전략 {strategy!r}은 계약에서 허용되지 "
                "않습니다: " + "; ".join(problems or ["기록된 경로가 전략과 다릅니다"]),
                plan, transformation=transformation.id,
            )
        if partitioned:
            if chosen.path != tims_contract.PATH_LOCAL:
                raise _mismatch(f"{transformation.id}의 분할 호출이 위임 전략으로 기록되었습니다.",
                                plan, transformation=transformation.id)
            _verify_partition(transformation, output, tools, covering, plan,
                              reference_date, strategy, contract)
        else:
            if strategy != tims_contract.FUSED_BUCKET_ROLLUP.name:
                raise _mismatch(f"{transformation.id}의 호출이 전략과 다릅니다.", plan,
                                transformation=transformation.id)
            _verify_fused(transformation, output, tools, plan)


def _verify_relowered_period(transformation, record, tools, covering, plan,
                             reference_date, contract):
    """기간 인자를 명시 범위나 하루 단위로 바꾼 호출이 원래 기간과 같은지 다시 본다."""
    value = transformation.params.get("date")
    week_start = (record.get("calendar") or {}).get(
        calendar_terms.WEEK_START, periods.DEFAULT_WEEK_START)
    start, end = periods.resolve_period(value, reference_date=reference_date,
                                        week_start=week_start)
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
    output = next((node for node in plan.concepts
                   if node.id in transformation.outputs), None)
    ok, reason, _ = tims_contract.daily_composition(
        spec.tool_name, reducer, days=len(expected), contract=contract,
        measure=_measure_of(output))
    combine = [step for step in covering if step.operator == analysis_ops.COMBINE_DAYS]
    keys = [key for step in tools for key in step.output_bindings.values()]
    if not ok or len(combine) != 1 or combine[0].inputs != keys or combine[0].arguments.get(
            "reducer") != tims_contract.COMPOSABLE_REDUCERS.get(reducer) or combine[
            0].arguments.get("empty_parts") != empty_day_policy(contract):
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
    listed = [name for name in ("dimension", "order", "limit")
              if step.arguments.get(name) is not None]
    if listed:
        # 구간별 값의 집계는 스칼라 하나다. 목록 인자가 붙으면 다른 계산이 된다.
        raise _mismatch(f"{step.id}의 위임 호출에 목록 인자가 있습니다: {listed}", plan,
                        step=step.id)


def _verify_partition(transformation, output, tools, covering, plan,
                      reference_date, strategy, contract=tims_contract.DEFAULT_CONTRACT):
    spec = get_operator(transformation.operator)
    period = transformation.params.get(spec.PERIOD_PARAM)
    _, _, groups, _, _ = _local_groups(transformation, output, spec, reference_date, plan)
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
    if daily and collect[0].arguments.get("empty_parts") != empty_day_policy(contract):
        raise _mismatch(f"{output.id}의 빈 날 처리가 계약과 다릅니다.", plan, node=output.id)


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
