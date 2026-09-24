# -*- coding: utf-8 -*-
"""L1 trigger가 기존 H0 관측 어디에 걸리는지 LLM 없이 센다.

기록된 H0 첫 grounding 응답을 제품 parser로 읽고 ``aggregation_refinement.triggered``를
적용한다. 보정 prompt를 쓰기 전에, trigger가 고칠 대상에 걸리고 집계와 무관한 질의에는
걸리지 않는지 확인하기 위한 것이다.

사용: python local_aggregation_trigger_replay.py --out <json>
"""

import argparse
import json
import os
import sys
from collections import Counter

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import aggregation_ab as B
import aggregation_plan as AP
import aggregation_refinement as R
import evaluate_prompt_ab as A
import failure_census as C
import paraphrase_corpus as P
from geoflow.errors import GeoFlowError
from geoflow.grounding import parse_grounding
from geoflow.planner import parse_planner_json

H0_CENSUS = "evaluation/prompt_ab/20260924_005520_census_head"
AGGREGATION_DEV = "evaluation/prompt_ab/20260924_032103_aggregation_holdout_h0_h2_r2"
#: 전역 H2에서 새로 조용한 오답이 된 질의. 보정 대상이 되면 안 된다.
H2_ONLY_SILENT = ("f12_p0", "f04_p2", "h05_p2", "h06_p0")


def initial_grounding(row):
    """H0 첫 응답을 제품 parser로 읽는다. 읽지 못하면 None(보정하지 않음)."""
    try:
        payload = parse_planner_json(row.get("raw_text") or "")
        if not isinstance(payload, dict) or payload.get("unsupported"):
            return None
        return parse_grounding(payload, row.get("question") or "", raw_text=row.get("raw_text"))
    except GeoFlowError:
        return None


def census_coverage():
    rows = {json.loads(line)["id"]: json.loads(line)
            for line in open(f"{H0_CENSUS}/census_rows.jsonl", encoding="utf-8")}
    _meta, observations, _report = A.load_run(H0_CENSUS)
    gold = C.goldens()
    out = []
    for obs in observations:
        row = rows[obs["id"]]
        grounding = initial_grounding(obs)
        factors = dict(grounding.factors) if grounding else {}
        raw = C._factors(C._payload(obs.get("raw_text")))
        gold_factors = C._factors(gold.get(obs["intent_id"]))
        out.append({
            "id": obs["id"], "intent": obs["intent_id"], "outcome": row["outcome"],
            "stage_swapped": "stage_swapped" in C.aggregation_families(raw, gold_factors),
            "trigger": R.triggered(grounding),
            "rollup_without_bucket": "rollup" in factors and "bucket" not in factors,
            "initial_factors": factors,
        })
    return out


def dev_coverage():
    _meta, observations, _report = A.load_run(AGGREGATION_DEV)
    items = {item["id"]: item for item in P.load_corpus_items(B.HOLDOUT)}
    goldens = {intent["intent"]: intent.get("golden") for intent in P.load_corpus(B.HOLDOUT)}
    out = []
    for obs in observations:
        if obs["variant"] != "H0_AGG" or obs.get("measurement") != A.VALID:
            continue
        note = B.annotate(obs, items[obs["id"]], goldens[obs["intent_id"]])
        grounding = initial_grounding(obs)
        factors = dict(grounding.factors) if grounding else {}
        semantic = note["semantic"]
        out.append({
            "id": obs["id"], "intent": obs["intent_id"], "cell": note["cell"],
            "gold_bucket": bool(semantic and "bucket" in semantic),
            "final_strict": note["final_strict"], "silent_wrong": note["silent_wrong"],
            "stage_swapped": AP.STAGE_SWAPPED in note["aggregation_errors"],
            "trigger": R.triggered(grounding),
            "rollup_without_bucket": "rollup" in factors and "bucket" not in factors,
            "initial_factors": factors,
        })
    return out


def _count(rows, where):
    chosen = [row for row in rows if where(row)]
    return {"observations": len(chosen), "triggered": sum(row["trigger"] for row in chosen),
            "intents": len({row["intent"] for row in chosen}),
            "triggered_intents": len({row["intent"] for row in chosen if row["trigger"]})}


def summarize(census, dev):
    return {
        "census": {
            "all": _count(census, lambda r: True),
            "stage_swapped": _count(census, lambda r: r["stage_swapped"]),
            "f01_silent": _count(census, lambda r: r["intent"].startswith("f01")
                                 and r["outcome"] == "SILENT_WRONG_PLAN"),
            "silent_wrong": _count(census, lambda r: r["outcome"] == "SILENT_WRONG_PLAN"),
            "correct": _count(census, lambda r: r["outcome"] == "CORRECT"),
            "rollup_without_bucket": _count(census, lambda r: r["rollup_without_bucket"]),
            "h2_only_silent": {rid: next(r["trigger"] for r in census if r["id"] == rid)
                               for rid in H2_ONLY_SILENT},
            "triggered_ids": sorted(r["id"] for r in census if r["trigger"]),
            "silent_not_triggered": sorted(r["id"] for r in census
                                           if r["outcome"] == "SILENT_WRONG_PLAN"
                                           and not r["trigger"]),
            "triggered_outcomes": dict(Counter(r["outcome"] for r in census if r["trigger"])),
        },
        "aggregation_dev_h0": {
            "all": _count(dev, lambda r: True),
            "gold_bucket": _count(dev, lambda r: r["gold_bucket"]),
            "gold_no_bucket": _count(dev, lambda r: not r["gold_bucket"]),
            "stage_swapped": _count(dev, lambda r: r["stage_swapped"]),
            "silent_wrong": _count(dev, lambda r: r["silent_wrong"]),
            "correct": _count(dev, lambda r: r["final_strict"]),
            "rollup_without_bucket": _count(dev, lambda r: r["rollup_without_bucket"]),
            "by_cell": {cell: _count(dev, lambda r, c=cell: r["cell"] == c)
                        for cell in sorted({r["cell"] for r in dev})},
            "gold_bucket_not_triggered": sorted(
                (r["id"], r["initial_factors"]) for r in dev
                if r["gold_bucket"] and not r["trigger"]),
            "gold_no_bucket_triggered": sorted(
                (r["id"], r["initial_factors"]) for r in dev
                if not r["gold_bucket"] and r["trigger"]),
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    census, dev = census_coverage(), dev_coverage()
    result = {"summary": summarize(census, dev), "census": census, "aggregation_dev_h0": dev}
    if args.out:
        with open(args.out, "x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2, default=str)
    json.dump(result["summary"], sys.stdout, ensure_ascii=False, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
