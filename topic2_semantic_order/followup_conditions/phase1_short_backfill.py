"""Continue approved same-device E1 cells in the last Phase 1 idle window."""
import argparse
from datetime import datetime, timedelta
import os
import sys

from device_baseline_queue import (BASELINES, DEFAULT_GPU, EXECUTION, INV, LEGACY, LEGACY_COMMIT,
                                   MANIFEST_PATH, MODEL_LOG, OUT, ROOT, S, START_BEFORE,
                                   TREATMENT_PATHS, WORK, WORKSTATION_GPUS, allocations,
                                   baseline_receipts, boundary, command, load, lock, pending,
                                   records, release_state, run_gpu)

SELECTION = {
    0: ("matched_a_o1102", ("aux_s3", "aux_s4")),
    1: ("matched_b_o211102", ("valid98_s3", "valid98_s4")),
}


def safe_window(jobs, slot):
    expected = allocations(jobs)
    _, completed = release_state(EXECUTION,jobs)
    gpu = WORKSTATION_GPUS[slot]
    if ((EXECUTION/"phase1_done.json").exists() or
        not set(expected[1][gpu]) <= completed[gpu]):
        raise RuntimeError("GPU has a current or imminent treatment reservation")
    verified = {r["cell"] for r in records(EXECUTION/"eval_provenance.jsonl")}
    active_lane = WORKSTATION_GPUS[2]
    remaining = [c for j in jobs[1] if j["id"] in expected[1][active_lane]
                 for c in j["cells"] if c["dataset"]=="CT10K" and f"{c['label']}_s{c['k']}" not in verified]
    if len(remaining)<2:
        raise RuntimeError("The remaining Phase 1 work no longer leaves a safe short window")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slot", type=int, choices=tuple(SELECTION))
    parser.add_argument("--job", help="A/B job ID on this Phase 1 GPU")
    parser.add_argument("--cells", nargs="+", help="Short E1 cell suffixes from the approved job")
    parser.add_argument("--start-minutes",type=int,choices=range(1,33),default=32)
    parser.add_argument("--preview",action="store_true")
    args = parser.parse_args()
    if (ROOT!=LEGACY or command(["git","rev-parse","HEAD"])!=LEGACY_COMMIT or command(["git","status","--porcelain"])):
        raise RuntimeError("Original pinned baseline evaluator is unavailable")
    from socket import gethostname
    if gethostname().split(".")[0]!="workstation4":
        raise RuntimeError("This lane reservation belongs to workstation4")
    manifest=load(MANIFEST_PATH)
    jobs={phase:load(path)["jobs"] for phase,path in TREATMENT_PATHS.items()}
    if bool(args.job)!=bool(args.cells):
        parser.error("Specify both --job and --cells")
    name,suffixes=(args.job,args.cells) if args.job else SELECTION[args.slot]
    gpu=WORKSTATION_GPUS[args.slot]
    phase1_seeds={j["order_seed"] for j in jobs[1] if j["id"] in allocations(jobs)[1][gpu]}
    job=next((j for j in manifest["jobs"] if j["id"]==name and j["gpu_uuid"]==gpu and
              j["seed"] in phase1_seeds),None)
    if job is None:
        raise ValueError("The selected baseline job does not belong to this Phase 1 GPU")
    selected={f"{name}_{suffix}" for suffix in suffixes}
    cells=[c for c in job["cells"] if c["dataset"]=="E1" and
           f"{c['label']}_s{c['k']}" in selected and not c["reuse"]]
    if len(cells)!=len(suffixes):
        raise RuntimeError("The chosen cells differ from the approved same-device manifest")
    for path in {c["gold"] for c in cells}:
        if S.sha_file(ROOT/path)!=manifest["eval_input_sha256"][path]:
            raise ValueError(f"Evaluation gold changed: {path}")
    with lock(f"baseline-device-{args.slot}.lock"):
        safe_window(jobs,args.slot)
        todo=pending([dict(job,cells=cells)],baseline_receipts(),OUT)
        print([f"{c['label']}_s{c['k']}" for j in todo for c in j["cells"]],flush=True)
        if args.preview or not todo:
            return
        cutoff=datetime.fromisoformat(START_BEFORE)
        deadline=min(cutoff,datetime.now(cutoff.tzinfo)+timedelta(minutes=args.start_minutes))
        boundary(deadline)
        sys.path.insert(0,str(INV/"pilot_007/results"))
        env={**os.environ,"HF_HOME":str(WORK/"hf-cache"),"HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1",
             "PYTHONDONTWRITEBYTECODE":"1","TOKENIZERS_PARALLELISM":"false",
             "PYTORCH_CUDA_ALLOC_CONF":"expandable_segments:True","OLLAMA_UUID":DEFAULT_GPU,
             "ALLOWED_UUIDS":WORKSTATION_GPUS[args.slot],"FOLLOWUP_RUN_COMMIT":LEGACY_COMMIT}
        run_gpu(todo,manifest,env,BASELINES,MODEL_LOG,deadline,OUT)


if __name__=="__main__":
    main()
