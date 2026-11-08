# -*- coding: utf-8 -*-
"""Topic 2 job table (decision 264) -> gpu/jobs_t2.json. scheduler16 picks by (prio, id), smallest first.

Priority: (1) B trainings T-B-* (prio 1-5)  (2) evals of finished B models: H-dev (10-14), E1 (20-24), CT10K (30-34)
(3) CT10K for the two A0 seeds that have none (o2026117, o2026131; prio 40-41)  (4) repeat pair on o2026131: trainings (50, 51), then H-dev (60, 61).
Eval jobs wait for gpu/ready/T2_TOOLS.json (analysis tool frozen and committed BEFORE any B result is read).
Eval commands = ablation_012/013 commands (same run_cell6x.py, sampler, k, seeds, concurrency); only output locations differ.
Server: lora:<name>=<checkpoint> rank 16. B epoch-end checkpoint = checkpoint-1984.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
MAIN = "/home/hwkim/assistant_univ"
OUT = f"{MAIN}/topic2_semantic_order/cells"
RAW = f"{MAIN}/training/generated/topic2_semantic_order/cells_raw"
WORK = "/data/hwkim/sftdpo_work/topic2_semantic_order/train"
T11 = "/data/hwkim/sftdpo_work/ablation_011/train"
T13 = "/data/hwkim/sftdpo_work/ablation_013/train"
SEEDS = (1102, 211102, 2026113, 2026117, 2026131)
E1_SETS = (("rdevv2", "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml"),
           ("valid98", "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml"),
           ("aux", "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml"))
CT = "sft_dpo_inventory/client_test_10000/qa_test_10000.yaml"
CH = "{WT}/sft_dpo_inventory/client_test_10000/gpu/chunks"
HDEV = "sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
STEPS = 1984
SEC_PER_STEP = 5.9
TOOLS = "ready:T2_TOOLS"


def run(model, label, k, conc, gold, extra):
    return (f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py --port {{PORT}} --model {model} --label {label} --k {k} "
            f"--concurrency {conc} --grounding-target full --out-dir {OUT} --raw-dir {RAW} --seed-base 20261100 --gold {gold} {extra}").strip()


def e1_cells(model, prefix):
    return [{"name": f"{prefix}_{st}_s{k}", "label": f"{prefix}_{st}", "k": k, "cmd": run(model, f"{prefix}_{st}", k, 8, gold, "--all-items")}
            for st, gold in E1_SETS for k in range(1, 5)]


def ct_cells(model, prefix):
    return [{"name": f"{prefix}_c{c}_s1", "label": f"{prefix}_c{c}", "k": 1, "cmd": run(model, f"{prefix}_c{c}", 1, 32, CT, f'--only "$(cat {CH}/c{c}.txt)"')}
            for c in range(1, 6)]


def hdev_cells(model, prefix):
    return [{"name": f"{prefix}_s1", "label": prefix, "k": 1, "cmd": run(model, prefix, 1, 32, HDEV, "--all-items")}]


def train(cid, prio):
    return {"id": f"T-{cid}", "type": "raw", "kind": f"train_t2_{cid}", "server": "train", "est": round(STEPS * SEC_PER_STEP / 60), "prio": prio, "deps": [],
            "cmd": [PY, "{WT}/topic2_semantic_order/train_semantic.py" if cid.startswith("B") else "{WT}/sft_dpo_inventory/ablation_011/train/train_a11.py",
                    "--config", f"{{WT}}/topic2_semantic_order/configs/{cid}.yaml"]}


def lora(name, ck):
    return f"lora:{name}={ck}"


def main():
    jobs = []
    for i, s in enumerate(SEEDS):
        jobs.append(train(f"B-o{s}", 1 + i))
    for i, s in enumerate(SEEDS):
        cid = f"B-o{s}"
        ck = f"{WORK}/{cid}/checkpoint-{STEPS}"
        name = cid.replace("-", "_")
        srv = lora(name, ck)
        dep = f"file:{ck}/adapter_model.safetensors|T-{cid}"
        jobs.append({"id": f"H-{cid}", "type": "raw", "kind": f"hdev_t2_{cid}", "server": srv, "est": 35, "prio": 10 + i, "deps": [dep, TOOLS],
                     "cells": hdev_cells(name, f"hdev_t2_b_o{s}")})
        jobs.append({"id": f"E-{cid}", "type": "raw", "kind": f"cells_t2_{cid}_rdevv2_valid98_aux_k4", "server": srv, "est": 45, "prio": 20 + i, "deps": [dep, TOOLS],
                     "cells": e1_cells(name, f"t2_b_o{s}")})
        jobs.append({"id": f"C-{cid}", "type": "raw", "kind": f"ct10k_t2_{cid}_k1", "server": srv, "est": 150, "prio": 30 + i, "deps": [dep, TOOLS],
                     "cells": ct_cells(name, f"ct10k_t2_b_o{s}")})
    for i, s in enumerate((2026117, 2026131)):  # A0 models without CT10K
        d = T13
        ck = f"{d}/A0-o{s}/checkpoint-{STEPS}"
        name = f"A0_o{s}"
        jobs.append({"id": f"C-A0-o{s}", "type": "raw", "kind": f"ct10k_t2_A0-o{s}_k1", "server": lora(name, ck), "est": 150, "prio": 40 + i, "deps": [TOOLS],
                     "cells": ct_cells(name, f"ct10k_t2_a0_o{s}")})
    # repeat pair (same order seed, same model seed 43; new run) on o2026131
    for i, cid in enumerate(("A0-o2026131-r2", "B-o2026131-r2")):
        jobs.append(train(cid, 50 + i))
    for i, cid in enumerate(("A0-o2026131-r2", "B-o2026131-r2")):
        ck = f"{WORK}/{cid}/checkpoint-{STEPS}"
        name = cid.replace("-", "_")
        jobs.append({"id": f"H-{cid}", "type": "raw", "kind": f"hdev_t2_{cid}", "server": lora(name, ck), "est": 35, "prio": 60 + i,
                     "deps": [f"file:{ck}/adapter_model.safetensors|T-{cid}", TOOLS], "cells": hdev_cells(name, f"hdev_t2_{cid.lower().replace('-', '_')}")})
    names = [c["name"] for j in jobs for c in j.get("cells", [])]
    assert len(names) == len(set(names)), "duplicate cell names"
    (HERE / "jobs_t2.json").write_text(json.dumps({"label": "topic2_semantic_order(decision 264)", "jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(len(jobs), "jobs;", len(names), "cells;", [(j["id"], j["prio"], j["est"]) for j in jobs])


if __name__ == "__main__":
    main()
