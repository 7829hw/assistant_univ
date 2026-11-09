"""Phase 0/2: audit the 8 existing checkpoints and generate the 10 new run configs (r2/r3). A new config = its r1 config with ONLY
training.output_dir and profiling.output changed (same data, order, seed 43, LoRA, LR, template, thinking, loss scope)."""
import hashlib, json, subprocess, sys
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "topic2_semantic_order_repro"
WORK = "/data/hwkim/sftdpo_work/topic2_semantic_order_repro/train"
EXIST = "/data/hwkim/sftdpo_work"
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csha(c): return hashlib.sha256(json.dumps(c, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
def a0_cfg(seed):
    for ab in ("ablation_011", "ablation_013"):
        p = ROOT / f"sft_dpo_inventory/{ab}/train/configs/A0-o{seed}.yaml"
        if p.exists(): return p
def a0_ckpt(seed, ab_dir=None):
    for ab in ("ablation_011", "ablation_013"):
        p = Path(f"{EXIST}/{ab}/train/A0-o{seed}/checkpoint-1984")
        if p.exists(): return p
def a_order_sha(seed):
    for ab in ("ablation_011", "ablation_013"):
        p = ROOT / f"sft_dpo_inventory/{ab}/build/orders/order_b2_o{seed}.json"
        if p.exists(): return json.loads(p.read_text())["order_sha256"]
SEEDS = [1102, 211102, 2026131]
existing = {}
for s in SEEDS:
    existing[("A", s, 1)] = (a0_cfg(s), a0_ckpt(s))
    existing[("B", s, 1)] = (ROOT / f"topic2_semantic_order/configs/B-o{s}.yaml", Path(f"{EXIST}/topic2_semantic_order/train/B-o{s}/checkpoint-1984"))
existing[("A", 2026131, 2)] = (ROOT / "topic2_semantic_order/configs/A0-o2026131-r2.yaml", Path(f"{EXIST}/topic2_semantic_order/train/A0-o2026131-r2/checkpoint-1984"))
existing[("B", 2026131, 2)] = (ROOT / "topic2_semantic_order/configs/B-o2026131-r2.yaml", Path(f"{EXIST}/topic2_semantic_order/train/B-o2026131-r2/checkpoint-1984"))
train = ROOT / "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl"
audit = []
for (arm, s, r), (cfgp, ck) in sorted(existing.items()):
    cfg = yaml.safe_load(cfgp.read_text())
    t = cfg["training"]
    prof_p = Path(cfg["profiling"]["output"]) if Path(cfg["profiling"]["output"]).exists() else None
    prof = json.loads(prof_p.read_text()) if prof_p else {}
    bseq = ROOT / f"topic2_semantic_order/orders/semantic_order_o{s}.json"
    audit.append({"arm": arm, "order_seed": s, "run": f"r{r}", "config": str(cfgp.relative_to(ROOT)), "config_sha256": sha(cfgp),
                  "checkpoint": str(ck), "adapter_sha256": sha(ck / "adapter_model.safetensors") if ck.exists() else None,
                  "model": cfg.get("model", {}).get("name_or_path") or cfg.get("model"), "train_data_sha256": sha(train),
                  "order_sha256": json.loads(bseq.read_text())["record_sequence_sha256"] if arm == "B" else a_order_sha(s),
                  "training_seed": t.get("seed"), "total_seconds": prof.get("total_seconds"), "mean_logged_loss": prof.get("mean_logged_loss"),
                  "policy_tokens": prof.get("policy_tokens"), "status": prof.get("status")})
(R / "tables/checkpoint_audit.json").write_text(json.dumps(audit, indent=1, ensure_ascii=False, default=str))
# generate new configs
new = []
for arm in "AB":
    for s in SEEDS:
        runs = (2, 3) if s != 2026131 else (3,)
        for r in runs:
            src = existing[(arm, s, 1)][0]
            cfg = yaml.safe_load(src.read_text())
            cid = f"{'A0' if arm == 'A' else 'B'}-o{s}-r{r}"
            cfg["training"]["output_dir"] = f"{WORK}/{cid}"
            cfg["profiling"]["output"] = f"{WORK}/{cid}_profile.json"
            out = R / f"configs/{cid}.yaml"
            out.write_text(f"# Repro {cid}: {src.name} with ONLY output paths changed (same data/order/seed 43/LoRA/LR)\n" + yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
            base = yaml.safe_load(src.read_text())
            def flat(d, p=""):
                return {p + k: v for k0, v0 in d.items() for k, v in (flat(v0, p + k0 + ".").items() if isinstance(v0, dict) else [(k0, v0)])}
            fa, fb = flat(base), flat(cfg)
            diff = sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))
            ok = all(d.endswith("output_dir") or d.endswith("output") for d in diff)
            new.append({"id": cid, "arm": arm, "order_seed": s, "run": f"r{r}", "src_config": str(src.relative_to(ROOT)), "diff_keys": diff, "only_paths_differ": ok, "config_sha256": sha(out)})
(R / "configs/manifest.json").write_text(json.dumps(new, indent=1))
print(len(new), all(n["only_paths_differ"] for n in new))
for a in audit: print(a["arm"], a["order_seed"], a["run"], (a["adapter_sha256"] or "NONE")[:12], a["status"], a["training_seed"], a["order_sha256"][:12])
