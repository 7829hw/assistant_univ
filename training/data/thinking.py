"""Thinking-format training records (reasoning + JSON completions) for thinking-ON training.

The nonthinking path (JSON-only completion, ``enable_thinking=False``) is unchanged. Thinking records are marked
with ``metadata.format == "thinking"``; the trainer renders them with this module.

- The assistant content is the model's own decoded response, ``<think>\\n…\\n</think>\\n\\n{json}``, exactly as
  generated (``skip_special_tokens=True`` keeps ``<think>``/``</think>``, which are not special tokens in Qwen3).
- Prompt rendering is the same ``render_prompt`` used for inference; configs must set
  ``chat_template_kwargs.enable_thinking: true`` (generation prefix ends with ``<|im_start|>assistant\\n``).
- Loss scope (``thinking.loss_scope`` in the config, no default):
  - ``full_response``: completion = whole response + EOS (reasoning and JSON are supervised).
  - ``json_only``: the reasoning is appended to the prompt; completion = JSON + EOS (SFT only). DPO pairs carry
    different reasoning for chosen and rejected, so they cannot share a prompt; ``json_only`` is refused for DPO.
"""
import json

FORMAT = "thinking"
LOSS_SCOPES = ("full_response", "json_only")
THINK_END = "</think>"


def split_response(text):
    """Response -> (reasoning part incl. ``</think>`` and following whitespace, JSON part)."""
    if THINK_END not in text:
        raise ValueError("Thinking response lacks </think>; truncated or not a thinking response")
    head, tail = text.split(THINK_END, 1)
    stripped = tail.lstrip()
    return head + THINK_END + tail[:len(tail) - len(stripped)], stripped


def response_json(text):
    """The JSON object of a thinking response (production tolerant extractor on the part after ``</think>``)."""
    from geoflow.planner import parse_planner_json
    return parse_planner_json(split_response(text)[1])


def is_thinking(record):
    return (record.get("metadata") or {}).get("format") == FORMAT


def loss_scope(config):
    scope = (config.get("thinking") or {}).get("loss_scope")
    if scope not in LOSS_SCOPES:
        raise ValueError(f"thinking.loss_scope must be one of {LOSS_SCOPES} (no default)")
    return scope


def render_thinking(tokenizer, record, config, stage, prompt, pids, args):
    """Prompt/completion strings for one thinking record; mirrors trainer_common.render_records guards."""
    if not (config.get("chat_template_kwargs") or {}).get("enable_thinking"):
        raise ValueError("Thinking records require chat_template_kwargs.enable_thinking: true")
    scope = loss_scope(config)
    row = {"prompt": prompt}
    if stage == "sft":
        content = record["messages"][-1]["content"]
        reasoning, answer = split_response(content)
        if scope == "json_only":
            row["prompt"] = prompt + reasoning
            pids = tokenizer(row["prompt"], add_special_tokens=False)["input_ids"]
            body = answer
        else:
            body = content
        text = body + tokenizer.eos_token
        completion_ids = tokenizer(text, add_special_tokens=False)["input_ids"]
        if len(pids) + len(completion_ids) + 1 > args.get("max_seq_length", 8192):
            raise ValueError("Example exceeds max length; refusing to truncate thinking response")
        whole = tokenizer(row["prompt"] + text, add_special_tokens=False)["input_ids"]
        if whole[:len(pids)] != pids or whole[len(pids):] != completion_ids:
            raise ValueError("Thinking prompt/completion token boundary changed")
        row["completion"] = text
        return row
    if scope != "full_response":
        raise ValueError("DPO thinking pairs need loss_scope full_response: chosen and rejected reasoning differ, "
                         "so the reasoning cannot be part of a shared prompt")
    if len(pids) > args.get("max_prompt_length", 7168):
        raise ValueError("Prompt exceeds max_prompt_length; increase limits")
    for key in ("chosen", "rejected"):
        content = record[key][0]["content"]
        split_response(content)
        ids = tokenizer(content + tokenizer.eos_token, add_special_tokens=False)["input_ids"]
        if len(pids) + len(ids) + 1 > args.get("max_length", 8192):
            raise ValueError("Example exceeds max length; refusing to truncate thinking response")
        if len(ids) > args.get("max_completion_length", 1024):
            raise ValueError("Thinking response exceeds max_completion_length")
        row[key] = content
    return row


def sft_record(trace, gold_record, *, source):
    """SFT record from one judged-correct trace. ``trace`` needs raw_text, trace_id, raw_sha256."""
    response_json(trace["raw_text"])
    meta = dict(gold_record["metadata"])
    meta.update(format=FORMAT, source=source, trace_id=trace["trace_id"], trace_sha256=trace["raw_sha256"],
                trace_kind=trace.get("kind"), reasoning_human_reviewed=False)
    return {"messages": [*gold_record["messages"][:2], {"role": "assistant", "content": trace["raw_text"]}],
            "metadata": meta}


def dpo_pair(chosen, rejected, gold_record, *, source, negative_category, details):
    meta = dict(gold_record["metadata"])
    meta.update(format=FORMAT, source=source, chosen_trace_id=chosen["trace_id"], rejected_trace_id=rejected["trace_id"],
                negative_type="model_sample_disagrees_with_gold", negative_category=negative_category,
                mutation_source="hf_base_thinking_sample", negative_details=details, reasoning_human_reviewed=False)
    return {"prompt": gold_record["messages"][:2], "chosen": [{"role": "assistant", "content": chosen["raw_text"]}],
            "rejected": [{"role": "assistant", "content": rejected["raw_text"]}], "metadata": meta}


def canonical_answer(content):
    """Canonical JSON of a thinking response's answer (for validation and identity checks)."""
    return json.dumps(response_json(content), ensure_ascii=False, sort_keys=True)
