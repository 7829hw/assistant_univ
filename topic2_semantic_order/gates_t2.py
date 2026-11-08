#!/usr/bin/env python3
"""Pre-GPU gates G1-G10 for Topic 2 A/B. Writes gates/GATES.json (+ per-config dry-run/tokenizer logs).
Run from repo root with the hf env python (needed for the sampler functional check and dry-run/tokenizer-check)."""
import hashlib, json, os, subprocess, sys, shutil
from collections import Counter
from pathlib import Path
import yaml

ROOT = Path.cwd()
T2 = ROOT / "topic2_semantic_order"
sys.path.insert(0, str(T2))
import semantic_schedule as S  # noqa: E402

TRAIN = ROOT / "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl"
APPR = ROOT / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v6.jsonl"
SEEDS = [1102, 211102, 2026113, 2026117, 2026131]
PY = sys.executable
res = {}


def gate(name, ok, evidence):
    res[name] = {"status": "PASS" if ok else "FAIL", "evidence": evidence}
    print(name, res[name]["status"], flush=True)


records = S.read_jsonl(TRAIN)
keys = [S.rid(r) for r in records]
# G1
man = json.loads((ROOT / "sft_dpo_inventory/pilot_010/build/V4/full/manifest.json").read_text())
sha = S.sha_file(TRAIN)
txt = json.dumps(man)
EXPECT = "3575c7f06c2ee7baaf59233b01c926504589ec2fbf3136f255a45599ced10e3f"
gate("G1_v4_sha256", sha == EXPECT and sha in txt, {"sha256": sha, "in_manifest": sha in txt, "expected_pinned_in_plan": EXPECT,
     "manifest_sft_keys": list(man["sft"])[:8]})
# G2/G3
ev2, ok2 = {}, True
for s in SEEDS:
    b = json.loads((T2 / f"orders/semantic_order_o{s}.json").read_text())["record_sequence"]
    a_p = next(p for p in (ROOT / f"sft_dpo_inventory/{d}/build/orders/record_order_A0_o{s}.json" for d in ("ablation_011", "ablation_013")) if p.exists())
    a = json.loads(a_p.read_text())["a0_record_sequence"] if "a0_record_sequence" in json.loads(a_p.read_text()) else None
    a = json.loads(a_p.read_text())["record_sequence"]
    ok = (len(a) == len(b) == 1984 and set(a) == set(b) == set(keys) and len(set(a)) == 1984 and len(set(b)) == 1984
          and a != b and Counter(S.qid_of_key(k) if hasattr(S, "qid_of_key") else k.split("|")[0] for k in a) == Counter(k.split("|")[0] for k in b))
    ok2 &= ok
    ev2[s] = {"A_n": len(a), "B_n": len(b), "same_set": set(a) == set(b) == set(keys), "A_unique": len(set(a)), "B_unique": len(set(b)),
              "A_sha": S.sha_lines(a), "B_sha": S.sha_lines(b), "A_order_file": str(a_p.relative_to(ROOT)), "orders_differ": a != b}
gate("G2_G3_same_1984_each_once", ok2, ev2)
# G4/G5
labels = S.labels_from_approved(records, S.read_jsonl(APPR))
ev4, ok4 = {}, True
for s in SEEDS + [7, 99, 12345, 424242, 5, 6, 8, 9]:
    o1 = S.build_balanced_order(records, labels, s)
    o2 = S.build_balanced_order(records, labels, s)
    ok = o1 == o2 and len(o1) == 1984 and set(o1) == set(keys) and S.max_run([k.split("|")[0] for k in o1]) <= 4
    if s in SEEDS:
        ok &= S.sha_lines(o1) == json.loads((T2 / f"orders/semantic_order_o{s}.json").read_text())["record_sequence_sha256"]
    ok4 &= ok
    ev4[s] = {"ok": ok, "sha": S.sha_lines(o1)[:16], "max_run": S.max_run([k.split("|")[0] for k in o1])}
shas = {v["sha"] for v in ev4.values()}
gate("G4_multi_seed_valid", ok4 and len(shas) == len(ev4), ev4)
gate("G5_same_seed_reproducible_and_matches_frozen_files", ok4, "each seed generated twice in-process; frozen order file sha re-matched (see G4 evidence)")
# G6 config diff
ALLOWED = {"training.shared_slot_order_seed", "training.shared_slot_order_file", "training.a11_record_order_file",
           "training.semantic_schedule_seed", "training.semantic_schedule_file", "training.output_dir", "profiling.output"}


def flat(d, p=""):
    o = {}
    for k, v in d.items():
        if isinstance(v, dict):
            o.update(flat(v, p + k + "."))
        else:
            o[p + k] = v
    return o


ev6, ok6 = {}, True
for s in SEEDS:
    a_p = next(p for p in (ROOT / f"sft_dpo_inventory/{d}/train/configs/A0-o{s}.yaml" for d in ("ablation_011", "ablation_013")) if p.exists())
    fa, fb = flat(yaml.safe_load(a_p.read_text())), flat(yaml.safe_load((T2 / f"configs/B-o{s}.yaml").read_text()))
    diff = sorted(k for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))
    bad = [k for k in diff if k not in ALLOWED]
    ok6 &= not bad
    ev6[s] = {"diff_keys": diff, "unexpected": bad, "a0_config": str(a_p.relative_to(ROOT))}
# the A0 configs differ from one another only by order keys/output paths
base = flat(yaml.safe_load((ROOT / "sft_dpo_inventory/ablation_011/train/configs/A0-o1102.yaml").read_text()))
for s in SEEDS[1:]:
    a_p = next(p for p in (ROOT / f"sft_dpo_inventory/{d}/train/configs/A0-o{s}.yaml" for d in ("ablation_011", "ablation_013")) if p.exists())
    fa = flat(yaml.safe_load(a_p.read_text()))
    bad = [k for k in set(fa) | set(base) if fa.get(k) != base.get(k) and k not in ALLOWED]
    ok6 &= not bad
    ev6[f"A0-o{s}_vs_A0-o1102_unexpected"] = bad
gate("G6_config_only_order_differs", ok6, ev6)
# G7 sampler functional check
import torch
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/pilot_007/train_data"))
import order7
from transformers import Trainer
fn = order7.install_sequential_sampler()


class Dummy:  # stands for the Trainer object
    train_dataset = list(range(1984))


smp = Trainer._get_train_sampler(Dummy())
gate("G7_sequential_sampler", Trainer._get_train_sampler is fn and list(smp) == list(range(1984)) and type(smp).__name__ == "SequentialSampler",
     {"sampler": type(smp).__name__, "first5": list(smp)[:5], "note": "dry-run logs also print trainer_sampler=SequentialSampler and the order sha"})
# G8 dry-run + tokenizer-check
env = {**os.environ, "HF_HOME": "/data/hwkim/sftdpo_work/hf-cache", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "CUDA_VISIBLE_DEVICES": "", "PYTHONDONTWRITEBYTECODE": "1"}
ev8, ok8 = {}, True
(T2 / "gates").mkdir(exist_ok=True)
for cid in [f"B-o{s}" for s in SEEDS]:
    for mode in ("dry-run", "tokenizer-check"):
        lg = T2 / f"gates/{cid}.{mode}.log"
        r = subprocess.run([PY, str(T2 / "train_semantic.py"), "--config", str(T2 / f"configs/{cid}.yaml"), f"--{mode}"], cwd=ROOT, env=env, capture_output=True, text=True)
        lg.write_text(r.stdout + r.stderr, encoding="utf-8")
        good = r.returncode == 0 and ("Tokenizer prefix and length checks passed" in r.stdout if mode == "tokenizer-check" else '"lr_plan"' in r.stdout)
        good &= '"trainer_sampler": "SequentialSampler"' in r.stdout
        seed = int(cid.split("o")[-1])
        good &= json.loads((T2 / f"orders/semantic_order_o{seed}.json").read_text())["record_sequence_sha256"] in r.stdout
        ok8 &= good
        ev8[f"{cid}.{mode}"] = {"rc": r.returncode, "ok": good, "log": str(lg.relative_to(ROOT))}
gate("G8_dry_run_and_tokenizer_check", ok8, ev8)
# G9 resources
du = shutil.disk_usage("/data/hwkim")
smi = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,memory.used,memory.total", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip().splitlines()
free_gib = du.free / 2**30
used = [int(x.split(",")[2].split()[0]) for x in smi]
gate("G9_resources", free_gib > 250 and max(used) < 2000, {"disk_free_GiB": round(free_gib, 1), "needed_estimate_GiB": "5 trainings x ~4 checkpoints x ~0.6 GiB + raw outputs ~3 GiB per CT10K; < 60", "gpus": smi})
# G10 conflicts
# NOT pgrep -f (it matches its own shell command line; CLAUDE.md waiting rule 3): inspect comm + argv of real processes only
rows = subprocess.run(["ps", "-eo", "pid,comm,args"], capture_output=True, text=True).stdout.splitlines()[1:]
pat = ("scheduler1", "train_a11", "train_semantic", "vllm.entrypoints", "vllm serve")
ps = "\n".join(r for r in rows if r.split(None, 2)[1].startswith(("python", "ollama", "vllm")) and any(x in r for x in pat) and "gates_t2" not in r)
apps = subprocess.run(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip()
gate("G10_no_conflict", ps == "" and apps == "", {"matching_processes": ps, "gpu_compute_apps": apps})
(T2 / "gates/GATES.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({k: v["status"] for k, v in res.items()}))
sys.exit(0 if all(v["status"] == "PASS" for v in res.values()) else 1)
