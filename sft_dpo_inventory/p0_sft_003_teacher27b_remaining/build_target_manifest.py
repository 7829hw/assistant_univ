# -*- coding: utf-8 -*-
"""남은 44문항 partition 재계산과 Track A 대상 manifest(PLAN.md 2·3절). 모델 호출 없음.

    python sft_dpo_inventory/p0_sft_003_teacher27b_remaining/build_target_manifest.py
    # -> partition.json, target_manifest.json(Track A 40), target_manifest.sha256

- covered = R70 ∪ M3 회수 ∪ M2 회수 ∪ 27B P1/P2 승인. missing = v006 154 − covered.
- partition: M1 P3(27B 미시도) / M2 실패 / M3 실패 / 27B 실패(M1 P1·P2 중 미승인). 합이 44가 아니거나 겹치면 중단한다.
- Track A = M1 P3 + M2 실패 + M3 실패. 순서: 그룹(A1 → A2 → A3) 안에서 prep manifest 순서. item_index는 이 순서의 위치.
"""
import collections
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def jl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def main():
    prep = json.loads((ROOT / "sft_dpo_inventory/p0_sft_003_prep/missing_reasoning_manifest.json").read_text(encoding="utf-8"))["items"]
    v006 = {r["metadata"]["source_record_id"]: r for r in jl(ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl")}
    r70 = {r["metadata"]["source_record_id"] for r in jl(ROOT / "training/generated/p0_sft_002/r70/sft_train.jsonl")}
    rec = jl(ROOT / "sft_dpo_inventory/p0_sft_003_recovery/recovered_traces.jsonl")
    m2_ok = {r["item_id"] for r in rec if r["recovery"] == "M2"}
    m3_ok = {r["item_id"] for r in rec if r["recovery"] == "M3"}
    t27_ok = {r["item_id"] for r in jl(ROOT / "sft_dpo_inventory/p0_sft_003_teacher27b/generation/approved_traces.jsonl")}
    t27_target = [x["item_id"] for x in json.loads((ROOT / "sft_dpo_inventory/p0_sft_003_recovery/teacher27b_manifest.json")
                                                   .read_text(encoding="utf-8"))["items"]]
    covered = r70 | m2_ok | m3_ok | t27_ok
    if len(covered) != 110 or len(r70) + len(m2_ok) + len(m3_ok) + len(t27_ok) != 110:
        raise SystemExit(f"covered {len(covered)} != 110 또는 출처 간 중복")
    missing = [x for x in prep if x["item_id"] not in covered]
    if set(v006) - covered != {x["item_id"] for x in missing}:
        raise SystemExit("prep manifest 밖의 missing이 있다")
    parts = collections.OrderedDict((k, []) for k in ("M1_P3", "M2_FAILED", "M3_FAILED", "T27_FAILED"))
    for x in missing:
        if x["item_id"] in t27_target:
            parts["T27_FAILED"].append(x)
        elif x["m_class"] == "M1" and x["priority"] == 3:
            parts["M1_P3"].append(x)
        elif x["m_class"] == "M2":
            parts["M2_FAILED"].append(x)
        elif x["m_class"] == "M3":
            parts["M3_FAILED"].append(x)
        else:
            raise SystemExit(f"분류 불가: {x['item_id']} {x['m_class']} P{x['priority']}")
    sizes = {k: len(v) for k, v in parts.items()}
    ids = [x["item_id"] for v in parts.values() for x in v]
    if sizes != {"M1_P3": 28, "M2_FAILED": 11, "M3_FAILED": 1, "T27_FAILED": 4} or len(ids) != len(set(ids)) or len(ids) != 44:
        raise SystemExit(f"partition 불일치: {sizes}")

    hf = collections.defaultdict(list)
    for r in jl(ROOT / "training/generated/thinking_traces/p0_v006_hf/traces.jsonl"):
        hf[r["item_id"]].append(r)
    m2raw = collections.defaultdict(list)
    for r in jl(ROOT / "training/generated/p0_sft_003_recovery/m2_raw/traces.jsonl"):
        m2raw[r["item_id"]].append(r)
    m2rev = json.loads((ROOT / "sft_dpo_inventory/p0_sft_003_recovery/m2_review.json").read_text(encoding="utf-8"))["items"]
    m3rev = json.loads((ROOT / "sft_dpo_inventory/p0_sft_003_recovery/m3_recovery.json").read_text(encoding="utf-8"))["items"]

    def failure_reason(group, x):
        if group == "M1_P3":
            return "8B 9표본 모두 정답 아님(M1). 27B 미시도(P3)"
        if group == "M2_FAILED":
            v = m2rev.get(x["item_id"]) or {}
            return f"8B M2 회수 실패: {v.get('reason')}"
        return "M3 기존 trace 사람 검토 거부: `시군구`를 place concept로 냄(p0_sft_003_recovery REPORT)" \
            if x["item_id"] == "b006-11" else f"M3 실패: {m3rev.get(x['item_id'])}"

    label = {"M1_P3": "A1", "M2_FAILED": "A2", "M3_FAILED": "A3"}
    items = []
    for group in ("M1_P3", "M2_FAILED", "M3_FAILED"):
        for x in parts[group]:
            f = x["semantic_features"]
            rs, ms = hf[x["item_id"]], m2raw[x["item_id"]]
            items.append({
                "item_index": len(items), "item_id": x["item_id"], "question": v006[x["item_id"]]["messages"][1]["content"],
                "track": "A", "group": label[group], "missing_class": group, "old_priority": x["priority"], "m_class": x["m_class"],
                "source": x["source"], "gap": {"augment_dt_event": "A", "augment_od_vs_dt": "B"}.get(x["source"]),
                "semantic_family": x["near_family"], "measure": f.get("measure"), "dimension": f.get("dimension"),
                "dimension_target": f.get("dimension_target"), "od_role": f.get("od_roles"), "od_ne_dt": bool(f.get("od_ne_dt")),
                "bucket": f.get("bucket"), "order": f.get("order"),
                "previous_8b_attempts": {"p0_v006_hf": len(rs),
                                         "p0_v006_hf_exact": sum(r["judge"]["category"] == "EXACT_OR_SEMANTIC_MATCH" for r in rs),
                                         "m2_sampling": len(ms),
                                         "m2_sampling_exact": sum(r["judge"]["category"] == "EXACT_OR_SEMANTIC_MATCH" for r in ms)},
                "previous_27b_attempts": 0, "previous_failure_reason": failure_reason(group, x),
                "planned_calls": {"greedy": 1, "sampling": 4}})
    if len(items) != 40 or any(i["item_id"] in t27_target for i in items):
        raise SystemExit("Track A 대상 불일치")
    order_sha = hashlib.sha256("\n".join(i["item_id"] for i in items).encode()).hexdigest()
    summary = {"track_a_targets": len(items), "by_group": dict(collections.Counter(i["group"] for i in items)),
               "by_source": dict(collections.Counter(i["source"] for i in items)),
               "dimension_target": dict(collections.Counter(str(i["dimension_target"]) for i in items)),
               "od_ne_dt": sum(i["od_ne_dt"] for i in items), "planned_calls_max": 5 * len(items),
               "item_order_sha256": order_sha,
               "excluded_track_b": [x["item_id"] for x in parts["T27_FAILED"]],
               "rule": "missing 44 중 27B P1/P2 batch 대상이 아닌 40(M1 P3 + M2 실패 + M3 실패). 순서 A1→A2→A3, 그룹 안은 prep manifest 순서"}
    partition = {"covered": len(covered), "by_source": {"r70": len(r70), "m2_recovered": len(m2_ok), "m3_recovered": len(m3_ok),
                                                       "t27_p12_approved": len(t27_ok)},
                 "missing": len(missing), "partition": sizes, "sum_check": sum(sizes.values()) == len(missing) == 44,
                 "duplicates": 0, "ids": {k: [x["item_id"] for x in v] for k, v in parts.items()}}
    (HERE / "partition.json").write_text(json.dumps(partition, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    path = HERE / "target_manifest.json"
    path.write_text(json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    (HERE / "target_manifest.sha256").write_text(f"{sha}  target_manifest.json\n{order_sha}  item_order\n", encoding="utf-8")
    print(json.dumps(partition, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("manifest sha256", sha)


if __name__ == "__main__":
    main()
