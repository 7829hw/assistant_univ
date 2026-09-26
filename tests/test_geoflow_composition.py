# -*- coding: utf-8 -*-
"""Grounding → macro composition → operator mapping 테스트.

여기서 확인하는 것은 "질문을 어떤 유형으로 분류했는가"가 아니라 다음 세
가지다.

1. 같은 조각이 여러 질문에서 재사용되는가
2. 조각이 IO port의 타입 계약으로만 연결되는가
3. 어떤 Tool을 부를지가 질문 문자열이 아니라 concept에서 유도되는가
"""

import os
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from build import build  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402
from tool_handlers import get_tool_handlers  # noqa: E402

from geoflow import operator_mapping  # noqa: E402
from geoflow import validator as geoflow_validator  # noqa: E402
from geoflow.compiler import compile_plan  # noqa: E402
from geoflow.composer import MacroComposer  # noqa: E402
from geoflow.errors import CompositionError, PlannerError  # noqa: E402
from geoflow.executor import STATUS_OK, execute_plan  # noqa: E402
from geoflow.grounding import parse_grounding  # noqa: E402
from geoflow.macros import MacroLibrary  # noqa: E402
from geoflow.operator_registry import (  # noqa: E402
    Operator,
    get_operator,
    operator_names,
)
from geoflow.types import (  # noqa: E402
    CONCEPT_SUBTYPES,
    KNOWN_SUBTYPES,
    ConceptNode,
    CoreConcept,
    FunctionalRole,
    NodeSource,
    Subtype,
    subtype_allowed,
)
from geoflow.validator import Rule  # noqa: E402

TOOLS, _SYSTEM_PROMPT = build()


def new_tool_executor():
    return ToolExecutor(tools=TOOLS, handlers=get_tool_handlers())


# -- grounding fixture ------------------------------------------------------


def place(node_id, name, region="", *, od_role=None):
    concept = {
        "id": node_id, "concept": "LOCATION", "subtype": "place",
        "role": "SUBCOND", "source": "user",
        "value": {"name": name, "region": region},
    }
    if od_role is not None:
        concept["attributes"] = {"od_role": od_role}
    return concept


def scope(node_id, value):
    return {
        "id": node_id, "concept": "LOCATION", "subtype": "scope",
        "role": "COND", "source": "user", "value": value,
    }


def event(node_id, subtype):
    return {
        "id": node_id, "concept": "EVENT", "subtype": subtype,
        "role": "SUPPORT", "source": "implicit",
    }


def measure(node_id, concept, subtype):
    return {
        "id": node_id, "concept": concept, "subtype": subtype,
        "role": "MEASURE", "source": "implicit",
    }


def payload(concepts, factors=None):
    return {"concepts": list(concepts), "factors": dict(factors or {})}


class ComposerCase(unittest.TestCase):
    """합성 결과를 조각·연산자·Tool 수준에서 확인하는 공통 도구."""

    @classmethod
    def setUpClass(cls):
        cls.library = MacroLibrary.from_directory()
        cls.composer = MacroComposer(cls.library)
        cls.tool_executor = new_tool_executor()

    def compose(self, question, concepts, factors=None):
        grounding = parse_grounding(payload(concepts, factors), question)
        return self.composer.compose(grounding)

    def assert_valid(self, plan):
        report = geoflow_validator.validate(
            plan, available_tools=self.tool_executor.tool_names,
        )
        self.assertTrue(report.ok, report.errors)
        return report

    def operators(self, plan):
        return [item.operator for item in plan.transformations]

    def tools(self, plan):
        return [step.tool_name for step in compile_plan(plan).steps]


class CompositionTest(ComposerCase):
    """C. 대표 질의의 합성 결과."""

    def test_place_scope_passage_speed(self):
        plan = self.compose(
            "대구 지역내 택시들의 평균 속도는?",
            [place("p", "대구"), event("e", "passage"),
             measure("m", "AMOUNT", "speed")],
            {"aggregation": "avg"},
        )
        self.assertEqual(
            plan.applied_macros, ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
        )
        self.assertEqual(
            self.operators(plan),
            [Operator.RESOLVE_PLACE_SCOPE, Operator.PASSAGE_METRIC],
        )
        self.assert_valid(plan)

    def test_vicinity_place_makes_a_vicinity_scope(self):
        """같은 조각이 factor 하나로 주변 범위를 만든다."""
        plan = self.compose(
            "동대구역 근처 차량의 평균 속도는?",
            [place("p", "동대구역"), event("e", "passage"),
             measure("m", "AMOUNT", "speed")],
            {"vicinity": True},
        )
        self.assertEqual(
            plan.applied_macros, ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
        )
        scope_node = next(
            node for node in plan.concepts
            if node.subtype == Subtype.VICINITY_SCOPE
        )
        self.assertEqual(scope_node.source, NodeSource.TOOL)
        resolve = plan.transformations[0]
        self.assertIs(resolve.params["include_vicinity"], True)
        self.assert_valid(plan)

    def test_direct_scope_skips_the_place_macro(self):
        """범위가 이미 주어지면 앞 조각이 붙지 않는다."""
        plan = self.compose(
            "scope:edge:1742상의 평균 속도는?",
            [scope("s", "scope:edge:1742"), event("e", "passage"),
             measure("m", "AMOUNT", "speed")],
        )
        self.assertEqual(plan.applied_macros, ["EVENT_TO_MEASURE"])
        self.assertEqual(self.operators(plan), [Operator.PASSAGE_METRIC])
        self.assert_valid(plan)

    def test_direct_and_place_share_the_measure_macro(self):
        direct = self.compose(
            "scope:edge:1742상의 평균 속도는?",
            [scope("s", "scope:edge:1742"),
             measure("m", "AMOUNT", "speed")],
        )
        place_plan = self.compose(
            "대구 지역내 택시들의 평균 속도는?",
            [place("p", "대구"), measure("m", "AMOUNT", "speed")],
        )
        self.assertEqual(direct.applied_macros[-1], "EVENT_TO_MEASURE")
        self.assertEqual(place_plan.applied_macros[-1], "EVENT_TO_MEASURE")
        self.assertEqual(len(place_plan.applied_macros), 2)
        self.assertEqual(len(direct.applied_macros), 1)

    def test_place_scope_trip_fare(self):
        plan = self.compose(
            "대구의 평균 택시 요금은?",
            [place("p", "대구"), event("e", "trip"),
             measure("m", "AMOUNT", "fare")],
            {"aggregation": "avg"},
        )
        self.assertEqual(
            plan.applied_macros, ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
        )
        self.assertEqual(
            self.operators(plan),
            [Operator.RESOLVE_PLACE_SCOPE, Operator.TRIP_METRIC],
        )
        self.assertEqual(plan.transformations[-1].params["metric"], "fare")
        self.assert_valid(plan)

    def test_origin_destination_trip_count(self):
        plan = self.compose(
            "대구 동성로에서 출발하여 신천동에 도착한 실차 구간 건수는?",
            [
                place("o", "동성로", "대구", od_role="pickup"),
                place("d", "신천동", od_role="dropoff"),
                event("e", "trip"),
                measure("m", "AMOUNT", "trip_count"),
            ],
        )
        # 같은 조각이 두 번 적용된 사실이 기록에 남는다.
        self.assertEqual(
            plan.applied_macros,
            ["PLACE_TO_SCOPE", "PLACE_TO_SCOPE", "OD_EVENT_TO_MEASURE"],
        )
        self.assertEqual(
            plan.template, "PLACE_TO_SCOPE+OD_EVENT_TO_MEASURE",
        )
        self.assertEqual(
            self.operators(plan),
            [
                Operator.RESOLVE_PLACE_SCOPE,
                Operator.RESOLVE_PLACE_SCOPE,
                Operator.TRIP_COUNT,
            ],
        )
        count = plan.transformations[-1]
        self.assertEqual(count.inputs["pickup"].node_id, "o_scope")
        self.assertEqual(count.inputs["dropoff"].node_id, "d_scope")
        self.assert_valid(plan)

    def test_pickup_only_is_composable(self):
        """하나만 주어져도 성립한다. 나머지를 지어내지 않는다."""
        plan = self.compose(
            "동성로에서 출발한 실차 구간 건수는?",
            [
                place("o", "동성로", od_role="pickup"),
                event("e", "trip"),
                measure("m", "AMOUNT", "trip_count"),
            ],
        )
        count = plan.transformations[-1]
        self.assertIn("pickup", count.inputs)
        self.assertNotIn("dropoff", count.inputs)
        self.assert_valid(plan)

    def test_operation_revenue(self):
        plan = self.compose(
            "개인택시의 평균 수입은?",
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"taxi_type": "private", "aggregation": "avg"},
        )
        self.assertEqual(plan.applied_macros, ["EVENT_TO_MEASURE"])
        self.assertEqual(self.operators(plan), [Operator.OPERATION_METRIC])
        self.assertEqual(plan.transformations[0].params["metric"], "revenue")
        self.assert_valid(plan)

    def test_drive_vacant_ratio(self):
        plan = self.compose(
            "법인택시의 공차율은?",
            [event("e", "drive"),
             measure("m", "PROPORTION", "vacant_ratio")],
            {"taxi_type": "corporate"},
        )
        self.assertEqual(self.operators(plan), [Operator.DRIVE_METRIC])
        self.assertEqual(
            plan.transformations[0].params["metric"], "vacant_ratio",
        )
        self.assert_valid(plan)

    def test_scope_to_place_name(self):
        plan = self.compose(
            "scope:district:2700000000은 어디인가요?",
            [
                scope("s", "scope:district:2700000000"),
                {"id": "p", "concept": "LOCATION", "subtype": "place",
                 "role": "MEASURE", "source": "implicit"},
            ],
        )
        self.assertEqual(plan.applied_macros, ["SCOPE_TO_PLACE"])
        self.assertEqual(self.operators(plan), [Operator.SCOPE_NAME])
        self.assert_valid(plan)

    def test_grouping_is_a_factor_not_a_macro(self):
        """그룹화는 조각을 늘리지 않고 같은 변환의 인자가 된다."""
        plain = self.compose(
            "택시 수입은?",
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
        )
        grouped = self.compose(
            "요일별 택시 수입 분포는?",
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"dimension": "dayofweek"},
        )
        self.assertEqual(plain.applied_macros, grouped.applied_macros)
        self.assertNotIn("dimension", plain.transformations[0].params)
        self.assertEqual(
            grouped.transformations[0].params["dimension"], "dayofweek",
        )

    def test_event_is_inferred_when_the_question_omits_it(self):
        """속도를 재려면 통행이 필요하다는 것은 registry가 안다."""
        plan = self.compose(
            "대구 지역내 택시들의 평균 속도는?",
            [place("p", "대구"), measure("m", "AMOUNT", "speed")],
        )
        inferred = next(
            node for node in plan.concepts
            if node.concept == CoreConcept.EVENT
        )
        self.assertEqual(inferred.subtype, Subtype.PASSAGE)
        self.assertEqual(inferred.source, NodeSource.IMPLICIT)
        self.assertTrue(inferred.attributes.get("inferred"))
        self.assert_valid(plan)

    def test_applied_macros_are_recorded_on_the_plan(self):
        plan = self.compose(
            "대구 지역내 택시들의 평균 속도는?",
            [place("p", "대구"), measure("m", "AMOUNT", "speed")],
        )
        self.assertEqual(plan.applied_macros, plan.template.split("+"))
        self.assertIn("applied_macros", plan.to_dict())

    def test_template_signature_folds_repeats(self):
        """조각이 두 번 쓰여도 서명은 한 번만 적는다."""
        plan = self.compose(
            "동성로에서 신천동으로 간 실차 구간 건수는?",
            [place("o", "동성로", od_role="pickup"),
             place("d", "신천동", od_role="dropoff"),
             measure("m", "AMOUNT", "trip_count")],
        )
        self.assertEqual(len(plan.applied_macros), 3)
        self.assertEqual(len(plan.template.split("+")), 2)

    def test_composition_is_deterministic(self):
        concepts = [
            place("o", "동성로", od_role="pickup"),
            place("d", "신천동", od_role="dropoff"),
            measure("m", "AMOUNT", "trip_count"),
        ]
        question = "동성로에서 신천동으로 간 실차 구간 건수는?"
        first = self.compose(question, concepts)
        second = self.compose(question, concepts)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_mismatched_event_and_measure_is_rejected(self):
        """요금은 trip에서만 나온다. 통행 사건과 붙일 수 없다."""
        with self.assertRaises(CompositionError) as caught:
            self.compose(
                "평균 택시 요금은?",
                [event("e", "passage"), measure("m", "AMOUNT", "fare")],
            )
        self.assertEqual(caught.exception.code, "NO_OPERATOR")

    def test_two_places_with_the_same_role_are_rejected(self):
        """어느 쪽을 조건으로 쓸지 정할 수 없으면 추측하지 않는다."""
        with self.assertRaises(CompositionError) as caught:
            self.compose(
                "대구와 부산 중 어디가 더 빠른가요?",
                [place("a", "대구"), place("b", "부산"),
                 measure("m", "AMOUNT", "speed")],
            )
        self.assertEqual(
            caught.exception.code, "AMBIGUOUS_LOCATION_RELATION",
        )

    def test_unusable_condition_fails_instead_of_being_dropped(self):
        """범위를 받지 못하는 측정에 장소가 붙으면 조용히 버리지 않는다."""
        with self.assertRaises(CompositionError) as caught:
            self.compose(
                "통행량이 가장 많은 시군구는?",
                [event("e", "passage"),
                 measure("m", "AMOUNT", "passage_count")],
                {"dimension": "sigungu"},
            )
        # get_passage_count는 범위가 필수인데 질문에 장소가 없다. 범위를
        # 지어내지 않고, operator가 없다가 아니라 input이 빠졌다고 말한다.
        self.assertEqual(caught.exception.code, "MISSING_REQUIRED_INPUT")


class RoleOrderingTest(ComposerCase):
    """D. procedural role ordering."""

    def test_composed_plan_follows_subcond_cond_support_measure(self):
        plan = self.compose(
            "대구 지역내 택시들의 평균 속도는?",
            [place("p", "대구"), event("e", "passage"),
             measure("m", "AMOUNT", "speed")],
        )
        roles = {node.id: node.role for node in plan.concepts}
        self.assertEqual(roles["p"], FunctionalRole.SUBCOND)
        self.assertEqual(roles["p_scope"], FunctionalRole.COND)
        self.assertEqual(roles["e"], FunctionalRole.SUPPORT)
        self.assertEqual(roles["m"], FunctionalRole.MEASURE)
        self.assert_valid(plan)

    def test_reversed_dependency_is_rejected_by_g2(self):
        """MEASURE가 COND의 입력이 되는 계획은 역행이다."""
        from geoflow.types import (
            GEOFLOW_VERSION,
            GeoFlowPlan,
            Transformation,
            ValueRef,
        )

        plan = GeoFlowPlan(
            version=GEOFLOW_VERSION,
            question="테스트",
            template="SYNTHETIC",
            concepts=[
                ConceptNode(
                    id="measure_first", concept=CoreConcept.LOCATION,
                    subtype=Subtype.PLACE, role=FunctionalRole.MEASURE,
                    source=NodeSource.USER, value={"name": "대구"},
                ),
                ConceptNode(
                    id="late_scope", concept=CoreConcept.LOCATION,
                    subtype=Subtype.SCOPE, role=FunctionalRole.COND,
                    source=NodeSource.TOOL,
                ),
            ],
            transformations=[Transformation(
                id="resolve",
                operator=Operator.RESOLVE_PLACE_SCOPE,
                inputs={"place_name": ValueRef("measure_first", "name")},
                outputs=["late_scope"],
                params={"include_vicinity": False},
            )],
            final_node="late_scope",
        )
        report = geoflow_validator.validate(
            plan, available_tools=self.tool_executor.tool_names,
            user_scopes=set(),
        )
        self.assertIn(Rule.ROLE_ORDERING, report.failed_rules())

    def test_measure_role_is_required_by_grounding(self):
        with self.assertRaises(PlannerError) as caught:
            parse_grounding(payload([place("p", "대구")]), "대구는?")
        self.assertEqual(caught.exception.code, "NO_MEASURE")


class NoInventionTest(ComposerCase):
    """E. 질문에 없는 정보를 만들지 않는다."""

    def test_absent_date_never_reaches_the_tool(self):
        plan = self.compose(
            "대구 지역내 택시들의 평균 속도는?",
            [place("p", "대구"), measure("m", "AMOUNT", "speed")],
        )
        for step in compile_plan(plan).steps:
            self.assertNotIn("date", step.arguments)
            self.assertNotIn("time", step.arguments)

    def test_present_date_does_reach_the_tool(self):
        plan = self.compose(
            "2026년 5월 30일 대구 지역내 택시들의 평균 속도는?",
            [place("p", "대구"), measure("m", "AMOUNT", "speed")],
            {"date": "20260530"},
        )
        metric = compile_plan(plan).steps[-1]
        self.assertEqual(metric.arguments["date"], "20260530")

    def test_absent_region_is_not_invented(self):
        plan = self.compose(
            "대구 지역내 택시들의 평균 속도는?",
            [place("p", "대구"), measure("m", "AMOUNT", "speed")],
        )
        resolve = compile_plan(plan).steps[0]
        self.assertEqual(resolve.arguments["name"], "대구")
        self.assertNotIn("region", resolve.arguments)

    def test_region_absent_from_the_question_is_dropped(self):
        from geoflow.grounding import drop_unsupported_regions

        grounding = parse_grounding(
            payload([
                place("p", "대구", "경상북도"),
                measure("m", "AMOUNT", "speed"),
            ]),
            "대구 지역내 택시들의 평균 속도는?",
        )
        drop_unsupported_regions(grounding)
        self.assertEqual(grounding.get("p").value["region"], "")

    def test_scope_absent_from_the_question_is_rejected(self):
        with self.assertRaises(PlannerError) as caught:
            parse_grounding(
                payload([
                    scope("s", "scope:district:999999999"),
                    measure("m", "AMOUNT", "speed"),
                ]),
                "대구 지역내 택시들의 평균 속도는?",
            )
        self.assertEqual(caught.exception.code, "UNGROUNDED_SCOPE")

    def test_composer_never_creates_a_scope_node_with_user_source(self):
        plan = self.compose(
            "대구 지역내 택시들의 평균 속도는?",
            [place("p", "대구"), measure("m", "AMOUNT", "speed")],
        )
        produced = [
            node for node in plan.concepts
            if node.subtype in (Subtype.SCOPE, Subtype.VICINITY_SCOPE)
        ]
        self.assertTrue(produced)
        for node in produced:
            self.assertEqual(node.source, NodeSource.TOOL)
            self.assertIsNone(node.value)

    def test_vicinity_written_on_the_concept_is_hoisted(self):
        """"근처"는 장소를 수식하는 말이라 모델이 개념 안에 적는 경우가 잦다.

        뜻은 같고 자리만 다르므로 거부하지 않고 옮긴다. 값을 만들어 내는 것이
        아니므로 질문에 없는 조건이 새로 생기지 않는다.
        """
        concept = place("p", "동대구역")
        concept["attributes"] = {"vicinity": True}
        grounding = parse_grounding(
            payload([concept, measure("m", "AMOUNT", "speed")]),
            "동대구역 근처 평균 속도는?",
        )
        self.assertEqual(grounding.factors, {"vicinity": True})
        self.assertEqual(grounding.get("p").attributes, {})
        plan = self.composer.compose(grounding)
        self.assertIs(
            plan.transformations[0].params["include_vicinity"], True,
        )

    def test_explicit_factors_win_over_a_hoisted_one(self):
        concept = place("p", "동대구역")
        concept["attributes"] = {"vicinity": True}
        grounding = parse_grounding(
            payload([concept, measure("m", "AMOUNT", "speed")],
                    {"vicinity": False}),
            "동대구역 평균 속도는?",
        )
        self.assertIs(grounding.factors["vicinity"], False)

    def test_unknown_factor_is_rejected(self):
        with self.assertRaises(PlannerError) as caught:
            parse_grounding(
                payload(
                    [measure("m", "AMOUNT", "speed")], {"weather": "맑음"},
                ),
                "대구 평균 속도는?",
            )
        self.assertEqual(caught.exception.code, "UNKNOWN_FACTOR")

    def test_malformed_factor_is_rejected(self):
        for factors in ({"date": "2026-05-30"}, {"aggregation": "mean"}):
            with self.subTest(factors=factors):
                with self.assertRaises(PlannerError) as caught:
                    parse_grounding(
                        payload([measure("m", "AMOUNT", "speed")], factors),
                        "대구 평균 속도는?",
                    )
                self.assertEqual(caught.exception.code, "INVALID_FACTOR")

    def test_unsupported_factor_is_rejected_not_silently_dropped(self):
        """Tool이 받지 않는 조건이 있으면 계획을 만들지 않는다.

        예전에는 unused_factors에 적고 택시 유형 없이 계산했다. 그 답은 "법인택시"
        가 아니라 전체 택시의 평균 속도였다.
        """
        with self.assertRaises(CompositionError) as caught:
            self.compose(
                "법인택시의 평균 속도는?",
                [place("p", "대구"), measure("m", "AMOUNT", "speed")],
                {"taxi_type": "corporate"},
            )
        # get_passage_metrics는 taxi_type을 받지 않는다.
        self.assertEqual(caught.exception.code, "UNCONSUMED_CONDITION")
        self.assertEqual(caught.exception.context["unconsumed"], ["taxi_type"])
        self.assertIn("택시 유형", caught.exception.user_message)

    def test_non_restrictive_value_may_be_absent_from_the_tool(self):
        """taxi_type=all은 조건을 걸지 않으므로 받는 Tool이 없어도 계산이 같다."""
        plan = self.compose(
            "대구 택시의 평균 속도는?",
            [place("p", "대구"), measure("m", "AMOUNT", "speed")],
            {"taxi_type": "all"},
        )
        for step in compile_plan(plan).steps:
            self.assertNotIn("taxi_type", step.arguments)


class OperatorMappingTest(ComposerCase):
    """개념 변환 → semantic operator 유도."""

    def test_output_subtype_alone_determines_the_operator(self):
        expected = {
            (CoreConcept.AMOUNT, Subtype.SPEED): Operator.PASSAGE_METRIC,
            (CoreConcept.AMOUNT, Subtype.RPM): Operator.PASSAGE_METRIC,
            (CoreConcept.AMOUNT, Subtype.PASSAGE_COUNT): Operator.PASSAGE_COUNT,
            (CoreConcept.AMOUNT, Subtype.TRIP_COUNT): Operator.TRIP_COUNT,
            (CoreConcept.AMOUNT, Subtype.FARE): Operator.TRIP_METRIC,
            (CoreConcept.AMOUNT, Subtype.REVENUE): Operator.OPERATION_METRIC,
            (CoreConcept.AMOUNT, Subtype.HOURS): Operator.OPERATION_METRIC,
            (CoreConcept.PROPORTION, Subtype.VACANT_RATIO):
                Operator.DRIVE_METRIC,
            (CoreConcept.PROPORTION, Subtype.OPERATING_RATIO):
                Operator.OPERATION_METRIC,
            (CoreConcept.LOCATION, Subtype.PLACE): Operator.SCOPE_NAME,
        }
        for (concept, subtype), operator in expected.items():
            with self.subTest(subtype=subtype):
                candidates = operator_mapping.candidates_for(concept, subtype)
                self.assertEqual(
                    [item.name for item in candidates], [operator],
                )

    def test_fare_and_revenue_map_to_different_tools(self):
        """이름이 비슷한 측정값이 같은 Tool로 합쳐지지 않는다."""
        fare = operator_mapping.candidates_for(
            CoreConcept.AMOUNT, Subtype.FARE,
        )[0]
        revenue = operator_mapping.candidates_for(
            CoreConcept.AMOUNT, Subtype.REVENUE,
        )[0]
        self.assertNotEqual(fare.tool_name, revenue.tool_name)
        self.assertEqual(fare.event_subtypes, frozenset({Subtype.TRIP}))
        self.assertEqual(
            revenue.event_subtypes, frozenset({Subtype.OPERATION}),
        )

    def test_vacant_ratio_and_operating_ratio_map_to_different_tools(self):
        vacant = operator_mapping.candidates_for(
            CoreConcept.PROPORTION, Subtype.VACANT_RATIO,
        )[0]
        operating = operator_mapping.candidates_for(
            CoreConcept.PROPORTION, Subtype.OPERATING_RATIO,
        )[0]
        self.assertNotEqual(vacant.tool_name, operating.tool_name)
        self.assertEqual(vacant.event_subtypes, frozenset({Subtype.DRIVE}))
        self.assertEqual(
            operating.event_subtypes, frozenset({Subtype.OPERATION}),
        )

    def test_event_subtype_is_derived_from_the_measure(self):
        self.assertEqual(
            operator_mapping.event_subtype_for(
                CoreConcept.AMOUNT, Subtype.FARE,
            ),
            Subtype.TRIP,
        )
        self.assertIsNone(
            operator_mapping.event_subtype_for(
                CoreConcept.LOCATION, Subtype.PLACE,
            ),
        )

    def test_unconsumable_input_disqualifies_an_operator(self):
        """받아 줄 port가 없는 입력이 있으면 그 operator는 후보가 아니다."""
        event_node = ConceptNode(
            id="e", concept=CoreConcept.EVENT, subtype=Subtype.TRIP,
            role=FunctionalRole.SUPPORT, source=NodeSource.IMPLICIT,
            value=Subtype.TRIP,
        )
        output = ConceptNode(
            id="m", concept=CoreConcept.AMOUNT, subtype=Subtype.SPEED,
            role=FunctionalRole.MEASURE, source=NodeSource.TOOL,
        )
        with self.assertRaises(CompositionError):
            operator_mapping.resolve(inputs=[event_node], output=output)

    def test_semantic_event_port_makes_no_tool_argument(self):
        spec = get_operator(Operator.PASSAGE_METRIC)
        self.assertTrue(spec.input("event").semantic_only)
        self.assertNotIn(None, spec.argument_names())

    def test_include_vicinity_follows_the_scope_subtype(self):
        """G3의 vicinity 일관성 검사와 같은 규칙으로 인자를 유도한다."""
        plain = self.compose(
            "대구 평균 속도는?",
            [place("p", "대구"), measure("m", "AMOUNT", "speed")],
        )
        vicinity = self.compose(
            "대구 근처 평균 속도는?",
            [place("p", "대구"), measure("m", "AMOUNT", "speed")],
            {"vicinity": True},
        )
        self.assertIs(plain.transformations[0].params["include_vicinity"], False)
        self.assertIs(
            vicinity.transformations[0].params["include_vicinity"], True,
        )

    def test_parameter_contract_is_enforced_before_execution(self):
        """factor 공기 제약은 조각을 고르기 전에 걸린다."""
        with self.assertRaises(PlannerError) as caught:
            self.compose(
                "주 단위 수입은?",
                [event("e", "operation"),
                 measure("m", "AMOUNT", "revenue")],
                {"bucket": "week"},
            )
        self.assertEqual(
            caught.exception.code, "INVALID_FACTOR_COMBINATION",
        )

    def test_operator_level_companion_check_is_the_last_defence(self):
        """grounding을 우회해도 operator 계약이 같은 조합을 거부한다."""
        spec = get_operator(Operator.OPERATION_METRIC)
        self.assertEqual(
            spec.missing_companions("bucket", {"bucket": "week"}),
            ("rollup",),
        )
        self.assertEqual(
            spec.missing_companions(
                "bucket", {"bucket": "week", "rollup": "avg"},
            ),
            (),
        )
        # 그 Tool이 받지 않는 parameter는 제약 대상이 아니다.
        self.assertEqual(
            get_operator(Operator.PASSAGE_METRIC).missing_companions(
                "bucket", {},
            ),
            (),
        )

    def test_parameter_value_outside_the_tool_enum_is_rejected(self):
        # 통행량 Tool의 dimension에는 요일이 없다. factor로는 합법이지만 이
        # Tool의 enum 밖이다.
        with self.assertRaises(CompositionError) as caught:
            self.compose(
                "대구의 요일별 통행량은?",
                [place("p", "대구"), event("e", "passage"),
                 measure("m", "AMOUNT", "passage_count")],
                {"dimension": "dayofweek"},
            )
        self.assertEqual(caught.exception.code, "INVALID_PARAM_VALUE")


class ValidatorRegressionTest(ComposerCase):
    """F. 합성 결과가 G1~G6를 그대로 통과한다."""

    CASES = (
        ("대구 지역내 택시들의 평균 속도는?",
         [place("p", "대구"), measure("m", "AMOUNT", "speed")], {}),
        ("동대구역 근처 통행량은?",
         [place("p", "동대구역"),
          measure("m", "AMOUNT", "passage_count")], {"vicinity": True}),
        ("scope:edge:1742상의 평균 속도는?",
         [scope("s", "scope:edge:1742"),
          measure("m", "AMOUNT", "speed")], {}),
        ("대구의 평균 택시 요금은?",
         [place("p", "대구"), measure("m", "AMOUNT", "fare")], {}),
        ("동성로에서 출발하여 신천동에 도착한 실차 구간 건수는?",
         [place("o", "동성로", od_role="pickup"),
          place("d", "신천동", od_role="dropoff"),
          measure("m", "AMOUNT", "trip_count")], {}),
        ("개인택시의 평균 수입은?",
         [event("e", "operation"),
          measure("m", "AMOUNT", "revenue")], {"taxi_type": "private"}),
        ("법인택시의 공차율은?",
         [event("e", "drive"),
          measure("m", "PROPORTION", "vacant_ratio")], {}),
        ("scope:district:2700000000은 어디인가요?",
         [scope("s", "scope:district:2700000000"),
          {"id": "p", "concept": "LOCATION", "subtype": "place",
           "role": "MEASURE", "source": "implicit"}], {}),
    )

    def test_every_composed_plan_passes_all_rules(self):
        for question, concepts, factors in self.CASES:
            with self.subTest(question=question):
                plan = self.compose(question, concepts, factors)
                report = geoflow_validator.validate(
                    plan,
                    available_tools=self.tool_executor.tool_names,
                    user_scopes=None,
                )
                self.assertTrue(report.ok, report.errors)
                self.assertEqual(
                    report.checked_rules,
                    [
                        Rule.ACYCLICITY, Rule.ROLE_ORDERING,
                        Rule.TYPE_COMPATIBILITY, Rule.EXECUTABILITY,
                        Rule.CONNECTIVITY, Rule.SCOPE_PROVENANCE,
                        Rule.AGGREGATION_SEMANTICS,
                    ],
                )

    def test_every_composed_plan_is_a_dag_with_a_reachable_final_node(self):
        for question, concepts, factors in self.CASES:
            with self.subTest(question=question):
                plan = self.compose(question, concepts, factors)
                self.assertIn(plan.final_node, plan.node_ids)
                report = geoflow_validator.validate(
                    plan, available_tools=self.tool_executor.tool_names,
                )
                self.assertEqual(
                    len(report.order), len(plan.transformations),
                )


class ExecutionRegressionTest(ComposerCase):
    """G. 합성 결과를 실제 Tool까지 실행한다."""

    EXPECTED_TRACE = (
        (
            "대구 지역내 택시들의 평균 속도는?",
            [place("p", "대구"), measure("m", "AMOUNT", "speed")],
            {"aggregation": "avg"},
            ["get_place_scope", "get_passage_metrics"],
        ),
        (
            "동대구역 근처 통행량은?",
            [place("p", "동대구역"), measure("m", "AMOUNT", "passage_count")],
            {"vicinity": True},
            ["get_place_scope", "get_passage_count"],
        ),
        (
            "scope:edge:1742상의 평균 속도는?",
            [scope("s", "scope:edge:1742"), measure("m", "AMOUNT", "speed")],
            {},
            ["get_passage_metrics"],
        ),
        (
            "대구의 평균 택시 요금은?",
            [place("p", "대구"), measure("m", "AMOUNT", "fare")],
            {},
            ["get_place_scope", "get_trip_metrics"],
        ),
        (
            "동성로에서 출발하여 신천동에 도착한 실차 구간 건수는?",
            [place("o", "동성로", od_role="pickup"),
             place("d", "신천동", od_role="dropoff"),
             measure("m", "AMOUNT", "trip_count")],
            {},
            ["get_place_scope", "get_place_scope", "get_trip_count"],
        ),
        (
            "개인택시의 평균 수입은?",
            [event("e", "operation"), measure("m", "AMOUNT", "revenue")],
            {"taxi_type": "private"},
            ["get_operation_metrics"],
        ),
        (
            "법인택시의 공차율은?",
            [event("e", "drive"),
             measure("m", "PROPORTION", "vacant_ratio")],
            {},
            ["get_drive_metrics"],
        ),
        (
            "scope:district:2700000000은 어디인가요?",
            [scope("s", "scope:district:2700000000"),
             {"id": "p", "concept": "LOCATION", "subtype": "place",
              "role": "MEASURE", "source": "implicit"}],
            {},
            ["get_scope_name"],
        ),
    )

    def test_expected_tool_trace(self):
        for question, concepts, factors, tools in self.EXPECTED_TRACE:
            with self.subTest(question=question):
                plan = self.compose(question, concepts, factors)
                self.assert_valid(plan)
                result = execute_plan(
                    compile_plan(plan),
                    new_tool_executor(),
                    known_scopes=set(
                        node.value for node in plan.concepts
                        if node.source == NodeSource.USER
                        and isinstance(node.value, str)
                    ),
                )
                self.assertEqual(result.status, STATUS_OK, result.error)
                self.assertEqual(
                    [entry["tool"] for entry in result.trace], tools,
                )
                self.assertIsNotNone(result.final_value)

    def test_od_binding_is_not_swapped(self):
        plan = self.compose(
            "동성로에서 출발하여 신천동에 도착한 실차 구간 건수는?",
            [place("o", "동성로", od_role="pickup"),
             place("d", "신천동", od_role="dropoff"),
             measure("m", "AMOUNT", "trip_count")],
        )
        result = execute_plan(compile_plan(plan), new_tool_executor())
        self.assertEqual(result.status, STATUS_OK, result.error)
        count_call = result.trace[-1]
        self.assertEqual(
            count_call["arguments"]["scope_pickup"],
            result.trace[0]["result"],
        )
        self.assertEqual(
            count_call["arguments"]["scope_dropoff"],
            result.trace[1]["result"],
        )

    def test_execution_binds_tool_results_not_literals(self):
        plan = self.compose(
            "대구 지역내 택시들의 평균 속도는?",
            [place("p", "대구"), measure("m", "AMOUNT", "speed")],
        )
        result = execute_plan(compile_plan(plan), new_tool_executor())
        self.assertEqual(result.status, STATUS_OK, result.error)
        self.assertEqual(
            result.trace[-1]["arguments"]["scope"], result.trace[0]["result"],
        )


class MeasuredDefectRegressionTest(ComposerCase):
    """실측으로 드러난 구현 결함 3건의 재발 방지.

    셋 다 모델이 계약을 조금 다르게 표현했을 때 시스템이 잘못 반응한 경우다.
    """

    # -- 1. contextual role을 가진 장소 --------------------------------------

    def test_extent_place_binds_to_place_to_scope(self):
        """"대구시의 평균 택시 요금"의 대구를 EXTENT로 읽어도 합성된다.

        EXTENT는 분석의 공간적 배경을 뜻하는 contextual role이다. 좁혀야 할
        조건으로 보든 배경으로 보든 조회를 거쳐야 범위가 된다는 사실은 같다.
        """
        plan = self.compose(
            "대구시의 평균 택시 요금은?",
            [
                {"id": "p", "concept": "LOCATION", "subtype": "place",
                 "role": "EXTENT", "source": "user",
                 "value": {"name": "대구", "region": ""}},
                measure("m", "AMOUNT", "fare"),
            ],
            {"aggregation": "avg"},
        )
        self.assertEqual(
            plan.applied_macros, ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
        )
        self.assertEqual(
            self.operators(plan),
            [Operator.RESOLVE_PLACE_SCOPE, Operator.TRIP_METRIC],
        )
        self.assert_valid(plan)

    def test_extent_role_is_preserved_on_the_node(self):
        """받아들이되 procedural role로 바꾸지 않는다."""
        plan = self.compose(
            "대구시의 평균 택시 요금은?",
            [
                {"id": "p", "concept": "LOCATION", "subtype": "place",
                 "role": "EXTENT", "source": "user",
                 "value": {"name": "대구", "region": ""}},
                measure("m", "AMOUNT", "fare"),
            ],
        )
        node = next(item for item in plan.concepts if item.id == "p")
        self.assertEqual(node.role, FunctionalRole.EXTENT)
        # 만들어진 범위는 macro가 정한 procedural role을 그대로 갖는다.
        scope_node = next(
            item for item in plan.concepts
            if item.subtype == Subtype.SCOPE
        )
        self.assertEqual(scope_node.role, FunctionalRole.COND)

    def test_extent_does_not_weaken_role_ordering(self):
        """contextual role은 G2 순서 검사에서 제외되므로 규칙이 약해지지 않는다."""
        plan = self.compose(
            "대구시의 평균 택시 요금은?",
            [
                {"id": "p", "concept": "LOCATION", "subtype": "place",
                 "role": "EXTENT", "source": "user",
                 "value": {"name": "대구", "region": ""}},
                measure("m", "AMOUNT", "fare"),
            ],
        )
        report = geoflow_validator.validate(
            plan, available_tools=self.tool_executor.tool_names,
        )
        self.assertNotIn(Rule.ROLE_ORDERING, report.failed_rules())
        self.assertTrue(report.ok, report.errors)

    def test_measure_role_is_still_rejected_by_the_place_port(self):
        """port를 넓힌 것이지 아무 role이나 받게 한 것이 아니다."""
        port = self.library.require("PLACE_TO_SCOPE").input_ports["place"]
        self.assertTrue(port.accepts_type(
            CoreConcept.LOCATION, Subtype.PLACE, role=FunctionalRole.EXTENT,
        ))
        for role in (FunctionalRole.MEASURE, FunctionalRole.SUPPORT):
            self.assertFalse(port.accepts_type(
                CoreConcept.LOCATION, Subtype.PLACE, role=role,
            ), role)

    # -- 2. MEASURE가 아닌 개념의 subtype 검증 ------------------------------

    def test_invalid_non_measure_subtype_is_rejected_at_grounding(self):
        """OBJECT/taxi_type은 합성까지 흘러가지 않고 즉시 거부된다.

        예전에는 grounding이 MEASURE의 subtype만 확인해서, 이런 개념이
        composer까지 내려간 뒤 "쓰이지 않은 개념"으로 나타났다. 원인에서
        먼 곳에서 실패하므로 진단이 어려웠다.
        """
        with self.assertRaises(PlannerError) as caught:
            parse_grounding(
                payload([
                    {"id": "t", "concept": "OBJECT", "subtype": "taxi_type",
                     "role": "COND", "source": "user", "value": "private"},
                    measure("m", "AMOUNT", "revenue"),
                ]),
                "개인택시의 평균 수입은?",
            )
        self.assertEqual(caught.exception.code, "INVALID_SUBTYPE")
        self.assertIn("OBJECT", caught.exception.detail)

    def test_subtype_belonging_to_another_concept_is_rejected(self):
        with self.assertRaises(PlannerError) as caught:
            parse_grounding(
                payload([measure("m", "AMOUNT", "place")]), "대구는?",
            )
        self.assertEqual(caught.exception.code, "INVALID_SUBTYPE")

    def test_every_valid_concept_subtype_pair_is_accepted(self):
        """어휘에 있는 조합은 모두 통과해야 한다. 좁히다가 막지 않도록."""
        for concept, subtypes in CONCEPT_SUBTYPES.items():
            for subtype in sorted(subtypes):
                with self.subTest(concept=concept.value, subtype=subtype):
                    self.assertTrue(subtype_allowed(concept, subtype))

    def test_vocabulary_has_a_single_source_of_truth(self):
        """어휘 목록을 모듈마다 따로 두지 않는다."""
        from geoflow import macros

        self.assertIs(macros.KNOWN_SUBTYPES, KNOWN_SUBTYPES)
        # registry가 만들 수 있는 출력은 전부 어휘 안에 있어야 한다.
        for concept, subtype in operator_mapping.measure_types():
            self.assertTrue(
                subtype_allowed(concept, subtype),
                f"{concept.value}/{subtype}",
            )

    def test_every_grounded_subtype_in_the_macro_library_is_known(self):
        for macro in self.library.all():
            for port in (*macro.input_ports.values(),
                         *macro.output_ports.values()):
                for concept, subtype in port.types:
                    with self.subTest(macro=macro.name, port=port.name):
                        self.assertTrue(subtype_allowed(concept, subtype))

    # -- 3. 값 없는 implicit 개념 --------------------------------------------

    def test_valueless_implicit_place_is_rejected_at_grounding(self):
        """장소가 없는 질문에 만들어진 빈 장소 개념을 조건으로 쓸 수 없다.

        예전에는 grounding을 통과한 뒤 implicit 개념의 값이 subtype 문자열
        ("place")로 채워져, compiler가 value["name"]을 꺼내려다 터졌다.
        """
        with self.assertRaises(PlannerError) as caught:
            parse_grounding(
                payload([
                    {"id": "loc", "concept": "LOCATION", "subtype": "place",
                     "role": "SUBCOND", "source": "implicit"},
                    event("e", "passage"),
                    measure("m", "AMOUNT", "passage_count"),
                ], {"dimension": "sigungu", "order": "top", "limit": 3}),
                "통행량이 가장 많은 시군구 3곳은?",
            )
        self.assertEqual(caught.exception.code, "VALUELESS_CONCEPT")

    def test_implicit_event_keeps_its_derived_value(self):
        """사건은 개념 이름이 곧 값이므로 값이 없어도 정상이다."""
        grounding = parse_grounding(
            payload([
                scope("s", "scope:edge:1742"),
                event("e", "passage"),
                measure("m", "AMOUNT", "speed"),
            ]),
            "scope:edge:1742상의 평균 속도는?",
        )
        plan = self.composer.compose(grounding)
        node = next(
            item for item in plan.concepts
            if item.concept == CoreConcept.EVENT
        )
        self.assertEqual(node.value, Subtype.PASSAGE)
        self.assert_valid(plan)

    def test_implicit_measure_may_have_no_value(self):
        """측정값은 실행이 채우므로 값이 없어야 정상이다."""
        grounding = parse_grounding(
            payload([
                scope("s", "scope:district:2700000000"),
                {"id": "p", "concept": "LOCATION", "subtype": "place",
                 "role": "MEASURE", "source": "implicit"},
            ]),
            "scope:district:2700000000은 어디인가요?",
        )
        plan = self.composer.compose(grounding)
        self.assertEqual(plan.applied_macros, ["SCOPE_TO_PLACE"])
        self.assert_valid(plan)

    def test_only_event_values_are_derived_from_the_subtype(self):
        """subtype 문자열로 값을 채우는 대상은 EVENT뿐이다."""
        from geoflow.composer import _seed_node
        from geoflow.grounding import GroundedConcept

        location = GroundedConcept(
            id="loc", concept=CoreConcept.LOCATION, subtype=Subtype.PLACE,
            role=FunctionalRole.SUBCOND, source=NodeSource.IMPLICIT,
        )
        passage = GroundedConcept(
            id="e", concept=CoreConcept.EVENT, subtype=Subtype.PASSAGE,
            role=FunctionalRole.SUPPORT, source=NodeSource.IMPLICIT,
        )
        self.assertIsNone(_seed_node(location).value)
        self.assertEqual(_seed_node(passage).value, Subtype.PASSAGE)

    def test_valueless_node_never_binds_to_an_input_port(self):
        """grounding을 우회해 만든 값 없는 node도 조건이 되지 않는다.

        grounding 검증과 별개로 composer가 한 번 더 막는다. compiler까지
        내려가 참조 오류로 터지는 경로를 구조적으로 없애기 위한 것이다.
        """
        from geoflow.composer import _bindable

        empty = ConceptNode(
            id="loc", concept=CoreConcept.LOCATION, subtype=Subtype.PLACE,
            role=FunctionalRole.SUBCOND, source=NodeSource.IMPLICIT,
        )
        filled = ConceptNode(
            id="p", concept=CoreConcept.LOCATION, subtype=Subtype.PLACE,
            role=FunctionalRole.SUBCOND, source=NodeSource.USER,
            value={"name": "대구", "region": ""},
        )
        produced = ConceptNode(
            id="s", concept=CoreConcept.LOCATION, subtype=Subtype.SCOPE,
            role=FunctionalRole.COND, source=NodeSource.TOOL,
        )
        self.assertFalse(_bindable(empty))
        self.assertTrue(_bindable(filled))
        self.assertTrue(_bindable(produced))

    def test_no_composed_plan_reaches_the_compiler_without_values(self):
        """검증을 통과한 계획의 모든 입력 node는 실행에 쓸 값을 갖는다."""
        for question, concepts, factors in ValidatorRegressionTest.CASES:
            with self.subTest(question=question):
                plan = self.compose(question, concepts, factors)
                produced = {
                    output
                    for item in plan.transformations
                    for output in item.outputs
                }
                for item in plan.transformations:
                    for port, ref in item.inputs.items():
                        node = plan.node(ref.node_id)
                        if node.id in produced:
                            continue
                        self.assertIsNotNone(
                            node.value, f"{item.id}.{port} → {node.id}",
                        )
                # compiler까지 실제로 내려가 본다.
                compile_plan(plan)


class LocationRelationInvariantTest(ComposerCase):
    """A. LOCATION qualification / arity 불변식.

    "출발", "도착" 같은 질문 문자열이 아니라 operator registry의 typed port
    계약에서만 유도한다. 승차/하차 범위만 받는 Tool에는 구분 없는 장소를
    넣을 자리가 없고, 그 사실은 port의 match_attributes에 이미 적혀 있다.
    """

    def _trip_count(self, places, question="실차 구간 건수는?"):
        return self.compose(
            question, [*places, event("e", "trip"),
                       measure("m", "AMOUNT", "trip_count")],
        )

    def test_pickup_qualified_location_is_valid(self):
        plan = self._trip_count([place("o", "동성로", od_role="pickup")])
        self.assertEqual(
            plan.applied_macros, ["PLACE_TO_SCOPE", "OD_EVENT_TO_MEASURE"],
        )
        self.assertIn("pickup", plan.transformations[-1].inputs)
        self.assertNotIn("dropoff", plan.transformations[-1].inputs)
        self.assert_valid(plan)

    def test_dropoff_qualified_location_is_valid(self):
        plan = self._trip_count([place("d", "신천동", od_role="dropoff")])
        self.assertIn("dropoff", plan.transformations[-1].inputs)
        self.assertNotIn("pickup", plan.transformations[-1].inputs)
        self.assert_valid(plan)

    def test_both_qualified_locations_are_valid(self):
        plan = self._trip_count([
            place("o", "동성로", od_role="pickup"),
            place("d", "신천동", od_role="dropoff"),
        ])
        count = plan.transformations[-1]
        self.assertEqual(count.inputs["pickup"].node_id, "o_scope")
        self.assertEqual(count.inputs["dropoff"].node_id, "d_scope")
        self.assert_valid(plan)

    def test_single_unqualified_location_reports_missing_relation(self):
        """b11 / b17. 구분 없는 장소 하나는 어느 port에도 들어갈 수 없다."""
        with self.assertRaises(CompositionError) as caught:
            self._trip_count([place("p", "동성로동")])
        error = caught.exception
        self.assertEqual(error.code, "MISSING_RELATION_QUALIFIER")
        self.assertEqual(error.context["unqualified"], ["p"])
        self.assertEqual(error.context["required_qualifiers"], ["od_role"])
        self.assertEqual(error.context["unqualified_capacity"], 0)
        self.assertEqual(
            sorted(error.context["candidate_ports"]), ["dropoff", "pickup"],
        )
        self.assertEqual(
            error.context["candidate_operators"], [Operator.TRIP_COUNT],
        )

    def test_two_unqualified_locations_report_ambiguous_relation(self):
        """q27. 구분이 없으면 어느 쪽이 출발인지 정할 수 없다."""
        with self.assertRaises(CompositionError) as caught:
            self._trip_count([place("a", "초읍동"), place("b", "초량동")])
        error = caught.exception
        self.assertEqual(error.code, "AMBIGUOUS_LOCATION_RELATION")
        self.assertEqual(sorted(error.context["unqualified"]), ["a", "b"])
        self.assertEqual(error.context["location_count"], 2)

    def test_area_operator_with_one_location_is_untouched(self):
        """일반 area operator는 새 불변식에 걸리지 않는다."""
        plan = self.compose(
            "대구 지역내 택시들의 평균 속도는?",
            [place("p", "대구"), event("e", "passage"),
             measure("m", "AMOUNT", "speed")],
        )
        self.assertEqual(
            plan.applied_macros, ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
        )
        self.assert_valid(plan)

    def test_area_operator_with_two_locations_is_ambiguous(self):
        """b20. 자리가 하나인데 장소가 둘이면 추측하지 않는다."""
        with self.assertRaises(CompositionError) as caught:
            self.compose(
                "대구와 부산 중 어디가 더 빠른가요?",
                [place("a", "대구"), place("b", "부산"),
                 event("e", "passage"), measure("m", "AMOUNT", "speed")],
            )
        self.assertEqual(
            caught.exception.code, "AMBIGUOUS_LOCATION_RELATION",
        )
        self.assertEqual(caught.exception.context["unqualified_capacity"], 1)

    def test_no_location_is_untouched(self):
        plan = self.compose(
            "평균 택시 요금은?",
            [event("e", "trip"), measure("m", "AMOUNT", "fare")],
            {"aggregation": "avg"},
        )
        self.assertEqual(plan.applied_macros, ["EVENT_TO_MEASURE"])
        self.assert_valid(plan)

    def test_scope_to_place_goal_is_untouched(self):
        """목표가 장소인 질문에서 목표 자신을 조건으로 세지 않는다."""
        plan = self.compose(
            "scope:district:2700000000은 어디인가요?",
            [scope("s", "scope:district:2700000000"),
             {"id": "p", "concept": "LOCATION", "subtype": "place",
              "role": "MEASURE", "source": "implicit"}],
        )
        self.assertEqual(plan.applied_macros, ["SCOPE_TO_PLACE"])
        self.assert_valid(plan)

    def test_qualifier_is_never_invented(self):
        """빠진 구분을 임의로 채우지 않는다. 반대로 답할 수 있기 때문이다."""
        with self.assertRaises(CompositionError):
            self._trip_count([place("p", "신천동")])
        # 실패했을 뿐 어떤 계획도 만들지 않았다.
        grounding = parse_grounding(
            payload([place("p", "신천동"), event("e", "trip"),
                     measure("m", "AMOUNT", "trip_count")]),
            "신천동에 도착한 실차 구간 건수는?",
        )
        self.assertIsNone(grounding.get("p").od_role)

    def test_invariant_is_derived_from_the_registry(self):
        """규칙이 특정 operator 이름이나 측정값에 하드코딩되지 않았다."""
        from geoflow.composer import _location_capacity, _location_contract

        self.assertEqual(
            _location_capacity(get_operator(Operator.TRIP_COUNT)), 0,
        )
        self.assertEqual(
            _location_capacity(get_operator(Operator.PASSAGE_METRIC)), 1,
        )
        # place_name/place_region은 같은 node를 보므로 한 자리로 센다.
        self.assertEqual(
            _location_capacity(get_operator(Operator.RESOLVE_PLACE_SCOPE)), 1,
        )
        capacity, requires, keys, ports = _location_contract(
            (get_operator(Operator.TRIP_COUNT),),
        )
        self.assertEqual((capacity, requires, keys), (0, True, ["od_role"]))
        self.assertEqual(sorted(ports), ["dropoff", "pickup"])

    def test_user_message_does_not_name_an_operator(self):
        """사용자에게 보여 줄 문구에 semantic operator 이름을 넣지 않는다."""
        for places in ([place("p", "동성로동")],
                       [place("a", "초읍동"), place("b", "초량동")]):
            with self.assertRaises(CompositionError) as caught:
                self._trip_count(places)
            message = caught.exception.user_message
            for name in operator_names():
                self.assertNotIn(name, message)


class FactorConstraintTest(ComposerCase):
    """B. factor 공기 불변식.

    특정 Tool이나 질문 유형이 아니라 조건 자체의 성질이므로 grounding 직후에
    확인한다. 어떤 operator가 그 조건을 소비할지 몰라도 판정할 수 있다.
    """

    def _ground(self, factors, question="택시 수입은?"):
        """조건 검증은 합성 진입점에서 일어나므로 전체 경로로 확인한다."""
        grounding = parse_grounding(
            payload([event("e", "operation"),
                     measure("m", "AMOUNT", "revenue")], factors),
            question,
        )
        self.composer.compose(grounding)
        return grounding

    def test_bucket_with_rollup_is_valid(self):
        grounding = self._ground(
            {"bucket": "week", "aggregation": "sum", "rollup": "avg"},
        )
        self.assertEqual(grounding.factors["bucket"], "week")
        plan = self.composer.compose(grounding)
        # 두 단계는 Tool 인자가 아니라 변환 둘로 표현된다.
        produce, combine = plan.transformations
        self.assertEqual(produce.params["aggregation"], "sum")
        self.assertNotIn("rollup", produce.params)
        self.assertEqual(combine.operator, "REDUCE_GROUPS")
        self.assertEqual(combine.params, {"reducer": "avg"})

    def test_bucket_without_inner_aggregation_is_rejected(self):
        """구간 안 집계가 질문에 없으면 Tool 기본값(avg)으로 채우지 않는다."""
        with self.assertRaises(CompositionError) as caught:
            self._ground({"bucket": "week", "rollup": "avg"})
        self.assertEqual(caught.exception.code, "AMBIGUOUS_INNER_AGGREGATION")

    def test_validation_runs_before_composition(self):
        """조각을 고르기 전에 걸린다. 계획이 만들어지지 않는다."""
        from geoflow.factors import validate_factors

        with self.assertRaises(PlannerError):
            validate_factors({"bucket": "week"})
        self.assertEqual(validate_factors({}), {})

    def test_bucket_alone_is_invalid(self):
        with self.assertRaises(PlannerError) as caught:
            self._ground({"bucket": "week"})
        error = caught.exception
        self.assertEqual(error.code, "INVALID_FACTOR_COMBINATION")
        self.assertEqual(error.context["factor"], "bucket")
        self.assertEqual(error.context["missing"], ["rollup"])

    def test_rollup_alone_is_invalid(self):
        with self.assertRaises(PlannerError) as caught:
            self._ground({"rollup": "avg"})
        self.assertEqual(caught.exception.context["missing"], ["bucket"])

    def test_order_with_dimension_is_valid(self):
        grounding = self._ground({"order": "top", "dimension": "sido"})
        self.assertEqual(grounding.factors["order"], "top")

    def test_order_alone_is_invalid(self):
        with self.assertRaises(PlannerError) as caught:
            self._ground({"order": "top"})
        self.assertEqual(caught.exception.context["missing"], ["dimension"])

    def test_limit_with_dimension_is_valid(self):
        grounding = self._ground({"limit": 3, "dimension": "sido"})
        self.assertEqual(grounding.factors["limit"], 3)

    def test_limit_alone_is_invalid(self):
        with self.assertRaises(PlannerError) as caught:
            self._ground({"limit": 3})
        self.assertEqual(caught.exception.context["missing"], ["dimension"])

    def test_unrelated_factors_are_untouched(self):
        grounding = self._ground({
            "date": "20260530", "taxi_type": "private", "aggregation": "avg",
        })
        self.assertEqual(sorted(grounding.factors), [
            "aggregation", "date", "taxi_type",
        ])

    def test_dimension_alone_is_valid(self):
        """그룹화만 있는 것은 정상이다. 순위가 그룹화를 요구할 뿐이다."""
        grounding = self._ground({"dimension": "dayofweek"})
        self.assertEqual(grounding.factors["dimension"], "dayofweek")

    def test_constraints_have_a_single_source_of_truth(self):
        """operator마다 같은 규칙을 다시 적어 두지 않는다."""
        import inspect

        from geoflow import factors, operator_registry

        source = inspect.getsource(operator_registry)
        self.assertNotIn("param_requires", source)
        # operator는 factor 표를 자기가 받는 parameter로 걸러 쓴다.
        self.assertEqual(factors.companions_for("bucket"), ("rollup",))
        self.assertEqual(
            get_operator(Operator.OPERATION_METRIC).missing_companions(
                "bucket", {},
            ),
            ("rollup",),
        )

    def test_factor_value_range_stays_on_the_operator(self):
        """값의 범위는 Tool마다 다르므로 registry가 갖는다."""
        self.assertEqual(
            sorted(get_operator(Operator.OPERATION_METRIC)
                   .allowed_values("dimension")),
            ["dayofweek", "emd", "h3", "sido", "sigungu"],
        )
        self.assertEqual(
            sorted(get_operator(Operator.PASSAGE_COUNT)
                   .allowed_values("dimension")),
            ["emd", "h3", "sido", "sigungu"],
        )

    def test_g4_still_checks_the_same_contract(self):
        """마지막 방어선인 G4를 제거하지 않았다."""
        import inspect

        from geoflow import validator

        source = inspect.getsource(validator._check_param_contract)
        self.assertIn("missing_companions", source)
        self.assertIn("allowed_values", source)


class FactorSemanticsTest(ComposerCase):
    """A·B·E. 집계 단계 조건의 의미가 한 곳에서 정의되고 Prompt로 흐른다."""

    GROUPED = ("bucket", "aggregation", "rollup")

    def test_every_grouped_factor_has_a_meaning(self):
        from geoflow.factors import FACTOR_SPECS

        for name in self.GROUPED:
            with self.subTest(factor=name):
                self.assertTrue(FACTOR_SPECS[name].meaning, name)

    def test_grouped_factor_meanings_are_distinct(self):
        from geoflow.factors import FACTOR_SPECS

        meanings = {FACTOR_SPECS[name].meaning for name in self.GROUPED}
        self.assertEqual(len(meanings), len(self.GROUPED))

    def test_rollup_allowed_values_match_aggregation(self):
        """2차 집계도 집계 방식이므로 같은 값 집합을 쓴다."""
        from geoflow.factors import FACTOR_SPECS

        self.assertEqual(
            FACTOR_SPECS["rollup"].values, FACTOR_SPECS["aggregation"].values,
        )
        self.assertNotIn("week", FACTOR_SPECS["rollup"].values)
        self.assertNotIn("month", FACTOR_SPECS["rollup"].values)

    def test_bucket_values_are_time_units(self):
        from geoflow.factors import FACTOR_SPECS

        self.assertEqual(
            FACTOR_SPECS["bucket"].values, frozenset({"week", "month"}),
        )

    def test_grounding_prompt_carries_the_semantics(self):
        from geoflow.factors import (
            FACTOR_STAGE_NOTE,
            describe_factor_semantics,
        )
        from geoflow.planner import GeoFlowPlanner

        class Client:
            model = "x"

        prompt = GeoFlowPlanner(client=Client()).system_prompt()
        self.assertIn(describe_factor_semantics(), prompt)
        self.assertIn(FACTOR_STAGE_NOTE, prompt)

    def test_repair_prompt_carries_the_same_semantics(self):
        """grounding과 재질의 설명이 어긋날 수 없다."""
        from geoflow.factors import describe_factor_semantics
        from geoflow.planner import (
            GeoFlowPlanner,
            _fill_instruction,
            _instruction_values,
        )
        from geoflow.repair import RepairDecision, RepairKind

        class Client:
            model = "x"

        decision = RepairDecision(
            repairable=True, kind=RepairKind.FACTOR_COMPLETION,
            reason="테스트", targets=("bucket",), allowed_additions=("rollup",),
        )
        planner = GeoFlowPlanner(client=Client())
        instruction = _fill_instruction(
            planner.repair_instructions[decision.kind],
            _instruction_values(decision, "테스트"),
        )
        self.assertIn(describe_factor_semantics(("rollup",)), instruction)

    def test_prompt_does_not_hardcode_the_vocabulary(self):
        """어휘 목록을 Prompt YAML에 손으로 적어 두지 않는다."""
        from geoflow.planner import DEFAULT_PLANNER_PROMPT

        body = Path(DEFAULT_PLANNER_PROMPT).read_text(encoding="utf-8")
        # 집계 방식 enum을 나열한 줄이 없어야 한다.
        self.assertNotIn("avg | max | med | min | sum", body)
        self.assertNotIn("week, month", body)

    def test_bucket_rollup_constraint_is_unchanged(self):
        from geoflow.factors import companions_for

        self.assertEqual(companions_for("bucket"), ("rollup",))
        self.assertEqual(companions_for("rollup"), ("bucket",))
        self.assertEqual(companions_for("order"), ("dimension",))
        self.assertEqual(companions_for("limit"), ("dimension",))

    def test_rollup_rejects_a_time_unit(self):
        """b21 형태. 시간 단위는 2차 집계 방식이 아니다."""
        for value in ("week", "month"):
            with self.subTest(value=value):
                with self.assertRaises(PlannerError) as caught:
                    parse_grounding(
                        payload([event("e", "operation"),
                                 measure("m", "AMOUNT", "revenue")],
                                {"bucket": "week", "rollup": value}),
                        "주 단위로 집계한 택시 수입의 평균은?",
                    )
                self.assertEqual(caught.exception.code, "INVALID_FACTOR")
                self.assertIn("rollup", caught.exception.detail)

    def test_rollup_accepts_an_aggregation(self):
        for value in ("avg", "max", "sum", "min", "med"):
            with self.subTest(value=value):
                plan = self.compose(
                    "주 단위로 나눈 택시 수입은?",
                    [event("e", "operation"),
                     measure("m", "AMOUNT", "revenue")],
                    {"bucket": "week", "aggregation": "sum", "rollup": value},
                )
                self.assertEqual(
                    plan.transformations[-1].params["reducer"], value,
                )

    def test_invalid_factor_is_still_not_repairable(self):
        """값 오류는 아직 재질의 대상이 아니다."""
        from geoflow.errors import PlannerError as PE
        from geoflow.repair import decide

        error = PE("테스트", code="INVALID_FACTOR", context={})
        self.assertFalse(decide(error).repairable)

    def test_correct_two_stage_factors_compose(self):
        """구간 안 집계까지 적은 두 단계 조건이 구간별 node로 합성된다."""
        for factors, expected in (
            ({"bucket": "week", "aggregation": "sum", "rollup": "avg"},
             ("week", "sum", "avg")),
            ({"bucket": "month", "aggregation": "avg", "rollup": "max",
              "taxi_type": "private"}, ("month", "avg", "max")),
        ):
            with self.subTest(factors=factors):
                plan = self.compose(
                    "구간을 나눈 수입은?",
                    [event("e", "operation"),
                     measure("m", "AMOUNT", "revenue")],
                    factors,
                )
                groups = next(
                    node for node in plan.concepts if node.attributes.get("group_by")
                )
                produce, combine = plan.transformations
                self.assertEqual(
                    (groups.attributes["group_by"]["bucket"],
                     produce.params["aggregation"], combine.params["reducer"]),
                    expected,
                )
                self.assert_valid(plan)

    def test_b21_b24_structure_without_inner_is_now_rejected(self):
        """b21/b24 golden(구간 안 집계 없음)은 예전에는 Tool 기본값으로 실행됐다."""
        for factors in (
            {"bucket": "week", "rollup": "avg"},
            {"bucket": "month", "rollup": "max", "taxi_type": "private"},
        ):
            with self.subTest(factors=factors):
                with self.assertRaises(CompositionError) as caught:
                    self.compose(
                        "구간을 나눈 수입은?",
                        [event("e", "operation"),
                         measure("m", "AMOUNT", "revenue")],
                        factors,
                    )
                self.assertEqual(caught.exception.code,
                                 "AMBIGUOUS_INNER_AGGREGATION")


class LegacyIsolationTest(unittest.TestCase):
    """예전 question-type template이 실행 경로로 돌아오지 않게 한다."""

    #: 실행 경로에 있는 모듈. 이들 중 어느 것도 legacy template을 쓰지 않는다.
    RUNTIME_MODULES = (
        "pipeline.py", "planner.py", "grounding.py", "composer.py",
        "macros.py", "operator_mapping.py", "operator_registry.py",
        "validator.py", "compiler.py", "executor.py", "answer.py",
        "labeling.py", "types.py",
    )

    def test_runtime_modules_do_not_import_legacy_templates(self):
        for name in self.RUNTIME_MODULES:
            with self.subTest(module=name):
                body = (BASE_DIR / "geoflow" / name).read_text(
                    encoding="utf-8",
                )
                self.assertNotIn("geoflow.templates", body)
                self.assertNotIn("TemplateRegistry", body)

    def test_pipeline_is_built_from_a_macro_library(self):
        import inspect

        from geoflow.pipeline import GeoFlowPipeline

        source = inspect.getsource(GeoFlowPipeline.create)
        self.assertIn("MacroLibrary", source)
        self.assertIn("MacroComposer", source)

    def test_planner_no_longer_receives_a_template_registry(self):
        import inspect

        from geoflow.planner import GeoFlowPlanner

        parameters = inspect.signature(GeoFlowPlanner.__init__).parameters
        self.assertNotIn("templates", parameters)

    def test_legacy_templates_still_load_for_comparison(self):
        """migration 근거 자료로 남겨 둔 정의가 깨지지 않았는지만 본다."""
        from geoflow.templates import TemplateRegistry

        registry = TemplateRegistry.from_directory()
        self.assertEqual(len(registry), 12)

    def test_every_legacy_template_maps_onto_the_macro_library(self):
        """예전 template이 모두 새 조각 조합으로 표현되는지 확인한다."""
        expected = {
            "DIRECT_SCOPE_METRIC": ["EVENT_TO_MEASURE"],
            "DIRECT_SCOPE_PASSAGE_COUNT": ["EVENT_TO_MEASURE"],
            "PLACE_SCOPE_METRIC": ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
            "VICINITY_SCOPE_METRIC": ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
            "PLACE_PASSAGE_COUNT": ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
            "VICINITY_PASSAGE_COUNT": ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
            "TRIP_FARE_METRIC": ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
            "DRIVE_RATIO_METRIC": ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
            "OPERATION_METRIC": ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
            "GROUPED_AGGREGATE": ["EVENT_TO_MEASURE"],
            "OD_TRIP_COUNT": ["PLACE_TO_SCOPE", "OD_EVENT_TO_MEASURE"],
            "SCOPE_PLACE_NAME": ["SCOPE_TO_PLACE"],
        }
        from geoflow.templates import TemplateRegistry

        registry = TemplateRegistry.from_directory()
        self.assertEqual(sorted(expected), sorted(registry.names))
        library = MacroLibrary.from_directory()
        for macros in expected.values():
            for name in macros:
                self.assertIn(name, library)


if __name__ == "__main__":
    unittest.main()
