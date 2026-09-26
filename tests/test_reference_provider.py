# -*- coding: utf-8 -*-
"""reference provider 위에서 의미 graph → 실행 계획 → 실제 계산 → 답변을 끝까지 검증한다.

기대값은 두 가지 독립 근거로 정한다.
1. 손으로 센 값(아래 상수와 evaluation/design/reference_provider.md의 표).
2. ``reference_data/expected_results.sql``을 SQLite로 CSV에 돌린 값.
provider(``reference_provider``)나 compiler·로컬 연산의 집계 함수로 기대값을 만들지 않는다.
LLM을 부르지 않는다(정답 grounding을 대본으로 넣는다).
"""

import copy
import csv
import json
import os
import re
import sqlite3
import unittest
from datetime import date
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from geoflow import tims_contract  # noqa: E402
from geoflow.compiler import DATE_POLICY_GUARANTEED, compile_plan, verify_lowering  # noqa: E402
from geoflow.composer import MacroComposer  # noqa: E402
from geoflow.errors import CompilerError, GeoFlowError  # noqa: E402
from geoflow.executor import execute_plan  # noqa: E402
from geoflow.grounding import parse_grounding  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline  # noqa: E402
from geoflow.providers import (  # noqa: E402
    MOCK, REFERENCE, REFERENCE_CONTRACT, STRICT, profile_for,
)
from tests.test_geoflow_composition import TOOLS  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402
from tool_handlers import get_tool_handlers  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "reference_data" / "synthetic_operation_days.csv"
SQL_PATH = ROOT / "reference_data" / "expected_results.sql"
REF_DATE = date(2026, 9, 25)
GARAM, NARAE = "scope:ref:district:garam", "scope:ref:district:narae"

# -- 손으로 센 기대값(가람구 개인택시, 2026년 8월) ---------------------------------
# 결측 아닌 레코드 12개(r02~r07, r09~r14; r08은 매출 결측), 합계 1,240,000.
# 주(월요일 시작, 8월 경계에서 자름)와 주별 (레코드 수, 합계, 평균):
WEEKS = ["20260801-20260802", "20260803-20260809", "20260810-20260816",
         "20260817-20260823", "20260824-20260830", "20260831-20260831"]
GARAM_PRIVATE_WEEKS = [(1, 100000, 100000), (3, 300000, 100000), (2, 300000, 150000),
                       (4, 280000, 70000), (1, 200000, 200000), (1, 60000, 60000)]
Q1_OVERALL_AVG = 1240000 / 12          # 103,333.33… 전체 평균(분모 = 레코드 12개)
Q2_AVG_OF_WEEKLY_SUMS = 1240000 / 6    # 206,666.66… 주별 합계 6개의 평균
Q3_MAX_OF_WEEKLY_AVGS = 200000         # 20260824-20260830
Q4_MAX_WEEKLY_SUM = 300000             # 20260803-20260809, 20260810-20260816 동률
MEAN_OF_WEEKLY_AVGS = 680000 / 6       # 113,333.33… 전체 평균과 다르다
# 변형
GARAM_CORPORATE_AVG = (50000 + 70000 + 40000 + 90000) / 4      # 62,500
GARAM_ALL_AVG = (1240000 + 250000) / 16                          # 93,125
NARAE_PRIVATE_AVG = 350000 / 7                                   # 50,000
NARAE_AVG_OF_WEEKLY_SUMS = 350000 / 6
NARAE_MAX_OF_WEEKLY_AVGS = 70000                                 # 20260817-20260823
NARAE_MAX_WEEKLY_SUM = 100000                                    # 20260810-20260816 단독
GARAM_PRIVATE_AUG_1_15_AVG = 700000 / 6                          # r02~r07


# -- 대본 grounding --------------------------------------------------------------


class _Client:
    model = "scripted"

    def __init__(self, responses):
        self.responses = list(responses)

    def chat(self, messages, tools=None, **kwargs):
        return {"message": {"content": json.dumps(self.responses.pop(0), ensure_ascii=False)}}


def grounding(aggregation, *, where="가람구", period="last_month", taxi="private"):
    concepts = [
        {"id": "place", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
         "source": "user", "value": {"name": where}},
        {"id": "operation", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
         "source": "implicit"},
        {"id": "revenue", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
         "source": "implicit"},
    ]
    factors = {"date": period, "aggregation_plan": aggregation}
    if taxi:
        factors["taxi_type"] = taxi
    return {"concepts": concepts, "factors": factors}


OVERALL_AVG = {"result": {"reducer": "avg"}}
SUM_THEN_AVG = {"bucket": {"unit": "week", "reducer": "sum"}, "result": {"reducer": "avg"}}
AVG_THEN_MAX = {"bucket": {"unit": "week", "reducer": "avg"}, "result": {"reducer": "max"}}
SUM_SELECT_MAX = {"bucket": {"unit": "week", "reducer": "sum"}, "result": {"select": "max"}}
AVG_THEN_AVG = {"bucket": {"unit": "week", "reducer": "avg"}, "result": {"reducer": "avg"}}
TOTAL_SUM = {"result": {"reducer": "sum"}}


def reference_executor():
    return ToolExecutor(tools=TOOLS, handlers=get_tool_handlers(REFERENCE), provider=REFERENCE)


def run(aggregation, question="질문", *, profile=None, executor=None, **where):
    pipeline = GeoFlowPipeline.create(
        client=_Client([grounding(aggregation, **where)]),
        tool_executor=executor or reference_executor(),
        aggregation_grounding="structured", clock=lambda: REF_DATE,
        execution_profile=profile or profile_for(REFERENCE))
    return pipeline.run(question)


def compiled(aggregation, *, contract=REFERENCE_CONTRACT, **where):
    plan = MacroComposer().compose(parse_grounding(
        grounding(aggregation, **where), "질문", structured_aggregation=True))
    return plan, compile_plan(plan, reference_date=REF_DATE, contract=contract,
                              date_policy=DATE_POLICY_GUARANTEED)


def measure_calls(result_run):
    return [hop for hop in result_run.hop_log if hop.get("tool") == "get_operation_metrics"]


def local_rows(result_run, operator):
    return next(hop["result"] for hop in result_run.hop_log if hop.get("operator") == operator)


# -- 1. 독립 기준 결과(SQL) --------------------------------------------------------


def sql_statements():
    text = SQL_PATH.read_text(encoding="utf-8")
    return {name: body.strip() for name, body in
            re.findall(r"-- name: (\w+)\n(?:--[^\n]*\n)*(.*?;)", text, flags=re.S)}


def sql_db():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE ops (record_id, taxi_id, service_date, closed_at, scope, "
               "taxi_type, revenue_krw INTEGER)")
    with open(CSV_PATH, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            row["revenue_krw"] = int(row["revenue_krw"]) if row["revenue_krw"] else None
            db.execute("INSERT INTO ops VALUES (?,?,?,?,?,?,?)", [
                row[k] for k in ("record_id", "taxi_id", "service_date", "closed_at", "scope",
                                 "taxi_type", "revenue_krw")])
    return db


class SqlReferenceTest(unittest.TestCase):
    """손으로 센 값과 독립 SQL의 값이 같은지. 둘 다 제품 코드를 쓰지 않는다."""

    @classmethod
    def setUpClass(cls):
        cls.db, cls.sql = sql_db(), sql_statements()

    def query(self, name, scope=GARAM, taxi="private", start="2026-08-01", end="2026-08-31"):
        return self.db.execute(self.sql[name], {"scope": scope, "taxi_type": taxi,
                                                "start": start, "end": end}).fetchall()

    def test_overall_statistics(self):
        self.assertEqual(self.query("overall")[0][:2], (12, 1240000))
        self.assertAlmostEqual(self.query("overall")[0][2], Q1_OVERALL_AVG)
        self.assertAlmostEqual(self.query("overall", taxi="corporate")[0][2], GARAM_CORPORATE_AVG)
        self.assertAlmostEqual(self.query("overall", taxi="all")[0][2], GARAM_ALL_AVG)
        self.assertAlmostEqual(self.query("overall", scope=NARAE)[0][2], NARAE_PRIVATE_AVG)
        self.assertAlmostEqual(self.query("overall", end="2026-08-15")[0][2],
                               GARAM_PRIVATE_AUG_1_15_AVG)

    def test_weekly_statistics(self):
        rows = self.query("weeks")
        self.assertEqual([row[0] for row in rows], WEEKS)
        self.assertEqual([tuple(row[1:3]) for row in rows],
                         [(n, total) for n, total, _ in GARAM_PRIVATE_WEEKS])
        self.assertEqual([row[3] for row in rows], [mean for *_, mean in GARAM_PRIVATE_WEEKS])
        corporate = self.query("weeks", taxi="corporate")
        self.assertEqual([row[1] for row in corporate], [0, 1, 2, 0, 1, 0])  # 빈 주 3개


# -- 2. 대표 질문 네 개 ------------------------------------------------------------


class RepresentativeQuestionsTest(unittest.TestCase):
    def test_q1_overall_average(self):
        result = run(OVERALL_AVG, "지난달 가람구 개인택시 전체 매출 평균은?")
        self.assertEqual(result.outcome, "answered", result.runtime_error)
        self.assertAlmostEqual(result.hop_log[-1]["result"], Q1_OVERALL_AVG)
        (call,) = measure_calls(result)
        # 상대 기간은 pipeline이 기준일로 풀고 reference에는 명시 범위(양 끝 포함)로 보낸다.
        self.assertEqual(call["arguments"], {"metric": "revenue", "scope": GARAM,
                                             "date": "20260801-20260831",
                                             "taxi_type": "private", "aggregation": "avg"})
        (record,) = result.execution_plan["date_semantics"].values()
        self.assertEqual((record["lowering"], record["provider"]), ("explicit_range", "confirmed"))
        self.assertIn("103,333.333", result.final_answer)
        self.assertIn("합성 데이터", result.final_answer)
        self.assertIn("reference provider", result.final_answer)

    def test_q2_average_of_weekly_sums(self):
        result = run(SUM_THEN_AVG, "지난달 가람구 개인택시 주별 매출 합계의 평균은?")
        self.assertEqual(result.outcome, "answered", result.runtime_error)
        operators = [t["operator"] for t in result.plan["transformations"]]
        self.assertEqual(operators, ["RESOLVE_PLACE_SCOPE", "OPERATION_METRIC", "REDUCE_GROUPS"])
        self.assertEqual(result.execution_plan["lowering"]["measure_groups"]["strategy"],
                         "range_partition")
        rows = local_rows(result, "COLLECT_GROUPS")
        self.assertEqual([row["group"]["label"] for row in rows], WEEKS)
        self.assertEqual([row["value"] for row in rows],
                         [total for _, total, _ in GARAM_PRIVATE_WEEKS])
        self.assertAlmostEqual(result.hop_log[-1]["result"], Q2_AVG_OF_WEEKLY_SUMS)
        self.assertIn("주별 합계의 평균: 206,666.667", result.final_answer)

    def test_q3_max_of_weekly_averages(self):
        result = run(AVG_THEN_MAX, "지난달 가람구 개인택시 주별 매출 평균의 최댓값은?")
        self.assertEqual(result.outcome, "answered", result.runtime_error)
        rows = local_rows(result, "COLLECT_GROUPS")
        self.assertEqual([row["value"] for row in rows],
                         [mean for *_, mean in GARAM_PRIVATE_WEEKS])
        self.assertEqual(result.hop_log[-1]["result"], Q3_MAX_OF_WEEKLY_AVGS)
        # 구간 안 집계는 각 주의 범위 호출에서 reference가 계산한다(일별 평균을 다시 평균하지 않음).
        self.assertTrue(all(call["arguments"]["aggregation"] == "avg"
                            for call in measure_calls(result)))
        self.assertIn("주별 평균의 최댓값: 200,000", result.final_answer)

    def test_q4_week_with_largest_sum_returns_both_tied_weeks(self):
        result = run(SUM_SELECT_MAX, "지난달 가람구 개인택시 매출 합계가 가장 큰 주는?")
        self.assertEqual(result.outcome, "answered", result.runtime_error)
        value = result.hop_log[-1]["result"]
        self.assertEqual(value["value"], Q4_MAX_WEEKLY_SUM)
        self.assertEqual([group["label"] for group in value["groups"]], WEEKS[1:3])
        self.assertIn("(동률)", result.final_answer)
        # 값(300,000)과 그 값을 가진 주를 구분해 답한다.
        self.assertIn("20260803-20260809, 20260810-20260816 (동률), 300,000",
                      result.final_answer)

    def test_conditions_reach_every_measure_call(self):
        for aggregation in (OVERALL_AVG, SUM_THEN_AVG, AVG_THEN_MAX, SUM_SELECT_MAX):
            result = run(aggregation)
            calls = measure_calls(result)
            with self.subTest(aggregation=aggregation):
                self.assertTrue(calls)
                for call in calls:
                    arguments = call["arguments"]
                    self.assertEqual((arguments["scope"], arguments["taxi_type"]),
                                     (GARAM, "private"))
                    start, _, end = arguments["date"].partition("-")
                    self.assertTrue("20260801" <= start <= (end or start) <= "20260831")

    def test_verification_summary_uses_the_reference_contract(self):
        pipeline = GeoFlowPipeline.create(
            client=_Client([grounding(SUM_SELECT_MAX)]), tool_executor=reference_executor(),
            aggregation_grounding="structured", clock=lambda: REF_DATE, condition_check=True,
            execution_profile=profile_for(REFERENCE))
        result = pipeline.run("지난달 가람구 개인택시 매출 합계가 가장 큰 주는?")
        self.assertEqual(result.outcome, "answered", result.runtime_error)
        self.assertEqual(result.verification["contract"], REFERENCE)
        self.assertEqual(result.verification["verified"], ["date", "taxi_type"])
        self.assertIn("reference provider 계약으로 확인: 기간, 택시 유형", result.final_answer)
        self.assertNotIn("TIMS 문서 계약", result.final_answer)
        # 같은 질문을 TIMS legacy로 돌리면 가정한 하루 분할이라 기간은 미검증이다.
        from tests.test_geoflow_aggregation_graph import FakeTims
        legacy = GeoFlowPipeline.create(
            client=_Client([grounding(SUM_SELECT_MAX, where="대구")]), tool_executor=FakeTims(),
            aggregation_grounding="structured", clock=lambda: REF_DATE,
            condition_check=True).run("지난달 대구 개인택시 매출 합계가 가장 큰 주는?")
        self.assertEqual(legacy.outcome, "answered", legacy.runtime_error)
        self.assertEqual(legacy.verification["contract"], "tims")
        self.assertNotIn("date", legacy.verification["verified"])

    def test_trace_maps_semantic_steps_to_calls_and_local_operations(self):
        result = run(SUM_SELECT_MAX)
        semantic_map = result.execution_plan["semantic_map"]
        self.assertEqual(semantic_map["resolve_scope"], ["resolve_scope"])
        self.assertEqual(semantic_map["measure_groups"],
                         [f"measure_groups#{i}" for i in range(1, 7)] + ["measure_groups.collect"])
        self.assertEqual(semantic_map["combine_groups"], ["combine_groups"])
        phases = [(hop["step_id"], hop["phase"]) for hop in result.hop_log]
        self.assertEqual(phases[0], ("resolve_scope", "tool"))
        self.assertEqual(phases[-2:], [("measure_groups.collect", "local"),
                                       ("combine_groups", "local")])
        self.assertEqual(result.execution_profile["provider"], REFERENCE)


# -- 3. 조건 변화와 의미 차이 ------------------------------------------------------


class VariationTest(unittest.TestCase):
    def value(self, aggregation, **where):
        result = run(aggregation, **where)
        self.assertEqual(result.outcome, "answered", result.runtime_error)
        return result.hop_log[-1]["result"]

    def test_private_corporate_and_all_differ(self):
        self.assertAlmostEqual(self.value(OVERALL_AVG, taxi="corporate"), GARAM_CORPORATE_AVG)
        self.assertAlmostEqual(self.value(OVERALL_AVG, taxi="all"), GARAM_ALL_AVG)
        self.assertAlmostEqual(self.value(OVERALL_AVG, taxi=None), GARAM_ALL_AVG)

    def test_region_changes_every_answer(self):
        self.assertAlmostEqual(self.value(OVERALL_AVG, where="나래구"), NARAE_PRIVATE_AVG)
        self.assertAlmostEqual(self.value(SUM_THEN_AVG, where="나래구"), NARAE_AVG_OF_WEEKLY_SUMS)
        self.assertEqual(self.value(AVG_THEN_MAX, where="나래구"), NARAE_MAX_OF_WEEKLY_AVGS)
        selected = self.value(SUM_SELECT_MAX, where="나래구")
        self.assertEqual((selected["value"], [g["label"] for g in selected["groups"]]),
                         (NARAE_MAX_WEEKLY_SUM, ["20260810-20260816"]))

    def test_date_range_changes_the_result_and_breaks_the_tie(self):
        self.assertAlmostEqual(self.value(OVERALL_AVG, period="20260801-20260815"),
                               GARAM_PRIVATE_AUG_1_15_AVG)
        # 8/4부터면 둘째 주가 잘려 합계 100,000이 되고 셋째 주만 남는다.
        selected = self.value(SUM_SELECT_MAX, period="20260804-20260831")
        self.assertEqual((selected["value"], [g["label"] for g in selected["groups"]]),
                         (300000, ["20260810-20260816"]))

    def test_overall_average_differs_from_average_of_weekly_averages(self):
        overall = self.value(OVERALL_AVG)
        of_weeks = self.value(AVG_THEN_AVG)
        self.assertAlmostEqual(overall, Q1_OVERALL_AVG)
        self.assertAlmostEqual(of_weeks, MEAN_OF_WEEKLY_AVGS)
        self.assertNotAlmostEqual(overall, of_weeks)


# -- 4. 계약 정책 -----------------------------------------------------------------


class PolicyTest(unittest.TestCase):
    def test_partial_weeks_are_marked(self):
        result = run(SUM_THEN_AVG)
        complete = [row["group"]["complete"] for row in local_rows(result, "COLLECT_GROUPS")]
        self.assertEqual(complete, [False, True, True, True, True, False])
        self.assertIn("20260801-20260802(부분 구간)", result.final_answer)

    def test_empty_week_is_a_structured_failure_not_zero(self):
        result = run(SUM_THEN_AVG, taxi="corporate")
        self.assertEqual(result.error["code"], "EMPTY_GROUP_VALUE")
        self.assertIsNone(result.final_answer)

    def test_empty_period_returns_null_and_is_reported(self):
        result = run(OVERALL_AVG, taxi="corporate", period="20260801-20260802")
        self.assertEqual(result.outcome, "answered", result.runtime_error)
        self.assertIsNone(result.hop_log[-1]["result"])
        self.assertIn("결과 없음", result.final_answer)

    def test_service_date_not_closing_time_decides_the_day(self):
        # r02: 영업일 8/1, 종료 8/2 01:10. 8/2 하루에는 들어가지 않는다.
        self.assertIsNone(run(TOTAL_SUM, period="20260802").hop_log[-1]["result"])
        self.assertEqual(run(TOTAL_SUM, period="20260801").hop_log[-1]["result"], 100000)

    def test_missing_revenue_is_excluded_from_the_denominator(self):
        # 셋째 주: r06·r07(150,000씩)과 결측 r08. 평균 분모는 2다.
        result = run(OVERALL_AVG, period="20260810-20260816")
        self.assertEqual(result.hop_log[-1]["result"], 150000)


class DecompositionEquivalenceTest(unittest.TestCase):
    """직접 집계와 분해 실행은 계약상 동등할 때만 비교한다."""

    NO_RANGE = tims_contract.TimsContract(
        {**REFERENCE_CONTRACT.items,
         "range_inclusive": tims_contract.ITEMS["range_inclusive"]},  # 범위 계약을 뺀 변형
        provider="reference-without-range")

    def execute(self, aggregation, contract):
        _, execution = compiled(aggregation, contract=contract)
        result = execute_plan(execution, reference_executor())
        self.assertEqual(result.status, "OK", result.error)
        return execution, result.final_value

    def test_range_and_daily_partition_agree_for_sum(self):
        ranged, by_range = self.execute(SUM_THEN_AVG, REFERENCE_CONTRACT)
        daily, by_day = self.execute(SUM_THEN_AVG, self.NO_RANGE)
        self.assertEqual(ranged.lowering["measure_groups"]["strategy"], "range_partition")
        self.assertEqual(daily.lowering["measure_groups"]["strategy"], "daily_partition")
        self.assertAlmostEqual(by_range, by_day)
        self.assertAlmostEqual(by_range, Q2_AVG_OF_WEEKLY_SUMS)
        self.assertEqual(len(daily.tool_steps), 1 + 31)

    def test_empty_days_are_skipped_only_under_a_confirmed_null_contract(self):
        from geoflow.compiler import empty_day_policy
        self.assertEqual(empty_day_policy(REFERENCE_CONTRACT), "skip")
        self.assertEqual(empty_day_policy(tims_contract.DEFAULT_CONTRACT), "fail")
        daily, _ = self.execute(SUM_THEN_AVG, self.NO_RANGE)
        collect = next(s for s in daily.steps if s.operator == "COLLECT_GROUPS")
        self.assertEqual(collect.arguments["empty_parts"], "skip")
        # 계약을 바꿔 빈 날 처리를 몰래 skip으로 두면 검증에서 막힌다.
        # TIMS legacy 경로(하루 분할을 가정으로 실행)에서도 빈 날은 멈춘다.
        plan = MacroComposer().compose(parse_grounding(
            grounding(SUM_THEN_AVG, where="대구"), "질문", structured_aggregation=True))
        execution = compile_plan(plan, reference_date=REF_DATE)
        collect = next(s for s in execution.steps if s.operator == "COLLECT_GROUPS")
        self.assertEqual(collect.arguments["empty_parts"], "fail")
        collect.arguments["empty_parts"] = "skip"
        with self.assertRaises(CompilerError):
            verify_lowering(plan, execution, reference_date=REF_DATE)

    def test_single_range_sum_equals_sum_of_weekly_sums(self):
        _, total = self.execute(TOTAL_SUM, REFERENCE_CONTRACT)
        self.assertEqual(total, sum(t for _, t, _ in GARAM_PRIVATE_WEEKS))

    def test_weekly_average_is_not_rebuilt_from_daily_values(self):
        with self.assertRaises(CompilerError) as caught:
            compiled(AVG_THEN_MAX, contract=self.NO_RANGE)
        self.assertEqual(caught.exception.code, "UNVERIFIED_TIMS_CONTRACT")


class TamperDetectionTest(unittest.TestCase):
    """잘못된 조건 전달이나 단계 뒤바뀜은 실행 전에 거부된다."""

    def verify(self, plan, execution):
        verify_lowering(plan, execution, reference_date=REF_DATE, contract=REFERENCE_CONTRACT)

    def test_untouched_plan_passes(self):
        self.verify(*compiled(SUM_THEN_AVG))

    def tampered(self, mutate):
        plan, execution = compiled(SUM_THEN_AVG)
        execution = copy.deepcopy(execution)
        mutate(execution)
        with self.assertRaises(CompilerError) as caught:
            self.verify(plan, execution)
        return caught.exception.code

    def test_dropped_taxi_type_in_one_week(self):
        def mutate(execution):
            execution.tool_steps[3].arguments.pop("taxi_type")
        self.assertEqual(self.tampered(mutate), "LOWERING_MISMATCH")

    def test_wrong_week_range(self):
        def mutate(execution):
            execution.tool_steps[2].arguments["date"] = "20260803-20260810"
        self.assertEqual(self.tampered(mutate), "LOWERING_MISMATCH")

    def test_swapped_inner_and_outer_reducers(self):
        def mutate(execution):
            for step in execution.tool_steps[1:]:
                step.arguments["aggregation"] = "avg"
            next(s for s in execution.steps if s.operator == "REDUCE_GROUPS").arguments[
                "reducer"] = "sum"
        self.assertEqual(self.tampered(mutate), "LOWERING_MISMATCH")

    def test_wrong_region(self):
        plan, execution = compiled(OVERALL_AVG)
        execution = copy.deepcopy(execution)
        execution.tool_steps[-1].arguments["taxi_type"] = "corporate"
        with self.assertRaises(CompilerError):
            self.verify(plan, execution)


# -- 5. 계약 격리와 provider 전환 --------------------------------------------------


class ContractIsolationTest(unittest.TestCase):
    def test_reference_contract_is_separate_and_quoted(self):
        self.assertEqual(tims_contract.evidence_problems(REFERENCE_CONTRACT), [])
        self.assertEqual(tims_contract.evidence_problems(), [])
        self.assertEqual(REFERENCE_CONTRACT.provider, REFERENCE)
        self.assertEqual(tims_contract.DEFAULT_CONTRACT.provider, "tims")
        self.assertTrue(REFERENCE_CONTRACT.satisfied("range_inclusive"))

    def test_tims_items_stay_unconfirmed(self):
        expected = {"range_inclusive": "observed", "relative_date_reference": "unknown",
                    "bucket_week_start": "unknown", "bucket_empty": "unknown",
                    "null_result": "unknown", "day_records:get_operation_metrics": "observed"}
        for key, status in expected.items():
            with self.subTest(key=key):
                self.assertEqual(tims_contract.DEFAULT_CONTRACT.status(key), status)
                self.assertEqual(tims_contract.ITEMS[key].status, status)

    def test_mock_profiles_use_the_tims_contract(self):
        for mode in ("legacy", STRICT):
            self.assertIs(profile_for(MOCK, mode).contract, tims_contract.DEFAULT_CONTRACT)
        with self.assertRaises(ValueError):
            profile_for("unknown")

    def test_strict_tims_does_not_get_reference_range_calls(self):
        from tests.test_geoflow_aggregation_graph import FakeTims
        pipeline = GeoFlowPipeline.create(
            client=_Client([grounding(SUM_THEN_AVG, where="대구")]), tool_executor=FakeTims(),
            aggregation_grounding="structured", clock=lambda: REF_DATE,
            execution_profile=profile_for(MOCK, STRICT))
        result = pipeline.run("질문")
        self.assertEqual(result.error["code"], "UNVERIFIED_TIMS_CONTRACT")
        self.assertIn("range_inclusive", result.error["detail"])


class ProviderSwitchTest(unittest.TestCase):
    def test_profile_must_match_the_executor_provider(self):
        mock_executor = ToolExecutor(tools=TOOLS, handlers=get_tool_handlers(MOCK), provider=MOCK)
        with self.assertRaises(GeoFlowError) as caught:
            GeoFlowPipeline.create(client=_Client([]), tool_executor=mock_executor,
                                   execution_profile=profile_for(REFERENCE))
        self.assertEqual(caught.exception.code, "PROVIDER_PROFILE_MISMATCH")

    def test_handlers_are_fresh_and_results_do_not_leak(self):
        first = get_tool_handlers(MOCK)
        first["get_operation_metrics"] = lambda arguments: 0
        self.assertIsNot(get_tool_handlers(MOCK)["get_operation_metrics"],
                         first["get_operation_metrics"])
        before = run(SUM_THEN_AVG).hop_log[-1]["result"]
        from tests.test_geoflow_composition import new_tool_executor
        mock_run = GeoFlowPipeline.create(
            client=_Client([grounding(OVERALL_AVG, where="대구")]),
            tool_executor=new_tool_executor(), aggregation_grounding="structured",
            clock=lambda: REF_DATE).run("질문")
        self.assertEqual(mock_run.execution_profile["provider"], MOCK)
        self.assertNotIn("합성 데이터", mock_run.final_answer or "")
        after = run(SUM_THEN_AVG).hop_log[-1]["result"]
        self.assertEqual(before, after)

    def test_unsupported_tools_and_arguments_are_not_sent_to_mock(self):
        executor = reference_executor()
        speed = executor.execute("get_passage_metrics", {"metric": "speed", "scope": GARAM})
        self.assertEqual(speed["error_code"], "UNSUPPORTED_BY_PROVIDER")
        listed = executor.execute("get_operation_metrics", {
            "metric": "revenue", "scope": GARAM, "dimension": "dayofweek"})
        self.assertEqual(listed["error_code"], "UNSUPPORTED_BY_PROVIDER")
        relative = executor.execute("get_operation_metrics", {
            "metric": "revenue", "scope": GARAM, "date": "last_month"})
        self.assertEqual(relative["error_code"], "UNSUPPORTED_BY_PROVIDER")
        hours = executor.execute("get_operation_metrics", {"metric": "hours", "scope": GARAM})
        self.assertEqual(hours["error_code"], "UNSUPPORTED_BY_PROVIDER")
        unknown = executor.execute("get_place_scope", {"name": "수성구"})
        self.assertEqual(unknown["error_code"], "NOT_FOUND")

    def test_unsupported_measure_is_an_unsupported_outcome(self):
        concepts = [
            {"id": "place", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
             "source": "user", "value": {"name": "가람구"}},
            {"id": "operation", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
             "source": "implicit"},
            {"id": "hours", "concept": "AMOUNT", "subtype": "hours", "role": "MEASURE",
             "source": "implicit"},
        ]
        payload = {"concepts": concepts, "factors": {
            "date": "20260801", "aggregation_plan": {"result": {"reducer": "sum"}}}}
        result = GeoFlowPipeline.create(
            client=_Client([payload]), tool_executor=reference_executor(),
            aggregation_grounding="structured", clock=lambda: REF_DATE,
            execution_profile=profile_for(REFERENCE)).run("질문")
        self.assertEqual((result.outcome, result.error["code"]),
                         ("unsupported", "UNSUPPORTED_BY_PROVIDER"))



class CliProfileTest(unittest.TestCase):
    """CLI는 provider 환경 변수와 --tims-execution으로 실행 프로필을 만든다."""

    def runtime(self, provider, mode):
        import assistant_cli
        from unittest import mock
        with mock.patch.dict(os.environ, {"ASSISTANT_TOOL_PROVIDER": provider}), \
                mock.patch.object(assistant_cli, "AGENT_MODE", assistant_cli.AGENT_MODE_GEOFLOW), \
                mock.patch.object(assistant_cli, "TIMS_EXECUTION", mode):
            return assistant_cli._new_runtime(TOOLS, "system")

    def test_reference_provider_gets_the_reference_profile(self):
        runtime = self.runtime(REFERENCE, "legacy")
        profile = runtime.geoflow.execution_profile
        self.assertEqual((profile.provider, profile.contract.provider, profile.mode),
                         (REFERENCE, REFERENCE, None))

    def test_mock_modes(self):
        self.assertEqual(self.runtime(MOCK, "legacy").geoflow.execution_profile.mode, "legacy")
        self.assertEqual(self.runtime(MOCK, STRICT).geoflow.execution_profile.mode, STRICT)


if __name__ == "__main__":
    unittest.main()
