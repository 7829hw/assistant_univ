# -*- coding: utf-8 -*-
"""C6: 시험 빌드 손실 마스크 audit. partial-grounding ``p0_sft_004/loss_mask_audit.py``(이식본 ``pilot_006_prep/integration/pg_tools/
loss_mask_audit_p0_sft_004.py``)의 방법을 그대로 쓴다: 학습 경로(load_records → render_records → SFTTrainer.data_collator, 모델은 작은 무작위 Qwen3)로
실제 label tensor를 보고, 영역(system·user / <think> / thinking / </think> / JSON / EOS)별 LOSS·MASK를 센다. GPU 0.

    hfvenv/bin/python loss_mask_audit6.py CONFIG OUT.json

바꾼 것: config를 인자로 받는다. 결정 86 출처별(by_source)이라 기대 마스크(``EXPECT``, 원본과 같음)를 레코드의 ``metadata.loss_scope``로 고른다.
두 arm의 input_ids 비교는 하지 않는다(pilot_006은 arm마다 system prompt가 다르다).
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_006_prep/integration/pg_tools"))
from loss_mask_audit_p0_sft_004 import EXPECT, regions  # noqa: E402


def main():
    from datasets import Dataset
    from transformers import Qwen3Config, Qwen3ForCausalLM
    from trl import SFTConfig, SFTTrainer
    from training.trainer_common import load_config, load_records, render_records, tokenizer_for
    config_path, out = Path(sys.argv[1]), Path(sys.argv[2])
    config = load_config(config_path, "sft")
    records, _ = load_records(config, "sft")
    tok = tokenizer_for(config)
    rendered = render_records(tok, records["train"], config, "sft")
    training = dict(config["training"])
    training["max_length"] = training.pop("max_seq_length", 8192)
    training.pop("resume_from_checkpoint", None)
    training.update(completion_only_loss=True, assistant_only_loss=False, packing=False, eval_strategy="no",
                    output_dir="/tmp/pilot006_loss_mask_audit", bf16=False, gradient_checkpointing=False, report_to="none")
    tiny = Qwen3ForCausalLM(Qwen3Config(vocab_size=len(tok), hidden_size=32, intermediate_size=64, num_hidden_layers=1,
                                        num_attention_heads=2, num_key_value_heads=1, head_dim=16))
    trainer = SFTTrainer(model=tiny, args=SFTConfig(**training), processing_class=tok, train_dataset=Dataset.from_list(rendered))
    summary, bad, per = {}, [], []
    for idx, (record, row) in enumerate(zip(records["train"], trainer.train_dataset)):
        scope = record["metadata"]["loss_scope"]
        batch = trainer.data_collator([row])
        ids, labels = batch["input_ids"][0].tolist(), batch["labels"][0].tolist()
        r = rendered[idx]
        full = r["prompt"] + r["completion"]
        head = full.find("<|im_start|>assistant\n") + len("<|im_start|>assistant\n")
        enc = tok(full, add_special_tokens=False, return_offsets_mapping=True)
        if enc["input_ids"] != ids:
            raise SystemExit(f"#{idx}: collator input_ids가 원문 tokenize와 다르다")
        of, _ = regions(full, head)
        counts = {}
        for i, ((s, e), lab) in enumerate(zip(enc["offset_mapping"], labels)):
            reg = "eos" if ids[i] == tok.eos_token_id and i == len(ids) - 1 else of(s)
            counts.setdefault(reg, {"LOSS": 0, "MASK": 0})["MASK" if lab == -100 else "LOSS"] += 1
        ok = all(counts.get(reg, {}).get("LOSS" if want == "MASK" else "MASK", 0) == 0 and counts.get(reg, {}).get(want, 0) > 0
                 for reg, want in EXPECT[scope].items())
        if not ok:
            bad.append(record["metadata"]["trace_id"])
        per.append({"scope": scope, "supervised": sum(c["LOSS"] for c in counts.values()),
                    "thinking_supervised": sum(counts.get(x, {}).get("LOSS", 0) for x in ("think_open", "thinking", "think_close"))})
        for reg, c in counts.items():
            agg = summary.setdefault(f"{scope}:{reg}", {"LOSS": 0, "MASK": 0})
            agg["LOSS"] += c["LOSS"]
            agg["MASK"] += c["MASK"]
    res = {"config": str(config_path), "grounding_target": config["data"].get("grounding_target", "full"), "records": len(per),
           "by_scope": dict(Counter(p["scope"] for p in per)), "region_token_counts": summary, "expect": EXPECT, "mismatch_records": bad,
           "supervised_tokens": {s: sum(p["supervised"] for p in per if p["scope"] == s) for s in ("full_response", "json_only")},
           "ok": not bad, "method": "pg p0_sft_004 loss_mask_audit와 같은 collator 기반 label 확인"}
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("grounding_target", "records", "by_scope", "ok", "mismatch_records", "supervised_tokens")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
