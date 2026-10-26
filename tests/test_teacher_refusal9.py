# -*- coding: utf-8 -*-
"""pilot_009 teacher 거부 추론(결정 228): 지시 메시지, 검사 (a)(c)(d)(e)(ii)(f), c2 정리 뒤 통과, 학습 레코드 형식."""

import json
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_009/teacher"))

import teacher_refusal9 as T  # noqa: E402

GOOD = ("질문은 지난달 부산 택시 수입을 기사마다 나눠 순위를 매겨 달라고 한다.\n"
        "\"기사별\"이라는 말이 핵심이다. 택시 운행 기록은 장소, 기간, 개인·법인 택시로만 모아 볼 수 있고 기사 한 사람 한 사람을 구분하지 않는다.\n"
        "시군구별로 수입을 나누는 질문이라면 답할 수 있지만, 이 질문은 기사별로 나눈다.\n"
        "결론: 지원하지 않음")
TARGET = {"id": "x", "variant": "refusal_v1", "gap": "r1_entity", "question": "지난달 부산 택시 기사별 수입 순위를 알려줘"}


class TeacherRefusal(unittest.TestCase):
    def test_messages(self):
        m = T.messages(TARGET)
        self.assertEqual(m[0]["role"], "system")
        self.assertIn("결론: 지원하지 않음", m[0]["content"])
        self.assertTrue(m[1]["content"].startswith(TARGET["question"] + "\n\n[결론]\n지원하지 않음\n\n[이유 범주]\n"))
        self.assertIn("개별 단위", m[1]["content"])
        self.assertEqual(set(T.REASONS), {"r1_metric", "r1_bucket", "r1_entity", "r1_forecast", "r1_mode", "r1_domain"})

    def test_good_passes(self):
        r = T.evaluate(TARGET, GOOD, "결론: 지원하지 않음")
        self.assertTrue(r["pass"], r)
        self.assertEqual(r["c2"]["removed_lines"], [])
        self.assertEqual(T.check_conclusion_line("**결론**: 지원하지 않음")["pass"], True)

    def test_f_conclusion_line(self):
        self.assertFalse(T.evaluate(TARGET, GOOD, "결론: 지원함")["pass"])
        self.assertFalse(T.evaluate(TARGET, GOOD, "지원하지 않음")["pass"])  # 결론 줄 없음
        self.assertFalse(T.evaluate(TARGET, GOOD, "결론: 지원하지 않음\n결론: 답할 수 있음")["pass"])

    def test_a_field_and_unsupported(self):
        r = T.evaluate(TARGET, GOOD + "\nunsupported", "결론: 지원하지 않음")
        self.assertIn("a", r["after"]["reasons"])
        r = T.evaluate(TARGET, GOOD.replace("기사별", "dimension_target 기사별"), "결론: 지원하지 않음")
        self.assertIn("a", r["after"]["reasons"])

    def test_c_exposure(self):
        for w in ("주어진 결론", "이유 범주", "정답", "힌트"):
            r = T.evaluate(TARGET, GOOD.replace("핵심이다", f"핵심이다({w})"), "결론: 지원하지 않음")
            self.assertIn("c", r["raw"]["reasons"], w)
            if w != "주어진 결론":  # (ii) 줄이라 c2가 그 줄을 지운다(결정 185 줄 단위)
                self.assertIn("c", r["after"]["reasons"], w)

    def test_d_korean_and_e_meta(self):
        eng = "The question asks about drivers. Drivers are not supported in the data at all, so we cannot answer this question.\n결론: 지원하지 않음"
        self.assertIn("d", T.evaluate(TARGET, eng, "결론: 지원하지 않음")["after"]["reasons"])
        r = T.evaluate(TARGET, GOOD + "\nI should write the thinking in Korean.", "결론: 지원하지 않음")
        self.assertIn("e", r["after"]["reasons"])

    def test_c2_removes_only_ii_lines(self):
        th = GOOD.replace("결론: 지원하지 않음", "받은 결론과 일치한다.\n결론: 지원하지 않음")
        self.assertIn("ii", T.evaluate(TARGET, th, "결론: 지원하지 않음")["raw"]["reasons"])
        r = T.evaluate(TARGET, th, "결론: 지원하지 않음")
        self.assertEqual(r["c2"]["removed_lines"], ["받은 결론과 일치한다."])
        self.assertTrue(r["pass"], r)
        self.assertEqual(r["thinking_after_c2"], GOOD)

    def test_record_content(self):
        c = T.to_record_content(GOOD + "\n")
        self.assertTrue(c.startswith("<think>\n질문은"))
        self.assertTrue(c.endswith("</think>\n\n{\"unsupported\": true}"))
        self.assertEqual(json.loads(c.split("</think>")[1]), {"unsupported": True})

    def test_v3b_variant_uses_existing_prompt(self):
        sem = {"nodes": [{"subtype": "revenue", "text": "수입"}], "event": "operation", "factors": {"date": "last_year", "dimension": "sido"}, "unsupported": None}
        t = {"id": "y", "variant": "v3b", "question": "작년 택시 수입을 시도별로 보여줘", "semantics": sem}
        m = T.messages(t)
        self.assertIn("[결론]\n측정: 수입", m[1]["content"])
        lines = "측정: 수입\n끝: 없음\n묶음: 시도별\n집계: 없음\n주변: 아니오"
        th = "질문은 \"작년 택시 수입을 시도별로\" 보여 달라고 한다. 측정은 수입이고 시도별로 나눈다. 집계를 뜻하는 말은 없다. 근처라는 말도 없다."
        self.assertTrue(T.evaluate(t, th, lines)["pass"])


if __name__ == "__main__":
    unittest.main()
