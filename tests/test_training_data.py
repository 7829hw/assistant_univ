"""CPU regression tests for the training/runtime responsibility boundary."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import yaml

from geoflow.composer import MacroComposer
from geoflow.examples import load_store
from geoflow.grounding import parse_grounding
from geoflow.validator import ALL_RULES, validate
from training.data.build_dpo import build as build_dpo, dpo_pair
from training.data.build_sft import build as build_sft, sft_record
from training.data.canonicalize import (canonical_json, flatten_source, semantic_key,
                                        serialize_planner_target)
from training.data.common import ROOT, check_source, coverage, production_prompt, read_jsonl, write_jsonl
from training.data.negative_mutations import mutations
from training.data.split import check_split, split_records
from training.data.validation import assess


def annotation(pid="gold", question="새길동 주변 평균 주행 속도는?"):
    return {"id": pid, "question": question, "parent_intent": "passage_speed",
            "grounding": {"concepts": [
                {"id": "place", "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
                 "source": "user", "value": {"name": "새길동", "region": ""}},
                {"id": "event", "concept": "EVENT", "subtype": "passage", "role": "SUPPORT", "source": "implicit"},
                {"id": "measure", "concept": "AMOUNT", "subtype": "speed", "role": "MEASURE", "source": "implicit"}],
                "factors": {"vicinity": True, "aggregation": "avg"}}}


def record(raw=None):
    return sft_record(raw or annotation(), source="authored", source_representation="flat")


class CanonicalTest(unittest.TestCase):
    def test_internal_metadata_is_never_a_target(self):
        raw = annotation()
        grounding = parse_grounding(raw["grounding"], raw["question"])
        self.assertIn("aggregation", grounding.to_dict())
        target = json.loads(serialize_planner_target(grounding))
        self.assertEqual(set(target), {"concepts", "factors"})
        self.assertEqual(target, json.loads(serialize_planner_target(raw["grounding"])))
        with self.assertRaises(ValueError):
            serialize_planner_target(grounding.to_dict())

    def test_order_ids_whitespace_and_utf8(self):
        payload = annotation()["grounding"]
        expected = serialize_planner_target(payload)
        payload["concepts"].reverse()
        for i, concept in enumerate(payload["concepts"]):
            concept["id"] = f"random_{i}"
        self.assertEqual(serialize_planner_target(payload), expected)
        self.assertIn("새길동", expected)
        self.assertNotIn("```", expected)
        self.assertEqual(serialize_planner_target(json.loads(expected)), expected)

    def test_bad_json_shapes_and_runtime_fields(self):
        for bad in ({"x": float("nan")}, {1: "not a JSON key"}, {"x": {1, 2}}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                canonical_json(bad)
        for value in ({"unsupported": 1}, {"unsupported": False}, {"unsupported": True, "factors": {}},
                      {"concepts": [], "factors": {}, "graph": []}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                serialize_planner_target(value)

    def test_duplicate_id_rejected_before_renaming(self):
        payload = annotation()["grounding"]
        payload["concepts"][1]["id"] = payload["concepts"][0]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            serialize_planner_target(payload)

    def test_structured_roundtrip_and_mixed_rejection(self):
        for example in load_store().examples:
            if example.expected_outcome != "answered":
                continue
            with self.subTest(example=example.id):
                flat = flatten_source(example.grounding)
                target = serialize_planner_target(flat)
                grounding = parse_grounding(json.loads(target), example.question)
                before = parse_grounding(example.grounding, example.question, structured_aggregation=True)
                self.assertEqual(grounding.aggregation.to_dict() | {"source": ""}, before.aggregation.to_dict() | {"source": ""})
                self.assertTrue(validate(MacroComposer().compose(grounding)).ok)
        payload = annotation()["grounding"]
        payload["factors"]["aggregation_plan"] = {"result": {"reducer": "avg"}}
        with self.assertRaisesRegex(ValueError, "Structured"):
            serialize_planner_target(payload)
        with self.assertRaisesRegex(ValueError, "Mixed"):
            flatten_source(payload)


class SFTTest(unittest.TestCase):
    def test_record_uses_production_prompt_and_valid_grounding(self):
        row = record()
        self.assertEqual(row["messages"][:2], [{"role": "system", "content": production_prompt()},
                         {"role": "user", "content": annotation()["question"]}])
        parsed = parse_grounding(json.loads(row["messages"][-1]["content"]), annotation()["question"])
        report = validate(MacroComposer().compose(parsed))
        self.assertTrue(report.ok)
        self.assertEqual(report.checked_rules, list(ALL_RULES))

    def test_unsupported_recognized_without_fake_validation(self):
        row = record({"id": "u", "question": "월별 속도 목록 전체를 출력해줘", "grounding": {"unsupported": True}})
        self.assertEqual(row["messages"][-1]["content"], '{"unsupported":true}')
        quality = row["metadata"]["chosen_quality"]
        self.assertTrue(quality["parse_ok"])
        self.assertIsNone(quality["compose_ok"])
        self.assertIsNone(quality["validation_ok"])

    def test_unknown_concept_subtype_role_factor_invalid_value(self):
        for section, name, value in (("concept", "concept", "UNKNOWN"), ("concept", "subtype", "hours"),
                                      ("concept", "role", "unknown"), ("factor", "location", "서울"),
                                      ("factor", "aggregation", "count"), ("factor", "date", "today")):
            raw = annotation()
            if section == "concept":
                raw["grounding"]["concepts"][-1][name] = value
            else:
                raw["grounding"]["factors"][name] = value
            with self.subTest(name=name, value=value), self.assertRaisesRegex(ValueError, "failed"):
                record(raw)

    def test_impossible_composition_is_not_gold(self):
        raw = annotation()
        raw["grounding"]["factors"].update(bucket="week", aggregation="avg")
        with self.assertRaisesRegex(ValueError, "failed"):
            record(raw)

    def test_evaluation_sources_blocked_including_parents(self):
        for path in ("evaluation/v2/paraphrases_holdout_v2.yaml", "evaluation/v2/holdout_v2_parents.yaml", "stub_query.yaml"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "Reserved"):
                check_source(ROOT / path)


class SplitTest(unittest.TestCase):
    def test_paraphrases_contrast_and_templates_stay_together(self):
        first, second = annotation("a"), annotation("b", "새길동 근처 주행 속도의 평균을 알려줘")
        third = annotation("c", "새길동 주변 RPM 평균을 알려줘")
        third["grounding"]["concepts"][-1]["subtype"] = "rpm"
        third["parent_intent"] = "rpm"
        a, b = record(first), record(second)
        a["metadata"]["tags"] = ["contrast_pair:c"]
        train, valid = split_records([a, b, record(third)], seed=42)
        self.assertEqual(len(train), 3)
        self.assertEqual(valid, [])
        check_split(train, valid)

    def test_template_group_catches_missing_parent_labels(self):
        a, b = record(), record(annotation("other", "새길동 근처 주행 속도 평균"))
        a["metadata"]["parent_intent"] = "explicit_1"
        b["metadata"]["parent_intent"] = "explicit_2"
        split_records([a, b])
        self.assertEqual(a["metadata"]["parent_intent"], b["metadata"]["parent_intent"])

    def test_split_deterministic_and_no_parent_leakage(self):
        rows = [sft_record(e.to_dict(), source="store", source_representation="structured")
                for e in load_store().examples if e.expected_outcome != "needs_clarification"]
        a, b = split_records(copy.deepcopy(rows), seed=9)
        c, d = split_records(copy.deepcopy(rows), seed=9)
        self.assertEqual(a, c)
        self.assertEqual(b, d)
        check_split(a, b)
        with self.assertRaisesRegex(ValueError, "leakage"):
            check_split([a[0]], [a[0]])

    def test_duplicate_questions_different_parents_are_blocked(self):
        a, b = record(), record()
        a["metadata"]["parent_intent"], b["metadata"]["parent_intent"] = "a", "b"
        b["messages"][1]["content"] = " 새길동 주변 평균 주행 속도는! "
        with self.assertRaisesRegex(ValueError, "duplicate"):
            check_split([a], [b])


class DPOTest(unittest.TestCase):
    def test_deterministic_single_field_semantic_measure_mutation(self):
        payload = annotation()["grounding"]
        before = copy.deepcopy(payload)
        first, second = mutations(payload, seed=123), mutations(payload, seed=123)
        self.assertEqual(first, second)
        self.assertEqual(payload, before)
        m = next(c for c in first if c["negative_type"] == "measure_confusion")
        expected = copy.deepcopy(before)
        expected["concepts"][-1]["subtype"] = "rpm"
        self.assertEqual(m["payload"], expected)
        self.assertNotEqual(mutations(payload, seed=9), first)

    def test_semantic_and_constraint_pairs(self):
        row = record()
        payload = json.loads(row["messages"][-1]["content"])
        candidates = mutations(payload)
        semantic = next(c for c in candidates if c["negative_type"] == "measure_confusion")
        constraint = next(c for c in candidates if c["negative_type"] == "measure_omission")
        a = dpo_pair(row, semantic["payload"], negative_type=semantic["negative_type"])
        b = dpo_pair(row, constraint["payload"], negative_type=constraint["negative_type"])
        self.assertEqual(a["prompt"], row["messages"][:2])
        self.assertTrue(a["metadata"]["chosen_quality"]["validation_ok"])
        self.assertTrue(a["metadata"]["rejected_quality"]["validation_ok"])
        self.assertEqual(a["metadata"]["negative_category"], "semantic")
        self.assertEqual(b["metadata"]["negative_category"], "constraint")
        self.assertEqual(b["metadata"]["rejected_quality"]["error_code"], "NO_MEASURE")

    def test_identical_and_cosmetic_predictions_not_preferences(self):
        row = record()
        payload = json.loads(row["messages"][-1]["content"])
        payload["concepts"].reverse()
        for c in payload["concepts"]:
            c["text"] = "cosmetic"
        with self.assertRaisesRegex(ValueError, "identical"):
            dpo_pair(row, payload, negative_type="model_prediction")

    def test_event_omission_is_valid_and_not_synthetic_error(self):
        row = record()
        payload = json.loads(row["messages"][-1]["content"])
        self.assertNotIn("implicit_event_omission", {c["negative_type"] for c in mutations(payload)})
        payload["concepts"] = [c for c in payload["concepts"] if c["concept"] != "EVENT"]
        self.assertTrue(assess(payload, row["messages"][1]["content"])["validation_ok"])
        with self.assertRaisesRegex(ValueError, "equivalent"):
            dpo_pair(row, payload, negative_type="model_prediction")

    def test_od_and_multistage_mutations_use_real_fields(self):
        raw = annotation()
        raw["grounding"]["concepts"][0]["attributes"] = {"od_role": "pickup"}
        raw["grounding"]["factors"].update(bucket="week", aggregation="sum", rollup="avg")
        found = {c["negative_type"]: c for c in mutations(raw["grounding"])}
        self.assertEqual(found["od_role_confusion"]["payload"]["concepts"][0]["attributes"]["od_role"], "dropoff")
        self.assertNotIn("od_role", found["od_role_omission"]["payload"]["concepts"][0]["attributes"])
        swapped = found["aggregation_stage_swap"]["payload"]["factors"]
        self.assertEqual((swapped["aggregation"], swapped["rollup"]), ("avg", "sum"))

    def test_supported_unsupported_preferences(self):
        supported = record()
        pair = dpo_pair(supported, {"unsupported": True}, negative_type="supported_false_refusal")
        self.assertEqual(pair["metadata"]["negative_category"], "semantic")
        unsupported = record({"id": "u", "question": "주별 속도 전체 목록", "grounding": {"unsupported": True}})
        neg = mutations({"unsupported": True})[0]
        pair = dpo_pair(unsupported, neg["payload"], negative_type=neg["negative_type"])
        self.assertTrue(pair["metadata"]["chosen_quality"]["parse_ok"])
        self.assertEqual(pair["metadata"]["negative_category"], "semantic")

    def test_full_od_swap_is_valid_but_semantically_wrong(self):
        raw = annotation("od", "새길동에서 출발해 해솔동에 도착한 실차 구간 건수는?")
        origin = raw["grounding"]["concepts"][0]
        origin["attributes"] = {"od_role": "pickup"}
        destination = copy.deepcopy(origin)
        destination.update(id="destination", value={"name": "해솔동", "region": ""}, attributes={"od_role": "dropoff"})
        raw["grounding"]["concepts"].insert(1, destination)
        raw["grounding"]["concepts"][2]["subtype"] = "trip"
        raw["grounding"]["concepts"][3]["subtype"] = "trip_count"
        raw["grounding"]["factors"] = {}
        row = record(raw)
        chosen = json.loads(row["messages"][-1]["content"])
        candidate = next(m for m in mutations(chosen) if m["negative_type"] == "od_pickup_dropoff_swap")
        pair = dpo_pair(row, candidate["payload"], negative_type=candidate["negative_type"])
        self.assertTrue(pair["metadata"]["rejected_quality"]["validation_ok"])
        self.assertEqual(pair["metadata"]["negative_category"], "semantic")


class BuildIntegrationTest(unittest.TestCase):
    def test_store_build_manifest_and_hard_negative_mining(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            path = Path(directory)
            train, valid = build_sft(ROOT / "geoflow_examples/question_graph_examples.yaml", path, strict=True)
            self.assertEqual(len(train) + len(valid), 15)
            self.assertEqual(len(valid), 3)
            counts = coverage(train + valid)
            self.assertEqual(counts["unsupported_sample_count"], 2)
            self.assertEqual(counts["distributions"]["concept"]["EVENT"], 13)
            self.assertEqual(counts["distributions"]["measure"]["revenue"], 6)
            pairs = build_dpo(path, path, strict=True)
            check_split(pairs["train"], pairs["valid"])
            self.assertEqual({p["metadata"]["negative_category"] for split in pairs.values() for p in split}, {"semantic", "constraint"})
            manifest = json.loads((path / "manifest.json").read_text())
            self.assertEqual(manifest["sft"]["seed"], 42)
            self.assertIn("geoflow/factors.py", manifest["sft"]["definition_hashes"])
            self.assertIn("sft_train.jsonl", manifest["sft"]["output_hashes"])
            row = next(r for r in train if not json.loads(r["messages"][-1]["content"]).get("unsupported"))
            payload = json.loads(row["messages"][-1]["content"])
            payload["factors"]["date"] = "20260101"
            prediction = {"source_record_id": row["metadata"]["source_record_id"], "question": row["messages"][1]["content"],
                          "grounding": payload, "model": "sft-test", "prompt_hash": manifest["sft"]["prompt_hash"]}
            predictions = path / "predictions.jsonl"
            write_jsonl(predictions, [prediction])
            mined = build_dpo(path, path / "mined", predictions=predictions, max_negatives=0, strict=True)
            self.assertEqual(len(mined["train"]), 1)
            self.assertEqual(mined["valid"], [])
            self.assertEqual(mined["train"][0]["metadata"]["mutation_source"], "sft_inference")
            self.assertEqual(read_jsonl(path / "mined/dpo_train.jsonl"), mined["train"])

    def test_strict_reports_bad_annotations_and_eval_overlap(self):
        from query_loader import load_queries
        bad = annotation()
        bad["grounding"]["factors"]["invented"] = 2
        overlap = annotation("overlap", load_queries(ROOT / "stub_query.yaml")[0]["question"])
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            path = Path(directory)
            source = path / "data.yaml"
            source.write_text(yaml.safe_dump([bad, overlap], allow_unicode=True))
            with self.assertRaises(ValueError):
                build_sft(source, path / "out", source_representation="flat", strict=True)
            issues = json.loads((path / "out/manifest.json").read_text())["sft"]["issues"]
            self.assertEqual(len(issues), 2)
            self.assertIn("UNKNOWN_FACTOR", issues[0]["detail"])
            self.assertIn("overlaps", issues[1]["detail"])

    def test_source_mixing_is_reported(self):
        raw = annotation()
        other = annotation("b", "다른 새길동 속도 질문")
        other["grounding"]["factors"].pop("aggregation")
        other["grounding"]["factors"]["aggregation_plan"] = {"result": {"reducer": "avg"}}
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            source = Path(directory) / "data.yaml"
            source.write_text(yaml.safe_dump([raw, other], allow_unicode=True))
            with self.assertRaises(ValueError):
                build_sft(source, Path(directory) / "out", source_representation="structured", strict=True)


if __name__ == "__main__":
    unittest.main()
