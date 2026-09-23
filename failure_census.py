# -*- coding: utf-8 -*-
"""current HEAD에 남은 실패를 세는 분석. 제품 코드를 바꾸지 않는다.

``evaluate_prompt_ab.py census``가 남긴 isolated 관측을 읽어 관측마다 다음을 붙인다.

* 실행 결과. LLM 이후는 결정적이므로 기록된 LLM 응답(첫 응답과 재질의 응답)을
  그대로 다시 넣어 Mock Provider에서 실행한다. 관측 당시의 합성·검증 결과와
  같은지도 확인한다.
* 실패 stage와 code. 재질의가 있었다면 원인은 첫 오류다.
* 의미적 실패 family. 질문 문자열이 아니라 grounding 구조를 golden grounding
  (없으면 expected_concepts)과 비교해 정한다. 구조로 정할 수 없는 것은
  ``manual_review``로 남긴다.
* 결과 등급. 조용히 틀린 답을 낼 수 있는지와 안전하게 거부했는지를 가른다.

사용: python failure_census.py <run_dir>
"""

import argparse
import dataclasses
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import yaml

import evaluate_planner as E
import evaluate_prompt_ab as A
from agent_graph import extract_scopes
from geoflow.compiler import compile_plan
from geoflow.composer import MacroComposer
from geoflow.executor import STATUS_OK, execute_plan
from geoflow.macros import MacroLibrary
from geoflow.planner import parse_planner_json

BASE_DIR = Path(__file__).resolve().parent

#: 오류 code가 난 단계. 표에 없는 code는 UNCLASSIFIED로 드러낸다.
STAGE_CODES = {
    "PLANNER_CALL": (
        "PLANNER_CALL_FAILED", "EMPTY_RESPONSE", "JSON_NOT_FOUND", "JSON_NOT_OBJECT",
        "JSON_PARSE_FAILED", "INVALID_RESPONSE", "OUTPUT_TRUNCATED", "PROMPT_BUILD_FAILED",
    ),
    # 모델이 지원 질의를 스스로 거부한 경우. 계약 위반이 아니라 판단이다.
    "GROUNDING_REFUSAL": ("UNSUPPORTED_QUESTION",),
    "GROUNDING_PARSE": (
        "INVALID_GROUNDING", "INVALID_CONCEPT", "INVALID_CONCEPT_SOURCE", "INVALID_SUBTYPE",
        "INVALID_FACTOR", "INVALID_FACTORS", "UNKNOWN_FACTOR", "UNKNOWN_ATTRIBUTE",
        "UNKNOWN_KEY", "UNKNOWN_CONCEPT_KEY", "VALUELESS_CONCEPT", "MISSING_CONCEPT_VALUE",
        "MISSING_CONCEPTS", "MULTIPLE_MEASURES", "NO_MEASURE", "INVALID_PLACE",
        "INVALID_OD_ROLE", "UNGROUNDED_SCOPE", "INVALID_SCOPE_SOURCE",
        "DUPLICATE_CONCEPT_ID", "UNSUPPORTED_MEASURE", "SCOPE_EXTRACTION_FAILED",
        # factor 공기 불변식. 합성 전에 grounding만 보고 판정한다.
        "INVALID_FACTOR_COMBINATION",
    ),
    "RELATION_INVARIANT": ("MISSING_RELATION_QUALIFIER", "AMBIGUOUS_LOCATION_RELATION"),
    "MACRO_COMPOSITION": ("UNUSED_CONCEPT", "AMBIGUOUS_PORT", "NO_MACRO"),
    "OPERATOR_MAPPING": (
        "NO_OPERATOR", "MISSING_REQUIRED_INPUT", "INVALID_PARAM_VALUE",
        "PARAM_VALUE_REQUIRES_INPUT", "MISSING_COMPANION_PARAM", "AMBIGUOUS_OPERATOR",
    ),
    "GRAPH_VALIDATION": ("VALIDATION_FAILED",),
    "REPAIR": ("REPAIR_UNSUPPORTED", "REPAIR_OUT_OF_SCOPE", "REPAIR_NO_CHANGE"),
}
_STAGE_OF = {code: stage for stage, codes in STAGE_CODES.items() for code in codes}


def stage_of(code):
    if code in (None, "OK"):
        return None
    if str(code).startswith("EXEC:"):
        return "EXECUTION"
    return _STAGE_OF.get(code, "UNCLASSIFIED")


# -- 결과 등급 --------------------------------------------------------------

CORRECT = "CORRECT"
SAFE_REJECTION = "SAFE_REJECTION"                   # 지원 범위 밖을 정확히 거부
SUPPORTED_REJECTION = "SUPPORTED_REJECTION"         # 지원 질의를 계획 없이 거부
RECOVERABLE_REJECTION = "RECOVERABLE_REJECTION"     # 실행이 재시도 가능한 오류로 멈춤
EXECUTION_REJECTION = "EXECUTION_REJECTION"         # 실행이 재시도 불가 오류로 멈춤
SILENT_WRONG_PLAN = "SILENT_WRONG_PLAN"             # 틀린 계획이 실행까지 성공
WRONG_PLAN_STOPPED = "WRONG_PLAN_STOPPED_AT_EXECUTION"
EVALUATOR_ONLY = "EVALUATOR_ONLY"                   # Tool 호출은 기대와 같고 라벨만 다름

OUTCOME_ORDER = (SILENT_WRONG_PLAN, SUPPORTED_REJECTION, RECOVERABLE_REJECTION,
                 EXECUTION_REJECTION, WRONG_PLAN_STOPPED, EVALUATOR_ONLY,
                 SAFE_REJECTION, CORRECT)


def outcome_of(row):
    """관측 하나의 등급. row에는 관측 기록과 실행 재생 결과가 함께 있다."""
    refusal_expected = E.NO_TEMPLATE_LABEL in (row.get("expected_macros") or [])
    executed = row.get("exec_status")
    if not row.get("validated"):
        return SAFE_REJECTION if refusal_expected else SUPPORTED_REJECTION
    if refusal_expected:
        return SILENT_WRONG_PLAN if executed == STATUS_OK else WRONG_PLAN_STOPPED
    if row.get("final_category") == "correct":
        if executed == STATUS_OK:
            return CORRECT
        return RECOVERABLE_REJECTION if row.get("exec_retryable") else EXECUTION_REJECTION
    if _calls_match_expectation(row):
        return EVALUATOR_ONLY
    return SILENT_WRONG_PLAN if executed == STATUS_OK else WRONG_PLAN_STOPPED


def _calls_match_expectation(row):
    """기대 Tool 인자가 있고 최종 Tool 호출이 그것과 같다. 라벨만 틀린 경우다."""
    expected = row.get("expected_tool_args") or {}
    return bool(expected) and row.get("arg_mismatches") == [] and not row.get("correct")


# -- 의미적 family ----------------------------------------------------------


def _concepts(payload):
    concepts = payload.get("concepts") if isinstance(payload, dict) else None
    return [item for item in (concepts or []) if isinstance(item, dict)]


def _factors(payload):
    factors = payload.get("factors") if isinstance(payload, dict) else None
    return dict(factors) if isinstance(factors, dict) else {}


def _by_role(concepts, role):
    return [item for item in concepts if item.get("role") == role]


def _locations(concepts):
    return [item for item in concepts if item.get("concept") == "LOCATION"
            and item.get("role") != "MEASURE"]


def _place_name(item):
    value = item.get("value")
    if isinstance(value, dict):
        return (value.get("name") or "").strip()
    return str(value or "").strip()


def _od_role(item):
    return (item.get("attributes") or {}).get("od_role")


def structural_families(payload, golden, expected_concepts):
    """첫 grounding을 기대 구조와 비교한 차이. 질문 문자열은 보지 않는다."""
    tags = []
    if payload is None:
        return ["unparsable_response"]
    if payload.get("unsupported"):
        return [] if (golden or {}).get("unsupported") else ["model_refused_supported"]
    if golden is None or golden.get("unsupported"):
        if golden is None:
            # stub 질의. concept 단위로만 비교할 수 있다.
            predicted = sorted(f"{c.get('concept')}/{c.get('subtype')}:{c.get('role')}"
                               for c in _concepts(payload))
            if expected_concepts and predicted != sorted(expected_concepts):
                tags.append("concept_mismatch_vs_label")
        return tags

    pred, gold = _concepts(payload), _concepts(golden)
    pred_measure = [c.get("subtype") for c in _by_role(pred, "MEASURE")]
    gold_measure = [c.get("subtype") for c in _by_role(gold, "MEASURE")]
    if pred_measure != gold_measure:
        tags.append("wrong_measure")

    pred_events = sorted(c.get("subtype") for c in pred if c.get("concept") == "EVENT")
    gold_events = sorted(c.get("subtype") for c in gold if c.get("concept") == "EVENT")
    if gold_events and not pred_events:
        tags.append("missing_event")
    elif pred_events and gold_events and pred_events != gold_events:
        tags.append("wrong_event")

    pred_factors, gold_factors = _factors(payload), _factors(golden)
    pred_places, gold_places = _locations(pred), _locations(gold)
    gold_names = {_place_name(item) for item in gold_places}
    for item in pred_places:
        if _place_name(item) in gold_names:
            continue
        if not _place_name(item):
            tags.append("place_without_value")
        elif not gold_places and ("dimension" in pred_factors or "dimension" in gold_factors):
            # 기대에 장소가 없고 그룹 기준이 있는 질의에 장소가 생겼다. 그룹 단어를
            # 장소로 읽었을 가능성. 값은 사람이 확인한다.
            tags.append("group_word_as_place?")
        elif gold_places:
            tags.append("wrong_place_value")
        else:
            tags.append("extra_location")
    pred_names = {_place_name(item) for item in pred_places}
    if any(_place_name(item) not in pred_names for item in gold_places):
        tags.append("missing_location")
    for gold_item in gold_places:
        match = next((item for item in pred_places
                      if _place_name(item) == _place_name(gold_item)), None)
        if match is None:
            continue
        if _od_role(gold_item) and not _od_role(match):
            tags.append("missing_od_role")
        elif _od_role(gold_item) != _od_role(match):
            tags.append("wrong_od_role")

    known = {("EVENT",), ("LOCATION",)}
    gold_kinds = Counter((c.get("concept"), c.get("subtype")) for c in gold
                         if (c.get("concept"),) not in known and c.get("role") != "MEASURE")
    pred_kinds = Counter((c.get("concept"), c.get("subtype")) for c in pred
                         if (c.get("concept"),) not in known and c.get("role") != "MEASURE")
    if pred_kinds - gold_kinds:
        tags.append("extra_concept")

    two_stage = {"bucket", "aggregation", "rollup"} <= set(gold_factors)
    if two_stage and not {"bucket", "aggregation", "rollup"} <= set(pred_factors):
        tags.append("collapsed_two_stage_aggregation")
    for key in sorted(set(gold_factors) | set(pred_factors)):
        if two_stage and key in ("bucket", "aggregation", "rollup") \
                and "collapsed_two_stage_aggregation" in tags:
            continue
        if key == "dimension":
            if gold_factors.get(key) != pred_factors.get(key):
                tags.append("wrong_dimension")
        elif key not in pred_factors:
            tags.append(f"missing_factor:{key}")
        elif key not in gold_factors:
            tags.append(f"extra_factor:{key}")
        elif gold_factors[key] != pred_factors[key]:
            tags.append(f"wrong_factor:{key}")
    return list(dict.fromkeys(tags))


def families_of(row, golden):
    payload = _payload(row.get("raw_text"))
    tags = list(row.get("initial_issues") or [])
    tags += structural_families(payload, golden, row.get("expected_concepts"))
    if row.get("exec_code") == "NOT_FOUND":
        tags.append("place_resolution_miss")
    if row.get("status") == "MISSING_REQUIRED_INPUT" and \
            E.NO_TEMPLATE_LABEL in (row.get("expected_macros") or []):
        tags.append("unsupported_global_grouping")
    return list(dict.fromkeys(tags))


def _payload(raw_text):
    try:
        payload = parse_planner_json(raw_text or "")
    except Exception:  # noqa: BLE001
        return None
    return payload if isinstance(payload, dict) else None


#: 같은 의미적 원인을 가리키는 구조 태그의 묶음. 한 관측이 여러 묶음에 들 수 있다.
FAMILY_GROUPS = {
    # bucket·aggregation·rollup 가운데 어느 단계에 무엇을 적는지 틀림
    "aggregation_stage": {
        "missing_rollup", "rollup_without_bucket", "bucket_as_rollup",
        "extra_factor:aggregation", "missing_factor:aggregation", "wrong_factor:aggregation",
        "missing_factor:rollup", "wrong_factor:rollup", "extra_factor:rollup",
        "collapsed_two_stage_aggregation",
    },
    # 택시 유형 조건을 factor가 아닌 자리에 적거나 빠뜨림
    "taxi_type_grounding": {
        "missing_factor:taxi_type", "wrong_factor:taxi_type", "extra_factor:taxi_type",
        "taxi_type_as_concept", "correct_factor_plus_spurious_concept",
    },
    "od_role": {"missing_od_role", "wrong_od_role", "relation_missing"},
    # 장소 이름과 상위 지역을 나누는 방식이 golden과 다름
    "place_decomposition": {
        "wrong_place_value", "missing_location", "valueless_location", "place_without_value",
        "extra_location", "group_word_as_place?",
    },
    "fabricated_scope": {"fabricated_scope"},
    "place_resolution_miss": {"place_resolution_miss"},
    "event_or_measure": {"missing_event", "wrong_event", "wrong_measure"},
    "model_refused_supported": {"model_refused_supported"},
}


def groups_of(tags):
    return sorted(name for name, members in FAMILY_GROUPS.items() if members & set(tags))


# -- 실행 재생 --------------------------------------------------------------


class ReplayClient:
    """기록된 LLM 응답을 순서대로 돌려준다. 모자라면 재생이 어긋난 것이다."""

    model = "replay"

    def __init__(self, contents):
        self.contents = list(contents)

    def chat(self, messages, tools=None):
        if not self.contents:
            raise RuntimeError("replay exhausted")
        return {"message": {"content": self.contents.pop(0)}}


def replay(row, item, composer, executor):
    """관측을 결정적으로 다시 돌려 실행 결과를 얻는다."""
    contents = [call.get("content") or "" for call in row.get("llm_calls") or []]
    variant = A.build_variant(row["variant"])
    planner = A.FixedPromptPlanner(client=ReplayClient(contents), variant=variant)
    plans = A.RecordingComposer(composer)
    again = E.evaluate_once(planner, plans, item)
    result = {
        "replay_consistent": (again["status"] == row["status"]
                              and again["validated"] == row["validated"]
                              and again["macros"] == row["macros"]
                              and again["operators"] == row["operators"]),
        "exec_status": None, "exec_code": None, "exec_retryable": None,
    }
    if again["validated"] and plans.last_plan is not None:
        executed = execute_plan(compile_plan(plans.last_plan), executor,
                                known_scopes=set(extract_scopes(item["question"])))
        error = executed.error or {}
        result.update(exec_status=executed.status, exec_code=error.get("code"),
                      exec_retryable=bool((error.get("context") or {}).get("retryable")))
    return result


# -- 집계 -------------------------------------------------------------------


def goldens():
    """intent id → golden grounding. corpus에만 있다."""
    table = {}
    for path in A.CENSUS_CORPORA:
        for intent in yaml.safe_load((BASE_DIR / path).read_text(encoding="utf-8"))["intents"]:
            table[intent["intent"]] = intent.get("golden")
    return table


def annotate(rows, items):
    from tests.test_geoflow_composition import new_tool_executor

    composer = MacroComposer(MacroLibrary.from_directory())
    executor = new_tool_executor()
    by_id = {item["id"]: item for item in items}
    gold = goldens()
    out = []
    for row in rows:
        item = by_id[row["id"]]
        row = {**row, **replay(row, item, composer, executor)}
        row["expected_concepts"] = list(item.get("expected_concepts") or [])
        repaired = bool(row.get("repair_attempted"))
        # 최종 Tool 인자까지 맞아야 정답이다. 재질의는 첫 합성이 실패했을 때만
        # 일어나므로, 재질의가 있었다면 첫 grounding은 틀린 것이다.
        row["final_correct"] = row.get("final_category") in ("correct", "unsupported_correct")
        row["initial_correct"] = False if repaired else row["final_correct"]
        primary = row.get("initial_error") if repaired else None
        final = row["status"] if row["status"] != "OK" else None
        if final is None and row.get("exec_status") not in (None, STATUS_OK):
            final = f"EXEC:{row.get('exec_code')}"
        row["primary_code"] = primary or final
        row["primary_stage"] = stage_of(row["primary_code"])
        row["secondary_codes"] = [code for code in (final, row.get("repair_error"))
                                  if code and code != row["primary_code"]]
        row["outcome"] = outcome_of(row)
        row["families"] = families_of(row, gold.get(item["intent_id"]))
        out.append(row)
    return out


def summarize(rows):
    # 최종 결과가 틀렸거나, 첫 grounding이 틀려 재질의가 필요했던 관측.
    failing = [row for row in rows if row["outcome"] not in (CORRECT, SAFE_REJECTION)
               or not row["initial_correct"]]
    family_obs = defaultdict(list)
    for row in failing:
        for tag in row["families"] or ["(no structural tag)"]:
            family_obs[tag].append(row)

    def family_table():
        table = []
        for tag, members in sorted(family_obs.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            table.append({
                "family": tag,
                "observations": len(members),
                "intents": sorted({row["intent_id"] for row in members}),
                "stages": dict(Counter(row["primary_stage"] or "-" for row in members)),
                "outcomes": dict(Counter(row["outcome"] for row in members)),
                "repair_attempted": sum(bool(row.get("repair_attempted")) for row in members),
                "repair_succeeded": sum(bool(row.get("repair_succeeded")) for row in members),
                "final_correct": sum(row["final_correct"] for row in members),
            })
        return table

    group_obs = defaultdict(list)
    for row in failing:
        for name in groups_of(row["families"]) or ["(ungrouped)"]:
            group_obs[name].append(row)
    group_table = [{
        "group": name,
        "observations": len(members),
        "intents": sorted({row["intent_id"] for row in members}),
        "outcomes": dict(Counter(row["outcome"] for row in members)),
        "initial_correct": sum(row["initial_correct"] for row in members),
        "repair_attempted": sum(bool(row.get("repair_attempted")) for row in members),
        "final_correct": sum(row["final_correct"] for row in members),
    } for name, members in sorted(group_obs.items(), key=lambda kv: (-len(kv[1]), kv[0]))]

    intents = defaultdict(list)
    for row in rows:
        intents[row["intent_id"]].append(row)
    return {
        "observations": len(rows),
        "intents": len(intents),
        "replay_consistent": sum(row["replay_consistent"] for row in rows),
        "outcomes": dict(Counter(row["outcome"] for row in rows)),
        "outcomes_by_intent": {
            name: dict(Counter(row["outcome"] for row in members))
            for name, members in sorted(intents.items())
        },
        "stages": dict(Counter(row["primary_stage"] for row in rows if row["primary_stage"])),
        "codes": dict(Counter(row["primary_code"] for row in rows if row["primary_code"])),
        "repair": {
            "attempted": sum(bool(row.get("repair_attempted")) for row in rows),
            "succeeded": sum(bool(row.get("repair_succeeded")) for row in rows),
            "initial_correct": sum(row["initial_correct"] for row in rows),
            "final_correct": sum(row["final_correct"] for row in rows),
        },
        "execution": dict(Counter(f"{row['exec_status']}:{row['exec_code']}"
                                  for row in rows if row["exec_status"])),
        "families": family_table(),
        "groups": group_table,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    meta, rows, report = A.load_run(args.run_dir)
    if not report.clean:
        raise SystemExit(f"무결성 문제로 분석하지 않는다: {dataclasses.asdict(report)}")
    annotated = annotate(rows, A.census_items())
    summary = summarize(annotated)
    summary["integrity"] = dataclasses.asdict(report) | {"clean": report.clean}
    summary["run_id"] = meta["run_id"]
    run_dir = Path(args.run_dir)
    with open(run_dir / "census_rows.jsonl", "x", encoding="utf-8") as handle:
        for row in annotated:
            keep = {key: row.get(key) for key in (
                "id", "intent_id", "question", "status", "initial_error", "repair_attempted",
                "repair_succeeded", "repair_error", "validated", "correct", "final_category",
                "arg_mismatches", "final_tool", "final_tool_args", "expected_tool_args",
                "exec_status", "exec_code", "exec_retryable", "replay_consistent",
                "primary_code", "primary_stage", "secondary_codes", "outcome", "families",
                "initial_correct", "final_correct", "raw_text", "census_aliases")}
            handle.write(json.dumps(keep, ensure_ascii=False, default=str) + "\n")
    with open(run_dir / "census_summary.json", "x", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, default=str)
    json.dump({key: summary[key] for key in summary
               if key not in ("families", "groups", "outcomes_by_intent")},
              sys.stdout, ensure_ascii=False, indent=2, default=str)
    print()
    for entry in summary["groups"]:
        print(f"GROUP {entry['group']:24s} obs={entry['observations']:3d} "
              f"intents={len(entry['intents']):2d} {entry['outcomes']}")
    for entry in summary["families"]:
        print(f"{entry['observations']:3d} obs {len(entry['intents']):2d} intents  "
              f"{entry['family']:40s} {entry['outcomes']} stages={entry['stages']}")


if __name__ == "__main__":
    main()
