# -*- coding: utf-8 -*-
"""조건 보존 기능(geoflow/conditions.py)의 결정적 검증. LLM을 부르지 않는다.

틀린 grounding을 거부만 하는 구현이 통과하지 못하도록 정상 수용, 올바른 보정, 거부/확인
요청을 함께 둔다. 기대값은 달력에서 손으로 셌다.
"""

import json
import os
import unittest
from datetime import date, datetime, timezone

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from geoflow import conditions  # noqa: E402
from geoflow.composer import MacroComposer  # noqa: E402
from geoflow.errors import CompilerError, PlannerError  # noqa: E402
from geoflow.grounding import parse_grounding  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline  # noqa: E402
from geoflow.planner import GeoFlowPlanner  # noqa: E402
from tests.test_geoflow_aggregation_graph import (  # noqa: E402
    DAEGU,
    FakeTims,
    event,
    measure,
    place,
)

REF = date(2026, 9, 25)


def reconcile(factors, question, *, concepts=None, reference=REF):
    payload = {"concepts": concepts or [event("operation"), measure("revenue")],
               "factors": dict(factors)}
    return conditions.reconcile_payload(payload, question, reference_date=reference)


def date_of(question, factors=None, reference=REF):
    fixed, audit = reconcile(factors or {}, question, reference=reference)
    return fixed["factors"].get("date"), audit["date"]


class DateInterpretationTest(unittest.TestCase):
    def test_relative_tokens_and_recorded_interpretation(self):
        value, record = date_of("지난달 평균 수입은?")
        self.assertEqual(value, "last_month")
        self.assertEqual(record["interpreted_range"], "20260801-20260831")
        self.assertEqual(record["mentions"][0]["text"], "지난달")
        value, record = date_of("지난주 평균 수입은?")
        self.assertEqual((value, record["interpreted_range"]),
                         ("last_week", "20260914-20260920"))
        value, record = date_of("작년 평균 수입은?")
        self.assertEqual((value, record["interpreted_range"]), ("last_year", "20250101-20251231"))

    def test_month_and_year_boundaries(self):
        _, record = date_of("지난달 수입은?", reference=date(2026, 1, 10))
        self.assertEqual(record["interpreted_range"], "20251201-20251231")
        # 2026-01-01은 목요일. 직전 주는 2025-12-22(월)~28(일)이다.
        _, record = date_of("지난주 수입은?", reference=date(2026, 1, 1))
        self.assertEqual(record["interpreted_range"], "20251222-20251228")
        value, _ = date_of("어제 수입은?", reference=date(2026, 1, 1))
        self.assertEqual(value, "20251231")

    def test_leap_years(self):
        _, record = date_of("지난달 수입은?", reference=date(2024, 3, 15))
        self.assertEqual(record["interpreted_range"], "20240201-20240229")
        self.assertEqual(date_of("2024년 2월 수입은?")[0], "20240201-20240229")
        self.assertEqual(date_of("2023년 2월 수입은?")[0], "20230201-20230228")
        with self.assertRaises(PlannerError) as caught:
            date_of("2025년 2월 29일 수입은?")
        self.assertEqual(caught.exception.code, "DATE_EXPRESSION_UNSUPPORTED")

    def test_kst_midnight(self):
        before = conditions.seoul_date(datetime(2026, 8, 31, 14, 30, tzinfo=timezone.utc))
        after = conditions.seoul_date(datetime(2026, 8, 31, 15, 30, tzinfo=timezone.utc))
        self.assertEqual((before, after), (date(2026, 8, 31), date(2026, 9, 1)))
        self.assertEqual(date_of("지난달 수입은?", reference=before)[1]["interpreted_range"],
                         "20260701-20260731")
        self.assertEqual(date_of("지난달 수입은?", reference=after)[1]["interpreted_range"],
                         "20260801-20260831")
        with self.assertRaises(ValueError):
            conditions.seoul_date(datetime(2026, 9, 1, 0, 30))

    def test_explicit_forms(self):
        cases = {
            "2026년 5월 30일 평균 속도는?": "20260530",
            "2026년 8월 한 달간 수입은?": "20260801-20260831",
            "2026년 7월부터 8월까지 수입은?": "20260701-20260831",
            "2026년 7월과 8월 중 수입이 더 많은 달은?": "20260701-20260831",
            "2026년 5월 1일부터 7일까지 요금은?": "20260501-20260507",
            "2026년 상반기 수입은?": "20260101-20260630",
            "20260801-20260810 수입은?": "20260801-20260810",
        }
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertEqual(date_of(question)[0], expected)

    def test_bucket_words_are_not_dates(self):
        value, record = date_of("월별 영업 시간 합계의 평균은?")
        self.assertIsNone(value)
        self.assertEqual(record["mentions"], [])
        self.assertIsNone(date_of("주 단위로 합산한 수입의 평균은?")[0])

    def test_recent_periods_are_not_normalized_to_calendar_tokens(self):
        for question in ("최근 한 달 수입은?", "최근 7일 수입은?", "최근 일주일 수입은?",
                         "지난 3개월 수입은?", "이번 달 수입은?", "추석 연휴 수입은?"):
            with self.subTest(question=question):
                with self.assertRaises(PlannerError) as caught:
                    date_of(question, {"date": "last_month"})
                self.assertEqual(caught.exception.code, "DATE_EXPRESSION_UNSUPPORTED")
        self.assertEqual(date_of("지난주 수입은?")[0], "last_week")

    def test_yearless_date_needs_clarification(self):
        with self.assertRaises(PlannerError) as caught:
            date_of("8월 수입은?", {"date": "20260801-20260831"})
        self.assertEqual(caught.exception.code, "DATE_AMBIGUOUS")
        self.assertTrue(caught.exception.context["needs_clarification"])

    def test_relative_and_explicit_conflict_is_not_resolved_silently(self):
        with self.assertRaises(PlannerError) as caught:
            date_of("지난달인 2026년 5월 수입은?")
        self.assertEqual(caught.exception.code, "DATE_CONFLICT")
        with self.assertRaises(PlannerError) as caught:
            date_of("지난주와 지난달 중 수입이 많은 쪽은?")
        self.assertEqual(caught.exception.code, "DATE_MULTIPLE_UNSUPPORTED")

    def test_llm_absolute_date_for_relative_expression_is_corrected(self):
        value, record = date_of("지난달 대구 수입은?", {"date": "20260501-20260531"})
        self.assertEqual(value, "last_month")
        self.assertEqual((record["action"], record["llm_value"]), ("corrected", "20260501-20260531"))

    def test_llm_month_format_error_is_corrected_before_validation(self):
        """flat 관측(e05 등)에서 '202608'이 date 형식 검사로 grounding 전체를 거부시켰다."""
        value, record = date_of("2026년 8월 한 달간 서울 영업 시간은?", {"date": "202608"})
        self.assertEqual(value, "20260801-20260831")
        self.assertEqual(record["action"], "corrected")

    def test_correct_date_is_accepted_unchanged(self):
        value, record = date_of("지난달 수입은?", {"date": "last_month"})
        self.assertEqual((value, record["action"]), ("last_month", "confirmed"))

    def test_date_without_evidence_is_removed(self):
        value, record = date_of("대구 평균 수입은?", {"date": "last_week"})
        self.assertIsNone(value)
        self.assertEqual(record["action"], "removed_no_evidence")

    def test_no_date_is_not_generated(self):
        value, record = date_of("대구 평균 수입은?")
        self.assertIsNone(value)
        self.assertEqual(record["action"], "none")


class TaxiTypeTest(unittest.TestCase):
    def taxi(self, question, llm=None):
        factors = {} if llm is None else {"taxi_type": llm}
        fixed, audit = reconcile(factors, question)
        return fixed["factors"].get("taxi_type"), audit["taxi_type"]

    def test_missing_private_is_filled_from_the_question(self):
        self.assertEqual(self.taxi("지난달 수성구 개인택시 평균 수입은?")[0], "private")
        self.assertEqual(self.taxi("법인 택시 평균 수입은?")[0], "corporate")
        self.assertEqual(self.taxi("회사택시 평균 수입은?")[0], "corporate")

    def test_changed_or_widened_value_is_corrected(self):
        value, record = self.taxi("개인택시 평균 수입은?", "corporate")
        self.assertEqual((value, record["action"]), ("private", "corrected"))
        self.assertEqual(self.taxi("개인택시 평균 수입은?", "all")[0], "private")

    def test_added_corporate_without_evidence_is_removed(self):
        value, record = self.taxi("대구 평균 수입은?", "corporate")
        self.assertIsNone(value)
        self.assertEqual(record["action"], "removed_no_evidence")

    def test_explicit_all_and_unspecified_are_distinct(self):
        self.assertEqual(self.taxi("전체 택시 평균 수입은?")[0], "all")
        value, record = self.taxi("평균 수입은?")
        self.assertIsNone(value)
        self.assertEqual(record["action"], "none")

    def test_negation_and_comparison_are_unsupported_not_flipped(self):
        for question in ("개인택시를 제외한 택시의 평균 수입은?",
                         "개인택시와 법인택시의 평균 수입은?"):
            with self.subTest(question=question):
                with self.assertRaises(PlannerError) as caught:
                    self.taxi(question, "private")
                self.assertEqual(caught.exception.code, "TAXI_TYPE_EXPRESSION_UNSUPPORTED")

    def test_correct_value_is_accepted(self):
        self.assertEqual(self.taxi("개인택시 수입은?", "private")[1]["action"], "confirmed")
        # census q18. 예전 어휘는 "개인용 택시"를 못 읽어 맞는 값을 지웠다.
        self.assertEqual(self.taxi("개인용 택시의 요일별 택시 수입 분포는?", "private")[0],
                         "private")

    def test_unrecognized_cue_keeps_the_llm_value(self):
        value, record = self.taxi("개인 사업자 택시 수입은?", "private")
        self.assertEqual((value, record["action"]), ("private", "unverified"))


class PlaceEvidenceTest(unittest.TestCase):
    def check(self, question, concepts):
        return conditions.check_places(concepts, question)

    def test_exact_and_normalized_names_are_accepted(self):
        exact = self.check("대구 평균 수입은?", [place("p", "대구")])
        self.assertEqual(exact[0]["evidence"], "exact")
        # 조회명이 질문 표현보다 긴 정규화(수성 → 수성구). 문자열 불일치로 거부하지 않는다.
        normalized = dict(place("p", "수성구"), text="수성")
        records = self.check("수성 지역 평균 수입은?", [normalized])
        self.assertEqual((records[0]["evidence"], records[0]["text"], records[0]["lookup_name"]),
                         ("normalized", "수성", "수성구"))
        # 조회명이 질문 표현 안에 있으면(대구시 → 대구) 그대로 근거가 있다.
        self.assertEqual(self.check("대구시 평균 수입은?",
                                    [dict(place("p", "대구"), text="대구시")])[0]["evidence"],
                         "exact")

    def test_place_not_in_question_needs_clarification(self):
        with self.assertRaises(PlannerError) as caught:
            self.check("수성구 평균 수입은?", [place("p", "부산")])
        self.assertEqual(caught.exception.code, "PLACE_NOT_IN_QUESTION")
        self.assertEqual(caught.exception.context["clarify"], "place")

    def test_od_roles_are_preserved(self):
        origin = dict(place("a", "동성로"), attributes={"od_role": "pickup"})
        destination = dict(place("b", "신천동"), attributes={"od_role": "dropoff"})
        records = self.check("동성로에서 출발하여 신천동에 도착한 건수는?", [origin, destination])
        self.assertEqual([r["od_role"] for r in records], ["pickup", "dropoff"])


class ReconcileScopeTest(unittest.TestCase):
    def test_only_date_and_taxi_type_change(self):
        concepts = [place("p", "대구"), event("operation"), measure("revenue")]
        factors = {"date": "20260501-20260531", "aggregation_plan": {
            "bucket": {"unit": "week", "reducer": "sum"}, "result": {"select": "max"}}}
        fixed, audit = reconcile(factors, "지난달 대구 개인택시 매출 합계가 가장 큰 주는?",
                                 concepts=concepts)
        self.assertEqual(fixed["concepts"], concepts)
        self.assertEqual(fixed["factors"]["aggregation_plan"], factors["aggregation_plan"])
        self.assertEqual(fixed["factors"]["date"], "last_month")
        self.assertEqual(fixed["factors"]["taxi_type"], "private")
        self.assertEqual({c["condition"] for c in audit["corrections"]}, {"date", "taxi_type"})


# -- pipeline -------------------------------------------------------------------


class _Client:
    model = "scripted"

    def __init__(self, responses):
        self.responses = list(responses)

    def chat(self, messages, tools=None, **kwargs):
        return {"message": {"content": json.dumps(self.responses.pop(0), ensure_ascii=False)}}


def pipeline(responses, *, check, mode="structured"):
    return GeoFlowPipeline.create(client=_Client(responses), tool_executor=FakeTims(),
                                  aggregation_grounding=mode, clock=lambda: REF,
                                  condition_check=check)


WRONG_DATE_NO_TAXI = {"concepts": [place("place", "대구"), event("operation"),
                                   measure("revenue")],
                      "factors": {"date": "20260501-20260531",
                                  "aggregation_plan": {"result": {"reducer": "avg"}}}}
QUESTION = "지난달 대구 개인택시 평균 매출은?"


class PipelineTest(unittest.TestCase):
    def test_default_path_is_unchanged(self):
        run = pipeline([WRONG_DATE_NO_TAXI], check=False).run(QUESTION)
        self.assertIsNone(run.condition_audit)
        args = [hop["arguments"] for hop in run.hop_log if hop["tool"] == "get_operation_metrics"]
        self.assertEqual(args[0]["date"], "20260501-20260531")
        self.assertNotIn("taxi_type", args[0])

    def test_condition_check_carries_question_conditions_to_the_call(self):
        run = pipeline([WRONG_DATE_NO_TAXI], check=True).run(QUESTION)
        self.assertEqual(run.outcome, "answered", run.runtime_error)
        (args,) = [hop["arguments"] for hop in run.hop_log
                   if hop["tool"] == "get_operation_metrics"]
        self.assertEqual((args["date"], args["taxi_type"], args["scope"]),
                         ("last_month", "private", DAEGU))
        trace = {row["condition"]: row for row in run.condition_trace}
        self.assertEqual(trace["date"]["text"], ["지난달"])
        self.assertEqual(trace["date"]["calls"][0]["argument"], "last_month")
        self.assertEqual(trace["taxi_type"]["action"], "filled")
        self.assertEqual(trace["place"]["calls"][0]["argument"], "대구")
        self.assertIn("적용 조건", run.final_answer)
        self.assertIn("LLM 값 20260501-20260531을 질문 표현으로 바로잡음", run.final_answer)
        self.assertIn("TIMS의 해석과 같다는 보장은 없음", run.final_answer)

    def test_partitioned_calls_keep_the_interpreted_period(self):
        payload = {"concepts": [place("place", "대구"), event("operation"), measure("revenue")],
                   "factors": {"date": "20260401-20260430", "taxi_type": "private",
                               "aggregation_plan": {"bucket": {"unit": "week", "reducer": "sum"},
                                                    "result": {"select": "max"}}}}
        run = pipeline([payload], check=True).run("지난달 대구 개인택시 매출 합계가 가장 큰 주는?")
        self.assertEqual(run.outcome, "answered", run.runtime_error)
        dates = [hop["arguments"]["date"] for hop in run.hop_log
                 if hop["tool"] == "get_operation_metrics"]
        self.assertEqual((dates[0], dates[-1], len(dates)), ("20260801", "20260831", 31))

    def test_correct_grounding_is_executed_without_corrections(self):
        payload = {"concepts": [place("place", "대구"), event("operation"), measure("revenue")],
                   "factors": {"date": "last_month", "taxi_type": "private",
                               "aggregation_plan": {"result": {"reducer": "avg"}}}}
        run = pipeline([payload], check=True).run(QUESTION)
        self.assertEqual(run.outcome, "answered")
        self.assertEqual(run.condition_audit["corrections"], [])

    def test_flat_month_format_error_now_executes(self):
        payload = {"concepts": [place("place", "대구"), event("operation"), measure("revenue")],
                   "factors": {"date": "202608", "aggregation": "avg"}}
        off = pipeline([payload], check=False, mode="flat").run("2026년 8월 한 달간 대구 평균 수입은?")
        on = pipeline([payload], check=True, mode="flat").run("2026년 8월 한 달간 대구 평균 수입은?")
        self.assertEqual(off.error["code"], "INVALID_FACTOR")
        self.assertEqual(on.outcome, "answered", on.runtime_error)

    def test_unsupported_date_expression_is_reported_not_guessed(self):
        payload = dict(WRONG_DATE_NO_TAXI, factors={"date": "last_month"})
        run = pipeline([payload], check=True).run("최근 한 달 대구 개인택시 평균 매출은?")
        self.assertEqual(run.outcome, "unsupported")
        self.assertEqual(run.error["code"], "DATE_EXPRESSION_UNSUPPORTED")

    def test_fabricated_place_needs_clarification(self):
        payload = {"concepts": [place("place", "부산"), event("operation"), measure("revenue")],
                   "factors": {"date": "last_month"}}
        run = pipeline([payload], check=True, mode="flat").run("지난달 수성구 평균 수입은?")
        self.assertEqual(run.outcome, "needs_clarification")
        self.assertEqual(run.error["code"], "PLACE_NOT_IN_QUESTION")

    def test_place_repair_keeps_evidence_history_and_aggregation(self):
        from geoflow.repair import PlaceValuePatch, apply_patch
        planner = GeoFlowPlanner(client=_Client([dict(WRONG_DATE_NO_TAXI)]),
                                 aggregation_grounding="structured", condition_check=True,
                                 clock=lambda: REF)
        grounding = planner.plan("지난달 대구 개인택시 평균 매출은?").grounding
        repaired = apply_patch(grounding, PlaceValuePatch("place", "대구광역시", ""))
        self.assertEqual(repaired.aggregation, grounding.aggregation)
        self.assertEqual(repaired.factors["taxi_type"], "private")
        record = repaired.condition_audit["places"][0]
        self.assertEqual(record["history"][0]["from"]["name"], "대구")
        self.assertEqual(record["lookup_name"], "대구광역시")
        self.assertEqual(grounding.condition_audit["places"][0]["lookup_name"], "대구")

    def test_lost_condition_is_detected_before_execution(self):
        plan = MacroComposer().compose(parse_grounding(
            {"concepts": [event("operation"), measure("revenue")],
             "factors": {"date": "last_month"}}, "지난달 수입은?"))
        from geoflow.compiler import compile_plan
        execution = compile_plan(plan, reference_date=REF)
        audit = {"date": {"value": "last_month", "mentions": []},
                 "taxi_type": {"value": "private", "mentions": []}, "places": []}
        with self.assertRaises(CompilerError) as caught:
            conditions.trace(plan, execution, audit)
        self.assertEqual(caught.exception.code, "CONDITION_LOST")


if __name__ == "__main__":
    unittest.main()
