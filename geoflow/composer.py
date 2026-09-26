# -*- coding: utf-8 -*-
"""Macro retrieval + IO-port composition.

Grounding 결과(개념 + factor)를 입력으로 받아, macro 조각을 input/output port로
이어 붙여 하나의 ``GeoFlowPlan``을 만든다. 질문 유형을 고르는 단계가 없다는
것이 요점이다. 같은 macro library에서

    "scope:edge:1742상의 평균 속도"   → EVENT_TO_MEASURE
    "동대구역 근처의 평균 속도"       → PLACE_TO_SCOPE + EVENT_TO_MEASURE
    "A에서 B로 간 실차 구간 건수"     → PLACE_TO_SCOPE ×2 + OD_EVENT_TO_MEASURE

처럼 서로 다른 합성 결과가 나온다.

합성은 목표(MEASURE)에서 시작하는 역방향 탐색이다.

1. 목표를 만들 수 있는 macro를 찾는다.
2. 그 macro의 input port를 채운다.
   a. 이미 grounding에 있는 개념으로 채울 수 있으면 그것을 쓴다.
   b. 없으면 그 개념을 만들 수 있는 macro를 다시 찾는다(재귀).
   c. 그래도 없고 registry가 유일하게 결정할 수 있는 개념이면 implicit으로
      만든다. 그 밖의 경우에는 개념을 지어내지 않는다.
3. 만들어진 변환마다 operator mapping이 semantic operator를 확정한다.

후보가 여럿이면 추측하지 않고 실패한다. 같은 질문이 실행마다 다른 계획으로
바뀌지 않아야 하기 때문이다.
"""

import json
from dataclasses import dataclass, field

from geoflow import analysis_ops, operator_mapping
from geoflow.aggregation import FLAT_KEYS, REDUCERS
from geoflow.errors import CompositionError
from geoflow.factors import STRUCTURAL_FACTORS, validate_factors
from geoflow.macros import MacroLibrary
from geoflow.operator_mapping import OperatorBinding
from geoflow.operator_registry import get_operator
from geoflow.types import (
    GEOFLOW_VERSION,
    ConceptNode,
    CoreConcept,
    FunctionalRole,
    GeoFlowPlan,
    NodeSource,
    Subtype,
    Transformation,
    ValueRef,
)

#: macro 연쇄 탐색의 최대 깊이. TIMS에서 실제로 필요한 깊이는 2다.
#: (place → scope → measure) 상한은 탐색이 끝나지 않는 상황을 막기 위한 것이다.
DEFAULT_MAX_DEPTH = 4

#: 질문에 없어도 만들어 낼 수 있는 concept. registry가 "이 측정값을 얻으려면
#: 반드시 이 사건이 필요하다"를 유일하게 알려 줄 수 있는 경우만 해당한다.
#: LOCATION을 여기에 넣으면 없는 장소를 지어내는 경로가 생긴다.
INFERABLE_CONCEPTS = frozenset({CoreConcept.EVENT})

#: 실행이 값을 채우는 node source. compiler와 같은 기준을 쓴다.
PRODUCED_SOURCES = frozenset({NodeSource.TOOL, NodeSource.DERIVED})

#: 모든 macro가 실패했을 때 보고할 오류의 우선순위. 앞일수록 먼저다.
#:
#: 기준은 원인의 위치다. 입력 node를 어느 port에 둘지 정하지 못한 오류가 가장
#: 앞이다. 그 port를 버리고 진행하면 뒤 단계의 오류(필수 input 부재, param 계약,
#: 남은 입력, 쓰이지 않은 개념)가 결과로 따라 나올 수 있지만, 반대 방향은 없다.
#: operator가 하나로 정해진 뒤에 난 param 계약 위반은 operator를 정하지 못한
#: NO_OPERATOR보다 구체적이다. UNUSED_CONCEPT는 "어떤 조건이 계획에 닿지
#: 않았다"는 결과만 말하므로 마지막이다. 재질의 가능 여부나 benchmark 점수는
#: 기준으로 쓰지 않는다.
#:
#: 표에 없는 code는 표의 모든 code 뒤에 온다.
DIAGNOSTIC_PRECEDENCE = (
    "AMBIGUOUS_PORT",
    "AMBIGUOUS_OPERATOR",
    "MISSING_REQUIRED_INPUT",
    "PARAM_VALUE_REQUIRES_INPUT",
    "INVALID_PARAM_VALUE",
    "MISSING_COMPANION_PARAM",
    "AMBIGUOUS_INNER_AGGREGATION",
    "UNSUPPORTED_GROUPED_MEASURE",
    "NO_OPERATOR",
    "UNCONSUMED_CONDITION",
    "UNUSED_CONCEPT",
)
_PRECEDENCE_RANK = {code: rank for rank, code in enumerate(DIAGNOSTIC_PRECEDENCE)}

#: 값이 조건을 걸지 않는 factor. 받는 Tool이 없어도 계산이 달라지지 않는다.
NON_RESTRICTIVE_FACTORS = {"taxi_type": "all", "taxi_status": "all"}

#: 구간별 집계와 함께 쓸 수 없는 factor. 공간 그룹과 시간 구간을 함께 나누는
#: 계산은 schema가 정하지 않았고 mock은 거절한다. 지원된다고 가정하지 않는다.
_GROUPED_EXCLUSIVE = ("dimension", "order", "limit")

#: 사용자에게 보일 조건 이름.
_FACTOR_LABELS = {
    "date": "기간", "time": "시간대", "taxi_type": "택시 유형",
    "taxi_status": "운행 상태", "dimension": "그룹 기준", "order": "정렬",
    "limit": "개수", "aggregation": "집계 방식", "bucket": "구간",
    "rollup": "구간별 값의 집계", "select": "구간 선택",
}


@dataclass(frozen=True)
class MacroFailure:
    """macro 하나를 시도하다 난 실패. 안쪽 macro에서 난 것도 포함한다."""

    macro: str
    error: CompositionError

    def summary(self):
        context = {
            key: value for key, value in self.error.context.items()
            if key != "macro_failures"
        }
        return {"macro": self.macro, "code": self.error.code, "context": context}


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def choose_diagnostic(failures):
    """모든 macro가 실패했을 때 보고할 오류 하나를 고른다.

    시도 순서와 무관하다. 우선순위 표, code, context 순으로 정렬하고, macro
    이름은 마지막 동률 해소에만 쓴다. 고른 오류의 context에는 모든 실패의
    요약을 ``macro_failures``로 남긴다. 사용자 메시지는 고른 오류의 것이다.
    """
    chosen = min(failures, key=lambda item: (
        _PRECEDENCE_RANK.get(item.error.code, len(DIAGNOSTIC_PRECEDENCE)),
        item.error.code or "",
        _canonical(item.summary()["context"]),
        item.macro,
    )).error
    summaries = {_canonical(item.summary()): item.summary() for item in failures}
    chosen.context = {
        **chosen.context,
        "macro_failures": [summaries[key] for key in sorted(summaries)],
    }
    return chosen


#: answer/재계획이 읽는 표층 조건 이름. 값은 grounding에서만 온다.
SLOT_PLACE = "place"
SLOT_ORIGIN = "origin"
SLOT_DESTINATION = "destination"
SLOT_SCOPE = "scope"
SLOT_METRIC = "metric"

_OD_SLOT = {"pickup": SLOT_ORIGIN, "dropoff": SLOT_DESTINATION}


@dataclass
class _Build:
    """합성 중간 상태. 실패한 후보를 되돌릴 수 있게 snapshot을 뜬다."""

    nodes: dict[str, ConceptNode] = field(default_factory=dict)
    transformations: list[Transformation] = field(default_factory=list)
    applied: list[str] = field(default_factory=list)
    used_factors: set = field(default_factory=set)
    #: 되돌리기 대상이 아니다. 실패한 갈래의 오류를 모두 남긴다. 결국 성공한
    #: 갈래 앞에서 난 실패는 원인이 아니므로 그 갈래가 성공하면 지운다.
    failures: list = field(default_factory=list)

    def note_failure(self, macro, error):
        self.failures.append(MacroFailure(macro=macro, error=error))

    def failure_mark(self):
        return len(self.failures)

    def forget_failures_since(self, mark):
        del self.failures[mark:]

    def snapshot(self):
        return (
            dict(self.nodes),
            list(self.transformations),
            list(self.applied),
            set(self.used_factors),
        )

    def restore(self, state):
        nodes, transformations, applied, used = state
        self.nodes = nodes
        self.transformations = transformations
        self.applied = applied
        self.used_factors = used

    def add_node(self, node):
        self.nodes[node.id] = node
        return node

    def unique_id(self, base):
        if base not in self.nodes:
            return base
        index = 2
        while f"{base}_{index}" in self.nodes:
            index += 1
        return f"{base}_{index}"

    def unique_transformation_id(self, base):
        taken = {item.id for item in self.transformations}
        if base not in taken:
            return base
        index = 2
        while f"{base}_{index}" in taken:
            index += 1
        return f"{base}_{index}"


class MacroComposer:
    """grounding + macro library → GeoFlowPlan."""

    def __init__(self, library=None, *, max_depth=DEFAULT_MAX_DEPTH):
        self.library = library or MacroLibrary.from_directory()
        self.max_depth = max_depth

    def compose(self, grounding):
        """검증된 grounding 하나를 GeoFlow Graph로 합성한다."""
        # 조건끼리의 공기 불변식을 조각을 고르기 전에 확인한다. 어떤 Tool이
        # 그 조건을 소비할지 몰라도 판정할 수 있고, 계획을 만들기 전이라
        # 빠진 조건을 다시 물어 채울 수 있다.
        validate_factors(grounding.factors)
        aggregation = grounding.aggregation
        _check_aggregation_combination(grounding, aggregation)
        goal = grounding.measure
        if goal is None:
            raise CompositionError(
                "측정 대상(MEASURE) 개념이 없어 합성할 수 없습니다.",
                code="NO_MEASURE",
            )

        build = _Build()
        # grounding이 준 개념을 pool에 올린다. 목표는 macro가 만들 값이므로
        # 여기에 넣지 않는다.
        for concept in grounding.concepts:
            if concept is goal:
                continue
            build.add_node(_seed_node(concept))

        goal_node = ConceptNode(
            id=goal.id,
            concept=goal.concept,
            subtype=goal.subtype,
            role=goal.role,
            source=NodeSource.TOOL,
            value=None,
            attributes=dict(goal.attributes),
        )
        build.add_node(goal_node)

        # 조각을 시도하기 전에, 질문의 장소들이 이 목표에 연결될 수 있는
        # 형태인지 먼저 본다. 실패하면 "만들 수 있는 operator가 없다" 같은
        # 먼 원인 대신 관계 정보가 빠졌다는 사실을 그대로 알려 준다.
        _check_location_relations(grounding, goal, goal_node)

        # 목표를 만들 수 있는 조각을 차례로 시도한다. 질문의 조건을 하나라도
        # 반영하지 못하는 합성은 성공으로 보지 않고 다음 후보로 넘어간다.
        # "A에서 B로"가 붙은 질문이 출발/도착을 조용히 버린 계획으로 끝나지
        # 않게 하는 장치다.
        # 집계 형태(한 단계 / 구간별)가 맞는 조각만 목표 후보가 된다. 구간을 나눈
        # 질문을 한 단계 조각으로 합성하면 두 단계가 Tool 인자로 압축된다.
        producers = self.library.producing(goal.concept, goal.subtype)
        candidates = [
            macro for macro in producers
            if macro.accepts_aggregation(aggregation)
        ]
        if producers and not candidates:
            raise CompositionError(
                "이 측정값은 요청한 집계 형태를 표현할 조각이 없습니다: "
                f"{goal.concept.value}/{goal.subtype}, "
                f"집계={aggregation.to_dict()}",
                user_message="이 측정값은 주·월 구간별 계산을 지원하지 않습니다.",
                code="UNSUPPORTED_AGGREGATION",
                context={
                    "goal": f"{goal.concept.value}/{goal.subtype}",
                    "aggregation": aggregation.to_dict(),
                },
            )
        for macro in candidates:
            state = build.snapshot()
            try:
                applied = self._apply(
                    macro, goal_node, grounding, build,
                    depth=0, stack=(macro.name,), demand={},
                )
            except CompositionError as error:
                build.note_failure(macro.name, error)
                build.restore(state)
                continue
            if applied:
                unused = self._unused_conditions(grounding, build, goal_node)
                unconsumed = self._unconsumed_factors(grounding, build)
                if unconsumed and not unused:
                    build.note_failure(macro.name, _unconsumed_error(
                        grounding, unconsumed,
                    ))
                    build.restore(state)
                    continue
                if not unused:
                    return self._build_plan(grounding, build, goal_node)
                build.note_failure(macro.name, CompositionError(
                    "질문의 조건을 계획에 반영하지 못했습니다: "
                    + ", ".join(sorted(unused)),
                    user_message=(
                        "질문의 조건 일부를 현재 분석으로 표현할 수 없습니다."
                    ),
                    code="UNUSED_CONCEPT",
                    context={"unused": sorted(unused)},
                ))
            build.restore(state)

        # 성공한 macro가 없을 때만 온다. 어떤 오류를 보고할지는 시도 순서가
        # 아니라 choose_diagnostic이 정한다.
        if build.failures:
            raise choose_diagnostic(build.failures)
        raise CompositionError(
            f"{goal.concept.value}/{goal.subtype}를 만들 수 있는 "
            "분석 조각이 없습니다.",
            user_message=(
                "현재 지원하는 분석으로는 이 질문을 처리할 수 없습니다."
            ),
            code="NO_MACRO",
            context={"goal": f"{goal.concept.value}/{goal.subtype}"},
        )

    # -- 역방향 탐색 -------------------------------------------------------

    def _produce(self, output_node, grounding, build, *, depth, stack, demand):
        """``output_node``를 만드는 macro를 적용한다. 성공하면 True."""
        if depth > self.max_depth:
            return False
        mark = build.failure_mark()
        for macro in self.library.producing(
            output_node.concept, output_node.subtype,
        ):
            if macro.name in stack:
                # 같은 조각이 자기 자신을 만들어 내는 순환을 막는다.
                continue
            state = build.snapshot()
            try:
                if self._apply(
                    macro, output_node, grounding, build,
                    depth=depth, stack=(*stack, macro.name), demand=demand,
                ):
                    build.forget_failures_since(mark)
                    return True
            except CompositionError as error:
                build.note_failure(macro.name, error)
                build.restore(state)
                continue
            build.restore(state)
        return False

    def _apply(self, macro, output_node, grounding, build, *, depth, stack,
               demand):
        """macro 하나를 적용해 output_node를 만든다."""
        port_name = macro.output_port_for(
            output_node.concept, output_node.subtype,
        )
        if port_name is None:
            return False
        return self._apply_key(
            macro, port_name, output_node, grounding, build,
            depth=depth, stack=stack, demand=demand, root=output_node,
        )

    def _apply_key(self, macro, key, output_node, grounding, build, *, depth,
                   stack, demand, root):
        """macro 안에서 ``key``를 만드는 변환 하나를 적용한다.

        변환의 입력이 같은 macro의 다른 변환이 만드는 내부 node라면 그 변환을
        먼저 적용한다. FILTER-AGGREGATE-MEASURE처럼 조각 하나가 여러 변환의
        사슬인 경우를 위한 경로다.
        """
        spec = next(
            (item for item in macro.transformations if item.output == key),
            None,
        )
        if spec is None:
            return False
        node_spec = macro.concepts.get(key)
        if node_spec is not None and output_node.source in PRODUCED_SOURCES:
            # 생성 node의 출처는 macro 정의가 정한다(Tool 결과인지 로컬 계산인지).
            output_node.source = node_spec.source
        inherited = _inherited_demand(macro, key, demand)

        bound = []
        for input_key in spec.inputs:
            port = macro.input_ports.get(input_key)
            if port is None:
                node_spec = macro.concepts.get(input_key)
                if node_spec is None:
                    return False
                if _produced_within(macro, input_key):
                    internal = build.add_node(_internal_node(
                        node_spec, input_key, root, grounding, build,
                    ))
                    if not self._apply_key(
                        macro, input_key, internal, grounding, build,
                        depth=depth, stack=stack, demand={}, root=root,
                    ):
                        return False
                    bound.append(internal)
                    continue
                # macro 내부 node. 같은 방식으로 다시 만든다.
                internal = build.add_node(ConceptNode(
                    id=build.unique_id(f"{output_node.id}_{input_key}"),
                    concept=output_node.concept,
                    subtype=node_spec.resolve_subtype(grounding.factors),
                    role=node_spec.role,
                    source=node_spec.source,
                ))
                if not self._produce(
                    internal, grounding, build,
                    depth=depth + 1, stack=stack, demand={},
                ):
                    return False
                bound.append(internal)
                continue

            node = self._resolve_port(
                macro, port, output_node, grounding, build,
                depth=depth, stack=stack,
                demand={**port.required_attributes, **inherited.get(input_key, {})},
            )
            if node is None:
                if port.required:
                    return False
                continue
            bound.append(node)

        binding = self._bind(macro, spec, bound, output_node, grounding, build)
        build.transformations.append(Transformation(
            id=build.unique_transformation_id(spec.id),
            operator=binding.operator,
            inputs=dict(binding.inputs),
            outputs=[output_node.id],
            params=dict(binding.params),
        ))
        build.used_factors.update(binding.used_factors)
        if key in macro.output_ports:
            # 내부 변환은 같은 조각의 일부이므로 조각 적용은 한 번으로 센다.
            build.applied.append(macro.name)
        return True

    def _bind(self, macro, spec, bound, output_node, grounding, build):
        """변환 하나의 operator와 parameter를 정한다.

        구간별 값을 받아 구간이 없는 값을 만드는 변환은 로컬 분석 연산자다.
        무엇을 할지는 집계 spec이 정한다. 나머지는 operator mapping이 TIMS
        operator를 고른다.
        """
        where = f"{macro.name}.{spec.id}"
        aggregation = grounding.aggregation
        if (
            len(bound) == 1 and analysis_ops.is_grouped(bound[0])
            and not analysis_ops.is_grouped(output_node)
        ):
            return _bind_group_combination(where, bound[0], output_node,
                                           aggregation)

        binding = operator_mapping.resolve(
            inputs=bound,
            output=output_node,
            factors=_tool_factors(grounding),
            where=where,
            # 선택에는 쓰지 않는다. 실패했을 때 필수 input이 graph에 정말
            # 없는지 판정하는 데만 쓴다.
            available_nodes=[
                node for node in build.nodes.values()
                if node.id != output_node.id and _bindable(node)
            ],
        )
        operator = get_operator(binding.operator)
        if not analysis_ops.is_grouped(output_node):
            if (
                aggregation.inner_specified
                and operator.inherent_reducer == aggregation.inner
            ):
                # "차량 대수의 합" 같은 표현. 개수 Tool의 결과가 곧 그 집계다.
                return OperatorBinding(
                    operator=binding.operator,
                    inputs=dict(binding.inputs),
                    params=dict(binding.params),
                    used_factors=binding.used_factors | {"aggregation"},
                )
            return binding
        if not operator.accepts_reducer:
            raise CompositionError(
                f"{where}: {binding.operator}는 구간 안 집계 방식을 받지 않아 "
                "구간별 값을 정할 수 없습니다.",
                user_message="이 측정값은 주·월 구간별 계산을 지원하지 않습니다.",
                code="UNSUPPORTED_GROUPED_MEASURE",
                context={"operator": binding.operator,
                         "aggregation": aggregation.to_dict()},
            )
        if not aggregation.inner_specified:
            # Tool 기본값(avg)을 조용히 쓰지 않는다. "주별 매출"은 주별 합계일
            # 수도, 일평균일 수도 있다. 다시 물어 채우는 것도 하지 않는다. 국소
            # 재질의(L1)는 질문에 없는 구간 안 집계를 지어냈다.
            raise CompositionError(
                f"{where}: 구간 안 집계 방식이 질문에 없습니다.",
                user_message=(
                    "각 구간 안에서 값을 어떻게 모을지(합계, 평균 등)가 질문에 "
                    "없습니다. 예: '주별 매출 합계의 평균'처럼 적어 주세요."
                ),
                code="AMBIGUOUS_INNER_AGGREGATION",
                context={"aggregation": aggregation.to_dict(),
                         "operator": binding.operator,
                         # 오류가 아니라 사용자 확인이 필요한 상태다. 무엇을 물어야
                         # 하는지와 고를 수 있는 값을 함께 남긴다.
                         "needs_clarification": True,
                         "clarify": "inner_reducer",
                         "choices": sorted(REDUCERS)},
            )
        return OperatorBinding(
            operator=binding.operator,
            inputs=dict(binding.inputs),
            params=dict(binding.params),
            used_factors=binding.used_factors | {"bucket"},
        )

    def _resolve_port(self, macro, port, output_node, grounding, build,
                      *, depth, stack, demand):
        """input port 하나에 연결할 node를 정한다."""
        matches = [
            node for node in build.nodes.values()
            if node.id != output_node.id
            and _bindable(node)
            and port.accepts_type(node.concept, node.subtype, role=node.role)
            and _satisfies(node, demand)
        ]
        if len(matches) > 1:
            raise CompositionError(
                f"{macro.name}.{port.name}에 연결할 개념이 여럿입니다: "
                + ", ".join(sorted(node.id for node in matches)),
                code="AMBIGUOUS_PORT",
                context={"macro": macro.name, "port": port.name},
            )
        if matches:
            return matches[0]

        node = self._expand_port(
            macro, port, grounding, build,
            depth=depth, stack=stack, demand=demand,
        )
        if node is not None:
            return node
        return self._infer_port(port, output_node, build, demand)

    def _expand_port(self, macro, port, grounding, build, *, depth, stack,
                     demand):
        """port가 요구하는 개념을 다른 macro로 만들어 본다."""
        mark = build.failure_mark()
        for producer in self._producers_for(port):
            concept, subtype = _first_type(producer, port)
            if concept is None:
                continue
            key = producer.output_port_for(concept, subtype)
            node_spec = producer.concepts.get(key)
            if node_spec is None:
                continue
            # 실제 subtype은 factor가 정한다. "근처"는 여기서 갈린다.
            subtype = node_spec.resolve_subtype(grounding.factors) or subtype
            concept = _concept_of(producer, key, subtype) or concept
            if not port.accepts_type(concept, subtype, role=node_spec.role):
                continue

            state = build.snapshot()
            candidate = build.add_node(ConceptNode(
                id=build.unique_id(f"{port.name}_{key}"),
                concept=concept,
                subtype=subtype,
                role=node_spec.role,
                source=node_spec.source,
            ))
            try:
                produced = self._produce(
                    candidate, grounding, build,
                    depth=depth + 1, stack=stack, demand=demand,
                )
            except CompositionError as error:
                build.note_failure(producer.name, error)
                produced = False
            if produced:
                _inherit_attributes(candidate, producer, key, build)
                if _satisfies(candidate, demand):
                    _rename_produced(candidate, build)
                    build.forget_failures_since(mark)
                    return candidate
            build.restore(state)
        return None

    def _producers_for(self, port):
        """port를 채울 수 있는 macro를 결정적 순서로 모은다."""
        producers = []
        for concept, subtype in sorted(
            port.types, key=lambda item: (item[0].value, item[1]),
        ):
            for macro in self.library.producing(concept, subtype):
                if macro not in producers:
                    producers.append(macro)
        return producers

    def _infer_port(self, port, output_node, build, demand=None):
        """질문에 없지만 반드시 따라오는 개념을 만든다.

        속도를 재려면 통행(passage)이 있어야 한다는 것처럼, registry가
        유일하게 결정할 수 있는 개념만 대상으로 한다. 후보가 여럿이면
        만들지 않는다.
        """
        if not port.concepts <= INFERABLE_CONCEPTS:
            return None
        subtype = operator_mapping.event_subtype_for(
            output_node.concept, output_node.subtype,
        )
        if subtype is None or not port.accepts_type(
            CoreConcept.EVENT, subtype,
        ):
            return None
        if demand:
            # 속성 조건이 붙은 port에는 개념을 만들어 넣지 않는다.
            return None
        role = (
            next(iter(sorted(port.roles, key=lambda item: item.value)))
            if port.roles else FunctionalRole.SUPPORT
        )
        return build.add_node(ConceptNode(
            id=build.unique_id(subtype),
            concept=CoreConcept.EVENT,
            subtype=subtype,
            role=role,
            source=NodeSource.IMPLICIT,
            # implicit 개념의 값은 그 개념의 이름 자체다. 실행 전에 이미
            # 정해져 있으므로 G5의 "값이 있어야 한다"를 만족한다.
            value=subtype,
            attributes={"inferred": True},
        ))

    # -- 마무리 ------------------------------------------------------------

    def _unused_conditions(self, grounding, build, goal_node):
        """질문의 조건 중 계획에 닿지 않은 것."""
        connected = _reachable(build, goal_node.id)
        return [
            concept.id for concept in grounding.concepts
            if concept.id in build.nodes and concept.id not in connected
        ]

    def _unconsumed_factors(self, grounding, build):
        """조건을 거는 factor 중 어떤 변환도 받지 못한 것.

        예전에는 plan.unused_factors에 적고 실행했다. "법인택시 평균 속도"가
        택시 유형 없이 계산되는 식이다. 조건을 잃은 계획은 실행하지 않는다.
        """
        aggregation = grounding.aggregation
        required = {
            name for name, value in grounding.factors.items()
            if name not in STRUCTURAL_FACTORS and name not in FLAT_KEYS
            and NON_RESTRICTIVE_FACTORS.get(name, object()) != value
        }
        if aggregation.inner_specified:
            required.add("aggregation")
        if aggregation.grouped:
            required.add("bucket")
            required.add("select" if aggregation.select else "rollup")
        return sorted(required - build.used_factors)

    def _build_plan(self, grounding, build, goal_node):
        connected = _reachable(build, goal_node.id)
        concepts = [
            node for node in build.nodes.values() if node.id in connected
        ]
        # applied_macros는 적용 횟수를 그대로 남긴다. OD 질의처럼 같은 조각이
        # 두 번 쓰이는 경우를 기록에서 확인할 수 있어야 하기 때문이다.
        # template 서명은 읽기 쉽게 중복을 접는다.
        applied = list(build.applied)
        return GeoFlowPlan(
            version=GEOFLOW_VERSION,
            question=grounding.question,
            template="+".join(dict.fromkeys(applied)),
            concepts=concepts,
            transformations=list(build.transformations),
            final_node=goal_node.id,
            slots=_surface_slots(grounding, goal_node),
            applied_macros=applied,
            unused_factors={
                name: value for name, value in grounding.factors.items()
                if name not in build.used_factors
                and name not in STRUCTURAL_FACTORS
            },
        )


# -- LOCATION 관계 불변식 ----------------------------------------------------


def _location_ports(spec):
    return [
        (port, port_spec) for port, port_spec in spec.inputs.items()
        if port_spec.concept == CoreConcept.LOCATION
    ]


def _location_capacity(spec):
    """이 operator가 받을 수 있는 "구분 없는 장소"의 개수.

    ``place_name``/``place_region``처럼 같은 node의 다른 field를 보는 port는
    한 자리로 센다. 타입 서명이 같으면 같은 node가 들어가기 때문이다.
    """
    return len({
        (port_spec.concept, port_spec.subtypes, port_spec.match_attributes)
        for _, port_spec in _location_ports(spec)
        if not port_spec.match_attributes
    })


def _location_contract(candidates):
    """후보 operator들의 LOCATION port 계약을 하나로 요약한다.

    질문 문자열을 보지 않고 registry의 typed port 계약만으로 유도한다.
    """
    capacity = 0
    required_keys = set()
    qualified_ports = []
    requires_qualifier = bool(candidates)
    for spec in candidates:
        free = _location_capacity(spec)
        capacity = max(capacity, free)
        if free:
            requires_qualifier = False
        for port, port_spec in _location_ports(spec):
            if port_spec.match_attributes:
                qualified_ports.append(port)
                required_keys.update(
                    key for key, _ in port_spec.match_attributes
                )
    return capacity, requires_qualifier, sorted(required_keys), qualified_ports


def _check_location_relations(grounding, goal, goal_node):
    """장소가 목표에 연결될 수 있는 형태인지 확인한다.

    두 가지를 본다. 둘 다 operator registry의 port 계약에서 유도하며, 질문
    문자열이나 측정값 이름을 보지 않는다.

    1. 후보 operator가 받을 수 있는 "구분 없는 장소" 자리보다 질문의 장소가
       많으면, 어느 장소를 어디에 쓸지 정할 수 없다.
    2. 후보 operator의 LOCATION port가 모두 속성 한정 port라면, 장소마다 그
       한정이 있어야 한다. 예를 들어 승차/하차 범위만 받는 Tool에는 구분
       없는 장소를 넣을 자리가 없다.

    빠진 한정을 임의로 채우지 않는다. 출발지와 도착지 중 어느 쪽인지는
    질문만이 가진 정보이고, 추정하면 반대로 답할 수 있다.
    """
    candidates = operator_mapping.candidates_for(goal.concept, goal.subtype)
    if not candidates:
        return
    locations = [
        concept for concept in grounding.concepts
        if concept.concept == CoreConcept.LOCATION
        and concept.id != goal_node.id
    ]
    if not locations:
        return

    capacity, requires_qualifier, required_keys, qualified_ports = (
        _location_contract(candidates)
    )
    unqualified = [
        concept for concept in locations
        if not (set(required_keys) & set(concept.attributes))
    ]
    diagnostics = {
        "locations": [concept.id for concept in locations],
        "location_count": len(locations),
        "unqualified": [concept.id for concept in unqualified],
        "unqualified_capacity": capacity,
        "required_qualifiers": required_keys,
        "candidate_operators": [spec.name for spec in candidates],
        "candidate_ports": sorted(set(qualified_ports)),
        "goal": f"{goal.concept.value}/{goal.subtype}",
    }

    if len(unqualified) >= 2 and len(unqualified) > capacity:
        raise CompositionError(
            "구분 없는 장소가 "
            f"{len(unqualified)}개인데 이 분석은 {capacity}개까지만 받을 수 "
            "있습니다: " + ", ".join(sorted(diagnostics["unqualified"])),
            user_message=(
                "질문에 장소가 여러 개인데 서로 어떤 관계인지 확정할 수 "
                "없습니다."
            ),
            code="AMBIGUOUS_LOCATION_RELATION",
            context=diagnostics,
        )

    if requires_qualifier and unqualified:
        raise CompositionError(
            "이 분석은 역할이 구분된 장소만 받는데 구분이 없는 장소가 "
            "있습니다: " + ", ".join(sorted(diagnostics["unqualified"]))
            + f" (필요한 구분: {', '.join(required_keys)})",
            user_message=(
                "질문의 장소가 분석에서 어떤 역할인지 구분되지 않았습니다."
            ),
            code="MISSING_RELATION_QUALIFIER",
            context=diagnostics,
        )


# -- 집계 -----------------------------------------------------------------


def _check_aggregation_combination(grounding, aggregation):
    """구간별 집계와 함께 성립하지 않는 조건을 합성 전에 거부한다."""
    if not aggregation.grouped:
        return
    present = [name for name in _GROUPED_EXCLUSIVE if name in grounding.factors]
    if present:
        raise CompositionError(
            "주·월 구간별 집계와 그룹 기준·순위를 함께 계산할 수 없습니다: "
            + ", ".join(present),
            user_message=(
                "구간별 집계와 지역·요일별 분포를 한 번에 계산하는 기능은 "
                "지원하지 않습니다."
            ),
            code="UNSUPPORTED_AGGREGATION_COMBINATION",
            context={"present": present, "aggregation": aggregation.to_dict()},
        )


def _tool_factors(grounding):
    """TIMS operator에 넘길 조건. 집계는 flat factor가 아니라 spec에서 온다.

    bucket·rollup은 의미 graph의 node와 변환으로 표현하므로 여기서 넘기지
    않는다. Tool 인자로 되살리는 것은 compiler의 lowering이다.
    """
    factors = {
        name: value for name, value in grounding.factors.items()
        if name not in FLAT_KEYS
    }
    aggregation = grounding.aggregation
    if aggregation.inner_specified:
        factors["aggregation"] = aggregation.inner
    return factors


def _bind_group_combination(where, groups, output_node, aggregation):
    """구간별 값 → 값/구간 변환에 로컬 분석 연산자를 붙인다."""
    if (groups.concept, groups.subtype) != (output_node.concept,
                                            output_node.subtype):
        raise CompositionError(
            f"{where}: 구간별 값과 결과의 개념이 다릅니다: "
            f"{groups.concept.value}/{groups.subtype} → "
            f"{output_node.concept.value}/{output_node.subtype}",
            code="NO_OPERATOR",
            context={"where": where},
        )
    ref = {"groups": ValueRef(groups.id)}
    if aggregation.select:
        output_node.attributes[analysis_ops.RETURNS] = analysis_ops.RETURNS_GROUP
        return OperatorBinding(
            operator=analysis_ops.SELECT_GROUP, inputs=ref,
            params={"select": aggregation.select},
            used_factors=frozenset({"select"}),
        )
    if aggregation.outer:
        return OperatorBinding(
            operator=analysis_ops.REDUCE_GROUPS, inputs=ref,
            params={"reducer": aggregation.outer},
            used_factors=frozenset({"rollup"}),
        )
    raise CompositionError(
        f"{where}: 구간별 값을 합치거나 고르는 방법이 없습니다.",
        user_message="구간별 값을 어떻게 합칠지 질문에서 찾지 못했습니다.",
        code="MISSING_OUTER_AGGREGATION",
        context={"aggregation": aggregation.to_dict()},
    )


def _unconsumed_error(grounding, names):
    labels = ", ".join(_FACTOR_LABELS.get(name, name) for name in names)
    return CompositionError(
        "질문의 조건을 받는 변환이 없습니다: " + ", ".join(names),
        user_message=(
            f"질문의 조건 중 현재 분석이 반영할 수 없는 것이 있습니다: {labels}"
        ),
        code="UNCONSUMED_CONDITION",
        context={
            "unconsumed": list(names),
            "values": {name: grounding.factors.get(name) for name in names},
            "aggregation": grounding.aggregation.to_dict(),
        },
    )


def _produced_within(macro, key):
    return any(item.output == key for item in macro.transformations)


def _internal_node(node_spec, key, root, grounding, build):
    """macro 내부 변환이 만드는 중간 node.

    ``same_type_as``이면 목표와 같은 (concept, subtype)이다. 구간별 node는 구간
    키를 속성으로 갖는다. 구간 키는 grounding의 집계 spec에서만 온다.
    """
    if node_spec.same_type_as is not None:
        concept, subtype = root.concept, root.subtype
    else:
        concept = root.concept
        subtype = node_spec.resolve_subtype(grounding.factors)
    attributes = {}
    if node_spec.grouped:
        attributes[analysis_ops.GROUP_BY] = {
            "bucket": grounding.aggregation.bucket,
        }
    return ConceptNode(
        id=build.unique_id(f"{root.id}_{key}"),
        concept=concept,
        subtype=subtype,
        role=node_spec.role,
        source=node_spec.source,
        attributes=attributes,
    )


# -- helper -----------------------------------------------------------------


def _seed_node(concept):
    """grounding 개념을 실행 전에 값이 있는 node로 만든다.

    값을 채우는 대상은 EVENT뿐이다. 사건은 "무엇을 재는가"를 뜻하므로 개념
    이름이 곧 값이고, 실행 전에 이미 정해져 있어 G5를 만족한다.

    다른 concept까지 subtype 문자열로 채우면 안 된다. 값 없는 LOCATION/place에
    ``"place"``를 넣으면 형식상 값이 있는 것처럼 보여 검증을 통과하고, 실제
    조회 단계에서 ``value["name"]``을 꺼내려다 참조 오류로 터진다.
    """
    node = concept.to_node()
    if (
        node.source == NodeSource.IMPLICIT
        and node.value is None
        and node.concept == CoreConcept.EVENT
    ):
        node.value = node.subtype
    return node


def _bindable(node):
    """input port에 연결할 수 있는 node인지 본다.

    실행이 값을 채워 주는 node(TOOL/DERIVED)이거나, 이미 값을 갖고 있어야
    한다. 값이 없는 node를 연결하면 실행할 수 없는 계획이 만들어진다.
    검증(G5)도 같은 것을 보지만, 여기서 먼저 막아야 합성이 애초에 그런
    계획을 후보로 삼지 않는다.
    """
    return node.source in PRODUCED_SOURCES or node.value is not None


def _first_type(producer, port):
    """producer가 port를 채울 때 만들 (concept, subtype)을 하나 고른다."""
    for concept, subtype in sorted(
        port.types, key=lambda item: (item[0].value, item[1]),
    ):
        if producer.produces(concept, subtype):
            return concept, subtype
    return None, None


def _concept_of(producer, key, subtype):
    port = producer.output_ports.get(key)
    if port is None:
        return None
    for concept, candidate in port.types:
        if candidate == subtype:
            return concept
    return None


def _inherited_demand(macro, port_name, demand):
    """출력 node가 물려받는 속성 조건을 입력 port 쪽으로 넘긴다.

    OD 질의에서 "승차 범위"를 요구받은 PLACE_TO_SCOPE가 어느 장소를 변환해야
    하는지 알 수 있게 하는 경로다. 이 연결이 없으면 출발지와 도착지 중
    어느 쪽을 쓸지 정할 수 없어 합성이 모호해진다.
    """
    node_spec = macro.concepts.get(port_name)
    if node_spec is None or not node_spec.inherit_from:
        return {}
    passed = {
        name: value for name, value in (demand or {}).items()
        if name in node_spec.inherit_attributes
    }
    return {node_spec.inherit_from: passed} if passed else {}


def _inherit_attributes(node, producer, key, build):
    """만들어진 node가 입력 node의 속성을 물려받게 한다."""
    node_spec = producer.concepts.get(key)
    if node_spec is None or not node_spec.inherit_attributes:
        return
    transformation = next(
        (item for item in build.transformations if node.id in item.outputs),
        None,
    )
    if transformation is None:
        return
    for ref in transformation.inputs.values():
        source = build.nodes.get(ref.node_id)
        if source is None:
            continue
        for name in node_spec.inherit_attributes:
            if name in source.attributes:
                node.attributes[name] = source.attributes[name]


def _rename_produced(node, build):
    """중간 node 이름을 입력 node에서 따와 추적하기 쉽게 만든다."""
    transformation = next(
        (item for item in build.transformations if node.id in item.outputs),
        None,
    )
    if transformation is None:
        return
    sources = [
        build.nodes[ref.node_id] for ref in transformation.inputs.values()
        if ref.node_id in build.nodes
    ]
    origin = next(
        (item for item in sources if item.concept == node.concept), None,
    )
    if origin is None:
        return
    new_id = build.unique_id(f"{origin.id}_{node.subtype}")
    if new_id == node.id:
        return
    build.nodes.pop(node.id, None)
    old_id = node.id
    node.id = new_id
    build.nodes[new_id] = node
    for item in build.transformations:
        item.outputs = [
            new_id if output == old_id else output for output in item.outputs
        ]
        item.inputs = {
            port: (ValueRef(new_id, ref.field) if ref.node_id == old_id else ref)
            for port, ref in item.inputs.items()
        }


def _satisfies(node, demand):
    """node가 속성 조건을 만족하는지 본다."""
    if not demand:
        return True
    return all(
        node.attributes.get(name) == value for name, value in demand.items()
    )


def _reachable(build, final_node_id):
    """final node에서 거꾸로 닿는 node id 집합. G5와 같은 규칙이다."""
    producers = {
        output_id: item
        for item in build.transformations
        for output_id in item.outputs
    }
    seen = set()
    queue = [final_node_id]
    while queue:
        node_id = queue.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        producer = producers.get(node_id)
        if producer is None:
            continue
        queue.extend(ref.node_id for ref in producer.inputs.values())
    return seen


def _surface_slots(grounding, goal_node):
    """answer 생성과 재계획이 읽는 표층 조건을 모은다.

    Tool 인자는 transformation params가 갖는다. 여기 담기는 값은 답변 문장을
    만들고, 장소 조회가 실패했을 때 어느 조건을 고쳐야 하는지 찾기 위한
    것이다. 장소는 ``{"name", "region"}`` 형태를 유지해야 한다.
    """
    slots = {
        name: value for name, value in grounding.factors.items()
        if name not in STRUCTURAL_FACTORS
    }
    aggregation = grounding.aggregation
    if not aggregation.grouped and aggregation.inner_specified:
        # 구조화 표기로 받은 집계도 답변이 읽을 수 있게 같은 자리에 둔다.
        slots["aggregation"] = aggregation.inner
    for concept in grounding.concepts:
        if concept.concept != CoreConcept.LOCATION or concept.value is None:
            # 실행이 채울 장소(예: "이 범위가 어디인가")는 표층 조건이 아니다.
            continue
        if concept.subtype == Subtype.PLACE:
            slots[_OD_SLOT.get(concept.od_role, SLOT_PLACE)] = concept.value
        elif concept.subtype in (Subtype.SCOPE, Subtype.VICINITY_SCOPE):
            slots[SLOT_SCOPE] = concept.value
    if goal_node.concept in (CoreConcept.AMOUNT, CoreConcept.PROPORTION):
        # 측정값의 subtype이 곧 metric이다.
        slots[SLOT_METRIC] = goal_node.subtype
    return slots
