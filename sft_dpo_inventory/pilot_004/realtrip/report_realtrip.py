# -*- coding: utf-8 -*-
"""실차 표본 수집 결과를 문항별로 정리한다(결정 98). 모델 호출 없음.

    python sft_dpo_inventory/pilot_004/realtrip/report_realtrip.py

- 입력: ``targets.json``, ``summary.json``, ``realtrip_filtered.json``, 서버 요청 로그 요약(``request_log.json``).
- 문항별: 정답 표본 수(32 중), 필터 뒤 SFT 후보 수, 필터 뒤 DPO 쌍 수, 결정 52 상한(질문당 8쌍) 뒤 DPO 쌍 수.
  상한은 pilot_003 builder의 ``cap_pairs``와 같은 함수이고, seed 순번은 pilot_003 DPO 질문(53개) 뒤에 이어서 붙인다
  (기존 질문의 상한 선택이 바뀌지 않게, build_pilot004와 같은 규칙).
- 결과: ``realtrip_report.json``.
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_003/data"))
import build_pilot003 as B  # noqa: E402

P3_DPO_QUESTIONS = 53


def main():
    targets = json.loads((HERE / "targets.json").read_text(encoding="utf-8"))
    summ = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))
    filt = json.loads((HERE / "realtrip_filtered.json").read_text(encoding="utf-8"))
    cands = json.loads((HERE / "candidates.json").read_text(encoding="utf-8"))
    kept_pairs = {(p["chosen"], p["rejected"]) for p in filt["dpo_kept_pairs"]}
    by_q = defaultdict(list)
    for c in cands["dpo"]:
        if (c["chosen"], c["rejected"]) in kept_pairs:
            by_q[c["source_record_id"]].append(c)
    capped = {}
    for i, sid in enumerate(sorted(by_q)):
        capped[sid] = B.cap_pairs(by_q[sid], random.Random(B.SEED + P3_DPO_QUESTIONS + i))
    q = {r["source_record_id"]: r for r in summ["questions"]}
    rows = []
    for t in targets:
        if not t["target"]:
            continue
        sid = t["source_record_id"]
        rows.append({"source_record_id": sid, "variant": t["variant"], "correct_samples_of_32": q[sid]["correct_samples"],
                     "unique_correct": q[sid]["unique_correct"], "unique_wrong": q[sid]["unique_wrong"],
                     "sft_candidates_after_filters": filt["sft_per_question"].get(sid, 0),
                     "dpo_pairs_after_filters": filt["dpo_per_question"].get(sid, 0),
                     "dpo_pairs_after_decision52_cap": len(capped.get(sid, [])),
                     "truncated": q[sid]["truncated"], "no_correct": q[sid]["correct_samples"] == 0})
    rl = json.loads((HERE / "request_log.json").read_text(encoding="utf-8")) if (HERE / "request_log.json").exists() else None
    out = {"targets": len(rows), "questions_with_correct": sum(not r["no_correct"] for r in rows),
           "still_no_correct": [r["source_record_id"] for r in rows if r["no_correct"]],
           "totals": {k: sum(r[k] for r in rows) for k in ("correct_samples_of_32", "sft_candidates_after_filters",
                                                            "dpo_pairs_after_filters", "dpo_pairs_after_decision52_cap")},
           "by_variant": {v: {k: sum(r[k] for r in rows if r["variant"] == v) for k in
                              ("correct_samples_of_32", "sft_candidates_after_filters", "dpo_pairs_after_decision52_cap")}
                          | {"questions": sum(r["variant"] == v for r in rows)} for v in sorted({r["variant"] for r in rows})},
           "filter_steps": filt["filter_steps"], "request_log": rl, "rows": rows}
    (HERE / "realtrip_report.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("targets", "questions_with_correct", "still_no_correct", "totals", "by_variant", "filter_steps")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
