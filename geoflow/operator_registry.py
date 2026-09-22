# -*- coding: utf-8 -*-
"""semantic operator ↔ 실제 Tool 이름 분리 registry.

Planner는 Tool 이름을 절대 다루지 않고, template은 semantic operator만 지정한다.
실제 ``tool_name``과 argument 이름 binding은 이 registry에서만 결정한다.

v1에서는 기존 ``schemas/*.yaml``에 x-geoflow metadata를 추가하지 않는다.
build.py와 Ollama Tool schema 계약에 영향을 주지 않기 위해서다. 추후 schema
metadata로 옮기더라도 이 모듈의 공개 인터페이스는 그대로 유지할 수 있다.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from geoflow.errors import ExecutionError
from geoflow.types import CoreConcept, Subtype, WHOLE_RESULT

#: output extraction selector. output_bindings의 key로 사용한다.
EXTRACT_SCOPE = "scope"
EXTRACT_WHOLE = WHOLE_RESULT

_SCOPE_PATTERN = re.compile(r"^scope:[A-Za-z0-9_:.-]+$")


class Operator:
    """semantic operator 이름 상수."""

    RESOLVE_PLACE_SCOPE = "RESOLVE_PLACE_SCOPE"
    PASSAGE_METRIC = "PASSAGE_METRIC"
    PASSAGE_COUNT = "PASSAGE_COUNT"
    TRIP_COUNT = "TRIP_COUNT"
    TRIP_METRIC = "TRIP_METRIC"
    DRIVE_METRIC = "DRIVE_METRIC"
    OPERATION_METRIC = "OPERATION_METRIC"
    SCOPE_NAME = "SCOPE_NAME"


@dataclass(frozen=True)
class OperatorInput:
    """semantic input port 하나의 정의.

    ``arg_name``이 ``None``이면 Tool 인자를 만들지 않는 의미 전용 port다.
    EVENT처럼 "무엇을 재는가"를 결정하지만 Tool 인자로는 나타나지 않는
    개념을 graph에 남기기 위한 것이다. 덕분에 operator mapping이
    (EVENT subtype, 출력 subtype)으로 Tool을 고를 수 있고, G3가 통행
    통계 Tool에 trip 사건이 붙는 것을 정적으로 막는다.

    ``match_attributes``는 타입이 같고 의미가 다른 port를 구분한다. 승차/하차
    binding을 LLM이 아니라 registry가 정한다는 계약을 코드로 표현한 것이다.
    node가 그 속성을 갖고 있지 않으면 검사하지 않으므로, 속성을 쓰지 않는
    기존 계획은 그대로 통과한다.
    """

    arg_name: str | None
    concept: CoreConcept
    subtypes: frozenset[str]
    field: str | None = None
    required: bool = True
    match_attributes: tuple[tuple[str, Any], ...] = ()

    @property
    def semantic_only(self):
        return self.arg_name is None

    def accepts(self, concept, subtype, attributes=None):
        if concept != self.concept or subtype not in self.subtypes:
            return False
        return self.matches_attributes(attributes)

    def matches_attributes(self, attributes):
        """node가 선언한 속성만 검사한다. 없는 속성은 제약으로 보지 않는다."""
        attributes = attributes or {}
        for key, value in self.match_attributes:
            if key in attributes and attributes[key] != value:
                return False
        return True

    def binds(self, concept, subtype, attributes=None):
        """operator mapping이 port를 고를 때 쓰는 엄격한 판정.

        ``accepts``와 달리 속성이 아예 없는 node는 속성을 요구하는 port에
        묶이지 않는다. origin/destination을 임의로 채우지 않기 위해서다.
        """
        if concept != self.concept or subtype not in self.subtypes:
            return False
        attributes = attributes or {}
        return all(
            attributes.get(key) == value for key, value in self.match_attributes
        )


@dataclass(frozen=True)
class OperatorOutput:
    """operator가 만들 수 있는 (concept, subtype) 조합과 추출 방법."""

    allowed: frozenset[tuple[CoreConcept, str]]
    extraction: str = EXTRACT_WHOLE

    def accepts(self, concept, subtype):
        return (concept, subtype) in self.allowed


@dataclass(frozen=True)
class OperatorSpec:
    """semantic operator 하나의 전체 계약.

    ``param_enums``/``param_requires``는 Tool이 INVALID_ARGUMENT로 거절할
    조합을 실행 전에 걸러 내기 위한 것이다. 예전에는 template YAML마다
    ``slot_types``/``slot_requires``로 적어 두었지만, 이는 질문 유형이 아니라
    Tool 계약에 속한 제약이므로 registry가 갖는 편이 맞다.
    """

    name: str
    tool_name: str
    inputs: dict[str, OperatorInput] = field(default_factory=dict)
    output: OperatorOutput | None = None
    params: frozenset[str] = frozenset()
    param_enums: dict[str, frozenset[str]] = field(default_factory=dict)
    param_requires: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def allowed_values(self, param):
        return self.param_enums.get(param)

    def missing_companions(self, param, present):
        """``param``과 함께 있어야 하는데 빠진 parameter 이름."""
        return tuple(
            name for name in self.param_requires.get(param, ())
            if name not in present
        )

    def input(self, port):
        return self.inputs.get(port)

    @property
    def required_ports(self):
        return tuple(
            port for port, spec in self.inputs.items() if spec.required
        )

    def argument_names(self):
        return {
            spec.arg_name for spec in self.inputs.values()
            if not spec.semantic_only
        } | set(self.params)

    @property
    def event_subtypes(self):
        """이 operator가 다루는 EVENT subtype. 없으면 빈 집합."""
        return frozenset(
            subtype
            for spec in self.inputs.values()
            if spec.concept == CoreConcept.EVENT
            for subtype in spec.subtypes
        )


def _inputs(*specs):
    return {port: spec for port, spec in specs}


_SCOPE_INPUT_SUBTYPES = frozenset({Subtype.SCOPE, Subtype.VICINITY_SCOPE})


def _event(subtype):
    """Tool 인자를 만들지 않는 EVENT 의미 port.

    "무엇을 재는가"를 graph에 남기기 위한 port다. 이 port가 있어야
    ``EVENT/trip → AMOUNT/fare``라는 개념 변환만 표현한 macro에서
    ``TRIP_METRIC``을 유도할 수 있고, 반대로 통행 통계 Tool에 trip 사건이
    붙는 계획을 G3가 정적으로 거부할 수 있다.

    기존 template은 EVENT node를 두지 않으므로 required=False로 둔다.
    """
    return OperatorInput(
        arg_name=None,
        concept=CoreConcept.EVENT,
        subtypes=frozenset({subtype}),
        required=False,
    )

_SPECS: tuple[OperatorSpec, ...] = (
    OperatorSpec(
        name=Operator.RESOLVE_PLACE_SCOPE,
        tool_name="get_place_scope",
        inputs=_inputs(
            ("place_name", OperatorInput(
                arg_name="name",
                concept=CoreConcept.LOCATION,
                subtypes=frozenset({Subtype.PLACE}),
                field="name",
            )),
            ("place_region", OperatorInput(
                arg_name="region",
                concept=CoreConcept.LOCATION,
                subtypes=frozenset({Subtype.PLACE}),
                field="region",
                required=False,
            )),
        ),
        output=OperatorOutput(
            allowed=frozenset({
                (CoreConcept.LOCATION, Subtype.SCOPE),
                (CoreConcept.LOCATION, Subtype.VICINITY_SCOPE),
            }),
            extraction=EXTRACT_SCOPE,
        ),
        params=frozenset({"include_vicinity"}),
    ),
    OperatorSpec(
        name=Operator.PASSAGE_METRIC,
        tool_name="get_passage_metrics",
        inputs=_inputs(
            ("event", _event(Subtype.PASSAGE)),
            ("area", OperatorInput(
                arg_name="scope",
                concept=CoreConcept.LOCATION,
                subtypes=_SCOPE_INPUT_SUBTYPES,
            )),
        ),
        output=OperatorOutput(
            # 현재 TIMS API는 speed를 연속 field가 아니라 집계 scalar로 돌려주므로
            # FIELD가 아니라 AMOUNT/speed로 표현한다.
            allowed=frozenset({
                (CoreConcept.AMOUNT, Subtype.SPEED),
                (CoreConcept.AMOUNT, Subtype.RPM),
            }),
        ),
        params=frozenset({"metric", "date", "time", "aggregation"}),
        param_enums={"aggregation": frozenset({"max", "min", "sum", "avg", "med"})},
    ),
    OperatorSpec(
        name=Operator.PASSAGE_COUNT,
        tool_name="get_passage_count",
        inputs=_inputs(
            ("event", _event(Subtype.PASSAGE)),
            ("area", OperatorInput(
                arg_name="scope",
                concept=CoreConcept.LOCATION,
                subtypes=_SCOPE_INPUT_SUBTYPES,
            )),
        ),
        output=OperatorOutput(
            allowed=frozenset({(CoreConcept.AMOUNT, Subtype.PASSAGE_COUNT)}),
        ),
        params=frozenset({
            "date", "time", "taxi_type", "taxi_status",
            "dimension", "order", "limit",
        }),
        param_enums={
            "dimension": frozenset({"h3", "sido", "sigungu", "emd"}),
            "taxi_type": frozenset({"private", "corporate", "all"}),
            "taxi_status": frozenset({"occupied", "vacant", "stationary", "all"}),
            "order": frozenset({"top", "bottom"}),
        },
        # order/limit은 dimension이 있어야 의미를 갖는다.
        param_requires={"order": ("dimension",), "limit": ("dimension",)},
    ),
    OperatorSpec(
        name=Operator.TRIP_COUNT,
        tool_name="get_trip_count",
        inputs=_inputs(
            ("event", _event(Subtype.TRIP)),
            # origin/destination 역할 뒤바뀜을 막는 고정 binding.
            # 이 mapping은 LLM이 아니라 registry가 결정한다. od_role 속성은
            # 어느 node가 어느 port로 가는지를 이름이 아니라 의미로 정한다.
            ("pickup", OperatorInput(
                arg_name="scope_pickup",
                concept=CoreConcept.LOCATION,
                subtypes=_SCOPE_INPUT_SUBTYPES,
                required=False,
                match_attributes=(("od_role", "pickup"),),
            )),
            ("dropoff", OperatorInput(
                arg_name="scope_dropoff",
                concept=CoreConcept.LOCATION,
                subtypes=_SCOPE_INPUT_SUBTYPES,
                required=False,
                match_attributes=(("od_role", "dropoff"),),
            )),
        ),
        output=OperatorOutput(
            allowed=frozenset({(CoreConcept.AMOUNT, Subtype.TRIP_COUNT)}),
        ),
        params=frozenset({"date", "time", "dimension", "order", "limit"}),
        param_enums={"order": frozenset({"top", "bottom"})},
        param_requires={"order": ("dimension",), "limit": ("dimension",)},
    ),
    OperatorSpec(
        name=Operator.TRIP_METRIC,
        tool_name="get_trip_metrics",
        inputs=_inputs(
            ("event", _event(Subtype.TRIP)),
            ("area", OperatorInput(
                arg_name="scope",
                concept=CoreConcept.LOCATION,
                subtypes=_SCOPE_INPUT_SUBTYPES,
                required=False,
            )),
        ),
        output=OperatorOutput(
            allowed=frozenset({(CoreConcept.AMOUNT, Subtype.FARE)}),
        ),
        params=frozenset({"metric", "date", "time", "aggregation"}),
        param_enums={"aggregation": frozenset({"max", "min", "sum", "avg", "med"})},
    ),
    OperatorSpec(
        name=Operator.DRIVE_METRIC,
        tool_name="get_drive_metrics",
        inputs=_inputs(
            ("event", _event(Subtype.DRIVE)),
            ("area", OperatorInput(
                arg_name="scope",
                concept=CoreConcept.LOCATION,
                subtypes=_SCOPE_INPUT_SUBTYPES,
                required=False,
            )),
        ),
        output=OperatorOutput(
            allowed=frozenset({(CoreConcept.PROPORTION, Subtype.VACANT_RATIO)}),
        ),
        params=frozenset({
            "metric", "date", "time", "taxi_type", "aggregation",
        }),
        param_enums={"aggregation": frozenset({"max", "min", "sum", "avg", "med"}), "taxi_type": frozenset({"private", "corporate", "all"})},
    ),
    OperatorSpec(
        name=Operator.OPERATION_METRIC,
        tool_name="get_operation_metrics",
        inputs=_inputs(
            ("event", _event(Subtype.OPERATION)),
            ("area", OperatorInput(
                arg_name="scope",
                concept=CoreConcept.LOCATION,
                subtypes=_SCOPE_INPUT_SUBTYPES,
                required=False,
            )),
        ),
        output=OperatorOutput(
            allowed=frozenset({
                (CoreConcept.AMOUNT, Subtype.REVENUE),
                (CoreConcept.AMOUNT, Subtype.OPERATING_COUNT),
                (CoreConcept.AMOUNT, Subtype.HOURS),
                (CoreConcept.PROPORTION, Subtype.OPERATING_RATIO),
            }),
        ),
        params=frozenset({
            "metric", "date", "taxi_type", "dimension", "order", "limit",
            "aggregation", "bucket", "rollup",
        }),
        param_enums={
            "dimension": frozenset({"dayofweek", "sido"}),
            "taxi_type": frozenset({"private", "corporate", "all"}),
            "order": frozenset({"top", "bottom"}),
            "aggregation": frozenset({"max", "min", "sum", "avg", "med"}),
            "bucket": frozenset({"week", "month"}),
            "rollup": frozenset({"max", "min", "sum", "avg", "med"}),
        },
        # bucket/rollup 2단계 집계는 반드시 짝으로 쓰인다.
        param_requires={
            "bucket": ("rollup",), "rollup": ("bucket",),
            "order": ("dimension",), "limit": ("dimension",),
        },
    ),
    OperatorSpec(
        name=Operator.SCOPE_NAME,
        tool_name="get_scope_name",
        inputs=_inputs(
            ("area", OperatorInput(
                arg_name="scope",
                concept=CoreConcept.LOCATION,
                subtypes=_SCOPE_INPUT_SUBTYPES,
            )),
        ),
        output=OperatorOutput(
            allowed=frozenset({(CoreConcept.LOCATION, Subtype.PLACE)}),
        ),
    ),
)

OPERATORS: dict[str, OperatorSpec] = {}
for _spec in _SPECS:
    if _spec.name in OPERATORS:
        raise RuntimeError(f"중복 operator 정의입니다: {_spec.name}")
    _arg_names = [
        spec.arg_name for spec in _spec.inputs.values()
        if not spec.semantic_only
    ]
    if len(set(_arg_names)) != len(_arg_names):
        raise RuntimeError(f"{_spec.name}: input port의 tool argument가 충돌합니다.")
    _collision = set(_arg_names) & set(_spec.params)
    if _collision:
        raise RuntimeError(
            f"{_spec.name}: input과 param의 argument 이름이 겹칩니다: "
            f"{sorted(_collision)}"
        )
    _unknown_params = (
        set(_spec.param_enums) | set(_spec.param_requires)
        | {name for names in _spec.param_requires.values() for name in names}
    ) - set(_spec.params)
    if _unknown_params:
        raise RuntimeError(
            f"{_spec.name}: params에 없는 parameter 제약입니다: "
            f"{sorted(_unknown_params)}"
        )
    OPERATORS[_spec.name] = _spec


def get_operator(name):
    """등록된 operator spec을 반환하고, 없으면 ``None``."""
    return OPERATORS.get(name)


def operator_names():
    return tuple(OPERATORS)


def tool_name_for(name):
    spec = OPERATORS.get(name)
    return None if spec is None else spec.tool_name


def is_scope_literal(value):
    return isinstance(value, str) and bool(_SCOPE_PATTERN.fullmatch(value))


def extract_output(selector, result, *, step_id=None, tool_name=None):
    """Tool 결과에서 output binding selector에 해당하는 값을 꺼낸다.

    Provider가 scalar/list/dict 어느 형태로 돌려주든 동일한 규칙으로 처리한다.
    """
    if selector == EXTRACT_WHOLE:
        return result
    if selector == EXTRACT_SCOPE:
        scope = _find_scope(result)
        if scope is None:
            raise ExecutionError(
                f"Tool 결과에서 scope를 하나로 확정하지 못했습니다: {result!r}",
                user_message="장소에 해당하는 공간 범위를 확정하지 못했습니다.",
                code="SCOPE_EXTRACTION_FAILED",
                context={"step_id": step_id, "tool_name": tool_name},
            )
        return scope
    raise ExecutionError(
        f"알 수 없는 output extraction selector입니다: {selector!r}",
        code="UNKNOWN_EXTRACTION",
        context={"step_id": step_id, "tool_name": tool_name},
    )


def _find_scope(result: Any):
    """단일 scope 문자열만 인정한다. 후보가 여럿이면 확정하지 않는다."""
    if is_scope_literal(result):
        return result
    if isinstance(result, dict):
        if result.get("status") == "ERROR":
            return None
        for key in ("scope", "value"):
            if is_scope_literal(result.get(key)):
                return result[key]
        return None
    if isinstance(result, (list, tuple)):
        candidates = [_find_scope(item) for item in result]
        found = [item for item in candidates if item is not None]
        if len(found) == 1:
            return found[0]
    return None
