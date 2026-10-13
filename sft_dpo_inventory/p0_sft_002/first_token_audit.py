# -*- coding: utf-8 -*-
"""보조 검증(결과 뒤 추가, 모델 호출 없음): 학습 데이터에서 assistant 첫 위치(`<|im_start|>assistant\\n` 바로 뒤) token이 손실을 받는가, 받는다면 어떤 token인가.

    HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 python sft_dpo_inventory/p0_sft_002/first_token_audit.py

render_records(학습과 같은 렌더링) 결과에서 prompt가 `assistant\\n`으로 끝나면 completion 첫 token이 손실을 받는 첫 assistant token이다.
prompt가 thinking까지 포함하면(json_only thinking 레코드) assistant 첫 위치(`<think>`)는 prompt 쪽이라 손실이 없다.
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from training.trainer_common import load_config, load_records, render_records, tokenizer_for  # noqa: E402

CONFIGS = {"p0_sft_001 gold_only(json_only)": "qwen3_8b_p0_sft001_gold_only.yaml",
           "p0_sft_001 clean_hybrid(json_only)": "qwen3_8b_p0_sft001_clean_hybrid.yaml",
           "p0_sft_002 r70_json(json_only)": "qwen3_8b_p0_sft002_r70_json.yaml",
           "p0_sft_002 r70_full(full_response)": "qwen3_8b_p0_sft002_r70_full.yaml"}


def main():
    out = {}
    for name, cfg in CONFIGS.items():
        config = load_config(ROOT / "training/configs" / cfg, "sft")
        records, _ = load_records(config, "sft")
        tok = tokenizer_for(config)
        c = collections.Counter()
        for r in render_records(tok, records["train"], config, "sft"):
            if r["prompt"].endswith("<|im_start|>assistant\n"):
                first = tok.convert_ids_to_tokens(tok(r["completion"], add_special_tokens=False)["input_ids"][:1])[0]
                c[f"LOSS {first}"] += 1
            else:
                c["MASK (assistant 첫 위치가 prompt 쪽)"] += 1
        out[name] = {"records": len(records["train"]), "assistant_first_position": dict(c)}
    (HERE / "first_token_audit.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
