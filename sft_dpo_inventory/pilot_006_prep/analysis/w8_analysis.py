# -*- coding: utf-8 -*-
"""W8 분석(CPU만, 모델 호출 없음). **추정이지 판정이 아니다.**

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/analysis/w8_analysis.py

1. power.json — 검정력.
   - pilot_005 selection_v2(98문항, k=4) 후보 7개(v1 467·934, v2 934·1401, v3 97·193, pilot_004 SFT 934)의 문항별 정답률(표본 4개 평균)로
     후보 쌍 21개의 정답률 차이 95% CI(문항 단위 쌍 bootstrap 10,000회, ``default_rng(20261109)``, PROTOCOL_v4 계산) 반폭을 다시 낸다.
   - 151문항(selection_v2 98 + augmentation_holdout_v1 53)의 예상 반폭: **가정** = holdout 문항의 문항별 차이 분산이 selection_v2와 같다.
     해석적 근사(1.96·SD/√n)와, SFT 후보 쌍의 문항별 차이를 151개 복원 추출한 bootstrap 두 가지.
   - Gate A(P − F 95% CI 하한 ≥ −5%p) 통과 확률: 진짜 차이 δ = 0, −1, −2%p. 모의실험 1,000회: SFT 후보 쌍 하나를 고르고 그 쌍의 문항별 차이를
     평균 0으로 옮긴 뒤 δ를 더해 n개 복원 추출, bootstrap 2,000회 2.5% 분위수 ≥ −0.05면 통과. n = 151과 98. **가정**: F와 P의 문항별 차이 분포가
     같은 recipe의 SFT 후보끼리의 차이 분포와 같다(표현이 다르므로 실제 분산은 더 클 수 있다).
2. latency.json — 지연.
   - pilot_005 ``latency/lat-base_s1.json``, ``lat-final_s1.json``(고정 30문항, 순차) 원문을 로컬 Qwen3-8B tokenizer로 thinking과 최종 JSON으로 나눈다.
   - 같은 30문항의 gold를 canonical로 바꿔 Full·Partial로 렌더링(``json.dumps``, ensure_ascii False)해 최종 JSON token 차이(Δ)를 잰다.
   - 추정 1: 문항마다 고른 후보의 모델 시간에서 Δ / (그 문항의 생성 속도)를 빼 중앙값 비를 다시 낸다(thinking은 그대로라고 가정).
   - 추정 2: 고른 후보의 실제 최종 JSON을 Partial로 바꿀 때의 감소 비율을 그 문항의 실제 최종 JSON token에 곱해 뺀다(모델 출력 형식이 gold보다 길다).
     비 1.5가 되려면 문항당 몇 token이 줄어야 하는지(중앙값 기준, 생성 속도 47.5 tok/s 근사)도 적는다. Partial prompt가 1,459 token 길어지는 prefill 비용은 따로 적는다.
3. thinking.json — thinking 길이.
   - pilot_004 데이터 판(``thinking_pilot004_t2pc`` SFT 467)의 출처별(teacher ``full_response`` / 8b 자체 ``json_only``) thinking token 분포.
   - selection_v2 셀의 thinking token(호출마다): vLLM-base(pilot_prep_007), 후보 7개. p50·p90.
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))

P5 = ROOT / "sft_dpo_inventory/pilot_005"
CANDS = {"v1_step467": P5 / "runs/v1_step467_s{}.json", "v1_step934": P5 / "runs/v1_step934_s{}.json",
         "v2_step934": P5 / "runs/v2_step934_s{}.json", "v2_step1401": P5 / "runs/v2_step1401_s{}.json",
         "v3_step97": P5 / "runs/v3_step97_s{}.json", "v3_step193": P5 / "runs/v3_step193_s{}.json",
         "p4_sft_step934": ROOT / "sft_dpo_inventory/pilot_004/selection/runs/sft_step934_s{}.json"}
BASE = ROOT / "sft_dpo_inventory/serving_vllm_fp8/runs/vllm-bf16-base_s{}.json"
RAWS = {"base": ROOT / "training/generated/serving_vllm_fp8/raw/vllm-bf16-base_s{}_raw.jsonl",
        **{k: ROOT / f"training/generated/pilot_005/raw/{k}_s{{}}_raw.jsonl" for k in CANDS if not k.startswith("p4")},
        "p4_sft_step934": ROOT / "training/generated/pilot_004/raw/sft_step934_s{}_raw.jsonl"}
SFT_ONLY = ("v1_step467", "v1_step934", "v2_step934", "v2_step1401", "p4_sft_step934")


def per_item(pattern):
    vals = defaultdict(list)
    order = None
    for k in (1, 2, 3, 4):
        d = json.loads(Path(str(pattern).format(k)).read_text(encoding="utf-8"))
        order = order or [r["id"] for r in d["rows"]]
        for r in d["rows"]:
            vals[r["id"]].append(bool(r["grounding_ok"]))
    return order, np.array([np.mean(vals[i]) for i in order])


def boot_ci(diff, rng, draws=10000, q=(2.5, 97.5)):
    idx = rng.integers(0, len(diff), size=(draws, len(diff)))
    means = diff[idx].mean(axis=1)
    return np.percentile(means, q)


def power():
    order, base = per_item(BASE)
    acc = {}
    for name, pat in CANDS.items():
        o, v = per_item(pat)
        assert o == order, name
        acc[name] = v
    pairs, names = [], list(CANDS)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            d = acc[names[i]] - acc[names[j]]
            lo, hi = boot_ci(d, np.random.default_rng(20261109))
            pairs.append({"a": names[i], "b": names[j], "diff_pp": round(100 * d.mean(), 2), "ci95_pp": [round(100 * lo, 2), round(100 * hi, 2)],
                          "half_width_pp": round(100 * (hi - lo) / 2, 2), "item_diff_sd": round(float(d.std(ddof=1)), 4)})
    sft_pairs = [p for p in pairs if p["a"] in SFT_ONLY and p["b"] in SFT_ONLY]
    sds = [p["item_diff_sd"] for p in sft_pairs]
    proj = {}
    rng = np.random.default_rng(20261109)
    for n in (98, 151):
        analytic = [1.96 * sd / np.sqrt(n) * 100 for sd in sds]
        hw = []
        for p in sft_pairs:
            d = acc[p["a"]] - acc[p["b"]]
            sample = d[rng.integers(0, len(d), size=n)]
            lo, hi = boot_ci(sample, rng, draws=4000)
            hw.append(100 * (hi - lo) / 2)
        proj[n] = {"analytic_half_width_pp": [round(min(analytic), 2), round(statistics.median(analytic), 2), round(max(analytic), 2)],
                   "bootstrap_half_width_pp(one resample per pair)": [round(min(hw), 2), round(statistics.median(hw), 2), round(max(hw), 2)]}
    sims = {}
    diffs = [acc[p["a"]] - acc[p["b"]] for p in sft_pairs]
    for n in (98, 151):
        for delta in (0.0, -0.01, -0.02):
            rng = np.random.default_rng(20261015)
            passes = 0
            runs = 1000
            for _ in range(runs):
                d = diffs[rng.integers(0, len(diffs))]
                d = d - d.mean() + delta
                sample = d[rng.integers(0, len(d), size=n)]
                idx = rng.integers(0, n, size=(2000, n))
                lo = np.percentile(sample[idx].mean(axis=1), 2.5)
                passes += lo >= -0.05
            sims[f"n{n}_delta{int(delta * 100)}pp"] = round(passes / runs, 3)
    return {"selection_v2_items": len(order), "k": 4, "pairs": pairs,
            "sft_only_pairs_half_width_pp": {"min": min(p["half_width_pp"] for p in sft_pairs), "max": max(p["half_width_pp"] for p in sft_pairs),
                                             "median": statistics.median(p["half_width_pp"] for p in sft_pairs)},
            "all_pairs_half_width_pp": {"min": min(p["half_width_pp"] for p in pairs), "max": max(p["half_width_pp"] for p in pairs)},
            "projection": proj, "gate_a_pass_probability(margin -5pp)": sims,
            "assumptions": ["holdout 53문항의 문항별 차이 분산 = selection_v2(지시 W8 1)",
                            "F−P의 문항별 차이 분포 = 같은 recipe SFT 후보끼리의 차이 분포(표현 차이로 더 클 수 있음)",
                            "모의실험: 쌍 하나의 문항 차이를 평균 0으로 옮기고 δ를 더해 복원 추출(문항 값의 [−1,1] 경계는 무시)"],
            "method": "paired item bootstrap 95% percentile CI, 10,000 draws, default_rng(20261109) (PROTOCOL_v4); 모의실험 1,000회 × bootstrap 2,000"}


def _split(tok, raw):
    from training.data.thinking import split_response
    if "</think>" in raw:
        thinking, answer = split_response(raw)
    else:
        thinking, answer = raw, ""
    return len(tok(thinking, add_special_tokens=False)["input_ids"]), len(tok(answer, add_special_tokens=False)["input_ids"])


def latency(tok):
    import evaluate_vendor100 as EV
    from grounding.canonical import semantics_from_full
    from grounding.full_renderer import render_full
    from grounding.partial_renderer import render_partial
    out, per = {}, {}
    for label in ("base", "final"):
        d = json.loads((P5 / f"latency/lat-{label}_s1.json").read_text(encoding="utf-8"))
        raws = defaultdict(list)
        for line in (ROOT / f"training/generated/pilot_005/raw/lat-{label}_s1_raw.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            raws[r["id"]].append(r["raw_text"])
        rows = []
        for r in d["rows"]:
            th = js = 0
            for raw in raws[r["id"]]:
                a, b = _split(tok, raw)
                th, js = th + a, js + b
            secs = sum(c["server_seconds"] for c in r["hf_calls"])
            gen = sum(c["generated_tokens"] for c in r["hf_calls"])
            rows.append({"id": r["id"], "model_seconds": secs, "generated_tokens": gen, "calls": len(r["hf_calls"]),
                         "thinking_tokens": th, "final_json_tokens": js, "tok_per_s": gen / secs if secs else None})
        per[label] = {r["id"]: r for r in rows}
        out[label] = {"items": len(rows), "median_model_seconds": statistics.median(r["model_seconds"] for r in rows),
                      "median_generated_tokens": statistics.median(r["generated_tokens"] for r in rows),
                      "median_thinking_tokens": statistics.median(r["thinking_tokens"] for r in rows),
                      "median_final_json_tokens": statistics.median(r["final_json_tokens"] for r in rows),
                      "p90_thinking_tokens": float(np.percentile([r["thinking_tokens"] for r in rows], 90)),
                      "median_tok_per_s": statistics.median(r["tok_per_s"] for r in rows)}
    ratio = out["final"]["median_model_seconds"] / out["base"]["median_model_seconds"]
    gold = {i["id"]: i for i in EV.load_gold(ROOT / "sft_dpo_inventory/conversion_diag/selection_gold.yaml")["items"]}
    deltas = {}
    for i in per["final"]:
        payload = EV.gold_grounding(gold[i])
        if payload is None:
            deltas[i] = None
            continue
        sem = semantics_from_full(payload)
        f = len(tok(json.dumps(render_full(sem), ensure_ascii=False), add_special_tokens=False)["input_ids"])
        p = len(tok(json.dumps(render_partial(sem), ensure_ascii=False), add_special_tokens=False)["input_ids"])
        deltas[i] = {"full": f, "partial": p, "delta": f - p}
    valid = [v for v in deltas.values() if v]
    new_final = []
    for i, r in per["final"].items():
        dlt = deltas[i]["delta"] if deltas[i] else 0
        new_final.append(r["model_seconds"] - (dlt / r["tok_per_s"] if r["tok_per_s"] else 0))
    new_ratio = statistics.median(new_final) / out["base"]["median_model_seconds"]
    # 추정 2: 고른 후보의 실제 최종 JSON(마지막 호출)을 Partial로 바꿀 때의 감소 비율을 그 문항의 실제 최종 JSON token에 적용한다.
    from geoflow.planner import parse_planner_json
    from training.data.thinking import split_response
    last = {}
    for line in (ROOT / "training/generated/pilot_005/raw/lat-final_s1_raw.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        last[r["id"]] = r["raw_text"]
    new_final2, red2 = [], []
    for i, r in per["final"].items():
        cut = 0
        try:
            parsed = parse_planner_json(split_response(last[i])[1])
            f = len(tok(json.dumps(parsed, ensure_ascii=False), add_special_tokens=False)["input_ids"])
            pt = len(tok(json.dumps(render_partial(semantics_from_full(parsed)), ensure_ascii=False), add_special_tokens=False)["input_ids"])
            cut = r["final_json_tokens"] * (f - pt) / f
            red2.append(cut)
        except Exception:  # noqa: BLE001 - JSON 없음
            pass
        new_final2.append(r["model_seconds"] - (cut / r["tok_per_s"] if r["tok_per_s"] else 0))
    new_ratio2 = statistics.median(new_final2) / out["base"]["median_model_seconds"]
    need_seconds = out["final"]["median_model_seconds"] - 1.5 * out["base"]["median_model_seconds"]
    rate = out["final"]["median_tok_per_s"]
    return {"pilot005": out, "ratio_final_over_base": round(ratio, 3),
            "gold_render_tokens(30)": {"median_full": statistics.median(v["full"] for v in valid), "median_partial": statistics.median(v["partial"] for v in valid),
                                       "median_delta": statistics.median(v["delta"] for v in valid),
                                       "mean_reduction_pct": round(100 * statistics.mean(v["delta"] / v["full"] for v in valid), 1),
                                       "items_with_gold": len(valid)},
            "estimate_partial_ratio(thinking unchanged)": round(new_ratio, 3),
            "estimate2_partial_ratio(actual final JSON, thinking unchanged)": round(new_ratio2, 3),
            "estimate2_median_tokens_cut_per_item": round(statistics.median(red2), 1) if red2 else None,
            "estimate2_items_parsed": len(red2),
            "needed_for_1.5": {"seconds_per_item(median)": round(need_seconds, 2), "tokens_per_item_at_median_rate": round(need_seconds * rate),
                               "median_rate_tok_per_s": round(rate, 1)},
            "prefill_note": "Partial P0.3 입력은 Full보다 1,459 token 길다(8,729 대 7,270). 순차 측정에서 같은 system prompt는 prefix cache로 재사용되므로 문항마다 다시 계산되는 양은 작지만, 첫 문항·cache 밖에서는 prefill이 는다(별도 측정 필요).",
            "per_item": {i: {**per["final"][i], "base_model_seconds": per["base"][i]["model_seconds"], "render": deltas[i]} for i in per["final"]},
            "note": "추정이지 판정이 아니다. thinking 길이가 Partial 학습으로 바뀌면 이 추정은 맞지 않는다."}


def thinking(tok):
    from training.data.thinking import split_response
    by_src = defaultdict(list)
    for line in (ROOT / "training/generated/thinking_pilot004_t2pc/sft_train.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        content = r["messages"][-1]["content"]
        th = split_response(content)[0] if "</think>" in content else ""
        src = "teacher(full_response)" if r["metadata"].get("loss_scope") == "full_response" else "8b_self(json_only)"
        by_src[src].append(len(tok(th, add_special_tokens=False)["input_ids"]))
    data = {s: {"records": len(v), "p50": float(np.percentile(v, 50)), "p90": float(np.percentile(v, 90)), "mean": round(float(np.mean(v)), 1)}
            for s, v in by_src.items()}
    cells = {}
    for name, pat in RAWS.items():
        lens = []
        for k in (1, 2, 3, 4):
            for line in Path(str(pat).format(k)).read_text(encoding="utf-8").splitlines():
                raw = json.loads(line)["raw_text"]
                lens.append(_split(tok, raw)[0])
        cells[name] = {"calls": len(lens), "p50": float(np.percentile(lens, 50)), "p90": float(np.percentile(lens, 90)), "mean": round(float(np.mean(lens)), 1)}
    return {"pilot004_data_by_source": data, "selection_v2_cells_thinking_tokens_per_call": cells,
            "note": "thinking = </think> 앞부분(tokenizer Qwen3-8B@b968826d). 셀은 k=4 표본의 모든 호출(재질의 포함)."}


def main():
    import hf_thinking as H
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    HERE.mkdir(exist_ok=True)
    results = {"power": power(), "latency": latency(tok), "thinking": thinking(tok)}
    for name, value in results.items():
        (HERE / f"{name}.json").write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    p, lt, th = results["power"], results["latency"], results["thinking"]
    print(json.dumps({"power": {k: p[k] for k in ("sft_only_pairs_half_width_pp", "all_pairs_half_width_pp", "projection", "gate_a_pass_probability(margin -5pp)")},
                      "latency": {k: lt[k] for k in ("ratio_final_over_base", "gold_render_tokens(30)", "estimate_partial_ratio(thinking unchanged)",
                                                    "estimate2_partial_ratio(actual final JSON, thinking unchanged)", "estimate2_median_tokens_cut_per_item",
                                                    "estimate2_items_parsed", "needed_for_1.5")},
                      "thinking": th}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
