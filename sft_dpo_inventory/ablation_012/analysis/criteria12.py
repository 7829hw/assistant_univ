# -*- coding: utf-8 -*-
"""CRITERIA_v2_DRAFT 수치(결정 262 D2, 초안·확정 안 함). **고정 분석 도구 밖의 사후 계산**이다. results_a12.json(고정 도구 출력)만 읽는다. 모델 호출 없음.

    python3 sft_dpo_inventory/ablation_012/analysis/criteria12.py   # -> analysis/criteria12.json

1. 안 2 마진 다시 계산: 고정 도구 모의(400 × bootstrap 1,000)의 seed 수·참 차이별 "CI 반폭 평균 hw"와 "점 추정 sd"로, 하한 ≈ N(Δ − hw, sd) 정규 근사를 쓴다.
   마진 m에서 통과 확률 = Φ((Δ − hw + m)/sd)(상한 기준 지표는 Φ((m − Δ − hw)/sd)). 근사는 고정 도구가 실제로 모의한 마진(−3·−5·+1.5)에서의 통과 확률과 나란히 적는다.
2. 안 3 변형: V4 6 seed의 seed 단위 값(넓은 셋 정답률, 30문항 이상 그룹 붕괴 수, E1 과잉 거부·올바른 거부)에서 n seed를 복원 추출(``default_rng(20261112)``, 20,000회).
   참 차이는 넓은 셋 정답률·E1 지표에 상수로 더한다(seed 단위 근사).
"""
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "results_a12.json").read_text(encoding="utf-8"))


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def plan2():
    out = {}
    sim = R["power_sim"]
    for setname, key in (("E1", "plan2_E1"), ("H-dev", "plan2_Hdev")):
        for met, rows in sim[key].items():
            for name, v in rows.items():
                hw, sd, d = v["ci_halfwidth_pp_mean"], max(v["point_sd_pp"], 1e-6), v["true_diff_pp"]
                margins = {"acc": (2, 3, 4, 5), "ref": (5, 7, 10), "over": (1.0, 1.5, 2.0)}[met]
                approx = {}
                for m in margins:
                    approx[str(m)] = round(phi((m - d - hw) / sd) if met == "over" else phi((d - hw + m) / sd), 3)
                out[f"{setname}|{met}|{name}"] = {"set": setname, "metric": met, "seeds": v["seeds"], "true_diff_pp": d, "hw": hw, "point_sd": v["point_sd_pp"],
                                                  "sim_pass_prob_at_frozen_margin": v["pass_prob"], "approx_pass_prob_by_margin": approx}
    return out


def plan3():
    rng = np.random.default_rng(20261112)
    sim = R["power_sim"]["plan3"]
    res = {}
    for broad, key in (("CT10K", "per_seed_CT10K"), ("H-dev", "per_seed_Hdev")):
        ps = sim.get(key)
        if not ps:
            continue
        names = list(ps)
        acc = np.array([ps[n]["broad_acc_pct"] for n in names])
        c20 = np.array([ps[n]["collapsed_groups_20pp"] for n in names])
        c30 = np.array([ps[n]["collapsed_groups_30pp"] for n in names])
        over = np.array([ps[n]["e1_over_pct"] for n in names])
        ref = np.array([ps[n]["e1_ref_pct"] for n in names])
        base = R["ct10k_seed_consistency"]["base_mean_pct"] if broad == "CT10K" else R["hdev_seed_consistency"]["base_mean_pct"]
        variants = {
            "3가_seed마다(정답률≥base+5, 30pp 붕괴≤1)": lambda a, c2, c3, o, r: bool(np.all(a >= base + 5) and np.all(c3 <= 1) and o.mean() <= 3.0 and r.mean() >= 85.0),
            "3나_평균+최저seed(평균≥base+5, 최저≥base, 30pp 붕괴 seed 평균≤3)": lambda a, c2, c3, o, r: bool(a.mean() >= base + 5 and a.min() >= base and c3.mean() <= 3 and o.mean() <= 3.0 and r.mean() >= 85.0),
            "참고_엄격(seed마다 20pp 붕괴 0)": lambda a, c2, c3, o, r: bool(np.all(a >= base + 5) and np.all(c2 == 0) and o.mean() <= 3.0 and r.mean() >= 85.0)}
        res[broad] = {"base_mean_pct": base, "per_seed": ps, "variants": {}}
        for vname, f in variants.items():
            res[broad]["variants"][vname] = {"observed_6seed": f(acc, c20, c30, over, ref)}
            for n in (3, 5, 8):
                for cname, da, do, dr in (("0", 0, 0, 0), ("acc-2", -2, 0, 0), ("acc-3", -3, 0, 0), ("over+1", 0, 1, 0), ("ref-5", 0, 0, -5)):
                    ok = 0
                    for _ in range(20000):
                        j = rng.integers(0, len(names), n)
                        ok += f(acc[j] + da, c20[j], c30[j], over[j] + do, ref[j] + dr)
                    res[broad]["variants"][vname][f"n{n}_{cname}"] = round(ok / 20000, 3)
    return res


def main():
    out = {"note": "CRITERIA_v2_DRAFT용 사후 계산(초안, 확정 안 함). 진단, 판정 아님.", "plan2": plan2(), "plan3": plan3()}
    (HERE / "criteria12.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in out["plan2"].items():
        if v["seeds"] in (3, 5, 8):
            print(k, v["hw"], v["point_sd"], v["sim_pass_prob_at_frozen_margin"], v["approx_pass_prob_by_margin"])
    for b, v in out["plan3"].items():
        for vn, x in v["variants"].items():
            print(b, vn, x)


if __name__ == "__main__":
    main()
