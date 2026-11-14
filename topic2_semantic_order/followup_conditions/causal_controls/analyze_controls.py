"""Analyze completed causal-control training runs and checkpoint trajectories."""
from collections import defaultdict
from itertools import product
from math import sqrt
from pathlib import Path
import argparse

import numpy as np

from schedules import HERE, ORDER_SEEDS, TRAIN_SEEDS
from common import ROOT, S, dump, load, local
from execution import CHECKPOINT_STEPS, plan_locked
from regression import A, context, read_model, run_summary
from taxonomy import summarize_cells, write_csv
from uncertainty import secondary_intervals, transition_summary

CONTRASTS = {
    "semantic": {"S0T0":-.5,"S1T0":.5,"S0T1":-.5,"S1T1":.5},
    "supervision": {"S0T0":-.5,"S1T0":-.5,"S0T1":.5,"S1T1":.5},
    "interaction": {"S0T0":1,"S1T0":-1,"S0T1":-1,"S1T1":1},
    "true_vs_placebo": {"S1T0":1,"placebo":-1},
    "placebo_vs_blind": {"placebo":1,"S0T0":-1},
    "high_vs_low_gap": {"high_gap":1,"low_gap":-1},
}
GATES = {
    "semantic": ("S0T0_vs_S1T0","S0T1_vs_S1T1"),
    "supervision": ("S0T0_vs_S0T1","S1T0_vs_S1T1"),
    "interaction": ("S0T0_vs_S1T0","S0T1_vs_S1T1","S0T0_vs_S0T1","S1T0_vs_S1T1"),
    "true_vs_placebo": ("S0T0_vs_S1T0","placebo","true_vs_placebo"),
    "placebo_vs_blind": ("placebo",),
    "high_vs_low_gap": ("spacing",),
}
FAMILY_ALPHA = .05
T975_DF7 = 2.3646242515927844


def gate_status(audit, key):
    if key == "true_vs_placebo":
        return audit["placebo"]["true_vs_placebo_scope_match"]
    return (audit[key] if key in ("placebo","spacing") else audit["factorial"][key])["eligible"]


def sign_flip_p(blocks):
    x = np.asarray(blocks)
    observed = abs(x.sum())
    the_null = np.asarray(list(product((-1,1),repeat=len(x)))) @ x
    return float(np.mean(np.abs(the_null)>=observed-1e-12))


def holm(pvalues):
    order = sorted(pvalues,key=pvalues.get)
    adjusted = {}
    previous = 0.0
    for i,key in enumerate(order):
        previous = max(previous,min(1.0,(len(order)-i)*pvalues[key]))
        adjusted[key] = previous
    return adjusted


def paired_contrasts(runs, audits):
    values = {}
    for name, weights in CONTRASTS.items():
        order_blocks = {}
        missing = []
        gate_failed = []
        for order in ORDER_SEEDS:
            if not all(gate_status(audits[order],g) for g in GATES[name]):
                gate_failed.append(order)
            pairs=[]
            for train in TRAIN_SEEDS:
                samples=[runs.get((arm,order,train)) for arm in weights]
                if any(s is None for s in samples):
                    missing.append(f"o{order}-t{train}")
                    continue
                # Pair on training and evaluation devices and all comparable
                # runtime/protocol fields. Seeds and checkpoint hashes are
                # recorded separately. Adapter identity varies by run.
                if len({s["comparison_signature"] for s in samples})!=1:
                    missing.append(f"o{order}-t{train}:environment_mismatch")
                    continue
                pairs.append(sum(w*s["collapse20"] for w,s in zip(weights.values(),samples,strict=True)))
            if len(pairs)==len(TRAIN_SEEDS):
                order_blocks[str(order)]=float(np.mean(pairs))
        eligible = not missing and not gate_failed and len(order_blocks)==len(ORDER_SEEDS)
        data = dict(eligible=eligible,order_blocks=order_blocks,failed_order_gates=gate_failed,
                    missing_or_incomparable_pairs=missing,p=1.0,estimate=None,ci95=None)
        if eligible:
            x=np.asarray(list(order_blocks.values()))
            estimate=float(x.mean())
            error=T975_DF7*float(x.std(ddof=1))/sqrt(len(x))
            data.update(p=sign_flip_p(x),estimate=estimate,ci95=[estimate-error,estimate+error])
        values[name]=data
    adj = holm({k:v["p"] for k,v in values.items()})
    for k,v in values.items():
        v.update(holm_adjusted_p=adj[k],reject=v["eligible"] and adj[k]<=FAMILY_ALPHA)
    return values


def core_eval_signature(meta):
    from compare_environment import signature
    fields=signature(meta)
    return {k:v for k,v in fields.items() if k not in ("code_commit","gold_sha256","item_order_sha256")}


def environment_key(metadata, train):
    if (any(v is None for v in metadata[0].values()) or not metadata[0]["sampling"]
        or any(v!=metadata[0] for v in metadata[1:])):
        return None
    if not train.get("packages") or not train.get("cuda") or not train.get("gpu_uuid"):
        return None
    return S.canonical(dict(eval=metadata[0],training={k:train[k] for k in ("gpu_uuid","packages","cuda","commit")}))


def result_paths(checkpoint, dataset, receipts, train, eval_input_sha256, out=HERE):
    paths = []
    signatures=[]
    checkpoint_hashes=set()
    for cell in checkpoint["cells"]:
        if cell["dataset"]!=dataset:
            continue
        label=f"{cell['label']}_s{cell['k']}"
        receipt=receipts.get(label)
        if not receipt:
            return [],[]
        file=out/"cells"/f"{label}.json"
        if S.sha_file(file)!=receipt["sha256"] or receipt["commit"]!=train["commit"] or receipt["gpu_uuid"]!=train["gpu_uuid"]:
            raise ValueError(f"Evaluation receipt mismatch: {label}")
        m=load(file)["meta"]
        if (m["gold_file"]!=cell["gold"] or m["gold_sha256"]!=eval_input_sha256[cell["gold"]]
            or m["vllm"]["server_meta"]["gpu_uuid"]!=train["gpu_uuid"]):
            raise ValueError(f"Evaluation inputs or device changed: {label}")
        checkpoint_hashes.add(m["vllm"]["server_meta"]["adapter_sha256"])
        signatures.append(core_eval_signature(m))
        paths.append(local(file))
    expected_hash=train.get("checkpoint_hashes",{}).get(str(checkpoint["step"]))
    if len(checkpoint_hashes)>1 or (expected_hash and checkpoint_hashes!={expected_hash}):
        raise ValueError("Evaluation adapter does not match the training checkpoint")
    return paths,signatures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir",type=Path,required=True)
    args=parser.parse_args()
    plan=plan_locked()
    audits={s:load(HERE/f"audits/o{s}.json") for s in ORDER_SEEDS}
    receipt_path=HERE/"execution/eval_provenance.jsonl"
    receipts={r["cell"]:r for r in S.read_jsonl(receipt_path)} if receipt_path.exists() else {}
    if args.out_dir.exists():
        parser.error("--out-dir must be a fresh snapshot directory")
    runs, trajectories, summaries, taxonomy_cells = {},[],[],[]
    vectors, transitions, sensitivity = {}, [], {}
    dynamics=defaultdict(list)
    if receipts:
        for dataset in ("CT10K","H-dev"):
            ids,clusters,groups=context(dataset)
            base_paths = A.ct_base_paths() if dataset=="CT10K" else [[f"{A.C12}/hdev_base_s{k}.json"] for k in (1,2)]
            base=np.mean([read_model(p,ids)[0]=="match" for p in base_paths],axis=0)
            for job in plan["jobs"]:
                train_file=HERE/"execution"/f"{job['id']}_training.json"
                if not train_file.exists():
                    continue
                train=load(train_file)
                if (not train["complete"] or train["config_sha256"]!=job["config_sha256"] or
                    train["order_sha256"]!=job["order"]["sha256"] or train["checkpoint_steps"]!=list(CHECKPOINT_STEPS)):
                    raise ValueError(f"No valid completed training receipt: {job['id']}")
                intermediate = {}
                signatures_by_step = {}
                for checkpoint in job["checkpoints"]:
                    paths,sigs=result_paths(checkpoint,dataset,receipts,train,plan["eval_input_sha256"])
                    if not paths:
                        continue
                    step=checkpoint["step"]
                    taxonomy_cells.extend(("causal_controls",f"{job['id']}-ck{step}",job["order_seed"],dataset,p) for p in paths)
                    cats,diagnostics=read_model(paths,ids)
                    key=environment_key(sigs,train)
                    correct=cats=="match"
                    summary=run_summary(cats,groups,base) | transition_summary(correct,base)
                    shared=dict(run=job["id"],arm=job["arm"],order_seed=job["order_seed"],
                                training_seed=job["training_seed"],dataset=dataset)
                    summaries.append(dict(**shared,step=step,**summary,**diagnostics))
                    for level in ("fine","coarse","type"):
                        for label,mask in groups[level].items():
                            transitions.append(dict(**shared,step=step,level=level,group=label,items=int(mask.sum()),
                                                    accuracy=float(correct[mask].mean()),
                                                    refusal=float((cats[mask]=="refused_unsupported").mean()),
                                                    silent_wrong=float((cats[mask]=="answered_mismatch").mean()),
                                                    **transition_summary(correct[mask],base[mask])))
                    if dataset=="CT10K" and step==CHECKPOINT_STEPS[-1] and key is not None:
                        run_key=(job["arm"],job["order_seed"],job["training_seed"])
                        runs[run_key] = dict(**summary,comparison_signature=key)
                        vectors[run_key] = correct.astype(float)
                    intermediate[step]=cats=="match"
                    signatures_by_step[step]=key
                if (set(intermediate)==set(CHECKPOINT_STEPS) and all(signatures_by_step.values())
                    and len(set(signatures_by_step.values()))==1):
                    for level in ("fine","coarse","type"):
                        for label,mask in groups[level].items():
                            accuracy=[float(intermediate[s][mask].mean()) for s in CHECKPOINT_STEPS]
                            prior_minus_final=max(accuracy[:-1])-accuracy[-1]
                            forget=max(0.0,prior_minus_final)
                            gain=accuracy[-1]-accuracy[0]
                            trajectories.append(dict(**shared,level=level,group=label,
                                                      items=int(mask.sum()),accuracy_25=accuracy[0],accuracy_50=accuracy[1],
                                                      accuracy_75=accuracy[2],accuracy_100=accuracy[3],
                                                      prior_peak_minus_final=prior_minus_final,forgetting=forget,final_minus_first=gain))
                            dynamics[(job["id"],job["arm"],dataset,level)].append((forget,gain))
            if dataset=="CT10K" and vectors:
                gold=A.load_gold(A.CT)
                group_of={item:A.esig(gold[item].get("gold"))[1] for item in ids}
                tab=A.Tab(ids,group_of,clusters,A.MIN_CT)
                contrasts={**CONTRASTS,"semantic_at_supervision_off":{"S1T0":1,"S0T0":-1}}
                compatible={name:weights for name,weights in contrasts.items()
                            if all(len({runs.get((arm,o,t),{}).get("comparison_signature") for arm in weights})==1
                                   for o in ORDER_SEEDS for t in TRAIN_SEEDS)}
                sensitivity=secondary_intervals(tab,vectors,base,ORDER_SEEDS,TRAIN_SEEDS,compatible)
    output=args.out_dir
    dump(output/"registered_contrasts.json",dict(comparable_final_ct10k_runs=len(runs),contrasts=paired_contrasts(runs,audits)))
    dump(output/"secondary_uncertainty.json",sensitivity)
    if transitions:
        write_csv(output/"checkpoint_group_transitions.csv",transitions)
    if summaries:
        write_csv(output/"checkpoint_summary.csv",summaries)
    if trajectories:
        write_csv(output/"group_trajectories.csv",trajectories)
        rows=[dict(run=key[0],arm=key[1],dataset=key[2],level=key[3],groups=len(x),
                   mean_forgetting=np.mean(x,axis=0)[0],mean_final_minus_first=np.mean(x,axis=0)[1])
              for key,x in dynamics.items()]
        write_csv(output/"run_forgetting.csv",rows)
    if taxonomy_cells:
        for name,rows in zip(("taxonomy","taxonomy_overlap","taxonomy_sources"),summarize_cells(taxonomy_cells),strict=True):
            write_csv(output/f"{name}.csv",rows)
    print(f"Analyzed {len(runs)} comparable final CT10K runs and {len(trajectories)} checkpoint group trajectories")


if __name__=="__main__":
    main()
