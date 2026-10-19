# -*- coding: utf-8 -*-
"""A3단계 config 여섯(결정 186). A단계 ``configs/A-R1-o<seed>.yaml``(1 epoch, 끝 lr 0, batch 1·accum 1, warmup 1, 모델 seed 43, data_seed = 순서 seed)에서
데이터(RC5/full)·learning_rate·출력만 바꾼다. 학습은 ``train_a7.py``(25·50·75·100% 저장).

    python3 make_a3_configs.py   # -> configs_a3/{R1p,R1pp}-o{43,1016,7}.yaml, configs_a3/DIFF.md
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
RC = "sft_dpo_inventory/pilot_007/build/RC5/full"
OUT = "/home/hwkim/sftdpo_work/pilot_007/train_a3"
KEYS = ("num_train_epochs", "gradient_accumulation_steps", "learning_rate", "warmup_steps", "warmup_ratio", "seed", "data_seed", "output_dir")
diff = ["# A3 config와 A단계 A-R1 config의 차이", ""]
for tag, lr in (("R1p", 1.0e-04), ("R1pp", 2.0e-04)):
    for o in ("o43", "o1016", "o7"):
        jid = f"{tag}-{o}"
        src = HERE / f"configs/A-R1-{o}.yaml"
        cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
        before = {k: cfg["training"].get(k) for k in KEYS}
        cfg["data"].update(train=f"{RC}/sft_train.jsonl", valid=f"{RC}/sft_valid.jsonl", manifest=f"{RC}/manifest.json")
        cfg["training"].update(learning_rate=lr, output_dir=f"{OUT}/{jid}")
        cfg["profiling"]["output"] = f"{OUT}/{jid}_profile.json"
        after = {k: cfg["training"].get(k) for k in KEYS}
        (HERE / f"configs_a3/{jid}.yaml").write_text(f"# pilot_007 A3 {jid}(결정 186): {src.name}에서 데이터 RC3c → RC5/full, learning_rate 5e-5 → {lr:g}, 출력만 바꿈. train_a7.py.\n"
                                                    + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        diff.append(f"- {jid} ← {src.name}: data RC3c/full → RC5/full; " + ", ".join(f"{k} {before[k]} → {after[k]}" for k in KEYS if before[k] != after[k]))
(HERE / "configs_a3/DIFF.md").write_text("\n".join(diff) + "\n", encoding="utf-8")
print("\n".join(diff))
