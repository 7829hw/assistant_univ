# -*- coding: utf-8 -*-
"""pilot_010 JV(결정 273) 보고 표 생성: ``jv_results.json``만 읽어 ``jv_tables.md``를 쓴다.
모델 호출·PF2 원문 접근 없음(집계 수치만). ``JV_RESULTS.md``의 표는 이 출력을 그대로 옮긴다. 측정 뒤 새로 쓴 표 생성기(수치를 바꾸지 않음). 판정 문구 없음.

    python3 sft_dpo_inventory/pilot_010/results/report_jv.py
"""
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "jv_results.json").read_text(encoding="utf-8"))
N = R["names"]
ARMS = [a for a in ("base", "B2F", "V4", "V8", "RRNM12") if a in R["table1"]["q4"]]
SHORT = {"base": "base", "B2F": "SFT", "V4": "RR+NM4", "V8": "RR+NM8", "RRNM12": "RR+NM 12", "T27Q4": "교사 Q4"}
MET = [("correct_refusal", "P1 올바른 거부(PF2 50)"), ("over_refusal_100", "P2 과잉 거부(PF2 답하는 100)"), ("over_refusal_contrast25", "P2c 과잉 거부(근접 대조 25)"),
       ("accuracy_100", "P3 정답률(PF2 100)"), ("hfinal_accuracy", "P4 H-final 정답률(1,000)"), ("hfinal_over_refusal", "H-final 과잉 거부(1,000)")]
HDR = "| | " + " | ".join(lab for _, lab in MET) + " |"
SEP = "|---|" + "---|" * len(MET)


def f(x, nd=2):
    return "—" if x is None else f"{x:.{nd}f}"


def ci(c):
    return "—" if not c else f"[{f(c[0])}, {f(c[1])}]"


def mv(m):
    return f"{f(m['mean_pct'])} {ci(m['ci95_pct'])}"


def dv(d):
    return f"{f(d['diff_pp'])} {ci(d['ci95_pp'])}"


def t1():
    T = R["table1"]
    out = [HDR, SEP]
    for a in ARMS:
        for b, lab in (("q4", "Q4"), ("bf16", "BF16")):
            x = T[b][a]
            out.append(f"| {SHORT[a]} {lab} (seed {len(x['seeds'])}) | " + " | ".join(mv(x["metrics"][k]) for k, _ in MET) + " |")
    out.append("| 교사 Q4 (JU, k=4·s1) | " + " | ".join(mv(T["teacher_q4"]["metrics"][k]) for k, _ in MET) + " |")
    out += ["", "seed별 값(%, Q4; H-final은 seed마다 1회):", "", "| arm | seed | " + " | ".join(k for k, _ in MET) + " |", "|---|---|" + "---|" * len(MET)]
    for a in ARMS:
        if a == "RRNM12":
            continue
        x = T["q4"][a]
        for i, s in enumerate(x["seeds"]):
            out.append(f"| {SHORT[a]} | {s} | " + " | ".join(f(x["metrics"][k]["per_seed_pct"][i]) for k, _ in MET) + " |")
    return out


def t2():
    T = R["table2_q4_minus_bf16_paired"]
    out = ["| arm (짝) | " + " | ".join(lab for _, lab in MET) + " |", SEP]
    for a in ARMS:
        x = T[a]
        out.append(f"| {SHORT[a]} ({x['pairs']}, {len(x['seeds'])}) | " + " | ".join(dv(x["diff"][k]) for k, _ in MET) + " |")
    out += ["", "짝 BF16 값(%, 위 차이의 기준; base는 BF16 PF2 k=1–4·H-final s1만):", "", HDR, SEP]
    for a in ARMS:
        out.append(f"| {SHORT[a]} BF16 짝 | " + " | ".join(mv(T[a]["bf16_pair_metrics"][k]) for k, _ in MET) + " |")
    out += ["", "seed별 Q4 − BF16(%p):", "", "| arm | seed | " + " | ".join(k for k, _ in MET) + " |", "|---|---|" + "---|" * len(MET)]
    for a in ARMS:
        if a == "RRNM12":
            continue
        x = T[a]
        for i, s in enumerate(x["seeds"]):
            out.append(f"| {SHORT[a]} | {s} | " + " | ".join(f(x["diff"][k]["per_seed_diff_pp"][i]) for k, _ in MET) + " |")
    return out


def t3():
    T = R["table3_q4_arm_differences"]
    out = ["| 차이 | 빌드 | " + " | ".join(lab for _, lab in MET) + " |", "|---|---|" + "---|" * len(MET)]
    for p, x in T.items():
        a, b = p.split("-")
        for bld, lab in (("q4", "Q4"), ("bf16", "BF16")):
            out.append(f"| {SHORT[a]} − {SHORT[b]} | {lab} | " + " | ".join(dv(x[bld][k]) for k, _ in MET) + " |")
    return out


def t4():
    T = R["table4_student_q4_minus_teacher_q4"]
    out = ["| 학생 Q4 − 교사 Q4 | " + " | ".join(lab for _, lab in MET) + " |", SEP]
    for a in ARMS:
        out.append(f"| {SHORT[a]} | " + " | ".join(dv(T[f"{a}-T27Q4"][k]) for k, _ in MET) + " |")
    return out


def t5():
    L = R["table5_latency"]
    out = [f"방식: {L['rule']}.", "",
           "| 빌드 | 셀 | 문항 | 모델 시간 중앙값 s | p95 s | 문항 wall 중앙값 s | p95 s | 생성 token 중앙값 | thinking 중앙값 | JSON 중앙값 | tok/s | 입력 token 중앙값 | 잘림 호출 | 가중치 GB | GPU 메모리 최대 MiB |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    lab = {"teacher_q4": "교사 Q4 (Ollama, MTP draft)", "base_q4": "base Q4 (Ollama)", "v4_o101_q4": "RR+NM4 o101 Q4 (Ollama)"}
    for k, c in L["cells"].items():
        if not c:
            out.append(f"| {lab.get(k, k)} | — | 없음 |" + " |" * 12)
            continue
        out.append(f"| {lab.get(k, k)} | `{c['cell']}` | {c['items']} | {f(c['median_model_seconds'])} | {f(c['p95_model_seconds'])} | {f(c['median_item_wall_seconds'])} | "
                   f"{f(c['p95_item_wall_seconds'])} | {f(c['median_generated_tokens'], 1)} | {f(c['median_thinking_tokens'], 1)} | {f(c['median_json_tokens'], 1)} | "
                   f"{f(c['decode_tok_s'], 1)} | {f(c['median_input_tokens'], 0)} | {c['truncated_calls']} | {c['weights_bytes'] / 1e9:.2f} | {c['gpu_memory_max_mib_during_cell(5s)']} |")
    J = L["bf16_vllm_reference_jt_table4"]
    jl = {"latjt_t27": "교사 BF16 (vLLM, TP 2)", "latjt_8b_base": "base BF16 (vLLM)", "latjt_8b_v4_o101": "RR+NM4 o101 BF16 (vLLM LoRA)"}
    jw = {"latjt_t27": J["weights"]["t27_gb"], "latjt_8b_base": J["weights"]["qwen3_8b_gb"], "latjt_8b_v4_o101": J["weights"]["qwen3_8b_gb"]}
    for k, c in J["cells"].items():
        mem = ", ".join(f"GPU {g} {m}" for g, m in (c.get("gpu_memory_max_mib_during_cell") or {}).items())
        out.append(f"| 참고 JT: {jl.get(k, k)} | `{Path(c['file']).stem}` | {c['items']} | {f(c['median_model_seconds'])} | {f(c['p95_model_seconds'])} | {f(c['median_item_wall_seconds'])} | "
                   f"{f(c['p95_item_wall_seconds'])} | {f(c['median_generated_tokens'], 1)} | {f(c['median_thinking_tokens'], 1)} | {f(c['median_json_tokens'], 1)} | "
                   f"{f(c['tok_per_s(sum generated / sum model seconds)'], 1)} | {f(c['median_input_tokens'], 0)} | {c['truncated_calls']} | {jw.get(k)} | {mem} |")
    out += ["", "tok/s: Ollama 행 = Σeval_count / Σeval_duration(prompt 처리 제외); JT vLLM 행 = Σ생성 / Σ모델 시간(prompt 처리 포함). 정의가 달라 직접 비교용 아님. "
            "thinking·JSON token은 각 모델 tokenizer로 나눔(27B와 8B token은 같은 단위가 아님). vLLM 메모리는 gpu_memory_utilization 예약을 포함.", "",
            "speculative decoding:"]
    for k, c in L["cells"].items():
        if c:
            sd = c["speculative_decoding"]
            out.append(f"- {lab.get(k, k)}: llama-server 명령에 spec type {'있음' if sd['spec_type_in_cmd'] else '없음'}, 로그 draft/MTP 줄 {sd['draft_mtp_lines']}; "
                       f"context {c['context_length_seen']}; `/api/ps` size = size_vram = {c['api_ps_after_load'][0]['size']:,} B")
    out += ["", "측정 셀 비용(학생 Q4, GPU 한 장·서버 한 벌·요청 하나씩, context 40,960; arm 안 seed 평균):", "",
            "| arm | seed | PF2 호출/문항 | PF2 decode tok/s | PF2 셀 wall s(평균) | H-final 호출/문항 | H-final decode tok/s | H-final wall s | H-final 생성 중앙값 | thinking 중앙값 | JSON 중앙값 | GPU 메모리 최대 MiB |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    C = R["cost"]["q4_students"]
    for key, c in C.items():
        a, s = key.split(":")
        p, h = c["pf2"], c["hfinal"]
        m = lambda k: statistics.mean(x[k] for x in p)  # noqa: E731
        out.append(f"| {SHORT[a]} | {s} | {f(m('calls_per_item'), 3)} | {f(m('decode_tok_s'), 1)} | {f(m('wall_seconds'), 1)} | {f(h['calls_per_item'], 3)} | {f(h['decode_tok_s'], 1)} | "
                   f"{f(h['wall_seconds'], 1)} | {f(h['generated_tokens_per_item_median'], 1)} | {f(h.get('thinking_tokens_per_item_median'), 1)} | "
                   f"{f(h.get('json_tokens_per_item_median'), 1)} | {max(c['gpu_memory_max_mib_pf2'], c['gpu_memory_max_mib_hfinal'])} |")
    W = R["cost"]["weights_q4_bytes"]
    out += ["", f"학생 Q4 GGUF 크기: base {W['jv-qwen3-8b-base']:,} B, 어댑터 병합 17개 각 {sorted(set(v for k, v in W.items() if k != 'jv-qwen3-8b-base'))} B."]
    out += ["", "문항 wall(arm 안 seed 평균; 문항마다 첫 호출부터 끝까지):", "", "| arm | PF2 호출/문항 | PF2 wall p50 s | p95 s | H-final 호출/문항 | H-final wall p50 s | p95 s |", "|---|---|---|---|---|---|---|"]
    D = R["table6_details"]
    for a, x in [(a, D["q4"][a]) for a in ARMS] + [("T27Q4", D["teacher_q4"])]:
        c = x["cost_seed_mean"]
        out.append(f"| {SHORT[a]} {'' if a == 'T27Q4' else 'Q4'} | {f(c['pf2']['llm_calls_per_item'], 3)} | {f(c['pf2']['wall_p50_s'])} | {f(c['pf2']['wall_p95_s'])} | "
                   f"{f(c['hfinal']['llm_calls_per_item'], 3)} | {f(c['hfinal']['wall_p50_s'])} | {f(c['hfinal']['wall_p95_s'])} |")
    return out


def rows6():
    D = R["table6_details"]
    r = []
    for a in ARMS:
        r.append((f"{SHORT[a]} Q4", D["q4"][a]))
        r.append((f"{SHORT[a]} BF16", D["bf16"][a]))
    r.append(("교사 Q4", D["teacher_q4"]))
    return r


def t6():
    rows = rows6()
    first = rows[0][1]
    out = ["PF2 형별 올바른 거부(%, seed 평균; 문항 M 34·P 10·C 6):", "", "| arm | M | P | C |", "|---|---|---|---|"]
    for lab, d in rows:
        out.append(f"| {lab} | " + " | ".join(f(d["pf2_correct_refusal_by_form"][x]["pct"]) for x in "MPC") + " |")
    for key, title in (("pf2_correct_refusal_by_category", "PF2 범주별 올바른 거부(%, seed 평균; P·C는 코드만):"),
                       ("pf2_contrast25_over_refusal_by_category", "근접 대조 25 범주별 과잉 거부(%, seed 평균):")):
        cats = list(first[key])
        out += ["", title, "", "| arm | " + " | ".join(f"{c} ({first[key][c]['items']})" for c in cats) + " |", "|---|" + "---|" * len(cats)]
        for lab, d in rows:
            out.append(f"| {lab} | " + " | ".join(f(d[key].get(c, {}).get("pct")) for c in cats) + " |")
    keys = ["correct", "refused_M", "refused_P", "refused_C", "truncated", "U", "silent", "other_fail"]
    for title, get in (("PF2 답하는 100 결과 분해(%, seed 평균):", lambda d: d["pf2_decomposition_100_seed_mean"]),
                       ("H-final 1,000 결과 분해(%, seed 평균):", lambda d: d["hfinal"]["decomposition_seed_mean"])):
        out += ["", title, "", "| arm | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
        for lab, d in rows:
            out.append(f"| {lab} | " + " | ".join(f(get(d).get(k)) for k in keys) + " |")
    types = list(first["hfinal"]["accuracy_by_tool_type_seed_mean"])
    n = {t: first["hfinal"]["accuracy_by_tool_type_seed_mean"][t]["items"] for t in types}
    out += ["", "H-final 1,000 도구 유형별 정답률(%, seed 평균):", "", "| arm | " + " | ".join(f"{t}({n[t]})" for t in types) + " |", "|---|" + "---|" * len(types)]
    for lab, d in rows:
        out.append(f"| {lab} | " + " | ".join(f(d["hfinal"]["accuracy_by_tool_type_seed_mean"][t]["pct"]) for t in types) + " |")
    ge30 = {g["groups_ge30"] for _, d in rows for g in d["hfinal"]["group_collapse_per_seed"].values()}
    if ge30 == {0}:
        out += ["", "template_group 붕괴: H-final 1,000문항 안에 30문항 이상인 template_group이 없어(모든 arm·seed에서 groups_ge30 = 0) 계산되지 않음."]
        return out
    out += ["", "template_group 붕괴(같은 빌드의 base 대비, seed 평균 그룹 수; 교사 Q4는 base Q4 대비):", "", "| arm | −20%p 이하 | −30%p 이하 |", "|---|---|---|"]
    for lab, d in rows:
        if lab.startswith("base"):
            continue
        g = d["hfinal"]["group_collapse_mean"]
        out.append(f"| {lab} | {f(g['below_base_20pp'], 1)} | {f(g['below_base_30pp'], 1)} |")
    return out


def main():
    L = ["<!-- report_jv.py가 jv_results.json에서 생성. 손으로 고치지 않음 -->", "", f"라벨: {R['label']}.", "",
         f"CI: {R['bootstrap']['method']}, {R['bootstrap']['reps']:,}회. H-final = JT 층화 {R['hfinal_items']:,}문항(교사 Q4·학생 BF16도 같은 문항으로 다시 계산). 교사 Q4는 seed 1벌(PF2 k=4·H-final s1).", ""]
    L += ["## 표 1. 학생 Q4·학생 BF16·교사 Q4 (%, [95% CI])", ""] + t1()
    L += ["", "## 표 2. 같은 어댑터 Q4 − BF16 (%p, seed·문항 짝, [95% CI])", ""] + t2()
    L += ["", "## 표 3. Q4 안의 arm 차이 (%p, [95% CI]), 같은 차이의 BF16 값과 나란히", ""] + t3()
    L += ["", "## 표 4. 학생 Q4 − 교사 Q4 (%p, [95% CI], 문항 공유 재추출) — 회복 비율은 계산하지 않음", ""] + t4()
    L += ["", "## 표 5. 지연·자원", ""] + t5()
    L += ["", "## 표 6. 형별·범주별·결과 분해·도구 유형별", ""] + t6()
    (HERE / "jv_tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("written", HERE / "jv_tables.md", len(L))


if __name__ == "__main__":
    main()
