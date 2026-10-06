# -*- coding: utf-8 -*-
"""v004 thinking 데이터에 결정 27을 적용한 새 판(thinking_v004_t2pc_r1)을 만든다. 모델·GPU를 쓰지 않는다.

    python sft_dpo_inventory/pilot_001/data/build_v004_r1.py

- 입력(고치지 않는다): ``pilot_prep_003/data/candidates_v004.json``(v004에 쓴 후보), 합친 trace
  ``training/generated/pilot_prep_003/combined_traces.jsonl``, gold ``reviewed_gold_v004_t2pc``.
- 결정 27: 결정 23에서 "우연히 정답"으로 판정한 trace 2개를 SFT 후보에서 빼고, 그 trace가 chosen인 DPO 쌍도 뺀다.
  검토하지 않은 다른 trace는 그대로 둔다. 그 밖의 처리(결정 4·6·7·18, 계약 필터)는 v004와 같고 같은 builder를 쓴다.
- 기록: 빠진 SFT 레코드·DPO 쌍 수, 질문별로 남은 SFT 수, 제외로 SFT 후보가 없어진 질문, 학습 SFT 레코드 중 장소 role이 gold와
  다른 레코드 수(결정 25에 따라 빼지 않는다, 정보용).
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

GEN = ROOT / "training/generated"
SOURCE = ROOT / "sft_dpo_inventory/pilot_prep_003/data/candidates_v004.json"
TRACES = GEN / "pilot_prep_003/combined_traces.jsonl"
CORPUS = GEN / "reviewed_gold_v004_t2pc"
PREVIOUS = GEN / "thinking_v004_t2pc"
OUT = GEN / "thinking_v004_t2pc_r1"
EXCLUDED = {"ann-d983889cf8c496178106:sample:7": "결정 23: 우연히 정답(bucket에서 rollup을 끌어내는 틀린 인과)",
            "ann-ea359d5569ef6070f9e4:sample:3": "결정 23: 우연히 정답(추론은 region 하늘구, JSON은 빈 값)"}


def location_roles(payload):
    return sorted((c.get("value") or {}).get("name", "") + ":" + str(c.get("role"))
                  for c in payload.get("concepts") or [] if c.get("concept") == "LOCATION" and isinstance(c.get("value"), dict))


def main():
    from training.data import build_thinking, thinking
    from training.data.common import read_jsonl
    if OUT.exists():
        raise SystemExit("output exists")
    cands = json.loads(SOURCE.read_text(encoding="utf-8"))
    sft = [c for c in cands["sft"] if c["trace_id"] not in EXCLUDED]
    dpo = [c for c in cands["dpo"] if c["chosen"] not in EXCLUDED]
    removed = {"sft_candidates": len(cands["sft"]) - len(sft), "dpo_candidates(chosen excluded)": len(cands["dpo"]) - len(dpo),
               "dpo_candidates(rejected is excluded trace, kept)": sum(c["rejected"] in EXCLUDED for c in dpo)}
    filtered = HERE / "candidates_v004_r1.json"
    filtered.write_text(json.dumps({"sft": sft, "dpo": dpo}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    built = build_thinking.build(TRACES, filtered, CORPUS, "train", OUT)
    rows = read_jsonl(OUT / "sft_train.jsonl")
    pairs = read_jsonl(OUT / "dpo_train.jsonl")
    old_rows = read_jsonl(PREVIOUS / "sft_train.jsonl")
    old_pairs = read_jsonl(PREVIOUS / "dpo_train.jsonl")
    per_q_old = Counter(r["metadata"]["source_record_id"] for r in old_rows)
    per_q = Counter(r["metadata"]["source_record_id"] for r in rows)
    gold = {r["metadata"]["source_record_id"]: json.loads(r["messages"][2]["content"]) for r in read_jsonl(CORPUS / "sft_train.jsonl")}
    role_diff = []
    for r in rows:
        sid = r["metadata"]["source_record_id"]
        got = location_roles(thinking.response_json(r["messages"][-1]["content"]))
        want = location_roles(gold[sid])
        if got != want:
            role_diff.append({"trace_id": r["metadata"]["trace_id"], "gold": want, "trace": got})
    summary = {
        "decision": "27", "excluded_traces": EXCLUDED, "removed": removed,
        "records": {"sft_before": len(old_rows), "sft_after": len(rows), "sft_removed": len(old_rows) - len(rows),
                    "dpo_before": len(old_pairs), "dpo_after": len(pairs), "dpo_removed": len(old_pairs) - len(pairs)},
        "sft_per_question": {sid: {"before": per_q_old[sid], "after": per_q.get(sid, 0)} for sid in sorted(per_q_old)},
        "questions_without_sft_after_exclusion": sorted(sid for sid in per_q_old if per_q.get(sid, 0) == 0),
        "sft_questions": len(per_q), "dpo_questions": len({p["metadata"]["source_record_id"] for p in pairs}),
        "location_role_differs_from_gold(decision 25, kept)": {"records": len(role_diff),
                                                                "of_records_with_location": sum(
                                                                    1 for r in rows if location_roles(gold[r["metadata"]["source_record_id"]])),
                                                                "items": role_diff},
        "build": built,
        "output": str(OUT.relative_to(ROOT)),
        "output_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir())},
    }
    (HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("removed", "records", "questions_without_sft_after_exclusion",
                                              "sft_questions", "dpo_questions")}, ensure_ascii=False, indent=1))
    print("role differs:", len(role_diff))


if __name__ == "__main__":
    main()
