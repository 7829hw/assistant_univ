# -*- coding: utf-8 -*-
"""27B teacher 대상 manifest(PLAN.md 5절). M1 AND priority ∈ {1, 2}. 모델 호출 없음.

    python sft_dpo_inventory/p0_sft_003_recovery/build_teacher27b_manifest.py   # -> teacher27b_manifest.json

대상 선택은 p0_sft_003_prep manifest(M 분류·priority)에서 바로 계산한다. M2 결과를 보지 않는다.
"왜 8B가 실패했는지"는 기존 HF 8B 9표본(greedy 1 + sampling 8)의 판정 범주와 원 출력 diff 항목 빈도다.
"""
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    prep = json.loads((ROOT / "sft_dpo_inventory/p0_sft_003_prep/missing_reasoning_manifest.json").read_text(encoding="utf-8"))
    targets = [x for x in prep["items"] if x["m_class"] == "M1" and x["priority"] in (1, 2)]
    v006 = {json.loads(x)["metadata"]["source_record_id"]: json.loads(x) for x in
            (ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl").read_text(encoding="utf-8").splitlines()}
    traces = collections.defaultdict(list)
    for line in (ROOT / "training/generated/thinking_traces/p0_v006_hf/traces.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        traces[r["item_id"]].append(r)
    items = []
    for x in targets:
        f = x["semantic_features"]
        rs = traces[x["item_id"]]
        cats = collections.Counter(r["judge"]["category"] for r in rs)
        diff_keys = collections.Counter(d[0] for r in rs for d in (r["judge"].get("raw_diffs") or []))
        items.append({
            "item_id": x["item_id"], "question": v006[x["item_id"]]["messages"][1]["content"], "source": x["source"],
            "priority": x["priority"], "semantic_family": x["near_family"],
            "measure": f.get("measure"), "dimension": f.get("dimension"), "dimension_target": f.get("dimension_target"),
            "od_role": f.get("od_roles"), "od_ne_dt": bool(f.get("od_ne_dt")), "bucket": f.get("bucket"), "order": f.get("order"),
            "gap": {"augment_dt_event": "A", "augment_od_vs_dt": "B"}.get(x["source"]),
            "compile_stop_target": x["compile_stop_target"],
            "why_8b_failed": {"samples": len(rs), "exact": cats.get("EXACT_OR_SEMANTIC_MATCH", 0), "categories": dict(cats),
                              "top_raw_diff_fields": dict(diff_keys.most_common(4))},
            "why_27b": f"8B 9표본 모두 정답 아님(M1). 우선순위 P{x['priority']}: {x['coverage_reason']}",
            "planned_calls": {"greedy": 1, "sampling": 4}})
    summary = {"targets": len(items), "by_priority": dict(collections.Counter(i["priority"] for i in items)),
               "by_source": dict(collections.Counter(i["source"] for i in items)),
               "dimension_target": dict(collections.Counter(str(i["dimension_target"]) for i in items)),
               "od_ne_dt": sum(i["od_ne_dt"] for i in items), "bucket": sum(bool(i["bucket"]) for i in items),
               "measure": dict(collections.Counter(i["measure"] for i in items)),
               "planned_calls_max": 5 * len(items),
               "rule": "M1 AND priority ∈ {P1, P2}(p0_sft_003_prep manifest), M2 결과와 무관"}
    (HERE / "teacher27b_manifest.json").write_text(json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=1) + "\n",
                                                   encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
