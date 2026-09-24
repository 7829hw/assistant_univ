# -*- coding: utf-8 -*-
"""production H2 통합 확인: 측정한 H2 arm과 production 동작, H0 census와 H2 census를 비교한다.

판정용 측정이 아니다. aggregation corpus는 이미 development다.

사용: python aggregation_production_compare.py \
        --measured <H0 vs H2 holdout run> --dev <production H2 aggregation run> \
        --old-census <H0 census run> --new-census <H2 census run> --out <json>
"""

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

os.environ.setdefault("ASSISTANT_TOOL_PROVIDER", "mock")

import aggregation_ab as B
import aggregation_plan as AP
import evaluate_prompt_ab as A
import failure_census as C
import paraphrase_corpus as P

AGGREGATION_KEYS = set(AP.FLAT_KEYS)


# -- aggregation corpus: measured H2 arm vs production ---------------------


def _annotated(run_dir, variant):
    meta, rows, report = A.load_run(run_dir)
    if not report.clean:
        raise SystemExit(f"무결성 문제: {run_dir}")
    items = {item["id"]: item for item in P.load_corpus_items(B.HOLDOUT)}
    goldens = {intent["intent"]: intent.get("golden") for intent in P.load_corpus(B.HOLDOUT)}
    picked = [row for row in rows if row["variant"] == variant]
    invalid = {row["id"] for row in picked if row.get("measurement") != A.VALID}
    out = {}
    for row in picked:
        if row["id"] in invalid:
            continue
        # annotate는 arm 이름으로 H2 표현을 읽는다. production은 H2 계약이다.
        out[row["id"]] = B.annotate({**row, "variant": "H2_AGG"}, items[row["id"]],
                                    goldens[row["intent_id"]])
        out[row["id"]]["status"] = row["status"]
        out[row["id"]]["bucket_unit_elsewhere"] = "bucket_unit_in_other_factor" in \
            C.aggregation_families(_factors(row), {})
    return meta, out, sorted(invalid)


def _factors(row):
    payload = C._payload(row.get("raw_text")) or {}
    return payload.get("factors") if isinstance(payload.get("factors"), dict) else {}


def compare_dev(measured_dir, dev_dir):
    measured_meta, measured, measured_invalid = _annotated(measured_dir, "H2_AGG")
    # 측정 run에서 두 arm 중 하나라도 무효였던 paraphrase는 판정에서 뺐다. 여기서는
    # 두 run 모두 유효한 paraphrase만 짝지어 본다.
    dev_meta, dev, dev_invalid = _annotated(dev_dir, "PRODUCTION")
    common = sorted(set(measured) & set(dev))
    pairs = [(measured[i], dev[i]) for i in common]
    same = lambda key: sum(a[key] == b[key] for a, b in pairs)  # noqa: E731
    transitions = Counter(f"{_state(a)}->{_state(b)}" for a, b in pairs if _state(a) != _state(b))
    return {
        "measured_run": measured_meta["run_id"], "dev_run": dev_meta["run_id"],
        "prompt_sha256": {"measured": _sha(measured_meta, "H2_AGG"),
                          "dev": _sha(dev_meta, "PRODUCTION")},
        "invalid": {"measured": measured_invalid, "dev": dev_invalid},
        "paired_paraphrases": len(common),
        "measured": _summary([a for a, _ in pairs]),
        "dev": _summary([b for _, b in pairs]),
        "dev_all_valid": _summary(list(dev.values())),
        "agreement": {"status": same("status"), "final_strict": same("final_strict"),
                      "silent_wrong": same("silent_wrong"),
                      "predicted_semantic": same("predicted")},
        "state_transitions": dict(transitions),
        "changed": [{"id": a["id"], "measured": [a["status"], _state(a), a["predicted"]],
                     "dev": [b["status"], _state(b), b["predicted"]]}
                    for a, b in pairs if _state(a) != _state(b)],
    }


def _sha(meta, variant):
    return next(arm["prompt_sha256"] for arm in meta["arms"] if arm["variant"] == variant)


def _state(row):
    if row["refusal_expected"] and not row["validated"]:
        return "safe_rejection"
    if row["final_strict"]:
        return "strict"
    if row["silent_wrong"]:
        return "silent"
    return "rejected"


def _summary(rows):
    summary = B.arm_summary(rows)
    summary.pop("by_cell")
    summary["stage_swapped"] = sum(AP.STAGE_SWAPPED in row["aggregation_errors"] for row in rows)
    summary["bucket_unit_elsewhere"] = dict(Counter(
        _state(row) for row in rows if row["bucket_unit_elsewhere"]))
    summary["statuses"] = dict(Counter(row["status"] for row in rows))
    return summary


# -- census: H0 vs H2 ------------------------------------------------------


def _census(run_dir):
    meta, rows, report = A.load_run(run_dir)
    if not report.clean:
        raise SystemExit(f"무결성 문제: {run_dir}")
    valid = [row for row in rows if row.get("measurement") == A.VALID]
    annotated = C.annotate(valid, A.census_items(), meta)
    return meta, annotated, sorted(row["id"] for row in rows if row.get("measurement") != A.VALID)


def _is_aggregation_intent(row, gold):
    golden = gold.get(row["intent_id"]) or {}
    factors = golden.get("factors") or {}
    expected = row.get("expected_tool_args") or {}
    return bool(AGGREGATION_KEYS & set(factors)) or any(
        expected.get(key) is not None for key in AGGREGATION_KEYS)


def _census_summary(rows, gold):
    outcomes = Counter(row["outcome"] for row in rows)
    groups = Counter(name for row in rows for name in C.groups_of(row["families"])
                     if row["outcome"] not in (C.CORRECT, C.SAFE_REJECTION)
                     or not row["initial_correct"])
    group_intents = defaultdict(set)
    for row in rows:
        if row["outcome"] in (C.CORRECT, C.SAFE_REJECTION) and row["initial_correct"]:
            continue
        for name in C.groups_of(row["families"]):
            group_intents[name].add(row["intent_id"])
    silent = [row for row in rows if row["outcome"] == C.SILENT_WRONG_PLAN]
    return {
        "observations": len(rows),
        "replay_consistent": sum(row["replay_consistent"] for row in rows),
        "strict_correct": sum(row["final_correct"] for row in rows),
        "initial_strict_correct": sum(row["initial_correct"] for row in rows),
        "outcomes": dict(outcomes),
        "silent_wrong": len(silent),
        "silent_wrong_intents": sorted({row["intent_id"] for row in silent}),
        "execution_not_found": sum(row.get("exec_code") == "NOT_FOUND" for row in rows),
        "repair_attempted": sum(bool(row.get("repair_attempted")) for row in rows),
        "repair_succeeded": sum(bool(row.get("repair_succeeded")) for row in rows),
        "codes": dict(Counter(row["primary_code"] for row in rows if row["primary_code"])),
        "groups": {name: {"observations": count, "intents": len(group_intents[name])}
                   for name, count in sorted(groups.items())},
        "stage_swapped": sum("stage_swapped" in row["families"] for row in rows),
        "bucket_unit_elsewhere": {
            "observations": sum("bucket_unit_in_other_factor" in row["families"] for row in rows),
            "intents": sorted({row["intent_id"] for row in rows
                               if "bucket_unit_in_other_factor" in row["families"]}),
            "outcomes": dict(Counter(row["outcome"] for row in rows
                                     if "bucket_unit_in_other_factor" in row["families"])),
        },
        "aggregation_intents": _slice(rows, gold, True),
        "non_aggregation_intents": _slice(rows, gold, False),
    }


def _slice(rows, gold, aggregation):
    part = [row for row in rows if _is_aggregation_intent(row, gold) == aggregation]
    return {"observations": len(part),
            "intents": len({row["intent_id"] for row in part}),
            "strict_correct": sum(row["final_correct"] for row in part),
            "outcomes": dict(Counter(row["outcome"] for row in part))}



def compare_census(old_dir, new_dir):
    gold = C.goldens()
    old_meta, old_rows, old_invalid = _census(old_dir)
    new_meta, new_rows, new_invalid = _census(new_dir)
    old = {row["id"]: row for row in old_rows}
    new = {row["id"]: row for row in new_rows}
    common = sorted(set(old) & set(new))
    transitions = Counter()
    changed = []
    for key in common:
        a, b = old[key], new[key]
        if a["outcome"] == b["outcome"]:
            continue
        kind = "aggregation" if _is_aggregation_intent(a, gold) else "non_aggregation"
        transitions[f"{kind}: {a['outcome']} -> {b['outcome']}"] += 1
        changed.append({"id": key, "intent": a["intent_id"], "slice": kind,
                        "h0": [a["outcome"], a["primary_code"]],
                        "h2": [b["outcome"], b["primary_code"]],
                        "h2_families": b["families"]})
    old_silent = {row["intent_id"] for row in old_rows if row["outcome"] == C.SILENT_WRONG_PLAN}
    new_silent = {row["intent_id"] for row in new_rows if row["outcome"] == C.SILENT_WRONG_PLAN}
    return {
        "old_run": old_meta["run_id"], "new_run": new_meta["run_id"],
        "prompt_sha256": {"old": old_meta["arms"][0]["prompt_sha256"],
                          "new": new_meta["arms"][0]["prompt_sha256"]},
        "invalid": {"old": old_invalid, "new": new_invalid},
        "paired_questions": len(common),
        "h0": _census_summary([old[k] for k in common], gold),
        "h2": _census_summary([new[k] for k in common], gold),
        "h2_all_valid": _census_summary(new_rows, gold),
        "new_silent_intents": sorted(new_silent - old_silent),
        "resolved_silent_intents": sorted(old_silent - new_silent),
        "transitions": dict(transitions),
        "changed": changed,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--measured", required=True)
    parser.add_argument("--dev", required=True)
    parser.add_argument("--old-census", required=True)
    parser.add_argument("--new-census", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    result = {"aggregation_dev": compare_dev(args.measured, args.dev),
              "census": compare_census(args.old_census, args.new_census)}
    with open(args.out, "x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, default=str)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2, default=str)
    print()


if __name__ == "__main__":
    main()
