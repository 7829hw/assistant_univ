# -*- coding: utf-8 -*-
"""Concept grounding 계약.

Planner LLM의 새 책임은 "질문을 어떤 유형으로 분류할 것인가"가 아니라
"질문의 표현이 어떤 core concept / subtype / functional role에 해당하는가"다.
이 모듈은 그 출력의 형식을 정의하고 검증한다.

    {
      "concepts": [
        {"id": "place_1", "text": "동대구역", "concept": "LOCATION",
         "subtype": "place", "role": "SUBCOND", "source": "user",
         "value": {"name": "동대구역", "region": ""}},
        {"id": "passage", "concept": "EVENT", "subtype": "passage",
         "role": "SUPPORT", "source": "implicit"},
        {"id": "speed", "concept": "AMOUNT", "subtype": "speed",
         "role": "MEASURE", "source": "implicit"}
      ],
      "factors": {"date": "20260530", "aggregation": "avg", "vicinity": true}
    }

Planner 출력은 전부 untrusted input이다. 여기서 형식을 확인하고, 그 뒤
composer가 만든 graph를 Validator가 다시 확인한다.

이 모듈이 읽는 factor는 내부 어휘다. Planner LLM은 집계를 ``aggregation_plan``
으로 적고, ``geoflow.aggregation.lower_raw_grounding``이 먼저 위의 flat factor
(bucket·aggregation·rollup)로 내린다. 재질의가 만든 grounding도 이 어휘다.

factor의 어휘와 공기(co-occurrence) 불변식은 ``geoflow/factors.py``가 갖는다.
개념이 아니라 조건에 속하는 규칙이고, 특정 Tool이나 질문 유형과 무관하기
때문이다. 이 모듈은 그 어휘로 값의 형식만 읽는다. 조건끼리의 공기 불변식은
합성 진입점에서 확인한다. 계획을 만들기 전 단계여야 재질의로 복구할 수 있기
때문이다.
"""

from dataclasses import dataclass, field
from typing import Any

from agent_graph import extract_scopes

from geoflow.errors import PlannerError
from geoflow.factors import FACTOR_SPECS, STRUCTURAL_FACTORS, FactorSpec
from geoflow.operator_mapping import measure_types
from geoflow.types import (
    CONCEPT_SUBTYPES,
    SCOPE_SUBTYPES,
    ConceptNode,
    CoreConcept,
    FunctionalRole,
    NodeSource,
    Subtype,
    subtype_allowed,
)

#: grounding이 선언할 수 있는 출처. tool/derived는 실행이 만드는 값이므로
#: LLM이 주장할 수 없다.
GROUNDED_SOURCES = frozenset({NodeSource.USER, NodeSource.IMPLICIT})

#: 승하차 구분 속성. OD 변환의 port 선택 근거가 된다.
OD_ROLE = "od_role"
OD_ROLES = frozenset({"pickup", "dropoff"})

_PLACE_FIELDS = ("name", "region")


@dataclass
class GroundedConcept:
    """질문에서 읽어 낸 개념 하나."""

    id: str
    concept: CoreConcept
    subtype: str
    role: FunctionalRole
    source: NodeSource
    value: Any = None
    text: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)

    @property
    def od_role(self):
        return self.attributes.get(OD_ROLE)

    def to_node(self):
        """검증에 쓰는 ``ConceptNode``로 바꾼다."""
        return ConceptNode(
            id=self.id,
            concept=self.concept,
            subtype=self.subtype,
            role=self.role,
            source=self.source,
            value=self.value,
            attributes=dict(self.attributes),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "concept": self.concept.value,
            "subtype": self.subtype,
            "role": self.role.value,
            "source": self.source.value,
            "value": self.value,
            "attributes": dict(self.attributes),
        }


@dataclass
class Grounding:
    """한 질문의 grounding 결과."""

    question: str
    concepts: list[GroundedConcept] = field(default_factory=list)
    factors: dict[str, Any] = field(default_factory=dict)

    @property
    def measure(self):
        for concept in self.concepts:
            if concept.role == FunctionalRole.MEASURE:
                return concept
        return None

    def by_role(self, role):
        return [item for item in self.concepts if item.role == role]

    def by_concept(self, concept):
        return [item for item in self.concepts if item.concept == concept]

    def get(self, concept_id):
        for concept in self.concepts:
            if concept.id == concept_id:
                return concept
        return None

    def to_dict(self):
        return {
            "concepts": [item.to_dict() for item in self.concepts],
            "factors": dict(self.factors),
        }


def parse_grounding(payload, question, *, raw_text=""):
    """Planner 출력 payload를 검증된 ``Grounding``으로 바꾼다."""
    if not isinstance(payload, dict):
        raise PlannerError(
            f"grounding 최상위는 object여야 합니다. "
            f"(받은 형식: {type(payload).__name__})",
            code="INVALID_GROUNDING",
            context={"raw_text": raw_text},
        )

    raw_concepts, hoisted = _hoist_structural_factors(payload.get("concepts"))
    if not isinstance(raw_concepts, list) or not raw_concepts:
        raise PlannerError(
            "grounding의 concepts는 비어 있지 않은 list여야 합니다.",
            code="MISSING_CONCEPTS",
            context={"raw_text": raw_text},
        )

    concepts = []
    seen_ids = set()
    for index, raw in enumerate(raw_concepts):
        concept = _parse_concept(f"concepts[{index}]", raw, question, raw_text)
        if concept.id in seen_ids:
            raise PlannerError(
                f"concept id가 중복되었습니다: {concept.id}",
                code="DUPLICATE_CONCEPT_ID",
                context={"raw_text": raw_text},
            )
        seen_ids.add(concept.id)
        concepts.append(concept)

    factors = _parse_factors(
        {**hoisted, **(payload.get("factors") or {})}, raw_text,
    )
    grounding = Grounding(
        question=question, concepts=concepts, factors=factors,
    )
    _check_measure(grounding, raw_text)
    return grounding


def _hoist_structural_factors(raw_concepts):
    """개념에 붙여 적은 구조 factor를 factors 쪽으로 옮긴다.

    "근처"는 장소를 수식하는 말이라 모델이 vicinity를 장소 개념 안에 적는
    경우가 잦다. 뜻은 같고 둘 수 있는 자리만 다르므로 거부하지 않고 옮긴다.
    od_role을 attributes 안팎 어디에 적어도 받는 것과 같은 취지다.

    값을 만들어 내는 것이 아니라 위치만 바로잡는 것이므로, 질문에 없는 조건이
    새로 생기지 않는다. 명시적으로 적은 factors가 우선한다.
    """
    if not isinstance(raw_concepts, list):
        return raw_concepts, {}
    hoisted = {}
    cleaned = []
    for raw in raw_concepts:
        if not isinstance(raw, dict):
            cleaned.append(raw)
            continue
        raw = dict(raw)
        attributes = dict(raw.get("attributes") or {})
        for name in STRUCTURAL_FACTORS:
            if name in attributes:
                hoisted.setdefault(name, attributes.pop(name))
            if name in raw:
                hoisted.setdefault(name, raw.pop(name))
        if "attributes" in raw:
            raw["attributes"] = attributes
        cleaned.append(raw)
    return cleaned, hoisted


def _parse_concept(where, raw, question, raw_text):
    if not isinstance(raw, dict):
        raise PlannerError(
            f"{where}: object여야 합니다.",
            code="INVALID_CONCEPT",
            context={"raw_text": raw_text},
        )
    unknown = sorted(
        set(raw) - {
            "id", "text", "concept", "subtype", "role", "source",
            "value", "attributes", OD_ROLE,
        }
    )
    if unknown:
        raise PlannerError(
            f"{where}: 허용되지 않은 key가 있습니다: {', '.join(unknown)}",
            code="UNKNOWN_CONCEPT_KEY",
            context={"raw_text": raw_text},
        )

    for key in ("id", "concept", "subtype", "role"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise PlannerError(
                f"{where}: {key}가 비어 있습니다.",
                code="INVALID_CONCEPT",
                context={"raw_text": raw_text},
            )

    concept = _require_enum(where, "concept", raw["concept"], CoreConcept, raw_text)
    role = _require_enum(where, "role", raw["role"], FunctionalRole, raw_text)
    source = _require_enum(
        where, "source", raw.get("source", NodeSource.IMPLICIT.value),
        NodeSource, raw_text,
    )
    if source not in GROUNDED_SOURCES:
        raise PlannerError(
            f"{where}: source는 "
            f"{', '.join(sorted(item.value for item in GROUNDED_SOURCES))} "
            f"중 하나여야 합니다. (받은 값: {source.value})",
            code="INVALID_CONCEPT_SOURCE",
            context={"raw_text": raw_text},
        )

    subtype = raw["subtype"].strip()
    # concept과 subtype의 짝을 IR 어휘와 대조한다. 예전에는 MEASURE만 확인해서
    # OBJECT/taxi_type 같은 조합이 합성 단계까지 흘러간 뒤 "쓰이지 않은 개념"
    # 으로 나타났다. 원인과 먼 곳에서 실패하므로 여기서 바로 거부한다.
    if not subtype_allowed(concept, subtype):
        allowed = ", ".join(sorted(CONCEPT_SUBTYPES.get(concept) or ()))
        raise PlannerError(
            f"{where}: {concept.value}에 없는 subtype입니다: {subtype!r}. "
            f"허용: {allowed or '(이 concept에는 사용할 수 있는 subtype이 없습니다)'}",
            code="INVALID_SUBTYPE",
            context={
                "raw_text": raw_text,
                "concept": concept.value,
                "subtype": subtype,
            },
        )

    value = _coerce_value(where, concept, subtype, raw.get("value"), raw_text)
    attributes = _parse_attributes(where, raw, raw_text)

    if source == NodeSource.USER and value is None:
        raise PlannerError(
            f"{where}: 사용자가 말한 개념이라면 값이 있어야 합니다.",
            code="MISSING_CONCEPT_VALUE",
            context={"raw_text": raw_text},
        )

    if (
        source == NodeSource.IMPLICIT
        and value is None
        and concept != CoreConcept.EVENT
        and role != FunctionalRole.MEASURE
    ):
        # 값 없는 implicit 개념은 두 경우만 성립한다. 사건(EVENT)은 개념 이름이
        # 곧 값이고, 측정값(MEASURE)은 실행이 채운다. 그 밖에는 조회에 쓸 값이
        # 없으므로 조건으로 쓸 수 없다. 장소가 없는 질문에 빈 LOCATION/place를
        # 만들어 두면 compiler까지 내려가 참조 오류로 터지던 경로다.
        raise PlannerError(
            f"{where}: 값이 없는 {concept.value}/{subtype} 개념은 조건으로 "
            "쓸 수 없습니다. 질문에 근거가 없다면 개념을 만들지 마세요.",
            code="VALUELESS_CONCEPT",
            context={
                "raw_text": raw_text,
                "concept": concept.value,
                "subtype": subtype,
            },
        )

    if subtype in SCOPE_SUBTYPES:
        # scope는 사용자가 그대로 적은 값만 인정한다. G6가 다시 확인하지만
        # 여기서 먼저 막아야 재계획 경로가 헛돌지 않는다.
        if source != NodeSource.USER:
            raise PlannerError(
                f"{where}: scope는 사용자가 직접 적은 값만 쓸 수 있습니다.",
                code="INVALID_SCOPE_SOURCE",
                context={"raw_text": raw_text},
            )
        if value not in set(extract_scopes(question)):
            raise PlannerError(
                f"{where}: 사용자 발화에 없는 scope입니다: {value!r}. "
                "scope 값을 직접 생성할 수 없습니다.",
                code="UNGROUNDED_SCOPE",
                context={"raw_text": raw_text, "scope": value},
            )

    return GroundedConcept(
        id=raw["id"].strip(),
        concept=concept,
        subtype=subtype,
        role=role,
        source=source,
        value=value,
        text=str(raw.get("text") or "").strip(),
        attributes=attributes,
    )


def _parse_attributes(where, raw, raw_text):
    attributes = raw.get("attributes")
    if attributes is None:
        attributes = {}
    if not isinstance(attributes, dict):
        raise PlannerError(
            f"{where}.attributes: object여야 합니다.",
            code="INVALID_CONCEPT",
            context={"raw_text": raw_text},
        )
    attributes = dict(attributes)
    # 모델이 attributes 안이 아니라 밖에 적는 경우가 잦아 둘 다 받는다.
    if OD_ROLE in raw:
        attributes[OD_ROLE] = raw[OD_ROLE]

    od_role = attributes.get(OD_ROLE)
    if od_role is not None and od_role not in OD_ROLES:
        raise PlannerError(
            f"{where}.{OD_ROLE}: {', '.join(sorted(OD_ROLES))} 중 하나여야 "
            f"합니다. (받은 값: {od_role!r})",
            code="INVALID_OD_ROLE",
            context={"raw_text": raw_text},
        )
    unknown = sorted(set(attributes) - {OD_ROLE})
    if unknown:
        raise PlannerError(
            f"{where}.attributes: 허용되지 않은 속성입니다: "
            f"{', '.join(unknown)}",
            code="UNKNOWN_ATTRIBUTE",
            context={"raw_text": raw_text},
        )
    return attributes


def _coerce_value(where, concept, subtype, value, raw_text):
    """값이 있으면 형식을 맞춘다.

    값이 없는 개념도 정상이다. "이 범위가 어디인가"를 묻는 질문의 장소처럼
    실행이 채울 개념은 grounding 시점에 값을 가질 수 없다. 다만 사용자가
    말했다고 선언한 개념(source=user)은 값이 있어야 한다.
    """
    if value in ("", None):
        return None
    if concept == CoreConcept.LOCATION and subtype == Subtype.PLACE:
        return _coerce_place(where, value, raw_text)
    return value


def _coerce_place(where, value, raw_text):
    if isinstance(value, str):
        value = {"name": value}
    if not isinstance(value, dict):
        raise PlannerError(
            f"{where}: 장소 개념의 value는 {{name, region}} object여야 합니다. "
            f"(받은 형식: {type(value).__name__})",
            code="INVALID_PLACE",
            context={"raw_text": raw_text},
        )
    unknown = sorted(set(value) - set(_PLACE_FIELDS))
    if unknown:
        raise PlannerError(
            f"{where}: 장소 개념에 허용되지 않은 필드가 있습니다: "
            f"{', '.join(unknown)}",
            code="INVALID_PLACE",
            context={"raw_text": raw_text},
        )
    name = value.get("name")
    if not isinstance(name, str) or not name.strip():
        raise PlannerError(
            f"{where}: 장소 개념의 name이 비어 있습니다.",
            code="INVALID_PLACE",
            context={"raw_text": raw_text},
        )
    region = value.get("region") or ""
    if not isinstance(region, str):
        raise PlannerError(
            f"{where}: 장소 개념의 region은 문자열이어야 합니다.",
            code="INVALID_PLACE",
            context={"raw_text": raw_text},
        )
    return {"name": name.strip(), "region": region.strip()}


def _parse_factors(raw, raw_text):
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise PlannerError(
            f"grounding의 factors는 object여야 합니다. "
            f"(받은 형식: {type(raw).__name__})",
            code="INVALID_FACTORS",
            context={"raw_text": raw_text},
        )
    unknown = sorted(set(raw) - set(FACTOR_SPECS))
    if unknown:
        raise PlannerError(
            f"알 수 없는 factor입니다: {', '.join(unknown)}. "
            f"사용 가능한 factor: {', '.join(sorted(FACTOR_SPECS))}",
            code="UNKNOWN_FACTOR",
            context={"raw_text": raw_text},
        )
    factors = {}
    for name, value in raw.items():
        if value in (None, ""):
            continue
        factors[name] = FACTOR_SPECS[name].coerce(value)
    return factors


def _check_measure(grounding, raw_text):
    """측정 대상이 정확히 하나인지 확인한다."""
    measures = grounding.by_role(FunctionalRole.MEASURE)
    if not measures:
        raise PlannerError(
            "무엇을 구해야 하는지(MEASURE) 찾지 못했습니다.",
            user_message="질문에서 구하려는 값을 찾지 못했습니다.",
            code="NO_MEASURE",
            context={"raw_text": raw_text},
        )
    if len(measures) > 1:
        raise PlannerError(
            "MEASURE 개념이 둘 이상입니다: "
            + ", ".join(item.id for item in measures),
            code="MULTIPLE_MEASURES",
            context={"raw_text": raw_text},
        )

    measure = measures[0]
    allowed = measure_types() | {(CoreConcept.LOCATION, Subtype.PLACE)}
    if (measure.concept, measure.subtype) not in allowed:
        raise PlannerError(
            f"현재 구할 수 없는 측정값입니다: "
            f"{measure.concept.value}/{measure.subtype}",
            user_message=(
                "현재 지원하는 분석으로는 이 질문을 처리할 수 없습니다."
            ),
            code="UNSUPPORTED_MEASURE",
            context={
                "raw_text": raw_text,
                "measure": f"{measure.concept.value}/{measure.subtype}",
            },
        )


def _require_enum(where, key, value, enum_type, raw_text):
    try:
        return enum_type(value)
    except ValueError as error:
        allowed = ", ".join(item.value for item in enum_type)
        raise PlannerError(
            f"{where}.{key}: 허용되지 않은 값 {value!r} (허용: {allowed})",
            code="INVALID_CONCEPT",
            context={"raw_text": raw_text},
        ) from error


def drop_unsupported_regions(grounding):
    """질문에 없는 상위 지역을 지운다.

    region은 정의상 사용자 발화에 있는 표현이다. 발화에 없는 region은 모델이
    지어낸 값이므로 조회를 더 어긋나게 만든다. 거부가 아니라 제거로 처리한다.
    장소명 자체는 정상일 수 있으므로 근거 없는 정보만 덜어 낸다.

    재계획 단계의 ``drop_invented_regions``와 같은 취지이며, 이쪽은 최초
    grounding에 적용된다.
    """
    dropped = []
    for concept in grounding.concepts:
        if not isinstance(concept.value, dict):
            continue
        region = concept.value.get("region")
        if region and region not in grounding.question:
            concept.value = {**concept.value, "region": ""}
            dropped.append(concept.id)
    return dropped
