# -*- coding: utf-8 -*-
"""v2 holdout(evaluation/v2)과 v2 평가 실행기(evaluate_v2.py)의 구조 보장.

모델을 부르지 않는다. golden grounding을 planner 응답처럼 넣어 실행기가 모든 문항을 정답으로
채점하는지(라벨·기대 인자·기대 결과가 코드 계약과 맞는지), 흔한 오류는 정답으로 세지 않는지,
새 문항이 기존 corpus·예시의 단순 paraphrase가 아닌지를 모델 실행 전에 고정한다.
"""

import copy
import hashlib
import json
import os
import unittest
from pathlib import Path

import yaml

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import aggregation_plan as AP  # noqa: E402
import evaluate_prompt_ab as A  # noqa: E402
import evaluate_v2 as V  # noqa: E402
import paraphrase_corpus as P  # noqa: E402
from build import build  # noqa: E402
from geoflow.examples import load_store  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
HOLDOUT = BASE_DIR / "evaluation" / "v2" / "paraphrases_holdout_v2.yaml"
REGISTRY = yaml.safe_load((BASE_DIR / "evaluation" / "corpus_registry.yaml")
                          .read_text(encoding="utf-8"))
TOOLS, _PROMPT = build()


class _Reset:
    def reset(self):
        return A.ResetResult(attempted=True, succeeded=True, duration_ms=0.0, detail="test")


class _Client:
    """planner 응답을 차례로 돌려준다. cold load가 확인된 관측처럼 보이게 한다."""

    model = "scripted"

    def __init__(self, payloads):
        self.payloads = list(payloads)

    def chat(self, messages, tools=None):
        payload = self.payloads.pop(0)
        return {"message": {"content": json.dumps(payload, ensure_ascii=False)},
                "done_reason": "stop", "load_duration": 900_000_000}


def observe(item, *payloads):
    return V.observe(item, client=_Client(payloads), reset=_Reset(), tools=TOOLS, model="scripted")


def golden_payload(intent):
    golden = copy.deepcopy(intent["golden"])
    if golden == {"unsupported": True}:
        return golden
    return golden   # load_corpus가 aggregation golden을 flat factor로 이미 폈다.


class RegistryTest(unittest.TestCase):
    def entry(self, path):
        return next(e for e in REGISTRY["corpora"] + REGISTRY["question_sets"]
                    if e["path"] == path)

    def test_registered_pinned_and_marked_unreviewed(self):
        entry = self.entry("evaluation/v2/paraphrases_holdout_v2.yaml")
        self.assertEqual(entry["sha256"], hashlib.sha256(HOLDOUT.read_bytes()).hexdigest())
        self.assertIn(entry["role"], ("fresh_holdout", "development"))
        self.assertEqual(entry["version"], "v2.0")
        self.assertEqual(entry["review"]["status"], "unreviewed")
        for parent in entry["parents"]:
            self.assertEqual(entry["parents_sha256"][parent],
                             hashlib.sha256((BASE_DIR / parent).read_bytes()).hexdigest())
        gold = self.entry("evaluation/v2/stub_v2_gold.yaml")
        self.assertEqual(gold["sha256"], hashlib.sha256(
            (BASE_DIR / gold["path"]).read_bytes()).hexdigest())
        self.assertEqual(gold["review"]["status"], "unreviewed")


class CompositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.intents = P.load_corpus(HOLDOUT)
        cls.items = P.load_corpus_items(HOLDOUT)

    def test_size_and_fields(self):
        self.assertEqual(len(self.intents), 42)
        self.assertEqual(len(self.items), 126)
        for intent in self.intents:
            with self.subTest(intent=intent["intent"]):
                self.assertEqual(len(intent["paraphrases"]), 3)
                for key in ("expected_outcome", "capability", "rationale"):
                    self.assertTrue(intent.get(key), key)

    def test_restores_exactly_the_retired_intents(self):
        """aggregation 10, local aggregation 10, verifier 7개를 하나씩 되살린다."""
        restored = {intent["restores"] for intent in self.intents if intent.get("restores")}
        for path, count in (("evaluation/paraphrases_aggregation_holdout.yaml", 10),
                            ("evaluation/paraphrases_local_aggregation_holdout.yaml", 10),
                            ("evaluation/paraphrases_verifier_holdout.yaml", 7)):
            with self.subTest(corpus=path):
                retired = set(P.v2_retired(BASE_DIR / path))
                self.assertEqual(len(retired), count)
                self.assertLessEqual(retired, restored)
        self.assertEqual(len(restored), 27)

    def test_new_intents_do_not_use_the_retired_metrics(self):
        text = HOLDOUT.read_text(encoding="utf-8")
        for name in ("subtype: hours", "subtype: operating_count", "operating_ratio"):
            self.assertNotIn(name, text)

    def test_outcome_mix_and_stage_swap_coverage(self):
        outcomes = [intent["expected_outcome"] for intent in self.intents]
        self.assertEqual(outcomes.count("answered"), 26)
        self.assertEqual(outcomes.count("needs_clarification"), 5)
        self.assertEqual(outcomes.count("unsupported"), 11)
        swappable = [i for i in self.intents
                     if isinstance(i["aggregation"], dict) and "bucket" in i["aggregation"]
                     and i["aggregation"]["inner"] not in (AP.UNSPECIFIED, i["aggregation"]["final"])]
        # 이전 aggregation holdout의 v2 유효 stage-swap 검사는 4개였다.
        self.assertGreaterEqual(sum(i["expected_outcome"] == "answered" for i in swappable), 11)


class LeakTest(unittest.TestCase):
    """새 holdout이 기존 corpus·부모·예시·질문 셋의 단순 paraphrase가 아니다."""

    @classmethod
    def setUpClass(cls):
        cls.new = yaml.safe_load(HOLDOUT.read_text(encoding="utf-8"))["intents"]

    def existing_questions(self):
        texts = set()
        files = ["stub_query.yaml", "stub_query_boundary.yaml", "evaluation/stub_query_v1.yaml",
                 "assistant_univ_questions_100_v3.yaml"]
        for entry in REGISTRY["corpora"]:
            if entry["path"] == "evaluation/v2/paraphrases_holdout_v2.yaml":
                continue
            files += entry["parents"]
            for intent in yaml.safe_load((BASE_DIR / entry["path"]).read_text(
                    encoding="utf-8"))["intents"]:
                texts |= {P.normalize_question(p["question"]) for p in intent["paraphrases"]}
        for name in files:
            for item in yaml.safe_load((BASE_DIR / name).read_text(encoding="utf-8")):
                texts.add(P.normalize_question(item["question"]))
        for entry in REGISTRY["question_sets"]:
            document = yaml.safe_load((BASE_DIR / entry["path"]).read_text(encoding="utf-8"))
            for item in document.get("questions") or []:
                texts.add(P.normalize_question(item["question"]))
        texts |= {P.normalize_question(example.question) for example in load_store().examples}
        return texts

    def test_no_question_text_is_reused(self):
        known = self.existing_questions()
        for intent in self.new:
            for paraphrase in intent["paraphrases"]:
                with self.subTest(id=paraphrase["id"]):
                    self.assertNotIn(P.normalize_question(paraphrase["question"]), known)

    def test_no_intent_repeats_an_existing_structure(self):
        signatures = {}
        for entry in REGISTRY["corpora"]:
            if entry["path"] == "evaluation/v2/paraphrases_holdout_v2.yaml":
                continue
            for intent in P.load_corpus(BASE_DIR / entry["path"]):
                signature = P.structure_signature(intent.get("golden"),
                                                  P.golden_aggregation(intent))
                signatures.setdefault(signature, []).append(intent["intent"])
        for example in load_store().examples:
            grounding = example.grounding if isinstance(example.grounding, dict) else {}
            if "concepts" not in grounding:
                continue
            plan = (grounding.get("factors") or {}).get(AP.PLAN_KEY) or {}
            result = plan.get("result") or {}
            semantic = ({"bucket": plan["bucket"]["unit"], "inner": plan["bucket"]["reducer"],
                         "final": result.get("reducer") or f"select:{result.get('select')}"}
                        if plan.get("bucket") else ({"final": result["reducer"]}
                                                    if result.get("reducer") else None))
            signatures.setdefault(P.structure_signature(grounding, semantic), []).append(example.id)
        signatures.pop(None, None)
        for intent in P.load_corpus(HOLDOUT):
            signature = P.structure_signature(intent.get("golden"), intent.get("aggregation"))
            with self.subTest(intent=intent["intent"]):
                self.assertNotIn(signature, signatures, signatures.get(signature))

    def test_parents_are_disjoint_from_every_other_corpus(self):
        for entry in REGISTRY["corpora"]:
            path = BASE_DIR / entry["path"]
            if path == HOLDOUT:
                continue
            with self.subTest(corpus=path.name):
                self.assertEqual(P.corpus_overlap(path, HOLDOUT),
                                 {"intents": [], "questions": [], "parents_used": []})


class GoldenScoringTest(unittest.TestCase):
    """golden grounding은 모든 문항에서 정답으로 채점된다. 틀린 grounding은 그렇지 않다."""

    @classmethod
    def setUpClass(cls):
        cls.intents = {intent["intent"]: intent for intent in P.load_corpus(HOLDOUT)}
        cls.items = {item["id"]: item for item in V.load_items(["stub", "holdout_v2"])}

    def item(self, intent):
        return self.items[f"{intent.split('_', 1)[0]}_p0"]

    def test_every_golden_is_scored_correct(self):
        for name, intent in self.intents.items():
            with self.subTest(intent=name):
                record = observe(self.item(name), golden_payload(intent))
                self.assertEqual(record["measurement"], A.VALID)
                self.assertEqual(record["category"], "correct",
                                 (record["outcome"], record["error_code"], record["checks"],
                                  record["final_answer"]))
                self.assertEqual(record["outcome"], intent["expected_outcome"])

    def test_a_swapped_stage_is_an_aggregation_error(self):
        checked = 0
        for name, intent in self.intents.items():
            semantic = intent["aggregation"]
            if (intent["expected_outcome"] != "answered" or not isinstance(semantic, dict)
                    or "bucket" not in semantic
                    or semantic["inner"] in (AP.UNSPECIFIED, semantic["final"])):
                continue
            swapped = {**semantic, "inner": semantic["final"], "final": semantic["inner"]}
            payload = copy.deepcopy(intent["golden"])
            payload["factors"] = {**{k: v for k, v in payload["factors"].items()
                                     if k not in AP.FLAT_KEYS}, **AP.semantic_to_flat(swapped)}
            with self.subTest(intent=name):
                record = observe(self.item(name), payload)
                self.assertNotEqual(record["category"], "correct")
                checked += 1
        self.assertGreaterEqual(checked, 11)

    def test_dropped_condition_and_wrong_target_are_wrong_arguments(self):
        record = observe(self.item("w09_jul_aug_private_month_sum_then_avg_days"),
                         {**self.intents["w09_jul_aug_private_month_sum_then_avg_days"]["golden"],
                          "factors": {k: v for k, v in self.intents[
                              "w09_jul_aug_private_month_sum_then_avg_days"]["golden"][
                              "factors"].items() if k != "taxi_type"}})
        self.assertEqual(record["category"], "wrong_tool_args")
        golden = copy.deepcopy(self.intents["w35_last_month_top_pickup_emd"]["golden"])
        del golden["factors"]["dimension_target"]
        record = observe(self.item("w35_last_month_top_pickup_emd"), golden)
        self.assertEqual(record["category"], "wrong_tool_args")

    def test_missing_vicinity_and_invented_conditions_are_wrong(self):
        """최종 Tool 인자에 드러나지 않는 조건도 golden과 대조한다."""
        name = "w38_this_week_dongdaegu_vicinity_passage_count"
        golden = copy.deepcopy(self.intents[name]["golden"])
        del golden["factors"]["vicinity"]
        record = observe(self.item(name), golden)
        self.assertEqual(record["category"], "wrong_tool_args")
        self.assertIn(["condition:vicinity", True, None], record["checks"]["arg_mismatches"])
        name = "w07_last_week_avg_fare"
        golden = copy.deepcopy(self.intents[name]["golden"])
        golden["factors"]["time"] = "090000-180000"
        record = observe(self.item(name), golden)
        self.assertEqual(record["category"], "wrong_tool_args")
        # 조건을 걸지 않는 값(taxi_type=all)은 없는 것과 같다.
        self.assertEqual(V.condition_mismatches({"taxi_type": "all", "date": "x"},
                                                {"date": "x"}), [])

    def test_grounded_refusals_are_still_refusals(self):
        """D 문항을 모델이 grounding해도 제품이 거부하면 거부 정확도에 든다."""
        cases = {
            "w30_last_month_ratio_sum": {"concepts": [
                {"id": "op", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
                 "source": "implicit"},
                {"id": "r", "concept": "PROPORTION", "subtype": "active_taxi_ratio",
                 "role": "MEASURE", "source": "implicit"}],
                "factors": {"date": "last_month", "aggregation": "sum"}},
            "w33_daegu_revenue_by_day": {"concepts": [
                {"id": "p", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
                 "source": "user", "value": {"name": "대구", "region": ""}},
                {"id": "op", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
                 "source": "implicit"},
                {"id": "m", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
                 "source": "implicit"}], "factors": {"dimension": "dayofweek"}},
            "w34_revenue_top_sigungu": {"concepts": [
                {"id": "op", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
                 "source": "implicit"},
                {"id": "m", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
                 "source": "implicit"}],
                "factors": {"dimension": "sigungu", "order": "top", "limit": 3}},
        }
        for name, payload in cases.items():
            with self.subTest(intent=name):
                record = observe(self.item(name), payload)
                self.assertEqual((record["outcome"], record["category"]),
                                 ("unsupported", "correct"), record["error_code"])

    def test_answering_a_refusal_item_is_not_correct(self):
        # 영업 시간을 매출로 바꿔 답하면 오답이다.
        record = observe(self.item("w28_last_month_corporate_avg_hours"), {"concepts": [
            {"id": "op", "concept": "EVENT", "subtype": "operation", "role": "SUPPORT",
             "source": "implicit"},
            {"id": "m", "concept": "AMOUNT", "subtype": "revenue", "role": "MEASURE",
             "source": "implicit"}], "factors": {"date": "last_month", "taxi_type": "corporate",
                                                  "aggregation": "avg"}})
        self.assertEqual(record["category"], "answered_instead_of_refusal")


class StubGoldTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = {item["id"]: item for item in V.load_items(["stub"])}

    def od(self, origin):
        return {"concepts": [
            {"id": "o", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
             "source": "user", "value": {"name": origin, "region": "대구"},
             "attributes": {"od_role": "pickup"}},
            {"id": "d", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
             "source": "user", "value": {"name": "신천동", "region": ""},
             "attributes": {"od_role": "dropoff"}},
            {"id": "t", "concept": "EVENT", "subtype": "trip", "role": "SUPPORT",
             "source": "implicit"},
            {"id": "c", "concept": "AMOUNT", "subtype": "trip_count", "role": "MEASURE",
             "source": "implicit"}], "factors": {}}

    def test_repair_to_another_place_is_not_correct(self):
        """동성로동 NOT_FOUND 뒤 동성로(도로)로 바꿔 실행에 성공해도 출발지가 바뀌었다."""
        item = self.items["q18_daegu_origin_destination_count"]
        record = observe(item, self.od("동성로동"),
                         {"concept_id": "o", "name": "동성로", "region": "대구"})
        self.assertEqual(record["outcome"], "answered")
        self.assertEqual(record["category"], "wrong_tool_args")
        self.assertEqual(record["checks"]["arg_mismatches"][0][0], "scope_pickup")

    def test_alias_is_the_same_place(self):
        item = self.items["q20_daegu_average_fare"]
        for name in ("대구시", "대구"):
            with self.subTest(name=name):
                record = observe(item, {"concepts": [
                    {"id": "p", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
                     "source": "user", "value": {"name": name, "region": ""}},
                    {"id": "t", "concept": "EVENT", "subtype": "trip", "role": "SUPPORT",
                     "source": "implicit"},
                    {"id": "f", "concept": "AMOUNT", "subtype": "fare", "role": "MEASURE",
                     "source": "implicit"}], "factors": {"aggregation": "avg"}})
                self.assertEqual(record["category"], "correct", record["checks"])

    def test_answer_format_checks(self):
        self.assertEqual(V.answer_problems("대구 택시 요금: 12,000", "q"), [])
        self.assertIn("raw_row", V.answer_problems("- sido=서울시, revenue=1", "q"))
        self.assertIn("raw_object", V.answer_problems("{'count': 3}", "q"))
        self.assertIn("scope_exposed", V.answer_problems("scope:district:1: 3건", "q"))
        self.assertEqual(V.answer_problems("scope:edge:1742 속도: 30km/h", "scope:edge:1742"), [])
        self.assertIn("double_unit", V.answer_problems("공차율: 35%%", "q"))


class AnalysisTest(unittest.TestCase):
    def test_summary_keeps_denominators(self):
        rows = [
            {"measurement": A.VALID, "expected_outcome": "answered", "outcome": "answered",
             "category": "correct", "set": "s", "intent_id": "x"},
            {"measurement": A.VALID, "expected_outcome": "answered", "outcome": "unsupported",
             "category": "refused_supported", "set": "s", "intent_id": "x"},
            {"measurement": A.VALID, "expected_outcome": "unsupported", "outcome": "failed",
             "category": "failed_instead_of_refusal", "set": "s", "intent_id": "y"},
        ]
        summary = V.summarize(rows)
        self.assertEqual(summary["execution_completion"], {"count": 1, "of": 2, "rate": 0.5})
        self.assertEqual(summary["refusal_strict"], {"count": 0, "of": 1, "rate": 0.0})
        self.assertEqual(summary["refusal_lenient"], {"count": 1, "of": 1, "rate": 1.0})
        self.assertEqual(summary["semantic_correct"]["of"], 3)


if __name__ == "__main__":
    unittest.main()
