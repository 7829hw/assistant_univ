# -*- coding: utf-8 -*-
"""사전 등록한 모델 후보 선택 규칙을 못박는다."""

import os
import unittest

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import evaluate_prompt_ab as A
import failure_census as C
import model_capacity as M


def summary(**overrides):
    base = {"silent_intents": ["f01", "b24", "h12"], "silent": 8,
            "strict_intents": ["b05", "b06"], "strict": 180, "supported_rejection": 9,
            "repair_attempted": 30, "unsupported_collapse": 2,
            "silent_groups": {"aggregation_stage": 6, "taxi_type_grounding": 2}}
    return {**base, **overrides}


def candidate(baseline=None, invalid_rate=0.0, deterministic=True, **overrides):
    return {"baseline": baseline or summary(), "candidate": summary(**overrides),
            "invalid": [], "invalid_rate": invalid_rate, "deterministic": deterministic}


BETTER = dict(silent_intents=["f01"], silent=4, strict_intents=["b05", "b06", "f02"],
              silent_groups={"aggregation_stage": 4})


class SelectionTest(unittest.TestCase):
    def test_a_better_model_is_selected(self):
        result = M.select(None, {"M2": candidate(**BETTER)})
        self.assertEqual(result["selected"], "M2")
        self.assertTrue(result["fresh_holdout_needed"])

    def test_each_check_can_block(self):
        cases = {
            "A_fewer_silent_intents": dict(BETTER, silent_intents=["f01", "b24", "h12"]),
            "B_no_new_silent_family": dict(BETTER, silent_groups={"od_role": 1}),
            "C_strict_intents_not_worse": dict(BETTER, strict_intents=["b05"]),
            "D_unsupported_collapse_not_worse": dict(BETTER, unsupported_collapse=3),
        }
        for check, overrides in cases.items():
            with self.subTest(check=check):
                result = M.select(None, {"M2": candidate(**overrides)})
                self.assertFalse(result["verdicts"]["M2"]["checks"][check])
                self.assertIsNone(result["selected"])
        for blocked in (candidate(invalid_rate=0.06, **BETTER),
                        candidate(deterministic=False, **BETTER)):
            self.assertIsNone(M.select(None, {"M2": blocked})["selected"])

    def test_ties_prefer_the_smaller_model(self):
        result = M.select(None, {"M1": candidate(**BETTER), "M2": candidate(**BETTER)})
        self.assertEqual(result["selected"], "M1")

    def test_fewer_silent_intents_wins_over_size(self):
        result = M.select(None, {"M1": candidate(**BETTER),
                                 "M2": candidate(**dict(BETTER, silent_intents=[]))})
        self.assertEqual(result["selected"], "M2")


class CategoryTest(unittest.TestCase):
    def test_taxi_categories(self):
        def row(families, correct=False, outcome=C.SILENT_WRONG_PLAN):
            return {"families": families, "final_correct": correct, "outcome": outcome}
        self.assertEqual(M.taxi_category(row([], True, C.CORRECT)), "correct")
        self.assertEqual(M.taxi_category(row(["taxi_type_as_concept"])), "conceptized")
        self.assertEqual(M.taxi_category(row(["missing_factor:taxi_type"])), "factor_omitted")
        self.assertEqual(M.taxi_category(row(["fabricated_scope"])), "fabricated_scope")
        self.assertEqual(M.taxi_category(row(["wrong_measure"])), "silent_other")
        self.assertEqual(M.taxi_category(row([], outcome=C.SUPPORTED_REJECTION)),
                         "rejected_other")

    def test_canaries_are_census_questions(self):
        ids = {item["id"] for item in A.census_items()}
        self.assertTrue(set(M.CANARY_IDS) <= ids)


class UnloadTest(unittest.TestCase):
    def test_every_loaded_model_is_unloaded(self):
        class Http:
            def __init__(self):
                self.loaded = ["qwen3:8b", "qwen3.8:27b"]
                self.posted = []

            def get(self, url, timeout):
                loaded = list(self.loaded)

                class R:
                    def json(self_inner):
                        return {"models": [{"name": n} for n in loaded]}
                return R()

            def post(self, url, json, timeout):
                self.posted.append(json["model"])
                self.loaded.remove(json["model"])

        http = Http()
        self.assertEqual(A.unload_all_models("http://x", http=http), ["qwen3:8b", "qwen3.8:27b"])
        self.assertEqual(http.loaded, [])


if __name__ == "__main__":
    unittest.main()
