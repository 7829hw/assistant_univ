# -*- coding: utf-8 -*-
"""A단계 학습 config 여섯(결정 167 O3). pilot_006 F43 config(``pilot_006/run3/configs/pilot006_F43.yaml``)에서 아래만 바꾼다.

    python3 make_a_configs.py   # -> configs/A-R{1,2}-o{43,1016,7}.yaml, configs/DIFF.md

- 공통: 데이터 RC3c/full, num_train_epochs 1, 모델 seed 43, data_seed = 순서 seed, save_strategy no(wrapper ``train_a7.py``가 25·50·75·100% 저장), 출력.
- R1: batch 1·accum 1, lr 5e-5, warmup 1 step(pilot_006과 같음).
- R2: batch 1·accum 16, lr 2e-4, warmup_ratio 0.03(warmup_steps 0 — Trainer는 warmup_steps > 0이면 ratio를 무시함).
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "pilot_006/run3/configs/pilot006_F43.yaml"
RC = "sft_dpo_inventory/pilot_007/build/RC3c/full"
OUT = "/data/hwkim/sftdpo_work/pilot_007/train"
ORDERS = {"o43": 43, "o1016": 20261016, "o7": 7}
RECIPES = {"R1": {"gradient_accumulation_steps": 1, "learning_rate": 5.0e-05, "warmup_steps": 1, "warmup_ratio": 0},
           "R2": {"gradient_accumulation_steps": 16, "learning_rate": 2.0e-04, "warmup_steps": 0, "warmup_ratio": 0.03}}
KEYS = ("num_train_epochs", "per_device_train_batch_size", "gradient_accumulation_steps", "learning_rate", "warmup_steps", "warmup_ratio",
        "seed", "data_seed", "save_strategy", "save_steps", "output_dir")

diff = [f"# A단계 config와 {SRC.name}의 차이", ""]
for r, rv in RECIPES.items():
    for o, oseed in ORDERS.items():
        jid = f"A-{r}-{o}"
        cfg = yaml.safe_load(SRC.read_text(encoding="utf-8"))
        before = {k: cfg["training"].get(k) for k in KEYS}
        cfg["data"].update(train=f"{RC}/sft_train.jsonl", valid=f"{RC}/sft_valid.jsonl", manifest=f"{RC}/manifest.json")
        cfg["training"].update(num_train_epochs=1, seed=43, data_seed=oseed, save_strategy="no", output_dir=f"{OUT}/{jid}", **rv)
        cfg["training"].pop("save_steps", None)
        cfg["profiling"]["output"] = f"{OUT}/{jid}_profile.json"
        after = {k: cfg["training"].get(k) for k in KEYS}
        (HERE / f"configs/{jid}.yaml").write_text(
            f"# pilot_007 A단계 {jid}(결정 167): {SRC.name}에서 데이터 RC3c/full, 1 epoch, recipe {r}, 모델 seed 43, data_seed {oseed}, 출력·저장만 바꿈.\n"
            + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        diff.append(f"- {jid}: data RC3/full → RC3c/full; " + ", ".join(f"{k} {before[k]} → {after[k]}" for k in KEYS if before[k] != after[k]))
(HERE / "configs/DIFF.md").write_text("\n".join(diff) + "\n", encoding="utf-8")
print("\n".join(diff))
