# -*- coding: utf-8 -*-
"""학습용 thinking trace 수집(GPU 2, HF base). 학습하지 않고, 어떤 corpus에도 넣지 않는다.

    CUDA_VISIBLE_DEVICES=2 HF_HOME=... HF_HUB_OFFLINE=1 python sft_dpo_inventory/thinking_prep_001/collect_traces.py \
        --corpus training/generated/reviewed_gold_v003_t2pc --split train \
        --out training/generated/thinking_traces/v003_t2pc_train --summary sft_dpo_inventory/thinking_prep_001/traces

- 대상: 승인된 corpus의 지정 split SFT 질문(기본 v003_t2pc train). batch004 후보는 검토·import 뒤 같은 명령으로 다시 돈다.
- 질문마다: greedy 1개 + 표본 8개(temperature 0.6, top_p 0.95, top_k 20, seed = 기준 seed + 질문 순번). ``enable_thinking=True``,
  max_new_tokens 8192(HF-E와 같음). 입력은 corpus 레코드의 system·user(현재 planner messages와 같은지 확인한다).
- 판정: 응답 본문(``</think>`` 뒤)의 JSON을 reviewed gold와 ``evaluate_vendor100.grounding_check``로 비교한다.
  **조건 계층을 거치기 전 모델 출력 기준**이다. 조건 계층(기준일 2026-09-25)을 거친 뒤에만 맞는 표본은 따로 센다.
  참고로 thor ``semantic_key`` 완전 일치도 센다.
- 후보: SFT = 맞는 표본(thinking 포함 전체 응답, 같은 질문의 같은 원문은 하나로), DPO = 같은 질문의 (맞는 표본, 틀린 표본) 쌍.
- trace 원문(thinking 문장, 생성 token id)은 ``--out``(ignore 경로)에만 둔다. ``--summary``에는 질문별 집계·후보 목록(원문 hash)과
  사람이 읽어 볼 표본 10개(고정 seed)의 id만 남긴다. 추론 문장은 사람이 검토하지 않았다.
- gold를 힌트로 주고 추론을 쓰게 하는 방식은 쓰지 않는다.
"""
import argparse
import hashlib
import json
import random
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import hf_thinking as H  # noqa: E402

SAMPLES = 8
BASE_SEED = 20261006
REVIEW_SEED = 7
REFERENCE_DATE = date(2026, 9, 25)


def judge(content, question, gold):
    import evaluate_vendor100 as EV
    from geoflow import conditions
    from geoflow.errors import GeoFlowError
    from geoflow.planner import parse_planner_json
    from training.data.canonicalize import semantic_key
    out = {"parse": "ok", "raw_match": False, "raw_diffs": [], "after_condition_match": None,
           "semantic_key_equal": False, "error_tags": []}
    try:
        payload = parse_planner_json(content) if content else None
    except Exception:  # noqa: BLE001 - JSON이 아닌 본문
        payload = None
    if payload is None:
        out.update(parse="no_json" if content else "empty_content", error_tags=["no_json" if content else "truncated_or_empty"])
        return out, None
    if payload.get("unsupported"):
        out.update(parse="unsupported", error_tags=["unsupported"])
        return out, payload
    item = {"gold_grounding": gold, "gold": None}
    same, diffs = EV.grounding_check(item, payload)
    out.update(raw_match=bool(same), raw_diffs=json.loads(json.dumps(diffs, ensure_ascii=False)))
    try:
        out["semantic_key_equal"] = semantic_key(payload) == semantic_key(gold)
    except Exception:  # noqa: BLE001 - 계약 밖 형태
        out["semantic_key_equal"] = False
    if not same:
        out["error_tags"] = sorted({(d if isinstance(d, str) else d[0]).replace("factor:", "factor_") for d in diffs})
        try:
            fixed, _ = conditions.reconcile_payload(payload, question, reference_date=REFERENCE_DATE)
            out["after_condition_match"] = bool(EV.grounding_check(item, fixed)[0])
        except GeoFlowError as error:
            out["after_condition_match"] = False
            out["after_condition_stop"] = getattr(error, "code", type(error).__name__)
    return out, payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--out", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--flags", default=str(ROOT / "training/records/corpora/reviewed_gold_v003_t2pc/review_flags.json"))
    args = parser.parse_args()
    out_dir, summary_dir = Path(args.out), Path(args.summary)
    if ROOT in out_dir.resolve().parents and "generated" not in out_dir.parts:
        raise SystemExit("--out은 저장소 밖이나 ignore 경로(generated)여야 한다")
    if out_dir.exists():
        raise SystemExit("--out이 이미 있다")
    out_dir.mkdir(parents=True)
    summary_dir.mkdir(parents=True, exist_ok=True)

    import torch
    from geoflow.planner import GeoFlowPlanner
    from training.data.common import check_expected_prompt, read_jsonl, sha256

    prompt_hash = check_expected_prompt()
    planner = GeoFlowPlanner(client=None)
    records = read_jsonl(Path(args.corpus) / f"sft_{args.split}.jsonl")
    flags = json.loads(Path(args.flags).read_text(encoding="utf-8")) if Path(args.flags).exists() else {"sft": [], "dpo": []}
    sft_marks = {f["source_record_id"]: f["marks"] for f in flags["sft"] if f["split"] == args.split and f["marks"]}
    dpo_marks = {}
    for f in flags["dpo"]:
        if f["split"] == args.split and any(m.startswith("t2pc_") for m in f["marks"]):
            dpo_marks.setdefault(f["source_record_id"], []).append({"negative_type": f["negative_type"],
                                                                    "marks": [m for m in f["marks"] if m.startswith("t2pc_")]})
    client = H.load_client()
    started = time.perf_counter()
    questions, sft_candidates, dpo_candidates = [], [], []
    with open(out_dir / "traces.jsonl", "w", encoding="utf-8") as stream:
        for qi, record in enumerate(records):
            messages = record["messages"][:2]
            question = messages[1]["content"]
            if planner.messages(question) != messages:
                raise SystemExit("corpus 레코드의 입력이 현재 planner messages와 다르다")
            gold = json.loads(record["messages"][-1]["content"])
            sid = record["metadata"]["source_record_id"]
            t0 = time.perf_counter()
            outputs = [("greedy", 0, r) for r in client.generate(messages)]
            seed = BASE_SEED + qi
            outputs += [("sample", k + 1, r) for k, r in enumerate(
                client.generate(messages, sample=True, num_return_sequences=SAMPLES, seed=seed))]
            seconds = time.perf_counter() - t0
            judged = []
            for kind, index, result in outputs:
                verdict, payload = judge(result["content"], question, gold)
                trace_id = f"{sid}:{kind}:{index}"
                row = {"trace_id": trace_id, "source_record_id": sid, "question_index": qi, "kind": kind,
                       "sample_index": index, "seed": seed if kind == "sample" else None,
                       **{k: result[k] for k in ("raw_text", "raw_sha256", "generated_ids", "thinking", "content",
                                                 "think_closed", "prompt_tokens", "generated_tokens", "done_reason")},
                       "parsed": payload, "verdict": verdict}
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                judged.append(row)
            correct = [r for r in judged if r["verdict"]["raw_match"]]
            wrong = [r for r in judged if not r["verdict"]["raw_match"]]
            unique_correct, seen = [], set()
            for r in correct:
                if r["raw_sha256"] not in seen:
                    seen.add(r["raw_sha256"])
                    unique_correct.append(r)
            unique_wrong, seen = [], set()
            for r in wrong:
                if r["raw_sha256"] not in seen:
                    seen.add(r["raw_sha256"])
                    unique_wrong.append(r)
            samples = [r for r in judged if r["kind"] == "sample"]
            questions.append({
                "question_index": qi, "source_record_id": sid, "batch_item_ids": record["metadata"].get("batch_item_ids") or [],
                "greedy_correct": judged[0]["verdict"]["raw_match"],
                "pass_at_8": any(r["verdict"]["raw_match"] for r in samples),
                "correct_samples_of_8": sum(r["verdict"]["raw_match"] for r in samples),
                "correct_only_after_condition_layer": sum(1 for r in judged if not r["verdict"]["raw_match"]
                                                          and r["verdict"]["after_condition_match"]),
                "semantic_key_equal": sum(r["verdict"]["semantic_key_equal"] for r in judged),
                "unique_correct": len(unique_correct), "unique_wrong": len(unique_wrong),
                "truncated": sum(r["done_reason"] == "length" for r in judged),
                "generated_tokens": [r["generated_tokens"] for r in judged], "seconds": round(seconds, 1),
                "v003_flags": {"sft": sft_marks.get(sid, []), "dpo": dpo_marks.get(sid, [])},
                "error_tags": dict(Counter(t for r in wrong for t in r["verdict"]["error_tags"]))})
            for r in unique_correct:
                sft_candidates.append({"trace_id": r["trace_id"], "source_record_id": sid, "raw_sha256": r["raw_sha256"],
                                       "generated_tokens": r["generated_tokens"], "prompt_tokens": r["prompt_tokens"],
                                       "v003_flags": sft_marks.get(sid, [])})
            for c in unique_correct:
                for w in unique_wrong:
                    dpo_candidates.append({"chosen": c["trace_id"], "rejected": w["trace_id"], "source_record_id": sid,
                                           "rejected_error_tags": w["verdict"]["error_tags"],
                                           "rejected_grounding_diffs": w["verdict"]["raw_diffs"],
                                           "rejected_parse": w["verdict"]["parse"],
                                           "rejected_correct_after_condition_layer": w["verdict"]["after_condition_match"],
                                           "v003_flags": {"sft": sft_marks.get(sid, []), "dpo": dpo_marks.get(sid, [])}})
            print(json.dumps({k: questions[-1][k] for k in ("question_index", "greedy_correct", "pass_at_8",
                                                             "correct_samples_of_8", "truncated", "seconds")}), flush=True)
    rng = random.Random(REVIEW_SEED)
    review = sorted(rng.sample([c["trace_id"] for c in sft_candidates], min(10, len(sft_candidates))))
    traces_path = out_dir / "traces.jsonl"
    summary = {
        "corpus": args.corpus, "split": args.split, "corpus_file_sha256": sha256(Path(args.corpus) / f"sft_{args.split}.jsonl"),
        "prompt_sha256": prompt_hash, "model": f"{H.MODEL}@{H.REVISION}", "enable_thinking": True,
        "max_new_tokens": H.MAX_NEW_TOKENS, "samples_per_question": SAMPLES, "sampling": H.SAMPLING, "base_seed": BASE_SEED,
        "judgment": "evaluate_vendor100.grounding_check on raw model output (before condition layer)",
        "questions": len(questions), "greedy_correct": sum(q["greedy_correct"] for q in questions),
        "pass_at_8": sum(q["pass_at_8"] for q in questions),
        "no_correct_sample": [q["source_record_id"] for q in questions if not q["greedy_correct"] and not q["pass_at_8"]],
        "correct_only_after_condition_layer": sum(q["correct_only_after_condition_layer"] for q in questions),
        "truncated_generations": sum(q["truncated"] for q in questions),
        "sft_candidates": len(sft_candidates), "dpo_candidate_pairs": len(dpo_candidates),
        "human_review_sample_trace_ids(seed 7)": review,
        "reasoning_text_human_reviewed": False,
        "traces_path": str(traces_path.resolve()), "traces_sha256": sha256(traces_path),
        "seconds": round(time.perf_counter() - started, 1),
        "peak_allocated_bytes": torch.cuda.max_memory_allocated()}
    (summary_dir / "summary.json").write_text(json.dumps({"summary": summary, "questions": questions}, ensure_ascii=False,
                                                         indent=1) + "\n", encoding="utf-8")
    (summary_dir / "candidates.json").write_text(json.dumps({"sft": sft_candidates, "dpo": dpo_candidates},
                                                            ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
