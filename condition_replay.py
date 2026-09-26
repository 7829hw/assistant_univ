# -*- coding: utf-8 -*-
"""structured_grounding run의 기록된 LLM 원문을 이 작업 트리의 코드로 다시 돌린다. LLM 호출 없음.

결과는 ``condition_scoring``이 읽는 관측 기록 모양이다(outcome, grounding, condition_audit,
executed). 두 코드 버전을 비교하려면 이 파일을 다른 작업 트리에 복사해 각각 돌린다.

    python condition_replay.py RUN_DIR --arm flat --condition-check on --label flat+cc --out X.jsonl

재생 중 녹화에 없는 LLM 호출이 필요해지면(재질의 경로가 달라짐) ``not_replayable``로 적는다.
기록에 없는 정보(예: 과거 실행의 요청 인자)는 이 재생이 새로 만든 것이며 과거 관측의
사실로 쓰지 않는다.
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

from failure_census import ReplayClient  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline  # noqa: E402

REFERENCE_DATE = date(2026, 9, 25)
_LOOKUPS = ("get_place_scope", "get_scope_name")


def executed_conditions(run):
    measure = [hop for hop in run.hop_log if hop.get("phase", "tool") == "tool"
               and hop.get("tool") not in _LOOKUPS]
    return {
        "measure_calls": len(measure),
        "dates": sorted({hop["arguments"].get("date") for hop in measure} - {None}),
        "taxi_types": sorted({hop["arguments"].get("taxi_type") for hop in measure} - {None}),
        "place_lookups": [hop["arguments"].get("name") for hop in run.hop_log
                          if hop.get("tool") == "get_place_scope"],
    }


def replay(run_dir, *, arm, condition_check, label, tims_execution="legacy"):
    from tests.test_geoflow_composition import new_tool_executor

    records = []
    for line in open(Path(run_dir) / "observations.jsonl", encoding="utf-8"):
        source = json.loads(line)
        if source["arm"] != arm or source.get("measurement") != "valid":
            continue
        contents = [call.get("content") or "" for call in source.get("llm_calls") or []]
        kwargs = {"client": ReplayClient(contents), "tool_executor": new_tool_executor(),
                  "aggregation_grounding": arm.split("+")[0],
                  "clock": lambda: REFERENCE_DATE}
        if condition_check:
            kwargs["condition_check"] = True
        try:
            from geoflow.providers import profile_for
        except ImportError:  # 0f2daaa 이전 코드: condition_check가 실행 계약을 정했다
            profile_for = None
        if profile_for is not None:
            kwargs["execution_profile"] = profile_for("mock", tims_execution)
        run = GeoFlowPipeline.create(**kwargs).run(source["question"])
        detail = str((run.error or {}).get("detail", ""))
        records.append({
            "id": source["id"], "arm": label, "question": source["question"],
            "measurement": "valid", "not_replayable": "replay exhausted" in detail,
            "outcome": run.outcome, "error": run.error, "grounding": run.grounding,
            "condition_audit": getattr(run, "condition_audit", None),
            "verification": getattr(run, "verification", None),
            "executed": executed_conditions(run),
            "tool_calls": sum(1 for hop in run.hop_log if hop.get("phase", "tool") == "tool"),
            "llm_calls": len(contents),
            "recorded_outcome": source.get("outcome"),
        })
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir")
    parser.add_argument("--arm", required=True, help="녹화된 arm 이름")
    parser.add_argument("--condition-check", choices=("off", "on"), default="off")
    parser.add_argument("--label", help="출력 기록의 arm 이름(기본: 녹화 arm)")
    parser.add_argument("--tims-execution", choices=("legacy", "strict"), default="legacy",
                        help="실행 계약(현재 코드). 0f2daaa의 condition_check 결과 재현은 strict")
    parser.add_argument("--out", required=True, help="새 JSONL 경로")
    args = parser.parse_args(argv)
    records = replay(args.run_dir, arm=args.arm, condition_check=args.condition_check == "on",
                     label=args.label or args.arm, tims_execution=args.tims_execution)
    with open(args.out, "x", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    consistent = sum(r["outcome"] == r["recorded_outcome"] for r in records)
    print(f"{len(records)} records, recorded outcome와 같음 {consistent}, "
          f"not_replayable {sum(r['not_replayable'] for r in records)}", file=sys.stderr)


if __name__ == "__main__":
    main()
