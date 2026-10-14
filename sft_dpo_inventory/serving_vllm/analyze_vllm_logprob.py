# -*- coding: utf-8 -*-
"""vLLM과 HF의 token 확률 비교(결정 89, 작업 3). 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/serving_vllm/analyze_vllm_logprob.py

- 기준 응답: logprob_diag의 60개(``sequences.jsonl``, sft 30·cal 30). 구간·지표 함수는 ``logprob_diag/analyze_logprob.py``의 것을 그대로 쓴다
  (``read``, ``kl_approx``, ``stats``).
- 경로: HF base(``logprob_diag/scores/hf_base.bin``), HF+pilot_003 최종 adapter(``hf_final_p3.bin``), vLLM base·final(LoRA).
- 기준과의 차이: vLLM base ↔ HF base, vLLM final ↔ HF final(평균 |Δlog p|, KL 근사, top-1 불일치).
- 학습 신호 보존: s_vLLM = log p_vLLM-final − log p_vLLM-base를 s_HF = log p_HF-final − log p_HF-base와 비교(보존율, 기울기, 상관, 강한 token |s_HF| ≥ 1).
- 결과: ``logprob_compare.json``(집계만).
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/logprob_diag"))
import analyze_logprob as L  # noqa: E402

SCORES = Path("/data/hwkim/sftdpo_work/serving_vllm/scores")
PATHS = {"hf_base": L.WORK / "scores/hf_base.bin", "hf_final": SCORES / "hf_final_p3.bin",
         "vllm_base": SCORES / "vllm_base.bin", "vllm_final": SCORES / "vllm_final.bin"}


def main():
    seqs = [json.loads(line) for line in (L.WORK / "sequences.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest = {m["index"]: m for m in json.loads((ROOT / "sft_dpo_inventory/logprob_diag/sequences_manifest.json").read_text())["sequences"]}
    scores = {p: L.read(f) for p, f in PATHS.items()}
    order = [s["index"] for s in seqs]
    seg, setname = {}, {}
    for s in seqs:
        pos = np.arange(s["resp_start"], len(s["ids"]))
        seg[s["index"]] = np.where(pos < s["think_end"], "thinking", "json")
        setname[s["index"]] = manifest[s["index"]]["set"]

    def cat(p, field):
        return np.concatenate([scores[p][i][field] for i in order])

    seg_all = np.concatenate([seg[i] for i in order])
    set_all = np.concatenate([np.full(len(seg[i]), setname[i]) for i in order])
    masks = {f"{g}/{sg}": (np.ones_like(seg_all, bool) if g == "all" else set_all == g) &
             (np.ones_like(seg_all, bool) if sg == "all" else seg_all == sg)
             for g in ("all", "sft", "cal") for sg in ("all", "thinking", "json")}
    out = {"note": "모델 호출 없음. 원문 없음.", "sequences": len(seqs), "score_files": {k: str(v) for k, v in PATHS.items()},
           "response_tokens": {k: int(v.sum()) for k, v in masks.items()}, "vs_hf": {}, "training_signal": {}}
    for ref, path in (("hf_base", "vllm_base"), ("hf_final", "vllm_final"), ("hf_base", "hf_final")):
        r = {f: cat(ref, f) for f in ("t", "top1", "ids", "lps")}
        q = {f: cat(path, f) for f in ("t", "top1", "ids", "lps")}
        kl = L.kl_approx(r, q)
        out["vs_hf"][f"{ref} → {path}"] = {k: L.stats(m, r, q, kl) for k, m in masks.items()}
        print(ref, path, {k: (v["mean_abs_dlogp"], v["kl_approx"], v["top1_mismatch_pct"])
                          for k, v in out["vs_hf"][f"{ref} → {path}"].items() if k.startswith("all/")})
    s_hf = cat("hf_final", "t") - cat("hf_base", "t")
    s_v = cat("vllm_final", "t") - cat("vllm_base", "t")
    for k, m in masks.items():
        a, b = s_v[m], s_hf[m]
        strong = np.abs(b) >= 1
        out["training_signal"][k] = {
            "mean_signal_vllm": round(float(a.mean()), 4), "mean_signal_hf": round(float(b.mean()), 4),
            "retention_mean_ratio": round(float(a.mean() / b.mean()), 3) if abs(b.mean()) > 1e-9 else None,
            "slope_on_hf": round(float(np.cov(a, b)[0, 1] / b.var(ddof=1)), 3), "corr": round(float(np.corrcoef(a, b)[0, 1]), 3),
            "mean_abs_diff_from_hf": round(float(np.abs(a - b).mean()), 4), "strong_tokens": int(strong.sum()),
            "strong_retention_mean_ratio": round(float(a[strong].mean() / b[strong].mean()), 3) if strong.any() else None,
            "strong_slope": round(float(np.cov(a[strong], b[strong])[0, 1] / b[strong].var(ddof=1)), 3) if strong.sum() > 2 else None,
            "strong_sign_agree_pct": round(100 * float((np.sign(a[strong]) == np.sign(b[strong])).mean()), 2) if strong.any() else None}
    print("signal", {k: (v["retention_mean_ratio"], v["slope_on_hf"], v["corr"], v["strong_tokens"], v["strong_slope"])
                     for k, v in out["training_signal"].items() if k.startswith("all/") or k == "cal/thinking"})
    (HERE / "logprob_compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
