# -*- coding: utf-8 -*-
"""pilot_007 두 arm 데이터 순서 공유(결정 168): 레코드 수가 달라도 질문 순서가 같다."""

import hashlib
import os
import sys
import types
import unittest
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_007/train"))

import order7 as O  # noqa: E402

RC = ROOT / "sft_dpo_inventory/pilot_007/build/RC3c"


def rec(q, scope, tid, sha="x"):
    return {"metadata": {"source_record_id": q, "loss_scope": scope, "trace_id": tid, "trace_sha256": sha}}


class SharedOrder(unittest.TestCase):
    def test_synthetic_arms_same_question_order(self):
        full = [rec("q1", "json_only", "J1:q1:1", "b"), rec("q2", "full_response", "q2:t:1"), rec("q1", "full_response", "q1:t:2"),
                rec("q3", "json_only", "J1:q3:1", "a"), rec("q1", "full_response", "q1:t:1")]
        part = [rec("q3", "json_only", "J6:q3:1", "c"), rec("q2", "full_response", "q2:t:1"), rec("q1", "full_response", "q1:t:1"),
                rec("q1", "full_response", "q1:t:2")]
        for seed in (43, 20261016, 7):
            f, p = O.order_records(full, seed), O.order_records(part, seed)
            self.assertEqual(O.question_sequence(f), O.question_sequence(p))
            self.assertEqual(O.question_sequence(f), O.question_order(["q1", "q2", "q3"], seed))
            # 질문 안: teacher 먼저 trace_id 순, 그다음 8b
            q1 = [r["metadata"]["trace_id"] for r in f if r["metadata"]["source_record_id"] == "q1"]
            self.assertEqual(q1, ["q1:t:1", "q1:t:2", "J1:q1:1"])
            # 같은 질문의 레코드는 이어져 있다
            seq = [r["metadata"]["source_record_id"] for r in f]
            self.assertEqual(len([i for i in range(1, len(seq)) if seq[i] != seq[i - 1]]) + 1, 3)

    def test_rc3c_arms(self):
        full, part = O.load_jsonl(RC / "full/sft_train.jsonl"), O.load_jsonl(RC / "partial/sft_train.jsonl")
        self.assertNotEqual(len(full), len(part))
        orders = set()
        for seed in (43, 20261016, 7):
            sf, sp = O.question_sequence(O.order_records(full, seed)), O.question_sequence(O.order_records(part, seed))
            self.assertEqual(sf, sp)
            self.assertEqual(hashlib.sha256("\n".join(sorted(sf)).encode()).hexdigest(),
                             hashlib.sha256("\n".join(sorted(sp)).encode()).hexdigest())
            d = O.order_file({"full": [r["metadata"]["source_record_id"] for r in full], "partial": [r["metadata"]["source_record_id"] for r in part]}, seed)
            self.assertEqual(d["order"], sf)
            orders.add(d["order_sha256"])
        self.assertEqual(len(orders), 3)

    def test_order_file_rejects_different_lists(self):
        with self.assertRaises(ValueError):
            O.order_file({"full": ["a", "b"], "partial": ["a"]}, 1)

    def test_sequential_sampler(self):
        import torch
        from transformers import Trainer
        original = Trainer._get_train_sampler
        try:
            O.install_sequential_sampler()
            fake = types.SimpleNamespace(train_dataset=list(range(5)))
            sampler = Trainer._get_train_sampler(fake)
            self.assertIsInstance(sampler, torch.utils.data.SequentialSampler)
            self.assertEqual(list(sampler), [0, 1, 2, 3, 4])
        finally:
            Trainer._get_train_sampler = original


if __name__ == "__main__":
    unittest.main()
