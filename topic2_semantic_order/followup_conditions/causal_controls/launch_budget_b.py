"""Run the approved Option B lanes and finish the CPU contrast analysis."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import fcntl
import os
from pathlib import Path
import socket

from budget_plan import manifest
from common import PY, ROOT, S, WORK, dump, load
from execution import HERE, MAIN_RESULTS, OUTPUT, authorized_scope, budget_paths, ensure_original_complete
from launch import MAIN, WORKSTATION_GPUS, append, boundary, command, logged, shell


def approved_lane(approval, commit, jobs):
    if approval["gpu_uuid"] not in WORKSTATION_GPUS:
        raise ValueError("Approval must identify a workstation4 GPU")
    slot = WORKSTATION_GPUS.index(approval["gpu_uuid"])
    lane = [j for j in jobs if j["gpu_slot"] == slot]
    if approval["jobs"] != [j["job"] for j in lane] or set(approval["actions"]) != {"train", "evaluate"}:
        raise ValueError("Approval must cover the entire fixed Option B lane")
    deadline = datetime.fromisoformat(approval["start_before"])
    if deadline.tzinfo is None:
        raise ValueError("Option B deadline requires a timezone")
    for job in lane:
        for action in ("train", "evaluate"):
            authorized_scope({"id":job["job"]}, approval, commit, "B", action)
    return lane, deadline


def verify_predecessors():
    ensure_original_complete()
    followup = MAIN_RESULTS.parent
    report = load(followup/"tables/device_matched/followup_analysis.json")
    arms = {"A", "B", "C", "D", "F0", "F48"}
    if not report["device_matched"] or any(set(report["status"][d]["all_five_seeds"]) != arms
                                          for d in ("CT10K", "H-dev")):
        raise ValueError("Original final analysis has incomplete treatment coverage")
    probe = load(followup/"gpu/execution/device_probe/comparison.json")
    if (any(probe["calls"].get(uuid) != 5 for uuid in WORKSTATION_GPUS) or
        set(probe["matches"]) != set(WORKSTATION_GPUS)):
        raise ValueError("The previous device-comparison gate is incomplete")


def cuda_index(uuid):
    return command(["nvidia-smi","-i",uuid,"--query-gpu=index","--format=csv,noheader,nounits"])


def run_lane(spec, approval_path, commit, logdir, training_dir):
    approval, jobs, deadline = spec
    uuid = approval["gpu_uuid"]
    env = {**os.environ, "HF_HOME":str(WORK/"hf-cache"), "HF_HUB_OFFLINE":"1",
           "TRANSFORMERS_OFFLINE":"1", "PYTHONDONTWRITEBYTECODE":"1",
           "TOKENIZERS_PARALLELISM":"false", "PYTORCH_CUDA_ALLOC_CONF":"expandable_segments:True",
           "FOLLOWUP_RUN_COMMIT":commit}
    for job in jobs:
        name = job["job"]
        for action in ("train", "evaluate"):
            if action == "train" and (training_dir/f"{name}_training.json").is_file():
                # The evaluation gate revalidates the receipt and adapter.
                continue
            boundary(deadline)
            env["CUDA_VISIBLE_DEVICES"] = cuda_index(uuid)
            log = logdir/f"budget_{action}_{name}.log"
            append(logdir/"queue_timeline.jsonl",dict(event="start",action=action,job=name,gpu_uuid=uuid,commit=commit))
            args = [PY,"-u",HERE/"execution.py","--budget-option","B",f"--{action}",name,"--approval",approval_path]
            rc = logged(args,env,log)
            append(logdir/"queue_timeline.jsonl",dict(event="finish",action=action,job=name,gpu_uuid=uuid,commit=commit,rc=rc))
            if rc:
                raise RuntimeError(f"{name} {action} failed. Review {log} before retrying.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", type=Path, nargs=3, required=True)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    commit = command(["git","rev-parse","HEAD"])
    plan, path = manifest("B")
    specs = []
    for source in args.approval:
        approval = load(source)
        lane, deadline = approved_lane(approval,commit,plan["jobs"])
        specs.append((approval,lane,deadline))
    if tuple(spec[0]["gpu_uuid"] for spec in specs) != WORKSTATION_GPUS:
        parser.error("Supply each approved physical GPU once, in manifest order")
    print(f"Option B {commit} {S.sha_file(path)} lanes {[len(s[1]) for s in specs]}",flush=True)
    if args.preview:
        return
    if (ROOT == MAIN or socket.gethostname().split(".")[0] != "workstation4" or
        shell(["git","symbolic-ref","-q","HEAD"]).returncode != 1 or command(["git","status","--porcelain"])):
        raise RuntimeError("Use the clean, approved detached worktree on workstation4")
    verify_predecessors()
    training_dir, out = budget_paths("B")
    logdir = out/"execution"
    logdir.mkdir(parents=True,exist_ok=True)
    training_dir.mkdir(parents=True,exist_ok=True)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    lock = OUTPUT.parent/"budget_b_queue.lock"
    with lock.open("a") as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(run_lane,spec,source,commit,logdir,training_dir)
                       for spec,source in zip(specs,args.approval,strict=True)]
            for future in futures:
                future.result()
        report_dir = out/"analysis"
        report = report_dir/"contrast.json"
        if not report.is_file():
            analysis_code = [PY,"-u",HERE/"analyze_budget.py","B","--out-dir",report_dir]
            env = {**os.environ,"CUDA_VISIBLE_DEVICES":"","OPENBLAS_NUM_THREADS":"1","PYTHONDONTWRITEBYTECODE":"1"}
            if logged(analysis_code,env,logdir/"analysis.log"):
                raise RuntimeError("Option B CPU analysis failed")
        result = load(report)
        if result["observed_runs"] != len(plan["jobs"]) or result["result"]["status"] == "INCOMPLETE":
            raise RuntimeError("Option B has incomparable or missing paired results. See the CPU report.")
        dump(logdir/"done.json",dict(commit=commit,manifest_sha256=S.sha_file(path),contrast_sha256=S.sha_file(report),
                                    trained_and_evaluated=len(plan["jobs"]),completed=datetime.now().astimezone().isoformat()))


if __name__=="__main__":
    main()
