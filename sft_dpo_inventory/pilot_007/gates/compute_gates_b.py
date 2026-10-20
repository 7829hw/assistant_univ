# -*- coding: utf-8 -*-
"""pilot_007 B단계 판정(결정 170·197). PLAN_B와 함께 학습 전에 고정한다. 모델 호출 없음.
pilot_006 ``gates/compute_gates.py``(고정, 고치지 않음)의 채점·지표·Gate 정의를 그대로 가져다 쓰고, CI만 **순서 seed × 문항 계층 bootstrap**으로 바꾼다.

    hfvenv/bin/python compute_gates_b.py --spec SPEC.json --out OUT.json

SPEC: {"sets": {"<셋>": "<gold yaml>"}, "base": {"<셋>": [셀, ...]},
       "seed_cells": {"o43": {"F": {"<셋>": [셀, ...]}, "P": {...}}, ...},
       "latency": {"base": "<셀>", "F": "<셀>", "P": "<셀>"}, "diagnostic_subsets": {...}, "dev": {...}(선택), "label": "..."}

- 문항 값: 셀 k표본 평균(``compute_gates.load_arm``). arm·순서 seed마다 문항 벡터(주 셋 = selection_v2 ∪ holdout 151). base는 순서 seed가 없다(셀을 이어 붙인 평균).
- **계층 bootstrap(J1)**: 반복 ``REPS`` = 10,000, 비교마다 새 ``numpy.random.default_rng(SEED = 20261109)``. 한 반복에서 순서 seed S개를 복원 추출하고 문항 n개를 복원 추출해
  통계 = 뽑힌 seed·문항 위 평균. P − F는 같은 순서 seed끼리 짝(뽑힌 seed마다 P[s] − F[s]). arm 대 base는 arm[s] − base(base는 문항만 함께 재추출).
  점 추정 = 모든 seed·문항 평균. 95% CI = 2.5·97.5 백분위.
- 판정(``compute_gates``와 같은 규칙): 선행(arm마다 대 base: ok 차 CI 하한 > 0, U 차 CI 하한 ≤ 0), A(P − F ok CI 하한 ≥ −5%p; 불통과이고 반폭 > 5%p면 판정 불가),
  B(dt_missing 하한 ≤ 0), C(silent 하한 ≤ 0), D((1) MM+NM 하한 ≤ 0 그리고 (2) struct·gfail·repair 중 하나 이상 상한 < 0), E(지연 비 ≤ 1.5(o43 모델),
  JSON token 중앙값 P ≤ 0.7·F, 생성 token 중앙값 P ≤ F — 중앙값은 다섯 seed 문항 값을 모두 모아서).
- 채택(결정 197): 선행 F·P와 A–E를 모두 통과하면 P가 채택 후보. P가 통과하지 못하고 F가 선행을 통과하면 F가 채택 후보. 그 밖은 후보 없음.
- 보조: J2(순서 seed마다 P − F ok 부호가 모두 같은지), arm별 seed sd(seed별 주 셋 ok의 표본 표준편차), 진단 부분집합(결정 140·155), 개발 셋(같은 계층 bootstrap).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))

SEED, REPS, MARGIN = 20261109, 10000, -0.05
FIELDS = ("ok", "U", "silent", "dt_missing", "mm_nm", "struct", "gfail", "repair")


def hier_ci(X, Y=None, base=None):
    """X·Y: (S, n) 배열(같은 seed 순서). Y − X(짝) 또는 X − base(base: (n,)). → (점 추정, [하한, 상한])."""
    D = (Y - X) if Y is not None else (X - base[None, :])
    S, n = D.shape
    rng = np.random.default_rng(SEED)
    stats = np.empty(REPS)
    for r in range(REPS):
        s = rng.integers(0, S, S)
        i = rng.integers(0, n, n)
        stats[r] = np.nanmean(D[s][:, i])
    return float(np.nanmean(D)), [float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))]


def fmt(est_ci):
    m, (lo, hi) = est_ci
    return {"diff_pp": round(100 * m, 2), "ci95_pp": [round(100 * lo, 2), round(100 * hi, 2)], "half_width_pp": round(50 * (hi - lo), 2)}


def decide(F, P, base, latency_ratio=None):
    """F·P: {지표: (S, n)}, base: {지표: (n,)}. → 선행·Gate A–E·채택."""
    out = {"prerequisite": {}}
    for arm, X in (("F", F), ("P", P)):
        okc, uc = fmt(hier_ci(X["ok"], base=base["ok"])), fmt(hier_ci(X["U"], base=base["U"]))
        out["prerequisite"][arm] = {"ok_vs_base": okc, "U_vs_base": uc, "pass": okc["ci95_pp"][0] > 0 and uc["ci95_pp"][0] <= 0}
    g = {}
    a = fmt(hier_ci(F["ok"], P["ok"]))
    g["A"] = {**a, "rule": "P−F ok CI 하한 ≥ −5%p", "pass": a["ci95_pp"][0] >= 100 * MARGIN, "undecidable_if_fail": a["half_width_pp"] > 5.0}
    b = fmt(hier_ci(F["dt_missing"], P["dt_missing"]))
    g["B"] = {**b, "rule": "dt_missing P−F CI 하한 ≤ 0", "pass": b["ci95_pp"][0] <= 0}
    c = fmt(hier_ci(F["silent"], P["silent"]))
    g["C"] = {**c, "rule": "조용한 오답 P−F CI 하한 ≤ 0", "pass": c["ci95_pp"][0] <= 0}
    d1 = fmt(hier_ci(F["mm_nm"], P["mm_nm"]))
    d2 = {k: fmt(hier_ci(F[k], P[k])) for k in ("struct", "gfail", "repair")}
    g["D"] = {"mm_nm": d1, "improve_any": d2, "rule": "(1) MM+NM P−F CI 하한 ≤ 0 그리고 (2) 구조·grounding failure·repair 중 하나 이상 P−F CI 상한 < 0",
              "pass": d1["ci95_pp"][0] <= 0 and any(v["ci95_pp"][1] < 0 for v in d2.values())}
    e = {"rule": "(1) P·F 지연 비 ≤ 1.5(o43 모델) (2) JSON token 중앙값 P ≤ 0.7·F (3) 생성 token 중앙값 P ≤ F(다섯 seed 문항 값 모두)"}
    jf, jp = np.nanmedian(F["json_tokens"]), np.nanmedian(P["json_tokens"])
    gf, gp = np.nanmedian(F["gen_tokens"]), np.nanmedian(P["gen_tokens"])
    e["json_tokens_median"] = {"F": float(jf), "P": float(jp), "reduction_pct": round(float(100 * (1 - jp / jf)), 2) if jf else None}
    e["gen_tokens_median"] = {"F": float(gf), "P": float(gp)}
    e["thinking_tokens_median"] = {"F": float(np.nanmedian(F["thinking_tokens"])), "P": float(np.nanmedian(P["thinking_tokens"]))}
    e["input_tokens_median"] = {"F": float(np.nanmedian(F["input_tokens"])), "P": float(np.nanmedian(P["input_tokens"]))}
    cond2, cond3 = bool(jf) and bool(jp <= 0.7 * jf), bool(gp <= gf)
    cond1 = all(v <= 1.5 for v in latency_ratio.values()) if latency_ratio else None
    e.update(latency_ratio=latency_ratio, conditions={"1_latency": cond1, "2_json_reduction": cond2, "3_gen_tokens": cond3},
             **{"pass": None if cond1 is None else (cond1 and cond2 and cond3)})
    g["E"] = e
    out["gates"] = g
    passes = [g[k]["pass"] for k in "ABCDE"]
    p_ok = out["prerequisite"]["P"]["pass"] and out["prerequisite"]["F"]["pass"] and all(x is True for x in passes)
    f_ok = out["prerequisite"]["F"]["pass"]
    out["adopt"] = {"P_all_pass": p_ok, "candidate": "P" if p_ok else ("F" if f_ok else None),
                    "rule": "선행 F·P와 A–E 모두 통과 → P; 아니고 F 선행 통과 → F; 그 밖 없음(결정 197)",
                    "gate_E_measured": passes[4] is not None}
    # 보조
    per_seed = (P["ok"] - F["ok"]).mean(axis=1)
    out["J2"] = {"per_seed_P_minus_F_pp": [round(100 * float(x), 2) for x in per_seed], "same_direction": bool(np.all(per_seed > 0) or np.all(per_seed < 0))}
    out["seed_sd_pp"] = {arm: round(100 * float(np.std(X["ok"].mean(axis=1), ddof=1)), 2) for arm, X in (("F", F), ("P", P))}
    out["arm_means_pp"] = {arm: {f: round(100 * float(np.nanmean(X[f])), 2) for f in FIELDS} for arm, X in (("F", F), ("P", P))}
    out["arm_means_pp"]["base"] = {f: round(100 * float(np.nanmean(base[f])), 2) for f in FIELDS}
    out["per_seed_means_pp"] = {arm: {f: [round(100 * float(x), 2) for x in np.nanmean(X[f], axis=1)] for f in ("ok", "U", "dt_missing")}
                                for arm, X in (("F", F), ("P", P))}
    return out


def load(spec):
    import compute_gates as CG
    sets = spec["sets"]
    items_b, mb, _ = CG.load_arm(spec["base"], sets)
    arms = {"F": [], "P": []}
    seeds = list(spec["seed_cells"])
    for s in seeds:
        for arm in ("F", "P"):
            items, m, _ = CG.load_arm(spec["seed_cells"][s][arm], sets)
            if items != items_b:
                raise SystemExit(f"{s} {arm}: cells cover different items than base")
            arms[arm].append(m)
    stack = {arm: {f: np.vstack([m[f] for m in ms]) for f in ms[0]} for arm, ms in arms.items()}
    return items_b, seeds, stack["F"], stack["P"], mb


def main():
    import compute_gates as CG
    p = argparse.ArgumentParser()
    p.add_argument("--spec", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    items, seeds, F, P, base = load(spec)
    lat = None
    if spec.get("latency"):
        lb = CG.latency(spec["latency"]["base"])
        lat = {arm: round(CG.latency(spec["latency"][arm]) / lb, 3) for arm in ("F", "P")}
    out = decide(F, P, base, lat)
    out.update(label=spec.get("label"), items=len(items), seeds=seeds, bootstrap={"reps": REPS, "seed": SEED, "kind": "순서 seed × 문항 계층(J1)"})
    if spec.get("diagnostic_subsets"):
        diag = {}
        for name, ids in spec["diagnostic_subsets"].items():
            idx = [items.index(i) for i in ids if i in items]
            if len(idx) > 1:
                diag[name] = {"n": len(idx), "F_ok": round(100 * float(F["ok"][:, idx].mean()), 2), "P_ok": round(100 * float(P["ok"][:, idx].mean()), 2),
                              "base_ok": round(100 * float(base["ok"][idx].mean()), 2), "P_minus_F_ok": fmt(hier_ci(F["ok"][:, idx], P["ok"][:, idx]))}
        out["diagnostic_subsets"] = diag
    if spec.get("dev"):
        dev = {}
        for st, cells in spec["dev"].items():
            mats = {"F": [], "P": []}
            for s in seeds:
                for arm in ("F", "P"):
                    _, m, _ = CG.load_arm({st: cells[s][arm]}, spec["sets"])
                    mats[arm].append(m["ok"])
            Fd, Pd = np.vstack(mats["F"]), np.vstack(mats["P"])
            dev[st] = {"F": round(100 * float(Fd.mean()), 2), "P": round(100 * float(Pd.mean()), 2), "P_minus_F_ok": fmt(hier_ci(Fd, Pd)),
                       "per_seed_P_minus_F_pp": [round(100 * float(x), 2) for x in (Pd - Fd).mean(axis=1)]}
        out["dev_sets"] = dev
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("prerequisite", "adopt", "J2", "seed_sd_pp")}, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
