# -*- coding: utf-8 -*-
"""A4 thinking 길이 · A5 selection_v2 대 holdout, 주 셋 대 개발 셋. 모델 호출 없음.

    hfvenv/bin/python a4_a5.py   # -> a4_a5.json

A4
- 출력 thinking token(첫 계획 호출, Qwen3-8B tokenizer) 분포: base·F·P(seed별), 주 셋.
- 학습 데이터 thinking 길이: RC3 arm별 출처(teacher full_response / 8b json_only)별 중앙값·p90(thinking은 ``<think>`` 안).
- 문항 안 길이와 정답: 같은 (모델, 문항)에서 맞힌 표본과 틀린 표본이 둘 다 있을 때 thinking token 평균 차(맞음 − 틀림).
- 지연과 정답률: Gate E 30문항 지연 요약(``latency_summary.json``)과 모델별 주 셋 정답률을 나란히(30문항 지연은 s43만).
A5
- 모델별 selection_v2·holdout 정답률, base 대비 차이(paired item bootstrap), 두 셋에서 방향이 같은지.
- s43 두 모델의 셋별 P − F(주: sel·holdout, 개발: valid98·aux·vendor100)와 gold 계획 특징 부분집합별 P − F — 셋 구성 차이로 설명되는지.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import itemdata as I  # noqa: E402
from a1_items import feats  # noqa: E402

RC3 = ROOT / "sft_dpo_inventory/pilot_006/build/RC3"
MAIN_MODELS = ("base", "F43e1", "P43e1", "F1016e1", "P1016e1")


def q(v):
    v = np.asarray(v, float)
    return {"n": int(len(v)), "median": float(np.median(v)), "p10": float(np.percentile(v, 10)), "p90": float(np.percentile(v, 90)), "mean": round(float(v.mean()), 1)}


def boot(d, rng):
    d = np.asarray(d, float)
    b = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(10000)]
    return [round(100 * float(np.percentile(b, 2.5)), 2), round(100 * float(np.percentile(b, 97.5)), 2)]


def item_acc(rows, model, st):
    acc = defaultdict(list)
    for r in rows:
        if r["model"] == model and r["set"] == st:
            acc[r["id"]].append(r["ok"])
    return {i: float(np.mean(v)) for i, v in acc.items()}


def main():
    rows = [json.loads(l) for l in (HERE / "samples_s3.jsonl").read_text(encoding="utf-8").splitlines()]
    rng = np.random.default_rng(20261109)
    out = {"A4": {}, "A5": {}}
    main_rows = [r for r in rows if r["set"] in ("sel", "holdout")]
    out["A4"]["output_thinking_tokens_main"] = {m: q([r["think_tokens"] for r in main_rows if r["model"] == m]) for m in MAIN_MODELS + ("R2",)}
    tk = I.tok()
    td = {}
    for arm in ("full", "partial"):
        by = defaultdict(list)
        for l in (RC3 / arm / "sft_train.jsonl").read_text(encoding="utf-8").splitlines():
            r = json.loads(l)
            c = r["messages"][-1]["content"]
            th = c.split("</think>")[0].replace("<think>", "") if "</think>" in c else ""
            by[r["metadata"]["loss_scope"]].append(len(tk(th, add_special_tokens=False)["input_ids"]))
        td[arm] = {k: q(v) for k, v in by.items()}
    out["A4"]["training_thinking_tokens_rc3"] = td
    within = {}
    for m in MAIN_MODELS:
        g = defaultdict(lambda: ([], []))
        for r in main_rows:
            if r["model"] == m:
                g[(r["set"], r["id"])][0 if r["ok"] else 1].append(r["think_tokens"])
        d = [np.mean(a) - np.mean(b) for a, b in g.values() if a and b]
        if d:
            b = [np.asarray(d)[rng.integers(0, len(d), len(d))].mean() for _ in range(10000)]
            within[m] = {"items": len(d), "right_minus_wrong_tokens": round(float(np.mean(d)), 1),
                         "ci95": [round(float(np.percentile(b, 2.5)), 1), round(float(np.percentile(b, 97.5)), 1)]}
    out["A4"]["within_item_length_vs_correct"] = within
    lat = json.loads((ROOT / "sft_dpo_inventory/pilot_006/latency/run3/latency_summary.json").read_text(encoding="utf-8"))
    acc = {m: round(100 * float(np.mean([r["ok"] for r in main_rows if r["model"] == m])), 2) for m in MAIN_MODELS}
    out["A4"]["latency_vs_accuracy"] = {"latency_30q": {k: {kk: v[kk] for kk in ("median_model_seconds", "median_thinking_tokens")} for k, v in lat["cells"].items()},
                                        "main_set_ok_pooled_samples": acc}
    # A5
    per = {}
    for m in MAIN_MODELS[1:]:
        per[m] = {}
        for st in ("sel", "holdout"):
            a, b = item_acc(rows, "base", st), item_acc(rows, m, st)
            ids = sorted(set(a) & set(b))
            d = [b[i] - a[i] for i in ids]
            per[m][st] = {"ok": round(100 * float(np.mean([b[i] for i in ids])), 2), "base": round(100 * float(np.mean([a[i] for i in ids])), 2),
                          "minus_base": round(100 * float(np.mean(d)), 2), "ci95": boot(d, rng)}
        per[m]["same_direction"] = np.sign(per[m]["sel"]["minus_base"]) == np.sign(per[m]["holdout"]["minus_base"])
        per[m]["same_direction"] = bool(per[m]["same_direction"])
    out["A5"]["sel_vs_holdout"] = per
    pf = {}
    for st in ("sel", "holdout", "valid98", "aux", "vendor100"):
        f, p = item_acc(rows, "F43e1", st), item_acc(rows, "P43e1", st)
        ids = sorted(set(f) & set(p))
        gold = I.gold(st)
        d = np.array([p[i] - f[i] for i in ids])
        sub = defaultdict(list)
        for j, i in enumerate(ids):
            for x in feats(st, gold[i])[1]:
                sub[x].append(j)
        pf[st] = {"items": len(ids), "P_minus_F": round(100 * float(d.mean()), 2), "ci95": boot(d, rng),
                  "subsets": {k: {"items": len(v), "share_of_items": round(len(v) / len(ids), 2), "P_minus_F": round(100 * float(d[v].mean()), 1)} for k, v in sorted(sub.items())}}
    out["A5"]["P_minus_F_s43_by_set"] = pf
    (HERE / "a4_a5.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps(out["A4"]["output_thinking_tokens_main"], ensure_ascii=False))
    print(json.dumps(td, ensure_ascii=False))
    print(within)
    print(json.dumps(per, ensure_ascii=False))
    for st, v in pf.items():
        print(st, v["items"], v["P_minus_F"], v["ci95"], {k: (x["share_of_items"], x["P_minus_F"]) for k, x in v["subsets"].items()})


if __name__ == "__main__":
    main()
