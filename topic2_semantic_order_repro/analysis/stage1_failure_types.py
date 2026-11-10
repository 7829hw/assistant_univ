"""Stage 1 (no GPU): failure-type breakdown of T1..T5 from EXISTING inference cells (CT10K, H-dev; A/B; r1 and the o2026131 r2 pair).

Item type (T1..T5/other) comes from the GOLD calls of the evaluation item (describes the question, never model output), as in analyze_t2.
Failure class comes from the row's own scorer output (`category`, `error_code`, `checks`); anything the evidence cannot place is `unclassified`.
Nothing here is used to shape any training order. H-final is not read.
"""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.argv = sys.argv[:1]
sys.path.insert(0, str(HERE.parents[1] / "topic2_semantic_order/analysis"))
import analyze_t2 as T  # noqa: E402

OUT = HERE.parent / "tables"
SEEDS = T.SEEDS
CLASSES = ["match", "wrong_tool", "wrong_metric", "wrong_aggregation", "wrong_time", "wrong_region", "wrong_od", "grounding_ok_exec_differs",
           "refused_unsupported", "failed_compiler_validator", "truncation", "answered_mismatch_unclassified", "failed_other"]
ARG_CLASS = {"metric": "wrong_metric", "aggregation": "wrong_aggregation", "rollup": "wrong_aggregation", "date": "wrong_time", "time": "wrong_time", "bucket": "wrong_time",
             "scope": "wrong_region", "name": "wrong_region", "region": "wrong_region", "include_vicinity": "wrong_region",
             "scope_pickup": "wrong_od", "scope_dropoff": "wrong_od", "dimension": "wrong_od", "dimension_target": "wrong_od", "limit": "wrong_od", "order": "wrong_od"}


def truncated(row):
    return any(x.get("finish_reason") == "length" for x in (row.get("hf_calls") or []))


def classify(row):
    cat = row["category"]
    if cat == "match":
        return "match"
    if truncated(row) and cat != "answered_mismatch":
        return "truncation"
    if cat == "refused_unsupported":
        return "refused_unsupported"
    ch = row.get("checks") or {}
    if cat == "failed":
        return "failed_compiler_validator" if row.get("error_code") else "failed_other"
    if cat == "answered_mismatch":
        if ch.get("tool_ok") is False:
            return "wrong_tool"
        mm = [m[0] for m in (ch.get("arg_mismatches") or [])]
        kinds = [ARG_CLASS[k] for k in mm if k in ARG_CLASS]
        if ch.get("place_lookups_ok") is False or ch.get("place_lookup_count_ok") is False:
            kinds.append("wrong_region")
        if kinds:
            order = ["wrong_metric", "wrong_aggregation", "wrong_time", "wrong_region", "wrong_od"]
            return next(k for k in order if k in kinds)  # first in a fixed priority; multi-error rows counted once
        if ch.get("args_ok") and ch.get("answer_value_ok") is False:
            return "grounding_ok_exec_differs"
        return "answered_mismatch_unclassified"
    return "failed_other"


def cells(dataset, arm, s):
    if dataset == "CT10K":
        return T.ct_paths(arm, s)
    return [T.hd_path(arm, s)]


def load(paths):
    rows = {}
    for p in paths:
        for r in json.loads((T.ROOT / p).read_text(encoding="utf-8"))["rows"]:
            rows[r["id"]] = r
    return rows


def main():
    gold = {"CT10K": T.load_gold(T.CT), "H-dev": T.load_gold(T.HDEV)}
    table, examples = [], defaultdict(list)
    series = [(a, s) for a in "AB" for s in SEEDS]
    for ds in ("CT10K", "H-dev"):
        tmap = {i: T.A13.tsig(g.get("gold")) for i, g in gold[ds].items()}
        runs = [(a, s, a) for a, s in series]
        if ds == "H-dev":  # repeat pair (r2), seed o2026131
            runs += [("A_r2", "o2026131", "A_r2"), ("B_r2", "o2026131", "B_r2")]
        for arm, s, label in runs:
            if arm.endswith("_r2"):
                p = [f"topic2_semantic_order/cells/hdev_t2_{'a0' if arm[0] == 'A' else 'b'}_o2026131_r2_s1.json"]
            else:
                p = cells(ds, arm, s)
            rows = load(p)
            per = defaultdict(Counter)
            for i, r in rows.items():
                t = tmap.get(i, "other")
                c = classify(r)
                per[t][c] += 1
                per["ALL"][c] += 1
                if t == "T1" and c not in ("match",) and len(examples[(ds, label, s, c)]) < 2:
                    examples[(ds, label, s, c)].append(i)
            for t, cnt in per.items():
                n = sum(cnt.values())
                table.append({"dataset": ds, "type": t, "arm": label, "seed": s, "items": n, **{c: cnt.get(c, 0) for c in CLASSES}})
    OUT.mkdir(exist_ok=True)
    with (OUT / "stage1_failure_types.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    (OUT / "stage1_t1_example_ids.json").write_text(json.dumps({"|".join(k): v for k, v in examples.items()}, ensure_ascii=False, indent=1))
    print(len(table), "rows")


if __name__ == "__main__":
    main()
