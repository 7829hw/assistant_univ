# -*- coding: utf-8 -*-
"""paraphrase 평가 corpus가 전제를 지키는지 확인한다.

corpus가 틀리면 측정 전체가 틀린다. 표현만 바뀌고 뜻은 그대로라는 전제,
정답 label이 코드 계약과 맞는다는 전제를 여기서 못박는다.
"""

import copy
import json
import os
import unittest

import yaml

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import aggregation_plan
import evaluate_planner as E
import paraphrase_corpus as P
from geoflow.composer import MacroComposer
from geoflow.grounding import parse_grounding
from geoflow.macros import MacroLibrary
from geoflow.operator_registry import get_operator
from geoflow.planner import GeoFlowPlanner

PARENTS = P.load_parents()
DOCUMENT = yaml.safe_load(P.CORPUS_FILE.read_text(encoding="utf-8"))
INTENTS = P.load_corpus(parents=PARENTS)
TOOL_SCHEMAS = {
    entry["function"]["name"]: entry["function"]["parameters"]["properties"]
    for entry in yaml.safe_load((P.BASE_DIR / "schemas" / "tims.yaml")
                                .read_text(encoding="utf-8"))
}


class _Client:
    model = "fake"

    def __init__(self, content):
        self.content = content

    def chat(self, messages, tools=None):
        return {"message": {"content": self.content}}


def _mutated(edit):
    document = copy.deepcopy(DOCUMENT)
    edit(document)
    return P.validate(document, PARENTS)


def _intent(document, name):
    return next(item for item in document["intents"] if item["intent"] == name)


class CorpusShapeTest(unittest.TestCase):
    def test_real_corpus_has_no_problems(self):
        self.assertEqual(P.validate(DOCUMENT, PARENTS), [])

    def test_three_cohorts_with_enough_paraphrases(self):
        minimum = {"taxi_type": 5, "factor_stage": 5, "relation": 3}
        seen = set()
        for intent in INTENTS:
            for cohort in intent["cohorts"]:
                seen.add(cohort)
                with self.subTest(intent=intent["intent"], cohort=cohort):
                    self.assertGreaterEqual(len(intent["paraphrases"]), minimum[cohort])
        # aggregation_stage는 집계 holdout에만 있다. 이 corpus는 세 cohort를 다룬다.
        self.assertEqual(seen, set(minimum))
        self.assertLessEqual(seen, set(P.COHORTS))

    def test_paraphrase_ids_are_unique(self):
        ids = [p["id"] for intent in INTENTS for p in intent["paraphrases"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_parent_exists(self):
        for intent in INTENTS:
            self.assertIn(intent["intent"], PARENTS)

    def test_labels_are_inherited_from_the_parent(self):
        for item in P.corpus_items(INTENTS, PARENTS):
            parent = PARENTS[item["original_question_id"]]
            with self.subTest(paraphrase=item["id"]):
                for key in P.LABEL_KEYS:
                    self.assertEqual(item[key], list(parent.get(key) or []))

    def test_unsupported_parent_stays_unsupported(self):
        unsupported = [item for item in P.corpus_items(INTENTS, PARENTS)
                       if P.NONE_LABEL in item["expected_macros"]]
        self.assertTrue(unsupported)
        for item in unsupported:
            self.assertEqual(item["expected_tool_args"], {})

    def test_shared_intent_appears_once(self):
        items = P.corpus_items(INTENTS, PARENTS)
        self.assertEqual(len(items), len({item["id"] for item in items}))
        b24 = [item for item in items if item["intent_id"].startswith("b24")]
        self.assertEqual(set(b24[0]["cohorts"]), {"taxi_type", "factor_stage"})

    def test_cohort_filter(self):
        items = P.corpus_items(INTENTS, PARENTS, cohorts=["relation"])
        self.assertTrue(items)
        self.assertTrue(all("relation" in item["cohorts"] for item in items))


class CorpusGuardTest(unittest.TestCase):
    """깨뜨린 corpus를 검증이 잡아내는지."""

    def test_label_override_on_a_paraphrase_is_rejected(self):
        problems = _mutated(lambda d: _intent(d, "b05_corporate_vacant_ratio")
                            ["paraphrases"][1].update(expected_macros=["NONE"]))
        self.assertTrue(any("label은 부모에서만" in p for p in problems))

    def test_empty_question_is_rejected(self):
        problems = _mutated(lambda d: _intent(d, "b10_revenue_without_grouping")
                            ["paraphrases"][2].update(question="  "))
        self.assertTrue(any("비어 있다" in p for p in problems))

    def test_duplicate_question_is_rejected_after_normalization(self):
        def edit(document):
            intent = _intent(document, "b10_revenue_without_grouping")
            intent["paraphrases"][2]["question"] = "개인택시의  평균 수입은 ?"
        self.assertTrue(any("같은 질문" in p for p in _mutated(edit)))

    def test_duplicate_id_and_bad_id_are_rejected(self):
        def edit(document):
            items = _intent(document, "b05_corporate_vacant_ratio")["paraphrases"]
            items[2]["id"] = items[1]["id"]
            items[3]["id"] = "x05_p9"
        problems = _mutated(edit)
        self.assertTrue(any("중복된 paraphrase id" in p for p in problems))
        self.assertTrue(any("형식" in p for p in problems))

    def test_missing_parent_is_rejected(self):
        problems = _mutated(lambda d: _intent(d, "b05_corporate_vacant_ratio")
                            .update(intent="b99_nothing"))
        self.assertTrue(any("부모 질의가 없다" in p for p in problems))

    def test_p0_must_be_the_original(self):
        problems = _mutated(lambda d: _intent(d, "b04_operating_ratio_by_day")
                            ["paraphrases"][0].update(question="요일별 운행률은?"))
        self.assertTrue(any("p0은 부모 원문" in p for p in problems))

    def test_bucket_paraphrase_cannot_turn_into_weekend(self):
        problems = _mutated(lambda d: _intent(d, "b21_bucket_rollup")["paraphrases"][1]
                            .update(question="주말 택시 수입을 주 단위로 집계했을 때 평균은?"))
        self.assertTrue(any("'주말'" in p for p in problems))

    def test_weekend_paraphrase_cannot_turn_into_bucket(self):
        problems = _mutated(lambda d: _intent(d, "b16_weekend_speed")["paraphrases"][1]
                            .update(question="대구 지역의 주 단위 평균 속도는?"))
        self.assertTrue(any("주말" in p for p in problems))
        self.assertTrue(any("'주 단위'" in p for p in problems))

    def test_dimension_paraphrase_must_keep_the_grouping(self):
        problems = _mutated(lambda d: _intent(d, "b04_operating_ratio_by_day")
                            ["paraphrases"][2].update(question="주말 택시 운행률은?"))
        self.assertTrue(any("요일별" in p for p in problems))

    def test_od_direction_cannot_flip(self):
        problems = _mutated(lambda d: _intent(d, "b11_origin_only")["paraphrases"][1]
                            .update(question="동성로동에 도착한 실차 구간 건수는?"))
        self.assertTrue(any("pickup 표지가 없다" in p for p in problems))
        problems = _mutated(lambda d: _intent(d, "q27_busan_origin_destination_count")
                            ["paraphrases"][2].update(
                                question="초읍동에 도착하고 초량동에서 출발한 부산 실차 구간 건수는?"))
        self.assertTrue(any("초읍동에 dropoff 표지" in p for p in problems))

    def test_od_markers_accept_every_real_paraphrase(self):
        for intent in INTENTS:
            for paraphrase in intent["paraphrases"]:
                with self.subTest(paraphrase=paraphrase["id"]):
                    self.assertEqual(P.od_marker_problems(
                        paraphrase["question"], intent.get("od_roles") or {}), [])

    def test_unsupported_intent_needs_an_unsupported_golden(self):
        problems = _mutated(lambda d: _intent(d, "b20_region_comparison")
                            .update(golden={"concepts": [], "factors": {}}))
        self.assertTrue(any("unsupported여야" in p for p in problems))


class _ContractChecks:
    """label이 코드 계약과 맞는지. 사람이 쓴 golden을 실제 경로에 통과시킨다.

    선택용과 검증용 corpus에 똑같이 적용한다.
    """

    PARENTS = PARENTS
    INTENTS = INTENTS
    CORPUS = P.CORPUS_FILE

    def setUp(self):
        self.composer = MacroComposer(MacroLibrary.from_directory())

    def _final_tool(self, intent):
        parent = self.PARENTS[intent["intent"]]
        return get_operator(parent["expected_operators"][-1]).tool_name

    def test_expected_tool_args_are_real_arguments(self):
        for intent in self.INTENTS:
            if not intent["expected_tool_args"]:
                continue
            schema = TOOL_SCHEMAS[self._final_tool(intent)]
            for key, value in intent["expected_tool_args"].items():
                with self.subTest(intent=intent["intent"], arg=key):
                    self.assertIn(key, schema)
                    enum = schema[key].get("enum")
                    if enum and value is not None:
                        self.assertIn(value, enum)

    def test_golden_grounding_meets_the_label(self):
        for intent in self.INTENTS:
            parent = self.PARENTS[intent["intent"]]
            if P.NONE_LABEL in parent["expected_macros"]:
                continue
            with self.subTest(intent=intent["intent"]):
                grounding = parse_grounding(intent["golden"], parent["question"])
                plan = self.composer.compose(grounding)
                self.assertEqual(list(plan.applied_macros), parent["expected_macros"])
                self.assertEqual([t.operator for t in plan.transformations],
                                 parent["expected_operators"])
                tool, args = P.final_tool_call(plan)
                self.assertEqual(tool, self._final_tool(intent))
                self.assertEqual(P.tool_arg_mismatches(intent["expected_tool_args"], args), [])

    def test_golden_is_scored_correct_by_the_real_evaluator(self):
        for item in P.corpus_items(self.INTENTS, self.PARENTS):
            if not item["id"].endswith("_p0"):
                continue
            intent = next(i for i in self.INTENTS if i["intent"] == item["intent_id"])
            raw = aggregation_plan.raw_grounding(intent["golden"])
            planner = GeoFlowPlanner(client=_Client(json.dumps(raw, ensure_ascii=False)))
            with self.subTest(intent=item["intent_id"]):
                record = E.evaluate_once(planner, self.composer, item)
                self.assertTrue(record["correct"], record["status"])


class CorpusContractTest(_ContractChecks, unittest.TestCase):
    pass


HOLDOUT_PARENTS = P.corpus_parents(P.HOLDOUT_CORPUS_FILE)
HOLDOUT_INTENTS = P.load_corpus(P.HOLDOUT_CORPUS_FILE, HOLDOUT_PARENTS)


class HoldoutContractTest(_ContractChecks, unittest.TestCase):
    PARENTS = HOLDOUT_PARENTS
    INTENTS = HOLDOUT_INTENTS
    CORPUS = P.HOLDOUT_CORPUS_FILE


class HoldoutSeparationTest(unittest.TestCase):
    """검증용이 선택용과 섞이면 검증이 아니다."""

    def test_no_shared_intent_question_or_parent(self):
        self.assertEqual(P.corpus_overlap(P.CORPUS_FILE, P.HOLDOUT_CORPUS_FILE),
                         {"intents": [], "questions": [], "parents_used": []})

    def test_holdout_parents_are_not_in_the_stub_sets(self):
        self.assertFalse(set(HOLDOUT_PARENTS) & set(PARENTS))

    def test_holdout_brings_the_total_to_at_least_twenty_intents(self):
        self.assertGreaterEqual(len(INTENTS) + len(HOLDOUT_INTENTS), 20)
        for intent in HOLDOUT_INTENTS:
            with self.subTest(intent=intent["intent"]):
                self.assertGreaterEqual(len(intent["paraphrases"]), 3)

    def test_holdout_covers_the_axes(self):
        args = [intent["expected_tool_args"] for intent in HOLDOUT_INTENTS]
        taxi = {a.get("taxi_type", "absent") for a in args if "taxi_type" in a}
        self.assertTrue({"private", "corporate", None} <= taxi)
        metrics = {a.get("metric") for a in args}
        self.assertTrue({"vacant_ratio", "revenue", "hours", "operating_count",
                         "operating_ratio"} <= metrics)
        tools = {get_operator(HOLDOUT_PARENTS[i["intent"]]["expected_operators"][-1]).tool_name
                 for i in HOLDOUT_INTENTS if HOLDOUT_PARENTS[i["intent"]]["expected_operators"]}
        self.assertTrue({"get_drive_metrics", "get_operation_metrics",
                         "get_passage_count"} <= tools)
        self.assertTrue(any(P.NONE_LABEL in HOLDOUT_PARENTS[i["intent"]]["expected_macros"]
                            for i in HOLDOUT_INTENTS))

    def test_holdout_does_not_reuse_the_prompt_example(self):
        for item in P.corpus_items(HOLDOUT_INTENTS, HOLDOUT_PARENTS):
            self.assertNotIn("운행시간", item["question"])

    def test_new_od_markers(self):
        self.assertEqual(P.od_marker_problems("신천동을 출발지로 한 구간", {"신천동": "pickup"}), [])
        self.assertTrue(P.od_marker_problems("신천동을 출발지로 한 구간", {"신천동": "dropoff"}))


if __name__ == "__main__":
    unittest.main()
