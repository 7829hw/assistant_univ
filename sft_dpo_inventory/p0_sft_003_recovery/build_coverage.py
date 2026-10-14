# -*- coding: utf-8 -*-
"""reasoning coverage manifest(PLAN.md 6·7절). 모델 호출 없음. -> coverage_manifest.json

- covered = R70 70 ∪ 회수 M3 ∪ 회수 M2(unique item).
- feature는 p0_sft_003_prep/coverage_analysis.feats와 같은 정의다.
- known_uncovered_family: scope 역조회·refusal(v006에 학습 예제 없음).
  - v006의 정지 target(compile·운영 경로 정지) 표현을 inventory로 남긴다. 새 문항은 만들지 않는다.
"""
import collections
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("ca", ROOT / "sft_dpo_inventory/p0_sft_003_prep/coverage_analysis.py")
CA = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CA)


def main():
    v006 = CA.train_set(CA.read_jsonl(ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl"))
    r70 = {json.loads(x)["metadata"]["source_record_id"] for x in
           (ROOT / "training/generated/p0_sft_002/r70/sft_train.jsonl").read_text(encoding="utf-8").splitlines()}
    rec = [json.loads(x) for x in (HERE / "recovered_traces.jsonl").read_text(encoding="utf-8").splitlines()]
    m3 = {r["item_id"] for r in rec if r["recovery"] == "M3"}
    m2 = {r["item_id"] for r in rec if r["recovery"] == "M2"}
    covered = r70 | m3 | m2
    flags = {
        "dt_pickup": lambda t: t["ft"].get("dimension_target") == "pickup",
        "dt_dropoff": lambda t: t["ft"].get("dimension_target") == "dropoff",
        "dt_both": lambda t: t["ft"].get("dimension_target") == "both",
        "od_ne_dt": lambda t: bool(t["ft"].get("od_ne_dt")),
        "gap_a": lambda t: t["source"] == "augment_dt_event", "gap_b": lambda t: t["source"] == "augment_od_vs_dt",
        "bucket": lambda t: t["ft"].get("bucket") is not None, "order": lambda t: t["ft"].get("order") is not None,
        "emd": lambda t: t["ft"].get("dimension") == "emd", "sido": lambda t: t["ft"].get("dimension") == "sido",
        "sigungu": lambda t: t["ft"].get("dimension") == "sigungu", "h3": lambda t: t["ft"].get("dimension") == "h3",
        "aggregation": lambda t: t["ft"].get("aggregation") is not None}
    table = {}
    for name, fn in flags.items():
        ts = [t for t in v006 if fn(t)]
        n = len(ts)
        table[name] = {"v006": n, "r70": sum(t["id"] in r70 for t in ts), "after_recovery": sum(t["id"] in covered for t in ts),
                       "r70_ratio": round(sum(t["id"] in r70 for t in ts) / n, 3) if n else None,
                       "after_ratio": round(sum(t["id"] in covered for t in ts) / n, 3) if n else None}
    verification = json.loads((ROOT / "evaluation/partial_grounding/sft_p0/v006_verification.json").read_text(encoding="utf-8"))
    stops = [{"item_id": x["id"], "error_code": x["full_exec"]["error_code"]} for x in verification["items"]
             if x["full_exec"]["outcome"] is None]
    v006_rows = CA.read_jsonl(ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl")
    unsupported_targets = sum(json.loads(r["messages"][2]["content"]).get("unsupported") is True for r in v006_rows)
    prep = json.loads((ROOT / "sft_dpo_inventory/p0_sft_003_prep/missing_reasoning_manifest.json").read_text(encoding="utf-8"))
    remaining = [x for x in prep["items"] if x["item_id"] not in covered]
    doc = {
        "covered_items": len(covered), "of": len(v006), "ratio": round(len(covered) / len(v006), 3),
        "components": {"r70": len(r70), "m3_recovered": sorted(m3), "m2_recovered": sorted(m2)},
        "feature_coverage": table,
        "remaining_missing": {"count": len(remaining), "m_class": dict(collections.Counter(x["m_class"] for x in remaining)),
                              "m1_p12": sum(x["m_class"] == "M1" and x["priority"] in (1, 2) for x in remaining),
                              "ids": sorted(x["item_id"] for x in remaining)},
        "known_uncovered_family": {
            "scope_reverse": {"v006_examples": 0, "note": "평가 보호 family와 겹쳐 batch006 Gap C 제외(결정 67). batch007 후보"},
            "refusal": {"v006_unsupported_targets": unsupported_targets, "v006_needs_clarification_targets": 0,
                        "v006_stop_targets(운영 경로 정지 gold)": stops,
                        "note": "v006의 정지 target은 계약상 정지 코드로 끝나는 grounding이다. 거부(unsupported·needs_clarification) 응답 예제는 0. batch007 후보"}},
        "provenance_fields": ["teacher_model", "teacher_revision", "generation_batch", "seed", "quality_tier", "review_decision"],
        "frozen_dataset": None}
    (HERE / "coverage_manifest.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: doc[k] for k in ("covered_items", "ratio", "remaining_missing")}, ensure_ascii=False, indent=1)[:900])
    for k, v in table.items():
        print(k, v)


if __name__ == "__main__":
    main()
