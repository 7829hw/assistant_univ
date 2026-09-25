# -*- coding: utf-8 -*-
"""reject-only 의미 검증기(H0 vs V0) fresh holdout과 그 golden을 못박는다."""

import hashlib
import os
import unittest
from collections import Counter

import yaml

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import evaluate_prompt_ab as A
import paraphrase_corpus as P
from geoflow import validator as geoflow_validator
from geoflow.composer import MacroComposer
from geoflow.grounding import parse_grounding
from geoflow.macros import MacroLibrary
from tests.test_geoflow_composition import new_tool_executor

HOLDOUT = P.BASE_DIR / "evaluation" / "paraphrases_verifier_holdout.yaml"
REGISTRY = yaml.safe_load((P.BASE_DIR / "evaluation" / "corpus_registry.yaml")
                          .read_text(encoding="utf-8"))
FAMILIES = ("A_aggregation", "B_taxi_type", "C_date_time", "D_od_relation",
            "E_unsupported_collapse", "F_location")


class VerifierHoldoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parents = P.corpus_parents(HOLDOUT)
        cls.intents = P.load_corpus(HOLDOUT, cls.parents)
        cls.items = P.load_corpus_items(HOLDOUT)

    def test_registered_and_pinned(self):
        entry = next(e for e in REGISTRY["corpora"] if e["path"].endswith(HOLDOUT.name))
        self.assertEqual(entry["role"], "fresh_holdout")
        self.assertEqual(entry["sha256"], hashlib.sha256(HOLDOUT.read_bytes()).hexdigest())

    def test_size_and_families(self):
        per_intent = Counter(item["intent_id"] for item in self.items)
        self.assertEqual(len(per_intent), 24)
        self.assertTrue(all(n == 3 for n in per_intent.values()))
        for family in FAMILIES:
            members = [i for i in self.intents if i["family"] == family]
            with self.subTest(family=family):
                self.assertEqual(len(members), 4)
                self.assertEqual(sum(bool(i["control"]) for i in members), 1)
        unsupported = [i for i in self.intents if i["golden"] == {"unsupported": True}]
        self.assertEqual({i["family"] for i in unsupported}, {"E_unsupported_collapse"})
        self.assertEqual(len(unsupported), 3)

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

    def test_labels_never_reach_the_verifier_input(self):
        """검증기 입력은 질문과 서명뿐이다. corpus의 family/control/golden은 쓰지 않는다."""
        import inspect

        import semantic_verifier as V
        source = inspect.getsource(A.verify_observation) + inspect.getsource(V.verify)
        for word in ("expected_tool_args", "golden", "family", "control", "expected_macros"):
            self.assertNotIn(word, source)


if __name__ == "__main__":
    unittest.main()
