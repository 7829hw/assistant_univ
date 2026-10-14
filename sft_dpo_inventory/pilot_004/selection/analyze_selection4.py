# -*- coding: utf-8 -*-
"""pilot_004 checkpoint 선택과 중단 규칙(PROTOCOL_v4 8절, 결정 96). 모델 호출 없음.

    HF_HOME=... HF_HUB_OFFLINE=1 hfvenv/bin/python sft_dpo_inventory/pilot_004/selection/analyze_selection4.py --stage sft \
        --cand sft_step460=/path --cand sft_step920=/path --train-log train_logs/sft_summary.json --out selection_sft.json [--stop-rule]

- 기준값(PROTOCOL_v4 5절): pilot_prep_007 ``serving_vllm_fp8/runs/vllm-bf16-base_s1–4.json``(vLLM BF16, flashinfer, 동시 요청 8, selection_v2 98, k=4).
- 후보: ``selection/runs/<label>_s1–4.json``(같은 조건, adapter는 LoRA). 원문(루프 판정) ``training/generated/pilot_004/raw``.
- 셀 통계·비교는 ``pilot_003/vendor100/judge_v3.py``와 같은 계산(analyze_cal 함수, 비교마다 ``default_rng(20261109)``).
- 선택(v3 7절 4): 문항 평균 grounding_ok가 가장 높은 checkpoint, 같으면 U 비율이 낮은 것, 그다음 늦은 step.
- 중단 규칙(``--stop-rule``, 결정 96): 고른 checkpoint의 base 대비 grounding_ok 차이 CI 하한 > 0 **그리고** U 차이 CI 하한 ≤ 0일 때만 진행.
- checkpoint마다: 평균, U·조용한 오답, 생성 상한·루프 수, 실차 통행량 오독(occupied_misread), vicinity 빠짐(결정 94·97), 오류 유형, 표본별 장치·동시 요청·커널·요청 로그 요약,
  학습 쪽 값(``--train-log``의 loss, step 시간, peak 메모리, adapter sha256).
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_003/vendor100"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/serving_vllm_fp8"))
import judge_v3 as J  # noqa: E402
import analyze_fp8 as F  # noqa: E402  (vicinity, run_meta)

A = J.A
BASE = (ROOT / "sft_dpo_inventory/serving_vllm_fp8/runs", "vllm-bf16-base", ROOT / "training/generated/serving_vllm_fp8/raw")
RUNS = HERE / "runs"
RAW = ROOT / "training/generated/pilot_004/raw"
IDS = (ROOT / "sft_dpo_inventory/pilot_003/selection/selection_v2_ids.txt").read_text(encoding="utf-8").strip().split(",")


def step_of(label):
    m = re.search(r"step(\d+)", label)
    return int(m.group(1)) if m else -1


def load(cfg, gold, runs, label, raw):
    A.RAW = raw
    samples, metas = J.load_cell({**cfg, "runs": runs, "prefix": ""}, label, gold)
    if samples is None:
        raise SystemExit(f"{label} 표본이 없다")
    if any(set(s) != set(IDS) for s in samples):
        raise SystemExit(f"{label}: 문항이 selection_v2 98개와 다르다")
    return samples, metas


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage", required=True)
    p.add_argument("--cand", action="append", required=True)
    p.add_argument("--train-log", default=None)
    p.add_argument("--stop-rule", action="store_true")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    cfg = dict(J.SETS["selftest"])
    gold = {i["id"]: i for i in A.EV.load_gold(cfg["gold"])["items"]}
    ids = [i for i in gold if i in set(IDS)]
    cells = {"vLLM-base": BASE}
    cands = dict(c.split("=", 1) for c in args.cand)
    for label in cands:
        cells[label] = (RUNS, label, RAW)
    data = {}
    for name, (runs, label, raw) in cells.items():
        samples, metas = load(cfg, gold, runs, label, raw)
        m = J.mats(samples, ids)
        st = J.cell_summary(samples, m, ids, 4)
        st["vicinity_missing(decision 94)"], m["vic"] = F.vicinity(runs, label, ids, gold)
        st["run_meta"] = F.run_meta(runs, label)
        data[name] = {"m": m, "stats": st, "samples": metas}
    train_doc = json.loads(Path(args.train_log).read_text(encoding="utf-8")) if args.train_log else {}
    rows = []
    for label, adapter in cands.items():
        d, b = data[label], data["vLLM-base"]
        v = J.versus("vLLM-base", label, b["m"], d["m"], b["stats"], d["stats"], ids)
        dv = d["m"]["vic"].mean(axis=1) - b["m"]["vic"].mean(axis=1)
        v["vicinity_missing_diff_pct"] = round(100 * float(dv.mean()), 2)
        v["vicinity_missing_ci95_pct"] = [round(100 * x, 2) for x in A.boot_ci(dv, np.random.default_rng(J.SEED))]
        rows.append({"label": label, "adapter": adapter, "step": step_of(label), "cell": d["stats"], "samples": d["samples"],
                     "vs_base": v, "train": ({**(train_doc.get("checkpoints", {}).get(label) or {}),
                                              "run": {k: x for k, x in train_doc.items() if k != "checkpoints"}} if train_doc else None)})
    best = sorted(rows, key=lambda r: (-r["cell"]["mean_pct"], r["cell"]["u_pct"], -r["step"]))[0]
    out = {"stage": args.stage, "set": "selection_v2(98)", "k": 4, "path": "vLLM 0.30.0 BF16, flashinfer, LoRA, 동시 요청 8",
           "rule": "max mean grounding_ok; tie: lower U, then later step",
           "base": {"label": "vLLM-base(pilot_prep_007 vllm-bf16-base, PROTOCOL_v4 5절)", "cell": data["vLLM-base"]["stats"],
                    "samples": data["vLLM-base"]["samples"]},
           "candidates": rows, "selected": {"label": best["label"], "adapter": best["adapter"], "step": best["step"]}}
    if args.stop_rule:
        v = best["vs_base"]
        c1, c2 = v["ci95_pct"][0] > 0, v["U_ci95_pct"][0] <= 0
        out["stop_rule(decision 96)"] = {"comparison": f"vLLM-base→{best['label']}", "grounding_ok_ci95_pct": v["ci95_pct"],
                                         "U_ci95_pct": v["U_ci95_pct"], "cond1_accuracy_ci_lower_gt_0": c1,
                                         "cond2_U_ci_lower_le_0": c2, "proceed_to_vendor100": c1 and c2}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for r in rows:
        c, v = r["cell"], r["vs_base"]
        print(f"{r['label']:14s} mean {c['mean_pct']:6.2f} U {c['u_pct']:5.2f} silent {c['silent_pct']:5.2f} occ {c['occupied_misread_item_samples']} "
              f"cap {c['length_capped_calls']} loop {c['loop_calls']} vic {c['vicinity_missing(decision 94)']['missing_item_samples']} | "
              f"d {v['diff_pct']} CI {v['ci95_pct']} U {v['U_diff_pct']} CI {v['U_ci95_pct']} silent {v['silent_diff_pct']} CI {v['silent_ci95_pct']}")
    b = data["vLLM-base"]["stats"]
    print(f"{'vLLM-base':14s} mean {b['mean_pct']:6.2f} U {b['u_pct']:5.2f} silent {b['silent_pct']:5.2f} occ {b['occupied_misread_item_samples']}")
    print("selected", json.dumps(out["selected"]), json.dumps(out.get("stop_rule(decision 96)"), ensure_ascii=False))


if __name__ == "__main__":
    main()
