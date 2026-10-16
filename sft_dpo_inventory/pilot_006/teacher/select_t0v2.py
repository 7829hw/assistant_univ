# -*- coding: utf-8 -*-
"""T0'(결정 131 G1) 대상 선택과 통과 규칙(실행 전에 커밋, 결정적, 모델 출력을 보지 않음).

    python3 select_t0v2.py   # -> t0v2_targets.json, t0v2_rule.json

- (i) 참고: T0와 같은 20문항(``t0_targets.json``의 id). semantics는 승인 corpus(R0)의 trunk 레코드(T0와 같은 gold).
- (ii) 판정: 승인 trunk 131질문에서 T0 20문항을 뺀 나머지에 T0와 같은 선정 규칙(``select_t0.py``)을 그대로 적용한 20문항:
  특징 다섯 가지(dt, OD endpoint, 실차, vicinity, bucket)를 돌아가며 id 순서로 1문항씩(특징마다 최대 3), 나머지는 측정값 subtype별로 돌아가며 채운다.
- 순서: (ii) 20문항을 먼저, 그다음 (i) 20문항(질문 순번이 seed에 들어간다: seed_base 20261116 + 1000 × 순번 + 표본).
- 통과 규칙(``t0v2_rule.json``): (ii) 160건에서 자동 검사 (a) 160/160 **그리고** (b) 136/160 이상. (i)은 참고로만 보고한다.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
recs = sorted((json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v1.jsonl").read_text(encoding="utf-8").splitlines()
               if json.loads(l)["corpus_group"] == "trunk"), key=lambda r: r["id"])
t0_ids = [t["id"] for t in json.loads((HERE / "t0_targets.json").read_text(encoding="utf-8"))]
by_id = {r["id"]: r for r in recs}


def feats(r):
    s = r["semantics"]
    f = s.get("factors") or {}
    roles = {(n.get("attributes") or {}).get("od_role") for n in s["nodes"]} - {None}
    meas = {n.get("subtype") for n in s["nodes"]}
    return {"dt": bool(f.get("dimension_target")), "od": bool(roles), "silcha": "trip_count" in meas or f.get("taxi_status") == "occupied",
            "vicinity": bool(f.get("vicinity")), "bucket": bool(f.get("bucket"))}


pool = [r for r in recs if r["id"] not in set(t0_ids)]
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
out = ([{"id": r["id"], "set": "ii_judge", "question": r["question"], "semantics": r["semantics"], "features": feats(r)} for r in picked]
       + [{"id": i, "set": "i_reference", "question": by_id[i]["question"], "semantics": by_id[i]["semantics"], "features": feats(by_id[i])} for i in t0_ids])
assert len({o["id"] for o in out}) == 40
(HERE / "t0v2_targets.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
rule = {"decision": "131(G1)", "instruction": "grounding/prompts/teacher_neutral_v2.md", "samples_per_question": 8, "seed_base": 20261116,
        "judge_set": "ii_judge(20 questions, 160 traces)", "reference_set": "i_reference(T0 20 questions, report only)",
        "pass_if": {"check_a_pass": "== 160 of 160", "check_b_pass": ">= 136 of 160 (0.85)"},
        "checks": "teacher6v2.check_field_names(thinking, content) / teacher6v2.check_conclusion(content, semantics)",
        "on_fail": "TEACH를 시작하지 않고 보고(지시 재수정은 사용자 결정)", "fixed_before_run": True}
(HERE / "t0v2_rule.json").write_text(json.dumps(rule, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(out), {k: sum(o["features"][k] for o in out if o["set"] == "ii_judge") for k in per})
