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

from geoflow import analysis_ops, periods
from geoflow.errors import CompilerError
from geoflow.operator_registry import get_operator
from geoflow.types import (
    STEP_LOCAL,
    WHOLE_RESULT,
    ExecutionPlan,
    GeoFlowPlan,
    NodeSource,
    ToolStep,
    ValueRef,
)

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


def compile_plan(plan: GeoFlowPlan, *, reference_date=None):
    """검증을 통과한 plan을 topological order의 실행 단계로 만든다.

    ``reference_date``는 상대 기간(last_month 등)을 날짜로 풀 기준일이다. 기간을
    로컬에서 나눠야 할 때만 쓰며, 없으면 그런 계획은 만들지 않는다.
    """
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
            execution.steps.append(_compile_step(transformation, nodes, plan))
            continue
        combine = _single_combiner(transformation, output, consumers, plan)
        spec = get_operator(transformation.operator)
        if _can_fuse(spec, output, combine):
            execution.steps.append(_fused_step(
                transformation, combine, output, spec, nodes, plan,
            ))
            fused.add(combine.id)
            execution.unobserved[output.id] = (
                "TIMS bucket/rollup 호출 안에서 계산되어 구간별 값은 반환되지 "
                "않습니다. 구간 경계는 TIMS의 정의를 따릅니다."
            )
            continue
        execution.steps.extend(_partition_steps(
            transformation, output, spec, nodes, plan, execution,
            reference_date=reference_date,
        ))

    for step in execution.steps:
        for covered in step.covers:
            execution.semantic_map.setdefault(covered, []).append(step.id)
    verify_lowering(plan, execution, reference_date=reference_date)
    return execution


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


def _can_fuse(spec, output, combine):
    """구간 안 집계와 구간별 값의 집계를 TIMS 호출 하나로 합칠 수 있는가."""
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
    return step


def _partition_steps(transformation, output, spec, nodes, plan, execution, *,
                     reference_date):
    """기간을 구간으로 나눠 구간마다 같은 조건으로 호출한다."""
    if spec is None or not spec.accepts_period:
        raise CompilerError(
            f"{transformation.id}: {transformation.operator}는 기간을 받지 않아 "
            "구간별로 나눠 호출할 수 없습니다.",
            code="UNSUPPORTED_GROUPED_MEASURE",
            user_message="이 측정값은 주·월 구간별 계산을 지원하지 않습니다.",
            context={"template": plan.template},
        )
    bucket = output.attributes[analysis_ops.GROUP_BY]["bucket"]
    period = transformation.params.get(spec.PERIOD_PARAM)
    start, end = periods.resolve_period(period, reference_date=reference_date)
    groups = periods.partition(start, end, bucket)
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
    }
    steps = []
    keys = []
    for index, group in enumerate(groups, start=1):
        step = _compile_step(transformation, nodes, plan)
        key = f"{output.id}#{index}"
        step.id = f"{transformation.id}#{index}"
        step.arguments[spec.PERIOD_PARAM] = periods.date_argument(group)
        step.argument_sources[spec.PERIOD_PARAM] = (
            f"{output.id}.group_by.bucket[{group['label']}] "
            f"⊂ {transformation.id}.params.{spec.PERIOD_PARAM}"
        )
        step.output_bindings = {spec.output.extraction: key}
        step.group = dict(group)
        steps.append(step)
        keys.append(key)
    steps.append(ToolStep(
        id=f"{transformation.id}.collect",
        operator=analysis_ops.COLLECT_GROUPS,
        tool_name=f"local:{analysis_ops.COLLECT_GROUPS}",
        arguments={"groups": [dict(group) for group in groups]},
        output_bindings={WHOLE_RESULT: output.id},
        kind=STEP_LOCAL,
        covers=[transformation.id],
        argument_sources={"groups": f"{output.id}.group_by.bucket"},
        inputs=keys,
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


def verify_lowering(plan, execution, *, reference_date=None):
    """실행 단계가 의미 graph의 조건과 집계를 빠짐없이 옮겼는지 확인한다.

    compiler의 결과를 다시 읽는 방어선이다. 인자 형식은 Tool schema가, 계획의
    구조는 validator가 보지만, "이 호출이 질문의 그 계산인가"는 둘 다 보지 않는다.
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
        for step in tools:
            for name, value in transformation.params.items():
                if value is None:
                    continue
                if partitioned and name == "date":
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
            if len(tools) != 1:
                raise _mismatch(f"{transformation.id}가 여러 호출로 나뉘었습니다.",
                                plan, transformation=transformation.id)
            continue
        if partitioned:
            _verify_partition(transformation, output, tools, covering, plan,
                              reference_date)
        else:
            _verify_fused(transformation, output, tools, plan)


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
                      reference_date):
    spec = get_operator(transformation.operator)
    period = transformation.params.get(spec.PERIOD_PARAM)
    start, end = periods.resolve_period(period, reference_date=reference_date)
    bucket = output.attributes[analysis_ops.GROUP_BY]["bucket"]
    expected = [periods.date_argument(group)
                for group in periods.partition(start, end, bucket)]
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
