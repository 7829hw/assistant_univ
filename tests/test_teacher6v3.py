import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/teacher"))
import teacher6v3 as T  # noqa: E402


class TeacherV3Test(unittest.TestCase):
    def test_conclusion_lines_roundtrip_on_corpus(self):
        rows = [json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v2.jsonl").read_text(encoding="utf-8").splitlines()]
        bad = [r["id"] for r in rows if not T.check_conclusion(T.conclusion_lines(r["semantics"]), r["semantics"])["pass"]]
        self.assertEqual(bad, [])

    def test_exposure(self):
        self.assertTrue(T.check_exposure("주어진 결론에 따르면 승차다")["exposed"])
        self.assertTrue(T.check_exposure("", "정답: 통행량")["exposed"])
        self.assertFalse(T.check_exposure("질문에 '태운'이 있으므로 승차 쪽이다", "측정: 통행량")["exposed"])

    def test_messages(self):
        sem = {"nodes": [{"subtype": "passage_count", "text": "통행량"}], "event": "passage", "factors": {}, "unsupported": None}
        a = T.messages("v3a", "질문", sem)
        b = T.messages("v3b", "질문", sem)
        self.assertNotIn("[결론]", a[1]["content"])
        self.assertIn("[결론]\n측정: 통행량", b[1]["content"])
        self.assertTrue(T.check_field_names(T.instruction_text("v3a"))["pass"])
        self.assertTrue(T.check_field_names(T.instruction_text("v3b"))["pass"])


if __name__ == "__main__":
    unittest.main()


class TeacherV3cTest(unittest.TestCase):
    def test_v3c_exposure_wider(self):
        self.assertTrue(T.check_exposure("모든 판단이 결론과 일치한다", "", "v3c")["exposed"])
        self.assertFalse(T.check_exposure("모든 판단이 결론과 일치한다", "", "v3b")["exposed"])
        self.assertTrue(T.check_exposure("Let me verify against the conclusion", "", "v3c")["exposed"])
        self.assertFalse(T.check_exposure("\"도착한\"은 하차 쪽이다", "측정: 통행량", "v3c")["exposed"])

    def test_v3c_prompt(self):
        self.assertIn("부근", T.instruction_text("v3c"))
        self.assertTrue(T.check_field_names(T.instruction_text("v3c"))["pass"])
        self.assertIn("[결론]", T.messages("v3c", "질문", {"nodes": [{"subtype": "rpm", "text": "RPM"}], "event": "drive", "factors": {}, "unsupported": None})[1]["content"])
