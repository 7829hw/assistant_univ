"""Lazy optional dependencies, config/dataset guards and identical chat rendering."""
import argparse
import hashlib
import json
from pathlib import Path

import yaml

from training.data.canonicalize import semantic_key, serialize_planner_target
from training.data.common import check_expected_prompt, production_prompt, read_jsonl, sha256
from training.data.split import check_split
from training.data import thinking
from training.data.validation import assess, chosen_ok


def load_config(path, stage):
    config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict) or set(config) - {"model", "data", "training", "lora", "reference", "chat_template_kwargs", "safety", "profiling", "thinking"}:
        raise ValueError("Invalid configuration sections")
    for name in ("model", "data", "training"):
        if not isinstance(config.get(name), dict):
            raise ValueError(f"Missing config section: {name}")
    if not config["model"].get("name_or_path"):
        raise ValueError("model.name_or_path required")
    args = config["training"]
    if args.get("bf16") and args.get("fp16"):
        raise ValueError("Select bf16 or fp16, not both")
    if not args.get("output_dir"):
        raise ValueError("training.output_dir required")
    for key in ("per_device_train_batch_size", "gradient_accumulation_steps", "num_train_epochs", "learning_rate"):
        if args.get(key, 1) <= 0:
            raise ValueError(f"{key} must be positive")
    lora = config.get("lora", {})
    if config["model"].get("load_in_4bit") and not lora.get("enabled", True):
        raise ValueError("QLoRA requires lora.enabled")
    if stage == "dpo":
        mode = config["model"].get("initial_mode", "sft")
        if mode not in {"sft", "dpo_only"}:
            raise ValueError("initial_mode must be sft or dpo_only")
        if mode == "sft" and not config["model"].get("adapter_path") and not config["model"].get("sft_merged", False):
            raise ValueError("SFT -> DPO requires adapter_path or explicit sft_merged: true")
        if mode == "dpo_only" and config["model"].get("adapter_path"):
            raise ValueError("DPO only starts from the base checkpoint without an SFT adapter")
        if config["model"].get("adapter_path") and not lora.get("enabled", True):
            raise ValueError("Adapter continuation requires lora.enabled")
        reference = config.get("reference", {})
        strategy = reference.get('strategy', 'auto')
        if strategy not in {'auto', 'shared_adapter', 'precompute', 'full'}:
            raise ValueError('Unknown reference.strategy')
        if strategy in {'shared_adapter', 'precompute'} and (not lora.get('enabled', True) or reference.get('mode') == 'explicit'):
            raise ValueError('Shared/precomputed reference profile requires PEFT initial-policy reference')
        if strategy == 'precompute' and args.get('precompute_ref_log_probs') is False:
            raise ValueError('precompute strategy conflicts with precompute_ref_log_probs=false')
        if strategy == 'full' and args.get('precompute_ref_log_probs'):
            raise ValueError('Select full or precompute reference benchmark separately')
        if reference.get("mode", "initial_policy") not in {"initial_policy", "explicit"}:
            raise ValueError("reference.mode must be initial_policy or explicit")
        if reference.get("mode") == "explicit" and (not reference.get("name_or_path") or config["model"].get("adapter_path")):
            raise ValueError("Explicit reference requires a full checkpoint and a merged policy")
        for key in ("max_prompt_length", "max_completion_length", "max_length", "beta"):
            if args.get(key, 1) <= 0:
                raise ValueError(f"{key} must be positive")
    elif args.get("max_seq_length", 8192) <= 0:
        raise ValueError("max_seq_length must be positive")
    from training.profiling import validate_profile
    validate_profile(config, stage)
    return config


def load_records(config, stage):
    paths = config["data"]
    manifest = json.loads(Path(paths["manifest"]).read_text(encoding="utf-8"))[stage]
    current = check_expected_prompt()
    if manifest["prompt_hash"] != current or manifest["representation"] != "flat":
        raise ValueError("Production prompt/schema drift; rebuild data before training")
    if any(issue.get("severity") == "error" for issue in manifest.get("issues", [])):
        raise ValueError("Manifest contains critical errors; repair source and rebuild with --strict")
    records = {name: read_jsonl(paths[name]) for name in ("train", "valid")}
    for name in records:
        if manifest["output_hashes"].get(f"{stage}_{name}.jsonl") != sha256(paths[name]):
            raise ValueError("Dataset checksum mismatch; regenerate data and manifest together")
    if not records["train"]:
        raise ValueError("Empty training dataset")
    check_split(records["train"], records["valid"])
    if manifest.get("format") == thinking.FORMAT:
        _check_thinking_records(records, stage)
        return records, manifest
    for split in records.values():
        for record in split:
            messages = record["messages"] if stage == "sft" else record["prompt"] + record["chosen"]
            if [m.get("role") for m in messages] != ["system", "user", "assistant"]:
                raise ValueError("Expected system/user/assistant chat")
            if messages[0]["content"] != production_prompt():
                raise ValueError("Record system prompt drift")
            target = json.loads(messages[-1]["content"])
            if serialize_planner_target(target) != messages[-1]["content"] or not chosen_ok(assess(target, messages[1]["content"])):
                raise ValueError("Invalid/noncanonical chosen grounding")
            if stage == "dpo":
                if [m.get("role") for m in record["rejected"]] != ["assistant"]:
                    raise ValueError("Rejected must contain one assistant message")
                rejected = json.loads(record["rejected"][0]["content"])
                if serialize_planner_target(rejected) != record["rejected"][0]["content"]:
                    raise ValueError("Rejected not canonical")
                if semantic_key(target, infer_events=True) == semantic_key(rejected, infer_events=True):
                    raise ValueError("Chosen/rejected identical")
                if record["metadata"].get("negative_category") not in {"semantic", "constraint"}:
                    raise ValueError("Missing DPO negative category")
    return records, manifest


def _check_thinking_records(records, stage):
    """Thinking corpus: answer JSON passes the existing (thor) contract check; chosen != rejected answer."""
    for split in records.values():
        for record in split:
            if not thinking.is_thinking(record):
                raise ValueError("Thinking manifest must not mix nonthinking records")
            messages = record["messages"] if stage == "sft" else record["prompt"] + record["chosen"]
            if [m.get("role") for m in messages] != ["system", "user", "assistant"]:
                raise ValueError("Expected system/user/assistant chat")
            if messages[0]["content"] != production_prompt():
                raise ValueError("Record system prompt drift")
            target = thinking.response_json(messages[-1]["content"])
            if not chosen_ok(assess(target, messages[1]["content"])):
                raise ValueError("Invalid chosen grounding in thinking response")
            if stage == "dpo":
                if [m.get("role") for m in record["rejected"]] != ["assistant"]:
                    raise ValueError("Rejected must contain one assistant message")
                rejected = thinking.response_json(record["rejected"][0]["content"])
                if semantic_key(target, infer_events=True) == semantic_key(rejected, infer_events=True):
                    raise ValueError("Chosen/rejected identical")
                if record["metadata"].get("negative_category") not in {"semantic", "constraint"}:
                    raise ValueError("Missing DPO negative category")


def render_prompt(tokenizer, messages, config):
    if not tokenizer.chat_template:
        raise ValueError("Tokenizer requires a chat template")
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True,
                                         **config.get("chat_template_kwargs", {}))


def render_records(tokenizer, records, config, stage):
    """Render generation prefix identically at train/eval; supervise only JSON+EOS.

    Use standard TRL prompt/completion strings to avoid dependence on a model's
    generation-mask template or Qwen's implicit thinking blocks in full chats.
    Fail on overlength rather than silently truncating prompt or JSON.
    """
    result = []
    args = config["training"]
    if not tokenizer.eos_token:
        raise ValueError("Tokenizer requires EOS")
    for record in records:
        prompt = render_prompt(tokenizer, record.get("messages", record.get("prompt"))[:2], config)
        if thinking.is_thinking(record):
            pids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
            result.append(thinking.render_thinking(tokenizer, record, config, stage, prompt, pids, args))
            continue
        row = {"prompt": prompt}
        fields = {"completion": record["messages"][-1]["content"]} if stage == "sft" else {
            key: record[key][0]["content"] for key in ("chosen", "rejected")}
        pids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
        if stage == "dpo" and len(pids) > args.get("max_prompt_length", 7168):
            raise ValueError("Prompt exceeds max_prompt_length; increase limits")
        for key, content in fields.items():
            text = content + (tokenizer.eos_token if stage == "sft" else "")
            completion_ids = tokenizer(content + tokenizer.eos_token, add_special_tokens=False)["input_ids"]
            maximum = args.get("max_seq_length", 8192) if stage == "sft" else args.get("max_length", 8192)
            if len(pids) + len(completion_ids) + 1 > maximum:
                raise ValueError("Example exceeds max length; refusing to truncate grounding")
            if stage == "dpo" and len(completion_ids) > args.get("max_completion_length", 1024):
                raise ValueError("JSON exceeds max_completion_length")
            if stage == "sft":
                whole = tokenizer(prompt + text, add_special_tokens=False)["input_ids"]
                if whole[:len(pids)] != pids:
                    raise ValueError("Chat prefix token boundary changed; completion loss would mask JSON incorrectly")
            row[key] = text
        result.append(row)
    return result


def tokenizer_for(config):
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(config["model"]["name_or_path"],
                                              trust_remote_code=config["model"].get("trust_remote_code", False),
                                              revision=config["model"].get("revision", "main"))
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    return tokenizer


def model_for(config):
    import os
    import torch
    from transformers import AutoModelForCausalLM
    spec, args = config["model"], config["training"]
    dtype = torch.bfloat16 if args.get("bf16") else torch.float16 if args.get("fp16") else torch.float32
    kwargs = dict(trust_remote_code=spec.get("trust_remote_code", False), torch_dtype=dtype,
                  revision=spec.get("revision", "main"))
    if spec.get('attn_implementation'):
        kwargs['attn_implementation'] = spec['attn_implementation']
    if spec.get("load_in_4bit"):
        from transformers import BitsAndBytesConfig
        from peft import prepare_model_for_kbit_training
        if not torch.cuda.is_available():
            raise ValueError("4-bit training requires a supported CUDA GPU; use --dry-run on CPU")
        from training.check_thor_env import cuda_tests
        compatibility = cuda_tests(torch, optional=True)
        if compatibility['qlora']['status'] != 'PASS':
            raise RuntimeError('QLoRA CUDA operation failed. Select the BF16 LoRA profile; no automatic objective/precision change: '
                               + str(compatibility['qlora']))
        kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                          bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype)
        kwargs["device_map"] = {"": int(os.environ.get("LOCAL_RANK", 0))}
    model = AutoModelForCausalLM.from_pretrained(spec["name_or_path"], **kwargs)
    model.config.use_cache = False
    if spec.get("load_in_4bit"):
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=args.get("gradient_checkpointing", True))
    return model


def peft_config_for(config, model):
    from peft import LoraConfig
    spec = config.get("lora", {})
    if not spec.get("enabled", True):
        return None
    targets = spec.get("target_modules", ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    validate_lora_targets(model, targets)
    return LoraConfig(task_type="CAUSAL_LM", r=spec.get("r", 16), lora_alpha=spec.get("alpha", 32),
                      lora_dropout=spec.get("dropout", 0.05), target_modules=targets, bias="none")


def validate_lora_targets(model, targets):
    counts = {target: 0 for target in targets}
    for name, _ in model.named_modules():
        for target in targets:
            if name == target or name.endswith('.' + target):
                counts[target] += 1
    if not counts or any(value == 0 for value in counts.values()):
        raise ValueError(f'LoRA target modules absent from model: {counts}')
    print(json.dumps({'lora_matched_modules': counts, 'total': sum(counts.values())}))
    return counts


def save_run(trainer, tokenizer, config, manifest, stage):
    output = Path(config["training"]["output_dir"])
    trainer.save_model(str(output))
    tokenizer.save_pretrained(str(output))
    (output / "training_provenance.json").write_text(json.dumps({"stage": stage, "config": config,
        "dataset_manifest": manifest, "prompt_hash": manifest["prompt_hash"]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cli(stage, argv=None):
    parser = argparse.ArgumentParser(description=f"GeoFlow grounding {stage.upper()} (optional GPU dependencies)")
    parser.add_argument("--config", default=f"training/configs/qwen_{stage}.yaml")
    parser.add_argument("--dry-run", action="store_true", help="CPU config, provenance, split and dataset validation; no model download")
    parser.add_argument("--tokenizer-check", action="store_true", help="Load tokenizer only, validate chat boundaries and token lengths")
    parser.add_argument("--resume-from-checkpoint", default=None)
    parser.add_argument('--max-steps', type=int, help='Override optimizer step count for a short benchmark')
    args = parser.parse_args(argv)
    config = load_config(args.config, stage)
    if args.max_steps is not None:
        if args.max_steps <= 0:
            parser.error('--max-steps must be positive')
        config['training']['max_steps'] = args.max_steps
    records, manifest = load_records(config, stage)
    # Smoke limits apply only after validating the complete source and split.
    for split, key in (('train', 'max_train_samples'), ('valid', 'max_valid_samples')):
        limit = config['data'].get(key)
        if limit is not None:
            if not isinstance(limit, int) or limit <= 0:
                raise ValueError(f'data.{key} must be a positive integer')
            records[split] = records[split][:limit]
    print(json.dumps({"stage": stage, "model": config["model"]["name_or_path"],
                      "train": len(records["train"]), "validation": len(records["valid"]),
                      "prompt_hash": manifest["prompt_hash"], "dry_run": args.dry_run}, ensure_ascii=False))
    if args.tokenizer_check:
        tokenizer = tokenizer_for(config)
        for rows in records.values():
            render_records(tokenizer, rows, config, stage)
        print("Tokenizer prefix and length checks passed")
    return args, config, records, manifest
