# -*- coding: utf-8 -*-
"""pilot_010 JV 집계(결정 273, PLAN_JV 4절). **학생 4비트 빌드 참고 측정(판정 아님) — PF2·H-final의 추가 사용.** 측정 전에 커밋한다. 모델 호출 없음.
학생 Q4 = Ollama 0.40.6, 공식 방식 Q4_K_M(attn_v F16) + hfthink TEMPLATE(``geoflow-jv-…``). 학생 BF16 = vLLM 셀(S: J·JP·JQ). 교사 Q4 = JU 셀(Ollama qwen3.8:27b).
``analyze_j``·``analyze_jp``·``analyze_jq``·``analyze_jg``·``analyze_jt``·``analyze_ju``는 고치지 않고 함수를 불러 쓴다. **PF2 질문·정답 호출·응답은 출력·저장하지 않는다**.

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/results/analyze_jv.py --out sft_dpo_inventory/pilot_010/results/jv_results.json

- H-final = JT 층화 1,000(``jt/hfinal_subset1000_ids.txt``, ``AT.restrict``). 교사 Q4·학생 BF16도 같은 1,000문항으로 다시 계산.
- 학생 Q4 arm: base, SFT(B2F), RR+NM4(V4), RR+NM8(V8, 선택: 고정 순서의 앞에서부터 PF2 4셀·H-final이 모두 있는 seed), RR+NM 12 seed(V4 5 + V8 7이 모두 있을 때만).
  지표 = PF2 올바른 거부·과잉 거부 100·근접 25·정답률, H-final 정답률·과잉 거부, CI = U1 bootstrap 10,000(``analyze_j.boot``).
- 같은 어댑터 Q4 − BF16(seed·문항 짝): seed별 (Q4 − BF16) 문항 값 행렬에 ``analyze_j.est``(seed·문항 함께 재추출). base는 BF16 PF2 k=1–4·H-final s1과 짝.
  짝의 회차 seed가 같은지 셀 meta로 확인(다르면 멈춤). 판정 문구 없음.
- Q4 안 arm 차이(``analyze_j.diff``): RR+NM4 − SFT, RR+NM4 − base, SFT − base(+ RR+NM 12 seed가 있으면 같은 셋). 같은 차이의 BF16 값을 나란히.
- 학생 Q4 − 교사 Q4(JU 표 3 방식). 회복 비율 없음.
- 세부: 형별(M·P·C)·범주별 올바른 거부, 근접 25 범주별 과잉 거부, 결과 분해(PF2 100·H-final), 도구 유형별, template_group 붕괴(같은 빌드의 base 대비).
- 비용: 셀마다 호출 수·decode tok/s(Σeval_count/Σeval_duration)·생성 token(H-final thinking / JSON, 8B tokenizer)·측정 중 GPU 메모리 최대(작업 창).
- 지연·자원: 지연 셀 3개(교사 Q4·base Q4·RR+NM4 o101 Q4, context 17,408), 참고로 ``jt_results.json`` latency(BF16 vLLM, JT 표 4).
- 검사: 학생 BF16 S 단일 seed 평균 = ``jp_posthoc.json``(전체 3,000), 교사 Q4 S 여섯 지표(전체 3,000) = ``ju_results.json``, JV 셀 유효성.
"""
import argparse
import hashlib
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
INV = ROOT / "sft_dpo_inventory"
for p in (ROOT, HERE, INV / "pilot_006/gates", INV / "pilot_006/post", INV / "pilot_009/gates", INV / "ablation_012/analysis", INV / "pilot_009/protected_final_v2",
          INV / "pilot_010/jv"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import analyze_j as AJ  # noqa: E402
import analyze_jg as AG  # noqa: E402
import analyze_jq as AQ  # noqa: E402
import analyze_jt as AT  # noqa: E402
import analyze_ju as AU  # noqa: E402
import models_jv as M  # noqa: E402
import validity_j as VJ  # noqa: E402

JV = INV / "pilot_010/cells/JV"
GJV = INV / "pilot_010/gpu/JV"
JVD = INV / "pilot_010/jv"
SUBSET = INV / "pilot_010/jt/hfinal_subset1000_ids.txt"
METRICS = AQ.METRICS
Q4ARMS = ("base", "B2F", "V4", "V8", "RRNM12")
NAMES = {"base": "base", "B2F": "SFT", "V4": "RR+NM4", "V8": "RR+NM8", "RRNM12": "RR+NM 12 seed (RR+NM4 5 + RR+NM8 7)", "T27Q4": "교사 Q4 (Ollama qwen3.8:27b)"}
LAB = ("학생 4비트 빌드 참고 측정(판정 아님); PF2·H-final 추가 사용; 학생 Q4 = Ollama 0.40.6 공식 방식 Q4_K_M + hfthink, 학생 BF16 = vLLM(J·JP·JQ), "
       "교사 Q4 = JU Ollama qwen3.8:27b; H-final = JT 층화 1,000")
EXTRA = {"min_p": 0.0, "presence_penalty": 0.0, "repeat_penalty": 1.0}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def tag(arm, s):
    return "base" if arm == "base" else f"{M.ARM_KEY[arm]}_{s}"


def q4_pf(arm, s, k):
    return AJ.PF_CELLS / f"pf2jv_{tag(arm, s)}_q4_s{k}.json"


def q4_hf(arm, s):
    return JV / f"hfinaljv_{tag(arm, s)}_q4_s1.json"


def round_seed(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))["meta"]["hf"]["decoding"]["round_seed"]


def model_of(arm, s):
    return M.model(arm, s)


# ---------------- 유효성 ----------------
def job_of(cell_name):
    for f in sorted((GJV / "jobs").glob("*.json")):
        if f.name.endswith(".server.json"):
            continue
        j = json.loads(f.read_text(encoding="utf-8"))
        for ses in j.get("sessions", []):
            if any(c["cell"] == cell_name and c["rc"] == 0 for c in ses.get("cells", [])):
                return j, ses
    return None, None


def jv_validity(p, digest):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    m, rows = d["meta"], d["rows"]
    calls = [c for r in rows for c in (r.get("hf_calls") or [])]
    jv, ol = m.get("jv") or {}, m.get("ollama") or {}
    j, ses = job_of(Path(p).stem)
    sl = (ses or {}).get("server_log") or {}
    return {**VJ.check(str(p)), "flashinfer": "n/a(Ollama)", "digest_ok": m.get("model_digest") == digest, "ollama_version": m.get("ollama_version"),
            "think_true": (ol.get("request_example(no message content)") or {}).get("think") is True,
            "num_predict_all_8192": all((c.get("options_sent") or {}).get("num_predict") == 8192 for c in calls),
            "extra_options_all_sent": all(all((c.get("options_sent") or {}).get(k) == v for k, v in EXTRA.items()) for c in calls),
            "render_all_equal": ol.get("render_all_equal"), "render_checks": len(ol.get("render_checks") or []),
            "sessions": jv.get("sessions"), "gpu_index": jv.get("gpu_index"), "ps_checks": jv.get("ps_checks"), "ps_all_100_gpu": jv.get("ps_all_100_gpu"),
            "other_process_seen": jv.get("other_process_seen"), "context_length_seen": jv.get("context_length_seen"), "wall_s": jv.get("wall_seconds"),
            "job": (j or {}).get("job"), "session": (ses or {}).get("session"), "sampler_blocks_session": sl.get("sampler_blocks"),
            "sampler_all_expected_session": sl.get("sampler_all_expected"), "truncation_lines_session": len(sl.get("truncation_lines") or []),
            "server_error_rows_any": sum(1 for r in rows if r.get("error_code") == "UNHANDLED_EXCEPTION")}


# ---------------- 읽기 ----------------
def load_q4_students(ctx):
    """→ PF[arm][seed] = [4 표본], HF[arm][seed] = [1 표본], 셀 정보, 유효성, arm별 seed."""
    PF, HF, cells, validity, seeds = {}, {}, [], [], {}
    plan = {"base": ("base",), "B2F": M.SFT_SEEDS, "V4": M.V4_SEEDS, "V8": M.V8_SEEDS}
    for arm, ss in plan.items():
        have = []
        for s in ss:
            ok = all(q4_pf(arm, s, k).exists() for k in range(1, 5)) and q4_hf(arm, s).exists()
            if not ok:
                if arm == "V8":
                    break          # 선택 arm: 고정 순서의 앞에서부터 이어진 seed만(PLAN_JV 3절)
                continue
            have.append(s)
        if not have:
            continue
        seeds[arm] = tuple(have)
        PF[arm], HF[arm] = {}, {}
        for s in have:
            dg = json.loads((JVD / "registration" / f"{model_of(arm, s)['name']}.json").read_text(encoding="utf-8"))["digest"]
            PF[arm][s] = []
            for k in range(1, 5):
                rec, info = AQ.load_cell(q4_pf(arm, s, k), "pf2", ctx)
                PF[arm][s].append(rec)
                cells.append(info)
                validity.append(jv_validity(q4_pf(arm, s, k), dg))
            rec, info = AQ.load_cell(q4_hf(arm, s), "hfinal", ctx)
            HF[arm][s] = [rec]
            cells.append(info)
            validity.append(jv_validity(q4_hf(arm, s), dg))
    if "V4" in seeds and "V8" in seeds and len(seeds["V4"]) == 5 and len(seeds["V8"]) == 7:
        AG.add_pool(PF, HF)
        seeds["RRNM12"] = tuple(PF["RRNM12"])
    return PF, HF, cells, validity, seeds


def seed_pairs_check(seeds):
    """Q4 셀과 짝 BF16 셀의 회차 seed가 같은지."""
    bad, n = [], 0
    for arm, ss in seeds.items():
        if arm == "RRNM12":
            continue
        for s in ss:
            bf_pf = AQ.pf_paths("V8" if arm == "V8" and s not in AQ.SEEDS["V8"] else arm, s)[:4]
            bf_hf = AQ.hf_paths("V8new" if arm == "V8" and s not in AQ.SEEDS["V8"] else arm, s)[:1]
            for k in range(4):
                n += 1
                if round_seed(q4_pf(arm, s, k + 1)) != round_seed(bf_pf[k]):
                    bad.append(f"{arm}:{s}:pf{k + 1}")
            n += 1
            if round_seed(q4_hf(arm, s)) != round_seed(bf_hf[0]):
                bad.append(f"{arm}:{s}:hf")
    if bad:
        raise SystemExit(f"round seeds differ: {bad}")
    return {"pairs_checked": n, "all_equal": True}


# ---------------- 계산 ----------------
def mats(PF, HF, arm, seeds, S):
    return AQ.metric_mats_single(PF, HF, arm, seeds, S)


def paired(Mq, Mb):
    out = {}
    for f in METRICS:
        D = Mq[f] - Mb[f]
        e = AJ.est(D)
        out[f] = {"diff_pp": e["mean_pct"], "ci95_pp": e["ci95_pct"], "per_seed_diff_pp": e["per_seed_pct"], "seeds": e["seeds"]}
    return out


def details(PF, HF, arm, S, ctx, base_hf):
    sd = tuple(PF[arm])
    return {"seeds": list(sd), "pf2_correct_refusal_by_form": AG.form_refusal(PF, arm, sd, S, ctx["pf_meta"]),
            "pf2_correct_refusal_by_category": AT.refusal_by_category(PF, arm, S, ctx["pf_meta"]),
            "pf2_contrast25_over_refusal_by_category": AT.contrast_by_category(PF, arm, S, ctx["pf_meta"]),
            "pf2_decomposition_100_seed_mean": AG.pf_decomp(PF, arm, sd, S),
            "hfinal": AQ.single_hf_details(HF, arm, sd, S, base_hf, ctx), "cost_seed_mean": AQ.single_cost(PF, HF, arm, sd)}


_TOK = {}


def tok(kind):
    if kind not in _TOK:
        from transformers import AutoTokenizer
        _TOK[kind] = AutoTokenizer.from_pretrained(str(AT.MODEL27_DIR)) if kind == "27b" else \
            AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", revision="b968826d9c46dd6066d109eabc6255188de91218")
    return _TOK[kind]


def cell_cost(p, split, tkind="8b"):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    rows = d["rows"]
    calls = [c for r in rows for c in (r.get("hf_calls") or [])]
    per_item = [sum(c.get("generated_tokens") or 0 for c in (r.get("hf_calls") or [])) for r in rows]
    es = sum(c.get("eval_seconds") or 0 for c in calls)
    out = {"cell": Path(p).name, "items": len(rows), "calls": len(calls), "calls_per_item": round(len(calls) / len(rows), 3),
           "truncated_calls": sum(c.get("done_reason") == "length" for c in calls),
           "generated_tokens_per_item_mean": round(float(np.mean(per_item)), 1), "generated_tokens_per_item_median": statistics.median(per_item),
           "decode_tok_s": round(sum(c.get("generated_tokens") or 0 for c in calls) / es, 1) if es else None,
           "prompt_tokens_first_call_median": statistics.median([r["hf_calls"][0].get("prompt_tokens") or 0 for r in rows if r.get("hf_calls")]),
           "wall_seconds": (d["meta"].get("jv") or {}).get("wall_seconds"), "gpu_index": (d["meta"].get("jv") or {}).get("gpu_index")}
    if split:
        t = tok(tkind)
        th, js = defaultdict(int), defaultdict(int)
        for line in Path(d["meta"]["hf"]["raw_out"]).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            th[r["id"]] += len(t(r.get("thinking") or "", add_special_tokens=False)["input_ids"])
            js[r["id"]] += len(t((r.get("content") or "").strip(), add_special_tokens=False)["input_ids"])
        out.update({"thinking_tokens_per_item_median": statistics.median(th.values()), "json_tokens_per_item_median": statistics.median(js.values()),
                    "thinking_tokens_per_item_mean": round(float(np.mean(list(th.values()))), 1), "json_tokens_per_item_mean": round(float(np.mean(list(js.values()))), 1),
                    "split_tokenizer": "Qwen/Qwen3.8-27B" if tkind == "27b" else "Qwen/Qwen3-8B@b968826d"})
    return out


def windows():
    tl = [json.loads(x) for x in (GJV / "timeline.jsonl").read_text(encoding="utf-8").splitlines()] if (GJV / "timeline.jsonl").exists() else []
    st = {e["cell"]: (e["t"], e["gpu"]) for e in tl if e.get("event") == "cell_start"}
    en = {e["cell"]: e["t"] for e in tl if e.get("event") == "cell_end" and e.get("rc") == 0}
    return {c: (datetime.fromisoformat(st[c][0]), datetime.fromisoformat(en[c]), st[c][1]) for c in en if c in st}


def mem_in(win, path):
    if not path.exists() or win is None:
        return None
    a, b, g = win
    best = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if a <= datetime.fromisoformat(e["t"]) <= b:
            for idx, used, *_ in e["gpus"]:
                if int(idx) == int(g):
                    best = max(best, int(used))
    return best or None


def cost_block(seeds):
    W = windows()
    out = {"note": "Ollama 0.40.6, 서버 한 벌·GPU 한 장·요청 하나씩(셀마다); tok/s = Σeval_count/Σeval_duration(prompt 처리 제외)", "q4_students": {}}
    for arm, ss in seeds.items():
        if arm == "RRNM12":
            continue
        for s in ss:
            key = f"{arm}:{s}"
            ent = {"pf2": [cell_cost(q4_pf(arm, s, k), False) for k in range(1, 5)], "hfinal": cell_cost(q4_hf(arm, s), True)}
            ent["gpu_memory_max_mib_pf2"] = max([x for x in (mem_in(W.get(q4_pf(arm, s, k).stem), GJV / "gpu_mem.jsonl") for k in range(1, 5)) if x] or [0]) or None
            ent["gpu_memory_max_mib_hfinal"] = mem_in(W.get(q4_hf(arm, s).stem), GJV / "gpu_mem.jsonl")
            out["q4_students"][key] = ent
    out["weights_q4_bytes"] = {m["name"]: json.loads((JVD / "receipts" / f"{m['name']}.json").read_text(encoding="utf-8"))["q4"]["bytes"]
                               for m in M.all_models() if (JVD / "receipts" / f"{m['name']}.json").exists()}
    return out


def latency_block():
    W = windows()
    cells = {"teacher_q4": ("latjv_t27q4_s1", "27b", C_TEACHER_W), "base_q4": ("latjv_base_q4_s1", "8b", None), "v4_o101_q4": ("latjv_v4_o101_q4_s1", "8b", None)}
    out = {"rule": "결정 113 방식: 고정 30문항, 동시 1, S, 서버 한 벌·GPU 한 장(GPU 0), context 17,408(OLLAMA_CONTEXT_LENGTH), 다른 GPU 작업 없음", "cells": {}}
    for k, (name, tkind, wbytes) in cells.items():
        p = JV / "latency" / f"{name}.json"
        if not p.exists():
            out["cells"][k] = None
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        rows = d["rows"]
        calls = [c for r in rows for c in r["hf_calls"]]
        model_s = [sum(c.get("server_seconds") or 0 for c in r["hf_calls"]) for r in rows]
        wall = [(datetime.fromisoformat(r["finished_at"]) - datetime.fromisoformat(r["started_at"])).total_seconds() for r in rows]
        cc = cell_cost(p, True, tkind)
        j, ses = job_of(name)
        sl = (ses or {}).get("server_log") or {}
        srv = (ses or {}).get("server") or {}
        if wbytes is None:
            wbytes = json.loads((JVD / "receipts" / f"{'jv-qwen3-8b-base' if k == 'base_q4' else 'jv-v4-o101'}.json").read_text(encoding="utf-8"))["q4"]["bytes"]
        out["cells"][k] = {"cell": name, "items": len(rows), "model": d["meta"]["model"], "digest": d["meta"]["model_digest"],
                           "median_model_seconds": round(statistics.median(model_s), 2), "p95_model_seconds": round(float(np.percentile(model_s, 95)), 2),
                           "median_item_wall_seconds": round(statistics.median(wall), 2), "p95_item_wall_seconds": round(float(np.percentile(wall, 95)), 2),
                           "median_generated_tokens": cc["generated_tokens_per_item_median"], "median_thinking_tokens": cc["thinking_tokens_per_item_median"],
                           "median_json_tokens": cc["json_tokens_per_item_median"], "decode_tok_s": cc["decode_tok_s"],
                           "median_input_tokens": statistics.median([r["hf_calls"][0].get("prompt_tokens") or 0 for r in rows]), "truncated_calls": cc["truncated_calls"],
                           "weights_bytes": wbytes, "context_length_seen": (d["meta"].get("jv") or {}).get("context_length_seen"),
                           "gpu_memory_after_load": srv.get("nvidia_smi_after_load"), "api_ps_after_load": srv.get("api_ps_after_load"),
                           "gpu_memory_max_mib_during_cell(5s)": mem_in(W.get(name), GJV / "latency_mem.jsonl"),
                           "speculative_decoding": sl.get("speculative"), "llama_server_cmd": sl.get("llama_server_cmd"),
                           "sampler_all_expected": sl.get("sampler_all_expected"), "render_all_equal": d["meta"]["ollama"]["render_all_equal"],
                           "tokenizer": "Qwen/Qwen3.8-27B" if tkind == "27b" else "Qwen/Qwen3-8B@b968826d"}
    jt = json.loads((HERE / "jt_results.json").read_text(encoding="utf-8"))
    out["bf16_vllm_reference_jt_table4"] = jt.get("latency_resources")
    return out


C_TEACHER_W = 16810714464 + 931146016     # JU: GGUF 모델 blob + vision projector blob(함께 올라감)


def stage_blocks():
    out = {}
    for n in ("render_check", "render_split", "scope"):
        f = GJV / f"{n}.json"
        out[n] = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    conv = {}
    for m in M.all_models():
        f, g = JVD / "receipts" / f"{m['name']}.json", JVD / "registration" / f"{m['name']}.json"
        if f.exists():
            r = json.loads(f.read_text(encoding="utf-8"))
            conv[m["name"]] = {"adapter_sha256_ok": r.get("adapter_sha256_ok"), "q4_sha256": r["q4"]["sha256"], "q4_bytes": r["q4"]["bytes"],
                               "types_equal_official": r.get("types_equal_official"), "type_counts": r["types"]["type_counts"],
                               "equals_decision75_base_official": r["q4"].get("equals_decision75_base_official"), "deleted_intermediates": len(r.get("deleted_intermediates") or [])}
        if g.exists():
            x = json.loads(g.read_text(encoding="utf-8"))
            mc = x.get("manifest_check") or {}
            conv.setdefault(m["name"], {}).update({"ollama": x["model"], "digest": x["digest"], "template_layer_equals_sent_hfthink": mc.get("template_layer_equals_sent_hfthink"),
                                                   "config_has_renderer_or_parser": mc.get("config_has_renderer_or_parser")})
    out["conversion_registration"] = conv
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ctx = AQ.setup()
    S_full = AQ.Sets(ctx)
    S = AT.restrict(S_full, SUBSET.read_text(encoding="utf-8").strip().split(","), ctx)
    res = {"label": LAB, "decision": 273, "plan": "sft_dpo_inventory/pilot_010/PLAN_JV.md", "names": NAMES, "hfinal_items": len(S.hf),
           "bootstrap": {"reps": AJ.REPS, "rng": f"default_rng({AJ.RNG_SEED}) per statistic", "method": "U1(문항 공유, arm 안 seed 재추출); Q4 − BF16 = seed별 차이 행렬(seed·문항 함께 재추출)"}}
    res.update(stage_blocks())
    # ---- 학생 BF16 ----
    PFb, HFb, _ = AQ.load_arms(ctx, {**AQ.SEEDS, "V8new": AQ.V8_NEW, "base": ("base",)})
    PFb["V8"] = {**PFb["V8"], **PFb.pop("V8new")}
    HFb["V8"] = {**HFb["V8"], **HFb.pop("V8new")}
    res["check_bf16_single_means_vs_jp_posthoc"] = AQ.check_against_jp({k: AQ.metric_mats_single(PFb, HFb, k, AQ.SEEDS[k], S_full) for k in AQ.SEEDS},
                                                                     AQ.metric_mats_single(PFb, HFb, "base", ("base",), S_full))
    AG.add_pool(PFb, HFb)
    # ---- 교사 Q4(JU) ----
    pf, hf, _, vq, miss = AU.load_q4(ctx, "s")
    if miss:
        raise SystemExit(f"JU cells missing {miss}")
    PFt, HFt = {"T27Q4": {"q4": pf["q4"]}}, {"T27Q4": {"q4": hf["q4"]}}
    full_t = AQ.est_all(AQ.metric_mats_single(PFt, HFt, "T27Q4", ("q4",), S_full))
    ju = json.loads((HERE / "ju_results.json").read_text(encoding="utf-8"))["conditions"]["S"]["arms"]["Q4"]["metrics"]
    bad = [f for f in METRICS if full_t[f]["mean_pct"] != ju[f]["mean_pct"] or full_t[f]["ci95_pct"] != ju[f]["ci95_pct"]]
    if bad:
        raise SystemExit(f"teacher Q4 full-set values differ from ju_results.json: {bad}")
    res["check_teacher_q4_full_vs_ju_results"] = {"compared": list(METRICS), "all_equal": True}
    # ---- 학생 Q4 ----
    PFq, HFq, cells, validity, seeds = load_q4_students(ctx)
    res["cells_q4"], res["validity_q4"], res["q4_seeds"] = cells, validity, {k: list(v) for k, v in seeds.items()}
    res["seed_pairs_check"] = seed_pairs_check(seeds)
    arms = [x for x in Q4ARMS if x in seeds]
    Mq = {x: mats(PFq, HFq, x, seeds[x], S) for x in arms}
    Mb_tab = {x: mats(PFb, HFb, x, tuple(PFb[x]) if x in ("base", "RRNM12") else seeds[x], S) for x in arms}
    Mt = mats(PFt, HFt, "T27Q4", ("q4",), S)
    # 짝: base는 BF16 k=1–4·s1만
    PFb_pair = {x: ({"base": PFb["base"]["base"][:4]} if x == "base" else {s: PFb[x][s] for s in seeds[x]}) for x in arms}
    HFb_pair = {x: ({"base": HFb["base"]["base"][:1]} if x == "base" else {s: HFb[x][s] for s in seeds[x]}) for x in arms}
    res["table1"] = {"q4": {x: {"name": NAMES[x], "seeds": list(seeds[x]), "metrics": AQ.est_all(Mq[x])} for x in arms},
                     "bf16": {x: {"name": NAMES[x], "seeds": list(PFb[x]) if x in ("base", "RRNM12") else list(seeds[x]), "metrics": AQ.est_all(Mb_tab[x])} for x in arms},
                     "teacher_q4": {"name": NAMES["T27Q4"], "metrics": AQ.est_all(Mt)}}
    res["table2_q4_minus_bf16_paired"] = {}
    for x in arms:
        mq = Mq[x]
        mb = mats({x: PFb_pair[x]}, {x: HFb_pair[x]}, x, tuple(PFb_pair[x]), S)
        res["table2_q4_minus_bf16_paired"][x] = {"name": NAMES[x], "seeds": list(PFb_pair[x]), "pairs": "base: BF16 PF2 k=1–4·H-final s1" if x == "base" else "같은 seed",
                                                 "bf16_pair_metrics": AQ.est_all(mb), "diff": paired(mq, mb)}
    pairs = [("V4", "B2F"), ("V4", "base"), ("B2F", "base")] + ([("RRNM12", "B2F"), ("RRNM12", "base")] if "RRNM12" in arms else [])
    res["table3_q4_arm_differences"] = {f"{x}-{y}": {"q4": AQ.diff_all(Mq[x], Mq[y]), "bf16": AQ.diff_all(Mb_tab[x], Mb_tab[y])} for x, y in pairs if x in arms and y in arms}
    res["table4_student_q4_minus_teacher_q4"] = {f"{x}-T27Q4": AQ.diff_all(Mq[x], Mt) for x in arms}
    base_hf_q4 = AQ.hf_vec(HFq["base"]["base"], S.hf)
    base_hf_b = AQ.hf_vec(HFb["base"]["base"], S.hf)
    res["table6_details"] = {"q4": {x: details(PFq, HFq, x, S, ctx, base_hf_q4) for x in arms},
                             "bf16": {x: details({x: PFb[x] if x in ("base", "RRNM12") else {s: PFb[x][s] for s in seeds[x]}},
                                                 {x: HFb[x] if x in ("base", "RRNM12") else {s: HFb[x][s] for s in seeds[x]}}, x, S, ctx, base_hf_b) for x in arms},
                             "teacher_q4": details(PFt, HFt, "T27Q4", S, ctx, base_hf_q4)}
    res["cost"] = cost_block(seeds)
    res["table5_latency"] = latency_block()
    rr = GJV / "RERUNS_JV.json"
    res["reruns"] = json.loads(rr.read_text(encoding="utf-8")) if rr.exists() else {"reruns": {}}
    res["jobs"] = {f.stem: {k: v for k, v in json.loads(f.read_text(encoding="utf-8")).items() if k in ("job", "gpu", "status", "started", "finished")}
                   for f in sorted((GJV / "jobs").glob("*.json")) if not f.name.endswith(".server.json")}
    res["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    res["inputs"] = {"pf2_gold_sha256": sha(AJ.PF_GOLD), "pf2_meta_sha256": sha(AJ.PF_META), "hfinal_sha256": sha(ROOT / AJ.HF_GOLD), "subset_ids_sha256": sha(SUBSET),
                     "analysis_sha256": sha(__file__), "ju_results_sha256": sha(HERE / "ju_results.json"), "jt_results_sha256": sha(HERE / "jt_results.json"),
                     "analyze_ju_sha256": sha(AU.__file__), "analyze_jt_sha256": sha(AT.__file__), "analyze_jg_sha256": sha(AG.__file__), "analyze_jq_sha256": sha(AQ.__file__),
                     "analyze_j_sha256": sha(AJ.__file__)}
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("written", a.out, "arms", arms, "hfinal_items", len(S.hf))


if __name__ == "__main__":
    main()
