# -*- coding: utf-8 -*-
"""검토 결정(review_decisions.json)을 초안에 적용해 승인 후보 파일을 만든다(모델 호출 없음).

    /data/hwkim/path_repeat_001/venv/py/bin/python sft_dpo_inventory/batch006/apply_review.py

- 원문 `candidates_draft.yaml`은 고치지 않는다. 수정은 review_decisions.json의 revision을 여기서만 적용한다.
  - `question`: 새 질문 문장.
  - `concept_text`: concept id → 새 text(null이면 text 삭제).
- 출력 `approved.jsonl`: final이 approve·approve_after_recheck인 후보. Full gold가 canonical source다(P0는 check에서 변환).
  EDIT_REQUIRED 후보는 이 파일로 `check_candidates.py --source approved.jsonl`을 다시 통과해야 v006에 들어간다.
"""
import copy
import json
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SOURCE = {"A": "augment_dt_event", "B": "augment_od_vs_dt", "C": "augment_scope_reverse"}


def main():
    drafts = {c["id"]: c for c in yaml.safe_load((HERE / "candidates_draft.yaml").read_text(encoding="utf-8"))["candidates"]}
    review = json.loads((HERE / "review_decisions.json").read_text(encoding="utf-8"))
    rows = []
    for d in review["items"]:
        if d["final"] not in ("approve", "approve_after_recheck"):
            continue
        c = copy.deepcopy(drafts[d["id"]])
        rev = d.get("revision") or {}
        original = {"question": c["question"]}
        if "question" in rev:
            c["question"] = rev["question"]
        for cid, text in (rev.get("concept_text") or {}).items():
            concept = next(x for x in c["gold"]["concepts"] if x["id"] == cid)
            original.setdefault("concept_text", {})[cid] = concept.get("text")
            if text is None:
                concept.pop("text", None)
            else:
                concept["text"] = text
        for x in c["gold"]["concepts"]:
            if x.get("text") and x["text"] not in c["question"]:
                raise SystemExit(f"{d['id']}: concept text {x['text']!r}가 질문에 없다")
        rows.append({"id": c["id"], "gap": c["gap"], "pair": c.get("pair") if d.get("pair_valid") else None,
                     "pair_draft": c.get("pair"), "question": c["question"], "rationale": c["rationale"],
                     "gold": c["gold"], "review_decision": d["decision"], "edited": d["edited"],
                     "original": original if d["edited"] else None,
                     "provenance": {"source": SOURCE[c["gap"]], "batch": "b006", "dataset_version": "reviewed_gold_v006_p0",
                                    "draft": "sft_dpo_inventory/batch006/candidates_draft.yaml",
                                    "review": "sft_dpo_inventory/batch006/review_decisions.json"}})
    with open(HERE / "approved.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps({"approved_rows": len(rows), "edited": sum(r["edited"] for r in rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
