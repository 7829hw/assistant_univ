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


class SeedBundleTest(unittest.TestCase):
    """결정 154: seed 묶음. 합성(파일 없이 gates를 바꿔 끼움)과 pilot_005 셀을 가짜 seed 쌍으로."""

    def test_merge_and_sensitivity_synthetic(self):
        calls = []

        def fake_gates(spec):
            calls.append(spec)
            f_files = spec["cells"]["F"]["sel"]
            passed = "a1" in f_files and "b1" in f_files or f_files == ["a1"]
            return {"prerequisite": {"F": {"pass": True}, "P": {"pass": True}},
                    "gates": {g: {"pass": (passed if g == "A" else True)} for g in "ABCDE"}}
        orig = CG.gates
        CG.gates = fake_gates
        try:
            out = CG.seeded({"sets": {"sel": "x"}, "cells": {"base": {"sel": ["base1"]}}, "latency": {"base": "l", "F": "lf", "P": "lp"},
                             "seed_cells": {"s43": {"F": {"sel": ["a1"]}, "P": {"sel": ["p1"]}}, "s1016": {"F": {"sel": ["b1"]}, "P": {"sel": ["q1"]}}}})
        finally:
            CG.gates = orig
        self.assertEqual(calls[0]["cells"]["F"]["sel"], ["a1", "b1"])          # 주 판정: 두 seed 이어 붙임
        self.assertIn("latency", calls[1])                                       # s43에만 지연
        self.assertNotIn("latency", calls[2])
        self.assertEqual(out["seed_sensitive"], {"gate:A": {"s43": True, "s1016": False}})

    def test_pilot005_fake_seed_pair_reproduces(self):
        import json
        base = json.loads((CG.HERE / "selftest/spec_p005.json").read_text(encoding="utf-8"))
        runs = "sft_dpo_inventory/pilot_005/runs/"
        cell = lambda name: {"selection_v2": [f"{runs}{name}_s{k}.json" for k in (1, 2, 3, 4)]}  # noqa: E731
        spec = {"sets": base["sets"], "cells": {"base": base["cells"]["base"]},
                "seed_cells": {"s43": {"F": cell("v1_step467"), "P": cell("v2_step934")}, "s1016": {"F": cell("v1_step934"), "P": cell("v2_step1401")}}}
        out = CG.seeded(spec)
        plain = CG.gates({"sets": base["sets"], "cells": {"base": base["cells"]["base"], "F": cell("v1_step467"), "P": cell("v2_step934")}})
        self.assertEqual(out["per_seed"]["s43"]["gates"]["A"]["ci95_pp"], plain["gates"]["A"]["ci95_pp"])   # seed별 = 기존 계산
        self.assertEqual(out["per_seed"]["s43"]["prerequisite"]["F"]["ok_vs_base"]["diff_pp"], 11.22)        # pilot_005 v1 대 base 재현
        f43, f16 = out["per_seed"]["s43"]["cells"]["F"]["ok"], out["per_seed"]["s1016"]["cells"]["F"]["ok"]
        self.assertAlmostEqual(out["cells"]["F"]["ok"], (f43 + f16) / 2, delta=0.02)                        # 8표본 평균
        self.assertEqual(out["seed_mode"]["samples_per_item"]["F"]["selection_v2"], 8)
