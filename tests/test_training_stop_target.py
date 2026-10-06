"""Decision 14 stop targets: a human-approved T2PC stop grounding is a valid target only when it stops the same way."""
import json
import unittest
from pathlib import Path

from training.data.build_sft import sft_record
from training.data.validation import STOP_TARGET, assess, chosen_ok, stop_signature, target_ok

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "sft_dpo_inventory/batch004/candidates_checked.json"


def candidate(cid):
    return next(c for c in json.loads(CANDIDATES.read_text(encoding="utf-8"))["candidates"] if c["id"] == cid)


class StopTargetTest(unittest.TestCase):
    def setUp(self):
        self.stop = candidate("b004-34")       # 요일별 속도: compose에서 MISSING_REQUIRED_INPUT으로 멈춘다
        self.answer = candidate("b004-18")

    def annotation(self, item, tags):
        return {"id": item["id"], "question": item["question"], "grounding": item["draft_grounding"],
                "family": item["family"], "tags": tags, "version": "test"}

    def test_stop_target_requires_tag_and_records_signature(self):
        with self.assertRaisesRegex(ValueError, "Gold parse/compose/validate failed"):
            sft_record(self.annotation(self.stop, ["targeted_gold"]), source="test", source_representation="flat")
        record = sft_record(self.annotation(self.stop, ["targeted_gold", STOP_TARGET]), source="test",
                            source_representation="flat")
        self.assertEqual(record["metadata"]["target_kind"], STOP_TARGET)
        self.assertEqual(record["metadata"]["expected_stop"][0], "MISSING_REQUIRED_INPUT")

    def test_tag_on_answerable_gold_is_refused(self):
        with self.assertRaisesRegex(ValueError, "does not parse-and-stop"):
            sft_record(self.annotation(self.answer, ["targeted_gold", STOP_TARGET]), source="test",
                       source_representation="flat")

    def test_target_ok_matches_only_the_recorded_stop(self):
        result = assess(self.stop["draft_grounding"], self.stop["question"])
        self.assertFalse(chosen_ok(result))
        meta = {"target_kind": STOP_TARGET, "expected_stop": stop_signature(result)}
        self.assertTrue(target_ok(result, meta))
        self.assertFalse(target_ok(result, {}))
        self.assertFalse(target_ok(result, {**meta, "expected_stop": ["UNCONSUMED_CONDITION", []]}))
        broken = assess({"concepts": "not-a-list"}, self.stop["question"])
        self.assertFalse(target_ok(broken, meta))
        ok = assess(self.answer["draft_grounding"], self.answer["question"])
        self.assertTrue(target_ok(ok, meta))


if __name__ == "__main__":
    unittest.main()
