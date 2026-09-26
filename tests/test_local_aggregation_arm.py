# -*- coding: utf-8 -*-
"""L1: H0 grounding 뒤 구간 집계일 때만 부르는 집계 전용 보정. 평가 전용."""

import dataclasses
import hashlib
import json
import os
import unittest

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import aggregation_refinement as R
import evaluate_prompt_ab as A
from geoflow import factors as F
from geoflow.composer import MacroComposer
from geoflow.grounding import parse_grounding
from geoflow.macros import MacroLibrary
from tests.test_prompt_ab_harness import FakeLLM, FakeServer, make_reset

CONCEPTS = [
    {"id": "op", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
     "source": "implicit"},
    {"id": "revenue", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
     "source": "implicit"},
]
ITEM = {
    "id": "x01_p0", "question": "월별 택시 수입의 최대값은?",
    "expected_concepts": ["EVENT/operation:SUPPORT", "AMOUNT/revenue:MEASURE"],
    "expected_macros": ["EVENT_TO_MEASURE"], "expected_operators": ["OPERATION_METRIC"],
    "expected_tool_args": {"metric": "revenue", "bucket": "month", "aggregation": None,
                           "rollup": "max"},
}


def grounding(factors):
    return json.dumps({"concepts": CONCEPTS, "factors": factors}, ensure_ascii=False)


def refiner(inner, final, **extra):
    return json.dumps({"inner_reducer": inner, "final_reducer": final, **extra})


def observe(variant, contents, item=ITEM):
    server = FakeServer()
    llm = FakeLLM(contents, server)
    record = A.observe(item, arm="A", variant=A.build_variant(variant), repetition=1,
                       position=1, pair_index=0, reset=make_reset(server), client=llm,
                       composer=MacroComposer(MacroLibrary.from_directory()))
    return record, llm


class ContractTest(unittest.TestCase):
    def test_first_call_is_the_production_prompt(self):
        l1, h0 = A.build_variant("L1_AGG"), A.build_variant("H0_AGG")
        self.assertEqual(l1.prompt, h0.prompt)
        self.assertEqual(l1.prompt, A._production_prompt())
        self.assertEqual(l1.repair_sha256, h0.repair_sha256)
        self.assertIsNone(l1.grounding_adapter)
        self.assertIsNone(h0.aggregation_refiner)

    def test_refiner_prompt_is_pinned(self):
        variant = A.build_variant("L1_AGG")
        self.assertEqual(variant.refiner_sha256, A.PINNED_REFINER_SHA256["L1_AGG"])
        self.assertEqual(hashlib.sha256(R.system_prompt().encode()).hexdigest(),
                         variant.refiner_sha256)

    def test_refiner_values_come_from_the_factor_specs(self):
        original = dict(F.FACTOR_SPECS)
        try:
            for name in ("aggregation", "rollup"):
                F.FACTOR_SPECS[name] = dataclasses.replace(
                    original[name], values=original[name].values | {"p90"})
            self.assertIn("avg | max | med | min | p90 | sum | unspecified", R.system_prompt())
            self.assertIn("final_reducer: avg | max | med | min | p90 | sum", R.system_prompt())
        finally:
            F.FACTOR_SPECS.clear()
            F.FACTOR_SPECS.update(original)

    def test_refiner_prompt_mentions_nothing_else(self):
        prompt = R.system_prompt()
        for word in ("taxi_type", "LOCATION", "date", "dimension", "concepts"):
            self.assertNotIn(word, prompt)

    def test_trigger_reads_structure_not_the_question(self):
        with_bucket = parse_grounding({"concepts": CONCEPTS, "factors": {"bucket": "week"}}, "a")
        same = parse_grounding({"concepts": CONCEPTS, "factors": {"bucket": "week"}}, "전혀 다른")
        self.assertTrue(R.triggered(with_bucket))
        self.assertTrue(R.triggered(same))
        for factors in ({}, {"aggregation": "max"}, {"date": "last_week", "aggregation": "min"},
                        {"rollup": "avg"}):
            self.assertFalse(R.triggered(parse_grounding(
                {"concepts": CONCEPTS, "factors": factors}, "월별 합산 주마다")))
        self.assertFalse(R.triggered(None))


class PatchTest(unittest.TestCase):
    def _before(self, **factors):
        return parse_grounding({"concepts": CONCEPTS, "factors": factors}, "q")

    def test_patch_moves_and_removes_values(self):
        before = self._before(bucket="month", aggregation="max", taxi_type="private")
        after = R.apply_patch(before, R.AggregationStagePatch("unspecified", "max"))
        self.assertEqual(after.factors, {"bucket": "month", "taxi_type": "private",
                                         "rollup": "max"})
        after = R.apply_patch(before, R.AggregationStagePatch("sum", "avg"))
        self.assertEqual(after.factors, {"bucket": "month", "aggregation": "sum",
                                         "taxi_type": "private", "rollup": "avg"})
        self.assertEqual(before.factors, {"bucket": "month", "aggregation": "max",
                                          "taxi_type": "private"})

    def test_output_contract(self):
        self.assertEqual(R.parse_patch({"inner_reducer": "sum", "final_reducer": "avg",
                                        "reason": "x"}),
                         R.AggregationStagePatch("sum", "avg"))
        for payload in ({"inner_reducer": "sum"},
                        {"inner_reducer": "sum", "final_reducer": "unspecified"},
                        {"inner_reducer": "mean", "final_reducer": "avg"},
                        {"inner_reducer": "sum", "final_reducer": "avg", "bucket": "week"},
                        {"inner_reducer": "sum", "final_reducer": "avg", "date": "last_week"},
                        {"inner_reducer": ["sum"], "final_reducer": "avg"},
                        ["sum", "avg"]):
            with self.subTest(payload=payload):
                with self.assertRaises(R.RefinementError) as caught:
                    R.parse_patch(payload)
                self.assertEqual(caught.exception.code, R.REFINER_INVALID_OUTPUT)

    def test_scope_guard_rejects_anything_outside_aggregation_and_rollup(self):
        before = self._before(bucket="month", aggregation="max", date="last_month")
        for factors in ({"bucket": "week", "rollup": "max"},
                        {"bucket": "month", "rollup": "max"},
                        {"bucket": "month", "rollup": "max", "date": "last_month",
                         "taxi_type": "private"},
                        {"rollup": "max", "date": "last_month"}):
            after = dataclasses.replace(before, factors=factors)
            with self.subTest(factors=factors):
                with self.assertRaises(R.RefinementError) as caught:
                    R.check_scope(before, after)
                self.assertEqual(caught.exception.code, R.PATCH_SCOPE_VIOLATION)
        after = dataclasses.replace(before, concepts=before.concepts[:1])
        with self.assertRaises(R.RefinementError):
            R.check_scope(before, after)


class ObservationTest(unittest.TestCase):
    def test_not_triggered_is_the_h0_observation(self):
        content = grounding({"date": "last_week", "aggregation": "min"})
        item = {**ITEM, "expected_tool_args": {"metric": "revenue", "aggregation": "min"}}
        h0, _ = observe("H0_AGG", [content], item)
        l1, llm = observe("L1_AGG", [content], item)
        self.assertEqual(llm.calls, 1)
        self.assertEqual(l1["aggregation_refinement"], {"outcome": R.NOT_TRIGGERED})
        for key in ("status", "validated", "strict_correct", "final_tool", "final_tool_args",
                    "factors", "raw_text", "planner_calls", "repair_attempted"):
            self.assertEqual(l1[key], h0[key], key)

    def test_rejected_first_grounding_is_recorded_as_not_triggered(self):
        content = grounding({"bucket": "month", "dimension": "month"})
        h0, _ = observe("H0_AGG", [content])
        l1, llm = observe("L1_AGG", [content])
        self.assertEqual(l1["status"], "INVALID_FACTOR")
        self.assertEqual(llm.calls, 1)
        self.assertEqual(l1["aggregation_refinement"], {"outcome": R.NOT_TRIGGERED})
        self.assertIsNone(h0["aggregation_refinement"])

    def test_applied_patch_moves_the_final_reducer(self):
        """b24_p3 모양: 최종 집계를 aggregation에 적고 rollup이 없다."""
        h0, _ = observe("H0_AGG", [grounding({"bucket": "month", "aggregation": "max"}),
                                   json.dumps({"factors": {"rollup": "sum"}})])
        self.assertTrue(h0["repair_attempted"])
        self.assertFalse(h0["strict_correct"])
        l1, llm = observe("L1_AGG", [grounding({"bucket": "month", "aggregation": "max"}),
                                     refiner("unspecified", "max")])
        self.assertEqual(llm.calls, 2)
        refinement = l1["aggregation_refinement"]
        self.assertEqual(refinement["outcome"], R.APPLIED)
        self.assertEqual(refinement["factors_after"], {"bucket": "month", "rollup": "max"})
        # b24 golden은 구간 안 집계가 없다. 예전에는 Tool 기본값으로 실행되어 strict
        # 정답이었고, 지금은 질문에 없는 구간 안 집계를 채우지 않아 거부된다.
        self.assertEqual(l1["status"], "AMBIGUOUS_INNER_AGGREGATION")
        self.assertFalse(l1["strict_correct"])
        self.assertFalse(l1["repair_attempted"])
        self.assertEqual([c["phase"] for c in l1["llm_calls"]],
                         ["initial", "aggregation_refinement"])
        self.assertEqual(l1["raw_text"], h0["raw_text"])
        self.assertEqual(l1["measurement"], A.VALID)

    def test_refiner_sees_only_the_aggregation_context(self):
        _l1, llm = observe("L1_AGG", [grounding({"bucket": "month", "aggregation": "max",
                                                 "taxi_type": "private"}),
                                      refiner("unspecified", "max")])
        system, user = llm.requests[1]
        self.assertEqual(system["content"], R.system_prompt())
        self.assertEqual(user["content"], "질문: 월별 택시 수입의 최대값은?\n구간 단위: month\n"
                                          "앞 단계의 aggregation: max\n앞 단계의 rollup: (없음)")

    def test_broken_refiner_falls_back_to_the_h0_path(self):
        first = grounding({"bucket": "month", "aggregation": "max"})
        repair = json.dumps({"factors": {"rollup": "sum"}})
        h0, _ = observe("H0_AGG", [first, repair])
        for bad, reason in (("not json", R.REFINER_INVALID_JSON),
                            (refiner("sum", "avg", bucket="week"), R.REFINER_INVALID_OUTPUT),
                            (refiner("sum", "unspecified"), R.REFINER_INVALID_OUTPUT)):
            with self.subTest(reason=reason, bad=bad):
                l1, llm = observe("L1_AGG", [first, bad, repair])
                self.assertEqual(llm.calls, 3)
                self.assertEqual(l1["aggregation_refinement"]["outcome"], R.FALLBACK)
                self.assertEqual(l1["aggregation_refinement"]["reason"], reason)
                for key in ("status", "validated", "strict_correct", "final_tool_args",
                            "repair_attempted", "repair_succeeded"):
                    self.assertEqual(l1[key], h0[key], key)

    def test_no_ordinary_repair_after_an_applied_refinement(self):
        concepts = [{"id": "p", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
                     "source": "user", "value": {"name": "대구", "region": ""}}, *CONCEPTS]
        first = json.dumps({"concepts": concepts,
                            "factors": {"bucket": "month", "aggregation": "max",
                                        "order": "top"}})
        l1, llm = observe("L1_AGG", [first, refiner("unspecified", "max")])
        self.assertEqual(llm.calls, 2)
        self.assertEqual(l1["aggregation_refinement"]["outcome"], R.APPLIED)
        self.assertFalse(l1["validated"])
        self.assertFalse(l1["repair_attempted"])
        self.assertEqual(l1["repair_skipped"], "refinement_used_budget")


if __name__ == "__main__":
    unittest.main()
