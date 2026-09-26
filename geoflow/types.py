# -*- coding: utf-8 -*-
"""GeoFlow 중간 표현(IR) 타입 정의.

Spatial-Agent의 core concept / functional role 체계를 유지하되, TIMS 고유
개념은 새 core concept가 아니라 subtype으로 표현한다.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

GEOFLOW_VERSION = "1.0"

#: ValueRef가 아닌 "결과 전체"를 가리키는 output binding selector.
WHOLE_RESULT = "$"


class CoreConcept(str, Enum):
    """Spatial-Agent core concept. TIMS 고유 개념을 여기에 추가하지 않는다."""

    LOCATION = "LOCATION"
    OBJECT = "OBJECT"
    FIELD = "FIELD"
    EVENT = "EVENT"
    NETWORK = "NETWORK"
    AMOUNT = "AMOUNT"
    PROPORTION = "PROPORTION"


class FunctionalRole(str, Enum):
    """GeoFlow node의 기능적 역할."""

    EXTENT = "EXTENT"
    TEXTENT = "TEXTENT"
    SUBCOND = "SUBCOND"
    COND = "COND"
    SUPPORT = "SUPPORT"
    MEASURE = "MEASURE"


#: procedural role의 상대 순서. SUBCOND < COND < SUPPORT < MEASURE.
PROCEDURAL_ROLE_PRIORITY: dict[FunctionalRole, int] = {
    FunctionalRole.SUBCOND: 0,
    FunctionalRole.COND: 1,
    FunctionalRole.SUPPORT: 2,
    FunctionalRole.MEASURE: 3,
}

#: EXTENT/TEXTENT는 절차 순서가 아니라 맥락을 나타내므로 순서 검사에서 제외한다.
CONTEXTUAL_ROLES = frozenset({FunctionalRole.EXTENT, FunctionalRole.TEXTENT})


class NodeSource(str, Enum):
    """concept node 값의 출처. scope provenance 판정의 근거가 된다."""

    USER = "user"
    TOOL = "tool"
    DERIVED = "derived"
    TEMPLATE = "template"
    #: 질문에 드러나지 않았지만 workflow를 완성하기 위해 필요한 개념.
    #: 예를 들어 "평균 속도"라는 질문에는 speed를 재는 대상인 passage가
    #: 표현되어 있지 않다. 사용자가 말한 값(USER)과 구분해 두어야 scope
    #: provenance(G6)가 implicit 개념을 사용자 입력으로 오인하지 않는다.
    IMPLICIT = "implicit"


class Subtype:
    """core concept 아래의 TIMS 고유 subtype 이름 모음."""

    # LOCATION
    PLACE = "place"
    SCOPE = "scope"
    VICINITY_SCOPE = "vicinity_scope"
    # NETWORK
    ROAD_NETWORK = "road_network"
    ROAD_EDGE = "road_edge"
    # EVENT
    PASSAGE = "passage"
    TRIP = "trip"
    DRIVE = "drive"
    OPERATION = "operation"
    # AMOUNT
    PASSAGE_COUNT = "passage_count"
    TRIP_COUNT = "trip_count"
    SPEED = "speed"
    RPM = "rpm"
    FARE = "fare"
    REVENUE = "revenue"
    OPERATING_COUNT = "operating_count"
    HOURS = "hours"
    # PROPORTION
    VACANT_RATIO = "vacant_ratio"
    OPERATING_RATIO = "operating_ratio"


#: CoreConcept별로 허용하는 subtype. IR 어휘의 단일 기준이다.
#:
#: macro port 계약, grounding 검증, prompt 어휘가 모두 이 표를 근거로 삼는다.
#: 목록을 여러 모듈에 복사해 두면 한쪽만 고쳐져 조용히 어긋나기 때문이다.
#: OBJECT/FIELD는 아직 TIMS subtype이 없으므로 비어 있다. 비어 있다는 것은
#: "그 concept로는 어떤 개념도 표현할 수 없다"는 뜻이며, 검증은 이를 그대로
#: 적용해 OBJECT/taxi_type 같은 조합을 거부한다.
CONCEPT_SUBTYPES: dict[CoreConcept, frozenset[str]] = {
    CoreConcept.LOCATION: frozenset({
        Subtype.PLACE, Subtype.SCOPE, Subtype.VICINITY_SCOPE,
    }),
    CoreConcept.NETWORK: frozenset({
        Subtype.ROAD_NETWORK, Subtype.ROAD_EDGE,
    }),
    CoreConcept.EVENT: frozenset({
        Subtype.PASSAGE, Subtype.TRIP, Subtype.DRIVE, Subtype.OPERATION,
    }),
    CoreConcept.AMOUNT: frozenset({
        Subtype.PASSAGE_COUNT, Subtype.TRIP_COUNT, Subtype.SPEED,
        Subtype.RPM, Subtype.FARE, Subtype.REVENUE,
        Subtype.OPERATING_COUNT, Subtype.HOURS,
    }),
    CoreConcept.PROPORTION: frozenset({
        Subtype.VACANT_RATIO, Subtype.OPERATING_RATIO,
    }),
    CoreConcept.OBJECT: frozenset(),
    CoreConcept.FIELD: frozenset(),
}

#: 어떤 concept에든 쓰일 수 있는 subtype 이름 전체.
KNOWN_SUBTYPES = frozenset().union(*CONCEPT_SUBTYPES.values())


def subtype_allowed(concept, subtype):
    """(concept, subtype) 조합이 IR 어휘에 있는지 본다."""
    return subtype in CONCEPT_SUBTYPES.get(concept, frozenset())


def describe_concept_subtypes():
    """concept별 subtype 목록을 사람이 읽을 수 있게 만든다."""
    lines = []
    for concept in CoreConcept:
        subtypes = CONCEPT_SUBTYPES.get(concept) or frozenset()
        shown = ", ".join(sorted(subtypes)) if subtypes else "(없음)"
        lines.append(f"- {concept.value}: {shown}")
    return "\n".join(lines)


#: scope provenance 규칙이 적용되는 LOCATION subtype.
SCOPE_SUBTYPES = frozenset({Subtype.SCOPE, Subtype.VICINITY_SCOPE})


@dataclass(frozen=True)
class ValueRef:
    """다른 concept node의 값을 가리키는 명시적 참조.

    문자열 interpolation 대신 이 객체를 쓰기 때문에 dependency/type/provenance
    검증이 정적으로 가능하다.
    """

    node_id: str
    field: str | None = None

    def describe(self):
        return f"{self.node_id}.{self.field}" if self.field else self.node_id

    def to_dict(self):
        return {"$ref": self.node_id, "field": self.field}


@dataclass
class ConceptNode:
    """GeoFlow graph의 개념 node."""

    id: str
    concept: CoreConcept
    subtype: str
    role: FunctionalRole
    source: NodeSource
    value: Any = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "concept": self.concept.value,
            "subtype": self.subtype,
            "role": self.role.value,
            "source": self.source.value,
            "value": self.value,
            "attributes": dict(self.attributes),
        }


@dataclass
class Transformation:
    """concept node를 입력으로 받아 새 concept node를 만드는 semantic 연산."""

    id: str
    operator: str
    inputs: dict[str, ValueRef] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "operator": self.operator,
            "inputs": {
                port: ref.to_dict() for port, ref in self.inputs.items()
            },
            "outputs": list(self.outputs),
            "params": dict(self.params),
        }


@dataclass
class GeoFlowPlan:
    """typed GeoFlow Plan.

    Planner 출력이 아니라 macro composition(또는 legacy template + slot)의
    결과물이다. ``applied_macros``는 이 graph를 만든 macro 조각의 목록이고,
    ``template``은 그 조각들을 이어 붙인 서명이다. 하나의 질문이 하나의
    완성 template에 대응하지 않으므로 이름 하나로는 계획을 설명할 수 없다.
    """

    version: str
    question: str
    template: str = ""
    concepts: list[ConceptNode] = field(default_factory=list)
    transformations: list[Transformation] = field(default_factory=list)
    final_node: str = ""
    slots: dict[str, Any] = field(default_factory=dict)
    #: 이 graph를 구성한 macro 이름을 적용 순서대로 담는다.
    applied_macros: list[str] = field(default_factory=list)
    #: grounding에는 있었지만 어떤 operator도 받지 못한 factor. 조용히
    #: 사라지는 조건을 실행 기록에서 확인할 수 있게 남긴다.
    unused_factors: dict[str, Any] = field(default_factory=dict)

    def node(self, node_id):
        for node in self.concepts:
            if node.id == node_id:
                return node
        return None

    @property
    def node_ids(self):
        return [node.id for node in self.concepts]

    def to_dict(self):
        return {
            "version": self.version,
            "question": self.question,
            "template": self.template,
            "slots": dict(self.slots),
            "applied_macros": list(self.applied_macros),
            "unused_factors": dict(self.unused_factors),
            "concepts": [node.to_dict() for node in self.concepts],
            "transformations": [
                transformation.to_dict()
                for transformation in self.transformations
            ],
            "final_node": self.final_node,
        }


#: ExecutionPlan step 종류. tool은 TIMS 호출, local은 로컬 계산이다.
STEP_TOOL = "tool"
STEP_LOCAL = "local"


@dataclass
class ToolStep:
    """실행 단계 하나. ``arguments``는 literal 또는 ValueRef를 갖는다.

    ``kind``가 ``local``이면 Tool을 부르지 않고 ``inputs``(state key)를 읽어
    로컬 분석 연산을 수행한다. ``tool_name``은 ``local:<operator>``로 둔다.
    기록과 CLI가 문자열을 기대하기 때문이다.

    ``covers``는 이 단계가 수행하는 의미 graph(GeoFlowPlan)의 transformation
    id다. 여러 의미 단계를 호출 하나로 합쳤다면 여럿이 된다.
    ``argument_sources``는 인자마다 그 값을 정한 의미 단계와 속성을 적는다.
    """

    id: str
    operator: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    output_bindings: dict[str, str] = field(default_factory=dict)
    kind: str = STEP_TOOL
    covers: list[str] = field(default_factory=list)
    argument_sources: dict[str, str] = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)
    #: 기간을 구간으로 나눠 부른 호출이면 그 구간.
    group: dict[str, Any] | None = None
    #: 이 호출이 옳으려면 TIMS가 지켜야 하는 계약 항목(``geoflow/tims_contract.py``).
    #: verify_lowering이 확인할 수 없는 외부 가정이다.
    assumptions: list[str] = field(default_factory=list)

    @property
    def is_local(self):
        return self.kind == STEP_LOCAL

    def to_dict(self):
        data = {
            "id": self.id,
            "operator": self.operator,
            "tool_name": self.tool_name,
            "arguments": {
                name: value.to_dict() if isinstance(value, ValueRef) else value
                for name, value in self.arguments.items()
            },
            "output_bindings": dict(self.output_bindings),
            "kind": self.kind,
            "covers": list(self.covers),
            "argument_sources": dict(self.argument_sources),
        }
        if self.inputs:
            data["inputs"] = list(self.inputs)
        if self.group is not None:
            data["group"] = dict(self.group)
        if self.assumptions:
            data["assumptions"] = list(self.assumptions)
        return data


@dataclass
class ExecutionPlan:
    """topological order로 정렬된 ToolStep 목록."""

    template: str
    steps: list[ToolStep] = field(default_factory=list)
    final_node: str = ""
    seed_state: dict[str, Any] = field(default_factory=dict)
    #: 의미 graph transformation id → 그것을 수행하는 step id 목록 (G ↔ G′).
    semantic_map: dict[str, list[str]] = field(default_factory=dict)
    #: 호출 안에서만 계산되어 실행 state에 나타나지 않는 중간 node와 그 이유.
    #: 예: TIMS bucket/rollup으로 합친 구간별 값.
    unobserved: dict[str, str] = field(default_factory=dict)
    #: 기간을 로컬에서 구간으로 나눴다면 그 해석. 답변이 적용 기간을 밝힌다.
    periods: dict[str, Any] = field(default_factory=dict)
    #: 구간별 집계마다 고른 lowering 전략과, 쓰지 않은 전략의 이유.
    lowering: dict[str, Any] = field(default_factory=dict)
    #: transformation id → 기간 인자의 해석·요청 인자·provider 의미 확인 상태.
    date_semantics: dict[str, Any] = field(default_factory=dict)

    @property
    def tool_steps(self):
        return [step for step in self.steps if not step.is_local]

    def to_dict(self):
        return {
            "template": self.template,
            "final_node": self.final_node,
            "steps": [step.to_dict() for step in self.steps],
            "semantic_map": {
                key: list(value) for key, value in self.semantic_map.items()
            },
            "unobserved": dict(self.unobserved),
            "periods": dict(self.periods),
            "lowering": dict(self.lowering),
            "date_semantics": dict(self.date_semantics),
        }


@dataclass
class ExecutionResult:
    """deterministic 실행 결과와 trace."""

    status: str
    state: dict[str, Any] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    final_node: str = ""
    final_value: Any = None
    error: dict[str, Any] | None = None

    @property
    def ok(self):
        return self.status == "OK"

    def to_dict(self):
        return {
            "status": self.status,
            "state": dict(self.state),
            "trace": [dict(entry) for entry in self.trace],
            "final_node": self.final_node,
            "final_value": self.final_value,
            "error": self.error,
        }
