# -*- coding: utf-8 -*-
"""A3 recipe 선택(결정 188 Q4). PLAN_A3와 함께 학습 전에 고정한다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/analysis/select_a3.py   # -> analysis/select_a3.json

규칙·채점은 A단계 ``select_a.py``와 같다(그 파일의 ``decide``·``item_means``·``set_acc``·``reference``를 그대로 씀):
- recipe(R1' = A3_R1p, R1'' = A3_R1pp)마다 주 셋 seed sd(순서 seed 세 모델의 주 셋 정답률 표본 표준편차, ddof 1) ≤ 3.0%p,
  개발 셋 평균(valid98 + aux 149문항 평균의 세 모델 평균) ≥ 64.19(기준값 66.19 − 2).
- 둘 다 통과면 seed sd가 작은 쪽, 차 < 0.5%p면 개발 셋 평균이 높은 쪽. 하나만 통과면 그쪽. 없으면 선택 없음(B단계로 가지 않고 보고).
- 주 셋 평균은 선택에 쓰지 않는다(결정 188).
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from select_a import decide, item_means, model_rows, reference, set_acc  # noqa: E402

RECIPES = {"R1p": "R1' (lr 1e-4)", "R1pp": "R1'' (lr 2e-4)"}
ORDERS = ("o43", "o1016", "o7")


def main():
    ref, ref_models = reference()
    threshold = ref - 2.0
    res, per_model = {}, {}
    for r in RECIPES:
        mains, devs = [], []
        for o in ORDERS:
            name = f"A3_{r}_{o}"
            im = item_means(model_rows(name))
            main, nm = set_acc(im, ("sel", "holdout"))
            dev, nd = set_acc(im, ("valid98", "aux"))
            assert nm == 151 and nd == 149, (name, nm, nd)
            per_model[name] = {"main(sd 근거만)": round(main, 2), "valid98": round(set_acc(im, ("valid98",))[0], 2), "aux": round(set_acc(im, ("aux",))[0], 2),
                               "dev_mean": round(dev, 2)}
            mains.append(main)
            devs.append(dev)
        res[r] = {"label": RECIPES[r], "main_seed_sd": round(float(np.std(mains, ddof=1)), 3), "dev_mean": round(float(np.mean(devs)), 3),
                  "main_by_seed(sd 근거만)": [round(x, 2) for x in mains]}
    pick, ok, why = decide(res, threshold)
    out = {"rule": {"sd_max_pp": 3.0, "dev_threshold": round(threshold, 3), "dev_reference": round(ref, 3), "dev_reference_models": ref_models, "tie_sd_pp": 0.5,
                    "main_mean_not_used": True},
           "per_model": per_model, "recipes": res, "pass": ok, "selected": pick, "why": why,
           "caveat": "seed 3개 sd는 자유도 2인 추정이라 크게 흔들린다."}
    (HERE / "select_a3.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
