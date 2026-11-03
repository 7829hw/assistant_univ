# -*- coding: utf-8 -*-
"""ablation_012 학습 config 6개(결정 262 D4): {A3R-d1, A3R-d2} × ablation_011 순서 seed(1102·211102·2026113).
바탕 = ablation_011 ``train/configs/A3-o<seed>.yaml``(그대로 둠; 그 바탕은 pilot_010 S-V4-o43.yaml — R1''·모델 seed 43·LoRA r16/α32·12,288·thinking ON·by_source).
바꾸는 것만: data(``ablation_012/build/<arm>/full``), 레코드 순서 파일(``ablation_012/build/orders/record_order_<arm>_o<seed>.json``), 출력(``/data/hwkim/sftdpo_work/ablation_012/train/<id>``).
A0 O4' 순서 파일(``ablation_011/build/orders/order_b2_o<seed>.json``)과 순서 seed는 A3 config와 같다. 학습 wrapper는 ablation_011 ``train/train_a11.py`` 그대로.

    python3 sft_dpo_inventory/ablation_012/train/make_a12_configs.py   # -> train/configs/<id>.yaml, train/configs/DIFF.md
"""
import copy
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
A11C = ROOT / "sft_dpo_inventory/ablation_011/train/configs"
SEEDS = (1102, 211102, 2026113)
ARMS = ("A3R-d1", "A3R-d2")
OUT_ROOT = "/data/hwkim/sftdpo_work/ablation_012/train"
B = "sft_dpo_inventory/ablation_012/build"


def main():
    out = HERE / "configs"
    out.mkdir(exist_ok=True)
    rows = []
    for arm in ARMS:
        for s in SEEDS:
            base = yaml.safe_load((A11C / f"A3-o{s}.yaml").read_text(encoding="utf-8"))
            cid = f"{arm}-o{s}"
            c = copy.deepcopy(base)
            d = f"{B}/{arm}/full"
            c["data"].update(train=f"{d}/sft_train.jsonl", valid=f"{d}/sft_valid.jsonl", manifest=f"{d}/manifest.json")
            t = c["training"]
            assert t["shared_slot_order_seed"] == s and t["shared_slot_order_file"] == f"sft_dpo_inventory/ablation_011/build/orders/order_b2_o{s}.json"
            t["output_dir"] = f"{OUT_ROOT}/{cid}"
            t["a11_record_order_file"] = f"{B}/orders/record_order_{arm}_o{s}.json"
            c["profiling"]["output"] = f"{OUT_ROOT}/{cid}_profile.json"
            head = (f"# ablation_012 {cid}(결정 262 D4): ablation_011 A3-o{s}.yaml에서 데이터({arm})·레코드 순서 파일·출력만 바꿈. "
                    f"wrapper ablation_011/train/train_a11.py.\n")
            (out / f"{cid}.yaml").write_text(head + yaml.safe_dump(c, allow_unicode=True, sort_keys=False), encoding="utf-8")
            rows.append(cid)
    diff = ["# config 차이(바탕 ablation_011/train/configs/A3-o<seed>.yaml)", "",
            "| 키 | 바탕(A3) | ablation_012 |", "|---|---|---|",
            "| data.train·valid·manifest | ablation_011/build/A3/full | ablation_012/build/<arm>/full |",
            "| training.output_dir·profiling.output | /data/hwkim/sftdpo_work/ablation_011/train/A3-o<seed> | /data/hwkim/sftdpo_work/ablation_012/train/<id> |",
            "| training.a11_record_order_file | ablation_011/build/orders/record_order_A3_o<seed>.json | ablation_012/build/orders/record_order_<arm>_o<seed>.json |",
            "", "순서 seed·A0 O4' 순서 파일(ablation_011/build/orders/order_b2_o<seed>.json)과 그 밖(모델·revision, 1 epoch, lr 2e-4 linear → 0, batch 1·accum 1, warmup 1,"
            " LoRA r16/α32/dropout 0.05·7 모듈, max_seq 12,288, seed 43, bf16, gradient checkpointing, thinking.loss_scope by_source, enable_thinking true)은 바탕과 같다.",
            "", "config: " + ", ".join(rows)]
    (out / "DIFF.md").write_text("\n".join(diff) + "\n", encoding="utf-8")
    print(rows)


if __name__ == "__main__":
    main()
