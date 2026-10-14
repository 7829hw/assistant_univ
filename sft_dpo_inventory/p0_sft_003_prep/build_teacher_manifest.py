# -*- coding: utf-8 -*-
"""survival(PLAN 8절)과 missing reasoning manifest(PLAN 8·9절). 모델 호출 없음.

    python sft_dpo_inventory/p0_sft_003_prep/build_teacher_manifest.py   # -> survival.json, missing_reasoning_manifest.json

- 단계: v006 154 → EXACT trace 있음 → 필터 통과 trace 있음(= 선택) → 승인(R70).
- M1 = EXACT 없음, M2 = 선택 trace 거부, M3 = EXACT 있지만 필터에서 모두 빠짐.
- 우선순위·action은 PLAN 9절 그대로다. teacher 호출은 없다.
"""
import collections
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("ca", HERE / "coverage_analysis.py")
CA = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CA)


def main():
    v006 = CA.train_set(CA.read_jsonl(ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl"))
    r70_ids = {json.loads(x)["metadata"]["source_record_id"] for x in
               (ROOT / "training/generated/p0_sft_002/r70/sft_train.jsonl").read_text(encoding="utf-8").splitlines()}
    exact_any = {r["item_id"] for r in map(json.loads, (ROOT / "training/generated/thinking_traces/p0_v006_hf/traces.jsonl")
                                         .read_text(encoding="utf-8").splitlines())
                 if r["judge"]["category"] == "EXACT_OR_SEMANTIC_MATCH"}
    quality = json.loads((ROOT / "evaluation/partial_grounding/sft_p0/trace_quality.json").read_text(encoding="utf-8"))
    filtered = {t.split(":")[0] for t in quality["adoption"]["after_filters_trace_ids"]}
    review = json.loads((ROOT / "sft_dpo_inventory/p0_sft_001/trace_review.json").read_text(encoding="utf-8"))
    reject_reason = {x["item_id"]: x.get("reason_code") for x in review["items"] if x["decision"] == "REJECT_TRACE"}
    approved = {x["item_id"] for x in review["items"] if x["decision"] == "APPROVE_TRACE"}
    if approved != r70_ids:
        raise SystemExit("승인 집합이 R70과 다르다")
    verification = json.loads((ROOT / "evaluation/partial_grounding/sft_p0/v006_verification.json").read_text(encoding="utf-8"))
    stop = {x["id"] for x in verification["items"] if x["full_exec"]["outcome"] is None}

    def feat_flags(t):
        ft = t["ft"]
        return {"bucket": ft.get("bucket") is not None, "dt_pickup": ft.get("dimension_target") == "pickup",
                "dt_dropoff": ft.get("dimension_target") == "dropoff", "dt_both": ft.get("dimension_target") == "both",
                "od_ne_dt": bool(ft.get("od_ne_dt")), "gap_a": t["source"] == "augment_dt_event",
                "gap_b": t["source"] == "augment_od_vs_dt", "place": (ft.get("n_places") or 0) > 0,
                "scope": bool(ft.get("has_scope")), "compile_stop_target": t["id"] in stop,
                "aggregation": ft.get("aggregation") is not None, "rollup": ft.get("rollup") is not None,
                **{f"measure_{ft['measure']}": True}}
    stages = {"v006": lambda i: True, "exact_trace": lambda i: i in exact_any, "filtered_trace(selected)": lambda i: i in filtered,
              "approved_r70": lambda i: i in approved}
    table = collections.defaultdict(lambda: {s: 0 for s in stages})
    for t in v006:
        flags = {k for k, v in feat_flags(t).items() if v} | {"all"}
        for s, fn in stages.items():
            if fn(t["id"]):
                for k in flags:
                    table[k][s] += 1
    for k, row in table.items():
        row["survival"] = round(row["approved_r70"] / row["v006"], 3) if row["v006"] else None

    cov = json.loads((HERE / "coverage_analysis.json").read_text(encoding="utf-8"))
    regression_near = {x["near_family"] for x in cov["items"] if x["group"] == "B"}
    r70 = [t for t in v006 if t["id"] in approved]
    r70_exact = {t["exact"] for t in r70}
    near_count = collections.Counter(t["near"] for t in r70)
    manifest = []
    for t in v006:
        if t["id"] in approved:
            continue
        reason = ("NO_CORRECT_TRACE" if t["id"] not in exact_any else
                  "REJECTED_IN_REVIEW" if t["id"] in reject_reason else "FILTERED_OUT")
        m_class = {"NO_CORRECT_TRACE": "M1", "REJECTED_IN_REVIEW": "M2", "FILTERED_OUT": "M3"}[reason]
        ft = t["ft"]
        important = bool(ft.get("dimension_target") or ft.get("od_ne_dt") or ft.get("bucket") or t["id"] in stop)
        if t["exact"] not in r70_exact and t["near"] in regression_near:
            priority, why = 1, "exact family가 R70에 없고 near family가 panel regression 문항과 같음"
        elif important and near_count[t["near"]] <= 2:
            priority, why = 2, f"중요 feature(dt·od_ne_dt·bucket·compile 정지)이고 R70 near family {near_count[t['near']]}개"
        else:
            priority, why = 3, f"R70 near family {near_count[t['near']]}개"
        manifest.append({"item_id": t["id"], "source": t["source"], "missing_reason": reason, "m_class": m_class,
                         "review_reject_reason": reject_reason.get(t["id"]), "priority": priority,
                         "semantic_features": {k: (list(v) if isinstance(v, tuple) else v) for k, v in ft.items()
                                               if v not in (None, False, 0, (), "")},
                         "near_family": t["near"], "r70_near_family_count": near_count[t["near"]],
                         "exact_family_in_r70": t["exact"] in r70_exact, "compile_stop_target": t["id"] in stop,
                         "coverage_reason": why,
                         "recommended_teacher_action": {"M1": "SUPPLEMENT", "M2": "REVIEW_OR_RESAMPLE", "M3": "REFILTER"}[m_class]})
    summary = {"missing": len(manifest), "m_class": dict(collections.Counter(x["m_class"] for x in manifest)),
               "priority": dict(collections.Counter(x["priority"] for x in manifest)),
               "priority_by_m": {f"P{p}": dict(collections.Counter(x["m_class"] for x in manifest if x["priority"] == p)) for p in (1, 2, 3)},
               "by_source": dict(collections.Counter(x["source"] for x in manifest)),
               "regression_near_families": sorted(regression_near)}
    (HERE / "survival.json").write_text(json.dumps({"stages": list(stages), "table": dict(sorted(table.items()))},
                                                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "missing_reasoning_manifest.json").write_text(json.dumps({"summary": summary, "items": manifest},
                                                                     ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for k in ("all", "bucket", "dt_pickup", "dt_dropoff", "dt_both", "od_ne_dt", "gap_a", "gap_b", "place", "scope",
              "compile_stop_target", "aggregation", "rollup"):
        print(k, table[k])


if __name__ == "__main__":
    main()
