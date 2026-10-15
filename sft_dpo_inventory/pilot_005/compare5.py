# -*- coding: utf-8 -*-
"""pilot_005 보조 비교(보고용, 선택·판정에 쓰지 않음). 모델 호출 없음.

    HF_HOME=... HF_HUB_OFFLINE=1 hfvenv/bin/python sft_dpo_inventory/pilot_005/compare5.py

같은 조건(selection_v2 98, vLLM 0.30.0 BF16, flashinfer, 동시 요청 8, k=4, 같은 seed 규칙)의 셀만 비교한다. 같은 표본으로 고른 후보라 선택 편향이 있다.
- V1 재현성(seed 차이): pilot_004 SFT step467 → V1 step467, pilot_004 SFT step934 → V1 step934.
- V2 epoch 효과: V2 step934 → V2 step1401(같은 학습 안), pilot_004 SFT 934 → V2 step934(같은 seed, 학습률 스케줄 길이만 다름).
- V3 해 감소: pilot_004 SFT 934 → V3 step97·step193, 견줄 것은 pilot_004 SFT 934 → pilot_004 DPO 385(lr 1e-5, 1 epoch).
- 비교마다 grounding_ok·U·조용한 오답 차이와 95% CI(``judge_v3.diff_ci``, 10,000회), 오류 유형별(특히 dt_missing) 차이와 95% CI.
- 실차 통행량 문항(g02·g04, n33)의 표본별 정답·오독 수, 셀마다 dt_missing·조용한 오답 문항.
- 결과: ``compare5.json``.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_003/vendor100"))
import judge_v3 as J  # noqa: E402

A = J.A
P4R, P4RAW = ROOT / "sft_dpo_inventory/pilot_004/selection/runs", ROOT / "training/generated/pilot_004/raw"
P5R, P5RAW = HERE / "runs", ROOT / "training/generated/pilot_005/raw"
CELLS = {"vLLM-base": (ROOT / "sft_dpo_inventory/serving_vllm_fp8/runs", "vllm-bf16-base", ROOT / "training/generated/serving_vllm_fp8/raw"),
         "p4_sft_step467": (P4R, "sft_step467", P4RAW), "p4_sft_step934": (P4R, "sft_step934", P4RAW), "p4_dpo_step385": (P4R, "dpo_step385", P4RAW),
         "v1_step467": (P5R, "v1_step467", P5RAW), "v1_step934": (P5R, "v1_step934", P5RAW),
         "v2_step934": (P5R, "v2_step934", P5RAW), "v2_step1401": (P5R, "v2_step1401", P5RAW),
         "v3_step97": (P5R, "v3_step97", P5RAW), "v3_step193": (P5R, "v3_step193", P5RAW)}
PAIRS = {"V1 재현성": [("p4_sft_step467", "v1_step467"), ("p4_sft_step934", "v1_step934")],
         "V2 epoch 효과": [("v2_step934", "v2_step1401"), ("p4_sft_step934", "v2_step934"), ("p4_sft_step934", "v2_step1401")],
         "V3 해 감소": [("p4_sft_step934", "v3_step97"), ("p4_sft_step934", "v3_step193"), ("p4_sft_step934", "p4_dpo_step385"),
                      ("p4_dpo_step385", "v3_step193")]}
REAL = ["old44/g02", "old44/g04", "indepv2/n33"]


def main():
    cfg = dict(J.SETS["selftest"])
    gold = {i["id"]: i for i in A.EV.load_gold(cfg["gold"])["items"]}
    data = {}
    for c, (runs, label, raw) in CELLS.items():
        A.RAW = raw
        samples, _ = J.load_cell({**cfg, "runs": runs, "prefix": ""}, label, gold)
        if samples is not None:
            data[c] = samples
    ids = [i for i in gold if all(i in s for c in data.values() for s in c)]
    m = {c: J.mats(s, ids) for c, s in data.items()}
    out = {"set": "selection_v2", "items": len(ids), "k": 4, "missing_cells": sorted(set(CELLS) - set(data)),
           "cells": {c: {"mean_pct": round(100 * float(m[c]["ok"].mean()), 2), "u_pct": round(100 * float(m[c]["U"].mean()), 2),
                         "silent_pct": round(100 * float(m[c]["silent"].mean()), 2),
                         "error_rates_pct": {e: round(100 * float(m[c][e].mean()), 2) for e in A.ERRORS}} for c in data},
           "comparisons": {}}
    for group, pairs in PAIRS.items():
        for a, b in pairs:
            if a not in m or b not in m:
                continue
            r = J.diff_ci(m[a], m[b])
            for e in A.ERRORS:
                d = m[b][e].mean(axis=1) - m[a][e].mean(axis=1)
                r[f"{e}_diff_pct"] = round(100 * float(d.mean()), 2)
                r[f"{e}_ci95_pct"] = [round(100 * x, 2) for x in A.boot_ci(d, np.random.default_rng(J.SEED))]
            out["comparisons"].setdefault(group, {})[f"{a}→{b}"] = r
    out["real_trip_items"] = {c: {i: {"ok_samples": int(sum(s[i]["ok"] for s in data[c])),
                                      "occupied_misread_samples": int(sum(s[i]["occupied_misread"] for s in data[c]))} for i in REAL}
                              for c in data}
    out["dt_missing_items"] = {c: {i: int(v) for i, v in zip(ids, m[c]["dt_missing"].sum(axis=1)) if v > 0} for c in data}
    out["silent_items"] = {c: {i: int(v) for i, v in zip(ids, m[c]["silent"].sum(axis=1)) if v > 0} for c in data}
    (HERE / "compare5.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("cells", "comparisons", "real_trip_items")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
