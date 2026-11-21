# -*- coding: utf-8 -*-
"""pilot_010 JV(결정 273) 공통: 상수, 기록(runs.log·timeline.jsonl), nvidia-smi 도우미, 서버 띄우기·내리기(``serve_jv.sh``). ``ju/driver_ju.py``의 같은 부분을 옮김."""
import gzip
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import models_jv as M  # noqa: E402
import serverlog_jv as SL  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
EXPECT_UUID = {0: "GPU-2445b100-70d8-e384-3a24-0249eeefc64d", 1: "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555",
               2: "GPU-c8f1bae2-de7a-a1c0-a054-8b6ebe5c2c8e", 3: "GPU-48f798cc-9437-50ac-d604-448bbad7b311"}
OLLAMA_UUID = "GPU-48f798cc-9437-50ac-d604-448bbad7b311"   # 결정 191 기존 컨테이너 GPU(gpu_ok가 그 컨테이너 상태를 읽기만 함; 컨테이너는 없음)
PORTS = {0: 11461, 1: 11462, 2: 11463, 3: 11464}
SERVERS = M.JV / "servers"
JV_MODELS = M.JV / "models"
JU_MODELS = Path("/data/hwkim/sftdpo_work/pilot_010_ju/models")
TEACHER = {"name": "t27q4", "ollama": "qwen3.8:27b", "digest": "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813", "models": JU_MODELS, "render": "qwen38"}
PF_GOLD = "/data/hwkim/sftdpo_work/protected_final_v2/pf2_gold.yaml"
PF_CELLS, PF_RAW = Path("/data/hwkim/sftdpo_work/protected_final_v2/cells"), Path("/data/hwkim/sftdpo_work/protected_final_v2/raw")
HF_GOLD = "sft_dpo_inventory/ablation_012/e2/h_final.yaml"
HDEV_GOLD = "sft_dpo_inventory/ablation_012/e2/h_dev.yaml"
LAT_GOLD = "sft_dpo_inventory/conversion_diag/selection_gold.yaml"
LAT_IDS_FILE = "sft_dpo_inventory/serving_vllm_fp8/latency_ids.txt"
SUBSET_FILE = "sft_dpo_inventory/pilot_010/jt/hfinal_subset1000_ids.txt"


def now():
    return datetime.now(KST)


class Ctx:
    def __init__(self, main, tag="jv"):
        self.main = Path(main)
        self.G = self.main / "sft_dpo_inventory/pilot_010/gpu/JV"
        self.cells = self.main / "sft_dpo_inventory/pilot_010/cells/JV"
        self.raw = self.main / "training/generated/pilot_010/cells_raw_JV"
        for d in (self.G, self.cells, self.raw, self.cells / "smoke", self.cells / "render", self.cells / "latency", self.G / "jobs", self.G / "server_logs"):
            d.mkdir(parents=True, exist_ok=True)
        self.env = {**os.environ, "OLLAMA_UUID": OLLAMA_UUID, "ALLOWED_UUIDS": " ".join(EXPECT_UUID.values()), "P3": str(self.G),
                    "HF_HOME": "/data/hwkim/sftdpo_work/hf-cache", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "TOKENIZERS_PARALLELISM": "false",
                    "PYTHONDONTWRITEBYTECODE": "1"}
        self.env.pop("OLLAMA_HOST", None)
        self.tag = tag
        self.lock = threading.Lock()
        self.running = {}          # gpu -> job name

    def log(self, msg):
        line = f"== [{self.tag}] {msg} {now().isoformat(timespec='seconds')}"
        with self.lock:
            with open(self.G / "runs.log", "a", encoding="utf-8") as f:
                f.write(line + "\n")
        print(line, flush=True)

    def tl(self, **ev):
        with self.lock:
            with open(self.G / "timeline.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": now().isoformat(timespec="seconds"), **ev}, ensure_ascii=False) + "\n")


def smi(query, kind="gpu"):
    q = "--query-gpu" if kind == "gpu" else "--query-compute-apps"
    out = subprocess.run(["nvidia-smi", f"{q}={query}", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout
    return [[x.strip() for x in l.split(",")] for l in out.strip().splitlines() if l.strip()]


def uuid_map():
    return {int(i): u for i, u in smi("index,uuid")}


def procs_on(indices):
    m = uuid_map()
    want = {m[i] for i in indices}
    return [p for p in smi("gpu_uuid,pid,used_memory,process_name", "apps") if p and p[0] in want]


def mem_sampler(ctx, stop, path=None, every=30):
    path = path or ctx.G / "gpu_mem.jsonl"
    while not stop.is_set():
        try:
            rows = smi("index,memory.used,utilization.gpu")
            procs = smi("gpu_uuid,pid,used_memory", "apps")
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": now().isoformat(timespec="seconds"), "running": {str(k): v for k, v in ctx.running.items()},
                                    "gpus": rows, "procs": procs}) + "\n")
        except Exception:  # noqa: BLE001
            pass
        stop.wait(every)


def start_server(ctx, g, job, model, digest, models_dir, ctx_len=None, debug=False):
    """서버 하나(GPU g, 모델 하나)를 띄운다. → (ok, server_json dict, 작업 디렉터리)."""
    port = PORTS[g]
    work = SERVERS / job
    work.mkdir(parents=True, exist_ok=True)
    env = {**ctx.env, "JVWORK": str(work)}
    if ctx_len:
        env["CTX"] = str(ctx_len)
    if debug:
        env["JV_DEBUG"] = "1"
    ctx.log(f"start server GPU {g} port {port} job {job} model {model}")
    rc = subprocess.run(["bash", str(HERE / "serve_jv.sh"), str(g), str(port), model, digest, str(models_dir)], env=env, cwd=WT,
                        stdout=open(ctx.G / f"serve_{job}.out", "a"), stderr=subprocess.STDOUT).returncode
    sj = work / f"server_{port}.json"
    rec = json.loads(sj.read_text(encoding="utf-8")) if sj.exists() else None
    ctx.tl(event="server_start", job=job, port=port, gpu=g, rc=rc, ready=(rec or {}).get("ready"))
    if rec:
        shutil.copy(sj, ctx.G / "jobs" / f"{job}.server.json")
    return rc == 0, rec, work


def stop_server(ctx, g, job):
    port = PORTS[g]
    work = SERVERS / job
    pidf = work / f"server_{port}.pid"
    if pidf.exists():
        pid = int(pidf.read_text().strip())
        try:
            os.kill(pid, 15)
        except ProcessLookupError:
            pass
        for _ in range(60):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(2)
    for _ in range(60):
        if not procs_on([g]):
            break
        time.sleep(2)
    left = procs_on([g])
    log = work / f"server_{port}.log"
    if log.exists():
        with open(log, "rb") as src, gzip.open(ctx.G / "server_logs" / f"{job}.log.gz", "wb") as dst:
            shutil.copyfileobj(src, dst)
    ctx.tl(event="server_stop", job=job, port=port, gpu=g, left=left)
    ctx.log(f"stop server GPU {g} port {port} job {job} left={left}")
    return not left


def server_log_summary(job, g, expect=SL.EXPECT_S):
    log = SERVERS / job / f"server_{PORTS[g]}.log"
    return SL.summary(log.read_text(errors="replace"), expect) if log.exists() else None
