"""Thin HF/replay wrapper over evaluate_planner, with intent/task breakdowns."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import yaml

import evaluate_planner as evaluator
import paraphrase_corpus as P
from geoflow.composer import MacroComposer
from geoflow.errors import PlannerError
from geoflow.planner import GeoFlowPlanner
from query_loader import load_queries
from training.data.common import production_prompt, provenance, read_jsonl, sha256


def load_items(path):
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if isinstance(document, dict) and "intents" in document:
        items = P.load_corpus_items(path)
        gold = {intent["intent"]: intent["golden"] for intent in P.load_corpus(path)}
        return [{**item, "golden": gold[item["intent_id"]]} for item in items]
    return load_queries(path)


class ReplayClient:
    model = "prediction-replay"

    def __init__(self, predictions):
        self.responses = {p["source_record_id"]: p for p in predictions}
        if len(self.responses) != len(predictions):
            raise ValueError("Evaluation replay requires one prediction per source_record_id")
        self.calls = 0

    def select(self, item):
        self.current = self.responses[item["id"]]
        if self.current["question"] != item["question"]:
            raise ValueError("Prediction question mismatch")
        if self.current.get("prompt_hash") != hashlib.sha256(production_prompt().encode()).hexdigest():
            raise ValueError("Prediction prompt provenance mismatch")
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        if self.calls > 1:
            raise PlannerError("Replay has no live repair inference", code="REPLAY_REPAIR_UNAVAILABLE")
        text = self.current.get("raw_text")
        if text is None:
            text = json.dumps(self.current["grounding"], ensure_ascii=False)
        return {"message": {"content": text}}


def evaluate(client, items, *, execute=False, tool_executor=None):
    planner, composer = GeoFlowPlanner(client=client), MacroComposer()
    profile = None
    if execute and tool_executor is not None and getattr(tool_executor, 'provider', None):
        from geoflow.providers import profile_for
        profile = profile_for(tool_executor.provider)
    records = []
    for item in items:
        if isinstance(client, ReplayClient):
            client.select(item)
        record = evaluator.evaluate_once(planner, composer, item, execute=execute, tool_executor=tool_executor,
                    available_tools=tool_executor.tool_names if tool_executor else None,
                    system_prompt_chars=len(planner.system_prompt()), execution_profile=profile)
        record["intent_id"] = item.get("intent_id", item.get("family", item["id"]))
        record["task_groups"] = item.get("cohorts") or [item.get("family") or next(
            (c.split(":")[0] for c in item.get("expected_concepts", []) if c.endswith(":MEASURE")), "unclassified")]
        records.append(record)
    intents, tasks = defaultdict(list), defaultdict(list)
    for record in records:
        intents[record["intent_id"]].append(record)
        for group in record["task_groups"]:
            tasks[group].append(record)
    return {"summary": evaluator.summarize(records), "by_intent": {k: evaluator.summarize(v) for k, v in intents.items()},
            "by_task_group": {k: evaluator.summarize(v) for k, v in tasks.items()}, "records": records}


def compare(paths):
    reports = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
    keys = ("corpus_hash", "source_files", "prompt_hash", "definition_hashes", "execute", "provider", "inference_mode", "max_new_tokens", "model_revision")
    if any(any(report["metadata"].get(k) != reports[0]["metadata"].get(k) for k in keys) for report in reports[1:]):
        raise ValueError("Cannot compare runs with different corpus/prompt/execution/replay settings")
    if any([r["id"] for r in report["records"]] != [r["id"] for r in reports[0]["records"]] for report in reports[1:]):
        raise ValueError("Comparison requires identical evaluation item IDs/order")
    rows = ["| Model | Grounding | Factor | Validation | Execution |", "|---|---:|---:|---:|---:|"]
    for report in reports:
        s = report["summary"]
        rows.append("| " + " | ".join(str(v) for v in [report["metadata"]["label"], s["grounding_exact_match"],
                            s["factor_exact_match"], s["validation_pass_rate"], s["execution_success_rate"]]) + " |")
    return {"table": "\n".join(rows), "runs": reports}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", help="HF full model/base checkpoint")
    parser.add_argument("--adapter", help="SFT/DPO PEFT adapter")
    parser.add_argument("--revision", help="Pinned base model/tokenizer revision (defaults to checkpoint provenance/main)")
    parser.add_argument("--query-file", default="evaluation/v2/paraphrases_holdout_v2.yaml")
    parser.add_argument("--predictions", help="Replay JSONL; no model downloads, repairs unavailable")
    parser.add_argument("--output", default="training/runs/evaluation.json")
    parser.add_argument("--label", default="Base")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--provider", choices=["mock", "reference"], default="mock")
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compare", nargs="+", help="Compare saved reports from the same corpus/settings")
    args = parser.parse_args(argv)
    if args.compare:
        result = compare(args.compare)
        print(result["table"])
    else:
        items = load_items(args.query_file)
        if args.dry_run:
            print(json.dumps({"items": len(items), "gold_labeled": sum("golden" in i or "grounding" in i for i in items),
                              "corpus_hash": sha256(args.query_file)}))
            return
        if args.predictions:
            client = ReplayClient(read_jsonl(args.predictions))
        elif args.model:
            from training.inference import HFClient
            client = HFClient(args.model, adapter=args.adapter, revision=args.revision, load_in_4bit=args.load_in_4bit,
                              max_new_tokens=args.max_new_tokens, seed=args.seed)
        else:
            parser.error("Provide --model or --predictions")
        executor = None
        if args.execute:
            from build import build
            from tool_executor import ToolExecutor
            from tool_handlers import get_tool_handlers
            executor = ToolExecutor(tools=build()[0], handlers=get_tool_handlers(args.provider), provider=args.provider)
        result = evaluate(client, items, execute=args.execute, tool_executor=executor)
        document = yaml.safe_load(Path(args.query_file).read_text(encoding="utf-8"))
        parents = [P.BASE_DIR / path for path in document.get("parents", [])] if isinstance(document, dict) else []
        result["metadata"] = {**provenance([args.query_file, *parents], args.seed), "corpus_hash": sha256(args.query_file),
                              "label": args.label, "model": args.model, "adapter": args.adapter,
                              "model_revision": client.config["model"]["revision"] if hasattr(client, "config") else None,
                              "execute": args.execute, "provider": args.provider, "max_new_tokens": args.max_new_tokens,
                              "inference_mode": "replay" if args.predictions else "hf"}
        print(json.dumps(result["summary"], ensure_ascii=False))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
