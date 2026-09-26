# -*- coding: utf-8 -*-
"""50fae72 factor 안내의 2x2 factorial 장치를 확인한다.

50fae72는 system prompt의 의미 절(S)과 factor 재질의의 의미(R)를 한 번에 바꿨다.
네 arm이 정말 한 축씩만 다르고, 분석이 두 축의 효과를 섞지 않고, 후보 선택과
holdout 판정 규칙이 결과와 무관하게 정해져 있는지 본다.
"""

import hashlib
import json
import os
import tempfile
import unittest

import yaml

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import evaluate_prompt_ab as A
import paraphrase_corpus as P
from geoflow.planner import GeoFlowPlanner
from geoflow.repair import RepairKind
from tests.test_prompt_ab_harness import CONCEPTS, MONTH_ITEM, grounding, rows_of, run

REGISTRY = yaml.safe_load((P.BASE_DIR / "evaluation" / "corpus_registry.yaml")
                          .read_text(encoding="utf-8"))
FACTOR_HOLDOUT = P.BASE_DIR / "evaluation" / "paraphrases_factor_holdout.yaml"


def arm(name):
    return A.build_variant(name)


class FactorialArmTest(unittest.TestCase):
    def test_arms_are_pinned(self):
        for name in A.FACTORIAL_ARMS:
            with self.subTest(arm=name):
                self.assertEqual(arm(name).sha256, A.PINNED_SHA256[name])
                self.assertEqual(arm(name).repair_sha256, A.PINNED_REPAIR_SHA256[name])

    def test_corner_arms_are_the_two_commits(self):
        """F00은 87ca968, F11은 50fae72(= 현재 production)의 factor 계약이다."""
        self.assertEqual(arm("F00").sha256, A.PINNED_SHA256["C"])
        self.assertEqual(arm("F00").repair_sha256, A.PINNED_REPAIR_SHA256["C"])
        self.assertEqual(arm("F11").sha256, A.PINNED_SHA256["D_PRE"])
        self.assertEqual(arm("F11").repair_sha256, A.PINNED_REPAIR_SHA256["D_PRE"])
        production = GeoFlowPlanner(client=A._StubClient()).system_prompt()
        self.assertEqual(arm("F11").prompt, production)

    def test_each_arm_differs_in_one_axis_only(self):
        f00, f10, f01, f11 = (arm(n) for n in ("F00", "F10", "F01", "F11"))
        render = A.render_factor_repair
        self.assertEqual(f10.prompt, f11.prompt)
        self.assertEqual(render(f10), render(f00))
        self.assertEqual(f01.prompt, f00.prompt)
        self.assertEqual(render(f01), render(f11))
        self.assertNotEqual(f00.prompt, f11.prompt)
        self.assertNotEqual(render(f00), render(f11))

    def test_system_axis_is_exactly_the_semantics_section(self):
        s0, s1 = arm("F00").prompt, arm("F10").prompt
        self.assertNotIn("[조건이 뜻하는 것]", s0)
        self.assertIn("[조건이 뜻하는 것]", s1)
        self.assertEqual(A.E._without_semantics(s1), s0)

    def test_other_repair_contracts_are_shared(self):
        """factor 재질의 말고는 네 arm이 같은 재질의 문구를 쓴다."""
        planners = {name: A.FixedPromptPlanner(client=A._StubClient(), variant=arm(name))
                    for name in A.FACTORIAL_ARMS}
        for kind in (RepairKind.RELATION_QUALIFIER, RepairKind.PLACE_VALUE):
            with self.subTest(kind=kind):
                texts = {name: planner.repair_instructions[kind]
                         for name, planner in planners.items()}
                self.assertEqual(len(set(texts.values())), 1)

    def test_building_arms_leaves_production_untouched(self):
        before = GeoFlowPlanner(client=A._StubClient()).system_prompt()
        for name in A.FACTORIAL_ARMS:
            arm(name)
        self.assertEqual(GeoFlowPlanner(client=A._StubClient()).system_prompt(), before)

    def test_repair_request_follows_the_r_axis_not_the_s_axis(self):
        month = grounding({"bucket": "month", "aggregation": "max"})
        patch = json.dumps({"kind": "factor_completion", "factors": {"rollup": "max"}})
        for name, old in (("F10", True), ("F01", False)):
            with self.subTest(arm=name), tempfile.TemporaryDirectory() as tmp:
                _, llm, _ = run(tmp, [MONTH_ITEM], [month, patch] * 2, arms=(name, name))
                request = llm.requests[1][-1]["content"]
                self.assertEqual("rollup은 나누는 단위가 아니라" in request, old)
                self.assertEqual("합치는 2차 집계 방식" in request, not old)


class CorpusRegistryTest(unittest.TestCase):
    def test_registered_hashes_match_the_files(self):
        """고정한 corpus가 바뀌면 그 corpus로 잰 run의 meta와 어긋난다."""
        for entry in REGISTRY["corpora"]:
            with self.subTest(path=entry["path"]):
                data = (P.BASE_DIR / entry["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])

    def test_used_corpora_are_development(self):
        roles = {entry["path"]: entry["role"] for entry in REGISTRY["corpora"]}
        self.assertEqual(roles["evaluation/paraphrases.yaml"], "development")
        self.assertEqual(roles["evaluation/paraphrases_holdout.yaml"], "development")
        self.assertEqual(set(roles.values()) - {"development", "fresh_holdout"}, set())
        # 결과를 본 factor holdout은 development다. 지금 fresh holdout은 없다.
        self.assertEqual(roles["evaluation/paraphrases_factor_holdout.yaml"], "development")

    def test_factor_holdout_was_disjoint_from_every_earlier_corpus(self):
        """쓰기 전에는 fresh였다. 쓴 뒤에는 development지만 다른 corpus와 겹치지 않는다."""
        development = [P.BASE_DIR / e["path"] for e in REGISTRY["corpora"]
                       if e["role"] == "development"
                       and P.BASE_DIR / e["path"] != FACTOR_HOLDOUT]
        for path in development:
            with self.subTest(development=path.name):
                self.assertEqual(P.corpus_overlap(path, FACTOR_HOLDOUT),
                                 {"intents": [], "questions": [], "parents_used": []})
        stub = set(P.load_parents())
        self.assertFalse(set(P.corpus_parents(FACTOR_HOLDOUT)) & stub)

    def test_fresh_holdout_is_big_enough_and_has_unsupported_controls(self):
        items = P.load_corpus_items(FACTOR_HOLDOUT)
        intents = {item["intent_id"] for item in items}
        self.assertGreaterEqual(len(intents), 12)
        per_intent = {i: sum(1 for item in items if item["intent_id"] == i) for i in intents}
        self.assertTrue(all(3 <= n <= 4 for n in per_intent.values()))
        unsupported = {item["intent_id"] for item in items
                       if P.NONE_LABEL in item["expected_macros"]}
        self.assertTrue(1 <= len(unsupported) <= 2)

    def test_fresh_holdout_golden_meets_the_label(self):
        import evaluate_planner as E
        from geoflow.composer import MacroComposer
        from geoflow.errors import CompositionError
        from geoflow.grounding import parse_grounding
        from geoflow.macros import MacroLibrary
        composer = MacroComposer(MacroLibrary.from_directory())
        parents = P.corpus_parents(FACTOR_HOLDOUT)
        for intent in P.load_corpus(FACTOR_HOLDOUT, parents):
            parent = parents[intent["intent"]]
            if P.NONE_LABEL in parent["expected_macros"]:
                continue
            with self.subTest(intent=intent["intent"]):
                grounding = parse_grounding(intent["golden"], parent["question"])
                if P.golden_inner_unspecified(grounding):
                    # golden과 제품 계약의 충돌. P.golden_inner_unspecified 참고.
                    with self.assertRaises(CompositionError) as caught:
                        composer.compose(grounding)
                    self.assertEqual(caught.exception.code,
                                     P.INNER_UNSPECIFIED_REFUSAL)
                    continue
                plan = composer.compose(grounding)
                self.assertEqual(E.corpus_labels(plan)[0], parent["expected_macros"])
                tool, args = P.final_tool_call(plan)
                self.assertEqual(P.tool_arg_mismatches(
                    intent["expected_tool_args"], args, P.tool_defaults(tool)), [])


class FactorSubsetTest(unittest.TestCase):
    def test_subset_is_chosen_from_labels_only(self):
        items = (P.load_corpus_items(P.CORPUS_FILE)
                 + P.load_corpus_items(P.HOLDOUT_CORPUS_FILE))
        subset = P.factor_subset(items)
        self.assertEqual(sorted({item["intent_id"] for item in subset}), [
            "b04_operating_ratio_by_day", "b06_fare_max", "b10_revenue_without_grouping",
            "b16_weekend_speed", "b21_bucket_rollup", "b24_bucket_rollup_month",
            "h01_private_hours_max", "h02_corporate_revenue_by_day",
            "h05_corporate_vacant_ratio_last_month", "h08_control_revenue_max",
            "h10_private_operating_count_top_sido", "h11_corporate_revenue_weekend",
            "h12_private_revenue_week_min",
        ])
        self.assertEqual(len(subset), 64)
        self.assertEqual(P.factor_subset(items), subset)

    def test_intent_without_a_factor_value_is_excluded(self):
        self.assertFalse(P.is_factor_item({"expected_tool_args": {"taxi_type": "private"}}))
        self.assertFalse(P.is_factor_item({"expected_tool_args": {"bucket": None}}))
        self.assertTrue(P.is_factor_item({"expected_tool_args": {"rollup": "max"}}))


def _row(arm_name, pid, *, raw, correct=True, repair=False, repaired=True,
         factors_expected=None, mismatches=None, category=None, status="OK", error=None,
         intent="x", repair_error=None):
    return {
        "id": pid, "repeat_index": 1, "arm": arm_name, "measurement": A.VALID,
        "intent_id": intent, "paraphrase_id": pid, "question": pid, "cohorts": ["factor_stage"],
        "raw_text": raw, "expected_macros": ["EVENT_TO_MEASURE"],
        "expected_operators": ["OPERATION_METRIC"],
        "expected_tool_args": factors_expected or {"bucket": "month", "rollup": "max"},
        "final_tool": "get_operation_metrics",
        "final_tool_args": None if not correct else {"bucket": "month", "rollup": "max"},
        "correct": correct, "status": status, "error": error,
        "repair_attempted": repair, "repair_kind": "factor_completion" if repair else None,
        "repair_succeeded": repair and repaired, "repair_error": repair_error,
        "planner_calls": 2 if repair else 1, "timeout": False,
    }


MISSING = grounding({"bucket": "month", "aggregation": "max"})
RIGHT = grounding({"bucket": "month", "rollup": "max"})


class StageMetricTest(unittest.TestCase):
    def test_initial_factor_errors_compare_the_first_grounding(self):
        row = A.rescore(_row("F00", "p", raw=MISSING, repair=True))
        self.assertIn("missing_rollup", A.initial_factor_errors(row))
        self.assertEqual(A.initial_factor_errors(A.rescore(_row("F10", "p", raw=RIGHT))), [])

    def test_schema_default_holds_for_the_first_grounding_too(self):
        row = A.rescore(_row("F00", "p", raw=grounding({}),
                             factors_expected={"aggregation": "avg"}))
        self.assertEqual(A.initial_factor_errors(row), [])

    def test_final_factor_errors_name_the_argument(self):
        row = _row("F00", "p", raw=RIGHT, factors_expected={"rollup": "max", "taxi_type": "private"})
        row["final_tool_args"] = {"bucket": "month", "rollup": "sum"}
        row = A.rescore(row)
        self.assertEqual(sorted(A.final_factor_errors(row)),
                         ["taxi_type_missing", "wrong_rollup_value"])


class FactorialAnalysisTest(unittest.TestCase):
    def _rows(self):
        """p1: S0에서는 rollup을 빠뜨려 재질의가 필요하고 R0는 실패, R1은 성공.
        S1에서는 처음부터 맞힌다. p2: 넷 다 맞힌다."""
        rows = []
        for name in ("F00", "F01"):
            ok = name == "F01"
            rows.append(_row(name, "p1", raw=MISSING, correct=ok, repair=True, repaired=ok,
                             status="OK" if ok else "INVALID_FACTOR_COMBINATION",
                             repair_error=None if ok else "REPAIR_OUT_OF_SCOPE"))
        for name in ("F10", "F11"):
            rows.append(_row(name, "p1", raw=RIGHT))
        for name in A.FACTORIAL_ARMS:
            rows.append(_row(name, "p2", raw=RIGHT, intent="y"))
        return rows

    def test_effects_and_repair_subset(self):
        result = A.analyze_factorial(self._rows())
        effects = result["effects"]["strict_correct"]
        self.assertEqual(effects["S_given_R0"], 1)
        self.assertEqual(effects["R_given_S0"], 1)
        self.assertEqual(effects["R_given_S1"], 0)
        self.assertEqual(effects["interaction"], -1)
        s0 = result["repair_subset"]["S0"]
        self.assertEqual(s0["needed"], 1)
        self.assertEqual(s0["F00"]["succeeded"], 0)
        self.assertEqual(s0["F01"]["succeeded"], 1)
        self.assertEqual(s0["F00"]["repair_errors"], {"REPAIR_OUT_OF_SCOPE": 1})
        # S1에서는 재질의가 필요 없어졌다. 그것은 R의 효과로 세지 않는다.
        self.assertEqual(result["repair_subset"]["S1"]["needed"], 0)
        self.assertEqual(result["shared_initial"]["F00/F01"], (2, 2))

    def test_ranking_prefers_accuracy_then_the_simpler_contract(self):
        result = A.analyze_factorial(self._rows())
        ranking = A.candidate_ranking(result)
        # F01·F10·F11은 strict 2로 같다. 첫 응답 factor 실패가 없는 F10·F11이 앞서고,
        # 둘 사이는 계약 크기로 F10이 앞선다. F00은 strict가 낮아 마지막이다.
        self.assertEqual(ranking, ["F10", "F11", "F01", "F00"])

    def test_full_tie_goes_to_the_simplest_contract(self):
        rows = [_row(name, "p", raw=RIGHT) for name in A.FACTORIAL_ARMS]
        self.assertEqual(A.candidate_ranking(A.analyze_factorial(rows)),
                         ["F00", "F01", "F10", "F11"])

    def test_holdout_pairs_the_candidate_with_production(self):
        self.assertEqual(A.holdout_arms(["F01", "F11", "F00", "F10"]), ("F01", "F11"))
        self.assertEqual(A.holdout_arms(["F11", "F10", "F00", "F01"]), ("F11", "F10"))

    def test_holdout_decision(self):
        def summary(candidate_ok):
            rows = [_row("F01", "p", raw=RIGHT, correct=candidate_ok),
                    _row("F11", "p", raw=RIGHT)]
            return A.holdout_summary(rows, "F01", "F11")
        self.assertEqual(A.holdout_decision(summary(True), "F01", "F11"), A.DECISIONS["F01"])
        self.assertEqual(A.holdout_decision(summary(False), "F01", "F11"), A.KEEP_PRODUCTION)

    def test_decisions_cover_every_arm(self):
        self.assertEqual(set(A.DECISIONS), set(A.FACTORIAL_ARMS))


if __name__ == "__main__":
    unittest.main()
