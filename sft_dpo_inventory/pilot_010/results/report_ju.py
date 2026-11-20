# -*- coding: utf-8 -*-
"""pilot_010 JU(결정 272) 보고 표 생성: ``ju_results.json``만 읽어 ``ju_tables.md``를 쓴다.
모델 호출·PF2 원문 접근 없음(집계 수치만). ``JU_RESULTS.md``의 표는 이 출력을 그대로 옮긴다. 측정 뒤 새로 쓴 표 생성기(수치를 바꾸지 않음).

    python3 sft_dpo_inventory/pilot_010/results/report_ju.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "ju_results.json").read_text(encoding="utf-8"))
N = dict(R["names"], T27="27B BF16 (vLLM)", Q4="27B Q4 (Ollama)")
STU = ["base", "B2F", "P9", "V4", "V8", "RRNM12"]
ALL = STU + ["T27", "Q4"]
MET = [("correct_refusal", "P1 PF2 올바른 거부(50)"), ("over_refusal_100", "P2 과잉 거부(답하는 100)"), ("over_refusal_contrast25", "P2c 과잉 거부(근접 대조 25)"),
       ("accuracy_100", "P3 PF2 정답률(100)"), ("hfinal_accuracy", "P4 H-final 정답률(3,000)"), ("hfinal_over_refusal", "H-final 과잉 거부")]


def f(x, nd=2):
    return "—" if x is None else f"{x:.{nd}f}"


def ci(c):
    return "—" if not c else f"[{f(c[0])}, {f(c[1])}]"


def mets(C):
    have = C["arms"]["Q4"]["metrics"]
    return [(k, lab) for k, lab in MET if k in have]


def t1(C):
    A = C["arms"]
    out = ["| 지표 | " + " | ".join(N[a] for a in ALL) + " |", "|---|" + "---|" * len(ALL)]
    for k, lab in mets(C):
        out.append(f"| {lab} | " + " | ".join(f"{f(A[a]['metrics'][k]['mean_pct'])} {ci(A[a]['metrics'][k]['ci95_pct'])}" for a in ALL) + " |")
    out.append("| seed 수 | " + " | ".join(str(len(A[a]["seeds"])) for a in ALL) + " |")
    return out


def t2(C):
    D = C["q4_minus_t27"]
    out = ["| 지표 | Q4 | BF16 | Q4 − BF16 %p [95% CI] | 폭 | 판정 | CI가 0을 벗어남 |", "|---|---|---|---|---|---|---|"]
    A = C["arms"]
    for k, lab in mets(C):
        d = D[k]
        b = "—" if d["bound_pp"] is None else f"±{d['bound_pp']:g}"
        out.append(f"| {lab} | {f(A['Q4']['metrics'][k]['mean_pct'])} | {f(A['T27']['metrics'][k]['mean_pct'])} | {f(d['diff_pp'])} {ci(d['ci95_pp'])} | {b} | {d['verdict']} | "
                   f"{'예' if d['ci_excludes_0'] else '아니오'} |")
    G = C["item_agreement_pf2"]["groups"]
    lab = {"all150": "전체 150", "refusal50": "거부 50", "refusal_M": "거부 M 34", "refusal_P": "거부 P 10", "refusal_C": "거부 C 6", "answer100": "답하는 100",
           "answer75(non-contrast)": "근접 대조 아닌 75", "contrast25": "근접 대조 25"}
    out += ["", "문항별 다수 결과 일치(PF2, 빌드마다 k=4 중 3개 이상 같은 결과 = 다수, 아니면 혼합; R 거부·C 정답·W 오답):", "",
            "| 묶음 | 문항 | 같음 | 같음 % | 혼합 뺀 문항 | 혼합 뺀 같음 % | 혼합 Q4 | 혼합 BF16 | 결과 쌍(Q4\\|BF16) |", "|---|---|---|---|---|---|---|---|---|"]
    for g, v in G.items():
        pairs = ", ".join(f"{p.replace('|', '/')} {n}" for p, n in sorted(v["pairs(q4|bf16)"].items(), key=lambda x: -x[1]))
        out.append(f"| {lab.get(g, g)} | {v['items']} | {v['agree']} | {f(v['agree_pct'])} | {v['items_without_mixed']} | {f(v['agree_without_mixed_pct'])} | "
                   f"{v['mixed_q4']} | {v['mixed_bf16']} | {pairs} |")
    return out


def t3(C):
    D = C["student_minus_q4"]
    M = mets(C)
    out = ["| 학생 arm − Q4 | " + " | ".join(lab.split(" ")[0] for _, lab in M) + " |", "|---|" + "---|" * len(M)]
    for a in STU:
        d = D[f"{a}-Q4"]
        out.append(f"| {N[a]} | " + " | ".join(f"{f(d[k]['diff_pp'])} {ci(d[k]['ci95_pp'])}" for k, _ in M) + " |")
    return out


def t4(C, with_hf):
    A = C["arms"]
    out = ["PF2 형별 올바른 거부(%, seed 평균; 문항 M 34·P 10·C 6):", "", "| arm | M | P | C |", "|---|---|---|---|"]
    for a in ALL:
        d = A[a]["pf2_correct_refusal_by_form"]
        out.append(f"| {N[a]} | " + " | ".join(f(d[x]["pct"]) for x in "MPC") + " |")
    for key, title in (("pf2_correct_refusal_by_category", "PF2 범주별 올바른 거부(%, seed 평균; P·C는 코드만):"),
                       ("pf2_contrast25_over_refusal_by_category", "근접 대조 25 범주별 과잉 거부(%, seed 평균):")):
        cats = list(A["Q4"][key])
        n = {c: A["Q4"][key][c]["items"] for c in cats}
        out += ["", title, "", "| 범주(문항) | " + " | ".join(N[a] for a in ALL) + " |", "|---|" + "---|" * len(ALL)]
        for c in cats:
            out.append(f"| {c} ({n[c]}) | " + " | ".join(f(A[a][key].get(c, {}).get("pct")) for a in ALL) + " |")
    keys = ["correct", "refused_M", "refused_P", "refused_C", "truncated", "U", "silent", "other_fail"]
    blocks = [("PF2 답하는 100 결과 분해(%, seed 평균):", lambda a: A[a]["pf2_decomposition_100_seed_mean"])]
    if with_hf:
        blocks.append(("H-final 3,000 결과 분해(%, seed 평균):", lambda a: A[a]["hfinal"]["decomposition_seed_mean"]))
    for title, get in blocks:
        out += ["", title, "", "| arm | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
        for a in ALL:
            d = get(a)
            out.append(f"| {N[a]} | " + " | ".join(f(d.get(k)) for k in keys) + " |")
    if not with_hf:
        return out
    types = list(A["Q4"]["hfinal"]["accuracy_by_tool_type_seed_mean"])
    n = {t: A["Q4"]["hfinal"]["accuracy_by_tool_type_seed_mean"][t]["items"] for t in types}
    out += ["", "H-final 도구 유형별 정답률(%, seed 평균):", "", "| arm | " + " | ".join(f"{t}({n[t]})" for t in types) + " |", "|---|" + "---|" * len(types)]
    for a in ALL:
        d = A[a]["hfinal"]["accuracy_by_tool_type_seed_mean"]
        out.append(f"| {N[a]} | " + " | ".join(f(d[t]["pct"]) for t in types) + " |")
    out += ["", "template_group 붕괴(30문항 이상 59그룹, 같은 조건 base 대비, seed 평균 그룹 수):", "", "| arm | −20%p 이하 | −30%p 이하 |", "|---|---|---|"]
    for a in ALL[1:]:
        g = A[a]["hfinal"]["group_collapse_mean"]
        out.append(f"| {N[a]} | {f(g['below_base_20pp'], 1)} | {f(g['below_base_30pp'], 1)} |")
    return out


def t5():
    Co = R["cost"]
    S, G = R["conditions"]["S"]["arms"], R["conditions"]["G1"]["arms"]
    out = [f"주의: {Co['note']}.", "", "호출·문항 wall(seed 평균):", "",
           "| arm | S PF2 호출/문항 | S PF2 wall p50 s | p95 s | H-final 호출/문항 | H-final wall p50 s | p95 s | G1 PF2 호출/문항 | G1 PF2 wall p50 s | p95 s |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for a in ALL:
        p, h, g = S[a]["cost_seed_mean"]["pf2"], S[a]["cost_seed_mean"]["hfinal"], G[a]["cost_seed_mean"]["pf2"]
        out.append(f"| {N[a]} | {f(p['llm_calls_per_item'], 3)} | {f(p['wall_p50_s'])} | {f(p['wall_p95_s'])} | {f(h['llm_calls_per_item'], 3)} | {f(h['wall_p50_s'])} | {f(h['wall_p95_s'])} | "
                   f"{f(g['llm_calls_per_item'], 3)} | {f(g['wall_p50_s'])} | {f(g['wall_p95_s'])} |")
    out += ["", "생성 token(문항당; H-final thinking / 최종 JSON은 각 모델 tokenizer로 나눔 — 27B와 8B token은 같은 단위가 아님)·속도:", "",
            "| 빌드·셀 | 문항 | 호출 | 생성 평균 | 생성 중앙값 | thinking 중앙값 | JSON 중앙값 | thinking 평균 | JSON 평균 | tok/s | 첫 호출 입력 token 중앙값 |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]

    def row(lab, c):
        ts = c.get("decode_tok_s(Σeval_count/Σeval_duration, 요청 하나씩)") or c.get("tok_s(Σgenerated/Σcall server_seconds, 동시 요청 묶음)")
        return (f"| {lab} `{c['cell']}` | {c['items']} | {c['calls']} | {f(c['generated_tokens_per_item_mean'], 1)} | {f(c['generated_tokens_per_item_median'], 1)} | "
                f"{f(c.get('thinking_tokens_per_item_median'), 1)} | {f(c.get('json_tokens_per_item_median'), 1)} | {f(c.get('thinking_tokens_per_item_mean'), 1)} | "
                f"{f(c.get('json_tokens_per_item_mean'), 1)} | {f(ts, 1)} | {f(c.get('prompt_tokens_first_call_median'), 0)} |")
    for b, lab in (("q4", "Q4"), ("t27", "BF16")):
        for part in ("pf2_s", "hfinal_s", "pf2_g1"):
            for c in Co[b][part]:
                out.append(row(lab, c))
    for k, c in Co["students_first_seed"].items():
        out.append(row(N[k.split(":")[0]], c))
    out += ["", "tok/s: Q4 = Σeval_count / Σeval_duration(서버당 요청 하나씩, prompt 처리 제외); BF16·학생 = Σ생성 / Σ호출 server_seconds(동시 요청 묶음, prompt 처리 포함). 정의가 달라 비교용 아님.",
            "", "GPU 메모리(MiB):", ""]
    for k, v in Co["gpu_memory_max_mib"].items():
        out.append(f"- 측정 중 최대 {k}: " + ", ".join(f"GPU {g} {m}" for g, m in v.items()))
    for p, v in Co["q4_server_after_load"].items():
        smi = [x for x in v["nvidia_smi_after_load"] if x.startswith(v["gpu_index"] + ",")]
        out.append(f"- Q4 포트 {p} 모델 올린 직후: GPU {v['gpu_index']} {smi[0].split(', ')[2] if smi else '—'} (`/api/ps` size = size_vram = {v['size']:,} B, context {v['context_length']:,})")
    W = Co["weights"]
    out += ["", f"가중치: Q4 GGUF {W['q4_gguf_model_blob_bytes'] / 1e9:.2f} GB(+ vision projector {W['q4_projector_blob_bytes(vision, 안 씀)'] / 1e9:.2f} GB, 함께 올라감·안 씀), "
            f"BF16 {W['t27_gb']} GB, 8B {W['qwen3_8b_gb']} GB. Q4 = GPU 1장 × 서버 4벌, BF16 = GPU 2장(TP 2) × 서버 2벌."]
    return out


def main():
    L = ["<!-- report_ju.py가 ju_results.json에서 생성. 손으로 고치지 않음 -->", ""]
    CS, CG = R["conditions"]["S"], R["conditions"]["G1"]
    hdr = "Q4 = Ollama qwen3.8:27b(Q4_K_M, aaee06c3), BF16 = JT의 Qwen/Qwen3.8-27B BF16 (vLLM). 교사 CI는 문항 재추출만(k=4 표본은 한 행으로 묶음), 학생은 U1."
    L += [f"## 표 1a. 조건 S: Q4·BF16·학생 arm (%, [95% CI]) — {CS['condition']}", "", hdr, ""] + t1(CS)
    L += ["", f"## 표 1b. 조건 G1(PF2만): Q4·BF16·학생 arm (%, [95% CI]) — {CG['condition']}", "", hdr, ""] + t1(CG)
    L += ["", "## 표 2a. 조건 S: Q4 − BF16 (%p, 문항 공유 재추출)와 판정(지표마다 따로)", "", f"규칙: {R['similarity_rule']['order']}. 근접 대조 25는 폭이 없어 판정하지 않음.", ""] + t2(CS)
    L += ["", "## 표 2b. 조건 G1(PF2만, 기술용): Q4 − BF16", ""] + t2(CG)
    L += ["", "## 표 3a. 조건 S: 학생 arm − Q4 (%p, [95% CI], 문항 공유 재추출) — 회복 비율은 계산하지 않음", ""] + t3(CS)
    L += ["", "## 표 3b. 조건 G1(PF2만): 학생 arm − Q4", ""] + t3(CG)
    L += ["", "## 표 4a. 조건 S: 형별·범주별·결과 분해·도구 유형별", ""] + t4(CS, True)
    L += ["", "## 표 4b. 조건 G1(PF2만): 형별·범주별·결과 분해", ""] + t4(CG, False)
    L += ["", "## 표 5. 비용(직접 비교 아님)", ""] + t5()
    (HERE / "ju_tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("written", HERE / "ju_tables.md", len(L))


if __name__ == "__main__":
    main()
