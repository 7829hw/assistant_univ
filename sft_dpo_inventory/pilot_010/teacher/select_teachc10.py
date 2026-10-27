# -*- coding: utf-8 -*-
"""TEACH-C 대상(결정 242 AA2, 실행 전 커밋, 결정적, 모델 호출 없음). ``pilot_009/teacher/select_teachr9.py``와 같은 방식.

    python3 select_teachc10.py   # -> teachc_targets.json

순서(문항 id 순, 묶음 차례대로):
1. ``batch011_r2``: 승인 corpus v5의 batch011 r2 승인분 40(문장·semantics = corpus v5).
2. ``batch012_r2``: 승인 corpus v5의 batch012 r2 승인분 40.
3. ``batch013_c1``·``batch013_c2``: batch013 초안 전체(``batch013/candidates_checked.json``의 남은 77 — 검사에서 빠진 3은 정답 grounding이 이미 학습·승인 데이터와 같아 넣지 않음;
   semantics = 초안 정답 호출에서 역산한 canonical, 승인 전 수집 — 거르기·사용은 승인 뒤).
4. ``approved_billing``: 승인 corpus v5 안의 요금 지표(측정 revenue·active_taxi_count·active_taxi_ratio·operating_days) 답하는 문항 중 batch011·012 r2가 아니고
   teacher 통과 trace가 없는 것. "통과 trace" = 이전 teacher 수집 원문(``pilot_006/teacher_v3``·``teacher_tv3d``의 ``pass``, ``pilot_009/teacher_teachr``의 ``pass``)에서
   통과로 기록된 trace, 또는 RC5·RC6·RC7 Full 학습 파일에 teacher 레코드가 있는 질문.
gap(가까운 거부 범주): r2는 provenance gap, batch013은 초안 gap, approved_billing은 없음(지시에 범주 줄을 붙이지 않음).
표본 8, seed_base 20272027, 지시 ``teacher_contrast_v1``.
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
V5 = ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v5.jsonl"
B13 = ROOT / "sft_dpo_inventory/batch013/candidates_checked.json"
BILLING = {"revenue", "active_taxi_count", "active_taxi_ratio", "operating_days"}
POOLS = [ROOT / "training/generated/pilot_006/teacher_v3/traces.jsonl", ROOT / "training/generated/pilot_006/teacher_tv3d/traces.jsonl",
         ROOT / "training/generated/pilot_009/teacher_teachr/traces.jsonl"]
TRAIN = [ROOT / "sft_dpo_inventory/pilot_007/build/RC5/full/sft_train.jsonl", ROOT / "sft_dpo_inventory/pilot_008/build/RC6/full/sft_train.jsonl",
         ROOT / "sft_dpo_inventory/pilot_009/build/RC7/full/sft_train.jsonl"]


def lines(p):
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


v5 = {r["id"]: r for r in lines(V5)}
with_pass = {r["id"] for p in POOLS for r in lines(p) if r.get("pass")}
with_rec = {r["metadata"]["source_record_id"] for p in TRAIN for r in lines(p) if r["metadata"].get("source") == "teacher"}
has_teacher = with_pass | with_rec
out = []
for grp, pre in (("batch011_r2", "b011:"), ("batch012_r2", "b012:")):
    out += [{"id": i, "set": grp, "variant": "contrast_v1", "gap": r["provenance"]["gap"], "question": r["question"], "semantics": r["semantics"]}
            for i, r in sorted(v5.items()) if i.startswith(pre) and r["provenance"].get("kind") == "r2_contrast"]
for c in sorted(json.loads(B13.read_text(encoding="utf-8"))["candidates"], key=lambda c: c["id"]):
    out.append({"id": f"b013:{c['id']}", "set": f"batch013_{c['group']}", "variant": "contrast_v1", "gap": c["gap"], "question": c["question"], "semantics": c["semantics"]})
bill = [r for i, r in sorted(v5.items()) if ((r.get("view") or {}).get("measure") or {}).get("subtype") in BILLING and r["provenance"].get("kind") != "r2_contrast"
        and not (r["semantics"] or {}).get("unsupported")]
out += [{"id": r["id"], "set": "approved_billing", "variant": "contrast_v1", "gap": None, "question": r["question"], "semantics": r["semantics"]}
        for r in bill if r["id"] not in has_teacher]
assert len({o["id"] for o in out}) == len(out)
(HERE / "teachc_targets.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(out), dict(Counter(o["set"] for o in out)), {"approved_billing_all": len(bill), "with_teacher": sum(r["id"] in has_teacher for r in bill)})
