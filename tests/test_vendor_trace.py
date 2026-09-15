# -*- coding: utf-8 -*-
"""업체 13개 질문 acceptance의 구조 보장 테스트.

여기서는 LLM을 호출하지 않는다. 자연어 해석의 실제 품질은
evaluate_vendor_trace.py가 실행 trace로 검증한다. 이 파일은 두 가지를 고정한다.

1. gold contract 자체가 유효한가
2. evaluator가 업체가 지적한 오류를 실제로 잡아내는가

2번이 핵심이다. 통과만 하는 evaluator는 아무것도 증명하지 못하므로, 업체가
자료에 기록한 실패 trace를 그대로 넣어 기대한 분류로 실패하는지 확인한다.

실행:
    python -m unittest discover -s tests -t .
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from build import build  # noqa: E402
from geoflow.compiler import compile_plan  # noqa: E402
from geoflow.executor import execute_plan  # noqa: E402
from geoflow.templates import TemplateRegistry  # noqa: E402
from geoflow.validator import validate  # noqa: E402
from query_loader import load_queries  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402
from tool_handlers import get_tool_handlers  # noqa: E402
from vendor_trace_contract import (  # noqa: E402
    Failure,
    evaluate_case,
    load_gold,
    normalize_value,
)

VENDOR_DIR = ROOT / "evaluation" / "vendor"
QUERIES = load_queries(VENDOR_DIR / "vendor_queries.yaml")
GOLD = load_gold(VENDOR_DIR / "vendor_trace_gold.yaml")
QUESTION = {item["id"]: item["question"] for item in QUERIES}
TOOLS, _PROMPT = build()

DAEGU = "scope:district:2700000000"
BUSAN = "scope:district:2600000000"
DONGSEONGRO = "scope:edge:1742"
SINCHEON = "scope:district:2723510100"
CHOEUP = "scope:district:2623010700"
CHORYANG = "scope:district:2617010100"
PARK = "scope:edge:busan_children_park"
DONGDAEGU = "scope:edge:11234"

NOT_FOUND = {
    "status": "ERROR",
    "error_code": "NOT_FOUND",
    "message": "일치하는 장소 또는 행정구역을 찾을 수 없습니다.",
    "retryable": True,
}


def call(tool, arguments, result):
    return {"tool": tool, "arguments": dict(arguments), "result": result}


def run(case_id, trace):
    return evaluate_case(GOLD[case_id], QUESTION[case_id], trace)[0]


def categories(problems):
    return {problem["category"] for problem in problems}


class GoldContractTest(unittest.TestCase):
    """gold contract 자체의 유효성."""

    def test_every_question_has_a_contract(self):
        self.assertEqual(len(QUERIES), 13)
        self.assertEqual({item["id"] for item in QUERIES}, set(GOLD))

    def test_contract_tools_exist_in_executor(self):
        available = set(
            ToolExecutor(tools=TOOLS, handlers=get_tool_handlers()).tool_names
        )
        for case in GOLD.values():
            for step in case.steps:
                with self.subTest(case=case.id, tool=step.tool):
                    self.assertIn(step.tool, available)

    def test_expected_templates_exist(self):
        registry = TemplateRegistry.from_directory()
        for item in QUERIES:
            with self.subTest(query=item["id"]):
                self.assertIn(item["expected_template"], registry)

    def test_vendor_notation_is_normalized(self):
        self.assertEqual(normalize_value("12:00~13:00"), "120000-130000")
        self.assertEqual(normalize_value("edge:1742"), "scope:edge:1742")
        self.assertEqual(normalize_value("20260530"), "20260530")


class VendorReportedFailureTest(unittest.TestCase):
    """업체가 자료에 기록한 실패 trace가 실제로 FAIL로 잡히는지 확인한다.

    evaluator가 이 trace들을 통과시키면 13/13은 아무 의미가 없다.
    """

    def test_q03_missing_include_vicinity(self):
        problems = run("q03_station_vicinity_speed", [
            call("get_place_scope", {"name": "동대구역"}, DONGDAEGU),
            call("get_passage_metrics",
                 {"metric": "speed", "aggregation": "avg",
                  "scope": DONGDAEGU}, "30km/h"),
        ])
        self.assertIn(Failure.MISSING_REQUIRED_ARGUMENT, categories(problems))

    def test_q04_hallucinated_last_week(self):
        problems = run("q04_daegu_average_speed", [
            call("get_place_scope", {"name": "대구"}, DAEGU),
            call("get_passage_metrics",
                 {"metric": "speed", "aggregation": "avg",
                  "scope": DAEGU, "date": "last_week"}, "27km/h"),
        ])
        self.assertIn(Failure.FORBIDDEN_ARGUMENT, categories(problems))

    def test_q05_hallucinated_last_week(self):
        problems = run("q05_dongseongro_average_speed", [
            call("get_place_scope", {"name": "동성로길"}, NOT_FOUND),
            call("get_place_scope", {"name": "동성로"}, DONGSEONGRO),
            call("get_passage_metrics",
                 {"metric": "speed", "scope": DONGSEONGRO,
                  "date": "last_week"}, "30km/h"),
        ])
        self.assertIn(Failure.FORBIDDEN_ARGUMENT, categories(problems))

    def test_q22_hallucinated_last_week(self):
        problems = run("q22_daegu_origin_destination_count", [
            call("get_place_scope", {"name": "동성로동"}, NOT_FOUND),
            call("get_place_scope", {"name": "동성로"}, DONGSEONGRO),
            call("get_place_scope", {"name": "신천동"}, SINCHEON),
            call("get_trip_count",
                 {"scope_pickup": DONGSEONGRO, "scope_dropoff": SINCHEON,
                  "date": "last_week"}, [{"count": 1}]),
        ])
        self.assertIn(Failure.FORBIDDEN_ARGUMENT, categories(problems))

    def test_q24_invents_gyeongsangbukdo(self):
        """사용자가 말하지 않은 '경상북도'를 만들어내는 경우."""
        problems = run("q24_daegu_average_fare", [
            call("get_place_scope", {"name": "대구시"}, NOT_FOUND),
            call("get_place_scope",
                 {"name": "대구", "region": "경상북도"}, NOT_FOUND),
            call("get_place_scope",
                 {"name": "대구광역시", "region": "경상북도"}, NOT_FOUND),
            call("get_place_scope", {"name": "대구"}, DAEGU),
            call("get_trip_metrics",
                 {"metric": "fare", "aggregation": "avg", "scope": DAEGU},
                 13289),
        ])
        found = categories(problems)
        self.assertIn(Failure.UNGROUNDED_ARGUMENT, found)
        self.assertIn(Failure.UNEXPECTED_RETRY, found)

    def test_q25_ranking_misinterpretation(self):
        """"주변의 통행량"을 순위 조회로 오해한 경우."""
        problems = run("q25_busan_park_vicinity_count", [
            call("get_place_scope",
                 {"name": "어린이대공원", "region": "부산 초읍동",
                  "include_vicinity": True}, PARK),
            call("get_passage_count",
                 {"scope": PARK, "dimension": "emd", "order": "top",
                  "limit": 1}, [{"count": 1}]),
        ])
        self.assertIn(Failure.FORBIDDEN_ARGUMENT, categories(problems))

    def test_q27_hallucinated_last_week(self):
        problems = run("q27_busan_origin_destination_count", [
            call("get_place_scope", {"name": "초읍동"}, CHOEUP),
            call("get_place_scope", {"name": "초량동"}, CHORYANG),
            call("get_trip_count",
                 {"scope_pickup": CHOEUP, "scope_dropoff": CHORYANG,
                  "date": "last_week"}, [{"count": 1}]),
        ])
        self.assertIn(Failure.FORBIDDEN_ARGUMENT, categories(problems))

    def test_q29_hallucinated_last_month(self):
        problems = run("q29_busan_average_fare", [
            call("get_place_scope", {"name": "부산시"}, NOT_FOUND),
            call("get_place_scope", {"name": "부산"}, BUSAN),
            call("get_trip_metrics",
                 {"metric": "fare", "aggregation": "avg", "scope": BUSAN,
                  "date": "last_month"}, 18028),
        ])
        self.assertIn(Failure.FORBIDDEN_ARGUMENT, categories(problems))

    def test_origin_destination_swap_is_detected(self):
        """O/D가 뒤바뀌면 binding 검사에서 잡혀야 한다."""
        problems = run("q27_busan_origin_destination_count", [
            call("get_place_scope", {"name": "초읍동"}, CHOEUP),
            call("get_place_scope", {"name": "초량동"}, CHORYANG),
            call("get_trip_count",
                 {"scope_pickup": CHORYANG, "scope_dropoff": CHOEUP},
                 [{"count": 1}]),
        ])
        self.assertIn(
            Failure.DEPENDENCY_BINDING_MISMATCH, categories(problems),
        )

    def test_fabricated_scope_is_detected(self):
        problems = run("q04_daegu_average_speed", [
            call("get_place_scope", {"name": "대구"}, DAEGU),
            call("get_passage_metrics",
                 {"metric": "speed", "aggregation": "avg",
                  "scope": "scope:district:999999999"}, "27km/h"),
        ])
        self.assertIn(
            Failure.SCOPE_PROVENANCE_VIOLATION, categories(problems),
        )

    def test_wrong_tool_is_detected(self):
        problems = run("q18_private_revenue_by_day", [
            call("get_trip_metrics", {"metric": "fare"}, 1000),
        ])
        self.assertIn(Failure.TOOL_SEQUENCE_MISMATCH, categories(problems))


class VendorGoldTracePassesTest(unittest.TestCase):
    """업체가 정답으로 제시한 흐름은 반드시 PASS여야 한다."""

    def test_q03_gold_trace_passes(self):
        self.assertEqual(run("q03_station_vicinity_speed", [
            call("get_place_scope",
                 {"name": "동대구역", "include_vicinity": True}, DONGDAEGU),
            call("get_passage_metrics",
                 {"metric": "speed", "aggregation": "avg",
                  "scope": DONGDAEGU, "date": "20260530",
                  "time": "120000-130000"}, "26km/h"),
        ]), [])

    def test_q02_default_arguments_are_allowed(self):
        """업체는 taxi_type=all, taxi_status=all이 있어도 정상으로 판정했다."""
        self.assertEqual(run("q02_edge_passage_count", [
            call("get_passage_count",
                 {"scope": "scope:edge:19384", "date": "20260530",
                  "time": "120000-130000", "taxi_type": "all",
                  "taxi_status": "all"}, [{"count": 3265}]),
        ]), [])

    def test_q24_single_repair_passes(self):
        self.assertEqual(run("q24_daegu_average_fare", [
            call("get_place_scope", {"name": "대구시"}, NOT_FOUND),
            call("get_place_scope", {"name": "대구"}, DAEGU),
            call("get_trip_metrics",
                 {"metric": "fare", "aggregation": "avg", "scope": DAEGU},
                 13289),
        ]), [])


class VendorStructuralGuaranteeTest(unittest.TestCase):
    """LLM 없이 template/compiler 수준에서 보장되는 부분을 고정한다."""

    def setUp(self):
        self.registry = TemplateRegistry.from_directory()
        self.tool_executor = ToolExecutor(
            tools=TOOLS, handlers=get_tool_handlers(),
        )

    def _steps(self, template_name, question, slots):
        template = self.registry.require(template_name)
        plan = template.instantiate(question, slots)
        report = validate(
            plan, available_tools=self.tool_executor.tool_names,
        )
        self.assertTrue(report.ok, report.errors)
        return plan, compile_plan(plan).steps

    def test_q25_template_cannot_express_ranking(self):
        """Q25 오해의 재발 방지: 해당 template에 순위 slot이 아예 없다."""
        template = self.registry.require("VICINITY_PASSAGE_COUNT")
        for forbidden in ("dimension", "order", "limit"):
            with self.subTest(slot=forbidden):
                self.assertNotIn(forbidden, template.slots)

    def test_q25_vicinity_count_shape(self):
        _plan, steps = self._steps(
            "VICINITY_PASSAGE_COUNT",
            QUESTION["q25_busan_park_vicinity_count"],
            {"place": {"name": "어린이대공원", "region": "부산 초읍동"}},
        )
        self.assertEqual([step.tool_name for step in steps],
                         ["get_place_scope", "get_passage_count"])
        self.assertIs(steps[0].arguments["include_vicinity"], True)
        for forbidden in ("dimension", "order", "limit"):
            self.assertNotIn(forbidden, steps[-1].arguments)

    def test_q03_include_vicinity_is_hardcoded(self):
        _plan, steps = self._steps(
            "VICINITY_SCOPE_METRIC",
            QUESTION["q03_station_vicinity_speed"],
            {"place": {"name": "동대구역", "region": ""}, "metric": "speed"},
        )
        self.assertIs(steps[0].arguments["include_vicinity"], True)

    def test_q22_origin_destination_binding_is_fixed(self):
        _plan, steps = self._steps(
            "OD_TRIP_COUNT",
            QUESTION["q22_daegu_origin_destination_count"],
            {
                "origin": {"name": "동성로", "region": "대구"},
                "destination": {"name": "신천동", "region": ""},
            },
        )
        trip = steps[-1]
        self.assertEqual(trip.arguments["scope_pickup"].node_id, "origin_scope")
        self.assertEqual(
            trip.arguments["scope_dropoff"].node_id, "destination_scope",
        )

    def test_period_is_never_added_when_absent_from_slots(self):
        """질문에 기간이 없으면 date/time argument 자체가 만들어지지 않는다."""
        for name, slots in (
            ("PLACE_SCOPE_METRIC",
             {"place": {"name": "대구", "region": ""}, "metric": "speed"}),
            ("TRIP_FARE_METRIC", {"place": {"name": "대구", "region": ""}}),
            ("OD_TRIP_COUNT", {"origin": {"name": "동성로", "region": "대구"},
                               "destination": {"name": "신천동", "region": ""}}),
        ):
            with self.subTest(template=name):
                _plan, steps = self._steps(name, "질문", slots)
                for step in steps:
                    self.assertNotIn("date", step.arguments)
                    self.assertNotIn("time", step.arguments)

    def test_q24_fare_uses_trip_metrics_not_operation(self):
        _plan, steps = self._steps(
            "TRIP_FARE_METRIC",
            QUESTION["q24_daegu_average_fare"],
            {"place": {"name": "대구", "region": ""}},
        )
        self.assertEqual(steps[-1].tool_name, "get_trip_metrics")
        self.assertEqual(steps[-1].arguments["metric"], "fare")

    def test_execution_binds_tool_results_not_literals(self):
        plan, _steps = self._steps(
            "OD_TRIP_COUNT",
            QUESTION["q22_daegu_origin_destination_count"],
            {
                "origin": {"name": "동성로", "region": "대구"},
                "destination": {"name": "신천동", "region": ""},
            },
        )
        result = execute_plan(compile_plan(plan), self.tool_executor)
        self.assertEqual(result.status, "OK", result.error)
        trace = result.trace
        self.assertEqual(
            trace[-1]["arguments"]["scope_pickup"], trace[0]["result"],
        )
        self.assertEqual(
            trace[-1]["arguments"]["scope_dropoff"], trace[1]["result"],
        )


if __name__ == "__main__":
    unittest.main()
