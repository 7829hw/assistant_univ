# -*- coding: utf-8 -*-
"""진단 학습 config 넷(결정 161, 세션 4 지시 2.2). 고정된 pilot_006 config(``run3/configs/pilot006_<F43|P43>.yaml``)에서 seed·data_seed·출력·저장만 바꾼다.

    python3 make_diag_configs.py   # -> configs/diag_<ID>.yaml, configs/DIFF.md
"""
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
RUN3 = HERE.parents[1] / "run3/configs"
OUT = "/home/hwkim/sftdpo_work/pilot_006/diag"
DIAG = [("D-F7", "F43", 7, 7), ("D-P7", "P43", 7, 7), ("D-F43o1016", "F43", 43, 20261016), ("D-F1016o43", "F43", 20261016, 43)]

(HERE / "configs").mkdir(exist_ok=True)
diff = ["# 진단 config와 고정 config의 차이(seed·data_seed·output_dir·profiling.output·save_strategy만)", ""]
for did, base, seed, dseed in DIAG:
    src = RUN3 / f"pilot006_{base}.yaml"
    cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
    before = {k: cfg["training"].get(k) for k in ("seed", "data_seed", "output_dir", "save_strategy", "save_steps")}
    cfg["training"].update(seed=seed, data_seed=dseed, output_dir=f"{OUT}/{did}", save_strategy="no")
    cfg["training"].pop("save_steps", None)
    cfg["profiling"]["output"] = f"{OUT}/{did}_profile.json"
    after = {k: cfg["training"].get(k) for k in ("seed", "data_seed", "output_dir", "save_strategy", "save_steps")}
    (HERE / f"configs/diag_{did}.yaml").write_text(f"# 진단 학습 {did}(결정 161): {src.name}에서 seed {seed}, data_seed {dseed}, 출력, 저장(wrapper가 epoch 1의 25·50·75·100%)만 바꿈.\n"
                                                + yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    diff.append(f"- {did} ← {src.name}: {before} → {after}")
(HERE / "configs/DIFF.md").write_text("\n".join(diff) + "\n", encoding="utf-8")
print("\n".join(diff))
