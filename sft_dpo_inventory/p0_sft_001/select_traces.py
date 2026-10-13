# -*- coding: utf-8 -*-
"""Clean-Hybrid용 trace를 문항당 하나만 고른다(결정 68, 실행 전 고정). 모델 호출 없음.

    python sft_dpo_inventory/p0_sft_001/select_traces.py

- 후보: `evaluation/partial_grounding/sft_p0/trace_quality.json`의 `after_filters_trace_ids`(307).
  이 목록의 조건은 다음과 같고, 같은 질문의 같은 원문은 먼저 나온 것 하나만 남아 있다.
  - EXACT_OR_SEMANTIC_MATCH
  - thinking 원문 있음(닫힘·비어 있지 않음)
  - 결정 4 tokenize 왕복 통과(done_reason stop 포함, truncation 없음)
  - 결정 40-D 루프 아님
  - 결정 18 길이 이내
- 우선순위(지시 5절): 위 조건을 모두 만족하는 trace 중 greedy가 있으면 greedy, 없으면 sample_index가 가장 작은 표본.
  sampling seed는 질문마다 하나(20261006 + 순번)라 sample_index가 표본 순서를 정한다.
- trace 내용(추론의 질)은 선택에 쓰지 않는다. 사람 검토 결과 REJECT_TRACE가 나와도 다른 표본으로 바꾸지 않는다(지시 9절).
출력: `selected_traces.jsonl`(질문당 1줄: trace id, item id, question, thinking, content, gold P0 target).
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TRACES = ROOT / "training/generated/thinking_traces/p0_v006_hf/traces.jsonl"
QUALITY = ROOT / "evaluation/partial_grounding/sft_p0/trace_quality.json"
DATASET = ROOT / "training/generated/reviewed_gold_v006_p0/sft_train.jsonl"


def main():
    quality = json.loads(QUALITY.read_text(encoding="utf-8"))
    if hashlib.sha256(TRACES.read_bytes()).hexdigest() != quality["traces_sha256"]:
        raise SystemExit("trace 파일 hash가 trace_quality.json과 다르다")
    eligible = set(quality["adoption"]["after_filters_trace_ids"])
    rows = {r["trace_id"]: r for r in (json.loads(x) for x in TRACES.read_text(encoding="utf-8").splitlines() if x.strip())}
    gold = {}
    for x in DATASET.read_text(encoding="utf-8").splitlines():
        r = json.loads(x)
        gold[r["metadata"]["source_record_id"]] = r
    by_q = {}
    for tid in eligible:
        r = rows[tid]
        if r["judge"]["category"] != "EXACT_OR_SEMANTIC_MATCH" or not r["think_closed"] or r["done_reason"] != "stop":
            raise SystemExit(f"{tid}: 후보 조건 위반")
        by_q.setdefault(r["item_id"], []).append(r)
    out = []
    for qid in gold:                                   # 데이터셋 순서
        cands = by_q.get(qid)
        if not cands:
            continue
        pick = min(cands, key=lambda r: (r["kind"] != "greedy", r["sample_index"]))
        out.append({"trace_id": pick["trace_id"], "item_id": qid, "kind": pick["kind"], "sample_index": pick["sample_index"],
                    "seed": pick["seed"], "source": gold[qid]["metadata"]["source"], "question": pick["question"],
                    "thinking": pick["thinking"], "content": pick["content"], "raw_sha256": pick["raw_sha256"],
                    "exact_json": pick["judge"]["exact_json"],
                    "gold_p0": json.loads(gold[qid]["messages"][2]["content"]), "candidates": len(cands)})
    with open(HERE / "selected_traces.jsonl", "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps({"eligible_traces": len(eligible), "questions_with_trace": len(out),
                      "questions_without": len(gold) - len(out),
                      "greedy": sum(r["kind"] == "greedy" for r in out),
                      "by_source": {s: sum(r["source"] == s for r in out) for s in {r["source"] for r in out}}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
