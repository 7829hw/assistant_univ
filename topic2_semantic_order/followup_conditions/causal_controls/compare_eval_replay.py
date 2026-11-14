"""Compare two completed evaluation cells on identical inputs, entirely on CPU."""
import argparse
from pathlib import Path

import schedules  # configures the follow-up import path
from common import S, dump, load
from compare_environment import signature

ACTION_FIELDS = ("outcome", "calls", "grounding", "error_code", "final_answer")
SCORER_FIELDS = ("category", "checks", "grounding_ok", "grounding_diffs")
SAFE_GOLD = {
    "sft_dpo_inventory/ablation_012/e2/h_dev.yaml",
    "sft_dpo_inventory/client_test_10000/qa_test_10000.yaml",
}


def call_view(call):
    return {k: call.get(k) for k in ("prompt_ids_sha256", "sampling_seed", "raw_sha256", "finish_reason")}


def compare(reference, candidate):
    meta_a, meta_b = reference["meta"], candidate["meta"]
    if meta_a.get("gold_file") != meta_b.get("gold_file") or meta_a.get("gold_file") not in SAFE_GOLD:
        raise ValueError("Replay only accepts the same approved development evaluation input")
    a, b = signature(meta_a), signature(meta_b)
    a["adapter_sha256"] = meta_a["vllm"]["server_meta"].get("adapter_sha256")
    b["adapter_sha256"] = meta_b["vllm"]["server_meta"].get("adapter_sha256")
    required = ("gold_sha256", "code_fingerprint", "planner_prompt_sha256", "scorer_version",
                "gpu_uuid", "round_seed", "model_revision", "adapter_sha256")
    if any(a[k] is None or a[k]=="" for k in required):
        raise ValueError("Replay provenance is incomplete")
    adjustable = {"concurrency"}
    drift = sorted(k for k in a if a[k] != b[k] and k not in adjustable)
    if drift or not a["adapter_sha256"] or not a["sampling"]:
        raise ValueError(f"Replay invariants failed: {drift}")
    ids = meta_a["item_order"]
    if (len(ids) != len(set(ids)) or not ids or meta_b["item_order"] != ids or
        any([r["id"] for r in doc["rows"]] != ids for doc in (reference, candidate))):
        raise ValueError("Replay item coverage or order differs")
    differences = {k: [] for k in ("raw_calls", "call_inputs", "call_count", "finish_reason",
                                    "tool_pipeline", "scorer", "correctness")}
    counts = []
    for x, y in zip(reference["rows"], candidate["rows"], strict=True):
        calls_a, calls_b = ([call_view(c) for c in row.get("hf_calls") or []] for row in (x,y))
        counts.append((sum(c["finish_reason"]=="length" for c in calls_a),
                       sum(c["finish_reason"]=="length" for c in calls_b)))
        conditions = (
            [c["raw_sha256"] for c in calls_a] != [c["raw_sha256"] for c in calls_b],
            [(c["prompt_ids_sha256"], c["sampling_seed"]) for c in calls_a] !=
            [(c["prompt_ids_sha256"], c["sampling_seed"]) for c in calls_b],
            len(calls_a) != len(calls_b),
            [c["finish_reason"] for c in calls_a] != [c["finish_reason"] for c in calls_b],
            any(x.get(k) != y.get(k) for k in ACTION_FIELDS),
            any(x.get(k) != y.get(k) for k in SCORER_FIELDS),
            (x["category"] == "match") != (y["category"] == "match"),
        )
        for name, diff in zip(differences, conditions, strict=True):
            if diff:
                differences[name].append(x["id"])
    same_scoring_context = ("reference_date", "protocol", "kind")
    if any(meta_a.get(k)!=meta_b.get(k) for k in same_scoring_context):
        raise ValueError("Replay scoring context changed")
    return dict(n_items=len(ids), reference_concurrency=a["concurrency"], candidate_concurrency=b["concurrency"],
                paired_rows_changed={k:len(v) for k,v in differences.items()}, ids_changed=differences,
                correct=[sum(r["category"]=="match" for r in doc["rows"]) for doc in (reference,candidate)],
                truncated_calls=[sum(column) for column in zip(*counts)],
                reference_wall_s=meta_a["vllm"]["wall_seconds"], candidate_wall_s=meta_b["vllm"]["wall_seconds"])


def compare_paths(reference, candidate):
    return dict(reference=reference.name, candidate=candidate.name,
                reference_sha256=S.sha_file(reference), candidate_sha256=S.sha_file(candidate),
                **compare(load(reference), load(candidate)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Use a fresh report path")
    dump(args.out, compare_paths(args.reference, args.candidate))


if __name__ == "__main__":
    main()
