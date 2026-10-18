# -*- coding: utf-8 -*-
"""B단계 예상 반폭(결정 170 O6): 같은 순서 seed끼리 짝지은 P − F를 순서 seed·문항 계층 bootstrap(J1)으로 낼 때 Gate A 95% 반폭 근사. 모델 호출 없음.

    python3 sft_dpo_inventory/pilot_007/analysis/halfwidth_b.py   # -> analysis/halfwidth_b.json (select_a.json 뒤)

모형은 세션 4 A6(``pilot_006/post/a6_power.py``)과 같다. 짝 P − F의 문항 평균 d_s(순서 seed s)에 대해
  Var(평균 d) = 2σ_b²(1 − ρ)/S + (σ_ai² + 2σ_c²/S + 2w_k/S)/n
- σ_b: A단계에서 고른 recipe의 주 셋 순서 seed sd(``select_a.json``; F만 있으므로 P도 같다고 둠).
- ρ: 같은 순서를 쓴 F·P의 seed 효과 상관. A단계는 F만이라 모른다 → ρ = 0(독립, 보수적)과 0.5를 함께 낸다.
- σ_c²(seed × 문항), σ_ai²(arm × 문항), w(표본 잡음): pilot_006 값(``a6_power.json`` pooled; pilot_007에서 σ_c는 A단계 셀로 다시 추정해 함께 적음).
- n = 151, S ∈ {3, 5}, k ∈ {4, 8}. 반폭 > 5%p면 "Gate A 판정 불가 가능성"(결정 170).
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    sel = json.loads((HERE / "select_a.json").read_text(encoding="utf-8"))
    a6 = json.loads((ROOT / "sft_dpo_inventory/pilot_006/post/a6_power.json").read_text(encoding="utf-8"))["pooled"]
    n = 151
    out = {"pilot006_components": a6, "recipes": {}}
    for r, v in sel["recipes"].items():
        sb2 = (v["main_seed_sd"] / 100) ** 2
        tab = {}
        for S in (3, 5):
            for k in (4, 8):
                wk = a6["w_k4"] * 4 / k
                item = (a6["sigma_ai2"] + 2 * a6["sigma_c2"] / S + 2 * wk / S) / n
                for rho in (0.0, 0.5):
                    tab[f"S{S}_k{k}_rho{rho}"] = round(100 * 1.96 * float(np.sqrt(2 * sb2 * (1 - rho) / S + item)), 2)
        out["recipes"][r] = {"main_seed_sd_pp": v["main_seed_sd"], "half_width_pp": tab,
                             "over_5pp_at_S3_k4_rho0": tab["S3_k4_rho0.0"] > 5, "over_5pp_at_S3_k4_rho0.5": tab["S3_k4_rho0.5"] > 5}
    out["selected"] = sel["selected"]
    (HERE / "halfwidth_b.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
