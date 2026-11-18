# -*- coding: utf-8 -*-
"""판정 뒤 추가(사후, 결정 268) 보고 표 A–E를 수치 원본 JSON에서 그대로 만든다(손으로 옮기지 않음).

    python3 sft_dpo_inventory/pilot_010/results/tables_jp.py
      입력: results/jp_posthoc.json(analyze_jp.py), results/selection_jp_dev.json(select_s10.py), 있으면 results/jp_posthoc_b2f_base.json(표 B에 B2 F − base 추가)
      출력: results/jp_posthoc_tables.md, results/jp_posthoc_efficiency.json(표 E)

표 E는 jp_posthoc.json의 셀 정보(analyze_j.cell_info: 문항당 호출·wall p50·p95·잘림·서버 오류)를 arm별로 모은다. 점수·문항 내용은 읽지 않는다.
"""
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ["base", "B2F", "P9", "V8", "V4"]
NAME = {"base": "base", "B2F": "B2 F", "P9": "P9", "V8": "V8", "V4": "V4"}
TAG = "판정 뒤 추가(사후)"
ADDED = set()  # 측정 뒤 더한 비교(표 B에 † 표시)


def cell(e):
    if e is None:
        return "—"
    ci = e["ci95_pct"]
    ps = "·".join(f"{x:.2f}" for x in e["per_seed_pct"])
    return f"{e['mean_pct']:.2f} [{ci[0]:.2f}, {ci[1]:.2f}]<br>seed별 {ps} (n={e['seeds']})"


def dcell(e):
    ci = e["ci95_pp"]
    return f"{e['diff_pp']:+.2f} [{ci[0]:+.2f}, {ci[1]:+.2f}] ({e['x_seeds']}·{e['y_seeds']})"


def table_a(d):
    pa, ha = d["pf2"]["arms"], d["hfinal"]["arms"]
    out = [f"**표 A — arm별 지표({TAG})**. 칸: seed 평균 [95% CI, U1 bootstrap 10,000] / seed별 값 (seed 수). base는 PF2 k=8·H-final k=2를 한 단위로 본다.", "",
           "| arm | PF2 올바른 거부(50) | PF2 과잉 거부(답하는 100) | PF2 과잉 거부(근접 25) | PF2 정답률(100) | H-final 정답률(3,000) | H-final 과잉 거부율(3,000) |",
           "|---|---|---|---|---|---|---|"]
    for a in ARMS:
        p, h = pa[a], ha[a]
        out.append(f"| {NAME[a]} | {cell(p['correct_refusal'])} | {cell(p['over_refusal_100'])} | {cell(p['over_refusal_contrast25'])} | {cell(p['accuracy_100'])} "
                   f"| {cell(h['accuracy'])} | {cell(h['over_refusal'])} |")
    return out


def table_b(d):
    cm = d["comparisons"]
    keys = [("pf2_correct_refusal", "P1 올바른 거부"), ("pf2_over_refusal_100", "P2 과잉 거부 100"), ("pf2_over_refusal_contrast25", "P2 근접 25"),
            ("pf2_accuracy_100", "P3 PF2 정답률"), ("hfinal_accuracy", "P4 H-final 정답률"), ("hfinal_over_refusal", "H-final 과잉 거부")]
    out = [f"**표 B — 차이(%p, {TAG})**. 칸: 차 [95% CI] (x seed 수·y seed 수). U1 bootstrap 10,000, 통계량마다 `default_rng(20261109)`.", "",
           "| 비교 | " + " | ".join(k[1] for k in keys) + " |", "|---|" + "---|" * len(keys)]
    for pr in cm:
        mark = " †" if pr in ADDED else ""
        out.append(f"| {pr.replace('B2F', 'B2 F')}{mark} | " + " | ".join(dcell(cm[pr][k]) for k, _ in keys) + " |")
    if ADDED:
        out += ["", "† 측정·보고 뒤 사용자 지시(2026-11-18)로 같은 방식으로 더한 비교(`analyze_jp_b2f_base.py` → `jp_posthoc_b2f_base.json`; 기존 비교·arm 값·분해는 다시 실행해도 모두 같음)."]
    return out


CATS = [("correct", "정답"), ("refused_M", "거부 M"), ("refused_P", "거부 P"), ("refused_C", "거부 C"), ("truncated", "잘림"), ("U", "U(용납할 수 없는 실패)"),
        ("silent", "조용한 오답"), ("other_fail", "그 밖 실패")]


def short(e):
    ps = "·".join(f"{x:.2f}" for x in e["per_seed_pct"])
    return f"{e['mean_pct']:.2f}<br>({ps})"


def table_c(d):
    out = [f"**표 C1 — 답하는 문항 결과 분해({TAG})**. 표본마다 한 범주(정답 → 거부 M·P·C → 잘림 → U → 조용한 오답 → 그 밖 실패 순). 칸: seed 평균 % (seed별). 행 합 = 100.", ""]
    for part, key, title in (("hfinal", "decomposition_3000", "H-final 3,000"), ("pf2", "decomposition_100", "PF2 답하는 100")):
        out += [f"*{title}*", "", "| arm | " + " | ".join(c[1] for c in CATS) + " | U1·U2·U3·U4(겹침 허용) |", "|---|" + "---|" * (len(CATS) + 1)]
        for a in ARMS:
            dc = d[part][key][a]
            fam = dc["U_flag_families_overlapping"]
            fs = "·".join(f"{fam[f]['mean_pct']:.2f}" for f in ("U1", "U2", "U3", "U4"))
            out.append(f"| {NAME[a]} | " + " | ".join(short(dc["categories"][c]) for c, _ in CATS) + f" | {fs} |")
        out.append("")
    dv = d["hfinal_v4_minus_b2f_decomposition"]
    out += [f"**표 C2 — H-final V4 − B2 F 정답률 차 분해(%p, {TAG})**. Δ정답 = −Σ Δ범주.", "",
            "| 범주 | Δ [95% CI] |", "|---|---|"]
    for c, n in CATS:
        out.append(f"| {n} | {dcell(dv['overall'][c])} |")
    out += ["", "*도구 유형별(점추정, %p)*", "", "| 도구 유형 | 문항 | " + " | ".join(c[1] for c in CATS) + " |", "|---|---|" + "---|" * len(CATS)]
    for t, v in sorted(dv["by_tool_type"].items(), key=lambda kv: kv[1]["correct"]):
        out.append(f"| {t} | {v['items']} | " + " | ".join(f"{v[c]:+.2f}" for c, _ in CATS) + " |")
    tg = sorted(dv["by_template_group"].items(), key=lambda kv: kv[1]["correct"])
    out += ["", f"*template_group별(점추정, %p) — 전체 {len(tg)}개 중 Δ정답이 가장 낮은 12개와 가장 높은 5개. 전체는 `jp_posthoc.json`.*", "",
            "| template_group | 문항 | " + " | ".join(c[1] for c in CATS) + " |", "|---|---|" + "---|" * len(CATS)]
    for t, v in tg[:12] + [("…", None)] + tg[-5:]:
        if v is None:
            out.append("| … |" + " |" * (len(CATS) + 1))
            continue
        out.append(f"| {t} | {v['items']} | " + " | ".join(f"{v[c]:+.2f}" for c, _ in CATS) + " |")
    return out


def table_d(d, sel):
    dv = d["dev_vs_protected"]
    s3 = dv["selection_stage_V4_3seeds"]["variants"]["V4"]
    e5 = dv["posthoc_EA_V4_5seeds"]["variants"]["V4"]
    pf = d["pf2"]["arms"]["V4"]
    hf = d["hfinal"]["arms"]["V4"]
    seeds = pf["seeds_present"]
    out = [f"**표 D — 개발 셋 대 보호 셋(V4, {TAG})**. 개발 셋 = refusal_dev v2 올바른 거부·과잉 거부, 개발 셋 정답률(valid98+aux, select_s10 정의). "
           "보호 셋 = PF2(k=4)·H-final(k=1). 선택 단계 3 seed(o43·o1016·o7)는 다른 학습 seed이며 PF2·H-final 측정이 없다.", "",
           "| 학습 seed | 개발 올바른 거부 | 개발 과잉 거부 | 개발 셋 정답률 | PF2 올바른 거부 | PF2 과잉 거부 100 | PF2 정답률 | H-final 정답률 |", "|---|---|---|---|---|---|---|---|"]
    for i, s in enumerate(seeds):
        e = e5["per_seed"][s]
        out.append(f"| {s}(사후 E-A) | {e['refusal_pct']:.2f} | {e['over_refusal_pct']:.2f} | {e['dev_ok_pct']:.2f} | {pf['correct_refusal']['per_seed_pct'][i]:.2f} "
                   f"| {pf['over_refusal_100']['per_seed_pct'][i]:.2f} | {pf['accuracy_100']['per_seed_pct'][i]:.2f} | {hf['accuracy']['per_seed_pct'][i]:.2f} |")
    out.append(f"| **5 seed 평균** | **{e5['refusal_pct']:.2f}** | **{e5['over_refusal_pct']:.2f}** | **{e5['dev_ok_pct']:.2f}** | **{pf['correct_refusal']['mean_pct']:.2f}** "
               f"| **{pf['over_refusal_100']['mean_pct']:.2f}** | **{pf['accuracy_100']['mean_pct']:.2f}** | **{hf['accuracy']['mean_pct']:.2f}** |")
    for s, e in s3["per_seed"].items():
        out.append(f"| {s}(선택 단계) | {e['refusal_pct']:.2f} | {e['over_refusal_pct']:.2f} | {e['dev_ok_pct']:.2f} | — | — | — | — |")
    out.append(f"| **선택 단계 3 seed 평균** | **{s3['refusal_pct']:.2f}** | **{s3['over_refusal_pct']:.2f}** | **{s3['dev_ok_pct']:.2f}** | — | — | — | — |")
    ref = dv["posthoc_EA_V4_5seeds"]["reference"]
    out += ["", "참고(같은 select_s10 출력의 기존 기준 셀, 개발 셋): " + "; ".join(
        f"{NAME[a]} {ref[a]['refusal_pct']:.2f} / {ref[a]['over_refusal_pct']:.2f} / {ref[a]['dev_ok_pct']:.2f}" for a in ("base", "B2F", "P9") if a in ref) + " (올바른 거부 / 과잉 거부 / 정답률)."]
    return out


def efficiency(d):
    res = {}
    for part in ("pf2", "hfinal"):
        agg = defaultdict(list)
        for k, cs in d[part]["cells"].items():
            agg[k.split(":")[0]] += cs
        res[part] = {}
        for a in ARMS:
            cs = agg[a]
            rows, calls = sum(c["rows"] for c in cs), sum(c["llm_calls_total"] for c in cs)
            res[part][a] = {"cells": len(cs), "rows": rows, "llm_calls": calls, "llm_calls_per_item": round(calls / rows, 3),
                            "wall_p50_s_median_of_cells": round(st.median(c["wall_p50_s"] for c in cs), 2),
                            "wall_p50_s_range": [min(c["wall_p50_s"] for c in cs), max(c["wall_p50_s"] for c in cs)],
                            "wall_p95_s_median_of_cells": round(st.median(c["wall_p95_s"] for c in cs), 2),
                            "wall_p95_s_range": [min(c["wall_p95_s"] for c in cs), max(c["wall_p95_s"] for c in cs)],
                            "truncated_calls": sum(c["truncated_calls"] for c in cs), "server_error_rows": sum(c["server_error_rows"] for c in cs),
                            "concurrency": sorted({c["concurrency"] for c in cs})}
    return res


def table_e(eff):
    out = [f"**표 E — arm별 비용({TAG})**. 문항당 LLM 호출 = 전체 호출/전체 행. wall = 문항별 started→finished(초)의 셀별 p50·p95, 칸은 셀 중앙값 [최소–최대]. "
           "동시 요청 수(PF2 8, H-final 32)에 따라 달라지는 값이라 같은 셋 안에서만 비교한다.", "",
           "| 셋 | arm | 셀 | 문항당 호출 | wall p50 | wall p95 | 잘림 호출 / 전체 호출 | 서버 오류 행 |", "|---|---|---|---|---|---|---|---|"]
    for part, nm in (("pf2", "PF2"), ("hfinal", "H-final")):
        for a in ARMS:
            e = eff[part][a]
            out.append(f"| {nm} | {NAME[a]} | {e['cells']} | {e['llm_calls_per_item']:.3f} | {e['wall_p50_s_median_of_cells']:.1f} [{e['wall_p50_s_range'][0]:.1f}–{e['wall_p50_s_range'][1]:.1f}] "
                       f"| {e['wall_p95_s_median_of_cells']:.1f} [{e['wall_p95_s_range'][0]:.1f}–{e['wall_p95_s_range'][1]:.1f}] | {e['truncated_calls']} / {e['llm_calls']} "
                       f"({100 * e['truncated_calls'] / e['llm_calls']:.2f}%) | {e['server_error_rows']} |")
    return out


def main():
    d = json.loads((HERE / "jp_posthoc.json").read_text(encoding="utf-8"))
    sel = json.loads((HERE / "selection_jp_dev.json").read_text(encoding="utf-8"))
    extra = HERE / "jp_posthoc_b2f_base.json"
    if extra.exists():
        e = json.loads(extra.read_text(encoding="utf-8"))
        assert all(e["consistency_with_jp_posthoc"].values())
        d["comparisons"].update(e["comparison"])
        ADDED.update(e["comparison"])
    eff = efficiency(d)
    (HERE / "jp_posthoc_efficiency.json").write_text(json.dumps({"label": TAG, "decision": 268, "source": "results/jp_posthoc.json cells", "efficiency": eff},
                                                                ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    lines = [f"<!-- tables_jp.py가 jp_posthoc.json·selection_jp_dev.json에서 만든 표. {TAG}. -->", ""]
    for part in (table_a(d), table_b(d), table_c(d), table_d(d, sel), table_e(eff)):
        lines += part + [""]
    (HERE / "jp_posthoc_tables.md").write_text("\n".join(lines), encoding="utf-8")
    print("ok", len(lines))


if __name__ == "__main__":
    main()
