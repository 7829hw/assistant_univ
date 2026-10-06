"""Build semantic/constraint DPO pairs, preserving the SFT intent split."""
import argparse
import hashlib
import json
from pathlib import Path

from training.data.canonicalize import semantic_key, serialize_planner_target
from training.data.common import (check_expected_prompt, production_prompt, provenance, read_jsonl, sha256, write_jsonl, write_manifest)
from training.data.negative_mutations import mutations
from training.data.split import check_split, question_key
from training.data.validation import assess, chosen_ok, target_ok


def dpo_pair(gold, rejected, *, negative_type, mutation_source="synthetic", negative_details=None):
    chosen = json.loads(gold["messages"][-1]["content"])
    chosen_text, rejected_text = serialize_planner_target(chosen), serialize_planner_target(rejected)
    if semantic_key(chosen, infer_events=True) == semantic_key(rejected, infer_events=True):
        raise ValueError("Chosen/rejected identical or semantically equivalent")
    question = gold["messages"][1]["content"]
    good = assess(chosen, question)
    if not target_ok(good, gold["metadata"]):
        raise ValueError(f"Chosen downstream failure: {good}")
    bad = assess(json.loads(rejected_text), question)
    category = "semantic" if chosen_ok(bad) else "constraint"
    return {"prompt": gold["messages"][:2], "chosen": [{"role": "assistant", "content": chosen_text}],
            "rejected": [{"role": "assistant", "content": rejected_text}],
            "metadata": {**gold["metadata"], "negative_type": negative_type, "negative_category": category,
                         "negative_details": negative_details or {}, "mutation_source": mutation_source,
                         "chosen_quality": good, "rejected_quality": bad}}


def build(gold_path, output, *, predictions=None, seed=42, max_negatives=8, strict=False):
    if max_negatives < 0 or not predictions and max_negatives == 0:
        raise ValueError("Provide synthetic negatives or --predictions")
    gold_path = Path(gold_path)
    manifest = json.loads((gold_path / "manifest.json").read_text(encoding="utf-8"))["sft"]
    prompt_hash = check_expected_prompt()
    if manifest["prompt_hash"] != prompt_hash or manifest["representation"] != "flat":
        raise ValueError("Gold prompt/schema drift; rebuild SFT corpus")
    gold = {name: read_jsonl(gold_path / f"sft_{name}.jsonl") for name in ("train", "valid")}
    for name in gold:
        if manifest["output_hashes"].get(f"sft_{name}.jsonl") != sha256(gold_path / f"sft_{name}.jsonl"):
            raise ValueError("SFT dataset checksum mismatch; rebuild from reviewed source")
    check_split(gold["train"], gold["valid"])
    prediction_records = read_jsonl(predictions) if predictions else []
    by_id = {}
    issues = []
    known = {r["metadata"]["source_record_id"] for split in gold.values() for r in split}
    for prediction in prediction_records:
        pid = str(prediction.get("source_record_id", ""))
        if pid not in known:
            issues.append({"id": pid, "severity": "error", "detail": "Prediction id absent from gold; benchmark predictions cannot be mined"})
        else:
            by_id.setdefault(pid, []).append(prediction)
    result = {"train": [], "valid": []}
    for split, records in gold.items():
        for record in records:
            pid = record["metadata"]["source_record_id"]
            if record["messages"][0]["content"] != production_prompt():
                raise ValueError("Gold record system prompt drift")
            payload = json.loads(record["messages"][-1]["content"])
            if record["messages"][-1]["content"] != serialize_planner_target(payload) or not target_ok(assess(payload, record["messages"][1]["content"]), record["metadata"]):
                raise ValueError(f"Invalid chosen SFT record: {pid}")
            derived_seed = seed + int(hashlib.sha256(pid.encode()).hexdigest()[:8], 16)
            candidates = mutations(payload, seed=derived_seed)[:max_negatives]
            for prediction in by_id.get(pid, []):
                try:
                    if prediction.get("question") != record["messages"][1]["content"] or prediction.get("prompt_hash") != prompt_hash:
                        raise ValueError("Prediction question/prompt does not match gold")
                    predicted = prediction.get("grounding")
                    if predicted is None:
                        predicted = json.loads(prediction["raw_text"])
                    if semantic_key(payload, infer_events=True) == semantic_key(predicted, infer_events=True):
                        issues.append({"id": pid, "severity": "excluded", "detail": "Prediction semantically equivalent to gold"})
                        continue
                    candidates.append({"payload": predicted, "negative_type": "model_prediction",
                                       "mutation_source": "sft_inference", "negative_details": {
                                           "model": prediction.get("model"), "semantic_judgment": "differs_from_gold_requires_review"}})
                except (ValueError, TypeError, KeyError) as error:
                    issues.append({"id": pid, "severity": "error", "detail": str(error)})
            seen = set()
            for candidate in candidates:
                try:
                    pair = dpo_pair(record, candidate["payload"], negative_type=candidate["negative_type"],
                                    mutation_source=candidate["mutation_source"], negative_details=candidate["negative_details"])
                    key = pair["rejected"][0]["content"]
                    if key in seen:
                        continue
                    seen.add(key)
                    result[split].append(pair)
                except (ValueError, TypeError, KeyError) as error:
                    issues.append({"id": pid, "severity": "error", "detail": str(error)})
    check_split(result["train"], result["valid"])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for split, records in result.items():
        write_jsonl(output / f"dpo_{split}.jsonl", records)
    paths = [gold_path / "manifest.json", gold_path / "sft_train.jsonl", gold_path / "sft_valid.jsonl"]
    if predictions:
        paths.append(Path(predictions))
    info = {**provenance(paths, seed), "gold_prompt_hash": manifest["prompt_hash"],
            "split_seed": manifest["seed"], "max_negatives": max_negatives}
    write_manifest(output, "dpo", result["train"], result["valid"], info, issues)
    print(json.dumps({"train": len(result["train"]), "validation": len(result["valid"]), "issues": issues}, ensure_ascii=False))
    if not result["train"] or strict and any(i["severity"] == "error" for i in issues):
        raise ValueError("DPO build failed; see manifest.json")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default="training/generated", help="SFT directory, preserving its split")
    parser.add_argument("--output", default="training/generated")
    parser.add_argument("--predictions", help="JSONL inference results from SFT source examples only")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-negatives", type=int, default=8, help="Synthetic negatives per question (0 for mining only)")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        build(args.gold, args.output, predictions=args.predictions, seed=args.seed,
              max_negatives=args.max_negatives, strict=args.strict)
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
