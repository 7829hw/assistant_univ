# -*- coding: utf-8 -*-
"""pilot_009 S0(결정 233·234): 고정한 받아들일 목록(``b012_accept_list.json``·``rdev2_accept_list.json``)을 검증하고 기록한다. 모델 호출 없음.
``pilot_008/review/apply8.py``와 같은 방식(그 파일은 고치지 않음).

    hfvenv/bin/python sft_dpo_inventory/pilot_009/review/apply9.py [--check-only]

1. 다시 검사(기록 전):
   - 수정 3건(b012-001·021·039, r1 거부): ``batch012/build_candidates12.py``의 대상(결정 120 규칙 대상, RC5·RC6 실제 학습 레코드, batch011 초안, refusal_dev v1 승인본·초안,
     refusal_dev 확장 초안, 승인 corpus v4) + refusal_dev 확장 승인본 문장 + 나머지 batch012(승인 문장)와 정규화 질문 일치·문자 3-gram Jaccard ≥ 0.5,
     거부 target T2PC ``unsupported``. 걸리면 그 문항만 제외.
   - 승인 문항(초안 그대로): r1은 T2PC ``unsupported`` 재확인, r2는 검증 사슬(``validate_semantics``) 재실행.
   - refusal_dev 확장(승인 60, 초안 그대로): T2PC ``unsupported`` 재확인.
2. 기록(``--check-only`` 아니면):
   - batch012: ``training.annotations.workflow.decide``(큐 ``b012/queue``, ``b012/decisions.jsonl``, 검토자 "사용자(이름 기록 안 함), 2차 검토 권고 채택").
   - 승인 corpus v5(``pilot_006_prep/approved/approved_train_v5.jsonl``) = v4 + batch012 승인분(``b012:b012-NNN``; r1은 semantics ``unsupported``, 정답 호출 없음). v4는 고치지 않는다.
   - refusal_dev v2 승인본: ``pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml``·``rdev_v2_items_meta.json`` = v1 승인본 60(거부 30·대조 30) + 확장 60(거부).
     개발 셋(학습·최종 판정에 쓰지 않음).
"""
import collections
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
P9 = HERE.parent
INV = P9.parent
ROOT = INV.parent
APPROVED = INV / "pilot_006_prep/approved"
for p in (ROOT, INV / "batch012", INV / "batch004", INV / "pilot_006_prep/aug300", INV / "pilot_006_prep/aug300_review", INV / "pilot_006/protected_final",
          INV / "pilot_008/review"):
    sys.path.insert(0, str(p))
REVIEWER = "사용자(이름 기록 안 함), 2차 검토 권고 채택"
REASON12 = "결정 233(2026-10-26): batch012 2차 검토 권고 채택"


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    sys.argv = [a for a in sys.argv if a != "--set"]
    import apply8 as A8  # index_targets·overlap 재사용(고치지 않음)
    import build_candidates12 as BC
    from grounding.canonical import record, semantics_from_full
    from grounding.validation import validate_semantics
    from training.annotations.inventory import digest
    from training.annotations.workflow import decide, decision_history, load_queue
    from training.data.canonicalize import canonical_json
    from training.data.common import sha256
    from training.data.validation import assess_t2pc
    pb = json.loads((HERE / "b012_accept_list.json").read_text(encoding="utf-8"))
    pr = json.loads((HERE / "rdev2_accept_list.json").read_text(encoding="utf-8"))
    cb = {c["id"]: c for c in json.loads((INV / "batch012/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    cr = {c["id"]: c for c in json.loads((P9 / "refusal_dev2/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    qb = {r["id"]: r.get("corrected_question") or cb[r["id"]]["question"] for r in pb["rows"]}
    qr = {r["id"]: cr[r["id"]]["question"] for r in pr["rows"]}
    base_tg = BC.targets()
    checks, excluded = {}, {}
    for r in pb["rows"]:
        c = cb[r["id"]]
        if r["decision"] == "modify":
            tg = dict(base_tg)
            tg["refusal_dev2_approved"] = [(i, qr[i], None) for i in qr]
            tg["batch012_others"] = [(i, qb[i], None) for i in qb if i != r["id"]]
            why, info = A8.overlap(qb[r["id"]], None, A8.index_targets(tg), refusal=True)
            t2 = assess_t2pc({"unsupported": True}, qb[r["id"]])
            why += [] if t2.get("outcome") == "unsupported" else [f"refusal_target_not_unsupported:{t2.get('outcome')}"]
            jmax = max(v["jaccard_max"] for v in info.values())
            checks[r["id"]] = {"kind": "modify(r1)", "ok": not why, "excluded_reasons": why, "jaccard_max_any": jmax,
                               "jaccard_nearest_any": max(info.items(), key=lambda kv: kv[1]["jaccard_max"])[0], "overlap": info, "t2pc_outcome": t2.get("outcome")}
        elif c["kind"] == "r1_refusal":
            t2 = assess_t2pc({"unsupported": True}, c["question"])
            checks[r["id"]] = {"kind": "approve(r1)", "ok": t2.get("outcome") == "unsupported", "t2pc_outcome": t2.get("outcome")}
        else:
            v = validate_semantics(c["semantics"], c["question"], c["gold"])
            checks[r["id"]] = {"kind": "approve(r2)", "ok": bool(v["ok"] and v["execution_match"] and v["full_answered"]),
                               "validation": {k: v[k] for k in ("ok", "assess_same", "mock_same", "execution_match", "full_answered")}}
        if not checks[r["id"]]["ok"]:
            excluded[r["id"]] = checks[r["id"]].get("excluded_reasons") or ["validation_failed"]
    rchecks, rexcluded = {}, {}
    for r in pr["rows"]:
        t2 = assess_t2pc({"unsupported": True}, qr[r["id"]])
        rchecks[r["id"]] = {"ok": t2.get("outcome") == "unsupported", "t2pc_outcome": t2.get("outcome")}
        if not rchecks[r["id"]]["ok"]:
            rexcluded[r["id"]] = [f"refusal_target_not_unsupported:{t2.get('outcome')}"]
    out = {"batch012": {"checks": checks, "excluded": excluded}, "refusal_dev2": {"checks": rchecks, "excluded": rexcluded}}
    (HERE / "apply9_checks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"b012_excluded": excluded, "rdev2_excluded": rexcluded,
                      "b012_modify": {k: {kk: v[kk] for kk in ("ok", "excluded_reasons", "jaccard_max_any", "jaccard_nearest_any", "t2pc_outcome")}
                                      for k, v in checks.items() if v["kind"].startswith("modify")},
                      "b012_ok": sum(v["ok"] for v in checks.values()), "rdev2_ok": sum(v["ok"] for v in rchecks.values())}, ensure_ascii=False, indent=1))
    if "--check-only" in sys.argv:
        return
    qdir, dec = HERE / "b012/queue", HERE / "b012/decisions.jsonl"
    if not (qdir / "manifest.json").exists():
        qdir.mkdir(parents=True, exist_ok=True)
        lines = []
        for cid in sorted(cb):
            c = cb[cid]
            row = {"candidate_id": cid, "candidate_type": "targeted_gold", "question": c["question"], "proposed_grounding": c["draft_grounding"],
                   "proposed_rejected": None, "provenance": {"file": "sft_dpo_inventory/batch012/candidates_checked.json", "id": cid},
                   "note": "pilot_009 S0: batch012 검토 큐(검토 시트 초안 그대로, 결정 233)"}
            row["candidate_hash"] = digest(row)
            lines.append(canonical_json(row))
        (qdir / "review_queue.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (qdir / "manifest.json").write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), "group": "batch012",
                                                        "output_hashes": {"review_queue.jsonl": sha256(qdir / "review_queue.jsonl")}}, ensure_ascii=False, indent=1) + "\n",
                                            encoding="utf-8")
    rows_q, _ = load_queue(qdir)
    have = decision_history(dec, rows_q) if dec.exists() else {}
    recorded = collections.Counter()
    for r in pb["rows"]:
        if r["id"] in excluded:
            continue
        prev = have.get(r["id"])
        if prev is not None and prev["status"] == "accepted" and prev["reason"].startswith(REASON12[:10]):
            continue
        if r["decision"] == "modify":
            decide(qdir, dec, r["id"], status="accepted", reviewer=REVIEWER, semantic_checks=True,
                   reason=f"{REASON12}: 질문 수정 → '{r['corrected_question']}'(정답 {{\"unsupported\": true}} 그대로). 이유: {r['reason']} 재검사 통과(apply9_checks.json).")
        else:
            decide(qdir, dec, r["id"], status="accepted", reviewer=REVIEWER, semantic_checks=True, reason=f"{REASON12}: 승인(초안 그대로).")
        recorded[r["decision"]] += 1
    train = read_jsonl(APPROVED / "approved_train_v4.jsonl")
    n4 = len(train)
    for r in pb["rows"]:
        if r["id"] in excluded:
            continue
        c = cb[r["id"]]
        refusal = c["kind"] == "r1_refusal"
        sem = semantics_from_full({"unsupported": True}) if refusal else c["semantics"]
        rec = record(f"b012:{r['id']}", qb[r["id"]], "batch012_draft", semantics=sem, execution=None if refusal else c["gold"],
                     execution_source="거부(정답 호출 없음, {\"unsupported\": true})" if refusal else "batch012 정답 호출(초안)",
                     status=f"approved(pilot_009 결정 233): {r['decision']}",
                     provenance={"file": "sft_dpo_inventory/batch012/candidates_checked.json", "id": r["id"], "gap": c["gap"], "kind": c["kind"],
                                 **({"original_question": c["question"]} if r["decision"] == "modify" else {})})
        rec["validation"] = checks[r["id"]].get("validation") or {"t2pc_outcome": checks[r["id"]].get("t2pc_outcome")}
        rec["corpus_group"] = "batch012"
        rec["k3_scope_name_family"] = False
        train.append(rec)
    out_p = APPROVED / "approved_train_v5.jsonl"
    if out_p.exists():
        raise SystemExit("approved_train_v5.jsonl exists; not overwriting")
    out_p.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in train), encoding="utf-8")
    man = {"version": "v5", "created_at": datetime.now(timezone.utc).isoformat(), "decision": "233 (Z1)", "base": "approved_train_v4.jsonl",
           "base_sha256": sha256(APPROVED / "approved_train_v4.jsonl"), "base_records": n4, "added_batch012": len(train) - n4,
           "added_by_kind": dict(collections.Counter(cb[r["id"]]["kind"] for r in pb["rows"] if r["id"] not in excluded)),
           "excluded": excluded, "records": len(train), "sha256": sha256(out_p), "decisions_recorded_this_run": dict(recorded),
           "decisions_file": "sft_dpo_inventory/pilot_009/review/b012/decisions.jsonl"}
    (APPROVED / "manifest_v5.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    adir = P9 / "refusal_dev2/approved"
    adir.mkdir(exist_ok=True)
    v1dir = INV / "pilot_008/refusal_dev/approved"
    v1 = yaml.safe_load((v1dir / "rdev_v1_gold.yaml").read_text(encoding="utf-8"))["items"]
    v1meta = json.loads((v1dir / "rdev_v1_items_meta.json").read_text(encoding="utf-8"))
    items = list(v1)
    meta = {i["id"]: {**v1meta[i["id"]], "part": "v1"} for i in v1}
    for r in pr["rows"]:
        if r["id"] in rexcluded:
            continue
        c = cr[r["id"]]
        items.append({"id": r["id"], "question": qr[r["id"]], "gold_text": "", "gold": [], "expected_outcome": "unsupported", "vendor_verdict": "-"})
        meta[r["id"]] = {"kind": c["kind"], "gap": c["gap"], "refusal": True, "decision": r["decision"], "part": "ext"}
    (adir / "rdev_v2_gold.yaml").write_text(yaml.safe_dump({"note": "refusal_dev v2 승인본(결정 234) = v1 승인본 60 + 확장 60 — 개발 셋, 학습·최종 판정에 쓰지 않음", "items": items},
                                                          allow_unicode=True, sort_keys=False), encoding="utf-8")
    (adir / "rdev_v2_items_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (adir / "manifest.json").write_text(json.dumps({"decision": "234 (Z2)", "reviewer": REVIEWER, "items": len(items),
                                                    "refusal": sum(m["refusal"] for m in meta.values()), "contrast": sum(not m["refusal"] for m in meta.values()),
                                                    "v1_source": {"file": "sft_dpo_inventory/pilot_008/refusal_dev/approved/rdev_v1_gold.yaml", "sha256": sha256(v1dir / "rdev_v1_gold.yaml")},
                                                    "excluded": rexcluded, "gold_sha256": sha256(adir / "rdev_v2_gold.yaml")}, ensure_ascii=False, indent=1) + "\n",
                                        encoding="utf-8")
    print(json.dumps({"corpus_v5": {k: man[k] for k in ("records", "added_batch012", "added_by_kind", "sha256")}, "rdev_v2": len(items),
                      "rdev_v2_refusal": sum(m["refusal"] for m in meta.values())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
