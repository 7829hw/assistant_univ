# -*- coding: utf-8 -*-
"""pilot_007 c2 편집(결정 185): (ii) 줄만 지우고 다른 줄은 바이트 그대로, 편집 기록이 맞는지."""

import hashlib
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sft_dpo_inventory/pilot_007/teacher"))

import c2_edit as E  # noqa: E402

T = ("질문: \"부산 초읍동 주변 실차 통행량\"\n"
     "1. 측정: \"통행했어\" → 통행량. 상태 실차.\n"
     "2. 끝: 장소가 끝을 정하지 않는다. 없음.\n"
     "주어진 결론과 일치한다.\n"
     "  들여쓴 줄도 그대로 둔다.  \n"
     "결론을 보면 측정은 통행량이다\n"
     "5. 주변: \"주변\"이 있다. 예.")


class C2Edit(unittest.TestCase):
    def test_only_type_ii_lines_removed(self):
        new, gone, lost = E.edit_thinking(T)
        self.assertEqual(gone, ["주어진 결론과 일치한다.", "결론을 보면 측정은 통행량이다"])
        self.assertFalse(lost)
        self.assertNotIn("결론", new)

    def test_other_lines_byte_identical(self):
        new, gone, _ = E.edit_thinking(T)
        kept = [ln for ln in T.splitlines(keepends=True) if ln.rstrip("\n") not in gone]
        self.assertEqual(new, "".join(kept))
        self.assertIn("  들여쓴 줄도 그대로 둔다.  \n", new)
        self.assertTrue(new.endswith("5. 주변: \"주변\"이 있다. 예."))

    def test_no_type_ii_unchanged(self):
        s = "1. 측정: 통행량.\n2. 끝: 없음."
        new, gone, lost = E.edit_thinking(s)
        self.assertEqual(new, s)
        self.assertEqual(gone, [])
        self.assertEqual(E.sha(new), hashlib.sha256(s.encode()).hexdigest())

    def test_field_line_removed_is_loss(self):
        s = "1. 측정: 통행량. 주어진 결론과 일치.\n2. 끝: 없음."
        _, gone, lost = E.edit_thinking(s)
        self.assertEqual(len(gone), 1)
        self.assertTrue(lost)

    def test_split_record_roundtrip(self):
        c = "<think>\n" + T + "\n</think>\n\n{\"concepts\": []}"
        a, th, b = E.split_record(c)
        self.assertEqual(a + th + b, c)
        self.assertTrue(th.startswith("\n질문"))


if __name__ == "__main__":
    unittest.main()
