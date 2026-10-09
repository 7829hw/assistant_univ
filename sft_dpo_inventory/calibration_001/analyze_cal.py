# -*- coding: utf-8 -*-
"""calibration_001 분석(PLAN.md 8–9절). 모델 호출 없음.

    python sft_dpo_inventory/calibration_001/analyze_cal.py

- 입력: ``runs/<셀>_s<k>.json``(k = 1..4)과 원문 ``training/generated/calibration_001/raw/<셀>_s<k>_raw.jsonl``(루프 판정만).
- 출력: ``samples.jsonl``(표본별 기록), ``analysis.json``(selection_v1·selection_v2 두 기준). 질문 문장은 넣지 않는다.
- 없는 셀은 건너뛰고 ``missing``으로 적는다.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/conversion_diag"))
import compare_selection as CS  # noqa: E402  (EV, C, decision_d, aggregation_added, is_loop 등)

EV, C = CS.EV, CS.C
RAW = ROOT / "training/generated/calibration_001/raw"
CELLS = ["HF-base", "HF-final", "E", "c", "B-conv", "d", "Ollama-final", "e"]
K = 4
SEED = 20261109
PAIRS = [("HF와 Ollama", "HF-base", "c"), ("HF와 Ollama", "HF-base", "d"), ("HF와 Ollama", "HF-final", "e"),
         ("TEMPLATE", "E", "c"), ("변환", "c", "B-conv"),
         ("양자화", "B-conv", "d"), ("양자화", "Ollama-final", "e"),
         ("학습 효과", "HF-base", "HF-final"), ("학습 효과", "B-conv", "Ollama-final"), ("학습 효과", "d", "e")]
V2_REMOVED = set(json.loads((HERE / "selection_v2_items.json").read_text(encoding="utf-8"))["removed"])
ERRORS = ("aggregation_added", "dt_missing", "role_error", "role_notation", "occupied_misread")


def loops(path):
    out = Counter()
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        thinking = r["thinking"] if "thinking" in r else CS.split_think(r["raw_text"])[0]
        m = CS.loop_metrics(thinking) if thinking else None
        if (CS.is_loop(m) if m else ["empty_thinking"]):
            out[r["id"]] += 1
    return out


def load_sample(path, gold):
    meta, axes = EV.axes_rows(str(path))
    source = {r["id"]: r for r in json.loads(path.read_text(encoding="utf-8"))["rows"]}
    loop = loops(RAW / f"{path.stem}_raw.jsonl")
    out = {}
    for row in axes:
        key, src = row["id"], source[row["id"]]
        flags = C.R.unacceptable(key, row, src)
        ok, diffs = EV.grounding_check(gold[key], src.get("grounding"))
        calls = src.get("llm_calls") or []
        out[key] = {"ok": bool(ok), "class": C.report_class(row, flags), "u_flags": flags,
                    "outcome": f"{src.get('outcome')}:{src.get('error_code')}",
                    "seconds": round((row["cost"]["total_ms"] or 0) / 1000, 2),
                    "truncated": sum(c.get("done_reason") == "length" for c in calls),
                    "loop_calls": None if loop is None else loop.get(key, 0), "calls": len(calls),
                    "aggregation_added": CS.aggregation_added(diffs), **CS.decision_d(gold[key], src.get("grounding"))}
    return meta, out


def boot_ci(d, rng, reps=10000):
    idx = rng.integers(0, len(d), size=(reps, len(d)))
    means = d[idx].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def sign_flip_p(d, rng, reps=10000):
    signs = rng.choice([-1.0, 1.0], size=(reps, len(d)))
    null = (signs * d).mean(axis=1)
    return float((np.sum(np.abs(null) >= abs(d.mean()) - 1e-12) + 1) / (reps + 1))


def unbiased_var(m):   # m: items × K (0/1) → 문항 안 분산 v_i
    p = m.mean(axis=1)
    return p * (1 - p) * K / (K - 1)


def cell_stats(ok, u, rng):
    n = ok.shape[0]
    p, pu = ok.mean(axis=1), u.mean(axis=1)
    v, vu = unbiased_var(ok), unbiased_var(u)
    halves = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]
    split = [float(100 * (ok[:, list(a)].mean(axis=1) - ok[:, list(b)].mean(axis=1)).mean()) for a, b in halves]
    dist = []
    for a, b in halves:
        diff = ok[:, list(a)].mean(axis=1) - ok[:, list(b)].mean(axis=1)
        idx = rng.integers(0, n, size=(2000, n))
        dist.extend((100 * diff[idx].mean(axis=1)).tolist())
    singles = ok.sum(axis=0)
    pairs = [(i, j) for i in range(K) for j in range(i + 1, K)]
    return {
        "items": n, "mean_pct": round(100 * float(p.mean()), 2), "u_pct": round(100 * float(pu.mean()), 2),
        "per_sample_grounding_ok": singles.tolist(), "per_sample_U": u.sum(axis=0).tolist(),
        "stable_correct": int((p == 1).sum()), "stable_wrong": int((p == 0).sum()), "boundary": int(((p > 0) & (p < 1)).sum()),
        "within_item_var_mean": float(v.mean()), "within_item_var_mean_U": float(vu.mean()),
        "sd_pct": {str(k): round(100 * float(np.sqrt(v.sum() / k) / n), 2) for k in (1, 2, 4, 8)},
        "sd_pct_U": {str(k): round(100 * float(np.sqrt(vu.sum() / k) / n), 2) for k in (1, 2, 4, 8)},
        "half_split_diff_pct": [round(x, 2) for x in split],
        "half_split_noise": {"sd_pct": round(float(np.std(dist)), 2),
                             "p2.5": round(float(np.percentile(dist, 2.5)), 2), "p97.5": round(float(np.percentile(dist, 97.5)), 2),
                             "expected_sd_pct_k2_diff": round(100 * float(np.sqrt(2 * v.sum() / 2) / n), 2)},
        "single_pairs": [{"pair": f"s{i + 1}-s{j + 1}", "diff": int(singles[j] - singles[i]),
                          "flipped_items": int((ok[:, i] != ok[:, j]).sum())} for i, j in pairs]}


def compare(A, B, okA, okB, uA, uB, rng, statsA, statsB):
    d = okB.mean(axis=1) - okA.mean(axis=1)
    du = uB.mean(axis=1) - uA.mean(axis=1)
    noise = 1.96 * np.sqrt((statsA["sd_pct"]["4"]) ** 2 + (statsB["sd_pct"]["4"]) ** 2)
    noise_u = 1.96 * np.sqrt((statsA["sd_pct_U"]["4"]) ** 2 + (statsB["sd_pct_U"]["4"]) ** 2)
    ci, ciu = boot_ci(d, rng), boot_ci(du, rng)
    return {"pair": f"{A}→{B}", "diff_pct": round(100 * float(d.mean()), 2),
            "ci95_pct": [round(100 * x, 2) for x in ci], "sign_flip_p": round(sign_flip_p(d, rng), 4),
            "noise95_pct": round(float(noise), 2),
            "U_diff_pct": round(100 * float(du.mean()), 2), "U_ci95_pct": [round(100 * x, 2) for x in ciu],
            "U_sign_flip_p": round(sign_flip_p(du, rng), 4), "U_noise95_pct": round(float(noise_u), 2),
            "ci_excludes_0": bool(ci[0] > 0 or ci[1] < 0), "U_ci_excludes_0": bool(ciu[0] > 0 or ciu[1] < 0),
            "items_systematic": {"B_better(≥0.75)": int((d >= 0.75).sum()), "A_better(≥0.75)": int((d <= -0.75).sum())},
            "_d": d, "_du": du, "_vA": unbiased_var(okA), "_vB": unbiased_var(okB),
            "_vuA": unbiased_var(uA), "_vuB": unbiased_var(uB)}


def power(rows, n_values=(100, 98), k_values=(1, 4, 8)):
    """MDD(양측 0.05, 검정력 0.8) = 2.80·sqrt([σ²_δ + (v̄A+v̄B)/k]/N). σ²_δ = var(d_i) − (v̄A+v̄B)/4(≥ 0)."""
    out = {}
    for key, vkeys in (("grounding_ok", ("_d", "_vA", "_vB")), ("U", ("_du", "_vuA", "_vuB"))):
        per = {}
        for r in rows:
            d, va, vb = (r[x] for x in vkeys)
            within = float(va.mean() + vb.mean())
            sigma = max(float(d.var(ddof=1)) - within / K, 0.0)
            per[r["pair"]] = {"sigma2_delta": round(sigma, 4), "within_sum": round(within, 4),
                              "mdd_pct": {f"N{n}_k{k}": round(100 * 2.80 * float(np.sqrt((sigma + within / k) / n)), 1)
                                          for n in n_values for k in k_values}}
        sig = float(np.mean([p["sigma2_delta"] for p in per.values()]))
        wit = float(np.mean([p["within_sum"] for p in per.values()]))
        per["모든 쌍 평균"] = {"sigma2_delta": round(sig, 4), "within_sum": round(wit, 4),
                            "mdd_pct": {f"N{n}_k{k}": round(100 * 2.80 * float(np.sqrt((sig + wit / k) / n)), 1)
                                        for n in n_values for k in k_values}}
        out[key] = per
    return out


def greedy_values():
    comp = json.loads((ROOT / "sft_dpo_inventory/conversion_diag/selection_comparison.json").read_text(encoding="utf-8"))
    out = {}
    for cell in CELLS:
        items = comp["items"].get(cell)
        if items:
            out[cell] = {"v1": sum(i["grounding_ok"] for i in items.values()),
                         "v2": sum(i["grounding_ok"] for k, i in items.items() if k not in V2_REMOVED)}
    return out


def main():
    gold = {i["id"]: i for i in EV.load_gold(CS.GOLD)["items"]}
    data, metas, missing = {}, {}, []
    samples_out = []
    for cell in CELLS:
        paths = [HERE / "runs" / f"{cell}_s{k}.json" for k in range(1, K + 1)]
        if not all(p.exists() for p in paths):
            missing.append(cell)
            continue
        data[cell] = []
        for k, p in enumerate(paths, 1):
            meta, rows = load_sample(p, gold)
            metas.setdefault(cell, []).append({"sample": k, "model": meta.get("model"),
                                               "sampling": (meta.get("pipeline") or {}).get("sampling")
                                               or ((meta.get("hf") or {}).get("decoding")),
                                               "raw_out_sha256": meta.get("raw_out_sha256") or (meta.get("hf") or {}).get("raw_out_sha256")})
            data[cell].append(rows)
            for key, r in rows.items():
                samples_out.append({"cell": cell, "sample": k, "id": key, **r})
    (HERE / "samples.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in samples_out), encoding="utf-8")
    greedy = greedy_values()
    result = {"note": "PLAN.md 9절. 모델 호출 없음.", "missing_cells": missing, "meta": metas, "sets": {}}
    for set_name in ("selection_v1", "selection_v2"):
        ids = [i for i in gold if set_name == "selection_v1" or i not in V2_REMOVED]
        rng = np.random.default_rng(SEED)
        mats = {c: {f: np.array([[float(s[i][f] if f != "U" else s[i]["class"] == CS.U_CLASS) for s in data[c]] for i in ids])
                    for f in ("ok", "U") + ERRORS}
                for c in data}
        for c in data:
            mats[c]["silent"] = np.array([[float(s[i]["class"] == CS.SILENT) for s in data[c]] for i in ids])
            mats[c]["truncated"] = np.array([[float(s[i]["truncated"] > 0) for s in data[c]] for i in ids])
            mats[c]["loop_calls"] = np.array([[float((s[i]["loop_calls"] or 0) > 0) for s in data[c]] for i in ids])
        cells = {}
        for c in data:
            st = cell_stats(mats[c]["ok"], mats[c]["U"], rng)
            st["silent_pct"] = round(100 * float(mats[c]["silent"].mean()), 2)
            st["error_rates_pct"] = {e: round(100 * float(mats[c][e].mean()), 2) for e in ERRORS}
            st["truncated_item_samples"] = int(mats[c]["truncated"].sum())
            st["loop_item_samples"] = int(mats[c]["loop_calls"].sum()) if all(
                s[i]["loop_calls"] is not None for s in data[c] for i in ids) else None
            st["latency_median_s"] = round(float(np.median([s[i]["seconds"] for s in data[c] for i in ids])), 2)
            g = greedy.get(c, {}).get("v1" if set_name == "selection_v1" else "v2")
            if g is not None:
                n = len(ids)
                sd1 = st["sd_pct"]["1"] * n / 100
                mu = st["mean_pct"] * n / 100
                st["greedy"] = {"value": g, "sampling_single_range": [min(st["per_sample_grounding_ok"]), max(st["per_sample_grounding_ok"])],
                                "in_range": min(st["per_sample_grounding_ok"]) <= g <= max(st["per_sample_grounding_ok"]),
                                "z": round((g - mu) / sd1, 2) if sd1 else None}
            cells[c] = st
        comps = []
        for group, a, b in PAIRS:
            if a in data and b in data:
                comps.append({"group": group, **compare(a, b, mats[a]["ok"], mats[b]["ok"], mats[a]["U"], mats[b]["U"],
                                                        rng, cells[a], cells[b])})
        pw = power(comps) if comps else None
        result["sets"][set_name] = {"items": len(ids), "cells": cells,
                                    "comparisons": [{k: v for k, v in r.items() if not k.startswith("_")} for r in comps],
                                    "power": pw}
    (HERE / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for set_name, s in result["sets"].items():
        print("==", set_name, s["items"])
        for c, st in s["cells"].items():
            print(f"{c:13s} mean {st['mean_pct']:6.2f} U {st['u_pct']:5.2f} singles {st['per_sample_grounding_ok']} "
                  f"sd1 {st['sd_pct']['1']} sd4 {st['sd_pct']['4']} half {st['half_split_noise']} greedy {st.get('greedy')}")
        for r in s["comparisons"]:
            print(f"{r['group']:8s} {r['pair']:20s} d {r['diff_pct']:6.2f} CI {r['ci95_pct']} noise±{r['noise95_pct']} "
                  f"| U {r['U_diff_pct']} CI {r['U_ci95_pct']}")
    print("missing", missing)


if __name__ == "__main__":
    main()
