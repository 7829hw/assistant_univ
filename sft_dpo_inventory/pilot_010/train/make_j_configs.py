# -*- coding: utf-8 -*-
"""pilot_010 판정 단계 학습 config 5개(결정 267 D2). 선택 단계 ``configs_s10/S-V4-o43.yaml``(그대로 둠)에서 순서 seed·O4' 순서 파일·출력만 바꾼다.

- data = V4 그대로(``pilot_010/build/V4/full``), recipe R1''·모델 seed 43(``training.seed``·``data_seed`` 43)·LoRA r16/α32·12,288·thinking ON·by_source는 바탕과 같다.
- 순서 seed = PLAN_J 예약 seed 101·523·2029·31·20271027, 순서 파일 = ``build/V4/order_b2_o<seed>.json``(``build/make_orders_j.py``).
- 출력 = ``/data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o<seed>``(결정 258 외부 저장소). wrapper ``pilot_007/train/train_b7b.py``(epoch 끝 = checkpoint-1984).

    python3 sft_dpo_inventory/pilot_010/train/make_j_configs.py   # -> configs_j/J-V4-o<seed>.yaml, configs_j/DIFF.md
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SRC = HERE / "configs_s10/S-V4-o43.yaml"
OUT = "/data/hwkim/sftdpo_work/pilot_010/train_j"
SEEDS = (101, 523, 2029, 31, 20271027)
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
    assert base["data"]["train"] == "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl" and base["training"]["seed"] == 43 and base["training"]["data_seed"] == 43
    (HERE / "configs_j").mkdir(exist_ok=True)
    diff = ["# 판정 단계 config와 선택 단계 S-V4-o43.yaml의 차이", "", "바꾼 키: " + ", ".join(sorted(CHANGED)) + ". 그 밖은 모두 같다(아래 검사).", ""]
    for s in SEEDS:
        jid = f"J-V4-o{s}"
        c = yaml.safe_load(SRC.read_text(encoding="utf-8"))
        c["training"].update(shared_slot_order_seed=s, shared_slot_order_file=f"sft_dpo_inventory/pilot_010/build/V4/order_b2_o{s}.json", output_dir=f"{OUT}/{jid}")
        c["profiling"]["output"] = f"{OUT}/{jid}_profile.json"
        fb, fc = flat(base), flat(c)
        changed = {k for k in fb.keys() | fc.keys() if fb.get(k) != fc.get(k)}
        assert changed == CHANGED, changed
        (HERE / f"configs_j/{jid}.yaml").write_text(f"# pilot_010 {jid}(결정 267 D2): configs_s10/S-V4-o43.yaml에서 순서 seed {s}·O4' 순서 파일·출력만 바꿈. train_b7b.py.\n"
                                                   + yaml.safe_dump(c, allow_unicode=True, sort_keys=False), encoding="utf-8")
        diff.append(f"- {jid}: shared_slot_order_seed 43 → {s}, shared_slot_order_file → build/V4/order_b2_o{s}.json, output {OUT}/{jid}")
    (HERE / "configs_j/DIFF.md").write_text("\n".join(diff) + "\n", encoding="utf-8")
    print("\n".join(diff))


if __name__ == "__main__":
    main()
