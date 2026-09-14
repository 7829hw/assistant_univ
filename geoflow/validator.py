# -*- coding: utf-8 -*-
"""GeoFlow Plan 정적 검증.

Planner 출력은 물론 template instantiate 결과도 신뢰하지 않고, 실제 Tool을
호출하기 전에 구조·타입·provenance를 모두 확인한다.
"""

from dataclasses import dataclass, field
from typing import Any

from agent_graph import extract_scopes

from geoflow.compiler import topological_order
from geoflow.errors import ValidationError
from geoflow.operator_registry import (
    Operator,
    get_operator,
    is_scope_literal,
)
from geoflow.types import (
    CONTEXTUAL_ROLES,
    PROCEDURAL_ROLE_PRIORITY,
    SCOPE_SUBTYPES,
    GeoFlowPlan,
    NodeSource,
    Subtype,
)


class Rule:
    """검증 규칙 식별자."""

    ACYCLICITY = "G1_ACYCLICITY"
    ROLE_ORDERING = "G2_ROLE_ORDERING"
    TYPE_COMPATIBILITY = "G3_TYPE_COMPATIBILITY"
    EXECUTABILITY = "G4_EXECUTABILITY"
    CONNECTIVITY = "G5_CONNECTIVITY"
    SCOPE_PROVENANCE = "G6_SCOPE_PROVENANCE"


ALL_RULES = (
    Rule.ACYCLICITY,
    Rule.ROLE_ORDERING,
    Rule.TYPE_COMPATIBILITY,
    Rule.EXECUTABILITY,
    Rule.CONNECTIVITY,
    Rule.SCOPE_PROVENANCE,
)

#: 실행 계획이 만들어지는 node source. 나머지는 실행 전에 이미 값이 있어야 한다.
_PRODUCED_SOURCES = frozenset({NodeSource.TOOL, NodeSource.DERIVED})


@dataclass
class ValidationReport:
    """규칙별 통과 여부와 오류 목록."""

    template: str = ""
    checked_rules: list[str] = field(default_factory=lambda: list(ALL_RULES))
    errors: list[dict[str, Any]] = field(default_factory=list)
    order: list[str] = field(default_factory=list)

    @property
    def ok(self):
        return not self.errors

    def add(self, rule, message, **context):
        self.errors.append({
            "rule": rule,
            "message": message,
            "context": context,
        })

    def failed_rules(self):
        return sorted({error["rule"] for error in self.errors})

    def raise_if_failed(self):
        if self.ok:
            return self
        first = self.errors[0]
        summary = "; ".join(
            f"[{error['rule']}] {error['message']}" for error in self.errors
        )
        raise ValidationError(
            summary,
            rule=first["rule"],
            context={"template": self.template, "errors": self.errors},
        )

    def to_dict(self):
        return {
            "status": "OK" if self.ok else "ERROR",
            "template": self.template,
            "checked_rules": list(self.checked_rules),
            "failed_rules": self.failed_rules(),
            "errors": [dict(error) for error in self.errors],
            "topological_order": list(self.order),
        }


def validate(plan: GeoFlowPlan, *, available_tools=None, user_scopes=None):
    """``GeoFlowPlan``을 검증하고 ``ValidationReport``를 반환한다."""
    report = ValidationReport(template=plan.template)
    nodes = {node.id: node for node in plan.concepts}
    if len(nodes) != len(plan.concepts):
        report.add(
            Rule.CONNECTIVITY,
            "concept id가 중복되었습니다.",
            node_ids=plan.node_ids,
        )
        return report

    producers = _check_structure(plan, nodes, report)
    _check_executability(plan, report, available_tools)
    _check_types(plan, nodes, report)
    report.order = _check_acyclicity(plan, report)
    _check_connectivity(plan, nodes, producers, report)
    _check_role_ordering(plan, nodes, report)
    _check_scope_provenance(plan, nodes, report, user_scopes)
    return report


# -- 개별 규칙 -------------------------------------------------------------


def _check_structure(plan, nodes, report):
    """transformation의 참조 무결성을 확인하고 node별 producer를 모은다."""
    producers: dict[str, str] = {}
    seen_ids = set()
    for transformation in plan.transformations:
        if transformation.id in seen_ids:
            report.add(
                Rule.CONNECTIVITY,
                f"transformation id가 중복되었습니다: {transformation.id}",
            )
        seen_ids.add(transformation.id)

        for port, ref in transformation.inputs.items():
            if ref.node_id not in nodes:
                report.add(
                    Rule.CONNECTIVITY,
                    f"{transformation.id}.{port}가 존재하지 않는 concept를 "
                    f"참조합니다: {ref.describe()}",
                    transformation=transformation.id,
                    port=port,
                )
        for output_id in transformation.outputs:
            if output_id not in nodes:
                report.add(
                    Rule.CONNECTIVITY,
                    f"{transformation.id}의 output concept가 없습니다: "
                    f"{output_id}",
                    transformation=transformation.id,
                )
                continue
            if output_id in producers:
                report.add(
                    Rule.CONNECTIVITY,
                    f"concept {output_id}를 {producers[output_id]}와 "
                    f"{transformation.id}가 중복 생성합니다.",
                    transformation=transformation.id,
                )
                continue
            producers[output_id] = transformation.id
    return producers


def _check_executability(plan, report, available_tools):
    """G4. operator가 registry에 있고 실제 Tool도 사용 가능해야 한다."""
    known_tools = None if available_tools is None else set(available_tools)
    for transformation in plan.transformations:
        spec = get_operator(transformation.operator)
        if spec is None:
            report.add(
                Rule.EXECUTABILITY,
                f"{transformation.id}: 등록되지 않은 operator입니다: "
                f"{transformation.operator}",
                transformation=transformation.id,
            )
            continue
        if known_tools is not None and spec.tool_name not in known_tools:
            report.add(
                Rule.EXECUTABILITY,
                f"{transformation.id}: 현재 실행 환경에서 사용할 수 없는 "
                f"Tool입니다: {spec.tool_name}",
                transformation=transformation.id,
                tool_name=spec.tool_name,
            )
        unknown_ports = sorted(set(transformation.inputs) - set(spec.inputs))
        if unknown_ports:
            report.add(
                Rule.EXECUTABILITY,
                f"{transformation.id}: {spec.name}에 없는 input port입니다: "
                f"{', '.join(unknown_ports)}",
                transformation=transformation.id,
            )
        missing_ports = [
            port for port in spec.required_ports
            if port not in transformation.inputs
        ]
        if missing_ports:
            report.add(
                Rule.EXECUTABILITY,
                f"{transformation.id}: 필수 input port가 없습니다: "
                f"{', '.join(missing_ports)}",
                transformation=transformation.id,
            )
        unknown_params = sorted(set(transformation.params) - set(spec.params))
        if unknown_params:
            report.add(
                Rule.EXECUTABILITY,
                f"{transformation.id}: {spec.name}이 지원하지 않는 "
                f"parameter입니다: {', '.join(unknown_params)}",
                transformation=transformation.id,
            )


def _check_types(plan, nodes, report):
    """G3. operator port와 output의 semantic type이 맞아야 한다."""
    for transformation in plan.transformations:
        spec = get_operator(transformation.operator)
        if spec is None:
            continue
        for port, ref in transformation.inputs.items():
            port_spec = spec.input(port)
            node = nodes.get(ref.node_id)
            if port_spec is None or node is None:
                continue
            if not port_spec.accepts(node.concept, node.subtype):
                report.add(
                    Rule.TYPE_COMPATIBILITY,
                    f"{transformation.id}.{port}는 "
                    f"{port_spec.concept.value}/"
                    f"{'|'.join(sorted(port_spec.subtypes))}를 요구하지만 "
                    f"{node.id}는 {node.concept.value}/{node.subtype}입니다.",
                    transformation=transformation.id,
                    port=port,
                    node=node.id,
                )
            if port_spec.field is not None and ref.field != port_spec.field:
                report.add(
                    Rule.TYPE_COMPATIBILITY,
                    f"{transformation.id}.{port}는 참조 field가 "
                    f"{port_spec.field!r}여야 하지만 {ref.field!r}입니다.",
                    transformation=transformation.id,
                    port=port,
                )
        if spec.output is None:
            continue
        for output_id in transformation.outputs:
            node = nodes.get(output_id)
            if node is None:
                continue
            if not spec.output.accepts(node.concept, node.subtype):
                allowed = ", ".join(
                    f"{concept.value}/{subtype}"
                    for concept, subtype in sorted(
                        spec.output.allowed, key=lambda item: item[1]
                    )
                )
                report.add(
                    Rule.TYPE_COMPATIBILITY,
                    f"{transformation.id}: {spec.name}은 {allowed} 중 하나만 "
                    f"만들 수 있지만 {node.id}는 "
                    f"{node.concept.value}/{node.subtype}입니다.",
                    transformation=transformation.id,
                    node=node.id,
                )
        _check_vicinity_consistency(transformation, nodes, report)


def _check_vicinity_consistency(transformation, nodes, report):
    """vicinity_scope는 include_vicinity=true로 얻은 값이어야 한다."""
    if transformation.operator != Operator.RESOLVE_PLACE_SCOPE:
        return
    include_vicinity = bool(transformation.params.get("include_vicinity"))
    for output_id in transformation.outputs:
        node = nodes.get(output_id)
        if node is None:
            continue
        is_vicinity = node.subtype == Subtype.VICINITY_SCOPE
        if is_vicinity and not include_vicinity:
            report.add(
                Rule.TYPE_COMPATIBILITY,
                f"{transformation.id}: {node.id}는 vicinity_scope인데 "
                "include_vicinity가 true가 아닙니다.",
                transformation=transformation.id,
            )
        elif not is_vicinity and include_vicinity:
            report.add(
                Rule.TYPE_COMPATIBILITY,
                f"{transformation.id}: include_vicinity=true인데 {node.id}의 "
                "subtype이 vicinity_scope가 아닙니다.",
                transformation=transformation.id,
            )


def _check_acyclicity(plan, report):
    """G1. compiler와 같은 정렬 규칙으로 cycle을 찾는다."""
    order, cycle = topological_order(plan)
    if cycle:
        report.add(
            Rule.ACYCLICITY,
            f"transformation dependency에 cycle이 있습니다: {', '.join(cycle)}",
            cycle=cycle,
        )
    return order


def _check_connectivity(plan, nodes, producers, report):
    """G5. 실행 전 값이 없는 node가 없고 final_node까지 연결되어야 한다."""
    if plan.final_node not in nodes:
        report.add(
            Rule.CONNECTIVITY,
            f"final_node가 concepts에 없습니다: {plan.final_node}",
        )
        return

    for node in plan.concepts:
        produced = node.id in producers
        if node.source in _PRODUCED_SOURCES and not produced:
            report.add(
                Rule.CONNECTIVITY,
                f"{node.id}는 source={node.source.value}인데 이를 생성하는 "
                "transformation이 없습니다.",
                node=node.id,
            )
        if node.source not in _PRODUCED_SOURCES:
            if produced:
                report.add(
                    Rule.CONNECTIVITY,
                    f"{node.id}는 source={node.source.value}인데 "
                    f"{producers[node.id]}가 값을 덮어씁니다.",
                    node=node.id,
                )
            elif node.value is None:
                report.add(
                    Rule.CONNECTIVITY,
                    f"{node.id}는 실행 전에 값이 있어야 하지만 비어 있습니다.",
                    node=node.id,
                )

    by_id = {item.id: item for item in plan.transformations}
    reachable = set()
    queue = [plan.final_node]
    while queue:
        node_id = queue.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        transformation = by_id.get(producers.get(node_id))
        if transformation is None:
            continue
        for ref in transformation.inputs.values():
            queue.append(ref.node_id)

    isolated = sorted(set(nodes) - reachable)
    if isolated:
        report.add(
            Rule.CONNECTIVITY,
            f"final_node({plan.final_node})와 연결되지 않은 concept가 "
            f"있습니다: {', '.join(isolated)}",
            isolated=isolated,
        )


def _check_role_ordering(plan, nodes, report):
    """G2. 명백한 procedural role 역행만 막는다.

    EXTENT/TEXTENT는 contextual role이므로 순서 검사에서 제외한다. TIMS의
    정상 workflow를 논문의 role ordering으로 기계적으로 거부하지 않도록,
    template이 만든 실제 dependency 위에서만 역행 여부를 판단한다.
    """
    for transformation in plan.transformations:
        input_nodes = [
            nodes[ref.node_id]
            for ref in transformation.inputs.values()
            if ref.node_id in nodes
        ]
        output_nodes = [
            nodes[output_id]
            for output_id in transformation.outputs
            if output_id in nodes
        ]
        for source_node in input_nodes:
            if source_node.role in CONTEXTUAL_ROLES:
                continue
            source_priority = PROCEDURAL_ROLE_PRIORITY[source_node.role]
            for target_node in output_nodes:
                if target_node.role in CONTEXTUAL_ROLES:
                    continue
                target_priority = PROCEDURAL_ROLE_PRIORITY[target_node.role]
                if source_priority > target_priority:
                    report.add(
                        Rule.ROLE_ORDERING,
                        f"{transformation.id}: {source_node.id}"
                        f"({source_node.role.value})가 {target_node.id}"
                        f"({target_node.role.value})보다 뒤 순서 role입니다.",
                        transformation=transformation.id,
                    )


def _check_scope_provenance(plan, nodes, report, user_scopes):
    """G6. scope 값은 사용자 입력 또는 Tool 결과에서만 올 수 있다."""
    allowed = (
        set(extract_scopes(plan.question))
        if user_scopes is None
        else set(user_scopes)
    )
    for node in plan.concepts:
        if node.subtype not in SCOPE_SUBTYPES:
            if is_scope_literal(node.value):
                report.add(
                    Rule.SCOPE_PROVENANCE,
                    f"{node.id}({node.subtype})가 scope 문자열을 값으로 "
                    f"가지고 있습니다: {node.value}",
                    node=node.id,
                )
            continue

        if node.source not in (NodeSource.USER, NodeSource.TOOL):
            report.add(
                Rule.SCOPE_PROVENANCE,
                f"{node.id}는 scope인데 source={node.source.value}입니다. "
                "scope는 source=user 또는 source=tool만 허용합니다.",
                node=node.id,
            )
            continue

        if node.source == NodeSource.TOOL:
            if node.value is not None:
                report.add(
                    Rule.SCOPE_PROVENANCE,
                    f"{node.id}는 Tool이 채워야 하는 scope인데 이미 값이 "
                    f"들어 있습니다: {node.value}",
                    node=node.id,
                )
            continue

        # source=user
        if not is_scope_literal(node.value):
            report.add(
                Rule.SCOPE_PROVENANCE,
                f"{node.id}의 사용자 제공 scope 형식이 올바르지 않습니다: "
                f"{node.value!r}",
                node=node.id,
            )
        elif node.value not in allowed:
            report.add(
                Rule.SCOPE_PROVENANCE,
                f"{node.id}의 scope가 사용자 발화에 없습니다: {node.value}. "
                "scope 값을 직접 생성할 수 없습니다.",
                node=node.id,
                scope=node.value,
            )
