# -*- coding: utf-8 -*-
"""W5: 기존 데이터를 canonical 레코드로 바꾸고 출처 사이 충돌과 검증 사슬 결과를 남긴다. 모델 호출 없음, 승인 아님.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/canonical/build_canonical.py

출처(각 레코드의 ``source``):
- ``t2pc_v006``: trunk ``reviewed_gold_v006_t2pc`` sft_train 가운데 pilot_004 판(``thinking_pilot004_t2pc``)의 131질문. Full target이 gold.
  (pilot_004 판 안에서는 같은 질문의 최종 JSON이 레코드마다 다를 수 있어 gold로 쓰지 않는다.)
- ``pg_v006_p0``: ``pg_imports/reviewed_gold_v006_p0`` 154(metadata.target_full이 Full gold, target_p0은 pg가 만든 Partial target).
- ``pg_reasoning_v001``: ``pg_imports/reviewed_reasoning_v001`` 154(같은 target_full·target_p0 + reasoning).
- ``batch007_draft``: ``batch007/candidates_checked.json`` 27(``draft_grounding``, **초안 표시 유지**).
id: trunk는 ``t2pc:<source_record_id>``, pg는 ``pg:<source_record_id>``이고 pg batch006(``b006-NN``)은 ``pg:pg-b006-NN``(결정 111. trunk ``b006-NN``과 이름만 같고
내용이 다르다). 출처 사이 비교는 id가 아니라 정규화 질문(``question_key``)으로 한다.

충돌(``conflicts.json``): 같은 정규화 질문이 둘 이상의 출처에 있고 ``semantic_key``(text span 제외)가 다르면 충돌이다. 임의로 고르지 않는다.
text span만 다르면 ``span_only``로 따로 적는다. 검증 사슬은 ``grounding.validation.validate_semantics``(모든 레코드).
pg 변환 일치(보고): ``render_partial(semantics)``가 pg ``target_p0``과 같은가.
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from grounding.canonical import record, semantics_from_full  # noqa: E402
from grounding.partial_renderer import render_partial  # noqa: E402
from grounding.validation import validate_semantics  # noqa: E402
from training.data.common import read_jsonl, sha256  # noqa: E402
from training.data.split import question_key  # noqa: E402

V006 = ROOT / "training/generated/reviewed_gold_v006_t2pc/sft_train.jsonl"
P004 = ROOT / "training/generated/thinking_pilot004_t2pc/sft_train.jsonl"
PG_P0 = ROOT / "sft_dpo_inventory/pg_imports/reviewed_gold_v006_p0/sft_train.jsonl"
PG_RR = ROOT / "sft_dpo_inventory/pg_imports/reviewed_reasoning_v001/dataset.jsonl"
B007 = ROOT / "sft_dpo_inventory/batch007/candidates_checked.json"


def _target(content):
    text = content.split("</think>")[-1].strip()
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


def _pg_id(srid):
    return f"pg:pg-{srid}" if srid.startswith("b006-") else f"pg:{srid}"


def load_records():
    p004 = {r["metadata"]["source_record_id"] for r in read_jsonl(P004)}
    out = []
    for row in read_jsonl(V006):
        srid = row["metadata"]["source_record_id"]
        if srid not in p004:
            continue
        question = next(m["content"] for m in row["messages"] if m["role"] == "user")
        out.append(record(f"t2pc:{srid}", question, "t2pc_v006", semantics=semantics_from_full(_target(row["messages"][-1]["content"])),
                          execution_source="full_target_mock", status="approved(trunk v006_t2pc)",
                          provenance={"file": str(V006.relative_to(ROOT)), "source_record_id": srid}))
    pg_p0_targets = {}
    for name, path in (("pg_v006_p0", PG_P0), ("pg_reasoning_v001", PG_RR)):
        for row in read_jsonl(path):
            meta = row["metadata"]
            question = next(m["content"] for m in row["messages"] if m["role"] == "user")
            rec = record(_pg_id(meta["source_record_id"]) + ("" if name == "pg_v006_p0" else "#rr"), question, name,
                         semantics=semantics_from_full(meta["target_full"]), execution_source="full_target_mock",
                         status=f"pg 승인 상태 그대로({meta.get('approved_by') or meta.get('review_decision') or meta.get('dataset_version')})",
                         provenance={"file": str(path.relative_to(ROOT)), "source_record_id": meta["source_record_id"], "commit": "ab9d215"})
            target_p0 = meta.get("target_p0")
            if target_p0 is None:
                target_p0 = _target(row["messages"][-1]["content"])
            pg_p0_targets[rec["id"]] = target_p0
            out.append(rec)
    for cand in json.loads(B007.read_text(encoding="utf-8"))["candidates"]:
        out.append(record(f"b007:{cand['id']}", cand["question"], "batch007_draft", semantics=semantics_from_full(cand["draft_grounding"]),
                          execution_source="full_target_mock", status="draft(승인 아님, 결정 104)",
                          provenance={"file": str(B007.relative_to(ROOT)), "id": cand["id"]}))
    return out, pg_p0_targets


def main():
    records, pg_p0 = load_records()
    p0_match = collections.Counter()
    p0_mismatch = []
    for rec in records:
        if rec["id"] in pg_p0:
            same = render_partial(rec["semantics"]) == pg_p0[rec["id"]]
            p0_match[same] += 1
            if not same:
                p0_mismatch.append({"id": rec["id"], "render_partial": render_partial(rec["semantics"]), "pg_target_p0": pg_p0[rec["id"]]})
    results = {}
    for rec in records:
        rec["validation"] = validate_semantics(rec["semantics"], rec["question"], rec.get("execution"))
        results[rec["id"]] = rec["validation"]["ok"]
    by_q = collections.defaultdict(list)
    for rec in records:
        by_q[question_key(rec["question"])].append(rec)
    conflicts, span_only = [], []
    for qk, recs in by_q.items():
        sources = {r["source"] for r in recs}
        if len(recs) < 2:
            continue
        keys = {r["semantic_key"] for r in recs}
        if len(keys) > 1:
            conflicts.append({"question": recs[0]["question"], "sources": sorted(sources),
                              "variants": [{"id": r["id"], "source": r["source"], "status": r["status"], "view": r["view"],
                                            "semantics": r["semantics"]} for r in recs],
                              "decision": None, "note": "사람 검토. 임의로 고르지 않는다"})
        elif len({r["semantic_key_with_text"] for r in recs}) > 1:
            span_only.append({"question": recs[0]["question"], "ids": [r["id"] for r in recs],
                              "spans": [[n.get("text") for n in r["semantics"]["nodes"]] for r in recs]})
    with open(HERE / "canonical_records.jsonl", "w", encoding="utf-8") as stream:
        for rec in records:
            stream.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (HERE / "conflicts.json").write_text(json.dumps({"rule": "같은 정규화 질문, 다른 semantic_key(text span 제외). 사람 검토 대상",
                                                     "conflicts": conflicts, "span_only_differences": span_only},
                                                    ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    fails = [r for r in records if not r["validation"]["ok"]]
    summary = {
        "records": len(records), "by_source": dict(collections.Counter(r["source"] for r in records)),
        "distinct_questions": len(by_q),
        "questions_in_multiple_sources": sum(len({r["source"] for r in recs}) > 1 for recs in by_q.values()),
        "validation_pass": sum(results.values()), "validation_fail": len(fails),
        "validation_by_source": {s: {"pass": sum(results[r["id"]] for r in records if r["source"] == s),
                                     "fail": sum(not results[r["id"]] for r in records if r["source"] == s)}
                                 for s in sorted({r["source"] for r in records})},
        "validation_fail_reasons": dict(collections.Counter(
            ",".join(k for k in ("assess_same", "signature_same(no EVENT)", "mock_same") if not r["validation"][k]) or "execution_match"
            for r in fails)),
        "validation_fail_ids": [r["id"] for r in fails],
        "full_path_answered_in_mock": {s: {"answered": sum(r["validation"]["full_answered"] for r in records if r["source"] == s),
                                           "not": sum(not r["validation"]["full_answered"] for r in records if r["source"] == s)}
                                       for s in sorted({r["source"] for r in records})},
        "full_path_not_answered_reasons": dict(collections.Counter(
            f"{r['validation']['full']['error_code'] or r['validation']['mock_full']['error_code']}" for r in records if not r["validation"]["full_answered"])),
        "conflicts": len(conflicts), "conflicts_by_sources": dict(collections.Counter("+".join(c["sources"]) for c in conflicts)),
        "span_only_differences": len(span_only),
        "pg_target_p0_equals_render_partial": {"same": p0_match[True], "different": p0_match[False]},
        "inputs": {str(p.relative_to(ROOT)): sha256(p) for p in (V006, P004, PG_P0, PG_RR, B007)},
    }
    (HERE / "validation_summary.json").write_text(json.dumps({"summary": summary, "pg_target_p0_mismatches": p0_mismatch[:50]},
                                                             ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
