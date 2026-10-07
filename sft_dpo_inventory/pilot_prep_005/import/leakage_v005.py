# -*- coding: utf-8 -*-
"""reviewed_gold_v005_t2pc의 모든 SFT 레코드를 보호 대상과 다시 대조한다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_005/import/leakage_v005.py

- thor 보호: ``Protection.current(reviewed_gold_v004_t2pc).reasons``(정규화 질문, id, semantic template, semantic family).
  ``merge_v005.py``가 이미 통과시킨 검사를 레코드별 결과로 남긴다.
- 확장 대조(batch004·batch005와 같은 ``extended_fingerprints``): vendor 형식 보호 셋의 정답 grounding에서 만든 template·family.
  v004의 b004-05, 06, 15, 30, 31은 결정 15로 업체 100 family 겹침을 알고 학습에 쓰기로 한 문항이다.
- 출력: ``leakage_v005.json``(id·사유·출처 셋 이름만, 질문 문장 없음).
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/batch004"))

from build_candidates import extended_fingerprints  # noqa: E402
from training.annotations.inventory import Protection, as_record, family_key  # noqa: E402
from training.data.common import read_jsonl, sha256  # noqa: E402
from training.data.split import template_key  # noqa: E402

GEN = ROOT / "training/generated"
V005 = GEN / "reviewed_gold_v005_t2pc"
DECISION15 = {"b004-05", "b004-06", "b004-15", "b004-30", "b004-31"}


def main():
    guard = Protection.current(GEN / "reviewed_gold_v004_t2pc")
    ext_t, ext_f = extended_fingerprints()
    rows = []
    for r in read_jsonl(V005 / "sft_train.jsonl"):
        meta = r["metadata"]
        payload = json.loads(r["messages"][-1]["content"])
        reasons = guard.reasons(r["messages"][1]["content"], payload,
                                [meta.get("parent_intent"), meta.get("family"), meta.get("source_record_id")])
        ext = {"template": sorted(ext_t.get(template_key(as_record(payload)), ())),
               "family": sorted(ext_f.get(family_key(payload), ()))}
        rows.append({"id": meta["source_record_id"], "origin": meta["corpus_origin_v005"], "thor_reasons": sorted(set(reasons)),
                     "extended": ext, "decision15_known": meta["source_record_id"] in DECISION15})
    hit = [r for r in rows if r["extended"]["template"] or r["extended"]["family"]]
    out = {"corpus": str(V005.relative_to(ROOT)), "sft_train_sha256": sha256(V005 / "sft_train.jsonl"),
           "records": len(rows), "thor_blocked": [r["id"] for r in rows if r["thor_reasons"]],
           "extended_overlap": {"total": len(hit), "by_origin": dict(Counter(r["origin"] for r in hit)),
                                "decision15_known": sorted(r["id"] for r in hit if r["decision15_known"]),
                                "other": [{k: r[k] for k in ("id", "origin", "extended")} for r in hit if not r["decision15_known"]]},
           "rows": rows}
    (HERE / "leakage_v005.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("records", "thor_blocked", "extended_overlap")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
