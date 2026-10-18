# -*- coding: utf-8 -*-
"""T-v3d 문항 (v)와 규칙(세션 4 A2·결정 164, 실행 전에 커밋, 결정적, 모델 호출 없음).

    python3 select_tv3d.py   # -> tv3d_targets.json, tv3d_rule.json

- (v): 승인 corpus v2의 trunk에서 T0·T0'(i)(ii)·T0''(iii)·T0'''(iv) 80문항을 모두 빼고 ``select_t0v4.py``와 같은 규칙(특징별 3개 → 측정별)으로 20문항.
- 표본 8개, seed_base 20261916. 판정이 아니다(채택 규칙 없음). trace는 학습에 쓰지 않는다.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TEACH = ROOT / "sft_dpo_inventory/pilot_006/teacher"
recs = sorted((json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v2.jsonl").read_text(encoding="utf-8").splitlines()
               if json.loads(l)["corpus_group"] == "trunk"), key=lambda r: r["id"])
used = set()
for f in ("t0_targets.json", "t0v2_targets.json", "t0v3_targets.json", "t0v4_targets.json"):
    used |= {t["id"] for t in json.loads((TEACH / f).read_text(encoding="utf-8"))}


def feats(r):
    s = r["semantics"]
    f = s.get("factors") or {}
    roles = {(n.get("attributes") or {}).get("od_role") for n in s["nodes"]} - {None}
    meas = {n.get("subtype") for n in s["nodes"]}
    return {"dt": bool(f.get("dimension_target")), "od": bool(roles), "silcha": "trip_count" in meas or f.get("taxi_status") == "occupied",
            "vicinity": bool(f.get("vicinity")), "bucket": bool(f.get("bucket"))}


pool = [r for r in recs if r["id"] not in used]
picked, per = [], {k: 0 for k in ("dt", "od", "silcha", "vicinity", "bucket")}
progress = True
while progress and len(picked) < 20:
    progress = False
    for k in per:
        if per[k] >= 3 or len(picked) >= 20:
            continue
        c = next((r for r in pool if feats(r)[k] and r not in picked), None)
        if c:
            picked.append(c)
            per[k] += 1
            progress = True
by_m = {}
for r in pool:
    by_m.setdefault(r["view"]["measure"]["subtype"] if r["view"]["measure"] else "-", []).append(r)
while len(picked) < 20:
    for m in sorted(by_m):
        c = next((r for r in by_m[m] if r not in picked), None)
        if c and len(picked) < 20:
            picked.append(c)
assert len(used) == 80 and not ({r["id"] for r in picked} & used) and len(picked) == 20
out = [{"id": r["id"], "set": "v_smoke", "question": r["question"], "semantics": r["semantics"], "features": feats(r)} for r in picked]
(HERE / "tv3d_targets.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
rule = {"decision": "164 (T-v3d, 세션 4)", "set": "v_smoke(20 questions, new; T0·T0'·T0''·T0''' 80 excluded)", "samples_per_question": 8, "seed_base": 20261916,
        "ollama": {"version": "0.40.6", "model": "qwen3.8:27b", "digest": "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813",
                   "guard_min_rate": "post/o1_speed.json threshold (0.5x median, 33.71)"},
        "trace_pass": "a and b and not c(EXPOSURE_V3D)", "also_reported": "A2 types i-iv rates (itemdata.concl_types)",
        "judgment": None, "use_for_training": False, "fixed_before_run": True}
(HERE / "tv3d_rule.json").write_text(json.dumps(rule, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(out), {k: sum(o["features"][k] for o in out) for k in per})
