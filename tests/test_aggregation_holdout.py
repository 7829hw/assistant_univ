# -*- coding: utf-8 -*-
"""두 단계 집계 fresh holdout과 그 의미 golden을 못박는다.

집계 의미는 intent마다 aggregation 하나에만 적는다. H0 golden(flat factor), H2
golden(aggregation_plan), 기대 Tool 인자는 모두 거기서 유도한다. 두 표현을 거쳐도
같은 Tool 호출이 나와야 한다.
"""

import copy
import hashlib
import os
import unittest

import yaml

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import aggregation_plan as AP
import evaluate_prompt_ab as A
import paraphrase_corpus as P
from geoflow import validator as geoflow_validator
from geoflow.composer import MacroComposer
from geoflow.grounding import parse_grounding
from geoflow.macros import MacroLibrary
from tests.test_geoflow_composition import new_tool_executor

HOLDOUT = P.BASE_DIR / "evaluation" / "paraphrases_aggregation_holdout.yaml"
REGISTRY = yaml.safe_load((P.BASE_DIR / "evaluation" / "corpus_registry.yaml")
                          .read_text(encoding="utf-8"))


def _intents():
    document = yaml.safe_load(HOLDOUT.read_text(encoding="utf-8"))
    problems = P.expand_aggregation(document)
    assert not problems, problems
    return document["intents"]


class PlanLoweringTest(unittest.TestCase):
    def test_single_stage(self):
        self.assertEqual(AP.lower_plan({"result": {"reducer": "avg"}}), {"aggregation": "avg"})

    def test_two_stages(self):
        plan = {"bucket": {"unit": "month", "reducer": "sum"}, "result": {"reducer": "avg"}}
        self.assertEqual(AP.lower_plan(plan),
                         {"bucket": "month", "aggregation": "sum", "rollup": "avg"})

    def test_unspecified_inner_reducer_never_reaches_the_tool(self):
        plan = {"bucket": {"unit": "month", "reducer": "unspecified"}, "result": {"reducer": "sum"}}
        lowered = AP.lower_plan(plan)
        self.assertEqual(lowered, {"bucket": "month", "rollup": "sum"})
        self.assertNotIn(AP.UNSPECIFIED, lowered.values())

    def test_invalid_plans_are_rejected(self):
        for plan in (
            {"result": {"reducer": "unspecified"}},
            {"result": {"reducer": "mean"}},
            {"bucket": {"unit": "day", "reducer": "sum"}, "result": {"reducer": "avg"}},
            {"bucket": {"unit": "month"}, "result": {"reducer": "avg"}},
            {"bucket": {"unit": "month", "reducer": "sum"}},
            {"result": {"reducer": "avg"}, "extra": 1},
            "avg",
        ):
            with self.subTest(plan=plan):
                with self.assertRaises(AP.PlanError) as caught:
                    AP.lower_plan(plan)
                self.assertEqual(caught.exception.code, AP.LOWERING_ERROR)

    def test_flat_aggregation_factors_are_not_a_second_source(self):
        plan = {"result": {"reducer": "avg"}}
        with self.assertRaises(AP.PlanError) as caught:
            AP.lower_payload({"concepts": [], "factors": {AP.PLAN_KEY: plan, "aggregation": "max"}})
        self.assertEqual(caught.exception.code, AP.DUPLICATE_AGGREGATION_SOURCE)
        with self.assertRaises(AP.PlanError) as caught:
            AP.lower_payload({"concepts": [], "factors": {"rollup": "max"}})
        self.assertEqual(caught.exception.code, AP.FLAT_AGGREGATION_FACTOR)

    def test_payload_without_aggregation_is_unchanged(self):
        payload = {"concepts": [], "factors": {"date": "last_month"}}
        self.assertEqual(AP.lower_payload(payload), payload)
        self.assertEqual(AP.lower_payload({"unsupported": True}), {"unsupported": True})


class ErrorCategoryTest(unittest.TestCase):
    GOLD = {"bucket": "month", "inner": "sum", "final": "avg"}

    def test_categories(self):
        cases = (
            ({"bucket": "month", "inner": "sum", "final": "avg"}, []),
            ({"bucket": "month", "inner": "unspecified", "final": "avg"},
             [AP.INNER_REDUCER_OMITTED]),
            ({"bucket": "month", "inner": "max", "final": "avg"}, [AP.INNER_REDUCER_WRONG]),
            ({"bucket": "month", "inner": "sum", "final": "max"}, [AP.FINAL_REDUCER_WRONG]),
            ({"bucket": "month", "inner": "avg", "final": "sum"}, [AP.STAGE_SWAPPED]),
            # H0에서 관측된 형태: 최종 집계를 aggregation에 적고 rollup이 없다
            ({"bucket": "month", "inner": "avg", "final": None}, [AP.STAGE_SWAPPED]),
            ({"bucket": "week", "inner": "sum", "final": "avg"}, [AP.BUCKET_WRONG]),
            ({"final": "avg"}, [AP.BUCKET_WRONG]),
        )
        for predicted, expected in cases:
            with self.subTest(predicted=predicted):
                self.assertEqual(AP.aggregation_errors(predicted, self.GOLD), expected)

    def test_unspecified_golden(self):
        gold = {"bucket": "week", "inner": "unspecified", "final": "max"}
        self.assertEqual(AP.aggregation_errors(
            {"bucket": "week", "inner": "sum", "final": "max"}, gold), [AP.INNER_REDUCER_INVENTED])
        # avg는 Tool 기본값과 같아 실행 의미가 같다
        self.assertEqual(AP.aggregation_errors(
            {"bucket": "week", "inner": "avg", "final": "max"}, gold), [])

    def test_explicit_inner_left_unspecified_counts_even_for_avg(self):
        gold = {"bucket": "week", "inner": "avg", "final": "max"}
        predicted = {"bucket": "week", "inner": "unspecified", "final": "max"}
        self.assertEqual(AP.aggregation_errors(predicted, gold), [])
        self.assertTrue(AP.explicit_inner_left_unspecified(predicted, gold))

    def test_flat_reading(self):
        self.assertEqual(AP.flat_to_semantic({"bucket": "month", "rollup": "sum"}),
                         {"bucket": "month", "inner": "unspecified", "final": "sum"})
        self.assertEqual(AP.flat_to_semantic({"aggregation": "max"}),
                         {"final": "max", "orphan_rollup": None})


class HoldoutCorpusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.intents = _intents()
        cls.items = P.load_corpus_items(HOLDOUT)
        cls.parents = P.corpus_parents(HOLDOUT)
        cls.composer = MacroComposer(MacroLibrary.from_directory())
        cls.executor = new_tool_executor()

    def test_registered_and_pinned(self):
        """H0 vs H2 판정에 한 번 썼으므로 이제 development다."""
        entry = next(e for e in REGISTRY["corpora"]
                     if e["path"] == "evaluation/paraphrases_aggregation_holdout.yaml")
        self.assertEqual(entry["role"], "development")
        self.assertTrue(any("20260924_032103" in line for line in entry["history"]))
        self.assertEqual(entry["sha256"], hashlib.sha256(HOLDOUT.read_bytes()).hexdigest())

    def test_size(self):
        per_intent = {}
        for item in self.items:
            per_intent[item["intent_id"]] = per_intent.get(item["intent_id"], 0) + 1
        self.assertGreaterEqual(len(per_intent), 16)
        self.assertTrue(all(n == 3 for n in per_intent.values()))
        self.assertEqual(len({item["id"] for item in self.items}), len(self.items))

    def test_disjoint_from_every_corpus_and_stub(self):
        for entry in REGISTRY["corpora"]:
            path = P.BASE_DIR / entry["path"]
            if path == HOLDOUT:
                continue
            with self.subTest(corpus=path.name):
                self.assertEqual(P.corpus_overlap(path, HOLDOUT),
                                 {"intents": [], "questions": [], "parents_used": []})
        stub_questions = {P.normalize_question(item["question"])
                          for item in A.census_items()}
        for item in self.items:
            self.assertNotIn(P.normalize_question(item["question"]), stub_questions)
        self.assertFalse(set(self.parents) & set(P.load_parents()))

    def test_semantic_matrix_is_covered(self):
        cells = {}
        for intent in self.intents:
            semantic = intent["aggregation"]
            factors = (intent.get("golden") or {}).get("factors") or {}
            places = [c for c in (intent.get("golden") or {}).get("concepts") or []
                      if c["concept"] == "LOCATION"]
            if semantic is None:
                cell = "G_unsupported"
            elif "bucket" not in semantic:
                cell = "D_no_bucket"
            elif "taxi_type" in factors:
                cell = "E_taxi_type"
            elif places:
                cell = "F_location"
            elif semantic["inner"] == AP.UNSPECIFIED:
                cell = "B_inner_unspecified"
            elif semantic["inner"] == "avg":
                cell = "C_inner_avg"
            else:
                cell = "A_explicit_inner"
            cells.setdefault(cell, []).append(intent["intent"])
        self.assertEqual({cell: len(names) for cell, names in cells.items()}, {
            "A_explicit_inner": 5, "B_inner_unspecified": 4, "C_inner_avg": 3,
            "D_no_bucket": 4, "E_taxi_type": 2, "F_location": 2, "G_unsupported": 3,
        })
        pairs = {(i["aggregation"]["inner"], i["aggregation"]["final"])
                 for i in self.intents if i["aggregation"] and "bucket" in i["aggregation"]}
        for pair in (("sum", "avg"), ("avg", "max"), ("sum", "max"), ("avg", "min")):
            self.assertIn(pair, pairs)

    def test_both_lowerings_give_the_expected_tool_call(self):
        for intent in self.intents:
            if intent["aggregation"] is None:
                continue
            parent = self.parents[intent["intent"]]
            h0 = intent["golden"]
            h2 = copy.deepcopy(h0)
            h2["factors"] = {k: v for k, v in h2["factors"].items() if k not in AP.FLAT_KEYS}
            h2["factors"][AP.PLAN_KEY] = AP.semantic_to_plan(intent["aggregation"])
            calls = []
            for payload in (h0, AP.lower_payload(h2)):
                plan = self.composer.compose(parse_grounding(payload, parent["question"]))
                self.assertTrue(geoflow_validator.validate(
                    plan, available_tools=self.executor.tool_names).ok)
                self.assertEqual(list(plan.applied_macros), parent["expected_macros"])
                tool, args = P.final_tool_call(plan)
                self.assertEqual(P.tool_arg_mismatches(
                    intent["expected_tool_args"], args, P.tool_defaults(tool)), [], intent["intent"])
                calls.append((tool, args))
            with self.subTest(intent=intent["intent"]):
                self.assertEqual(calls[0], calls[1])

    def test_unsupported_controls_are_unsupported_in_both_representations(self):
        for intent in self.intents:
            if intent["aggregation"] is None:
                with self.subTest(intent=intent["intent"]):
                    self.assertEqual(intent["golden"], {"unsupported": True})
                    self.assertEqual(self.parents[intent["intent"]]["expected_macros"], ["NONE"])
                    self.assertIsNone(AP.semantic_to_plan(None))

    def test_a_swapped_golden_is_not_accidentally_correct(self):
        checked = 0
        for intent in self.intents:
            semantic = intent["aggregation"]
            if not semantic or "bucket" not in semantic or semantic["inner"] in (
                    AP.UNSPECIFIED, semantic["final"]):
                continue
            swapped = {**semantic, "inner": semantic["final"], "final": semantic["inner"]}
            factors = AP.semantic_to_flat(swapped)
            self.assertNotEqual(
                P.tool_arg_mismatches(intent["expected_tool_args"], factors,
                                      P.tool_defaults("get_operation_metrics")), [])
            self.assertIn(AP.STAGE_SWAPPED, AP.aggregation_errors(swapped, semantic))
            checked += 1
        self.assertGreaterEqual(checked, 8)

    def test_golden_derivation_rejects_a_second_source(self):
        document = yaml.safe_load(HOLDOUT.read_text(encoding="utf-8"))
        document["intents"][0]["golden"]["factors"]["rollup"] = "avg"
        self.assertTrue(P.expand_aggregation(document))


if __name__ == "__main__":
    unittest.main()
