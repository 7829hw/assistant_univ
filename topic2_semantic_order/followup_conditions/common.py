"""Shared, explicitly pinned inputs for the V4 follow-up."""
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REL = HERE.relative_to(ROOT)
T2 = HERE.parent
INV = ROOT / "sft_dpo_inventory"
WORK = Path("/data/hwkim/sftdpo_work")
PY = WORK / "runtime/envs/hf/bin/python"
V4 = INV / "pilot_010/build/V4/full"
TRAIN = V4 / "sft_train.jsonl"
APPROVED = INV / "pilot_006_prep/approved/approved_train_v6.jsonl"
TRAIN_SHA = "3575c7f06c2ee7baaf59233b01c926504589ec2fbf3136f255a45599ced10e3f"
PROMPT = "87048d0c554c365e0e7994d09a4515c1cc646785708ce6dc9d1f120b4b5e8c2c"
REV = "b968826d9c46dd6066d109eabc6255188de91218"
SEEDS = (1102, 211102, 2026113, 2026117, 2026131)
STEPS = 1984
PEAK = 2e-4
WARMUP = 1
CONST = (PEAK * STEPS / 2) / (STEPS - WARMUP)
for p in (ROOT, T2, INV / "pilot_007/train_data", INV / "ablation_011/train"):
    sys.path.insert(0, str(p))
import semantic_schedule as S


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False,
                               default=lambda x: x.item()) + "\n", encoding="utf-8")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def local(path):
    return str(path.relative_to(ROOT))


def source(arm, seed):
    if arm == "A":
        return INV / ("ablation_011" if seed in SEEDS[:3] else "ablation_013") / f"train/configs/A0-o{seed}.yaml"
    if arm == "B":
        return T2 / f"configs/B-o{seed}.yaml"
    raise ValueError(arm)


def config(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def input_records():
    if S.sha_file(TRAIN) != TRAIN_SHA or load(V4 / "manifest.json")["sft"]["output_hashes"]["sft_train.jsonl"] != TRAIN_SHA:
        raise ValueError("V4 hash drift")
    records = S.read_jsonl(TRAIN)
    ids = [S.rid(r) for r in records]
    if len(set(ids)) != len(ids) or len(ids) != STEPS or len({S.qid(r) for r in records}) != 494:
        raise ValueError("Unexpected V4 cardinality")
    return records


def labels_for(records):
    return S.labels_from_approved(records, S.read_jsonl(APPROVED))


def check_seq(seq, records, within=False):
    by_q = defaultdict(list)
    for key, r in S.training_record_slots(records).items():
        by_q[S.qid(r)].append(S.rid(r))
    actual = defaultdict(list)
    for key in seq:
        actual[key.split("|", 1)[0]].append(key)
    if len(seq) != len(records) or set(seq) != {S.rid(r) for r in records} or len(seq) != len(set(seq)):
        raise ValueError("Sequence is not the approved record permutation")
    run = S.max_run([x.split("|", 1)[0] for x in seq])
    if run > 4 or (within and actual != by_q):
        raise ValueError("Sequence violates the question ordering constraints")
    return run, sum(actual[q] != by_q[q] for q in by_q)


def actual_order(arm, seed, records):
    c = config(source(arm, seed))["training"]
    if arm == "A":
        import order7b
        slotpath, orderpath = (ROOT / c[k] for k in ("shared_slot_order_file", "a11_record_order_file"))
        slots, o = load(slotpath), load(orderpath)
        keys = sorted(dict(order7b.slots(records)))
        regenerated = [keys[i] for i in np.random.default_rng(seed).permutation(len(keys))]
        seq = [S.rid(r) for r in order7b.order_records(records, regenerated)]
        if not (regenerated == slots["order"] and slots["seed"] == seed == o["seed"]
                and S.sha_lines(regenerated) == slots["order_sha256"] == o["a0_order_sha256"]
                and seq == o["a0_record_sequence"] and S.sha_lines(seq) == o["a0_record_sequence_sha256"]):
            raise ValueError("NumPy O4′ reference differs from frozen A")
        files = [slotpath, orderpath]
    else:
        orderpath = ROOT / c["semantic_schedule_file"]
        o = load(orderpath)
        seq = o["record_sequence"]
        if not (o["seed"] == seed and o["training_sha256"] == TRAIN_SHA and o["fine_weight"] == .24):
            raise ValueError("Frozen B metadata drift")
        files = [orderpath]
    if not (S.sha_lines(seq) == o["record_sequence_sha256"] and seq == o["record_sequence"]):
        raise ValueError("Frozen order hash drift")
    check_seq(seq, records, within=arm == "B")
    return seq, files


def analytical_rates(kind, steps=STEPS):
    if kind == "linear":
        return np.r_[0., PEAK * np.arange(steps - 1, 0, -1) / (steps - 1)]
    if kind == "constant_with_warmup":
        return np.r_[0., np.full(steps - 1, CONST)]
    raise ValueError(kind)


def hf_rates(c, steps=STEPS):
    import torch
    from transformers import get_scheduler
    from trl import SFTConfig
    t = c["training"]
    a = SFTConfig(output_dir="/tmp/followup-lr", use_cpu=True, report_to="none",
                  learning_rate=t["learning_rate"], lr_scheduler_type=t.get("lr_scheduler_type", "linear"),
                  warmup_steps=t["warmup_steps"], warmup_ratio=t["warmup_ratio"])
    opt = torch.optim.AdamW([torch.nn.Parameter(torch.zeros(1))], lr=a.learning_rate)
    sch = get_scheduler(a.lr_scheduler_type, opt, num_warmup_steps=a.get_warmup_steps(steps), num_training_steps=steps)
    rates = []
    for _ in range(steps):
        rates.append(opt.param_groups[0]["lr"])
        opt.step()
        sch.step()
    return np.array(rates)
