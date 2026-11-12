"""Check existing input, order, evaluation and adapter assets without GPU use."""
from collections import Counter
import subprocess
import sys

from common import *

sys.path.insert(0, str(T2 / "analysis"))
import analyze_t2 as A
sys.path.insert(0, str(ROOT / "topic2_semantic_order_repro/analysis"))
import variance_repro as R


def main():
    records = input_records()
    labels = labels_for(records)
    repeat = load(ROOT / "topic2_semantic_order_repro/tables/checkpoint_audit.json")
    repeat_refs = {(r["arm"], int(r["order_seed"]), r["run"]): r for r in repeat}
    extra_manifest = {(r["arm"], int(r["order_seed"]), r["run"]):r for r in
                      load(ROOT / "topic2_semantic_order_repro/configs/manifest.json")}
    rev_path = WORK / f"hf-cache/hub/models--Qwen--Qwen3-8B/snapshots/{REV}"
    model_paths = sorted(rev_path.glob("model-*.safetensors"))
    if len(model_paths) != 5 or not all(p.is_file() for p in model_paths):
        raise ValueError("Pinned base model snapshot is incomplete")
    report = {
        "reference_commit": subprocess.check_output(["git", "rev-parse", "5d6a2576"], text=True).strip(),
        "training_inputs": {local(p): S.sha_file(p) for p in (TRAIN, V4 / "sft_valid.jsonl", V4 / "manifest.json", APPROVED)},
        "base_snapshot": {"revision": REV, "shards_present": [p.name for p in model_paths],
                          "tokenizer_sha256": S.sha_file(rev_path / "tokenizer.json")},
        "records": len(records), "questions": len(labels),
        "scopes": dict(Counter(r["metadata"]["loss_scope"] for r in records)), "orders": [], "checkpoints": [],
        "evaluations": {},
    }
    for arm in ("A", "B"):
        for seed in SEEDS:
            seq, files = actual_order(arm, seed, records)
            run, flips = check_seq(seq, records, within=arm == "B")
            report["orders"].append(dict(arm=arm, seed=seed, sequence_sha256=S.sha_lines(seq), max_run=run,
                                         question_orders_differing_from_sorted_slots=flips,
                                         files={local(p): S.sha_file(p) for p in files}))
            for r in ("r1", "r2", "r3"):
                ref = repeat_refs.get((arm, seed, r))
                if r == "r1":
                    cp = source(arm, seed)
                    ck = Path(config(cp)["training"]["output_dir"]) / "checkpoint-1984"
                elif ref:
                    cp, ck = ROOT / ref["config"], Path(ref["checkpoint"])
                elif (extra := extra_manifest.get((arm,seed,r))):
                    cp = ROOT / f"topic2_semantic_order_repro/configs/{extra['id']}.yaml"
                    if S.sha_file(cp) != extra["config_sha256"]:
                        raise ValueError(f"Repeat config hash drift: {cp}")
                    ck = Path(config(cp)["training"]["output_dir"]) / "checkpoint-1984"
                else:
                    continue
                # Historical YAML may retain a pre-migration path.
                ck = Path(str(ck).replace("/home/hwkim/sftdpo_work/", str(WORK) + "/"))
                weights = ck / "adapter_model.safetensors"
                confighash = S.sha_file(cp)
                hashval = S.sha_file(weights) if weights.is_file() else None
                if ref and (confighash != ref["config_sha256"] or (hashval and hashval != ref["adapter_sha256"])):
                    raise ValueError(f"Historical repeat checkpoint mismatch: {ck}")
                prov = ck.parent / "training_provenance.json"
                if not prov.exists():
                    prov = ck / "training_provenance.json"
                report["checkpoints"].append(dict(arm=arm, seed=seed, repeat=r, config=local(cp), config_sha256=confighash,
                                                  adapter_present=bool(hashval), matched_repeat_reference=bool(ref and hashval),
                                                  training_provenance_present=prov.is_file()))
    paths = {
        "ct10k": [A.CT] + [p for pp in A.ct_base_paths() for p in pp] + [p for a in "AB" for s in A.SEEDS for p in A.ct_paths(a,s)],
        "hdev": [A.HDEV] + [f"{A.C12}/hdev_base_s{k}.json" for k in (1, 2)]
                + sorted({A.hd_path(a,s) for a in "AB" for s in A.SEEDS} | {R.path(a,s,r) for a in "AB" for s in R.SEEDS for r in R.RUNS}),
        "e1": list(A.CORE.SETS.values()) + sorted({p for a in "AB" for s in A.SEEDS for pp in A.e1_cells(a,s).values() for p in pp}),
    }
    for name, items in paths.items():
        report["evaluations"][name] = {p: S.sha_file(ROOT / p) if (ROOT / p).is_file() else None for p in items}
    dump(HERE / "provenance/existing_evidence.json", report)
    print({k: (len(v), sum(x is None for x in v.values())) for k,v in report["evaluations"].items()})
    print("verified orders:", len(report["orders"]), "checkpoints present:", sum(x["adapter_present"] for x in report["checkpoints"]))


if __name__ == "__main__":
    main()
