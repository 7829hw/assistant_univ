"""Build thinking-format SFT/DPO candidate datasets from collected traces (no approvals, no training).

    python -m training.data.build_thinking --traces <traces.jsonl> --candidates <candidates.json> \
        --corpus training/generated/reviewed_gold_v003_t2pc --split train \
        --output training/generated/thinking_v003_t2pc_train

- SFT: every unique judged-correct trace (thinking + JSON exactly as generated) for its reviewed-gold question whose
  answer also passes the existing contract check (``grounding_check`` alone does not check the contract); traces
  failing it are excluded and counted, and DPO pairs using them as chosen are excluded too.
- DPO: (correct, wrong) trace pairs of the same question. Wrong traces without a parseable answer (truncated,
  no JSON) are excluded: syntax-only failures are not preference negatives (thor policy). Category is constraint
  when the wrong answer fails the existing contract check, else semantic.
- Splits: the traces come from one corpus split; that split is written, the other split file is empty.
- Flags from ``review_flags.json`` stay in metadata (``v003_flags``); nothing is filtered by them.
- Reasoning text is model-generated and not human-reviewed (``reasoning_human_reviewed: false``).
- Teacher traces (``source: teacher`` rows) may be in the traces file; they are normalized by
  ``thinking.normalize_trace`` and their records are marked ``metadata.source == "teacher"`` (decision 40-A).
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from training.data import thinking
from training.data.common import check_expected_prompt, provenance, read_jsonl, sha256, write_jsonl
from training.data.validation import assess, chosen_ok, target_ok


def build(traces_path, candidates_path, corpus, split, output):
    output = Path(output)
    if output.exists():
        raise ValueError(f"Output already exists: {output}")
    prompt_hash = check_expected_prompt()
    traces = {row["trace_id"]: thinking.normalize_trace(row) for row in read_jsonl(traces_path)}
    candidates = json.loads(Path(candidates_path).read_text(encoding="utf-8"))
    gold = {r["metadata"]["source_record_id"]: r for r in read_jsonl(Path(corpus) / f"sft_{split}.jsonl")}
    sft, dpo, excluded, sft_excluded = [], [], Counter(), Counter()
    contract_failed = set()
    for cand in candidates["sft"]:
        trace = traces[cand["trace_id"]]
        question = gold[cand["source_record_id"]]["messages"][1]["content"]
        # grounding_check는 측정값·장소·factor 값만 본다. 학습 target은 기존 계약 판정(thor assess)도 통과해야 한다.
        # 결정 14의 정지 target은 gold와 같은 계약 정지로 멈추면 통과한다(``target_ok``).
        if not target_ok(assess(thinking.response_json(trace["raw_text"]), question),
                         gold[cand["source_record_id"]]["metadata"]):
            contract_failed.add(cand["trace_id"])
            sft_excluded["chosen_contract_failure"] += 1
            continue
        record = thinking.sft_record(trace, gold[cand["source_record_id"]], source=str(traces_path))
        record["metadata"]["v003_flags"] = cand.get("v003_flags", [])
        sft.append(record)
    for cand in candidates["dpo"]:
        chosen, rejected = traces[cand["chosen"]], traces[cand["rejected"]]
        if cand["chosen"] in contract_failed:
            excluded["chosen_contract_failure"] += 1
            continue
        if cand["rejected_parse"] not in ("ok",):
            excluded[f"rejected_{cand['rejected_parse']}"] += 1
            continue
        target = thinking.response_json(rejected["raw_text"])
        question = gold[cand["source_record_id"]]["messages"][1]["content"]
        category = "semantic" if chosen_ok(assess(target, question)) else "constraint"
        pair = thinking.dpo_pair(chosen, rejected, gold[cand["source_record_id"]], source=str(traces_path),
                                 negative_category=category,
                                 details={"rejected_error_tags": cand["rejected_error_tags"],
                                          "rejected_grounding_diffs": cand["rejected_grounding_diffs"],
                                          "rejected_correct_after_condition_layer":
                                              cand["rejected_correct_after_condition_layer"]})
        pair["metadata"]["v003_flags"] = cand.get("v003_flags", {})
        dpo.append(pair)
    output.mkdir(parents=True)
    other = "valid" if split == "train" else "train"
    for stage, rows in (("sft", sft), ("dpo", dpo)):
        write_jsonl(output / f"{stage}_{split}.jsonl", rows)
        write_jsonl(output / f"{stage}_{other}.jsonl", [])
    info = provenance([Path(traces_path), Path(candidates_path), Path(corpus) / f"sft_{split}.jsonl"], 42)
    if info["prompt_hash"] != prompt_hash:
        raise ValueError("Prompt hash changed during build")
    manifest = {}
    for stage, rows in (("sft", sft), ("dpo", dpo)):
        manifest[stage] = {**info, "format": thinking.FORMAT, "representation": "flat", "corpus": str(corpus),
                           "split_source": split, "reasoning_human_reviewed": False,
                           "train_count": len(rows) if split == "train" else 0,
                           "validation_count": len(rows) if split == "valid" else 0,
                           "questions": len({r["metadata"]["source_record_id"] for r in rows}),
                           "excluded": dict(excluded) if stage == "dpo" else dict(sft_excluded),
                           "negative_category": dict(Counter(r["metadata"]["negative_category"] for r in rows))
                           if stage == "dpo" else {},
                           "issues": [], "output_hashes": {f"{stage}_{s}.jsonl": sha256(output / f"{stage}_{s}.jsonl")
                                                           for s in ("train", "valid")}}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {stage: {k: manifest[stage][k] for k in ("train_count", "validation_count", "questions", "excluded",
                                                     "negative_category")} for stage in manifest}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", required=True)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    print(json.dumps(build(args.traces, args.candidates, args.corpus, args.split, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
