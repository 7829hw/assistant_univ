# -*- coding: utf-8 -*-
"""pilot_009 S1 teacher 절 이름 거르기 규칙(결정 235)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_009/build"))

import teacher_filter9 as F  # noqa: E402


class SectionRule(unittest.TestCase):
    def test_section_names_whole_line_only(self):
        text = "머리말\n[가나]\n본문 [다라] 중간\n  [마바]  \n[사아\n"
        self.assertEqual(F.section_names(text), ["가나"])

    def test_allowed_if_in_student_prompt(self):
        r = F.rule("학생 prompt에는 [출력 형식] 절이 있다", {"x": "[출력]\n본문\n[분석으로 답할 수 있는 것]\n"})
        self.assertEqual(r["x"]["allowed"], ["출력"])
        self.assertEqual(r["x"]["forbidden"], ["분석으로 답할 수 있는 것"])

    def test_real_prompts(self):
        from training.trainer_common import expected_system_prompt
        r = F.rule(expected_system_prompt("full"))
        self.assertEqual(r["refusal_v1"]["names"], ["분석으로 답할 수 있는 것", "사용자 메시지", "출력"])
        self.assertEqual(r["refusal_v1"]["forbidden"], ["분석으로 답할 수 있는 것", "사용자 메시지"])
        self.assertEqual(r["refusal_v1"]["allowed"], ["출력"])
        self.assertIn("판단할 다섯 가지", r["v3b"]["forbidden"])

    def test_cites_with_or_without_brackets(self):
        fb = ["분석으로 답할 수 있는 것", "사용자 메시지"]
        self.assertEqual(F.cites("[분석으로 답할 수 있는 것]에서 보면", fb), ["분석으로 답할 수 있는 것"])
        self.assertEqual(F.cites("분석으로 답할 수 있는 것의 목록", fb), ["분석으로 답할 수 있는 것"])
        self.assertEqual(F.cites("\"기사별\"은 개별 단위다", fb), [])

    def test_strip_lines_keeps_other_bytes(self):
        th = "첫 줄\n[분석으로 답할 수 있는 것]에 따르면 기사 단위는 없다.\n결론: 지원하지 않음"
        new, gone, lost = F.strip_lines(th, ["분석으로 답할 수 있는 것"])
        self.assertEqual(new, "첫 줄\n결론: 지원하지 않음")
        self.assertEqual(len(gone), 1)
        self.assertFalse(lost)

    def test_strip_lines_loss_when_four_or_more(self):
        th = "".join(f"[사용자 메시지] {i}\n" for i in range(4)) + "끝"
        _, gone, lost = F.strip_lines(th, ["사용자 메시지"])
        self.assertEqual(len(gone), 4)
        self.assertTrue(lost)


if __name__ == "__main__":
    unittest.main()
