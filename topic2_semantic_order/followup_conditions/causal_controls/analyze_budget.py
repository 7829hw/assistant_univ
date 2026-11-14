"""Analyze only verified final-evaluation receipts for the two-arm budget study."""
import argparse
from pathlib import Path

from budget_plan import ARMS, DATASETS, ORDER_SEEDS, TRAIN_SEEDS, manifest
from common import S, STEPS, dump, load, np
from execution import budget_paths
from analyze_controls import T975_DF7, environment_key, result_paths, sign_flip_p
from integration import json_lines
from regression import A, context, read_model, run_summary
from taxonomy import write_csv
from uncertainty import secondary_intervals, transition_summary

CONTRAST = "S1T0_minus_S0T0"
DEFERRED = ("semantic", "supervision", "interaction", "true_vs_placebo", "placebo_vs_blind", "high_vs_low_gap")


def paired_estimate(runs, option):
    pairs, invalid = [], []
    for order in ORDER_SEEDS:
        block = [runs.get((arm, order, seed)) for seed in TRAIN_SEEDS for arm in ARMS]
        signatures = {run["signature"] for run in block if run is not None}
        for index, seed in enumerate(TRAIN_SEEDS):
            left, right = block[2*index:2*(index+1)]
            if left is None or right is None or len(signatures)!=1:
                invalid.append(f"o{order}-t{seed}")
                continue
            pairs.append(dict(order_seed=order, training_seed=seed, difference=right["collapse20"]-left["collapse20"]))
    if invalid:
        return dict(status="INCOMPLETE", missing_or_incomparable_pairs=invalid, paired_differences=pairs)
    differences = np.array([p["difference"] for p in pairs]).reshape(len(ORDER_SEEDS),len(TRAIN_SEEDS))
    block_means = differences.mean(axis=1)
    mean = float(block_means.mean())
    sd = float(block_means.std(ddof=1))
    half_width = T975_DF7 * sd / np.sqrt(len(block_means))
    return dict(status="EXPLORATORY" if option=="A" else "PROSPECTIVE_DEVELOPMENT_CONTRAST",
                paired_differences=pairs, order_block_means=block_means.tolist(),
                across_order_block_sd=sd, within_order_training_seed_sd=differences.std(axis=1,ddof=1).tolist(),
                training_seed_means=dict(zip(map(str,TRAIN_SEEDS),differences.mean(axis=0).tolist(),strict=True)),
                training_seed_mean_difference=float((differences[:,1]-differences[:,0]).mean()),
                estimate=mean, nominal_ci95=[mean-half_width,mean+half_width],
                sign_flip_p=sign_flip_p(block_means) if option=="B" else None)


def observed_runs(plan, training_dir, eval_dir):
    receipts = {r["cell"]:r for r in json_lines(eval_dir/"execution"/"eval_provenance.jsonl")}
    if not receipts:
        return {}, {}, [], None
    dataset = plan["dataset"]
    ids, clusters, groups = context(dataset)
    ref_paths=A.ct_base_paths() if dataset=="CT10K" else [[f"{A.C12}/hdev_base_s{k}.json"] for k in (1,2)]
    base=np.mean([read_model(paths,ids)[0]=="match" for paths in ref_paths],axis=0)
    gold=A.load_gold(A.CT if dataset=="CT10K" else A.HDEV)
    groups_of={item:A.esig(gold[item].get("gold"))[1] for item in ids}
    tab=A.Tab(ids,groups_of,clusters,A.MIN_CT if dataset=="CT10K" else A.MIN_HD)
    runs, vectors, rows = {}, {}, []
    for job in plan["jobs"]:
        receipt_file = training_dir/f"{job['job']}_training.json"
        if not receipt_file.is_file():
            continue
        train = load(receipt_file)
        _, train_manifest = manifest(train["budget_option"])
        if (not train["complete"] or train["optimizer_steps"]!=STEPS or
            train["config_sha256"]!=job["config_sha256"] or train["order_sha256"]!=job["order"]["sha256"] or
            train["manifest_sha256"]!=S.sha_file(train_manifest) or
            not train.get("checkpoint_hashes",{}).get(str(STEPS))):
            raise ValueError(f"Training receipt fails policy: {job['job']}")
        paths, sigs = result_paths(job["checkpoint"],dataset,receipts,train,plan["eval_input_sha256"],out=eval_dir)
        if not paths:
            continue
        cats, diag = read_model(paths,ids)
        key = job["arm"],job["order_seed"],job["training_seed"]
        signature = environment_key(sigs,train)
        summary = run_summary(cats,groups,base)
        rows.append(dict(job=job["job"],order_seed=key[1],training_seed=key[2],arm=key[0],**summary,**diag,
                         **transition_summary(cats=="match",base),environment_verified=signature is not None))
        if signature is not None:
            runs[key] = dict(collapse20=summary["collapse20"],signature=signature)
            vectors[key] = (cats=="match").astype(float)
    return runs, vectors, rows, (tab, base)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("option",choices=DATASETS)
    parser.add_argument("--out-dir",type=Path,required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("Write to a fresh analysis directory")
    plan, path = manifest(args.option)
    runs, vectors, rows, context_for_intervals = observed_runs(plan, *budget_paths(args.option))
    comparison = paired_estimate(runs,args.option)
    if context_for_intervals is not None and comparison["status"]!="INCOMPLETE":
        tab, base = context_for_intervals
        comparison["secondary_bootstrap"] = secondary_intervals(
            tab,vectors,base,ORDER_SEEDS,TRAIN_SEEDS,{CONTRAST:{"S1T0":1,"S0T0":-1}}
        )[CONTRAST]
    dump(args.out_dir/"contrast.json",dict(option=args.option,dataset=plan["dataset"],manifest_sha256=S.sha_file(path),
                                          observed_runs=len(rows),contrast=CONTRAST,result=comparison,
                                          frozen_six={k:"NOT_TESTED" for k in DEFERRED}))
    if rows:
        write_csv(args.out_dir/"final_per_run.csv",rows)
    print(f"{args.option} {len(rows)}/32 observed runs, {comparison['status']}")


if __name__=="__main__":
    main()
