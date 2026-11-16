"""Start only the released GPU 2 Option B lane using the pinned experiment."""
import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import sys

SCRIPT = Path(__file__).resolve()
PIN = Path("/data/hwkim/sftdpo_work/worktrees/wt_followup_budget_b_decbc87a")
PIN_COMMIT = "decbc87a138fd2100bfdd1d41cb4b755f7feee2a"
TREATMENT_COMMIT = "007d86ab80705453880b0958a0b2d6812811510f"
BASELINE_COMMIT = "215b2dd0f6721c4067d2af4946b034738e5f7144"
REL = Path("topic2_semantic_order/followup_conditions/causal_controls")
sys.path.insert(0,str(PIN/REL))

import execution
import launch_budget_b as pinned
from common import PY, ROOT, S, WORK, load
from integration import json_lines
from launch import WORKSTATION_GPUS, append, boundary, command, logged

GPU2 = WORKSTATION_GPUS[2]
MODEL_PROVENANCE = WORK/"topic2_semantic_order/followup_conditions/provenance"
LANE_LOCK = execution.OUTPUT.parent/"budget_b_gpu2_lane.lock"
PIN_APPROVALS = MODEL_PROVENANCE/"budget_b_decbc87a"


@contextmanager
def mutex(path, *, wait=True):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a") as handle:
        fcntl.flock(handle,fcntl.LOCK_EX if wait else fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def approved_gpu2(path):
    if path.resolve()!=(PIN_APPROVALS/"lane2.json").resolve():
        raise ValueError("Use the existing task-specific GPU 2 authorization")
    plan,_ = pinned.manifest("B")
    approval=load(path)
    jobs, deadline=pinned.approved_lane(approval,PIN_COMMIT,plan["jobs"])
    if approval["gpu_uuid"]!=GPU2 or len(jobs)!=8:
        raise ValueError("Early start covers only the eight previously assigned GPU 2 jobs")
    return approval,jobs,deadline


def verify_release():
    followup=execution.MAIN_RESULTS.parent
    source=followup/"gpu/execution"
    for phase in ("phase1_done.json","phase2_assignment.json"):
        receipt=load(source/phase)
        if receipt["commit"]!=TREATMENT_COMMIT:
            raise ValueError("Original treatment execution commit differs")
    if load(source/"phase2_assignment.json")["jobs_by_gpu"][GPU2]:
        raise ValueError("GPU 2 has an original Phase 2 reservation")
    probe=load(source/"device_probe/comparison.json")
    if any(probe["calls"].get(uuid)!=5 for uuid in WORKSTATION_GPUS):
        raise ValueError("The original device check is incomplete")
    baseline=source/"matched_baselines"
    if load(baseline/"device_queue/lane2.done")["status"]!="complete":
        raise ValueError("GPU 2 A/B lane has not completed")
    plan=load(followup/"gpu/device_matched_baselines.json")
    names={f"{c['label']}_s{c['k']}" for j in plan["jobs"] if j["gpu_uuid"]==GPU2
           for c in j["cells"] if not c["reuse"]}
    receipts={r["cell"]:r for r in json_lines(baseline/"eval_provenance.jsonl") if r["gpu_uuid"]==GPU2}
    if len(names)!=34 or set(receipts)!=names:
        raise ValueError("Not all original GPU 2 A/B cells are verified")
    for name,r in receipts.items():
        if (r["commit"]!=BASELINE_COMMIT or not r["raw_sha256_match"] or
            S.sha_file(followup/"cells"/f"{name}.json")!=r["sha256"]):
            raise ValueError(f"Baseline receipt changed: {name}")


def early_locks(budget, uuid):
    if budget!="B" or uuid!=GPU2:
        raise ValueError("The early execution lock is limited to Option B on GPU 2")
    return mutex(MODEL_PROVENANCE/f"budget-{uuid}.lock",wait=False)


def run_child(approval, action, job):
    _,jobs,deadline=approved_gpu2(approval)
    boundary(deadline)
    if job not in {j["job"] for j in jobs}:
        raise ValueError("Early start does not cover this job")
    # Narrow only the timing prerequisite and exclusion lock. Keep the pinned
    # trainer, evaluator, job scope, UUID guard and per-device lock in use.
    execution.ensure_original_complete=verify_release
    execution.gpu_locks=early_locks
    sys.argv=[str(PIN/REL/"execution.py"),"--budget-option","B",f"--{action}",job,"--approval",str(approval)]
    execution.main()


def all_verified(jobs, training_dir, out):
    receipts={r["cell"]:r for r in json_lines(out/"execution/eval_provenance.jsonl")}
    for job in jobs:
        p=training_dir/f"{job['job']}_training.json"
        if not p.is_file():
            return False
        train=load(p)
        if (not train["complete"] or train["commit"]!=PIN_COMMIT or train["gpu_uuid"]!=GPU2 or
            train["config_sha256"]!=job["config_sha256"] or train["order_sha256"]!=job["order"]["sha256"]):
            raise ValueError(f"Existing GPU 2 training receipt mismatch: {p}")
        for cell in job["checkpoint"]["cells"]:
            key=f"{cell['label']}_s{cell['k']}"
            r=receipts.get(key)
            if r is None:
                return False
            if (r["commit"]!=PIN_COMMIT or r["gpu_uuid"]!=GPU2 or
                S.sha_file(out/"cells"/f"{key}.json")!=r["sha256"]):
                raise ValueError(f"Existing GPU 2 evaluation receipt mismatch: {key}")
    return True


def run_early(path, preview):
    approval,jobs,deadline=approved_gpu2(path)
    verify_release()
    print("Approved early GPU 2 jobs:",[j["job"] for j in jobs],flush=True)
    if preview:
        return
    boundary(deadline)
    training_dir,out=execution.budget_paths("B")
    logdir=out/"execution"
    logdir.mkdir(parents=True,exist_ok=True)
    training_dir.mkdir(parents=True,exist_ok=True)
    env={**os.environ,"HF_HOME":str(WORK/"hf-cache"),"HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1",
         "PYTHONDONTWRITEBYTECODE":"1","TOKENIZERS_PARALLELISM":"false",
         "PYTORCH_CUDA_ALLOC_CONF":"expandable_segments:True","FOLLOWUP_RUN_COMMIT":PIN_COMMIT}
    with mutex(LANE_LOCK):
        for job in jobs:
            name=job["job"]
            if all_verified([job],training_dir,out):
                continue
            for action in ("train","evaluate"):
                if action=="train" and (training_dir/f"{name}_training.json").is_file():
                    continue
                boundary(deadline)
                env["CUDA_VISIBLE_DEVICES"]=pinned.cuda_index(approval["gpu_uuid"])
                state=dict(action=action,job=name,gpu_uuid=GPU2,commit=PIN_COMMIT,early=True)
                append(logdir/"queue_timeline.jsonl",dict(event="start",**state))
                args=[PY,"-u",SCRIPT,"child","--approval",path,"--action",action,"--job",name]
                rc=logged(args,env,logdir/f"budget_{action}_{name}.log")
                append(logdir/"queue_timeline.jsonl",dict(event="finish",rc=rc,**state))
                if rc:
                    raise RuntimeError(f"GPU 2 {name} {action} failed")
        if not all_verified(jobs,training_dir,out):
            raise ValueError("The early GPU 2 lane has missing evaluation receipts")


def run_normal(approvals, preview):
    original_run=pinned.run_lane

    def coordinate_lane(spec,path,commit,logdir,training_dir):
        approval,jobs,_=spec
        if approval["gpu_uuid"]!=GPU2:
            return original_run(spec,path,commit,logdir,training_dir)
        with mutex(LANE_LOCK):
            _,out=execution.budget_paths("B")
            if not all_verified(jobs,training_dir,out):
                original_run(spec,path,commit,logdir,training_dir)

    pinned.run_lane=coordinate_lane
    sys.argv=[str(PIN/REL/"launch_budget_b.py"),"--approval",*map(str,approvals)]
    if preview:
        sys.argv.append("--preview")
    pinned.main()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("early","normal","child"))
    parser.add_argument("--approval",type=Path,nargs="+",required=True)
    parser.add_argument("--action",choices=("train","evaluate"))
    parser.add_argument("--job")
    parser.add_argument("--preview",action="store_true")
    args=parser.parse_args()
    if (ROOT!=PIN or command(["git","rev-parse","HEAD"])!=PIN_COMMIT or
        command(["git","status","--porcelain"])):
        raise RuntimeError("Use the original clean and pinned Option B execution worktree")
    if args.mode=="normal":
        if len(args.approval)!=3:
            parser.error("Supply all three original lane approvals in order")
        run_normal(args.approval,args.preview)
    elif len(args.approval)!=1:
        parser.error("Supply only the original GPU 2 approval")
    elif args.mode=="early":
        run_early(args.approval[0],args.preview)
    elif args.action and args.job and not args.preview:
        run_child(args.approval[0],args.action,args.job)
    else:
        parser.error("The GPU 2 worker requires a job and action")


if __name__=="__main__":
    main()
