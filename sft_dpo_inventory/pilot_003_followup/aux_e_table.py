# -*- coding: utf-8 -*-
"""aux_test_v1 참고표(결정 87): pilot_003 aux의 HF-base·HF-최종(k=4)과 이번에 잰 E(Ollama 0.40.3 연속, k=4). 판정하지 않는다. 모델 호출 없음.

    python sft_dpo_inventory/pilot_003_followup/aux_e_table.py

- 셀 통계·비교는 ``pilot_003/vendor100/judge_v3.py``(analyze_cal 함수, U 키 연결)와 같은 계산이다. 비교마다 ``default_rng(20261109)``.
- 입력: HF 셀 ``pilot_003/aux_test/runs/aux_HF-{base,final}_s1–4.json``(원문 ``training/generated/pilot_003/raw``),
  E ``aux_e/runs/aux_E_s1–4.json``(원문 ``training/generated/pilot_003_followup/raw``).
- 결과: ``aux_e/comparison.json``. pilot_003의 ``aux_test/comparison.json``은 고치지 않는다.
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
CELLS = {"HF-base": (ROOT / "sft_dpo_inventory/pilot_003/aux_test/runs", ROOT / "training/generated/pilot_003/raw"),
         "HF-final": (ROOT / "sft_dpo_inventory/pilot_003/aux_test/runs", ROOT / "training/generated/pilot_003/raw"),
         "E": (HERE / "aux_e/runs", ROOT / "training/generated/pilot_003_followup/raw")}
PAIRS = [("HF-base", "HF-final"), ("E", "HF-base"), ("E", "HF-final")]


def main():
    cfg = dict(J.SETS["aux"])
    gold = {i["id"]: i for i in A.EV.load_gold(cfg["gold"])["items"]}
    data = {}
    for cell, (runs, raw) in CELLS.items():
        A.RAW = raw
        samples, metas = J.load_cell({**cfg, "runs": runs}, cell, gold)
        if samples is None:
            raise SystemExit(f"{cell} 표본이 없다")
        data[cell] = {"samples": samples, "meta": metas}
    common = set.intersection(*[set(s) for c in data.values() for s in c["samples"]])
    ids = [i for i in gold if i in common]
    for c in data.values():
        c["m"] = J.mats(c["samples"], ids)
        c["stats"] = J.cell_summary(c["samples"], c["m"], ids, 4)
    out = {"set": "aux_test_v1", "items": len(ids), "k": 4, "judgment": "없음(참고표, 결정 87)",
           "cells": {c: {"stats": d["stats"], "samples": d["meta"]} for c, d in data.items()},
           "comparisons": {f"{a}→{b}": J.versus(a, b, data[a]["m"], data[b]["m"], data[a]["stats"], data[b]["stats"], ids)
                           for a, b in PAIRS}}
    (HERE / "aux_e").mkdir(exist_ok=True)
    (HERE / "aux_e/comparison.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for c, d in data.items():
        s = d["stats"]
        print(f"{c:9s} mean {s['mean_pct']:6.2f} U {s['u_pct']:5.2f} silent {s['silent_pct']:5.2f} stable {s['stable_correct']} "
              f"lat {s['latency_median_s']} singles {s['per_sample_grounding_ok']} occ {s['occupied_misread_items']}")
    for k, r in out["comparisons"].items():
        print(f"{k:16s} d {r['diff_pct']} CI {r['ci95_pct']} | U {r['U_diff_pct']} CI {r['U_ci95_pct']} | silent {r['silent_diff_pct']} "
              f"CI {r['silent_ci95_pct']} | lat x{r['latency_ratio']}")


if __name__ == "__main__":
    main()
