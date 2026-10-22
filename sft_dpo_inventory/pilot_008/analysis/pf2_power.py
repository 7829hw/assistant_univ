# -*- coding: utf-8 -*-
"""protected_final_v2 크기·검정력(P6)과 pilot_008 기준 반폭(P5). 모델 호출 없음. protected_final_v1은 **집계 수치만**(결정 217의 반폭) 교차 확인에 쓴다.

    hfvenv/bin/python sft_dpo_inventory/pilot_008/analysis/pf2_power.py   # -> analysis/pf2_power.json

1. 정답률(후보 대 base 우월, 문항 쌍 bootstrap CI 하한 > 0): 문항 차이 분산 = 문항 간 성분 + 표본 성분/k. 성분은 주 셋 151에서 F-o11(B2 셀 k=4) 대 base(k=12)
   문항 차이로 추정(표본 성분은 문항별 p(1 − p)/k의 평균). 크기 n·k=8의 95% 반폭 = 1.96·sqrt(var/n), 검정력 = P(점 추정 − 반폭 > 0 | 참 차이 δ)(정규 근사).
   교차 확인: protected_final_v1 최종 판정 반폭(+10.73 [3.96, 17.40] → 6.72%p, n=120·k=8).
2. 거부율(올바른 거부 표본 비율, 후보 대 base): 거부 문항 n_r에서 같은 방법. 성분은 refusal_dev 초안 셀(J-rdev: base·F-o11 각 k=4) 거부 30문항에서 추정 — 셀이 없으면 건너뜀.
   검정력: 참 차이 δ_r(예: F-o11 수준 → base 수준으로 회복 = +30·+40%p, 작은 회복 +15%p).
3. 과잉 거부(근접 대조 문항 표본 중 거부): 같은 방법, refusal_dev 대조 30에서 추정.
4. pilot_008 정답률 비열등(같은 순서 seed 짝, 계층): B2 F 다섯의 seed sd 3.99와 B2 실제 반폭(Gate A 3.92, P − F)에서 S3·S5 반폭 투영(결정 190 모형: 2σ_s²(1 − ρ)/S + 문항 성분/n).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
P8 = HERE.parent
ROOT = P8.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/gates"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006/post"))
Z = 1.959964


def comps(A, B):
    """A·B: 문항 × 표본 0/1 행렬(같은 문항 순서). → 문항 간 분산(참 차이), 표본 성분(k=1 기준), 평균 차이."""
    pa, pb = A.mean(axis=1), B.mean(axis=1)
    d = pb - pa
    samp = (pa * (1 - pa) / A.shape[1] + pb * (1 - pb) / B.shape[1])
    between = max(float(d.var(ddof=1) - samp.mean()), 0.0)
    unit = float((pa * (1 - pa) + pb * (1 - pb)).mean())  # k=1 표본 성분(두 셀 합)
    return {"mean_diff_pp": round(100 * float(d.mean()), 2), "between_var": between, "sample_var_k1": unit, "items": int(len(d))}


def project(c, n, k, deltas):
    var = c["between_var"] + c["sample_var_k1"] / k
    hw = Z * math.sqrt(var / n)
    se = math.sqrt(var / n)
    power = {f"{d:+d}pp": round(0.5 * (1 + math.erf(((d / 100) - Z * se) / se / math.sqrt(2))), 3) for d in deltas}
    return {"n": n, "k": k, "half_width_pp": round(100 * hw, 2), "power_superiority": power}


def ok_matrix(cells, sets):
    import compute_gates as CG
    items, m, _ = CG.load_arm(cells, sets, with_tokens=False)
    return items, m["ok"]


def main():
    import robust_scoring
    robust_scoring.patch()
    out = {}
    C7, P6P = "sft_dpo_inventory/pilot_007/cells/", "sft_dpo_inventory/pilot_006_prep/cells/"
    ks = lambda p, k=4: [f"{p}_s{i}.json" for i in range(1, k + 1)]  # noqa: E731
    sets = {"selection_v2": "sft_dpo_inventory/conversion_diag/selection_gold.yaml", "holdout": "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml"}
    import compute_gates as CG

    def mat(cells):
        A = CG.scorer()
        import evaluate_vendor100 as EV
        rows = []
        for st, paths in cells.items():
            gold = {i["id"]: i for i in EV.load_gold(ROOT / sets[st])["items"]}
            per = {}
            for p in paths:
                p = ROOT / p
                A.RAW = Path((json.loads(p.read_text(encoding="utf-8"))["meta"].get("hf") or {}).get("raw_out") or ".").parent
                _, sc = A.load_sample(p, gold)
                for i, r in sc.items():
                    per.setdefault(f"{st}:{i}", []).append(float(r["ok"]))
            rows += sorted(per.items())
        return [r[0] for r in rows], [r[1] for r in rows]

    ib, base = mat({"selection_v2": ks(P6P + "b1_sel_base") + ks(P6P + "x2_sel_base_17408") + ks(C7 + "b_base3_sel"),
                    "holdout": ks(P6P + "b2_holdout_base") + ks(C7 + "b_base3_holdout")})
    io, o11 = mat({"selection_v2": ks(C7 + "b2_f_o11_sel"), "holdout": ks(C7 + "b2_f_o11_holdout")})
    assert ib == io
    # base k가 문항마다 12·8로 달라 표본 성분은 문항별로 계산
    pa = np.array([np.mean(x) for x in base])
    pb = np.array([np.mean(x) for x in o11])
    d = pb - pa
    samp = np.array([pa[i] * (1 - pa[i]) / len(base[i]) + pb[i] * (1 - pb[i]) / len(o11[i]) for i in range(len(d))])
    c = {"mean_diff_pp": round(100 * float(d.mean()), 2), "between_var": max(float(d.var(ddof=1) - samp.mean()), 0.0),
         "sample_var_k1": float((pa * (1 - pa) + pb * (1 - pb)).mean()), "items": int(len(d)), "source": "주 셋 151, F-o11(B2 k=4) 대 base(k=12/8)"}
    out["accuracy_components"] = c
    out["accuracy_projection"] = [project(c, n, 8, (5, 8, 11)) for n in (100, 120, 150, 160)]
    v1_hw = (17.40 - 3.96) / 2
    var_v1 = (v1_hw / 100 / Z) ** 2 * 120
    out["v1_crosscheck"] = {"v1_half_width_pp(n120,k8)": round(v1_hw, 2), "implied_item_var": round(var_v1, 4),
                            "projection_with_v1_var": {n: round(100 * Z * math.sqrt(var_v1 / n), 2) for n in (100, 120, 150, 160)},
                            "note": "v1 집계 반폭에서 역산한 문항 분산(v1 문항 값은 쓰지 않음)"}
    # 거부·과잉 거부: refusal_dev 초안 셀
    cdir = P8 / "cells"
    if all((cdir / f"rdev_{m}_s{k}.json").exists() for m in ("base", "o11") for k in range(1, 5)):
        meta = json.loads((P8 / "refusal_dev/rdev_items_meta.json").read_text(encoding="utf-8"))
        R, C = {}, {}
        for m in ("base", "o11"):
            per = {}
            for k in range(1, 5):
                for r in json.loads((cdir / f"rdev_{m}_s{k}.json").read_text(encoding="utf-8"))["rows"]:
                    refused = r.get("outcome") in ("unsupported", "needs_clarification")
                    analysis = sum(1 for x in (r.get("calls") or []) if x.get("tool") != "get_place_scope")
                    per.setdefault(r["id"], []).append(float(refused and analysis == 0) if meta[r["id"]]["refusal"] else float(refused))
            R[m] = np.array([per[i] for i in sorted(per) if meta[i]["refusal"]])
            C[m] = np.array([per[i] for i in sorted(per) if not meta[i]["refusal"]])
        cr, cc = comps(R["base"], R["o11"]), comps(C["base"], C["o11"])
        cr["source"] = "refusal_dev 초안 거부 30, F-o11 − base 올바른 거부(k=4)"
        cc["source"] = "refusal_dev 초안 대조 30, F-o11 − base 과잉 거부(k=4)"
        out["refusal_components"], out["over_refusal_components"] = cr, cc
        out["refusal_projection"] = [project(cr, n, 8, (15, 30, 40)) for n in (10, 20, 30)]
        out["over_refusal_projection"] = [project(cc, n, 8, (5, 10)) for n in (20, 30, 40)]
        out["refusal_dev_k4_half_width_pp"] = {"refusal(n30)": project(cr, 30, 4, (15, 30))["half_width_pp"],
                                               "over_refusal(n30)": project(cc, 30, 4, (5, 10))["half_width_pp"]}
    # pilot_008 비열등 반폭(같은 순서 seed 짝)
    item_comp = ((3.92 / 100 / Z) ** 2 - 2 * (0.0399 ** 2) * (1 - 0.5) / 5) * 151  # B2 실제 반폭에서 seed 성분을 뺀 문항 성분(ρ 0.5 가정)
    item_comp = max(item_comp, 0.0)
    out["noninferiority_half_width_pp"] = {f"S{S}, rho {rho}": round(100 * Z * math.sqrt(2 * 0.0399 ** 2 * (1 - rho) / S + item_comp / 151), 2)
                                          for S in (3, 5) for rho in (0.0, 0.5)}
    out["noninferiority_check_S5_rho0.5_reproduces_B2"] = round(100 * Z * math.sqrt(2 * 0.0399 ** 2 * 0.5 / 5 + item_comp / 151), 2)
    out["noninferiority_note"] = "결정 190 모형, σ_s = B2 F seed sd 3.99, 문항 성분은 B2 Gate A 반폭 3.92(S5)에서 ρ 0.5 가정으로 역산"
    (HERE / "pf2_power.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
