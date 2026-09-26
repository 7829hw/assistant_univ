# -*- coding: utf-8 -*-
"""V0: 최종 계획의 의미 서명과 reject-only 의미 검증. 평가 전용."""

import hashlib
import json
import os
import unittest

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import evaluate_prompt_ab as A
import semantic_verifier as V
from geoflow.composer import MacroComposer
from geoflow.grounding import parse_grounding
from geoflow.macros import MacroLibrary
from tests.test_prompt_ab_harness import FakeLLM, FakeServer, make_reset

OP = {"id": "op", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
      "source": "implicit"}
REVENUE = {"id": "revenue", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
           "source": "implicit"}
ITEM = {
    "id": "x01_p0", "question": "개인택시의 평균 수입은?",
    "expected_concepts": ["EVENT/operation:SUPPORT", "AMOUNT/revenue:MEASURE"],
    "expected_macros": ["EVENT_TO_MEASURE"], "expected_operators": ["OPERATION_METRIC"],
    "expected_tool_args": {"metric": "revenue", "taxi_type": "private", "aggregation": "avg"},
}


def plan_of(concepts, factors, question="q"):
    return MacroComposer(MacroLibrary.from_directory()).compose(
        parse_grounding({"concepts": concepts, "factors": factors}, question))


def place(node_id, name, region="", **attributes):
    concept = {"id": node_id, "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
               "source": "user", "value": {"name": name, "region": region}}
    if attributes:
        concept["attributes"] = attributes
    return concept


def verdict(value, *issues):
    return json.dumps({"verdict": value, "issues": list(issues)}, ensure_ascii=False)


def observe(contents, factors=None, item=ITEM):
    server = FakeServer()
    llm = FakeLLM(contents, server)
    grounding = json.dumps({"concepts": [OP, REVENUE],
                            "factors": factors if factors is not None
                            else {"taxi_type": "private", "aggregation": "avg"}})
    record = A.observe(item, arm="A", variant=A.build_variant("V0_VERIFY"), repetition=1,
                       position=1, pair_index=0, reset=make_reset(server),
                       client=FakeLLMPrefix(grounding, llm),
                       composer=MacroComposer(MacroLibrary.from_directory()))
    return record, llm


class FakeLLMPrefix:
    """첫 호출은 grounding, 그 뒤는 준비한 응답."""

    model = "fake-model"

    def __init__(self, first, rest):
        self.first, self.rest, self.sent = first, rest, False

    def chat(self, messages, tools=None):
        if not self.sent:
            self.sent = True
            self.rest.contents.insert(0, self.first)
        return self.rest.chat(messages, tools=tools)


class ContractTest(unittest.TestCase):
    def test_generation_is_the_production_contract(self):
        variant = A.build_variant("V0_VERIFY")
        self.assertEqual(variant.prompt, A._production_prompt())
        self.assertEqual(variant.sha256, A.PINNED_SHA256["H0_AGG"])
        self.assertEqual(variant.repair_sha256, A.PINNED_REPAIR_SHA256["H0_AGG"])
        self.assertIsNone(variant.aggregation_refiner)
        self.assertEqual(hashlib.sha256(V.SYSTEM_PROMPT.encode()).hexdigest(),
                         A.PINNED_VERIFIER_SHA256["V0_VERIFY"])

    def test_prompt_carries_no_known_question(self):
        questions = {item["question"] for item in A.census_items()}
        for question in questions:
            self.assertNotIn(question, V.SYSTEM_PROMPT)
        for literal in ("월 단위로 합산", "지난주와 지난달", "주별 운행률", "개인택시", "법인택시"):
            self.assertNotIn(literal, V.SYSTEM_PROMPT)

    def test_verifier_sees_only_the_question_and_the_signature(self):
        record, llm = observe([verdict("consistent")])
        system, user = llm.requests[1]
        self.assertEqual(system["content"], V.SYSTEM_PROMPT)
        self.assertEqual(user["content"],
                         V.user_message(ITEM["question"],
                                        record["semantic_verification"]["signature_text"]))
        self.assertNotIn("expected", user["content"])
        self.assertNotIn("get_operation_metrics", user["content"])


class SignatureTest(unittest.TestCase):
    def test_two_stage_aggregation_and_defaults(self):
        # 구간 안 집계가 없는 두 단계 계획은 이제 합성되지 않는다(Tool 기본값을 구간
        # 안 집계로 쓰지 않는다). 그래서 구간 안 집계를 명시한 계획으로 렌더링을 본다.
        plan = plan_of([OP, REVENUE], {"bucket": "month", "aggregation": "avg",
                                       "rollup": "sum"})
        text = V.render(V.signature_of(plan))
        self.assertIn("[bucket] 기간을 월 단위 구간으로 나눈다", text)
        self.assertIn("[aggregation] 각 구간 안의 원시 값을 모으는 방식: 평균", text)
        self.assertNotIn("[aggregation] 각 구간 안의 원시 값을 모으는 방식: 평균 "
                         "(질문이 정하지 않아 쓰는 기본값)", text)
        self.assertIn("[rollup] 구간별 결과들을 최종 값 하나로 합치는 방식: 합계", text)
        self.assertIn("[taxi_type] 택시 유형: 전체 택시 (질문이 정하지 않아 쓰는 기본값)", text)
        text = V.render(V.signature_of(plan_of([OP, REVENUE], {"bucket": "week",
                                                               "aggregation": "sum",
                                                               "rollup": "avg"})))
        self.assertIn("각 구간 안의 원시 값을 모으는 방식: 합계\n", text)

    def test_single_stage_filters(self):
        text = V.render(V.signature_of(plan_of(
            [OP, REVENUE], {"date": "last_week", "taxi_type": "corporate", "aggregation": "max"})))
        self.assertIn("[date] 기간: 지난주", text)
        self.assertIn("[taxi_type] 택시 유형: 법인 택시\n", text)
        self.assertIn("[aggregation] 원시 값을 모으는 방식: 최대", text)
        self.assertIn("[dimension] 그룹으로 나누지 않고 값 하나를 구한다", text)
        self.assertIn("[location] 조회 범위: 지정 없음(전체 지역)", text)

    def test_origin_destination_relation(self):
        trip = [place("a", "초읍동", "부산", od_role="pickup"),
                place("b", "초량동", "부산", od_role="dropoff"),
                {"id": "trip", "concept": "EVENT", "subtype": "trip", "role": "SUPPORT",
                 "source": "implicit"},
                {"id": "count", "concept": "AMOUNT", "subtype": "trip_count", "role": "MEASURE",
                 "source": "implicit"}]
        signature = V.signature_of(plan_of(trip, {}))
        text = V.render(signature)
        self.assertIn("[pickup_location] 승차(출발) 위치: 부산 초읍동", text)
        self.assertIn("[dropoff_location] 하차(도착) 위치: 부산 초량동", text)
        self.assertIn("[aggregation] 해당하는 건수를 센다", text)

    def test_vicinity_time_date_range_and_ranking(self):
        passage = [place("s", "동대구역"),
                   {"id": "p", "concept": "EVENT", "subtype": "passage", "role": "SUPPORT",
                    "source": "implicit"},
                   {"id": "v", "concept": "AMOUNT", "subtype": "speed", "role": "MEASURE",
                    "source": "implicit"}]
        text = V.render(V.signature_of(plan_of(
            passage, {"vicinity": True, "time": "080000-090000", "date": "20260501-20260507"})))
        self.assertIn("[vicinity] 장소 주변 영역까지 포함한다", text)
        self.assertIn("[time] 시간대: 08:00 ~ 09:00", text)
        self.assertIn("[date] 기간: 2026-05-01 ~ 2026-05-07", text)
        text = V.render(V.signature_of(plan_of(
            [OP, REVENUE], {"dimension": "sido", "order": "top", "limit": 3})))
        self.assertIn("[dimension] 결과를 시도별로 나눈 목록으로 보여 준다", text)
        self.assertIn("[order] 값 순서: 상위", text)
        self.assertIn("[limit] 보여 줄 개수: 3", text)

    def test_signature_follows_the_final_tool_arguments(self):
        import paraphrase_corpus as P

        plan = plan_of([OP, REVENUE], {"bucket": "week", "aggregation": "min", "rollup": "max",
                                       "taxi_type": "private", "date": "weekend"})
        _tool, args = P.final_tool_call(plan)
        signature = V.signature_of(plan)
        self.assertEqual(signature.args, {k: v for k, v in args.items() if k != "metric"})
        self.assertEqual(signature.measure, args["metric"])

    def test_every_field_named_in_a_render_is_a_known_field(self):
        import re

        text = V.render(V.signature_of(plan_of([OP, REVENUE], {"bucket": "week",
                                                               "aggregation": "sum",
                                                               "rollup": "max"})))
        for name in re.findall(r"^\[(\w+)\]", text, flags=re.M):
            self.assertIn(name, V.FIELDS)


class VerdictTest(unittest.TestCase):
    Q = "지난주 개인택시 평균 수입은?"

    def test_valid_outputs(self):
        self.assertEqual(V.parse_verdict({"verdict": "consistent"}, self.Q), ("consistent", []))
        self.assertEqual(V.parse_verdict({"verdict": "uncertain", "issues": []}, self.Q),
                         ("uncertain", []))
        issue = {"kind": "missing_constraint", "question_evidence": "개인택시",
                 "plan_field": "taxi_type"}
        self.assertEqual(V.parse_verdict({"verdict": "inconsistent", "issues": [issue]}, self.Q),
                         ("inconsistent", [issue]))
        extra = {"kind": "extra_constraint", "question_evidence": None, "plan_field": "bucket"}
        self.assertEqual(V.parse_verdict({"verdict": "inconsistent", "issues": [extra]},
                                         self.Q)[0], "inconsistent")

    def test_bracketed_field_name_is_the_same_field(self):
        issue = {"kind": "missing_constraint", "question_evidence": "개인택시",
                 "plan_field": "[taxi_type]"}
        _verdict, issues = V.parse_verdict({"verdict": "inconsistent", "issues": [issue]}, self.Q)
        self.assertEqual(issues[0]["plan_field"], "taxi_type")
        for field in ("[taxi_type] 택시 유형: 전체", "[tool]", "taxi_type]"):
            with self.assertRaises(V.VerifierError):
                V.parse_verdict({"verdict": "inconsistent",
                                 "issues": [{**issue, "plan_field": field}]}, self.Q)

    def test_invalid_outputs(self):
        good = {"kind": "missing_constraint", "question_evidence": "개인택시",
                "plan_field": "taxi_type"}
        cases = (
            ({"verdict": "maybe"}, V.VERIFIER_INVALID_OUTPUT),
            ({"verdict": "inconsistent", "issues": []}, V.VERIFIER_INVALID_OUTPUT),
            ({"verdict": "inconsistent", "issues": [{**good, "kind": "typo"}]},
             V.VERIFIER_INVALID_OUTPUT),
            ({"verdict": "inconsistent", "issues": [{**good, "plan_field": "tool"}]},
             V.VERIFIER_INVALID_OUTPUT),
            ({"verdict": "inconsistent", "issues": [{**good, "expected_value": "private"}]},
             V.VERIFIER_INVALID_OUTPUT),
            ({"verdict": "inconsistent", "issues": [{**good, "question_evidence": "법인택시"}]},
             V.EVIDENCE_NOT_IN_QUESTION),
            ({"verdict": "inconsistent", "issues": [{**good, "question_evidence": None}]},
             V.EVIDENCE_NOT_IN_QUESTION),
            ({"verdict": "consistent", "fix": {"taxi_type": "private"}},
             V.VERIFIER_INVALID_OUTPUT),
            (["consistent"], V.VERIFIER_INVALID_OUTPUT),
        )
        for payload, code in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(V.VerifierError) as caught:
                    V.parse_verdict(payload, self.Q)
                self.assertEqual(caught.exception.code, code)


class ObservationTest(unittest.TestCase):
    ISSUE = {"kind": "missing_constraint", "question_evidence": "개인택시",
             "plan_field": "taxi_type"}

    def _check_invariant(self, record):
        """V0 최종 결과는 H0 계획 그대로이거나 계획 없음이다."""
        if record["v0_rejected"]:
            self.assertIsNone(record["v0_final_tool_args"])
            self.assertEqual(record["v0_tool_calls"], 0)
        else:
            self.assertEqual(record["v0_final_tool_args"], record["final_tool_args"])
            self.assertEqual(record["v0_tool_calls"], record["h0_tool_calls"])

    def test_consistent_and_uncertain_keep_the_h0_plan(self):
        for text in (verdict("consistent"), verdict("uncertain")):
            with self.subTest(text=text):
                record, llm = observe([text])
                self.assertEqual(llm.calls, 2)
                self.assertFalse(record["v0_rejected"])
                self.assertEqual(record["h0_tool_calls"], 1)
                self._check_invariant(record)

    def test_inconsistent_rejects_without_calling_a_tool(self):
        record, _ = observe([verdict("inconsistent", self.ISSUE)])
        self.assertTrue(record["v0_rejected"])
        self.assertEqual(record["semantic_verification"]["issues"], [self.ISSUE])
        self._check_invariant(record)
        # H0 기록은 그대로다.
        self.assertTrue(record["strict_correct"])
        self.assertEqual(record["measurement"], A.VALID)

    def test_broken_verifier_falls_back_to_h0(self):
        bad_issue = {**self.ISSUE, "question_evidence": "법인택시"}
        for content, reason in (("not json", V.VERIFIER_INVALID_JSON),
                                (verdict("inconsistent", bad_issue), V.EVIDENCE_NOT_IN_QUESTION),
                                (TimeoutError("t"), V.VERIFIER_CALL_FAILED)):
            with self.subTest(reason=reason):
                record, _ = observe([content])
                self.assertEqual(record["semantic_verification"]["outcome"], V.FALLBACK)
                self.assertEqual(record["semantic_verification"]["reason"], reason)
                self.assertFalse(record["v0_rejected"])
                self.assertEqual(record["measurement"], A.VALID)
                self._check_invariant(record)

    def test_rejected_h0_plan_is_not_verified(self):
        record, llm = observe([], factors={"bucket": "month", "dimension": "month"})
        self.assertEqual(record["status"], "INVALID_FACTOR")
        self.assertEqual(llm.calls, 1)
        self.assertEqual(record["semantic_verification"], {"outcome": V.NOT_CALLED})
        self.assertEqual((record["h0_tool_calls"], record["v0_tool_calls"]), (0, 0))

    def test_generation_record_is_the_h0_record(self):
        h0_server = FakeServer()
        grounding = json.dumps({"concepts": [OP, REVENUE],
                                "factors": {"taxi_type": "private", "aggregation": "avg"}})
        h0 = A.observe(ITEM, arm="A", variant=A.build_variant("H0_AGG"), repetition=1,
                       position=1, pair_index=0, reset=make_reset(h0_server),
                       client=FakeLLM([grounding], h0_server),
                       composer=MacroComposer(MacroLibrary.from_directory()))
        v0, _ = observe([verdict("inconsistent", self.ISSUE)])
        for key in ("status", "validated", "strict_correct", "final_tool", "final_tool_args",
                    "raw_text", "planner_calls"):
            self.assertEqual(json.dumps(v0[key], default=str, sort_keys=True),
                             json.dumps(h0[key], default=str, sort_keys=True), key)
        self.assertEqual([(c["phase"], c["content"]) for c in v0["llm_calls"]],
                         [(c["phase"], c["content"]) for c in h0["llm_calls"]])


if __name__ == "__main__":
    unittest.main()
