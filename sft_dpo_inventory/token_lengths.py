# -*- coding: utf-8 -*-
"""reviewed gold v003 학습 입력의 system prompt를 현재 prompt(87048d0c)로 바꿨을 때의 token 길이. GPU·weights 없음.

    python sft_dpo_inventory/token_lengths.py --tokenizer-dir DIR [--thor-root THOR_WORKTREE]

- tokenizer: thor와 같은 Qwen/Qwen3-8B revision b968826d…의 tokenizer 파일만 쓴다(``DIR``에 tokenizer.json,
  tokenizer_config.json, vocab.json, merges.txt). 파일 hash를 thor receipt(token_validation.json)와 대조한다.
- 측정 방식은 thor ``training/data/analyze_tokens.analyze``와 같다: chat template(enable_thinking=False)의 생성
  prefix, JSON+EOS completion, total = max(p+n, 이어 붙인 문자열의 길이) + 1(trainer guard).
- ``--thor-root``를 주면 그 worktree에서 522aa3b1 prompt를 만들어 같은 측정을 하고, thor가 저장한
  token_lengths.jsonl과 일치하는지로 측정 방법을 대조한다.
- transformers(>=4.56.1,<4.57)가 필요하다. torch는 필요 없다.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from _common import (CORPORA, T2PC_PROMPT_SHA, THOR_PROMPT_SHA, production_prompt, sha256_file, thor_json,
                     thor_yaml, git_show, write_output)

LIMITS = {
    "pilot003": {"sft_total": 7040, "dpo_total": 7040, "dpo_prompt": 6816, "dpo_completion": 256},
    "pilot001_002": {"sft_total": 6912, "dpo_total": 6912, "dpo_prompt": 6784, "dpo_completion": 256},
}


def thor_prompt(thor_root):
    code = ("import sys; from geoflow.planner import GeoFlowPlanner; "
            "sys.stdout.write(GeoFlowPlanner(client=None).system_prompt())")
    text = subprocess.check_output([sys.executable, "-c", code], cwd=thor_root,
                                   env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"}).decode("utf-8")
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != THOR_PROMPT_SHA:
        raise SystemExit("thor worktree의 prompt hash가 522aa3b1이 아닙니다")
    return text


def measure(tokenizer, kwargs, system, record, stage):
    messages = record["messages"][:2] if stage == "sft" else record["prompt"]
    messages = [{"role": m["role"], "content": system if m["role"] == "system" else m["content"]}
                for m in messages]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, **kwargs)
    p = len(tokenizer(prompt, add_special_tokens=False)["input_ids"])
    fields = ({"completion": record["messages"][-1]["content"]} if stage == "sft"
              else {k: record[k][0]["content"] for k in ("chosen", "rejected")})
    completions, totals = {}, {}
    for key, content in fields.items():
        completion = content + tokenizer.eos_token
        n = len(tokenizer(completion, add_special_tokens=False)["input_ids"])
        completions[key] = n
        totals[key] = max(p + n, len(tokenizer(prompt + completion, add_special_tokens=False)["input_ids"])) + 1
    return {"prompt": p, "completions": completions, "total": max(totals.values())}


def limit_failures(row, stage, limits):
    fails = []
    if stage == "sft" and row["total"] > limits["sft_total"]:
        fails.append("total")
    if stage == "dpo":
        if row["total"] > limits["dpo_total"]:
            fails.append("total")
        if row["prompt"] > limits["dpo_prompt"]:
            fails.append("prompt")
        if max(row["completions"].values()) > limits["dpo_completion"]:
            fails.append("completion")
    return fails


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tokenizer-dir", required=True)
    parser.add_argument("--thor-root", default="")
    args = parser.parse_args()

    from transformers import AutoTokenizer, __version__ as tf_version

    receipt = thor_json(f"{CORPORA}/reviewed_gold_v003/token_validation.json")
    directory = Path(args.tokenizer_dir)
    files = {name: sha256_file(directory / name) for name in receipt["tokenizer_file_hashes"]}
    if files != receipt["tokenizer_file_hashes"]:
        raise SystemExit(f"tokenizer 파일 hash가 thor receipt와 다릅니다: {files}")
    tokenizer = AutoTokenizer.from_pretrained(str(directory))
    template_sha = hashlib.sha256(tokenizer.chat_template.encode("utf-8")).hexdigest()
    kwargs = thor_yaml("training/configs/qwen3_8b_thor_pilot_003_sft.yaml")["chat_template_kwargs"]

    index = thor_json(f"{CORPORA}/reviewed_gold_v003/dataset_index.json")
    new_prompt = production_prompt()
    new_sha = hashlib.sha256(new_prompt.encode("utf-8")).hexdigest()
    if new_sha != T2PC_PROMPT_SHA:
        raise SystemExit(f"현재 prompt hash가 87048d0c가 아닙니다: {new_sha}")
    prompts = {"87048d0c": new_prompt}
    if args.thor_root:
        prompts["522aa3b1"] = thor_prompt(args.thor_root)

    recorded = {}
    for line in git_show(f"{CORPORA}/reviewed_gold_v003/token_lengths.jsonl").decode("utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            recorded.setdefault((row["stage"], row["split"], row["source_record_id"]), []).append(row)

    rows = []
    for split_key, records in index.items():
        stage, split = split_key.split("_")
        for position, record in enumerate(records):
            meta = record["metadata"]
            row = {"stage": stage, "split": split, "position": position, "id": meta["source_record_id"],
                   "batch_item_ids": meta.get("batch_item_ids") or [], "negative_type": meta.get("negative_type")}
            for label, system in prompts.items():
                row[label] = measure(tokenizer, kwargs, system, record, stage)
                row[label]["limit_failures"] = {name: limit_failures(row[label], stage, limits)
                                                for name, limits in LIMITS.items()}
            rows.append(row)

    control = None
    if "522aa3b1" in prompts:
        # thor 기록은 같은 (stage, split, id)를 여러 행으로 가질 수 있어 기록 순서대로 대조한다.
        used, mismatched = {}, []
        for row in rows:
            key = (row["stage"], row["split"], row["id"])
            i = used.get(key, 0)
            used[key] = i + 1
            ref = (recorded.get(key) or [None] * (i + 1))[i]
            mine = row["522aa3b1"]
            if ref is None or ref["prompt"] != mine["prompt"] or ref["total"] != mine["total"] \
                    or ref["completions"] != mine["completions"]:
                mismatched.append({"key": list(key), "recorded": ref, "measured": mine})
        control = {"rows": len(rows), "matched": len(rows) - len(mismatched), "mismatched": mismatched[:10]}

    def stats(stage, label, field):
        values = sorted((r[label][field] if field != "completion" else max(r[label]["completions"].values()))
                        for r in rows if r["stage"] == stage)
        return {"n": len(values), "min": values[0], "p50": values[len(values) // 2], "max": values[-1]}

    summary = {
        "tokenizer": {"model": "Qwen/Qwen3-8B", "revision": receipt["model"]["revision"], "files": files,
                      "chat_template_sha256": template_sha,
                      "chat_template_matches_thor": template_sha == receipt["tokenizer_chat_template_sha256"],
                      "chat_template_kwargs": kwargs, "transformers": tf_version},
        "prompts": {label: {"sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "chars": len(text)}
                    for label, text in prompts.items()},
        "control_vs_thor_token_lengths_jsonl": control,
        "limits": LIMITS,
        "stats": {label: {stage: {f: stats(stage, label, f) for f in ("prompt", "completion", "total")}
                          for stage in ("sft", "dpo")} for label in prompts},
        "prompt_delta_tokens": sorted({r["87048d0c"]["prompt"] - r["522aa3b1"]["prompt"] for r in rows})
        if "522aa3b1" in prompts else None,
        "blocked": {label: {name: sum(1 for r in rows if r[label]["limit_failures"][name]) for name in LIMITS}
                    for label in prompts},
        "minimum_limits_87048d0c": {
            "sft_total": max(r["87048d0c"]["total"] for r in rows if r["stage"] == "sft"),
            "dpo_total": max(r["87048d0c"]["total"] for r in rows if r["stage"] == "dpo"),
            "dpo_prompt": max(r["87048d0c"]["prompt"] for r in rows if r["stage"] == "dpo"),
            "dpo_completion": max(max(r["87048d0c"]["completions"].values()) for r in rows if r["stage"] == "dpo"),
        },
    }
    path, digest = write_output("token_lengths_87048d0c.json", {"summary": summary, "rows": rows})
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print(f"\nwrote {path} sha256={digest}")


if __name__ == "__main__":
    main()
