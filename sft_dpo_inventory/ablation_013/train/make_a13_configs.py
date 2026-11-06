# -*- coding: utf-8 -*-
"""ablation_013 학습 config 5개(결정 263): A3T × ablation_011 순서 seed(1102·211102·2026113), A0(V4) × 새 순서 seed(2026117·2026131).
- A3T 바탕 = ablation_011 ``train/configs/A3-o<seed>.yaml``(그대로 둠). 바꾸는 것: data(``ablation_013/build/A3T/full``), 레코드 순서 파일
  (``ablation_013/build/orders/record_order_A3T_o<seed>.json``), 출력(``/data/hwkim/sftdpo_work/ablation_013/train/<id>``).
- A0 새 seed 바탕 = ablation_011 ``train/configs/A0-o1102.yaml``(그대로 둠). 바꾸는 것: ``shared_slot_order_seed``·``shared_slot_order_file``
  (``ablation_013/build/orders/order_b2_o<seed>.json``)·레코드 순서 파일(``ablation_013/build/orders/record_order_A0_o<seed>.json``)·출력. data는 V4 그대로.
학습 wrapper는 ablation_011 ``train/train_a11.py`` 그대로. 그 밖(R1''·모델 seed 43·LoRA·12,288·thinking ON·by_source)은 바탕과 같다.

    python3 sft_dpo_inventory/ablation_013/train/make_a13_configs.py   # -> train/configs/<id>.yaml, train/configs/DIFF.md
"""
import copy
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
A11C = ROOT / "sft_dpo_inventory/ablation_011/train/configs"
OLD = (1102, 211102, 2026113)
NEW = (2026117, 2026131)
OUT_ROOT = "/data/hwkim/sftdpo_work/ablation_013/train"
B = "sft_dpo_inventory/ablation_013/build"


def dump(out, cid, c, head):
    (out / f"{cid}.yaml").write_text(head + yaml.safe_dump(c, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main():
    out = HERE / "configs"
    out.mkdir(exist_ok=True)
    rows = []
    for s in OLD:
        c = yaml.safe_load((A11C / f"A3-o{s}.yaml").read_text(encoding="utf-8"))
        cid = f"A3T-o{s}"
        c["data"].update(train=f"{B}/A3T/full/sft_train.jsonl", valid=f"{B}/A3T/full/sft_valid.jsonl", manifest=f"{B}/A3T/full/manifest.json")
        t = c["training"]
        assert t["shared_slot_order_seed"] == s and t["shared_slot_order_file"] == f"sft_dpo_inventory/ablation_011/build/orders/order_b2_o{s}.json"
        t["output_dir"] = f"{OUT_ROOT}/{cid}"
        t["a11_record_order_file"] = f"{B}/orders/record_order_A3T_o{s}.json"
        c["profiling"]["output"] = f"{OUT_ROOT}/{cid}_profile.json"
        dump(out, cid, c, f"# ablation_013 {cid}(결정 263 D4): ablation_011 A3-o{s}.yaml에서 데이터(A3T)·레코드 순서 파일·출력만 바꿈. wrapper ablation_011/train/train_a11.py.\n")
        rows.append(cid)
    base = yaml.safe_load((A11C / "A0-o1102.yaml").read_text(encoding="utf-8"))
    assert base["data"]["train"] == "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl"
    for s in NEW:
        c = copy.deepcopy(base)
        cid = f"A0-o{s}"
        t = c["training"]
        t["shared_slot_order_seed"] = s
        t["shared_slot_order_file"] = f"{B}/orders/order_b2_o{s}.json"
        t["a11_record_order_file"] = f"{B}/orders/record_order_A0_o{s}.json"
        t["output_dir"] = f"{OUT_ROOT}/{cid}"
        c["profiling"]["output"] = f"{OUT_ROOT}/{cid}_profile.json"
        dump(out, cid, c, f"# ablation_013 {cid}(결정 263 A0 짝 seed): ablation_011 A0-o1102.yaml에서 순서 seed·O4' 순서 파일·레코드 순서 파일·출력만 바꿈(data = V4 그대로). wrapper ablation_011/train/train_a11.py.\n")
        rows.append(cid)
    diff = ["# config 차이(ablation_013)", "",
            "| config | 바탕 | 바꾼 키 |", "|---|---|---|",
            "| A3T-o<seed>(1102·211102·2026113) | ablation_011/train/configs/A3-o<seed>.yaml | data.train·valid·manifest → ablation_013/build/A3T/full; training.a11_record_order_file → ablation_013/build/orders/record_order_A3T_o<seed>.json; output_dir·profiling.output → /data/hwkim/sftdpo_work/ablation_013/train/<id> |",
            "| A0-o<seed>(2026117·2026131) | ablation_011/train/configs/A0-o1102.yaml | training.shared_slot_order_seed → <seed>; shared_slot_order_file → ablation_013/build/orders/order_b2_o<seed>.json; a11_record_order_file → ablation_013/build/orders/record_order_A0_o<seed>.json; output_dir·profiling.output → /data/hwkim/sftdpo_work/ablation_013/train/<id> |",
            "", "그 밖(모델·revision, 1 epoch, lr 2e-4 linear → 0, batch 1·accum 1, warmup 1, LoRA r16/α32/dropout 0.05·7 모듈, max_seq 12,288, seed 43, bf16, gradient checkpointing,"
            " thinking.loss_scope by_source, enable_thinking true)은 바탕과 같다.", "", "config: " + ", ".join(rows)]
    (out / "DIFF.md").write_text("\n".join(diff) + "\n", encoding="utf-8")
    print(rows)


if __name__ == "__main__":
    main()
