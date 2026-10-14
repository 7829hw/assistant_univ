# -*- coding: utf-8 -*-
"""serving_vllm_fp8 분석(결정 90·91·93·94). 모델 호출 없음.

    HF_HOME=... HF_HUB_OFFLINE=1 hfvenv/bin/python sft_dpo_inventory/serving_vllm_fp8/analyze_fp8.py {logprob|cells|latency|all}

- logprob: logprob_diag 기준 응답 60개. HF base(``logprob_diag/scores/hf_base.bin``)·HF+pilot_003 최종(``serving_vllm/scores/hf_final_p3.bin``)과
  vLLM {BF16, FP8} × {base, final}(flashinfer, ``scores/*_fi_*.bin``)을 비교한다. 참고로 이전 vLLM BF16(PyTorch sampler, 자동 attention)도 같이 적는다.
  지표·함수는 ``logprob_diag/analyze_logprob.py``와 같다. → ``logprob_compare.json``
- cells: selection_v2 k=4, 동시 요청 셀 넷(vllm-{bf16,fp8}-{base,final})과 이전 순차 셀(``serving_vllm/runs``의 vllm-base·final).
  셀 통계·비교는 ``pilot_003/vendor100/judge_v3.py``와 같은 계산. 비교마다 ``default_rng(20261109)``.
  - 정밀도 효과: BF16 → FP8(base, 최종). 학습 효과: base → 최종(BF16, FP8). 학습 효과 차이(FP8 − BF16, 문항별).
  - 동시 요청 영향: 이전 순차 BF16 셀(PyTorch sampler) → 새 동시 요청 BF16 셀(flashinfer). 커널과 동시 요청이 함께 바뀐 비교다.
  - vicinity 빠짐(결정 94): gold에 vicinity가 있는 문항의 표본 중 출력에서 vicinity가 빠진 비율(grounding_diffs의 factor:vicinity True → 없음).
  → ``cell_compare.json``
- latency: 고정 30문항 1표본 순차(동시 요청 없음). 문항 모델 시간 중앙값, 호출당 생성 속도 중앙값. → ``latency.json``
"""
import json
import statistics
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/logprob_diag"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_003/vendor100"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/calibration_001"))

S = Path("/data/hwkim/sftdpo_work/serving_vllm_fp8/scores")
OLD = Path("/data/hwkim/sftdpo_work/serving_vllm/scores")


def logprob():
    import analyze_logprob as L
    paths = {"hf_base": L.WORK / "scores/hf_base.bin", "hf_final": OLD / "hf_final_p3.bin",
             "bf16_base": S / "bf16_fi_base.bin", "bf16_final": S / "bf16_fi_final.bin",
             "fp8_base": S / "fp8_fi_base.bin", "fp8_final": S / "fp8_fi_final.bin",
             "bf16_torch_base(serving_vllm)": OLD / "vllm_base.bin", "bf16_torch_final(serving_vllm)": OLD / "vllm_final.bin"}
    seqs = [json.loads(line) for line in (L.WORK / "sequences.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest = {m["index"]: m for m in json.loads((ROOT / "sft_dpo_inventory/logprob_diag/sequences_manifest.json").read_text())["sequences"]}
    scores = {p: L.read(f) for p, f in paths.items()}
    order = [s["index"] for s in seqs]
    seg, setname = {}, {}
    for s in seqs:
        pos = np.arange(s["resp_start"], len(s["ids"]))
        seg[s["index"]] = np.where(pos < s["think_end"], "thinking", "json")
        setname[s["index"]] = manifest[s["index"]]["set"]

    def cat(p, f):
        return np.concatenate([scores[p][i][f] for i in order])

    seg_all = np.concatenate([seg[i] for i in order])
    set_all = np.concatenate([np.full(len(seg[i]), setname[i]) for i in order])
    masks = {f"{g}/{sg}": (np.ones_like(seg_all, bool) if g == "all" else set_all == g) &
             (np.ones_like(seg_all, bool) if sg == "all" else seg_all == sg)
             for g in ("all", "sft", "cal") for sg in ("all", "thinking", "json")}
    out = {"note": "모델 호출 없음", "score_files": {k: str(v) for k, v in paths.items()}, "vs_hf": {}, "training_signal": {}}
    for ref, p in (("hf_base", "bf16_base"), ("hf_final", "bf16_final"), ("hf_base", "fp8_base"), ("hf_final", "fp8_final"),
                   ("hf_base", "bf16_torch_base(serving_vllm)"), ("hf_final", "bf16_torch_final(serving_vllm)"),
                   ("bf16_base", "fp8_base"), ("bf16_final", "fp8_final")):
        r = {f: cat(ref, f) for f in ("t", "top1", "ids", "lps")}
        q = {f: cat(p, f) for f in ("t", "top1", "ids", "lps")}
        kl = L.kl_approx(r, q)
        out["vs_hf"][f"{ref} → {p}"] = {k: L.stats(m, r, q, kl) for k, m in masks.items()}
    s_hf = cat("hf_final", "t") - cat("hf_base", "t")
    for label, fp, bp in (("vLLM BF16 flashinfer", "bf16_final", "bf16_base"), ("vLLM FP8 flashinfer", "fp8_final", "fp8_base"),
                          ("vLLM BF16 torch(serving_vllm)", "bf16_torch_final(serving_vllm)", "bf16_torch_base(serving_vllm)")):
        s = cat(fp, "t") - cat(bp, "t")
        res = {}
        for k, m in masks.items():
            a, b = s[m], s_hf[m]
            strong = np.abs(b) >= 1
            res[k] = {"mean_signal": round(float(a.mean()), 4), "mean_signal_hf": round(float(b.mean()), 4),
                      "retention_mean_ratio": round(float(a.mean() / b.mean()), 3) if abs(b.mean()) > 1e-9 else None,
                      "slope_on_hf": round(float(np.cov(a, b)[0, 1] / b.var(ddof=1)), 3), "corr": round(float(np.corrcoef(a, b)[0, 1]), 3),
                      "strong_tokens": int(strong.sum()),
                      "strong_retention_mean_ratio": round(float(a[strong].mean() / b[strong].mean()), 3) if strong.any() else None,
                      "strong_slope": round(float(np.cov(a[strong], b[strong])[0, 1] / b[strong].var(ddof=1)), 3) if strong.sum() > 2 else None,
                      "strong_sign_agree_pct": round(100 * float((np.sign(a[strong]) == np.sign(b[strong])).mean()), 2) if strong.any() else None}
        out["training_signal"][label] = res
    (HERE / "logprob_compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in out["vs_hf"].items():
        a = v["all/all"]
        print(f"{k:50s} |d| {a['mean_abs_dlogp']} KL {a['kl_approx']} top1 {a['top1_mismatch_pct']}")
    for k, v in out["training_signal"].items():
        a, t, c = v["all/all"], v["all/thinking"], v["cal/thinking"]
        print(f"{k:32s} ret {a['retention_mean_ratio']} slope {a['slope_on_hf']} corr {a['corr']} strong {a['strong_tokens']}/{a['strong_slope']} "
              f"| thinking ret {t['retention_mean_ratio']} corr {t['corr']} | cal-thinking strong slope {c['strong_slope']}")


def vicinity(cell_dir, label, ids, gold, k=4):
    """gold vicinity 문항의 표본 중 출력에서 vicinity가 빠진 수. 문항별 비율 행렬(문항 × 표본)도 돌려준다."""
    import evaluate_vendor100 as EV
    vic_items = [i for i in ids if ((EV.gold_grounding(gold[i]) or {}).get("factors") or {}).get("vicinity")]
    m = np.zeros((len(ids), k))
    for s in range(1, k + 1):
        rows = {r["id"]: r for r in json.loads((cell_dir / f"{label}_s{s}.json").read_text(encoding="utf-8"))["rows"]}
        for x, i in enumerate(ids):
            if i in vic_items:
                g = (rows[i].get("grounding") or {}).get("factors") or {}
                m[x, s - 1] = float(not g.get("vicinity"))
    n = len(vic_items) * k
    return {"gold_vicinity_items": len(vic_items), "missing_item_samples": int(m.sum()), "rate_pct": round(100 * m.sum() / n, 2) if n else None}, m


def cells():
    import judge_v3 as J
    A = J.A
    cfg = dict(J.SETS["selftest"])
    gold = {i["id"]: i for i in A.EV.load_gold(cfg["gold"])["items"]}
    sv = ROOT / "sft_dpo_inventory/serving_vllm/runs"
    cellmap = {"BF16-base": (HERE / "runs", "vllm-bf16-base", ROOT / "training/generated/serving_vllm_fp8/raw"),
               "BF16-final": (HERE / "runs", "vllm-bf16-final", ROOT / "training/generated/serving_vllm_fp8/raw"),
               "FP8-base": (HERE / "runs", "vllm-fp8-base", ROOT / "training/generated/serving_vllm_fp8/raw"),
               "FP8-final": (HERE / "runs", "vllm-fp8-final", ROOT / "training/generated/serving_vllm_fp8/raw"),
               "seq-BF16-base(serving_vllm)": (sv, "vllm-base", ROOT / "training/generated/serving_vllm/raw"),
               "seq-BF16-final(serving_vllm)": (sv, "vllm-final", ROOT / "training/generated/serving_vllm/raw")}
    data = {}
    for c, (runs, label, raw) in cellmap.items():
        A.RAW = raw
        samples, metas = J.load_cell({**cfg, "runs": runs, "prefix": ""}, label, gold)
        if samples is None:
            raise SystemExit(f"{c} 표본이 없다")
        data[c] = {"samples": samples, "meta": metas, "dir": runs, "label": label}
    common = set.intersection(*[set(s) for c in data.values() for s in c["samples"]])
    ids = [i for i in gold if i in common]
    for c, d in data.items():
        d["m"] = J.mats(d["samples"], ids)
        d["stats"] = J.cell_summary(d["samples"], d["m"], ids, 4)
        d["stats"]["vicinity_missing(decision 94)"], d["m"]["vic"] = vicinity(d["dir"], d["label"], ids, gold)
        d["stats"]["run_meta"] = run_meta(d["dir"], d["label"])
    out = {"set": "selection_v2", "items": len(ids), "k": 4,
           "cells": {c: {"stats": d["stats"], "samples": d["meta"]} for c, d in data.items()}, "comparisons": {}}
    pairs = [("BF16-base", "FP8-base", "정밀도 효과(base)"), ("BF16-final", "FP8-final", "정밀도 효과(최종)"),
             ("BF16-base", "BF16-final", "학습 효과(BF16)"), ("FP8-base", "FP8-final", "학습 효과(FP8)"),
             ("seq-BF16-base(serving_vllm)", "BF16-base", "동시 요청·커널 영향(base)"),
             ("seq-BF16-final(serving_vllm)", "BF16-final", "동시 요청·커널 영향(최종)")]
    for a, b, label in pairs:
        r = J.versus(a, b, data[a]["m"], data[b]["m"], data[a]["stats"], data[b]["stats"], ids)
        dv = data[b]["m"]["vic"].mean(axis=1) - data[a]["m"]["vic"].mean(axis=1)
        r["vicinity_missing_diff_pct(per item)"] = round(100 * float(dv.mean()), 2)
        r["vicinity_missing_ci95_pct"] = [round(100 * x, 2) for x in A.boot_ci(dv, np.random.default_rng(J.SEED))]
        out["comparisons"][label] = r
    eff = {}
    for key, field in (("grounding_ok", "ok"), ("U", "U"), ("silent", "silent")):
        d = ((data["FP8-final"]["m"][field].mean(axis=1) - data["FP8-base"]["m"][field].mean(axis=1))
             - (data["BF16-final"]["m"][field].mean(axis=1) - data["BF16-base"]["m"][field].mean(axis=1)))
        eff[key] = {"diff_of_effects_pct": round(100 * float(d.mean()), 2),
                    "ci95_pct": [round(100 * x, 2) for x in A.boot_ci(d, np.random.default_rng(J.SEED))]}
    out["training_effect_fp8_minus_bf16"] = eff
    (HERE / "cell_compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for c, d in data.items():
        s = d["stats"]
        print(f"{c:30s} mean {s['mean_pct']:6.2f} U {s['u_pct']:5.2f} silent {s['silent_pct']:5.2f} stable {s['stable_correct']} "
              f"cap {s['length_capped_calls']} loop {s['loop_calls']} vic {s['vicinity_missing(decision 94)']} singles {s['per_sample_grounding_ok']}")
        print("   err", s["error_rates_pct"], "meta", s["run_meta"])
    for k, r in out["comparisons"].items():
        print(f"{k:24s} d {r['diff_pct']} CI {r['ci95_pct']} | U {r['U_diff_pct']} CI {r['U_ci95_pct']} | silent {r['silent_diff_pct']} "
              f"CI {r['silent_ci95_pct']} | vic {r['vicinity_missing_diff_pct(per item)']} CI {r['vicinity_missing_ci95_pct']}")
    print("effect diff", eff)


def run_meta(cell_dir, label):
    out = []
    for s in range(1, 5):
        v = json.loads((cell_dir / f"{label}_s{s}.json").read_text(encoding="utf-8"))["meta"].get("vllm") or {}
        rl = v.get("request_log") or {}
        out.append({"concurrency": (v.get("concurrency") or {}).get("max_concurrent_requests", 1),
                    "kernels": (v.get("kernels") or {}).get("attention_backend(server log)"),
                    "requests_logged": rl.get("requests"), "sampling_param_sets": len(rl.get("sampling_params(seed masked)") or {}),
                    "wall_seconds": v.get("wall_seconds")})
    return out


def latency():
    lat = HERE / "latency"
    out = {}
    for name, kind in (("lat-vllm-bf16-base", "vllm"), ("lat-vllm-bf16-final", "vllm"), ("lat-vllm-fp8-base", "vllm"),
                       ("lat-vllm-fp8-final", "vllm"), ("lat-E", "ollama")):
        p = lat / f"{name}_s1.json"
        if not p.exists():
            out[name] = "missing"
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        rates, secs = [], []
        for r in d["rows"]:
            calls = r.get("llm_calls") or []
            for c in calls:
                n, ms = c.get("eval_count"), c.get("duration_ms")
                if kind == "ollama":
                    ms = c.get("eval_duration_ms") or ((ms or 0) - (c.get("load_duration_ms") or 0))
                if n and ms:
                    rates.append(n / (ms / 1000))
            secs.append(sum((c.get("duration_ms") or 0) for c in calls) / 1000)
        out[name] = {"items": len(d["rows"]), "calls": len(rates), "item_model_seconds_median": round(statistics.median(secs), 2),
                     "item_model_seconds_mean": round(statistics.mean(secs), 2),
                     "gen_tokens_per_s_median": round(statistics.median(rates), 1), "grounding_ok": sum(bool(r["grounding_ok"]) for r in d["rows"]),
                     "per_item_seconds": {r["id"]: round(sum((c.get("duration_ms") or 0) for c in r.get("llm_calls") or []) / 1000, 2) for r in d["rows"]}}
    pairs = {}
    for a, b in (("lat-vllm-bf16-base", "lat-vllm-fp8-base"), ("lat-vllm-bf16-final", "lat-vllm-fp8-final"),
                 ("lat-vllm-bf16-base", "lat-vllm-bf16-final"), ("lat-vllm-fp8-base", "lat-vllm-fp8-final"),
                 ("lat-E", "lat-vllm-fp8-final"), ("lat-E", "lat-vllm-bf16-final")):
        if isinstance(out.get(a), dict) and isinstance(out.get(b), dict):
            pairs[f"{a} → {b}"] = {"median_ratio": round(out[b]["item_model_seconds_median"] / out[a]["item_model_seconds_median"], 3),
                                   "tok_s_ratio": round(out[b]["gen_tokens_per_s_median"] / out[a]["gen_tokens_per_s_median"], 3)}
    # FP8이 BF16보다 빠른지(같은 문항 쌍): 문항별 생성 속도(생성 token 합 / 호출 시간 합)의 비 FP8/BF16, 문항 bootstrap 95% CI
    import analyze_cal as A  # noqa: E402  (boot_ci)

    def item_speed(name):
        d = json.loads((lat / f"{name}_s1.json").read_text(encoding="utf-8"))
        return {r["id"]: sum(c.get("eval_count") or 0 for c in r.get("llm_calls") or []) /
                max(1e-9, sum((c.get("duration_ms") or 0) for c in r.get("llm_calls") or []) / 1000) for r in d["rows"]}
    paired = {}
    for m in ("base", "final"):
        a, b = item_speed(f"lat-vllm-bf16-{m}"), item_speed(f"lat-vllm-fp8-{m}")
        ids = sorted(set(a) & set(b))
        r = np.log(np.array([b[i] / a[i] for i in ids]))
        lo, hi = A.boot_ci(r, np.random.default_rng(20261109))
        paired[f"bf16→fp8 {m}"] = {"items": len(ids), "speed_ratio_geomean": round(float(np.exp(r.mean())), 3),
                                    "ci95": [round(float(np.exp(lo)), 3), round(float(np.exp(hi)), 3)], "fp8_faster_confirmed": bool(lo > 0)}
    pairs["paired_item_speed"] = paired
    (HERE / "latency.json").write_text(json.dumps({"items": "latency_ids.txt(30)", "cells": out, "ratios": pairs}, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8")
    for k, v in out.items():
        print(k, {x: v[x] for x in ("items", "calls", "item_model_seconds_median", "gen_tokens_per_s_median", "grounding_ok")} if isinstance(v, dict) else v)
    print(json.dumps(pairs, ensure_ascii=False))


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("logprob", "all"):
        logprob()
    if what in ("cells", "all"):
        cells()
    if what in ("latency", "all"):
        latency()
