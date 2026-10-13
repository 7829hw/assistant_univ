# -*- coding: utf-8 -*-
"""pilot_003 checkpoint 선택과 중단 규칙(PROTOCOL_v3 6·7절, 결정 73의 HF 경로 적용). 모델 호출 없음.

    tokvenv/bin/python sft_dpo_inventory/pilot_003/selection/analyze_selection.py --stage sft \
        --base HF-base --cand sft_stepA=/path/adapter --cand sft_stepB=/path/adapter --out selection_sft.json

- 입력: ``selection/runs/<label>_s<k>.json``(k = 1..4, selection_v2 98문항, sampling). 원문(루프 판정)은 ignore 경로
  ``training/generated/pilot_003/raw/<label>_s<k>_raw.jsonl``.
- 셀 통계·비교는 calibration_001 ``analyze_cal.py``의 함수(``load_sample``, ``cell_stats``, ``compare``, ``boot_ci``) 그대로다.
  bootstrap은 비교마다 ``default_rng(20261109)``를 새로 만든다(비교 순서와 무관하게 같은 값).
- 선택(7절 4): 문항 평균 grounding_ok가 가장 높은 checkpoint. 같으면 U 비율이 낮은 것, 그다음 늦은 step.
- 중단 규칙(7절 5): ``--stop-rule``이면 고른 checkpoint의 HF-base → checkpoint grounding_ok 차이 95% CI 하한 > 0일 때만 진행.
- checkpoint마다 기록: 문항 평균 정답률, U·조용한 오답 비율, 지연 중앙값, 생성 상한(done_reason length) 호출 수, 루프 호출 수,
  실차 통행량 오독(``occupied_misread``) 문항·표본 수, 오류 유형 비율, 안정 정답 문항 수. 학습 쪽 값(loss, step 시간, peak 메모리)은
  ``--train-log``로 받은 요약을 그대로 붙인다.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/calibration_001"))
import analyze_cal as A  # noqa: E402

A.RAW = ROOT / "training/generated/pilot_003/raw"
RUNS = HERE / "runs"
IDS = (HERE / "selection_v2_ids.txt").read_text(encoding="utf-8").strip().split(",")
SEED = 20261109


def load(label, gold):
    out, metas = [], []
    for k in range(1, A.K + 1):
        meta, rows = A.load_sample(RUNS / f"{label}_s{k}.json", gold)
        if set(rows) != set(IDS):
            raise SystemExit(f"{label}_s{k}: 문항이 selection_v2 98개와 다르다")
        out.append(rows)
        metas.append({"sample": k, "device": A.device(meta), "seed": (meta.get("hf") or {}).get("decoding", {}).get("round_seed")})
    return out, metas


def mats(samples):
    m = {f: np.array([[float(s[i][f] if f != "U" else s[i]["class"] == A.CS.U_CLASS) for s in samples] for i in IDS])
         for f in ("ok", "U") + A.ERRORS}
    m["silent"] = np.array([[float(s[i]["class"] == A.CS.SILENT) for s in samples] for i in IDS])
    return m


def stats(samples, m):
    st = A.cell_stats(m["ok"], m["U"], np.random.default_rng(SEED))
    st["silent_pct"] = round(100 * float(m["silent"].mean()), 2)
    st["error_rates_pct"] = {e: round(100 * float(m[e].mean()), 2) for e in A.ERRORS}
    st["occupied_misread_item_samples"] = int(m["occupied_misread"].sum())
    st["latency_median_s"] = round(float(np.median([s[i]["seconds"] for s in samples for i in IDS])), 2)
    st["length_capped_calls"] = int(sum(s[i]["truncated"] for s in samples for i in IDS))
    loops = [s[i]["loop_calls"] for s in samples for i in IDS]
    st["loop_calls"] = None if any(x is None for x in loops) else int(sum(loops))
    return st


def versus(a, b, ma, mb, sa, sb):
    r = A.compare(a, b, ma["ok"], mb["ok"], ma["U"], mb["U"], np.random.default_rng(SEED), sa, sb)
    ds = mb["silent"].mean(axis=1) - ma["silent"].mean(axis=1)
    r["silent_diff_pct"] = round(100 * float(ds.mean()), 2)
    r["silent_ci95_pct"] = [round(100 * x, 2) for x in A.boot_ci(ds, np.random.default_rng(SEED))]
    r["latency_ratio"] = round(sb["latency_median_s"] / sa["latency_median_s"], 3)
    return {k: v for k, v in r.items() if not k.startswith("_")}


def step_of(label):
    m = re.search(r"step(\d+)", label)
    return int(m.group(1)) if m else -1


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage", required=True)
    p.add_argument("--base", default="HF-base")
    p.add_argument("--cand", action="append", required=True, help="LABEL=ADAPTER_DIR")
    p.add_argument("--train-log", default=None, help="학습 요약 JSON(label → loss·step 시간·peak 메모리)")
    p.add_argument("--stop-rule", action="store_true")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    gold = {i["id"]: i for i in A.EV.load_gold(A.CS.GOLD)["items"]}
    cands = dict(c.split("=", 1) for c in args.cand)
    data = {}
    for label in [args.base, *cands]:
        samples, metas = load(label, gold)
        m = mats(samples)
        data[label] = {"samples": samples, "m": m, "stats": stats(samples, m), "meta": metas}
    train_doc = json.loads(Path(args.train_log).read_text(encoding="utf-8")) if args.train_log else {}
    train = train_doc.get("checkpoints", {})
    run_level = {k: v for k, v in train_doc.items() if k != "checkpoints"}
    rows = []
    for label, adapter in cands.items():
        d = data[label]
        rows.append({"label": label, "adapter": adapter, "step": step_of(label), "cell": d["stats"], "samples": d["meta"],
                     "vs_base": versus(args.base, label, data[args.base]["m"], d["m"], data[args.base]["stats"], d["stats"]),
                     "train": {**(train.get(label) or {}), "run": run_level} if train_doc else None})
    best = sorted(rows, key=lambda r: (-r["cell"]["mean_pct"], r["cell"]["u_pct"], -r["step"]))[0]
    out = {"stage": args.stage, "set": "selection_v2(98)", "k": A.K, "rule": "max mean grounding_ok; tie: lower U, then later step",
           "base": {"label": args.base, "cell": data[args.base]["stats"], "samples": data[args.base]["meta"]},
           "candidates": rows, "selected": {"label": best["label"], "adapter": best["adapter"], "step": best["step"]}}
    if args.stop_rule:
        lo = best["vs_base"]["ci95_pct"][0]
        out["stop_rule"] = {"comparison": f"{args.base}→{best['label']}", "ci95_pct": best["vs_base"]["ci95_pct"],
                            "lower_bound_gt_0": lo > 0, "proceed_to_vendor100": lo > 0}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for r in rows:
        c, v = r["cell"], r["vs_base"]
        print(f"{r['label']:14s} mean {c['mean_pct']:6.2f} U {c['u_pct']:5.2f} silent {c['silent_pct']:5.2f} occ {c['occupied_misread_item_samples']} "
              f"lat {c['latency_median_s']} cap {c['length_capped_calls']} loop {c['loop_calls']} | d {v['diff_pct']} CI {v['ci95_pct']} "
              f"U {v['U_diff_pct']} CI {v['U_ci95_pct']} silent {v['silent_diff_pct']} CI {v['silent_ci95_pct']}")
    b = data[args.base]["stats"]
    print(f"{args.base:14s} mean {b['mean_pct']:6.2f} U {b['u_pct']:5.2f} silent {b['silent_pct']:5.2f} occ {b['occupied_misread_item_samples']} lat {b['latency_median_s']}")
    print("selected", json.dumps(out["selected"]), json.dumps(out.get("stop_rule"), ensure_ascii=False))


if __name__ == "__main__":
    main()
