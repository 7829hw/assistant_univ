# -*- coding: utf-8 -*-
"""A6: seed 분산을 넣은 검정력 재계산과 Gate A 반폭 표. 모델 호출 없음.

    hfvenv/bin/python a6_power.py   # -> a6_power.json

모형(arm마다, 주 셋 n문항, seed s, 표본 k): 표본 정답 y_sik ~ Bernoulli(p_si), p_si = μ + a_i + b_s + c_si.
- 표본 잡음 w = 평균 p̂(1 − p̂)/(k − 1)(문항·seed별 표본 평균의 분산 추정, k = 4 → 계획 k로 4/k 배).
- seed × 문항 σ_c²: 두 seed의 문항 정답률 차 d_i의 분산 = 2(σ_c² + w) → σ_c² = var(d)/2 − w (seed 쌍마다 평균).
- seed 주효과 σ_b²: seed 평균 M_s의 분산 = σ_b² + (σ_c² + w)/n → σ_b² = var(M_s) − (σ_c² + w)/n(ddof 1; seed 2개면 자유도 1이라 매우 불안정).
- arm × 문항 σ_ai²: 두 arm의 seed 평균 문항 정답률 차의 문항 분산에서 seed·표본 몫을 뺀 값.
- P − F(문항 짝, seed는 arm마다 따로) 반폭(95%) ≈ 1.96 √(2σ_b²/S + (σ_ai² + 2σ_c²/S + 2w_k/S)/n).
- 비교: 세션 3 판정(seed 고정, 문항 bootstrap)은 σ_b² 항이 없다 — 그 반폭이 4.55였다.
seed 목록에 진단 학습(D-F7·D-P7 100%)과 E-rep(같은 모델 새 sampling seed: 표본 잡음 확인)이 있으면 함께 쓴다.
"""
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

SAMPLES = [HERE / "samples_s3.jsonl", HERE / "samples_s4.jsonl"]
ARMS = {"F": ["F43e1", "F1016e1", "D_F7q100"], "P": ["P43e1", "P1016e1", "D_P7q100"]}


def load():
    rows = []
    for p in SAMPLES:
        if p.exists():
            rows += [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]
    return [r for r in rows if r["set"] in ("sel", "holdout")]


def matrix(rows, model, items):
    g = defaultdict(list)
    for r in rows:
        if r["model"] == model:
            g[(r["set"], r["id"])].append(r["ok"])
    if not all(it in g for it in items):
        return None
    return np.array([np.mean(g[it]) for it in items]), np.array([np.var(g[it], ddof=1) / len(g[it]) if len(g[it]) > 1 else 0 for it in items]), \
        int(np.median([len(g[it]) for it in items]))


def components(rows, models, items):
    mats = {m: matrix(rows, m, items) for m in models}
    mats = {m: v for m, v in mats.items() if v is not None}
    n = len(items)
    means = {m: float(v[0].mean()) for m, v in mats.items()}
    w = float(np.mean([v[1].mean() for v in mats.values()]))
    k = int(np.median([v[2] for v in mats.values()]))
    sc = [float(np.var(mats[a][0] - mats[b][0], ddof=1)) / 2 - w for a, b in combinations(mats, 2)]
    s_c = max(0.0, float(np.mean(sc))) if sc else None
    s_b = max(0.0, float(np.var(list(means.values()), ddof=1)) - (s_c + w) / n) if len(mats) >= 2 else None
    return {"seeds": list(mats), "seed_means": {m: round(100 * x, 2) for m, x in means.items()}, "k": k, "w_per_item_mean": w,
            "sigma_c2": s_c, "sigma_b2": s_b, "sd_b_pp": round(100 * s_b ** 0.5, 2) if s_b is not None else None,
            "df_sigma_b": len(mats) - 1, "mats": mats}


def main():
    rows = load()
    items = sorted({(r["set"], r["id"]) for r in rows if r["model"] == "F43e1"})
    n = len(items)
    comp = {a: components(rows, ms, items) for a, ms in ARMS.items()}
    fbar = np.mean([v[0] for v in comp["F"]["mats"].values()], axis=0)
    pbar = np.mean([v[0] for v in comp["P"]["mats"].values()], axis=0)
    S_obs = {a: len(comp[a]["mats"]) for a in comp}
    s_b = float(np.mean([comp[a]["sigma_b2"] for a in comp]))
    s_c = float(np.mean([comp[a]["sigma_c2"] for a in comp]))
    w4 = float(np.mean([comp[a]["w_per_item_mean"] for a in comp]))
    k_obs = comp["F"]["k"]
    v_d = float(np.var(pbar - fbar, ddof=1))
    s_ai = max(0.0, v_d - sum((s_c + w4) / S_obs[a] for a in comp))
    table = {}
    for S in (2, 3, 5):
        for k in (4, 8):
            wk = w4 * k_obs / k
            hw = 1.96 * np.sqrt(2 * s_b / S + (s_ai + 2 * s_c / S + 2 * wk / S) / n)
            hw_fixed = 1.96 * np.sqrt((s_ai + 2 * s_c / S + 2 * wk / S) / n)
            table[f"S{S}_k{k}"] = {"half_width_pp": round(100 * hw, 2), "half_width_seed_fixed_pp": round(100 * hw_fixed, 2),
                                   "train_runs_total": 2 * S, "eval_samples_per_item_per_arm": S * k}
    # sd_b가 클 때 Gate A(비열등 −5%p)를 통과할 수 있는 최소 seed 수(차이 0 가정, 반폭 ≤ 5)
    need = None
    for S in range(2, 41):
        hw = 1.96 * np.sqrt(2 * s_b / S + (s_ai + 2 * s_c / S + 2 * w4 * k_obs / 8 / S) / n)
        if hw <= 0.05:
            need = S
            break
    out = {"items": n, "components": {a: {k: v for k, v in c.items() if k != "mats"} for a, c in comp.items()},
           "pooled": {"sigma_b2": s_b, "sd_b_pp": round(100 * s_b ** 0.5, 2), "sigma_c2": s_c, "sigma_ai2": s_ai, "w_k4": w4},
           "gate_A_half_width_table": table, "min_seeds_per_arm_for_half_width_le_5pp(k=8, true diff 0)": need,
           "caveat": "σ_b²는 arm마다 seed 2–3개로 추정(자유도 1–2) — 표는 크기 감각용이며 신뢰구간이 매우 넓다."}
    (HERE / "a6_power.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "components"}, ensure_ascii=False, indent=1))
    for a, c in out["components"].items():
        print(a, c["seeds"], c["seed_means"], c["sd_b_pp"], round(c["sigma_c2"], 4))


if __name__ == "__main__":
    main()
