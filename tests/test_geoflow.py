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
from tool_executor import ToolExecutor  # noqa: E402
from tool_handlers import get_tool_handlers  # noqa: E402

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
from geoflow.operator_registry import Operator  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline, Stage  # noqa: E402
from geoflow.planner import GeoFlowPlanner  # noqa: E402
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
        return self.responses.pop(0)


def planner_response(payload):
    return {"message": {"content": json.dumps(payload, ensure_ascii=False)}}


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
            },
        )

    def test_unknown_template_is_rejected(self):
        with self.assertRaises(TemplateError) as caught:
            self.registry.require("NOT_A_TEMPLATE")
        self.assertIn("알 수 없는 template", caught.exception.detail)

    def test_required_slot_is_enforced(self):
        template = self.registry.require("OD_TRIP_COUNT")
        with self.assertRaises(TemplateError) as caught:
            template.instantiate(OD_QUESTION, {"origin": {"name": "동성로"}})
        self.assertIn("필수 slot이 없습니다: destination", caught.exception.detail)

    def test_unknown_slot_is_rejected(self):
        template = self.registry.require("OD_TRIP_COUNT")
        with self.assertRaises(TemplateError) as caught:
            template.instantiate(
                OD_QUESTION, {**OD_SLOTS, "scope": "scope:district:1"},
            )
        self.assertIn("허용되지 않은 slot", caught.exception.detail)

    def test_enum_slot_value_is_validated(self):
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

    def setUp(self):
        self.registry = TemplateRegistry.from_directory()

    def _planner(self, text):
        return GeoFlowPlanner(
            client=ScriptedClient([{"message": {"content": text}}]),
            templates=self.registry,
        )

    def test_planner_is_called_without_tools(self):
        planner = self._planner(
            json.dumps({"template": "OD_TRIP_COUNT", "slots": OD_SLOTS})
        )
        planner.plan(OD_QUESTION)
        self.assertIsNone(planner.client.calls[0]["tools"])

    def test_prompt_lists_every_template(self):
        planner = self._planner("{}")
        prompt = planner.system_prompt()
        for name in self.registry.names:
            self.assertIn(name, prompt)

    def test_json_inside_code_fence_is_parsed(self):
        planner = self._planner(
            "설명입니다.\n```json\n"
            + json.dumps({"template": "OD_TRIP_COUNT", "slots": OD_SLOTS})
            + "\n```"
        )
        output = planner.plan(OD_QUESTION)
        self.assertEqual(output.template, "OD_TRIP_COUNT")
        self.assertEqual(output.slots["origin"]["region"], "대구")

    def test_unknown_template_is_planner_error(self):
        planner = self._planner('{"template": "FREESTYLE", "slots": {}}')
        with self.assertRaises(PlannerError) as caught:
            planner.plan(OD_QUESTION)
        self.assertEqual(caught.exception.code, "UNKNOWN_TEMPLATE")

    def test_tool_name_output_is_planner_error(self):
        planner = self._planner('{"tool": "get_trip_count", "arguments": {}}')
        with self.assertRaises(PlannerError):
            planner.plan(OD_QUESTION)

    def test_broken_json_is_planner_error(self):
        planner = self._planner("답을 모르겠습니다.")
        with self.assertRaises(PlannerError) as caught:
            planner.plan(OD_QUESTION)
        self.assertEqual(caught.exception.code, "JSON_NOT_FOUND")

    def test_no_matching_template_is_planner_error(self):
        planner = self._planner('{"template": "NONE", "slots": {}}')
        with self.assertRaises(PlannerError) as caught:
            planner.plan("오늘 날씨 알려줘")
        self.assertEqual(caught.exception.code, "NO_MATCHING_TEMPLATE")


class PipelineScenarioTest(unittest.TestCase):
    """stub_query.yaml 기준 필수 시나리오."""

    def test_case1_od_trip_count(self):
        pipeline, _client = new_pipeline([
            {"template": "OD_TRIP_COUNT", "slots": OD_SLOTS},
        ])
        run = pipeline.run(OD_QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(run.template, "OD_TRIP_COUNT")
        self.assertEqual(
            [entry["tool"] for entry in run.hop_log],
            ["get_place_scope", "get_place_scope", "get_trip_count"],
        )
        trip_arguments = run.hop_log[-1]["arguments"]
        self.assertEqual(
            trip_arguments["scope_pickup"], run.hop_log[0]["result"],
        )
        self.assertEqual(
            trip_arguments["scope_dropoff"], run.hop_log[1]["result"],
        )
        self.assertIsNotNone(run.final_answer)

    def test_case2_vicinity_scope_metric(self):
        pipeline, _client = new_pipeline([{
            "template": "VICINITY_SCOPE_METRIC",
            "slots": {
                "place": {"name": "동대구역", "region": ""},
                "metric": "speed",
                "aggregation": "avg",
                "date": "20260530",
                "time": "120000-130000",
            },
        }])
        run = pipeline.run(VICINITY_QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
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
        pipeline, _client = new_pipeline([{
            "template": "PLACE_SCOPE_METRIC",
            "slots": {
                "place": {"name": "대구", "region": ""},
                "metric": "speed",
                "aggregation": "avg",
            },
        }])
        run = pipeline.run(PLACE_QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        self.assertEqual(
            [entry["tool"] for entry in run.hop_log],
            ["get_place_scope", "get_passage_metrics"],
        )
        self.assertIs(
            run.hop_log[0]["arguments"]["include_vicinity"], False,
        )

    def test_case4_direct_scope_metric_skips_gazetteer(self):
        pipeline, _client = new_pipeline([{
            "template": "DIRECT_SCOPE_METRIC",
            "slots": {
                "scope": "scope:edge:1742",
                "metric": "speed",
                "aggregation": "avg",
                "date": "20260530",
                "time": "120000-130000",
            },
        }])
        run = pipeline.run(DIRECT_QUESTION)
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        tools_used = [entry["tool"] for entry in run.hop_log]
        self.assertEqual(tools_used, ["get_passage_metrics"])
        self.assertNotIn("get_place_scope", tools_used)
        self.assertEqual(
            run.hop_log[0]["arguments"]["scope"], "scope:edge:1742",
        )

    def test_case5_hallucinated_scope_is_blocked(self):
        pipeline, _client = new_pipeline([{
            "template": "DIRECT_SCOPE_METRIC",
            "slots": {
                "scope": "scope:district:999999999",
                "metric": "speed",
            },
        }])
        run = pipeline.run(DIRECT_QUESTION)
        self.assertEqual(run.stage, Stage.VALIDATION)
        self.assertEqual(run.hop_log, [])
        self.assertIn(
            Rule.SCOPE_PROVENANCE, run.validation["failed_rules"],
        )
        self.assertIsNone(run.final_answer)

    def test_grouped_aggregate(self):
        pipeline, _client = new_pipeline([{
            "template": "GROUPED_AGGREGATE",
            "slots": {
                "metric": "revenue",
                "dimension": "dayofweek",
                "taxi_type": "private",
            },
        }])
        run = pipeline.run("개인용 택시의 요일별 택시 수입 분포는?")
        self.assertEqual(run.stage, Stage.DONE, run.runtime_error)
        arguments = run.hop_log[0]["arguments"]
        self.assertEqual(run.hop_log[0]["tool"], "get_operation_metrics")
        self.assertEqual(arguments["dimension"], "dayofweek")
        self.assertEqual(arguments["taxi_type"], "private")
        self.assertIn("월", run.final_answer)


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
        pipeline, client = new_pipeline([
            {"template": "OD_TRIP_COUNT", "slots": OD_SLOTS},
        ])
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
        self.assertEqual(len(result["hop_log"]), 3)
        self.assertEqual(result["geoflow"]["template"], "OD_TRIP_COUNT")
        self.assertEqual(result["geoflow"]["validation"]["status"], "OK")
        self.assertIn("planner_ms", result["geoflow"]["durations"])
        self.assertEqual(len(result["model_calls"]), 1)

    def test_geoflow_result_is_json_serializable(self):
        pipeline, client = new_pipeline([
            {"template": "OD_TRIP_COUNT", "slots": OD_SLOTS},
        ])
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
