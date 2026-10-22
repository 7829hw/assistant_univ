# -*- coding: utf-8 -*-
"""pilot_008 본 세션 작업 표·sampling seed·판정 spec(결정 224·225, 지시 2.2). PLAN_008 고정 전에 커밋한다. scheduler10(세 장, Ollama GPU = GPU 2)이 읽는다.

    python3 make_jobs_main.py   # -> gpu/jobs_main.json, gpu/cell_seeds_main.json, gates/spec_p8.json

| 우선 | 작업 |
| 1 | P8-F-o{43,1016,7,11,2027} 학습(``pilot_007/train/train_b7b.py``, configs_p8) — 세 장이라 첫 바퀴 3, 둘째 바퀴 2 |
| 2 | E8-rdev-base: base(Full prompt) refusal_dev v1 k=12 / E8-rdev-B2F-o*: B2 F 다섯(checkpoint-1811) refusal_dev v1 k=4 — 둘째 바퀴의 빈 장에서 |
| 3 | E8-eval-o*: P8 모델(checkpoint-2005)마다 주 셋(selection_v2·holdout) k=4 + valid98·aux k=4 + refusal_dev v1 k=4, 해당 학습 끝(``file:`` 의존) |

- 셀: ``pilot_006_prep/gpu/run_cell6x.py``(vLLM 0.30.0 BF16, 17,408, 동시 8, PROTOCOL_v4 3절 sampling, 회차 seed S_k = 20261100 + k), 출력 ``pilot_008/cells``,
  원문 ``training/generated/pilot_008/cells_raw``(ignore). B2 F의 주 셋·개발 셋은 pilot_007 B2 셀을 그대로 쓴다(재측정 없음).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P8 = HERE.parent
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"
MAIN = "/home/hwkim/assistant_univ"
SEEDS = {"o43": 43, "o1016": 20261016, "o7": 7, "o11": 11, "o2027": 2027}
OUT8 = "/home/hwkim/sftdpo_work/pilot_008/train_p8"
B2CK = "/home/hwkim/sftdpo_work/pilot_007/train_b2/B2-F-{o}/checkpoint-1811"
P8CK = OUT8 + "/P8-F-{o}/checkpoint-2005"
RDEV = "sft_dpo_inventory/pilot_008/refusal_dev/approved/rdev_v1_gold.yaml"
GOLD = {"sel": None, "holdout": "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml", "valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml",
        "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml", "rdev1": RDEV}
SEED_BASE = 20261100


def run(model, label, gold_key, k):
    g = GOLD[gold_key]
    return (f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu/run_cell6x.py --port {{PORT}} --model {model} --label {label} --k {k} --concurrency 8 "
            f"--grounding-target full --out-dir {MAIN}/sft_dpo_inventory/pilot_008/cells --raw-dir {MAIN}/training/generated/pilot_008/cells_raw --seed-base {SEED_BASE}"
            + (f" --gold {g} --all-items" if g else ""))


jobs, seeds = [], {}
for o in SEEDS:
    jobs.append({"id": f"P8-F-{o}", "type": "raw", "kind": f"train_b7b_P8-F-{o}", "server": "train", "est": 195, "prio": 1,
                 "cmd": [PY, "{WT}/sft_dpo_inventory/pilot_007/train/train_b7b.py", "--config", f"{{WT}}/sft_dpo_inventory/pilot_008/train/configs_p8/P8-F-{o}.yaml"], "outputs": []})
jobs.append({"id": "E8-rdev-base", "type": "raw", "kind": "cells_base_rdev1_k12", "server": "b17408", "est": 30, "prio": 2,
             "cmd": ["bash", "-c", " && ".join(run("base", "base_rdev1", "rdev1", k) for k in range(1, 13))], "outputs": []})
seeds["base_rdev1"] = {"seed_base": SEED_BASE, "round_seeds": [SEED_BASE + k for k in range(1, 13)]}
for o in SEEDS:
    name = f"B2_F_{o}"
    jobs.append({"id": f"E8-rdev-B2F-{o}", "type": "raw", "kind": f"cells_B2F_{o}_rdev1_k4", "server": f"lora:{name}={B2CK.format(o=o)}", "est": 12, "prio": 2,
                 "cmd": ["bash", "-c", " && ".join(run(name, f"b2f_{o}_rdev1", "rdev1", k) for k in range(1, 5))], "outputs": []})
    seeds[f"b2f_{o}_rdev1"] = {"seed_base": SEED_BASE, "round_seeds": [SEED_BASE + k for k in range(1, 5)]}
for o in SEEDS:
    name = f"P8_F_{o}"
    cmds = [run(name, f"p8_f_{o}_{g}", g, k) for g in ("sel", "holdout", "valid98", "aux", "rdev1") for k in range(1, 5)]
    jobs.append({"id": f"E8-eval-{o}", "type": "raw", "kind": f"cells_P8F_{o}_main_dev_rdev1_k4", "server": f"lora:{name}={P8CK.format(o=o)}", "est": 70, "prio": 3,
                 "deps": [f"file:{P8CK.format(o=o)}/adapter_model.safetensors|P8-F-{o}"], "cmd": ["bash", "-c", " && ".join(cmds)], "outputs": []})
    for g in ("sel", "holdout", "valid98", "aux", "rdev1"):
        seeds[f"p8_f_{o}_{g}"] = {"seed_base": SEED_BASE, "round_seeds": [SEED_BASE + k for k in range(1, 5)]}
(HERE / "jobs_main.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(HERE / "cell_seeds_main.json").write_text(json.dumps({"decision": "225 (X5): 실행 전 커밋, PROTOCOL_v4 3절 회차 seed", "cells": seeds}, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8")
ks = lambda p, k=4: [f"{p}_s{i}.json" for i in range(1, k + 1)]  # noqa: E731
C7, P6P, C8 = "sft_dpo_inventory/pilot_007/cells/", "sft_dpo_inventory/pilot_006_prep/cells/", "sft_dpo_inventory/pilot_008/cells/"
spec = {"label": "pilot_008 단계 판정(결정 225)", "sets": {"selection_v2": "sft_dpo_inventory/conversion_diag/selection_gold.yaml",
                                                       "holdout": GOLD["holdout"], "valid98": GOLD["valid98"], "aux": GOLD["aux"]},
        "rdev_gold": RDEV, "rdev_meta": "sft_dpo_inventory/pilot_008/refusal_dev/approved/rdev_v1_items_meta.json",
        "seeds": list(SEEDS), "seed_numbers": SEEDS,
        "cells": {"P8": {o: {"selection_v2": ks(f"{C8}p8_f_{o}_sel"), "holdout": ks(f"{C8}p8_f_{o}_holdout"), "valid98": ks(f"{C8}p8_f_{o}_valid98"),
                             "aux": ks(f"{C8}p8_f_{o}_aux"), "rdev": ks(f"{C8}p8_f_{o}_rdev1")} for o in SEEDS},
                  "B2F": {o: {"selection_v2": ks(f"{C7}b2_f_{o}_sel"), "holdout": ks(f"{C7}b2_f_{o}_holdout"), "valid98": ks(f"{C7}b2_f_{o}_valid98"),
                              "aux": ks(f"{C7}b2_f_{o}_aux"), "rdev": ks(f"{C8}b2f_{o}_rdev1")} for o in SEEDS},
                  "base": {"selection_v2": ks(P6P + "b1_sel_base") + ks(P6P + "x2_sel_base_17408") + ks(C7 + "b_base3_sel"),
                           "holdout": ks(P6P + "b2_holdout_base") + ks(C7 + "b_base3_holdout"), "valid98": ks(P6P + "b3_valid98_base"), "aux": ks(P6P + "b4_aux_base"),
                           "rdev": ks(C8 + "base_rdev1", 12)}}}
(P8 / "gates/spec_p8.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print([(j["prio"], j["id"]) for j in jobs])
