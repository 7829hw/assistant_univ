# -*- coding: utf-8 -*-
"""pilot_010 JT(결정 271) 보고 표 생성: ``jt_results.json``(+ pilot_007 B2 지연 요약, 참고)만 읽어 ``jt_tables.md``를 쓴다.
모델 호출·PF2 원문 접근 없음(집계 수치만). ``JT_RESULTS.md``의 표는 이 출력을 그대로 옮긴다. 측정 뒤 새로 쓴 표 생성기(수치를 바꾸지 않음).

    python3 sft_dpo_inventory/pilot_010/results/report_jt.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
R = json.loads((HERE / "jt_results.json").read_text(encoding="utf-8"))
N = dict(R["names"], T27="27B BF16 (vLLM)")
STU = ["base", "B2F", "P9", "V4", "V8", "RRNM12"]
ALL = STU + ["T27"]
MET = [("correct_refusal", "P1 PF2 올바른 거부(50)"), ("over_refusal_100", "P2 과잉 거부(답하는 100)"), ("over_refusal_contrast25", "P2c 과잉 거부(근접 대조 25)"),
       ("accuracy_100", "P3 PF2 정답률(100)"), ("hfinal_accuracy", "P4 H-final 정답률(3,000)"), ("hfinal_over_refusal", "H-final 과잉 거부")]
SHORT = [lab.split(" ")[0] for _, lab in MET]


def f(x, nd=2):
    return "—" if x is None else f"{x:.{nd}f}"


def ci(c):
    return "—" if not c else f"[{f(c[0])}, {f(c[1])}]"


def t1(C):
    A = C["arms"]
    out = ["| 지표 | " + " | ".join(N[a] for a in ALL) + " |", "|---|" + "---|" * len(ALL)]
    for k, lab in MET:
        out.append(f"| {lab} | " + " | ".join(f"{f(A[a]['metrics'][k]['mean_pct'])} {ci(A[a]['metrics'][k]['ci95_pct'])}" for a in ALL) + " |")
    out.append("| seed 수 | " + " | ".join(str(len(A[a]["seeds"])) for a in ALL) + " |")
    return out


def t2(C):
    D = C["student_minus_t27"]
    out = ["| 학생 arm − 27B | " + " | ".join(SHORT) + " |", "|---|" + "---|" * len(MET)]
    for a in STU:
        d = D[f"{a}-T27"]
        out.append(f"| {N[a]} | " + " | ".join(f"{f(d[k]['diff_pp'])} {ci(d[k]['ci95_pp'])}" for k, _ in MET) + " |")
    return out


def t3(C):
    A = C["arms"]
    out = ["PF2 형별 올바른 거부(%, seed 평균; 문항 M 34·P 10·C 6):", "", "| arm | M | P | C |", "|---|---|---|---|"]
    for a in ALL:
        d = A[a]["pf2_correct_refusal_by_form"]
        out.append(f"| {N[a]} | " + " | ".join(f(d[x]["pct"]) for x in "MPC") + " |")
    cats = list(A["T27"]["pf2_correct_refusal_by_category"])
    n = {c: A["T27"]["pf2_correct_refusal_by_category"][c]["items"] for c in cats}
    out += ["", "PF2 범주별 올바른 거부(%, seed 평균; P·C는 코드만):", "", "| 범주(문항) | " + " | ".join(N[a] for a in ALL) + " |", "|---|" + "---|" * len(ALL)]
    for c in cats:
        out.append(f"| {c} ({n[c]}) | " + " | ".join(f(A[a]["pf2_correct_refusal_by_category"].get(c, {}).get("pct")) for a in ALL) + " |")
    cats = list(A["T27"]["pf2_contrast25_over_refusal_by_category"])
    n = {c: A["T27"]["pf2_contrast25_over_refusal_by_category"][c]["items"] for c in cats}
    out += ["", "근접 대조 25 범주별 과잉 거부(%, seed 평균):", "", "| 범주(문항) | " + " | ".join(N[a] for a in ALL) + " |", "|---|" + "---|" * len(ALL)]
    for c in cats:
        out.append(f"| {c} ({n[c]}) | " + " | ".join(f(A[a]["pf2_contrast25_over_refusal_by_category"].get(c, {}).get("pct")) for a in ALL) + " |")
    keys = ["correct", "refused_M", "refused_P", "refused_C", "truncated", "U", "silent", "other_fail"]
    for title, get in (("PF2 답하는 100 결과 분해(%, seed 평균):", lambda a: A[a]["pf2_decomposition_100_seed_mean"]),
                       ("H-final 3,000 결과 분해(%, seed 평균):", lambda a: A[a]["hfinal"]["decomposition_seed_mean"])):
        out += ["", title, "", "| arm | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
        for a in ALL:
            d = get(a)
            out.append(f"| {N[a]} | " + " | ".join(f(d.get(k)) for k in keys) + " |")
    types = list(A["T27"]["hfinal"]["accuracy_by_tool_type_seed_mean"])
    n = {t: A["T27"]["hfinal"]["accuracy_by_tool_type_seed_mean"][t]["items"] for t in types}
    out += ["", "H-final 도구 유형별 정답률(%, seed 평균):", "", "| arm | " + " | ".join(f"{t}({n[t]})" for t in types) + " |", "|---|" + "---|" * len(types)]
    for a in ALL:
        d = A[a]["hfinal"]["accuracy_by_tool_type_seed_mean"]
        out.append(f"| {N[a]} | " + " | ".join(f(d[t]["pct"]) for t in types) + " |")
    out += ["", "template_group 붕괴(30문항 이상 59그룹, 같은 조건 base 대비, seed 평균 그룹 수):", "", "| arm | −20%p 이하 | −30%p 이하 |", "|---|---|---|"]
    for a in ALL[1:]:
        g = A[a]["hfinal"]["group_collapse_mean"]
        out.append(f"| {N[a]} | {f(g['below_base_20pp'], 1)} | {f(g['below_base_30pp'], 1)} |")
    out += ["", "비용(seed 평균; 27B는 서버 2벌 TP 2, 학생은 GPU 1장 — 셀 wall은 동시 요청·서버 구성이 달라 직접 비교용 아님, 지연은 표 4):", "",
            "| arm | PF2 호출/문항 | PF2 wall p50 s | PF2 wall p95 s | H-final 호출/문항 | H-final wall p50 s | H-final wall p95 s |", "|---|---|---|---|---|---|---|"]
    for a in ALL:
        p, h = A[a]["cost_seed_mean"]["pf2"], A[a]["cost_seed_mean"]["hfinal"]
        out.append(f"| {N[a]} | {f(p['llm_calls_per_item'], 3)} | {f(p['wall_p50_s'])} | {f(p['wall_p95_s'])} | {f(h['llm_calls_per_item'], 3)} | {f(h['wall_p50_s'])} | {f(h['wall_p95_s'])} |")
    return out


def t4():
    L = R["latency_resources"]
    C = L["cells"]
    W = L["weights"]
    old = json.loads((ROOT / "sft_dpo_inventory/pilot_007/latency/B2/latency_summary.json").read_text(encoding="utf-8"))["cells"]["base"]
    rows = [("27B BF16 (vLLM)", "latjt_t27", "2 (TP 2, GPU 0·1)", f"{W['t27_gb']}"), ("8B base", "latjt_8b_base", "1 (GPU 0)", f"{W['qwen3_8b_gb']}"),
            ("8B RR+NM4 o101", "latjt_8b_v4_o101", "1 (GPU 0)", f"{W['qwen3_8b_gb']} + 어댑터 {W['rrnm4_o101_adapter_bytes'] / 1e6:.1f} MB")]
    out = ["| 모델 | 문항 모델 시간 중앙값 s | p95 s | 문항 wall 중앙값 s | p95 s | 생성 token 중앙값 | thinking 중앙값 | 최종 JSON 중앙값 | tok/s | 입력 token 중앙값 | 잘림 | 가중치 GB | GPU 수 | 측정 중 GPU 메모리 최대 MiB |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, key, g, w in rows:
        c = C[key]
        mem = ", ".join(f"GPU {k}: {v}" for k, v in c["gpu_memory_max_mib_during_cell"].items())
        out.append(f"| {name} | {f(c['median_model_seconds'])} | {f(c['p95_model_seconds'])} | {f(c['median_item_wall_seconds'])} | {f(c['p95_item_wall_seconds'])} | "
                   f"{f(c['median_generated_tokens'], 1)} | {f(c['median_thinking_tokens'], 1)} | {f(c['median_json_tokens'], 1)} | {f(c['tok_per_s(sum generated / sum model seconds)'], 1)} | "
                   f"{f(c['median_input_tokens'], 0)} | {c['truncated_calls']} | {w} | {g} | {mem} |")
    out.append(f"| (참고) 8B base, pilot_007 B2 2026-10-22, runtime 재구성 전 | {f(old['median_model_seconds'])} | — | — | — | {f(old['median_generated_tokens'], 1)} | "
               f"{f(old['median_thinking_tokens'], 1)} | {f(old['median_json_tokens'], 1)} | — | {f(old['median_input_tokens'], 0)} | — | 16.38 | 1 | — |")
    out += ["", "서버 기동 직후 메모리(nvidia-smi):", ""]
    for port, v in L["server_memory_after_ready"].items():
        if not v.get("nvidia_smi_after_ready"):
            out.append(f"- 포트 {port}: nvidia-smi 기록 없음(8B 서버 `serve_a11.sh`는 이 항목을 쓰지 않음; 측정 중 최대는 위 표)")
            continue
        out.append(f"- 포트 {port}: " + "; ".join(x.split(", ")[0] + " " + x.split(", ")[2] for x in (v.get("nvidia_smi_after_ready") or [])) + f" (attention {', '.join(v.get('attention_backend') or [])})")
    out += ["", "token 수는 각 모델 자신의 tokenizer로 센다(27B = Qwen/Qwen3.8-27B, 8B = Qwen3-8B@b968826d) — 두 tokenizer의 token은 같은 단위가 아니다."]
    return out


def opt():
    O = R["optional_dev_cells_t27"]
    out = ["| 셀(S, k=1) | 문항 | match % | 거부 결과 % | 잘린 호출 / 호출 |", "|---|---|---|---|---|"]
    for k, v in O.items():
        out.append(f"| {k} | {v['items']} | {f(v['match_pct'])} | {f(v['refusal_outcome_pct'])} | {v['truncated_calls']} / {v['calls']} |")
    # 행 category 개수(셀 rows만 읽음). match % = category == "match" 비율이며, rdev v2 거부 문항의 올바른 거부는 "expected_refusal"로 따로 센다
    # (analyze_jt.py JSON의 note "match … 올바른 거부 포함"은 틀린 설명 — 수치는 그대로 두고 여기서 바로잡는다).
    from collections import Counter
    out += ["", "행 category 개수(셀 rows; rdev v2 gold = 거부 90·답하는 30):", "", "| 셀 | category 개수 |", "|---|---|"]
    for k, v in O.items():
        rows = json.loads((ROOT / v["file"]).read_text(encoding="utf-8"))["rows"]
        out.append(f"| {k} | " + ", ".join(f"{c} {n}" for c, n in Counter(r.get("category") for r in rows).most_common()) + " |")
    return out


def main():
    L = ["<!-- report_jt.py가 jt_results.json에서 생성. 손으로 고치지 않음 -->", ""]
    for i, cond in enumerate(["S", "G1"]):
        C = R["conditions"][cond]
        L += [f"## 표 1{'ab'[i]}. 조건 {cond}: 27B와 학생 arm (%, [95% CI]) — {C['condition']}", "", "27B = Qwen/Qwen3.8-27B BF16 (vLLM), Ollama qwen3.8:27b(Q4_K_M)와 다른 빌드. 27B CI는 문항 재추출만, 학생은 U1.", ""]
        L += t1(C)
    for i, cond in enumerate(["S", "G1"]):
        L += ["", f"## 표 2{'ab'[i]}. 조건 {cond}: 학생 arm − 27B (%p, [95% CI], 문항 공유 재추출) — 회복 비율은 계산하지 않음", ""] + t2(R["conditions"][cond])
    for i, cond in enumerate(["S", "G1"]):
        L += ["", f"## 표 3{'ab'[i]}. 조건 {cond}: 형별·범주별·결과 분해·도구 유형별", ""] + t3(R["conditions"][cond])
    L += ["", "## 표 4. 지연·자원 (결정 113 방식: 고정 30문항, 동시 1, S)", ""] + t4()
    L += ["", "## 선택 셀(27B 단독, S, 개발 셋; 기술만)", ""] + opt()
    (HERE / "jt_tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("written", HERE / "jt_tables.md", len(L))


if __name__ == "__main__":
    main()
