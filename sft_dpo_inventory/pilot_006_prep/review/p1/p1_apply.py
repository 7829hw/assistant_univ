# -*- coding: utf-8 -*-
"""P1 2단계(결정 139–142): 고정한 목록(``p1_accept_list.json``, 커밋 d455edf)을 검증하고 기록한다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/review/p1/p1_apply.py [--check-only]

1. 검증(기록 전): batch009 수정 4건은 수정 JSON → semantics → W5 검증 사슬(정답 호출 포함), mock 호출이 초안과 같음. 승인 38·w1 9도 사슬을 다시 돌린다.
   aug300 복원 5·348은 초안 semantics(원래 문구)로 사슬을 다시 돌린다. 실패하면 그 문항만 보류(기록 안 함, 대체 수정안 없음).
2. holdout 고정값(``69d3af19…``, ``23ee1bc8…``, gold 파일) 확인. 다르면 exit 3.
3. 기록: ``training.annotations.workflow.decide``. batch009(52 = 43 + w1 9)는 새 큐 ``../r0/queues/batch009``(초안 그대로), 결정 파일 ``../r0/decisions/batch009.jsonl``.
   aug300 5건은 결정 130의 rejected를 ``supersedes``로 잇는 accepted, 348은 첫 결정(accepted, 원래 문구). 검토자 = "사용자(이름 기록 안 함)"(결정 138).
4. 승인 corpus v2(``../../approved/approved_train_v2.jsonl``): v1 + aug300 6(복원 5 + 348) + batch009 51(승인 38 + 수정 4 + w1 9).
   w1 9건과 scope 이름 조회(``get_scope_name`` 단독) 레코드에는 ``k3_scope_name_family: true``(결정 140, gate 보고에서 따로 표시).
   holdout은 v1 그대로. ``manifest_v2.json``.
"""
import copy
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
INV = HERE.parents[2]
ROOT = INV.parent
PREP = INV / "pilot_006_prep"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PREP / "review/r0"))
REVIEWER = "사용자(이름 기록 안 함)"
REASON = "결정 139–142(2026-10-16): 2차 검토 권고 채택(batch009_review_v2_2nd.xlsx sha256 86449a69…)"
OUT = PREP / "approved"
QDIR = PREP / "review/r0/queues/batch009"


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    import r0_apply as R0
    from grounding.canonical import record, semantics_from_full
    from grounding.validation import validate_semantics
    from training.annotations.inventory import digest
    from training.annotations.workflow import decide, decision_history, load_queue
    from training.data.canonicalize import canonical_json
    from training.data.common import sha256
    plan = json.loads((HERE / "p1_accept_list.json").read_text(encoding="utf-8"))
    assert not plan["problems"]
    kept = {c["id"]: c for c in json.loads((INV / "batch009/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    excl = {c["id"]: c for c in json.loads((INV / "batch009/excluded.json").read_text(encoding="utf-8"))}
    b9 = {**{k: v for k, v in excl.items() if any(r["id"] == k and r["group"] == "batch009_w1" for r in plan["rows"])}, **kept}
    aug_sem = {r["id"]: r for r in read_jsonl(PREP / "aug300_review/semantics_draft.jsonl")}
    aug_items = {r["id"]: r for r in read_jsonl(PREP / "aug300/augmentation_300.jsonl")}
    # ---- 1. 검증
    checks, hold = {}, {}
    for r in plan["rows"]:
        if r["decision"] == "exclude":
            continue
        rid = r["id"]
        if r["group"].startswith("batch009"):
            c = b9[rid]
            base = validate_semantics(c["semantics"], c["question"], c["gold"])
            if r["decision"] == "modify":
                sem = semantics_from_full(json.loads(r["corrected_grounding"]))
                v = validate_semantics(sem, c["question"], c["gold"])
                same = v["mock_full"]["calls"] == base["mock_full"]["calls"]
                ok = bool(v["ok"] and v["execution_match"] and v["assess_same"] and v["mock_same"] and same)
                checks[rid] = {"kind": "batch009_modify", "ok": ok, "mock_calls_same_as_draft": same, "validation": v, "semantics": sem}
            else:
                ok = bool(base["ok"] and base["execution_match"])
                checks[rid] = {"kind": r["group"], "ok": ok, "validation": base, "semantics": c["semantics"]}
        else:
            d, it = aug_sem[rid], aug_items[rid]
            v = validate_semantics(d["semantics"], it["question"], it["gold"])
            ok = bool(v["ok"] and v["execution_match"])
            checks[rid] = {"kind": "aug300_restore", "ok": ok, "validation": v, "question": it["question"]}
        if not checks[rid]["ok"]:
            hold[rid] = "검증 실패 — 보류(대체 수정안 없음)"
    # ---- 2. holdout
    holdout = json.loads((PREP / "aug300/holdout_v1.json").read_text(encoding="utf-8"))
    ids = sorted(i["id"] for i in holdout["list"])
    hc = {"sorted_ids_sha256": hashlib.sha256("\n".join(ids).encode()).hexdigest(),
          "questions_sha256": hashlib.sha256("\n".join(aug_items[i]["question"] for i in ids).encode()).hexdigest(),
          "gold_file_sha256": hashlib.sha256((PREP / "aug300" / holdout["gold_file"]).read_bytes()).hexdigest()}
    hc["same"] = (hc["sorted_ids_sha256"] == R0.HOLDOUT["sorted_ids_sha256"] and hc["questions_sha256"] == R0.HOLDOUT["questions_sha256"]
                  and hc["gold_file_sha256"] == holdout["gold_file_sha256"])
    hc["touched_holdout"] = sorted(r["id"] for r in plan["rows"] if r["id"] in ids)
    hc["same"] = hc["same"] and not hc["touched_holdout"]
    (HERE / "p1_checks.json").write_text(json.dumps({"checks": {k: {kk: vv for kk, vv in v.items() if kk != "semantics"} for k, v in checks.items()},
                                                     "hold": hold, "holdout": hc}, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print("holdout", hc["same"], "fail", hold)
    if not hc["same"]:
        raise SystemExit(3)
    if "--check-only" in sys.argv:
        return
    # ---- 3. 기록
    if not (QDIR / "manifest.json").exists():
        QDIR.mkdir(parents=True, exist_ok=True)
        lines = []
        for cid in sorted(b9):
            c = b9[cid]
            row = {"candidate_id": cid, "candidate_type": "targeted_gold", "question": c["question"], "proposed_grounding": c["draft_grounding"],
                   "proposed_rejected": None, "provenance": {"file": "sft_dpo_inventory/batch009/candidates_checked.json or excluded.json(w1)", "id": cid},
                   "note": "pilot_006 P1: batch009 검토 큐(검토 시트 초안 그대로, 결정 139·140)"}
            row["candidate_hash"] = digest(row)
            lines.append(canonical_json(row))
        (QDIR / "review_queue.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (QDIR / "manifest.json").write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), "group": "batch009",
                                                        "output_hashes": {"review_queue.jsonl": sha256(QDIR / "review_queue.jsonl")}}, ensure_ascii=False, indent=1) + "\n",
                                            encoding="utf-8")
    recorded = Counter()
    for group, qdir, dec_path in (("batch009", QDIR, HERE.parent / "r0/decisions/batch009.jsonl"),
                                  ("aug300", PREP / "aug300_review/review", HERE.parent / "r0/decisions/aug300.jsonl")):
        rows_q, _ = load_queue(qdir)
        have = decision_history(dec_path, rows_q) if dec_path.exists() else {}
        for r in plan["rows"]:
            if (r["group"] == "aug300") != (group == "aug300") or r["id"] in hold:
                continue
            prev = have.get(r["id"])
            if prev is not None and prev["status"] == ("rejected" if r["decision"] == "exclude" else "accepted") and prev["reason"].startswith(REASON[:10]):
                continue
            src = r["decision_source"]
            if r["decision"] == "exclude":
                decide(qdir, dec_path, r["id"], status="rejected", reviewer=REVIEWER, reason=f"{REASON}: 제외. {r['reason']}")
            elif r["decision"] == "modify":
                decide(qdir, dec_path, r["id"], status="accepted", reviewer=REVIEWER, corrected=json.loads(r["corrected_grounding"]), semantic_checks=True,
                       reason=f"{REASON}: 수정(지역 안 OD = 장소 하나 + od_role both). 검증 사슬 재실행 통과(p1_checks.json). {r['reason']}")
            else:
                decide(qdir, dec_path, r["id"], status="accepted", reviewer=REVIEWER, semantic_checks=True, reason=f"{REASON}: 승인({src}). {r['reason']}")
            recorded[f"{r['group']}:{r['decision']}"] += 1
    # ---- 4. corpus v2
    train = read_jsonl(OUT / "approved_train_v1.jsonl")
    stamp = "approved(pilot_006 결정 139–142)"
    for r in plan["rows"]:
        if r["id"] in hold or r["decision"] == "exclude":
            continue
        rid = r["id"]
        if r["group"] == "aug300":
            rec = copy.deepcopy(aug_sem[rid])
            rec["status"] = f"{stamp}: {r['decision_source']}"
            rec["corpus_group"] = "aug300"
            rec["validation"] = checks[rid]["validation"]
        else:
            c = b9[rid]
            rec = record(f"b009:{rid}", c["question"], "batch009_draft", semantics=checks[rid]["semantics"], execution=c["gold"],
                         execution_source="batch009 정답 호출(초안)", status=f"{stamp}: {r['decision']}({r['decision_source']})",
                         provenance={"file": "sft_dpo_inventory/batch009/candidates_checked.json" if rid in kept else "sft_dpo_inventory/batch009/excluded.json",
                                     "id": rid, "gap": c["gap"]})
            rec["validation"] = checks[rid]["validation"]
            rec["corpus_group"] = "batch009"
        train.append(rec)
    for rec in train:
        calls = rec.get("execution") or []
        rec["k3_scope_name_family"] = bool(len(calls) == 1 and calls[0].get("tool") == "get_scope_name")
    path = OUT / "approved_train_v2.jsonl"
    path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True, default=str) + "\n" for x in train), encoding="utf-8")
    man = {"created_at": datetime.now(timezone.utc).isoformat(), "decisions": "130(G0) + 139–142(K2–K5)", "reviewer": REVIEWER,
           "train": {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "records": len(train),
                     "by_group": dict(Counter(r["corpus_group"] for r in train)), "k3_scope_name_family": sum(r["k3_scope_name_family"] for r in train)},
           "holdout": {"file": "approved_holdout_v1.jsonl", "unchanged": True},
           "added_since_v1": {"aug300": sorted(r["id"] for r in plan["rows"] if r["group"] == "aug300" and r["id"] not in hold),
                              "batch009": sum(1 for r in plan["rows"] if r["group"].startswith("batch009") and r["decision"] != "exclude" and r["id"] not in hold)},
           "excluded": [r["id"] for r in plan["rows"] if r["decision"] == "exclude"], "hold(verification failed)": hold,
           "aug300_348": "원래 문구로 승인(결정 142). R0 manifest의 보류 표시는 이 판에서 해제. 원래 문구 출력(J1·J3·J6)은 유효(invalidated_outputs.json에 없음)",
           "decisions_recorded_this_run": dict(recorded)}
    (OUT / "manifest_v2.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: man[k] for k in ("train", "added_since_v1", "hold(verification failed)", "decisions_recorded_this_run")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
