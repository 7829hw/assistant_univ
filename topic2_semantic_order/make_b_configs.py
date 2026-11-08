#!/usr/bin/env python3
"""Generate Arm B (semantic order) configs, plus the optional repeat pair for the nondeterminism check.

Each B config is the matching A0 config with ONLY these keys changed: training.{shared_slot_order_seed,
shared_slot_order_file, a11_record_order_file} -> training.{semantic_schedule_seed, semantic_schedule_file},
training.output_dir, profiling.output. Paths are repo-relative so a commit-pinned worktree uses its own copy.
A0 source: ablation_011 (seeds 1102/211102/2026113) or ablation_013 (2026117/2026131); the A0 models are reused.
"""
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "topic2_semantic_order/configs"
WORK = "/data/hwkim/sftdpo_work/topic2_semantic_order/train"
SEEDS = [1102, 211102, 2026113, 2026117, 2026131]


def a0_src(seed):
    for ab in ("ablation_011", "ablation_013"):
        p = ROOT / f"sft_dpo_inventory/{ab}/train/configs/A0-o{seed}.yaml"
        if p.exists():
            return p
    raise FileNotFoundError(seed)


def dump(cfg, path, header):
    path.write_text(f"# {header}\n" + yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=True)
    rows = []
    for seed in SEEDS:
        src = a0_src(seed)
        cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
        t = cfg["training"]
        for k in ("shared_slot_order_seed", "shared_slot_order_file", "a11_record_order_file"):
            t.pop(k)
        t["semantic_schedule_seed"] = seed
        t["semantic_schedule_file"] = f"topic2_semantic_order/orders/semantic_order_o{seed}.json"
        cid = f"B-o{seed}"
        t["output_dir"] = f"{WORK}/{cid}"
        cfg["profiling"]["output"] = f"{WORK}/{cid}_profile.json"
        dump(cfg, OUT / f"{cid}.yaml", f"Topic2 Arm B ({cid}): {src.name} with semantic order only (decision 264)")
        rows.append({"id": cid, "arm": "B", "seed": seed, "a0_config": str(src.relative_to(ROOT))})
    # repeat pair on the most variable A0 seed (nondeterminism check; same order, same model seed, new run)
    seed = 2026131
    src = a0_src(seed)
    cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
    cfg["training"]["output_dir"] = f"{WORK}/A0-o{seed}-r2"
    cfg["profiling"]["output"] = f"{WORK}/A0-o{seed}-r2_profile.json"
    dump(cfg, OUT / f"A0-o{seed}-r2.yaml", "Topic2 repeat of A0-o2026131 (output path only changed; run-to-run nondeterminism)")
    rows.append({"id": f"A0-o{seed}-r2", "arm": "A0-repeat", "seed": seed, "a0_config": str(src.relative_to(ROOT))})
    b = yaml.safe_load((OUT / f"B-o{seed}.yaml").read_text(encoding="utf-8"))
    b["training"]["output_dir"] = f"{WORK}/B-o{seed}-r2"
    b["profiling"]["output"] = f"{WORK}/B-o{seed}-r2_profile.json"
    dump(b, OUT / f"B-o{seed}-r2.yaml", "Topic2 repeat of B-o2026131 (output path only changed)")
    rows.append({"id": f"B-o{seed}-r2", "arm": "B-repeat", "seed": seed, "a0_config": str(src.relative_to(ROOT))})
    (OUT / "manifest.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
