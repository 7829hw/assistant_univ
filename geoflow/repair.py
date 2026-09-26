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

import copy
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
    elif decision.kind == RepairKind.PLACE_VALUE:
        _validate_place_delta(before, after, decision)
    else:
        raise RepairViolation(f"알 수 없는 재질의 종류입니다: {decision.kind}")
    return after


def _validate_place_delta(before, after, decision):
    """장소 값 수정. 고칠 대상은 조회에 실패한 개념 하나뿐이다."""
    previous = {item.id: item for item in before.concepts}
    current = {item.id: item for item in after.concepts}
    if set(previous) != set(current):
        raise RepairViolation("개념을 더하거나 뺄 수 없습니다.")
    if before.factors != after.factors:
        raise RepairViolation("조건(factor)은 그대로 두어야 합니다.")

    targets = set(decision.targets)
    for node_id, node in current.items():
        old = previous[node_id]
        if old.attributes != node.attributes:
            raise RepairViolation(f"{node_id}: 속성은 바꿀 수 없습니다.")
        if (old.concept, old.subtype, old.role, old.source) != (
            node.concept, node.subtype, node.role, node.source
        ):
            raise RepairViolation(
                f"{node_id}: 개념·subtype·role·출처는 바꿀 수 없습니다."
            )
        if _freeze(old.value) == _freeze(node.value):
            continue
        if node_id not in targets:
            raise RepairViolation(
                f"{node_id}: 조회에 실패한 개념이 아니므로 값을 바꿀 수 "
                "없습니다."
            )
        if not isinstance(node.value, dict) or sorted(node.value) != [
            "name", "region",
        ]:
            raise RepairViolation(f"{node_id}: 장소 값 형식이 아닙니다.")


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


# -- typed patch ------------------------------------------------------------
#
# 재질의는 생성 작업이 아니라 제한된 편집 작업이다. 예전에는 모델에게 고친
# grounding 전체를 다시 내놓으라고 했는데, 그러면 손대면 안 되는 부분까지
# 다시 쓰게 되어 실패 표면이 넓어진다. 지금은 "무엇을 더하거나 바꿀지"만
# 받고, 실제 수정은 아래 코드가 수행한다.


@dataclass(frozen=True)
class QualifierUpdate:
    concept_id: str
    attribute: str
    value: Any


@dataclass(frozen=True)
class RelationQualifierPatch:
    """장소 개념에 역할 속성만 덧붙인다."""

    updates: tuple[QualifierUpdate, ...]

    def to_dict(self):
        return {
            "kind": RepairKind.RELATION_QUALIFIER,
            "updates": [
                {
                    "concept_id": item.concept_id,
                    "attribute": item.attribute,
                    "value": item.value,
                }
                for item in self.updates
            ],
        }


@dataclass(frozen=True)
class FactorCompletionPatch:
    """짝이 빠진 조건만 덧붙인다."""

    factors: dict[str, Any]

    def to_dict(self):
        return {
            "kind": RepairKind.FACTOR_COMPLETION,
            "factors": dict(self.factors),
        }


@dataclass(frozen=True)
class PlaceValuePatch:
    """장소 하나의 이름과 상위 지역만 고친다."""

    concept_id: str
    name: str
    region: str = ""

    def to_dict(self):
        return {
            "kind": RepairKind.PLACE_VALUE,
            "concept_id": self.concept_id,
            "name": self.name,
            "region": self.region,
        }


PATCH_KEYS = {
    RepairKind.RELATION_QUALIFIER: ("updates",),
    RepairKind.FACTOR_COMPLETION: ("factors",),
    RepairKind.PLACE_VALUE: ("concept_id", "name", "region"),
}


def parse_patch(payload, grounding, decision):
    """모델이 제안한 수정안을 검증된 patch로 바꾼다.

    patch schema 자체가 첫 번째 방어선이다. 여기서 통과한 것만 코드가
    적용하고, 적용 결과는 ``validate_repair_delta``가 다시 확인한다.
    """
    if not isinstance(payload, dict):
        raise RepairViolation(
            f"수정안은 object여야 합니다. (받은 형식: {type(payload).__name__})"
        )
    allowed_keys = set(PATCH_KEYS.get(decision.kind) or ())
    unknown = sorted(set(payload) - allowed_keys - {"kind"})
    if unknown:
        raise RepairViolation(
            f"허용되지 않은 key가 있습니다: {', '.join(unknown)}. "
            f"허용: {', '.join(sorted(allowed_keys))}"
        )
    if decision.kind == RepairKind.RELATION_QUALIFIER:
        return _parse_relation_patch(payload, grounding, decision)
    if decision.kind == RepairKind.FACTOR_COMPLETION:
        return _parse_factor_patch(payload, grounding, decision)
    if decision.kind == RepairKind.PLACE_VALUE:
        return _parse_place_patch(payload, grounding, decision)
    raise RepairViolation(f"알 수 없는 재질의 종류입니다: {decision.kind}")


def _concepts_by_id(grounding):
    return {concept.id: concept for concept in grounding.concepts}


def _parse_relation_patch(payload, grounding, decision):
    from geoflow.types import CoreConcept

    raw = payload.get("updates")
    if not isinstance(raw, list) or not raw:
        raise RepairViolation("updates는 비어 있지 않은 list여야 합니다.")

    concepts = _concepts_by_id(grounding)
    allowed_attributes = set(decision.allowed_additions) & registry_qualifiers()
    targets = set(decision.targets)
    seen = set()
    updates = []
    for index, item in enumerate(raw):
        where = f"updates[{index}]"
        if not isinstance(item, dict):
            raise RepairViolation(f"{where}: object여야 합니다.")
        unknown = sorted(set(item) - {"concept_id", "attribute", "value"})
        if unknown:
            raise RepairViolation(
                f"{where}: 허용되지 않은 key입니다: {', '.join(unknown)}"
            )
        concept_id = item.get("concept_id")
        attribute = item.get("attribute")
        value = item.get("value")
        concept = concepts.get(concept_id)
        if concept is None:
            raise RepairViolation(
                f"{where}: 없는 개념입니다: {concept_id!r}. "
                f"있는 개념: {', '.join(sorted(concepts))}"
            )
        if concept_id not in targets:
            raise RepairViolation(
                f"{where}: 이 개념은 수정 대상이 아닙니다: {concept_id}"
            )
        if concept.concept != CoreConcept.LOCATION:
            raise RepairViolation(
                f"{where}: 장소 개념에만 속성을 덧붙일 수 있습니다: {concept_id}"
            )
        if attribute not in allowed_attributes:
            raise RepairViolation(
                f"{where}: 덧붙일 수 없는 속성입니다: {attribute!r}. "
                f"허용: {', '.join(sorted(allowed_attributes))}"
            )
        if attribute in concept.attributes:
            raise RepairViolation(
                f"{where}: 이미 있는 속성을 덮어쓸 수 없습니다: {attribute}"
            )
        if (concept_id, attribute) in seen:
            raise RepairViolation(f"{where}: 같은 속성을 두 번 지정했습니다.")
        seen.add((concept_id, attribute))
        updates.append(QualifierUpdate(concept_id, attribute, value))
    return RelationQualifierPatch(tuple(updates))


def _parse_factor_patch(payload, grounding, decision):
    raw = payload.get("factors")
    if not isinstance(raw, dict) or not raw:
        raise RepairViolation("factors는 비어 있지 않은 object여야 합니다.")
    allowed = set(decision.allowed_additions)
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise RepairViolation(
            f"덧붙일 수 없는 조건입니다: {', '.join(unknown)}. "
            f"허용: {', '.join(sorted(allowed))}"
        )
    existing = sorted(set(raw) & set(grounding.factors))
    if existing:
        raise RepairViolation(
            f"이미 있는 조건을 덮어쓸 수 없습니다: {', '.join(existing)}"
        )
    missing = sorted(allowed - set(raw))
    if missing:
        raise RepairViolation(
            f"빠진 조건을 모두 채워야 합니다: {', '.join(missing)}"
        )
    return FactorCompletionPatch(dict(raw))


def _parse_place_patch(payload, grounding, decision):
    concepts = _concepts_by_id(grounding)
    concept_id = payload.get("concept_id")
    concept = concepts.get(concept_id)
    if concept is None:
        raise RepairViolation(
            f"없는 개념입니다: {concept_id!r}. "
            f"있는 개념: {', '.join(sorted(concepts))}"
        )
    if decision.targets and concept_id not in set(decision.targets):
        raise RepairViolation(
            f"이 개념은 수정 대상이 아닙니다: {concept_id}"
        )
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise RepairViolation("name이 비어 있습니다.")
    region = payload.get("region") or ""
    if not isinstance(region, str):
        raise RepairViolation("region은 문자열이어야 합니다.")
    return PlaceValuePatch(concept_id, name.strip(), region.strip())


def apply_patch(grounding, patch):
    """검증된 patch를 grounding에 적용해 새 grounding을 만든다.

    직렬화한 표현 위에서 수정하고 다시 읽어 들인다. 결과가 grounding 계약을
    처음부터 다시 통과하므로, 수정된 값이라고 검증을 건너뛰는 경로가 생기지
    않는다. 입력 grounding은 바꾸지 않는다.
    """
    from geoflow.grounding import parse_grounding

    payload = grounding.to_dict()
    by_id = {item["id"]: item for item in payload["concepts"]}

    if isinstance(patch, RelationQualifierPatch):
        for update in patch.updates:
            concept = by_id[update.concept_id]
            attributes = dict(concept.get("attributes") or {})
            attributes[update.attribute] = update.value
            concept["attributes"] = attributes
    elif isinstance(patch, FactorCompletionPatch):
        payload["factors"] = {**payload["factors"], **patch.factors}
    elif isinstance(patch, PlaceValuePatch):
        by_id[patch.concept_id]["value"] = {
            "name": patch.name, "region": patch.region,
        }
    else:
        raise RepairViolation(f"알 수 없는 patch입니다: {type(patch).__name__}")

    structured = grounding.aggregation_plan
    if structured is not None and isinstance(patch, FactorCompletionPatch):
        # 구조화 집계가 있는데 flat 집계 factor를 덧붙이면 두 표현이 섞인다.
        raise RepairViolation("구조화 집계가 있는 grounding에 집계 factor를 덧붙일 수 없습니다.")
    repaired = parse_grounding(payload, grounding.question)
    # 직렬화 표현(factors)에는 구조화 집계가 없다. 수정 대상이 아니므로 그대로 옮긴다.
    # 옮기지 않으면 장소 값 수정만으로 집계 의미가 조용히 사라진다.
    repaired.aggregation_plan = structured
    repaired.condition_audit = _carry_condition_audit(grounding, patch)
    return repaired


def _carry_condition_audit(grounding, patch):
    """조건 기록을 옮기고, 장소 값이 바뀌면 원래 근거와 수정 이력을 남긴다."""
    audit = grounding.condition_audit
    if audit is None:
        return None
    audit = copy.deepcopy(audit)
    if isinstance(patch, PlaceValuePatch):
        for record in audit.get("places") or []:
            if record.get("id") != patch.concept_id:
                continue
            record.setdefault("history", []).append({
                "from": {"name": record.get("lookup_name"), "region": record.get("region")},
                "to": {"name": patch.name, "region": patch.region},
                "reason": "place_value_repair",
            })
            record["lookup_name"], record["region"] = patch.name, patch.region
    return audit
