# -*- coding: utf-8 -*-
"""pilot_004 선택 결과의 보조 비교(보고용, 판정·선택에 쓰지 않음). 모델 호출 없음.

    HF_HOME=... HF_HUB_OFFLINE=1 hfvenv/bin/python sft_dpo_inventory/pilot_004/selection/compare_pilot003.py

- 같은 조건(selection_v2 98, vLLM 0.30.0 BF16, flashinfer, 동시 요청 8, k=4, 같은 seed 규칙)의 셀만 비교한다:
  vLLM-base와 pilot_003 최종(pilot_prep_007 ``serving_vllm_fp8/runs/vllm-bf16-{base,final}``), pilot_004 SFT 934·DPO 385(``selection/runs``).
- 비교: pilot_003 최종 → pilot_004 최종(DPO 385), pilot_003 최종 → pilot_004 SFT 934, DPO 효과(SFT 934 → DPO 385).
  같은 표본으로 고른 checkpoint라 선택 편향이 있다(PROTOCOL_v3 7절 5).
- 실차 통행량: 오독 문항(old44/g02, old44/g04, indepv2/n33)의 표본별 정답·오독 수. dt_missing 문항 목록과 표본 수.
- 결과: ``selection/compare_pilot003.json``.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_003/vendor100"))
import judge_v3 as J  # noqa: E402

A = J.A
FP = ROOT / "sft_dpo_inventory/serving_vllm_fp8/runs"
CELLS = {"vLLM-base": (FP, "vllm-bf16-base", ROOT / "training/generated/serving_vllm_fp8/raw"),
         "pilot003-final": (FP, "vllm-bf16-final", ROOT / "training/generated/serving_vllm_fp8/raw"),
         "pilot004-sft934": (HERE / "runs", "sft_step934", ROOT / "training/generated/pilot_004/raw"),
         "pilot004-final(dpo385)": (HERE / "runs", "dpo_step385", ROOT / "training/generated/pilot_004/raw")}
REAL = ["old44/g02", "old44/g04", "indepv2/n33"]


def main():
    cfg = dict(J.SETS["selftest"])
    gold = {i["id"]: i for i in A.EV.load_gold(cfg["gold"])["items"]}
    data = {}
    for c, (runs, label, raw) in CELLS.items():
        A.RAW = raw
        samples, _ = J.load_cell({**cfg, "runs": runs, "prefix": ""}, label, gold)
        data[c] = samples
    ids = [i for i in gold if all(i in s for c in data.values() for s in c)]
    m = {c: J.mats(s, ids) for c, s in data.items()}
    st = {c: J.cell_summary(data[c], m[c], ids, 4) for c in data}
    out = {"set": "selection_v2", "items": len(ids), "k": 4,
           "cells": {c: {k: st[c][k] for k in ("mean_pct", "u_pct", "silent_pct", "stable_correct", "error_rates_pct", "per_sample_grounding_ok")}
                     for c in data}, "comparisons": {}}
    for a, b in (("pilot003-final", "pilot004-final(dpo385)"), ("pilot003-final", "pilot004-sft934"),
                 ("pilot004-sft934", "pilot004-final(dpo385)"), ("vLLM-base", "pilot004-sft934")):
        r = J.diff_ci(m[a], m[b])
        out["comparisons"][f"{a}→{b}"] = r
    out["real_trip_items"] = {c: {i: {"ok_samples": int(sum(s[i]["ok"] for s in data[c])),
                                      "occupied_misread_samples": int(sum(s[i]["occupied_misread"] for s in data[c]))} for i in REAL}
                              for c in data}
    out["dt_missing_items"] = {c: {i: int(v) for i, v in zip(ids, m[c]["dt_missing"].sum(axis=1)) if v > 0} for c in data}
    out["silent_items"] = {c: {i: int(v) for i, v in zip(ids, m[c]["silent"].sum(axis=1)) if v > 0} for c in data}
    (HERE / "compare_pilot003.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("cells", "comparisons", "real_trip_items")}, ensure_ascii=False, indent=1))
    print("dt_missing", json.dumps(out["dt_missing_items"], ensure_ascii=False))


if __name__ == "__main__":
    main()
