# -*- coding: utf-8 -*-
"""A2단계 config 여섯(결정 177·178). 기존 config에서 아래만 바꾼다.

    python3 make_a2_configs.py   # -> configs_a2/{C-s43,C-s1016,C-s7,R1p-o43,R1p-o1016,R1p-o7}.yaml, configs_a2/DIFF.md

- (a) C-s<seed>: ``pilot_006/run3/configs/pilot006_F43.yaml``(pilot_006 F recipe: batch 1·accum 1, lr 5e-5, warmup 1, 2 epoch 선형 감쇠)에서 데이터 RC3c/full,
  seed(모델 = 데이터 순서, data_seed 없음 — pilot_006 F와 같은 방식), 출력·저장만. 학습은 ``pilot_006/post/diag/train_diag.py``(2 epoch 일정 그대로 epoch 1 끝 step N에서 멈춤, 25·50·75·100% 저장).
- (b) R1p-o<seed>: A단계 ``configs/A-R1-o<seed>.yaml``(1 epoch, 끝 lr 0, batch 1·accum 1, warmup 1, 모델 seed 43, data_seed = 순서 seed)에서 learning_rate 5e-5 → 1e-4, 출력만.
  학습은 ``train_a7.py``.
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
F43 = HERE.parents[1] / "pilot_006/run3/configs/pilot006_F43.yaml"
RC = "sft_dpo_inventory/pilot_007/build/RC3c/full"
OUT = "/home/hwkim/sftdpo_work/pilot_007/train_a2"
KEYS = ("num_train_epochs", "gradient_accumulation_steps", "learning_rate", "warmup_steps", "warmup_ratio", "seed", "data_seed", "save_strategy", "save_steps", "output_dir")
diff = ["# A2 config와 원본의 차이", ""]
for tag, seed in (("s43", 43), ("s1016", 20261016), ("s7", 7)):
    jid = f"C-{tag}"
    cfg = yaml.safe_load(F43.read_text(encoding="utf-8"))
    before = {k: cfg["training"].get(k) for k in KEYS}
    cfg["data"].update(train=f"{RC}/sft_train.jsonl", valid=f"{RC}/sft_valid.jsonl", manifest=f"{RC}/manifest.json")
    cfg["training"].update(seed=seed, save_strategy="no", output_dir=f"{OUT}/{jid}")
    cfg["training"].pop("save_steps", None)
    cfg["profiling"]["output"] = f"{OUT}/{jid}_profile.json"
    after = {k: cfg["training"].get(k) for k in KEYS}
    (HERE / f"configs_a2/{jid}.yaml").write_text(f"# pilot_007 A2 (a) {jid}(결정 177): {F43.name}에서 데이터 RC3c/full, seed {seed}(데이터 순서도 같은 seed), 출력·저장만 바꿈. train_diag.py로 epoch 1에서 멈춤.\n"
                                                + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    diff.append(f"- {jid} ← {F43.name}: data RC3/full → RC3c/full; " + ", ".join(f"{k} {before[k]} → {after[k]}" for k in KEYS if before[k] != after[k]))
for o in ("o43", "o1016", "o7"):
    jid = f"R1p-{o}"
    src = HERE / f"configs/A-R1-{o}.yaml"
    cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
    before = {k: cfg["training"].get(k) for k in KEYS}
    cfg["training"].update(learning_rate=1.0e-04, output_dir=f"{OUT}/{jid}")
    cfg["profiling"]["output"] = f"{OUT}/{jid}_profile.json"
    after = {k: cfg["training"].get(k) for k in KEYS}
    (HERE / f"configs_a2/{jid}.yaml").write_text(f"# pilot_007 A2 (b) {jid}(결정 178): {src.name}에서 learning_rate 5e-5 → 1e-4, 출력만 바꿈. train_a7.py.\n"
                                                + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    diff.append(f"- {jid} ← {src.name}: " + ", ".join(f"{k} {before[k]} → {after[k]}" for k in KEYS if before[k] != after[k]))
(HERE / "configs_a2/DIFF.md").write_text("\n".join(diff) + "\n", encoding="utf-8")
print("\n".join(diff))
