# -*- coding: utf-8 -*-
"""factor 수정 재질의의 행동 검증(scripted 모델, LLM 없음).

코드가 할 수 있어야 하는 것만 본다. 실제 모델이 올바른 수정안을 내는지는 평가 실행으로 따로 잰다.

- 최초 응답 → 검증 → 재질의 → 재검증이 같은 계약을 따른다(재질의 문구가 보여 준 수정 범위 = 파서가 받는 범위,
  수정 결과는 합성·검증·컴파일을 처음부터 다시 지난다).
- 잘못 넣은 조건은 바꾸거나 뺄 수 있고, 기록을 고르는 조건(기간·유형)과 개념은 바꿀 수 없다.
- 복구가 끝나기 전에는 Tool을 부르지 않는다. 재질의는 한 번이다.
- 모델이 "질문에 없다"고 답하면 사용자 확인(빠진 짝·답 대상) 또는 지원 범위 밖(계약에 없는 값)이다.
- 올바른 grounding은 재질의 없이 그대로 실행된다.
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
from geoflow.factors import (  # noqa: E402
    CONTRACT_COMPANIONS,
    FACTOR_CONSTRAINTS,
    RESULT_SHAPE_FACTORS,
    describe_factor,
)
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


class WrongConditionIsCorrectedTest(unittest.TestCase):
    """누락 보완만이 아니라 잘못 넣은 조건을 고친다."""

    QUESTION = "지난달 요일별 법인택시 평균 수입이 가장 낮은 요일은?"
    FIRST = {"date": "last_month", "taxi_type": "corporate", "dimension": "dayofweek",
             "aggregation": "avg", "order": "bottom", "limit": 1, "answer": "bucket"}

    def without_answer(self):
        return {key: value for key, value in self.FIRST.items()
                if key in RESULT_SHAPE_FACTORS and key != "answer"}

    def test_answer_on_a_weekday_ranking_is_removed(self):
        """요일 순위의 answer=bucket: 계약상 빠진 것은 bucket이지만 고칠 것은 answer다."""
        result, client = run(self.QUESTION, plan(self.FIRST), {"factors": self.without_answer()})
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)
        self.assertEqual(len(client.calls), 2)
        (first,) = [item for item in result.attempts if item.get("error_code")]
        self.assertEqual((first["error_code"], first["repair_kind"], first["repair_result"]),
                         ("INVALID_FACTOR_COMBINATION", RepairKind.FACTOR_CORRECTION, "OK"))
        self.assertNotIn("answer", first["repaired_factors"])
        # 재질의 문구는 계약에서 만든 두 방법(짝 채우기 / 잘못 넣은 조건 빼기)을 모두 보여 준다.
        instruction = client.calls[1][-1]["content"]
        self.assertIn("bucket에 해당하는 표현이 있으면 채우고, 없으면 answer를 뺍니다", instruction)
        self.assertEqual(tools_called(result), ["get_billing_metrics"])

    def test_echoing_unchanged_record_filters_is_accepted(self):
        """범위 밖 조건(기간·택시 유형)을 지금 값 그대로 되풀이해도 거부하지 않는다."""
        echoed = {key: value for key, value in self.FIRST.items() if key != "answer"}
        result, _ = run(self.QUESTION, plan(self.FIRST), {"factors": echoed})
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)

    def test_omitted_result_shape_factors_are_removed(self):
        """적지 않은 결과 형태 조건은 빠진다(수정안은 고친 뒤의 전체다). 빠진 순위는 재검증에서 드러난다."""
        result, client = run(self.QUESTION, plan(self.FIRST),
                             {"factors": {"dimension": "dayofweek", "aggregation": "avg"}})
        self.assertEqual(len(client.calls), 2)
        (first,) = [item for item in result.attempts if item.get("error_code")][:1]
        self.assertEqual(first["repaired_factors"],
                         {"date": "last_month", "taxi_type": "corporate",
                          "dimension": "dayofweek", "aggregation": "avg"})

    def test_changing_a_record_filter_is_rejected_before_any_tool(self):
        """수정 범위 밖(기간·택시 유형)을 바꾸면 거부하고, 잘못된 계획의 Tool도 부르지 않는다."""
        for outside in ({"date": "this_month"}, {"taxi_type": "private"}):
            with self.subTest(outside=outside):
                result, client = run(self.QUESTION, plan(self.FIRST),
                                     {"factors": {**self.without_answer(), **outside}})
                self.assertNotEqual(result.outcome, OUTCOME_ANSWERED)
                self.assertEqual(result.error["code"], "INVALID_FACTOR_COMBINATION")
                (first,) = [item for item in result.attempts if item.get("error_code")]
                self.assertEqual(first["repair_error"]["code"], "REPAIR_OUT_OF_SCOPE")
                self.assertEqual(tools_called(result), [])
                self.assertEqual(len(client.calls), 2)

    def test_a_correction_that_still_breaks_the_contract_is_not_asked_again(self):
        """수정 결과도 합성·검증을 다시 지난다. 또 어긋나면 재질의하지 않고 멈춘다."""
        result, client = run(self.QUESTION, plan(self.FIRST),
                             {"factors": {**self.FIRST, "bucket": "week", "rollup": "min"}})
        self.assertNotEqual(result.outcome, OUTCOME_ANSWERED)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(tools_called(result), [])
        self.assertEqual(result.error["code"], "UNSUPPORTED_AGGREGATION_COMBINATION")


class AggregationStageTest(unittest.TestCase):
    """구간 안 집계와 구간별 결과의 집계를 따로 둔다. 미지정은 확인 요청으로 남는다."""

    def test_moving_the_only_aggregation_word_to_rollup_leaves_inner_unspecified(self):
        """"월별 수입의 평균": 평균을 aggregation에 둔 첫 응답을 rollup으로 옮기면 구간 안 집계가 비어 확인을 받는다."""
        first = {"date": "last_year", "taxi_type": "corporate", "bucket": "month", "aggregation": "avg"}
        result, client = run("지난해 월별 법인택시 수입의 평균은?", plan(first),
                             {"factors": {"bucket": "month", "rollup": "avg"}})
        self.assertEqual(result.outcome, OUTCOME_NEEDS_CLARIFICATION, result.runtime_error)
        self.assertEqual(result.error["code"], "AMBIGUOUS_INNER_AGGREGATION")
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(tools_called(result), [])

    def test_inner_aggregation_gap_is_never_sent_back_to_the_model(self):
        """구간 안 집계가 없는 grounding은 재질의하지 않는다(모델이 집계를 지어내는 경로를 열지 않는다)."""
        first = {"date": "last_year", "bucket": "month", "rollup": "max"}
        result, client = run("지난해 대구 소속 택시의 월별 수입 중 가장 큰 값은?", plan(first))
        self.assertEqual(result.outcome, OUTCOME_NEEDS_CLARIFICATION)
        self.assertEqual(len(client.calls), 1)

    def test_explicit_inner_and_outer_run_without_repair(self):
        first = {"date": "last_month", "bucket": "week", "aggregation": "sum", "rollup": "avg"}
        result, client = run("지난달 주별 수입 합계의 평균은?", plan(first))
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)
        self.assertEqual(len(client.calls), 1)


class ValueAndBucketTest(unittest.TestCase):
    """값 질문과 그 값을 가진 구간 질문. 올바른 grounding은 재질의 없이 끝난다."""

    def test_value_question_is_answered(self):
        first = {"date": "last_month", "bucket": "week", "aggregation": "sum", "rollup": "max"}
        result, client = run("지난달 주별 수입 합계 중 가장 큰 값은?", plan(first))
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)
        self.assertEqual(len(client.calls), 1)

    def test_bucket_question_stops_on_the_provider_contract_without_repair(self):
        first = {"date": "last_month", "bucket": "week", "aggregation": "sum", "rollup": "max",
                 "answer": "bucket"}
        result, client = run("지난달 수입 합계가 가장 큰 주는?", plan(first))
        self.assertEqual(result.outcome, OUTCOME_UNSUPPORTED)
        self.assertEqual(result.error["code"], "UNVERIFIED_TIMS_CONTRACT")
        self.assertEqual(len(client.calls), 1)

    def test_answer_target_with_a_non_selecting_rollup_is_sent_back(self):
        """answer=bucket인데 rollup이 avg: 답 대상 오류로 재질의한다. 질문에 없다고 하면 확인을 받는다."""
        first = {"date": "last_month", "bucket": "week", "aggregation": "sum", "rollup": "avg",
                 "answer": "bucket"}
        result, client = run("지난달 주별 수입 합계의 평균이 가장 큰 주는?", plan(first),
                             {"unsupported": True})
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(result.outcome, OUTCOME_NEEDS_CLARIFICATION)
        self.assertEqual(result.error["code"], "INVALID_ANSWER_TARGET")


class PlanStageErrorTest(unittest.TestCase):
    """grounding 계약(값 검사)에서 멈춘 오류도 합성 단계 오류와 같은 판정으로 재질의에 닿는다."""

    def test_weekday_written_as_a_bucket_is_corrected(self):
        first = {"date": "this_month", "taxi_type": "corporate", "bucket": "dayofweek",
                 "aggregation": "avg", "rollup": "max"}
        fix = {"factors": {"dimension": "dayofweek", "aggregation": "avg", "order": "top", "limit": 1}}
        result, client = run("이번 달 요일별 법인택시 평균 수입 중 가장 높은 요일은?", plan(first), fix)
        self.assertEqual(result.outcome, OUTCOME_ANSWERED, result.runtime_error)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(result.attempts[0]["stage"], "planner")
        self.assertEqual(result.attempts[0]["error_code"], "INVALID_FACTOR")
        self.assertEqual(tools_called(result), ["get_billing_metrics"])

    def test_value_outside_the_contract_is_unsupported_when_the_model_says_so(self):
        """시간대별 구간은 계약에 없다. 모델이 표현할 수 없다고 답하면 지원 범위 밖이다."""
        first = {"date": "this_month", "bucket": "hour", "aggregation": "sum", "rollup": "sum"}
        result, client = run("이번 달 수입을 시간대별로 나눠서 보여줘.", plan(first), {"unsupported": True})
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(result.outcome, OUTCOME_UNSUPPORTED)
        self.assertEqual(result.error["code"], "UNSUPPORTED_QUESTION")

    def test_a_correction_cannot_drop_the_grouping(self):
        """계약에 없는 구간 값을 빼고 전체 값으로 답하게 만드는 수정은 범위 밖이다(조용한 오답 대신 멈춘다)."""
        first = {"date": "this_month", "bucket": "hour", "aggregation": "sum", "rollup": "sum"}
        result, client = run("이번 달 수입을 시간대별로 나눠서 보여줘.", plan(first),
                             {"factors": {"aggregation": "sum"}})
        self.assertEqual(len(client.calls), 2)
        self.assertNotEqual(result.outcome, OUTCOME_ANSWERED)
        self.assertEqual(result.attempts[0]["repair_error"]["code"], "REPAIR_OUT_OF_SCOPE")
        self.assertEqual(tools_called(result), [])

    def test_record_filter_value_errors_are_not_sent_back(self):
        """날짜는 조건 계층이 질문 근거로 다룬다(여기서는 "지난달"을 last_month로 보존한다). 재질의로 다시 정하지 않는다."""
        first = {"date": "지난달"}
        _result, client = run("지난달 수입 평균은?", plan(first))
        self.assertEqual(len(client.calls), 1)


class ContractConsistencyTest(unittest.TestCase):
    """재질의가 보여 주는 수정 범위, 파서가 받는 범위, 재검증이 같은 계약이다."""

    def test_every_companion_violation_is_sent_back_with_the_editable_contract(self):
        """짝 규칙마다: 위반한 첫 응답 → 재질의 문구에 고칠 수 있는 조건 전부가 있고, 빠진 짝을 채운 수정안은 받아들여져
        다시 합성된다(같은 오류로 멈추지 않는다)."""
        rules = {factor: constraint.requires for factor, constraint in FACTOR_CONSTRAINTS.items()}
        for factor, (requires, _) in CONTRACT_COMPANIONS.items():
            rules[factor] = tuple(rules.get(factor, ())) + tuple(requires)
        samples = {"bucket": "week", "rollup": "avg", "answer": "bucket", "dimension": "sido",
                   "dimension_target": "pickup", "order": "top", "limit": 3, "aggregation": "sum"}
        for factor, requires in sorted(rules.items()):
            with self.subTest(factor=factor):
                first = {"date": "last_month", factor: samples[factor]}
                if factor == "answer":
                    first["rollup"] = "max"
                fill = {name: value for name, value in first.items() if name in RESULT_SHAPE_FACTORS}
                fill.update({name: samples[name] for name in requires if name not in first})
                result, client = run("지난달 수입은?", plan(first), {"factors": fill})
                self.assertEqual(len(client.calls), 2, result.attempts)
                instruction = client.calls[1][-1]["content"]
                for name in RESULT_SHAPE_FACTORS:
                    self.assertIn(describe_factor(name), instruction)
                first_attempt = result.attempts[0]
                self.assertEqual(first_attempt["repair_result"], "OK", first_attempt)
                first_key = (first_attempt["error_code"],
                             first_attempt["error"]["context"].get("factor"))
                for item in result.attempts[1:]:
                    context = (item.get("error") or {}).get("context") or {}
                    self.assertNotEqual((item.get("error_code"), context.get("factor")), first_key)


if __name__ == "__main__":
    unittest.main()
