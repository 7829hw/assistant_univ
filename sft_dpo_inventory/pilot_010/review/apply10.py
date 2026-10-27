# -*- coding: utf-8 -*-
"""pilot_010 선택 단계 P0(결정 247): 고정한 받아들일 목록(``b013_accept_list.json``)을 검증하고 기록한다. 모델 호출 없음.
``pilot_009/review/apply9.py``와 같은 방식(그 파일은 고치지 않음).

    hfvenv/bin/python sft_dpo_inventory/pilot_010/review/apply10.py [--check-only]

1. 다시 검사(기록 전): 77건 모두 r2(답하는 근접 대조, 초안 그대로) — 검증 사슬(``validate_semantics``: ok·assess_same·mock_same·execution_match·full_answered) 재실행. 걸리면 그 문항만 제외.
2. 기록(``--check-only`` 아니면):
   - ``training.annotations.workflow.decide``(큐 ``b013/queue``, ``b013/decisions.jsonl``, 검토자 "사용자(이름 기록 안 함), 2차 검토 권고 채택").
   - 승인 corpus v6(``pilot_006_prep/approved/approved_train_v6.jsonl``) = v5 + batch013 승인분(``b013:b013-NNN``). v5는 고치지 않는다.
"""
import collections
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
P10 = HERE.parent
INV = P10.parent
ROOT = INV.parent
APPROVED = INV / "pilot_006_prep/approved"
sys.path.insert(0, str(ROOT))
REVIEWER = "사용자(이름 기록 안 함), 2차 검토 권고 채택"
REASON13 = "결정 247(2026-10-27): batch013 2차 검토 권고 채택"


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    from grounding.canonical import record
    from grounding.validation import validate_semantics
    from training.annotations.inventory import digest
    from training.annotations.workflow import decide, decision_history, load_queue
    from training.data.canonicalize import canonical_json
    from training.data.common import sha256
    pb = json.loads((HERE / "b013_accept_list.json").read_text(encoding="utf-8"))
    cb = {c["id"]: c for c in json.loads((INV / "batch013/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    checks, excluded = {}, {}
    for r in pb["rows"]:
        c = cb[r["id"]]
        assert r["decision"] == "approve" and c["kind"] == "r2_contrast", r
        v = validate_semantics(c["semantics"], c["question"], c["gold"])
        checks[r["id"]] = {"kind": "approve(r2)", "ok": bool(v["ok"] and v["execution_match"] and v["full_answered"]),
                           "validation": {k: v[k] for k in ("ok", "assess_same", "mock_same", "execution_match", "full_answered")}}
        if not checks[r["id"]]["ok"]:
            excluded[r["id"]] = ["validation_failed"]
    (HERE / "apply10_checks.json").write_text(json.dumps({"batch013": {"checks": checks, "excluded": excluded}}, ensure_ascii=False, indent=1, default=str) + "\n",
                                              encoding="utf-8")
    print(json.dumps({"b013_ok": sum(v["ok"] for v in checks.values()), "b013_excluded": excluded}, ensure_ascii=False))
    if "--check-only" in sys.argv:
        return
    qdir, dec = HERE / "b013/queue", HERE / "b013/decisions.jsonl"
    if not (qdir / "manifest.json").exists():
        qdir.mkdir(parents=True, exist_ok=True)
        lines = []
        for cid in sorted(cb):
            c = cb[cid]
            row = {"candidate_id": cid, "candidate_type": "targeted_gold", "question": c["question"], "proposed_grounding": c["draft_grounding"],
                   "proposed_rejected": None, "provenance": {"file": "sft_dpo_inventory/batch013/candidates_checked.json", "id": cid},
                   "note": "pilot_010 S단계 P0: batch013 검토 큐(검토 시트 초안 그대로, 결정 247)"}
            row["candidate_hash"] = digest(row)
            lines.append(canonical_json(row))
        (qdir / "review_queue.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (qdir / "manifest.json").write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), "group": "batch013",
                                                        "output_hashes": {"review_queue.jsonl": sha256(qdir / "review_queue.jsonl")}}, ensure_ascii=False, indent=1) + "\n",
                                            encoding="utf-8")
    rows_q, _ = load_queue(qdir)
    have = decision_history(dec, rows_q) if dec.exists() else {}
    recorded = collections.Counter()
    for r in pb["rows"]:
        if r["id"] in excluded:
            continue
        prev = have.get(r["id"])
        if prev is not None and prev["status"] == "accepted" and prev["reason"].startswith(REASON13[:10]):
            continue
        decide(qdir, dec, r["id"], status="accepted", reviewer=REVIEWER, semantic_checks=True, reason=f"{REASON13}: 승인(초안 그대로).")
        recorded[r["decision"]] += 1
    train = read_jsonl(APPROVED / "approved_train_v5.jsonl")
    n5 = len(train)
    for r in pb["rows"]:
        if r["id"] in excluded:
            continue
        c = cb[r["id"]]
        rec = record(f"b013:{r['id']}", c["question"], "batch013_draft", semantics=c["semantics"], execution=c["gold"],
                     execution_source="batch013 정답 호출(초안)", status=f"approved(pilot_010 결정 247): {r['decision']}",
                     provenance={"file": "sft_dpo_inventory/batch013/candidates_checked.json", "id": r["id"], "gap": c["gap"], "kind": c["kind"],
                                 "group": c["group"], "subtype": c["subtype"]})
        rec["validation"] = checks[r["id"]]["validation"]
        rec["corpus_group"] = "batch013"
        rec["k3_scope_name_family"] = False
        train.append(rec)
    out_p = APPROVED / "approved_train_v6.jsonl"
    if out_p.exists():
        raise SystemExit("approved_train_v6.jsonl exists; not overwriting")
    out_p.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in train), encoding="utf-8")
    man = {"version": "v6", "created_at": datetime.now(timezone.utc).isoformat(), "decision": "247 (AB1)", "base": "approved_train_v5.jsonl",
           "base_sha256": sha256(APPROVED / "approved_train_v5.jsonl"), "base_records": n5, "added_batch013": len(train) - n5,
           "added_by_group": dict(collections.Counter(cb[r["id"]]["group"] for r in pb["rows"] if r["id"] not in excluded)),
           "added_by_subtype": dict(collections.Counter(cb[r["id"]]["subtype"] for r in pb["rows"] if r["id"] not in excluded)),
           "excluded": excluded, "records": len(train), "sha256": sha256(out_p), "decisions_recorded_this_run": dict(recorded),
           "decisions_file": "sft_dpo_inventory/pilot_010/review/b013/decisions.jsonl"}
    (APPROVED / "manifest_v6.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: man[k] for k in ("records", "added_batch013", "added_by_group", "sha256")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
