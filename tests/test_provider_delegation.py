# -*- coding: utf-8 -*-
"""업체 Tool 위임 경로와 GeoFlow 로컬 재계산 경로의 책임 분리.

LLM을 부르지 않는다. 업체 100문항의 정답 grounding(``evaluate_vendor100.derive_grounding``)과
mock provider로 본다.

- 위임: 질문의 두 단계 집계를 bucket/aggregation/rollup으로 온전히 옮길 수 있으면 호출한다.
  질문이 정하지 않은 구간 정의는 제공자에게 맡기고 그 사실을 기록한다(43, 98, 100).
- 로컬: 분해 전후 동등성의 근거(계약·수학 조건)가 없으면 쓰지 않는다. 위임 가능 여부와 무관하다.
- 질문이 정의를 명시하면 그 정의를 보장하는 경로만 쓴다. 제공자 기본값으로 바꾸지 않는다.
"""

import os
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

import yaml

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import evaluate_vendor100 as V  # noqa: E402
from geoflow import calendar_terms, providers, tims_contract  # noqa: E402
from geoflow.compiler import compile_plan  # noqa: E402
from geoflow.composer import MacroComposer  # noqa: E402
from geoflow.errors import CompilerError, CompositionError  # noqa: E402
from geoflow.grounding import parse_grounding  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
REF = date(2026, 9, 25)
GOLD = {item["id"]: item for item in V.load_gold()["items"]}
VENDOR = {"043": {"metric": "active_taxi_ratio", "date": "this_month", "taxi_type": "corporate",
                  "aggregation": "avg", "bucket": "week", "rollup": "min"},
          "098": {"metric": "operating_days", "date": "last_month", "taxi_type": "private",
                  "aggregation": "avg", "bucket": "week", "rollup": "med",
                  "scope": "scope:district:2700000000"},
          "100": {"metric": "revenue", "date": "last_year", "taxi_type": "corporate",
                  "aggregation": "sum", "bucket": "month", "rollup": "max",
                  "scope": "scope:district:2700000000"}}
#: 로컬 재계산 근거(하루 기록 귀속, 범위 양 끝 포함)를 가정한 계약. 계약 근거가 아니다.
LOCAL_EVIDENCE = tims_contract.DEFAULT_CONTRACT.assuming(
    range_inclusive="inclusive", **{"day_records:get_billing_metrics": "택시·일"})


def plan_for(number, question=None):
    item = GOLD[number]
    grounding = parse_grounding(V.derive_grounding(item["gold"]), question or item["question"])
    return MacroComposer().compose(grounding)


def run_gold(number, question=None, profile=None):
    item = GOLD[number]
    pipeline = V._pipeline(V._GoldPlanner(V.derive_grounding(item["gold"])))
    if profile is not None:
        pipeline.execution_profile = profile
    return V.run_item(pipeline, question or item["question"])


class CalendarTermsTest(unittest.TestCase):
    def test_closed_vocabulary(self):
        cases = {
            "일요일부터 시작하는 주별 합계": {"week_start": "sunday"},
            "주 시작은 화요일로": {"week_start": "tuesday"},
            "월요일 기준 주별": {"week_start": "monday"},
            "온전한 주만": {"partial": "exclude"},
            "부분 주는 제외": {"partial": "exclude"},
            "잘린 달도 포함": {"partial": "include"},
            "자료가 없는 주는 0으로": {"empty": "zero"},
            "빈 주는 빼고": {"empty": "skip"},
        }
        for text, stated in cases.items():
            with self.subTest(text=text):
                self.assertEqual(calendar_terms.read(text).stated, stated)

    def test_conflicting_or_unreadable_definitions_are_not_guessed(self):
        both = calendar_terms.read("일요일 시작 주와 월요일 시작 주로")
        self.assertEqual(both.stated, {})
        self.assertEqual(len(both.unreadable), 2)
        self.assertEqual(calendar_terms.read("주 시작 기준이 뭐든").unreadable, ("주 시작 기준",))

    def test_no_vendor_question_states_a_definition(self):
        """업체 100문항은 구간 정의를 말하지 않는다. 모두 제공자 정의에 맡길 수 있다."""
        questions = yaml.load((BASE_DIR / "assistant_univ_questions_100_v3.yaml").read_text(
            encoding="utf-8"), Loader=yaml.BaseLoader)
        self.assertEqual(len(questions), 100)
        self.assertFalse([q["id"] for q in questions if calendar_terms.read(q["question"])])

    def test_ordinary_weekday_ranges_are_not_definitions(self):
        """"주차", "주행", "주말", 도로 "구간"은 구간 정의가 아니다."""
        for text in ("월요일부터 금요일까지 평균 속도", "지난 주 평균 운행 일수", "주중 오후 6시",
                     "주말 부산 광안동에서 출발", "일부 구간의 평균 속도", "부분 구간 통행 속도",
                     "일부 구간을 제외한 통행량", "일부 주차장 제외한 승차 건수", "지난달 빈 주차면 수",
                     "이번 주 시작부터 오늘까지 매출 합계", "월요일 기준 주차 수요",
                     "금요일 시작 주말 매출", "화요일에 시작한 주행"):
            with self.subTest(text=text):
                self.assertFalse(calendar_terms.read(text))


class VendorDelegationTest(unittest.TestCase):
    """43·98·100: 업체 정답 호출 그대로, 제공자에게 맡긴 의미가 기록된다."""

    def test_representative_questions_call_the_vendor_contract(self):
        for number, expected in VENDOR.items():
            with self.subTest(number=number):
                observed = run_gold(number)
                self.assertEqual(observed["outcome"], "answered", observed["error_code"])
                final = observed["calls"][-1]
                self.assertEqual(final["tool"], "get_billing_metrics")
                self.assertEqual(final["args"], expected)
                (lowering,) = observed["lowering"].values()
                self.assertEqual(lowering["path"], tims_contract.PATH_PROVIDER)
                self.assertEqual(lowering["requires"],
                                 ["inner_is_aggregation", "rollup_unweighted"])
                self.assertIn("relative_date", lowering["delegated"])
                self.assertEqual("week_start" in lowering["delegated"],
                                 expected["bucket"] == "week")
                self.assertIn("provider_calculation", lowering["not_verified"][0])
                self.assertIn("TIMS 기준을 따릅니다", observed["final_answer"])
                category, checks = V.score(GOLD[number], observed)
                self.assertEqual(category, "match", checks)

    def test_stage_roles_are_not_swapped(self):
        """98 업체 지적: 택시별 평균(aggregation=avg)과 주별 중간값(rollup=med)을 뒤바꾸지 않는다."""
        final = run_gold("098")["calls"][-1]["args"]
        self.assertEqual((final["aggregation"], final["rollup"]), ("avg", "med"))

    def test_the_same_questions_are_not_recomputed_locally(self):
        """로컬 재계산은 위임과 별개로 판정한다. 근거를 가정해도 수학적으로 안 되는 것은 막는다."""
        reasons = {}
        for number in ("043", "098"):
            with self.subTest(number=number):
                contract = tims_contract.DEFAULT_CONTRACT.assuming(
                    **{"day_records:get_billing_metrics": "택시·일"})
                with self.assertRaises(CompilerError) as caught:
                    compile_plan(plan_for(number), reference_date=REF, contract=contract,
                                 delegation=False)
                reasons[number] = {item["strategy"]: item["reason"]
                                   for item in caught.exception.context.get("rejected", [])}
        # 43: 가동률(집단 비율)의 구간 평균은 하루 값으로 다시 만들 수 없다.
        self.assertIn("avg", reasons["043"]["daily_partition"])
        # 98: 운행일수 평균(택시별 기간 집계의 평균)도 하루 값으로 다시 만들 수 없다.
        self.assertIn("avg", reasons["098"]["daily_partition"])
        # 100: 합계는 다시 만들 수 있지만 1년 365번 호출은 상한을 넘는다(아래 테스트).
        for number in ("043", "098"):
            self.assertIn("range_inclusive", reasons[number]["range_partition"])
            self.assertIn("위임을 허용하지 않는 프로필", reasons[number]["fused_bucket_rollup"])

    def test_long_period_local_recomputation_is_bounded(self):
        with self.assertRaises(CompilerError) as caught:
            compile_plan(plan_for("100"), reference_date=REF, delegation=False,
                         contract=tims_contract.DEFAULT_CONTRACT.assuming(
                             **{"day_records:get_billing_metrics": "택시·일"}))
        self.assertEqual(caught.exception.code, "UNSUPPORTED_PARTITION_SIZE")

    def test_range_evidence_enables_a_different_claim(self):
        """범위 계약이 있으면 43을 주마다 범위 호출해 로컬에서 최솟값을 구할 수 있다. 이것은
        애플리케이션 주 정의(월요일 시작)로 계산한 다른 주장이며 위임 결과와 같다고 보지 않는다."""
        execution = compile_plan(plan_for("043"), reference_date=REF, contract=LOCAL_EVIDENCE,
                                 delegation=False)
        (lowering,) = execution.lowering.values()
        self.assertEqual((lowering["strategy"], lowering["path"]),
                         ("range_partition", tims_contract.PATH_LOCAL))
        self.assertEqual(lowering["semantics"]["week_start"],
                         {"value": "monday", "source": "application"})
        self.assertEqual(lowering["semantics"]["relative_date"]["source"], "application")
        (detail,) = execution.periods.values()
        self.assertEqual(detail["groups"], ["20260901-20260906", "20260907-20260913",
                                            "20260914-20260920", "20260921-20260925"])
        delegated = compile_plan(plan_for("043"), reference_date=REF, contract=LOCAL_EVIDENCE)
        self.assertEqual(next(iter(delegated.lowering.values()))["path"],
                         tims_contract.PATH_PROVIDER)

    def test_strict_profile_does_not_delegate(self):
        observed = run_gold("043", profile=providers.profile_for(providers.MOCK, providers.STRICT))
        self.assertEqual(observed["outcome"], "unsupported")
        rejected = observed["error_context"]["rejected"]
        self.assertEqual(rejected[0]["path"], tims_contract.PATH_PROVIDER)
        self.assertIn("위임을 허용하지 않는 프로필", rejected[0]["reason"])


class StatedRequirementTest(unittest.TestCase):
    """사용자가 정의를 명시하면 Tool·계약이 보장할 때만 위임한다."""

    Q43_SUNDAY = "이번 달 법인택시의 일요일부터 시작하는 주별 평균 가동률 중 가장 낮은 값은?"

    def test_every_stated_variant_behaves_as_registered(self):
        document = yaml.safe_load(V.VARIANTS_FILE.read_text(encoding="utf-8"))
        for variant in document["variants"]:
            with self.subTest(variant=variant["id"]):
                observed = run_gold(variant["base"], variant["question"])
                self.assertEqual((observed["outcome"], observed["error_code"]),
                                 (variant["expected_outcome"], variant["expected_error"]))
                self.assertEqual([call for call in observed["calls"]
                                  if call["tool"] != "get_place_scope"], [])

    def test_a_guaranteed_definition_is_delegated_with_its_evidence(self):
        contract = tims_contract.DEFAULT_CONTRACT.assuming(bucket_week_start="sunday")
        profile = replace(providers.profile_for(), contract=contract)
        observed = run_gold("043", self.Q43_SUNDAY, profile=profile)
        self.assertEqual(observed["outcome"], "answered", observed["error_code"])
        self.assertEqual(observed["plan_calendar"], {"week_start": "sunday"})
        (lowering,) = observed["lowering"].values()
        self.assertEqual(lowering["semantics"]["week_start"],
                         {"value": "sunday", "source": "question",
                          "guaranteed_by": "bucket_week_start"})
        self.assertIn("질문에서 정한 구간 기준은 TIMS 계약으로 확인된 정의와 같습니다",
                      observed["final_answer"])

    def test_a_different_guaranteed_definition_is_not_substituted(self):
        contract = tims_contract.DEFAULT_CONTRACT.assuming(bucket_week_start="monday")
        profile = replace(providers.profile_for(), contract=contract)
        observed = run_gold("043", self.Q43_SUNDAY, profile=profile)
        self.assertEqual(observed["error_code"], "CALENDAR_REQUIREMENT_UNSUPPORTED")

    def test_local_path_honours_a_stated_week_start(self):
        """로컬 근거가 있으면 사용자가 정한 요일로 기간을 나눈다(애플리케이션 기본 월요일이 아님)."""
        execution = compile_plan(plan_for("043", self.Q43_SUNDAY), reference_date=REF,
                                 contract=LOCAL_EVIDENCE)
        (lowering,) = execution.lowering.values()
        self.assertEqual(lowering["path"], tims_contract.PATH_LOCAL)
        self.assertEqual(lowering["semantics"]["week_start"],
                         {"value": "sunday", "source": "question"})
        (detail,) = execution.periods.values()
        self.assertEqual(detail["groups"], ["20260901-20260905", "20260906-20260912",
                                            "20260913-20260919", "20260920-20260925"])
        self.assertTrue(detail["boundary"].startswith("일요일 시작 7일"))

    def test_one_stage_week_token_with_a_stated_start(self):
        question = "일요일부터 시작하는 주 기준으로 지난 주 개인택시의 평균 가동률은?"
        plan = plan_for("014", question)
        with self.assertRaises(CompilerError) as caught:
            compile_plan(plan, reference_date=REF)
        self.assertEqual(caught.exception.code, "CALENDAR_REQUIREMENT_UNSUPPORTED")
        execution = compile_plan(plan, reference_date=REF, contract=LOCAL_EVIDENCE)
        record = next(iter(execution.date_semantics.values()))
        self.assertEqual((record["lowering"], record["request"], record["responsibility"]),
                         ("explicit_range", ["20260913-20260919"], "application"))

    def test_month_bucket_keeps_a_stated_week_for_the_period(self):
        """월 구간 + last_week: 주 시작 요일은 기간에 걸린다. 위임하면 제공자 주 정의가 쓰이므로
        거부하고, 로컬 근거가 있으면 그 요일로 기간을 푼다."""
        question = "일요일 시작 주 기준 지난 주 대구 소속 법인택시의 월별 총 수입 중 가장 큰 값은?"
        item = GOLD["100"]
        payload = V.derive_grounding(item["gold"])
        payload["factors"]["date"] = "last_week"
        plan = MacroComposer().compose(parse_grounding(payload, question))
        with self.assertRaises(CompilerError) as caught:
            compile_plan(plan, reference_date=REF)
        self.assertEqual(caught.exception.code, "CALENDAR_REQUIREMENT_UNSUPPORTED")
        local = compile_plan(plan, reference_date=REF, contract=LOCAL_EVIDENCE, delegation=False)
        self.assertEqual([s.arguments["date"] for s in local.tool_steps[1:]],
                         ["20260913-20260919"])
        (detail,) = local.periods.values()
        self.assertEqual(detail["interpretation"]["week_start"], "sunday")
        self.assertIn("일요일", detail["interpretation"]["rule"])
        (lowering,) = local.lowering.values()
        self.assertEqual(lowering["semantics"]["week_start"],
                         {"value": "sunday", "source": "question"})

    def test_strict_stated_week_still_checks_the_relative_date_value(self):
        contract = tims_contract.DEFAULT_CONTRACT.assuming(
            relative_date_reference="UTC", bucket_week_start="sunday")
        question = "일요일부터 시작하는 주 기준으로 지난 주 개인택시의 평균 가동률은?"
        with self.assertRaises(CompilerError):
            compile_plan(plan_for("014", question), reference_date=REF, contract=contract,
                         date_policy="guaranteed")

    def test_strict_month_bucket_does_not_need_a_week_start(self):
        contract = tims_contract.DEFAULT_CONTRACT.assuming(
            bucket_partial="clip_to_period", bucket_empty="undefined", range_inclusive="inclusive")
        payload = V.derive_grounding(GOLD["100"]["gold"])
        payload["factors"]["date"] = "20250101-20251231"
        plan = MacroComposer().compose(parse_grounding(payload, GOLD["100"]["question"]))
        execution = compile_plan(plan, reference_date=REF, contract=contract, delegation=False)
        self.assertEqual(next(iter(execution.lowering.values()))["strategy"],
                         "fused_bucket_rollup")
        # 범위 양 끝 계약이 없으면 위임을 허용하지 않는 프로필은 범위를 그대로 넘기지 않는다.
        without_range = tims_contract.DEFAULT_CONTRACT.assuming(
            bucket_partial="clip_to_period", bucket_empty="undefined")
        with self.assertRaises(CompilerError) as caught:
            compile_plan(plan, reference_date=REF, contract=without_range, delegation=False)
        reasons = " ".join(item["reason"] for item in caught.exception.context["rejected"])
        self.assertIn("기간 인자", reasons)

    def test_partition_recorded_as_delegation_is_rejected(self):
        from geoflow.compiler import verify_lowering
        plan = plan_for("100")
        execution = compile_plan(plan, reference_date=REF, contract=LOCAL_EVIDENCE,
                                 delegation=False)
        (key,) = execution.lowering
        execution.lowering[key].update(strategy="fused_bucket_rollup",
                                       path=tims_contract.PATH_PROVIDER)
        with self.assertRaises(CompilerError) as caught:
            verify_lowering(plan, execution, reference_date=REF)
        self.assertEqual(caught.exception.code, "LOWERING_MISMATCH")

    def test_unconsumed_definitions_stop_composition(self):
        for number, question, code in (
                ("057", "지난달 부산 소속 택시의 평균 수입은? 부분 주는 제외하고.",
                 "UNCONSUMED_CONDITION"),
                ("100", "일요일 시작 주 기준으로 지난해 대구 소속 법인택시의 월별 총 수입 중 "
                        "가장 큰 값은?", "UNCONSUMED_CONDITION"),
                ("100", "지난해 대구 소속 법인택시의 일요일부터 시작하는 월별 총 수입 중 가장 큰 값은?",
                 "AMBIGUOUS_CALENDAR_REQUIREMENT"),
                ("063", "주 시작은 어떻게 잡든 지난 주 개인택시의 평균 운행 일수는?",
                 "AMBIGUOUS_CALENDAR_REQUIREMENT")):
            with self.subTest(number=number):
                with self.assertRaises(CompositionError) as caught:
                    plan_for(number, question)
                self.assertEqual(caught.exception.code, code)


class GoldExtractionTest(unittest.TestCase):
    def test_gold_file_matches_the_vendor_sources(self):
        import hashlib
        document = V.load_gold()
        self.assertEqual(document["source_sha256"],
                         hashlib.sha256(V.XLSX_FILE.read_bytes()).hexdigest())
        self.assertEqual(len(document["items"]), 100)
        self.assertEqual(document["conflicts"], [])
        questions = {q["id"]: q["question"] for q in yaml.load(
            V.QUESTIONS_FILE.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)}
        for item in document["items"]:
            self.assertEqual(item["question"], questions[item["id"]])

    def test_answer_value_check_is_not_vacuous(self):
        check = V._answer_has_value
        self.assertTrue(check("통행량: 12,345건", {"count": 12345}))
        self.assertFalse(check("통행량: 18,345건", {"count": 12345}))   # 업체 1번 오류 유형
        self.assertFalse(check("2026년 합계", 20))                       # 숫자 일부 일치 금지
        self.assertFalse(check("결과 없음", None))
        self.assertFalse(check("대구", "수성 H3-1"))
        self.assertTrue(check("- 북구: 1,280건\n- 서구: 1,502건",
                              [{"sigungu": "북구", "count": 1280}, {"sigungu": "서구", "count": 1502}]))
        self.assertFalse(check("- 북구: 1,280건\n- 동구: 1,502건",
                               [{"sigungu": "북구", "count": 1280}, {"sigungu": "서구", "count": 1502}]))

    def test_every_gold_grounding_reproduces_the_vendor_call(self):
        """정답 grounding 기반 검증 100문항. 업체 정답 Tool과 인자·scope 출처·답변 값이 일치한다."""
        for number, item in GOLD.items():
            with self.subTest(number=number):
                observed = run_gold(number)
                category, checks = V.score(item, observed)
                self.assertEqual(category, "match", (observed["error_code"], checks))


if __name__ == "__main__":
    unittest.main()
