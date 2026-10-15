# -*- coding: utf-8 -*-
"""C1: selection_v2 base가 낮게 나온 원인 확인(모델 호출 없음). 기록된 셀만 비교한다.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/analysis/base_drift.py

- 셀: pilot_prep_007 base(16,384, LoRA 없는 서버, 2026-10-14 17:54–18:31), J4(16,384 + LoRA final, 1표본), B1·X2(17,408 + LoRA final, 같은 seed),
  X1(16,384 + LoRA final, 같은 seed), R3a(v1_step467, 17,408), pilot_005 v1_step467(16,384, LoRA 둘).
- 비교: 표본별 정답 수, 같은 seed 표본끼리 첫 호출 원문 바이트 일치 수, 문항별 정답 일치, 문항 단위 쌍 bootstrap 95% CI(10,000회, default_rng(20261109),
  문항 값 = 그 셀 표본들의 평균).
"""
import json
import statistics
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
C = ROOT / "sft_dpo_inventory/pilot_006_prep/cells"
CELLS = {"p007_base": ROOT / "sft_dpo_inventory/serving_vllm_fp8/runs/vllm-bf16-base_s{}.json",
         "B1": C / "b1_sel_base_s{}.json", "X1": C / "x1_sel_base_16384_s{}.json", "X2": C / "x2_sel_base_17408_s{}.json",
         "R3a": C / "r3a_sel_v1s467_s{}.json", "p005_v1s467": ROOT / "sft_dpo_inventory/pilot_005/runs/v1_step467_s{}.json"}


def load(name):
    return [json.loads(Path(str(CELLS[name]).format(k)).read_text(encoding="utf-8")) for k in (1, 2, 3, 4)]


def item_matrix(ds):
    order = [r["id"] for r in ds[0]["rows"]]
    return order, np.array([[bool({r["id"]: r for r in d["rows"]}[i]["grounding_ok"]) for d in ds] for i in order], float)


def ci(a, b, draws=10000):
    d = a - b
    rng = np.random.default_rng(20261109)
    idx = rng.integers(0, len(d), size=(draws, len(d)))
    m = d[idx].mean(axis=1)
    return round(100 * d.mean(), 2), [round(100 * x, 2) for x in np.percentile(m, [2.5, 97.5])]


def main():
    data = {n: load(n) for n in CELLS}
    mats = {}
    out = {"cells": {}}
    for n, ds in data.items():
        order, m = item_matrix(ds)
        mats[n] = (order, m)
        sm = ds[0]["meta"]["vllm"].get("server_meta") or {}
        args = sm.get("args", [])
        out["cells"][n] = {"per_sample_ok": [int(x) for x in m.sum(axis=0)], "mean_pct": round(100 * m.mean(), 2),
                           "max_model_len": args[args.index("--max-model-len") + 1] if "--max-model-len" in args else None,
                           "loras_on_server": list((sm.get("lora_adapter_sha256") or {}).keys()),
                           "versions": {k: sm.get(k) for k in ("vllm", "flashinfer", "torch", "torch_cuda", "transformers")},
                           "gpu": sm.get("gpu_uuid"), "first_item_started": ds[0]["rows"][0].get("started_at"),
                           "code_fingerprint": ds[0]["meta"].get("code_fingerprint", "")[:8],
                           "median_generated_tokens": statistics.median(c["generated_tokens"] for d in ds for r in d["rows"] for c in r["hf_calls"])}
    def shas(ds, k):
        return {r["id"]: (r["hf_calls"][0]["raw_sha256"] if r["hf_calls"] else None) for r in ds[k]["rows"]}
    pairs = {}
    for a, b in (("B1", "X2"), ("B1", "X1"), ("X1", "X2"), ("X1", "p007_base"), ("X2", "p007_base"), ("B1", "p007_base"), ("R3a", "p005_v1s467")):
        pa, pb = mats[a][1], mats[b][1]
        pairs[f"{a} - {b}"] = {"diff_pp_and_ci95": ci(pa.mean(axis=1), pb.mean(axis=1)),
                               "byte_identical_first_call_same_seed": [sum(shas(data[a], k)[i] == shas(data[b], k)[i] for i in shas(data[a], k)) for k in range(4)]}
    pooled17 = np.concatenate([mats["B1"][1], mats["X2"][1]], axis=1).mean(axis=1)
    pooled16 = np.concatenate([mats["X1"][1], mats["p007_base"][1]], axis=1).mean(axis=1)
    pairs["17408(B1+X2, 8표본) - 16384(X1+p007, 8표본)"] = {"diff_pp_and_ci95": ci(pooled17, pooled16)}
    pairs["16384 LoRA final(X1) - 16384 no LoRA(p007)"] = {"diff_pp_and_ci95": ci(mats["X1"][1].mean(axis=1), mats["p007_base"][1].mean(axis=1))}
    out["pairs"] = pairs
    sample_ok = [x for n in ("B1", "X1", "X2", "p007_base") for x in out["cells"][n]["per_sample_ok"]]
    out["base_sample_spread(16 samples)"] = {"min": min(sample_ok), "max": max(sample_ok), "sd": round(statistics.stdev(sample_ok), 2)}
    (ROOT / "sft_dpo_inventory/pilot_006_prep/analysis/base_drift.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"cells": {n: {k: v[k] for k in ("per_sample_ok", "mean_pct", "max_model_len", "loras_on_server")} for n, v in out["cells"].items()},
                      "pairs": pairs, "spread": out["base_sample_spread(16 samples)"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
