# -*- coding: utf-8 -*-
"""경로별 token 확률 분석(결정 75, 작업 2). 모델 호출 없음(CPU, tokenizer만).

    HF_HOME=... HF_HUB_OFFLINE=1 hfvenv/bin/python sft_dpo_inventory/logprob_diag/analyze_logprob.py

입력: ``/data/hwkim/sftdpo_work/logprob_diag/scores/<경로>.bin``(run_scores.sh), ``sequences.jsonl``.
출력: ``analysis.json``(집계만, 원문·token 열 없음).

- 구간: 응답 token 중 ``</think>``까지 thinking, 그 뒤 JSON. 묶음(sft, cal)별로도 나눈다.
- 기준과의 차이(최종 경로는 ``hf_final_peft``, base 경로는 ``hf_base`` 기준):
  - 평균 |Δlog p|: 기준 응답 token의 log 확률 차이 절댓값의 평균.
  - KL 근사: KL(기준‖경로)를 기준의 top-64 token과 나머지 묶음 하나로 계산한다. 경로의 top-64에 없는 token의 log 확률은
    경로의 64번째 값으로 둔다(그래서 실제 KL보다 작게 나올 수 있다). 단위 nat/token.
  - top-1 불일치 비율.
- 학습 신호 보존율: 경로 P마다 s_P(t) = log p_최종,P(t) − log p_base,P(t). HF(s_HF: hf_final_peft − hf_base)와 비교한다.
  - 보존율 = mean(s_P) / mean(s_HF), 기울기 = cov(s_P, s_HF)/var(s_HF), 상관, 평균 |s_P − s_HF|.
  - 강한 학습 token(|s_HF| ≥ 1)에서 같은 값과, 부호 일치 비율.
  - 운영 경로 주 비교(결정 72)의 기준 E에 맞춘 신호도 낸다: 최종 경로 − 공식 qwen3:8b blob.
- 결정 token(JSON 구간): ``dimension_target`` 키·값, ``od_role`` 값, ``subtype`` 값, ``aggregation`` 키·값.
  값은 값 문자열의 첫 token을 결정 token으로 본다. 키는 키 이름의 첫 token이다.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
WORK = Path("/data/hwkim/sftdpo_work/logprob_diag")
K = 64
REC = np.dtype([("t", "<f4"), ("top1", "<i4"), ("ids", "<i4", K), ("lps", "<f4", K)])
FINAL = ["hf_final_peft", "hf_final_merged", "final_gguf_bf16", "final_q8", "final_self_q4", "final_official_q4"]
BASE = ["hf_base", "base_gguf_bf16", "base_q8", "base_self_q4", "base_official_q4", "official_blob"]
SIGNAL_PAIRS = [("HF+adapter", "hf_final_peft", "hf_base"), ("HF 병합 BF16", "hf_final_merged", "hf_base"),
                ("GGUF BF16", "final_gguf_bf16", "base_gguf_bf16"), ("GGUF Q8_0", "final_q8", "base_q8"),
                ("자체 Q4_K_M", "final_self_q4", "base_self_q4"), ("공식 방식 Q4", "final_official_q4", "base_official_q4"),
                ("E 기준: 자체 Q4_K_M − qwen3:8b", "final_self_q4", "official_blob"),
                ("E 기준: 공식 방식 Q4 − qwen3:8b", "final_official_q4", "official_blob"),
                ("E 기준: Q8_0 − qwen3:8b", "final_q8", "official_blob")]
DECISIONS = {
    "dimension_target 키": (r'"(dimension_target)"\s*:', "key"),
    "dimension_target 값": (r'"dimension_target"\s*:\s*"([^"]+)"', "value"),
    "od_role 값": (r'"od_role"\s*:\s*"([^"]+)"', "value"),
    "subtype 값": (r'"subtype"\s*:\s*"([^"]+)"', "value"),
    "aggregation 키": (r'"(aggregation)"\s*:', "key"),
    "aggregation 값": (r'"aggregation"\s*:\s*"([^"]+)"', "value"),
}


def read(path):
    data, out, o = path.read_bytes(), {}, 0
    while o < len(data):
        seq, count = np.frombuffer(data, "<i4", 2, o)
        o += 8
        out[int(seq)] = np.frombuffer(data, REC, int(count), o)
        o += int(count) * REC.itemsize
    return out


def kl_approx(ref, path):
    """행마다 KL(ref‖path), ref top-64 + 나머지 묶음."""
    p = np.exp(ref["lps"].astype(np.float64))                        # (T, K)
    q_lp = np.empty_like(p)
    for i in range(len(ref["t"])):
        lookup = dict(zip(path["ids"][i].tolist(), path["lps"][i].tolist()))
        floor = float(path["lps"][i][-1])
        q_lp[i] = [lookup.get(v, floor) for v in ref["ids"][i].tolist()]
    q = np.exp(q_lp)
    kl = (p * (ref["lps"] - q_lp)).sum(axis=1)
    pr, qr = np.clip(1 - p.sum(axis=1), 1e-12, 1), np.clip(1 - q.sum(axis=1), 1e-12, 1)
    return kl + pr * np.log(pr / qr)


def decision_positions(tok, seq):
    """JSON 구간의 결정 token 위치(시퀀스 절대 위치). byte-level BPE를 바이트로 되돌려 정규식으로 찾는다."""
    from transformers.models.gpt2.tokenization_gpt2 import bytes_to_unicode
    dec = {v: k for k, v in bytes_to_unicode().items()}
    ids = seq["ids"][seq["think_end"]:]
    starts, buf = [], b""
    for piece in tok.convert_ids_to_tokens(ids):
        starts.append(len(buf))
        buf += bytes(dec[c] for c in piece) if all(c in dec for c in piece) else piece.encode("utf-8")
    starts = np.array(starts)
    text = buf.decode("utf-8", errors="replace")
    found = defaultdict(list)
    for name, (pattern, _) in DECISIONS.items():
        for m in re.finditer(pattern.encode(), buf):
            byte_start = m.start(1)
            j = int(np.searchsorted(starts, byte_start, side="right") - 1)   # 값(또는 키) 첫 바이트를 담은 token
            found[name].append({"pos": seq["think_end"] + j, "value": m.group(1).decode("utf-8", "replace")})
    return found, text


def stats(mask, ref, path, kl):
    d = np.abs(path["t"] - ref["t"])[mask]
    return {"tokens": int(mask.sum()), "mean_abs_dlogp": round(float(d.mean()), 4) if d.size else None,
            "kl_approx": round(float(kl[mask].mean()), 5) if d.size else None,
            "top1_mismatch_pct": round(100 * float((path["top1"] != ref["top1"])[mask].mean()), 3) if d.size else None,
            "mean_logp_ref": round(float(ref["t"][mask].mean()), 4) if d.size else None,
            "mean_logp_path": round(float(path["t"][mask].mean()), 4) if d.size else None}


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", revision="b968826d9c46dd6066d109eabc6255188de91218")
    seqs = [json.loads(line) for line in (WORK / "sequences.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest = {m["index"]: m for m in json.loads((HERE / "sequences_manifest.json").read_text())["sequences"]}
    scores = {p: read(WORK / "scores" / f"{p}.bin") for p in FINAL + BASE}
    # 위치 배열: 시퀀스마다 응답 위치(절대) → 구간 표지
    seg, setname, flat = {}, {}, defaultdict(dict)
    for s in seqs:
        n, start, te = len(s["ids"]), s["resp_start"], s["think_end"]
        pos = np.arange(start, n)
        seg[s["index"]] = np.where(pos < te, "thinking", "json")
        setname[s["index"]] = manifest[s["index"]]["set"]
    order = [s["index"] for s in seqs]

    def cat(p, field):
        return np.concatenate([scores[p][i][field] for i in order])

    seg_all = np.concatenate([seg[i] for i in order])
    set_all = np.concatenate([np.full(len(seg[i]), setname[i]) for i in order])
    masks = {f"{g}/{sg}": (np.ones_like(seg_all, bool) if g == "all" else set_all == g) &
             (np.ones_like(seg_all, bool) if sg == "all" else seg_all == sg)
             for g in ("all", "sft", "cal") for sg in ("all", "thinking", "json")}
    result = {"note": "모델 호출 없음. 원문 없음.", "sequences": len(seqs),
              "response_tokens": {k: int(v.sum()) for k, v in masks.items()}, "vs_reference": {}, "training_signal": {},
              "decision_tokens": {}}
    # 1) 기준과의 차이
    for ref_name, paths in (("hf_final_peft", FINAL), ("hf_base", BASE)):
        ref = {f: cat(ref_name, f) for f in ("t", "top1", "ids", "lps")}
        for p in paths:
            if p == ref_name:
                continue
            path = {f: cat(p, f) for f in ("t", "top1", "ids", "lps")}
            kl = kl_approx(ref, path)
            result["vs_reference"][f"{ref_name} → {p}"] = {k: stats(m, ref, path, kl) for k, m in masks.items()}
            print("ref", ref_name, p, {k: (v["mean_abs_dlogp"], v["kl_approx"], v["top1_mismatch_pct"])
                                       for k, v in result["vs_reference"][f"{ref_name} → {p}"].items() if k.startswith("all/")})
    # 2) 학습 신호 보존
    s_hf = cat("hf_final_peft", "t") - cat("hf_base", "t")
    for label, fp, bp in SIGNAL_PAIRS:
        s = cat(fp, "t") - cat(bp, "t")
        out = {}
        for k, m in masks.items():
            a, b = s[m], s_hf[m]
            strong = np.abs(b) >= 1
            out[k] = {"mean_signal": round(float(a.mean()), 4), "mean_signal_hf": round(float(b.mean()), 4),
                      "retention_mean_ratio": round(float(a.mean() / b.mean()), 3) if abs(b.mean()) > 1e-9 else None,
                      "slope_on_hf": round(float(np.cov(a, b)[0, 1] / b.var(ddof=1)), 3),
                      "corr": round(float(np.corrcoef(a, b)[0, 1]), 3),
                      "mean_abs_diff_from_hf": round(float(np.abs(a - b).mean()), 4),
                      "strong_tokens": int(strong.sum()),
                      "strong_retention_mean_ratio": round(float(a[strong].mean() / b[strong].mean()), 3) if strong.any() else None,
                      "strong_slope": round(float(np.cov(a[strong], b[strong])[0, 1] / b[strong].var(ddof=1)), 3) if strong.sum() > 2 else None,
                      "strong_sign_agree_pct": round(100 * float((np.sign(a[strong]) == np.sign(b[strong])).mean()), 2) if strong.any() else None}
        result["training_signal"][label] = {"final": fp, "base": bp, **out}
        print("signal", label, {k: (v["mean_signal"], v["retention_mean_ratio"], v["slope_on_hf"], v["corr"])
                                for k, v in out.items() if k.endswith("/json") or k == "all/all"})
    # 3) 결정 token
    rows = defaultdict(list)
    for s in seqs:
        found, _ = decision_positions(tok, s)
        offset = s["resp_start"]
        for name, hits in found.items():
            for h in hits:
                r = h["pos"] - offset
                rows[name].append({"set": setname[s["index"]], "value": h["value"],
                                   **{p: float(scores[p][s["index"]]["t"][r]) for p in FINAL + BASE},
                                   **{f"top1_{p}": int(scores[p][s["index"]]["top1"][r]) == s["ids"][h["pos"]] for p in FINAL + BASE}})
    for name, items in rows.items():
        out = {"count": len(items), "values": dict(sorted(((v, sum(1 for i in items if i["value"] == v))
                                                           for v in {i["value"] for i in items}), key=lambda x: -x[1]))}
        for p in FINAL + BASE:
            lp = np.array([i[p] for i in items])
            out[p] = {"mean_prob": round(float(np.exp(lp).mean()), 4), "mean_logp": round(float(lp.mean()), 4),
                      "min_prob": round(float(np.exp(lp).min()), 4),
                      "ref_token_is_top1_pct": round(100 * float(np.mean([i[f"top1_{p}"] for i in items])), 1)}
        for label, fp, bp in SIGNAL_PAIRS:
            sig = np.array([i[fp] - i[bp] for i in items])
            out[f"signal: {label}"] = round(float(sig.mean()), 4)
        result["decision_tokens"][name] = out
        print("decision", name, out["count"], {p: out[p]["mean_prob"] for p in FINAL + BASE})
    (HERE / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
