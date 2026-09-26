# -*- coding: utf-8 -*-
"""조건(날짜·장소·택시 유형) 오류를 관측 단위로 분류한다. LLM 호출 없음.

``structured_grounding_eval.py``가 남긴 관측(LLM 원문 포함)을 현재 코드로 재생해
조건마다 다음을 잇는다.

    질문 → LLM 원문(첫 응답, 재질의 응답) → 초기 grounding → 최종 grounding → 실행 인자

오류 유형(조건 하나마다 하나 이상)

    missing            질문에 있는 조건이 없다
    added              질문에 없는 조건이 있다
    value_changed      값이나 범위가 다르다
    relative_misconverted  상대 날짜를 틀린 절대 날짜로 바꿨다
    wrong_target       조건을 다른 자리(개념 node 등)에 적었다
    lost_in_repair     첫 응답에는 맞게 있었는데 재질의 뒤에 사라지거나 바뀌었다
    lost_in_execution  최종 grounding에는 있는데 실행 인자에 없다
    not_judgeable      grounding 전체가 거부되어 조건을 판정할 수 없다(원문 조건은 따로 적는다)

집계 구조(bucket·inner·outer·select)의 오류는 여기서 세지 않는다. 기대 조건은 평가
라벨(질문 셋의 expected.conditions)에서만 읽는다. 이 도구는 분석용이며 제품 실행 경로에
쓰지 않는다.

사용: python condition_error_audit.py RUN_DIR [--condition-check on] --out-json X --out-md Y
"""

import argparse
import json
import os
from collections import Counter
from datetime import date
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import yaml  # noqa: E402

from failure_census import ReplayClient  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline  # noqa: E402
from geoflow.planner import parse_planner_json  # noqa: E402

CONDITIONS = ("date", "taxi_type", "place")
RELATIVE_TOKENS = {"last_week", "last_month", "last_year", "weekday", "weekend", "holiday"}


def _tool_executor():
    from tests.test_geoflow_composition import new_tool_executor
    return new_tool_executor()


def _places(concepts):
    names = []
    for item in concepts or []:
        if not isinstance(item, dict) or item.get("concept") != "LOCATION":
            continue
        if item.get("role") == "MEASURE":
            continue
        value = item.get("value")
        name = value.get("name") if isinstance(value, dict) else value
        if name:
            names.append(name)
    return sorted(names)


def conditions_of(payload):
    """grounding(또는 LLM 원문 payload)에서 조건을 읽는다. 형식이 틀려도 읽을 수 있는 만큼."""
    if not isinstance(payload, dict):
        return None
    factors = payload.get("factors") if isinstance(payload.get("factors"), dict) else {}
    found = {}
    if factors.get("date"):
        found["date"] = factors["date"]
    if factors.get("taxi_type") and factors["taxi_type"] != "all":
        found["taxi_type"] = factors["taxi_type"]
    places = _places(payload.get("concepts"))
    if places:
        found["place"] = places
    return found


def taxi_as_concept(payload):
    for item in (payload or {}).get("concepts") or []:
        if not isinstance(item, dict):
            continue
        text = f"{item.get('subtype')} {item.get('id')} {item.get('text') or ''}"
        if any(word in text for word in ("taxi", "private", "corporate", "개인", "법인")):
            if item.get("concept") in ("OBJECT", "EVENT") and item.get("subtype") not in (
                    "operation", "trip", "drive", "passage"):
                return True
    return False


def execution_conditions(run):
    """실행한 Tool 인자에서 조건을 읽는다(측정 호출 전부)."""
    measure = [hop for hop in run.hop_log
               if hop.get("phase", "tool") == "tool" and hop.get("tool") != "get_place_scope"
               and hop.get("tool") != "get_scope_name"]
    places = sorted({hop["arguments"].get("name") for hop in run.hop_log
                     if hop.get("tool") == "get_place_scope"} - {None})
    return {
        "measure_calls": len(measure),
        "dates": sorted({hop["arguments"].get("date") for hop in measure} - {None}),
        "taxi_types": sorted({hop["arguments"].get("taxi_type") for hop in measure} - {None}),
        "places": places,
    }


def replay(record, arm, condition_check):
    contents = [call.get("content") or "" for call in record.get("llm_calls") or []]
    kwargs = {"condition_check": condition_check} if condition_check else {}
    pipeline = GeoFlowPipeline.create(
        client=ReplayClient(contents), tool_executor=_tool_executor(),
        aggregation_grounding=arm, clock=lambda: date(2026, 9, 25), **kwargs)
    return pipeline.run(record["question"])


def _want(expected):
    want = dict(expected.get("conditions") or {})
    if "place" in want:
        want["place"] = sorted(want["place"] if isinstance(want["place"], list)
                               else [want["place"]])
    return want


def classify(want, initial, final, execution, raw_payload):
    """조건마다 오류 유형 목록."""
    errors = {}
    for key in CONDITIONS:
        wanted = want.get(key)
        got = (final or {}).get(key) if final is not None else None
        first = (initial or {}).get(key) if initial is not None else None
        kinds = []
        if final is None:
            if wanted is not None or first is not None:
                kinds.append("not_judgeable")
        elif wanted is None and got is not None:
            kinds.append("added")
        elif wanted is not None and got is None:
            kinds.append("missing")
            if key == "taxi_type" and taxi_as_concept(raw_payload):
                kinds.append("wrong_target")
        elif wanted is not None and got != wanted:
            if key == "date" and wanted in RELATIVE_TOKENS and got not in RELATIVE_TOKENS:
                kinds.append("relative_misconverted")
            else:
                kinds.append("value_changed")
        if final is not None and first == wanted and got != wanted and wanted is not None:
            kinds.append("lost_in_repair")
        if final is not None and got is not None and got == wanted and execution is not None \
                and execution["measure_calls"]:
            lost = {
                "date": not execution["dates"],
                "taxi_type": got not in execution["taxi_types"],
                "place": not execution["places"] and key == "place",
            }[key]
            if lost:
                kinds.append("lost_in_execution")
        if kinds:
            errors[key] = kinds
    return errors


def audit(run_dir, condition_check=None):
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
    questions = yaml.safe_load(Path(meta["questions_file"]).read_text(encoding="utf-8"))
    expected = {item["id"]: item for item in questions["questions"]}
    rows = []
    for line in open(run_dir / "observations.jsonl", encoding="utf-8"):
        record = json.loads(line)
        if record.get("measurement") != "valid":
            continue
        item = expected[record["id"]]
        calls = record.get("llm_calls") or []
        try:
            raw_payload = parse_planner_json(calls[0].get("content") or "") if calls else None
        except Exception:  # noqa: BLE001 - 원문이 JSON이 아닐 수 있다
            raw_payload = None
        run = replay(record, record["arm"], condition_check)
        final_payload = run.grounding if run.plan is not None or run.grounding else None
        final = conditions_of(final_payload) if final_payload else None
        initial = conditions_of(raw_payload)
        execution = execution_conditions(run) if run.execution else None
        want = _want(item["expected"])
        errors = classify(want, initial, final, execution, raw_payload)
        rows.append({
            "id": record["id"], "arm": record["arm"], "question": record["question"],
            "class": item.get("class"), "expected_conditions": want,
            "llm_raw": [call.get("content") for call in calls],
            "initial_conditions": initial, "final_conditions": final,
            "execution": execution, "outcome": run.outcome,
            "code": (run.error or {}).get("code"),
            "condition_audit": getattr(run, "condition_audit", None),
            "errors": errors,
            "recorded_outcome_matches_replay": record.get("outcome") == run.outcome
            if condition_check is None else None,
        })
    return rows


def summarize(rows):
    summary = {}
    for arm in sorted({row["arm"] for row in rows}):
        mine = [row for row in rows if row["arm"] == arm]
        kinds = Counter()
        by_condition = Counter()
        for row in mine:
            for key, values in row["errors"].items():
                for value in values:
                    kinds[value] += 1
                    by_condition[f"{key}:{value}"] += 1
        judgeable = [row for row in mine if row["final_conditions"] is not None]
        summary[arm] = {
            "observations": len(mine),
            "grounding_rejected": len(mine) - len(judgeable),
            "observations_with_condition_error_judgeable": sum(
                any(v != ["not_judgeable"] for v in row["errors"].values()) and bool(row["errors"])
                for row in judgeable),
            "error_kinds": dict(kinds),
            "by_condition": dict(by_condition),
            "replay_matches_recorded_outcome": sum(
                bool(row["recorded_outcome_matches_replay"]) for row in mine),
        }
    return summary


def to_markdown(rows, summary, title):
    lines = [f"# {title}", "", "생성: `condition_error_audit.py`. LLM 호출 없음(기록된 원문 재생).", "",
             "| arm | 관측 | 기대 조건 | 첫 응답 조건 | 최종 grounding 조건 | 실행 인자 | 결과 | 조건 오류 |",
             "|---|---|---|---|---|---|---|---|"]
    for row in rows:
        execution = row["execution"] or {}
        executed = (f"date={execution.get('dates')} taxi={execution.get('taxi_types')} "
                    f"place={execution.get('places')}" if row["execution"] else "-")
        errors = "; ".join(f"{k}: {','.join(v)}" for k, v in row["errors"].items()) or "-"
        lines.append(
            f"| {row['arm']} | {row['id']} {row['question']} | "
            f"`{json.dumps(row['expected_conditions'], ensure_ascii=False)}` | "
            f"`{json.dumps(row['initial_conditions'], ensure_ascii=False)}` | "
            f"`{json.dumps(row['final_conditions'], ensure_ascii=False)}` | {executed} | "
            f"{row['outcome']} ({row['code']}) | {errors} |")
    lines += ["", "## 요약", "", "```json", json.dumps(summary, ensure_ascii=False, indent=2), "```"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir")
    parser.add_argument("--condition-check", choices=("off", "on"), default=None)
    parser.add_argument("--out-json")
    parser.add_argument("--out-md")
    parser.add_argument("--title", default="조건 오류 감사표")
    args = parser.parse_args(argv)
    check = None if args.condition_check in (None, "off") else args.condition_check
    rows = audit(args.run_dir, check)
    summary = summarize(rows)
    if args.out_json:
        with open(args.out_json, "x", encoding="utf-8") as handle:
            json.dump({"summary": summary, "rows": rows}, handle, ensure_ascii=False, indent=2,
                      default=str)
    if args.out_md:
        with open(args.out_md, "x", encoding="utf-8") as handle:
            handle.write(to_markdown(rows, summary, args.title))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
