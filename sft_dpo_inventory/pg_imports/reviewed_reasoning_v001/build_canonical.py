# -*- coding: utf-8 -*-
"""final-6 gold 재검토·canonical rationale·검토 기록(모델 호출 0). -> canonical_review.json, canonical_rationales.jsonl"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import canonical_source as S  # noqa: E402

FINAL6 = ["b006-05", "b006-15", "b006-20", "b006-26", "b006-19", "b006-34"]


def main():
    v6 = {json.loads(x)["metadata"]["source_record_id"]: json.loads(x) for x in
          (ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl").read_text(encoding="utf-8").splitlines()}
    rem = json.loads((ROOT / "sft_dpo_inventory/p0_sft_003_teacher27b_remaining/remaining_manifest.json").read_text(encoding="utf-8"))
    if sorted(x["item_id"] for x in rem["items"]) != sorted(FINAL6):
        raise SystemExit("final-6이 remaining manifest와 다르다")
    rows, items = [], {}
    for i in FINAL6:
        gold_verdict, gold_note = S.GOLD_REVIEW[i]
        if gold_verdict == "GOLD_PROBLEM":
            raise SystemExit(f"{i}: GOLD_PROBLEM — dataset freeze 중단")
        text = S.RATIONALE[i]
        if "<think>" in text or "</think>" in text or len(text.strip().splitlines()) < 4:
            raise SystemExit(f"{i}: rationale 형식 위반")
        dec, checks, note = S.REVIEW[i]
        items[i] = {"question": v6[i]["messages"][1]["content"], "gold_p0": json.loads(v6[i]["messages"][2]["content"]),
                    "gold_review": gold_verdict, "gold_review_note": gold_note,
                    "canonical_reason": S.CANONICAL_REASON[i], "review_decision": dec, "review_checks": checks, "review_note": note,
                    "rationale_chars": len(text), "rationale_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
        rows.append({"item_id": i, "reasoning_source": "manual_canonical", "teacher_model": None, "teacher_revision": None,
                     "teacher_digest": None, "generation_batch": "reviewed_reasoning_v001/manual_canonical", "seed": None,
                     "author": "Claude(사람 기준 작성·검토)", "canonical_reason": S.CANONICAL_REASON[i],
                     "review_decision": dec, "thinking": text})
    summary = {"final6": FINAL6, "gold_review": {k: v["gold_review"] for k, v in items.items()},
               "approved": sum(v["review_decision"] == "APPROVE_CANONICAL" for v in items.values()),
               "rejected": sum(v["review_decision"] == "REJECT_CANONICAL" for v in items.values()),
               "new_model_calls": 0, "language": "영어 thinking(다른 148 trace와 같음), 질문 표현은 한국어 인용"}
    if summary["approved"] != 6:
        raise SystemExit("canonical 6/6 승인이 아니다")
    (HERE / "canonical_review.json").write_text(json.dumps({"summary": summary, "items": items}, ensure_ascii=False, indent=1) + "\n",
                                                encoding="utf-8")
    with open(HERE / "canonical_rationales.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    for i in FINAL6:
        print(i, items[i]["rationale_chars"])


if __name__ == "__main__":
    main()
