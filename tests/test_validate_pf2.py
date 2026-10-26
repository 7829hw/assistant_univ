# -*- coding: utf-8 -*-
"""protected_final_v2 검사 도구(결정 239 Z7) — 합성 서식(가짜 문항)으로 시험한다. 실제 v2 문항은 쓰지 않는다."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_009/protected_final_v2"))

import common_pf2 as C  # noqa: E402
import make_fake_pf2 as F  # noqa: E402
import validate_pf2 as V  # noqa: E402


class ValidatePF2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.tmp.name) / "fake.xlsx"
        F.B4.write_workbook(cls.path, [(C.SHEET, C.COLUMNS, [r for r, _ in F.FAKE])])
        tg = {"dummy": [("d1", "가짜시험 람다 번호 겹침", None), ("d2", "전혀 관계없는 문장 하나", None)]}
        cls.report = V.validate(cls.path, test=True, tg=tg)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_constants_follow_decision_238(self):
        self.assertEqual(C.TYPE_TARGET["장소 이름(역방향)"], 5)
        self.assertEqual(C.TYPE_TARGET["통과량 건수"], 19)
        self.assertEqual(sum(C.TYPE_TARGET.values()) + C.REFUSAL_TARGET, C.SIZE)
        self.assertEqual(sum(C.FORM_TARGET.values()), C.REFUSAL_TARGET)
        self.assertEqual(len(C.SCOPE_NAME_ALLOWED), 5)

    def test_expected_row_codes(self):
        rp = self.report["row_problems"]
        for row, want in F.FAKE:
            n = row[0]
            if n == "10":
                continue  # 번호 겹침 두 행은 아래에서 따로 본다
            got = {c for c in rp.get(n, []) if not c.startswith("overlap_")}
            self.assertEqual(got, want, n)

    def test_duplicate_number_rows(self):
        got = set(self.report["row_problems"]["10"])
        self.assertTrue({"duplicate_number", "form_code", "difficulty_code", "hard_factor_code"} <= got)

    def test_overlap_question_reported_by_row_and_target_only(self):
        self.assertIn("overlap_question:dummy", self.report["row_problems"]["10"])
        text = str(self.report)
        for q in F.QUESTIONS:
            self.assertNotIn(q, text)

    def test_distribution_counts(self):
        d = self.report["distribution"]
        self.assertEqual(d["forms"]["M"]["count"], 2)
        self.assertEqual(d["forms"]["P"]["count"], 2)
        self.assertEqual(d["forms"]["C"]["count"], 2)
        self.assertEqual(d["p_error_codes"], {"UNCONSUMED_CONDITION": 1})
        self.assertEqual(d["c_error_codes"], {"AMBIGUOUS_INNER_AGGREGATION": 1})
        self.assertEqual(d["contrast"]["count"], 1)
        self.assertIn("size_not_target", self.report["distribution_problems"])
        self.assertTrue(self.report["test_mode"])

    def test_file_inside_repo_flagged_without_test(self):
        p = ROOT / "sft_dpo_inventory/pilot_009/protected_final_v2/protected_final_v2_template.xlsx"
        r = V.validate(p, test=False, tg={})
        self.assertIn("file_inside_repository", r["file_problems"])
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
