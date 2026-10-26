# -*- coding: utf-8 -*-
"""pilot_009 config 5개(결정 236 Z4). B2 F config(``pilot_007/train/configs_b2/B2-F-o*.yaml``, R1''·O4'·모델 seed 43)에서 데이터(RC7 Full)·순서 파일(RC7 O4')·출력만 바꾼다.
학습은 ``pilot_007/train/train_b7b.py``(O4' slot 순서, SequentialSampler). ``pilot_008/train/make_p8_configs.py``와 같은 방식.

    python3 make_p9_configs.py   # -> configs_p9/P9-F-o{43,1016,7,11,2027}.yaml, configs_p9/DIFF.md
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "pilot_007/train/configs_b2"
RC = "sft_dpo_inventory/pilot_009/build/RC7"
OUT = "/home/hwkim/sftdpo_work/pilot_009/train_p9"
SEEDS = {"o43": 43, "o1016": 20261016, "o7": 7, "o11": 11, "o2027": 2027}
(HERE / "configs_p9").mkdir(exist_ok=True)
diff = ["# P9 config와 B2 F config(pilot_007/train/configs_b2)의 차이", ""]
for o, s in SEEDS.items():
    src, jid = SRC / f"B2-F-{o}.yaml", f"P9-F-{o}"
    cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
    cfg["data"].update(train=f"{RC}/full/sft_train.jsonl", valid=f"{RC}/full/sft_valid.jsonl", manifest=f"{RC}/full/manifest.json")
    assert cfg["data"]["grounding_target"] == "full" and cfg["training"]["shared_slot_order_seed"] == s
    cfg["training"].update(shared_slot_order_file=f"/home/hwkim/assistant_univ/{RC}/order_b2_o{s}.json", output_dir=f"{OUT}/{jid}")
    cfg["profiling"]["output"] = f"{OUT}/{jid}_profile.json"
    (HERE / f"configs_p9/{jid}.yaml").write_text(f"# pilot_009 {jid}(결정 236): {src.name}에서 데이터 RC7 Full·순서 파일 RC7 O4' seed {s}·출력만 바꿈. train_b7b.py.\n"
                                                + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    diff.append(f"- {jid}: data RC5/full → RC7/full, shared_slot_order_file → RC7/order_b2_o{s}.json, output {OUT}/{jid}")
(HERE / "configs_p9/DIFF.md").write_text("\n".join(diff) + "\n", encoding="utf-8")
print("\n".join(diff))
