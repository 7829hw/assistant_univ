# -*- coding: utf-8 -*-
"""다음 보호 셋 검사 v2(pilot_007 B2 C4): 겹침 대상에 실제 학습 레코드(RC 빌드 sft_train.jsonl)를 넣는다."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PF = ROOT / "sft_dpo_inventory/pilot_006/protected_final"
sys.path.insert(0, str(PF))
RC5 = ROOT / "sft_dpo_inventory/pilot_007/build/RC5"
V1 = ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v1.jsonl"


def rc5_question_ids():
    return {json.loads(l)["metadata"]["source_record_id"] for a in ("full", "partial") for l in (RC5 / a / "sft_train.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}


class TrainTargets(unittest.TestCase):
    def test_rc5_targets_cover_all_training_questions(self):
        import validate_v2 as V
        tg, missing = V.train_targets(V.DEFAULT_TRAIN, V.DEFAULT_CORPUS)
        self.assertEqual(missing, [])
        self.assertEqual(set(tg), {"train_rc:RC5/full", "train_rc:RC5/partial"})
        ids = {i for v in tg.values() for i, _, _ in v}
        self.assertEqual(ids, rc5_question_ids())
        self.assertTrue(all(pl for v in tg.values() for _, _, pl in v))

    def test_v1_target_misses_some_rc5_questions(self):
        """validate.py(v1 corpus만)가 놓치는 RC5 질문이 있다 — v2가 필요한 이유."""
        v1 = {json.loads(l)["id"] for l in V1.read_text(encoding="utf-8").splitlines() if l.strip()}
        self.assertGreater(len(rc5_question_ids() - v1), 0)

    def test_unresolved_id_reported(self):
        import validate_v2 as V
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x" / "full" / "sft_train.jsonl"
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({"metadata": {"source_record_id": "no-such-id"}}) + "\n", encoding="utf-8")
            tg, missing = V.train_targets([str(p)], V.DEFAULT_CORPUS)
        self.assertEqual(missing, ["no-such-id"])
        self.assertEqual(tg["train_rc:x/full"], [])


class EndToEnd(unittest.TestCase):
    def test_fake_row_with_training_question_flagged(self):
        """가짜 xlsx 1행 질문을 v1에 없는 RC5 학습 질문으로 바꾸면 v2는 train_rc 겹침으로 잡고, 출력에 질문이 없다."""
        import make_fake
        sys.path.insert(0, str(ROOT))
        v1 = {json.loads(l)["id"] for l in V1.read_text(encoding="utf-8").splitlines() if l.strip()}
        corpus = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v3.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
        qid = sorted(rc5_question_ids() - v1)[0]
        q = corpus[qid]["question"]
        rows = [list(r) for r in make_fake.FAKE]
        rows[0][1] = q
        with tempfile.TemporaryDirectory() as d:
            x = Path(d) / "fake.xlsx"
            make_fake.B4.write_workbook(str(x), [(make_fake.SHEET, make_fake.COLUMNS, rows)])
            r = subprocess.run([sys.executable, str(PF / "validate_v2.py"), "--xlsx", str(x), "--test"], capture_output=True, text=True)
        out = json.loads(r.stdout)
        self.assertIn("overlap_question:train_rc:RC5/full", out["row_problems"]["1"])
        self.assertIn("overlap_question:train_rc:RC5/partial", out["row_problems"]["1"])
        self.assertEqual(out["train_ids_missing_in_corpus"], 0)
        self.assertNotIn(q, r.stdout)


if __name__ == "__main__":
    unittest.main()
