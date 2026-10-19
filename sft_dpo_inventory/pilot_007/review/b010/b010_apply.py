# -*- coding: utf-8 -*-
"""batch010 결정 2단계(결정 175 P1): 고정한 목록(``b010_accept_list.json``)을 검증하고 기록한다. 모델 호출 없음. ``pilot_006_prep/review/p1/p1_apply.py``와 같은 방식.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/review/b010/b010_apply.py [--check-only]

1. 검증(기록 전): 승인 48은 초안 semantics로 W5 검증 사슬(``validate_semantics``: 정답 호출 포함)을 다시 돌린다.
   수정 2(b010-08·36, 발화에 없는 region "부산"을 비움)는 수정 JSON → semantics, 정답 호출도 같은 수정(``get_place_scope``의 region 인자 제거)으로 사슬을 돌린다.
   실패하면 그 문항만 보류(기록 안 함, 대체 수정안 없음).
2. 기록: ``training.annotations.workflow.decide``. 큐 ``queue/``(검토 시트 초안 그대로), 결정 파일 ``decisions.jsonl``. 검토자 = "사용자(이름 기록 안 함)"(결정 138).
   측정 span 7건은 측정 text가 빈 초안 그대로 승인(결정 175).
3. 승인 corpus v3(``pilot_006_prep/approved/approved_train_v3.jsonl``): v2 + batch010(``b010:b010-NN``). holdout은 v1 그대로. ``manifest_v3.json``. v2 파일은 고치지 않는다.
"""
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
INV = HERE.parents[2]
ROOT = INV.parent
APPROVED = INV / "pilot_006_prep/approved"
QDIR = HERE / "queue"
DEC = HERE / "decisions.jsonl"
sys.path.insert(0, str(ROOT))
REVIEWER = "사용자(이름 기록 안 함)"
REASON = "결정 175(2026-10-19): batch010 결정 파일(batch010_review_decisions_v1.xlsx sha256 23487fcf…) 채택"


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def drop_region(calls):
    out = copy.deepcopy(calls)
    for c in out:
        if c.get("tool") == "get_place_scope":
            c["args"].pop("region", None)
    return out


def main():
    from grounding.canonical import record, semantics_from_full
    from grounding.validation import validate_semantics
    from training.annotations.inventory import digest
    from training.annotations.workflow import decide, decision_history, load_queue
    from training.data.canonicalize import canonical_json
    from training.data.common import sha256
    plan = json.loads((HERE / "b010_accept_list.json").read_text(encoding="utf-8"))
    assert not plan["problems"]
    cands = {c["id"]: c for c in json.loads((INV / "batch010/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    checks, hold = {}, {}
    for r in plan["rows"]:
        c = cands[r["id"]]
        if r["decision"] == "modify":
            sem = semantics_from_full(r["corrected_grounding"])
            regions = [((n.get("value") or {}).get("region")) for n in r["corrected_grounding"]["concepts"] if n.get("concept") == "LOCATION"]
            calls = drop_region(c["gold"]) if all(not x for x in regions) else c["gold"]
            v = validate_semantics(sem, c["question"], calls)
            ok = bool(v["ok"] and v["execution_match"] and v["assess_same"] and v["mock_same"])
            checks[r["id"]] = {"kind": "modify", "ok": ok, "validation": v, "semantics": sem, "execution": calls,
                               "calls_changed": calls != c["gold"]}
        else:
            v = validate_semantics(c["semantics"], c["question"], c["gold"])
            ok = bool(v["ok"] and v["execution_match"])
            checks[r["id"]] = {"kind": "approve", "ok": ok, "validation": v, "semantics": c["semantics"], "execution": c["gold"]}
        if not checks[r["id"]]["ok"]:
            hold[r["id"]] = "검증 실패 — 보류(대체 수정안 없음)"
    (HERE / "b010_checks.json").write_text(json.dumps({"checks": {k: {kk: vv for kk, vv in v.items() if kk not in ("semantics",)} for k, v in checks.items()},
                                                       "hold": hold}, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print("hold", hold, "modify calls changed", {k: v.get("calls_changed") for k, v in checks.items() if v["kind"] == "modify"})
    if "--check-only" in sys.argv:
        return
    if not (QDIR / "manifest.json").exists():
        QDIR.mkdir(parents=True, exist_ok=True)
        lines = []
        for cid in sorted(cands):
            c = cands[cid]
            row = {"candidate_id": cid, "candidate_type": "targeted_gold", "question": c["question"], "proposed_grounding": c["draft_grounding"],
                   "proposed_rejected": None, "provenance": {"file": "sft_dpo_inventory/batch010/candidates_checked.json", "id": cid},
                   "note": "pilot_007 P1: batch010 검토 큐(검토 시트 초안 그대로, 결정 175)"}
            row["candidate_hash"] = digest(row)
            lines.append(canonical_json(row))
        (QDIR / "review_queue.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (QDIR / "manifest.json").write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), "group": "batch010",
                                                        "output_hashes": {"review_queue.jsonl": sha256(QDIR / "review_queue.jsonl")}}, ensure_ascii=False, indent=1) + "\n",
                                            encoding="utf-8")
    rows_q, _ = load_queue(QDIR)
    have = decision_history(DEC, rows_q) if DEC.exists() else {}
    recorded = Counter()
    for r in plan["rows"]:
        if r["id"] in hold:
            continue
        prev = have.get(r["id"])
        if prev is not None and prev["status"] == "accepted" and prev["reason"].startswith(REASON[:10]):
            continue
        note = f"{r['memo'] or ''} 2차 검토 근거: {r['second_review_reason'] or ''}".strip()
        if r["decision"] == "modify":
            decide(QDIR, DEC, r["id"], status="accepted", reviewer=REVIEWER, corrected=r["corrected_grounding"], semantic_checks=True,
                   reason=f"{REASON}: 수정(발화에 없는 region '부산'을 비움; 정답 호출의 region 인자도 제거). 검증 사슬 재실행 통과(b010_checks.json). {note}")
        else:
            extra = " 측정 text를 비운 채 승인(결정 175)." if r["measure_text_empty"] else ""
            decide(QDIR, DEC, r["id"], status="accepted", reviewer=REVIEWER, semantic_checks=True, reason=f"{REASON}: 승인.{extra} {note}")
        recorded[r["decision"] + ("(measure_text_empty)" if r["measure_text_empty"] else "")] += 1
    train = read_jsonl(APPROVED / "approved_train_v2.jsonl")
    stamp = "approved(pilot_007 결정 175)"
    for r in plan["rows"]:
        if r["id"] in hold:
            continue
        c, ch = cands[r["id"]], checks[r["id"]]
        rec = record(f"b010:{r['id']}", c["question"], "batch010_draft", semantics=ch["semantics"], execution=ch["execution"],
                     execution_source="batch010 정답 호출(초안" + (", region 인자 제거" if ch.get("calls_changed") else "") + ")",
                     status=f"{stamp}: {r['decision']}" + (" (측정 text 비움)" if r["measure_text_empty"] else ""),
                     provenance={"file": "sft_dpo_inventory/batch010/candidates_checked.json", "id": r["id"], "gap": c["gap"]})
        rec["validation"] = ch["validation"]
        rec["corpus_group"] = "batch010"
        train.append(rec)
    for rec in train:
        calls = rec.get("execution") or []
        rec["k3_scope_name_family"] = bool(len(calls) == 1 and calls[0].get("tool") == "get_scope_name")
    path = APPROVED / "approved_train_v3.jsonl"
    path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True, default=str) + "\n" for x in train), encoding="utf-8")
    man = {"created_at": datetime.now(timezone.utc).isoformat(), "decisions": "130(G0) + 139–142(K2–K5) + 175(P1)", "reviewer": REVIEWER,
           "train": {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "records": len(train),
                     "by_group": dict(Counter(r["corpus_group"] for r in train)), "k3_scope_name_family": sum(r["k3_scope_name_family"] for r in train)},
           "base": {"file": "approved_train_v2.jsonl", "sha256": hashlib.sha256((APPROVED / "approved_train_v2.jsonl").read_bytes()).hexdigest()},
           "holdout": {"file": "approved_holdout_v1.jsonl", "unchanged": True},
           "added_since_v2": {"batch010": sum(1 for r in plan["rows"] if r["id"] not in hold),
                              "by_gap": dict(Counter(cands[r["id"]]["gap"] for r in plan["rows"] if r["id"] not in hold))},
           "hold(verification failed)": hold, "decisions_recorded_this_run": dict(recorded)}
    (APPROVED / "manifest_v3.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: man[k] for k in ("train", "added_since_v2", "hold(verification failed)", "decisions_recorded_this_run")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
