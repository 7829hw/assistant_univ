# -*- coding: utf-8 -*-
"""GeoFlow v1 테스트.

새 dependency를 추가하지 않기 위해 표준 라이브러리 ``unittest``만 사용한다.

실행:
    python -m unittest discover -s tests -t .
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assistant_runtime import (  # noqa: E402
    AGENT_MODE_GEOFLOW,
    AGENT_MODE_REACT,
    AssistantRuntime,
)
from build import build  # noqa: E402
from evaluate_planner import (  # noqa: E402
    NO_TEMPLATE_LABEL,
    check_concept_roles,
    score_concepts,
    score_sequence,
)
from query_loader import load_queries  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402
from mock_responses import mock_get_place_scope  # noqa: E402
from ollama_client import OllamaClient, chat_options, resolve_think  # noqa: E402
from tool_handlers import get_tool_handlers  # noqa: E402

from geoflow.answer import format_answer  # noqa: E402
from geoflow.compiler import compile_plan, topological_order  # noqa: E402
from geoflow.errors import (  # noqa: E402
    ExecutionError,
    PlannerError,
    TemplateError,
    ValidationError,
)
from geoflow.executor import (  # noqa: E402
    STATUS_EXECUTOR_ERROR,
    STATUS_OK,
    STATUS_TOOL_ERROR,
    execute_plan,
    resolve_refs,
)
from geoflow.grounding import parse_grounding  # noqa: E402
from geoflow.macros import MacroLibrary  # noqa: E402
from geoflow.operator_registry import Operator, operator_names  # noqa: E402
from geoflow.pipeline import (  # noqa: E402
    STATUS_REPAIR_FAILED,
    STATUS_REPAIR_SKIPPED,
    GeoFlowPipeline,
    Stage,
)
from geoflow.planner import (  # noqa: E402
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_PLANNER_PROMPT,
    GeoFlowPlanner,
    drop_invented_regions,
)
from geoflow.templates import TemplateRegistry  # noqa: E402
from geoflow.types import (  # noqa: E402
    ConceptNode,
    CoreConcept,
    FunctionalRole,
    GeoFlowPlan,
    NodeSource,
    Subtype,
    Transformation,
    ValueRef,
)
from geoflow.validator import Rule, validate  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
TOOLS, SYSTEM_PROMPT = build()

OD_QUESTION = "대구 동성로동에서 출발하여 신천동에 도착한 실차 구간 건수는?"
VICINITY_QUESTION = (
    "2026년 5월 30일 오후 12시에서 1시사이에 동대구역 근처 차량의 평균 운행 속도는?"
)
PLACE_QUESTION = "대구 지역내 택시들의 평균 속도는?"
DIRECT_QUESTION = (
    "2026년 5월 30일 오후 12시에서 1시사이에 "
    "scope:edge:1742상의 택시들의 평균 속도는?"
)

OD_SLOTS = {
    "origin": {"name": "동성로", "region": "대구"},
    "destination": {"name": "신천동", "region": ""},
}


# -- grounding 계약 fixture --------------------------------------------------
# Planner는 template 이름이 아니라 개념을 돌려준다. 아래 helper는 그 계약을
# 테스트에서 읽기 쉽게 만들기 위한 것이다.

def grounding_payload(concepts, factors=None):
    return {"concepts": list(concepts), "factors": dict(factors or {})}


def place_concept(node_id, name, region="", *, od_role=None, role="SUBCOND"):
    concept = {
        "id": node_id,
        "concept": "LOCATION",
        "subtype": "place",
        "role": role,
        "source": "user",
        "value": {"name": name, "region": region},
    }
    if od_role is not None:
        concept["attributes"] = {"od_role": od_role}
    return concept


def scope_concept(node_id, value, subtype="scope"):
    return {
        "id": node_id,
        "concept": "LOCATION",
        "subtype": subtype,
        "role": "COND",
        "source": "user",
        "value": value,
    }


def event_concept(node_id, subtype):
    return {
        "id": node_id,
        "concept": "EVENT",
        "subtype": subtype,
        "role": "SUPPORT",
        "source": "implicit",
    }


def measure_concept(node_id, concept, subtype):
    return {
        "id": node_id,
        "concept": concept,
        "subtype": subtype,
        "role": "MEASURE",
        "source": "implicit",
    }


def od_grounding(origin="동성로", destination="신천동"):
    return grounding_payload([
        place_concept("origin", origin, "대구", od_role="pickup"),
        place_concept("destination", destination, od_role="dropoff"),
        event_concept("trip", "trip"),
        measure_concept("trip_count", "AMOUNT", "trip_count"),
    ])


def fare_grounding(name, region=""):
    return grounding_payload([
        place_concept("place_1", name, region),
        event_concept("trip", "trip"),
        measure_concept("fare", "AMOUNT", "fare"),
    ], {"aggregation": "avg"})


OD_GROUNDING = od_grounding()


def place_patch(concept_id, name, region=""):
    """장소 값 수정안. 재질의는 고친 grounding 전체가 아니라 수정안만 낸다."""
    return {"concept_id": concept_id, "name": name, "region": region}


def new_tool_executor():
    return ToolExecutor(tools=TOOLS, handlers=get_tool_handlers())


class ScriptedClient:
    """Ollama 응답을 미리 정해두는 테스트용 client."""

    model = "scripted-test-model"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, tools=None):
        self.calls.append({"messages": messages, "tools": tools})
        if not self.responses:
            raise AssertionError("준비된 응답보다 많은 chat 호출이 발생했습니다.")
        response = self.responses.pop(0)
        # 각본에 예외를 넣으면 무응답·연결 실패를 그대로 재현할 수 있다.
        if isinstance(response, Exception):
            raise response
        return response


def planner_response(payload):
    return {"message": {"content": json.dumps(payload, ensure_ascii=False)}}


def analysis_tools(hop_log):
    """표시용 scope 라벨링 호출을 제외한 분석 단계 Tool만 추린다."""
    return [
        entry["tool"] for entry in hop_log
        if entry.get("phase") != "labeling"
    ]


def labeling_tools(hop_log):
    return [
        entry["tool"] for entry in hop_log
        if entry.get("phase") == "labeling"
    ]


def new_pipeline(planner_payloads):
    client = ScriptedClient([
        planner_response(payload) for payload in planner_payloads
    ])
    pipeline = GeoFlowPipeline.create(
        client=client,
        tool_executor=new_tool_executor(),
    )
    return pipeline, client


class TemplateLoadingTest(unittest.TestCase):
    """template loading / slot 계약."""

    def setUp(self):
        self.registry = TemplateRegistry.from_directory()

    def test_all_v1_templates_are_loaded(self):
        self.assertEqual(
            set(self.registry.names),
            {
                "DIRECT_SCOPE_METRIC",
                "PLACE_SCOPE_METRIC",
                "VICINITY_SCOPE_METRIC",
                "OD_TRIP_COUNT",
                "GROUPED_AGGREGATE",
                "OPERATION_METRIC",
                "SCOPE_PLACE_NAME",
                "DIRECT_SCOPE_PASSAGE_COUNT",
                "PLACE_PASSAGE_COUNT",
                "VICINITY_PASSAGE_COUNT",
                "TRIP_FARE_METRIC",
                "DRIVE_RATIO_METRIC",
            },
        )

    def test_every_template_instantiates_and_validates(self):
        """모든 template이 required slot만으로 검증을 통과해야 한다."""
        samples = {
            "place": {"name": "대구", "region": ""},
            "origin": {"name": "동성로", "region": "대구"},
            "destination": {"name": "신천동", "region": ""},
            "scope": "scope:edge:1742",
            "metric": None,
            "dimension": "dayofweek",
        }
        tool_names = new_tool_executor().tool_names
        for template in self.registry.all():
            with self.subTest(template=template.name):
                slots = {}
                for name in template.required_slots:
                    spec = template.slots[name]
                    slots[name] = (
                        spec.enum_values[0] if spec.enum_values
                        else samples[name]
                    )
                plan = template.instantiate(DIRECT_QUESTION, slots)
                report = validate(plan, available_tools=tool_names)
                self.assertTrue(report.ok, report.errors)

    def test_unknown_template_is_rejected(self):
        with self.assertRaises(TemplateError) as caught:
            self.registry.require("NOT_A_TEMPLATE")
        self.assertIn("알 수 없는 template", caught.exception.detail)

    def test_required_slot_is_enforced(self):
        template = self.registry.require("OD_TRIP_COUNT")
        with self.assertRaises(TemplateError) as caught:
            template.instantiate(
                OD_QUESTION, {"destination": {"name": "신천동"}},
            )
        self.assertIn("필수 slot이 없습니다: origin", caught.exception.detail)

    def test_od_without_destination_drops_dropoff(self):
        """도착지가 없는 질문은 승차 위치만으로 집계한다.

        destination을 필수로 두면 Planner가 가짜 장소를 지어내 채우려 한다.
        """
        template = self.registry.require("OD_TRIP_COUNT")
        plan = template.instantiate(
            "동성로동에서 출발한 실차 구간 건수는?",
            {"origin": {"name": "동성로", "region": "대구"}},
        )
        report = validate(
            plan, available_tools=new_tool_executor().tool_names,
        )
        self.assertTrue(report.ok, report.errors)
        steps = compile_plan(plan).steps
        self.assertEqual(
            [step.tool_name for step in steps],
            ["get_place_scope", "get_trip_count"],
        )
        self.assertIn("scope_pickup", steps[-1].arguments)
        self.assertNotIn("scope_dropoff", steps[-1].arguments)
        self.assertNotIn("destination_scope", plan.node_ids)

    def test_blank_place_name_is_rejected(self):
        """Planner가 필수 slot을 공백으로 채우는 경우를 막는다."""
        template = self.registry.require("OD_TRIP_COUNT")
        for blank in ("", " ", "\t"):
            with self.subTest(value=blank):
                with self.assertRaises(TemplateError):
                    template.instantiate(
                        OD_QUESTION, {"origin": {"name": blank}},
                    )

    def test_unknown_slot_is_rejected(self):
        template = self.registry.require("OD_TRIP_COUNT")
        with self.assertRaises(TemplateError) as caught:
            template.instantiate(
                OD_QUESTION, {**OD_SLOTS, "scope": "scope:district:1"},
            )
        self.assertIn("허용되지 않은 slot", caught.exception.detail)

    def test_enum_slot_value_is_validated(self):
        """PLACE_SCOPE_METRIC은 passage metric만 받는다. fare는 trip 개념이다."""
        template = self.registry.require("PLACE_SCOPE_METRIC")
        with self.assertRaises(TemplateError) as caught:
            template.instantiate(
                PLACE_QUESTION,
                {"place": {"name": "대구", "region": ""}, "metric": "fare"},
            )
        self.assertIn("허용되지 않은 값", caught.exception.detail)

    def test_place_slot_requires_name(self):
        template = self.registry.require("PLACE_SCOPE_METRIC")
        with self.assertRaises(TemplateError):
            template.instantiate(
                PLACE_QUESTION,
                {"place": {"region": "대구"}, "metric": "speed"},
            )

    def test_missing_scope_prefix_is_restored_from_question(self):
        """Planner가 "scope:" 접두어를 빠뜨려도 발화에 있는 값이면 복원한다."""
        template = self.registry.require("DIRECT_SCOPE_METRIC")
        plan = template.instantiate(
            DIRECT_QUESTION, {"scope": "edge:1742", "metric": "speed"},
        )
        self.assertEqual(plan.slots["scope"], "scope:edge:1742")
        self.assertTrue(
            validate(plan, available_tools=new_tool_executor().tool_names).ok
        )

    def test_scope_prefix_restore_requires_exact_token(self):
        """발화 scope의 앞부분만 일치하는 값은 복원하지 않는다."""
        template = self.registry.require("DIRECT_SCOPE_METRIC")
        with self.assertRaises(TemplateError):
            template.instantiate(
                DIRECT_QUESTION, {"scope": "edge:17", "metric": "speed"},
            )

    def test_scope_prefix_restore_rejects_invented_value(self):
        template = self.registry.require("DIRECT_SCOPE_METRIC")
        with self.assertRaises(TemplateError):
            template.instantiate(
                DIRECT_QUESTION,
                {"scope": "district:999999999", "metric": "speed"},
            )

    def test_optional_slot_is_omitted_when_absent(self):
        template = self.registry.require("OD_TRIP_COUNT")
        plan = template.instantiate(OD_QUESTION, OD_SLOTS)
        count_trips = plan.transformations[-1]
        self.assertNotIn("date", count_trips.params)
        self.assertNotIn("time", count_trips.params)


class CompilerTest(unittest.TestCase):
    """compiler의 고정 binding과 실행 순서."""

    def setUp(self):
        self.registry = TemplateRegistry.from_directory()

    def _od_plan(self, slots=None):
        return self.registry.require("OD_TRIP_COUNT").instantiate(
            OD_QUESTION, slots or OD_SLOTS,
        )

    def test_od_binds_origin_to_pickup_and_destination_to_dropoff(self):
        execution_plan = compile_plan(self._od_plan())
        trip_step = execution_plan.steps[-1]
        self.assertEqual(trip_step.tool_name, "get_trip_count")
        self.assertEqual(
            trip_step.arguments["scope_pickup"], ValueRef("origin_scope"),
        )
        self.assertEqual(
            trip_step.arguments["scope_dropoff"],
            ValueRef("destination_scope"),
        )

    def test_execution_order_is_deterministic(self):
        orders = [
            [step.id for step in compile_plan(self._od_plan()).steps]
            for _ in range(5)
        ]
        self.assertEqual(
            orders,
            [["resolve_origin", "resolve_destination", "count_trips"]] * 5,
        )

    def test_direct_scope_template_does_not_resolve_place(self):
        plan = self.registry.require("DIRECT_SCOPE_METRIC").instantiate(
            DIRECT_QUESTION,
            {
                "scope": "scope:edge:1742",
                "metric": "speed",
                "aggregation": "avg",
            },
        )
        execution_plan = compile_plan(plan)
        tool_names = [step.tool_name for step in execution_plan.steps]
        self.assertEqual(tool_names, ["get_passage_metrics"])
        self.assertEqual(
            execution_plan.steps[0].arguments["scope"], "scope:edge:1742",
        )

    def test_vicinity_template_sets_include_vicinity(self):
        plan = self.registry.require("VICINITY_SCOPE_METRIC").instantiate(
            VICINITY_QUESTION,
            {
                "place": {"name": "동대구역", "region": ""},
                "metric": "speed",
                "aggregation": "avg",
                "date": "20260530",
                "time": "120000-130000",
            },
        )
        execution_plan = compile_plan(plan)
        self.assertIs(
            execution_plan.steps[0].arguments["include_vicinity"], True,
        )


class OptionalConceptTest(unittest.TestCase):
    """질문에 없는 optional 조건은 node와 Tool 호출에서 함께 사라진다."""

    def setUp(self):
        self.registry = TemplateRegistry.from_directory()
        self.tool_executor = new_tool_executor()

    def _steps(self, template_name, question, slots):
        plan = self.registry.require(template_name).instantiate(
            question, slots,
        )
        report = validate(
            plan, available_tools=self.tool_executor.tool_names,
        )
        self.assertTrue(report.ok, report.errors)
        return plan, compile_plan(plan).steps

    def test_absent_place_drops_resolve_step(self):
        plan, steps = self._steps(
            "TRIP_FARE_METRIC", "평균 택시 요금은?", {},
        )
        self.assertEqual([step.tool_name for step in steps],
                         ["get_trip_metrics"])
        self.assertNotIn("scope", steps[0].arguments)
        self.assertEqual(plan.node_ids, ["measure"])

    def test_present_place_keeps_resolve_step(self):
        plan, steps = self._steps(
            "TRIP_FARE_METRIC",
            "대구시의 평균 택시 요금은?",
            {"place": {"name": "대구", "region": ""}},
        )
        self.assertEqual(
            [step.tool_name for step in steps],
            ["get_place_scope", "get_trip_metrics"],
        )
        self.assertEqual(steps[1].arguments["scope"], ValueRef("place_scope"))
        self.assertIn("place_scope", plan.node_ids)

    def test_drive_ratio_without_place(self):
        _plan, steps = self._steps(
            "DRIVE_RATIO_METRIC",
            "공차로 운행되는 택시 비율은?",
            {},
        )
        self.assertEqual([step.tool_name for step in steps],
                         ["get_drive_metrics"])
        self.assertEqual(steps[0].arguments["metric"], "vacant_ratio")

    def test_passage_count_dimension_and_ranking(self):
        """dimension/order/limit은 있을 때만 전달하고 답변에 드러낸다."""
        template = self.registry.require("PLACE_PASSAGE_COUNT")
        plain = template.instantiate(
            "대구 지역 전체 통행량은?",
            {"place": {"name": "대구", "region": ""}},
        )
        plain_step = compile_plan(plain).steps[-1]
        for name in ("dimension", "order", "limit"):
            self.assertNotIn(name, plain_step.arguments)

        ranked = template.instantiate(
            "대구에서 통행량이 가장 많은 시군구 3곳은?",
            {
                "place": {"name": "대구", "region": ""},
                "dimension": "sigungu",
                "order": "top",
                "limit": 3,
            },
        )
        report = validate(
            ranked, available_tools=self.tool_executor.tool_names,
        )
        self.assertTrue(report.ok, report.errors)
        ranked_step = compile_plan(ranked).steps[-1]
        self.assertEqual(ranked_step.arguments["dimension"], "sigungu")
        self.assertEqual(ranked_step.arguments["order"], "top")
        self.assertEqual(ranked_step.arguments["limit"], 3)

        result = execute_plan(compile_plan(ranked), self.tool_executor)
        self.assertEqual(result.status, STATUS_OK, result.error)
        self.assertEqual(len(result.final_value), 3)
        answer = format_answer(ranked, result, answer=template.answer)
        self.assertIn("시군구별", answer)
        self.assertIn("상위", answer)
        self.assertIn("3개", answer)

    def test_optional_drop_still_executes(self):
        _plan, steps = self._steps(
            "DRIVE_RATIO_METRIC",
            "공차로 운행되는 택시 비율은?",
            {},
        )
        plan = self.registry.require("DRIVE_RATIO_METRIC").instantiate(
            "공차로 운행되는 택시 비율은?", {},
        )
        result = execute_plan(compile_plan(plan), self.tool_executor)
        self.assertEqual(result.status, STATUS_OK, result.error)
        self.assertIsNotNone(result.final_value)


def _synthetic_plan(concepts, transformations, final_node, question=""):
    return GeoFlowPlan(
        version="1.0",
        question=question,
        template="SYNTHETIC",
        concepts=concepts,
        transformations=transformations,
        final_node=final_node,
    )


def _scope_node(node_id, source, value=None, subtype=Subtype.SCOPE):
    return ConceptNode(
        id=node_id,
        concept=CoreConcept.LOCATION,
        subtype=subtype,
        role=FunctionalRole.COND,
        source=source,
        value=value,
    )


def _measure_node(node_id):
    return ConceptNode(
        id=node_id,
        concept=CoreConcept.AMOUNT,
        subtype=Subtype.SPEED,
        role=FunctionalRole.MEASURE,
        source=NodeSource.TOOL,
    )


class ValidatorTest(unittest.TestCase):
    """G1~G6 정적 검증."""

    def setUp(self):
        self.registry = TemplateRegistry.from_directory()
        self.tool_names = new_tool_executor().tool_names

    def test_valid_plan_passes_all_rules(self):
        plan = self.registry.require("OD_TRIP_COUNT").instantiate(
            OD_QUESTION, OD_SLOTS,
        )
        report = validate(plan, available_tools=self.tool_names)
        self.assertTrue(report.ok, report.errors)

    def test_cycle_is_detected(self):
        plan = _synthetic_plan(
            concepts=[
                _scope_node("a", NodeSource.TOOL),
                _scope_node("b", NodeSource.TOOL),
            ],
            transformations=[
                Transformation(
                    id="t1",
                    operator=Operator.RESOLVE_PLACE_SCOPE,
                    inputs={"place_name": ValueRef("b", "name")},
                    outputs=["a"],
                ),
                Transformation(
                    id="t2",
                    operator=Operator.RESOLVE_PLACE_SCOPE,
                    inputs={"place_name": ValueRef("a", "name")},
                    outputs=["b"],
                ),
            ],
            final_node="a",
        )
        report = validate(plan, available_tools=self.tool_names)
        self.assertIn(Rule.ACYCLICITY, report.failed_rules())
        _order, cycle = topological_order(plan)
        self.assertEqual(sorted(cycle), ["t1", "t2"])

    def test_unknown_operator_is_rejected(self):
        plan = _synthetic_plan(
            concepts=[_measure_node("measure")],
            transformations=[
                Transformation(
                    id="t1", operator="MAKE_UP_AN_ANSWER", outputs=["measure"],
                ),
            ],
            final_node="measure",
        )
        report = validate(plan, available_tools=self.tool_names)
        self.assertIn(Rule.EXECUTABILITY, report.failed_rules())

    def test_unavailable_tool_is_rejected(self):
        plan = self.registry.require("OD_TRIP_COUNT").instantiate(
            OD_QUESTION, OD_SLOTS,
        )
        report = validate(plan, available_tools=("get_place_scope",))
        self.assertIn(Rule.EXECUTABILITY, report.failed_rules())

    def test_type_mismatch_is_rejected(self):
        """AMOUNT node를 scope 입력으로 넘기면 G3가 잡는다."""
        plan = _synthetic_plan(
            concepts=[
                ConceptNode(
                    id="amount",
                    concept=CoreConcept.AMOUNT,
                    subtype=Subtype.TRIP_COUNT,
                    role=FunctionalRole.SUBCOND,
                    source=NodeSource.USER,
                    value=3,
                ),
                _measure_node("measure"),
            ],
            transformations=[
                Transformation(
                    id="t1",
                    operator=Operator.PASSAGE_METRIC,
                    inputs={"area": ValueRef("amount")},
                    outputs=["measure"],
                ),
            ],
            final_node="measure",
        )
        report = validate(plan, available_tools=self.tool_names)
        self.assertIn(Rule.TYPE_COMPATIBILITY, report.failed_rules())

    def test_isolated_concept_is_rejected(self):
        plan = self.registry.require("OD_TRIP_COUNT").instantiate(
            OD_QUESTION, OD_SLOTS,
        )
        plan.concepts.append(
            _scope_node("orphan", NodeSource.USER, "scope:edge:1742"),
        )
        report = validate(
            plan,
            available_tools=self.tool_names,
            user_scopes={"scope:edge:1742"},
        )
        self.assertIn(Rule.CONNECTIVITY, report.failed_rules())

    def test_hallucinated_user_scope_is_rejected(self):
        """Case 5: 발화에 없는 scope는 실행 전에 차단된다."""
        plan = self.registry.require("DIRECT_SCOPE_METRIC").instantiate(
            DIRECT_QUESTION,
            {"scope": "scope:district:999999999", "metric": "speed"},
        )
        report = validate(plan, available_tools=self.tool_names)
        self.assertIn(Rule.SCOPE_PROVENANCE, report.failed_rules())
        with self.assertRaises(ValidationError):
            report.raise_if_failed()

    def test_user_provided_scope_is_accepted(self):
        plan = self.registry.require("DIRECT_SCOPE_METRIC").instantiate(
            DIRECT_QUESTION,
            {"scope": "scope:edge:1742", "metric": "speed"},
        )
        report = validate(plan, available_tools=self.tool_names)
        self.assertTrue(report.ok, report.errors)

    def test_template_generated_scope_is_rejected(self):
        """template/LLM이 만든 scope literal은 source 자체로 거부된다."""
        plan = _synthetic_plan(
            concepts=[
                _scope_node(
                    "made_up", NodeSource.TEMPLATE, "scope:district:999999999",
                ),
                _measure_node("measure"),
            ],
            transformations=[
                Transformation(
                    id="t1",
                    operator=Operator.PASSAGE_METRIC,
                    inputs={"area": ValueRef("made_up")},
                    params={"metric": "speed"},
                    outputs=["measure"],
                ),
            ],
            final_node="measure",
            question=DIRECT_QUESTION,
        )
        report = validate(plan, available_tools=self.tool_names)
        self.assertIn(Rule.SCOPE_PROVENANCE, report.failed_rules())

    def test_role_reversal_is_rejected(self):
        plan = _synthetic_plan(
            concepts=[
                ConceptNode(
                    id="measure_input",
                    concept=CoreConcept.LOCATION,
                    subtype=Subtype.SCOPE,
                    role=FunctionalRole.MEASURE,
                    source=NodeSource.USER,
                    value="scope:edge:1742",
                ),
                ConceptNode(
                    id="condition",
                    concept=CoreConcept.AMOUNT,
                    subtype=Subtype.SPEED,
                    role=FunctionalRole.SUBCOND,
                    source=NodeSource.TOOL,
                ),
            ],
            transformations=[
                Transformation(
                    id="t1",
                    operator=Operator.PASSAGE_METRIC,
                    inputs={"area": ValueRef("measure_input")},
                    params={"metric": "speed"},
                    outputs=["condition"],
                ),
            ],
            final_node="condition",
            question=DIRECT_QUESTION,
        )
        report = validate(plan, available_tools=self.tool_names)
        self.assertIn(Rule.ROLE_ORDERING, report.failed_rules())


class ExecutorTest(unittest.TestCase):
    """ValueRef 해소, 실행 순서, provenance 재확인."""

    def setUp(self):
        self.registry = TemplateRegistry.from_directory()
        self.tool_executor = new_tool_executor()

    def test_resolve_refs_uses_state(self):
        resolved = resolve_refs(
            {
                "scope_pickup": ValueRef("origin_scope"),
                "name": ValueRef("origin", "name"),
                "date": "20260530",
            },
            {
                "origin_scope": "scope:edge:1742",
                "origin": {"name": "동성로", "region": "대구"},
            },
        )
        self.assertEqual(
            resolved,
            {
                "scope_pickup": "scope:edge:1742",
                "name": "동성로",
                "date": "20260530",
            },
        )

    def test_unresolved_ref_is_executor_error(self):
        with self.assertRaises(ExecutionError) as caught:
            resolve_refs({"scope": ValueRef("missing")}, {})
        self.assertEqual(caught.exception.code, "UNRESOLVED_REF")

    def test_od_execution_order_and_binding(self):
        """Case 1: get_place_scope 2회 후 get_trip_count."""
        plan = self.registry.require("OD_TRIP_COUNT").instantiate(
            OD_QUESTION, OD_SLOTS,
        )
        result = execute_plan(compile_plan(plan), self.tool_executor)
        self.assertEqual(result.status, STATUS_OK, result.error)
        self.assertEqual(
            [entry["tool"] for entry in result.trace],
            ["get_place_scope", "get_place_scope", "get_trip_count"],
        )
        trip_arguments = result.trace[-1]["arguments"]
        self.assertEqual(
            trip_arguments["scope_pickup"], result.state["origin_scope"],
        )
        self.assertEqual(
            trip_arguments["scope_dropoff"], result.state["destination_scope"],
        )

    def test_execution_blocks_unverified_scope(self):
        """Case 5: 검증을 우회해도 실행 시점에서 다시 차단된다."""
        plan = self.registry.require("DIRECT_SCOPE_METRIC").instantiate(
            DIRECT_QUESTION,
            {"scope": "scope:district:999999999", "metric": "speed"},
        )
        result = execute_plan(
            compile_plan(plan),
            self.tool_executor,
            known_scopes={"scope:edge:1742"},
        )
        self.assertEqual(result.status, STATUS_TOOL_ERROR)
        self.assertIn("확인되지 않았습니다", result.error["detail"])

    def test_tool_error_returns_structured_failure(self):
        plan = self.registry.require("PLACE_SCOPE_METRIC").instantiate(
            PLACE_QUESTION,
            {"place": {"name": "존재하지않는장소", "region": ""}, "metric": "speed"},
        )
        result = execute_plan(compile_plan(plan), self.tool_executor)
        self.assertEqual(result.status, STATUS_TOOL_ERROR)
        self.assertEqual(result.error["code"], "NOT_FOUND")
        self.assertEqual(len(result.trace), 1)

    def test_missing_state_produces_executor_error(self):
        plan = self.registry.require("OD_TRIP_COUNT").instantiate(
            OD_QUESTION, OD_SLOTS,
        )
        execution_plan = compile_plan(plan)
        # resolve 단계를 제거해 참조가 해소되지 않는 상황을 만든다.
        execution_plan.steps = [execution_plan.steps[-1]]
        result = execute_plan(execution_plan, self.tool_executor)
        self.assertEqual(result.status, STATUS_EXECUTOR_ERROR)
        self.assertEqual(result.error["code"], "UNRESOLVED_REF")


class PlannerTest(unittest.TestCase):
    """Planner 출력은 모두 untrusted input으로 다룬다."""

    def _planner(self, text):
        return GeoFlowPlanner(
            client=ScriptedClient([{"message": {"content": text}}]),
        )

    def test_planner_is_called_without_tools(self):
        planner = self._planner(json.dumps(OD_GROUNDING))
        planner.plan(OD_QUESTION)
        self.assertIsNone(planner.client.calls[0]["tools"])

    def test_prompt_states_the_factor_pairs_from_one_source(self):
        """짝 규칙 문구를 Prompt에 손으로 또 적어 두지 않는다."""
        from geoflow.factors import describe_constraints

        prompt = self._planner("{}").system_prompt()
        self.assertIn(describe_constraints(), prompt)

    def test_prompt_makes_the_od_qualifier_explicit(self):
        prompt = self._planner("{}").system_prompt()
        self.assertIn("od_role", prompt)
        self.assertIn("pickup", prompt)
        self.assertIn("dropoff", prompt)

    def test_prompt_separates_region_from_an_independent_place(self):
        """상위 지역 수식과 독립 장소를 구분해 설명한다."""
        prompt = self._planner("{}").system_prompt()
        self.assertIn("어린이대공원", prompt)
        self.assertIn("대구와 부산", prompt)

    def test_prompt_states_the_concept_vocabulary(self):
        """어휘는 registry에서 만들어 붙이므로 prompt가 표류하지 않는다."""
        prompt = self._planner("{}").system_prompt()
        for line in ("EVENT/trip", "AMOUNT/fare", "PROPORTION/vacant_ratio"):
            self.assertIn(line, prompt)
        for factor in ("aggregation", "vicinity", "dimension"):
            self.assertIn(factor, prompt)

    def test_prompt_does_not_offer_question_type_templates(self):
        """질문 유형을 고르라는 지시가 남아 있으면 안 된다."""
        prompt = self._planner("{}").system_prompt()
        for name in TemplateRegistry.from_directory().names:
            self.assertNotIn(name, prompt)

    def test_json_inside_code_fence_is_parsed(self):
        planner = self._planner(
            "설명입니다.\n```json\n" + json.dumps(OD_GROUNDING) + "\n```"
        )
        output = planner.plan(OD_QUESTION)
        self.assertEqual(
            [item.id for item in output.concepts],
            ["origin", "destination", "trip", "trip_count"],
        )
        self.assertEqual(
            output.grounding.get("origin").value["region"], "대구",
        )

    def test_unknown_concept_is_planner_error(self):
        planner = self._planner(json.dumps(grounding_payload([
            {"id": "x", "concept": "TAXI", "subtype": "place",
             "role": "MEASURE", "source": "user", "value": "x"},
        ])))
        with self.assertRaises(PlannerError) as caught:
            planner.plan(OD_QUESTION)
        self.assertEqual(caught.exception.code, "INVALID_CONCEPT")

    def test_unknown_subtype_is_planner_error(self):
        """어휘에 없는 subtype은 어느 concept에 붙어도 즉시 거부한다."""
        planner = self._planner(json.dumps(grounding_payload([
            measure_concept("m", "AMOUNT", "택시비"),
        ])))
        with self.assertRaises(PlannerError) as caught:
            planner.plan(OD_QUESTION)
        self.assertEqual(caught.exception.code, "INVALID_SUBTYPE")

    def test_valid_subtype_that_cannot_be_measured_is_rejected(self):
        """어휘에는 있으나 측정값이 될 수 없는 조합은 따로 거른다."""
        planner = self._planner(json.dumps(grounding_payload([
            measure_concept("m", "NETWORK", "road_edge"),
        ])))
        with self.assertRaises(PlannerError) as caught:
            planner.plan(OD_QUESTION)
        self.assertEqual(caught.exception.code, "UNSUPPORTED_MEASURE")

    def test_missing_measure_is_planner_error(self):
        planner = self._planner(json.dumps(grounding_payload([
            place_concept("place_1", "대구"),
        ])))
        with self.assertRaises(PlannerError) as caught:
            planner.plan(PLACE_QUESTION)
        self.assertEqual(caught.exception.code, "NO_MEASURE")

    def test_two_measures_are_planner_error(self):
        planner = self._planner(json.dumps(grounding_payload([
            measure_concept("speed", "AMOUNT", "speed"),
            measure_concept("fare", "AMOUNT", "fare"),
        ])))
        with self.assertRaises(PlannerError) as caught:
            planner.plan(PLACE_QUESTION)
        self.assertEqual(caught.exception.code, "MULTIPLE_MEASURES")

    def test_tool_name_output_is_planner_error(self):
        planner = self._planner('{"tool": "get_trip_count", "arguments": {}}')
        with self.assertRaises(PlannerError):
            planner.plan(OD_QUESTION)

    def test_template_style_output_is_planner_error(self):
        """예전 계약(template + slots)은 더 이상 받지 않는다."""
        planner = self._planner(
            '{"template": "OD_TRIP_COUNT", "slots": {}}'
        )
        with self.assertRaises(PlannerError) as caught:
            planner.plan(OD_QUESTION)
        self.assertEqual(caught.exception.code, "UNKNOWN_KEY")

    def test_broken_json_is_planner_error(self):
        planner = self._planner("답을 모르겠습니다.")
        with self.assertRaises(PlannerError) as caught:
            planner.plan(OD_QUESTION)
        self.assertEqual(caught.exception.code, "JSON_NOT_FOUND")

    def test_unsupported_question_is_planner_error(self):
        planner = self._planner('{"unsupported": true}')
        with self.assertRaises(PlannerError) as caught:
            planner.plan("오늘 날씨 알려줘")
        self.assertEqual(caught.exception.code, "UNSUPPORTED_QUESTION")


class PlannerRetryTest(unittest.TestCase):
    """응답을 반환하지 못한 호출만 다시 부른다.

    작은 모델이 thinking 안에서 같은 문장을 반복하다 생성을 끝내지 못하는
    경우가 있고, 같은 입력이라도 다시 부르면 끝나는 경우가 관측되었다.
    반대로 grounding 판단이 어긋난 출력은 다시 불러도 같으므로 재시도
    대상이 아니다.
    """

    def _planner(self, responses, **kwargs):
        return GeoFlowPlanner(client=ScriptedClient(responses), **kwargs)

    def _valid_response(self):
        return planner_response(OD_GROUNDING)

    def test_unanswered_call_is_retried(self):
        planner = self._planner([
            TimeoutError("timed out"),
            self._valid_response(),
        ])
        output = planner.plan(OD_QUESTION)
        self.assertEqual(output.attempts, 2)
        self.assertEqual(len(planner.client.calls), 2)

    def test_retry_count_is_bounded(self):
        planner = self._planner(
            [TimeoutError("timed out")] * DEFAULT_MAX_ATTEMPTS,
        )
        with self.assertRaises(PlannerError) as caught:
            planner.plan(OD_QUESTION)
        self.assertEqual(caught.exception.code, "PLANNER_CALL_FAILED")
        self.assertEqual(len(planner.client.calls), DEFAULT_MAX_ATTEMPTS)
        self.assertEqual(
            caught.exception.context["attempts"], DEFAULT_MAX_ATTEMPTS,
        )

    def test_empty_response_is_retried(self):
        planner = self._planner([{"message": {}}, self._valid_response()])
        self.assertEqual(planner.plan(OD_QUESTION).attempts, 2)

    def test_truncated_response_is_retried(self):
        """생성 상한에 걸려 잘린 응답은 읽히더라도 계획으로 쓰지 않는다."""
        planner = self._planner([
            {"message": {"content": '{"concepts": [{"id": "origin"'},
             "done_reason": "length"},
            self._valid_response(),
        ])
        self.assertEqual(planner.plan(OD_QUESTION).attempts, 2)

    def test_truncation_without_retry_is_reported(self):
        planner = self._planner(
            [{"message": {"content": "{}"}, "done_reason": "length"}],
            max_attempts=1,
        )
        with self.assertRaises(PlannerError) as caught:
            planner.plan(OD_QUESTION)
        self.assertEqual(caught.exception.code, "OUTPUT_TRUNCATED")

    def test_judgment_error_is_not_retried(self):
        planner = self._planner([
            {"message": {"content": "답을 모르겠습니다."}},
            self._valid_response(),
        ])
        with self.assertRaises(PlannerError) as caught:
            planner.plan(OD_QUESTION)
        self.assertEqual(caught.exception.code, "JSON_NOT_FOUND")
        self.assertEqual(len(planner.client.calls), 1)

    def test_retry_is_configurable(self):
        with self.assertRaises(ValueError):
            self._planner([], max_attempts=0)


class FakeResponse:
    status_code = 200

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


class FakeHttp:
    """payload만 받아 두는 httpx 대역."""

    def __init__(self):
        self.payloads = []

    def post(self, url, json=None, timeout=None):
        self.payloads.append(json)
        return FakeResponse({"message": {"content": "{}"}})


class ChatPayloadTest(unittest.TestCase):
    """think/num_predict는 지정했을 때만 요청에 들어간다."""

    def _client(self, **kwargs):
        http = FakeHttp()
        client = OllamaClient(
            "http://localhost:11434", "test-model", {"temperature": 0},
            http_client=http, **kwargs,
        )
        return client, http

    def test_think_is_absent_by_default(self):
        client, http = self._client()
        client.chat([{"role": "user", "content": "안녕"}])
        self.assertNotIn("think", http.payloads[0])

    def test_think_off_is_sent(self):
        client, http = self._client(think=False)
        client.chat([{"role": "user", "content": "안녕"}])
        self.assertIs(http.payloads[0]["think"], False)

    def test_num_predict_is_sent_as_option(self):
        client, http = self._client()
        client.options = chat_options({"temperature": 0}, 2048)
        client.chat([{"role": "user", "content": "안녕"}])
        self.assertEqual(http.payloads[0]["options"]["num_predict"], 2048)

    def test_chat_options_keeps_base_when_unset(self):
        self.assertEqual(chat_options({"temperature": 0}), {"temperature": 0})
        with self.assertRaises(ValueError):
            chat_options({}, 0)

    def test_resolve_think_choices(self):
        self.assertIsNone(resolve_think("auto"))
        self.assertIs(resolve_think("on"), True)
        self.assertIs(resolve_think("off"), False)


class PlannerPromptExampleTest(unittest.TestCase):
    """출력 예시의 장소명은 실제로 조회되는 이름이어야 한다.

    조회에 실패하는 이름을 정답 예시로 보여 주면, 그 값으로 조회가 깨졌을 때
    재계획 요청과 예시가 충돌해 Planner가 결론을 내지 못한다.
    """

    def test_output_format_example_places_resolve(self):
        import re

        import yaml

        document = yaml.safe_load(
            Path(DEFAULT_PLANNER_PROMPT).read_text(encoding="utf-8")
        )
        examples = document["sections"]["output_format"]
        places = re.findall(
            r'\{"name": "([^"]+)", "region": "([^"]*)"\}', examples,
        )
        self.assertTrue(places, "출력 예시에서 장소 slot을 찾지 못했습니다.")
        for name, region in places:
            with self.subTest(name=name, region=region):
                result = mock_get_place_scope({"name": name, "region": region})
                self.assertNotIsInstance(
                    result, dict,
                    f"예시 장소가 조회되지 않습니다: {name} / {region}",
                )

    def test_repair_instruction_covers_dong_suffix(self):
        """"동"이 접미사 목록에 없으면 재계획이 결론을 내지 못한다."""
        planner = GeoFlowPlanner(client=ScriptedClient([]))
        for suffix in ("시", "군", "구", "동", "길", "로"):
            self.assertIn(f'"{suffix}"', planner.repair_instruction)


class PipelineScenarioTest(unittest.TestCase):
    """stub_query.yaml 기준 필수 시나리오.

    같은 macro library에서 서로 다른 합성 결과가 나오는지를 본다. 질문마다
    다른 완성 template을 고르는 것이 아니라는 점이 요점이다.
    """

    def test_case1_od_trip_count(self):
        pipeline, _client = new_pipeline([OD_GROUNDING])
        run = pipeline.run(OD_QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        # 출발지·도착지 각각에 장소 변환 조각이 한 번씩 적용된다.
        self.assertEqual(
            run.applied_macros,
            ["PLACE_TO_SCOPE", "PLACE_TO_SCOPE", "OD_EVENT_TO_MEASURE"],
        )
        self.assertEqual(run.template, "PLACE_TO_SCOPE+OD_EVENT_TO_MEASURE")
        self.assertEqual(
            analysis_tools(run.hop_log),
            ["get_place_scope", "get_place_scope", "get_trip_count"],
        )
        trip_arguments = next(
            entry for entry in run.hop_log
            if entry["tool"] == "get_trip_count"
        )["arguments"]
        self.assertEqual(
            trip_arguments["scope_pickup"], run.hop_log[0]["result"],
        )
        self.assertEqual(
            trip_arguments["scope_dropoff"], run.hop_log[1]["result"],
        )
        self.assertIsNotNone(run.final_answer)

    def test_result_scopes_are_labeled_with_place_names(self):
        """집계 결과의 scope는 장소명으로 바꿔 보여준다."""
        pipeline, _client = new_pipeline([OD_GROUNDING])
        run = pipeline.run(OD_QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(
            labeling_tools(run.hop_log),
            ["get_scope_name", "get_scope_name"],
        )
        self.assertTrue(run.scope_labels)
        # 답변에는 원본 scope 대신 장소명이 나와야 한다.
        self.assertNotIn("scope:", run.final_answer)
        for name in run.scope_labels.values():
            self.assertIn(name, run.final_answer)

    def test_scope_to_place_name(self):
        """사용자가 제시한 scope의 장소명을 찾는다. 측정값이 없는 질문이다."""
        question = "scope:district:2700000000은 어디인가요?"
        pipeline, _client = new_pipeline([grounding_payload([
            scope_concept("user_scope", "scope:district:2700000000"),
            {"id": "place_name", "concept": "LOCATION", "subtype": "place",
             "role": "MEASURE", "source": "implicit"},
        ])])
        run = pipeline.run(question)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(run.applied_macros, ["SCOPE_TO_PLACE"])
        self.assertEqual(analysis_tools(run.hop_log), ["get_scope_name"])
        self.assertIn("대구", run.final_answer)

    def test_bucket_requires_rollup(self):
        """혼자 쓸 수 없는 조건은 조각을 고르기 전에 거부한다."""
        for factors in (
            {"bucket": "week"},
            {"rollup": "avg"},
        ):
            with self.subTest(factors=factors):
                pipeline, _client = new_pipeline([grounding_payload([
                    event_concept("operation", "operation"),
                    measure_concept("revenue", "AMOUNT", "revenue"),
                ], factors)])
                run = pipeline.run("주 단위 수입은?")
                self.assertEqual(run.stage, Stage.COMPOSITION)
                self.assertEqual(
                    run.error["code"], "INVALID_FACTOR_COMBINATION",
                )
                self.assertIn("함께", run.error["detail"])

    def test_bucket_rollup_is_passed_and_shown(self):
        pipeline, _client = new_pipeline([grounding_payload([
            event_concept("operation", "operation"),
            measure_concept("revenue", "AMOUNT", "revenue"),
        ], {"bucket": "week", "aggregation": "sum", "rollup": "avg",
            "date": "20260801-20260831"})])
        run = pipeline.run("2026년 8월 주 단위로 합산한 택시 수입의 평균은?")
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        tools = [hop for hop in run.hop_log if hop["phase"] == "tool"]
        # bucket 경계가 계약으로 확인되지 않아 호출 하나로 합치지 않는다.
        self.assertEqual([hop["arguments"]["date"] for hop in tools][:2],
                         ["20260801", "20260802"])
        self.assertEqual(len(tools), 31)
        for hop in tools:
            self.assertNotIn("bucket", hop["arguments"])
            self.assertEqual(hop["arguments"]["aggregation"], "sum")
        self.assertIn("주별 합계의 평균", run.final_answer)
        self.assertIn("영업 수익", run.final_answer)

    def test_two_stage_without_period_is_refused(self):
        """기간이 없으면 구간을 나눌 수 없다. TIMS에 기간을 맡기는 병합도 하지 않는다."""
        pipeline, _client = new_pipeline([grounding_payload([
            event_concept("operation", "operation"),
            measure_concept("revenue", "AMOUNT", "revenue"),
        ], {"bucket": "week", "aggregation": "sum", "rollup": "avg"})])
        run = pipeline.run("주 단위로 합산한 택시 수입의 평균은?")
        self.assertIsNone(run.final_answer)
        self.assertEqual(run.error["code"], "UNRESOLVED_PERIOD")
        self.assertEqual(run.hop_log, [])

    def test_bucket_without_inner_aggregation_is_refused(self):
        """구간 안 집계가 없으면 Tool 기본값(avg)으로 실행하지 않고 되묻는다."""
        pipeline, _client = new_pipeline([grounding_payload([
            event_concept("operation", "operation"),
            measure_concept("revenue", "AMOUNT", "revenue"),
        ], {"bucket": "week", "rollup": "avg"})])
        run = pipeline.run("주 단위로 집계한 택시 수입의 평균은?")
        self.assertIsNone(run.final_answer)
        self.assertEqual(run.hop_log, [])
        self.assertEqual(run.error["code"], "AMBIGUOUS_INNER_AGGREGATION")
        self.assertIn("합계, 평균", run.error["user_message"])

    def test_order_requires_dimension(self):
        pipeline, _client = new_pipeline([grounding_payload([
            place_concept("place_1", "대구"),
            event_concept("passage", "passage"),
            measure_concept("count", "AMOUNT", "passage_count"),
        ], {"order": "top"})])
        run = pipeline.run("대구에서 통행량이 가장 많은 곳은?")
        self.assertEqual(run.stage, Stage.COMPOSITION)
        self.assertEqual(run.error["code"], "INVALID_FACTOR_COMBINATION")
        self.assertIn("함께", run.error["detail"])

    def test_relative_date_and_metric_are_named_in_answer(self):
        """상대 날짜와 측정값은 원시값 대신 사람이 읽을 이름으로 보인다."""
        pipeline, _client = new_pipeline([grounding_payload([
            place_concept("place_1", "대구"),
            event_concept("passage", "passage"),
            measure_concept("speed", "AMOUNT", "speed"),
        ], {"date": "last_month", "aggregation": "avg"})])
        run = pipeline.run("지난달 대구 지역 평균 속도는?")
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertIn("지난달", run.final_answer)
        self.assertNotIn("last_month", run.final_answer)
        self.assertIn("속도", run.final_answer)

        pipeline2, _c2 = new_pipeline([grounding_payload([
            event_concept("operation", "operation"),
            measure_concept("count", "AMOUNT", "operating_count"),
        ], {"taxi_type": "private"})])
        run2 = pipeline2.run("부산 개인택시의 영업 횟수는?")
        self.assertEqual(run2.stage, Stage.DONE, run2.runtime_error)
        self.assertIn("영업 횟수", run2.final_answer)

    def test_labeling_failure_keeps_raw_scope(self):
        """장소명 조회가 실패해도 답변 생성은 계속한다."""
        from geoflow.labeling import resolve_scope_labels

        class FailingExecutor:
            tool_names = ("get_scope_name",)

            def execute(self, tool_name, arguments):
                raise RuntimeError("provider down")

        labels, trace = resolve_scope_labels(
            [{"scope": "scope:edge:1742", "count": 1}], FailingExecutor(),
        )
        self.assertEqual(labels, {})
        self.assertEqual(len(trace), 1)
        self.assertEqual(trace[0]["result"]["status"], "ERROR")

    def test_case2_vicinity_scope_metric(self):
        pipeline, _client = new_pipeline([grounding_payload([
            place_concept("place_1", "동대구역"),
            event_concept("passage", "passage"),
            measure_concept("speed", "AMOUNT", "speed"),
        ], {
            "date": "20260530", "time": "120000-130000",
            "aggregation": "avg", "vicinity": True,
        })])
        run = pipeline.run(VICINITY_QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(
            run.applied_macros, ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
        )
        resolve_arguments = run.hop_log[0]["arguments"]
        self.assertEqual(run.hop_log[0]["tool"], "get_place_scope")
        self.assertIs(resolve_arguments["include_vicinity"], True)
        metric_arguments = run.hop_log[1]["arguments"]
        self.assertEqual(run.hop_log[1]["tool"], "get_passage_metrics")
        self.assertEqual(metric_arguments["metric"], "speed")
        self.assertEqual(metric_arguments["aggregation"], "avg")
        self.assertEqual(metric_arguments["date"], "20260530")
        self.assertEqual(metric_arguments["time"], "120000-130000")

    def test_case3_place_scope_metric(self):
        """근처 표현이 없으면 같은 조각이 주변을 포함하지 않는 범위를 만든다."""
        pipeline, _client = new_pipeline([grounding_payload([
            place_concept("place_1", "대구"),
            event_concept("passage", "passage"),
            measure_concept("speed", "AMOUNT", "speed"),
        ], {"aggregation": "avg"})])
        run = pipeline.run(PLACE_QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(
            run.applied_macros, ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
        )
        self.assertEqual(
            [entry["tool"] for entry in run.hop_log],
            ["get_place_scope", "get_passage_metrics"],
        )
        self.assertIs(
            run.hop_log[0]["arguments"]["include_vicinity"], False,
        )

    def test_case4_direct_scope_metric_skips_gazetteer(self):
        """범위를 직접 받은 질문은 장소 변환 조각 없이 합성된다."""
        pipeline, _client = new_pipeline([grounding_payload([
            scope_concept("user_scope", "scope:edge:1742"),
            event_concept("passage", "passage"),
            measure_concept("speed", "AMOUNT", "speed"),
        ], {
            "date": "20260530", "time": "120000-130000",
            "aggregation": "avg",
        })])
        run = pipeline.run(DIRECT_QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(run.applied_macros, ["EVENT_TO_MEASURE"])
        tools_used = [entry["tool"] for entry in run.hop_log]
        self.assertEqual(tools_used, ["get_passage_metrics"])
        self.assertNotIn("get_place_scope", tools_used)
        self.assertEqual(
            run.hop_log[0]["arguments"]["scope"], "scope:edge:1742",
        )

    def test_direct_and_place_share_one_measure_macro(self):
        """직접 범위와 장소 질문은 같은 측정 조각을 쓴다.

        완성 template을 따로 두지 않고 앞단 조각의 유무로만 갈린다.
        """
        direct, _ = new_pipeline([grounding_payload([
            scope_concept("user_scope", "scope:edge:1742"),
            measure_concept("speed", "AMOUNT", "speed"),
        ])])
        place, _ = new_pipeline([grounding_payload([
            place_concept("place_1", "대구"),
            measure_concept("speed", "AMOUNT", "speed"),
        ])])
        direct_run = direct.run(DIRECT_QUESTION)
        place_run = place.run(PLACE_QUESTION)
        self.assertEqual(direct_run.applied_macros, ["EVENT_TO_MEASURE"])
        self.assertEqual(
            place_run.applied_macros, ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
        )
        self.assertEqual(
            direct_run.applied_macros[-1], place_run.applied_macros[-1],
        )

    def test_case5_hallucinated_scope_is_blocked(self):
        """발화에 없는 scope는 계획이 만들어지기 전에 막힌다."""
        pipeline, _client = new_pipeline([grounding_payload([
            scope_concept("user_scope", "scope:district:999999999"),
            event_concept("passage", "passage"),
            measure_concept("speed", "AMOUNT", "speed"),
        ])])
        run = pipeline.run(DIRECT_QUESTION)
        self.assertEqual(run.stage, Stage.PLANNER)
        self.assertEqual(run.error["code"], "UNGROUNDED_SCOPE")
        self.assertEqual(run.hop_log, [])
        self.assertIsNone(run.final_answer)

    def test_grouped_aggregate(self):
        """그룹화는 별도 조각이 아니라 측정 변환의 factor다."""
        pipeline, _client = new_pipeline([grounding_payload([
            event_concept("operation", "operation"),
            measure_concept("revenue", "AMOUNT", "revenue"),
        ], {"dimension": "dayofweek", "taxi_type": "private"})])
        run = pipeline.run("개인용 택시의 요일별 택시 수입 분포는?")
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(run.applied_macros, ["EVENT_TO_MEASURE"])
        arguments = run.hop_log[0]["arguments"]
        self.assertEqual(run.hop_log[0]["tool"], "get_operation_metrics")
        self.assertEqual(arguments["dimension"], "dayofweek")
        self.assertEqual(arguments["taxi_type"], "private")
        self.assertIn("월", run.final_answer)


class RepairTest(unittest.TestCase):
    """장소 조회 실패에 한정한 1회 재계획.

    재계획은 개념 구조를 바꾸지 못하고 실패한 장소의 값만 고칠 수 있다.
    """

    FARE_QUESTION = "대구시의 평균 택시 요금은?"

    def test_not_found_triggers_one_repair(self):
        """대구시(NOT_FOUND) → 재계획 → 대구(성공)."""
        pipeline, client = new_pipeline([
            fare_grounding("대구시"),
            place_patch("place_1", "대구"),
        ])
        run = pipeline.run(self.FARE_QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(run.repair_count, 1)
        self.assertEqual(len(client.calls), 2)
        # 실패한 시도의 Tool 호출도 trace에 남는다.
        self.assertEqual(
            [entry["tool"] for entry in run.hop_log],
            ["get_place_scope", "get_place_scope", "get_trip_metrics"],
        )
        self.assertEqual(
            [item["status"] for item in run.attempts], ["TOOL_ERROR", "OK"],
        )
        self.assertIsNotNone(run.final_answer)

    def test_repair_is_capped_at_one_attempt(self):
        pipeline, client = new_pipeline([
            fare_grounding("대구시"),
            place_patch("place_1", "없는장소"),
        ])
        run = pipeline.run(self.FARE_QUESTION)
        self.assertEqual(run.repair_count, 1)
        self.assertEqual(len(client.calls), 2)
        self.assertIsNotNone(run.runtime_error)
        # 재계획을 이미 한 번 썼으므로 두 번째 실패는 '미시도'로 끝난다.
        self.assertEqual(run.attempts[-1]["status"], STATUS_REPAIR_SKIPPED)

    def test_repair_output_still_passes_every_guard(self):
        """재계획이 지어낸 scope를 끼워 넣어도 계획이 만들어지지 않는다."""
        # 수정안 schema 밖의 내용을 끼워 넣으면 patch 단계에서 걸린다.
        smuggled = {
            "concept_id": "place_1", "name": "대구", "region": "",
            "concepts": [scope_concept("smuggled", "scope:district:999999999")],
        }
        pipeline, _client = new_pipeline([fare_grounding("대구시"), smuggled])
        run = pipeline.run(self.FARE_QUESTION)
        self.assertIsNotNone(run.runtime_error)
        self.assertEqual(run.attempts[-1]["status"], STATUS_REPAIR_FAILED)
        self.assertEqual(
            run.attempts[-1]["error"]["code"], "REPAIR_OUT_OF_SCOPE",
        )
        self.assertIn("NOT_FOUND", json.dumps(run.error, ensure_ascii=False))

    def test_repair_call_failure_is_distinguishable(self):
        """재계획 호출 실패와 재계획 결과 탈락을 기록에서 구분한다.

        Tool trace만 보면 둘 다 "첫 조회 실패 후 아무 호출도 없음"으로 같아
        보인다. 모델별 실패 원인을 나중에 판별하려면 attempt 기록이 필요하다.
        """
        client = ScriptedClient([
            planner_response(fare_grounding("대구시")),
            # content 없음. 재시도 횟수만큼 반복되고 나서야 실패로 확정된다.
            *[{"message": {}}] * DEFAULT_MAX_ATTEMPTS,
        ])
        pipeline = GeoFlowPipeline.create(
            client=client, tool_executor=new_tool_executor(),
        )
        run = pipeline.run(self.FARE_QUESTION)
        self.assertEqual(run.repair_count, 0)
        self.assertEqual(
            [item["status"] for item in run.attempts],
            ["TOOL_ERROR", STATUS_REPAIR_FAILED],
        )
        self.assertIn("content", run.attempts[-1]["error"]["detail"])
        self.assertEqual(
            run.attempts[-1]["error"]["context"]["attempts"],
            DEFAULT_MAX_ATTEMPTS,
        )

    def test_repair_keeps_values_other_than_the_failed_one(self):
        """접미사 제거 규칙이 성공한 개념까지 망가뜨리지 못하게 한다.

        재계획이 origin을 고치면서 destination "신천동"을 "신천"으로 함께
        줄이는 경우가 관측되었다. 고칠 대상은 오류가 난 개념 하나뿐이다.
        """
        # 수정안은 실패한 개념 하나만 가리킨다. 다른 개념은 구조적으로
        # 손댈 수 없다.
        pipeline, _client = new_pipeline([
            od_grounding("동성로동", "신천동"),
            place_patch("origin", "동성로"),
        ])
        run = pipeline.run(OD_QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(run.slots["origin"]["name"], "동성로")
        self.assertEqual(run.slots["destination"]["name"], "신천동")
        self.assertEqual(
            analysis_tools(run.hop_log)[-3:],
            ["get_place_scope", "get_place_scope", "get_trip_count"],
        )

    def test_repair_rejects_structure_change(self):
        """수정안이 개념을 바꾸려 하면 받지 않는다."""
        # 개념을 바꾸려는 수정안은 schema 자체가 받지 않는다.
        pipeline, _client = new_pipeline([
            fare_grounding("대구시"),
            grounding_payload([
                event_concept("operation", "operation"),
                measure_concept("revenue", "AMOUNT", "revenue"),
            ], {"dimension": "dayofweek"}),
        ])
        run = pipeline.run(self.FARE_QUESTION)
        self.assertEqual(run.repair_count, 0)
        self.assertEqual(run.attempts[-1]["status"], STATUS_REPAIR_FAILED)
        self.assertEqual(
            run.attempts[-1]["error"]["code"], "REPAIR_OUT_OF_SCOPE",
        )
        self.assertIn("NOT_FOUND", json.dumps(run.error, ensure_ascii=False))

    def test_repair_rejects_identical_values(self):
        pipeline, _client = new_pipeline([
            fare_grounding("대구시"),
            place_patch("place_1", "대구시"),
        ])
        run = pipeline.run(self.FARE_QUESTION)
        self.assertEqual(run.repair_count, 0)
        self.assertIsNotNone(run.runtime_error)
        self.assertEqual(
            run.attempts[-1]["error"]["code"], "REPAIR_NO_CHANGE",
        )

    def _grounding(self, payload, question):
        return parse_grounding(payload, question)

    def test_repair_cannot_invent_a_region(self):
        """업체 지적: 재계획이 발화에 없는 상위 지역을 만들어 붙이는 문제."""
        for invented in ("경상북도", "시", "대구광역시"):
            with self.subTest(region=invented):
                previous = self._grounding(
                    fare_grounding("대구시"), self.FARE_QUESTION,
                )
                repaired = self._grounding(
                    fare_grounding("대구", invented), self.FARE_QUESTION,
                )
                drop_invented_regions(previous, repaired)
                self.assertEqual(
                    repaired.get("place_1").value,
                    {"name": "대구", "region": ""},
                )

    def test_repair_keeps_region_the_user_actually_said(self):
        """처음부터 region이 있었다면 재계획이 다듬는 것은 허용한다."""
        question = "부산 초읍동의 어린이대공원 평균 택시 요금은?"
        previous = self._grounding(
            fare_grounding("어린이대공원", "부산 초읍동"), question,
        )
        repaired = self._grounding(
            fare_grounding("어린이대공원", "부산"), question,
        )
        drop_invented_regions(previous, repaired)
        self.assertEqual(repaired.get("place_1").value["region"], "부산")

    def test_grounding_drops_a_region_absent_from_the_question(self):
        """최초 grounding도 발화에 없는 상위 지역을 만들 수 없다."""
        planner = GeoFlowPlanner(client=ScriptedClient([
            planner_response(fare_grounding("대구", "경상북도")),
        ]))
        output = planner.plan(self.FARE_QUESTION)
        self.assertEqual(
            output.grounding.get("place_1").value,
            {"name": "대구", "region": ""},
        )

    def test_repair_drops_invented_region_end_to_end(self):
        """대구시 → 대구/시 로 고쳐 와도 region 없이 조회해 성공해야 한다."""
        pipeline, _client = new_pipeline([
            fare_grounding("대구시"),
            place_patch("place_1", "대구", "시"),
        ])
        run = pipeline.run("대구시의 평균 택시 요금은?")
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(run.repair_count, 1)
        resolved = [
            entry for entry in run.hop_log
            if entry["tool"] == "get_place_scope"
        ]
        self.assertEqual(resolved[-1]["arguments"]["name"], "대구")
        self.assertNotIn("region", resolved[-1]["arguments"])

    def test_non_place_failure_is_not_repaired(self):
        """장소 조회가 아닌 경로는 재계획 대상이 아니다."""
        pipeline, client = new_pipeline([grounding_payload([
            scope_concept("user_scope", "scope:edge:1742"),
            event_concept("passage", "passage"),
            measure_concept("speed", "AMOUNT", "speed"),
        ])])
        run = pipeline.run(DIRECT_QUESTION)
        self.assertEqual(run.stage, Stage.DONE)
        self.assertEqual(len(client.calls), 1)

    def test_successful_run_does_not_call_planner_twice(self):
        pipeline, client = new_pipeline([OD_GROUNDING])
        run = pipeline.run(OD_QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(run.repair_count, 0)


class GroundingAccuracyHarnessTest(unittest.TestCase):
    """grounding 정확도 측정 harness의 판정 로직."""

    OD_QUESTION = "대구 동성로동에서 출발하여 신천동에 도착한 실차 구간 건수는?"

    def _grounding(self, origin, destination):
        return parse_grounding(
            od_grounding(origin, destination), self.OD_QUESTION,
        )

    def test_correct_origin_destination_order(self):
        self.assertTrue(check_concept_roles(
            self.OD_QUESTION, self._grounding("동성로동", "신천동"),
        ))

    def test_swapped_origin_destination_is_detected(self):
        self.assertFalse(check_concept_roles(
            self.OD_QUESTION, self._grounding("신천동", "동성로동"),
        ))

    def test_unjudgeable_grounding_returns_none(self):
        grounding = parse_grounding(
            fare_grounding("대구"), "대구시의 평균 택시 요금은?",
        )
        self.assertIsNone(check_concept_roles(
            "대구시의 평균 택시 요금은?", grounding,
        ))

    def test_concept_scoring_counts_each_level(self):
        score = score_concepts(
            ["LOCATION/place:SUBCOND", "AMOUNT/fare:MEASURE"],
            ["LOCATION/place:SUBCOND", "AMOUNT/revenue:MEASURE"],
        )
        # concept은 둘 다 맞고, subtype부터 하나가 어긋난다.
        self.assertEqual(score["concept"]["matched"], 2)
        self.assertEqual(score["subtype"]["matched"], 1)
        self.assertEqual(score["role"]["matched"], 1)

    def test_repeated_concepts_are_counted_as_a_multiset(self):
        """출발지·도착지처럼 같은 개념이 둘인 질문을 집합으로 뭉개지 않는다."""
        score = score_concepts(
            ["LOCATION/place:SUBCOND"],
            ["LOCATION/place:SUBCOND", "LOCATION/place:SUBCOND"],
        )
        self.assertEqual(score["role"]["matched"], 1)
        self.assertEqual(score["role"]["expected"], 2)

    def test_macro_scoring_reports_recall_and_exactness(self):
        score = score_sequence(
            ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
            ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
        )
        self.assertTrue(score["exact"])
        partial = score_sequence(
            ["EVENT_TO_MEASURE"],
            ["PLACE_TO_SCOPE", "EVENT_TO_MEASURE"],
        )
        self.assertFalse(partial["exact"])
        self.assertEqual(partial["matched"], 1)

    def test_every_query_label_is_a_known_macro(self):
        """평가 셋의 정답 라벨이 macro library와 어긋나지 않아야 한다."""
        library = MacroLibrary.from_directory()
        for query_file in ("stub_query.yaml", "stub_query_boundary.yaml"):
            for query in load_queries(BASE_DIR / query_file):
                with self.subTest(query_file=query_file, query=query["id"]):
                    expected = query.get("expected_macros")
                    self.assertTrue(expected, "expected_macros가 없습니다.")
                    for name in expected:
                        if name == NO_TEMPLATE_LABEL:
                            continue
                        self.assertIn(name, library)

    def test_every_query_label_is_a_known_operator(self):
        for query_file in ("stub_query.yaml", "stub_query_boundary.yaml"):
            for query in load_queries(BASE_DIR / query_file):
                with self.subTest(query_file=query_file, query=query["id"]):
                    for name in query.get("expected_operators") or []:
                        self.assertIn(name, operator_names())


class RuntimeIntegrationTest(unittest.TestCase):
    """AssistantRuntime의 agent mode 분기와 react 회귀."""

    def test_default_agent_mode_is_react(self):
        runtime = AssistantRuntime(
            client=ScriptedClient([]),
            tools=TOOLS,
            system_prompt=SYSTEM_PROMPT,
            tool_executor=new_tool_executor(),
        )
        self.assertEqual(runtime.agent_mode, AGENT_MODE_REACT)

    def test_geoflow_mode_requires_pipeline(self):
        with self.assertRaises(ValueError):
            AssistantRuntime(
                client=ScriptedClient([]),
                tools=TOOLS,
                system_prompt=SYSTEM_PROMPT,
                tool_executor=new_tool_executor(),
                agent_mode=AGENT_MODE_GEOFLOW,
            )

    def test_react_mode_smoke(self):
        """Case 6: 기존 react 경로가 그대로 동작해야 한다."""
        client = ScriptedClient([
            {
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "function": {
                            "name": "get_passage_metrics",
                            "arguments": {
                                "metric": "speed",
                                "scope": "scope:edge:1742",
                                "date": "20260530",
                                "time": "120000-130000",
                                "aggregation": "avg",
                            },
                        },
                    }],
                },
            },
            {"message": {"content": "평균 속도는 34.912km/h입니다."}},
        ])
        runtime = AssistantRuntime(
            client=client,
            tools=TOOLS,
            system_prompt=SYSTEM_PROMPT,
            tool_executor=new_tool_executor(),
        )
        result = runtime.run_question(DIRECT_QUESTION)
        self.assertIsNone(result["runtime_error"])
        self.assertEqual(result["agent_mode"], AGENT_MODE_REACT)
        self.assertEqual(len(result["hop_log"]), 1)
        self.assertEqual(result["hop_log"][0]["tool"], "get_passage_metrics")
        self.assertEqual(
            result["final_answer"], "평균 속도는 34.912km/h입니다.",
        )
        # react mode는 기존처럼 Tool Schema를 모델에 전달한다.
        self.assertIsNotNone(client.calls[0]["tools"])

    def test_react_mode_still_blocks_unverified_scope(self):
        client = ScriptedClient([
            {
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "function": {
                            "name": "get_passage_metrics",
                            "arguments": {
                                "metric": "speed",
                                "scope": "scope:district:999999999",
                            },
                        },
                    }],
                },
            },
            {"message": {"content": "scope를 확인할 수 없습니다."}},
        ])
        runtime = AssistantRuntime(
            client=client,
            tools=TOOLS,
            system_prompt=SYSTEM_PROMPT,
            tool_executor=new_tool_executor(),
        )
        result = runtime.run_question(DIRECT_QUESTION)
        blocked = result["hop_log"][0]["result"]
        self.assertEqual(blocked["status"], "ERROR")
        self.assertEqual(blocked["error_code"], "INVALID_ARGUMENT")

    def test_geoflow_mode_runs_through_runtime(self):
        pipeline, client = new_pipeline([OD_GROUNDING])
        runtime = AssistantRuntime(
            client=client,
            tools=TOOLS,
            system_prompt=SYSTEM_PROMPT,
            tool_executor=pipeline.tool_executor,
            agent_mode=AGENT_MODE_GEOFLOW,
            geoflow=pipeline,
        )
        result = runtime.run_question(OD_QUESTION)
        self.assertIsNone(result["runtime_error"])
        self.assertEqual(result["agent_mode"], AGENT_MODE_GEOFLOW)
        self.assertEqual(len(analysis_tools(result["hop_log"])), 3)
        self.assertEqual(
            result["geoflow"]["applied_macros"],
            ["PLACE_TO_SCOPE", "PLACE_TO_SCOPE", "OD_EVENT_TO_MEASURE"],
        )
        self.assertTrue(result["geoflow"]["grounding"]["concepts"])
        self.assertEqual(result["geoflow"]["validation"]["status"], "OK")
        self.assertIn("planner_ms", result["geoflow"]["durations"])
        self.assertEqual(len(result["model_calls"]), 1)

    def test_geoflow_result_is_json_serializable(self):
        pipeline, client = new_pipeline([OD_GROUNDING])
        runtime = AssistantRuntime(
            client=client,
            tools=TOOLS,
            system_prompt=SYSTEM_PROMPT,
            tool_executor=pipeline.tool_executor,
            agent_mode=AGENT_MODE_GEOFLOW,
            geoflow=pipeline,
        )
        result = runtime.run_question(OD_QUESTION)
        json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
