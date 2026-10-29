# -*- coding: utf-8 -*-
"""client_test_10000 결과 요약: seed마다 묶음 c1–c5 셀을 합쳐 정답률(category == match)·결과 분류·오류 코드·잘림 호출을 세고,
pool·category(client_qa/synthetic_qa)별 정답률과 seed 평균을 ``results_ct10k.json``에 쓴다. 모델 호출 없음(셀·원문 파일만 읽는다).

    python3 summarize_ct10k.py
"""
import json
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
RAW = HERE.parents[1] / "training/generated/client_test_10000/raw"
SEEDS = ("o43", "o1016", "o7")


def pct(a, b):
    return round(100 * a / b, 2) if b else None


def main():
    items = {str(i["id"]): i for i in yaml.safe_load((HERE / "qa_test_10000.yaml").read_text(encoding="utf-8"))["items"]}
    out = {"items": len(items), "seeds": {}}
    for seed in SEEDS:
        rows, trunc, calls, walls = [], 0, 0, []
        for c in range(1, 6):
            cell = HERE / "cells" / f"ct10k_v4_{seed}_c{c}_s1.json"
            if not cell.exists():
                continue
            d = json.loads(cell.read_text(encoding="utf-8"))
            rows += d["rows"]
            walls.append(d["meta"]["vllm"]["wall_seconds"])
            for line in (RAW / f"ct10k_v4_{seed}_c{c}_s1_raw.jsonl").read_text(encoding="utf-8").splitlines():
                calls += 1
                trunc += json.loads(line).get("finish_reason") == "length"
        if not rows:
            continue
        n = len(rows)
        ok = sum(r["category"] == "match" for r in rows)
        groups = {}
        for key in ("pool", "category"):
            g = {}
            for r in rows:
                v = items[r["id"]][key]
                g.setdefault(v, [0, 0])
                g[v][0] += r["category"] == "match"
                g[v][1] += 1
            groups[key] = {v: {"match": a, "of": b, "pct": pct(a, b)} for v, (a, b) in sorted(g.items())}
        out["seeds"][seed] = {
            "items": n, "match": ok, "match_pct": pct(ok, n),
            "grounding_ok": sum(bool(r["grounding_ok"]) for r in rows),
            "categories": dict(Counter(r["category"] for r in rows).most_common()),
            "outcomes": dict(Counter(r["outcome"] for r in rows).most_common()),
            "error_codes": dict(Counter(r["error_code"] for r in rows if r["error_code"]).most_common()),
            "llm_calls": calls, "truncated_calls": trunc, "wall_seconds": round(sum(walls), 1), "by": groups}
    done = [s for s in out["seeds"].values() if s["items"] == len(items)]
    if len(done) == len(SEEDS):
        out["mean_match_pct"] = round(sum(s["match_pct"] for s in done) / len(done), 2)
        out["all_seeds_match"] = sum(all(x) for x in zip(*[[r == "match" for r in _cats(seed)] for seed in SEEDS]))
        out["any_seed_match"] = sum(any(x) for x in zip(*[[r == "match" for r in _cats(seed)] for seed in SEEDS]))
    (HERE / "results_ct10k.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({s: {k: v[k] for k in ("items", "match_pct", "truncated_calls")} for s, v in out["seeds"].items()}, ensure_ascii=False))


def _cats(seed):
    rows = {}
    for c in range(1, 6):
        for r in json.loads((HERE / "cells" / f"ct10k_v4_{seed}_c{c}_s1.json").read_text(encoding="utf-8"))["rows"]:
            rows[r["id"]] = r["category"]
    return [rows[i] for i in sorted(rows)]


if __name__ == "__main__":
    main()
