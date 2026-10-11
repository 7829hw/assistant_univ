"""결과를 본 뒤의 탐색 분석(사후 정의, 판정에 쓰지 않음): dimension_target 누락과 dimension=week/month.

- valid98: 정답에 dimension_target이 있는 문항(gold에 문자열 포함) 부분집합의 Full vs P0.2 정답률과 paired bootstrap CI.
- grounding_diffs의 factor:dimension_target를 (gold, pred)로 센다. valid98과 업체 100(ab_p0/runs의 Full·P0·P0.1·P0.2).
- planner 첫 응답의 dimension 값이 week/month/day/hour인 경우를 센다.

사용: python explore_failure_modes.py --out explore_failure_modes.json
"""
import argparse
import collections
import csv
import json
import os
import random
import re
import statistics

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GOLD = os.path.join(ROOT, "sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml")
V98 = os.path.join(HERE, "raw")
V100 = os.path.join(HERE, "..", "ab_p0", "runs")
ROUNDS = range(1, 6)
DIM_TIME = re.compile(r'"dimension":\s*"(week|month|day|hour)"')


def rows(path):
    return json.load(open(path))["rows"]


def dt_counts(base, arm):
    c = collections.Counter()
    for r in ROUNDS:
        p = os.path.join(base, f"{arm}_sample_r{r}.json")
        if not os.path.exists(p):
            return None
        for x in rows(p):
            for d in x.get("grounding_diffs") or []:
                if d[0] == "factor:dimension_target":
                    c[f"gold={d[1]} pred={d[2]}"] += 1
    return dict(c)


def first_plan(x):
    calls = x.get("llm_calls")
    if isinstance(calls, str):
        m = re.search(r"'content': '(.*?)', 'thinking_chars'", calls, re.S)
        return m.group(1).replace("\\n", "\n").replace('\\"', '"') if m else ""
    for c in calls or []:
        if c.get("kind") == "plan":
            return c.get("content") or ""
    return ""


def subset(rows_csv, ids):
    out = {}
    for name, sel in (("with_dimension_target", lambda r: r["id"] in ids),
                      ("without_dimension_target", lambda r: r["id"] not in ids)):
        R = [r for r in rows_csv if sel(r)]
        f = sum(int(r["k_full"]) for r in R) / (5 * len(R))
        p = sum(int(r["k_p0_2"]) for r in R) / (5 * len(R))
        d = [(int(r["k_p0_2"]) - int(r["k_full"])) / 5 for r in R]
        rng = random.Random(0)
        bs = sorted(statistics.mean(rng.choices(d, k=len(d))) for _ in range(10000))
        out[name] = {"n": len(R), "full": f, "p0_2": p, "diff": p - f, "ci95": [bs[249], bs[9749]]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    items = yaml.safe_load(open(GOLD))["items"]
    ids = {it["id"] for it in items if "dimension_target" in json.dumps(it, ensure_ascii=False)}
    rows_csv = list(csv.DictReader(open(os.path.join(HERE, "paired_items.csv"))))
    dim_time = {}
    for arm in ("full", "p0_2"):
        c = collections.Counter()
        for r in ROUNDS:
            for x in rows(os.path.join(V98, f"{arm}_sample_r{r}.json")):
                if DIM_TIME.search(first_plan(x)):
                    c[x["id"]] += 1
        dim_time[arm] = {"total": sum(c.values()), "items": dict(sorted(c.items()))}
    res = {
        "note": "사후 탐색. 부분집합은 결과를 본 뒤 정했다. gate 판정에 쓰지 않는다.",
        "valid98_subset": subset(rows_csv, ids),
        "dimension_target_diffs": {
            "valid98": {arm: dt_counts(V98, arm) for arm in ("full", "p0_2")},
            "vendor100": {arm: dt_counts(V100, arm) for arm in ("full", "p0", "p0_1", "p0_2")},
        },
        "first_response_dimension_time_bucket": dim_time,
    }
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
