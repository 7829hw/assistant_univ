"""Build canonical chat SFT records from independent, validated annotations."""
import argparse
import json
from pathlib import Path

import yaml

from geoflow.examples import load_store, verify_example
from geoflow.errors import GeoFlowError
from geoflow.grounding import drop_unsupported_regions, parse_grounding
from training.data.canonicalize import check_shape, flatten_source, semantic_key, serialize_planner_target
from training.data.common import (check_source, production_prompt, protected_questions, provenance,
                                 write_jsonl, write_manifest)
from training.data.split import question_key, split_records
from training.data.validation import assess, chosen_ok


def sft_record(raw, *, source, source_representation, prompt=None):
    question = raw.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Missing question")
    payload = raw["grounding"]
    check_shape(payload, structured=source_representation == "structured")
    if source_representation == "structured":
        payload = flatten_source(payload)
    target = serialize_planner_target(payload)
    result = assess(json.loads(target), question, normalize=False)
    if not chosen_ok(result):
        raise ValueError(f"Gold parse/compose/validate failed: {result}")
    if not payload.get("unsupported"):
        effective = parse_grounding(json.loads(target), question)
        drop_unsupported_regions(effective)
        if semantic_key(effective) != semantic_key(json.loads(target)):
            raise ValueError("Gold requires runtime normalization; correct annotation explicitly before training")
    runtime = assess(json.loads(target), question)
    if not chosen_ok(runtime):
        raise ValueError(f"Gold production pipeline failed: {runtime}")
    return {"messages": [{"role": "system", "content": prompt or production_prompt()},
                         {"role": "user", "content": question},
                         {"role": "assistant", "content": target}],
            "metadata": {"source": source, "source_record_id": str(raw["id"]),
                         "parent_intent": raw.get("parent_intent") or raw.get("family"),
                         "family": raw.get("family"), "tags": raw.get("tags", []),
                         "reviewed_by": raw.get("reviewed_by"), "source_version": raw.get("version"),
                         "source_representation": source_representation, "representation": "flat",
                         "output_schema_version": "geoflow-planner-flat-training-v1", "chosen_quality": runtime}}


def build(input_path, output, *, seed=42, valid_fraction=0.2, source_representation="structured", strict=False):
    check_source(input_path)
    document = yaml.safe_load(Path(input_path).read_text(encoding="utf-8"))
    source_records = document.get("examples", []) if isinstance(document, dict) else document
    if not isinstance(source_records, list) or not source_records:
        raise ValueError("Input must be a nonempty examples document or annotation list")
    registered = {}
    if isinstance(document, dict) and any(r.get("split") == "retrieval_store" for r in source_records):
        registered = {e.id: e for e in load_store(input_path).examples}
    prompt, protected = production_prompt(), protected_questions()
    records, issues, seen_ids, seen_questions = [], [], set(), set()
    observed = set()
    for raw in source_records:
        where = str(raw.get("id", "<missing>")) if isinstance(raw, dict) else "<non-object>"
        try:
            if not isinstance(raw, dict) or not raw.get("id"):
                raise ValueError("Record requires an id and object shape")
            if where in seen_ids or question_key(raw["question"]) in seen_questions:
                raise ValueError("Duplicate source id/question")
            seen_ids.add(where)
            seen_questions.add(question_key(raw["question"]))
            if question_key(raw["question"]) in protected:
                raise ValueError("Question overlaps reserved evaluation corpus")
            payload = raw["grounding"]
            check_shape(payload, structured=source_representation == "structured")
            if not payload.get("unsupported") and payload.get("factors"):
                has_plan = "aggregation_plan" in payload["factors"]
                has_flat = bool(set(payload["factors"]) & {"aggregation", "bucket", "rollup", "answer"})
                if has_plan or has_flat:
                    observed.add("structured" if has_plan else "flat")
                if has_plan and has_flat or len(observed) > 1:
                    raise ValueError("Mixed flat/structured source corpus")
                if has_plan and source_representation != "structured" or has_flat and source_representation != "flat":
                    raise ValueError("Source representation does not match --source-representation")
            if where in registered:
                problems = verify_example(registered[where], execute_reference=False)
                if problems:
                    raise ValueError(f"Store annotation verification failed: {problems}")
            if raw.get("expected_outcome") == "needs_clarification":
                issues.append({"id": where, "severity": "excluded", "detail": "No production clarification JSON target"})
                continue
            if (raw.get("expected_outcome") == "unsupported") != (payload.get("unsupported") is True) and raw.get("expected_outcome"):
                raise ValueError("Expected outcome contradicts grounding")
            records.append(sft_record(raw, source=str(input_path), source_representation=source_representation, prompt=prompt))
        except (GeoFlowError, ValueError, TypeError, KeyError) as error:
            issues.append({"id": where, "severity": "error", "detail": str(error)})
    # Mixing is a corpus-level error: never write a partially mixed experiment.
    if len(observed) > 1:
        records = []
    train, valid = split_records(records, seed=seed, valid_fraction=valid_fraction)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "sft_train.jsonl", train)
    write_jsonl(output / "sft_valid.jsonl", valid)
    info = {**provenance([input_path], seed), "valid_fraction": valid_fraction,
            "source_representation": source_representation}
    write_manifest(output, "sft", train, valid, info, issues)
    print(json.dumps({"train": len(train), "validation": len(valid), "issues": issues}, ensure_ascii=False))
    if not records or strict and any(i["severity"] == "error" for i in issues):
        raise ValueError("SFT build failed; see manifest.json issues")
    return train, valid


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="geoflow_examples/question_graph_examples.yaml")
    parser.add_argument("--output", default="training/generated")
    parser.add_argument("--source-representation", choices=["flat", "structured"], default="structured")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--valid-fraction", type=float, default=0.2)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        build(args.input, args.output, seed=args.seed, valid_fraction=args.valid_fraction,
              source_representation=args.source_representation, strict=args.strict)
    except (GeoFlowError, ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
