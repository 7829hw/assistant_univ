# -*- coding: utf-8 -*-
"""사전 등록한 H0 vs L1 판정 규칙과 관측 주석을 못박는다."""

import json
import os
import tempfile
import unittest

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import local_aggregation_ab as L
import paraphrase_corpus as P
from tests.test_prompt_ab_harness import run

REVENUE = [
    {"id": "op", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
     "source": "implicit"},
    {"id": "revenue", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
     "source": "implicit"},
]


def grounding(factors):
    return json.dumps({"concepts": REVENUE, "factors": factors}, ensure_ascii=False)


def arm(**overrides):
    base = {"silent_intents": ["l01"], "strict_intents": ["l14", "l15"],
            "aggregation_stage_silent": 3, "stage_swapped": 2}
    return {**base, **overrides}


def result(h0, l1, **overrides):
    base = {"arms": {"H0": h0, "L1": l1}, "not_triggered_behavior_diff": [],
            "control_behavior_diff": [], "scope_violations": [],
            "latency_ratio": 1.1, "extra_calls_per_observation": 0.3}
    return {**base, **overrides}


class DecisionTest(unittest.TestCase):
    BETTER = dict(silent_intents=[], aggregation_stage_silent=0, stage_swapped=0,
                  strict_intents=["l01", "l14", "l15"])

    def test_clear_improvement(self):
        self.assertEqual(L.decide(result(arm(), arm(**self.BETTER)))["case"], "A")

    def test_a_new_silent_intent_discards(self):
        decision = L.decide(result(arm(), arm(**{**self.BETTER, "silent_intents": ["l16"]})))
        self.assertEqual(decision["case"], "B")
        self.assertEqual(decision["new_silent_intents"], ["l16"])

    def test_any_control_difference_discards(self):
        for key in ("not_triggered_behavior_diff", "control_behavior_diff", "scope_violations"):
            with self.subTest(key=key):
                self.assertEqual(L.decide(result(arm(), arm(**self.BETTER),
                                                 **{key: ["l14_p0"]}))["case"], "B")

    def test_no_aggregation_improvement(self):
        self.assertEqual(L.decide(result(arm(), arm(silent_intents=[])))["case"], "C")
        more_swaps = dict(self.BETTER, stage_swapped=3)
        self.assertEqual(L.decide(result(arm(), arm(**more_swaps)))["case"], "C")

    def test_fewer_strict_intents_discards(self):
        self.assertEqual(L.decide(result(arm(), arm(**{**self.BETTER,
                                                       "strict_intents": ["l14"]})))["case"], "B")

    def test_cost_is_a_separate_tradeoff(self):
        for cost in ({"latency_ratio": 1.6}, {"extra_calls_per_observation": 0.8}):
            with self.subTest(cost=cost):
                self.assertEqual(L.decide(result(arm(), arm(**self.BETTER), **cost))["case"], "D")


class EndToEndTest(unittest.TestCase):
    def _items(self, ids):
        return [item for item in P.load_corpus_items(L.HOLDOUT) if item["id"] in ids]

    def test_analyze_a_real_run_directory(self):
        swapped = grounding({"bucket": "week", "aggregation": "min"})
        repair = json.dumps({"factors": {"rollup": "min"}})
        refined = json.dumps({"inner_reducer": "unspecified", "final_reducer": "min"})
        control = grounding({"date": "last_week", "aggregation": "max"})
        # arm_order: 반복 1에서 첫 질문(l06_p0)은 L1부터, 둘째(l14_p0)는 H0부터
        contents = [swapped, refined, swapped, repair, control, control]
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, self._items({"l06_p0", "l14_p0"}), contents,
                                arms=("H0_AGG", "L1_AGG"))
            out = L.analyze(run_dir)
        h0, l1 = out["primary"]["arms"]["H0"], out["primary"]["arms"]["L1"]
        self.assertEqual(out["first_grounding_identity"]["identical"], 2)
        self.assertEqual(h0["silent_intents"], ["l06_week_unspecified_min_revenue"])
        self.assertEqual(l1["silent_intents"], [])
        self.assertEqual((h0["aggregation_stage_silent"], l1["aggregation_stage_silent"]), (1, 0))
        self.assertEqual(l1["refinement"], {"applied": 1, "not_triggered": 1})
        self.assertEqual(l1["refiner_calls_on_controls"], 0)
        self.assertEqual(out["primary"]["control_behavior_diff"], [])
        self.assertEqual(out["primary"]["not_triggered_behavior_diff"], [])
        self.assertEqual(out["primary"]["scope_violations"], [])
        checks = out["decision"]["checks"]
        self.assertTrue(all(checks.values()), checks)
        self.assertIn(out["decision"]["case"], ("A", "D"))
        self.assertTrue(out["decision"]["F_same_verdict_with_intent_exclusion"])

    def test_a_different_first_grounding_voids_the_pair(self):
        control = grounding({"date": "last_week", "aggregation": "max"})
        other = grounding({"date": "last_week", "aggregation": "min"})
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, self._items({"l14_p0"}), [control, other],
                                arms=("H0_AGG", "L1_AGG"))
            out = L.analyze(run_dir)
        self.assertEqual(out["first_grounding_identity"]["different"], ["l14_p0"])
        self.assertEqual(out["excluded_paraphrases"], ["l14_p0"])
        self.assertEqual(out["decision"]["case"], "INVALID")


if __name__ == "__main__":
    unittest.main()
