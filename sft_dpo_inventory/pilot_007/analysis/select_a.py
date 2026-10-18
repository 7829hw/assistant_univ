# -*- coding: utf-8 -*-
"""A단계 recipe 선택(결정 167 O3). PLAN_A와 함께 학습 전에 고정한다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/analysis/select_a.py   # -> pilot_007/analysis/select_a.json

채점: pilot_006과 같은 채점기(``pilot_006/post/itemdata.cell_rows`` = ``gates/compute_gates`` + 견고성 패치). 셀은 ``pilot_007/cells/<label>_s<k>.json``.
- 문항 정답률 = k=4 표본 평균. 셋 정답률 = 문항 정답률의 평균.
- 주 셋 = selection_v2(98) + holdout(53) = 151문항. **recipe 주 셋 seed sd** = 순서 seed 세 모델의 주 셋 정답률 표본 표준편차(ddof 1, %p).
- **개발 셋 평균** = valid98(98) + aux(51) 149문항의 문항 정답률 평균(= 문항 수 가중). recipe 값 = 순서 seed 세 모델 평균.
- 기준값 = pilot_006 F의 같은 값을 s43(F-s43 e1)·s7(D-F7 100%) 두 모델 평균(``pilot_006/post/samples_s3·s4.jsonl``, 세션 4 채점 그대로) = 66.19. 통과 문턱 = 기준값 − 2%p.
- 통과 = seed sd ≤ 3.0 그리고 개발 셋 평균 ≥ 문턱. 둘 다 통과면 seed sd가 작은 쪽, 두 sd 차 < 0.5면 개발 셋 평균이 높은 쪽. 하나만 통과면 그쪽. 둘 다 불통과면 선택 없음(B단계로 가지 않음).
- **주 셋 평균은 선택에 쓰지 않는다**(B단계 판정 셋). 보고에는 seed별 주 셋 값을 sd 계산 근거로만 적는다.
- 한계: seed 3개로 낸 sd는 그 자체가 크게 흔들린다(자유도 2). 참고로 sd의 bootstrap 범위(문항 재표집, seed 고정)를 함께 적는다 — 선택에는 쓰지 않음.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
P6POST = ROOT / "sft_dpo_inventory/pilot_006/post"
sys.path.insert(0, str(P6POST))
CELLS = "sft_dpo_inventory/pilot_007/cells/"
RECIPES = ("R1", "R2")
ORDERS = ("o43", "o1016", "o7")
SD_MAX, DEV_MARGIN, TIE_SD = 3.0, 2.0, 0.5


def item_means(rows):
    g = defaultdict(list)
    for r in rows:
        g[(r["set"], r["id"])].append(r["ok"])
    return {k: float(np.mean(v)) for k, v in g.items()}


def set_acc(im, sets):
    v = [x for (s, _), x in im.items() if s in sets]
    return 100 * float(np.mean(v)), len(v)


def reference():
    rows = []
    for f in ("samples_s3.jsonl", "samples_s4.jsonl"):
        rows += [json.loads(l) for l in (P6POST / f).read_text(encoding="utf-8").splitlines()]
    vals = {}
    for m in ("F43e1", "D_F7q100"):
        im = item_means([r for r in rows if r["model"] == m and r["set"] in ("valid98", "aux")])
        vals[m] = set_acc(im, ("valid98", "aux"))
    assert all(n == 149 for _, n in vals.values()), vals
    return float(np.mean([v for v, _ in vals.values()])), {m: round(v, 3) for m, (v, _) in vals.items()}


def model_rows(name):
    import itemdata as I
    rows = []
    for st in ("sel", "holdout", "valid98", "aux"):
        rows += I.cell_rows(f"{CELLS}{name.lower()}_{st}", st, name, 4, with_tokens=False)
    return rows


def decide(res, threshold):
    ok = {r: res[r]["main_seed_sd"] <= SD_MAX and res[r]["dev_mean"] >= threshold for r in res}
    passing = [r for r in res if ok[r]]
    if not passing:
        return None, ok, "두 recipe 모두 불통과 → 선택 없음(B단계로 가지 않고 보고)"
    if len(passing) == 1:
        return passing[0], ok, f"{passing[0]}만 통과"
    a, b = sorted(passing, key=lambda r: res[r]["main_seed_sd"])
    if res[b]["main_seed_sd"] - res[a]["main_seed_sd"] < TIE_SD:
        pick = max(passing, key=lambda r: res[r]["dev_mean"])
        return pick, ok, f"둘 다 통과, seed sd 차 {res[b]['main_seed_sd'] - res[a]['main_seed_sd']:.2f} < {TIE_SD} → 개발 셋 평균이 높은 {pick}"
    return a, ok, f"둘 다 통과, seed sd가 작은 {a}"


def main():
    ref, ref_models = reference()
    threshold = ref - DEV_MARGIN
    res, per_model = {}, {}
    rng = np.random.default_rng(20261109)
    for r in RECIPES:
        mains, devs, ims = [], [], []
        for o in ORDERS:
            name = f"A_{r}_{o}"
            im = item_means(model_rows(name))
            main, nm = set_acc(im, ("sel", "holdout"))
            dev, nd = set_acc(im, ("valid98", "aux"))
            assert nm == 151 and nd == 149, (name, nm, nd)
            per_model[name] = {"main": round(main, 2), "valid98": round(set_acc(im, ("valid98",))[0], 2), "aux": round(set_acc(im, ("aux",))[0], 2), "dev_mean": round(dev, 2)}
            mains.append(main)
            devs.append(dev)
            ims.append(np.array([im[k] for k in sorted(k for k in im if k[0] in ("sel", "holdout"))]))
        sd = float(np.std(mains, ddof=1))
        mat = np.vstack(ims)
        boots = []
        for _ in range(2000):
            idx = rng.integers(0, mat.shape[1], mat.shape[1])
            boots.append(float(np.std(100 * mat[:, idx].mean(axis=1), ddof=1)))
        res[r] = {"main_seed_sd": round(sd, 3), "dev_mean": round(float(np.mean(devs)), 3), "main_by_seed(sd 근거만)": [round(x, 2) for x in mains],
                  "sd_item_bootstrap_95(참고, 선택에 안 씀)": [round(float(np.percentile(boots, 2.5)), 2), round(float(np.percentile(boots, 97.5)), 2)]}
    pick, ok, why = decide(res, threshold)
    out = {"rule": {"sd_max_pp": SD_MAX, "dev_threshold": round(threshold, 3), "dev_reference(pilot_006 F s43·s7 mean)": round(ref, 3), "dev_reference_models": ref_models,
                    "tie_sd_pp": TIE_SD, "main_mean_not_used": True},
           "per_model": per_model, "recipes": res, "pass": ok, "selected": pick, "why": why,
           "caveat": "seed 3개 sd는 자유도 2인 추정이라 크게 흔들린다(참고 bootstrap 범위는 문항 재표집만 반영, seed 표집 불확실성은 반영하지 않음)."}
    (HERE / "select_a.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
