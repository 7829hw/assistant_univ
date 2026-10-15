# -*- coding: utf-8 -*-
"""pilot_005 후보 7개 비교, 선택, 중단 규칙(PROTOCOL_v5 3·4절, 결정 102·103). 모델 호출 없음.

    HF_HOME=... HF_HUB_OFFLINE=1 hfvenv/bin/python sft_dpo_inventory/pilot_005/analyze_selection5.py [--out selection.json]

- 기준값(vLLM-base): pilot_prep_007 ``serving_vllm_fp8/runs/vllm-bf16-base_s1–4.json``(PROTOCOL_v5 3절, v4 5절).
- 후보(m = 7 고정, 결정 102):
  - V1·V2·V3 checkpoint 2개씩: ``train_logs/<variant>_summary.json``의 checkpoint, 셀 ``runs/<variant>_step<N>_s1–4.json``, 원문 ``training/generated/pilot_005/raw``.
  - pilot_004 SFT 934: ``pilot_004/selection/runs/sft_step934_s1–4.json``(PROTOCOL_v5 3절, 다시 씀), 원문 ``training/generated/pilot_004/raw``.
  - 학습이 실패했거나 셀이 없는 후보는 "없음"으로 남기고, 보정의 m은 7 그대로다.
- 셀 통계·95% CI는 ``pilot_003/vendor100/judge_v3.py``와 같은 계산(10,000회, 비교마다 ``default_rng(20261109)``).
- 99.29% CI(결정 103): 문항 단위 쌍 bootstrap 20,000회, 새 ``default_rng(20261109)``, 백분위 [0.05/14, 1 − 0.05/14].
- 고르는 방법: U 차이 95% CI 하한 ≤ 0인 후보 중 정답 표본 수 최대 → U 표본 수 최소 → 누적 학습 step 최소(V3은 934 + 자기 step).
- 중단 규칙: 고른 후보의 정답률 차이 99.29% CI 하한 > 0 그리고 U 차이 95% CI 하한 ≤ 0.
- 결과: ``selection.json``(전체), ``selection_table.md``(후보 7개 비교표).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_003/vendor100"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/serving_vllm_fp8"))
import judge_v3 as J  # noqa: E402
import analyze_fp8 as F  # noqa: E402  (vicinity, run_meta)

A = J.A
M = 7
ALPHA = 0.05 / M
REPS_BONF = 20000
BASE = (ROOT / "sft_dpo_inventory/serving_vllm_fp8/runs", "vllm-bf16-base", ROOT / "training/generated/serving_vllm_fp8/raw")
P4 = ROOT / "sft_dpo_inventory/pilot_004"
RUNS = HERE / "runs"
RAW = ROOT / "training/generated/pilot_005/raw"
IDS = (ROOT / "sft_dpo_inventory/pilot_003/selection/selection_v2_ids.txt").read_text(encoding="utf-8").strip().split(",")
VARIANTS = {"v1": ("V1 SFT seed 43, 2 epoch", 0), "v2": ("V2 SFT 3 epoch", 0), "v3": ("V3 약한 DPO(SFT 934에서, lr 5e-6, 0.5 epoch)", 934)}
EXPECTED = ["v1_step467", "v1_step934", "v2_step934", "v2_step1401", "v3_step97", "v3_step193", "p4_sft_step934"]
REAL_WORD = ["old44/g02", "old44/g04"]   # 질문에 "실차"가 있는 실차 통행량 문항
N33 = "indepv2/n33"                       # "손님을 태운 택시"(실차라는 말 없음)


def boot_ci_level(d, alpha, reps, rng):
    idx = rng.integers(0, len(d), size=(reps, len(d)))
    means = d[idx].mean(axis=1)
    return [float(np.percentile(means, 100 * alpha / 2)), float(np.percentile(means, 100 * (1 - alpha / 2)))]


def load(cfg, gold, runs, label, raw):
    A.RAW = raw
    samples, metas = J.load_cell({**cfg, "runs": runs, "prefix": ""}, label, gold)
    if samples is None:
        return None, None
    if any(set(s) != set(IDS) for s in samples):
        raise SystemExit(f"{label}: 문항이 selection_v2 98개와 다르다")
    return samples, metas


def candidates():
    out = {}
    for v, (desc, offset) in VARIANTS.items():
        p = HERE / "train_logs" / f"{v}_summary.json"
        doc = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
        for label, ck in ((doc or {}).get("checkpoints") or {}).items():
            out[label] = {"variant": v, "desc": desc, "runs": RUNS, "cell": label, "raw": RAW, "step": ck["step"], "cum_step": offset + ck["step"],
                          "train": {**ck, "run": {k: x for k, x in doc.items() if k != "checkpoints"}}}
    s4 = json.loads((P4 / "train_logs/sft_summary.json").read_text(encoding="utf-8"))
    out["p4_sft_step934"] = {"variant": "p4", "desc": "pilot_004 SFT checkpoint-934(기록 다시 씀)", "runs": P4 / "selection/runs", "cell": "sft_step934",
                             "raw": ROOT / "training/generated/pilot_004/raw", "step": 934, "cum_step": 934,
                             "train": {**s4["checkpoints"]["sft_step934"], "run": {k: x for k, x in s4.items() if k != "checkpoints"}}}
    return out


def real_trip(samples):
    def count(items, f):
        return int(sum(s[i][f] for s in samples for i in items))
    return {"실차_표현(g02,g04)": {"occupied_misread_samples": count(REAL_WORD, "occupied_misread"), "ok_samples": count(REAL_WORD, "ok"),
                                  "samples": len(REAL_WORD) * len(samples)},
            "n33": {"occupied_misread_samples": count([N33], "occupied_misread"), "ok_samples": count([N33], "ok"), "samples": len(samples)}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default=str(HERE / "selection.json"))
    args = p.parse_args()
    cfg = dict(J.SETS["selftest"])
    gold = {i["id"]: i for i in A.EV.load_gold(cfg["gold"])["items"]}
    ids = [i for i in gold if i in set(IDS)]
    bs, bmeta = load(cfg, gold, *BASE[:2], BASE[2])
    bm = J.mats(bs, ids)
    bst = J.cell_summary(bs, bm, ids, 4)
    bst["vicinity_missing(decision 94)"], bm["vic"] = F.vicinity(BASE[0], BASE[1], ids, gold)
    bst["real_trip"] = real_trip(bs)
    cands = candidates()
    rows = []
    for label in EXPECTED + sorted(set(cands) - set(EXPECTED)):
        c = cands.get(label)
        if c is None:
            rows.append({"label": label, "status": "없음(학습 실패 또는 checkpoint 없음)"})
            continue
        samples, metas = load(cfg, gold, c["runs"], c["cell"], c["raw"])
        if samples is None:
            rows.append({"label": label, "status": "없음(셀 없음)", "train": c["train"]})
            continue
        m = J.mats(samples, ids)
        st = J.cell_summary(samples, m, ids, 4)
        st["vicinity_missing(decision 94)"], m["vic"] = F.vicinity(c["runs"], c["cell"], ids, gold)
        st["run_meta"] = F.run_meta(c["runs"], c["cell"])
        st["real_trip"] = real_trip(samples)
        st["ok_samples"], st["U_samples"] = int(m["ok"].sum()), int(m["U"].sum())
        v = J.versus("vLLM-base", label, bm, m, bst, st, ids)
        d = m["ok"].mean(axis=1) - bm["ok"].mean(axis=1)
        v[f"ci{100 * (1 - ALPHA):.2f}_pct(bonferroni m=7, {REPS_BONF} reps)"] = [round(100 * x, 2) for x in
                                                                               boot_ci_level(d, ALPHA, REPS_BONF, np.random.default_rng(J.SEED))]
        dv = m["vic"].mean(axis=1) - bm["vic"].mean(axis=1)
        v["vicinity_missing_diff_pct"] = round(100 * float(dv.mean()), 2)
        v["vicinity_missing_ci95_pct"] = [round(100 * x, 2) for x in A.boot_ci(dv, np.random.default_rng(J.SEED))]
        v["U_condition(U_ci95_lower_le_0)"] = v["U_ci95_pct"][0] <= 0
        rows.append({"label": label, "status": "평가함", "variant": c["variant"], "desc": c["desc"], "step": c["step"], "cum_step": c["cum_step"],
                     "cell_source": str((c["runs"] / c["cell"]).relative_to(ROOT)), "cell": st, "samples": metas, "vs_base": v, "train": c["train"]})
    key99 = f"ci{100 * (1 - ALPHA):.2f}_pct(bonferroni m=7, {REPS_BONF} reps)"
    ok_rows = [r for r in rows if r["status"] == "평가함" and r["vs_base"]["U_condition(U_ci95_lower_le_0)"]]
    ranked = sorted(ok_rows, key=lambda r: (-r["cell"]["ok_samples"], r["cell"]["U_samples"], r["cum_step"]))
    best = ranked[0] if ranked else None
    out = {"set": "selection_v2(98)", "k": 4, "path": "vLLM 0.30.0 BF16, flashinfer attention·sampler, LoRA, 동시 요청 8",
           "m_candidates": M, "alpha_each": ALPHA, "evaluated": sum(r["status"] == "평가함" for r in rows),
           "rule": "U 차이 95% CI 하한 ≤ 0인 후보 중 정답 표본 수 최대 → U 표본 수 최소 → 누적 학습 step 최소(결정 103)",
           "base": {"label": "vLLM-base(pilot_prep_007 vllm-bf16-base, PROTOCOL_v5 3절)", "cell": bst, "samples": bmeta},
           "candidates": rows, "ranking_U_ok": [r["label"] for r in ranked],
           "selected": ({"label": best["label"], "variant": best["variant"], "step": best["step"], "cum_step": best["cum_step"],
                         "adapter": best["train"].get("adapter_file")} if best else None)}
    if best:
        v = best["vs_base"]
        c1, c2 = v[key99][0] > 0, v["U_ci95_pct"][0] <= 0
        out["stop_rule(decision 103)"] = {"comparison": f"vLLM-base→{best['label']}", "grounding_ok_ci9929_pct": v[key99],
                                          "grounding_ok_ci95_pct(reference)": v["ci95_pct"], "U_ci95_pct": v["U_ci95_pct"],
                                          "cond1_accuracy_ci9929_lower_gt_0": c1, "cond2_U_ci95_lower_le_0": c2, "proceed_to_vendor100": c1 and c2}
    else:
        out["stop_rule(decision 103)"] = {"comparison": None, "reason": "U 조건을 만족한 후보 없음", "proceed_to_vendor100": False}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    # 비교표
    b = bst
    lines = ["# pilot_005 후보 7개 비교(selection_v2 98문항, k=4, vLLM BF16 flashinfer LoRA, 동시 요청 8)", "",
             f"`analyze_selection5.py`가 만든 표. 차이는 base 대비 %p. 99.29% CI는 Bonferroni(m=7) 20,000회, 95% CI는 10,000회. 선택: **{out['selected']['label'] if best else '없음'}**, "
             f"중단 규칙 진행 = **{out['stop_rule(decision 103)']['proceed_to_vendor100']}**.", "",
             "| 후보 | 누적 step | 정답률 | 차이 | 95% CI | 99.29% CI | U | U 차이 [95% CI] | U 조건 | 조용한 오답 | 조용한 오답 차이 [95% CI] | 상한·루프 | 실차 표현 오독 | n33 오독 | vicinity 빠짐 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
             f"| vLLM-base | – | {b['mean_pct']} | – | – | – | {b['u_pct']} | – | – | {b['silent_pct']} | – | {b['length_capped_calls']}·{b['loop_calls']} | "
             f"{b['real_trip']['실차_표현(g02,g04)']['occupied_misread_samples']}/8 | {b['real_trip']['n33']['occupied_misread_samples']}/4 | "
             f"{b['vicinity_missing(decision 94)']['missing_item_samples']}/{4 * b['vicinity_missing(decision 94)']['gold_vicinity_items']} |"]
    for r in rows:
        if r["status"] != "평가함":
            lines.append(f"| {r['label']} | – | {r['status']} | | | | | | | | | | | | |")
            continue
        c, v = r["cell"], r["vs_base"]
        lines.append(f"| {r['label']}{' **(선택)**' if best and r['label'] == best['label'] else ''} | {r['cum_step']} | {c['mean_pct']} | {v['diff_pct']:+.2f} | "
                     f"{v['ci95_pct']} | {v[key99]} | {c['u_pct']} | {v['U_diff_pct']:+.2f} {v['U_ci95_pct']} | {'만족' if v['U_condition(U_ci95_lower_le_0)'] else '불만족'} | "
                     f"{c['silent_pct']} | {v['silent_diff_pct']:+.2f} {v['silent_ci95_pct']} | {c['length_capped_calls']}·{c['loop_calls']} | "
                     f"{c['real_trip']['실차_표현(g02,g04)']['occupied_misread_samples']}/8 | {c['real_trip']['n33']['occupied_misread_samples']}/4 | "
                     f"{c['vicinity_missing(decision 94)']['missing_item_samples']}/{4 * c['vicinity_missing(decision 94)']['gold_vicinity_items']} |")
    lines += ["", "오류 유형(표본 비율 %):", "", "| 후보 | " + " | ".join(A.ERRORS) + " |", "|---|" + "---|" * len(A.ERRORS),
              "| vLLM-base | " + " | ".join(str(b["error_rates_pct"][e]) for e in A.ERRORS) + " |"]
    for r in rows:
        if r["status"] == "평가함":
            lines.append(f"| {r['label']} | " + " | ".join(str(r["cell"]["error_rates_pct"][e]) for e in A.ERRORS) + " |")
    (HERE / "selection_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("selected", json.dumps(out["selected"], ensure_ascii=False), json.dumps(out["stop_rule(decision 103)"], ensure_ascii=False))


if __name__ == "__main__":
    main()
