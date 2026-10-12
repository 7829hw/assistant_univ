# -*- coding: utf-8 -*-
"""공식 방식 Q4 sampling 셀 분석(결정 75, 작업 3). calibration_001의 분석 방법(``analyze_cal.py``)을 그대로 쓴다. 모델 호출 없음.

    tokvenv/bin/python sft_dpo_inventory/quant_recipe/analyze_qr.py

- 셀: calibration_001의 8셀(``calibration_001/runs``) + 이번 두 셀(``quant_recipe/runs``의 B-off, F-off).
- 기준: selection_v1(100)과 selection_v2(98). 난수는 analyze_cal과 같은 seed(20261109)이고, 셀 통계 뒤 비교 순서대로 쓴다.
- 결정 74(P) 후보 규칙: 공식 방식 Q4 → Q8_0 비교에서 정답률 차이와 U 차이의 95% CI가 둘 다 0을 포함하면 "공식 방식 Q4",
  아니면 "Q8_0". 최종(F-off → e)이 운영 경로 판단의 대상이고, base(B-off → d)도 함께 적는다.
- 출력: ``analysis.json``, ``samples.jsonl``(이번 두 셀만).
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/calibration_001"))
import analyze_cal as A  # noqa: E402

CAL_RUNS = ROOT / "sft_dpo_inventory/calibration_001/runs"
CELLS = {"HF-base": CAL_RUNS, "HF-final": CAL_RUNS, "E": CAL_RUNS, "c": CAL_RUNS, "B-conv": CAL_RUNS, "d": CAL_RUNS,
         "Ollama-final": CAL_RUNS, "e": CAL_RUNS, "B-off": HERE / "runs", "F-off": HERE / "runs"}
PAIRS = [
    ("결정 74: Q4 공식 방식 대 Q8_0(최종)", "e", "F-off"),
    ("결정 74: Q4 공식 방식 대 Q8_0(base)", "d", "B-off"),
    ("HF 대비(최종)", "HF-final", "F-off"),
    ("HF 대비(base)", "HF-base", "B-off"),
    ("Q4 방식(최종)", "Ollama-final", "F-off"),
    ("Q4 방식(base)", "B-conv", "B-off"),
    ("공식 blob과 같은 배치(base)", "c", "B-off"),
    ("학습 효과(공식 방식 Q4, 같은 방식 base)", "B-off", "F-off"),
    ("학습 효과(주 비교 형태: E 대 학습 모델)", "E", "F-off"),
    ("참고: 주 비교 형태(Q8_0)", "E", "e"),
    ("참고: 주 비교 형태(자체 Q4)", "E", "Ollama-final"),
]
ROWS_SHOWN = ("HF-base", "HF-final", "E", "c", "B-conv", "d", "Ollama-final", "e", "B-off", "F-off")


def main():
    gold = {i["id"]: i for i in A.EV.load_gold(A.CS.GOLD)["items"]}
    data, metas, samples_out = {}, {}, []
    for cell, runs in CELLS.items():
        paths = [runs / f"{cell}_s{k}.json" for k in range(1, A.K + 1)]
        if not all(p.exists() for p in paths):
            raise SystemExit(f"missing {cell}")
        data[cell] = []
        for k, p in enumerate(paths, 1):
            meta, rows = A.load_sample(p, gold)
            metas.setdefault(cell, []).append({"sample": k, "model": meta.get("model"), "device": A.device(meta)})
            data[cell].append(rows)
            if runs == HERE / "runs":
                samples_out += [{"cell": cell, "sample": k, "id": key, **r} for key, r in rows.items()]
    (HERE / "samples.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in samples_out),
                                        encoding="utf-8")
    result = {"note": "calibration_001 분석 방법. 모델 호출 없음.", "meta": metas, "sets": {}}
    for set_name in ("selection_v1", "selection_v2"):
        ids = [i for i in gold if set_name == "selection_v1" or i not in A.V2_REMOVED]
        rng = np.random.default_rng(A.SEED)
        mats = {c: {f: np.array([[float(s[i][f] if f != "U" else s[i]["class"] == A.CS.U_CLASS) for s in data[c]]
                                 for i in ids]) for f in ("ok", "U") + A.ERRORS} for c in data}
        for c in data:
            mats[c]["silent"] = np.array([[float(s[i]["class"] == A.CS.SILENT) for s in data[c]] for i in ids])
        cells = {}
        for c in data:
            st = A.cell_stats(mats[c]["ok"], mats[c]["U"], rng)
            st["silent_pct"] = round(100 * float(mats[c]["silent"].mean()), 2)
            st["error_rates_pct"] = {e: round(100 * float(mats[c][e].mean()), 2) for e in A.ERRORS}
            st["latency_median_s"] = round(float(np.median([s[i]["seconds"] for s in data[c] for i in ids])), 2)
            st["truncated_item_samples"] = int(sum(s[i]["truncated"] > 0 for s in data[c] for i in ids))
            cells[c] = st
        comps = []
        for group, a, b in PAIRS:
            r = A.compare(a, b, mats[a]["ok"], mats[b]["ok"], mats[a]["U"], mats[b]["U"], rng, cells[a], cells[b])
            ds = mats[b]["silent"].mean(axis=1) - mats[a]["silent"].mean(axis=1)
            r["silent_diff_pct"] = round(100 * float(ds.mean()), 2)
            r["silent_ci95_pct"] = [round(100 * x, 2) for x in A.boot_ci(ds, rng)]
            comps.append({"group": group, **r})
        rule = {}
        for label, a, b in (("최종", "e", "F-off"), ("base", "d", "B-off")):
            r = next(x for x in comps if x["pair"] == f"{a}→{b}")
            ok_zero = r["ci95_pct"][0] <= 0 <= r["ci95_pct"][1]
            u_zero = r["U_ci95_pct"][0] <= 0 <= r["U_ci95_pct"][1]
            rule[label] = {"pair": r["pair"], "grounding_ci": r["ci95_pct"], "U_ci": r["U_ci95_pct"],
                           "grounding_ci_contains_0": ok_zero, "U_ci_contains_0": u_zero,
                           "candidate": "공식 방식 Q4" if ok_zero and u_zero else "Q8_0"}
        result["sets"][set_name] = {"items": len(ids), "cells": {c: cells[c] for c in ROWS_SHOWN},
                                    "comparisons": [{k: v for k, v in r.items() if not k.startswith("_")} for r in comps],
                                    "decision_74_rule": rule}
    (HERE / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for set_name, s in result["sets"].items():
        print("==", set_name, s["items"])
        for c, st in s["cells"].items():
            print(f"{c:13s} mean {st['mean_pct']:6.2f} U {st['u_pct']:5.2f} silent {st['silent_pct']:5.2f} singles "
                  f"{st['per_sample_grounding_ok']} U/s {st['per_sample_U']} lat {st['latency_median_s']} err {st['error_rates_pct']}")
        for r in s["comparisons"]:
            print(f"{r['group']:34s} {r['pair']:18s} d {r['diff_pct']:6.2f} CI {r['ci95_pct']} p {r['sign_flip_p']} "
                  f"noise±{r['noise95_pct']} | U {r['U_diff_pct']} CI {r['U_ci95_pct']} | silent {r['silent_diff_pct']} CI {r['silent_ci95_pct']}")
        print("rule", json.dumps(s["decision_74_rule"], ensure_ascii=False))


if __name__ == "__main__":
    main()
