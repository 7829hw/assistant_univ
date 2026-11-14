"""Inventory completed work and build a non-executable queue for authorization."""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import json
import statistics
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

from schedules import HERE, ORDER_SEEDS, TRAIN_SEEDS
from common import ROOT, WORK, S, dump, load, local
from execution import PLAN, CHECKPOINT_STEPS, plan_locked
from taxonomy import write_csv


def json_lines(path):
    if not path.is_file():
        return []
    data = path.read_bytes()
    # The active launcher may have begun writing the next line.
    return [json.loads(line) for line in data.splitlines(keepends=True) if line.endswith(b"\n")]


def elapsed(r):
    return (datetime.fromisoformat(r["time"]) - datetime.fromisoformat(r["started"])).total_seconds()


def inventory():
    followup = HERE.parent
    g = followup/"gpu/execution"
    historical = WORK/"topic2_semantic_order/followup_conditions"
    manifests = [followup/f"gpu/jobs_phase{i}.json" for i in (1,2)]
    jobs = {j["id"]:j for m in manifests for j in load(m)["jobs"]}
    timeline = json_lines(g/"timeline.jsonl")
    trained = {r["job"] for r in timeline if r["stage"]=="train" and r.get("rc")==0}
    completed = {r["job"] for r in timeline if r["stage"]=="job_completed"}
    started = {r["job"]:r for r in timeline if r["stage"]=="job_started"}
    receipts = {r["cell"]:r for r in json_lines(g/"eval_provenance.jsonl")}
    cells_by_job = {job:{f"{c['label']}_s{c['k']}":c["dataset"] for c in j["cells"]} for job,j in jobs.items()}
    counts = Counter(cells_by_job[job][cell] for job in jobs for cell in cells_by_job[job] if cell in receipts)
    checkpoint_rows = []
    storage_samples = []
    for name in sorted(trained):
        receipt = historical/"provenance"/f"trained_{name}.json"
        if not receipt.is_file():
            continue
        root = Path(jobs[name]["checkpoint"]).parent
        for step in CHECKPOINT_STEPS:
            directory = root/f"checkpoint-{step}"
            available = (directory/"adapter_model.safetensors").is_file()
            size = sum(p.stat().st_size for p in directory.iterdir() if p.is_file()) if available else None
            checkpoint_rows.append(dict(run=name,step=step,available=available,bytes=size))
            if available:
                storage_samples.append(size)
    train_sec = [elapsed(r) for r in timeline if r["stage"]=="train" and r.get("rc")==0]
    times = defaultdict(list)
    for r in timeline:
        if r["stage"]=="eval" and r.get("rc")==0:
            times[cells_by_job[r["job"]][r["cell"]]].append(elapsed(r))
    receipt_snapshot = {}
    for p in (g/"phase1_done.json",g/"phase2_done.json",g/"matched_baselines/done.json"):
        receipt_snapshot[local(p)] = p.is_file()
    approval = load(historical/"provenance/approval_007d86ab.json")
    for phase,p in enumerate(manifests,1):
        if approval["manifest_sha256"][str(phase)]!=S.sha_file(p):
            raise ValueError(f"Original GPU approval hash mismatch: {p}")
    services = {}
    for name in ("topic2-followup-007d86ab.service","topic2-followup-baselines-215b2dd0.path",
                 "topic2-followup-analysis-215b2dd0.path"):
        result = subprocess.run(["systemctl","--user","show",name,"-p","ActiveState","-p","SubState","-p","ExecMainStatus"],
                                capture_output=True,text=True)
        services[name] = dict(line.split("=",1) for line in result.stdout.splitlines() if "=" in line)
    trajectory_status = [dict(job=j,arm=jobs[j]["arm"],stage="EVALUATED" if j in completed else "TRAINED" if j in trained
                              else "RUNNING" if j in started else "READY_FOR_GPU",
                              verified_cells=len(set(cells_by_job[j]) & set(receipts)),
                              assigned_gpu=started.get(j,{}).get("gpu_uuid")) for j in jobs]
    historical_checkpoint_sizes = [r["bytes"] for r in checkpoint_rows if r["available"] and r["step"]==1984]
    snapshot = dict(snapshot_kst=datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
        branch=subprocess.check_output(["git","branch","--show-current"],cwd=ROOT,text=True).strip(),
        source_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        original_authority=dict(commit=approval["commit"],gpu_uuids=approval["gpu_uuids"],start_before=approval["start_before"],
                                manifest_sha256=approval["manifest_sha256"],scope="original E1/E2 and their queued A/B device match"),
        services=services,phase_receipts=receipt_snapshot,train_completed=len(trained),jobs_evaluated=len(completed),
        receipt_counts=dict(counts),treatment_jobs=trajectory_status,
        rerun_count=len(json_lines(g/"reruns.jsonl")),
        worker_failures=sum(r["stage"]=="worker_error" or r.get("rc",0)!=0 for r in timeline),
        matched_baseline_cells_verified=len({r["cell"] for r in json_lines(g/"matched_baselines/eval_provenance.jsonl")}),
        checkpoint_count=sum(r["available"] for r in checkpoint_rows))
    perf = dict(train_h=statistics.median(train_sec)/3600,
                eval_h={k:statistics.median(v)/3600 for k,v in times.items()},
                checkpoint_gib=statistics.median(storage_samples)/2**30,
                final_bundle_gib=statistics.median(historical_checkpoint_sizes)/2**30)
    return snapshot, checkpoint_rows, perf


def queue(perf):
    plan = plan_locked()
    jobs = {j["id"]:j for j in plan["jobs"]}
    expected = {
        "E5": {"S0T0", "S1T0", "S0T1", "S1T1"},
        "E6": {"S0T0", "S1T0", "placebo"},
        "E7": {"low_gap", "high_gap"},
    }
    cost = lambda n,repeat:dict(runs=n,checkpoints=n*4,evaluation_cells=n*24,
        gpu_hours=round(n*(perf["train_h"]+4*(5*perf["eval_h"]["CT10K"]+perf["eval_h"]["H-dev"])*repeat),1),
        checkpoint_and_final_bundle_gib=round(n*(4*perf["checkpoint_gib"]+perf["final_bundle_gib"]),1))
    assigned_once=set()
    waves={}
    for experiment,arms in expected.items():
        members=sorted((j for j in jobs.values() if j["arm"] in arms),key=lambda j:(
            ORDER_SEEDS.index(j["order_seed"]),TRAIN_SEEDS.index(j["training_seed"]),j["arm"]))
        fresh=[j["id"] for j in members if j["id"] not in assigned_once]
        dependencies=[j["id"] for j in members if j["id"] in assigned_once]
        assigned_once.update(fresh)
        waves[experiment] = dict(status="BLOCKED",role="exploratory factorial" if experiment=="E5" else "registered contrasts",
            jobs=fresh,reuse=dependencies,estimate=cost(len(fresh),1),estimate_with_one_retry_per_cell=cost(len(fresh),2))
    matching_first = [j["id"] for j in jobs.values() if j["arm"] in
                      ("S0T0", "S1T0", "placebo", "low_gap", "high_gap")]
    return dict(status="BLOCKED_NEW_GPU_AUTHORIZATION", existing_first=[
                "E1/E2 phase 1","E1/E2 phase 2","110 same-GPU A/B evaluation cells","original final analysis"],
                proposed_priority=waves,
                matching_first_option=dict(jobs=matching_first,estimate=cost(len(matching_first),1),
                                           estimate_with_one_retry_per_cell=cost(len(matching_first),2)),
                run_plan_sha256=S.sha_file(PLAN),
                original_control_protocol_sha256=plan["protocol_sha256"],
                amendment_sha256=S.sha_file(HERE/"PREREGISTRATION_AMENDMENT.md"),
                authority_fields=["commit","manifest_sha256","jobs","gpu_uuid","start_before"],
                authorized_new_jobs=[], validated_order_seeds=list(ORDER_SEEDS),training_seeds=list(TRAIN_SEEDS),
                planning_inputs=perf,total=cost(len(jobs),1),total_one_retry_per_cell=cost(len(jobs),2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir",type=Path,required=True)
    args=parser.parse_args()
    if args.out_dir.exists():
        parser.error("Use a fresh audit directory")
    snapshot,points,perf=inventory()
    dump(args.out_dir/"status.json",snapshot)
    dump(args.out_dir/"queue.json",queue(perf))
    write_csv(args.out_dir/"original_checkpoint_inventory.csv",points)
    print(snapshot["snapshot_kst"], "trained",snapshot["train_completed"],"evaluated",snapshot["jobs_evaluated"],
          "verified counts",snapshot["receipt_counts"],"available checkpoints",snapshot["checkpoint_count"])


if __name__=="__main__":
    main()
