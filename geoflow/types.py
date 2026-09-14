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
    """typed GeoFlow Plan. Planner 출력이 아니라 template + slot의 결과물이다."""

    version: str
    question: str
    template: str
    concepts: list[ConceptNode] = field(default_factory=list)
    transformations: list[Transformation] = field(default_factory=list)
    final_node: str = ""
    slots: dict[str, Any] = field(default_factory=dict)

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
            "concepts": [node.to_dict() for node in self.concepts],
            "transformations": [
                transformation.to_dict()
                for transformation in self.transformations
            ],
            "final_node": self.final_node,
        }


@dataclass
class ToolStep:
    """실제 Tool 호출 하나. ``arguments``는 literal 또는 ValueRef를 갖는다."""

    id: str
    operator: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    output_bindings: dict[str, str] = field(default_factory=dict)

    def to_dict(self):
        return {
            "id": self.id,
            "operator": self.operator,
            "tool_name": self.tool_name,
            "arguments": {
                name: value.to_dict() if isinstance(value, ValueRef) else value
                for name, value in self.arguments.items()
            },
            "output_bindings": dict(self.output_bindings),
        }


@dataclass
class ExecutionPlan:
    """topological order로 정렬된 ToolStep 목록."""

    template: str
    steps: list[ToolStep] = field(default_factory=list)
    final_node: str = ""
    seed_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "template": self.template,
            "final_node": self.final_node,
            "steps": [step.to_dict() for step in self.steps],
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
