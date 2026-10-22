# -*- coding: utf-8 -*-
"""pilot_008 S0(결정 221·222): 고정한 받아들일 목록(``b011_accept_list.json``·``rdev_accept_list.json``)을 검증하고 기록한다. 모델 호출 없음.
``pilot_007/review/b010/b010_apply.py``와 같은 방식.

    hfvenv/bin/python sft_dpo_inventory/pilot_008/review/apply8.py [--check-only]

1. 다시 검사(기록 전, 수정 3건) — ``batch011/build_candidates11.py``의 대상(결정 120 규칙 대상·batch008–010·승인 corpus v3·RC5 실제 학습 레코드 Full·Partial)을 그대로 쓴다.
   - b011-015(r1 거부, 질문 수정): 대상 + refusal_dev(승인본 문장) + 나머지 batch011과 정규화 질문 일치·문자 3-gram Jaccard ≥ 0.5, 거부 target T2PC ``unsupported``.
   - rdev-046·048(대조, date → last_year): 정답 호출 schema·역산 grounding·검증 사슬(``validate_semantics``)·Full 경로 답함, 대상 + batch011(승인본) 겹침
     (질문·Jaccard·같은 grounding, 보호 넷 family). 걸리면 그 문항만 제외.
   승인 문항(초안 그대로)은 batch011: r2는 검증 사슬 재실행, r1은 T2PC ``unsupported`` 재확인.
2. 기록(``--check-only`` 아니면):
   - batch011: ``training.annotations.workflow.decide``(큐 ``b011/queue``, ``b011/decisions.jsonl``, 검토자 "사용자(이름 기록 안 함), 2차 검토 권고 채택").
   - 승인 corpus v4(``pilot_006_prep/approved/approved_train_v4.jsonl``) = v3 + batch011 승인분(``b011:b011-NNN``; r1은 semantics ``unsupported``, 정답 호출 없음). v3는 고치지 않는다.
   - refusal_dev 승인본: ``pilot_008/refusal_dev/approved/rdev_v1_gold.yaml``·``rdev_v1_items_meta.json``(개발 셋, 학습·최종 판정에 쓰지 않음).
"""
import collections
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
P8 = HERE.parent
INV = P8.parent
ROOT = INV.parent
APPROVED = INV / "pilot_006_prep/approved"
for p in (ROOT, INV / "batch011", INV / "batch004", INV / "pilot_006_prep/aug300", INV / "pilot_006_prep/aug300_review", INV / "pilot_006/protected_final"):
    sys.path.insert(0, str(p))
REVIEWER = "사용자(이름 기록 안 함), 2차 검토 권고 채택"
REASON11 = "결정 221(2026-10-22): batch011 2차 검토 권고 채택"


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def index_targets(tg):
    import evaluate_vendor100 as EV
    import check_aug300 as W6
    from training.annotations.inventory import as_record, family_key
    from training.data.split import question_key
    idx = {}
    for name, rows in tg.items():
        i = {"q": collections.defaultdict(list), "g": [], "view": collections.defaultdict(list), "f": collections.defaultdict(list)}
        for rid, q, pl in rows:
            qk = question_key(q)
            i["q"][qk].append(rid)
            i["g"].append((rid, W6.grams(qk)))
            if pl and not pl.get("unsupported"):
                try:
                    i["view"][json.dumps(EV._grounding_view(pl), ensure_ascii=False, sort_keys=True, default=str)].append(rid)
                    i["f"][family_key(pl)].append(rid)
                except Exception:  # noqa: BLE001
                    pass
        idx[name] = i
    return idx


def overlap(question, payload, idx, refusal):
    import evaluate_vendor100 as EV
    import check_aug300 as W6
    from training.annotations.inventory import family_key
    from training.data.split import question_key
    qk = question_key(question)
    g = W6.grams(qk)
    why, info = [], {}
    vk = None if refusal else json.dumps(EV._grounding_view(payload), ensure_ascii=False, sort_keys=True, default=str)
    fk = None if refusal else family_key(payload)
    for name, i in idx.items():
        best = max(((len(g & vg) / len(g | vg), rid) for rid, vg in i["g"]), default=(0.0, None))
        info[name] = {"jaccard_max": round(best[0], 3), "nearest": best[1]}
        why += [f"{name}:question"] if i["q"].get(qk) else []
        why += [f"{name}:jaccard>=0.5({best[1]},{round(best[0], 3)})"] if best[0] >= 0.5 else []
        if not refusal:
            why += [f"{name}:same_grounding"] if i["view"].get(vk) else []
            why += [f"{name}:family"] if name in ("selection_v2", "holdout", "valid98", "aux_test_v1") and i["f"].get(fk) else []
    return why, info


def main():
    import build_candidates11 as BC
    import evaluate_vendor100 as EV
    from draft_semantics import add_spans
    from grounding.canonical import record, semantics_from_full
    from grounding.validation import validate_semantics
    from training.annotations.inventory import digest
    from training.annotations.workflow import decide, decision_history, load_queue
    from training.data.canonicalize import canonical_json
    from training.data.common import sha256
    from training.data.validation import assess_t2pc
    pb = json.loads((HERE / "b011_accept_list.json").read_text(encoding="utf-8"))
    pr = json.loads((HERE / "rdev_accept_list.json").read_text(encoding="utf-8"))
    cb = {c["id"]: c for c in json.loads((INV / "batch011/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    cr = {c["id"]: c for c in json.loads((P8 / "refusal_dev/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}
    qb = {r["id"]: r.get("corrected_question") or cb[r["id"]]["question"] for r in pb["rows"]}
    qr = {r["id"]: r.get("corrected_question") or cr[r["id"]]["question"] for r in pr["rows"]}
    gr = {r["id"]: r.get("corrected_gold_text") or cr[r["id"]]["gold_text"] for r in pr["rows"]}
    base_tg = BC.targets()
    checks, excluded = {}, {}
    # b011-015 등 batch011 수정(r1): + refusal_dev 승인본 문장 + 나머지 batch011
    for r in pb["rows"]:
        c = cb[r["id"]]
        if r["decision"] == "modify":
            tg = dict(base_tg)
            tg["refusal_dev_v1"] = [(i, qr[i], None) for i in qr]
            tg["batch011_others"] = [(i, qb[i], None) for i in qb if i != r["id"]]
            why, info = overlap(qb[r["id"]], None, index_targets(tg), refusal=True)
            t2 = assess_t2pc({"unsupported": True}, qb[r["id"]])
            why += [] if t2.get("outcome") == "unsupported" else [f"refusal_target_not_unsupported:{t2.get('outcome')}"]
            checks[r["id"]] = {"kind": "modify(r1)", "ok": not why, "excluded_reasons": why, "overlap": info, "t2pc_outcome": t2.get("outcome")}
        elif c["kind"] == "r1_refusal":
            t2 = assess_t2pc({"unsupported": True}, c["question"])
            checks[r["id"]] = {"kind": "approve(r1)", "ok": t2.get("outcome") == "unsupported", "t2pc_outcome": t2.get("outcome")}
        else:
            v = validate_semantics(c["semantics"], c["question"], c["gold"])
            checks[r["id"]] = {"kind": "approve(r2)", "ok": bool(v["ok"] and v["execution_match"] and v["full_answered"]),
                               "validation": {k: v[k] for k in ("ok", "assess_same", "mock_same", "execution_match", "full_answered")}}
        if not checks[r["id"]]["ok"]:
            excluded[r["id"]] = checks[r["id"]].get("excluded_reasons") or ["validation_failed"]
    # refusal_dev 수정(대조): 검증 사슬 + 겹침(대상 + batch011 승인본)
    tg = dict(base_tg)
    tg["batch011_v1"] = [(i, qb[i], cb[i]["draft_grounding"] if cb[i]["kind"] == "r2_contrast" else None) for i in qb if i not in excluded]
    idx = index_targets(tg)
    rchecks, rexcluded = {}, {}
    for r in pr["rows"]:
        if r["decision"] != "modify":
            continue
        calls = EV.parse_calls(gr[r["id"]])
        payload, flags = add_spans(EV.derive_grounding(calls), qr[r["id"]])
        sem = semantics_from_full(payload)
        v = validate_semantics(sem, qr[r["id"]], calls)
        why, info = overlap(qr[r["id"]], payload, idx, refusal=False)
        why += [] if v["ok"] else ["validation_chain_failed"]
        why += [] if v["full_answered"] else ["full_path_not_answered"]
        rchecks[r["id"]] = {"ok": not why, "excluded_reasons": why, "overlap": info, "span_flags": flags,
                            "validation": {k: v[k] for k in ("ok", "assess_same", "mock_same", "execution_match", "full_answered")}, "calls": calls, "payload": payload}
        if why:
            rexcluded[r["id"]] = why
    out = {"batch011": {"checks": checks, "excluded": excluded}, "refusal_dev": {"checks": {k: {kk: vv for kk, vv in v.items() if kk not in ("calls", "payload")}
                                                                                          for k, v in rchecks.items()}, "excluded": rexcluded}}
    (HERE / "apply8_checks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"b011_excluded": excluded, "rdev_excluded": rexcluded,
                      "b011_modify": {k: v for k, v in checks.items() if v["kind"].startswith("modify")},
                      "rdev_modify": {k: {kk: rchecks[k][kk] for kk in ("ok", "excluded_reasons", "validation")} for k in rchecks},
                      "b011_ok": sum(v["ok"] for v in checks.values())}, ensure_ascii=False, indent=1, default=str)[:4000])
    if "--check-only" in sys.argv:
        return
    # 기록: batch011 결정
    qdir, dec = HERE / "b011/queue", HERE / "b011/decisions.jsonl"
    if not (qdir / "manifest.json").exists():
        qdir.mkdir(parents=True, exist_ok=True)
        lines = []
        for cid in sorted(cb):
            c = cb[cid]
            row = {"candidate_id": cid, "candidate_type": "targeted_gold", "question": c["question"], "proposed_grounding": c["draft_grounding"],
                   "proposed_rejected": None, "provenance": {"file": "sft_dpo_inventory/batch011/candidates_checked.json", "id": cid},
                   "note": "pilot_008 S0: batch011 검토 큐(검토 시트 초안 그대로, 결정 221)"}
            row["candidate_hash"] = digest(row)
            lines.append(canonical_json(row))
        (qdir / "review_queue.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (qdir / "manifest.json").write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), "group": "batch011",
                                                        "output_hashes": {"review_queue.jsonl": sha256(qdir / "review_queue.jsonl")}}, ensure_ascii=False, indent=1) + "\n",
                                            encoding="utf-8")
    rows_q, _ = load_queue(qdir)
    have = decision_history(dec, rows_q) if dec.exists() else {}
    recorded = collections.Counter()
    for r in pb["rows"]:
        if r["id"] in excluded:
            continue
        prev = have.get(r["id"])
        if prev is not None and prev["status"] == "accepted" and prev["reason"].startswith(REASON11[:10]):
            continue
        if r["decision"] == "modify":
            decide(qdir, dec, r["id"], status="accepted", reviewer=REVIEWER, semantic_checks=True,
                   reason=f"{REASON11}: 질문 수정 → '{r['corrected_question']}'(정답 {{\"unsupported\": true}} 그대로). 이유: {r['reason']}. 재검사 통과(apply8_checks.json).")
        else:
            decide(qdir, dec, r["id"], status="accepted", reviewer=REVIEWER, semantic_checks=True, reason=f"{REASON11}: 승인(초안 그대로).")
        recorded[r["decision"]] += 1
    # corpus v4
    train = read_jsonl(APPROVED / "approved_train_v3.jsonl")
    n3 = len(train)
    for r in pb["rows"]:
        if r["id"] in excluded:
            continue
        c = cb[r["id"]]
        refusal = c["kind"] == "r1_refusal"
        sem = semantics_from_full({"unsupported": True}) if refusal else c["semantics"]
        rec = record(f"b011:{r['id']}", qb[r["id"]], "batch011_draft", semantics=sem, execution=None if refusal else c["gold"],
                     execution_source="거부(정답 호출 없음, {\"unsupported\": true})" if refusal else "batch011 정답 호출(초안)",
                     status=f"approved(pilot_008 결정 221): {r['decision']}",
                     provenance={"file": "sft_dpo_inventory/batch011/candidates_checked.json", "id": r["id"], "gap": c["gap"], "kind": c["kind"],
                                 **({"original_question": c["question"]} if r["decision"] == "modify" else {})})
        rec["validation"] = checks[r["id"]].get("validation") or {"t2pc_outcome": checks[r["id"]].get("t2pc_outcome")}
        rec["corpus_group"] = "batch011"
        rec["k3_scope_name_family"] = False
        train.append(rec)
    out_p = APPROVED / "approved_train_v4.jsonl"
    if out_p.exists():
        raise SystemExit("approved_train_v4.jsonl exists; not overwriting")
    out_p.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in train), encoding="utf-8")
    man = {"version": "v4", "created_at": datetime.now(timezone.utc).isoformat(), "decision": "221 (X1)", "base": "approved_train_v3.jsonl",
           "base_sha256": sha256(APPROVED / "approved_train_v3.jsonl"), "base_records": n3, "added_batch011": len(train) - n3,
           "added_by_kind": dict(collections.Counter(cb[r["id"]]["kind"] for r in pb["rows"] if r["id"] not in excluded)),
           "excluded": excluded, "records": len(train), "sha256": sha256(out_p), "decisions_recorded_this_run": dict(recorded),
           "decisions_file": "sft_dpo_inventory/pilot_008/review/b011/decisions.jsonl"}
    (APPROVED / "manifest_v4.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    # refusal_dev 승인본
    adir = P8 / "refusal_dev/approved"
    adir.mkdir(exist_ok=True)
    items, meta = [], {}
    for r in pr["rows"]:
        if r["id"] in rexcluded:
            continue
        c = cr[r["id"]]
        refusal = c["kind"] == "r1_refusal"
        calls = [] if refusal else (rchecks[r["id"]]["calls"] if r["decision"] == "modify" else c["gold"])
        items.append({"id": r["id"], "question": qr[r["id"]], "gold_text": "" if refusal else gr[r["id"]], "gold": calls,
                      "expected_outcome": "unsupported" if refusal else "answered", "vendor_verdict": "-"})
        meta[r["id"]] = {"kind": c["kind"], "gap": c["gap"], "refusal": refusal, "decision": r["decision"]}
    (adir / "rdev_v1_gold.yaml").write_text(yaml.safe_dump({"note": "refusal_dev v1 승인본(결정 222) — 개발 셋, 학습·최종 판정에 쓰지 않음", "items": items},
                                                          allow_unicode=True, sort_keys=False), encoding="utf-8")
    (adir / "rdev_v1_items_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (adir / "manifest.json").write_text(json.dumps({"decision": "222 (X2)", "reviewer": REVIEWER, "items": len(items),
                                                    "refusal": sum(m["refusal"] for m in meta.values()), "contrast": sum(not m["refusal"] for m in meta.values()),
                                                    "modified": [r["id"] for r in pr["rows"] if r["decision"] == "modify" and r["id"] not in rexcluded],
                                                    "excluded": rexcluded, "gold_sha256": sha256(adir / "rdev_v1_gold.yaml")}, ensure_ascii=False, indent=1) + "\n",
                                        encoding="utf-8")
    print(json.dumps({"corpus_v4": {k: man[k] for k in ("records", "added_batch011", "added_by_kind", "sha256")}, "rdev_v1": len(items)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
