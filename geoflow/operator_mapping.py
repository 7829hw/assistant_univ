# -*- coding: utf-8 -*-
"""Concept transformation → semantic operator 결정(factorization).

Macro는 ``EVENT/trip → AMOUNT/fare``처럼 개념 변환만 표현한다. 어떤 semantic
operator가 그 변환을 수행할 수 있는지는 여기서 정한다. 그래서 macro 정의에
``TRIP_METRIC`` 같은 이름이 나타나지 않고, Tool이 추가·변경되어도 macro는
그대로 둘 수 있다.

선택 근거는 세 가지뿐이며 모두 registry에 이미 들어 있는 정보다.

1. 출력 (CoreConcept, subtype)을 만들 수 있는 operator인가
2. 입력 node 전부를 port로 받을 수 있는가 (남는 node가 있으면 후보가 아니다)
3. 필수 port가 모두 채워지는가

질문 문자열이나 template 이름은 근거로 쓰지 않는다. ``metric``·
``include_vicinity``처럼 concept subtype에서 곧바로 따라오는 인자도 LLM이 아니라
이 단계가 유도한다.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from geoflow.errors import CompositionError
from geoflow.operator_registry import OPERATORS, OperatorSpec
from geoflow.types import ConceptNode, CoreConcept, Subtype, ValueRef


@dataclass(frozen=True)
class OperatorBinding:
    """변환 하나에 확정된 operator와 port/parameter binding."""

    operator: str
    inputs: dict[str, ValueRef] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    #: factors에서 실제로 쓰인 이름. 어떤 조건이 버려졌는지 추적하는 데 쓴다.
    used_factors: frozenset[str] = frozenset()


def candidates_for(concept, subtype):
    """(concept, subtype)을 만들 수 있는 operator를 이름 순으로 돌려준다."""
    return tuple(sorted(
        (
            spec for spec in OPERATORS.values()
            if spec.output is not None and spec.output.accepts(concept, subtype)
        ),
        key=lambda spec: spec.name,
    ))


class BindFailureReason(str, Enum):
    """후보 operator 하나가 입력 node를 port에 배치하지 못한 이유."""

    #: 필수 port에 맞는 입력 node가 없다.
    REQUIRED_PORT_UNBOUND = "REQUIRED_PORT_UNBOUND"
    #: 한 port에 맞는 입력 node가 둘 이상이다.
    AMBIGUOUS_PORT = "AMBIGUOUS_PORT"
    #: 어느 port에도 들어가지 못한 입력 node가 남는다.
    UNCONSUMED_INPUT = "UNCONSUMED_INPUT"


@dataclass(frozen=True)
class BindProblem:
    """배치 실패 하나. port가 없는 문제(UNCONSUMED_INPUT)는 port가 None이다."""

    reason: BindFailureReason
    port: str | None = None
    expected_concept: CoreConcept | None = None
    expected_subtypes: tuple[str, ...] = ()
    #: 문제에 걸린 입력 node. 여럿이 맞은 port나 남은 입력이다.
    nodes: tuple[str, ...] = ()

    def to_dict(self):
        return {
            "reason": self.reason.value,
            "port": self.port,
            "expected_concept": (
                self.expected_concept.value if self.expected_concept else None
            ),
            "expected_subtypes": list(self.expected_subtypes),
            "nodes": list(self.nodes),
        }


@dataclass(frozen=True)
class CandidateFailure:
    """출력 타입은 맞지만 입력을 배치하지 못한 후보 operator.

    한 후보가 여러 문제를 함께 가질 수 있으므로 문제를 모두 담는다.
    """

    operator: str
    problems: tuple[BindProblem, ...]

    @property
    def reasons(self):
        return tuple(sorted({item.reason for item in self.problems},
                            key=lambda reason: reason.value))

    def sole_missing_port(self):
        """유일한 문제가 필수 port 하나가 빈 것이면 그 문제를, 아니면 None.

        이때만 "입력 하나가 있으면 이 후보가 성립한다"고 말할 수 있다.
        """
        if len(self.problems) != 1:
            return None
        problem = self.problems[0]
        if problem.reason != BindFailureReason.REQUIRED_PORT_UNBOUND:
            return None
        return problem

    def to_dict(self):
        return {
            "operator": self.operator,
            "reasons": [reason.value for reason in self.reasons],
            "problems": [item.to_dict() for item in self.problems],
        }


#: 필수 input이 비었을 때 사용자에게 보이는 말. operator 이름은 쓰지 않는다.
_MISSING_INPUT_MESSAGES = {
    CoreConcept.LOCATION: "이 분석은 지역을 함께 지정해야 합니다.",
}
_MISSING_INPUT_FALLBACK = "이 분석에 필요한 조건이 질문에 없습니다."


def resolve(*, inputs, output, factors=None, where="", available_nodes=None):
    """입력 node 집합과 출력 node로 operator를 확정한다.

    후보가 없거나 둘 이상이면 추측하지 않고 실패한다. 계획이 실행마다 달라지지
    않아야 하기 때문이다.

    ``available_nodes``는 이 변환을 만들 때 graph에서 입력으로 쓸 수 있는 node
    전체다. operator 선택에는 쓰지 않고, 실패했을 때 필수 input이 정말 없는지
    판정하는 데만 쓴다. 주지 않으면 그 판정을 하지 않는다.
    """
    factors = dict(factors or {})
    matched = []
    failures = []
    for spec in candidates_for(output.concept, output.subtype):
        bound, failure = _bind_ports(spec, inputs)
        if failure is None:
            matched.append((spec, bound))
        else:
            failures.append(failure)

    if not matched:
        raise _binding_failure(
            inputs=inputs, output=output, failures=failures, where=where,
            available_nodes=available_nodes,
        )
    if len(matched) > 1:
        names = ", ".join(spec.name for spec, _ in matched)
        raise CompositionError(
            f"{where or output.id}: 같은 변환을 수행할 수 있는 operator가 "
            f"여럿입니다: {names}",
            code="AMBIGUOUS_OPERATOR",
            context={"candidates": [spec.name for spec, _ in matched]},
        )

    spec, assigned = matched[0]
    # param 값과 port binding이 모두 정해지는 가장 이른 지점이다. 어떤 input이
    # 채워졌는지에 따라 합법 여부가 달라지는 param은 여기서부터 검사할 수 있다.
    params, used = _resolve_params(spec, output, factors, bound_inputs=assigned)
    return OperatorBinding(
        operator=spec.name,
        inputs={
            port: ValueRef(node.id, spec.inputs[port].field)
            for port, node in assigned.items()
        },
        params=params,
        used_factors=used,
    )


def _type_name(node):
    return f"{node.concept.value}/{node.subtype}"


def _binding_failure(*, inputs, output, failures, where, available_nodes):
    """모든 후보가 배치에 실패했을 때의 오류를 만든다.

    MISSING_REQUIRED_INPUT은 다음을 모두 만족할 때만 낸다. 하나라도 어긋나면
    NO_OPERATOR다. 틀린 안내("지역을 지정하세요")를 내는 것보다 원인을 덜
    구체적으로 말하는 편이 낫다.

    1. 출력 타입이 맞는 후보가 있다.
    2. 그중 하나의 유일한 문제가 필수 port 하나가 빈 것이다.
    3. 그 port가 기대하는 concept의 node가 graph 어디에도 없다. subtype이나
       속성이 맞지 않는 node라도 concept이 같으면 "있다"고 본다. 질문에 장소가
       있는데 역할이 맞지 않는 경우를 "장소가 없다"로 말하지 않기 위해서다.
    """
    output_type = f"{output.concept.value}/{output.subtype}"
    input_types = [_type_name(node) for node in inputs]
    candidate_failures = [failure.to_dict() for failure in failures]

    if available_nodes is not None:
        present = {
            node.concept for node in available_nodes if node.id != output.id
        }
        for failure in failures:
            problem = failure.sole_missing_port()
            if problem is None or problem.expected_concept in present:
                continue
            return CompositionError(
                f"{where or output.id}: {output_type}를 만들려면 "
                f"{problem.expected_concept.value}"
                f"({', '.join(problem.expected_subtypes)}) 입력이 필요하지만 "
                "graph에 없습니다.",
                code="MISSING_REQUIRED_INPUT",
                user_message=_MISSING_INPUT_MESSAGES.get(
                    problem.expected_concept, _MISSING_INPUT_FALLBACK,
                ),
                context={
                    "output": output_type,
                    "candidate_operator": failure.operator,
                    "required_port": problem.port,
                    "expected_concept": problem.expected_concept.value,
                    "expected_subtypes": list(problem.expected_subtypes),
                    "available_inputs": input_types,
                    "candidate_failures": candidate_failures,
                },
            )

    return CompositionError(
        f"{where or output.id}: "
        f"{_describe(inputs)} → {output_type} "
        "변환을 수행할 semantic operator가 없습니다.",
        code="NO_OPERATOR",
        context={
            "output": output_type,
            "inputs": input_types,
            "candidate_failures": candidate_failures,
        },
    )


def _bind_ports(spec: OperatorSpec, inputs):
    """입력 node를 operator port에 결정적으로 배치한다.

    한 port에 후보가 둘 이상이면 배치하지 않는다. 출발지와 도착지를 임의로
    정하는 일이 없어야 하기 때문이다.

    ``(assigned, None)`` 또는 ``(None, CandidateFailure)``를 돌려준다. 문제가
    하나라도 있으면 배치하지 않는다는 판정은 예전과 같다. 첫 문제에서 멈추지
    않고 끝까지 보는 것은 실패 이유를 모두 남기기 위해서다.
    """
    assigned: dict[str, ConceptNode] = {}
    problems: list[BindProblem] = []
    for port, port_spec in spec.inputs.items():
        matches = [
            node for node in inputs
            if port_spec.binds(node.concept, node.subtype, node.attributes)
        ]
        if len(matches) > 1:
            problems.append(_port_problem(
                BindFailureReason.AMBIGUOUS_PORT, port, port_spec, matches,
            ))
            continue
        if not matches:
            if port_spec.required:
                problems.append(_port_problem(
                    BindFailureReason.REQUIRED_PORT_UNBOUND, port, port_spec,
                ))
            continue
        assigned[port] = matches[0]

    # 받아 줄 port가 없는 입력이 남아 있으면 이 operator는 그 조건을
    # 조용히 버리게 된다. 후보에서 제외한다. 여러 node가 맞아 배치하지 못한
    # port의 node는 AMBIGUOUS_PORT로 이미 적었으므로 다시 세지 않는다.
    consumed = {node.id for node in assigned.values()}
    consumed.update(
        node_id for problem in problems for node_id in problem.nodes
    )
    leftover = [node for node in inputs if node.id not in consumed]
    if leftover:
        problems.append(BindProblem(
            reason=BindFailureReason.UNCONSUMED_INPUT,
            nodes=tuple(node.id for node in leftover),
        ))
    if problems:
        return None, CandidateFailure(operator=spec.name, problems=tuple(problems))
    return assigned, None


def _port_problem(reason, port, port_spec, nodes=()):
    return BindProblem(
        reason=reason,
        port=port,
        expected_concept=port_spec.concept,
        expected_subtypes=tuple(sorted(port_spec.subtypes)),
        nodes=tuple(node.id for node in nodes),
    )


#: 출력 concept subtype에서 곧바로 따라오는 Tool 인자.
#: template마다 적어 두던 값을 개념에서 유도하도록 옮긴 것이다.
def _derive_metric(output, factors):
    """metric 인자는 곧 측정 대상 concept의 subtype이다."""
    return output.subtype


def _derive_include_vicinity(output, factors):
    """주변 포함 여부는 만들려는 scope subtype이 정한다."""
    return output.subtype == Subtype.VICINITY_SCOPE


DERIVED_PARAMS = {
    "metric": _derive_metric,
    "include_vicinity": _derive_include_vicinity,
}


def _resolve_params(spec, output, factors, bound_inputs=()):
    """operator가 지원하는 parameter만 factor와 개념에서 채운다.

    지원하지 않는 factor는 인자로 만들지 않는다. 질문에 없는 조건을 만들어
    내지 않는 것과 같은 이유로, 이 Tool이 받을 수 없는 조건을 억지로 끼워
    넣지도 않는다. 어떤 조건이 빠졌는지는 호출한 쪽이 기록한다.
    """
    params: dict[str, Any] = {}
    used = set()
    for name in sorted(spec.params):
        derive = DERIVED_PARAMS.get(name)
        if derive is not None:
            params[name] = derive(output, factors)
            continue
        if name in factors and factors[name] is not None:
            params[name] = factors[name]
            used.add(name)
    _check_param_contract(spec, params, bound_inputs)
    return params, frozenset(used)


def _check_param_contract(spec, params, bound_inputs=()):
    """Tool이 거절할 값·조합을 합성 단계에서 미리 막는다.

    Validator G4가 같은 검사를 다시 수행하지만, 여기서 먼저 걸러야 어떤
    조건이 문제였는지 합성 오류로 설명할 수 있다.
    """
    for name, value in sorted(params.items()):
        allowed = spec.allowed_values(name)
        if allowed is not None and value is not None and value not in allowed:
            raise CompositionError(
                f"{spec.name}의 {name}은 {', '.join(sorted(allowed))} 중 "
                f"하나여야 하지만 {value!r}입니다.",
                code="INVALID_PARAM_VALUE",
                context={"operator": spec.name, "param": name},
            )
        missing = spec.missing_companions(name, params)
        if missing:
            raise CompositionError(
                f"{name} 조건을 쓰려면 {', '.join(missing)} 조건도 함께 "
                "필요합니다.",
                code="MISSING_COMPANION_PARAM",
                context={"operator": spec.name, "param": name},
            )
    for violation in spec.contract_violations(params, bound_inputs):
        raise CompositionError(
            violation.detail(),
            code=violation.kind,
            user_message=violation.reason,
            context=violation.context(),
        )


def _describe(nodes):
    if not nodes:
        return "(입력 없음)"
    return " + ".join(
        f"{node.concept.value}/{node.subtype}"
        for node in sorted(nodes, key=lambda item: item.id)
    )


def event_subtype_for(concept, subtype):
    """출력 (concept, subtype)을 만들려면 어떤 EVENT가 필요한지 알려준다.

    질문에 "통행"이라는 말이 없어도 속도를 재려면 passage가 있어야 한다.
    이 함수는 그 필연적인 개념을 registry에서 읽어 온다. 후보 operator가
    여럿이거나 EVENT를 쓰지 않으면 ``None``을 돌려주고, 그 경우 개념을
    지어내지 않는다.
    """
    subtypes = {
        event
        for spec in candidates_for(concept, subtype)
        for event in spec.event_subtypes
    }
    if len(subtypes) != 1:
        return None
    return next(iter(subtypes))


def measure_types():
    """operator registry가 만들 수 있는 측정값 타입 전체."""
    return frozenset(
        pair
        for spec in OPERATORS.values()
        if spec.output is not None
        for pair in spec.output.allowed
        if pair[0] in (CoreConcept.AMOUNT, CoreConcept.PROPORTION)
    )
