# -*- coding: utf-8 -*-
"""pilot_010 JU 집계(결정 272, PLAN_JU 4절). **교사 4비트 빌드 참고 측정(판정 아님) — PF2·H-final의 추가 사용.** 측정 전에 커밋한다. 모델 호출 없음.
Q4 = "Ollama qwen3.8:27b (Q4_K_M, digest aaee06c3)" — 교사 응답 수집·운영 빌드. BF16 = JT의 "Qwen/Qwen3.8-27B BF16 (vLLM)"(결정 271). backend·정밀도·렌더링이 다르다.
``analyze_j``·``analyze_jp``·``analyze_jq``·``analyze_jg``·``analyze_jt``는 고치지 않고 함수를 불러 쓴다. **PF2 질문·정답 호출·응답은 출력·저장하지 않는다**
(집계 수치·형 M·P·C·범주 코드·sha256·문항 결과 개수만).

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/results/analyze_ju.py --out sft_dpo_inventory/pilot_010/results/ju_results.json

- Q4 셀: PF2 ``<700>/cells/pf2ju_{s,g1}_q4_s{1..4}.json``, H-final ``cells/JU/hfinalju_s_q4_s1.json``(범위 = ``gpu/JU/scope.json``: full3000 또는
  subset1000 = ``jt/hfinal_subset1000_ids.txt``). BF16 = JT 셀(``analyze_jt.load_t27``). 학생 = JT와 같음(S: J·JP·JQ, G1: JG). 부분집합이면 모두 그 1,000문항.
- Q4 단독: PF2 올바른 거부(전체·형 M·P·C·범주 코드), 과잉 거부(답하는 100·근접 25), 정답률, 결과 분해; H-final 정답률·과잉 거부·결과 분해·도구 유형별.
  CI = 문항 bootstrap 10,000회(``analyze_j.boot``; 교사는 행 하나 → 문항만).
- Q4 − BF16: 같은 문항, 문항 공유 재추출(``analyze_j.diff``). 지표마다 따로 판정(합쳐서 한 줄로 요약하지 않음, PLAN_JU 4절):
  CI 전체가 ±폭 안 → "유사"; 아니고 CI가 0을 벗어남 → "다름"; 그 밖 → "판단할 수 없음". 폭 = PF2 올바른 거부·과잉 거부(100)·정답률 10%p,
  H-final 정답률 2%p, H-final 과잉 거부 1%p. 근접 대조 25는 폭이 지시에 없어 차이·CI만 적는다(판정 없음, 사전 고정 해석).
  "유사"이면서 CI가 0을 벗어나면 그 사실(``ci_excludes_0``)을 함께 적는다.
- 문항별 일치(PF2 150): 빌드마다 문항의 k=4 표본 결과(거부 R / 정답 C / 오답 W) 중 3개 이상이 같은 것을 다수 결과로, 아니면 "혼합". 두 빌드 다수 결과가 같은 비율
  (혼합 = 혼합도 같음으로 셈)과 혼합을 뺀 비율, 묶음별(거부 M·P·C, 답하는 75(근접 대조 아님), 근접 대조 25), 결과 쌍 개수표.
- 학생 arm − Q4: JT 표 2와 같은 방식(학생 U1, Q4 문항만). 회복 비율은 계산하지 않는다.
- 비용: 문항당 호출 수·wall p50·p95, 생성 token(문항당; H-final은 thinking / 최종 JSON을 각 모델 tokenizer로 나눔 — PF2 원문은 나누지 않음),
  tok/s(Q4 = Σeval_count / Σeval_duration, 요청 하나씩; vLLM = Σ생성 / Σ호출 server_seconds, 동시 요청 묶음 처리 — 직접 비교 아님), GPU 메모리(측정 중 30초 표본 최대).
- 검사: S 학생 단일 seed 평균이 jp_posthoc와 같은지(``analyze_jq.check_against_jp``), BF16 S 값이 ``jt_results.json``과 같은지(범위가 full3000일 때 전부, 부분집합이면 PF2만),
  Q4 셀 유효성(``validity_j.check`` + Ollama 항목: digest·버전·think·num_predict·세션 4개·100% GPU 확인).
"""
import argparse
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
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
import analyze_jq as AQ  # noqa: E402
import analyze_jt as AT  # noqa: E402
import validity_j as VJ  # noqa: E402

JU = INV / "pilot_010/cells/JU"
GJU = INV / "pilot_010/gpu/JU"
GJT = INV / "pilot_010/gpu/JT"
SUBSET = INV / "pilot_010/jt/hfinal_subset1000_ids.txt"
DIGEST = "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813"
NAMES = {**AT.NAMES, "Q4": "Ollama qwen3.8:27b (Q4_K_M, aaee06c3)"}
STUDENTS = AT.ARMS
BOUNDS = {"correct_refusal": 10.0, "over_refusal_100": 10.0, "accuracy_100": 10.0, "hfinal_accuracy": 2.0, "hfinal_over_refusal": 1.0, "over_refusal_contrast25": None}
LAB = ("교사 4비트 빌드 참고 측정(판정 아님); PF2·H-final 추가 사용; Q4 = Ollama qwen3.8:27b(Q4_K_M, aaee06c3, 교사 수집·운영 빌드), "
       "BF16 = Qwen/Qwen3.8-27B BF16 (vLLM, JT); backend·정밀도·렌더링이 다름")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def q4_pf_path(cond, k):
    return AJ.PF_CELLS / f"pf2ju_{cond}_q4_s{k}.json"


def ju_validity(p):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    m, rows = d["meta"], d["rows"]
    calls = [c for r in rows for c in (r.get("hf_calls") or [])]
    ju = m.get("ju") or {}
    return {**VJ.check(str(p)), "flashinfer": "n/a(Ollama)", "digest_ok": m.get("model_digest") == DIGEST, "ollama_version": m.get("ollama_version"),
            "think_true": ((m.get("ollama") or {}).get("request_example(no message content)") or {}).get("think") is True,
            "num_predict_all_8192": all((c.get("options_sent") or {}).get("num_predict") == 8192 for c in calls),
            "sessions": len(ju.get("sessions") or {}), "ps_checks": ju.get("ps_checks"), "ps_all_100_gpu": ju.get("ps_all_100_gpu"),
            "reused_shards": ju.get("reused_shards"), "server_error_rows_any": sum(1 for r in rows if r.get("error_code") == "UNHANDLED_EXCEPTION")}


def load_q4(ctx, cond):
    pf = [q4_pf_path(cond, k) for k in range(1, 5)]
    hf = [JU / "hfinalju_s_q4_s1.json"] if cond == "s" else []
    missing = [p.name for p in pf + hf if not p.exists()]
    if missing:
        return None, None, [], [], missing
    PFr, HFr, cells, validity = [], [], [], []
    for p in pf:
        rec, info = AQ.load_cell(p, "pf2", ctx)
        PFr.append(rec)
        cells.append(info)
        validity.append(ju_validity(p))
    for p in hf:
        rec, info = AQ.load_cell(p, "hfinal", ctx)
        HFr.append(rec)
        cells.append(info)
        validity.append(ju_validity(p))
    return {"q4": PFr}, ({"q4": HFr} if HFr else None), cells, validity, []


def judge(d, bound):
    lo, hi = d["ci95_pp"]
    ex0 = bool(lo > 0 or hi < 0)
    if bound is None:
        v = "판정 없음(폭이 지시에 없음, 기술만)"
    elif -bound <= lo and hi <= bound:
        v = "유사"
    elif ex0:
        v = "다름"
    else:
        v = "판단할 수 없음"
    return {**d, "bound_pp": bound, "verdict": v, "ci_excludes_0": ex0}


# ---------------- 문항별 일치 ----------------
def item_label(samples, i):
    labs = ["R" if s[i]["refused"] else ("C" if s[i]["correct"] else "W") for s in samples]
    top, n = Counter(labs).most_common(1)[0]
    return top if n >= 3 else "mixed"


def agreement(pf_a, pf_b, S, meta):
    groups = {"refusal_M": [i for i in S.ref if meta[i]["form"] == "M"], "refusal_P": [i for i in S.ref if meta[i]["form"] == "P"],
              "refusal_C": [i for i in S.ref if meta[i]["form"] == "C"], "answer75(non-contrast)": [i for i in S.ans if i not in set(S.con)],
              "contrast25": list(S.con)}
    groups = {"all150": list(S.pf_all), "refusal50": list(S.ref), "answer100": list(S.ans), **groups}
    out = {}
    for g, ids in groups.items():
        la = {i: item_label(pf_a, i) for i in ids}
        lb = {i: item_label(pf_b, i) for i in ids}
        same = sum(la[i] == lb[i] for i in ids)
        clean = [i for i in ids if la[i] != "mixed" and lb[i] != "mixed"]
        pairs = Counter(f"{la[i]}|{lb[i]}" for i in ids)
        out[g] = {"items": len(ids), "agree": same, "agree_pct": AJ.pp(same / len(ids)) if ids else None,
                  "items_without_mixed": len(clean), "agree_without_mixed": sum(la[i] == lb[i] for i in clean),
                  "agree_without_mixed_pct": AJ.pp(sum(la[i] == lb[i] for i in clean) / len(clean)) if clean else None,
                  "mixed_q4": sum(v == "mixed" for v in la.values()), "mixed_bf16": sum(v == "mixed" for v in lb.values()),
                  "pairs(q4|bf16)": dict(sorted(pairs.items()))}
    return {"rule": "빌드마다 k=4 표본 중 3개 이상 같은 결과(R 거부 / C 정답 / W 오답)가 다수 결과, 아니면 mixed. 같음 = 두 빌드 다수 결과가 같음(mixed=mixed 포함)",
            "groups": out}


# ---------------- 한 조건 ----------------
def pf_mats(PF, arm, S):
    pv = [AQ.pf_vec(PF[arm][s], S.ref, S.ans, S.con) for s in PF[arm]]
    return {f: np.vstack([v[f] for v in pv]) for f in AQ.PF_METRICS}


def block(PF, HF, S, ctx, label, with_hf):
    arms = [a for a in STUDENTS if PF.get(a)] + ["T27", "Q4"]
    if with_hf:
        mats = {a: AQ.metric_mats_single(PF, HF, a, tuple(PF[a]), S) for a in arms}
        base_hf = AQ.hf_vec(HF["base"][next(iter(HF["base"]))], S.hf)
        est = AQ.est_all
        dif = AQ.diff_all
    else:
        mats = {a: pf_mats(PF, a, S) for a in arms}
        est = lambda m: {f: AJ.est(m[f]) for f in AQ.PF_METRICS}  # noqa: E731
        dif = lambda x, y: {f: AJ.diff(x[f], y[f]) for f in AQ.PF_METRICS}  # noqa: E731
    out = {"condition": label, "hfinal_items": len(S.hf) if with_hf else None, "arms": {}, "q4_minus_t27": {}, "student_minus_q4": {}}
    for a in arms:
        sd = tuple(PF[a])
        rec = {"name": NAMES[a], "seeds": list(sd), "metrics": est(mats[a]),
               "pf2_correct_refusal_by_form": AG.form_refusal(PF, a, sd, S, ctx["pf_meta"]),
               "pf2_correct_refusal_by_category": AT.refusal_by_category(PF, a, S, ctx["pf_meta"]),
               "pf2_contrast25_over_refusal_by_category": AT.contrast_by_category(PF, a, S, ctx["pf_meta"]),
               "pf2_decomposition_100_seed_mean": AG.pf_decomp(PF, a, sd, S)}
        if with_hf:
            rec["hfinal"] = AQ.single_hf_details(HF, a, sd, S, base_hf, ctx)
            rec["cost_seed_mean"] = AQ.single_cost(PF, HF, a, sd)
        else:
            rec["cost_seed_mean"] = {"pf2": AQ.mean_cost([AQ.cost(PF[a][s]) for s in sd])}
        out["arms"][a] = rec
    out["q4_minus_t27"] = {f: judge(d, BOUNDS[f]) for f, d in dif(mats["Q4"], mats["T27"]).items()}
    for a in arms[:-2]:
        out["student_minus_q4"][f"{a}-Q4"] = dif(mats[a], mats["Q4"])
    out["item_agreement_pf2"] = agreement(PF["Q4"]["q4"], PF["T27"]["t27"], S, ctx["pf_meta"])
    return out


# ---------------- 비용 ----------------
_TOK = {}


def tok(kind):
    if kind not in _TOK:
        from transformers import AutoTokenizer
        _TOK[kind] = AutoTokenizer.from_pretrained(str(AT.MODEL27_DIR)) if kind == "27b" else \
            AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", revision="b968826d9c46dd6066d109eabc6255188de91218")
    return _TOK[kind]


def gen_tokens(p, kind, split):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    rows = d["rows"]
    per_item = [sum(c.get("generated_tokens") or 0 for c in (r.get("hf_calls") or [])) for r in rows]
    calls = [c for r in rows for c in (r.get("hf_calls") or [])]
    out = {"cell": Path(p).name, "items": len(rows), "calls": len(calls), "generated_tokens_per_item_mean": round(float(np.mean(per_item)), 1),
           "generated_tokens_per_item_median": statistics.median(per_item)}
    if kind == "q4":
        es = sum(c.get("eval_seconds") or 0 for c in calls)
        out["decode_tok_s(Σeval_count/Σeval_duration, 요청 하나씩)"] = round(sum(c.get("generated_tokens") or 0 for c in calls) / es, 1) if es else None
        out["prompt_tokens_first_call_median"] = statistics.median([r["hf_calls"][0].get("prompt_tokens") or 0 for r in rows if r.get("hf_calls")])
    else:
        ss = sum(c.get("server_seconds") or 0 for c in calls)
        out["tok_s(Σgenerated/Σcall server_seconds, 동시 요청 묶음)"] = round(sum(c.get("generated_tokens") or 0 for c in calls) / ss, 1) if ss else None
    if split:
        t = tok("27b" if kind in ("q4", "t27") else "8b")
        th, js = defaultdict(int), defaultdict(int)
        for line in Path(d["meta"]["hf"]["raw_out"]).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if "thinking" in r:
                a, b = r["thinking"], r.get("content") or ""
            else:
                text = r["raw_text"]
                a, b = (text.split("</think>", 1) + [""])[:2] if "</think>" in text else (text, "")
            th[r["id"]] += len(t(a, add_special_tokens=False)["input_ids"])
            js[r["id"]] += len(t(b.strip(), add_special_tokens=False)["input_ids"])
        out["thinking_tokens_per_item_median"] = statistics.median(th.values())
        out["json_tokens_per_item_median"] = statistics.median(js.values())
        out["thinking_tokens_per_item_mean"] = round(float(np.mean(list(th.values()))), 1)
        out["json_tokens_per_item_mean"] = round(float(np.mean(list(js.values()))), 1)
        out["split_tokenizer"] = "Qwen/Qwen3.8-27B" if kind in ("q4", "t27") else "Qwen/Qwen3-8B@b968826d"
    return out


def mem_max(gdir, steps=None, cells=None):
    p = gdir / "gpu_mem.jsonl"
    if not p.exists():
        return None
    win = None
    if cells is not None:
        tl = [json.loads(x) for x in (gdir / "timeline.jsonl").read_text(encoding="utf-8").splitlines()]
        st = {e["cell"]: e["t"] for e in tl if e.get("event") == "cell_start"}
        en = {e["cell"]: e["t"] for e in tl if e.get("event") == "cell_end"}
        win = [(datetime.fromisoformat(st[c]), datetime.fromisoformat(en[c])) for c in cells if c in st and c in en]
    best = defaultdict(int)
    for line in p.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if steps is not None and e.get("step") not in steps:
            continue
        if win is not None and not any(a <= datetime.fromisoformat(e["t"]) <= b for a, b in win):
            continue
        for idx, used, *_ in e["gpus"]:
            best[int(idx)] = max(best[int(idx)], int(used))
    return dict(sorted(best.items())) or None


def cost_block(scope):
    out = {"note": "backend가 다르다(Q4 = Ollama, 서버 4벌 × GPU 1장, 서버당 요청 하나씩; BF16 = vLLM TP 2, 서버 2벌 × GPU 2장, 셀 동시 32·서버당 16; 학생 = vLLM GPU 1장). "
                   "직접 비교가 아니라 나란히 둔 기술 수치", "q4": {}, "t27": {}, "students_first_seed": {}}
    for name, p, split in (("pf2_s", [q4_pf_path("s", k) for k in range(1, 5)], False), ("hfinal_s", [JU / "hfinalju_s_q4_s1.json"], True),
                           ("pf2_g1", [q4_pf_path("g1", k) for k in range(1, 5)], False)):
        if all(x.exists() for x in p):
            out["q4"][name] = [gen_tokens(x, "q4", split) for x in p]
    for name, p, split in (("pf2_s", [AT.PF_CELL("s", k) for k in range(1, 5)], False), ("hfinal_s", [AT.JT / "hfinaljt_s_t27_s1.json"], True),
                           ("pf2_g1", [AT.PF_CELL("g1", k) for k in range(1, 5)], False)):
        if all(x.exists() for x in p):
            out["t27"][name] = [gen_tokens(x, "t27", split) for x in p]
    for arm, s in (("base", "base"), ("B2F", AQ.SEEDS["B2F"][0]), ("P9", AQ.SEEDS["P9"][0]), ("V4", AQ.SEEDS["V4"][0]), ("V8", AQ.SEEDS["V8"][0])):
        hp = AQ.hf_paths(arm, s)[0]
        if hp.exists():
            out["students_first_seed"][f"{arm}:{s}"] = gen_tokens(hp, "student", True)
    out["gpu_memory_max_mib"] = {"q4_S_and_G1_steps(GPU 0-3)": mem_max(GJU, steps=("S", "G1")),
                                 "t27_hfinal_s_cell(GPU 0-3)": mem_max(GJT, cells=["hfinaljt_s_t27_s1"])}
    sp = {}
    for port in (11441, 11442, 11443, 11444):
        f = GJU / f"server_{port}.json"
        if f.exists():
            sm = json.loads(f.read_text(encoding="utf-8"))
            sp[str(port)] = {"gpu_index": sm.get("gpu_index"), "nvidia_smi_after_load": sm.get("nvidia_smi_after_load"), "context_length": sm.get("context_length"),
                             "size": (sm.get("api_ps_after_load") or [{}])[0].get("size"), "size_vram": (sm.get("api_ps_after_load") or [{}])[0].get("size_vram")}
    out["q4_server_after_load"] = sp
    out["weights"] = {"q4_gguf_model_blob_bytes": 16810714464, "q4_projector_blob_bytes(vision, 안 씀)": 931146016, **AT.weights()}
    out["hfinal_scope"] = scope
    return out


def check_t27_vs_jt(res_s, scope):
    jt = json.loads((HERE / "jt_results.json").read_text(encoding="utf-8"))
    a = jt["conditions"]["S"]["arms"]["T27"]["metrics"]
    b = res_s["arms"]["T27"]["metrics"]
    keys = AQ.PF_METRICS + (("hfinal_accuracy", "hfinal_over_refusal") if scope == "full3000" else ())
    bad = [k for k in keys if a[k]["mean_pct"] != b[k]["mean_pct"] or a[k]["ci95_pct"] != b[k]["ci95_pct"]]
    if bad:
        raise SystemExit(f"BF16 S values differ from jt_results.json: {bad}")
    return {"compared": list(keys), "all_equal": True}


def smoke_block():
    sc = GJU / "scope.json"
    if not sc.exists():
        return None
    rec = json.loads(sc.read_text(encoding="utf-8"))
    p = JU / "smoke/hdev100ju_s_q4_s1.json"
    if p.exists():
        rec["cell"] = {"file": str(p.relative_to(ROOT)), "sha256": sha(p), "validity": ju_validity(p)}
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ctx = AQ.setup()
    S_full = AQ.Sets(ctx)
    scope = json.loads((GJU / "scope.json").read_text(encoding="utf-8"))["scope"]
    S = S_full if scope == "full3000" else AT.restrict(S_full, SUBSET.read_text(encoding="utf-8").strip().split(","), ctx)
    res = {"label": LAB, "decision": 272, "plan": "sft_dpo_inventory/pilot_010/PLAN_JU.md", "names": NAMES, "hfinal_scope": scope, "hfinal_items": len(S.hf),
           "bootstrap": {"reps": AJ.REPS, "rng": f"default_rng({AJ.RNG_SEED}) per statistic", "method": "학생 U1(문항 공유, arm마다 seed 재추출), 교사 두 빌드는 문항만"},
           "similarity_rule": {"bounds_pp": BOUNDS, "order": "CI 전체가 ±폭 안 → 유사; 아니고 CI가 0을 벗어남 → 다름; 그 밖 → 판단할 수 없음; 지표마다 따로"},
           "smoke": smoke_block(), "conditions": {}, "cells_q4": [], "validity_q4": []}
    # ---- S ----
    PFs, HFs, cells_s = AQ.load_arms(ctx, {**AQ.SEEDS, "V8new": AQ.V8_NEW, "base": ("base",)})
    PFs["V8"] = {**PFs["V8"], **PFs.pop("V8new")}
    HFs["V8"] = {**HFs["V8"], **HFs.pop("V8new")}
    res["check_sampling_single_means_vs_jp_posthoc"] = AQ.check_against_jp({k: AQ.metric_mats_single(PFs, HFs, k, AQ.SEEDS[k], S_full) for k in AQ.SEEDS},
                                                                         AQ.metric_mats_single(PFs, HFs, "base", ("base",), S_full))
    AG.add_pool(PFs, HFs)
    pf, hf, _, vt = AT.load_t27(ctx, "s")
    PFs["T27"], HFs["T27"] = pf, hf
    res["validity_t27"] = vt
    pf, hf, c, v, miss = load_q4(ctx, "s")
    if miss:
        raise SystemExit(f"Q4 S cells missing: {miss}")
    PFs["Q4"], HFs["Q4"] = pf, hf
    res["cells_q4"] += c
    res["validity_q4"] += v
    res["conditions"]["S"] = block(PFs, HFs, S, ctx, "S (T 0.6, top-p 0.95, top-k 20): 학생 = J·JP·JQ 셀, BF16 = JT S 셀", True)
    res["check_t27_S_vs_jt_results"] = check_t27_vs_jt(res["conditions"]["S"], scope)
    # ---- G1(선택: Q4 G1 PF2가 있을 때만, PF2만) ----
    pfq, _, c, v, miss = load_q4(ctx, "g1")
    if miss:
        res["conditions"]["G1"] = {"measured": False, "missing": miss}
    else:
        PFg, HFg, _, _, missing_st = AG.load_cond(ctx, "g1")
        AG.add_pool(PFg, HFg)
        pf, _, _, vt = AT.load_t27(ctx, "g1")
        PFg["T27"], PFg["Q4"] = pf, pfq
        res["cells_q4"] += c
        res["validity_q4"] += v
        res["conditions"]["G1"] = {"measured": True, **block(PFg, None, S, ctx, "G1 (T 0.2, top-p 0.95, top-k 20), PF2만: 학생 = JG 셀, BF16 = JT G1 셀", False),
                                   "missing_students": missing_st}
    res["cost"] = cost_block(scope)
    rr = GJU / "RERUNS_JU.json"
    res["reruns"] = json.loads(rr.read_text(encoding="utf-8")) if rr.exists() else {"reruns": {}}
    res["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    res["inputs"] = {"pf2_gold_sha256": sha(AJ.PF_GOLD), "pf2_meta_sha256": sha(AJ.PF_META), "hfinal_sha256": sha(ROOT / AJ.HF_GOLD), "analysis_sha256": sha(__file__),
                     "subset_ids_sha256": sha(SUBSET), "analyze_jt_sha256": sha(AT.__file__), "jt_results_sha256": sha(HERE / "jt_results.json"),
                     "analyze_jg_sha256": sha(AG.__file__), "analyze_jq_sha256": sha(AQ.__file__), "analyze_j_sha256": sha(AJ.__file__)}
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("written", a.out, "scope", scope, "hfinal_items", len(S.hf))


if __name__ == "__main__":
    main()
