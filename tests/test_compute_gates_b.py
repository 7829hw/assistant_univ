# -*- coding: utf-8 -*-
"""pilot_007 B단계 판정 도구(결정 197): 계층 bootstrap과 판정 규칙(합성 데이터)."""

import os
import sys
import unittest
from pathlib import Path

import numpy as np

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sft_dpo_inventory/pilot_007/gates"))

import compute_gates_b as G  # noqa: E402

FIELDS = ("ok", "U", "silent", "dt_missing", "mm_nm", "struct", "gfail", "repair", "input_tokens", "gen_tokens", "thinking_tokens", "json_tokens")


def arm(rng, S, n, ok, seed_sd=0.0, **over):
    shift = rng.normal(0, seed_sd, size=(S, 1))
    m = {f: np.zeros((S, n)) for f in FIELDS}
    m["ok"] = np.clip(ok + shift + rng.normal(0, 0.05, size=(S, n)), 0, 1)
    m["gen_tokens"] = np.full((S, n), 600.0)
    m["json_tokens"] = np.full((S, n), 120.0)
    m["input_tokens"] = np.full((S, n), 7000.0)
    m["thinking_tokens"] = np.full((S, n), 480.0)
    for k, v in over.items():
        m[k] = np.full((S, n), v)
    return m


class Hier(unittest.TestCase):
    def test_seed_variance_widens_ci(self):
        rng = np.random.default_rng(1)
        n, S = 151, 5
        base = rng.uniform(0.5, 0.9, n)
        F0 = np.tile(base, (S, 1))
        P_flat = F0 + 0.0
        P_seedy = F0 + rng.normal(0, 0.05, size=(S, 1))
        _, (lo1, hi1) = G.hier_ci(F0, P_flat + rng.normal(0, 0.1, size=(S, n)))
        _, (lo2, hi2) = G.hier_ci(F0, P_seedy + rng.normal(0, 0.1, size=(S, n)))
        self.assertGreater(hi2 - lo2, hi1 - lo1)

    def test_point_estimate_and_pairing(self):
        X = np.zeros((3, 4))
        Y = np.array([[0.1] * 4, [0.2] * 4, [0.3] * 4])
        m, (lo, hi) = G.hier_ci(X, Y)
        self.assertAlmostEqual(m, 0.2)
        self.assertGreaterEqual(lo, 0.1 - 1e-12)
        self.assertLessEqual(hi, 0.3 + 1e-12)

    def test_vs_base(self):
        X = np.full((5, 10), 0.8)
        b = np.full(10, 0.7)
        m, (lo, hi) = G.hier_ci(X, base=b)
        self.assertAlmostEqual(m, 0.1)
        self.assertAlmostEqual(lo, 0.1)
        self.assertAlmostEqual(hi, 0.1)

    def test_reproducible(self):
        rng = np.random.default_rng(3)
        X, Y = rng.random((5, 30)), rng.random((5, 30))
        self.assertEqual(G.hier_ci(X, Y), G.hier_ci(X, Y))


class Decide(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(7)
        self.n, self.S = 151, 5
        self.base = {f: np.zeros(self.n) for f in FIELDS}
        self.base["ok"] = np.full(self.n, 0.70)

    def test_p_candidate_when_all_pass(self):
        F = arm(self.rng, self.S, self.n, 0.80)
        P = arm(self.rng, self.S, self.n, 0.80, json_tokens=60.0, gen_tokens=550.0, struct=0.0)
        F["struct"] = np.full((self.S, self.n), 0.05)
        out = G.decide(F, P, self.base, {"F": 0.9, "P": 0.8})
        self.assertTrue(out["prerequisite"]["F"]["pass"] and out["prerequisite"]["P"]["pass"])
        self.assertTrue(out["gates"]["A"]["pass"])
        self.assertTrue(out["gates"]["D"]["pass"])
        self.assertTrue(out["gates"]["E"]["pass"])
        self.assertEqual(out["adopt"]["candidate"], "P")

    def test_f_candidate_when_p_fails_gate(self):
        F = arm(self.rng, self.S, self.n, 0.80)
        P = arm(self.rng, self.S, self.n, 0.70)
        out = G.decide(F, P, self.base, {"F": 0.9, "P": 0.8})
        self.assertFalse(out["gates"]["A"]["pass"])
        self.assertEqual(out["adopt"]["candidate"], "F")

    def test_no_candidate(self):
        F = arm(self.rng, self.S, self.n, 0.70)
        P = arm(self.rng, self.S, self.n, 0.60)
        out = G.decide(F, P, self.base, None)
        self.assertIsNone(out["adopt"]["candidate"])
        self.assertIsNone(out["gates"]["E"]["pass"])

    def test_j2_and_seed_sd(self):
        F = arm(self.rng, self.S, self.n, 0.75)
        P = arm(self.rng, self.S, self.n, 0.85)
        out = G.decide(F, P, self.base, None)
        self.assertTrue(out["J2"]["same_direction"])
        self.assertEqual(len(out["J2"]["per_seed_P_minus_F_pp"]), 5)
        self.assertIn("F", out["seed_sd_pp"])


if __name__ == "__main__":
    unittest.main()
