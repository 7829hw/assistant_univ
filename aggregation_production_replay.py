# -*- coding: utf-8 -*-
"""flat 집계 계약(H0) census의 raw 응답을 H2 경로로 다시 돌린다. LLM 호출 없음.

집계 factor가 없는 응답은 두 계약에서 같은 grounding이어야 하므로 결과가 같아야 한다.
flat 집계 factor를 적은 응답은 새 계약에서 거부되는 것이 맞다. 행동 회귀로 세지 않고
따로 센다(그 의미의 동등성은 corpus golden으로 테스트가 확인한다).

사용: python aggregation_production_replay.py <H0 census run_dir>
"""

import argparse
import json
import os
import sys
from collections import Counter

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import aggregation_plan as AP
import evaluate_planner as E
import evaluate_prompt_ab as A
from failure_census import ReplayClient, _payload
from geoflow.composer import MacroComposer
from geoflow.macros import MacroLibrary

COMPARED = ("status", "validated", "macros", "operators", "final_tool", "final_tool_args",
            "repair_attempted", "repair_succeeded", "arg_mismatches", "correct")


def _evaluate(row, item, variant, composer):
    contents = [call.get("content") or "" for call in row.get("llm_calls") or []]
    planner = A.FixedPromptPlanner(client=ReplayClient(contents), variant=variant)
    return E.evaluate_once(planner, A.RecordingComposer(composer), item)


def uses_flat_aggregation(row):
    payload = _payload(row.get("raw_text")) or {}
    factors = payload.get("factors") if isinstance(payload.get("factors"), dict) else {}
    return [key for key in AP.FLAT_KEYS if key in factors]


def replay_run(run_dir):
    meta, rows, report = A.load_run(run_dir)
    if not report.clean:
        raise SystemExit("무결성 문제로 재생하지 않는다")
    h0 = A.recorded_variant(meta["arms"][0])
    if h0.grounding_adapter is not None:
        raise SystemExit(f"flat 계약 run이 아니다: {h0.name}")
    # 422b952의 production과 같은 계약(prompt 04d7baed, 같은 lowering 규칙)
    h2 = A.build_variant("H2_AGG")
    items = {item["id"]: item for item in A.census_items()}
    composer = MacroComposer(MacroLibrary.from_directory())
    same, changed, legacy = [], [], []
    for row in rows:
        if row.get("measurement") != A.VALID:
            continue
        item = items[row["id"]]
        flat = uses_flat_aggregation(row)
        before = _evaluate(row, item, h0, composer)
        after = _evaluate(row, item, h2, composer)
        entry = {"id": row["id"], "intent": row["intent_id"],
                 "h0_status": before["status"], "h2_status": after["status"]}
        if flat:
            legacy.append({**entry, "flat_factors": flat})
            continue
        diff = [key for key in COMPARED if before.get(key) != after.get(key)]
        (changed if diff else same).append({**entry, "diff": diff} if diff else entry)
    return {
        "run_id": meta["run_id"],
        "h0_variant": h0.name, "h0_prompt_sha256": h0.sha256,
        "h2_prompt_sha256": h2.sha256,
        "non_aggregation": {"observations": len(same) + len(changed),
                            "identical": len(same), "changed": changed},
        "flat_aggregation_legacy": {
            "observations": len(legacy),
            "intents": sorted({entry["intent"] for entry in legacy}),
            "h2_status": dict(Counter(entry["h2_status"] for entry in legacy)),
            "rows": legacy,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir")
    parser.add_argument("--out", help="결과 JSON 경로 (새 파일)")
    args = parser.parse_args(argv)
    result = replay_run(args.run_dir)
    if args.out:
        with open(args.out, "x", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2, default=str)
    view = {**result, "flat_aggregation_legacy": {
        key: value for key, value in result["flat_aggregation_legacy"].items() if key != "rows"}}
    json.dump(view, sys.stdout, ensure_ascii=False, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
