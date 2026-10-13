# -*- coding: utf-8 -*-
"""pilot_002 최종과 pilot_003 최종의 같은 조건 비교(보고용, 판정 없음). 모델 호출 없음.

    python sft_dpo_inventory/pilot_003/selection/compare_pilot002.py

- 같은 조건: selection_v2 98문항, HF BF16, sampling(PROTOCOL_v3 3절), k=4, 같은 회차 seed 20261101–04.
  pilot_002 최종(``pilot_002/checkpoints/dpo/checkpoint-144/policy``)은 calibration_001 HF-final(selection_v1으로 잼, 98문항만 씀),
  pilot_003 최종은 selection runs의 dpo_step174.
- pilot_003 최종은 같은 표본으로 골랐으므로 선택 편향이 있다(PROTOCOL_v3 7절 5). 크기 비교는 참고로만 쓴다.
- 실차 통행량 오독(occupied_misread) 문항 목록도 셀마다 적는다(HF-base, pilot_002 최종, pilot_003 SFT·최종).
- 결과: ``selection/compare_pilot002.json``.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/calibration_001"))
import analyze_cal as A  # noqa: E402

IDS = (HERE / "selection_v2_ids.txt").read_text(encoding="utf-8").strip().split(",")
SEED = 20261109
CAL = ROOT / "sft_dpo_inventory/calibration_001/runs"
CELLS = {"HF-base": (HERE / "runs", "HF-base", ROOT / "training/generated/pilot_003/raw"),
         "pilot002_final": (CAL, "HF-final", ROOT / "training/generated/calibration_001/raw"),
         "pilot003_sft": (HERE / "runs", "sft_step920", ROOT / "training/generated/pilot_003/raw"),
         "pilot003_final": (HERE / "runs", "dpo_step174", ROOT / "training/generated/pilot_003/raw")}


def main():
    gold = {i["id"]: i for i in A.EV.load_gold(A.CS.GOLD)["items"]}
    m, occ = {}, {}
    for name, (runs, label, raw) in CELLS.items():
        A.RAW = raw
        samples = [A.load_sample(runs / f"{label}_s{k}.json", gold)[1] for k in range(1, 5)]
        m[name] = {f: np.array([[float(s[i][f] if f != "U" else s[i]["class"] == A.CS.U_CLASS) for s in samples] for i in IDS])
                   for f in ("ok", "U", "occupied_misread")}
        m[name]["silent"] = np.array([[float(s[i]["class"] == A.CS.SILENT) for s in samples] for i in IDS])
        occ[name] = {i: int(v) for i, v in zip(IDS, m[name]["occupied_misread"].sum(axis=1)) if v > 0}
    out = {"set": "selection_v2(98)", "k": 4, "cells": {n: {"mean_pct": round(100 * float(x["ok"].mean()), 2),
                                                          "u_pct": round(100 * float(x["U"].mean()), 2),
                                                          "silent_pct": round(100 * float(x["silent"].mean()), 2)} for n, x in m.items()},
           "occupied_misread_items(samples of 4)": occ, "comparisons": {}}
    for a, b in (("pilot002_final", "pilot003_final"), ("HF-base", "pilot002_final"), ("HF-base", "pilot003_final")):
        r = {}
        for key, f in (("diff", "ok"), ("U_diff", "U"), ("silent_diff", "silent")):
            d = m[b][f].mean(axis=1) - m[a][f].mean(axis=1)
            r[f"{key}_pct"] = round(100 * float(d.mean()), 2)
            r[f"{key}_ci95_pct"] = [round(100 * x, 2) for x in A.boot_ci(d, np.random.default_rng(SEED))]
        out["comparisons"][f"{a}→{b}"] = r
    (HERE / "compare_pilot002.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
