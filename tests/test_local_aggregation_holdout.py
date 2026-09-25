# -*- coding: utf-8 -*-
"""국소 집계 보정(H0 vs L1) fresh holdout과 그 golden을 못박는다."""

import hashlib
import os
import unittest

import yaml

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import aggregation_refinement as R
import evaluate_prompt_ab as A
import paraphrase_corpus as P
from geoflow import validator as geoflow_validator
from geoflow.composer import MacroComposer
from geoflow.grounding import parse_grounding
from geoflow.macros import MacroLibrary
from tests.test_geoflow_composition import new_tool_executor

HOLDOUT = P.BASE_DIR / "evaluation" / "paraphrases_local_aggregation_holdout.yaml"
REGISTRY = yaml.safe_load((P.BASE_DIR / "evaluation" / "corpus_registry.yaml")
                          .read_text(encoding="utf-8"))


class LocalHoldoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents = P.corpus_parents(HOLDOUT)
        cls.intents = P.load_corpus(HOLDOUT, cls.parents)
        cls.items = P.load_corpus_items(HOLDOUT)

    def test_registered_and_pinned(self):
        """H0 vs L1 판정에 한 번 썼으므로 이제 development다."""
        entry = next(e for e in REGISTRY["corpora"] if e["path"].endswith(HOLDOUT.name))
        self.assertEqual(entry["role"], "development")
        self.assertTrue(any("20260925_121002" in line for line in entry["history"]))
        self.assertEqual(entry["sha256"], hashlib.sha256(HOLDOUT.read_bytes()).hexdigest())

    def test_size(self):
        per_intent = {}
        for item in self.items:
            per_intent[item["intent_id"]] = per_intent.get(item["intent_id"], 0) + 1
        self.assertGreaterEqual(len(per_intent), 20)
        self.assertTrue(all(n == 3 for n in per_intent.values()))

    def test_disjoint_from_every_other_corpus_stub_and_census(self):
        for entry in REGISTRY["corpora"]:
            path = P.BASE_DIR / entry["path"]
            if path == HOLDOUT:
                continue
            with self.subTest(corpus=path.name):
                self.assertEqual(P.corpus_overlap(path, HOLDOUT),
                                 {"intents": [], "questions": [], "parents_used": []})
        known = {P.normalize_question(item["question"]) for item in A.census_items()}
        for item in self.items:
            self.assertNotIn(P.normalize_question(item["question"]), known)
        self.assertFalse(set(self.parents) & set(P.load_parents()))

    def test_half_triggers_and_half_are_controls(self):
        trigger = [i["intent"] for i in self.intents if i["trigger_expected"]]
        control = [i["intent"] for i in self.intents if not i["trigger_expected"]]
        self.assertEqual(len(trigger), 13)
        self.assertEqual(len(control), 11)
        pairs = {(i["aggregation"]["inner"], i["aggregation"]["final"])
                 for i in self.intents if i["trigger_expected"]}
        for pair in (("sum", "avg"), ("sum", "max"), ("avg", "min"), ("min", "avg"),
                     ("max", "sum"), ("unspecified", "min"), ("unspecified", "avg")):
            self.assertIn(pair, pairs)
        unsupported = [i for i in self.intents if i.get("golden") == {"unsupported": True}]
        self.assertEqual(len(unsupported), 2)

    def test_golden_trigger_matches_trigger_expected(self):
        """정답 grounding을 H0가 그대로 읽었다면 보정 여부가 trigger_expected와 같다."""
        for intent in self.intents:
            golden = intent["golden"]
            if golden == {"unsupported": True}:
                self.assertFalse(intent["trigger_expected"])
                continue
            with self.subTest(intent=intent["intent"]):
                grounding = parse_grounding(golden, self.parents[intent["intent"]]["question"])
                self.assertEqual(R.triggered(grounding), intent["trigger_expected"])

    def test_golden_meets_the_label_and_tool_args(self):
        composer = MacroComposer(MacroLibrary.from_directory())
        tools = new_tool_executor().tool_names
        for intent in self.intents:
            parent = self.parents[intent["intent"]]
            if P.NONE_LABEL in parent["expected_macros"]:
                continue
            with self.subTest(intent=intent["intent"]):
                plan = composer.compose(parse_grounding(intent["golden"], parent["question"]))
                self.assertTrue(geoflow_validator.validate(plan, available_tools=tools).ok)
                self.assertEqual(list(plan.applied_macros), parent["expected_macros"])
                self.assertEqual([t.operator for t in plan.transformations],
                                 parent["expected_operators"])
                tool, args = P.final_tool_call(plan)
                self.assertEqual(P.tool_arg_mismatches(
                    intent["expected_tool_args"], args, P.tool_defaults(tool)), [])

    def test_a_swapped_golden_is_not_accidentally_correct(self):
        import aggregation_plan as AP

        checked = 0
        for intent in self.intents:
            semantic = intent["aggregation"]
            if not intent["trigger_expected"] or semantic["inner"] in (
                    AP.UNSPECIFIED, semantic["final"]):
                continue
            swapped = {**semantic, "inner": semantic["final"], "final": semantic["inner"]}
            self.assertNotEqual(P.tool_arg_mismatches(
                intent["expected_tool_args"], AP.semantic_to_flat(swapped),
                P.tool_defaults("get_operation_metrics")), [], intent["intent"])
            checked += 1
        self.assertGreaterEqual(checked, 8)

    def test_trigger_expected_must_agree_with_the_aggregation(self):
        document = yaml.safe_load(HOLDOUT.read_text(encoding="utf-8"))
        document["intents"][0]["trigger_expected"] = False
        self.assertTrue(P.expand_aggregation(document))


if __name__ == "__main__":
    unittest.main()
