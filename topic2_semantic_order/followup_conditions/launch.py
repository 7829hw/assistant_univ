"""Run one approved GPU at a time from a clean detached commit; default is preview."""
import argparse
import ast
from datetime import datetime
import fcntl
import os
import re
import shutil
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request

from common import *
from prepare import OUT

MAIN=Path("/home/hwkim/assistant_univ")
DEFAULT_GPU="GPU-48f798cc-9437-50ac-d604-448bbad7b311"
SPARE_GPU="GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21"
RUN_REL=REL/"gpu"
SERVE_ROOT=WORK/"pilot_006_prep/vllm"


def stamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def shell(args,**kw):
    return subprocess.run([str(x) for x in args],cwd=ROOT,text=True,capture_output=True,**kw)


def command(args,**kw):
    p=shell(args,**kw)
    if p.returncode:
        raise RuntimeError(f"Command failed: {args[0]}: {p.stderr.strip()}")
    return p.stdout.strip()


def append(path,d):
    with path.open("a",encoding="utf-8") as f:
        f.write(json.dumps(dict(time=stamp(),**d),ensure_ascii=False)+"\n")


def ollama_state():
    # Docker failure due to permissions is distinct from container absence.
    docker=command(["docker","ps","-a","--filter","name=^/ollama$","--format","{{.Names}}"])
    device=None
    if docker:
        details=json.loads(command(["docker","inspect","ollama"]))[0]
        reqs=details["HostConfig"].get("DeviceRequests") or []
        device={"running":details["State"]["Running"],"device_ids":[i for r in reqs for i in (r.get("DeviceIDs") or [])]}
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps",timeout=4) as response:
            models=json.load(response)["models"]
    except urllib.error.URLError as e:
        if (device and device["running"]) or not isinstance(e.reason, ConnectionRefusedError):
            raise RuntimeError("Could not verify Ollama model state") from e
        models=[]
    if models:
        raise RuntimeError("Ollama has a model loaded; no HF measurements or training started")
    return {"container":device,"loaded_models":len(models)}


def gpu_gate(uuid,env,log):
    rows=[x.split(", ") for x in command(["nvidia-smi","--query-gpu=index,uuid,pstate,memory.used,memory.total",
                                        "--format=csv,noheader,nounits"]).splitlines()]
    current=next((r for r in rows if r[1]==uuid),None)
    if not current:
        raise RuntimeError(f"Approved GPU absent: {uuid}")
    index, _, pstate, used, total = current
    if uuid==SPARE_GPU and any(r[1]==DEFAULT_GPU and int(r[3])<100 for r in rows):
        raise RuntimeError("Spare permitted only when default GPU is unavailable")
    apps=command(["nvidia-smi","-i",uuid,"--query-compute-apps=pid,process_name,used_gpu_memory","--format=csv,noheader"])
    if apps or int(used)>=100:
        raise RuntimeError(f"GPU busy: {uuid}, {used} MiB, {apps}")
    olla=ollama_state()
    if olla["container"] and olla["container"]["running"]:
        devices=olla["container"]["device_ids"]
        expected=next((r[0] for r in rows if r[1]==DEFAULT_GPU),None)
        if not devices or set(devices) not in ({DEFAULT_GPU},{expected}):
            raise RuntimeError("Ollama assignment cannot be verified against the repository UUID")
    torch_uuid=command([PY,"-c","import torch; assert torch.cuda.device_count()==1; print('GPU-'+str(torch.cuda.get_device_properties(0).uuid))"],
                       env={**env,"CUDA_VISIBLE_DEVICES":index})
    if torch_uuid!=uuid:
        raise RuntimeError(f"Host/torch GPU UUID mismatch: {uuid}/{torch_uuid}")
    append(log,dict(gpu_uuid=uuid,index=index,pstate=pstate,used_mib=int(used),total_mib=int(total),torch_uuid=torch_uuid,ollama=olla))
    return index


def logged(args,env,log):
    with log.open("a",encoding="utf-8") as f:
        f.write("$ "+repr([str(x) for x in args])+"\n")
        f.flush()
        p=subprocess.Popen([str(x) for x in args],cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            return p.wait()
        except BaseException:
            kill_group(p)
            raise


def kill_group(p):
    try:
        os.killpg(p.pid,signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        p.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGKILL)
        p.wait()


def boundary(deadline):
    if datetime.now(deadline.tzinfo)>=deadline:
        raise RuntimeError("Authorized deadline for starting new work has passed")


def pick_port():
    for port in range(18716,18732):
        if (SERVE_ROOT/f"server_{port}.pid").exists():
            continue
        try:
            with socket.socket() as s:
                s.bind(("127.0.0.1",port))
            return port
        except OSError:
            pass
    raise RuntimeError("No dedicated vLLM port available")


def trajectory(log, job):
    out=[]
    for line in log.read_text(encoding="utf-8").splitlines():
        if line.startswith("{'loss':") and "'learning_rate':" in line:
            d=ast.literal_eval(line.split("}",1)[0]+"}")
            out.append({k:d[k] for k in ("loss","learning_rate","num_tokens","epoch")})
    kind="constant_with_warmup" if job["arm"] in ("C","D") else "linear"
    if len(out)!=STEPS or not np.allclose([r["learning_rate"] for r in out],analytical_rates(kind),rtol=0,atol=1e-18):
        raise RuntimeError("Actual optimizer LR trajectory does not match the frozen schedule")
    if out[-1]["num_tokens"] != load(HERE/"provenance/token_ledger.json")["input_tokens"]:
        raise RuntimeError("Actual token budget differs from the CPU gate")
    return out


def train_job(job, env, logdir, model_log, deadline, uuid, commit, checkpoint):
    name=job["id"]
    status=model_log/f"trained_{name}.json"
    model=checkpoint/"adapter_model.safetensors"
    if status.is_file():
        prior=load(status)
        if (prior["commit"]!=commit or prior["gpu_uuid"]!=uuid or not model.is_file()
            or S.sha_file(model)!=prior["adapter_sha256"]):
            raise RuntimeError("Resuming requires the verified adapter, original GPU and commit")
        return prior
    for attempt in (1,2):
        boundary(deadline)
        if checkpoint.parent.exists():
            raise RuntimeError(f"Output already exists: {checkpoint.parent}")
        index=gpu_gate(uuid,env,logdir/"gpu_checks.jsonl")
        log=logdir/f"train_{name}_a{attempt}.log"
        if log.exists():
            raise RuntimeError(f"Previous unverified attempt needs review: {log}")
        start=stamp()
        rc=logged(job["train_cmd"],{**env,"CUDA_VISIBLE_DEVICES":index},log)
        append(logdir/"timeline.jsonl",dict(job=name,stage="train",attempt=attempt,gpu_uuid=uuid,commit=commit,started=start,rc=rc))
        if rc==0 and model.is_file():
            steps=trajectory(log,job)
            training_prov=load(checkpoint.parent/"training_provenance.json")
            profile=load(OUT/(name+"_profile.json"))
            dump(logdir/f"training_{name}.json",dict(config_sha256=job["config_sha256"],order_sha256=job["order_sha256"],
                 train_sha256=TRAIN_SHA,steps=steps,logged_lr_sum=sum(x["learning_rate"] for x in steps),
                 provenance=training_prov,profile=profile))
            prior=dict(commit=commit,gpu_uuid=uuid,adapter_sha256=S.sha_file(model))
            dump(status,prior)
            return prior
        if attempt!=1 or not re.search(r"out of memory|OutOfMemoryError|(?i:non[- ]finite|\bnan\b)",
                                      log.read_text(encoding="utf-8")[-6000:],re.I):
            raise RuntimeError(f"Training failed: {name}, attempt {attempt}; see log")
        if checkpoint.parent.exists():
            dst=checkpoint.parent.with_name(name+".failed1")
            if dst.exists():
                raise RuntimeError("Previous failure directory exists")
            checkpoint.parent.rename(dst)
    raise AssertionError("unreachable")


def evaluate(job, manifest, env, logdir, model_log, deadline, uuid, commit, out, checkpoint, adapter_sha):
    boundary(deadline)
    index=gpu_gate(uuid,env,logdir/"gpu_checks.jsonl")
    port=pick_port()
    ep=manifest["evaluation"]
    server_env={**env,"P3":str(logdir),"LORAS":f"{job['model']}={checkpoint}","MAX_LORA_RANK":"16"}
    server_log=logdir/f"serve_{job['id']}.log"
    raw=out/"cells_raw"
    cells=out/"cells"
    for p in (raw,cells):
        p.mkdir(parents=True,exist_ok=True)
    import completeness_B as CB
    CB.CELLS=cells
    with server_log.open("a",encoding="utf-8") as f:
        server=subprocess.Popen(["bash",ep["server"],index,str(port),ep["dtype"],ep["kernel"]],cwd=ROOT,env=server_env,
                                stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            if server.wait()!=0:
                raise RuntimeError(f"vLLM failed: {server_log}")
            info=load(SERVE_ROOT/f"server_{port}.json")
            if (not info["ready"] or info["gpu_uuid"]!=uuid or info["adapter_sha256"]!=adapter_sha
                or info["precision"]!="bf16" or info["kernels"]!="fi"):
                raise RuntimeError("vLLM device, model, or execution condition mismatch")
            dump(model_log/f"server_{job['id']}.json",info)
            dump(logdir/f"server_{job['id']}.json",{k:info[k] for k in ("ready","precision","kernels","gpu_uuid",
                        "log_attention_backend","log_flashinfer_sampler_lines","vllm","flashinfer","torch","transformers")})
            for cell in job["cells"]:
                label,k=cell["label"],cell["k"]
                base=f"{label}_s{k}"
                for attempt in (1,2):
                    boundary(deadline)
                    result=cells/f"{base}.json"
                    if not result.exists():
                        args=[PY,ep["harness"],"--port",str(port),"--model",job["model"],"--label",label,"--k",str(k),
                              "--concurrency",str(cell["concurrency"]),"--grounding-target","full","--out-dir",cells,
                              "--raw-dir",raw,"--seed-base",str(ep["seed_base"]),"--gold",cell["gold"]]
                        args += ["--only",(ROOT/cell["chunk"]).read_text().strip()] if cell["chunk"] else ["--all-items"]
                        start=stamp()
                        rc=logged(args,env,logdir/f"eval_{base}_a{attempt}.log")
                        append(logdir/"timeline.jsonl",dict(job=job["id"],stage="eval",cell=base,attempt=attempt,
                               gpu_uuid=uuid,commit=commit,started=start,rc=rc))
                        if rc:
                            for p in (result,cells/f"{base}.log",raw/f"{base}_raw.jsonl"):
                                if p.exists():
                                    p.rename(p.with_name("ABORTED_"+p.name))
                            raise RuntimeError(f"Invalid eval cell {base}; retain partial files for review")
                    r=CB.cell(label,k)
                    if not all(r.get(key) for key in ("exists","raw_sha256_match","raw_items_cover","rows_equal_item_order",
                                                      "fingerprint_ok","prompt_ok")) or r["model"]!=job["model"]:
                        raise RuntimeError(f"Evaluation completeness or provenance mismatch: {base}")
                    need=(r["truncated_calls"]>=2 or r["server_error_rows"]>=2) if label.endswith("_rdevv2") else r["rerun"]
                    already=(cells/"replaced"/result.name).exists()
                    if need and attempt==1 and not already:
                        for p in (result,cells/f"{base}.log",raw/f"{base}_raw.jsonl"):
                            dst=p.parent/"replaced"/p.name
                            dst.parent.mkdir(exist_ok=True)
                            p.rename(dst)
                        append(logdir/"reruns.jsonl",dict(cell=base,original_sha256=r["sha256"],
                               truncated_calls=r["truncated_calls"],server_error_rows=r["server_error_rows"]))
                        continue
                    append(logdir/"eval_provenance.jsonl",dict(cell=base,gpu_uuid=uuid,commit=commit,**r))
                    break
        finally:
            kill_group(server)
            (SERVE_ROOT/f"server_{port}.pid").unlink(missing_ok=True)
            # Give our own server workers time to release CUDA allocations.
            for _ in range(15):
                if not command(["nvidia-smi","-i",uuid,"--query-compute-apps=pid","--format=csv,noheader"]):
                    break
                time.sleep(1)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase",type=int,choices=(1,2),required=True)
    p.add_argument("--approval",type=Path)
    p.add_argument("--run",action="store_true")
    a=p.parse_args()
    path=HERE/f"gpu/jobs_phase{a.phase}.json"
    m=load(path)
    gate=load(HERE/"gates/GATES.json") if (HERE/"gates/GATES.json").exists() else {}
    digest=S.sha_file(path)
    if not a.run:
        print(json.dumps(dict(phase=a.phase,jobs=len(m["jobs"]),cells=sum(len(j["cells"]) for j in m["jobs"]),
                              manifest_sha256=digest,cpu_gates_pass=sum(v["status"]=="PASS" for v in gate.values()),
                              estimated_gpu_hours=sum(j["train_estimate_min"]+j["eval_estimate_min"] for j in m["jobs"])/60)))
        return
    if a.approval is None:
        p.error("--run needs a new task-specific authorization record")
    commit=command(["git","rev-parse","HEAD"])
    if ROOT==MAIN or shell(["git","symbolic-ref","-q","HEAD"]).returncode!=1 or command(["git","status","--porcelain"]):
        raise RuntimeError("Use a separate clean, detached worktree at the approved commit")
    approved=load(a.approval)
    uuid=approved["gpu_uuid"]
    deadline=datetime.fromisoformat(approved["start_before"])
    if deadline.tzinfo is None or approved.get("commit")!=commit or approved.get("manifest_sha256")!=digest:
        raise RuntimeError("Authorization does not match this commit, phase manifest or deadline")
    boundary(deadline)
    if uuid not in (DEFAULT_GPU,SPARE_GPU):
        raise RuntimeError("Requested GPU is outside default/spare policy")
    if len(gate)!=40 or any(v["status"]!="PASS" or S.sha_file(ROOT/v["log"])!=v["log_sha256"] for v in gate.values()):
        raise RuntimeError("Pinned CPU gates have not passed")
    if m["preregistration_sha256"]!=S.sha_file(HERE/"EXPERIMENT_PLAN.md"):
        raise RuntimeError("Preregistration hash mismatch")
    for f,h in m["eval_input_sha256"].items():
        if S.sha_file(ROOT/f)!=h:
            raise RuntimeError(f"Evaluation input hash drift: {f}")
    if min(shutil.disk_usage(WORK).free,shutil.disk_usage(MAIN).free)/2**30 < 100:
        raise RuntimeError("Follow-up disk gate requires >=100 GiB free on both volumes")
    out=MAIN/REL
    logdir=out/"gpu"/"execution"
    logdir.mkdir(parents=True,exist_ok=True)
    # Keep actual adapter hashes outside Git, per decision 255.
    model_log=WORK/"topic2_semantic_order/followup_conditions/provenance"
    model_log.mkdir(parents=True,exist_ok=True)
    env={**os.environ,"HF_HOME":str(WORK/"hf-cache"),"HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1",
         "PYTHONDONTWRITEBYTECODE":"1","TOKENIZERS_PARALLELISM":"false","PYTORCH_CUDA_ALLOC_CONF":"expandable_segments:True",
         "OLLAMA_UUID":DEFAULT_GPU,"ALLOWED_UUIDS":uuid,"FOLLOWUP_RUN_COMMIT":commit}
    env.pop("LORAS",None)
    with (model_log/"run.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        sys.path.insert(0,str(INV/"pilot_007/results"))
        for job in m["jobs"]:
            boundary(deadline)
            checkpoint=Path(job["checkpoint"])
            # Training logs stay in the repo; only the verification receipt is external.
            trained=train_job(job,env,logdir,model_log,deadline,uuid,commit,checkpoint)
            evaluate(job,m,env,logdir,model_log,deadline,uuid,commit,out,checkpoint,trained["adapter_sha256"])
        dump(logdir/f"phase{a.phase}_done.json",dict(commit=commit,manifest_sha256=digest,gpu_uuid=uuid,
                                                     completed=stamp(),jobs=len(m["jobs"])))


if __name__=="__main__":
    main()
