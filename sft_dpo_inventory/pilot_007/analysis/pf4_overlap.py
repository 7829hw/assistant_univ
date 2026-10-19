# -*- coding: utf-8 -*-
"""PF4(결정 193): RC5 학습 레코드 질문이 ``protected_final_v1`` 초안과 겹치는지 — **개수만** 낸다. 초안 내용은 출력·저장하지 않는다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/analysis/pf4_overlap.py --xlsx /home/hwkim/sftdpo_work/protected_final_v1/protected_final_v1.xlsx
    # -> analysis/pf4_overlap.json (겹친 레코드·질문 수, 기준별 수, 초안 sha256)

방법은 ``pilot_006/protected_final/validate.py``의 겹침 검사와 같다: 정규화 질문 같음, 문자 3-gram Jaccard ≥ ``check_aug300.STRONG_AT``, 같은 grounding view.
초안 쪽은 validate.py의 ``load_rows``로 읽고 정답 호출에서 grounding을 역산한다. RC5 쪽은 승인 corpus v3 semantics의 ``render_full``.
초안은 고정 전이라 겹침이 0이 아니어도 RC5를 고치지 않는다(결정 193 PF4).
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
for p in (ROOT, ROOT / "sft_dpo_inventory/pilot_006_prep/aug300", ROOT / "sft_dpo_inventory/pilot_006/protected_final"):
    sys.path.insert(0, str(p))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--xlsx", required=True)
    a = p.parse_args()
    import check_aug300 as W6
    import evaluate_vendor100 as EV
    from grounding.full_renderer import render_full
    from training.data.split import question_key
    spec = importlib.util.spec_from_file_location("pfv", ROOT / "sft_dpo_inventory/pilot_006/protected_final/validate.py")
    V = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(V)
    rows, errs = V.load_rows(Path(a.xlsx))
    if rows is None:
        raise SystemExit(f"load failed: {errs}")
    dq, dg, dv = set(), [], set()
    for r in rows:
        if r["질문"]:
            k = question_key(r["질문"])
            dq.add(k)
            dg.append(W6.grams(k))
        try:
            calls = EV.parse_calls(r["정답 호출"]) if r["정답 호출"] else []
            if calls:
                dv.add(json.dumps(EV._grounding_view(EV.derive_grounding(calls)), ensure_ascii=False, sort_keys=True, default=str))
        except Exception:  # noqa: BLE001
            pass
    corpus = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v3.jsonl").read_text(encoding="utf-8").splitlines()}
    out = {"draft_sha256": hashlib.sha256(Path(a.xlsx).read_bytes()).hexdigest(), "draft_rows": len(rows), "method": "validate.py와 같음(question / jaccard ≥ STRONG_AT / same grounding)",
           "arms": {}}
    qcache = {}
    for arm in ("full", "partial"):
        recs = [json.loads(l) for l in (HERE.parent / f"build/RC5/{arm}/sft_train.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        rec_hits, q_hits = Counter(), {"question": set(), "jaccard": set(), "same_grounding": set()}
        for r in recs:
            cid = r["metadata"]["source_record_id"]
            if cid not in qcache:
                c = corpus[cid]
                k = question_key(c["question"])
                g = W6.grams(k)
                v = json.dumps(EV._grounding_view(render_full(c["semantics"])), ensure_ascii=False, sort_keys=True, default=str)
                qcache[cid] = {"question": k in dq, "jaccard": max((len(g & x) / len(g | x) for x in dg), default=0) >= W6.STRONG_AT, "same_grounding": v in dv}
            h = qcache[cid]
            for crit, hit in h.items():
                if hit:
                    rec_hits[crit] += 1
                    q_hits[crit].add(cid)
            if any(h.values()):
                rec_hits["any"] += 1
        out["arms"][arm] = {"records": len(recs), "records_overlapping": {k: rec_hits.get(k, 0) for k in ("any", "question", "jaccard", "same_grounding")},
                            "questions_overlapping": {k: len(v) for k, v in q_hits.items()},
                            "questions_overlapping_any": len(set().union(*q_hits.values()))}
    (HERE / "pf4_overlap.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
