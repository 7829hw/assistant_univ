# -*- coding: utf-8 -*-
"""두 단계 집계에 H1("bucket이면 aggregation도 명시")을 가정해 적용해 본다.

제품 코드를 바꾸지 않는다. census가 남긴 첫 grounding을 LLM 호출 없이 다시 읽어,
H1 규칙이 무엇을 새로 거부하는지 센다.

    H0  bucket -> rollup, rollup -> bucket. aggregation은 생략 가능(Tool 기본 avg)
    H1  H0 + bucket -> aggregation

사용: python aggregation_replay.py <census run_dir>
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import failure_census as C

STAGE_FACTORS = ("bucket", "aggregation", "rollup")


def h0_rejects(factors):
    return ("bucket" in factors) != ("rollup" in factors)


def h1_rejects(factors):
    return h0_rejects(factors) or ("bucket" in factors and "aggregation" not in factors)


def expected_stages(row, golden):
    """기대하는 bucket·aggregation·rollup. Tool 인자 라벨을 먼저, 없으면 golden을 본다.

    라벨에 없는 key는 채점하지 않는 key다. 값이 None이면 라벨이 그 인자를
    묻지 않는다는 뜻이다.
    """
    labelled = row.get("expected_tool_args") or {}
    factors = C._factors(golden or {})
    return {key: labelled.get(key, factors.get(key)) for key in STAGE_FACTORS}


def classify(row, golden):
    factors = C._factors(C._payload(row.get("raw_text")) or {})
    expected = expected_stages(row, golden)
    if "bucket" not in factors and expected["bucket"] is None:
        return "unrelated"
    if h0_rejects(factors):
        return "already_rejected_by_h0"
    if not h1_rejects(factors):
        return ("h1_valid_currently_silent_wrong" if row["outcome"] == C.SILENT_WRONG_PLAN
                else "h1_valid")
    if row["outcome"] == C.SILENT_WRONG_PLAN:
        return "silent_wrong_h1_rejects"
    if row["initial_correct"]:
        return "correct_h1_newly_rejects"
    return "h1_rejects_other"


def replay(rows, goldens):
    out = []
    for row in rows:
        golden = goldens.get(row["intent_id"])
        factors = C._factors(C._payload(row.get("raw_text")) or {})
        out.append({
            "id": row["id"], "intent_id": row["intent_id"], "question": row["question"],
            "outcome": row["outcome"], "initial_correct": row["initial_correct"],
            "initial_error": row.get("initial_error"),
            "initial_stages": {key: factors.get(key) for key in STAGE_FACTORS},
            "expected_stages": expected_stages(row, golden),
            "arg_mismatches": row.get("arg_mismatches"),
            "h1": classify(row, golden),
        })
    return out


def summarize(replayed):
    related = [row for row in replayed if row["h1"] != "unrelated"]
    return {
        "observations": len(replayed),
        "related": len(related),
        "classes": dict(Counter(row["h1"] for row in related)),
        "intents_newly_rejected": sorted({row["intent_id"] for row in related
                                          if row["h1"] == "correct_h1_newly_rejects"}),
        "rows": related,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    run_dir = Path(args.run_dir)
    rows = [json.loads(line) for line in
            (run_dir / "census_rows.jsonl").read_text(encoding="utf-8").splitlines()]
    summary = summarize(replay(rows, C.goldens()))
    with open(run_dir / "aggregation_h1_replay.json", "x", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
    print(json.dumps({key: summary[key] for key in summary if key != "rows"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
