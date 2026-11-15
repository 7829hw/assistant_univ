"""Dispatch approved A/B cells into idle windows without changing the evaluator."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
import fcntl
import os
from pathlib import Path
import socket
import sys

LEGACY = Path("/data/hwkim/sftdpo_work/worktrees/wt_followup_215b2dd0")
LEGACY_COMMIT = "215b2dd0f6721c4067d2af4946b034738e5f7144"
START_BEFORE = "2026-11-20T07:04:14+09:00"
RELATIVE = Path("topic2_semantic_order/followup_conditions")
sys.path.insert(0, str(LEGACY/RELATIVE))

from common import HERE, INV, ROOT, S, WORK, config, dump, load, source
from launch import MAIN, DEFAULT_GPU, WORKSTATION_GPUS, boundary, command, evaluate


def records(path):
    if not path.is_file():
        return []
    return [json.loads(raw) for raw in path.read_bytes().splitlines(keepends=True) if raw.endswith(b"\n")]


def pending(jobs, receipts, out):
    result = []
    for job in jobs:
        cells = []
        for cell in job["cells"]:
            if cell["reuse"]:
                continue
            name = f"{cell['label']}_s{cell['k']}"
            receipt = receipts.get(name)
            if not receipt:
                cells.append(cell)
                continue
            path = out/"cells"/f"{name}.json"
            if (receipt["commit"]!=LEGACY_COMMIT or receipt["gpu_uuid"]!=job["gpu_uuid"] or
                S.sha_file(path)!=receipt["sha256"] or not receipt["raw_sha256_match"]):
                raise ValueError(f"Prior baseline receipt mismatch: {name}")
        if cells:
            result.append(dict(job,cells=cells))
    return result


def select(stage, manifest, execution):
    lane1, lane2 = WORKSTATION_GPUS[1:]
    if stage in ("idle1","idle1-e1"):
        phase1=load(HERE/"gpu/jobs_phase1.json")["jobs"]
        completed={e["job"] for e in records(execution/"timeline.jsonl") if e["stage"]=="job_completed"}
        assigned=load(execution/"phase1_assignment.json")["jobs_by_gpu"]
        if (execution/"phase1_done.json").exists() or completed.issuperset(j["id"] for j in phase1) or not completed.issuperset(assigned[lane1]):
            raise RuntimeError("Current GPU 1 idle window has closed or is unverified")
        verified = {r["cell"] for r in records(execution/"eval_provenance.jsonl")}
        pending_ct10k = sum(f"{c['label']}_s{c['k']}" not in verified for j in phase1 for c in j["cells"]
                           if j["order_seed"]==1102 and c["dataset"]=="CT10K")
        if pending_ct10k < (5 if stage=="idle1-e1" else 4):
            raise RuntimeError("GPU 1 backfill is too close to the Phase 2 handoff")
        job=next(j for j in manifest["jobs"] if j["id"]=="matched_b_o211102" and j["gpu_uuid"]==lane1)
        cells=[c for c in job["cells"] if c["dataset"]=="E1" and
               (stage=="idle1-e1" or c["label"].endswith("_aux"))]
        return [dict(job,cells=cells)]
    if stage=="idle2":
        if not (execution/"phase1_done.json").is_file():
            raise RuntimeError("GPU 2 still belongs to Phase 1")
        phase2=load(HERE/"gpu/jobs_phase2.json")["jobs"]
        from common import SEEDS
        if any(WORKSTATION_GPUS[SEEDS.index(j["order_seed"])%3]==lane2 for j in phase2):
            raise RuntimeError("GPU 2 has a treatment reservation")
        return [j for j in manifest["jobs"] if j["gpu_uuid"]==lane2]
    if not (execution/"phase2_done.json").is_file():
        raise RuntimeError("Finish the registered treatment phases first")
    assigned={}
    for phase in (1,2):
        allocation=load(execution/f"phase{phase}_assignment.json")["jobs_by_gpu"]
        assigned.update({int(name.split("-o")[1]):uuid for uuid,jobs in allocation.items() for name in jobs})
    if any(assigned[j["seed"]]!=j["gpu_uuid"] for j in manifest["jobs"]):
        raise RuntimeError("Baseline evaluation assignment differs from the treatment study")
    return manifest["jobs"]


def adapter(job):
    model = config(source(job["arm"],job["seed"]))["training"]["output_dir"]
    checkpoint = Path(model)/"checkpoint-1984"
    digest = S.sha_file(checkpoint/"adapter_model.safetensors")
    original = load(ROOT/job["cells"][0]["prior"])["meta"]["vllm"]["server_meta"]
    if digest!=original["adapter_sha256"]:
        raise RuntimeError(f"Historical adapter hash mismatch for {job['id']}")
    return checkpoint,digest


def run_gpu(jobs,manifest,env,logdir,model_log,deadline,out):
    for job in jobs:
        checkpoint,digest=adapter(job)
        evaluate(job,manifest,env,logdir,model_log,deadline,job["gpu_uuid"],LEGACY_COMMIT,out,checkpoint,digest)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("idle1","idle1-e1","idle2","complete"))
    parser.add_argument("--preview",action="store_true")
    args=parser.parse_args()
    if (ROOT!=LEGACY or socket.gethostname().split(".")[0]!="workstation4" or
        command(["git","rev-parse","HEAD"])!=LEGACY_COMMIT or command(["git","status","--porcelain"])):
        raise RuntimeError("The evaluator must come from the original clean, pinned baseline worktree")
    manifest_path=HERE/"gpu/device_matched_baselines.json"
    manifest=load(manifest_path)
    out=MAIN/RELATIVE
    execution=out/"gpu/execution"
    logdir=execution/"matched_baselines"
    if set(load(execution/"device_probe/comparison.json")["matches"])!=set(WORKSTATION_GPUS):
        raise RuntimeError("Missing serving comparison for an allocated GPU")
    for p,digest in manifest["eval_input_sha256"].items():
        if S.sha_file(ROOT/p)!=digest:
            raise RuntimeError(f"Evaluation input hash drift: {p}")
    approved=datetime.fromisoformat(START_BEFORE)
    # Bound the first group of cell starts to reserve GPU 1 for Phase 2.
    idle_minutes = {"idle1":45,"idle1-e1":90}.get(args.stage)
    deadline = approved
    if idle_minutes:
        deadline = min(approved,datetime.now(approved.tzinfo)+timedelta(minutes=idle_minutes))
    boundary(deadline)
    jobs=select(args.stage,manifest,execution)
    receipts={r["cell"]:r for r in records(logdir/"eval_provenance.jsonl")}
    jobs=pending(jobs,receipts,out)
    print(args.stage,[(j["id"],len(j["cells"])) for j in jobs],flush=True)
    if args.preview:
        for job in jobs:
            adapter(job)
        return
    sys.path.insert(0,str(INV/"pilot_007/results"))
    logdir.mkdir(parents=True,exist_ok=True)
    model_log=WORK/"topic2_semantic_order/followup_conditions/provenance"
    env={**os.environ,"HF_HOME":str(WORK/"hf-cache"),"HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1",
         "PYTHONDONTWRITEBYTECODE":"1","TOKENIZERS_PARALLELISM":"false","PYTORCH_CUDA_ALLOC_CONF":"expandable_segments:True",
         "OLLAMA_UUID":DEFAULT_GPU,"ALLOWED_UUIDS":" ".join(WORKSTATION_GPUS),"FOLLOWUP_RUN_COMMIT":LEGACY_COMMIT}
    # Early lanes occupy GPUs already released by the active pinned treatment launcher.
    # Final dispatch uses the legacy global exclusion lock after its treatment barrier.
    lock_name="run.lock" if args.stage=="complete" else f"baseline-{args.stage.split('-')[0]}.lock"
    with (model_log/lock_name).open("a") as lock, ThreadPoolExecutor(max_workers=3) as pool:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        futures=[pool.submit(run_gpu,[j for j in jobs if j["gpu_uuid"]==uuid],manifest,env,logdir,model_log,
                             deadline,out) for uuid in WORKSTATION_GPUS]
        for future in futures:
            future.result()
        if args.stage=="complete":
            receipts={r["cell"]:r for r in records(logdir/"eval_provenance.jsonl")}
            if pending(manifest["jobs"],receipts,out):
                raise ValueError("A/B reevaluation is incomplete")
            dump(logdir/"done.json",dict(commit=LEGACY_COMMIT,manifest_sha256=S.sha_file(manifest_path)))


if __name__=="__main__":
    main()
