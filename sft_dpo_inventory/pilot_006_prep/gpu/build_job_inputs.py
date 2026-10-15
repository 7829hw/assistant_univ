# -*- coding: utf-8 -*-
"""GPU 작업 J1·J3(그리고 같은 문항을 쓰는 J6)의 문항 목록을 만든다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/pilot_006_prep/gpu/build_job_inputs.py --pg-rr PATH

- ``inputs/self_questions.jsonl``(J1·J6): aug300 train(결정 106 적용 220) + partial-grounding ``reviewed_reasoning_v001`` 154문항
  (``ab9d215``의 ``sft_dpo_inventory/reviewed_reasoning_v001/dataset.jsonl``을 ``git show``로 꺼낸 파일, ``--pg-rr``) + batch007 초안 27.
  - id: ``aug300-NNN``, ``pg-rr-<source_record_id>``, ``b007-NN``. gold(나중 필터용): aug300은 정답 호출 역산 grounding, pg는 ``metadata.target_full``,
    batch007은 ``draft_grounding``(초안, 승인 아님).
  - 같은 정규화 질문이 둘 이상이면 처음 것만 남기고 ``duplicates``에 적는다.
- ``inputs/aug300_train.jsonl``(J3): aug300 train 220(같은 형식).
holdout·제외·축소 문항은 넣지 않는다.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from training.data.common import read_jsonl  # noqa: E402
from training.data.split import question_key  # noqa: E402

AUG = ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_300.jsonl"
B007 = ROOT / "sft_dpo_inventory/batch007/candidates_checked.json"
PG_RR_BLOB = "ab9d215:sft_dpo_inventory/reviewed_reasoning_v001/dataset.jsonl"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import evaluate_vendor100 as EV
    p = argparse.ArgumentParser()
    p.add_argument("--pg-rr", required=True)
    args = p.parse_args()
    aug = [{"id": i["id"], "source": "aug300_train", "question": i["question"], "gold_grounding": EV.derive_grounding(i["gold"]),
            "gold_kind": "aug300 정답 호출 역산(execution 층)"} for i in read_jsonl(AUG) if i["status"] == "train"]
    pg = []
    for row in read_jsonl(args.pg_rr):
        meta = row["metadata"]
        pg.append({"id": f"pg-rr-{meta['source_record_id']}", "source": "pg_reviewed_reasoning_v001",
                   "question": next(m["content"] for m in row["messages"] if m["role"] == "user"),
                   "gold_grounding": meta.get("target_full"), "gold_kind": "partial-grounding target_full(승인 상태 그대로, PG)"})
    b7 = [{"id": c["id"], "source": "batch007_draft", "question": c["question"], "gold_grounding": c["draft_grounding"],
           "gold_kind": "batch007 초안(승인 아님)"} for c in json.loads(B007.read_text(encoding="utf-8"))["candidates"]]
    seen, rows, dups = {}, [], []
    for r in aug + pg + b7:
        k = question_key(r["question"])
        if k in seen:
            dups.append({"id": r["id"], "duplicate_of": seen[k]})
            continue
        seen[k] = r["id"]
        rows.append(r)
    (HERE / "inputs").mkdir(exist_ok=True)
    with open(HERE / "inputs/self_questions.jsonl", "w", encoding="utf-8") as out:
        for r in rows:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(HERE / "inputs/aug300_train.jsonl", "w", encoding="utf-8") as out:
        for r in aug:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    meta = {"self_questions": len(rows), "by_source": {s: sum(r["source"] == s for r in rows) for s in ("aug300_train", "pg_reviewed_reasoning_v001", "batch007_draft")},
            "duplicates_dropped": dups, "aug300_train": len(aug),
            "sources": {"aug300": {"path": str(AUG.relative_to(ROOT)), "sha256": sha(AUG)},
                        "pg_reviewed_reasoning_v001": {"blob": PG_RR_BLOB, "sha256": sha(args.pg_rr)},
                        "batch007": {"path": str(B007.relative_to(ROOT)), "sha256": sha(B007)}},
            "outputs": {n: sha(HERE / "inputs" / n) for n in ("self_questions.jsonl", "aug300_train.jsonl")}}
    (HERE / "inputs/inputs_manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
