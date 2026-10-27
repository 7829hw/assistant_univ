# -*- coding: utf-8 -*-
"""pilot_010 선택 단계 config 6개(결정 251 AB5). P9 config(``pilot_009/train/configs_p9/P9-F-o*.yaml``, R1''·O4'·모델 seed 43)에서 데이터(변형 Full)·순서 파일(변형 O4')·출력만 바꾼다.
학습은 ``pilot_007/train/train_b7b.py``(O4' slot 순서, SequentialSampler). ``pilot_009/train/make_p9_configs.py``와 같은 방식.

    python3 make_s10_configs.py   # -> configs_s10/S-{V4,V8}-o{43,1016,7}.yaml, configs_s10/DIFF.md
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "pilot_009/train/configs_p9"
OUT = "/home/hwkim/sftdpo_work/pilot_010/train_s10"
SEEDS = {"o43": 43, "o1016": 20261016, "o7": 7}
(HERE / "configs_s10").mkdir(exist_ok=True)
diff = ["# 선택 단계 config와 P9 config(pilot_009/train/configs_p9)의 차이", ""]
for v in ("V4", "V8"):
    rc = f"sft_dpo_inventory/pilot_010/build/{v}"
    for o, s in SEEDS.items():
        src, jid = SRC / f"P9-F-{o}.yaml", f"S-{v}-{o}"
        cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
        cfg["data"].update(train=f"{rc}/full/sft_train.jsonl", valid=f"{rc}/full/sft_valid.jsonl", manifest=f"{rc}/full/manifest.json")
        assert cfg["data"]["grounding_target"] == "full" and cfg["training"]["shared_slot_order_seed"] == s and cfg["training"]["seed"] == 43
        cfg["training"].update(shared_slot_order_file=f"/home/hwkim/assistant_univ/{rc}/order_b2_o{s}.json", output_dir=f"{OUT}/{jid}")
        cfg["profiling"]["output"] = f"{OUT}/{jid}_profile.json"
        (HERE / f"configs_s10/{jid}.yaml").write_text(f"# pilot_010 {jid}(결정 251): {src.name}에서 데이터 {v} Full·순서 파일 {v} O4' seed {s}·출력만 바꿈. train_b7b.py.\n"
                                                     + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        diff.append(f"- {jid}: data RC7/full → {v}/full, shared_slot_order_file → {v}/order_b2_o{s}.json, output {OUT}/{jid}")
(HERE / "configs_s10/DIFF.md").write_text("\n".join(diff) + "\n", encoding="utf-8")
print("\n".join(diff))
