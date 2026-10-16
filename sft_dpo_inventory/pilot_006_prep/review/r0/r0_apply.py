# -*- coding: utf-8 -*-
"""R0 2단계(결정 130 G0): 고정한 받아들일 목록(``r0_accept_list.json``, 커밋 1d897d4)을 검증하고 기록한다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/review/r0/r0_apply.py

1. 수정 검증(결정 기록 전)
   - grounding 수정 6건: 수정 JSON → semantics → W5 검증 사슬(``grounding.validation.validate_semantics``, 업체 형식 정답 호출 포함).
     통과 = 사슬 ok, execution_match 참, Full·Partial 판정(assess)·mock 같음, **mock 호출이 원래 초안의 mock 호출과 같음**.
   - 질문 수정 4건: 정답 호출에서 역산한 뜻은 그대로 두고 측정·장소 span만 새 문구에서 다시 찾는다(``draft_semantics.add_spans``와 같은 규칙).
     검증 사슬을 새 문구로 다시 돌리고, W6 겹침 검사(``check_aug300``과 같은 대상·기준: 질문 같음, 문자 3-gram Jaccard ≥ 0.5, 같은 grounding, thor 보호)를
     새 문구로 다시 한다. 이전 문구에 없던 강한 겹침이 생기면 그 문항은 보류.
   - 실패한 문항은 결정을 기록하지 않고 ``보류``로 남긴다(대체 수정안을 만들지 않는다).
2. holdout 고정값: 정렬 ID sha256 ``69d3af19…``, 질문 sha256 ``23ee1bc8…``, gold 파일 sha256이 그대로인지 확인. 다르면 exit 3(전체 멈춤).
3. 결정 기록: 기존 ``training.annotations.workflow.decide``를 그대로 부른다(원본 큐 불변, decision_hash·supersedes 사슬).
   aug300·batch007은 기존 검토 큐, batch008·pg EDIT_REQUIRED는 검토 큐가 없어 같은 형식의 큐를 ``queues/``에 새로 만든다(초안 그대로).
   결정 파일은 묶음마다 ``decisions/<묶음>.jsonl``. 이미 기록이 있으면 같은 결정은 다시 쓰지 않는다(재실행 안전).
4. 승인 corpus(``../../approved/``): canonical 레코드 형식.
   - ``approved_train_v1.jsonl``: trunk 131 + pg 154(수용 147 + EDIT_REQUIRED 7) + aug300 train 승인 + batch007 27 + batch008 10.
   - ``approved_holdout_v1.jsonl``: aug300 holdout 53(평가 전용, 학습 금지). 평가 gold 파일(``augmentation_holdout_v1_gold.yaml``)은 바꾸지 않는다.
   - ``invalidated_outputs.json``: 질문이 바뀐 문항의 이전 문구 출력(J1·J3·J6 trace id) — 학습·판정에서 뺀다.
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
sys.path.insert(0, str(PREP / "aug300"))
sys.path.insert(0, str(PREP / "aug300_review"))
sys.path.insert(0, str(INV / "batch004"))

REVIEWER = "사용자(검토자 이름 미기재)"
REASON = "Claude 2차 검토 권고 일괄 채택(결정 130 G0, 2026-10-16, 결정 파일 pilot006_review_decisions_v1.xlsx sha256 405a217f…)"
QUEUES = {"aug300": PREP / "aug300_review/review", "batch007": INV / "batch007/review",
          "batch008": HERE / "queues/batch008", "pg_edit_required": HERE / "queues/pg_edit_required"}
HOLDOUT = {"sorted_ids_sha256": "69d3af197dd591d73fba097e1b7be9ffadfb9ba71e153338f274b29ac9457d17",
           "questions_sha256": "23ee1bc8eab8e6a9420775fb48a87b77a6c2a13fa0217fa8fde6dbb77aadb73b"}
OUT = PREP / "approved"


def read_jsonl(p):
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def overlap_index():
    """check_aug300과 같은 대상·기준(W6 3)."""
    import evaluate_vendor100 as EV
    from check_aug300 import grams, load_targets
    from training.annotations.inventory import Protection
    from training.data.split import question_key
    targets = load_targets(None)
    idx = {}
    for name, rows in targets.items():
        idx[name] = {"q": {question_key(q) for _, q, _ in rows}, "g": [(rid, grams(question_key(q))) for rid, q, _ in rows],
                     "view": {json.dumps(EV._grounding_view(pl), ensure_ascii=False, sort_keys=True, default=str) for _, _, pl in rows if pl}}
    guard = Protection.current(ROOT / "training/generated/reviewed_gold_v006_t2pc")
    return idx, guard


def strong_hits(question, payload, rid, idx, guard):
    import evaluate_vendor100 as EV
    from check_aug300 import STRONG_AT, grams
    from training.data.split import question_key
    qk = question_key(question)
    g = grams(qk)
    view = json.dumps(EV._grounding_view(payload), ensure_ascii=False, sort_keys=True, default=str)
    hits = []
    for name, i in idx.items():
        if qk in i["q"]:
            hits.append(f"{name}:question")
        best = max((len(g & vg) / len(g | vg) for _, vg in i["g"]), default=0.0)
        if best >= STRONG_AT:
            hits.append(f"{name}:jaccard>={STRONG_AT}")
        if view in i["view"]:
            hits.append(f"{name}:same_grounding")
    hits += [f"thor:{r}" for r in guard.reasons(question, payload, [rid]) if r in ("protected_question", "protected_parent_or_family")]
    return sorted(hits)


def make_queue(group, rows):
    """batch008·pg EDIT_REQUIRED용 최소 검토 큐(workflow.load_queue 형식). 초안을 그대로 담는다."""
    from training.annotations.inventory import digest
    from training.data.canonicalize import canonical_json
    d = QUEUES[group]
    if (d / "manifest.json").exists():
        return
    d.mkdir(parents=True, exist_ok=True)
    lines = []
    for r in rows:
        row = {"candidate_id": r["candidate_id"], "candidate_type": "targeted_gold", "question": r["question"],
               "proposed_grounding": r["proposed_grounding"], "proposed_rejected": None, "provenance": r["provenance"],
               "note": "pilot_006 R0: 원래 검토 큐가 없는 묶음이라 검토 시트의 초안을 그대로 담은 큐(결정 130)"}
        row["candidate_hash"] = digest(row)
        lines.append(canonical_json(row))
    (d / "review_queue.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    from training.data.common import sha256
    (d / "manifest.json").write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), "group": group,
                                                 "output_hashes": {"review_queue.jsonl": sha256(d / "review_queue.jsonl")}},
                                                ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    import evaluate_vendor100 as EV
    from draft_semantics import add_spans
    from grounding.canonical import record, semantics_from_full
    from grounding.full_renderer import render_full
    from grounding.validation import validate_semantics
    from training.annotations.workflow import decide, decision_history, load_queue

    plan = json.loads((HERE / "r0_accept_list.json").read_text(encoding="utf-8"))
    assert not plan["problems"]
    canon = {r["id"]: r for r in read_jsonl(PREP / "canonical/canonical_records.jsonl")}
    aug_sem = {r["id"]: r for r in read_jsonl(PREP / "aug300_review/semantics_draft.jsonl")}
    aug_items = {r["id"]: r for r in read_jsonl(PREP / "aug300/augmentation_300.jsonl")}
    b008 = {c["id"]: c for c in json.loads((INV / "batch008/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]}

    # ---- 1. 수정 검증
    idx, guard = overlap_index()
    checks, hold = {}, {}
    for r in plan["rows"]:
        if r["decision"] != "modify":
            continue
        rid = r["id"]
        item, draft = aug_items[rid], aug_sem[rid]
        base_v = validate_semantics(draft["semantics"], item["question"], item["gold"])
        if r["modify_kind"] == "grounding":
            payload = json.loads(r["corrected_grounding"])
            sem = semantics_from_full(payload)
            v = validate_semantics(sem, item["question"], item["gold"])
            same_calls = v["mock_full"]["calls"] == base_v["mock_full"]["calls"]
            ok = bool(v["ok"] and v["execution_match"] and v["assess_same"] and v["mock_same"] and same_calls)
            checks[rid] = {"kind": "grounding", "ok": ok, "validation": v, "mock_calls_same_as_draft": same_calls,
                           "draft_validation_ok": base_v["ok"], "question": "unchanged"}
            if ok:
                checks[rid]["semantics"] = sem
        else:
            new_q = r["corrected_question"].strip()
            payload, flags = add_spans(EV.derive_grounding(item["gold"]), new_q)
            sem = semantics_from_full(payload)
            v = validate_semantics(sem, new_q, item["gold"])
            old_payload, _ = add_spans(EV.derive_grounding(item["gold"]), item["question"])
            old_hits = strong_hits(item["question"], old_payload, rid, idx, guard)
            new_hits = strong_hits(new_q, payload, rid, idx, guard)
            added = sorted(set(new_hits) - set(old_hits))
            ok = bool(v["ok"] and v["execution_match"] and not flags and not added)
            checks[rid] = {"kind": "question", "ok": ok, "old_question": item["question"], "new_question": new_q, "span_flags": flags,
                           "validation": v, "strong_overlap_old": old_hits, "strong_overlap_new": new_hits, "strong_overlap_added": added}
            if ok:
                checks[rid]["semantics"] = sem
        if not checks[rid]["ok"]:
            hold[rid] = "검증 실패 — 보류(대체 수정안 없음)"

    # ---- 2. holdout 고정값
    holdout = json.loads((PREP / "aug300/holdout_v1.json").read_text(encoding="utf-8"))
    hold_ids = sorted(i["id"] for i in holdout["list"])
    ids_sha = sha_bytes("\n".join(hold_ids).encode("utf-8"))
    q_sha = sha_bytes("\n".join(aug_items[i]["question"] for i in hold_ids).encode("utf-8"))
    gold_sha = sha_bytes((PREP / "aug300" / holdout["gold_file"]).read_bytes())
    holdout_check = {"sorted_ids_sha256": ids_sha, "questions_sha256": q_sha, "gold_file_sha256": gold_sha,
                     "expected": {**HOLDOUT, "gold_file_sha256": holdout["gold_file_sha256"]},
                     "same": ids_sha == HOLDOUT["sorted_ids_sha256"] and q_sha == HOLDOUT["questions_sha256"] and gold_sha == holdout["gold_file_sha256"],
                     "modified_holdout_items": sorted(r["id"] for r in plan["rows"] if r["decision"] == "modify" and r["status_e4"] == "holdout"),
                     "holdout_questions_changed": sorted(r["id"] for r in plan["rows"] if r["modify_kind"] == "question" and r["id"] in hold_ids)}
    holdout_check["same"] = holdout_check["same"] and not holdout_check["holdout_questions_changed"]
    (HERE / "r0_checks.json").write_text(json.dumps({"modifications": checks, "hold": hold, "holdout": holdout_check}, ensure_ascii=False, indent=1,
                                                    default=str) + "\n", encoding="utf-8")
    if not holdout_check["same"]:
        print(json.dumps(holdout_check, ensure_ascii=False, indent=1))
        raise SystemExit(3)
    if "--check-only" in sys.argv:
        print(json.dumps({"holdout": holdout_check, "checks": {k: {kk: vv for kk, vv in v.items() if kk not in ("validation", "semantics")}
                                                                for k, v in checks.items()}}, ensure_ascii=False, indent=1, default=str))
        return

    # ---- 3. 결정 기록
    make_queue("batch008", [{"candidate_id": cid, "question": c["question"], "proposed_grounding": c["draft_grounding"],
                             "provenance": {"file": "sft_dpo_inventory/batch008/candidates_checked.json", "id": cid}} for cid, c in b008.items()])
    pg_rows = [r for r in plan["rows"] if r["group"] == "pg_edit_required"]
    make_queue("pg_edit_required", [{"candidate_id": r["id"], "question": canon[f"pg:{r['id']}"]["question"],
                                     "proposed_grounding": render_full(canon[f"pg:{r['id']}"]["semantics"]),
                                     "provenance": {"canonical_id": f"pg:{r['id']}", **canon[f"pg:{r['id']}"]["provenance"]}} for r in pg_rows])
    recorded = Counter()
    for group, qdir in QUEUES.items():
        dec_path = HERE / "decisions" / f"{group}.jsonl"
        rows_q, _ = load_queue(qdir)
        known = {q["candidate_id"] for q in rows_q}
        have = decision_history(dec_path, rows_q) if dec_path.exists() else {}
        for r in plan["rows"]:
            if r["group"] != group or r["decision"].startswith("not_applicable") or r["id"] in hold:
                continue
            if r["id"] not in known:
                raise SystemExit(f"{group}:{r['id']} not in queue {qdir}")
            if r["id"] in have:
                continue
            memo = f" 메모: {r['memo']}" if r.get("memo") else ""
            if r["decision"] == "approve":
                decide(qdir, dec_path, r["id"], status="accepted", reviewer=REVIEWER, reason=f"{REASON}: 승인.{memo}", semantic_checks=True)
            elif r["decision"] == "exclude":
                decide(qdir, dec_path, r["id"], status="rejected", reviewer=REVIEWER, reason=f"{REASON}: 제외(SCOPE_NAME 표현만 바꾼 중복).{memo}")
            elif r["modify_kind"] == "grounding":
                decide(qdir, dec_path, r["id"], status="accepted", reviewer=REVIEWER, corrected=json.loads(r["corrected_grounding"]), semantic_checks=True,
                       reason=f"{REASON}: 수정(grounding: 지역 안 OD = 장소 하나 + od_role both, trunk 관례). 검증 사슬 재실행 통과(r0_checks.json).{memo}")
            else:
                decide(qdir, dec_path, r["id"], status="accepted", reviewer=REVIEWER, semantic_checks=True,
                       reason=f"{REASON}: 수정(질문 문구만): 새 질문 \"{r['corrected_question'].strip()}\". 실행 호출 그대로, span 재탐색·검증 사슬·W6 겹침 재검사 통과"
                              f"(r0_checks.json). 이전 문구 출력(J1·J3·J6)은 학습·판정에서 뺀다.{memo}")
            recorded[f"{group}:{r['decision']}"] += 1

    # ---- 4. 승인 corpus
    OUT.mkdir(exist_ok=True)
    stamp = "approved(pilot_006 결정 130 G0)"
    train, hold_rows = [], []
    for c in canon.values():
        if c["source"] == "t2pc_v006":
            train.append({**c, "corpus_group": "trunk"})
        elif c["source"] == "pg_v006_p0":
            rid = c["id"][len("pg:"):]
            pg_edit = any(r["id"] == rid for r in pg_rows)
            train.append({**c, "corpus_group": "pg", "status": f"{stamp}: pg EDIT_REQUIRED 승인" if pg_edit else c["status"]})
    by_id = {r["id"]: r for r in plan["rows"]}
    for rid, item in aug_items.items():
        r = by_id.get(rid)
        if r is None or r["decision"] in ("exclude",) or r["decision"].startswith("not_applicable") or rid in hold:
            continue
        rec = copy.deepcopy(aug_sem[rid])
        if rid in checks:
            sem = checks[rid]["semantics"]
            question = checks[rid].get("new_question", item["question"])
            rec = record(rid, question, "aug300_v2", semantics=sem, execution=item["gold"], execution_source=aug_sem[rid]["execution_source"],
                         status=f"{stamp}: 수정({checks[rid]['kind']})", provenance={**aug_sem[rid]["provenance"], "modified": checks[rid]["kind"],
                                                                                   **({"old_question": item["question"]} if checks[rid]["kind"] == "question" else {})})
            rec["validation"] = checks[rid]["validation"]
        else:
            rec["status"] = f"{stamp}: 승인"
        rec["corpus_group"] = "aug300"
        (hold_rows if r["status_e4"] == "holdout" else train).append(rec)
    for c in canon.values():
        if c["source"] == "batch007_draft":
            train.append({**c, "status": f"{stamp}: 승인", "corpus_group": "batch007"})
    for cid, c in b008.items():
        if by_id.get(cid, {}).get("decision") != "approve":
            continue
        sem = semantics_from_full(c["draft_grounding"])
        rec = record(f"b008:{cid}", c["question"], "batch008_draft", semantics=sem, execution=c["gold"], execution_source="batch008 정답 호출(초안)",
                     status=f"{stamp}: 승인", provenance={"file": "sft_dpo_inventory/batch008/candidates_checked.json", "id": cid})
        rec["validation"] = validate_semantics(sem, c["question"], c["gold"])
        rec["corpus_group"] = "batch008"
        train.append(rec)

    def dump(path, rows):
        path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True, default=str) + "\n" for x in rows), encoding="utf-8")
        return sha_bytes(path.read_bytes())
    s_train = dump(OUT / "approved_train_v1.jsonl", train)
    s_hold = dump(OUT / "approved_holdout_v1.jsonl", hold_rows)
    # 이전 문구 출력 무효화
    inval = {}
    qchanged = [rid for rid, c in checks.items() if c["kind"] == "question" and c["ok"]]
    for name, path, key in (("J1", ROOT / "training/generated/pilot_006/self_full/raw/self_full_raw.jsonl", "id"),
                            ("J6", ROOT / "training/generated/pilot_006/self_partial/raw/self_partial_raw.jsonl", "id"),
                            ("J3", PREP / "aug300/base_first_response.jsonl", "id")):
        rows = read_jsonl(path) if path.exists() else []
        inval[name] = {rid: [x.get("trace_id") or f"{rid}:first_response" for x in rows if x.get(key) == rid] for rid in qchanged}
    (OUT / "invalidated_outputs.json").write_text(json.dumps({"reason": "결정 130 G0·133 G3: 질문 문구가 바뀐 문항의 이전 문구 출력은 학습·판정에서 뺀다",
                                                              "questions": qchanged, "outputs": inval}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    groups = Counter(r["corpus_group"] for r in train)
    manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "decision": "130(G0)", "reviewer": REVIEWER,
                "train": {"file": "approved_train_v1.jsonl", "sha256": s_train, "records": len(train), "by_group": dict(groups)},
                "holdout": {"file": "approved_holdout_v1.jsonl", "sha256": s_hold, "records": len(hold_rows),
                            "note": "평가 전용(학습 금지). 평가 gold 파일은 그대로(holdout 고정값 확인: r0_checks.json)"},
                "aug300": {"train_approved": sum(1 for r in train if r["corpus_group"] == "aug300"), "holdout_approved": len(hold_rows),
                           "modified_in_train": sum(1 for r in train if r["corpus_group"] == "aug300" and r["id"] in checks),
                           "modified_in_holdout": sum(1 for r in hold_rows if r["id"] in checks),
                           "excluded_g0": sorted(r["id"] for r in plan["rows"] if r["decision"] == "exclude"),
                           "excluded_decision_119": sorted(r["id"] for r in plan["rows"] if r["decision"].startswith("not_applicable")),
                           "hold(verification failed)": hold},
                "decisions_recorded_this_run": dict(recorded),
                "note": "trunk·pg는 이전부터 승인된 레코드(pg는 pg 승인 상태, 결정 121). pg 154에는 trunk와 같은 v005 질문 111이 들어 있다(빌드에서 정규화 질문으로 하나로 합친다)."}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("train", "holdout", "aug300", "decisions_recorded_this_run")}, ensure_ascii=False, indent=1))
    print("holdout", holdout_check["same"], "| checks", {k: v["ok"] for k, v in checks.items()})


if __name__ == "__main__":
    main()
