# -*- coding: utf-8 -*-
"""Repro job table -> gpu/jobs_repro.json. 10 new trainings (3 order seeds x 2 arms, to 3 runs each) and their H-dev evaluations.
Training order interleaves arms/seeds/runs so no arm, seed or run index sits on one GPU only (the scheduler hands the next job to whichever GPU frees first).
Evals (H-dev 2,000, k=1, same command as ablation_012/topic2_semantic_order) wait for gpu/ready/REPRO_TOOLS.json (analysis frozen + committed before any new result is read)."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
MAIN = "/home/hwkim/assistant_univ"
OUT = f"{MAIN}/topic2_semantic_order_repro/cells"
RAW = f"{MAIN}/training/generated/topic2_semantic_order_repro/cells_raw"
WORK = "/data/hwkim/sftdpo_work/topic2_semantic_order_repro/train"
HDEV = "sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
STEPS, SEC = 1984, 5.9
TOOLS = "ready:REPRO_TOOLS"
ORDER = [("A", 1102, 2), ("B", 211102, 2), ("A", 2026131, 3), ("B", 1102, 2), ("A", 211102, 2), ("B", 2026131, 3),
         ("A", 1102, 3), ("B", 211102, 3), ("A", 211102, 3), ("B", 1102, 3)]


def cid(arm, s, r):
    return f"{'A0' if arm == 'A' else 'B'}-o{s}-r{r}"


def main():
    jobs = []
    for i, (arm, s, r) in enumerate(ORDER):
        c = cid(arm, s, r)
        script = "{WT}/topic2_semantic_order/train_semantic.py" if arm == "B" else "{WT}/sft_dpo_inventory/ablation_011/train/train_a11.py"
        jobs.append({"id": f"T-{c}", "type": "raw", "kind": f"train_repro_{c}", "server": "train", "est": round(STEPS * SEC / 60), "prio": 1 + i, "deps": [],
                     "cmd": [PY, script, "--config", f"{{WT}}/topic2_semantic_order_repro/configs/{c}.yaml"]})
    for i, (arm, s, r) in enumerate(ORDER):
        c = cid(arm, s, r)
        ck = f"{WORK}/{c}/checkpoint-{STEPS}"
        name = c.replace("-", "_")
        lab = f"hdev_repro_{'a0' if arm == 'A' else 'b'}_o{s}_r{r}"
        cmd = (f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py --port {{PORT}} --model {name} --label {lab} --k 1 --concurrency 32 "
               f"--grounding-target full --out-dir {OUT} --raw-dir {RAW} --seed-base 20261100 --gold {HDEV} --all-items")
        jobs.append({"id": f"H-{c}", "type": "raw", "kind": f"hdev_repro_{c}", "server": f"lora:{name}={ck}", "est": 35, "prio": 20 + i,
                     "deps": [f"file:{ck}/adapter_model.safetensors|T-{c}", TOOLS], "cells": [{"name": f"{lab}_s1", "label": lab, "k": 1, "cmd": cmd}]})
    (HERE / "jobs_repro.json").write_text(json.dumps({"label": "topic2_semantic_order_repro", "jobs": jobs}, ensure_ascii=False, indent=1) + "\n")
    print(len(jobs), "jobs", [(j["id"], j["prio"]) for j in jobs[:10]])


if __name__ == "__main__":
    main()
