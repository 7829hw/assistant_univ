# -*- coding: utf-8 -*-
"""pilot_010 근접 대조 teacher 지시·검사(결정 242 AA2)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_010/teacher"))

import teacher_contrast10 as T  # noqa: E402

V5 = ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v5.jsonl"


def record(rid="b012:b012-077"):
    for line in V5.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["id"] == rid:
            return r
    raise KeyError(rid)


THINK = ("질문은 지난 기간의 택시 수입을 월별로 먼저 묶어 묻는다.\n"
         "\"월별 평균\"이라는 말이 있어 월 단위로 먼저 집계하고, \"최댓값\"으로 다시 고른다.\n"
         "분기별로 묶었다면 답할 수 없지만, 월 단위라 답할 수 있다.\n")


class Contrast(unittest.TestCase):
    def setUp(self):
        self.r = record()
        self.sem = self.r["semantics"]
        self.five = T.T3.conclusion_lines(self.sem)
        self.fb = T.forbidden_sections()

    def test_forbidden_sections(self):
        self.assertEqual(self.fb, ["분석으로 나타낼 수 있는 범위", "판단할 다섯 가지", "사용자 메시지"])

    def test_user_message(self):
        u = T.user_message(self.r["question"], self.sem, "r2_bucket")
        self.assertTrue(u.startswith(self.r["question"] + "\n\n[결론]\n" + self.five))
        self.assertTrue(u.endswith("[가까운 거부 범주]\n" + T.NEAR["r2_bucket"]))
        self.assertNotIn("가까운 거부 범주", T.user_message(self.r["question"], self.sem))

    def test_good_trace_passes(self):
        ev = T.evaluate({"semantics": self.sem}, THINK + self.five, self.five, self.fb)
        self.assertTrue(ev["pass"], ev["after"]["reasons"])

    def test_f_prime_refusal_in_output(self):
        r = T.checks_contrast(THINK, self.five + "\n결론: 지원하지 않음", self.sem, self.fb)
        self.assertIn("f'", r["reasons"])
        self.assertTrue(r["f'"]["conclusion_matches"])

    def test_wrong_conclusion_fails_b_and_f(self):
        bad = self.five.replace("집계: ", "집계: 합계, 다시 ", 1) if "집계: " in self.five else self.five + "x"
        r = T.checks_contrast(THINK, bad, self.sem, self.fb)
        self.assertIn("b", r["reasons"])
        self.assertIn("f'", r["reasons"])

    def test_section_citation_fails(self):
        r = T.checks_contrast(THINK + "판단할 다섯 가지를 차례로 본다.\n", self.five, self.sem, self.fb)
        self.assertEqual(r["s235"], ["판단할 다섯 가지"])
        self.assertIn("s235", r["reasons"])

    def test_exposure_label_fails(self):
        r = T.checks_contrast(THINK + "가까운 거부 범주는 묶음 단위다.\n", self.five, self.sem, self.fb)
        self.assertIn("c", r["reasons"])

    def test_unsupported_field_name_fails(self):
        r = T.checks_contrast(THINK + "unsupported 가 아니다.\n", self.five, self.sem, self.fb)
        self.assertIn("a", r["reasons"])


if __name__ == "__main__":
    unittest.main()
