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


def blocked(base, proposal):
    try:
        correct(base, proposal)
    except ScopeViolation as violation:
        return {item["factor"] for item in violation.record["blocked"]} or {"(no change)"}
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

    def test_inventing_or_changing_an_aggregation_is_rejected(self):
        """g44: rollup을 채우면서 aggregation을 avg → sum으로 바꿨다. 집계 값은 옮길 수만 있고 새로 만들 수 없다."""
        for bucket in ("week", "month"):
            for before, invented in (("avg", "sum"), ("sum", "avg"), ("max", "min")):
                base = {"bucket": bucket, "aggregation": before}
                with self.subTest(bucket=bucket, before=before):
                    self.assertEqual(blocked(base, {"bucket": bucket, "aggregation": invented,
                                                    "rollup": before}), {"aggregation"})
                    # 값을 버리고 다른 rollup을 적는 것도 집계를 만들어 낸 것이다.
                    self.assertEqual(blocked(base, {"bucket": bucket, "rollup": invented}), {"aggregation"})
        # 집계가 없던 grounding에 집계를 새로 적는 것도 받지 않는다(답 대상 오류를 고치는 중).
        base = {"bucket": "week", "rollup": "avg", "answer": "bucket"}
        self.assertEqual(blocked(base, {"bucket": "week", "rollup": "max", "answer": "bucket",
                                        "aggregation": "sum"}), {"aggregation"})

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
                self.assertEqual(shown, set(correction_scope(grounding_factors).permissions))


if __name__ == "__main__":
    unittest.main()
