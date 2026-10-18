# -*- coding: utf-8 -*-
"""pilot_007 teacher 검사 (d) 한국어·(e) 영어 노출·메타·(ii) 정리 규칙(결정 166)."""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sft_dpo_inventory/pilot_007/teacher"))

import teacher_checks7 as C  # noqa: E402


class KoreanCheck(unittest.TestCase):
    def test_korean_passes(self):
        t = '질문: "부산 초읍동 주변 실차 통행량"\n1. 측정: "통행했어" → 통행량. 상태 실차.'
        self.assertTrue(C.check_korean(t)["pass"])

    def test_english_fails(self):
        t = "Let me analyze this question carefully. The measurement is passage count with occupied status. 측정: 통행량"
        r = C.check_korean(t)
        self.assertFalse(r["pass"])
        self.assertLess(r["korean_ratio"], 0.5)

    def test_short_terms_do_not_count(self):
        # 한 글자 영문(예: "H3"의 H)은 세지 않는다; "rpm" 같은 짧은 낱말은 세지만 한국어 생각이면 비율이 높다.
        t = "1. 측정: rpm이라고 명시되어 있다. 택시의 엔진 회전수를 묻는 것이고 H3 셀별로 나누지 않는다."
        self.assertTrue(C.check_korean(t)["pass"])

    def test_empty_fails(self):
        self.assertFalse(C.check_korean("")["pass"])


class ExposureMeta(unittest.TestCase):
    def test_english_exposure(self):
        for t in ("이건 통행량.\nThis matches the five lines provided. Good.", "Let me verify against the given conclusion.",
                  "But wait, the five lines say '끝: 없음'.", "결론: conclusion lines"):
            self.assertFalse(C.check_english_exposure_meta(t)["pass"], t)

    def test_meta(self):
        for t in ("Now let me write the thinking in Korean.", "Let me make sure I don't use forbidden words.", "구조를 따른다(required format)."):
            self.assertFalse(C.check_english_exposure_meta(t)["pass"], t)

    def test_clean_korean(self):
        t = '질문: "지난주 동대구역 부근을 지난 택시의 rpm은?"\n5. 주변: "부근"이 있다. 예.'
        self.assertTrue(C.check_english_exposure_meta(t)["pass"])


class TypeII(unittest.TestCase):
    def test_type_ii(self):
        self.assertTrue(C.has_type_ii("측정: 통행량\n주어진 결론과 일치한다."))
        self.assertFalse(C.has_type_ii("측정은 통행량이다. 끝은 없음."))


if __name__ == "__main__":
    unittest.main()
