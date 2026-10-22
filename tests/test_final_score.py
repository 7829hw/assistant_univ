# -*- coding: utf-8 -*-
"""pilot_007 최종 판정 채점 규칙(결정 214): 거부 문항·과잉 거부·판정 범주. 합성 예시만(보호 셋 문항 안 씀)."""

import os
import sys
import unittest
from pathlib import Path

import numpy as np

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_007/final"))

import final_score as S  # noqa: E402


class FinalOk(unittest.TestCase):
    def test_refusal_item(self):
        self.assertTrue(S.final_ok(True, None, "unsupported", 0))
        self.assertTrue(S.final_ok(True, None, "needs_clarification", 0))
        self.assertFalse(S.final_ok(True, None, "answered", 1))
        self.assertFalse(S.final_ok(True, None, "failed", 0))
        self.assertFalse(S.final_ok(True, None, "unsupported", 1))  # 분석 tool이 실행됐으면 아님

    def test_non_refusal_item(self):
        self.assertTrue(S.final_ok(False, True, "answered", 1))
        self.assertFalse(S.final_ok(False, False, "answered", 1))
        self.assertFalse(S.final_ok(False, None, "answered", 1))
        self.assertFalse(S.final_ok(False, True, "unsupported", 0))  # 과잉 거부는 오답
        self.assertFalse(S.final_ok(False, True, "needs_clarification", 0))


class Judge(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(0)
        self.n = 120
        self.base = {"ok": rng.uniform(0.4, 0.9, self.n), "U": np.full(self.n, 0.05), "silent": np.full(self.n, 0.02)}

    def test_improve(self):
        cand = {"ok": np.clip(self.base["ok"] + 0.15, 0, 1), "U": self.base["U"].copy(), "silent": self.base["silent"].copy()}
        self.assertEqual(S.judge(self.base, cand, 0.8)["category"], "개선")

    def test_improve_blocked_by_latency(self):
        cand = {"ok": np.clip(self.base["ok"] + 0.15, 0, 1), "U": self.base["U"].copy(), "silent": self.base["silent"].copy()}
        self.assertEqual(S.judge(self.base, cand, 1.6)["category"], "악화")

    def test_worse_by_U(self):
        cand = {"ok": self.base["ok"].copy(), "U": self.base["U"] + 0.2, "silent": self.base["silent"].copy()}
        self.assertEqual(S.judge(self.base, cand, 0.8)["category"], "악화")

    def test_no_difference(self):
        rng = np.random.default_rng(1)
        cand = {"ok": np.clip(self.base["ok"] + rng.normal(0, 0.2, self.n), 0, 1), "U": self.base["U"].copy(), "silent": self.base["silent"].copy()}
        r = S.judge(self.base, cand, 0.8)
        self.assertLessEqual(r["ok"]["ci95_pp"][0], 0)
        self.assertEqual(r["category"], "차이 없음(구분 안 됨)")

    def test_ci_reproducible(self):
        cand = {"ok": np.clip(self.base["ok"] + 0.05, 0, 1), "U": self.base["U"].copy(), "silent": self.base["silent"].copy()}
        self.assertEqual(S.judge(self.base, cand, 0.8), S.judge(self.base, cand, 0.8))


if __name__ == "__main__":
    unittest.main()
