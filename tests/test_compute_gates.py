# -*- coding: utf-8 -*-
"""pilot_006 gate 계산(C7) 경계 사례: 합성 문항 행렬로 Gate A–E와 선행 조건 판정을 확인한다."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sft_dpo_inventory/pilot_006/gates"))
import compute_gates as CG  # noqa: E402

N = 200


def arm(ok, dt=0.0, silent=0.0, mm=0.0, struct=0.1, json_t=200.0, gen=900.0):
    z = np.zeros(N)
    return {"ok": np.full(N, ok), "U": z.copy(), "silent": np.full(N, silent), "dt_missing": np.full(N, dt), "mm_nm": np.full(N, mm),
            "struct": np.full(N, struct), "gfail": z.copy(), "repair": z.copy(), "input_tokens": np.full(N, 7300.0),
            "gen_tokens": np.full(N, gen), "thinking_tokens": np.full(N, gen - json_t), "json_tokens": np.full(N, json_t)}


def noisy(base, delta, seed):
    rng = np.random.default_rng(seed)
    return {k: (np.clip(v + rng.normal(delta if k == "ok" else 0, 0.3, N), 0, 1) if k == "ok" else v.copy()) for k, v in base.items()}


class GateTest(unittest.TestCase):
    def test_identical_arms_pass_semantic_gates_and_fail_improvement(self):
        f = arm(0.7)
        out = CG.decide({"F": f, "P": dict(f)}, {"F": 1.2, "P": 1.2})
        g = out["gates"]
        self.assertTrue(g["A"]["pass"] and g["B"]["pass"] and g["C"]["pass"])
        self.assertFalse(g["D"]["pass"])          # 개선이 확인되지 않음
        self.assertFalse(g["E"]["pass"])          # JSON 30% 감소 없음
        self.assertFalse(out["adopt"])

    def test_partial_better_structure_and_shorter_json_adopts(self):
        f = arm(0.7, struct=0.3, json_t=200)
        p = arm(0.7, struct=0.1, json_t=120, gen=850)
        out = CG.decide({"F": f, "P": p}, {"F": 1.4, "P": 1.3})
        self.assertTrue(out["gates"]["D"]["pass"])
        self.assertTrue(out["gates"]["E"]["pass"])
        self.assertTrue(out["adopt"])

    def test_margin_boundary(self):
        f = noisy(arm(0.7), 0, 1)
        worse = {**f, "ok": f["ok"] - 0.08}
        self.assertFalse(CG.decide({"F": f, "P": worse})["gates"]["A"]["pass"])
        slightly = {**f, "ok": f["ok"] - 0.02}
        self.assertTrue(CG.decide({"F": f, "P": slightly})["gates"]["A"]["pass"])

    def test_dt_missing_increase_fails_b(self):
        f, p = arm(0.7, dt=0.0), arm(0.7, dt=0.1)
        self.assertFalse(CG.decide({"F": f, "P": p})["gates"]["B"]["pass"])

    def test_latency_over_15_fails_e(self):
        f, p = arm(0.7, json_t=200), arm(0.7, json_t=100, gen=800)
        self.assertFalse(CG.decide({"F": f, "P": p}, {"F": 1.6, "P": 1.4})["gates"]["E"]["pass"])
        self.assertIsNone(CG.decide({"F": f, "P": p})["gates"]["E"]["pass"])

    def test_prerequisite_vs_base(self):
        b = arm(0.6)
        out = CG.decide({"base": b, "F": arm(0.75), "P": arm(0.6)})
        self.assertTrue(out["prerequisite"]["F"]["pass"])
        self.assertFalse(out["prerequisite"]["P"]["pass"])


if __name__ == "__main__":
    unittest.main()


class ScorerRegistrationTest(unittest.TestCase):
    def test_holdout_and_valid98_sets_resolve(self):
        A = CG.scorer()
        hold = A.C.R.C._gold("aug300", None)
        self.assertEqual(len(hold), 53)
        self.assertIn("heldout_v9", A.C.R.C.GOLD_FILES)
