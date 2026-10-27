# -*- coding: utf-8 -*-
"""pilot_010 판정 단계 검정력(결정 244 AA4, PLAN_DRAFT 용, 판정 아님). 모델 호출 없음. 셀은 pilot_009 판정 spec(``pilot_009/gates/spec_p9.json``)을 그대로 읽는다.

    hfvenv/bin/python sft_dpo_inventory/pilot_010/analysis/power10.py   # -> analysis/power10.json

판정 단계는 새 순서 seed 5개라 B2 F(순서 seed 43·1016·7·11·2027)와 seed 짝이 없다. 세 가지 CI 방법을 비교한다(모두 반복 ``BOOT``, 2.5–97.5 백분위):
- ``paired``: 지금 방법(``compute_gates_b.hier_ci``) — seed 번호를 짝으로 seed·문항을 함께 다시 뽑는다(새 seed에서는 쓸 수 없음, 참고).
- ``U1``: 짝짓지 않은 계층 — arm마다 seed를 따로 다시 뽑고, 문항은 두 arm에 같은 번호로 다시 뽑는다(문항 짝은 유지).
- ``U2``: 짝짓지 않은 계층 — arm마다 seed와 문항을 모두 따로 다시 뽑는다(지시의 안 그대로; 문항 짝도 버림).
A. pilot_009 실제 셀에서 세 방법의 CI(P9 − B2 F, 조건 1·3·4, 그리고 base 대비 조건 2는 base가 seed 없는 한 arm이라 문항 짝만 — 방법 무관).
B. 모의(검정력, ``pilot_009/analysis/power9.py`` C와 같은 방식): 지표마다 B2 F 셀의 문항 평균 μ_i와, 후보의 문항별 차이 모양으로 P8 − B2 F 문항 차 d_i를 쓴다.
   후보 참값 p_si = clip(μ_i + d_i − mean(d) + c + e_s)(c는 e_s = 0에서 평균 차가 Δ가 되게 이분법으로 맞춤, e_s ~ N(0, σ_s)는 새 seed 5의 효과),
   관측 = Binomial(4, p_si)/4(셀의 k=4). B2 F는 실제 셀 그대로. σ_s는 B2 F seed 평균 sd와 P8 seed 평균 sd(더 큰 쪽) 두 경우.
   조건마다 참 차이 Δ에서 통과 확률: 조건 3(과잉 거부, 상한 ≤ +3) Δ ∈ {0, +1, +2}, 조건 4(정답률, 하한 ≥ −5) Δ ∈ {0, −2, −3}, 조건 1(거부 개선, 하한 > 0) Δ ∈ {+5, +10, +20}.
   조건 2(거부 비열등 대 base, −15)는 base에 seed가 없어 방법에 따라 바뀌지 않는다(pilot_009 power9 C 그대로 쓸 수 있음).
seed: ``default_rng(20271027)``. 모의 ``SIMS``번, bootstrap ``BOOT``번(환경 변수 ``POWER10_SIMS_BOOT``).
"""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
P10 = HERE.parent
ROOT = P10.parents[1]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_006/gates", ROOT / "sft_dpo_inventory/pilot_006/post", ROOT / "sft_dpo_inventory/pilot_007/gates",
          ROOT / "sft_dpo_inventory/pilot_009/gates"):
    sys.path.insert(0, str(p))
SEED = 20271027
SIMS, BOOT = (int(x) for x in os.environ.get("POWER10_SIMS_BOOT", "400,1000").split(","))
SPEC = ROOT / "sft_dpo_inventory/pilot_009/gates/spec_p9.json"


def load_p8():
    return load(("P8",))["P8"]


def load(arms=("P9", "B2F")):
    """pilot_009 spec → {arm: {지표: (S, n)}}(compute_p9와 같은 값: ref·over·ok)."""
    import robust_scoring
    robust_scoring.patch()
    import compute_gates as CG
    import compute_p9 as C9
    import evaluate_vendor100 as EV
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    sets = dict(spec["sets"])
    sets["rdev"] = spec["rdev_gold"]
    expected = {st: {i["id"]: i.get("expected_outcome", "answered") for i in EV.load_gold(ROOT / g)["items"]} for st, g in sets.items()}
    over_sets = ("selection_v2", "holdout", "valid98", "aux", "rdev")
    M = {a: defaultdict(list) for a in arms}
    for arm in M:
        for s in spec["seeds"]:
            cells = spec["cells"][arm][s]
            M[arm]["ref"].append(C9.matrix({"rdev": cells["rdev"]}, expected, "refusal")[1])
            M[arm]["over"].append(C9.matrix({st: cells[st] for st in over_sets}, expected, "answered")[1])
            M[arm]["ok"].append(CG.load_arm({st: cells[st] for st in ("selection_v2", "holdout")}, sets, with_tokens=False)[1]["ok"])
    return {a: {k: np.vstack(v) for k, v in M[a].items()} for a in M}


def ci(X, Y, method, rng, boot=BOOT):
    """Y − X 평균 차의 95% CI. X·Y: (S, n)."""
    S, n = X.shape
    if method == "paired":
        D = Y - X
        s = rng.integers(0, S, (boot, S))
        i = rng.integers(0, n, (boot, n))
        stats = np.array([D[s[b]][:, i[b]].mean() for b in range(boot)])
    else:
        ix = rng.integers(0, n, (boot, n))
        iy = ix if method == "U1" else rng.integers(0, n, (boot, n))
        cx = np.zeros((boot, n))
        cy = np.zeros((boot, n))
        np.add.at(cx, (np.arange(boot)[:, None], ix), 1.0)
        np.add.at(cy, (np.arange(boot)[:, None], iy), 1.0)
        xm = (cx @ X.T) / n  # boot × S: 문항 다시 뽑은 seed별 평균
        ym = (cy @ Y.T) / n
        sx = rng.integers(0, S, (boot, S))
        sy = rng.integers(0, S, (boot, S))
        stats = np.take_along_axis(ym, sy, 1).mean(1) - np.take_along_axis(xm, sx, 1).mean(1)
    return float((Y - X).mean() if method == "paired" else Y.mean() - X.mean()), [float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))]


def seed_sd(X):
    return float(X.mean(1).std(ddof=1))


def calibrate(mu, dc, delta):
    lo, hi = -1.0, 1.0
    for _ in range(60):
        c = (lo + hi) / 2
        m = np.clip(mu + dc + c, 0, 1).mean() - mu.mean()
        lo, hi = (c, hi) if m < delta else (lo, c)
    return (lo + hi) / 2


def main():
    rng = np.random.default_rng(SEED)
    A = load()
    X, Y = A["B2F"], A["P9"]
    part_a = {}
    for k, name in (("ref", "1 거부 개선"), ("over", "3 과잉 거부"), ("ok", "4 정답률")):
        part_a[name] = {}
        for m in ("paired", "U1", "U2"):
            est, (lo, hi) = ci(X[k], Y[k], m, np.random.default_rng(SEED))
            part_a[name][m] = {"diff_pp": round(100 * est, 2), "ci95_pp": [round(100 * lo, 2), round(100 * hi, 2)], "half_width_pp": round(50 * (hi - lo), 2)}
    rule = {"over": (lambda lo, hi: hi <= 0.03), "ok": (lambda lo, hi: lo >= -0.05), "ref": (lambda lo, hi: lo > 0)}
    deltas = {"over": (0.0, 0.01, 0.02), "ok": (0.0, -0.02, -0.03), "ref": (0.05, 0.10, 0.20)}
    part_b = {}
    P8 = load_p8()
    for k, name in (("over", "3 과잉 거부(상한 ≤ +3)"), ("ok", "4 정답률(하한 ≥ −5)"), ("ref", "1 거부 개선(하한 > 0)")):
        mu = X[k].mean(0)
        d = P8[k].mean(0) - mu
        dc = d - d.mean()
        sb, s8 = seed_sd(X[k]), seed_sd(P8[k])
        part_b[name] = {"seed_sd_pp": {"B2F": round(100 * sb, 2), "P8": round(100 * s8, 2), "P9": round(100 * seed_sd(Y[k]), 2)}, "pass_prob": {}}
        for tag, ss in (("seed_sd=B2F", sb), ("seed_sd=max(B2F,P8)", max(sb, s8))):
            for dlt in deltas[k]:
                c = calibrate(mu, dc, dlt)
                res, hw = {"U1": 0, "U2": 0}, {"U1": [], "U2": []}
                for _ in range(SIMS):
                    e_s = rng.normal(0, ss, (5, 1))
                    C = rng.binomial(4, np.clip(mu[None, :] + dc[None, :] + c + e_s, 0, 1)) / 4
                    for m in ("U1", "U2"):
                        _, (lo, hi) = ci(X[k], C, m, rng)
                        res[m] += rule[k](lo, hi)
                        hw[m].append(50 * (hi - lo))
                part_b[name]["pass_prob"][f"{tag}, Δ={round(100 * dlt)}pp"] = {m: {"pass": round(res[m] / SIMS, 3), "half_width_pp_median": round(float(np.median(hw[m])), 2)}
                                                                            for m in res}
    out = {"spec": str(SPEC.relative_to(ROOT)), "sims": SIMS, "boot": BOOT, "seed": SEED,
           "A_pilot009_cells_P9_minus_B2F": part_a, "B_power_new_seeds_vs_B2F": part_b,
           "note": "B는 후보 arm = B2 F 문항 평균 + (P8 − B2 F 문항 차 모양) + 맞춘 상수 + 새 seed 효과, k=4 이항 표본(참 차이 Δ 고정). 조건 2(base 대비)는 방법 무관(pilot_009 power9 C)."}
    (HERE / "power10.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
