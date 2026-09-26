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
from geoflow.providers import MOCK, STRICT, profile_for  # noqa: E402
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

    def test_unrecognized_cue_holds_the_llm_value_without_verifying_it(self):
        value, record = self.taxi("개인 사업자 택시 수입은?", "private")
        self.assertEqual((value, record["action"], record["status"]),
                         ("private", "held", "unverifiable"))
        self.assertNotIn(record["status"], conditions.VERIFIED_STATUSES)

    def test_type_cue_without_value_is_flagged_not_declared_absent(self):
        value, record = self.taxi("영업용 택시 수입은?")
        self.assertIsNone(value)
        self.assertEqual((record["status"], record["action"]), ("unverifiable", "flagged"))

    def test_explicit_all_keeps_provenance_without_counting_as_correction(self):
        fixed, audit = reconcile({}, "전체 택시 평균 수입은?")
        record = audit["taxi_type"]
        self.assertEqual((record["value"], record["stated"], record["action"]),
                         ("all", "explicit_all", "confirmed_equivalent"))
        self.assertEqual(audit["corrections"], [])
        _, audit = reconcile({}, "평균 수입은?")
        self.assertEqual(audit["taxi_type"]["stated"], "not_stated")


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


STRICT_TIMS = profile_for(MOCK, STRICT)


def pipeline(responses, *, check, mode="structured", profile=None):
    """실행 계약은 profile이 정한다(기본 mock + legacy). condition_check는 해석 옵션이다."""
    return GeoFlowPipeline.create(client=_Client(responses), tool_executor=FakeTims(),
                                  aggregation_grounding=mode, clock=lambda: REF,
                                  condition_check=check, execution_profile=profile)


WRONG_DATE_NO_TAXI = {"concepts": [place("place", "대구"), event("operation"),
                                   measure("revenue")],
                      "factors": {"date": "20260501-20260531",
                                  "aggregation_plan": {"result": {"reducer": "avg"}}}}
QUESTION = "지난달 대구 개인택시 평균 매출은?"


class PipelineTest(unittest.TestCase):
    def test_condition_check_does_not_change_the_execution_contract(self):
        """condition_check는 해석 옵션이다. 같은 프로필이면 켜든 끄든 기간 정책이 같다."""
        payload = {"concepts": [place("place", "대구"), event("operation"), measure("revenue")],
                   "factors": {"date": "last_month", "taxi_type": "private",
                               "aggregation_plan": {"result": {"reducer": "avg"}}}}
        for profile in (None, STRICT_TIMS):
            runs = [pipeline([payload], check=check, profile=profile).run(QUESTION)
                    for check in (False, True)]
            policies = {run.execution_profile["date_policy"] for run in runs}
            outcomes = {run.outcome for run in runs}
            with self.subTest(profile=None if profile is None else profile.mode):
                self.assertEqual(len(policies), 1)
                self.assertEqual(len(outcomes), 1)
        legacy = pipeline([payload], check=True).run(QUESTION)
        self.assertEqual(legacy.outcome, "answered", legacy.runtime_error)
        self.assertEqual(legacy.execution_profile["mode"], "legacy")
        # legacy는 토큰을 가정으로 넘긴다. 검증 요약은 기간을 검증으로 적지 않는다.
        self.assertNotIn("date", legacy.verification["verified"])
        self.assertIn("relative_date_reference", legacy.execution_profile["legacy_assumptions"])


    def test_default_path_is_unchanged(self):
        run = pipeline([WRONG_DATE_NO_TAXI], check=False).run(QUESTION)
        self.assertIsNone(run.condition_audit)
        args = [hop["arguments"] for hop in run.hop_log if hop["tool"] == "get_operation_metrics"]
        self.assertEqual(args[0]["date"], "20260501-20260531")
        self.assertNotIn("taxi_type", args[0])

    def test_condition_check_stops_when_relative_date_semantics_are_unverified(self):
        """strict TIMS 프로필에서. 이전 구현은 '지난달'을 KST 범위로 풀어 기록하면서 TIMS에는 last_month를 넘기고,
        답변 문구("보장 없음")만 붙여 정상 실행했다. 계약이 없으면 실행하지 않는다."""
        run = pipeline([WRONG_DATE_NO_TAXI], check=True, profile=STRICT_TIMS).run(QUESTION)
        self.assertEqual(run.outcome, "unsupported")
        self.assertEqual(run.error["code"], "DATE_EXECUTION_UNVERIFIED")
        record = run.error["context"]["date_semantics"]
        self.assertEqual((record["value"], record["interpreted_range"], record["provider"]),
                         ("last_month", "20260801-20260831", "unverified"))
        self.assertIn("relative_date_reference", record["missing"])
        # 질문 해석(보정)은 기록에 남는다. 측정 호출은 한 번도 나가지 않았다.
        self.assertEqual(run.condition_audit["date"]["action"], "corrected")
        self.assertEqual(run.condition_audit["taxi_type"]["action"], "filled")
        self.assertFalse([hop for hop in run.hop_log
                          if hop.get("tool") == "get_operation_metrics"])
        self.assertIsNone(run.final_answer)

    def test_single_day_is_executed_with_confirmed_semantics(self):
        payload = {"concepts": [place("place", "대구"), event("operation"), measure("revenue")],
                   "factors": {"date": "20260823", "aggregation_plan": {"result": {"reducer": "sum"}}}}
        run = pipeline([payload], check=True).run("어제 대구 개인택시 매출 합계는?")
        self.assertEqual(run.outcome, "answered", run.runtime_error)
        (args,) = [hop["arguments"] for hop in run.hop_log
                   if hop["tool"] == "get_operation_metrics"]
        # 기준일 2026-09-25의 어제. LLM 값 20260823은 질문 표현으로 바로잡혔다.
        self.assertEqual((args["date"], args["taxi_type"], args["scope"]),
                         ("20260924", "private", DAEGU))
        trace = {row["condition"]: row for row in run.condition_trace}
        self.assertEqual(trace["date"]["provider"], ["confirmed"])
        self.assertEqual(trace["place"]["calls"][0]["argument"], "대구")
        summary = run.verification
        self.assertEqual(summary["verified"], ["date", "taxi_type"])
        self.assertIn("place", summary["unverified"])
        self.assertFalse(summary["complete"])
        self.assertIn("LLM 값 20260823을 질문 표현으로 바로잡음", run.final_answer)
        self.assertIn("장소는 이름 근거만 확인", run.final_answer)
        self.assertNotIn("보장은 없음", run.final_answer)

    def test_partitioned_calls_need_the_day_record_contract(self):
        """구간별 집계의 하루 단위 합성은 기록이 하루에만 속한다는 계약이 필요하다.
        legacy 프로필은 이를 가정으로 적고 실행하지만, strict 프로필은 멈춘다."""
        payload = {"concepts": [place("place", "대구"), event("operation"), measure("revenue")],
                   "factors": {"date": "20260401-20260430", "taxi_type": "private",
                               "aggregation_plan": {"bucket": {"unit": "week", "reducer": "sum"},
                                                    "result": {"select": "max"}}}}
        question = "지난달 대구 개인택시 매출 합계가 가장 큰 주는?"
        run = pipeline([payload], check=True, profile=STRICT_TIMS).run(question)
        self.assertEqual(run.outcome, "unsupported")
        self.assertEqual(run.error["code"], "UNVERIFIED_TIMS_CONTRACT")
        self.assertIn("day_records:get_operation_metrics", run.error["detail"])
        legacy = pipeline([dict(payload, factors=dict(payload["factors"], date="last_month"))],
                          check=False).run(question)
        self.assertEqual(legacy.outcome, "answered", legacy.runtime_error)

    def test_correct_grounding_is_accepted_without_corrections(self):
        payload = {"concepts": [place("place", "대구"), event("operation"), measure("revenue")],
                   "factors": {"date": "20260924", "taxi_type": "private",
                               "aggregation_plan": {"result": {"reducer": "avg"}}}}
        run = pipeline([payload], check=True).run("2026년 9월 24일 대구 개인택시 평균 매출은?")
        self.assertEqual(run.outcome, "answered", run.runtime_error)
        self.assertEqual(run.condition_audit["corrections"], [])
        self.assertEqual(run.condition_audit["date"]["status"], "interpreted")

    def test_flat_month_format_error_is_interpreted_but_range_is_not_executed(self):
        payload = {"concepts": [place("place", "대구"), event("operation"), measure("revenue")],
                   "factors": {"date": "202608", "aggregation": "avg"}}
        question = "2026년 8월 한 달간 대구 평균 수입은?"
        off = pipeline([payload], check=False, mode="flat").run(question)
        on = pipeline([payload], check=True, mode="flat", profile=STRICT_TIMS).run(question)
        self.assertEqual(off.error["code"], "INVALID_FACTOR")
        # 형식 오류는 질문 표현으로 바로잡지만, 범위 양 끝 포함이 계약에 없고 avg는
        # 하루 값으로 합칠 수 없으므로 실행하지 않는다.
        self.assertEqual(on.condition_audit["date"]["value"], "20260801-20260831")
        self.assertEqual(on.error["code"], "DATE_EXECUTION_UNVERIFIED")
        self.assertIn("avg", on.error["context"]["reason"])

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


# -- 해석 · 요청 인자 · provider 의미의 분리 ------------------------------------


from geoflow import tims_contract  # noqa: E402
from geoflow.compiler import DATE_POLICY_GUARANTEED, compile_plan  # noqa: E402
from geoflow.executor import execute_plan  # noqa: E402

ASSUMED_DAY_RECORDS = tims_contract.DEFAULT_CONTRACT.assuming(
    **{"day_records:get_operation_metrics": "택시·일 기록"})


def compiled(factors, question, *, contract=tims_contract.DEFAULT_CONTRACT,
             concepts=None, reference=REF):
    grounding = parse_grounding(
        {"concepts": concepts or [place("place", "대구"), event("operation"),
                                  measure("revenue")],
         "factors": factors}, question)
    plan = MacroComposer().compose(grounding)
    return plan, compile_plan(plan, reference_date=reference, contract=contract,
                              date_policy=DATE_POLICY_GUARANTEED)


class ReferenceInstantTest(unittest.TestCase):
    def test_same_instant_in_other_timezones_gives_the_same_last_month(self):
        """'지난달'은 요청 시각을 Asia/Seoul 날짜로 바꾼 뒤 푼다. 기대값은 손으로 셌다."""
        from zoneinfo import ZoneInfo
        instant_utc = datetime(2026, 8, 31, 16, 0, tzinfo=timezone.utc)   # KST 9/1 01:00
        instant_la = instant_utc.astimezone(ZoneInfo("America/Los_Angeles"))  # 8/31 09:00
        for instant in (instant_utc, instant_la):
            with self.subTest(tz=str(instant.tzinfo)):
                reference = conditions.seoul_date(instant)
                self.assertEqual(reference, date(2026, 9, 1))
                self.assertEqual(date_of("지난달 수입은?", reference=reference)[1]
                                 ["interpreted_range"], "20260801-20260831")
        # 같은 KST 날짜 안에서는 시각이 달라도 같다. 날짜가 바뀌면 달라진다.
        self.assertEqual(date_of("지난달 수입은?", reference=date(2026, 9, 30))[1]
                         ["interpreted_range"], "20260801-20260831")
        self.assertEqual(date_of("지난달 수입은?", reference=date(2026, 10, 1))[1]
                         ["interpreted_range"], "20260901-20260930")


class DateArgumentSemanticsTest(unittest.TestCase):
    def test_only_single_day_is_confirmed_by_the_default_contract(self):
        expected = {"20260924": "confirmed", "20260801-20260831": "unverified",
                    "last_month": "unverified", "weekend": "unverified",
                    None: "not_requested"}
        for value, status in expected.items():
            with self.subTest(value=value):
                self.assertEqual(tims_contract.date_argument_semantics(value)["status"], status)

    def test_provider_reference_that_differs_from_local_interpretation_is_not_accepted(self):
        utc_calendar = tims_contract.DEFAULT_CONTRACT.assuming(
            relative_date_reference="UTC calendar")
        semantics = tims_contract.date_argument_semantics("last_month", utc_calendar)
        self.assertEqual(semantics["status"], "unverified")
        with self.assertRaises(CompilerError) as caught:
            compiled({"date": "last_month", "aggregation": "avg"}, "지난달 대구 평균 수입은?",
                     contract=utc_calendar)
        self.assertEqual(caught.exception.code, "DATE_EXECUTION_UNVERIFIED")
        seoul = tims_contract.DEFAULT_CONTRACT.assuming(
            relative_date_reference="Asia/Seoul calendar")
        _, execution = compiled({"date": "last_month", "aggregation": "avg"},
                                "지난달 대구 평균 수입은?", contract=seoul)
        (step,) = execution.tool_steps[-1:]
        self.assertEqual(step.arguments["date"], "last_month")

    def test_no_explicit_range_substitution_without_range_contract(self):
        with self.assertRaises(CompilerError) as caught:
            compiled({"date": "last_month", "aggregation": "avg"}, "지난달 대구 평균 수입은?")
        record = caught.exception.context["date_semantics"]
        self.assertEqual(record["request"], ["last_month"])
        self.assertEqual(record["lowering"], "passthrough")
        ranged = tims_contract.DEFAULT_CONTRACT.assuming(range_inclusive="inclusive")
        _, execution = compiled({"date": "last_month", "aggregation": "avg"},
                                "지난달 대구 평균 수입은?", contract=ranged)
        call = execution.tool_steps[-1]
        self.assertEqual(call.arguments["date"], "20260801-20260831")
        record = next(iter(execution.date_semantics.values()))
        self.assertEqual((record["lowering"], record["provider"]),
                         ("explicit_range", "confirmed"))

    def test_legacy_policy_records_but_does_not_enforce(self):
        grounding = parse_grounding(
            {"concepts": [place("place", "대구"), event("operation"), measure("revenue")],
             "factors": {"date": "last_month", "aggregation": "avg"}}, "지난달 대구 평균 수입은?")
        execution = compile_plan(MacroComposer().compose(grounding), reference_date=REF)
        record = next(iter(execution.date_semantics.values()))
        self.assertEqual((record["request"], record["provider"], record["policy"]),
                         (["last_month"], "unverified", "legacy"))


class DailyCompositionTest(unittest.TestCase):
    def test_composable_and_non_composable_aggregations(self):
        allowed = ASSUMED_DAY_RECORDS
        for reducer in ("sum", "max", "min"):
            self.assertTrue(tims_contract.daily_composition(
                "get_operation_metrics", reducer, contract=allowed)[0], reducer)
        for reducer in ("avg", "med", None):
            ok, reason, _ = tims_contract.daily_composition(
                "get_operation_metrics", reducer, contract=allowed)
            self.assertFalse(ok, reducer)
            self.assertIn("다시 만들 수 없습니다", reason)
        # 목록 결과, 호출 상한, 데이터 계약.
        self.assertFalse(tims_contract.daily_composition(
            "get_operation_metrics", "sum", grouped_arguments=("dimension",),
            contract=allowed)[0])
        self.assertFalse(tims_contract.daily_composition(
            "get_operation_metrics", "sum", days=63, contract=allowed)[0])
        ok, reason, _ = tims_contract.daily_composition("get_operation_metrics", "sum")
        self.assertFalse(ok)
        self.assertIn("day_records:get_operation_metrics", reason)
        # 개수 Tool(합)도 trip의 날짜 귀속이 계약에 없으면 합치지 않는다.
        self.assertFalse(tims_contract.daily_composition(
            "get_trip_count", "sum", contract=allowed)[0])

    def test_daily_sum_under_assumed_contract_matches_hand_computed_total(self):
        plan, execution = compiled(
            {"date": "last_month", "taxi_type": "private", "aggregation": "sum"},
            "지난달 대구 개인택시 매출 합계는?", contract=ASSUMED_DAY_RECORDS)
        calls = [step for step in execution.tool_steps
                 if step.tool_name == "get_operation_metrics"]
        self.assertEqual([step.arguments["date"] for step in calls],
                         [f"202608{day:02d}" for day in range(1, 32)])
        self.assertTrue(all(step.arguments["taxi_type"] == "private" for step in calls))
        result = execute_plan(execution, FakeTims())
        self.assertEqual(result.status, "OK", result.error)
        # 31일 × 10 + (300 + 80×4 + 190 + 30). 법인·부산·범위 밖 날짜는 빠진다.
        self.assertEqual(result.final_value, 1150)

    def test_average_is_not_composed_even_with_the_day_contract(self):
        with self.assertRaises(CompilerError) as caught:
            compiled({"date": "last_month", "aggregation": "avg"}, "지난달 대구 평균 매출은?",
                     contract=ASSUMED_DAY_RECORDS)
        self.assertEqual(caught.exception.code, "DATE_EXECUTION_UNVERIFIED")
        self.assertIn("avg", caught.exception.context["reason"])


class UnverifiableConditionTest(unittest.TestCase):
    def test_leftover_date_cue_holds_the_llm_value(self):
        value, record = date_of("지난달 15일 대구 수입은?", {"date": "20260815"})
        self.assertEqual(value, "20260815")
        self.assertEqual((record["status"], record["action"], record["partial_interpretation"]),
                         ("unverifiable", "held", "last_month"))

    def test_calendar_position_beside_relative_word_is_not_read_as_the_whole_period(self):
        for question in ("지난주 금요일 대구 수입은?", "지난달 말 대구 수입은?"):
            with self.subTest(question=question):
                value, record = date_of(question, {"date": "20260918"})
                self.assertEqual((value, record["status"]), ("20260918", "unverifiable"))

    def test_llm_date_with_anchor_in_question_is_not_deleted(self):
        # "9/24"는 지원 문법 밖이지만 LLM 값의 숫자 근거가 질문에 있다.
        value, record = date_of("9/24 대구 수입은?", {"date": "20260924"})
        self.assertEqual((value, record["status"]), ("20260924", "unverifiable"))

    def test_date_cue_without_any_value_is_flagged(self):
        value, record = date_of("지난 금요일 대구 수입은?")
        self.assertIsNone(value)
        self.assertEqual((record["status"], record["action"]), ("unverifiable", "flagged"))

    def test_held_values_are_listed_and_not_verified(self):
        payload = {"concepts": [place("place", "대구"), event("operation"), measure("revenue")],
                   "factors": {"date": "20260924", "taxi_type": "private", "aggregation": "sum"}}
        run = pipeline([payload], check=True, mode="flat").run("9/24 대구 개인 사업자 택시 매출 합계는?")
        self.assertEqual(run.outcome, "answered", run.runtime_error)
        self.assertEqual({item["condition"] for item in run.condition_audit["held"]},
                         {"date", "taxi_type"})
        self.assertEqual(run.verification["verified"], [])
        self.assertIn("현재 문법으로 검증하지 못한 LLM 값", run.final_answer)


class PlaceCompletenessTest(unittest.TestCase):
    def test_one_of_two_places_output_is_not_detected_and_not_reported_complete(self):
        origin = dict(place("a", "대구"), attributes={"od_role": "pickup"})
        records = conditions.check_places([origin], "대구에서 출발해 부산에 도착한 건수는?")
        self.assertEqual(len(records), 1)  # 누락을 탐지하지 못한다(한계).
        payload = {"concepts": [place("place", "대구"), event("operation"), measure("revenue")],
                   "factors": {"date": "20260924", "aggregation": "sum"}}
        run = pipeline([payload], check=True, mode="flat").run(
            "2026년 9월 24일 대구와 부산 매출 합계는?")
        self.assertEqual(run.outcome, "answered", run.runtime_error)
        self.assertFalse(run.verification["complete"])
        self.assertEqual(run.verification["conditions"]["place"]["completeness"], "unchecked")
        self.assertIn("place", run.verification["unverified"])
        self.assertIn("누락은 미검증", run.final_answer)


if __name__ == "__main__":
    unittest.main()
