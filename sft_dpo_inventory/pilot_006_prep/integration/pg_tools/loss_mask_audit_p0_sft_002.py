# -*- coding: utf-8 -*-
# [pilot_006 준비 W3 이식] 원본: geoflow/partial-grounding 커밋 ab9d215의 sft_dpo_inventory/p0_sft_002/loss_mask_audit.py. 본문은 원본 그대로다(아래 '이식 수정' 줄 제외).
# 원본의 경로 상수(ROOT 등)는 원 위치 기준이라 이 위치에서 바로 돌리려면 경로 인자를 확인한다. 참고값 경로(HF greedy·Ollama, 다른 장비)의 기록용 도구다.
"""R70 loss mask audit(PLAN.md 4절). 학습 전에 실제 label tensor를 본다. GPU를 쓰지 않는다.

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 python sft_dpo_inventory/p0_sft_002/loss_mask_audit.py
    # -> loss_mask_audit.json, loss_mask_examples.txt

- 학습 경로(`training.train_sft.train`)와 같은 순서로 만든다.
  - config → `load_records` → `render_records` → SFTConfig(같은 training dict 수정) → SFTTrainer → `trainer.data_collator`
  - 모델만 작은 무작위 Qwen3(같은 tokenizer, CPU)로 바꾼다. dataset 처리와 collator(labels 생성)는 모델과 무관하다.
  - 그래서 labels는 실제 학습 때와 같은 TRL 코드로 만든 tensor다.
- 각 token을 원문 위치로 영역에 나눈다:
  system_user(assistant 머리 포함) / think_open(`<think>`) / thinking(본문) / think_close(`</think>`와 뒤 줄바꿈) / json / eos.
- 기대(지시 13절):
  - json_only: system_user·think_open·thinking·think_close MASK, json·eos LOSS
  - full_response: system_user MASK, 나머지 전부 LOSS
- 70개 전부 영역별 LOSS·MASK 수를 세고, 기대와 하나라도 다르면 `ok: false`. 예제 3개는 영역 경계 token을 사람이 읽을 수 있게 남긴다.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

EXPECT = {"json_only": {"system_user": "MASK", "think_open": "MASK", "thinking": "MASK", "think_close": "MASK",
                        "json": "LOSS", "eos": "LOSS"},
          "full_response": {"system_user": "MASK", "think_open": "LOSS", "thinking": "LOSS", "think_close": "LOSS",
                            "json": "LOSS", "eos": "LOSS"}}


def build(arm):
    from transformers import Qwen3Config, Qwen3ForCausalLM
    from trl import SFTConfig, SFTTrainer
    from datasets import Dataset
    from training.trainer_common import load_config, load_records, render_records, tokenizer_for
    config = load_config(ROOT / f"training/configs/qwen3_8b_p0_sft002_r70_{arm}.yaml", "sft")
    records, _ = load_records(config, "sft")
    tok = tokenizer_for(config)
    rendered = render_records(tok, records["train"], config, "sft")
    training = dict(config["training"])
    training["max_length"] = training.pop("max_seq_length", 8192)
    training.pop("resume_from_checkpoint", None)
    training.update(completion_only_loss=True, assistant_only_loss=False, packing=False, eval_strategy="no",
                    output_dir=str(Path("/data/hwkim/p0_sft_002/audit_tmp") / arm), bf16=False, gradient_checkpointing=False,
                    report_to="none")
    tiny = Qwen3ForCausalLM(Qwen3Config(vocab_size=len(tok), hidden_size=32, intermediate_size=64, num_hidden_layers=1,
                                        num_attention_heads=2, num_key_value_heads=1, head_dim=16))
    trainer = SFTTrainer(model=tiny, args=SFTConfig(**training), processing_class=tok,
                         train_dataset=Dataset.from_list(rendered))
    return config, records["train"], rendered, trainer, tok


def regions(text, prompt_head_len):
    """원문 문자 위치 → 영역 함수."""
    t_open = text.find("<think>", prompt_head_len - 1 if prompt_head_len else 0)
    t_close = text.find("</think>")
    j = text.find("{", t_close if t_close >= 0 else 0)
    body_start = t_open + len("<think>")
    close_end = t_close + len("</think>")

    def of(pos):
        if pos < t_open:
            return "system_user"
        if pos < body_start:
            return "think_open"
        if pos < t_close:
            return "thinking"
        if pos < j:
            return "think_close"
        return "json"
    return of, (t_open, body_start, t_close, close_end, j)


def audit(arm):
    config, records, rendered, trainer, tok = build(arm)
    scope = config["thinking"]["loss_scope"]
    summary, examples, bad, all_ids = {}, [], [], []
    for idx, (record, row) in enumerate(zip(records, trainer.train_dataset)):
        batch = trainer.data_collator([row])
        ids = batch["input_ids"][0].tolist()
        labels = batch["labels"][0].tolist()
        all_ids.append(ids)
        r = rendered[idx]
        full = r["prompt"] + r["completion"]
        head = full.find("<|im_start|>assistant\n") + len("<|im_start|>assistant\n")
        enc = tok(full, add_special_tokens=False, return_offsets_mapping=True)
        if enc["input_ids"] != ids:
            raise SystemExit(f"{arm} #{idx}: collator input_ids가 원문 tokenize와 다르다")
        of, cuts = regions(full, head)
        counts = {}
        token_regions = []
        for i, ((s, e), lab) in enumerate(zip(enc["offset_mapping"], labels)):
            reg = "eos" if ids[i] == tok.eos_token_id and i == len(ids) - 1 else of(s)
            kind = "MASK" if lab == -100 else "LOSS"
            counts.setdefault(reg, {"LOSS": 0, "MASK": 0})[kind] += 1
            token_regions.append((reg, kind))
        ok = all(counts.get(reg, {}).get("LOSS" if want == "MASK" else "MASK", 0) == 0 and
                 counts.get(reg, {}).get(want, 0) > 0 for reg, want in EXPECT[scope].items())
        if not ok:
            bad.append(record["metadata"]["source_record_id"])
        for reg, c in counts.items():
            agg = summary.setdefault(reg, {"LOSS": 0, "MASK": 0})
            agg["LOSS"] += c["LOSS"]
            agg["MASK"] += c["MASK"]
        if idx < 3:
            lines = [f"### {arm} 예제 {idx + 1}: {record['metadata']['source_record_id']} "
                     f"(token {len(ids)}, prompt 쪽 {sum(1 for x in labels if x == -100)} MASK)"]
            prev = None
            for i, ((reg, kind), (s, e)) in enumerate(zip(token_regions, enc["offset_mapping"])):
                if (reg, kind) != prev or i == len(ids) - 1:
                    lines.append(f"  [{i:5d}] {reg:<12} {kind:<4} {json.dumps(full[s:e] if reg != 'eos' else tok.eos_token, ensure_ascii=False)}")
                    prev = (reg, kind)
            examples.append("\n".join(lines))
    return {"loss_scope": scope, "records": len(records), "region_token_counts": summary,
            "expect": EXPECT[scope], "mismatch_records": bad, "ok": not bad}, examples, all_ids


def main():
    out, text, ids = {}, [], {}
    for arm in ("json", "full"):
        res, ex, ids[arm] = audit(arm)
        out[f"r70_{arm}"] = res
        text += ex
    # 두 arm의 collator input_ids가 문항마다 같은가(차이는 labels뿐이어야 한다).
    out["identical_input_ids_both_arms"] = ids["json"] == ids["full"]
    (HERE / "loss_mask_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "loss_mask_examples.txt").write_text("\n\n".join(text) + "\n", encoding="utf-8")
    print(json.dumps({k: {x: v[x] for x in ("loss_scope", "ok", "region_token_counts")} for k, v in out.items()
                      if isinstance(v, dict)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
