# -*- coding: utf-8 -*-
"""계획 단계 실패의 복구 가능성 판정과 mutation guard.

계획을 만들지 못한 모든 실패를 다시 물어보지 않는다. 다시 물어서 얻을 수
있는 것은 **현재 계약 안에서 표현할 수 있는데 빠진 정보**뿐이다.

    "초읍동에서 출발하여 초량동에 도착한 건수"
        장소 둘의 관계가 승차/하차다. od_role이라는 표현 수단이 이미 있고
        모델이 그것을 빠뜨렸을 뿐이다.            → 다시 물어볼 만하다

    "대구와 부산 중 어디가 더 빠른가요?"
        장소 둘의 관계가 비교다. 지금 grounding schema에도 macro library에도
        비교를 표현할 방법이 없다.                → 다시 물어봐야 소용없다

두 경우 모두 "LOCATION이 둘인데 구분이 없다"로 똑같이 실패하므로, 오류 코드만
보고 판정하면 뒤엣것까지 재질의하게 된다. 그러면 모델은 요구받은 대로 없는
관계를 있는 것처럼 꾸며 내고, 지원하지 않는 질문이 그럴듯한 오답으로 바뀐다.

그래서 판정 근거를 오류의 구조화된 context와 registry 계약으로 한정한다.
질문 문자열은 보지 않는다.
"""

from dataclasses import dataclass, field
from typing import Any

from geoflow.factors import FACTOR_CONSTRAINTS
from geoflow.operator_registry import OPERATORS


class RepairKind:
    """재질의의 종류. 종류마다 허용하는 수정 범위가 다르다."""

    #: 장소 조회가 실패해 이름/상위 지역만 고친다. Tool 오류에서 온다.
    PLACE_VALUE = "place_value"
    #: 장소가 분석에서 어떤 역할인지 나타내는 속성만 덧붙인다.
    RELATION_QUALIFIER = "relation_qualifier"
    #: 짝이 빠진 조건 하나만 덧붙인다.
    FACTOR_COMPLETION = "factor_completion"


#: registry의 port 계약에 실제로 쓰이는 속성 이름. 모델이 새 속성을 발명하는
#: 것을 막기 위해 정의에서 직접 만든다.
def registry_qualifiers():
    return frozenset(
        key
        for spec in OPERATORS.values()
        for port_spec in spec.inputs.values()
        for key, _ in port_spec.match_attributes
    )


@dataclass(frozen=True)
class RepairDecision:
    """계획 단계 실패 하나에 대한 재질의 판정."""

    repairable: bool
    reason: str
    kind: str | None = None
    #: 수정이 허용되는 대상. 종류에 따라 개념 id 또는 factor 이름이다.
    targets: tuple[str, ...] = ()
    #: 덧붙이는 것이 허용된 이름. 속성 키 또는 factor 이름.
    allowed_additions: tuple[str, ...] = ()
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "repairable": self.repairable,
            "kind": self.kind,
            "reason": self.reason,
            "targets": list(self.targets),
            "allowed_additions": list(self.allowed_additions),
        }


NOT_REPAIRABLE = RepairDecision(
    repairable=False, reason="다시 물어서 복구할 수 있는 실패가 아닙니다.",
)


def decide(error):
    """``GeoFlowError`` 하나를 보고 재질의 여부와 범위를 정한다.

    근거는 오류 코드, 오류가 남긴 구조화 context, registry/factor 계약뿐이다.
    """
    code = getattr(error, "code", None)
    context = dict(getattr(error, "context", None) or {})
    if code == "MISSING_RELATION_QUALIFIER":
        return _decide_relation(context, ambiguous=False)
    if code == "AMBIGUOUS_LOCATION_RELATION":
        return _decide_relation(context, ambiguous=True)
    if code == "INVALID_FACTOR_COMBINATION":
        return _decide_factor(context)
    return NOT_REPAIRABLE


def _decide_relation(context, *, ambiguous):
    """장소의 관계가 빠진 실패를 판정한다.

    핵심은 "지금 계약에 이 관계를 적을 자리가 있는가"다. 오류가 남긴
    required_qualifiers가 비어 있다면, 후보 operator 어디에도 속성 한정
    port가 없다는 뜻이다. 즉 장소들의 관계를 적을 자리 자체가 없다. 비교
    질의가 여기에 해당하며, 다시 물어도 표현할 수단이 생기지 않는다.
    """
    required = tuple(context.get("required_qualifiers") or ())
    unqualified = tuple(context.get("unqualified") or ())
    if not required:
        return RepairDecision(
            repairable=False,
            reason=(
                "장소들의 관계를 적을 수 있는 속성이 현재 계약에 없습니다. "
                "다시 물어도 표현할 수단이 생기지 않습니다."
            ),
            context=context,
        )

    unknown = sorted(set(required) - registry_qualifiers())
    if unknown:
        return RepairDecision(
            repairable=False,
            reason=(
                "registry가 쓰지 않는 속성을 요구하고 있습니다: "
                + ", ".join(unknown)
            ),
            context=context,
        )
    if not unqualified:
        return RepairDecision(
            repairable=False,
            reason="속성을 덧붙일 장소가 지정되지 않았습니다.",
            context=context,
        )

    return RepairDecision(
        repairable=True,
        kind=RepairKind.RELATION_QUALIFIER,
        reason=(
            "장소의 역할을 나타내는 속성이 계약에 이미 있고, 기존 개념에 그"
            " 속성만 덧붙이면 됩니다."
        ),
        targets=unqualified,
        allowed_additions=required,
        context={**context, "ambiguous": ambiguous},
    )


def _decide_factor(context):
    """짝이 빠진 조건을 판정한다.

    빠진 조건이 factor 어휘에 있고, 그 조건 하나만 덧붙이면 되는 경우만
    다시 묻는다. 값을 임의로 정해 채우지 않는다.
    """
    factor = context.get("factor")
    missing = tuple(context.get("missing") or ())
    if not missing:
        return RepairDecision(
            repairable=False,
            reason="어떤 조건이 빠졌는지 오류에 적혀 있지 않습니다.",
            context=context,
        )
    unknown = sorted(set(missing) - set(FACTOR_CONSTRAINTS.get(factor).requires
                                        if factor in FACTOR_CONSTRAINTS else ())
                     )
    if unknown:
        return RepairDecision(
            repairable=False,
            reason=(
                "factor 불변식이 요구하지 않는 조건입니다: " + ", ".join(unknown)
            ),
            context=context,
        )
    return RepairDecision(
        repairable=True,
        kind=RepairKind.FACTOR_COMPLETION,
        reason=(
            "빠진 조건이 factor 어휘에 있고, 그 조건만 덧붙이면 성립합니다."
        ),
        targets=(factor,) if factor else (),
        allowed_additions=missing,
        context=context,
    )


# -- mutation guard ---------------------------------------------------------


class RepairViolation(ValueError):
    """재질의 결과가 허용 범위를 벗어났다."""


def _concept_shape(concept):
    """수정이 허용되지 않는 부분만 뽑는다."""
    return (
        concept.concept,
        concept.subtype,
        concept.role,
        concept.source,
        _freeze(concept.value),
    )


def _freeze(value):
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def validate_repair_delta(before, after, decision):
    """재질의 결과가 허용된 수정만 했는지 코드로 확인한다.

    요청문에 무엇을 하라고 적어 두는 것만으로는 부족하다. 모델은 요청받지
    않은 부분까지 손대며, 그 수정이 이미 성공한 조회를 망가뜨리는 경우가
    관측되었다. 허용 범위는 여기서 강제한다.
    """
    if decision.kind == RepairKind.RELATION_QUALIFIER:
        _validate_relation_delta(before, after, decision)
    elif decision.kind == RepairKind.FACTOR_COMPLETION:
        _validate_factor_delta(before, after, decision)
    else:
        raise RepairViolation(f"알 수 없는 재질의 종류입니다: {decision.kind}")
    return after


def _validate_relation_delta(before, after, decision):
    previous = {item.id: item for item in before.concepts}
    current = {item.id: item for item in after.concepts}
    if set(previous) != set(current):
        added = sorted(set(current) - set(previous))
        removed = sorted(set(previous) - set(current))
        raise RepairViolation(
            "개념을 더하거나 뺄 수 없습니다. "
            f"추가: {added or '없음'} / 삭제: {removed or '없음'}"
        )
    if before.factors != after.factors:
        raise RepairViolation("조건(factor)은 그대로 두어야 합니다.")

    allowed = set(decision.allowed_additions)
    for node_id, node in current.items():
        old = previous[node_id]
        if _concept_shape(old) != _concept_shape(node):
            raise RepairViolation(
                f"{node_id}: 개념·subtype·role·출처·값은 바꿀 수 없습니다."
            )
        added = set(node.attributes) - set(old.attributes)
        outside = sorted(added - allowed)
        if outside:
            raise RepairViolation(
                f"{node_id}: 허용되지 않은 속성을 덧붙였습니다: "
                + ", ".join(outside)
            )
        for key, value in old.attributes.items():
            if node.attributes.get(key) != value:
                raise RepairViolation(
                    f"{node_id}: 이미 있던 속성 {key!r}을 바꿨습니다."
                )


def _validate_factor_delta(before, after, decision):
    previous = {item.id: item for item in before.concepts}
    current = {item.id: item for item in after.concepts}
    if set(previous) != set(current):
        raise RepairViolation("개념은 그대로 두어야 합니다.")
    for node_id, node in current.items():
        old = previous[node_id]
        if _concept_shape(old) != _concept_shape(node) or (
            old.attributes != node.attributes
        ):
            raise RepairViolation(f"{node_id}: 개념을 바꿀 수 없습니다.")

    allowed = set(decision.allowed_additions)
    added = set(after.factors) - set(before.factors)
    outside = sorted(added - allowed)
    if outside:
        raise RepairViolation(
            "허용되지 않은 조건을 덧붙였습니다: " + ", ".join(outside)
        )
    removed = sorted(set(before.factors) - set(after.factors))
    if removed:
        raise RepairViolation(
            "있던 조건을 뺄 수 없습니다: " + ", ".join(removed)
        )
    for name, value in before.factors.items():
        if after.factors.get(name) != value:
            raise RepairViolation(f"이미 있던 조건 {name!r}의 값을 바꿨습니다.")
    still_missing = sorted(allowed - set(after.factors))
    if still_missing:
        raise RepairViolation(
            "빠진 조건이 그대로입니다: " + ", ".join(still_missing)
        )
