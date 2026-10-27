# -*- coding: utf-8 -*-
"""protected_final_v2 검사 2판: 근접 대조 짧은 이름(결정 254 AB8). 합성 서식만 쓴다(문항 없음)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_010/protected_final_v2"))

import validate_pf2b as B  # noqa: E402


class Normalize(unittest.TestCase):
    def test_short_names(self):
        for short, full in (("지표", "없는 지표"), ("묶음 단위", "없는 묶음 단위"), ("개별 단위", "개별 단위"), ("예측", "예측"),
                            ("교통수단", "다른 교통수단"), ("도메인 밖", "도메인 밖")):
            self.assertEqual(B.normalize_contrast(short), full)
            self.assertEqual(B.normalize_contrast(f"{short}(설명 붙음)"), full)
            self.assertEqual(B.normalize_contrast(f" {short} （설명） "), full)

    def test_full_names_and_none(self):
        self.assertEqual(B.normalize_contrast("없는 묶음 단위"), "없는 묶음 단위")
        self.assertEqual(B.normalize_contrast("다른 교통수단 (버스)"), "다른 교통수단")
        self.assertEqual(B.normalize_contrast("-"), "-")
        self.assertEqual(B.normalize_contrast(""), "")

    def test_unknown_kept(self):
        self.assertEqual(B.normalize_contrast("기간"), "기간")
        self.assertEqual(B.normalize_contrast("지표 묶음"), "지표 묶음")

    def test_fake_workbook_unchanged(self):
        fake = ROOT / "sft_dpo_inventory/pilot_009/protected_final_v2/protected_final_v2_template.xlsx"
        r = B.validate(fake, test=True, tg={})
        self.assertNotIn("contrast_code", r.get("row_problem_counts", {}))


if __name__ == "__main__":
    unittest.main()
