# -*- coding: utf-8 -*-
"""결정 120(E5): 약한 겹침만으로 뺀 batch008 20건을 다시 분류한다. 모델 호출 없음.

    hfvenv/bin/python sft_dpo_inventory/batch008/apply_e5.py

- 계속 뺀다: selection_v2, augmentation_holdout_v1, valid98, aux_test_v1 중 하나와 family 수준 겹침.
- 되살린다: 위가 아니고, 남은 약한 겹침이 업체 100뿐이거나(D1로 개발 셋) template 수준뿐일 때(결정 54식 예외로 기록).
- 그 밖(selection_v1·thor 보호 원본·확장 family처럼 위 넷에 속하지 않는 family 겹침만 남음): 결정 120의 두 경우 어디에도 정확히 들지 않으므로
  **빼 둔 채 "분류 밖"으로 보고**한다(사용자 확인).
출력: ``e5_reclassification.json``, ``inputs_first_response_revived.jsonl``(J7b 입력).
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from training.annotations.inventory import family_key  # noqa: E402
from training.data.common import read_jsonl  # noqa: E402

KEEP_OUT = ("selection_v2", "holdout", "valid98", "aux_test_v1")


def weak(w):
    return w.endswith((":template", ":family")) or w.startswith(("extended_", "thor:protected_semantic"))


def main():
    import evaluate_vendor100 as EV
    hold = {i["id"] for i in json.loads((ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/holdout_v1.json").read_text(encoding="utf-8"))["list"]}
    hold_f = {family_key(EV.derive_grounding(i["gold"])) for i in read_jsonl(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_300.jsonl")
              if i["id"] in hold}
    ex = json.loads((HERE / "excluded.json").read_text(encoding="utf-8"))
    rows, revived = [], []
    for r in ex:
        reasons = r["excluded_reasons"]
        if not all(weak(w) for w in reasons):
            continue
        fam = {n for n, e in r["leakage"]["per_set"].items() if e["family"]}
        tmpl = {n for n, e in r["leakage"]["per_set"].items() if e["template"]}
        if r["family_key"] in hold_f:
            fam.add("holdout")
        hits = sorted(fam & set(KEEP_OUT))
        other_family = [w for w in reasons if w.endswith(":family") and w.split(":")[0] not in ("vendor100",) and w.split(":")[0] not in KEEP_OUT]
        other_family += [w for w in reasons if w in ("extended_family", "thor:protected_semantic_family")]
        if hits:
            decision, why = "계속 뺌", f"family 겹침: {', '.join(hits)}"
        elif not other_family:
            decision, why = "되살림", "업체 100만 또는 template 수준만 겹침(결정 54식 예외, 결정 120)"
        else:
            decision, why = "분류 밖(빼 둔 채 보고)", f"넷 밖의 family 겹침만: {', '.join(sorted(set(other_family)))}"
        row = {"id": r["id"], "gap": r["gap"], "question": r["question"], "decision": decision, "why": why,
               "family_sets": sorted(fam), "template_sets": sorted(tmpl), "reasons": reasons}
        rows.append(row)
        if decision == "되살림":
            revived.append(r)
    (HERE / "e5_reclassification.json").write_text(json.dumps({"decision": "120(BG, E5)", "rows": rows,
                                                               "counts": {d: sum(x["decision"] == d for x in rows) for d in {x["decision"] for x in rows}}},
                                                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with open(HERE / "inputs_first_response_revived.jsonl", "w", encoding="utf-8") as out:
        for r in revived:
            out.write(json.dumps({"id": r["id"], "source": "batch008_draft_revived_e5", "question": r["question"], "gold_grounding": r["draft_grounding"],
                                  "gold_kind": "batch008 초안(승인 아님), 결정 120으로 되살림"}, ensure_ascii=False) + "\n")
    for x in rows:
        print(x["id"], x["gap"][:2], x["decision"], "|", x["why"])


if __name__ == "__main__":
    main()
