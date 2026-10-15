# -*- coding: utf-8 -*-
"""C10: protected_final_v1 크기 근거. 최종 판정은 채택 후보 대 base 한 번(PROTOCOL_v4 6절, 우월 = 쌍 bootstrap 95% CI 하한 > 0)이므로,
같은 비교의 실제 문항 차이 분포(pilot_005 v1_step467 대 vLLM base, selection_v2 98문항, k=4; W8과 같은 셀)에서 반폭과 검정력을 투영한다.
k=8 효과는 표본 단위 분산을 문항 간·문항 안으로 나눠 반영한다. 모델 호출 없음.

    hfvenv/bin/python protected_final_power.py   # -> protected_final_power.json
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "gates"))
import compute_gates as CG  # noqa: E402

SPEC = json.loads((HERE / "gates/selftest/spec_p005.json").read_text(encoding="utf-8"))
SEL = {"selection_v2": SPEC["sets"]["selection_v2"]}


def per_sample(paths):
    """문항 × 표본 ok 행렬."""
    cols = []
    for p in paths:
        _, m, _ = CG.load_arm({"selection_v2": [p]}, SEL, with_tokens=False)
        cols.append(m["ok"])
    return np.stack(cols, axis=1)


def main():
    b = per_sample(SPEC["cells"]["base"]["selection_v2"])
    f = per_sample(SPEC["cells"]["F"]["selection_v2"])
    n, k = b.shape
    d = f.mean(1) - b.mean(1)
    # 문항 안 분산(표본 하나의 Bernoulli 분산, 두 arm 합)과 문항 간 분산
    within = (f.var(1, ddof=1) + b.var(1, ddof=1)).mean()
    total = d.var(ddof=1)
    between = max(total - within / k, 0.0)
    rng = np.random.default_rng(20261109)
    out = {"source": "pilot_005 v1_step467 대 vLLM-bf16-base, selection_v2, k=4", "observed": {"n": n, "k": k, "diff_pp": round(100 * d.mean(), 2),
           "ci95_pp": CG.cmp({"ok": b.mean(1)}, {"ok": f.mean(1)}, "ok")["ci95_pp"], "item_diff_sd": round(float(np.sqrt(total)), 4),
           "between_var": round(float(between), 5), "within_var_per_sample": round(float(within), 5)}, "projection": {}}
    for kk in (4, 8):
        for nn in (60, 80, 100, 120, 150):
            se = np.sqrt((between + within / kk) / nn)
            hw = 1.96 * se
            # 우월 판정 검정력: P(CI 하한 > 0) ≈ Φ(δ/se − 1.96)
            from math import erf, sqrt
            pw = {f"delta_{x}pp": round(0.5 * (1 + erf((x / 100 / se - 1.96) / sqrt(2))), 3) for x in (5, 8, 11)}
            out["projection"][f"k{kk}_n{nn}"] = {"half_width_pp": round(100 * hw, 2), "power_superiority": pw}
    # 확인: 관측 반폭(k=4, n=98) 재현
    out["check_k4_n98_half_width_pp"] = round(100 * 1.96 * np.sqrt((between + within / 4) / n), 2)
    (HERE / "protected_final_power.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
