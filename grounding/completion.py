# -*- coding: utf-8 -*-
"""Partial Grounding structural completion(subtype → concept, role, source, id). ``grounding_target: partial``에서만 쓴다.

원본: ``geoflow/partial-grounding`` 커밋 ``ab9d215``의 ``geoflow/grounding.py``
(``_CONCEPT_OF_SUBTYPE``, ``_inferred_fields``, ``complete_grounding_payload``). 본문은 원본과 같다.
결정 111(D6): Full 경로와 ``SEMANTIC_CODE``(지문 ``791c4a68``)를 바꾸지 않도록 ``geoflow/`` 밖에 둔다.

원본과 다른 점 하나(``_tag_condition_object``): 원본은 ``hoist_condition_concepts``가 concept이 빈 개념을 OBJECT로 보도록
``geoflow/grounding.py``를 고쳤다. 이식본은 그 함수를 고치지 않는 대신, 원본 hoist가 OBJECT로 보고 factor로 옮기는 개념
(조건 값 subtype, 또는 subtype 없이 조건 값 value)의 빈 concept을 ``OBJECT``로 채운다. 그러면 trunk hoist가 같은 개념을 옮긴다.
hoist가 옮기지 못하고 남기는 경우(같은 factor에 다른 값)에는 원본은 concept 없음, 이식본은 OBJECT로 남아 거부 오류 코드가 다를 수 있다
(``pilot_006_prep/integration`` W4 5에서 문항 단위로 비교).
"""
from geoflow.grounding import _CONDITION_SUBTYPES
from geoflow.types import (
    CONCEPT_SUBTYPES,
    SCOPE_SUBTYPES,
    CoreConcept,
    FunctionalRole,
    NodeSource,
    Subtype,
)

#: subtype 하나가 속하는 core concept. subtype 이름은 concept 사이에 겹치지 않는다(``CONCEPT_SUBTYPES``).
_CONCEPT_OF_SUBTYPE = {subtype: concept.value
                       for concept, subtypes in CONCEPT_SUBTYPES.items() for subtype in subtypes}


def _inferred_fields(raw):
    """subtype과 value 유무만으로 정해지는 concept·role·source. 정할 수 없으면 그 필드는 None이다.

    - subtype → concept: ``CONCEPT_SUBTYPES``의 역방향 표.
    - role: 측정값 subtype(AMOUNT·PROPORTION)은 MEASURE, EVENT는 SUPPORT, scope는 COND.
      LOCATION/place는 값이 있으면 조건(SUBCOND), 없으면 답이 장소인 질문의 MEASURE다.
    - source: 조건(SUBCOND·COND)은 사용자가 말한 값(user), 사건과 측정값은 implicit.
    """
    subtype = raw.get("subtype")
    concept = _CONCEPT_OF_SUBTYPE.get(subtype.strip()) if isinstance(subtype, str) else None
    if concept is None:
        return {"concept": None, "role": None, "source": None}
    subtype = subtype.strip()
    if concept in (CoreConcept.AMOUNT.value, CoreConcept.PROPORTION.value):
        role = FunctionalRole.MEASURE.value
    elif concept == CoreConcept.EVENT.value:
        role = FunctionalRole.SUPPORT.value
    elif subtype in SCOPE_SUBTYPES:
        role = FunctionalRole.COND.value
    elif subtype == Subtype.PLACE:
        role = (FunctionalRole.MEASURE.value if raw.get("value") in (None, "", {})
                else FunctionalRole.SUBCOND.value)
    else:
        role = None
    source = None
    if role in (FunctionalRole.SUBCOND.value, FunctionalRole.COND.value):
        source = NodeSource.USER.value
    elif role in (FunctionalRole.SUPPORT.value, FunctionalRole.MEASURE.value):
        source = NodeSource.IMPLICIT.value
    return {"concept": concept, "role": role, "source": source}


def _tag_condition_object(raw):
    """원본 ``hoist_condition_concepts``의 ``as_object``(concept 없음 = OBJECT)를 대신한다. 채웠으면 True."""
    if raw.get("concept") not in (None, ""):
        return False
    subtype = raw.get("subtype")
    value = raw.get("value") if isinstance(raw.get("value"), str) else None
    if (not subtype and value in _CONDITION_SUBTYPES) or (isinstance(subtype, str) and subtype in _CONDITION_SUBTYPES):
        raw["concept"] = CoreConcept.OBJECT.value
        return True
    return False


def complete_grounding_payload(payload, notes=None):
    """생략된 구조 필드를 ontology에서 채운다(Partial Grounding). 질문 원문은 읽지 않는다.

    LLM이 subtype과 value(장소 값, od_role 등 뜻을 정하는 부분)만 적어도 기존 Grounding과 같은
    payload가 되게 한다.

    1. concept·role·source가 비었으면 ``_inferred_fields``로 채운다.
    2. id가 없으면 ``{subtype}_{순번}``을 붙인다(이미 쓰인 id와 겹치지 않게).

    적어 둔 값은 바꾸지 않고 기존 계약 검사에 맡긴다. concept이 subtype과 어긋나면
    ``INVALID_SUBTYPE``으로 거부된다. role은 추론과 달라도 거부하지 않는다. 값이 있는 장소를
    EXTENT로 적는 것, 그룹 단위 말을 값 없는 SUBCOND 장소로 적어 정리 규칙이 빼는 것이 기존 계약에서
    성립하기 때문이다. support EVENT는 채우지 않는다. 측정값에서 하나로 정해지는 사건은 composer가
    이미 만든다(``MacroComposer._infer_port``). 정할 수 없는 경우(모르는 subtype)도 채우지 않고
    기존 검사가 거부하게 한다. 이미 완전한 payload는 그대로 돌려준다(멱등).
    """
    concepts = payload.get("concepts") if isinstance(payload, dict) else None
    if not isinstance(concepts, list):
        return payload
    completed, filled = [], []
    for index, raw in enumerate(concepts):
        if not isinstance(raw, dict):
            completed.append(raw)
            continue
        raw = dict(raw)
        for key, want in _inferred_fields(raw).items():
            if want is not None and raw.get(key) in (None, ""):
                raw[key] = want
                filled.append(f"concepts[{index}].{key}")
        if _tag_condition_object(raw):
            filled.append(f"concepts[{index}].concept(OBJECT, condition hoist)")
        completed.append(raw)

    taken = {raw["id"] for raw in completed
             if isinstance(raw, dict) and isinstance(raw.get("id"), str) and raw["id"].strip()}
    counters = {}
    for index, raw in enumerate(completed):
        if not isinstance(raw, dict) or raw.get("id") not in (None, ""):
            continue
        base = raw.get("subtype").strip() if isinstance(raw.get("subtype"), str) else ""
        base = base or "concept"
        while True:
            counters[base] = counters.get(base, 0) + 1
            candidate = f"{base}_{counters[base]}"
            if candidate not in taken:
                break
        raw["id"] = candidate
        taken.add(candidate)
        filled.append(f"concepts[{index}].id")

    if not filled:
        return payload
    if notes is not None:
        notes.append({"rule": "partial_grounding_completed", "filled": filled})
    return {**payload, "concepts": completed}
