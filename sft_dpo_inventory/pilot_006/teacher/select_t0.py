# -*- coding: utf-8 -*-
"""T0 대상 20질문 선택(실행 전에 커밋, 결정적, 모델 출력을 보지 않음).

    hfvenv/bin/python select_t0.py   # -> t0_targets.json

규칙: 승인된 trunk ``reviewed_gold_v006_t2pc``(pilot_004 판 131질문, ``pilot_006_prep/canonical/canonical_records.jsonl``의 t2pc_v006) 중에서
1. 특징 다섯 가지를 차례로 돌아가며 1문항씩 고른다: dt(dimension_target 있음), OD endpoint(장소에 od_role 있음), 실차(trip_count 또는 taxi_status occupied),
   vicinity, bucket. 각 특징 안에서는 id 순서. 이미 고른 문항은 건너뛴다. 특징마다 최대 3문항.
2. 나머지는 측정값 subtype별로 돌아가며(id 순서) 20문항이 될 때까지 채운다.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
recs = sorted((json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/canonical/canonical_records.jsonl").read_text(encoding="utf-8").splitlines()
               if json.loads(l)["source"] == "t2pc_v006"), key=lambda r: r["id"])


def feats(r):
    s = r["semantics"]
    f = s.get("factors") or {}
    roles = {(n.get("attributes") or {}).get("od_role") for n in s["nodes"]} - {None}
    meas = {n.get("subtype") for n in s["nodes"]}
    return {"dt": bool(f.get("dimension_target")), "od": bool(roles), "silcha": "trip_count" in meas or f.get("taxi_status") == "occupied",
            "vicinity": bool(f.get("vicinity")), "bucket": bool(f.get("bucket"))}


picked, per = [], {k: 0 for k in ("dt", "od", "silcha", "vicinity", "bucket")}
progress = True
while progress and len(picked) < 20:
    progress = False
    for k in per:
        if per[k] >= 3 or len(picked) >= 20:
            continue
        c = next((r for r in recs if feats(r)[k] and r not in picked), None)
        if c:
            picked.append(c)
            per[k] += 1
            progress = True
by_m = {}
for r in recs:
    m = next((n["subtype"] for n in r["semantics"]["nodes"] if (n.get("role_override") or "") != "EXTENT"), "-")
    by_m.setdefault(r["view"]["measure"]["subtype"] if r["view"]["measure"] else m, []).append(r)
while len(picked) < 20:
    for m in sorted(by_m):
        c = next((r for r in by_m[m] if r not in picked), None)
        if c and len(picked) < 20:
            picked.append(c)
out = [{"id": r["id"], "question": r["question"], "semantics": r["semantics"], "features": feats(r)} for r in picked]
(HERE / "t0_targets.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(out), {k: sum(o["features"][k] for o in out) for k in per})
