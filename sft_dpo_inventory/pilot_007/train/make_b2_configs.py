# -*- coding: utf-8 -*-
"""B2단계 config 열(결정 206·207). B단계 ``configs_b/B-{F,P}-o*.yaml``(R1'', RC5, 모델 seed 43)에서 순서 키·출력만 바꾼다. 학습은 ``train_b7b.py``.

    python3 make_b2_configs.py   # -> configs_b2/B2-{F,P}-o{43,1016,7,11,2027}.yaml, configs_b2/DIFF.md

- ``training.shared_order_seed``·``shared_order_file``(O4) 대신 ``shared_slot_order_seed`` = 순서 seed, ``shared_slot_order_file`` = ``build/RC5/order_b2_o<seed>.json``(O4').
- 출력 ``/home/hwkim/sftdpo_work/pilot_007/train_b2/<ID>``. 나머지(데이터·grounding_target·recipe·data_seed)는 B config 그대로.
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
RC = "sft_dpo_inventory/pilot_007/build/RC5"
OUT = "/home/hwkim/sftdpo_work/pilot_007/train_b2"
SEEDS = {"o43": 43, "o1016": 20261016, "o7": 7, "o11": 11, "o2027": 2027}
(HERE / "configs_b2").mkdir(exist_ok=True)
diff = ["# B2 config와 B config(configs_b)의 차이", ""]
for tag in ("F", "P"):
    for o, s in SEEDS.items():
        src, jid = HERE / f"configs_b/B-{tag}-{o}.yaml", f"B2-{tag}-{o}"
        cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
        t = cfg["training"]
        assert t.pop("shared_order_seed") == s
        t.pop("shared_order_file")
        t.update(shared_slot_order_seed=s, shared_slot_order_file=f"/home/hwkim/assistant_univ/{RC}/order_b2_o{s}.json", output_dir=f"{OUT}/{jid}")
        cfg["profiling"]["output"] = f"{OUT}/{jid}_profile.json"
        (HERE / f"configs_b2/{jid}.yaml").write_text(f"# pilot_007 B2 {jid}(결정 206·207): {src.name}에서 순서 키(O4 → O4' slot 순열 seed {s})·출력만 바꿈. train_b7b.py.\n"
                                                    + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        diff.append(f"- {jid}: shared_order_seed/file(O4, order_o{s}.json) → shared_slot_order_seed {s}, shared_slot_order_file order_b2_o{s}.json; output {OUT}/{jid}")
(HERE / "configs_b2/DIFF.md").write_text("\n".join(diff) + "\n", encoding="utf-8")
print("\n".join(diff))
