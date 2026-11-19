# -*- coding: utf-8 -*-
"""pilot_010 JG(결정 270) 보고 표 생성: ``jg_results.json``(+ 셀 meta·RERUNS_JG·runs.log)만 읽어 ``jg_tables.md``를 쓴다.
모델 호출·PF2 원문 접근 없음(집계 수치만 읽음). ``JG_RESULTS.md``의 표는 이 출력을 그대로 옮긴다.

    python3 sft_dpo_inventory/pilot_010/results/report_jg.py
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
P10 = HERE.parent
R = json.loads((HERE / "jg_results.json").read_text(encoding="utf-8"))
ARMS = ["base", "B2F", "P9", "V4", "V8", "RRNM12"]
MET = [("correct_refusal", "P1 PF2 올바른 거부(50)"), ("over_refusal_100", "P2 과잉 거부(답하는 100)"), ("over_refusal_contrast25", "P2c 과잉 거부(근접 대조 25)"),
       ("accuracy_100", "P3 PF2 정답률(100)"), ("hfinal_accuracy", "P4 H-final 정답률(3,000)"), ("hfinal_over_refusal", "H-final 과잉 거부")]


def f(x, nd=2):
    return "—" if x is None else f"{x:.{nd}f}"


def ci(c):
    return "—" if not c else f"[{f(c[0])}, {f(c[1])}]"


def arm_table(block):
    out = ["| 지표 | " + " | ".join(R["names"][a] for a in ARMS) + " |", "|---|" + "---|" * len(ARMS)]
    for k, lab in MET:
        cells = []
        for a in ARMS:
            m = block["arms"][a]["metrics"].get(k)
            cells.append("—" if not m else f"{f(m['mean_pct'])} {ci(m['ci95_pct'])}")
        out.append(f"| {lab} | " + " | ".join(cells) + " |")
    return out


def seed_table(block):
    out = ["| arm | seed | " + " | ".join(lab.split(" ")[0] for _, lab in MET) + " |", "|---|---|" + "---|" * len(MET)]
    for a in ARMS[:-1]:
        A = block["arms"][a]
        for i, s in enumerate(A["seeds"]):
            out.append(f"| {R['names'][a]} | {s} | " + " | ".join(f(A["metrics"][k]["per_seed_pct"][i]) for k, _ in MET) + " |")
        out.append(f"| {R['names'][a]} | seed SD(%p) | " + " | ".join(f(A["metrics"][k]["seed_sd_pp"]) for k, _ in MET) + " |")
    return out


def diff_table(diffs, names):
    out = ["| 비교 | " + " | ".join(lab.split(" ")[0] for _, lab in MET) + " |", "|---|" + "---|" * len(MET)]
    for key, d in diffs.items():
        x, y = key.split("-")
        out.append(f"| {names[x]} − {names[y]} | " + " | ".join(f"{f(d[k]['diff_pp'])} {ci(d[k]['ci95_pp'])}" if k in d else "—" for k, _ in MET) + " |")
    return out


def opsamp_table():
    out = ["| arm | " + " | ".join(lab.split(" ")[0] for _, lab in MET) + " |", "|---|" + "---|" * len(MET)]
    for a in ARMS:
        d = R["operating_minus_sampling"][a]["paired_diff"]
        out.append(f"| {R['names'][a]} | " + " | ".join(f"{f(d[k]['mean_pct'])} {ci(d[k]['ci95_pct'])}" if k in d else "—" for k, _ in MET) + " |")
    return out


def decomp_tables(block):
    keys = ["correct", "refused_M", "refused_P", "refused_C", "truncated", "U", "silent", "other_fail"]
    out = ["PF2 답하는 100 결과 분해(seed 평균 %):", "", "| arm | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for a in ARMS:
        d = block["arms"][a].get("pf2_decomposition_100_seed_mean") or {}
        out.append(f"| {R['names'][a]} | " + " | ".join(f(d.get(k)) for k in keys) + " |")
    out += ["", "H-final 3,000 결과 분해(seed 평균 %):", "", "| arm | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    for a in ARMS:
        d = (block["arms"][a].get("hfinal") or {}).get("decomposition_seed_mean") or {}
        out.append(f"| {R['names'][a]} | " + " | ".join(f(d.get(k)) for k in keys) + " |")
    out += ["", "PF2 형별 올바른 거부(%, seed 평균; 문항 수 M 34·P 10·C 6):", "", "| arm | M | P | C |", "|---|---|---|---|"]
    for a in ARMS:
        d = block["arms"][a].get("pf2_correct_refusal_by_form") or {}
        out.append(f"| {R['names'][a]} | " + " | ".join(f(d.get(x, {}).get("pct")) for x in "MPC") + " |")
    types = list((block["arms"]["base"]["hfinal"]["accuracy_by_tool_type_seed_mean"]).keys())
    n = {t: block["arms"]["base"]["hfinal"]["accuracy_by_tool_type_seed_mean"][t]["items"] for t in types}
    out += ["", "H-final 도구 유형별 정답률(%, seed 평균):", "", "| arm | " + " | ".join(f"{t}({n[t]})" for t in types) + " |", "|---|" + "---|" * len(types)]
    for a in ARMS:
        d = block["arms"][a]["hfinal"]["accuracy_by_tool_type_seed_mean"]
        out.append(f"| {R['names'][a]} | " + " | ".join(f(d[t]["pct"]) for t in types) + " |")
    out += ["", "template_group 붕괴(30문항 이상 그룹, 같은 조건 base 대비, seed 평균 그룹 수):", "", "| arm | 그룹 | −20%p 이하 | −30%p 이하 |", "|---|---|---|---|"]
    for a in ARMS[1:]:
        h = block["arms"][a]["hfinal"]
        g = next(iter(h["group_collapse_per_seed"].values()))["groups_ge30"]
        out.append(f"| {R['names'][a]} | {g} | {f(h['group_collapse_mean']['below_base_20pp'], 1)} | {f(h['group_collapse_mean']['below_base_30pp'], 1)} |")
    return out


def cost_table(block):
    out = ["| arm | PF2 호출/문항 | PF2 wall p50 s | PF2 wall p95 s | H-final 호출/문항 | H-final wall p50 s | H-final wall p95 s |", "|---|---|---|---|---|---|---|"]
    for a in ARMS:
        c = block["arms"][a].get("cost_seed_mean") or {}
        p, h = c.get("pf2", {}), c.get("hfinal", {})
        out.append(f"| {R['names'][a]} | {f(p.get('llm_calls_per_item'), 3)} | {f(p.get('wall_p50_s'))} | {f(p.get('wall_p95_s'))} | "
                   f"{f(h.get('llm_calls_per_item'), 3)} | {f(h.get('wall_p50_s'))} | {f(h.get('wall_p95_s'))} |")
    return out


def trunc_table():
    rr = json.loads((P10 / "RERUNS_JG.json").read_text(encoding="utf-8"))["reruns"]
    out = ["| H-final 셀(G1) | 호출 | 잘린 호출 | 잘림 % | 다시 돌리기 | 원본 잘림 % |", "|---|---|---|---|---|---|"]
    for p in sorted((P10 / "cells/JG").glob("hfinalg1_*_s1.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        raw = Path(d["meta"]["hf"]["raw_out"])
        recs = [json.loads(x) for x in raw.read_text(encoding="utf-8").splitlines()]
        t = sum(x.get("finish_reason") == "length" for x in recs)
        r = rr.get(p.stem)
        out.append(f"| {p.stem} | {len(recs)} | {t} | {100 * t / len(recs):.2f} | {r['job'] if r else '—'} | {f(r['truncated_pct']) if r else '—'} |")
    return out


def main():
    op, sa = R["operating"], R["sampling"]
    L = [f"<!-- report_jg.py가 jg_results.json에서 생성. 손으로 고치지 않음 -->", "", "## 표 1. arm별 운영 조건(G1) 결과 (%, [95% CI], U1 bootstrap 10,000)", ""]
    L += arm_table(op) + ["", "seed별 값(%):", ""] + seed_table(op)
    L += ["", "## 표 2. 운영 조건 안의 차이 (%p, [95% CI])", ""] + diff_table(op["differences"], R["names"])
    L += ["", "기술용 추가:", ""] + diff_table(op["differences_extra_descriptive"], R["names"])
    L += ["", "## 표 3. 운영 조건 대 sampling", "", "sampling 조건 같은 함수 결과(%, [95% CI]):", ""] + arm_table(sa)
    L += ["", "sampling 조건 안의 차이(%p):", ""] + diff_table(sa["differences"], R["names"])
    L += ["", "운영 − sampling(같은 어댑터 seed 짝, %p, [95% CI]):", ""] + opsamp_table()
    L += ["", "## 표 4. 결과 분해·형별·유형별 (운영 조건)", ""] + decomp_tables(op)
    L += ["", "## 표 5. 비용 (운영 조건, seed 평균)", ""] + cost_table(op)
    L += ["", "## 셀별 잘림 (H-final, 다시 돌린 뒤 최종 셀)", ""] + trunc_table()
    (HERE / "jg_tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("written", HERE / "jg_tables.md", len(L))


if __name__ == "__main__":
    main()
