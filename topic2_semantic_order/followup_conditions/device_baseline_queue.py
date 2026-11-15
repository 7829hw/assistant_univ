"""Release same-device A/B lanes from validated original treatment receipts."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta
import fcntl
import json
import os
from pathlib import Path
import socket
import sys
from tempfile import NamedTemporaryFile

from backfill_baselines import (HERE, INV, LEGACY, LEGACY_COMMIT, MAIN, RELATIVE, ROOT, S, START_BEFORE,
                                WORK, WORKSTATION_GPUS, boundary, command, dump, load, pending, records, run_gpu)
from common import SEEDS
from launch import DEFAULT_GPU

TREATMENT_COMMIT = "007d86ab80705453880b0958a0b2d6812811510f"
MANIFEST_PATH = HERE/"gpu/device_matched_baselines.json"
TREATMENT_PATHS = {p: HERE/f"gpu/jobs_phase{p}.json" for p in (1, 2)}
OUT = MAIN/RELATIVE
EXECUTION = OUT/"gpu/execution"
BASELINES = EXECUTION/"matched_baselines"
QUEUE = BASELINES/"device_queue"
MODEL_LOG = WORK/"topic2_semantic_order/followup_conditions/provenance"
SHORT_CELLS = {f"matched_b_o211102_{ds}_s{k}" for ds in ("rdevv2","valid98","aux") for k in range(1,5)}


def atomic_receipt(path, data):
    with NamedTemporaryFile(dir=path.parent, prefix=".receipt-", delete=False) as handle:
        tmp = Path(handle.name)
    try:
        dump(tmp,data)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


@contextmanager
def lock(name):
    with (MODEL_LOG/name).open("a") as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        yield


def allocations(jobs):
    return {phase:{uuid:[j["id"] for j in jobs[phase]
                         if WORKSTATION_GPUS[SEEDS.index(j["order_seed"])%3]==uuid]
                   for uuid in WORKSTATION_GPUS} for phase in (1,2)}


def release_state(execution, jobs):
    expected = allocations(jobs)
    allocations_ok = {}
    for phase in (1,2):
        path = execution/f"phase{phase}_assignment.json"
        if not path.is_file():
            allocations_ok[phase] = False
            continue
        try:
            actual = load(path)
        except json.JSONDecodeError:
            # The existing launcher writes assignments in place.
            allocations_ok[phase] = False
            continue
        if actual["commit"]!=TREATMENT_COMMIT or actual["jobs_by_gpu"]!=expected[phase]:
            raise ValueError(f"Published Phase {phase} assignment differs from the frozen queue")
        allocations_ok[phase] = True
    events = records(execution/"timeline.jsonl")
    completed = {uuid:set() for uuid in WORKSTATION_GPUS}
    for event in events:
        if event["stage"]=="job_completed" and event["commit"]==TREATMENT_COMMIT:
            completed[event["gpu_uuid"]].add(event["job"])
    released = []
    for slot, uuid in enumerate(WORKSTATION_GPUS):
        required = set(expected[1][uuid]+expected[2][uuid])
        if (allocations_ok[1] and (allocations_ok[2] or not expected[2][uuid])
            and required <= completed[uuid]):
            released.append(slot)
    return released, completed


def short_window(execution, phase1_jobs, completed, receipts):
    if ((execution/"phase1_done.json").exists() or
        not set(allocations({1:phase1_jobs,2:[]})[1][WORKSTATION_GPUS[1]]) <= completed[WORKSTATION_GPUS[1]] or
        not SHORT_CELLS <= set(receipts)):
        return False
    validated = {r["cell"] for r in records(execution/"eval_provenance.jsonl")}
    for seed in (1102,2026113):
        remaining = sum(f"{c['label']}_s{c['k']}" not in validated
                        for j in phase1_jobs if j["order_seed"]==seed
                        for c in j["cells"] if c["dataset"]=="CT10K")
        if remaining >= 5:
            return True
    return False


def lane_jobs(manifest, slot, short=False):
    jobs = [j for j in manifest["jobs"] if j["gpu_uuid"]==WORKSTATION_GPUS[slot]]
    if not short:
        return jobs
    return [dict(j,cells=[c for c in j["cells"] if c["dataset"]=="H-dev"])
            for j in jobs if j["id"]=="matched_b_o211102"]


def baseline_receipts():
    result = {}
    for row in records(BASELINES/"eval_provenance.jsonl"):
        previous = result.setdefault(row["cell"],row)
        if any(previous[k]!=row[k] for k in ("sha256","gpu_uuid","commit")):
            raise ValueError(f"Conflicting completed receipts for {row['cell']}")
    return result


def maybe_finalize(manifest):
    if not (EXECUTION/"phase2_done.json").is_file() or not all((QUEUE/f"lane{i}.done").is_file() for i in range(3)):
        return
    with lock("baseline-device-finalize.lock"):
        if (BASELINES/"done.json").is_file():
            return
        if load(EXECUTION/"phase2_done.json")["commit"]!=TREATMENT_COMMIT:
            raise ValueError("Phase 2 completion provenance differs")
        if pending(manifest["jobs"],baseline_receipts(),OUT):
            raise ValueError("A/B reevaluation is incomplete")
        atomic_receipt(BASELINES/"done.json",dict(commit=LEGACY_COMMIT,manifest_sha256=S.sha_file(MANIFEST_PATH)))


def dispatch(manifest,jobs,released,completed,preview):
    candidates = [f"lane{i}" for i in released]
    if short_window(EXECUTION,jobs[1],completed,baseline_receipts()):
        candidates.append("short1")
    if preview:
        print(dict(released=released,eligible=candidates,
                   pending={name:sum(len(j["cells"]) for j in pending(lane_jobs(manifest,i),baseline_receipts(),OUT))
                            for i,name in enumerate(("lane0","lane1","lane2"))}),flush=True)
        return
    with lock("baseline-device-dispatch.lock"):
        for name in candidates:
            if not (QUEUE/f"{name}.ready").exists():
                atomic_receipt(QUEUE/f"{name}.ready",dict(manifest_sha256=S.sha_file(MANIFEST_PATH),stage=name))
                print(f"Released {name}",flush=True)
    maybe_finalize(manifest)


def evaluate_lane(stage,manifest,jobs,approved):
    short = stage=="short1"
    slot = 1 if short else int(stage[-1])
    with lock(f"baseline-device-{slot}.lock"):
        done = QUEUE/f"{stage}.done"
        if done.is_file() or (BASELINES/"done.json").is_file():
            return
        marker = load(QUEUE/f"{stage}.ready")
        if marker!=dict(manifest_sha256=S.sha_file(MANIFEST_PATH),stage=stage):
            raise ValueError("Invalid ready receipt")
        released, completed = release_state(EXECUTION,jobs)
        saved = baseline_receipts()
        if short and not short_window(EXECUTION,jobs[1],completed,saved):
            atomic_receipt(done,dict(stage=stage,status="window_closed"))
            return
        if not short and slot not in released:
            raise RuntimeError("Treatment lane has not released its GPU")
        todo = pending(lane_jobs(manifest,slot,short),saved,OUT)
        deadline = min(approved,datetime.now(approved.tzinfo)+timedelta(minutes=75)) if short else approved
        if todo:
            boundary(deadline)
            sys.path.insert(0,str(INV/"pilot_007/results"))
            env={**os.environ,"HF_HOME":str(WORK/"hf-cache"),"HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1",
                 "PYTHONDONTWRITEBYTECODE":"1","TOKENIZERS_PARALLELISM":"false",
                 "PYTORCH_CUDA_ALLOC_CONF":"expandable_segments:True","OLLAMA_UUID":DEFAULT_GPU,
                 "ALLOWED_UUIDS":WORKSTATION_GPUS[slot],"FOLLOWUP_RUN_COMMIT":LEGACY_COMMIT}
            run_gpu(todo,manifest,env,BASELINES,MODEL_LOG,deadline,OUT)
        if pending(lane_jobs(manifest,slot,short),baseline_receipts(),OUT):
            raise ValueError("Lane has missing evaluation receipts")
        atomic_receipt(done,dict(stage=stage,status="complete",evaluated=sum(len(j["cells"]) for j in todo)))
    maybe_finalize(manifest)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("dispatch","short1","lane0","lane1","lane2"))
    parser.add_argument("--preview",action="store_true")
    args=parser.parse_args()
    if (ROOT!=LEGACY or socket.gethostname().split(".")[0]!="workstation4" or
        command(["git","rev-parse","HEAD"])!=LEGACY_COMMIT or command(["git","status","--porcelain"])):
        raise RuntimeError("The evaluator must come from the clean pinned baseline worktree")
    manifest = load(MANIFEST_PATH)
    jobs = {phase:load(path)["jobs"] for phase,path in TREATMENT_PATHS.items()}
    if not args.preview and (BASELINES/"done.json").is_file():
        return
    approved = datetime.fromisoformat(START_BEFORE)
    if args.stage=="dispatch":
        released, completed = release_state(EXECUTION,jobs)
        if args.preview:
            dispatch(manifest,jobs,released,completed,True)
            return
        QUEUE.mkdir(parents=True,exist_ok=True)
        dispatch(manifest,jobs,released,completed,False)
        return
    if args.preview:
        parser.error("Use dispatch for the read-only preview")
    for path,digest in manifest["eval_input_sha256"].items():
        if S.sha_file(ROOT/path)!=digest:
            raise ValueError(f"Evaluation inputs changed: {path}")
    probe=load(EXECUTION/"device_probe/comparison.json")
    if set(probe["matches"])!=set(WORKSTATION_GPUS):
        raise ValueError("Device comparison is incomplete")
    evaluate_lane(args.stage,manifest,jobs,approved)


if __name__=="__main__":
    main()
