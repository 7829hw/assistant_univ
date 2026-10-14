# -*- coding: utf-8 -*-
"""vLLM 셀과 HF 셀 비교(결정 89, 작업 3). 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/serving_vllm/analyze_vllm_cells.py

- 셋: selection_v2 98문항, k=4, 같은 seed 규칙(회차 20261100+k, 호출 ``EV.call_seed``).
- 셀: HF-base·HF-최종(pilot_003 ``selection/runs``의 HF-base, dpo_step174), vLLM-base·vLLM-최종(이 폴더 ``runs``).
- 셀 통계·비교는 ``pilot_003/vendor100/judge_v3.py``와 같은 계산(analyze_cal 함수, 비교마다 ``default_rng(20261109)``).
- 비교:
  - 경로 차이: HF-base → vLLM-base, HF-최종 → vLLM-최종.
  - 학습 효과: HF-base → HF-최종, vLLM-base → vLLM-최종, 그리고 둘의 차이(문항별 (vLLM 효과 − HF 효과)의 bootstrap CI).
- 원문 일치: 같은 문항·표본·호출 순번에서 첫 호출 원문 sha256이 HF와 같은 비율.
- 지연: 문항 지연 중앙값, 호출당 생성 속도(생성 token / 호출 시간), 표본 하나의 벽시계 시간(문항 수/시간).
  E(Ollama 0.40.3)는 selection_v2 기록이 없다. 업체 100은 이 작업에서 쓰지 않으므로, 작업 1에서 잰 aux_test_v1 E 셀의 같은 지표만 따로 적는다
  (호출당 생성 속도는 셋과 거의 무관하지만 문항 지연은 셋에 따라 다르다).
- 결과: ``cell_compare.json``.
"""
import json
import statistics
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_003/vendor100"))
import judge_v3 as J  # noqa: E402

A = J.A
SEL = ROOT / "sft_dpo_inventory/pilot_003/selection/runs"
CELLS = {"HF-base": (SEL, "", "HF-base", ROOT / "training/generated/pilot_003/raw"),
         "HF-final": (SEL, "", "dpo_step174", ROOT / "training/generated/pilot_003/raw"),
         "vLLM-base": (HERE / "runs", "", "vllm-base", ROOT / "training/generated/serving_vllm/raw"),
         "vLLM-final": (HERE / "runs", "", "vllm-final", ROOT / "training/generated/serving_vllm/raw")}
PAIRS = [("HF-base", "vLLM-base", "경로 차이(base)"), ("HF-final", "vLLM-final", "경로 차이(최종)"),
         ("HF-base", "HF-final", "학습 효과(HF)"), ("vLLM-base", "vLLM-final", "학습 효과(vLLM)")]
E_CELLS = {"E(aux_test_v1, 0.40.3, k=4; 지연만)": [ROOT / f"sft_dpo_inventory/pilot_003_followup/aux_e/runs/aux_E_s{k}.json" for k in range(1, 5)]}


def rows_of(path):
    return json.loads(path.read_text(encoding="utf-8"))


def speed(cell_paths, kind):
    """호출당 생성 속도(token/s)와 문항 지연, 표본 벽시계."""
    rates, item_secs, walls = [], [], []
    for p in cell_paths:
        d = rows_of(p)
        for r in d["rows"]:
            for c in r.get("llm_calls") or []:
                n = c.get("eval_count")
                ms = c.get("duration_ms")
                if kind == "ollama":
                    ev = c.get("eval_duration_ms")
                    ms = ev if ev else (ms or 0) - (c.get("load_duration_ms") or 0)
                if n and ms:
                    rates.append(n / (ms / 1000))
            item_secs.append(sum((c.get("duration_ms") or 0) for c in r.get("llm_calls") or []) / 1000)
        start = min(r["started_at"] for r in d["rows"])
        end = max(r["finished_at"] for r in d["rows"])
        from datetime import datetime
        walls.append((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())
    return {"calls": len(rates), "gen_tokens_per_s_median": round(statistics.median(rates), 1) if rates else None,
            "item_model_seconds_median": round(statistics.median(item_secs), 2) if item_secs else None,
            "sample_wall_seconds": [round(w) for w in walls], "items_per_hour": round(3600 * len(rows_of(cell_paths[0])["rows"]) / statistics.mean(walls), 1)}


def raw_match(a_label, b_label, gold_ids):
    (ra, pa, la, _), (rb, pb, lb, _) = CELLS[a_label], CELLS[b_label]
    same = total = 0
    for k in range(1, 5):
        A_ = {r["id"]: r for r in rows_of(ra / f"{pa}{la}_s{k}.json")["rows"]}
        B_ = {r["id"]: r for r in rows_of(rb / f"{pb}{lb}_s{k}.json")["rows"]}
        for i in gold_ids:
            ca, cb = A_[i].get("hf_calls") or [], B_[i].get("hf_calls") or []
            if ca and cb:
                total += 1
                same += ca[0]["raw_sha256"] == cb[0]["raw_sha256"]
    return {"first_call_pairs": total, "identical": same, "identical_pct": round(100 * same / total, 2) if total else None}


def main():
    cfg = dict(J.SETS["selftest"])
    gold = {i["id"]: i for i in A.EV.load_gold(cfg["gold"])["items"]}
    ids_v2 = (ROOT / "sft_dpo_inventory/pilot_003/selection/selection_v2_ids.txt").read_text().strip().split(",")
    data = {}
    for cell, (runs, prefix, label, raw) in CELLS.items():
        A.RAW = raw
        samples, metas = J.load_cell({**cfg, "runs": runs, "prefix": prefix}, label, gold)
        if samples is None:
            raise SystemExit(f"{cell} 표본이 없다")
        data[cell] = {"samples": samples, "meta": metas}
    common = set.intersection(*[set(s) for c in data.values() for s in c["samples"]])
    ids = [i for i in gold if i in common]
    if set(ids) != set(ids_v2):
        raise SystemExit("문항이 selection_v2 98개와 다르다")
    for c in data.values():
        c["m"] = J.mats(c["samples"], ids)
        c["stats"] = J.cell_summary(c["samples"], c["m"], ids, 4)
    out = {"set": "selection_v2", "items": len(ids), "k": 4,
           "cells": {c: {"stats": d["stats"], "samples": d["meta"]} for c, d in data.items()}, "comparisons": {}}
    for a, b, label in PAIRS:
        out["comparisons"][label] = J.versus(a, b, data[a]["m"], data[b]["m"], data[a]["stats"], data[b]["stats"], ids)
    # 학습 효과의 경로 차이: 문항별 (vLLM 최종 − vLLM base) − (HF 최종 − HF base)
    eff = {}
    for key, field in (("grounding_ok", "ok"), ("U", "U"), ("silent", "silent")):
        d = ((data["vLLM-final"]["m"][field].mean(axis=1) - data["vLLM-base"]["m"][field].mean(axis=1))
             - (data["HF-final"]["m"][field].mean(axis=1) - data["HF-base"]["m"][field].mean(axis=1)))
        eff[key] = {"diff_of_effects_pct": round(100 * float(d.mean()), 2),
                    "ci95_pct": [round(100 * x, 2) for x in A.boot_ci(d, np.random.default_rng(J.SEED))]}
    out["training_effect_vllm_minus_hf"] = eff
    out["raw_identical_first_call"] = {"HF-base vs vLLM-base": raw_match("HF-base", "vLLM-base", ids),
                                       "HF-final vs vLLM-final": raw_match("HF-final", "vLLM-final", ids)}
    lat = {}
    for cell, (runs, prefix, label, _) in CELLS.items():
        lat[cell] = speed([runs / f"{prefix}{label}_s{k}.json" for k in range(1, 5)], "hf")
    for name, paths in E_CELLS.items():
        if all(p.exists() for p in paths):
            lat[name] = speed(paths, "ollama")
    out["latency"] = lat
    (HERE / "cell_compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for c, d in data.items():
        s = d["stats"]
        print(f"{c:11s} mean {s['mean_pct']:6.2f} U {s['u_pct']:5.2f} silent {s['silent_pct']:5.2f} stable {s['stable_correct']} "
              f"lat {s['latency_median_s']} cap {s['length_capped_calls']} loop {s['loop_calls']} singles {s['per_sample_grounding_ok']} "
              f"err {s['error_rates_pct']}")
    for k, r in out["comparisons"].items():
        print(f"{k:14s} {r['pair']:22s} d {r['diff_pct']} CI {r['ci95_pct']} | U {r['U_diff_pct']} CI {r['U_ci95_pct']} | "
              f"silent {r['silent_diff_pct']} CI {r['silent_ci95_pct']} | lat x{r['latency_ratio']}")
    print("effect diff", eff)
    print("raw", out["raw_identical_first_call"])
    print("latency", json.dumps(lat, ensure_ascii=False))


if __name__ == "__main__":
    main()
