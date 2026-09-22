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


def resolve(*, inputs, output, factors=None, where=""):
    """입력 node 집합과 출력 node로 operator를 확정한다.

    후보가 없거나 둘 이상이면 추측하지 않고 실패한다. 계획이 실행마다 달라지지
    않아야 하기 때문이다.
    """
    factors = dict(factors or {})
    matched = []
    for spec in candidates_for(output.concept, output.subtype):
        bound = _bind_ports(spec, inputs)
        if bound is not None:
            matched.append((spec, bound))

    if not matched:
        raise CompositionError(
            f"{where or output.id}: "
            f"{_describe(inputs)} → {output.concept.value}/{output.subtype} "
            "변환을 수행할 semantic operator가 없습니다.",
            code="NO_OPERATOR",
            context={
                "output": f"{output.concept.value}/{output.subtype}",
                "inputs": [
                    f"{node.concept.value}/{node.subtype}" for node in inputs
                ],
            },
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
    params, used = _resolve_params(spec, output, factors)
    return OperatorBinding(
        operator=spec.name,
        inputs={
            port: ValueRef(node.id, spec.inputs[port].field)
            for port, node in assigned.items()
        },
        params=params,
        used_factors=used,
    )


def _bind_ports(spec: OperatorSpec, inputs):
    """입력 node를 operator port에 결정적으로 배치한다.

    한 port에 후보가 둘 이상이면 배치하지 않는다. 출발지와 도착지를 임의로
    정하는 일이 없어야 하기 때문이다.
    """
    assigned: dict[str, ConceptNode] = {}
    for port, port_spec in spec.inputs.items():
        matches = [
            node for node in inputs
            if port_spec.binds(node.concept, node.subtype, node.attributes)
        ]
        if len(matches) > 1:
            return None
        if not matches:
            if port_spec.required:
                return None
            continue
        assigned[port] = matches[0]

    consumed = {node.id for node in assigned.values()}
    if any(node.id not in consumed for node in inputs):
        # 받아 줄 port가 없는 입력이 남아 있으면 이 operator는 그 조건을
        # 조용히 버리게 된다. 후보에서 제외한다.
        return None
    return assigned


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


def _resolve_params(spec, output, factors):
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
    _check_param_contract(spec, params)
    return params, frozenset(used)


def _check_param_contract(spec, params):
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
