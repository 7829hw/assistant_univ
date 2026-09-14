# -*- coding: utf-8 -*-
"""GeoFlowPlan → ExecutionPlan 변환.

여기서 처음으로 semantic operator가 실제 Tool 이름과 argument 이름에 묶인다.
Planner도 template도 Tool argument 이름을 직접 지정하지 않는다.
"""

from geoflow.errors import CompilerError
from geoflow.operator_registry import get_operator
from geoflow.types import (
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


def compile_plan(plan: GeoFlowPlan):
    """검증을 통과한 plan을 topological order의 ToolStep 목록으로 만든다."""
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
    steps = [
        _compile_step(by_id[identifier], nodes, plan) for identifier in order
    ]
    seed_state = {
        node.id: node.value
        for node in plan.concepts
        if node.source not in PRODUCED_SOURCES
    }
    return ExecutionPlan(
        template=plan.template,
        steps=steps,
        final_node=plan.final_node,
        seed_state=seed_state,
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
