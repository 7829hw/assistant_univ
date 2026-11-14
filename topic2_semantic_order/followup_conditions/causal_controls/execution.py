"""Freeze the run matrix, validate training on CPU and prepare checkpoint evaluation."""
import argparse
import copy
from datetime import datetime
import os
import shutil
from pathlib import Path
import sys

import yaml

from schedules import HERE, FACTORIAL, TRAIN_SEEDS, assert_block_sequence, experiment
from common import (HERE as FOLLOWUP, ROOT, WORK, PROMPT, REV, S, STEPS, TRAIN_SHA, config,
                    check_seq, dump, hf_rates, analytical_rates, load, local, source)
from prepare import data_policy, diff_keys

MAIN_RESULTS = Path("/home/hwkim/assistant_univ") / HERE.relative_to(ROOT)
CHECKPOINT_STEPS = (496, 992, 1488, 1984)
OUTPUT = WORK/"topic2_semantic_order/followup_conditions/causal_controls/train"
PLAN = HERE/"run_plan.json"
CONFIG_KEYS = {"training.output_dir","profiling.output","training.seed","training.data_seed",
               "training.semantic_schedule_seed","training.semantic_schedule_file"}


def run_id(arm, order_seed, training_seed):
    return f"{arm}-o{order_seed}-t{training_seed}"


def matrix():
    order_manifest=load(HERE/"orders/manifest.json")
    eval_manifest=load(FOLLOWUP/"gpu/jobs_phase1.json")
    template=[c for c in eval_manifest["jobs"][0]["cells"] if c["dataset"] in ("CT10K","H-dev")]
    jobs=[]
    for order in order_manifest["runs"]:
        arm,seed=order["arm"],order["order_seed"]
        ref = config(source("B",1102))
        for train_seed in TRAIN_SEEDS:
            name=run_id(arm,seed,train_seed)
            c=copy.deepcopy(ref)
            c["training"].update(output_dir=str(OUTPUT/name),seed=train_seed,data_seed=train_seed,
                                 semantic_schedule_seed=seed,semantic_schedule_file=order["path"])
            c["profiling"]["output"]=str(OUTPUT/f"{name}_profile.json")
            path=HERE/"configs"/f"{name}.yaml"
            path.parent.mkdir(exist_ok=True)
            path.write_text(yaml.safe_dump(c,sort_keys=False),encoding="utf-8")
            status = "eligible_order"
            audit = load(HERE/"audits"/f"o{seed}.json")
            if arm in FACTORIAL and not all(v["eligible"] for v in audit["factorial"].values()):
                status="partial_factorial_match"
            elif arm=="placebo" and not audit["placebo"]["eligible"]:
                status="exploratory"
            elif arm in ("low_gap","high_gap") and not audit["spacing"]["eligible"]:
                status="exploratory"
            checkpoints=[]
            for step in CHECKPOINT_STEPS:
                model=f"{name.lower().replace('-','_')}_ck{step}"
                cells=[dict(**{k:v for k,v in cell.items() if k!="label"},
                            label=f"{model}_{cell['label'].split('_')[0]}_{i}")
                       for i,cell in enumerate(template)]
                checkpoints.append(dict(step=step,id=model,model=model,cells=cells))
            jobs.append(dict(id=name,arm=arm,order_seed=seed,training_seed=train_seed,
                             config=local(path),config_sha256=S.sha_file(path),order=order,
                             exposure_status=status,checkpoints=checkpoints))
    inputs={c["gold"] for c in template}|{c["chunk"] for c in template if c["chunk"]}
    for p in sorted(inputs):
        if S.sha_file(ROOT/p)!=eval_manifest["eval_input_sha256"][p]:
            raise ValueError(f"Development input hash changed: {p}")
    return dict(status="CPU_ONLY_PENDING_NEW_GPU_AUTHORIZATION", jobs=jobs,
                protocol_sha256=order_manifest["protocol_sha256"],
                order_manifest_sha256=S.sha_file(HERE/"orders/manifest.json"),
                evaluation=eval_manifest["evaluation"],
                eval_input_sha256={p:eval_manifest["eval_input_sha256"][p] for p in sorted(inputs)})


def validate_job(job, records, blocks):
    path=ROOT/job["config"]
    if S.sha_file(path)!=job["config_sha256"] or S.sha_file(ROOT/job["order"]["path"])!=job["order"]["sha256"]:
        raise ValueError("Run matrix config or order hash changed")
    c=config(path)
    data_policy(c)
    ref=config(source("B",1102))
    if diff_keys(c,ref)-CONFIG_KEYS:
        raise ValueError("Frozen training recipe changed")
    train=c["training"]
    if (job["order_seed"]!=train["semantic_schedule_seed"] or
        job["training_seed"]!=train["seed"] or job["training_seed"]!=train["data_seed"] or
        str(OUTPUT/job["id"])!=train["output_dir"] or job["order"]["path"]!=train["semantic_schedule_file"] or
        c["model"]["revision"]!=REV):
        raise ValueError("Run metadata differs from the training config")
    order=load(ROOT/job["order"]["path"])
    sequence=order["record_sequence"]
    block_order=order["block_order"]
    if (order["seed"]!=job["order_seed"] or order["treatment"]!=job["arm"] or
        order["training_sha256"]!=TRAIN_SHA or order["record_sequence_sha256"]!=S.sha_lines(sequence) or
        sorted(block_order)!=list(range(len(blocks))) or sequence!=[k for i in block_order for k in blocks[i].records]):
        raise ValueError("Order and block identities disagree")
    assert_block_sequence(block_order,blocks)
    check_seq(sequence,records,within=True)
    return c


def plan_locked():
    plan=load(PLAN)
    if (S.sha_file(HERE/"orders/manifest.json")!=plan["order_manifest_sha256"] or
        S.sha_file(HERE/"PREREGISTRATION.md")!=plan["protocol_sha256"]):
        raise ValueError("Frozen plan ancestry changed")
    order_manifest=load(HERE/"orders/manifest.json")
    for path,digest in order_manifest["audits"].items():
        if S.sha_file(ROOT/path)!=digest:
            raise ValueError(f"Exposure audit changed: {path}")
    return plan


def ensure_original_complete():
    followup = MAIN_RESULTS.parent
    pending = (
        followup/"gpu/execution/phase2_done.json",
        followup/"gpu/execution/matched_baselines/done.json",
        followup/"tables/device_matched/followup_analysis.json",
    )
    if any(not path.is_file() for path in pending):
        raise RuntimeError("The authorized E1/E2 queue, device-matched A/B and final analysis take priority")


def execute_train(job, mode, approval_path):
    if not mode and approval_path is None:
        raise ValueError("New task-specific GPU authorization is required")
    from launch import SPARE_GPU, WORKSTATION_GPUS, boundary, command, gpu_gate, shell
    import train_a11
    import train_semantic
    from train_b7b import SaveAt, save_points
    from training.trainer_common import cli
    from trl import SFTTrainer
    import numpy as np

    records,blocks,_,ledger_path=experiment()
    c=validate_job(job,records,blocks)
    if S.sha_file(ledger_path)!=load(HERE/"orders/manifest.json")["ledger_sha256"]:
        raise ValueError("Exact supervised-token ledger changed")
    if tuple(save_points(STEPS))!=CHECKPOINT_STEPS:
        raise ValueError("Checkpoint callback does not match the protocol")
    if not mode:
        ensure_original_complete()
        commit=command(["git","rev-parse","HEAD"])
        if ROOT==Path("/home/hwkim/assistant_univ") or shell(["git","symbolic-ref","-q","HEAD"]).returncode!=1 or command(["git","status","--porcelain"]):
            raise RuntimeError("Train from a clean detached worktree at the approved commit")
        approval=load(approval_path)
        if (approval["commit"]!=commit or approval["manifest_sha256"]!=S.sha_file(PLAN) or
            job["id"] not in approval["jobs"]):
            raise ValueError("Approval does not cover this commit, manifest and run")
        deadline=datetime.fromisoformat(approval["start_before"])
        if deadline.tzinfo is None:
            raise ValueError("GPU deadline requires timezone")
        boundary(deadline)
        if approval["gpu_uuid"] not in (*WORKSTATION_GPUS,SPARE_GPU):
            raise ValueError("GPU UUID is outside the workstation policy")
        if min(shutil.disk_usage(WORK).free,shutil.disk_usage(MAIN_RESULTS).free)/2**30 < 100:
            raise RuntimeError("Insufficient disk headroom for checkpoint or evaluation artifacts")
        import fcntl
        lock_path=WORK/"topic2_semantic_order/followup_conditions/provenance/run.lock"
        lock_path.parent.mkdir(parents=True,exist_ok=True)
        # Retain the descriptor for the full run. This also excludes the
        # existing follow-up launcher while any of its jobs are active.
        lock=lock_path.open("a")
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        exec_dir=MAIN_RESULTS/"execution"
        exec_dir.mkdir(exist_ok=True)
        index=gpu_gate(approval["gpu_uuid"],os.environ,exec_dir/"gpu_checks.jsonl")
        if os.environ.get("CUDA_VISIBLE_DEVICES")!=index or Path(c["training"]["output_dir"]).exists():
            raise RuntimeError("Expected only the approved physical GPU and a fresh run directory")
        if os.environ.get("PYTORCH_CUDA_ALLOC_CONF")!="expandable_segments:True":
            raise RuntimeError("Set the frozen training allocator configuration before starting")
    train_a11.install_override()
    args,c,splits,manifest=cli("sft",["--config",str(ROOT/job["config"]),*([mode] if mode else [])])
    train_semantic.apply_semantic_order(c,splits)
    sampler=SFTTrainer._get_train_sampler(type("CPUProbe",(),{"train_dataset":list(range(STEPS))})())
    if list(sampler)!=list(range(STEPS)) or type(sampler).__name__!="SequentialSampler":
        raise ValueError("Actual trainer sampler is not sequential")
    if manifest["prompt_hash"]!=PROMPT or not np.allclose(hf_rates(c),analytical_rates("linear"),rtol=0,atol=1e-18):
        raise ValueError("Prompt or optimizer step LR changed")
    print(f"{job['id']} records={len(splits['train'])}, sampler=SequentialSampler, steps={STEPS}, checkpoints={CHECKPOINT_STEPS}",flush=True)
    if mode:
        return
    from training.profiling import RunProfile
    from training.train_sft import train
    profile=RunProfile(c,"sft")
    error=None
    try:
        train(args,c,splits,manifest,profile,callbacks=[SaveAt()])
        checkpoint_hashes={}
        for step in CHECKPOINT_STEPS:
            weights=OUTPUT/job["id"]/f"checkpoint-{step}"/"adapter_model.safetensors"
            if not weights.is_file():
                raise ValueError(f"Missing checkpoint adapter for step {step}")
            checkpoint_hashes[str(step)]=S.sha_file(weights)
        dump(OUTPUT/job["id"]/"checkpoint_hashes.json",checkpoint_hashes)
    except BaseException as exc:
        error=exc
        raise
    finally:
        try:
            profile.finish(error)
            if error is None:
                write_training_receipt(job,c,commit,approval["gpu_uuid"],ledger_path,exec_dir)
        finally:
            lock.close()


def write_training_receipt(job, config, commit, uuid, ledger_path, exec_dir):
    import torch
    profile=load(config["profiling"]["output"])
    ledger=load(ledger_path)
    if (profile["status"]!="completed" or profile["optimizer_steps"]!=STEPS
        or profile["policy_tokens"]!=ledger["input_tokens"]):
        raise ValueError("Run profile does not validate optimizer steps and the token budget")
    dump(exec_dir/f"{job['id']}_training.json",
         dict(commit=commit,job=job["id"],complete=True,gpu_uuid=uuid,
              training_sha256=TRAIN_SHA,config_sha256=job["config_sha256"],order_sha256=job["order"]["sha256"],
              ledger_sha256=S.sha_file(ledger_path),checkpoint_steps=list(CHECKPOINT_STEPS),
              packages=profile["environment"],cuda=torch.version.cuda,
              optimizer_steps=profile["optimizer_steps"],policy_tokens=profile["policy_tokens"],
              loss_tokens=ledger["loss_tokens"],profile=profile))


def evaluate_checkpoints(job, approval_path):
    """Only evaluate after a completed training receipt and four verified adapters."""
    import fcntl
    from launch import DEFAULT_GPU, boundary, command, evaluate, shell
    if approval_path is None:
        raise ValueError("New task-specific GPU authorization is required")
    ensure_original_complete()
    plan=plan_locked()
    commit=command(["git","rev-parse","HEAD"])
    approval=load(approval_path)
    if (ROOT==Path("/home/hwkim/assistant_univ") or shell(["git","symbolic-ref","-q","HEAD"]).returncode!=1 or
        command(["git","status","--porcelain"]) or approval["commit"]!=commit or
        approval["manifest_sha256"]!=S.sha_file(PLAN) or job["id"] not in approval["jobs"]):
        raise ValueError("Evaluation requires the approved run in a clean detached worktree")
    deadline=datetime.fromisoformat(approval["start_before"])
    if deadline.tzinfo is None:
        raise ValueError("GPU deadline requires timezone")
    boundary(deadline)
    logdir=MAIN_RESULTS/"execution"
    receipt=load(logdir/f"{job['id']}_training.json")
    if (not receipt["complete"] or receipt["commit"]!=commit or receipt["gpu_uuid"]!=approval["gpu_uuid"] or
        receipt["config_sha256"]!=job["config_sha256"] or receipt["order_sha256"]!=job["order"]["sha256"]):
        raise ValueError("No corresponding completed training run on the approved device")
    for path,digest in plan["eval_input_sha256"].items():
        if S.sha_file(ROOT/path)!=digest:
            raise ValueError(f"Evaluation input changed: {path}")
    lock_path=WORK/"topic2_semantic_order/followup_conditions/provenance/run.lock"
    model_log=OUTPUT/job["id"]
    hashes=load(model_log/"checkpoint_hashes.json")
    for step in CHECKPOINT_STEPS:
        if hashes[str(step)]!=S.sha_file(model_log/f"checkpoint-{step}"/"adapter_model.safetensors"):
            raise ValueError(f"Checkpoint changed at step {step}")
    env={**os.environ,"OLLAMA_UUID":DEFAULT_GPU,
         "ALLOWED_UUIDS":approval["gpu_uuid"],"HF_HOME":str(WORK/"hf-cache"),
         "HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1","PYTHONDONTWRITEBYTECODE":"1"}
    sys.path.insert(0,str(ROOT/"sft_dpo_inventory/pilot_007/results"))
    with lock_path.open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for checkpoint in job["checkpoints"]:
            step=checkpoint["step"]
            evaluate(checkpoint,plan,env,logdir,model_log,deadline,approval["gpu_uuid"],commit,
                     MAIN_RESULTS,model_log/f"checkpoint-{step}",hashes[str(step)])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare",action="store_true")
    modes.add_argument("--validate",action="store_true")
    for name in ("dry-run","tokenizer-check","train","evaluate"):
        modes.add_argument("--"+name,metavar="RUN")
    parser.add_argument("--approval",type=Path)
    args=parser.parse_args()
    if args.prepare:
        dump(PLAN,matrix())
        return
    plan=plan_locked()
    if args.validate:
        records,blocks,_,_=experiment()
        for job in plan["jobs"]:
            validate_job(job,records,blocks)
        print(f"Validated {len(plan['jobs'])} run specifications and {len(plan['jobs'])*len(CHECKPOINT_STEPS)} checkpoint specifications")
        return
    name=args.dry_run or args.tokenizer_check or args.train or args.evaluate
    job=next(j for j in plan["jobs"] if j["id"]==name)
    mode="--dry-run" if args.dry_run else "--tokenizer-check" if args.tokenizer_check else None
    if args.evaluate:
        evaluate_checkpoints(job,args.approval)
    else:
        execute_train(job,mode,args.approval)


if __name__=="__main__":
    main()
