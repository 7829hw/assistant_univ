# -*- coding: utf-8 -*-
"""결정 119(E4)를 300문항 상태에 적용한다. ``augmentation_300.jsonl``(holdout 고정 기록이 sha256을 참조)은 고치지 않고 ``status_e4.json``을 낸다.

    python3 sft_dpo_inventory/pilot_006_prep/aug300/apply_e4.py

- 134·135(현재 코드가 지원하지 않는 조합) → 제외.
- 새 강한 겹침: 겹친 상대가 평가·보호 셋(selection_v1·v2, valid98, aux_test_v1, 업체 100, thor 보호 원본, batch007 아님)이면 제외.
  학습 데이터(train_v006_t2pc, train_thinking_pilot004_t2pc, pg_*)와만 겹치면 제외하지 않고 canonical 병합 대상으로 표시(train 수에서 뺌).
- holdout은 바꾸지 않는다.
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL = ("selection_v1", "selection_v2", "valid98", "aux_test_v1", "vendor100", "thor")
TRAIN = ("train_v006_t2pc", "train_thinking_pilot004_t2pc", "pg_batch006", "pg_reviewed_reasoning_v001", "pg_reviewed_gold_v006_p0")

items = [json.loads(l) for l in (HERE / "augmentation_300.jsonl").read_text(encoding="utf-8").splitlines()]
props = {p["id"]: p for p in json.loads((HERE / "status_proposals.json").read_text(encoding="utf-8"))["proposals"]}
rows = []
for it in items:
    st, reason, merge = it["status"], "결정 106 상태 그대로", None
    p = props.get(it["id"])
    if p and it["status"] != "holdout":
        if p["current_code"]:
            st, reason = "제외", "결정 119: 현재 코드가 지원하지 않는 조합(주변 장소 + 읍면동 dimension)"
        else:
            targets = {h.split(":")[0] for h in p["new_strong_overlap"]}
            if targets & set(EVAL):
                if it["status"] != "제외":
                    st = "제외"
                reason = f"결정 119: 평가·보호 셋과 강한 겹침({', '.join(sorted(targets & set(EVAL)))})"
            elif targets <= set(TRAIN):
                st, reason, merge = "merge_with_training", "결정 119: 학습 데이터와만 겹침 → canonical 하나로 합침(train 수에서 뺌)", sorted(targets)
            else:
                reason = f"결정 119 분류 밖: {sorted(targets)}(상태 그대로, 보고)"
    rows.append({"id": it["id"], "status_v2": it["status_v2"], "status_d1": it["status"], "status_e4": st, "reason": reason, "merge_targets": merge})
counts = Counter(r["status_e4"] for r in rows)
out = {"decision": "119(BF, E4)", "counts": dict(counts), "changed": [r for r in rows if r["status_e4"] != r["status_d1"] or r["merge_targets"]],
       "holdout_unchanged": sum(r["status_e4"] == "holdout" for r in rows) == 53, "items": rows}
(HERE / "status_e4.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({k: out[k] for k in ("counts", "holdout_unchanged")}, ensure_ascii=False), [(r["id"], r["status_d1"], r["status_e4"]) for r in out["changed"]])
