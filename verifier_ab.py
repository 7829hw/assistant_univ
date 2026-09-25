# -*- coding: utf-8 -*-
"""의미 검증기 holdout에서 H0와 V0를 비교하고 사전 등록한 규칙으로 판정한다.

V0는 H0 grounding을 그대로 쓰므로 한 관측에서 두 결과가 나온다. H0는 최종 계획을
그대로 실행한 결과, V0는 검증기가 inconsistent로 판정하면 계획 없이 거부한 결과다.
판정 규칙은 결과를 보기 전에 이 파일과
``evaluation/prompt_ab/variants/verifier_decision_rule.md``에 고정했다.

사용: python verifier_ab.py <run_dir>
"""

import argparse
import dataclasses
import json
from collections import Counter, defaultdict
from pathlib import Path

import evaluate_prompt_ab as A
import paraphrase_corpus as P
import semantic_verifier as V

HOLDOUT = P.BASE_DIR / "evaluation" / "paraphrases_verifier_holdout.yaml"
MIN_PRECISION = 0.9
MAX_FP_INTENTS = 1
MIN_TP_INTENTS = 2
MIN_TP_FAMILIES = 2
MAX_FALLBACK_RATE = 0.10


def annotate(row, intent, item):
    refusal_expected = P.NONE_LABEL in (item.get("expected_macros") or [])
    validated = bool(row.get("validated"))
    h0_strict = bool(row.get("strict_correct"))
    verification = row.get("semantic_verification") or {}
    outcome = verification.get("outcome")
    rejected = bool(row.get("v0_rejected"))
    # V0: 거부하면 계획이 없다. 지원 범위 밖 질의라면 그것이 정답이다.
    v0_validated = validated and not rejected
    v0_strict = (refusal_expected if rejected else h0_strict)
    calls = verification.get("calls") or []
    invariant = (row.get("v0_final_tool_args") is None if rejected
                 else row.get("v0_final_tool_args") == row.get("final_tool_args"))
    return {
        "id": row["id"], "intent": row["intent_id"],
        "family": intent["family"], "control": bool(intent["control"]),
        "refusal_expected": refusal_expected, "status": row["status"],
        "h0_validated": validated, "h0_strict": h0_strict,
        "h0_silent": validated and not h0_strict,
        "h0_supported_rejection": not refusal_expected and not validated,
        "v0_validated": v0_validated, "v0_strict": v0_strict,
        "v0_silent": v0_validated and not v0_strict,
        "v0_supported_rejection": not refusal_expected and not v0_validated,
        "verifier_called": outcome not in (None, V.NOT_CALLED),
        "outcome": outcome, "fallback_reason": verification.get("reason"),
        "rejected": rejected, "issues": verification.get("issues") or [],
        "signature_text": verification.get("signature_text"),
        "invariant_ok": invariant,
        "h0_tool_calls": row.get("h0_tool_calls", 0), "v0_tool_calls": row.get("v0_tool_calls", 0),
        "verifier_ms": sum(call.get("elapsed_ms") or 0.0 for call in calls),
        "verifier_load_ms": [call.get("load_duration_ms") for call in calls],
        "first_load_ms": row.get("cold_load_ms"),
    }


def _intents(rows, predicate):
    return sorted({row["intent"] for row in rows if predicate(row)})


def summarize(rows):
    called = [row for row in rows if row["verifier_called"]]
    tp = [r for r in called if r["h0_silent"] and r["rejected"]]
    fp = [r for r in called if r["h0_strict"] and r["rejected"]]
    fn = [r for r in called if r["h0_silent"] and not r["rejected"]]
    tn = [r for r in called if r["h0_strict"] and not r["rejected"]]
    precision = len(tp) / (len(tp) + len(fp)) if tp or fp else None
    recall = len(tp) / (len(tp) + len(fn)) if tp or fn else None
    fallbacks = [r for r in called if r["outcome"] == V.FALLBACK]
    by_family = {}
    for family in sorted({r["family"] for r in rows}):
        members = [r for r in rows if r["family"] == family]
        by_family[family] = {
            "observations": len(members),
            "h0_silent": sum(r["h0_silent"] for r in members),
            "v0_silent": sum(r["v0_silent"] for r in members),
            "tp": sum(r in tp for r in members), "fp": sum(r in fp for r in members),
            "fn": sum(r in fn for r in members), "tn": sum(r in tn for r in members),
            "h0_strict": sum(r["h0_strict"] for r in members),
            "v0_strict": sum(r["v0_strict"] for r in members),
        }
    verifier_ms = sorted(r["verifier_ms"] for r in called)
    return {
        "observations": len(rows),
        "verifier_calls": len(called),
        "outcomes": dict(Counter(r["outcome"] for r in rows)),
        "fallback_reasons": dict(Counter(r["fallback_reason"] for r in fallbacks)),
        "fallback_rate": round(len(fallbacks) / len(called), 3) if called else 0.0,
        "confusion": {"tp": len(tp), "fp": len(fp), "fn": len(fn), "tn": len(tn)},
        "precision": None if precision is None else round(precision, 3),
        "recall": None if recall is None else round(recall, 3),
        "tp_ids": [r["id"] for r in tp], "fp_ids": [r["id"] for r in fp],
        "tp_intents": _intents(tp, lambda r: True),
        "fp_intents": _intents(fp, lambda r: True),
        "tp_families": sorted({r["family"] for r in tp}),
        "h0": {"strict": sum(r["h0_strict"] for r in rows),
               "silent": sum(r["h0_silent"] for r in rows),
               "silent_intents": _intents(rows, lambda r: r["h0_silent"]),
               "supported_rejection": sum(r["h0_supported_rejection"] for r in rows),
               "strict_intents": sorted(n for n, m in _group(rows).items()
                                        if all(r["h0_strict"] for r in m)),
               "tool_calls": sum(r["h0_tool_calls"] for r in rows)},
        "v0": {"strict": sum(r["v0_strict"] for r in rows),
               "silent": sum(r["v0_silent"] for r in rows),
               "silent_intents": _intents(rows, lambda r: r["v0_silent"]),
               "supported_rejection": sum(r["v0_supported_rejection"] for r in rows),
               "strict_intents": sorted(n for n, m in _group(rows).items()
                                        if all(r["v0_strict"] for r in m)),
               "tool_calls": sum(r["v0_tool_calls"] for r in rows)},
        "v0_only_silent": [r["id"] for r in rows if r["v0_silent"] and not r["h0_silent"]],
        "invariant_violations": [r["id"] for r in rows if not r["invariant_ok"]],
        "by_family": by_family,
        "issue_kinds": dict(Counter(issue["kind"] for r in rows if r["rejected"]
                                    for issue in r["issues"])),
        "verifier_ms": {"total": round(sum(verifier_ms), 1),
                        "median": verifier_ms[len(verifier_ms) // 2] if verifier_ms else None,
                        "max": verifier_ms[-1] if verifier_ms else None},
        "verifier_load_ms_max": max((x or 0) for r in called for x in r["verifier_load_ms"])
                                if called else None,
    }


def _group(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["intent"]].append(row)
    return groups


# -- 사전 등록 판정 ---------------------------------------------------------


def decide(summary):
    """결과를 보기 전에 고정한 규칙. verifier_decision_rule.md와 같다."""
    precision = summary["precision"]
    checks = {
        "A_no_v0_only_silent": not summary["v0_only_silent"]
            and not summary["invariant_violations"],
        "B_fp_intents_at_most_1": len(summary["fp_intents"]) <= MAX_FP_INTENTS,
        "C_detects_2_silent_intents": len(summary["tp_intents"]) >= MIN_TP_INTENTS,
        "D_detects_2_families": len(summary["tp_families"]) >= MIN_TP_FAMILIES,
        "E_precision_at_least_0_9": precision is None or precision >= MIN_PRECISION,
        "F_fallback_rate_at_most_0_1": summary["fallback_rate"] <= MAX_FALLBACK_RATE,
    }
    if not checks["A_no_v0_only_silent"]:
        case = "INVALID"
    elif not (checks["B_fp_intents_at_most_1"] and checks["E_precision_at_least_0_9"]):
        case = "C"
    elif not checks["C_detects_2_silent_intents"]:
        case = "D"
    elif not checks["D_detects_2_families"]:
        case = "B"
    elif not checks["F_fallback_rate_at_most_0_1"]:
        case = "UNRELIABLE"
    else:
        case = "A_REVIEW" if summary["fp_intents"] else "A"
    return {"case": case, "checks": checks}


CASE_MEANING = {
    "A": "production semantic gate 후보. 도입은 별도 단계",
    "A_REVIEW": "production semantic gate 후보이나 거부된 정답 intent 1개를 사람이 검토한다",
    "B": "한 family만 잡는다. 범용 검증기로 가치 낮음",
    "C": "정답 거부가 많다. 검증기 폐기, H0 유지",
    "D": "조용한 오답 탐지가 부족하다. 추가 prompt 연구 중단",
    "UNRELIABLE": "검증기 출력 실패가 많다. 채택하지 않는다",
    "INVALID": "V0가 H0에 없는 계획을 만들었다. 구현 오류다",
}


def analyze(run_dir):
    meta, rows, report = A.load_run(run_dir)
    if not report.clean:
        raise SystemExit(f"무결성 문제로 분석하지 않는다: {dataclasses.asdict(report)}")
    items = {item["id"]: item for item in P.load_corpus_items(HOLDOUT)}
    intents = {intent["intent"]: intent for intent in P.load_corpus(HOLDOUT)}
    invalid = sorted(row["id"] for row in rows if row.get("measurement") != A.VALID)
    annotated = [annotate(row, intents[row["intent_id"]], items[row["id"]])
                 for row in rows if row["id"] not in invalid]
    summary = summarize(annotated)
    return {"run_id": meta["run_id"],
            "integrity": dataclasses.asdict(report) | {"clean": report.clean},
            "invalid_paraphrases": invalid,
            "cold_load_verified": sum(bool(row.get("cold_load_verified")) for row in rows
                                      if row["id"] not in invalid),
            "summary": summary, "decision": decide(summary), "rows": annotated}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir")
    args = parser.parse_args(argv)
    result = analyze(args.run_dir)
    with open(Path(args.run_dir) / "verifier_summary.json", "x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, default=str)
    view = {key: result[key] for key in ("run_id", "invalid_paraphrases", "cold_load_verified",
                                         "decision")}
    view["summary"] = result["summary"]
    print(json.dumps(view, ensure_ascii=False, indent=2, default=str))
    print(CASE_MEANING[result["decision"]["case"]])


if __name__ == "__main__":
    main()
