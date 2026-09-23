# -*- coding: utf-8 -*-
"""사전 등록한 H0 vs H2 판정 규칙과 관측 주석을 못박는다."""

import os
import unittest

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import aggregation_ab as B
import aggregation_plan as AP


def summary(**overrides):
    base = {"two_stage_explicit_silent": 5, "invented_inner": 1, "no_bucket_strict": 12,
            "silent_intents": ["a01", "a02"], "strict_intents": ["a13", "a14"],
            "pipeline_failures": {}}
    return {**base, **overrides}


class DecisionTest(unittest.TestCase):
    def test_clear_improvement(self):
        result = B.decide(summary(), summary(two_stage_explicit_silent=1, silent_intents=["a01"],
                                             strict_intents=["a02", "a13", "a14"]))
        self.assertEqual(result["case"], "A")

    def test_a_new_silent_intent_blocks_adoption(self):
        result = B.decide(summary(), summary(two_stage_explicit_silent=1, silent_intents=["a09"]))
        self.assertNotIn(result["case"], ("A", "A_TRADEOFF"))
        self.assertEqual(result["new_silent_intents"], ["a09"])

    def test_tradeoff_needs_a_person(self):
        result = B.decide(summary(), summary(two_stage_explicit_silent=1, silent_intents=["a01"],
                                             strict_intents=["a13"]))
        self.assertEqual(result["case"], "A_TRADEOFF")

    def test_more_silent_intents_is_worse(self):
        result = B.decide(summary(), summary(silent_intents=["a01", "a02", "a03"]))
        self.assertEqual(result["case"], "C")

    def test_equal_silent_fewer_strict_is_worse(self):
        result = B.decide(summary(), summary(strict_intents=["a13"]))
        self.assertEqual(result["case"], "C")

    def test_tie_is_not_adopted(self):
        self.assertEqual(B.decide(summary(), summary())["case"], "B")

    def test_controls_can_block(self):
        better = dict(two_stage_explicit_silent=1, silent_intents=["a01"])
        for control in ({"invented_inner": 3}, {"no_bucket_strict": 10},
                        {"pipeline_failures": {"NO_OPERATOR": 1}}):
            with self.subTest(control=control):
                self.assertEqual(B.decide(summary(), summary(**better, **control))["case"], "B")


class AnnotateTest(unittest.TestCase):
    ITEM = {"semantic_aggregation": {"bucket": "month", "inner": "sum", "final": "avg"}}
    GOLDEN = {"concepts": [], "factors": {}}

    def _row(self, variant, factors, **extra):
        import json
        return {"id": "a01_p0", "intent_id": "a01", "variant": variant,
                "raw_text": json.dumps({"concepts": [], "factors": factors}),
                "status": "OK", "validated": True, "strict_correct": False,
                "repair_attempted": False, **extra}

    def test_h0_final_reducer_written_as_aggregation_is_a_stage_swap(self):
        row = B.annotate(self._row("H0_AGG", {"bucket": "month", "aggregation": "avg"}),
                         self.ITEM, self.GOLDEN)
        self.assertEqual(row["arm"], "H0")
        self.assertIn(AP.STAGE_SWAPPED, row["aggregation_errors"])
        self.assertTrue(row["silent_wrong"])

    def test_h2_reads_the_plan(self):
        plan = {"bucket": {"unit": "month", "reducer": "unspecified"}, "result": {"reducer": "avg"}}
        row = B.annotate(self._row("H2_AGG", {AP.PLAN_KEY: plan}), self.ITEM, self.GOLDEN)
        self.assertEqual(row["aggregation_errors"], [AP.INNER_REDUCER_OMITTED])
        self.assertTrue(row["explicit_inner_left_unspecified"])

    def test_lowering_rejection_is_not_silent(self):
        row = B.annotate(self._row("H2_AGG", {"rollup": "avg"}, status=AP.FLAT_AGGREGATION_FACTOR,
                                   validated=False), self.ITEM, self.GOLDEN)
        self.assertFalse(row["silent_wrong"])
        self.assertEqual(row["plan_code"], AP.FLAT_AGGREGATION_FACTOR)

    def test_cells_match_the_corpus_test(self):
        self.assertEqual(B.cell_of(None, None), "G_unsupported")
        self.assertEqual(B.cell_of({"final": "avg"}, {}), "D_no_bucket")
        self.assertEqual(B.cell_of({"bucket": "week", "inner": "unspecified", "final": "max"},
                                   {"factors": {"taxi_type": "corporate"}}), "E_taxi_type")



class EndToEndTest(unittest.TestCase):
    def test_analyze_reads_a_real_run_directory(self):
        import json
        import tempfile
        import paraphrase_corpus as P
        from tests.test_prompt_ab_harness import run
        items = [item for item in P.load_corpus_items(B.HOLDOUT)
                 if item["id"] in ("a01_p0", "a21_p0")]
        concepts = [
            {"id": "op", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
             "source": "implicit"},
            {"id": "hours", "concept": "AMOUNT", "subtype": "hours", "role": "MEASURE",
             "source": "implicit"}]
        h0 = json.dumps({"concepts": concepts,
                         "factors": {"bucket": "week", "aggregation": "sum", "rollup": "avg"}})
        h2 = json.dumps({"concepts": concepts, "factors": {AP.PLAN_KEY: {
            "bucket": {"unit": "week", "reducer": "sum"}, "result": {"reducer": "avg"}}}})
        refuse = json.dumps({"unsupported": True})
        # arm_order: 첫 질문은 B(H2)부터, 둘째 질문은 A(H0)부터
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, items, [h2, h0, refuse, refuse], arms=("H0_AGG", "H2_AGG"))
            result = B.analyze(run_dir)
        for arm in ("H0", "H2"):
            self.assertEqual(result["arms"][arm]["final_strict"], 2)
            self.assertEqual(result["arms"][arm]["silent_intents"], [])
        self.assertEqual(result["decision"]["case"], "B")


class ExclusionTest(unittest.TestCase):
    def test_an_invalid_observation_drops_the_paraphrase_from_both_arms(self):
        import json
        import tempfile
        import paraphrase_corpus as P
        from tests.test_prompt_ab_harness import run
        items = [item for item in P.load_corpus_items(B.HOLDOUT)
                 if item["id"] in ("a21_p0", "a21_p1")]
        refuse = json.dumps({"unsupported": True})
        # a21_p0의 H2 관측: 재시도가 두 번 생겨 무효. a21_p1은 정상.
        contents = [TimeoutError("t"), refuse, TimeoutError("t"), refuse, refuse,
                    refuse, refuse]
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, _, _ = run(tmp, items, contents, arms=("H0_AGG", "H2_AGG"),
                                max_invalid=5)
            result = B.analyze(run_dir)
        self.assertEqual([entry["id"] for entry in result["excluded_paraphrases"]],
                         ["a21_p0", "a21_p0"])
        self.assertEqual({row["id"] for row in result["rows"]}, {"a21_p1"})
        self.assertEqual(result["arms"]["H0"]["observations"], 1)
        self.assertEqual(result["arms"]["H2"]["observations"], 1)


if __name__ == "__main__":
    unittest.main()
