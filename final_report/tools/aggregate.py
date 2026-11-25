# -*- coding: utf-8 -*-
"""최종 결과보고서 집계(새 파일, CPU). 자체시험 원자료(final_report/logs)와 기존 실험 기록(sft_dpo_inventory)을 읽어
latency_results.csv · vram_results.csv · summary.json · figures/*.svg 를 만든다. 수치는 모두 파일에서 읽으며 손으로 넣지 않는다.

    python3 final_report/tools/aggregate.py
"""
import csv
import json
import random
import re
import statistics as st
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FR = ROOT / "final_report"
LAT = FR / "logs/latency"
VR = FR / "logs/vram"
FIG = FR / "figures"
INV = ROOT / "sft_dpo_inventory"

CELLS = [  # key, file label, 설명
    ("A", "A_hf_bf16_base", "초기: HF transformers BF16 · base"),
    ("B", "B_vllm_bf16_fi_base", "vLLM BF16 + FlashInfer · base"),
    ("C", "C_vllm_fp8_fi_base", "vLLM FP8 + FlashInfer · base"),
    ("D", "D_vllm_bf16_fi_v4", "vLLM BF16 + FlashInfer · LoRA 학습 모델"),
    ("E", "E_vllm_fp8_fi_v4", "최적화: vLLM FP8 + FlashInfer · LoRA 학습 모델"),
]
VCFG = [
    ("M1", "M1_hf_bf16_default", "HF BF16 · PyTorch allocator 기본"),
    ("M2", "M2_hf_bf16_expandable", "HF BF16 · expandable_segments"),
    ("M3", "M3_vllm_bf16_fi_base", "vLLM BF16 + FlashInfer · PagedAttention"),
    ("M4", "M4_vllm_fp8_fi_v4", "vLLM FP8 + FlashInfer + LoRA · PagedAttention"),
]


def mean(x):
    return sum(x) / len(x) if x else None


def pct(x, q):
    s = sorted(x)
    k = (len(s) - 1) * q
    f = int(k)
    return s[f] + (s[min(f + 1, len(s) - 1)] - s[f]) * (k - f)


def boot_improvement(a, b, n=10000, seed=20261124):
    """문항 쌍 bootstrap: (mean(a) − mean(b)) / mean(a) × 100 의 95% 구간."""
    rnd = random.Random(seed)
    m = len(a)
    vals = []
    for _ in range(n):
        idx = [rnd.randrange(m) for _ in range(m)]
        ma = sum(a[i] for i in idx) / m
        mb = sum(b[i] for i in idx) / m
        vals.append((ma - mb) / ma * 100)
    vals.sort()
    return [round(vals[int(0.025 * n)], 2), round(vals[int(0.975 * n) - 1], 2)]


def r2(x, k=2):
    return None if x is None else round(x, k)


# ---------------------------------------------------------------- latency (자체시험)
def latency():
    out_rows, cells = [], {}
    for key, label, desc in CELLS:
        p = LAT / f"{label}.json"
        if not p.exists():
            cells[key] = {"label": label, "description": desc, "status": "측정 파일 없음"}
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        rows = d["rows"]
        e2e = [r["e2e_ms"] / 1000 for r in rows]
        mdl = [r["model_ms"] / 1000 for r in rows]
        non = [r["non_model_ms"] / 1000 for r in rows]
        gen = [sum(t or 0 for t in r["generated_tokens"]) for r in rows]
        sm = d["meta"].get("server_meta") or {}
        cells[key] = {
            "label": label, "description": desc, "items": len(rows), "warmup_items": len(d["warmup"]),
            "load_seconds_client": d["meta"]["load_seconds"], "warmup_seconds": d["meta"]["warmup_seconds"],
            "e2e_mean_s": r2(mean(e2e), 3), "e2e_median_s": r2(st.median(e2e), 3), "e2e_p95_s": r2(pct(e2e, 0.95), 3),
            "e2e_min_s": r2(min(e2e), 3), "e2e_max_s": r2(max(e2e), 3),
            "model_mean_s": r2(mean(mdl), 3), "non_model_mean_s": r2(mean(non), 4), "non_model_max_s": r2(max(non), 4),
            "model_share_pct": r2(sum(mdl) / sum(e2e) * 100, 3),
            "generated_tokens_mean": r2(mean(gen), 1), "llm_calls_total": sum(r["llm_calls"] for r in rows),
            "system_ok": sum(r["system_ok"] for r in rows), "timeouts": sum(r["timeout"] for r in rows),
            "crashes": sum(r["crashed"] for r in rows), "failed_calls": sum(r["failed_calls"] for r in rows),
            "truncated_calls": sum(r["truncated_calls"] for r in rows),
            "answered": sum(r["outcome"] == "answered" for r in rows),
            "grounding_ok(reference)": sum(bool(r["grounding_ok"]) for r in rows),
            "category_match(reference)": sum(r["category"] == "match" for r in rows),
            "timeout_threshold_s": d["meta"]["timeout_s"], "started_at": d["meta"]["started_at"], "finished_at": d["meta"]["finished_at"],
            "gpu_uuid": d["meta"]["env"].get("gpu_uuid") or sm.get("gpu_uuid"),
            "server": {k: sm.get(k) for k in ("precision", "kernels", "log_attention_backend", "log_flashinfer_sampler_lines", "vllm", "flashinfer", "lora_adapter_sha256")} if sm else None,
            "_e2e": e2e, "_ids": [r["id"] for r in rows],
        }
        for r in rows:
            out_rows.append({
                "cell": key, "label": label, "environment": desc, "item_id": r["id"], "question": r["question"],
                "e2e_s": round(r["e2e_ms"] / 1000, 3), "model_inference_s": round(r["model_ms"] / 1000, 3),
                "pipeline_non_model_s": round(r["non_model_ms"] / 1000, 4), "llm_calls": r["llm_calls"],
                "generated_tokens": sum(t or 0 for t in r["generated_tokens"]),
                "prompt_tokens_first_call": (r["prompt_tokens"] or [None])[0],
                "outcome": r["outcome"], "error_code": r["error_code"] or "", "system_ok": r["system_ok"],
                "timeout": r["timeout"], "crashed": r["crashed"], "failed_calls": r["failed_calls"], "truncated_calls": r["truncated_calls"],
                "grounding_ok_ref": r["grounding_ok"], "category_ref": r["category"], "started_at": r["started_at"], "finished_at": r["finished_at"]})
    comps = {}
    if "_e2e" in cells.get("A", {}):
        base = cells["A"]
        for key in "BCDE":
            c = cells.get(key, {})
            if "_e2e" not in c:
                continue
            assert c["_ids"] == base["_ids"]
            imp = (base["e2e_mean_s"] - c["e2e_mean_s"]) / base["e2e_mean_s"] * 100
            comps[f"A→{key}"] = {"e2e_mean_reduction_pct": round(imp, 2), "paired_bootstrap_95ci": boot_improvement(base["_e2e"], c["_e2e"]),
                                 "model_mean_reduction_pct": round((base["model_mean_s"] - c["model_mean_s"]) / base["model_mean_s"] * 100, 2),
                                 "median_reduction_pct": round((base["e2e_median_s"] - c["e2e_median_s"]) / base["e2e_median_s"] * 100, 2)}
        for a, b in (("B", "C"), ("B", "D"), ("C", "E"), ("D", "E")):
            if "_e2e" in cells.get(a, {}) and "_e2e" in cells.get(b, {}):
                comps[f"{a}→{b}"] = {"e2e_mean_reduction_pct": round((cells[a]["e2e_mean_s"] - cells[b]["e2e_mean_s"]) / cells[a]["e2e_mean_s"] * 100, 2),
                                     "paired_bootstrap_95ci": boot_improvement(cells[a]["_e2e"], cells[b]["_e2e"])}
    # 민감도(주 결과 아님): E에서 정상 판정이 아닌 문항(타임아웃·잘림)을 양쪽에서 함께 뺀 A→E
    if "_e2e" in cells.get("A", {}) and "_e2e" in cells.get("E", {}):
        e_rows = json.loads((LAT / "E_vllm_fp8_fi_v4.json").read_text(encoding="utf-8"))["rows"]
        keep = [i for i, r in enumerate(e_rows) if r["system_ok"]]
        a = [cells["A"]["_e2e"][i] for i in keep]
        b = [cells["E"]["_e2e"][i] for i in keep]
        comps["A→E(sensitivity: E 비정상 문항 제외)"] = {
            "excluded_items": [e_rows[i]["id"] for i in range(len(e_rows)) if i not in keep], "items": len(keep),
            "A_mean_s": round(mean(a), 3), "E_mean_s": round(mean(b), 3),
            "e2e_mean_reduction_pct": round((mean(a) - mean(b)) / mean(a) * 100, 2), "paired_bootstrap_95ci": boot_improvement(a, b)}
    for c in cells.values():
        c.pop("_e2e", None)
        c.pop("_ids", None)
    with open(FR / "latency_results.csv", "w", encoding="utf-8-sig", newline="") as f:
        if out_rows:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
            w.writeheader()
            w.writerows(out_rows)
    return cells, comps


def server_load_info():
    """vLLM 서버 로그에서 가중치 적재 메모리·KV cache 크기·기동 시간."""
    info = {}
    for prec in ("bf16", "fp8"):
        p = LAT / f"server_{prec}_fi.log"
        if not p.exists():
            continue
        t = p.read_text(errors="replace")
        m = re.findall(r"Model loading took ([\d.]+) GiB(?: memory)? and ([\d.]+) seconds", t)
        kv = re.findall(r"GPU KV cache size: ([\d,]+) tokens", t)
        rl = (LAT / "runs.log").read_text() if (LAT / "runs.log").exists() else ""
        su = re.findall(rf"server {prec} rc=0 startup_seconds=([\d.]+)", rl)
        info[prec] = {"model_loading_gib": float(m[0][0]) if m else None, "model_loading_seconds": float(m[0][1]) if m else None,
                      "gpu_kv_cache_tokens": int(kv[0].replace(",", "")) if kv else None,
                      "server_startup_to_ready_seconds": float(su[0]) if su else None}
    return info


# ---------------------------------------------------------------- VRAM (자체시험)
def vram():
    out_rows, cfgs = [], {}
    for key, label, desc in VCFG:
        p = VR / f"{label}.json"
        if not p.exists():
            cfgs[key] = {"label": label, "description": desc, "status": "측정 파일 없음"}
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        meta, rows = d["meta"], d["rows"]
        waste = []
        if meta["backend"] == "hf":
            persistent = meta["after_load"]["allocated_mib"]   # 가중치 등 질의와 무관한 상주 tensor
            proc = []
            for r in rows:
                alloc_q = r["peak_reserved_mib"] - persistent   # 질의 처리에 allocator가 잡아 둔 메모리(상주 tensor 제외)
                used_q = r["peak_allocated_mib"] - persistent   # 그중 실제 tensor가 쓴 최대치
                wq = (alloc_q - used_q) / alloc_q * 100
                waste.append(wq)
                proc.append(r["process_waste_pct"])
                out_rows.append({"config": key, "label": label, "environment": desc, "qid": r["qid"], "prompt_tokens": r["prompt_tokens"],
                                 "generated_tokens": r["generated_tokens"], "scope": "PyTorch allocator, 질의 구간(상주 가중치 제외)",
                                 "allocated_mib": round(alloc_q, 1), "used_mib": round(used_q, 1), "waste_pct": round(wq, 3),
                                 "process_allocated_mib(reserved)": r["peak_reserved_mib"], "process_used_mib(allocated)": r["peak_allocated_mib"],
                                 "process_waste_pct": r["process_waste_pct"], "seconds": r["seconds"]})
            cfgs[key] = {"label": label, "description": desc, "backend": "hf", "queries": len(rows),
                         "method": "질의마다 empty_cache·reset_peak 뒤 같은 구간의 max_memory_reserved(할당) 대 max_memory_allocated(실사용); 질의 범위는 적재 직후 상주 tensor를 양쪽에서 뺌",
                         "persistent_allocated_mib": persistent, "query_waste_pct_mean": r2(mean(waste), 3), "query_waste_pct_max": r2(max(waste), 3),
                         "process_waste_pct_mean": r2(mean(proc), 3), "process_waste_pct_max": r2(max(proc), 3),
                         "query_allocated_mib_mean": r2(mean([x["allocated_mib"] for x in out_rows if x["config"] == key]), 1),
                         "query_used_mib_mean": r2(mean([x["used_mib"] for x in out_rows if x["config"] == key]), 1),
                         "allocator_conf": meta.get("PYTORCH_CUDA_ALLOC_CONF"), "gpu_uuid": meta["gpu_uuid"], "model": meta["model"], "adapter": meta["adapter"]}
        else:
            for r in rows:
                waste.append(r["kv_waste_pct"])
                out_rows.append({"config": key, "label": label, "environment": desc, "qid": r["qid"], "prompt_tokens": r["prompt_tokens"],
                                 "generated_tokens": r["generated_tokens"], "scope": "vLLM 질의별 KV cache(PagedAttention block)",
                                 "allocated_mib": r["kv_allocated_mib"], "used_mib": r["kv_used_mib"], "waste_pct": r["kv_waste_pct"],
                                 "process_allocated_mib(reserved)": r["torch_reserved_mib_at_peak"], "process_used_mib(allocated)": r["torch_allocated_mib_at_peak"],
                                 "process_waste_pct": None, "seconds": r["seconds"], "peak_blocks": r["peak_blocks"], "block_size": r["block_size"],
                                 "kv_filled_tokens": r["peak_computed_tokens"]})
            cfgs[key] = {"label": label, "description": desc, "backend": "vllm", "queries": len(rows),
                         "method": "engine step마다 같은 순간의 (배정 block × block_size × token당 KV 바이트) 대 (KV가 채워진 token × token당 KV 바이트); 질의별 최대 배정 순간 값",
                         "kv_bytes_per_token": meta["kv_bytes_per_token"], "block_size": rows[0]["block_size"],
                         "kv_pool_blocks": meta["kv_pool_blocks"], "kv_pool_mib_reference_only": meta["kv_pool_mib(reference only, not counted as allocation)"],
                         "query_waste_pct_mean": r2(mean(waste), 3), "query_waste_pct_max": r2(max(waste), 3),
                         "query_allocated_mib_mean": r2(mean([r["kv_allocated_mib"] for r in rows]), 3),
                         "query_used_mib_mean": r2(mean([r["kv_used_mib"] for r in rows]), 3),
                         "gpu_uuid": meta["gpu_uuid"], "engine_kwargs": meta["engine_kwargs"], "lora": meta["lora"], "vllm": meta["vllm"]}
    fields = []
    for r in out_rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with open(FR / "vram_results.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)
    return cfgs


# ---------------------------------------------------------------- 기존 기록
def existing():
    ex = {}
    fp8 = json.loads((INV / "serving_vllm_fp8/latency.json").read_text())
    ex["serving_vllm_fp8_latency(2026-10-14, 고정 30문항, 모델 시간)"] = {
        k: {"item_model_seconds_mean": v.get("item_model_seconds_mean"), "item_model_seconds_median": v.get("item_model_seconds_median"),
            "gen_tokens_per_s_median": v.get("gen_tokens_per_s_median")} for k, v in fp8["cells"].items()}
    ex["serving_vllm_fp8_latency_ratios"] = fp8["ratios"]
    lat = {}
    for p in sorted((INV / "pilot_010/cells/JV/latency").glob("*.json")) + sorted((INV / "pilot_010/cells/JT/latency").glob("*.json")):
        d = json.loads(p.read_text())
        rows = d["rows"]
        w = [(datetime.fromisoformat(r["finished_at"]) - datetime.fromisoformat(r["started_at"])).total_seconds() for r in rows]
        lat[p.stem] = {"model": d["meta"].get("model"), "items": len(rows), "wall_mean_s": round(mean(w), 3), "wall_median_s": round(st.median(w), 3),
                       "started_at": d["meta"].get("started_at"), "source": str(p.relative_to(ROOT))}
    ex["pilot_010_latency_cells(JT vLLM BF16 2026-11-20, JV Ollama Q4_K_M 2026-11-22)"] = lat
    return ex


# ---------------------------------------------------------------- SVG
# 정부기관 제출 보고서 양식: 흰 바탕, 검은 테두리, 회색·검정 막대, 굴림/돋움 계열, 단위·주석 표기
FONT = "Gulim, 굴림, Dotum, 돋움, 'Malgun Gothic', 'Noto Sans CJK KR', 'WenQuanYi Zen Hei', sans-serif"
INK, GRID, SURF = "#000000", "#999999", "#ffffff"
S1, S2 = "#a6a6a6", "#000000"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def nice_step(vmax):
    import math
    raw = vmax / 5
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag


def hbar_svg(path, title, subtitle, items, unit, xmax=None, ref=None, ref_label=None, stacked=None, legend=None, fmt="{:.2f}", tfmt="{:g}"):
    """items: [(label, value)] 또는 stacked=[(label, [v1, v2])]."""
    rows = stacked if stacked else items
    W, left, right, rh = 900, 340, 90, 40
    top = 92 if legend else 72
    ph = rh * len(rows)
    H = top + ph + 74
    vmax = xmax or max((sum(v) if stacked else v) for _, v in rows) * 1.12
    step = nice_step(vmax)
    vmax = step * (int(vmax / step - 1e-9) + 1)
    n = int(round(vmax / step))
    sx = lambda v: left + (W - left - right) * v / vmax
    pr = W - right
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
         f'<rect width="{W}" height="{H}" fill="{SURF}"/>',
         f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" fill="none" stroke="{INK}" stroke-width="1"/>',
         f'<text x="{W / 2}" y="32" font-size="18" font-weight="700" fill="{INK}" text-anchor="middle">&lt; {esc(title)} &gt;</text>',
         f'<text x="{pr}" y="{top - 10}" font-size="12" fill="{INK}" text-anchor="end">(단위: {esc(unit)})</text>']
    for i in range(n + 1):
        v = step * i
        x = sx(v)
        if 0 < i < n:
            o.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + ph}" stroke="{GRID}" stroke-width="0.8" stroke-dasharray="3 3"/>')
        o.append(f'<line x1="{x:.1f}" y1="{top + ph}" x2="{x:.1f}" y2="{top + ph + 5}" stroke="{INK}" stroke-width="1"/>')
        o.append(f'<text x="{x:.1f}" y="{top + ph + 19}" font-size="12" fill="{INK}" text-anchor="middle">{tfmt.format(v)}</text>')
    for i, (lab, v) in enumerate(rows):
        y = top + i * rh
        o.append(f'<line x1="{left - 5}" y1="{y + rh / 2}" x2="{left}" y2="{y + rh / 2}" stroke="{INK}" stroke-width="1"/>')
        o.append(f'<text x="{left - 9}" y="{y + rh / 2 + 4}" font-size="13" fill="{INK}" text-anchor="end">{esc(lab)}</text>')
        if stacked:
            x0 = left
            for j, part in enumerate(v):
                w = sx(part) - left
                o.append(f'<rect x="{x0:.1f}" y="{y + 10}" width="{max(w, 0.8):.1f}" height="{rh - 20}" fill="{[S1, S2][j]}" stroke="{INK}" stroke-width="0.8"><title>{esc(lab)}: {fmt.format(part)} {esc(unit)}</title></rect>')
                x0 += w
            tot = sum(v)
            o.append(f'<text x="{sx(tot) + 7:.1f}" y="{y + rh / 2 + 4}" font-size="12" fill="{INK}">{fmt.format(tot)}</text>')
        else:
            o.append(f'<rect x="{left}" y="{y + 10}" width="{max(sx(v) - left, 0.8):.1f}" height="{rh - 20}" fill="{S1}" stroke="{INK}" stroke-width="0.8"><title>{esc(lab)}: {fmt.format(v)} {esc(unit)}</title></rect>')
            o.append(f'<text x="{sx(v) + 7:.1f}" y="{y + rh / 2 + 4}" font-size="12" fill="{INK}">{fmt.format(v)}</text>')
    if ref is not None:
        x = sx(ref)
        o.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + ph}" stroke="{INK}" stroke-width="1.5" stroke-dasharray="6 3"/>')
        o.append(f'<text x="{x + 5:.1f}" y="{top + 14}" font-size="12" fill="{INK}">{esc(ref_label)}</text>')
    o.append(f'<rect x="{left}" y="{top}" width="{pr - left}" height="{ph}" fill="none" stroke="{INK}" stroke-width="1"/>')
    if legend:
        sizes = [24 + 13 * len(name) for name in legend]
        lw = sum(sizes) + 12
        lx = left
        o.append(f'<rect x="{lx}" y="{top - 38}" width="{lw}" height="22" fill="{SURF}" stroke="{INK}" stroke-width="0.8"/>')
        cx = lx + 8
        for j, name in enumerate(legend):
            o.append(f'<rect x="{cx}" y="{top - 32}" width="14" height="10" fill="{[S1, S2][j]}" stroke="{INK}" stroke-width="0.8"/>'
                     f'<text x="{cx + 19}" y="{top - 22}" font-size="12" fill="{INK}">{esc(name)}</text>')
            cx += sizes[j]
    o.append(f'<text x="16" y="{H - 14}" font-size="11.5" fill="{INK}">※ {esc(subtitle)}</text>')
    o.append("</svg>")
    path.write_text("\n".join(o), encoding="utf-8")


def figures(cells, comps, cfgs, load):
    FIG.mkdir(exist_ok=True)
    have = [(k, c) for k, c in cells.items() if "e2e_mean_s" in c]
    if have:
        hbar_svg(FIG / "latency_e2e_mean.svg", "평균 End-to-End 응답시간 (자체시험, 고정 30문항)",
                 "질의 입력 → 최종 응답, 동시 1, 워밍업 제외, GPU 1장 · 파이프라인(모델 외)은 문항당 0.04–0.06초로 막대에서 거의 보이지 않음",
                 None, "초", stacked=[(f"{k} {c['description']}", [c["model_mean_s"], c["non_model_mean_s"]]) for k, c in have],
                 legend=["모델 추론시간", "파이프라인 처리(모델 외)"])
        if "A" in cells and "e2e_mean_s" in cells["A"]:
            A = cells["A"]["e2e_mean_s"]
            hbar_svg(FIG / "latency_reduction_vs_initial.svg", "초기 환경(A) 대비 평균 응답시간 감소율",
                     "(A − X) / A × 100, 목표선 15%", [(f"{k[-1]} {cells[k[-1]]['description']}", v["e2e_mean_reduction_pct"]) for k, v in comps.items() if k.startswith("A→") and len(k) == 3],
                     "%", xmax=100, ref=15, ref_label="목표 15%", fmt="{:.1f}")
    hv = [(k, c) for k, c in cfgs.items() if "query_waste_pct_mean" in c]
    if hv:
        hbar_svg(FIG / "vram_waste.svg", "2,048-token 질의 10건 VRAM 낭비율(질의별 평균)",
                 "낭비율 = (할당 − 실제 활용) / 할당 × 100 · HF = PyTorch allocator 질의 구간, vLLM = 질의별 KV block", [(f"{k} {c['description']}", c["query_waste_pct_mean"]) for k, c in hv],
                 "%", xmax=max(25, max(c["query_waste_pct_mean"] for _, c in hv) * 1.2), ref=20, ref_label="목표 20% 이하", fmt="{:.2f}")
    # 모델 경량화: 가중치 크기(파일·서버 로그 실측)
    sizes = [("BF16 원본(GGUF BF16 파일)", 16388044160 / 1e9)]
    if load.get("bf16", {}).get("model_loading_gib"):
        sizes.append(("vLLM BF16 적재 메모리", load["bf16"]["model_loading_gib"] * 1.073741824))
    if load.get("fp8", {}).get("model_loading_gib"):
        sizes.append(("vLLM FP8 적재 메모리", load["fp8"]["model_loading_gib"] * 1.073741824))
    sizes.append(("GGUF Q4_K_M(공식 방식) 파일", 5225375104 / 1e9))
    hbar_svg(FIG / "model_compression_size.svg", "모델 경량화: 가중치 크기 비교 (Qwen3-8B)", "GB(10^9 B) · 파일 크기는 sha256 영수증 기록, 적재 메모리는 vLLM 서버 로그 'Model loading took'",
             sizes, "GB", fmt="{:.2f}")
    fp8 = json.loads((INV / "serving_vllm_fp8/latency.json").read_text())["cells"]
    sp = [("HF BF16 (serving_vllm, 98문항 k=4)", 37.5), ]
    sp = []
    for k, lab in (("lat-vllm-bf16-base", "vLLM BF16 + FlashInfer · base"), ("lat-vllm-fp8-base", "vLLM FP8 + FlashInfer · base"),
                   ("lat-vllm-bf16-final", "vLLM BF16 + FlashInfer · 학습 모델"), ("lat-vllm-fp8-final", "vLLM FP8 + FlashInfer · 학습 모델"),
                   ("lat-E", "Ollama Q4_K_M (E 셀)")):
        if k in fp8:
            sp.append((lab, fp8[k]["gen_tokens_per_s_median"]))
    hbar_svg(FIG / "model_compression_speed.svg", "경량화·서빙 경로별 생성 속도 (기존 기록, 2026-10-14)",
             "serving_vllm_fp8/latency.json, 고정 30문항, 동시 1, 호출당 생성 속도 중앙값(prefill 포함)", sp, "tok/s", fmt="{:.1f}")


def main():
    cells, comps = latency()
    load = server_load_info()
    cfgs = vram()
    ex = existing()
    figures(cells, comps, cfgs, load)
    E, A = cells.get("E", {}), cells.get("A", {})
    lat_goal = None
    if "e2e_mean_s" in E and "e2e_mean_s" in A:
        lat_goal = {"metric": "평균 End-to-End 응답시간 감소율(초기 A 대비 최적화 E)", "target": "≥ 15%", "value_pct": comps["A→E"]["e2e_mean_reduction_pct"],
                    "paired_bootstrap_95ci": comps["A→E"]["paired_bootstrap_95ci"], "achieved": comps["A→E"]["e2e_mean_reduction_pct"] >= 15,
                    "initial_mean_s": A["e2e_mean_s"], "optimized_mean_s": E["e2e_mean_s"], "test_type": "자체시험"}
    M4 = cfgs.get("M4", {})
    vr_goal = None
    if "query_waste_pct_mean" in M4:
        vr_goal = {"metric": "2,048-token 질의 10건 VRAM 낭비율(최적화 환경 M4, 질의별 평균)", "target": "≤ 20%", "value_pct": M4["query_waste_pct_mean"],
                   "max_pct": M4["query_waste_pct_max"], "achieved": M4["query_waste_pct_mean"] <= 20 and M4["query_waste_pct_max"] <= 20, "test_type": "자체시험"}
    summary = {"generated_at": datetime.now().astimezone().isoformat(), "official_test_results": "없음(저장소에 시험합의서·공인시험 기록 없음; 본 수치는 모두 자체시험·기존 자체 실험 기록)",
               "goals": {"latency": lat_goal, "vram_waste": vr_goal},
               "latency_self_test": {"cells": cells, "comparisons": comps, "vllm_server": load},
               "vram_self_test": cfgs, "existing_records": ex}
    (FR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary["goals"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
