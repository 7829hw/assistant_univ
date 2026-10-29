# -*- coding: utf-8 -*-
"""B단계 config 열(결정 194·195). A3 ``configs_a3/R1pp-o43.yaml``(R1'': 1 epoch, lr 2e-4 → 0, batch 1·accum 1, warmup 1, 모델 seed 43, RC5/full)에서
arm 데이터·grounding_target·순서 공유 키·출력만 바꾼다. 학습은 ``train_b7.py``(순서 파일대로 레코드를 놓고 순차 sampler, 25·50·75·100% 저장).

    python3 make_b_configs.py   # -> configs_b/B-{F,P}-o{43,1016,7,11,2027}.yaml, configs_b/DIFF.md

- 순서 seed: 43·20261016(ID o1016, A3 순서 파일 그대로)·7·11·2027. ``training.shared_order_seed`` = 순서 seed, ``shared_order_file`` = ``build/RC5/order_o<seed>.json``.
  ``data_seed``도 같은 값으로 두지만 순차 sampler라 쓰이지 않는다.
- P: 데이터 RC5/partial, ``grounding_target: partial``(pilot_006 F·P config 차이와 같음).
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SRC = HERE / "configs_a3/R1pp-o43.yaml"
RC = "sft_dpo_inventory/pilot_007/build/RC5"
OUT = "/data/hwkim/sftdpo_work/pilot_007/train_b"
SEEDS = {"o43": 43, "o1016": 20261016, "o7": 7, "o11": 11, "o2027": 2027}
diff = [f"# B config와 {SRC.name}의 차이", ""]
for arm, tag in (("full", "F"), ("partial", "P")):
    for o, s in SEEDS.items():
        jid = f"B-{tag}-{o}"
        cfg = yaml.safe_load(SRC.read_text(encoding="utf-8"))
        cfg["data"].update(train=f"{RC}/{arm}/sft_train.jsonl", valid=f"{RC}/{arm}/sft_valid.jsonl", manifest=f"{RC}/{arm}/manifest.json", grounding_target=arm)
        cfg["training"].update(data_seed=s, shared_order_seed=s, shared_order_file=f"/home/hwkim/assistant_univ/{RC}/order_o{s}.json", output_dir=f"{OUT}/{jid}")
        cfg["profiling"]["output"] = f"{OUT}/{jid}_profile.json"
        (HERE / f"configs_b/{jid}.yaml").write_text(f"# pilot_007 B {jid}(결정 194·195): {SRC.name}에서 데이터 RC5/{arm}, grounding_target {arm}, 순서 공유 seed {s}, 출력만 바꿈. train_b7.py.\n"
                                                   + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        diff.append(f"- {jid}: data RC5/{arm}, grounding_target {arm}, data_seed 43 → {s}, shared_order_seed {s}, shared_order_file order_o{s}.json, output {OUT}/{jid}")
(HERE / "configs_b/DIFF.md").write_text("\n".join(diff) + "\n", encoding="utf-8")
print("\n".join(diff))
