# -*- coding: utf-8 -*-
"""국소 집계 보정 holdout에서 H0와 L1을 비교하고 사전 등록한 규칙으로 판정한다.

판정 규칙은 결과를 보기 전에 이 파일과
``evaluation/prompt_ab/variants/local_aggregation_decision_rule.md``에 고정했다.

사용: python local_aggregation_ab.py <run_dir>
"""

import argparse
import dataclasses
import json
from collections import Counter, defaultdict
from pathlib import Path

import aggregation_plan as AP
import aggregation_refinement as R
import evaluate_prompt_ab as A
import paraphrase_corpus as P

HOLDOUT = P.BASE_DIR / "evaluation" / "paraphrases_local_aggregation_holdout.yaml"
ARMS = {"H0_AGG": "H0", "L1_AGG": "L1"}
#: 관측의 최종 동작. 대조군에서 H0와 L1이 이것까지 같아야 한다.
BEHAVIOR_KEYS = ("status", "validated", "strict_correct", "final_tool", "final_tool_args",
                 "repair_attempted", "repair_succeeded")
#: 첫 grounding이 다른 쌍이 이 비율을 넘으면 serving 상태 protocol을 믿을 수 없다.
MAX_IDENTITY_FAILURE_RATE = 0.10
#: 비용 기준. 넘으면 정확도 판정과 별도로 Case D(자동 채택 안 함)다.
MAX_LATENCY_RATIO = 1.5
MAX_EXTRA_CALLS_PER_OBSERVATION = 0.75


def _final_factors(row):
    return row.get("factors_after_repair") or row.get("factors") or {}


def _latency_ms(row):
    return sum(call.get("elapsed_ms") or 0.0 for call in row.get("llm_calls") or [])


def annotate(row, intent, item):
    semantic = item.get("semantic_aggregation")
    refusal_expected = P.NONE_LABEL in (item.get("expected_macros") or [])
    validated = bool(row.get("validated"))
    strict = bool(row.get("strict_correct"))
    predicted = AP.flat_to_semantic(_final_factors(row))
    errors = AP.aggregation_errors(predicted, semantic) if semantic is not None else []
    refinement = row.get("aggregation_refinement") or {}
    calls = row.get("llm_calls") or []
    refiner_calls = [call for call in calls if call.get("phase") == "aggregation_refinement"]
    return {
        "id": row["id"], "intent": row["intent_id"], "arm": ARMS[row["variant"]],
        "trigger_expected": bool(intent.get("trigger_expected")),
        "semantic": semantic, "predicted": predicted,
        "status": row["status"], "validated": validated,
        "initial_strict": strict and not row.get("repair_attempted")
                          and refinement.get("outcome") != R.APPLIED,
        "final_strict": strict,
        "silent_wrong": validated and not strict,
        "safe_rejection": refusal_expected and not validated,
        "supported_rejection": not refusal_expected and not validated,
        "refusal_expected": refusal_expected,
        "aggregation_errors": errors,
        "explicit_inner_left_unspecified": AP.explicit_inner_left_unspecified(predicted, semantic),
        "repair_attempted": bool(row.get("repair_attempted")),
        "repair_skipped": row.get("repair_skipped"),
        "refinement_outcome": refinement.get("outcome"),
        "refinement_reason": refinement.get("reason"),
        "refinement": refinement or None,
        "llm_calls": len(calls),
        "refiner_calls": len(refiner_calls),
        "refiner_ms": sum(call.get("elapsed_ms") or 0.0 for call in refiner_calls),
        "refiner_load_ms": [call.get("load_duration_ms") for call in refiner_calls],
        "latency_ms": _latency_ms(row),
        "raw_text": row.get("raw_text"),
        "concepts": row.get("concepts"),
        **{f"behavior_{key}": row.get(key) for key in BEHAVIOR_KEYS},
    }


def _behavior(row):
    return tuple(json.dumps(row[f"behavior_{key}"], sort_keys=True, default=str)
                 for key in BEHAVIOR_KEYS)


def _intents(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["intent"]].append(row)
    return groups


def arm_summary(rows):
    intents = _intents(rows)
    errors = Counter(error for row in rows for error in row["aggregation_errors"])
    trigger_rows = [row for row in rows if row["trigger_expected"]]
    return {
        "observations": len(rows),
        "initial_strict": sum(row["initial_strict"] for row in rows),
        "final_strict": sum(row["final_strict"] for row in rows),
        "silent_wrong": sum(row["silent_wrong"] for row in rows),
        "safe_rejection": sum(row["safe_rejection"] for row in rows),
        "supported_rejection": sum(row["supported_rejection"] for row in rows),
        "strict_intents": sorted(n for n, m in intents.items() if all(r["final_strict"] for r in m)),
        "silent_intents": sorted(n for n, m in intents.items() if any(r["silent_wrong"] for r in m)),
        "aggregation_stage_silent": sum(row["silent_wrong"] and bool(row["aggregation_errors"])
                                        for row in trigger_rows),
        "stage_swapped": sum(AP.STAGE_SWAPPED in row["aggregation_errors"] for row in rows),
        "stage_swapped_silent": sum(AP.STAGE_SWAPPED in row["aggregation_errors"]
                                    and row["silent_wrong"] for row in rows),
        "aggregation_errors": dict(errors),
        "explicit_inner_left_unspecified": sum(row["explicit_inner_left_unspecified"]
                                               for row in rows),
        "trigger_expected_strict": sum(row["final_strict"] for row in trigger_rows),
        "control_strict": sum(row["final_strict"] for row in rows if not row["trigger_expected"]),
        "repair_attempted": sum(row["repair_attempted"] for row in rows),
        "repair_skipped_by_refinement": sum(bool(row["repair_skipped"]) for row in rows),
        "refinement": dict(Counter(row["refinement_outcome"] for row in rows
                                   if row["refinement_outcome"])),
        "refinement_fallback_reasons": dict(Counter(row["refinement_reason"] for row in rows
                                                    if row["refinement_outcome"] == R.FALLBACK)),
        "refiner_calls": sum(row["refiner_calls"] for row in rows),
        "refiner_calls_on_controls": sum(row["refiner_calls"] for row in rows
                                         if not row["trigger_expected"]),
        "llm_calls": sum(row["llm_calls"] for row in rows),
        "latency_ms": round(sum(row["latency_ms"] for row in rows), 1),
        "refiner_ms": round(sum(row["refiner_ms"] for row in rows), 1),
        "statuses": dict(Counter(row["status"] for row in rows)),
    }


def scope_violations(l1_rows, h0_by_id):
    """적용된 patch가 aggregation·rollup 밖을 바꿨는가. 기록과 H0 쌍으로 다시 확인한다."""
    found = []
    for row in l1_rows:
        refinement = row["refinement"] or {}
        if refinement.get("reason") == R.PATCH_SCOPE_VIOLATION:
            found.append((row["id"], "guard"))
        if refinement.get("outcome") != R.APPLIED:
            continue
        before = {k: v for k, v in refinement["factors_before"].items() if k not in R.WRITABLE}
        after = {k: v for k, v in refinement["factors_after"].items() if k not in R.WRITABLE}
        if before != after:
            found.append((row["id"], "factors"))
        if row["concepts"] != h0_by_id[row["id"]]["concepts"]:
            found.append((row["id"], "concepts"))
    return found


def compare(pairs):
    """짝지은 관측에서 두 arm 요약과 판정 입력을 만든다."""
    h0 = [a for a, _ in pairs]
    l1 = [b for _, b in pairs]
    h0_by_id = {row["id"]: row for row in h0}
    summary = {"H0": arm_summary(h0), "L1": arm_summary(l1)}
    not_triggered_diff = [b["id"] for a, b in pairs
                          if b["refinement_outcome"] == R.NOT_TRIGGERED and _behavior(a) != _behavior(b)]
    control_diff = [b["id"] for a, b in pairs
                    if not b["trigger_expected"] and _behavior(a) != _behavior(b)]
    transitions = Counter()
    for a, b in pairs:
        if a["final_strict"] and not b["final_strict"]:
            transitions["H0_strict_to_L1_wrong"] += 1
        if b["final_strict"] and not a["final_strict"]:
            transitions["L1_strict_to_H0_wrong"] += 1
        if b["silent_wrong"] and not a["silent_wrong"]:
            transitions["L1_new_silent"] += 1
        if a["silent_wrong"] and not b["silent_wrong"]:
            transitions["L1_removed_silent"] += 1
    extra_calls = (summary["L1"]["llm_calls"] - summary["H0"]["llm_calls"]) / max(len(pairs), 1)
    latency_ratio = summary["L1"]["latency_ms"] / max(summary["H0"]["latency_ms"], 1.0)
    return {
        "arms": summary,
        "not_triggered_behavior_diff": not_triggered_diff,
        "control_behavior_diff": control_diff,
        "scope_violations": scope_violations(l1, h0_by_id),
        "transitions": dict(transitions),
        "changed": [{"id": a["id"], "h0": [a["status"], a["final_strict"], a["silent_wrong"]],
                     "l1": [b["status"], b["final_strict"], b["silent_wrong"],
                            b["refinement_outcome"], (b["refinement"] or {}).get("patch")]}
                    for a, b in pairs if _behavior(a) != _behavior(b)],
        "extra_calls_per_observation": round(extra_calls, 3),
        "latency_ratio": round(latency_ratio, 3),
    }


# -- 사전 등록 판정 ---------------------------------------------------------


def decide(result):
    """결과를 보기 전에 고정한 규칙. local_aggregation_decision_rule.md와 같다."""
    h0, l1 = result["arms"]["H0"], result["arms"]["L1"]
    new_silent = sorted(set(l1["silent_intents"]) - set(h0["silent_intents"]))
    checks = {
        "A_no_new_L1_silent_intent": not new_silent,
        "B_controls_identical": not result["not_triggered_behavior_diff"]
            and not result["control_behavior_diff"],
        "C_aggregation_stage_silent_decreases":
            l1["aggregation_stage_silent"] < h0["aggregation_stage_silent"]
            and l1["stage_swapped"] <= h0["stage_swapped"],
        "D_strict_intents_not_worse": len(l1["strict_intents"]) >= len(h0["strict_intents"]),
        "E_no_patch_scope_violation": not result["scope_violations"],
    }
    if not (checks["A_no_new_L1_silent_intent"] and checks["B_controls_identical"]
            and checks["E_no_patch_scope_violation"]):
        case = "B"
    elif not checks["C_aggregation_stage_silent_decreases"]:
        case = "C"
    elif not checks["D_strict_intents_not_worse"]:
        case = "B"
    elif (result["latency_ratio"] > MAX_LATENCY_RATIO
          or result["extra_calls_per_observation"] > MAX_EXTRA_CALLS_PER_OBSERVATION):
        case = "D"
    else:
        case = "A"
    return {"case": case, "checks": checks, "new_silent_intents": new_silent}


CASE_MEANING = {
    "A": "L1 production 도입 후보. 도입은 별도 commit으로 한다",
    "B": "폐기. global/local 모두 production H0 유지",
    "C": "개선 없음. 두 단계 집계는 known limitation. 추가 prompt 연구 중단",
    "D": "정확도 이득과 비용을 별도 tradeoff로 기록. 자동 채택하지 않는다",
    "UNSTABLE": "무효 관측 처리 방식에 따라 결론이 바뀐다. 채택하지 않는다",
    "INVALID": "첫 grounding 동일성이 깨졌다. 측정을 무효로 한다",
}


def _pairs(rows, exclude_ids):
    by_key = defaultdict(dict)
    for row in rows:
        if row["id"] in exclude_ids:
            continue
        by_key[row["id"]][row["arm"]] = row
    return [(arms["H0"], arms["L1"]) for _, arms in sorted(by_key.items())
            if "H0" in arms and "L1" in arms]


def analyze(run_dir):
    meta, rows, report = A.load_run(run_dir)
    if not report.clean:
        raise SystemExit(f"무결성 문제로 분석하지 않는다: {dataclasses.asdict(report)}")
    items = {item["id"]: item for item in P.load_corpus_items(HOLDOUT)}
    intents = {intent["intent"]: intent for intent in P.load_corpus(HOLDOUT)}
    annotated = [annotate(row, intents[row["intent_id"]], items[row["id"]]) for row in rows]
    raw = {(row["id"], ARMS[row["variant"]]): row for row in rows}

    invalid = sorted({row["id"] for row in rows if row.get("measurement") != A.VALID})
    both_valid = sorted({row["id"] for row in rows} - set(invalid))
    identity_failures = sorted(
        rid for rid in both_valid
        if (raw[(rid, "H0")].get("raw_text") or "") != (raw[(rid, "L1")].get("raw_text") or ""))
    excluded = set(invalid) | set(identity_failures)
    primary = compare(_pairs(annotated, excluded))
    primary["decision"] = decide(primary)

    # 민감도: 무효 관측이 하나라도 있는 intent를 통째로 뺀다.
    bad_intents = {items[rid]["intent_id"] for rid in excluded}
    intent_level = compare(_pairs(annotated, {rid for rid in items
                                              if items[rid]["intent_id"] in bad_intents}))
    intent_level["decision"] = decide(intent_level)

    decision = dict(primary["decision"])
    decision["F_same_verdict_with_intent_exclusion"] = (
        intent_level["decision"]["case"] == primary["decision"]["case"])
    identity_rate = len(identity_failures) / max(len(both_valid), 1)
    if identity_rate > MAX_IDENTITY_FAILURE_RATE:
        decision["case"] = "INVALID"
    elif not decision["F_same_verdict_with_intent_exclusion"]:
        decision["case"] = "UNSTABLE"
    return {
        "run_id": meta["run_id"],
        "integrity": dataclasses.asdict(report) | {"clean": report.clean},
        "invalid_paraphrases": invalid,
        "first_grounding_identity": {"compared": len(both_valid),
                                     "identical": len(both_valid) - len(identity_failures),
                                     "different": identity_failures},
        "excluded_paraphrases": sorted(excluded),
        "primary": primary,
        "intent_level_exclusion": {"excluded_intents": sorted(bad_intents), **intent_level},
        "decision": decision,
        "rows": annotated,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    result = analyze(args.run_dir)
    with open(Path(args.run_dir) / "local_aggregation_summary.json", "x",
              encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, default=str)
    view = {key: result[key] for key in ("run_id", "invalid_paraphrases",
                                         "first_grounding_identity", "decision")}
    view["primary"] = {key: value for key, value in result["primary"].items() if key != "changed"}
    print(json.dumps(view, ensure_ascii=False, indent=2, default=str))
    print(CASE_MEANING[result["decision"]["case"]])


if __name__ == "__main__":
    main()
