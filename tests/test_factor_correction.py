# -*- coding: utf-8 -*-
"""factor 수정 재질의의 수정 범위와 적용 검증(scripted 모델, LLM 없음).

코드가 할 수 있어야 하는 것만 본다. 실제 모델이 올바른 수정안을 내는지는 평가 실행으로 따로 잰다.

- 수정 범위는 계약 위반과 factor 계약으로만 정한다(질문을 읽지 않는다). 위반과 무관한 결과 형태는 열지 않는다.
- 범위 밖 조건은 응답에서 빠져도 남고, 다른 값으로 적거나 새로 적으면 수정안 전체를 받지 않는다.
- 역할을 옮기는 정당한 수정(요일을 bucket → dimension, 순위를 rollup → order, 집계 단계 옮기기)은 된다.
- 그룹이나 순위 방향이 계약상 이유 없이 사라지거나 바뀌면 받지 않는다. 집계 값을 새로 만들지 않는다.
- 이 검사는 계약 수준이다. 첫 grounding에 이미 있던 의미 오류(m04: 순위 방향)는 잡지 못한다.
- 복구가 끝나기 전에는 Tool을 부르지 않는다. 재질의는 한 번이다. 올바른 grounding은 재질의 없이 끝난다.

사례 이름(c06a, g44, m04, 015, k36, t01c, c08b, g24, m17, k19, 070, c10a)은 grounding_v5 최종 실측에 기록된 첫 응답·수정안의
결과 형태다. 같은 구조를 다른 factor 조합으로도 본다.
"""

import json
import os
import sys
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from evaluate_vendor100 import REFERENCE_DATE, _executor  # noqa: E402
from geoflow import providers  # noqa: E402
from geoflow.correction_scope import (  # noqa: E402
    ADD,
    CHANGE,
    MOVE,
    REMOVE,
    ScopeViolation,
    apply_correction,
    correction_scope,
)
from geoflow.factors import CONTRACT_COMPANIONS, FACTOR_CONSTRAINTS  # noqa: E402
from geoflow.pipeline import (  # noqa: E402
    OUTCOME_ANSWERED,
    OUTCOME_NEEDS_CLARIFICATION,
    OUTCOME_UNSUPPORTED,
    GeoFlowPipeline,
)
from geoflow.repair import RepairKind  # noqa: E402

REVENUE = [
    {"id": "e", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT", "source": "implicit"},
    {"id": "m", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE", "source": "implicit"},
]


class ScriptedClient:
    model = "scripted"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, messages, tools=None, **kwargs):
        self.calls.append(messages)
        if not self.responses:
            raise AssertionError("준비된 응답보다 많은 호출")
        return {"message": {"content": json.dumps(self.responses.pop(0), ensure_ascii=False)}}


def run(question, *responses):
    client = ScriptedClient(responses)
    pipeline = GeoFlowPipeline.create(
        client=client, tool_executor=_executor(), clock=lambda: REFERENCE_DATE,
        condition_check=True, condition_notes=False,
        execution_profile=providers.profile_for(providers.MOCK, providers.LEGACY))
    result = pipeline.run(question)
    return result, client


def plan(factors, concepts=REVENUE):
    return {"concepts": list(concepts), "factors": dict(factors)}


def tools_called(result):
    return [hop["tool"] for hop in result.hop_log if hop.get("phase") == "tool"]


def tool_args(result):
    calls = [hop for hop in result.hop_log if hop.get("phase") == "tool"]
    return calls[-1].get("arguments") or {}


def permissions(factors):
    return dict(correction_scope(factors).permissions)


def correct(base, proposal):
    return apply_correction(base, proposal, correction_scope(base))


def outcome(base, proposal, question="", evidence=None):
    """("applied", 결과) / ("blocked", 막힌 factor) / ("unverified", 확인 못 한 단계) / ("no change", None)."""
    try:
        result, _ = apply_correction(base, proposal, correction_scope(base), question=question,
                                     evidence=evidence)
    except ScopeViolation as violation:
        if violation.record["blocked"]:
            return "blocked", {item["factor"] for item in violation.record["blocked"]}
        if violation.record.get("terminal"):
            return "unverified", violation.record["terminal"]["unverified_stages"]
        return "no change", None
    return "applied", result


def blocked(base, proposal, question="", evidence=None):
    kind, detail = outcome(base, proposal, question, evidence)
    if kind == "blocked":
        return detail
    if kind == "no change":
        return {"(no change)"}
    if kind == "unverified":
        return {"(unverified)"}
    return set()


# -- 1. 수정 범위 ---------------------------------------------------------------


class ScopeTest(unittest.TestCase):
    """오류에 필요한 범위만 연다. 문제 필드 하나로 고정하지도 않는다."""

    def test_answer_on_a_ranking_opens_only_answer(self):
        """요일 순위에 answer=bucket(t04b 형태): bucket은 dimension과 함께 쓸 수 없어 열지 않고, 순위·개수·그룹·집계는 닫는다."""
        base = {"dimension": "dayofweek", "aggregation": "avg", "order": "bottom", "limit": 1,
                "answer": "bucket"}
        self.assertEqual(permissions(base), {"answer": {REMOVE}})

    def test_ranking_written_as_rollup_opens_order_and_limit(self):
        """g24 형태: answer와 rollup이 함께 bucket 없이 있다. 순위를 order·limit으로 옮길 수 있게 연다."""
        base = {"dimension": "dayofweek", "aggregation": "avg", "rollup": "min", "answer": "bucket"}
        self.assertEqual(permissions(base), {
            "answer": {REMOVE}, "rollup": {REMOVE}, "order": {ADD}, "limit": {ADD}})

    def test_weekday_written_as_bucket_opens_the_dimension_move(self):
        """k36 형태: bucket=dayofweek는 허용값이 아니다. dimension으로 옮기고 순위를 order·limit으로 적을 수 있다."""
        base = {"bucket": "dayofweek", "aggregation": "min", "rollup": "max"}
        scope = permissions(base)
        self.assertEqual(scope["bucket"], {CHANGE, REMOVE})
        self.assertEqual(scope["rollup"], {REMOVE})
        self.assertEqual({name for name, ops in scope.items() if ADD in ops},
                         {"dimension", "order", "limit"})
        self.assertNotIn("aggregation", scope)

    def test_missing_rollup_opens_the_stage_move_but_not_a_new_grouping(self):
        """c08b 형태: bucket=month에 rollup이 없다. 집계 값을 rollup으로 옮길 수 있지만 주·월을 지역 그룹으로 바꾸지는 않는다."""
        base = {"bucket": "month", "aggregation": "avg"}
        self.assertEqual(permissions(base), {
            "bucket": {REMOVE}, "rollup": {ADD}, "aggregation": {MOVE}})

    def test_record_filter_value_errors_are_not_repairable(self):
        scope = correction_scope({"date": "지난달", "bucket": "week"})
        self.assertFalse(scope.repairable)
        self.assertEqual(scope.unrepairable, ["date"])

    def test_valid_factors_open_nothing(self):
        for base in ({"dimension": "sido", "order": "top", "limit": 1, "aggregation": "sum"},
                     {"bucket": "week", "aggregation": "sum", "rollup": "max", "answer": "bucket"}):
            with self.subTest(base=base):
                self.assertEqual(permissions(base), {})


# -- 2. 적용: 범위 밖은 남고, 정당한 이동은 된다 ------------------------------------


class ApplyTest(unittest.TestCase):

    def test_fixing_answer_keeps_order_limit_and_aggregation_even_when_omitted(self):
        """잘못된 answer만 고친다. 응답에서 순위·개수·집계가 빠져도 지우지 않고 기록한다."""
        base = {"date": "last_month", "dimension": "dayofweek", "aggregation": "avg",
                "order": "bottom", "limit": 1, "answer": "bucket"}
        result, record = correct(base, {"dimension": "dayofweek"})
        self.assertEqual(result, {key: value for key, value in base.items() if key != "answer"})
        self.assertEqual(record["applied"]["removed"], {"answer": "bucket"})
        self.assertEqual(sorted(record["kept_omitted"]), ["aggregation", "limit", "order"])
        self.assertEqual(record["roles"]["before"]["direction"], record["roles"]["after"]["direction"])

    def test_legitimate_role_moves_are_accepted(self):
        """기록된 정당한 수정과 같은 구조의 다른 조합."""
        cases = {
            "015 요일 bucket → dimension, rollup max → order top": (
                {"dimension": "dayofweek", "bucket": "dayofweek", "aggregation": "avg", "rollup": "max",
                 "answer": "bucket"},
                {"dimension": "dayofweek", "aggregation": "avg", "order": "top", "limit": 1}),
            "k36 요일 bucket → 새 dimension": (
                {"bucket": "dayofweek", "aggregation": "min", "rollup": "max"},
                {"dimension": "dayofweek", "aggregation": "min", "order": "top", "limit": 1}),
            "g24 rollup min → order bottom": (
                {"dimension": "dayofweek", "aggregation": "avg", "rollup": "min", "answer": "bucket"},
                {"dimension": "dayofweek", "aggregation": "avg", "order": "bottom", "limit": 1}),
            "같은 구조, 시도·max": (
                {"dimension": "sido", "aggregation": "sum", "rollup": "max", "answer": "bucket"},
                {"dimension": "sido", "aggregation": "sum", "order": "top", "limit": 1}),
            "t01c 집계 단계 옮기기(max)": (
                {"bucket": "month", "aggregation": "max", "answer": "value"},
                {"bucket": "month", "rollup": "max", "answer": "value"}),
            "c08b 집계 단계 옮기기(avg)": (
                {"bucket": "month", "aggregation": "avg"},
                {"bucket": "month", "rollup": "avg"}),
            "rollup → aggregation(그룹 안 최댓값)": (
                {"dimension": "sido", "rollup": "max"},
                {"dimension": "sido", "aggregation": "max"}),
            "m17 rollup=top → order": (
                {"dimension": "sido", "aggregation": "min", "rollup": "top", "limit": 3},
                {"dimension": "sido", "aggregation": "min", "order": "top", "limit": 3}),
            "k19 answer·rollup 빼기, order 유지": (
                {"dimension": "dayofweek", "order": "top", "limit": 1, "aggregation": "avg",
                 "rollup": "max", "answer": "bucket"},
                {"dimension": "dayofweek", "order": "top", "limit": 1, "aggregation": "avg"}),
            "070 rollup 빼기, answer=value는 생략과 같음": (
                {"dimension": "emd", "order": "top", "limit": 1, "aggregation": "sum", "rollup": "max"},
                {"dimension": "emd", "order": "top", "limit": 1, "aggregation": "sum", "answer": "value"}),
            "007 빠진 dimension 채우기": (
                {"dimension_target": "pickup", "order": "top", "limit": 3},
                {"dimension": "h3", "dimension_target": "pickup", "order": "top", "limit": 3}),
        }
        for name, (base, proposal) in cases.items():
            with self.subTest(case=name):
                self.assertEqual(blocked(base, proposal), set())

    def test_ranking_lost_while_fixing_rollup_is_rejected(self):
        """c06a: rollup=min을 빼면서 순위를 order로 옮기지 않으면 순위가 사라진다. 방향이 뒤집혀도 받지 않는다."""
        for grouping in ("sido", "dayofweek", "h3"):
            for rollup, direction, flipped in (("min", "bottom", "top"), ("max", "top", "bottom")):
                base = {"dimension": grouping, "aggregation": "avg", "rollup": rollup}
                with self.subTest(grouping=grouping, rollup=rollup):
                    self.assertEqual(blocked(base, {"dimension": grouping, "aggregation": "avg"}),
                                     {"direction"})
                    self.assertEqual(blocked(base, {"dimension": grouping, "aggregation": "avg",
                                                    "order": flipped, "limit": 1}), {"direction"})
                    self.assertEqual(blocked(base, {"dimension": grouping, "aggregation": "avg",
                                                    "order": direction, "limit": 1}), set())

    def test_new_inner_aggregation_values_are_never_taken_from_a_repair(self):
        """g44·s01d: rollup을 채우며 aggregation을 avg → sum으로 바꿨다. 구간 안 집계의 새 값은 받지 않는다.

        근거 문자열이 질문에 있어도("월별 수입", c2a0e2c 대조 셋 s01d) 그 값을 뜻한다는 것을 코드가 확인할 수 없다.
        막는 대신 실행하지 않고 구간 안 집계를 확인받는다. 질문에 구간 안 집계 표현이 실제로 있는 경우(첫 응답이
        단계를 잘못 배치함)도 같은 확인 요청으로 끝난다. 이것은 이 정책의 비용이다.
        """
        base = {"bucket": "week", "aggregation": "avg"}
        proposal = {"bucket": "week", "aggregation": "sum", "rollup": "avg"}
        g44 = "지난달 주별 개인택시 수입의 평균은?"
        self.assertEqual(outcome(base, proposal, g44), ("unverified", ["aggregation"]))
        self.assertEqual(outcome(base, proposal, g44, {"aggregation": "주별 개인택시 수입"}),
                         ("unverified", ["aggregation"]))
        misplaced = "지난달 주별 개인택시 수입 합계의 평균은?"
        self.assertEqual(outcome(base, proposal, misplaced, {"aggregation": "합계"}), ("unverified", ["aggregation"]))
        # 값만 옮기는 수정(구간 안 집계를 비움)은 받는다. 그 뒤 구간 안 집계 확인 요청은 합성 단계가 한다.
        self.assertEqual(outcome(base, {"bucket": "week", "rollup": "avg"}, g44)[0], "applied")

    def test_two_new_equal_values_are_a_new_inner_value(self):
        """두 단계가 모두 새 값이고 같으면 '첫 grounding이 읽은 값의 두 번째 자리'가 아니다. 구간 안 집계 새 값으로 본다.

        grounding_v7(ecf323c)에서는 이 경우가 같은 값 두 단계 경로로 들어가 반복 문자열 검사만으로 받아졌다.
        """
        base = {"bucket": "week", "rollup": "top"}
        twice = "지난달 주별 최댓값 중 최댓값은?"
        self.assertEqual(outcome(base, {"bucket": "week", "aggregation": "max", "rollup": "max"}, twice,
                                 {"aggregation": "최댓값", "rollup": "최댓값"}), ("unverified", ["aggregation"]))

    def test_new_rollup_value_needs_a_literal_basis(self):
        """빠진 짝(rollup)의 새 값은 근거 문자열이 질문에 있어야 한다(뜻은 확인하지 않는다)."""
        base = {"bucket": "month", "aggregation": "sum"}
        proposal = {"bucket": "month", "aggregation": "sum", "rollup": "max"}
        question = "지난해 월별 수입 합계 중 가장 큰 값은?"
        self.assertEqual(outcome(base, proposal, question, {"rollup": "가장 큰"})[0], "applied")
        self.assertEqual(outcome(base, proposal, question), ("unverified", ["rollup"]))
        self.assertEqual(outcome(base, proposal, question, {"rollup": "최댓값"}), ("unverified", ["rollup"]))

    def test_same_aggregation_in_both_stages_needs_two_separate_places(self):
        """두 단계에 같은 집계를 적으면 질문의 겹치지 않는 두 자리에 근거가 있어야 한다(값이 같다는 것만으로 막지 않는다)."""
        base = {"bucket": "week", "aggregation": "max"}
        copy = {"bucket": "week", "aggregation": "max", "rollup": "max"}
        twice = "지난달 주별 최댓값 중 최댓값은?"
        self.assertEqual(outcome(base, copy, twice, {"aggregation": "최댓값", "rollup": "최댓값"})[0], "applied")
        # 서로 다른 문자열 둘은 같은 표현이 두 번 있다는 사실이 아니다(1b4a173 실측 t01c: "월별", "가장 큰 값").
        self.assertEqual(outcome(base, copy, twice, {"aggregation": "주별 최댓값", "rollup": "중 최댓값"})[0],
                         "unverified")
        t01c = "지난해 대구 소속 택시의 월별 수입 중 가장 큰 값은?"
        self.assertEqual(outcome(base | {"bucket": "month"}, copy | {"bucket": "month"}, t01c,
                                 {"aggregation": "월별", "rollup": "가장 큰 값"})[0], "unverified")
        once = "지난달 주별 수입 중 최댓값은?"
        self.assertEqual(outcome(base, copy, once, {"aggregation": "최댓값", "rollup": "최댓값"}),
                         ("unverified", ["aggregation", "rollup"]))
        self.assertEqual(outcome(base, copy, twice), ("unverified", ["aggregation", "rollup"]))
        # 같은 구조의 다른 조합.
        for bucket, value, question, word in (("month", "avg", "월별 평균 매출의 평균은?", "평균"),
                                              ("week", "sum", "주별 합계의 합계는?", "합계")):
            with self.subTest(bucket=bucket, value=value):
                self.assertEqual(outcome({"bucket": bucket, "aggregation": value},
                                         {"bucket": bucket, "aggregation": value, "rollup": value}, question,
                                         {"aggregation": word, "rollup": word})[0], "applied")
                self.assertEqual(outcome({"bucket": bucket, "aggregation": value},
                                         {"bucket": bucket, "aggregation": value, "rollup": value},
                                         question.replace(word, "", 1), {"aggregation": word, "rollup": word})[0],
                                 "unverified")

    def test_moving_a_value_between_stages_needs_no_evidence_but_dropping_it_is_blocked(self):
        base = {"bucket": "month", "aggregation": "avg"}
        self.assertEqual(outcome(base, {"bucket": "month", "rollup": "avg"})[0], "applied")
        # 값을 옮기지 않고 다른 rollup을 적으면 원래 값을 버린 것이다.
        self.assertIn("aggregation", blocked(base, {"bucket": "month", "rollup": "max"}, "월별 최대",
                                             {"rollup": "최대"}))

    def test_answer_target_reselect_keeps_the_old_value(self):
        """answer=bucket에 rollup=avg: 구간을 고르는 질문이면 avg를 aggregation으로 옮기고 rollup을 max·min으로 다시 고른다."""
        base = {"bucket": "week", "rollup": "avg", "answer": "bucket"}
        question = "지난달 주별 평균 수입이 가장 큰 주는?"
        reselect = {"bucket": "week", "aggregation": "avg", "rollup": "max", "answer": "bucket"}
        self.assertEqual(outcome(base, reselect, question, {"rollup": "가장 큰"})[0], "applied")
        self.assertEqual(outcome(base, reselect, question), ("unverified", ["rollup"]))
        # 원래 avg를 버리고 방향만 고르면 막는다.
        self.assertIn("rollup", blocked(base, {"bucket": "week", "rollup": "max", "answer": "bucket"}, question,
                                        {"rollup": "가장 큰"}))
        # 값을 묻는 질문이면 answer를 뺀다(avg는 그대로).
        kind, result = outcome(base, {"bucket": "week", "rollup": "avg"})
        self.assertEqual((kind, result.get("answer"), result["rollup"]), ("applied", None, "avg"))

    def test_answer_target_with_inner_aggregation_opens_only_answer_removal(self):
        """aggregation이 이미 있으면 rollup을 다시 고를 때 원래 값을 보존할 자리가 없다. answer 빼기만 연다."""
        base = {"bucket": "week", "aggregation": "sum", "rollup": "avg", "answer": "bucket"}
        self.assertEqual(permissions(base), {"answer": {REMOVE}})

    def test_integer_written_as_text_is_read_as_integer(self):
        """k36(9a37248 실측): limit을 "1"로 적은 올바른 수정안. 형식만 맞춘다."""
        base = {"bucket": "dayofweek", "aggregation": "min", "rollup": "max"}
        result, _ = correct(base, {"dimension": "dayofweek", "aggregation": "min", "order": "top",
                                   "limit": "1"})
        self.assertEqual(result["limit"], 1)

    def test_out_of_scope_changes_and_additions_are_not_applied(self):
        """c10a: answer를 빼면서 계약에 없는 bucket=emd를 새로 적었다. 범위 밖 변경이 있으면 수정안 전체를 받지 않는다."""
        base = {"date": "this_month", "dimension": "emd", "dimension_target": "pickup",
                "order": "top", "limit": 2, "answer": "bucket"}
        self.assertEqual(blocked(base, {"dimension": "emd", "dimension_target": "pickup", "order": "top",
                                        "limit": 2, "bucket": "emd"}), {"bucket"})
        self.assertEqual(blocked(base, {"dimension_target": "dropoff"}), {"dimension_target"})
        self.assertEqual(blocked(base, {"order": None}), {"order"})
        self.assertEqual(blocked(base, {"taxi_type": "private"}), {"taxi_type"})

    def test_a_correction_cannot_introduce_the_bucket_dimension_conflict(self):
        """015(R2 기록): 허용값이 아닌 bucket=dayofweek를 week로 바꾸고 dimension을 남겼다. 지원 범위 밖 조합을 새로 만든다."""
        base = {"dimension": "dayofweek", "bucket": "dayofweek", "aggregation": "avg", "rollup": "max",
                "answer": "bucket"}
        self.assertEqual(blocked(base, {**base, "bucket": "week"}), {"bucket"})

    def test_removing_every_grouping_is_rejected(self):
        """n23·m40: 구간을 빼고 전체 값으로 답하게 만드는 수정."""
        self.assertIn("grouping", blocked({"bucket": "month", "aggregation": "min", "answer": "value"},
                                          {"aggregation": "min", "answer": "value"}))
        self.assertIn("grouping", blocked({"bucket": "hour", "aggregation": "sum", "rollup": "sum"},
                                          {"aggregation": "sum"}))

    def test_preexisting_errors_outside_the_conflict_stay(self):
        """m04: answer를 빼는 수정은 정당하다. 첫 응답의 order=top("뜸했던")은 계약 위반이 아니라 그대로 남는다.

        계약 검사는 이 오류를 찾지 못한다. 복구 뒤 실행되면 '기존 오류가 실행 가능해진 경우'로 따로 센다.
        """
        base = {"dimension": "emd", "dimension_target": "pickup", "order": "top", "limit": 3,
                "answer": "bucket"}
        result, record = correct(base, {"dimension": "emd", "dimension_target": "pickup", "order": "top",
                                        "limit": 3})
        self.assertEqual(result["order"], "top")
        self.assertNotIn("order", record["scope"]["permissions"])

    def test_unchanged_proposal_is_rejected(self):
        """g24 기록: answer=bucket을 그대로 둔 수정안."""
        base = {"dimension": "dayofweek", "aggregation": "avg", "rollup": "min", "answer": "bucket"}
        self.assertEqual(blocked(base, dict(base)), {"(no change)"})


# -- 3. 파이프라인: 실행·재질의 횟수·Tool ---------------------------------------------


class PipelineTest(unittest.TestCase):
    QUESTION = "지난달 요일별 법인택시 평균 수입이 가장 낮은 요일은?"
    FIRST = {"date": "last_month", "taxi_type": "corporate", "dimension": "dayofweek",
             "aggregation": "avg", "order": "bottom", "limit": 1, "answer": "bucket"}

    def test_stage_guidance_appears_only_when_the_scope_opens_stage_values(self):
        """순위 복구 문구에는 집계 단계·evidence 지침을 섞지 않는다(1b4a173 실측: 순위 복구가 rollup을 남겼다)."""
        _, client = run(self.QUESTION, plan(self.FIRST), {"factors": {"dimension": "dayofweek"}})
        self.assertNotIn("evidence", client.calls[1][-1]["content"])
        _, client = run("지난달 주별 수입의 평균은?", plan({"date": "last_month", "bucket": "week", "aggregation": "avg"}),
                        {"factors": {"bucket": "week", "rollup": "avg"}})
        self.assertIn("evidence", client.calls[1][-1]["content"])

    def test_answer_fix_runs_with_the_original_ranking(self):
        result, client = run(self.QUESTION, plan(self.FIRST), {"factors": {"dimension": "dayofweek"}})
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)
        self.assertEqual(len(client.calls), 2)
        args = tool_args(result)
        self.assertEqual((args.get("order"), args.get("limit"), args.get("dimension")),
                         ("bottom", 1, "dayofweek"))
        (first,) = [item for item in result.attempts if item.get("error_code")]
        self.assertEqual((first["repair_kind"], first["repair_result"]),
                         (RepairKind.FACTOR_CORRECTION, "OK"))
        self.assertEqual(first["correction"]["applied"]["removed"], {"answer": "bucket"})
        instruction = client.calls[1][-1]["content"]
        self.assertIn("- answer (지금 'bucket'): 뺄 수 있음", instruction)
        self.assertNotIn("- order (", instruction)

    def test_rejected_correction_calls_no_tool(self):
        """c06a 형태 수정안(순위 삭제)은 거부되고 Tool을 부르지 않는다. 최초 오류와 막힌 이유가 남는다."""
        first = {"date": "last_month", "dimension": "sido", "aggregation": "avg", "rollup": "min"}
        result, client = run("지난달 시도별 평균 수입이 가장 낮은 곳은?", plan(first),
                             {"factors": {"dimension": "sido", "aggregation": "avg"}})
        self.assertNotEqual(result.outcome, OUTCOME_ANSWERED)
        self.assertEqual(tools_called(result), [])
        self.assertEqual(len(client.calls), 2)
        (attempt,) = [item for item in result.attempts if item.get("error_code")]
        self.assertEqual(attempt["repair_error"]["code"], "REPAIR_OUT_OF_SCOPE")
        self.assertEqual([item["factor"] for item in attempt["correction"]["blocked"]], ["direction"])

    def test_same_case_with_the_ranking_moved_runs(self):
        first = {"date": "last_month", "dimension": "sido", "aggregation": "avg", "rollup": "min"}
        result, _ = run("지난달 시도별 평균 수입이 가장 낮은 곳은?", plan(first),
                        {"factors": {"aggregation": "avg", "order": "bottom", "limit": 1}})
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)
        self.assertEqual(tool_args(result).get("order"), "bottom")

    def test_correction_that_still_breaks_the_contract_is_not_asked_again(self):
        """범위 안의 수정이 다른 위반을 남기면 재검증이 멈추고 다시 묻지 않는다(t04b 기록: rollup을 남김)."""
        first = {**self.FIRST, "rollup": "min"}
        result, client = run(self.QUESTION, plan(first),
                             {"factors": {"rollup": "min", "dimension": "dayofweek"}})
        self.assertNotEqual(result.outcome, OUTCOME_ANSWERED)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(tools_called(result), [])
        self.assertEqual(result.error["code"], "INVALID_FACTOR_COMBINATION")

    def test_plan_stage_value_error_is_corrected(self):
        first = {"date": "this_month", "taxi_type": "corporate", "bucket": "dayofweek",
                 "aggregation": "avg", "rollup": "max"}
        fix = {"factors": {"dimension": "dayofweek", "order": "top", "limit": 1}}
        result, client = run("이번 달 요일별 법인택시 평균 수입 중 가장 높은 요일은?", plan(first), fix)
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)
        self.assertEqual(result.attempts[0]["error_code"], "INVALID_FACTOR")
        self.assertEqual(tool_args(result).get("aggregation"), "avg")

    def test_moving_the_only_aggregation_word_leaves_inner_unspecified(self):
        first = {"date": "last_year", "taxi_type": "corporate", "bucket": "month", "aggregation": "avg"}
        result, client = run("지난해 월별 법인택시 수입의 평균은?", plan(first),
                             {"factors": {"bucket": "month", "rollup": "avg"}})
        self.assertEqual(result.outcome, OUTCOME_NEEDS_CLARIFICATION, result.runtime_error)
        self.assertEqual(result.error["code"], "AMBIGUOUS_INNER_AGGREGATION")
        self.assertEqual(tools_called(result), [])

    def test_inner_aggregation_gap_is_never_sent_back(self):
        result, client = run("지난해 대구 소속 택시의 월별 수입 중 가장 큰 값은?",
                             plan({"date": "last_year", "bucket": "month", "rollup": "max"}))
        self.assertEqual(result.outcome, OUTCOME_NEEDS_CLARIFICATION)
        self.assertEqual(len(client.calls), 1)

    def test_correct_groundings_run_without_repair(self):
        cases = (
            ("지난달 주별 수입 합계 중 가장 큰 값은?",
             {"date": "last_month", "bucket": "week", "aggregation": "sum", "rollup": "max"}, OUTCOME_ANSWERED),
            ("지난달 수입 합계가 가장 큰 주는?",
             {"date": "last_month", "bucket": "week", "aggregation": "sum", "rollup": "max",
              "answer": "bucket"}, OUTCOME_UNSUPPORTED),
            (self.QUESTION, {key: value for key, value in self.FIRST.items() if key != "answer"},
             OUTCOME_ANSWERED),
        )
        for question, factors, outcome in cases:
            with self.subTest(question=question):
                result, client = run(question, plan(factors))
                self.assertEqual(result.outcome, outcome, result.runtime_error)
                self.assertEqual(len(client.calls), 1)

    def test_unsupported_answers(self):
        """질문에 없다고 답하면: 답 대상 → 확인 요청, 계약에 없는 값 → 지원 범위 밖."""
        result, client = run("지난달 주별 수입 합계의 평균이 가장 큰 주는?",
                             plan({"date": "last_month", "bucket": "week", "aggregation": "sum",
                                   "rollup": "avg", "answer": "bucket"}), {"unsupported": True})
        self.assertEqual((result.outcome, result.error["code"]),
                         (OUTCOME_NEEDS_CLARIFICATION, "INVALID_ANSWER_TARGET"))
        result, client = run("이번 달 수입을 시간대별로 나눠서 보여줘.",
                             plan({"date": "this_month", "bucket": "hour", "aggregation": "sum",
                                   "rollup": "sum"}), {"unsupported": True})
        self.assertEqual((result.outcome, result.error["code"]), (OUTCOME_UNSUPPORTED, "UNSUPPORTED_QUESTION"))


def run_on(provider, question, *responses):
    """TIMS legacy(mock) 또는 reference provider에서 실행한다. grounding 계약과 provider 실행 가능성을 따로 보기 위한 것이다."""
    from build import build
    from tool_executor import ToolExecutor
    from tool_handlers import get_tool_handlers

    client = ScriptedClient(responses)
    if provider == providers.REFERENCE:
        tools, _ = build()
        executor = ToolExecutor(tools=tools, handlers=get_tool_handlers(providers.REFERENCE),
                                provider=providers.REFERENCE)
        profile = providers.profile_for(providers.REFERENCE)
    else:
        executor, profile = _executor(), providers.profile_for(providers.MOCK, providers.LEGACY)
    pipeline = GeoFlowPipeline.create(client=client, tool_executor=executor, clock=lambda: REFERENCE_DATE,
                                      condition_check=True, condition_notes=False, execution_profile=profile)
    return pipeline.run(question), client


class ExpressionAndRecoveryTest(unittest.TestCase):
    """정상 표현 능력(첫 grounding이 바로 맞음)과 계약 오류 초안의 정당한 복구를 함께 본다. 허용해야 할 것이 통과하는지도 본다."""

    TWICE = "지난달 주별 수입 최댓값 중 최댓값은?"
    ONCE = "지난달 주별 수입 중 최댓값은?"

    def test_same_aggregation_in_both_stages_is_expressible_directly(self):
        result, client = run(self.TWICE, plan({"date": "last_month", "bucket": "week",
                                               "aggregation": "max", "rollup": "max"}))
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)
        self.assertEqual(len(client.calls), 1)

    def test_same_aggregation_in_both_stages_recovers_from_a_draft_with_evidence(self):
        draft = plan({"date": "last_month", "bucket": "week", "aggregation": "max"})
        fix = {"factors": {"bucket": "week", "aggregation": "max", "rollup": "max"},
               "evidence": {"aggregation": "최댓값", "rollup": "최댓값"}}
        result, client = run(self.TWICE, draft, fix)
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)
        attempt = result.attempts[0]
        self.assertEqual(attempt["correction"]["evidence_check"]["unverified"], [])
        self.assertIn("뜻은 확인하지 않았다", attempt["correction"]["evidence_check"]["note"])
        args = tool_args(result)
        self.assertEqual((args.get("aggregation"), args.get("rollup")), ("max", "max"))

    def test_copy_without_two_places_ends_in_a_stage_clarification(self):
        """같은 값을 두 단계에 적었는데 질문에 그 표현이 한 번뿐이다: 실행하지 않고 어느 단계인지 확인받는다."""
        draft = plan({"date": "last_month", "bucket": "week", "aggregation": "max"})
        fix = {"factors": {"bucket": "week", "aggregation": "max", "rollup": "max"},
               "evidence": {"aggregation": "최댓값", "rollup": "최댓값"}}
        result, client = run(self.ONCE, draft, fix)
        self.assertEqual(result.outcome, OUTCOME_NEEDS_CLARIFICATION)
        self.assertEqual(result.error["code"], "AMBIGUOUS_AGGREGATION_STAGE")
        self.assertEqual(result.error["context"]["clarify"], ["aggregation", "rollup"])
        self.assertEqual(tools_called(result), [])
        self.assertEqual(len(client.calls), 2)

    def test_one_stage_only_is_a_clarification_directly_and_after_a_move(self):
        result, client = run(self.ONCE, plan({"date": "last_month", "bucket": "week", "rollup": "max"}))
        self.assertEqual((result.outcome, result.error["code"]),
                         (OUTCOME_NEEDS_CLARIFICATION, "AMBIGUOUS_INNER_AGGREGATION"))
        self.assertEqual(len(client.calls), 1)
        result, client = run(self.ONCE, plan({"date": "last_month", "bucket": "week", "aggregation": "max"}),
                             {"factors": {"bucket": "week", "rollup": "max"}})
        self.assertEqual((result.outcome, result.error["code"]),
                         (OUTCOME_NEEDS_CLARIFICATION, "AMBIGUOUS_INNER_AGGREGATION"))
        self.assertEqual(tools_called(result), [])

    def test_misplaced_stage_is_expressible_directly_but_not_recovered_by_inventing(self):
        """질문에 구간 안 합계가 있다. 첫 grounding이 바로 적으면 답한다. 첫 응답이 합계를 빠뜨리면 복구가 합계를
        채우지 못하고 구간 안 집계를 확인받는다(정책 비용: 정당할 수 있는 수정이 확인 요청으로 끝남)."""
        question = "지난달 주별 수입 합계의 평균은?"
        result, client = run(question, plan({"date": "last_month", "bucket": "week", "aggregation": "sum",
                                             "rollup": "avg"}))
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)
        self.assertEqual(len(client.calls), 1)
        draft = plan({"date": "last_month", "bucket": "week", "aggregation": "avg"})
        fix = {"factors": {"bucket": "week", "aggregation": "sum", "rollup": "avg"},
               "evidence": {"aggregation": "합계"}}
        result, _ = run(question, draft, fix)
        self.assertEqual((result.outcome, result.error["code"]),
                         (OUTCOME_NEEDS_CLARIFICATION, "AMBIGUOUS_INNER_AGGREGATION"))
        self.assertEqual(tools_called(result), [])

    def test_invented_inner_aggregation_ends_in_an_inner_clarification(self):
        """g44 형태: 질문에 구간 안 집계 표현이 없는데 sum을 지어냈다. 근거가 없으니 구간 안 집계를 확인받는다."""
        question = "지난달 주별 수입의 평균은?"
        draft = plan({"date": "last_month", "bucket": "week", "aggregation": "avg"})
        fix = {"factors": {"bucket": "week", "aggregation": "sum", "rollup": "avg"}}
        result, _ = run(question, draft, fix)
        self.assertEqual((result.outcome, result.error["code"]),
                         (OUTCOME_NEEDS_CLARIFICATION, "AMBIGUOUS_INNER_AGGREGATION"))
        self.assertEqual(result.error["context"]["reason"], "repair_stage_value_unverified")
        self.assertEqual(tools_called(result), [])

    def test_value_and_bucket_targets_are_separate_from_provider_support(self):
        """값 질문은 TIMS에서 답한다. 구간 질문은 grounding이 유효하고, TIMS는 실행 계약으로 멈추며 reference는 계산한다."""
        value = {"date": "last_month", "bucket": "week", "aggregation": "sum", "rollup": "max"}
        result, client = run_on(providers.MOCK, "지난달 주별 수입 합계 중 가장 큰 값은?", plan(value))
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)
        bucket = {**value, "answer": "bucket"}
        question = "지난달 주별 수입 합계가 가장 큰 주는?"
        result, client = run_on(providers.MOCK, question, plan(bucket))
        self.assertEqual((result.outcome, result.error["code"], len(client.calls)),
                         (OUTCOME_UNSUPPORTED, "UNVERIFIED_TIMS_CONTRACT", 1))
        result, client = run_on(providers.REFERENCE, question, plan(bucket))
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)
        self.assertEqual(len(client.calls), 1)

    def test_answer_target_draft_recovers_and_provider_support_is_judged_after(self):
        """answer=bucket + rollup=avg 초안: avg를 aggregation으로 옮기고 rollup=max를 근거와 함께 고른다.

        고친 grounding은 유효하다. TIMS가 실행하지 못하는 것은 provider 계약이며 grounding 오류가 아니다.
        """
        question = "지난달 주별 평균 수입이 가장 큰 주는?"
        draft = plan({"date": "last_month", "bucket": "week", "rollup": "avg", "answer": "bucket"})
        fix = {"factors": {"bucket": "week", "aggregation": "avg", "rollup": "max", "answer": "bucket"},
               "evidence": {"rollup": "가장 큰"}}
        result, _ = run_on(providers.MOCK, question, draft, fix)
        self.assertEqual((result.outcome, result.error["code"]), (OUTCOME_UNSUPPORTED, "UNVERIFIED_TIMS_CONTRACT"))
        self.assertEqual(result.attempts[0]["repair_result"], "OK")
        result, _ = run_on(providers.REFERENCE, question, draft, fix)
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)


class ContractConsistencyTest(unittest.TestCase):
    """재질의가 보여 주는 수정 범위 = 파서가 적용하는 범위. 짝 규칙마다 본다."""

    def test_instruction_scope_matches_the_parser_scope(self):
        rules = {factor: constraint.requires for factor, constraint in FACTOR_CONSTRAINTS.items()}
        for factor, (requires, _) in CONTRACT_COMPANIONS.items():
            rules[factor] = tuple(rules.get(factor, ())) + tuple(requires)
        samples = {"bucket": "week", "rollup": "avg", "answer": "bucket", "dimension": "sido",
                   "dimension_target": "pickup", "order": "top", "limit": 3}
        for factor in sorted(rules):
            first = {"date": "last_month", factor: samples[factor]}
            if factor == "answer":
                first["rollup"] = "max"
            with self.subTest(factor=factor):
                result, client = run("지난달 수입은?", plan(first), {"unsupported": True})
                self.assertEqual(len(client.calls), 2, result.attempts)
                instruction = client.calls[1][-1]["content"]
                shown = {line[2:].split(" (")[0] for line in instruction.splitlines()
                         if line.startswith("- ") and " (지금 " in line}
                grounding_factors = json.loads(client.calls[1][-2]["content"])["factors"]
                self.assertEqual(shown, set(correction_scope(grounding_factors).editable))


if __name__ == "__main__":
    unittest.main()
