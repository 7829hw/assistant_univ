# -*- coding: utf-8 -*-
# [pilot_006 준비 W3 이식] 원본: geoflow/partial-grounding 커밋 ab9d215의 sft_dpo_inventory/p0_sft_004/loss_mask_audit.py. 본문은 원본 그대로다(아래 '이식 수정' 줄 제외).
# 원본의 경로 상수(ROOT 등)는 원 위치 기준이라 이 위치에서 바로 돌리려면 경로 인자를 확인한다. 참고값 경로(HF greedy·Ollama, 다른 장비)의 기록용 도구다.
"""FULL154 / JSON154 loss-mask·input 동일성·assistant 첫 token audit(지시 29–32절). 학습 전에 실제 label tensor를 본다. GPU 0.

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 /data/hwkim/path_repeat_001/venv/py/bin/python \
        sft_dpo_inventory/p0_sft_004/loss_mask_audit.py   # -> datasets/loss_mask_audit.json, datasets/loss_mask_examples.txt

- p0_sft_002/loss_mask_audit.py와 같은 방법(학습 경로 load_records → render_records → SFTTrainer.data_collator, 모델만 작은 무작위 Qwen3)이다.
- 154개 전부 영역별 LOSS·MASK를 세고 기대(아래 EXPECT)와 하나라도 다르면 ok false.
- 두 arm의 input_ids를 문항마다 실제로 비교한다(차이는 labels뿐이어야 한다).
- assistant 첫 위치(`<|im_start|>assistant\n` 바로 뒤) token과 그 label, '{'를 학습하는 레코드 수를 센다.
- 손실 token 통계: arm별·출처 묶음(8B / 27B / canonical)별 input·supervised·thinking supervised·JSON supervised.
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
    config = load_config(ROOT / f"training/configs/qwen3_8b_p0_sft004_{arm}.yaml", "sft")
    records, _ = load_records(config, "sft")
    tok = tokenizer_for(config)
    rendered = render_records(tok, records["train"], config, "sft")
    training = dict(config["training"])
    training["max_length"] = training.pop("max_seq_length", 8192)
    training.pop("resume_from_checkpoint", None)
    training.update(completion_only_loss=True, assistant_only_loss=False, packing=False, eval_strategy="no",
                    output_dir=str(Path("/data/hwkim/p0_sft_004/audit_tmp") / arm), bf16=False, gradient_checkpointing=False,
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
    summary, examples, bad, all_ids, per = {}, [], [], [], []
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
        first = next(i for i, (s, e) in enumerate(enc["offset_mapping"]) if s >= head)
        per.append({"id": record["metadata"]["source_record_id"], "source": record["metadata"]["reasoning_source"],
                    "input_tokens": len(ids), "supervised": sum(c["LOSS"] for c in counts.values()),
                    "thinking_supervised": sum(counts.get(r_, {}).get("LOSS", 0) for r_ in ("think_open", "thinking", "think_close")),
                    "json_supervised": sum(counts.get(r_, {}).get("LOSS", 0) for r_ in ("json", "eos")),
                    "first_token": tok.convert_ids_to_tokens(ids[first]), "first_token_supervised": labels[first] != -100,
                    "first_token_is_brace": full[enc["offset_mapping"][first][0]:enc["offset_mapping"][first][1]].startswith("{")})
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
            "expect": EXPECT[scope], "mismatch_records": bad, "ok": not bad}, examples, all_ids, per


def stats(per):
    groups = {"hf8b": ("hf8b_r70", "hf8b_m2", "hf8b_m3"), "t27b": ("t27b_p12", "t27b_remaining"), "canonical": ("manual_canonical",)}
    keys = ("input_tokens", "supervised", "thinking_supervised", "json_supervised")
    tot = {k: sum(p[k] for p in per) for k in keys}
    by = {g: {"records": sum(p["source"] in m for p in per), **{k: sum(p[k] for p in per if p["source"] in m) for k in keys}}
          for g, m in groups.items()}
    for g in by.values():
        g["share_of_supervised"] = round(g["supervised"] / tot["supervised"], 4) if tot["supervised"] else None
        g["share_of_thinking_supervised"] = round(g["thinking_supervised"] / tot["thinking_supervised"], 4) if tot["thinking_supervised"] else None
    first = {"first_tokens": dict(__import__("collections").Counter(p["first_token"] for p in per)),
             "first_token_supervised": sum(p["first_token_supervised"] for p in per),
             "brace_first_supervised": sum(p["first_token_is_brace"] and p["first_token_supervised"] for p in per),
             "brace_first_any": sum(p["first_token_is_brace"] for p in per)}
    return {"totals": tot, "by_group": by, "first_token": first}


def main():
    out, text, ids, per = {}, [], {}, {}
    for arm in ("full154", "json154"):
        res, ex, ids[arm], per[arm] = audit(arm)
        res["token_stats"] = stats(per[arm])
        out[arm] = res
        text += ex
    same = [a == b for a, b in zip(ids["full154"], ids["json154"])]
    out["input_ids_identical"] = {"records_compared": len(same), "identical": sum(same), "all": all(same) and len(same) == 154,
                                  "differing_ids": [p["id"] for p, s in zip(per["full154"], same) if not s]}
    out["per_record"] = {arm: per[arm] for arm in per}
    out["ok"] = out["full154"]["ok"] and out["json154"]["ok"] and out["input_ids_identical"]["all"] and \
        out["full154"]["token_stats"]["first_token"]["brace_first_supervised"] == 0 and \
        out["json154"]["token_stats"]["first_token"]["first_token_supervised"] == 0
    (HERE / "datasets/loss_mask_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "datasets/loss_mask_examples.txt").write_text("\n\n".join(text) + "\n", encoding="utf-8")
    print(json.dumps({"ok": out["ok"], "input_ids_identical": out["input_ids_identical"],
                      **{a: {x: out[a][x] for x in ("loss_scope", "ok", "mismatch_records", "region_token_counts", "token_stats")}
                         for a in ("full154", "json154")}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
