"""Reuse historical A/B cells on the assigned GPU and evaluate only mismatched cells."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import fcntl
import os

from common import HERE, INV, REL, ROOT, S, SEEDS, WORK, config, dump, load, source
from launch import MAIN, DEFAULT_GPU, WORKSTATION_GPUS, boundary, command, evaluate, shell
from regression import A


def historical_cell_paths(arm, seed):
    tag = f"o{seed}"
    paths = {"H-dev": iter([A.hd_path(arm, tag)]), "CT10K": iter(A.ct_paths(arm, tag))}
    paths.update({gold: iter(cells) for name, cells in A.e1_cells(arm, tag).items()
                  for gold in (A.CORE.SETS[name],)})
    return paths


def eval_gpu(path):
    return load(path)["meta"]["vllm"]["server_meta"]["gpu_uuid"]


def make_plan():
    manifests = [load(HERE / f"gpu/jobs_phase{phase}.json") for phase in (1, 2)]
    templates = {j["order_seed"]: j["cells"] for m in manifests for j in m["jobs"] if j["arm"] == "C"}
    expected = load(HERE / "provenance/existing_evidence.json")["evaluations"]
    frozen_hashes = {p: h for group in expected.values() for p, h in group.items()}
    jobs = []
    for index, seed in enumerate(SEEDS):
        uuid = WORKSTATION_GPUS[index % len(WORKSTATION_GPUS)]
        for arm in ("A", "B"):
            paths = historical_cell_paths(arm, seed)
            name = f"matched_{arm.lower()}_o{seed}"
            cells = []
            for original in templates[seed]:
                ds = original["dataset"]
                path = next(paths[original["gold"] if ds == "E1" else ds])
                if S.sha_file(ROOT / path) != frozen_hashes[path]:
                    raise ValueError(f"Historical evaluation hash drift: {path}")
                prior_gpu = eval_gpu(ROOT / path)
                label = original["label"].replace(f"c_o{seed}", name)
                cells.append(dict(**{k:v for k,v in original.items() if k!="label"},label=label,
                                  prior=path,prior_sha256=frozen_hashes[path],prior_gpu=prior_gpu,
                                  reuse=prior_gpu==uuid))
            jobs.append(dict(id=name,model=name,arm=arm,seed=seed,gpu_uuid=uuid,cells=cells))
    return dict(evaluation=manifests[0]["evaluation"],eval_input_sha256=manifests[0]["eval_input_sha256"],jobs=jobs)


def run_gpu(jobs,manifest,env,logdir,model_log,deadline,commit,out):
    for job in jobs:
        selected = [cell for cell in job["cells"] if not cell["reuse"]]
        if not selected:
            continue
        checkpoint = Path(config(source(job["arm"],job["seed"]))["training"]["output_dir"]) / "checkpoint-1984"
        adapter_sha = S.sha_file(checkpoint/"adapter_model.safetensors")
        old = load(ROOT/selected[0]["prior"])["meta"]["vllm"]["server_meta"]
        if adapter_sha!=old["adapter_sha256"]:
            raise RuntimeError(f"Historical adapter hash mismatch for {job['id']}")
        evaluate(dict(job,cells=selected),manifest,env,logdir,model_log,deadline,
                 job["gpu_uuid"],commit,out,checkpoint,adapter_sha)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-plan",action="store_true")
    parser.add_argument("--run",action="store_true")
    parser.add_argument("--start-before",type=datetime.fromisoformat)
    args = parser.parse_args()
    planpath = HERE/"gpu/device_matched_baselines.json"
    if args.write_plan:
        dump(planpath,make_plan())
    manifest=load(planpath)
    summary=Counter((j["gpu_uuid"],c["dataset"],c["reuse"]) for j in manifest["jobs"] for c in j["cells"])
    for key,n in sorted(summary.items()):
        print(*key,n,flush=True)
    if not args.run:
        return
    if args.start_before is None or args.start_before.tzinfo is None:
        parser.error("--run needs --start-before with a timezone")
    boundary(args.start_before)
    commit=command(["git","rev-parse","HEAD"])
    if ROOT==MAIN or shell(["git","symbolic-ref","-q","HEAD"]).returncode!=1 or command(["git","status","--porcelain"]):
        raise RuntimeError("Run from the clean detached worktree for this evaluation plan")
    out=MAIN/REL
    execution=out/"gpu/execution"
    logdir=execution/"matched_baselines"
    logdir.mkdir(parents=True,exist_ok=True)
    model_log=WORK/"topic2_semantic_order/followup_conditions/provenance"
    if not (execution/"phase2_done.json").is_file():
        raise RuntimeError("Finish the registered training and evaluation phases first")
    for path,digest in manifest["eval_input_sha256"].items():
        if S.sha_file(ROOT/path)!=digest:
            raise RuntimeError(f"Evaluation input hash drift: {path}")
    probe=load(execution/"device_probe/comparison.json")
    if set(probe["matches"])!=set(WORKSTATION_GPUS):
        raise RuntimeError("Missing comparison for an approved GPU")
    assigned={}
    for phase in (1,2):
        allocation=load(execution/f"phase{phase}_assignment.json")["jobs_by_gpu"]
        assigned.update({int(job.split("-o")[1]):uuid for uuid,jobs in allocation.items() for job in jobs})
    if any(assigned[j["seed"]]!=j["gpu_uuid"] for j in manifest["jobs"]):
        raise RuntimeError("Baseline evaluation assignment differs from the completed study")
    env={**os.environ,"HF_HOME":str(WORK/"hf-cache"),"HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1",
         "PYTHONDONTWRITEBYTECODE":"1","TOKENIZERS_PARALLELISM":"false","PYTORCH_CUDA_ALLOC_CONF":"expandable_segments:True",
         "OLLAMA_UUID":DEFAULT_GPU,"ALLOWED_UUIDS":" ".join(WORKSTATION_GPUS),"FOLLOWUP_RUN_COMMIT":commit}
    import sys
    sys.path.insert(0,str(INV/"pilot_007/results"))
    with (model_log/"run.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with ThreadPoolExecutor(max_workers=len(WORKSTATION_GPUS)) as pool:
            futures=[pool.submit(run_gpu,[j for j in manifest["jobs"] if j["gpu_uuid"]==uuid],
                                 manifest,env,logdir,model_log,args.start_before,commit,out) for uuid in WORKSTATION_GPUS]
            for future in futures:
                future.result()
        dump(logdir/"done.json",dict(commit=commit,manifest_sha256=S.sha_file(planpath)))


if __name__=="__main__":
    main()
