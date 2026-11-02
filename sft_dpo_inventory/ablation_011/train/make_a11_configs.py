# -*- coding: utf-8 -*-
"""ablation_011 학습 config 12개(결정 261): {A0,A1,A2,A3} × 순서 seed(1102·211102·2026113).
바탕 = pilot_010 ``train_data/configs_s10/S-V4-o43.yaml``(V4 o43, R1''·모델 seed 43·LoRA r16/α32·12,288·thinking ON·by_source). 바꾸는 것만:
data(A0 = pilot_010 V4 그대로, A1–A3 = build/<arm>/full), 순서(``shared_slot_order_seed``·``shared_slot_order_file`` = A0 O4' 순서, ``a11_record_order_file``),
출력(``/data/hwkim/sftdpo_work/ablation_011/train/<id>``). 경로는 worktree 기준 상대 경로(작업은 고정 worktree에서 돈다).

    python3 sft_dpo_inventory/ablation_011/train/make_a11_configs.py   # -> train/configs/<id>.yaml, train/configs/DIFF.md
"""
import copy
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / "sft_dpo_inventory/pilot_010/train_data/configs_s10/S-V4-o43.yaml"
SEEDS = (1102, 211102, 2026113)
ARMS = ("A0", "A1", "A2", "A3")
OUT_ROOT = "/data/hwkim/sftdpo_work/ablation_011/train"
B = "sft_dpo_inventory/ablation_011/build"


def main():
    base = yaml.safe_load(BASE.read_text(encoding="utf-8"))
    out = HERE / "configs"
    out.mkdir(exist_ok=True)
    rows = []
    for s in SEEDS:
        for arm in ARMS:
            cid = f"{arm}-o{s}"
            c = copy.deepcopy(base)
            d = "sft_dpo_inventory/pilot_010/build/V4/full" if arm == "A0" else f"{B}/{arm}/full"
            c["data"].update(train=f"{d}/sft_train.jsonl", valid=f"{d}/sft_valid.jsonl", manifest=f"{d}/manifest.json")
            t = c["training"]
            t["output_dir"] = f"{OUT_ROOT}/{cid}"
            t["shared_slot_order_seed"] = s
            t["shared_slot_order_file"] = f"{B}/orders/order_b2_o{s}.json"
            t["a11_record_order_file"] = f"{B}/orders/record_order_{arm}_o{s}.json"
            c["profiling"]["output"] = f"{OUT_ROOT}/{cid}_profile.json"
            head = (f"# ablation_011 {cid}(결정 261): pilot_010 S-V4-o43.yaml에서 데이터({arm})·순서(A0 O4' seed {s} + arm 레코드 순서)·출력만 바꿈. "
                    f"wrapper ablation_011/train/train_a11.py.\n")
            (out / f"{cid}.yaml").write_text(head + yaml.safe_dump(c, allow_unicode=True, sort_keys=False), encoding="utf-8")
            rows.append(cid)
    diff = ["# config 차이(바탕 pilot_010/train_data/configs_s10/S-V4-o43.yaml)", "",
            "| 키 | 바탕 | ablation_011 |", "|---|---|---|",
            "| data.train·valid·manifest | pilot_010/build/V4/full | A0: 같음 / A1–A3: ablation_011/build/<arm>/full |",
            "| training.output_dir·profiling.output | /data/hwkim/sftdpo_work/pilot_010/train_s10/S-V4-o43 | /data/hwkim/sftdpo_work/ablation_011/train/<id> |",
            "| training.shared_slot_order_seed | 43 | 1102 · 211102 · 2026113 |",
            "| training.shared_slot_order_file | pilot_010/build/V4/order_b2_o43.json(절대 경로) | ablation_011/build/orders/order_b2_o<seed>.json(worktree 상대) |",
            "| training.a11_record_order_file | – | ablation_011/build/orders/record_order_<arm>_o<seed>.json |",
            "", "그 밖(모델·revision, 1 epoch, lr 2e-4 linear → 0, batch 1·accum 1, warmup 1, LoRA r16/α32/dropout 0.05·7 모듈, max_seq 12,288, seed 43, data_seed 43(쓰이지 않음),"
            " bf16, gradient checkpointing, thinking.loss_scope by_source, enable_thinking true)은 바탕과 같다.", "", "config: " + ", ".join(rows)]
    (out / "DIFF.md").write_text("\n".join(diff) + "\n", encoding="utf-8")
    print(rows)


if __name__ == "__main__":
    main()
