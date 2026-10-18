# -*- coding: utf-8 -*-
"""A1(epoch 2 반대 방향): selection_v2에서 e2 − e1이 s43은 내려가고 s1016은 올라간 것을 문항·실패 유형으로 본다. 모델 호출 없음.

    hfvenv/bin/python a1_epoch2.py   # -> a1_epoch2.json

- 모델별 e2 − e1(문항 짝 bootstrap), 문항 변화 벡터 상관(F43·P43·F1016·P1016 사이), 변화가 몰린 gold 계획 특징 부분집합.
- 실패 유형(report_class)·U·구조·thinking 길이·"결론" 유형의 e1 → e2 변화.
- e2의 seed 간 차(s43 − s1016)가 e1보다 작아지는지(epoch 2가 seed 차를 줄이는가).
"""
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import itemdata as I  # noqa: E402
from a1_items import feats  # noqa: E402

rng = np.random.default_rng(20261109)


def ci(d):
    b = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(10000)]
    return [round(100 * float(np.percentile(b, 2.5)), 2), round(100 * float(np.percentile(b, 97.5)), 2)]


def main():
    rows = [json.loads(l) for l in (HERE / "samples_s3.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = [r for r in rows if r["set"] == "sel"]
    acc = defaultdict(lambda: defaultdict(list))
    for r in rows:
        acc[r["model"]][r["id"]].append(r)
    items = sorted(acc["F43e1"])
    gold = I.gold("sel")
    v = {m: np.array([np.mean([x["ok"] for x in acc[m][i]]) for i in items]) for m in acc}
    out = {"items": len(items), "models": {}}
    delta = {}
    for m in ("F43", "P43", "F1016", "P1016"):
        d = v[f"{m}e2"] - v[f"{m}e1"]
        delta[m] = d
        sub = defaultdict(list)
        for j, i in enumerate(items):
            for f in feats("sel", gold[i])[1]:
                sub[f].append(j)
        prof = {}
        for e in ("e1", "e2"):
            rr = [x for i in items for x in acc[f"{m}{e}"][i]]
            n = len(rr)
            prof[e] = {"ok": round(100 * np.mean([x["ok"] for x in rr]), 2), "U": round(100 * np.mean([x["U"] for x in rr]), 2),
                       "struct": round(100 * np.mean([x["struct"] for x in rr]), 2), "repair": round(100 * np.mean([x["repair"] for x in rr]), 2),
                       "think_median": int(np.median([x["think_tokens"] for x in rr])),
                       "concl_iii": round(100 * sum("iii" in x["concl"] for x in rr) / n, 1),
                       "wrong_by_class": dict(Counter(x["cls"] for x in rr if not x["ok"]).most_common())}
        out["models"][m] = {"e2_minus_e1": round(100 * d.mean(), 2), "ci95": ci(d), "items_up": int((d > 0).sum()), "items_down": int((d < 0).sum()),
                            "subsets": {k: round(100 * float(d[j].mean()), 1) for k, j in sorted(sub.items())}, "profile": prof}
    out["corr_item_change"] = {f"{a}~{b}": round(float(np.corrcoef(delta[a], delta[b])[0, 1]), 3) for a, b in combinations(delta, 2)}
    out["seed_gap"] = {arm: {"e1": round(100 * float((v[f"{arm}43e1"] - v[f"{arm}1016e1"]).mean()), 2),
                             "e2": round(100 * float((v[f"{arm}43e2"] - v[f"{arm}1016e2"]).mean()), 2),
                             "e2_ci95": ci(v[f"{arm}43e2"] - v[f"{arm}1016e2"])} for arm in ("F", "P")}
    (HERE / "a1_epoch2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for m, x in out["models"].items():
        print(m, x["e2_minus_e1"], x["ci95"], x["items_up"], x["items_down"], {e: {k: x["profile"][e][k] for k in ("ok", "U", "struct", "think_median", "concl_iii")} for e in ("e1", "e2")})
        print("   ", x["subsets"])
    print(out["corr_item_change"])
    print(out["seed_gap"])


if __name__ == "__main__":
    main()
