# -*- coding: utf-8 -*-
"""pilot_010 판정 단계 검정력 2판(결정 253 AB7, PLAN_J_DRAFT 용, 판정 아님). 모델 호출 없음. ``power10.py``(그대로)의 ``ci``·``calibrate``·``seed_sd``를 불러 쓰고,
조건 4 판정 셋을 **주 셋 151 + 개발 셋 149(valid98 + aux) = 300문항**으로 넓힌다. CI는 **U1**(arm마다 seed 따로, 문항 공유 재추출)만(결정 253).

    hfvenv/bin/python sft_dpo_inventory/pilot_010/analysis/power10b.py   # -> analysis/power10b.json

A. pilot_009 셀(P9 − B2 F)에서 조건 4를 151문항과 300문항으로 낸 U1 CI(반폭 비교).
B. 모의(power10 B와 같은 방식): 후보 = B2 F 문항 평균 + (P8 − B2 F 문항 차 모양) + 맞춘 상수 + 새 seed 5 효과, k=4 이항. 조건 4는 151·300 두 셋, 조건 1·3은 power10과 같은 셋.
   Δ: 조건 4 {0, −2, −3}, 조건 3 {0, +1, +2}, 조건 1 {+5, +10}. σ_s는 B2 F seed sd와 max(B2 F, P8) 두 경우.
seed ``default_rng(20271033)``. 모의 ``SIMS``번, bootstrap ``BOOT``번(환경 변수 ``POWER10B_SIMS_BOOT``, 기본 400,1000).
"""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import power10 as P  # noqa: E402

SEED = 20271033
SIMS, BOOT = (int(x) for x in os.environ.get("POWER10B_SIMS_BOOT", "400,1000").split(","))


def load(arms=("P9", "B2F", "P8")):
    """pilot_009 spec → {arm: {ref, over, ok151, ok300}}."""
    import robust_scoring
    robust_scoring.patch()
    import compute_gates as CG
    import compute_p9 as C9
    import evaluate_vendor100 as EV
    spec = json.loads(P.SPEC.read_text(encoding="utf-8"))
    sets = dict(spec["sets"])
    sets["rdev"] = spec["rdev_gold"]
    expected = {st: {i["id"]: i.get("expected_outcome", "answered") for i in EV.load_gold(P.ROOT / g)["items"]} for st, g in sets.items()}
    over_sets = ("selection_v2", "holdout", "valid98", "aux", "rdev")
    M = {a: defaultdict(list) for a in arms}
    for arm in arms:
        for s in spec["seeds"]:
            cells = spec["cells"][arm][s]
            M[arm]["ref"].append(C9.matrix({"rdev": cells["rdev"]}, expected, "refusal")[1])
            M[arm]["over"].append(C9.matrix({st: cells[st] for st in over_sets}, expected, "answered")[1])
            M[arm]["ok151"].append(CG.load_arm({st: cells[st] for st in ("selection_v2", "holdout")}, sets, with_tokens=False)[1]["ok"])
            M[arm]["ok300"].append(CG.load_arm({st: cells[st] for st in ("selection_v2", "holdout", "valid98", "aux")}, sets, with_tokens=False)[1]["ok"])
    return {a: {k: np.vstack(v) for k, v in M[a].items()} for a in M}


def main():
    P.BOOT = BOOT
    rng = np.random.default_rng(SEED)
    A = load()
    X, Y, P8 = A["B2F"], A["P9"], A["P8"]
    part_a = {}
    for k in ("ok151", "ok300"):
        est, (lo, hi) = P.ci(X[k], Y[k], "U1", np.random.default_rng(SEED), boot=BOOT)
        part_a[k] = {"items": int(X[k].shape[1]), "diff_pp": round(100 * est, 2), "ci95_pp": [round(100 * lo, 2), round(100 * hi, 2)], "half_width_pp": round(50 * (hi - lo), 2)}
    rule = {"over": (lambda lo, hi: hi <= 0.03), "ok151": (lambda lo, hi: lo >= -0.05), "ok300": (lambda lo, hi: lo >= -0.05), "ref": (lambda lo, hi: lo > 0)}
    deltas = {"over": (0.0, 0.01, 0.02), "ok151": (0.0, -0.02, -0.03), "ok300": (0.0, -0.02, -0.03), "ref": (0.05, 0.10)}
    names = {"over": "3 과잉 거부(상한 ≤ +3)", "ok151": "4 정답률 151(하한 ≥ −5)", "ok300": "4 정답률 300(하한 ≥ −5)", "ref": "1 거부 개선(하한 > 0)"}
    part_b = {}
    for k in ("ok300", "ok151", "over", "ref"):
        mu = X[k].mean(0)
        dc = (P8[k].mean(0) - mu) - (P8[k].mean(0) - mu).mean()
        sb, s8 = P.seed_sd(X[k]), P.seed_sd(P8[k])
        part_b[names[k]] = {"items": int(X[k].shape[1]), "seed_sd_pp": {"B2F": round(100 * sb, 2), "P8": round(100 * s8, 2), "P9": round(100 * P.seed_sd(Y[k]), 2)},
                            "pass_prob_U1": {}}
        for tag, ss in (("seed_sd=B2F", sb), ("seed_sd=max(B2F,P8)", max(sb, s8))):
            for dlt in deltas[k]:
                c = P.calibrate(mu, dc, dlt)
                res, hw = 0, []
                for _ in range(SIMS):
                    e_s = rng.normal(0, ss, (5, 1))
                    C = rng.binomial(4, np.clip(mu[None, :] + dc[None, :] + c + e_s, 0, 1)) / 4
                    _, (lo, hi) = P.ci(X[k], C, "U1", rng, boot=BOOT)
                    res += rule[k](lo, hi)
                    hw.append(50 * (hi - lo))
                part_b[names[k]]["pass_prob_U1"][f"{tag}, Δ={round(100 * dlt)}pp"] = {"pass": round(res / SIMS, 3), "half_width_pp_median": round(float(np.median(hw)), 2)}
    out = {"spec": str(P.SPEC.relative_to(P.ROOT)), "sims": SIMS, "boot": BOOT, "seed": SEED, "method": "U1",
           "A_pilot009_cells_P9_minus_B2F_condition4": part_a, "B_power_new_seeds_vs_B2F": part_b,
           "note": "B 후보 arm = B2 F 문항 평균 + (P8 − B2 F 문항 차 모양) + 맞춘 상수 + 새 seed 5 효과, k=4 이항(참 차이 Δ 고정). 조건 2(base 대비)는 방법 무관(pilot_009 power9 C)."}
    (HERE / "power10b.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
