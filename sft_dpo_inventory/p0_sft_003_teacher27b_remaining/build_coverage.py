# -*- coding: utf-8 -*-
"""coverage 갱신과 남은 문항 manifest(PLAN.md 8절). 모델 호출 없음. -> coverage_after.json, remaining_manifest.json

- covered = 110(R70 ∪ M2 ∪ M3 ∪ 27B P1/P2) ∪ Track A 승인. Track B rationale 후보는 더하지 않는다.
- feature 정의는 p0_sft_003_teacher27b/build_coverage_after.py의 FLAGS와 같다.
"""
import collections
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("prev", ROOT / "sft_dpo_inventory/p0_sft_003_teacher27b/build_coverage_after.py")
PREV = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PREV)
CA, FLAGS = PREV.CA, PREV.FLAGS


def main():
    jl = CA.read_jsonl
    v006 = CA.train_set(jl(ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl"))
    by_id = {t["id"]: t for t in v006}
    part = json.loads((HERE / "partition.json").read_text(encoding="utf-8"))
    r70 = {r["metadata"]["source_record_id"] for r in jl(ROOT / "training/generated/p0_sft_002/r70/sft_train.jsonl")}
    rec = jl(ROOT / "sft_dpo_inventory/p0_sft_003_recovery/recovered_traces.jsonl")
    m2 = {r["item_id"] for r in rec if r["recovery"] == "M2"}
    m3 = {r["item_id"] for r in rec if r["recovery"] == "M3"}
    t27a = {r["item_id"] for r in jl(ROOT / "sft_dpo_inventory/p0_sft_003_teacher27b/generation/approved_traces.jsonl")}
    t27b = {r["item_id"] for r in jl(HERE / "generation/approved_traces.jsonl")}
    before = r70 | m2 | m3 | t27a
    if len(before) != 110 or before & t27b:
        raise SystemExit("시작 coverage 불일치 또는 중복")
    after = before | t27b
    review = json.loads((HERE / "generation/human_review.json").read_text(encoding="utf-8"))["items"]
    judge = json.loads((HERE / "generation/judge.json").read_text(encoding="utf-8"))["items"]
    man = json.loads((HERE / "target_manifest.json").read_text(encoding="utf-8"))["items"]
    targets = [x["item_id"] for x in man]
    table = {}
    for name, fn in FLAGS.items():
        ts = [t for t in v006 if fn(t)]
        n = len(ts)
        table[name] = {"v006": n, "before": sum(t["id"] in before for t in ts), "after": sum(t["id"] in after for t in ts),
                       "before_ratio": round(sum(t["id"] in before for t in ts) / n, 3) if n else None,
                       "after_ratio": round(sum(t["id"] in after for t in ts) / n, 3) if n else None}
    track_a = {name: {"target": sum(fn(by_id[i]) for i in targets), "correct_ge1": sum(fn(by_id[i]) and judge[i]["exact"] > 0 for i in targets),
                      "approved": sum(fn(by_id[i]) and i in t27b for i in targets)} for name, fn in FLAGS.items()}
    remaining = []
    for i in sorted(set(by_id) - after):
        if i in part["ids"]["T27_FAILED"]:
            tax, prev = "IMPLICIT_PICKUP_REPEAT_FAILURE", "M1 P1/P2(27B P1/P2 batch 5/5 실패)"
        elif review.get(i, {}).get("decision") == "REJECT_TRACE":
            tax, prev = "TOP1_REJECTED", next(k for k, v in part["ids"].items() if i in v)
        elif i in judge and judge[i]["exact"] == 0:
            tax, prev = "NO_CORRECT_27B_TRACE", next(k for k, v in part["ids"].items() if i in v)
        else:
            tax, prev = "OTHER", next((k for k, v in part["ids"].items() if i in v), None)
        t = by_id[i]
        remaining.append({"item_id": i, "taxonomy": tax, "original_class": prev, "source": t["source"],
                          "features": [n for n, fn in FLAGS.items() if fn(t)],
                          "note": review.get(i, {}).get("reason") if i in review else
                          "Track B: implicit-pickup, rationale 후보만 있음(training_inclusion false)"})
    doc = {"covered_items": len(after), "of": len(v006), "ratio": round(len(after) / len(v006), 3),
           "before": {"covered": len(before), "ratio": round(len(before) / len(v006), 3)},
           "by_source": {"HF Qwen3-8B R70": len(r70), "HF Qwen3-8B M2 회수": len(m2), "M3 기존 trace 회수": len(m3),
                         "Ollama qwen3.8:27b P1/P2": len(t27a), "Ollama qwen3.8:27b remaining(Track A)": len(t27b)},
           "duplicate_ids": 0, "track_b_rationale_counted": 0,
           "feature_coverage": table, "track_a_by_feature": track_a,
           "remaining": {"count": len(remaining), "taxonomy": dict(collections.Counter(r["taxonomy"] for r in remaining)),
                         "original_class": dict(collections.Counter(r["original_class"] for r in remaining))},
           "frozen_dataset": None, "training_runs": 0}
    (HERE / "coverage_after.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "remaining_manifest.json").write_text(json.dumps({"count": len(remaining), "items": remaining}, ensure_ascii=False, indent=1) + "\n",
                                                  encoding="utf-8")
    print(json.dumps({k: doc[k] for k in ("covered_items", "ratio", "before", "by_source", "remaining")}, ensure_ascii=False, indent=1))
    for k, v in table.items():
        print(k, v, track_a[k])
    for r in remaining:
        print(r["item_id"], r["taxonomy"], r["original_class"], r["features"])


if __name__ == "__main__":
    main()
