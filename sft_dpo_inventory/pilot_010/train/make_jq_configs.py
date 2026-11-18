# -*- coding: utf-8 -*-
"""pilot_010 JQ(결정 269) RR+NM8(V8) 새 seed 학습 config 4개. 선택 단계 ``configs_s10/S-V8-o43.yaml``(그대로 둠)에서 순서 seed·O4' 순서 파일·출력만 바꾼다.
판정 단계 ``make_j_configs.py``(V4)와 같은 방식·같은 바꾼 키.

- data = V8 그대로(``pilot_010/build/V8/full``), recipe R1''·모델 seed 43·LoRA r16/α32·12,288·thinking ON·by_source는 바탕과 같다(검사).
- 순서 seed = ``build/seeds_jq.json``, 순서 파일 = ``build/V8/order_b2_o<seed>.json``(``build/make_orders_jq.py``).
- 출력 = ``/data/hwkim/sftdpo_work/pilot_010/train_jq/JQ-V8-o<seed>``. wrapper ``pilot_007/train/train_b7b.py``(epoch 끝 = checkpoint-2071).

    python3 sft_dpo_inventory/pilot_010/train/make_jq_configs.py   # -> configs_jq/JQ-V8-o<seed>.yaml, configs_jq/DIFF.md
"""
import json
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SRC = HERE / "configs_s10/S-V8-o43.yaml"
OUT = "/data/hwkim/sftdpo_work/pilot_010/train_jq"
SEEDS = tuple(json.loads((HERE.parent / "build/seeds_jq.json").read_text(encoding="utf-8"))["order_seeds"])
CHANGED = {"training.shared_slot_order_seed", "training.shared_slot_order_file", "training.output_dir", "profiling.output"}


def flat(d, p=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flat(v, f"{p}{k}."))
        else:
            out[f"{p}{k}"] = v
    return out


def main():
    base = yaml.safe_load(SRC.read_text(encoding="utf-8"))
    assert base["data"]["train"] == "sft_dpo_inventory/pilot_010/build/V8/full/sft_train.jsonl" and base["training"]["seed"] == 43 and base["training"]["data_seed"] == 43
    assert base["chat_template_kwargs"]["enable_thinking"] is True and base["thinking"]["loss_scope"] == "by_source" and base["data"]["grounding_target"] == "full"
    (HERE / "configs_jq").mkdir(exist_ok=True)
    diff = ["# JQ config와 선택 단계 S-V8-o43.yaml의 차이(결정 269)", "", "바꾼 키: " + ", ".join(sorted(CHANGED)) + ". 그 밖은 모두 같다(아래 검사).", ""]
    for s in SEEDS:
        jid = f"JQ-V8-o{s}"
        c = yaml.safe_load(SRC.read_text(encoding="utf-8"))
        c["training"].update(shared_slot_order_seed=s, shared_slot_order_file=f"sft_dpo_inventory/pilot_010/build/V8/order_b2_o{s}.json", output_dir=f"{OUT}/{jid}")
        c["profiling"]["output"] = f"{OUT}/{jid}_profile.json"
        fb, fc = flat(base), flat(c)
        changed = {k for k in fb.keys() | fc.keys() if fb.get(k) != fc.get(k)}
        assert changed == CHANGED, changed
        (HERE / f"configs_jq/{jid}.yaml").write_text(f"# pilot_010 {jid}(결정 269): configs_s10/S-V8-o43.yaml에서 순서 seed {s}·O4' 순서 파일·출력만 바꿈. train_b7b.py.\n"
                                                    + yaml.safe_dump(c, allow_unicode=True, sort_keys=False), encoding="utf-8")
        diff.append(f"- {jid}: shared_slot_order_seed 43 → {s}, shared_slot_order_file → build/V8/order_b2_o{s}.json, output {OUT}/{jid}")
    (HERE / "configs_jq/DIFF.md").write_text("\n".join(diff) + "\n", encoding="utf-8")
    print("\n".join(diff))


if __name__ == "__main__":
    main()
