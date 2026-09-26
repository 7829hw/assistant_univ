# -*- coding: utf-8 -*-
"""GeoFlow Plan 정적 검증.

Planner 출력은 물론 template instantiate 결과도 신뢰하지 않고, 실제 Tool을
호출하기 전에 구조·타입·provenance를 모두 확인한다.
"""

from dataclasses import dataclass, field
from typing import Any

from agent_graph import extract_scopes

from geoflow import analysis_ops
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
    #: 구간별 값이 의미대로 만들어지고 소비되는가. 논문의 G1~G5에 없는 이
    #: 프로젝트의 규칙이다. G3(타입)만으로는 "주별 합계"와 "합계"가 같은
    #: AMOUNT/revenue라서 두 단계 집계의 누락·뒤섞임을 볼 수 없다.
    AGGREGATION_SEMANTICS = "G7_AGGREGATION_SEMANTICS"


ALL_RULES = (
    Rule.ACYCLICITY,
    Rule.ROLE_ORDERING,
    Rule.TYPE_COMPATIBILITY,
    Rule.EXECUTABILITY,
    Rule.CONNECTIVITY,
    Rule.SCOPE_PROVENANCE,
    Rule.AGGREGATION_SEMANTICS,
)

#: 의미 graph에 둘 수 없는 Tool parameter. 두 단계 집계는 node와 변환으로
#: 표현하고, 이 인자는 compiler의 lowering만 만든다.
LOWERING_ONLY_PARAMS = frozenset({"bucket", "rollup"})

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
    _check_aggregation_semantics(plan, nodes, producers, report)
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
        if analysis_ops.is_analysis_operator(transformation.operator):
            # 로컬 계산이다. 계약은 G7이 본다.
            continue
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
        _check_param_contract(transformation, spec, report)


def _check_param_contract(transformation, spec, report):
    """G4. Tool이 거절할 parameter 값·조합을 실행 전에 걸러 낸다.

    예전에 template YAML의 slot_types/slot_requires가 하던 검사를 registry
    기준으로 옮긴 것이다. 계획을 만든 경로(template이든 macro composition이든)와
    무관하게 같은 규칙이 적용된다.
    """
    for name, value in sorted(transformation.params.items()):
        allowed = spec.allowed_values(name)
        if allowed is not None and value is not None and value not in allowed:
            report.add(
                Rule.EXECUTABILITY,
                f"{transformation.id}: {spec.name}의 {name}은 "
                f"{', '.join(sorted(allowed))} 중 하나여야 하지만 "
                f"{value!r}입니다.",
                transformation=transformation.id,
                param=name,
            )
        missing = spec.missing_companions(name, transformation.params)
        if missing:
            report.add(
                Rule.EXECUTABILITY,
                f"{transformation.id}: {name}을 쓰려면 "
                f"{', '.join(missing)}도 함께 필요합니다.",
                transformation=transformation.id,
                param=name,
            )
    # 합성과 같은 규칙이다. 어떤 경로로 만든 계획이든 여기서 다시 막는다.
    for violation in spec.contract_violations(transformation.params,
                                              transformation.inputs):
        report.add(
            Rule.EXECUTABILITY,
            f"{transformation.id}: {violation.detail()}",
            transformation=transformation.id,
            code=violation.kind,
            **violation.context(),
        )


def _check_types(plan, nodes, report):
    """G3. operator port와 output의 semantic type이 맞아야 한다."""
    for transformation in plan.transformations:
        if analysis_ops.is_analysis_operator(transformation.operator):
            continue
        spec = get_operator(transformation.operator)
        if spec is None:
            continue
        for port, ref in transformation.inputs.items():
            port_spec = spec.input(port)
            node = nodes.get(ref.node_id)
            if port_spec is None or node is None:
                continue
            if not port_spec.accepts(
                node.concept, node.subtype, node.attributes,
            ):
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


def _check_aggregation_semantics(plan, nodes, producers, report):
    """G7. 구간별 값이 의미대로 만들어지고 합쳐지는지 본다.

    1. 분석 연산자는 구간별 node 하나를 받아 같은 (concept, subtype)의 구간 없는
       node를 만든다. 원시 값이나 다른 측정값에서 구간 값을 "재구성"하지 않는다.
    2. 구간별 node는 구간 안 집계를 명시한 TIMS 변환이 만든다. 명시하지 않으면
       Tool 기본값이 조용히 구간 안 집계가 된다.
    3. 구간별 node는 분석 연산자 하나가 소비하며 최종 답이 될 수 없다.
    4. bucket·rollup은 의미 graph의 Tool parameter로 둘 수 없다(lowering 전용).
    """
    consumers = {}
    for transformation in plan.transformations:
        for ref in transformation.inputs.values():
            consumers.setdefault(ref.node_id, []).append(transformation)
        compressed = sorted(set(transformation.params) & LOWERING_ONLY_PARAMS)
        if compressed and not analysis_ops.is_analysis_operator(
            transformation.operator
        ):
            report.add(
                Rule.AGGREGATION_SEMANTICS,
                f"{transformation.id}: {', '.join(compressed)}는 의미 graph의 "
                "parameter가 아닙니다. 구간별 집계는 구간별 node와 분석 연산자로 "
                "표현합니다.",
                transformation=transformation.id,
            )
        if not analysis_ops.is_analysis_operator(transformation.operator):
            continue
        spec = analysis_ops.ANALYSIS_OPERATORS[transformation.operator]
        if not spec.semantic:
            report.add(
                Rule.AGGREGATION_SEMANTICS,
                f"{transformation.id}: {transformation.operator}는 lowering 전용 "
                "연산자입니다.",
                transformation=transformation.id,
            )
            continue
        for problem in analysis_ops.param_problems(
            transformation.operator, transformation.params,
        ):
            report.add(Rule.AGGREGATION_SEMANTICS,
                       f"{transformation.id}: {problem}",
                       transformation=transformation.id)
        inputs = [nodes.get(ref.node_id) for ref in transformation.inputs.values()]
        outputs = [nodes.get(item) for item in transformation.outputs]
        if (
            len(inputs) != 1 or len(outputs) != 1
            or not analysis_ops.is_grouped(inputs[0])
            or outputs[0] is None or analysis_ops.is_grouped(outputs[0])
            or (inputs[0].concept, inputs[0].subtype)
            != (outputs[0].concept, outputs[0].subtype)
        ):
            report.add(
                Rule.AGGREGATION_SEMANTICS,
                f"{transformation.id}: {transformation.operator}는 구간별 값 하나를 "
                "받아 같은 개념의 값 하나를 만들어야 합니다.",
                transformation=transformation.id,
            )
            continue
        returns_group = (
            outputs[0].attributes.get(analysis_ops.RETURNS)
            == analysis_ops.RETURNS_GROUP
        )
        if returns_group != (transformation.operator == analysis_ops.SELECT_GROUP):
            report.add(
                Rule.AGGREGATION_SEMANTICS,
                f"{transformation.id}: 구간을 고르는 연산만 구간을 답으로 "
                "돌려줍니다.",
                transformation=transformation.id,
            )

    by_id = {item.id: item for item in plan.transformations}
    for node in plan.concepts:
        if not analysis_ops.is_grouped(node):
            continue
        if node.id == plan.final_node:
            report.add(
                Rule.AGGREGATION_SEMANTICS,
                f"{node.id}: 구간별 값은 최종 답이 될 수 없습니다. 구간별 목록을 "
                "돌려주는 계산은 지원하지 않습니다.",
                node=node.id,
            )
        bucket = node.attributes[analysis_ops.GROUP_BY].get("bucket")
        if bucket not in ("week", "month"):
            report.add(Rule.AGGREGATION_SEMANTICS,
                       f"{node.id}: 구간 단위가 올바르지 않습니다: {bucket!r}",
                       node=node.id)
        users = consumers.get(node.id, [])
        if len(users) != 1 or not analysis_ops.is_analysis_operator(
            users[0].operator
        ):
            report.add(
                Rule.AGGREGATION_SEMANTICS,
                f"{node.id}: 구간별 값은 분석 연산자 하나가 소비해야 합니다.",
                node=node.id,
            )
        producer = by_id.get(producers.get(node.id))
        if producer is None:
            continue
        spec = get_operator(producer.operator)
        if spec is None or not spec.accepts_reducer:
            report.add(
                Rule.AGGREGATION_SEMANTICS,
                f"{producer.id}: {producer.operator}는 구간 안 집계를 받지 않아 "
                "구간별 값을 만들 수 없습니다.",
                transformation=producer.id,
            )
        elif producer.params.get(spec.REDUCER_PARAM) is None:
            report.add(
                Rule.AGGREGATION_SEMANTICS,
                f"{producer.id}: 구간 안 집계가 지정되지 않았습니다. Tool 기본값을 "
                "구간 안 집계로 쓰지 않습니다.",
                transformation=producer.id,
            )
