"""Derive the proposed final-only manifests from the frozen causal-control plan."""
import argparse
from itertools import product
from pathlib import Path

from schedules import HERE, ORDER_SEEDS, TRAIN_SEEDS
from common import S, STEPS, dump, load, local
from execution import PLAN, plan_locked, run_id

DATASETS = {"A": "H-dev", "B": "CT10K"}
ARMS = ("S0T0", "S1T0")
AMENDMENT = HERE/"BUDGET_AMENDMENT.md"
FOLDER = HERE/"budget"


def build(option):
    dataset = DATASETS[option]
    source = plan_locked()
    jobs = {job["id"]: job for job in source["jobs"]}
    selected = []
    for index, order in enumerate(ORDER_SEEDS):
        if not load(HERE/f"audits/o{order}.json")["factorial"]["S0T0_vs_S1T0"]["eligible"]:
            raise ValueError(f"Frozen exposure gate failed for order {order}")
        for seed, arm in product(TRAIN_SEEDS, ARMS):
            job = jobs[run_id(arm, order, seed)]
            final = next(c for c in job["checkpoints"] if c["step"] == STEPS)
            cells = [c for c in final["cells"] if c["dataset"] == dataset]
            if len(cells) != (1 if option == "A" else 5):
                raise ValueError("Final evaluation cell set has changed")
            selected.append(dict(job=job["id"], arm=arm, order_seed=order, training_seed=seed,
                                 gpu_slot=index % 3, config=job["config"], config_sha256=job["config_sha256"],
                                 order=job["order"], checkpoint={**final, "cells": cells}))
    eval_inputs = {p for job in selected for c in job["checkpoint"]["cells"]
                   for p in (c["gold"], c["chunk"]) if p}
    return dict(status="BLOCKED_PENDING_TASK_SPECIFIC_GPU_AUTHORIZATION", option=option, dataset=dataset,
                parent_manifest=local(PLAN), parent_manifest_sha256=S.sha_file(PLAN),
                budget_amendment_sha256=S.sha_file(AMENDMENT), optimizer_steps=STEPS,
                checkpoint_steps=[STEPS], intermediate_eval_cells=0, jobs=selected,
                eval_input_sha256={p: source["eval_input_sha256"][p] for p in sorted(eval_inputs)},
                evaluation=source["evaluation"], deferred_arms=["S0T1", "S1T1", "placebo", "low_gap", "high_gap"])


def manifest(option):
    path = FOLDER/f"option_{option}.json"
    plan = load(path)
    if plan != build(option):
        raise ValueError("Budget manifest differs from the frozen plan or amendment")
    return plan, path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit", type=Path, help="Generate both options in a fresh directory")
    args = parser.parse_args()
    if args.emit:
        args.emit.mkdir()
    for option in DATASETS:
        if args.emit:
            plan = build(option)
            dump(args.emit/f"option_{option}.json", plan)
        else:
            plan, _ = manifest(option)
        print(option, plan["dataset"], len(plan["jobs"]), sum(len(j["checkpoint"]["cells"]) for j in plan["jobs"]))


if __name__ == "__main__":
    main()
