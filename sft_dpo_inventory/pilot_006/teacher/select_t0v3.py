# -*- coding: utf-8 -*-
"""T0''(결정 144 K7) 문항 (iii)과 통과·선택 규칙(실행 전에 커밋, 결정적, 모델 출력을 보지 않음).

    python3 select_t0v3.py   # -> t0v3_targets.json, t0v3_rule.json

- (iii): 승인 trunk(T0·T0'와 같은 풀, 승인 corpus v2의 trunk 131)에서 T0 20(= T0'(i))·T0'(ii) 20, 모두 40을 빼고, ``select_t0.py``와 같은 규칙
  (특징 다섯 가지 돌아가며 id 순서로 1문항씩, 특징마다 최대 3, 나머지는 측정 subtype별로)으로 20문항. v3a·v3b 모두 같은 20문항 × 8.
- 통과(결정 144): v3a (a) ≥ 157/160 그리고 (b) ≥ 136/160. v3b (a) ≥ 157/160, (b) ≥ 152/160, (c) 노출 ≤ 3/160.
- 선택: v3b 통과 → v3b. v3b 불통과·v3a 통과 → v3a. 둘 다 불통과 → TEACH 없음.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
recs = sorted((json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v2.jsonl").read_text(encoding="utf-8").splitlines()
               if json.loads(l)["corpus_group"] == "trunk"), key=lambda r: r["id"])
used = {t["id"] for t in json.loads((HERE / "t0_targets.json").read_text(encoding="utf-8"))} | \
       {t["id"] for t in json.loads((HERE / "t0v2_targets.json").read_text(encoding="utf-8"))}


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
assert len(used) == 40 and not ({r["id"] for r in picked} & used)
out = [{"id": r["id"], "set": "iii_judge", "question": r["question"], "semantics": r["semantics"], "features": feats(r)} for r in picked]
(HERE / "t0v3_targets.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
rule = {"decision": "144(K7)", "set": "iii_judge(20 questions, new; T0·T0'(i)(ii) excluded)", "samples_per_question": 8,
        "seed_base": {"v3b": 20261316, "v3a": 20261416},
        "pass_if": {"v3a": {"check_a_pass": ">= 157 of 160", "check_b_pass": ">= 136 of 160"},
                    "v3b": {"check_a_pass": ">= 157 of 160", "check_b_pass": ">= 152 of 160", "check_c_exposed": "<= 3 of 160"}},
        "note_a_threshold": "(a) 기준을 160에서 157로 낮춤(결정 144): 실패 trace는 학습 전에 걸러진다",
        "selection": ["v3b pass -> TEACH with v3b", "v3b fail and v3a pass -> TEACH with v3a", "both fail -> no TEACH, report"],
        "training_traces": {"v3a": "a and b", "v3b": "a and b and not c", "max_per_question": 4},
        "exposure_phrases": "teacher6v3.EXPOSURE", "fixed_before_run": True}
(HERE / "t0v3_rule.json").write_text(json.dumps(rule, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(out), {k: sum(o["features"][k] for o in out) for k in per})
