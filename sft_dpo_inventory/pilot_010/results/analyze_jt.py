# -*- coding: utf-8 -*-
"""pilot_010 JT 집계(결정 271, PLAN_JT 5절). **교사 참고 측정(판정 아님) — PF2·H-final의 추가 사용.** 측정 전에 커밋한다. 모델 호출 없음.
모델 = "Qwen/Qwen3.8-27B BF16 (vLLM)" — 교사 응답 생성·운영에 쓴 Ollama qwen3.8:27b(Q4_K_M, digest aaee06c3)와 같은 빌드가 아니다.
``analyze_j``·``analyze_jp``·``analyze_jq``·``analyze_jg``는 고치지 않고 함수를 불러 쓴다. **PF2 질문·정답 호출·응답은 출력·저장하지 않는다**
(집계 수치·형 M·P·C·범주 코드·sha256만; P·C 범주는 ``redact_j``와 같은 코드 P-1, C-b …로만).

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/results/analyze_jt.py --out sft_dpo_inventory/pilot_010/results/jt_results.json

- 27B 셀: PF2 ``<700>/cells/pf2jt_{s,g1}_t27_s{1..4}.json``, H-final ``cells/JT/hfinaljt_{s,g1}_t27_s1.json``(범위 = ``gpu/JT/scope.json``:
  full3000 또는 subset1000 = ``jt/hfinal_subset1000_ids.txt``). 27B는 seed 하나인 arm(행 1개) → CI는 문항만 재추출(``analyze_j.boot``, 10,000회).
- 학생(새 측정 없음): S = J·JP·JQ sampling 셀(``analyze_jq.load_arms``, base PF2 k=8·H-final 두 회차), G1 = JG 셀(``analyze_jg.load_cond``).
  arm = base, SFT, RR, RR+NM4, RR+NM8(7), RR+NM 12 seed. H-final은 27B와 같은 문항(부분집합이면 그 1,000문항)으로 다시 계산한다.
- 차이: 학생 arm − 27B(``analyze_j.diff``: 학생 U1 = seed 재추출, 27B 문항만, 문항 공유 재추출). "교사 대비 회복 비율"은 계산하지 않는다.
- 세부: PF2 올바른 거부 형별(M·P·C)·범주별(M 이름, P·C 코드), 근접 대조 25 범주별 과잉 거부, 답하는 100 결과 분해, H-final 결과 분해·도구 유형별·
  template_group 붕괴(같은 조건 base 대비), 호출·wall. smoke(``scope.json``)·선택 셀(rdev v2·valid98·aux, 기술만)·지연·자원(5절).
- 검사: S 학생 단일 seed 평균(3,000문항)이 ``jp_posthoc.json``과 같은지(``analyze_jq.check_against_jp``), 27B 셀 유효성(``validity_j.check``).
"""
import argparse
import glob
import hashlib
import json
import re
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INV = ROOT / "sft_dpo_inventory"
for p in (ROOT, HERE, INV / "pilot_006/gates", INV / "pilot_006/post", INV / "pilot_009/gates", INV / "ablation_012/analysis", INV / "pilot_009/protected_final_v2"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import analyze_j as AJ  # noqa: E402
import analyze_jg as AG  # noqa: E402
import analyze_jp as AP  # noqa: E402
import analyze_jq as AQ  # noqa: E402
import validity_j as VJ  # noqa: E402

JT = INV / "pilot_010/cells/JT"
GJT = INV / "pilot_010/gpu/JT"
SUBSET = INV / "pilot_010/jt/hfinal_subset1000_ids.txt"
MODEL27_DIR = Path("/data/hwkim/sftdpo_work/pilot_010_jt/model/Qwen3.8-27B")
NAMES = {**AG.NAMES, "T27": "Qwen/Qwen3.8-27B BF16 (vLLM)"}
ARMS = ("base", "B2F", "P9", "V4", "V8", "RRNM12")
LAB = "교사 참고 측정(판정 아님); PF2·H-final 추가 사용; 27B = Qwen/Qwen3.8-27B BF16 (vLLM), Ollama qwen3.8:27b(Q4_K_M, aaee06c3)와 다른 빌드"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def restrict(S, ids, ctx):
    """H-final 문항을 ids(원래 순서)로 줄인 Sets 사본."""
    keep = set(ids)
    T = AQ.Sets.__new__(AQ.Sets)
    T.__dict__.update({k: v for k, v in S.__dict__.items() if k not in ("hf", "types", "groups")})
    T.hf = [i for i in S.hf if i in keep]
    hg = ctx["gold_hfinal"]
    T.types, T.groups = defaultdict(list), defaultdict(list)
    for x, i in enumerate(T.hf):
        T.types[ctx["TYPE_BY_TOOL"].get(hg[i]["gold"][-1]["tool"], "기타")].append(x)
        T.groups[hg[i]["template_group"]].append(x)
    return T


def cat_code(form, cat):
    m = re.match(r"^([PC]-[0-9a-z]+)\b", cat or "")
    return f"{form} {cat}" if form == "M" else (m.group(1) if m else f"{form} ?")


def refusal_by_category(PF, arm, S, meta):
    seeds = tuple(PF[arm])
    per = defaultdict(list)
    n = defaultdict(int)
    for i in S.ref:
        n[cat_code(meta[i]["form"], meta[i]["category"])] += 1
    for s in seeds:
        c = defaultdict(list)
        for i in S.ref:
            c[cat_code(meta[i]["form"], meta[i]["category"])].append(np.mean([float(x[i]["refused"]) for x in PF[arm][s]]))
        for k, v in c.items():
            per[k].append(np.mean(v))
    return {k: {"items": n[k], "pct": AJ.pp(np.mean(v))} for k, v in sorted(per.items())}


def contrast_by_category(PF, arm, S, meta):
    seeds = tuple(PF[arm])
    per = defaultdict(list)
    n = defaultdict(int)
    for i in S.con:
        n[meta[i]["contrast"]] += 1
    for s in seeds:
        c = defaultdict(list)
        for i in S.con:
            c[meta[i]["contrast"]].append(np.mean([float(x[i]["refused"]) for x in PF[arm][s]]))
        for k, v in c.items():
            per[k].append(np.mean(v))
    return {k: {"items": n[k], "pct": AJ.pp(np.mean(v))} for k, v in sorted(per.items())}


def block(PF, HF, S, ctx, label):
    """한 조건: 27B와 학생 arm의 추정·세부, 학생 − 27B 차이."""
    arms = [a for a in ARMS if PF.get(a)] + ["T27"]
    mats = {a: AQ.metric_mats_single(PF, HF, a, tuple(PF[a]), S) for a in arms}
    base_hf = AQ.hf_vec(HF["base"][next(iter(HF["base"]))], S.hf)
    out = {"condition": label, "hfinal_items": len(S.hf), "arms": {}, "student_minus_t27": {}}
    for a in arms:
        sd = tuple(PF[a])
        out["arms"][a] = {"name": NAMES[a], "seeds": list(sd), "metrics": AQ.est_all(mats[a]),
                          "pf2_correct_refusal_by_form": AG.form_refusal(PF, a, sd, S, ctx["pf_meta"]),
                          "pf2_correct_refusal_by_category": refusal_by_category(PF, a, S, ctx["pf_meta"]),
                          "pf2_contrast25_over_refusal_by_category": contrast_by_category(PF, a, S, ctx["pf_meta"]),
                          "pf2_decomposition_100_seed_mean": AG.pf_decomp(PF, a, sd, S),
                          "hfinal": AQ.single_hf_details(HF, a, sd, S, base_hf, ctx), "cost_seed_mean": AQ.single_cost(PF, HF, a, sd)}
    for a in arms[:-1]:
        out["student_minus_t27"][f"{a}-T27"] = AQ.diff_all(mats[a], mats["T27"])
    return out


def load_t27(ctx, cond):
    pf = [PF_CELL(cond, k) for k in range(1, 5)]
    hf = JT / f"hfinaljt_{cond}_t27_s1.json"
    missing = [str(p) for p in pf + [hf] if not p.exists()]
    if missing:
        raise SystemExit(f"27B cells missing ({cond}): {[Path(m).name for m in missing]}")
    PFr, cells, validity = [], [], []
    for p in pf:
        rec, info = AQ.load_cell(p, "pf2", ctx)
        PFr.append(rec)
        cells.append(info)
        validity.append(VJ.check(str(p)))
    rec, info = AQ.load_cell(hf, "hfinal", ctx)
    cells.append(info)
    validity.append(VJ.check(str(hf)))
    return {"t27": PFr}, {"t27": [rec]}, cells, validity


def PF_CELL(cond, k):
    return AJ.PF_CELLS / f"pf2jt_{cond}_t27_s{k}.json"


# ---------------- 선택 셀·smoke·지연 ----------------
def dev_cell(p):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    rows = d["rows"]
    calls = [c for r in rows for c in (r.get("hf_calls") or [])]
    refused = sum(1 for r in rows if r.get("outcome") in AJ.REFUSAL_OUTCOMES)
    return {"file": str(Path(p).relative_to(ROOT)), "sha256": sha(p), "items": len(rows), "match_pct": AJ.pp(np.mean([r.get("category") == "match" for r in rows])),
            "refusal_outcome_pct": AJ.pp(refused / len(rows)), "truncated_calls": sum(c.get("finish_reason") == "length" for c in calls), "calls": len(calls),
            "validity": VJ.check(str(p)), "note": "기술만(27B 단독, 학생 비교 없음); match = 행 category == match(rdev v2는 거부 문항의 올바른 거부 포함)"}


_TOK = {}


def tok(kind):
    if kind not in _TOK:
        from transformers import AutoTokenizer
        _TOK[kind] = AutoTokenizer.from_pretrained(str(MODEL27_DIR)) if kind == "27b" else AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", revision="b968826d9c46dd6066d109eabc6255188de91218")
    return _TOK[kind]


def latency_cell(p, kind, mem):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    rows, meta = d["rows"], d["meta"]
    secs = [sum(c["server_seconds"] for c in r["hf_calls"]) for r in rows]
    walls = [AQ.wall(r) for r in rows if AQ.wall(r) is not None]
    gen = [sum(c["generated_tokens"] for c in r["hf_calls"]) for r in rows]
    parts = defaultdict(lambda: {"thinking": 0, "json": 0})
    raw = Path(meta["hf"]["raw_out"])
    t = tok(kind)
    for line in raw.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        text = r["raw_text"]
        th, js = (text.split("</think>", 1) + [""])[:2] if "</think>" in text else (text, "")
        parts[r["id"]]["thinking"] += len(t(th, add_special_tokens=False)["input_ids"])
        parts[r["id"]]["json"] += len(t(js.strip(), add_special_tokens=False)["input_ids"])
    return {"file": str(Path(p).relative_to(ROOT)), "sha256": sha(p), "items": len(rows), "model": meta["model"],
            "median_model_seconds": round(statistics.median(secs), 3), "p95_model_seconds": round(float(np.percentile(secs, 95)), 3),
            "median_item_wall_seconds": round(statistics.median(walls), 3) if walls else None, "p95_item_wall_seconds": round(float(np.percentile(walls, 95)), 3) if walls else None,
            "median_generated_tokens": statistics.median(gen), "median_thinking_tokens": statistics.median(v["thinking"] for v in parts.values()),
            "median_json_tokens": statistics.median(v["json"] for v in parts.values()),
            "tok_per_s(sum generated / sum model seconds)": round(sum(gen) / sum(secs), 1),
            "median_input_tokens": statistics.median(r["hf_calls"][0]["prompt_tokens"] for r in rows if r["hf_calls"]),
            "truncated_calls": sum(c.get("finish_reason") == "length" for r in rows for c in r["hf_calls"]), "gpu_memory_max_mib_during_cell": mem,
            "tokenizer": "Qwen/Qwen3.8-27B" if kind == "27b" else "Qwen/Qwen3-8B@b968826d"}


def cell_windows():
    tl = [json.loads(x) for x in (GJT / "timeline.jsonl").read_text(encoding="utf-8").splitlines()] if (GJT / "timeline.jsonl").exists() else []
    starts, win = {}, {}
    for e in tl:
        if e.get("event") == "cell_start":
            starts[e["cell"]] = e["t"]
        elif e.get("event") == "cell_end" and e["cell"] in starts:
            win[e["cell"]] = (starts[e["cell"]], e["t"])
    return win


def mem_during(name, gpus):
    win = cell_windows().get(name)
    p = GJT / "gpu_mem.jsonl"
    if not win or not p.exists():
        return None
    a, b = datetime.fromisoformat(win[0]), datetime.fromisoformat(win[1])
    best = defaultdict(int)
    for line in p.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if a <= datetime.fromisoformat(e["t"]) <= b:
            for idx, used, _ in e["gpus"]:
                if int(idx) in gpus:
                    best[int(idx)] = max(best[int(idx)], int(used))
    return dict(best) or None


def weights():
    w27 = sum(Path(f).stat().st_size for f in glob.glob(str(MODEL27_DIR / "*.safetensors")))
    snap = glob.glob("/data/hwkim/sftdpo_work/hf-cache/hub/models--Qwen--Qwen3-8B/snapshots/b968826d*/*.safetensors") or \
        glob.glob(str(Path.home() / ".cache/huggingface/hub/models--Qwen--Qwen3-8B/snapshots/b968826d*/*.safetensors"))
    w8 = sum(Path(f).resolve().stat().st_size for f in snap)
    ad = Path("/data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o101/checkpoint-1984/adapter_model.safetensors")
    return {"t27_bf16_bytes": w27, "t27_gb": round(w27 / 1e9, 2), "qwen3_8b_bf16_bytes": w8, "qwen3_8b_gb": round(w8 / 1e9, 2),
            "rrnm4_o101_adapter_bytes": ad.stat().st_size if ad.exists() else None}


def latency_block():
    L = JT / "latency"
    out = {"method": "결정 113 방식: 고정 30문항(serving_vllm_fp8/latency_ids.txt), 동시 요청 1, S 조건(T 0.6), 문항 모델 시간 = 호출 server_seconds 합",
           "cells": {}, "weights": weights(), "gpus": {"t27": 2, "8b": 1}}
    for name, kind, gpus in (("latjt_t27", "27b", [0, 1]), ("latjt_8b_base", "8b", [0]), ("latjt_8b_v4_o101", "8b", [0])):
        p = L / f"{name}_s1.json"
        if p.exists():
            out["cells"][name] = latency_cell(p, kind, mem_during(name, gpus))
    for port in ("8700", "8701", "8710"):
        sp = GJT / f"server_{port}.json"
        if sp.exists():
            sm = json.loads(sp.read_text(encoding="utf-8"))
            out.setdefault("server_memory_after_ready", {})[port] = {"nvidia_smi_after_ready": sm.get("nvidia_smi_after_ready"),
                                                                     "log_memory_lines": sm.get("log_memory_lines"), "attention_backend": sm.get("log_attention_backend")}
    return out


def smoke_block():
    sc = GJT / "scope.json"
    if not sc.exists():
        return None
    rec = json.loads(sc.read_text(encoding="utf-8"))
    p = JT / "smoke/hdev100jt_s_t27_s1.json"
    if p.exists():
        rec["cell"] = {"file": str(p.relative_to(ROOT)), "sha256": sha(p), "validity": VJ.check(str(p))}
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ctx = AQ.setup()
    S_full = AQ.Sets(ctx)
    scope = json.loads((GJT / "scope.json").read_text(encoding="utf-8"))["scope"]
    S = S_full if scope == "full3000" else restrict(S_full, SUBSET.read_text(encoding="utf-8").strip().split(","), ctx)
    res = {"label": LAB, "decision": 271, "plan": "sft_dpo_inventory/pilot_010/PLAN_JT.md", "names": NAMES, "hfinal_scope": scope, "hfinal_items": len(S.hf),
           "bootstrap": {"reps": AJ.REPS, "rng": f"default_rng({AJ.RNG_SEED}) per statistic", "method": "학생 U1(문항 공유, arm마다 seed 재추출), 27B 문항만"},
           "smoke": smoke_block(), "conditions": {}, "cells_t27": [], "validity_t27": []}
    # ---- S: 학생 J·JP·JQ sampling ----
    PFs, HFs, cells_s = AQ.load_arms(ctx, {**AQ.SEEDS, "V8new": AQ.V8_NEW, "base": ("base",)})
    PFs["V8"] = {**PFs["V8"], **PFs.pop("V8new")}
    HFs["V8"] = {**HFs["V8"], **HFs.pop("V8new")}
    res["check_sampling_single_means_vs_jp_posthoc"] = AQ.check_against_jp({k: AQ.metric_mats_single(PFs, HFs, k, AQ.SEEDS[k], S_full) for k in AQ.SEEDS},
                                                                         AQ.metric_mats_single(PFs, HFs, "base", ("base",), S_full))
    AG.add_pool(PFs, HFs)
    pf, hf, c, v = load_t27(ctx, "s")
    PFs["T27"], HFs["T27"] = pf, hf
    res["cells_t27"] += c
    res["validity_t27"] += v
    res["conditions"]["S"] = block(PFs, HFs, S, ctx, "S (T 0.6, top-p 0.95, top-k 20): 학생 = J·JP·JQ 셀")
    res["cells_students_S"] = cells_s
    # ---- G1: 학생 JG ----
    PFg, HFg, cells_g, val_g, missing = AG.load_cond(ctx, "g1")
    AG.add_pool(PFg, HFg)
    pf, hf, c, v = load_t27(ctx, "g1")
    PFg["T27"], HFg["T27"] = pf, hf
    res["cells_t27"] += c
    res["validity_t27"] += v
    res["conditions"]["G1"] = block(PFg, HFg, S, ctx, "G1 (T 0.2, top-p 0.95, top-k 20): 학생 = JG 셀")
    res["cells_students_G1"], res["missing_students_G1"] = cells_g, missing
    # ---- 선택·지연 ----
    res["optional_dev_cells_t27"] = {t: dev_cell(JT / f"jt_s_t27_{t}_s1.json") for t in ("rdevv2", "valid98", "aux") if (JT / f"jt_s_t27_{t}_s1.json").exists()}
    res["latency_resources"] = latency_block()
    rr = GJT / "RERUNS_JT.json"
    res["reruns"] = json.loads(rr.read_text(encoding="utf-8")) if rr.exists() else {"reruns": {}}
    res["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    res["inputs"] = {"pf2_gold_sha256": sha(AJ.PF_GOLD), "pf2_meta_sha256": sha(AJ.PF_META), "hfinal_sha256": sha(ROOT / AJ.HF_GOLD), "analysis_sha256": sha(__file__),
                     "subset_ids_sha256": sha(SUBSET), "analyze_jg_sha256": sha(AG.__file__), "analyze_jq_sha256": sha(AQ.__file__), "analyze_j_sha256": sha(AJ.__file__)}
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("written", a.out, "scope", scope, "hfinal_items", len(S.hf))


if __name__ == "__main__":
    main()
