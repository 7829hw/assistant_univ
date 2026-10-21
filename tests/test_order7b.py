# -*- coding: utf-8 -*-
"""pilot_007 B2단계 공유 순서 O4'(결정 206): slot 키 순열, 공통 slot 상대 순서, 질문 목록 sha256, 연속 길이 통계."""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_007/train"))

import order7 as O  # noqa: E402
import order7b as B  # noqa: E402

RC = ROOT / "sft_dpo_inventory/pilot_007/build/RC5"


def rec(q, scope, tid, sha="x"):
    return {"metadata": {"source_record_id": q, "loss_scope": scope, "trace_id": tid, "trace_sha256": sha}}


FULL = [rec("q1", "json_only", "J1:q1:1", "b"), rec("q2", "full_response", "q2:t:1"), rec("q1", "full_response", "q1:t:2"),
        rec("q3", "json_only", "J1:q3:1", "a"), rec("q1", "full_response", "q1:t:1"), rec("q2", "json_only", "J1:q2:1", "c")]
PART = [rec("q3", "json_only", "J6:q3:1", "c"), rec("q2", "full_response", "q2:t:1"), rec("q1", "full_response", "q1:t:1"),
        rec("q1", "full_response", "q1:t:2")]


class Slots(unittest.TestCase):
    def test_slot_keys_follow_within_rule(self):
        ks = [(k, r["metadata"]["trace_id"]) for k, r in B.slots(FULL) if k.startswith("q1#")]
        self.assertEqual(ks, [("q1#0", "q1:t:1"), ("q1#1", "q1:t:2"), ("q1#2", "J1:q1:1")])

    def test_common_slots_same_relative_order(self):
        for seed in (43, 20261016, 7, 11, 2027):
            d = B.order_file({"full": FULL, "partial": PART}, seed)
            self.assertTrue(d["common_relative_order_equal"])
            f = B.arm_slot_sequence(FULL, d["order"])
            p = B.arm_slot_sequence(PART, d["order"])
            self.assertEqual([k for k in f if k in set(p)], p)  # PART slot은 모두 FULL에도 있음
            self.assertEqual(len(B.order_records(FULL, d["order"])), len(FULL))

    def test_rejects_different_question_lists(self):
        with self.assertRaises(ValueError):
            B.order_file({"full": FULL, "partial": PART[1:]}, 1)  # q3 빠짐

    def test_common_relative_order_detects_difference(self):
        self.assertTrue(B.common_relative_order_equal(["a", "x", "b"], ["a", "b", "y"]))
        self.assertFalse(B.common_relative_order_equal(["a", "b"], ["b", "a"]))


class RunStats(unittest.TestCase):
    def test_values(self):
        s = B.run_stats(["a", "a", "b", "c", "c", "c", "a"])
        self.assertEqual(s["runs"], 4)
        self.assertEqual(s["max_run"], 3)
        self.assertAlmostEqual(s["mean_run"], 7 / 4)
        self.assertAlmostEqual(s["share_runs_ge2"], 0.5)
        self.assertAlmostEqual(s["share_records_in_runs_ge2"], 5 / 7, places=4)

    def test_o4_grouped_vs_o4prime(self):
        """B단계 O4는 질문마다 run 하나(run 수 = 질문 수), O4'는 그렇지 않다."""
        full = O.load_jsonl(RC / "full/sft_train.jsonl")
        o4 = B.run_stats([B.qid(r) for r in O.order_records(full, 43)])
        self.assertEqual(o4["runs"], len({B.qid(r) for r in full}))
        d = B.order_file({"full": full, "partial": O.load_jsonl(RC / "partial/sft_train.jsonl")}, 43)
        self.assertLess(d["arms"]["full"]["run_stats"]["max_run"], o4["max_run"])
        self.assertGreater(d["arms"]["full"]["run_stats"]["runs"], o4["runs"])


class RC5(unittest.TestCase):
    def test_rc5_question_lists_and_common_order(self):
        recs = {"full": O.load_jsonl(RC / "full/sft_train.jsonl"), "partial": O.load_jsonl(RC / "partial/sft_train.jsonl")}
        shas = set()
        for seed in (43, 20261016):
            d = B.order_file(recs, seed)
            self.assertTrue(d["common_relative_order_equal"])
            self.assertEqual(d["arms"]["full"]["slots"], 1811)
            self.assertEqual(d["arms"]["partial"]["slots"], 1775)
            shas.add(d["question_list_sha256"])
        self.assertEqual(len(shas), 1)


if __name__ == "__main__":
    unittest.main()
