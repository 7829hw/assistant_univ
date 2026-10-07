# -*- coding: utf-8 -*-
"""결정 48: 기존 teacher 17문항의 정답 trace에 질문당 4개 상한을 적용하고, 사람 검토용 표본 10개 문서를 만든다. 모델을 부르지 않는다.

    python sft_dpo_inventory/pilot_prep_005/teacher/select_teacher.py

- 후보: ``pilot_prep_004/teacher_scale/teacher_scale.json``에서 모든 필터(결정 4 대신 쓴 tokenize 왕복·렌더 경계, 계약 필터,
  결정 18 길이, 결정 40-D 루프)를 통과한 정답 trace 121개. 그 계산의 입력 trace 파일 sha256이 지금 파일과 같은지 확인한다.
- 상한: 질문 id 정렬 순서로 ``random.Random(SEED + 순번).sample(질문의 통과 trace id 정렬 목록, min(4, 개수))``.
- 교차 DPO 쌍(27b chosen × 8b rejected)은 만들지 않는다(결정 48).
- 사람 검토 표본: 고른 trace에서 ``random.Random(REVIEW_SEED).sample(정렬 목록, 10)``. 문서
  ``training/generated/thinking_traces/teacher/human_review_teacher_10.md``(ignore 경로, 커밋하지 않음)의 형식은
  ``v003_t2pc_train/human_review_10.md``와 같다: 맨 위 검토 기준 4개, 표본마다 질문, gold, 추론 원문 전체, 최종 JSON 원문,
  판정 정보, 검토 칸. gold는 지금 학습 corpus(``reviewed_gold_v005_t2pc``)의 기록이다.
- 출력(커밋): ``selected_teacher.json``(고른 trace id 목록, 질문별 수, 표본 id, 검토 문서 sha256).
"""
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

SCALE = ROOT / "sft_dpo_inventory/pilot_prep_004/teacher_scale/teacher_scale.json"
CORPUS = ROOT / "training/generated/reviewed_gold_v005_t2pc/sft_train.jsonl"
REVIEW = ROOT / "training/generated/thinking_traces/teacher/human_review_teacher_10.md"
CAP = 4
SEED = 20261008
REVIEW_SEED = 48

CRITERIA = """## 검토 기준

1. 측정값과 사건을 계약대로 고른 이유를 대는가.
2. 안쪽 집계·구간·바깥 집계(또는 dimension·순위)를 질문의 어느 말에서 읽었는지 맞게 설명하는가.
3. 질문에 없는 조건을 만들거나, 있는 조건을 버리는 추론이 있는가.
4. 추론의 결론과 최종 JSON이 어긋나는가.
"""


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def fence(lang, text):
    return f"````{lang}\n{text}\n````"


def main():
    scale = json.loads(SCALE.read_text(encoding="utf-8"))
    for path, digest in scale["inputs"].items():
        if sha256(ROOT / path) != digest:
            raise SystemExit(f"teacher_scale 입력이 바뀌었다: {path}")
    kept = [r for r in scale["rows"] if r["excluded"] is None]
    if len(kept) != scale["sft_kept"] or len(kept) != 121:
        raise SystemExit("필터 통과 teacher trace 수가 기록(121)과 다르다")
    by_q = defaultdict(list)
    for r in kept:
        by_q[r["source_record_id"]].append(r["trace_id"])
    selected = {}
    for index, sid in enumerate(sorted(by_q)):
        ids = sorted(by_q[sid])
        selected[sid] = sorted(random.Random(SEED + index).sample(ids, min(CAP, len(ids))))
    chosen = sorted(t for ids in selected.values() for t in ids)
    review_ids = sorted(random.Random(REVIEW_SEED).sample(chosen, 10))

    traces, source_of = {}, {}
    for path in scale["inputs"]:
        for row in read(ROOT / path):
            traces[row["trace_id"]] = row
            source_of[row["trace_id"]] = path
    gold = {r["metadata"]["source_record_id"]: r for r in read(CORPUS)}
    group = {r["trace_id"]: r["group"] for r in kept}
    tokens = {r["trace_id"]: r for r in kept}
    parts = ["# teacher trace 사람 검토 10건(결정 48)", "",
             "- 원본(teacher, Ollama qwen3.8:27b): " + ", ".join(f"`{p}` (sha256 `{d[:16]}…`)" for p, d in scale["inputs"].items())
             + ". `pilot_prep_004/teacher_scale/teacher_scale.json`의 inputs와 일치 확인.",
             f"- 대상: 질문당 4개 상한으로 고른 {len(chosen)}개(`pilot_prep_005/teacher/selected_teacher.json`)에서 "
             f"`random.Random({REVIEW_SEED}).sample` 10개(id 정렬 순서).",
             "- gold: `training/generated/reviewed_gold_v005_t2pc/sft_train.jsonl`의 정답(지금 학습 corpus). 처음 들어온 판을 함께 적는다.",
             "- 추론과 최종 JSON은 생성 원문 그대로다(Ollama 응답의 thinking과 content). 요약하거나 고치지 않았다.",
             "- 판정 기준은 결정 23과 같다. 채점(`grounding_check`)이 보는 핵심 필드(측정값·사건, 집계 구조, 조건, 장소 값)에서 추론이 "
             "틀렸는데 JSON만 맞으면 \"우연히 정답\"이고, 채점이 보지 않는 필드(role, answer, source, id, text)의 오류는 \"경미\"로 둔다. "
             "결과는 결정 27과 같은 방식으로 반영한다(\"우연히 정답\" trace를 학습에서 뺀다).",
             "- 이 파일은 ignore 경로에 있고 커밋하지 않는다.", "", CRITERIA, "---", ""]
    for n, tid in enumerate(review_ids, 1):
        row = traces[tid]
        sid = row["source_record_id"]
        record = gold[sid]
        meta = record["metadata"]
        g = json.loads(record["messages"][-1]["content"])
        v = row["verdict"]
        first = meta.get("source_version") or meta.get("corpus_version")
        parts += [f"## {n}. `{tid}`", "", f"**질문:** {record['messages'][1]['content']}", "",
                  f"### gold grounding (reviewed_gold_v005_t2pc 기록, 처음 들어온 판: {first})", "",
                  fence("json", json.dumps(g, ensure_ascii=False, indent=2, sort_keys=True)), "",
                  "### 추론 원문(thinking)", "", fence("text", row["thinking"]), "",
                  "### 최종 JSON 원문", "", fence("json", row["content"]), "",
                  "### 판정 정보", "",
                  f"- gold 일치(조건 계층 전 원 출력): {'예' if v['raw_match'] else '아니오'}",
                  "- 조건 계층 뒤 일치: " + ("해당 없음(원 출력이 이미 일치)" if v["raw_match"] else str(v.get("after_condition_match"))),
                  f"- 생성 token 수: Ollama eval_count {row.get('eval_count')}, Qwen3-8B tokenizer 기준 응답 "
                  f"{tokens[tid]['response_tokens']} (done_reason {row.get('done_reason')})",
                  f"- 종류: teacher 표본 {row.get('sample_index')}, seed {row.get('seed')}, 모델 {row.get('model')} "
                  f"({row.get('model_digest', '')[:12]}), think {row.get('think')}, temperature {row.get('options', {}).get('temperature')}",
                  f"- 묶음: {group[tid]} (`{source_of[tid]}`)",
                  "- 필터: tokenize 왕복·렌더 경계, 계약, 길이, 루프 모두 통과",
                  "", "### 검토", "", "추론 판정: [ ] 타당 / [ ] 타당(경미) / [ ] 우연히 정답 / [ ] 판단 불가", "", "메모:", "", "", "---", ""]
    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    REVIEW.write_text("\n".join(parts), encoding="utf-8")
    out = {"decision": "48", "cap_per_question": CAP, "seed": SEED, "review_seed": REVIEW_SEED,
           "source": str(SCALE.relative_to(ROOT)), "source_sha256": sha256(SCALE), "inputs": scale["inputs"],
           "candidates": len(kept), "selected": len(chosen),
           "per_question": {sid: {"group": next(r["group"] for r in kept if r["source_record_id"] == sid),
                                  "passed": len(by_q[sid]), "selected": len(selected[sid])} for sid in sorted(by_q)},
           "selected_trace_ids": selected, "cross_model_dpo_pairs": "not built (decision 48)",
           "human_review_sample_trace_ids": review_ids,
           "human_review_doc": str(REVIEW.relative_to(ROOT)), "human_review_doc_sha256": sha256(REVIEW),
           "human_review_doc_committed": False, "reasoning_text_human_reviewed": False}
    (HERE / "selected_teacher.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("candidates", "selected", "human_review_sample_trace_ids", "human_review_doc_sha256")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
