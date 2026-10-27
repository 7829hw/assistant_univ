# -*- coding: utf-8 -*-
"""pilot_010 근접 대조 teacher 지시 2판·넓힌 검사 (c)(결정 248 AB2)."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_010/teacher"))

import teacher_contrast10b as T  # noqa: E402

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


class ContrastV2(unittest.TestCase):
    def setUp(self):
        self.r = record()
        self.sem = self.r["semantics"]
        self.five = T.T3.conclusion_lines(self.sem)
        self.fb = T.forbidden_sections()

    def test_prompt_has_no_label(self):
        text = T.instruction_text()
        for w in ("가까운 거부", "거부 범주", "범주"):
            self.assertNotIn(w, text)
        self.assertNotEqual(T.instruction_sha256(), T.T1.instruction_sha256())

    def test_forbidden_sections(self):
        self.assertEqual(self.fb, ["분석으로 나타낼 수 있는 범위", "판단할 다섯 가지", "사용자 메시지"])

    def test_user_message_has_no_label(self):
        u = T.user_message(self.r["question"], self.sem)
        self.assertEqual(u, self.r["question"] + "\n\n[결론]\n" + self.five)
        m = T.messages({"question": self.r["question"], "semantics": self.sem, "gap": "r2_bucket"})
        self.assertNotIn("범주", m[1]["content"])

    def test_good_trace_passes(self):
        ev = T.evaluate({"semantics": self.sem}, THINK + self.five, self.five, self.fb)
        self.assertTrue(ev["pass"], ev["after"]["reasons"])

    def test_label_variants_fail_c(self):
        for line in ("가까운 거부: 분기별로 묶는 질문.", "거부 범주와 견주어: 기사별은 안 된다.", "없는 묶음 범주: 분기.", "가까운 거부 범주는 묶음 단위다.",
                     "근접 대조로 보면 분기는 안 된다.", "대조 범주: 예측."):
            r = T.checks_contrast(THINK + line + "\n", self.five, self.sem, self.fb)
            self.assertIn("c", r["reasons"], line)

    def test_plain_sentence_not_caught(self):
        r = T.checks_contrast(THINK + "기사별로 나눴다면 답할 수 없다.\n", self.five, self.sem, self.fb)
        self.assertNotIn("c", r["reasons"])

    def test_other_checks_unchanged(self):
        r = T.checks_contrast(THINK, self.five + "\n결론: 지원하지 않음", self.sem, self.fb)
        self.assertIn("f'", r["reasons"])
        r = T.checks_contrast(THINK + "판단할 다섯 가지를 차례로 본다.\n", self.five, self.sem, self.fb)
        self.assertIn("s235", r["reasons"])
        r = T.checks_contrast(THINK + "unsupported 가 아니다.\n", self.five, self.sem, self.fb)
        self.assertIn("a", r["reasons"])

    def test_to_arm_records_tag(self):
        recs = T.to_arm_records({"trace_id": "t", "thinking": THINK + self.five, "content": self.five}, self.sem, self.r["question"], "x")
        self.assertEqual(recs["full"]["metadata"]["teacher_instruction"], "teacher_contrast_v2")


if __name__ == "__main__":
    unittest.main()
