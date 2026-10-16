# -*- coding: utf-8 -*-
"""T0''' 문항 (iv)와 L1·L3 규칙, v3a·v3b (iii) 재계산(결정 149–151, 실행 전에 커밋, 결정적, 모델 출력은 이미 있는 (iii) pass 값만 씀).

    python3 select_t0v4.py   # -> t0v4_targets.json, t0v4_rule.json

- (iv): 승인 corpus v2의 trunk(T0·T0'·T0''와 같은 풀)에서 T0·T0'(i)(ii)·T0''(iii) 60문항을 모두 빼고 ``select_t0.py``와 같은 규칙으로 20문항.
- L1: trace 통과 = (a)(b)(c)(v3a는 (a)(b)). 지시 통과 = 160 trace 중 통과 ≥ 144(0.90), v3b 계열은 L2 통과도.
- L3 선택: 1) L2 통과 ∧ v3c (iv) 지시 통과 → v3c. 2) 아니면 L2 통과 ∧ v3b (iii) 지시 통과 → v3b. 3) 아니면 v3a (iii) 지시 통과 → v3a. 4) 없음.
- v3a·v3b (iii) 통과 trace 수는 기존 원문(``teacher_t0v3a|b/traces.jsonl``)의 ``pass``로 다시 센다(새로 재지 않음).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
recs = sorted((json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v2.jsonl").read_text(encoding="utf-8").splitlines()
               if json.loads(l)["corpus_group"] == "trunk"), key=lambda r: r["id"])
used = set()
for f in ("t0_targets.json", "t0v2_targets.json", "t0v3_targets.json"):
    used |= {t["id"] for t in json.loads((HERE / f).read_text(encoding="utf-8"))}


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
assert len(used) == 60 and not ({r["id"] for r in picked} & used) and len(picked) == 20
out = [{"id": r["id"], "set": "iv_judge", "question": r["question"], "semantics": r["semantics"], "features": feats(r)} for r in picked]
(HERE / "t0v4_targets.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
iii = {}
for v in ("v3a", "v3b"):
    rows = [json.loads(l) for l in (ROOT / f"training/generated/pilot_006/teacher_t0{v}/traces.jsonl").read_text(encoding="utf-8").splitlines()]
    n = sum(r["pass"] for r in rows)
    iii[v] = {"traces": len(rows), "trace_pass": n, "trace_pass_ge_144": n >= 144}
l2 = json.loads((HERE / "v3b_read_result.json").read_text(encoding="utf-8"))
rule = {"decision": "149–151(L1–L3)", "set": "iv_judge(20 questions, new; T0·T0'(i)(ii)·T0''(iii) excluded)", "samples_per_question": 8,
        "seed_base": {"v3c": 20261716},
        "trace_pass": {"v3a": "a and b", "v3b": "a and b and not c(EXPOSURE)", "v3c": "a and b and not c(EXPOSURE_V3C)"},
        "instruction_pass": ">= 144 of 160 trace_pass, and L2 pass for v3b/v3c",
        "L2": {"derive": l2["derive"], "repeat": l2["repeat"], "pass": l2["pass"]}, "iii_recount": iii,
        "selection": ["L2 pass and v3c(iv) instruction pass -> v3c", "else L2 pass and v3b(iii) instruction pass -> v3b",
                      "else v3a(iii) instruction pass -> v3a", "else none"],
        "exposure_list_v3c": "teacher6v3.EXPOSURE_V3C", "fixed_before_run": True}
(HERE / "t0v4_rule.json").write_text(json.dumps(rule, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(out), {k: sum(o["features"][k] for o in out) for k in per}, iii)
