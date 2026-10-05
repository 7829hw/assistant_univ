"""Collect first SFT outputs on training-source records for hard-negative review."""
import argparse
import hashlib
import json

from training.data.common import production_prompt, read_jsonl, write_jsonl


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", default="training/generated/sft_train.jsonl")
    parser.add_argument("--model", required=True)
    parser.add_argument("--adapter")
    parser.add_argument("--revision")
    parser.add_argument("--output", default="training/generated/predictions.jsonl")
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    records = read_jsonl(args.gold)
    prompt_hash = hashlib.sha256(production_prompt().encode()).hexdigest()
    for record in records:
        if record["messages"][0]["content"] != production_prompt():
            raise ValueError("Gold prompt drift")
    if args.dry_run:
        print(json.dumps({"items": len(records), "prompt_hash": prompt_hash}))
        return
    from training.inference import HFClient
    client = HFClient(args.model, adapter=args.adapter, revision=args.revision, load_in_4bit=args.load_in_4bit,
                      max_new_tokens=args.max_new_tokens, seed=args.seed)
    predictions = []
    for record in records:
        raw = client.chat(record["messages"][:2])["message"]["content"]
        predictions.append({"source_record_id": record["metadata"]["source_record_id"],
                            "question": record["messages"][1]["content"], "raw_text": raw,
                            "prompt_hash": prompt_hash, "model": client.model,
                            "model_revision": client.config["model"]["revision"], "seed": args.seed})
    write_jsonl(args.output, predictions)


if __name__ == "__main__":
    main()
