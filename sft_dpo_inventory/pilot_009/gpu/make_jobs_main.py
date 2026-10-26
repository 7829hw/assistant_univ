# -*- coding: utf-8 -*-
"""pilot_009 본 세션 작업 표·sampling seed·판정 spec(결정 236·237, 지시 2.2). PLAN_009 고정 전에 커밋한다. scheduler11(세 장, Ollama GPU = GPU 2)이 읽는다.
``pilot_008/gpu/make_jobs_main.py``와 같은 방식(그 파일은 고치지 않음).

    python3 make_jobs_main.py   # -> gpu/jobs_main.json, gpu/cell_seeds_main.json, gates/spec_p9.json

| 우선 | 작업 |
| 1 | P9-F-o{43,1016,7,11,2027} 학습(``pilot_007/train/train_b7b.py``, configs_p9) — 세 장이라 첫 바퀴 3, 둘째 바퀴 2 |
| 2 | E9-rdev-base: base(Full prompt) refusal_dev v2 k=12 / E9-rdev-B2F-o*: B2 F 다섯(checkpoint-1811) refusal_dev v2 k=4 / E9-rdev-P8-o*: P8 다섯(checkpoint-2005) refusal_dev v2 k=4(보조) |
| 3 | E9-eval-o*: P9 모델(checkpoint-1993)마다 주 셋(selection_v2·holdout) k=4 + valid98·aux k=4 + refusal_dev v2 k=4, 해당 학습 끝(``file:`` 의존) |

- 셀: ``pilot_006_prep/gpu/run_cell6x.py``(vLLM 0.30.0 BF16, 17,408, 동시 8, PROTOCOL_v4 3절 sampling, 회차 seed S_k = 20261100 + k), 출력 ``pilot_009/cells``,
  원문 ``training/generated/pilot_009/cells_raw``(ignore). B2 F의 주 셋·개발 셋은 pilot_007 B2 셀, P8의 주 셋·개발 셋은 pilot_008 셀을 그대로 쓴다(재측정 없음).
- base의 주 셋·개발 셋은 pilot_008 판정과 같은 기존 셀(재측정 없음). refusal_dev v2는 base·B2 F·P8 모두 새로 잰다(v2 승인본, 결정 234·237).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
P9 = HERE.parent
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"
MAIN = "/home/hwkim/assistant_univ"
SEEDS = {"o43": 43, "o1016": 20261016, "o7": 7, "o11": 11, "o2027": 2027}
OUT9 = "/home/hwkim/sftdpo_work/pilot_009/train_p9"
B2CK = "/home/hwkim/sftdpo_work/pilot_007/train_b2/B2-F-{o}/checkpoint-1811"
P8CK = "/home/hwkim/sftdpo_work/pilot_008/train_p8/P8-F-{o}/checkpoint-2005"
P9CK = OUT9 + "/P9-F-{o}/checkpoint-1993"
RDEV = "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml"
GOLD = {"sel": None, "holdout": "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml", "valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml",
        "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml", "rdevv2": RDEV}
SEED_BASE = 20261100


def run(model, label, gold_key, k):
    g = GOLD[gold_key]
    return (f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu/run_cell6x.py --port {{PORT}} --model {model} --label {label} --k {k} --concurrency 8 "
            f"--grounding-target full --out-dir {MAIN}/sft_dpo_inventory/pilot_009/cells --raw-dir {MAIN}/training/generated/pilot_009/cells_raw --seed-base {SEED_BASE}"
            + (f" --gold {g} --all-items" if g else ""))


def rounds(k):
    return {"seed_base": SEED_BASE, "round_seeds": [SEED_BASE + i for i in range(1, k + 1)]}


jobs, seeds = [], {}
for o in SEEDS:
    jobs.append({"id": f"P9-F-{o}", "type": "raw", "kind": f"train_b7b_P9-F-{o}", "server": "train", "est": 195, "prio": 1,
                 "cmd": [PY, "{WT}/sft_dpo_inventory/pilot_007/train/train_b7b.py", "--config", f"{{WT}}/sft_dpo_inventory/pilot_009/train/configs_p9/P9-F-{o}.yaml"], "outputs": []})
jobs.append({"id": "E9-rdev-base", "type": "raw", "kind": "cells_base_rdevv2_k12", "server": "b17408", "est": 90, "prio": 2,
             "cmd": ["bash", "-c", " && ".join(run("base", "base_rdevv2", "rdevv2", k) for k in range(1, 13))], "outputs": []})
seeds["base_rdevv2"] = rounds(12)
for arm, ck, pre in (("B2F", B2CK, "B2_F"), ("P8", P8CK, "P8_F")):
    for o in SEEDS:
        name, lab = f"{pre}_{o}", f"{arm.lower()}_{o}_rdevv2"
        jobs.append({"id": f"E9-rdev-{arm}-{o}", "type": "raw", "kind": f"cells_{arm}_{o}_rdevv2_k4", "server": f"lora:{name}={ck.format(o=o)}", "est": 25, "prio": 2,
                     "cmd": ["bash", "-c", " && ".join(run(name, lab, "rdevv2", k) for k in range(1, 5))], "outputs": []})
        seeds[lab] = rounds(4)
for o in SEEDS:
    name = f"P9_F_{o}"
    cmds = [run(name, f"p9_f_{o}_{g}", g, k) for g in ("sel", "holdout", "valid98", "aux", "rdevv2") for k in range(1, 5)]
    jobs.append({"id": f"E9-eval-{o}", "type": "raw", "kind": f"cells_P9F_{o}_main_dev_rdevv2_k4", "server": f"lora:{name}={P9CK.format(o=o)}", "est": 90, "prio": 3,
                 "deps": [f"file:{P9CK.format(o=o)}/adapter_model.safetensors|P9-F-{o}"], "cmd": ["bash", "-c", " && ".join(cmds)], "outputs": []})
    for g in ("sel", "holdout", "valid98", "aux", "rdevv2"):
        seeds[f"p9_f_{o}_{g}"] = rounds(4)
(HERE / "jobs_main.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
(HERE / "cell_seeds_main.json").write_text(json.dumps({"decision": "237 (Z5): 실행 전 커밋, PROTOCOL_v4 3절 회차 seed", "cells": seeds}, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8")
ks = lambda p, k=4: [f"{p}_s{i}.json" for i in range(1, k + 1)]  # noqa: E731
C7, P6P, C8, C9 = "sft_dpo_inventory/pilot_007/cells/", "sft_dpo_inventory/pilot_006_prep/cells/", "sft_dpo_inventory/pilot_008/cells/", "sft_dpo_inventory/pilot_009/cells/"
spec = {"label": "pilot_009 단계 판정(결정 237)", "sets": {"selection_v2": "sft_dpo_inventory/conversion_diag/selection_gold.yaml",
                                                       "holdout": GOLD["holdout"], "valid98": GOLD["valid98"], "aux": GOLD["aux"]},
        "rdev_gold": RDEV, "rdev_meta": "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_items_meta.json",
        "seeds": list(SEEDS), "seed_numbers": SEEDS,
        "cells": {"P9": {o: {"selection_v2": ks(f"{C9}p9_f_{o}_sel"), "holdout": ks(f"{C9}p9_f_{o}_holdout"), "valid98": ks(f"{C9}p9_f_{o}_valid98"),
                             "aux": ks(f"{C9}p9_f_{o}_aux"), "rdev": ks(f"{C9}p9_f_{o}_rdevv2")} for o in SEEDS},
                  "B2F": {o: {"selection_v2": ks(f"{C7}b2_f_{o}_sel"), "holdout": ks(f"{C7}b2_f_{o}_holdout"), "valid98": ks(f"{C7}b2_f_{o}_valid98"),
                              "aux": ks(f"{C7}b2_f_{o}_aux"), "rdev": ks(f"{C9}b2f_{o}_rdevv2")} for o in SEEDS},
                  "P8": {o: {"selection_v2": ks(f"{C8}p8_f_{o}_sel"), "holdout": ks(f"{C8}p8_f_{o}_holdout"), "valid98": ks(f"{C8}p8_f_{o}_valid98"),
                             "aux": ks(f"{C8}p8_f_{o}_aux"), "rdev": ks(f"{C9}p8_{o}_rdevv2")} for o in SEEDS},
                  "base": {"selection_v2": ks(P6P + "b1_sel_base") + ks(P6P + "x2_sel_base_17408") + ks(C7 + "b_base3_sel"),
                           "holdout": ks(P6P + "b2_holdout_base") + ks(C7 + "b_base3_holdout"), "valid98": ks(P6P + "b3_valid98_base"), "aux": ks(P6P + "b4_aux_base"),
                           "rdev": ks(C9 + "base_rdevv2", 12)}}}
(P9 / "gates").mkdir(exist_ok=True)
(P9 / "gates/spec_p9.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print([(j["prio"], j["id"]) for j in jobs])
