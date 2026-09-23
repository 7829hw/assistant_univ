# -*- coding: utf-8 -*-
"""두 단계 집계 holdout에서 H0와 H2를 비교하고 사전 등록한 규칙으로 판정한다.

판정 규칙은 결과를 보기 전에 이 파일과
``evaluation/prompt_ab/variants/aggregation_decision_rule.md``에 고정했다.

사용: python aggregation_ab.py <run_dir>
"""

import argparse
import dataclasses
import json
from collections import Counter, defaultdict
from pathlib import Path

import aggregation_plan as AP
import evaluate_prompt_ab as A
import paraphrase_corpus as P

HOLDOUT = P.BASE_DIR / "evaluation" / "paraphrases_aggregation_holdout.yaml"
ARMS = {"H0_AGG": "H0", "H2_AGG": "H2"}

#: 합성 이후 단계의 실패. H2 lowering이 제품 경로를 깨지 않는지 본다.
PIPELINE_CODES = frozenset({
    "NO_MACRO", "UNUSED_CONCEPT", "AMBIGUOUS_PORT", "NO_OPERATOR", "MISSING_REQUIRED_INPUT",
    "INVALID_PARAM_VALUE", "PARAM_VALUE_REQUIRES_INPUT", "MISSING_COMPANION_PARAM",
    "AMBIGUOUS_OPERATOR", "VALIDATION_FAILED",
})
PLAN_CODES = frozenset({AP.DUPLICATE_AGGREGATION_SOURCE, AP.FLAT_AGGREGATION_FACTOR,
                        AP.LOWERING_ERROR})


def cell_of(semantic, golden):
    """의미 칸. corpus 테스트와 같은 기준이다."""
    factors = (golden or {}).get("factors") or {}
    places = [c for c in (golden or {}).get("concepts") or [] if c["concept"] == "LOCATION"]
    if semantic is None:
        return "G_unsupported"
    if "bucket" not in semantic:
        return "D_no_bucket"
    if "taxi_type" in factors:
        return "E_taxi_type"
    if places:
        return "F_location"
    if semantic["inner"] == AP.UNSPECIFIED:
        return "B_inner_unspecified"
    if semantic["inner"] == "avg":
        return "C_inner_avg"
    return "A_explicit_inner"


def _payload(raw_text):
    try:
        payload = A.parse_planner_json(raw_text or "")
    except Exception:  # noqa: BLE001
        return None
    return payload if isinstance(payload, dict) else None


def annotate(row, item, golden):
    arm = ARMS[row["variant"]]
    semantic = item.get("semantic_aggregation")
    payload = _payload(row.get("raw_text")) or {}
    factors = payload.get("factors") if isinstance(payload.get("factors"), dict) else {}
    if arm == "H2":
        predicted = AP.plan_to_semantic(factors.get(AP.PLAN_KEY))
    else:
        predicted = AP.flat_to_semantic(factors)
    refusal_expected = semantic is None
    validated = bool(row.get("validated"))
    final_strict = bool(row.get("strict_correct"))
    errors = AP.aggregation_errors(predicted, semantic) if semantic is not None else []
    return {
        "id": row["id"], "intent": row["intent_id"], "arm": arm,
        "cell": cell_of(semantic, golden),
        "semantic": semantic, "predicted": predicted,
        "status": row["status"], "validated": validated,
        "initial_strict": final_strict and not row.get("repair_attempted"),
        "final_strict": final_strict,
        "silent_wrong": validated and not final_strict,
        "refusal_expected": refusal_expected,
        "aggregation_errors": errors,
        "explicit_inner_left_unspecified": AP.explicit_inner_left_unspecified(predicted, semantic),
        "plan_code": row["status"] if row["status"] in PLAN_CODES else None,
        "pipeline_failure": row["status"] if row["status"] in PIPELINE_CODES else None,
        "repair_attempted": bool(row.get("repair_attempted")),
        "repair_succeeded": bool(row.get("repair_succeeded")),
        "arg_mismatches": row.get("arg_mismatches"),
        "final_tool_args": row.get("final_tool_args"),
    }


def _two_stage_explicit(row):
    return bool(row["semantic"] and "bucket" in row["semantic"]
                and row["semantic"]["inner"] != AP.UNSPECIFIED)


def _inner_unspecified(row):
    return bool(row["semantic"] and "bucket" in row["semantic"]
                and row["semantic"]["inner"] == AP.UNSPECIFIED)


def arm_summary(rows):
    intents = defaultdict(list)
    for row in rows:
        intents[row["intent"]].append(row)
    errors = Counter(error for row in rows for error in row["aggregation_errors"])
    return {
        "observations": len(rows),
        "initial_strict": sum(row["initial_strict"] for row in rows),
        "final_strict": sum(row["final_strict"] for row in rows),
        "silent_wrong": sum(row["silent_wrong"] for row in rows),
        "strict_intents": sorted(name for name, members in intents.items()
                                 if all(row["final_strict"] for row in members)),
        "silent_intents": sorted(name for name, members in intents.items()
                                 if any(row["silent_wrong"] for row in members)),
        "two_stage_explicit_silent": sum(row["silent_wrong"] for row in rows
                                         if _two_stage_explicit(row)),
        "invented_inner": sum(AP.INNER_REDUCER_INVENTED in row["aggregation_errors"]
                              for row in rows if _inner_unspecified(row)),
        "no_bucket_strict": sum(row["final_strict"] for row in rows
                                if row["cell"] == "D_no_bucket"),
        "unsupported_validated": sum(row["validated"] for row in rows
                                     if row["refusal_expected"]),
        "aggregation_errors": dict(errors),
        "explicit_inner_left_unspecified": sum(row["explicit_inner_left_unspecified"]
                                               for row in rows),
        "plan_codes": dict(Counter(row["plan_code"] for row in rows if row["plan_code"])),
        "pipeline_failures": dict(Counter(row["pipeline_failure"] for row in rows
                                          if row["pipeline_failure"])),
        "repair_attempted": sum(row["repair_attempted"] for row in rows),
        "repair_succeeded": sum(row["repair_succeeded"] for row in rows),
        "by_cell": {cell: {"observations": len(members),
                           "final_strict": sum(r["final_strict"] for r in members),
                           "silent_wrong": sum(r["silent_wrong"] for r in members)}
                    for cell, members in sorted(_group(rows, "cell").items())},
    }


def _group(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    return groups


def intent_comparison(rows):
    """intent마다 최종 strict 정답 paraphrase 수와 조용한 오답 여부를 비교한다."""
    table = {}
    for (intent, arm), members in sorted(_group_pairs(rows).items()):
        table.setdefault(intent, {})[arm] = {
            "final_strict": sum(r["final_strict"] for r in members),
            "silent": any(r["silent_wrong"] for r in members),
        }
    outcome = Counter()
    for intent, arms in table.items():
        h0, h2 = arms.get("H0"), arms.get("H2")
        # 조용한 오답이 먼저다. 그다음 strict 정답 수.
        key0 = (not h0["silent"], h0["final_strict"])
        key2 = (not h2["silent"], h2["final_strict"])
        outcome["H2 win" if key2 > key0 else "H0 win" if key0 > key2 else "tie"] += 1
    return table, dict(outcome)


def _group_pairs(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["intent"], row["arm"])].append(row)
    return groups


# -- 사전 등록 판정 ---------------------------------------------------------


def decide(h0, h2):
    """결과를 보기 전에 고정한 규칙. aggregation_decision_rule.md와 같다."""
    new_silent = sorted(set(h2["silent_intents"]) - set(h0["silent_intents"]))
    checks = {
        "A_two_stage_explicit_silent_decreases":
            h2["two_stage_explicit_silent"] < h0["two_stage_explicit_silent"],
        "B_no_more_invented_inner_reducers": h2["invented_inner"] <= h0["invented_inner"],
        "C_no_bucket_no_regression": h2["no_bucket_strict"] >= h0["no_bucket_strict"],
        "D_no_new_silent_intent": not new_silent
            and len(h2["silent_intents"]) <= len(h0["silent_intents"]),
        "E_strict_intents_not_worse": len(h2["strict_intents"]) >= len(h0["strict_intents"]),
        "F_no_new_pipeline_failures": sum(h2["pipeline_failures"].values())
            <= sum(h0["pipeline_failures"].values()),
    }
    if all(checks.values()):
        case = "A"
    elif all(value for name, value in checks.items() if not name.startswith("E_")):
        # silent 감소는 분명하지만 strict intent가 줄었다. 자동으로 채택하지 않는다.
        case = "A_TRADEOFF"
    elif (len(h2["silent_intents"]) > len(h0["silent_intents"])
          or (len(h2["silent_intents"]) == len(h0["silent_intents"])
              and len(h2["strict_intents"]) < len(h0["strict_intents"]))):
        case = "C"
    else:
        case = "B"
    return {"case": case, "checks": checks, "new_silent_intents": new_silent}


CASE_MEANING = {
    "A": "H2 명확한 개선. production 구현을 다음 별도 단계로 추천한다",
    "A_TRADEOFF": "silent 감소, strict intent 감소. 사람이 판단한다. 자동 채택하지 않는다",
    "B": "동률 또는 혼재. H2를 채택하지 않는다. known limitation으로 유지",
    "C": "H2 악화. H2를 폐기한다",
}


def analyze(run_dir):
    meta, rows, report = A.load_run(run_dir)
    if not report.clean:
        raise SystemExit(f"무결성 문제로 분석하지 않는다: {dataclasses.asdict(report)}")
    items = {item["id"]: item for item in P.load_corpus_items(HOLDOUT)}
    goldens = {intent["intent"]: intent.get("golden") for intent in P.load_corpus(HOLDOUT)}
    annotated = [annotate(row, items[row["id"]], goldens[row["intent_id"]]) for row in rows]
    by_arm = _group(annotated, "arm")
    h0, h2 = arm_summary(by_arm["H0"]), arm_summary(by_arm["H2"])
    table, outcome = intent_comparison(annotated)
    return {
        "run_id": meta["run_id"],
        "integrity": dataclasses.asdict(report) | {"clean": report.clean},
        "arms": {"H0": h0, "H2": h2},
        "intent_outcome": outcome,
        "intents": table,
        "decision": decide(h0, h2),
        "rows": annotated,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    result = analyze(args.run_dir)
    with open(Path(args.run_dir) / "aggregation_ab_summary.json", "x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, default=str)
    view = {key: result[key] for key in ("run_id", "intent_outcome", "decision")}
    view["arms"] = {arm: {key: value for key, value in summary.items() if key != "by_cell"}
                    for arm, summary in result["arms"].items()}
    print(json.dumps(view, ensure_ascii=False, indent=2, default=str))
    print(CASE_MEANING[result["decision"]["case"]])


if __name__ == "__main__":
    main()
