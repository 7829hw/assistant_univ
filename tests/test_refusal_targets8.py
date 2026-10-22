# -*- coding: utf-8 -*-
"""pilot_008 RC6 S-2 거부 target(결정 223): 근거 문장 중립성·질문별 차이·JSON 형식."""

import json
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_008/build"))

import refusal_targets8 as T  # noqa: E402

V4 = ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v4.jsonl"


def r1_questions():
    out = {}
    for line in V4.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["id"].startswith("b011:") and r["provenance"]["kind"] == "r1_refusal":
            out[r["id"][5:]] = (r["question"], r["provenance"]["gap"])
    return out


class RefusalTargets(unittest.TestCase):
    def setUp(self):
        self.q = r1_questions()

    def test_covers_all_approved_r1(self):
        self.assertEqual(set(self.q), set(T.SPAN))

    def test_span_in_question(self):
        for qid, (question, _) in self.q.items():
            self.assertIn(T.SPAN[qid], question, qid)

    def test_no_field_names_or_conclusion_words(self):
        for qid, (_, gap) in self.q.items():
            for v in range(4):
                self.assertEqual(T.check_text(T.rationale(qid, gap, v)), [], (qid, v))

    def test_check_text_catches(self):
        self.assertTrue(T.check_text("결론: unsupported"))
        self.assertTrue(T.check_text("concepts를 비운다"))

    def test_distinct_per_question_and_variant(self):
        texts = [T.rationale(qid, gap, v) for qid, (_, gap) in self.q.items() for v in range(4)]
        self.assertEqual(len(texts), len(set(texts)))
        first = [T.rationale(qid, gap, 0) for qid, (_, gap) in self.q.items()]
        self.assertEqual(len(first), len(set(first)))

    def test_json_target(self):
        for qid, (_, gap) in list(self.q.items())[:5]:
            c = T.content(qid, gap, 1)
            self.assertTrue(c.startswith("<think>\n"))
            think, _, tail = c.partition("</think>")
            self.assertEqual(json.loads(tail.strip()), {"unsupported": True})
            self.assertNotIn("unsupported", think)

    def test_parses_with_training_split(self):
        sys.path.insert(0, str(ROOT))
        from training.data import thinking as TH
        c = T.content("b011-001", "r1_metric", 0)
        self.assertEqual(TH.response_json(c), {"unsupported": True})


if __name__ == "__main__":
    unittest.main()
