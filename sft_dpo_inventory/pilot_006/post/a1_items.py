# -*- coding: utf-8 -*-
"""A1(문항 단위): 같은 arm의 s43과 s1016 모델을 주 셋 151문항에서 비교(F, P 각각). 모델 호출 없음.

    hfvenv/bin/python a1_items.py   # -> a1_items.json

- 문항 정답률 = k=4 표본 평균. 차이(s43 − s1016)의 분포, 한쪽만 맞히는 문항(≥ 0.5 차이) 수, 큰 차이 문항 목록.
- 실패 유형: report_class·첫 오류 코드 분포(seed별), U·구조·thinking token·"결론"(ii) 비율.
- 부분집합: gold 계획(``gold_text``·``gold``) 정규식 특징 — dt(dimension_target), od(scope_pickup/dropoff), 실차(taxi_status 또는 trip 도구),
  주변(include_vicinity), bucket, dimension(…별), 순위(order/limit), 집계(aggregation), 거부 기대(expected_outcome ≠ answered); 출처 묶음(id 앞부분).
- 같은 seed 안 F와 P의 문항 차이가 seed 간 차이와 얼마나 겹치는지(문항 차이 벡터의 상관).
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import itemdata as I  # noqa: E402

PAIRS = {"F": ("F43e1", "F1016e1"), "P": ("P43e1", "P1016e1")}


def feats(st, g):
    t = (g.get("gold_text") or "") + " " + json.dumps(g.get("gold"), ensure_ascii=False)
    grp = "holdout" if st == "holdout" else g["id"].split("/")[0]
    out = {"dt": "dimension_target" in t, "od": bool(re.search(r"scope_(pickup|dropoff)", t)), "silcha": "taxi_status" in t or "trip" in t,
           "vicinity": "include_vicinity" in t, "bucket": "bucket" in t, "dimension": bool(re.search(r"\bdimension\b", t)),
           "rank": "order" in t or "limit" in t, "aggregation": "aggregation" in t, "refusal_expected": g.get("expected_outcome") != "answered"}
    return grp, [k for k, v in out.items() if v]


def boot(d, rng, n=10000):
    d = np.asarray(d, float)
    b = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(n)]
    return [round(100 * float(np.percentile(b, 2.5)), 2), round(100 * float(np.percentile(b, 97.5)), 2)]


def main():
    rows = [json.loads(l) for l in (HERE / "samples_s3.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = [r for r in rows if r["set"] in ("sel", "holdout")]
    by = defaultdict(list)
    for r in rows:
        by[(r["model"], r["set"], r["id"])].append(r)
    items = [(st, i) for st in ("sel", "holdout") for i in I.gold(st) if ("F43e1", st, i) in by]  # selection_v2 = gold 100 중 98
    meta = {(st, i): feats(st, I.gold(st)[i]) for st, i in items}
    rng = np.random.default_rng(20261109)
    out = {"items": len(items), "arms": {}}
    diffs = {}
    for arm, (a, b) in PAIRS.items():
        acc = {m: np.array([np.mean([x["ok"] for x in by[(m, st, i)]]) for st, i in items]) for m in (a, b)}
        d = acc[a] - acc[b]
        diffs[arm] = d
        big = sorted(range(len(items)), key=lambda j: -abs(d[j]))[:15]
        res = {"ok_s43": round(100 * acc[a].mean(), 2), "ok_s1016": round(100 * acc[b].mean(), 2), "diff": round(100 * d.mean(), 2), "diff_ci95": boot(d, rng),
               "items_s43_better": int((d > 0).sum()), "items_s1016_better": int((d < 0).sum()), "items_equal": int((d == 0).sum()),
               "items_gap_ge_0.5": {"s43": int((d >= 0.5).sum()), "s1016": int((d <= -0.5).sum())},
               "items_all_right_one_seed_all_wrong_other": int(((acc[a] == 1) & (acc[b] == 0)).sum() + ((acc[a] == 0) & (acc[b] == 1)).sum()),
               "diff_sum_share_top15": round(float(np.abs(d[big]).sum() / max(1e-9, np.abs(d).sum())), 3),
               "largest": [{"set": items[j][0], "id": items[j][1], "s43": round(float(acc[a][j]), 2), "s1016": round(float(acc[b][j]), 2),
                            "group": meta[items[j]][0], "features": meta[items[j]][1]} for j in big]}
        for m, lab in ((a, "s43"), (b, "s1016")):
            mr = [x for x in rows if x["model"] == m]
            n = len(mr)
            wrong = [x for x in mr if not x["ok"]]
            res[lab] = {"samples": n, "U": round(100 * sum(x["U"] for x in mr) / n, 2), "silent": round(100 * sum(x["silent"] for x in mr) / n, 2),
                        "struct": round(100 * sum(x["struct"] for x in mr) / n, 2), "repair": round(100 * sum(x["repair"] for x in mr) / n, 2),
                        "think_tokens_median": int(np.median([x["think_tokens"] for x in mr])),
                        "think_tokens_p90": int(np.percentile([x["think_tokens"] for x in mr], 90)),
                        "concl_ii": round(100 * sum("ii" in x["concl"] for x in mr) / n, 1),
                        "wrong_by_class": dict(Counter(x["cls"] for x in wrong).most_common()),
                        "wrong_by_code": dict(Counter(x["code"] or "-" for x in wrong).most_common(10)),
                        "u_flags": dict(Counter(f for x in mr for f in (x["u_flags"] or [])).most_common(8))}
        sub = defaultdict(list)
        for j, it in enumerate(items):
            sub["group:" + meta[it][0]].append(j)
            for f in meta[it][1]:
                sub[f].append(j)
        res["subsets"] = {k: {"items": len(v), "s43": round(100 * acc[a][v].mean(), 1), "s1016": round(100 * acc[b][v].mean(), 1),
                              "diff": round(100 * d[v].mean(), 1), "share_of_total_diff": round(float(d[v].sum() / d.sum()), 2) if d.sum() else None}
                          for k, v in sorted(sub.items())}
        out["arms"][arm] = res
    out["corr_item_diff_F_vs_P"] = round(float(np.corrcoef(diffs["F"], diffs["P"])[0, 1]), 3)
    out["note"] = "corr > 0이면 s43이 잘하는 문항이 F·P에서 겹친다(seed가 arm과 무관하게 같은 문항에 작용)."
    (HERE / "a1_items.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for arm, r in out["arms"].items():
        print(arm, {k: r[k] for k in ("ok_s43", "ok_s1016", "diff", "diff_ci95", "items_s43_better", "items_s1016_better", "items_gap_ge_0.5", "diff_sum_share_top15")})
        for lab in ("s43", "s1016"):
            print(" ", lab, {k: r[lab][k] for k in ("U", "silent", "struct", "repair", "think_tokens_median", "concl_ii")}, r[lab]["wrong_by_class"])
        print("  subsets", {k: (v["items"], v["diff"]) for k, v in r["subsets"].items()})
    print("corr", out["corr_item_diff_F_vs_P"])


if __name__ == "__main__":
    main()
