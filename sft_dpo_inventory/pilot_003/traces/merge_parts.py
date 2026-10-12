# -*- coding: utf-8 -*-
"""GPU별로 나눠 모은 batch006 trace(``collect_traces.py --range``)를 하나로 합친다. 모델 호출 없음.

    python sft_dpo_inventory/pilot_003/traces/merge_parts.py

- 입력: ``training/generated/thinking_traces/batch006/part{0..3}/traces.jsonl``(ignore), ``traces/batch006/part{0..3}/summary.json``·``candidates.json``.
- 각 part의 traces sha256을 그 summary와 대조한다. 질문 번호(qi)가 겹치거나 빠지면 멈춘다.
- 출력: ``training/generated/thinking_traces/batch006/traces.jsonl``(질문 순서대로 이어 붙임, ignore),
  ``traces/batch006/summary.json``·``candidates.json``(collect_traces와 같은 형식, part별 장치·범위를 ``parts``에 남긴다).
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TRACES = ROOT / "training/generated/thinking_traces/batch006"
SUMMARY = HERE / "batch006"
PARTS = 4


def main():
    rows, questions, sft, dpo, parts, review = [], [], [], [], [], []
    base = None
    for i in range(PARTS):
        s = json.loads((SUMMARY / f"part{i}/summary.json").read_text(encoding="utf-8"))
        c = json.loads((SUMMARY / f"part{i}/candidates.json").read_text(encoding="utf-8"))
        path = TRACES / f"part{i}/traces.jsonl"
        if hashlib.sha256(path.read_bytes()).hexdigest() != s["summary"]["traces_sha256"]:
            raise SystemExit(f"part{i} trace hash differs from its summary")
        rows += [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        questions += s["questions"]
        sft += c["sft"]
        dpo += c["dpo"]
        review += s["summary"]["human_review_sample_trace_ids(seed 7)"]
        parts.append({k: s["summary"].get(k) for k in ("range", "device_uuid", "questions", "seconds", "peak_allocated_bytes",
                                                         "traces_sha256")})
        base = base or s["summary"]
    qis = [q["question_index"] for q in questions]
    if sorted(qis) != list(range(len(qis))):
        raise SystemExit(f"question indices overlap or missing: {sorted(qis)}")
    rows.sort(key=lambda r: (r["question_index"], r["kind"] != "greedy", r["sample_index"]))
    questions.sort(key=lambda q: q["question_index"])
    out = TRACES / "traces.jsonl"
    if out.exists():
        raise SystemExit("merged traces already exist")
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    summary = {**{k: base[k] for k in ("corpus", "split", "corpus_file_sha256", "prompt_sha256", "model", "enable_thinking",
                                       "max_new_tokens", "samples_per_question", "sampling", "base_seed", "judgment")},
               "questions": len(questions), "greedy_correct": sum(q["greedy_correct"] for q in questions),
               "pass_at_8": sum(q["pass_at_8"] for q in questions),
               "no_correct_sample": [q["source_record_id"] for q in questions if not q["greedy_correct"] and not q["pass_at_8"]],
               "correct_only_after_condition_layer": sum(q["correct_only_after_condition_layer"] for q in questions),
               "truncated_generations": sum(q["truncated"] for q in questions),
               "sft_candidates": len(sft), "dpo_candidate_pairs": len(dpo),
               "human_review_sample_trace_ids(seed 7, per part)": sorted(review), "reasoning_text_human_reviewed": False,
               "traces_path": str(out.resolve()), "traces_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
               "parts": parts, "seconds_wall_max": max(p["seconds"] for p in parts)}
    (SUMMARY / "summary.json").write_text(json.dumps({"summary": summary, "questions": questions}, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8")
    (SUMMARY / "candidates.json").write_text(json.dumps({"sft": sft, "dpo": dpo}, ensure_ascii=False, indent=1) + "\n",
                                             encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("parts",)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
