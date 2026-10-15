# -*- coding: utf-8 -*-
"""pilot_006 PLAN 초안의 데이터 구성 추정(질문 단위, 모델 호출 없음). 추정이고 고정이 아니다.

    hfvenv/bin/python sft_dpo_inventory/pilot_006/plan_estimates.py

- 후보 질문 풀(계획서 v2 7절, 승인 여부와 무관하게 "승인되면 들어올 수 있는" 최대치):
  trunk pilot_004 판 131 ∪ pg reviewed_reasoning_v001 154(질문 기준 중복 제거: v005 111은 trunk와 같은 질문) ∪ aug300 train 220
  ∪ batch007 27(검토 전) ∪ batch008 남은 10(검토 전).
- 유형 칸: ``pilot_prep_004/type_target.profile``(집계·dimension·dimension_target 유무), 개발 분포 ``type_target.json``, 상한 ``type_caps.caps_for``(τ 0.09).
  결정 92 예외(실차 대조 묶음)는 trunk batch006 실차 대조 질문과 batch007(같은 계열, 결정 104)로 둔다(추정 가정).
- canonical 검증 통과 수는 ``pilot_006_prep/canonical/validation_summary.json``과 ``aug300_review/semantics_draft_summary.json``에서 읽는다.
출력: ``plan_estimates.json``.
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_004_prep"))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_prep_004/type_target"))

from grounding.full_renderer import render_full  # noqa: E402
from training.data.common import read_jsonl  # noqa: E402
from training.data.split import question_key  # noqa: E402


def main():
    import type_caps as TC
    from type_target import profile, tv
    dev = json.loads((ROOT / "sft_dpo_inventory/pilot_prep_004/type_target/type_target.json").read_text(encoding="utf-8"))["dev_distribution"]["share"]
    canon = read_jsonl(ROOT / "sft_dpo_inventory/pilot_006_prep/canonical/canonical_records.jsonl")
    drafts = read_jsonl(ROOT / "sft_dpo_inventory/pilot_006_prep/aug300_review/semantics_draft.jsonl")
    b8 = json.loads((ROOT / "sft_dpo_inventory/batch008/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    b6 = json.loads((ROOT / "sft_dpo_inventory/batch006/candidates_checked.json").read_text(encoding="utf-8"))["candidates"]
    realtrip = {c["id"] for c in b6 if c.get("variant")}
    pool, seen = [], {}
    order = [("t2pc_v006", [r for r in canon if r["source"] == "t2pc_v006"]), ("pg_reasoning_v001", [r for r in canon if r["source"] == "pg_reasoning_v001"]),
             ("aug300_train", [r for r in drafts if r["provenance"]["status_d1"] == "train"]),
             ("batch007_draft", [r for r in canon if r["source"] == "batch007_draft"])]
    for source, recs in order:
        for r in recs:
            qk = question_key(r["question"])
            if qk in seen:
                continue
            seen[qk] = source
            sid = r["provenance"].get("source_record_id") or r["id"]
            exempt = (source == "t2pc_v006" and sid in realtrip) or source == "batch007_draft"
            pool.append({"source": source, "id": r["id"], "cell": profile(render_full(r["semantics"]))["cell"], "exempt": exempt,
                         "chain_ok": r["validation"]["ok"], "mock_answered": r["validation"]["full_answered"]})
    for c in b8:
        if question_key(c["question"]) in seen:
            continue
        pool.append({"source": "batch008_draft", "id": c["id"], "cell": profile(c["draft_grounding"])["cell"], "exempt": False,
                     "chain_ok": c["validation_chain"]["ok"], "mock_answered": c["validation_chain"]["full_answered"]})
    avail = Counter(p["cell"] for p in pool if not p["exempt"])
    exempt_n = Counter(p["cell"] for p in pool if p["exempt"])
    m, caps = TC.caps_for(dict(avail), dev, 0.09)
    kept_cells = Counter({c: min(avail[c], caps.get(c, 0)) for c in avail}) + exempt_n
    total = sum(kept_cells.values())
    share_before = {c: v / len(pool) for c, v in Counter(p["cell"] for p in pool).items()}
    share_after = {c: v / total for c, v in kept_cells.items()}
    out = {"pool_questions": len(pool), "by_source": dict(Counter(p["source"] for p in pool)),
           "chain_ok": dict(Counter(f"{p['source']}:{p['chain_ok']}" for p in pool)),
           "pool_cells": dict(Counter(p["cell"] for p in pool)), "dev_share": dev,
           "tv_before_cap": round(tv(share_before, dev), 4), "exempt_questions": sum(exempt_n.values()),
           "caps_non_exempt": caps, "kept_questions_estimate": total, "kept_cells": dict(kept_cells),
           "tv_after_cap_estimate": round(tv(share_after, dev), 4),
           "dropped_by_source_estimate": "칸 안에서 어느 질문을 뺄지는 seed 순서(다음 세션 데이터 판 생성 때)",
           "assumptions": ["모든 후보가 승인된다고 본 최대치", "batch007은 결정 92 예외 계열로 봄", "레코드 단위 상한은 trace 수집 뒤에 정한다"]}
    (HERE / "plan_estimates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
