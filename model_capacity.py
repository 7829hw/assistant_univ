# -*- coding: utf-8 -*-
"""H0 architecture를 고정하고 grounding model만 바꾼 census를 비교한다. 평가 전용.

모든 모델 arm은 같은 production prompt(64bbceb4)와 재질의 문구(5af4c744), 같은 생성 옵션
(temperature 0, think 미지정), 같은 timeout(300초), 같은 isolation protocol을 쓴다.
바뀌는 것은 model id 하나다. 채점과 실패 분류는 failure_census.py 그대로다.

선택 규칙은 결과를 보기 전에 이 파일과
``evaluation/prompt_ab/variants/model_capacity_selection_rule.md``에 고정했다.

사용: python model_capacity.py --out <json> --census M0=<dir> --census M2=<dir> \
        --canary M0=<before>,<after> --canary M2=<before>,<after>
"""

import argparse
import dataclasses
import json
import statistics
import sys
from collections import Counter, defaultdict

import evaluate_planner as E
import evaluate_prompt_ab as A
import failure_census as C

BASELINE = "M0"
#: 결과를 보기 전에 고른 결정성 확인 질문. family마다 하나씩.
CANARY_IDS = ("f01_p0", "b24_p0", "b05_p0", "q27_p0", "b20_p0", "f14_p0", "h06_p0", "f12_p0")
MAX_INVALID_RATE = 0.05
#: 모델 크기 순서. 동률이면 앞의 것(작은 모델)을 고른다.
SIZE_ORDER = ("M0", "M1", "M2")
FAMILY_REPORT = ("aggregation_stage", "taxi_type_grounding", "od_role", "place_decomposition",
                 "place_resolution_miss", "event_or_measure", "fabricated_scope",
                 "model_refused_supported", "bucket_unit_elsewhere")


def _percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))]


def load_census(run_dir):
    meta, rows, report = A.load_run(run_dir)
    if not report.clean:
        raise SystemExit(f"무결성 문제: {run_dir} {dataclasses.asdict(report)}")
    valid = [row for row in rows if row.get("measurement") == A.VALID]
    annotated = {row["id"]: row for row in C.annotate(valid, A.census_items(), meta)}
    raw = {row["id"]: row for row in rows}
    return {"meta": meta, "rows": annotated, "raw": raw,
            "invalid": sorted(row["id"] for row in rows if row.get("measurement") != A.VALID),
            "report": report}


def _intent_table(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["intent_id"]].append(row)
    return groups


def _groups(row):
    return C.groups_of(row["families"]) or ["(ungrouped)"]


def summarize(rows, raw):
    intents = _intent_table(rows)
    silent = [r for r in rows if r["outcome"] == C.SILENT_WRONG_PLAN]
    failing = [r for r in rows if r["outcome"] not in (C.CORRECT, C.SAFE_REJECTION)
               or not r["initial_correct"]]
    refusal = [r for r in rows if E.NO_TEMPLATE_LABEL in (r.get("expected_macros") or [])]
    family = {}
    for name in FAMILY_REPORT + ("(ungrouped)",):
        members = [r for r in failing if name in _groups(r)]
        family[name] = {"observations": len(members),
                        "intents": len({r["intent_id"] for r in members}),
                        "silent": sum(r["outcome"] == C.SILENT_WRONG_PLAN for r in members),
                        "outcomes": dict(Counter(r["outcome"] for r in members))}
    calls = [call for r in rows for call in raw[r["id"]].get("llm_calls") or []]
    first = [raw[r["id"]]["llm_calls"][0].get("elapsed_ms") for r in rows
             if raw[r["id"]].get("llm_calls")]
    repair = [call.get("elapsed_ms") for call in calls if call.get("phase") == "repair"]
    cold = [raw[r["id"]].get("cold_load_ms") for r in rows if raw[r["id"]].get("cold_load_ms")]
    return {
        "observations": len(rows),
        "intents": len(intents),
        "strict": sum(r["final_correct"] for r in rows),
        "initial_strict": sum(r["initial_correct"] for r in rows),
        "outcomes": dict(Counter(r["outcome"] for r in rows)),
        "silent": len(silent),
        "silent_intents": sorted({r["intent_id"] for r in silent}),
        "strict_intents": sorted(n for n, m in intents.items() if all(r["final_correct"] for r in m)),
        "partial_intents": sorted(n for n, m in intents.items()
                                  if any(r["final_correct"] for r in m)
                                  and not all(r["final_correct"] for r in m)),
        "wrong_intents": sorted(n for n, m in intents.items()
                                if not any(r["final_correct"] for r in m)),
        "supported_rejection": sum(r["outcome"] == C.SUPPORTED_REJECTION for r in rows),
        "safe_rejection": sum(r["outcome"] == C.SAFE_REJECTION for r in rows),
        "recoverable_execution_failure": sum(r["outcome"] == C.RECOVERABLE_REJECTION for r in rows),
        "execution_not_found": sum(r.get("exec_code") == "NOT_FOUND" for r in rows),
        "repair_attempted": sum(bool(r.get("repair_attempted")) for r in rows),
        "repair_succeeded": sum(bool(r.get("repair_succeeded")) for r in rows),
        "unsupported_collapse": sum(r["outcome"] == C.SILENT_WRONG_PLAN for r in refusal),
        "unsupported_collapse_intents": sorted({r["intent_id"] for r in refusal
                                                if r["outcome"] == C.SILENT_WRONG_PLAN}),
        "silent_groups": dict(Counter(g for r in silent for g in _groups(r))),
        "families": family,
        "latency": {
            "cold_load_ms_median": statistics.median(cold) if cold else None,
            "first_response_ms_median": statistics.median(first) if first else None,
            "first_response_ms_p90": _percentile(first, 0.9),
            "first_response_ms_p95": _percentile(first, 0.95),
            "repair_ms_median": statistics.median(repair) if repair else None,
            "llm_calls": len(calls),
            "llm_wall_s": round(sum(call.get("elapsed_ms") or 0 for call in calls) / 1000, 1),
        },
    }


def _row_view(row, raw):
    payload = C._payload(raw.get("raw_text")) or {}
    return {"outcome": row["outcome"], "status": row["status"],
            "initial_factors": payload.get("factors"),
            "initial_concepts": [f"{c.get('concept')}/{c.get('subtype')}"
                                 for c in payload.get("concepts") or [] if isinstance(c, dict)],
            "final_tool_args": row.get("final_tool_args"),
            "arg_mismatches": row.get("arg_mismatches"), "families": row["families"],
            "repair_attempted": bool(row.get("repair_attempted"))}


def taxi_category(row):
    tags = set(row["families"])
    if row["final_correct"]:
        return "correct"
    if "taxi_type_as_concept" in tags or "correct_factor_plus_spurious_concept" in tags:
        return "conceptized"
    if "fabricated_scope" in tags:
        return "fabricated_scope"
    if "missing_factor:taxi_type" in tags:
        return "factor_omitted"
    if row["outcome"] == C.SILENT_WRONG_PLAN:
        return "silent_other"
    return "rejected_other"


def details(census, ids):
    rows, raw = census["rows"], census["raw"]
    f01 = {rid: _row_view(rows[rid], raw[rid]) for rid in ids if rid.startswith("f01_")}
    taxi = {}
    for rid in ids:
        row = rows[rid]
        if (row.get("expected_tool_args") or {}).get("taxi_type"):
            taxi[rid] = taxi_category(row)
    unsupported = {rid: rows[rid]["outcome"] for rid in ids
                   if E.NO_TEMPLATE_LABEL in (rows[rid].get("expected_macros") or [])}
    return {"f01": f01, "taxi_type": taxi,
            "taxi_type_categories": dict(Counter(taxi.values())),
            "unsupported": unsupported}


def canary(census, before_dir, after_dir):
    """같은 모델, 같은 질문을 run 전후에 다시 잰다. 첫 응답 원문이 같아야 한다."""
    runs = {"before": A.load_run(before_dir)[1], "after": A.load_run(after_dir)[1]}
    out, equal, compared = {}, 0, 0
    for rid in CANARY_IDS:
        texts = {"census": census["raw"].get(rid, {}).get("raw_text")}
        for name, rows in runs.items():
            row = next((r for r in rows if r["id"] == rid), None)
            texts[name] = row.get("raw_text") if row and row.get("measurement") == A.VALID else None
        present = [t for t in texts.values() if t is not None]
        same = len(present) == 3 and len(set(present)) == 1
        out[rid] = {"all_valid": len(present) == 3, "identical": same}
        compared += len(present) == 3
        equal += same
    return {"compared": compared, "identical": equal, "per_id": out,
            "deterministic": compared == len(CANARY_IDS) and equal == compared}


def model_meta(census):
    meta = census["meta"]
    arm = meta["arms"][0]
    return {"model": meta["model"], "digest": meta["model_digest"],
            "details": meta.get("model_details"), "ollama_version": meta["ollama_version"],
            "prompt_sha256": arm["prompt_sha256"], "repair_sha256": arm["repair_contract_sha256"],
            "options": meta["options"], "chat_timeout": meta["chat_timeout"],
            "run_id": meta["run_id"], "invalid": census["invalid"],
            "invalid_rate": round(len(census["invalid"]) / len(meta["query_ids"]), 3),
            "cold_load_verified": sum(bool(r.get("cold_load_verified")) for r in census["raw"].values()
                                      if r.get("measurement") == A.VALID),
            "fresh_restarts": sum(r.get("fresh_restarts") or 0 for r in census["raw"].values()),
            "other_models_loaded_after_reset": sum(bool(r.get("loaded_models_after_reset"))
                                                   for r in census["raw"].values())}


# -- 사전 등록 선택 규칙 ----------------------------------------------------


def _rank(name, s):
    return (len(s["silent_intents"]), s["silent"], -len(s["strict_intents"]), -s["strict"],
            s["supported_rejection"], s.get("invalid", 0), s["repair_attempted"],
            SIZE_ORDER.index(name))


def select(baseline, candidates):
    """baseline과 짝지은 요약으로 후보를 판정한다. 결과를 보기 전에 고정했다."""
    verdicts = {}
    for name, item in candidates.items():
        b, c = item["baseline"], item["candidate"]
        new_groups = sorted(set(c["silent_groups"]) - set(b["silent_groups"]))
        checks = {
            "A_fewer_silent_intents": len(c["silent_intents"]) < len(b["silent_intents"]),
            "B_no_new_silent_family": not new_groups,
            "C_strict_intents_not_worse": len(c["strict_intents"]) >= len(b["strict_intents"]),
            "D_unsupported_collapse_not_worse": c["unsupported_collapse"] <= b["unsupported_collapse"],
            "E_measurable": item["invalid_rate"] <= MAX_INVALID_RATE and item["deterministic"],
        }
        verdicts[name] = {"checks": checks, "new_silent_groups": new_groups,
                          "candidate": all(checks.values())}
    passing = [name for name, v in verdicts.items() if v["candidate"]]
    chosen = min(passing, key=lambda n: _rank(n, candidates[n]["candidate"]
                                              | {"invalid": len(candidates[n]["invalid"])}),
                 default=None)
    return {"verdicts": verdicts, "selected": chosen,
            "fresh_holdout_needed": chosen is not None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--census", action="append", required=True, help="NAME=run_dir")
    parser.add_argument("--canary", action="append", default=[], help="NAME=before,after")
    parser.add_argument("--excluded", action="append", default=[],
                        help="NAME=사유. census를 잴 수 없었던 모델")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    censuses = {k: load_census(v) for k, v in (s.split("=", 1) for s in args.census)}
    canaries = {k: v.split(",") for k, v in (s.split("=", 1) for s in args.canary)}
    base = censuses[BASELINE]
    result = {"models": {n: model_meta(c) for n, c in censuses.items()},
              "excluded": dict(s.split("=", 1) for s in args.excluded),
              "canary": {n: canary(censuses[n], *canaries[n]) for n in canaries},
              "comparisons": {}}
    candidates = {}
    for name, census in censuses.items():
        if name == BASELINE:
            continue
        ids = sorted(set(base["rows"]) & set(census["rows"]))
        b_rows = [base["rows"][i] for i in ids]
        c_rows = [census["rows"][i] for i in ids]
        comparison = {
            "paired_questions": len(ids),
            "excluded_invalid": sorted(set(base["invalid"]) | set(census["invalid"])),
            "baseline": summarize(b_rows, base["raw"]),
            "candidate": summarize(c_rows, census["raw"]),
            "baseline_details": details(base, ids), "candidate_details": details(census, ids),
            "transitions": dict(Counter(f"{base['rows'][i]['outcome']} -> {census['rows'][i]['outcome']}"
                                        for i in ids
                                        if base["rows"][i]["outcome"] != census["rows"][i]["outcome"])),
        }
        result["comparisons"][name] = comparison
        candidates[name] = {**comparison, "invalid": census["invalid"],
                            "invalid_rate": result["models"][name]["invalid_rate"],
                            "deterministic": result["canary"].get(name, {}).get("deterministic",
                                                                                False)
                            and result["canary"].get(BASELINE, {}).get("deterministic", False)}
    result["selection"] = select(base, candidates)
    with open(args.out, "x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, default=str)
    view = {"models": result["models"], "excluded": result["excluded"],
            "canary": {n: {k: v for k, v in c.items() if k != "per_id"}
                       for n, c in result["canary"].items()},
            "selection": result["selection"]}
    json.dump(view, sys.stdout, ensure_ascii=False, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
