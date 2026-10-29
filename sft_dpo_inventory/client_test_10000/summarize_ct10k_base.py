# -*- coding: utf-8 -*-
"""client_test_10000 base 결과 요약(결정 260): base 회차 k=1·2·3의 묶음 c1–c5를 합쳐 ``summarize_ct10k.py``와 같은 수를 세고,
V4(seed 3개, ``results_ct10k.json``)와 문항 단위로 맞대어 ``results_ct10k_base.json``에 쓴다. 모델 호출 없음.

    python3 summarize_ct10k_base.py
"""
import json
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
RAW = HERE.parents[1] / "training/generated/client_test_10000/raw"
RUNS = {"base_k1": ("ct10k_base", 1), "base_k2": ("ct10k_base", 2), "base_k3": ("ct10k_base", 3)}
V4 = {"V4_o43": ("ct10k_v4_o43", 1), "V4_o1016": ("ct10k_v4_o1016", 1), "V4_o7": ("ct10k_v4_o7", 1)}


def pct(a, b):
    return round(100 * a / b, 2) if b else None


def load(prefix, k):
    rows, trunc, calls, wall = [], 0, 0, 0.0
    for c in range(1, 6):
        d = json.loads((HERE / "cells" / f"{prefix}_c{c}_s{k}.json").read_text(encoding="utf-8"))
        rows += d["rows"]
        wall += d["meta"]["vllm"]["wall_seconds"]
        for line in (RAW / f"{prefix}_c{c}_s{k}_raw.jsonl").read_text(encoding="utf-8").splitlines():
            calls += 1
            trunc += json.loads(line).get("finish_reason") == "length"
    return rows, trunc, calls, round(wall, 1)


def main():
    items = {str(i["id"]): i for i in yaml.safe_load((HERE / "qa_test_10000.yaml").read_text(encoding="utf-8"))["items"]}
    out, ok = {"items": len(items), "runs": {}}, {}
    for name, (prefix, k) in {**RUNS, **V4}.items():
        rows, trunc, calls, wall = load(prefix, k)
        ok[name] = {r["id"]: r["category"] == "match" for r in rows}
        if name in V4:
            continue
        n, m = len(rows), sum(ok[name].values())
        by = {}
        for key in ("pool", "category"):
            g = {}
            for r in rows:
                a = g.setdefault(items[r["id"]][key], [0, 0])
                a[0] += r["category"] == "match"
                a[1] += 1
            by[key] = {v: {"match": a, "of": b, "pct": pct(a, b)} for v, (a, b) in sorted(g.items())}
        out["runs"][name] = {
            "items": n, "match": m, "match_pct": pct(m, n), "grounding_ok": sum(bool(r["grounding_ok"]) for r in rows),
            "categories": dict(Counter(r["category"] for r in rows).most_common()),
            "outcomes": dict(Counter(r["outcome"] for r in rows).most_common()),
            "error_codes": dict(Counter(r["error_code"] for r in rows if r["error_code"]).most_common()),
            "llm_calls": calls, "truncated_calls": trunc, "wall_seconds": wall, "by": by}
    base, v4 = list(RUNS), list(V4)
    out["base_mean_match_pct"] = round(sum(out["runs"][r]["match_pct"] for r in base) / len(base), 2)
    out["base_all_runs_match"] = sum(all(ok[r][i] for r in base) for i in items)
    out["base_any_run_match"] = sum(any(ok[r][i] for r in base) for i in items)
    # 문항 단위 맞대기: 문항마다 3표본 중 맞힌 수(base 0–3, V4 0–3).
    nb = {i: sum(ok[r][i] for r in base) for i in items}
    nv = {i: sum(ok[r][i] for r in v4) for i in items}
    pair = {"V4_better": sum(nv[i] > nb[i] for i in items), "base_better": sum(nb[i] > nv[i] for i in items),
            "same": sum(nv[i] == nb[i] for i in items),
            "base_0_V4_3": sum(nb[i] == 0 and nv[i] == 3 for i in items), "base_3_V4_0": sum(nb[i] == 3 and nv[i] == 0 for i in items)}
    by_pool = {}
    for key in ("pool", "category"):
        g = {}
        for i, it in items.items():
            a = g.setdefault(it[key], [0, 0, 0])
            a[0] += nb[i]
            a[1] += nv[i]
            a[2] += 3
        by_pool[key] = {v: {"base_pct": pct(a, n), "V4_pct": pct(b, n), "diff_pp": round(pct(b, n) - pct(a, n), 2)} for v, (a, b, n) in sorted(g.items())}
    out["paired_vs_V4"] = {"per_item_match_counts": pair, "by": by_pool,
                           "V4_mean_match_pct": pct(sum(nv.values()), 3 * len(items)), "base_mean_match_pct": pct(sum(nb.values()), 3 * len(items))}
    (HERE / "results_ct10k_base.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({r: out["runs"][r]["match_pct"] for r in base} | {"pair": pair}, ensure_ascii=False))


if __name__ == "__main__":
    main()
