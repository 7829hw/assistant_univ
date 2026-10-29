# -*- coding: utf-8 -*-
"""pilot_007 A2 공유 GPU 큐(결정 177–181). ``scheduler7.py``의 사본(규칙 15: 새 파일).

    hfvenv/bin/python <worktree>/sft_dpo_inventory/pilot_007/gpu_data/scheduler8.py --jobs <MAIN>/sft_dpo_inventory/pilot_007/gpu_data/jobs_A2.json \
        --gpus GPU-2445b100-70d8-e384-3a24-0249eeefc64d GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555 --ollama-uuid GPU-2445b100-70d8-e384-3a24-0249eeefc64d [--dry-run]

scheduler7과 다른 것:
- ``--gpus``(UUID 목록)에 있는 GPU만 worker로 만든다(GPU 2 48f798cc는 넣지 않음, 결정 180). 서버는 ``serve7.sh``(gpu_lib7: ALLOWED_UUIDS 밖 GPU 거부).
- ``--ollama-uuid``: Ollama GPU(2026-10-19 = GPU 0 2445b100, 결정 181). 그 GPU에 작업을 줄 때마다 ``/api/ps`` 결과를 runs.log에 적고, 모델이 있으면 주지 않는다
  (직접 내리지 않음; 다른 GPU부터 채움). 작업이 도는 중에 모델이 올라오면 시각·모델을 한 번 적고, 그 GPU에는 다음 작업을 붙이지 않는다(내려갈 때까지).
  30분 넘게 내려가지 않으면 "30분 초과" 줄을 적는다(GPU 1 한 장으로 계속).
- ``--dry-run``: worker 목록, 작업 표, Ollama 확인 결과, 첫 배정 결정을 출력만 하고 아무것도 시작하지 않는다.
- 기록: runs.log 태그 ``[s7a2]``, PID ``scheduler8.pid``. 나머지(작업 하나 = GPU 하나, 고정 worktree, 작업 표 다시 읽기, train_a7·train_diag·cells·raw)는 scheduler7과 같다.
"""
import json
import os
import signal
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import sys as _sys0

SCHED_WT = Path(__file__).resolve().parents[3]
MAIN = Path("/home/hwkim/assistant_univ")
G = MAIN / "sft_dpo_inventory/pilot_007/gpu"
TL = SCHED_WT / "sft_dpo_inventory/pilot_006_prep/gpu_data/timeline.py"
READY = G / "ready"
WTROOT = Path("/data/hwkim/sftdpo_work/worktrees")
VW = Path("/data/hwkim/sftdpo_work/pilot_006_prep/vllm")
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
CELLS = MAIN / "sft_dpo_inventory/pilot_007/cells"
RAWP = MAIN / "training/generated/pilot_007/cells_raw"
OLLAMA_UUID = _sys0.argv[_sys0.argv.index("--ollama-uuid") + 1]
ALLOWED = _sys0.argv[_sys0.argv.index("--gpus") + 1:]
ALLOWED = ALLOWED[:next((i for i, a in enumerate(ALLOWED) if a.startswith("--")), len(ALLOWED))]
DRY = "--dry-run" in _sys0.argv
ADAPTER_467 = "/data/hwkim/sftdpo_work/pilot_005/checkpoints/v1/checkpoint-467"
GOLD = {"sel": None, "holdout": "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml", "vendor100": "evaluation/vendor100/gold.yaml",
        "valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml"}
ENV = {**os.environ, "OLLAMA_UUID": OLLAMA_UUID, "ALLOWED_UUIDS": " ".join(ALLOWED), "HF_HOME": "/data/hwkim/sftdpo_work/hf-cache", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
       "TOKENIZERS_PARALLELISM": "false", "PYTHONDONTWRITEBYTECODE": "1", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}
LOCK = threading.RLock()


def now():
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def log(msg):
    with LOCK, open(G / "runs.log", "a", encoding="utf-8") as f:
        f.write(f"== [s7a2] {msg} {now()}\n")


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def cell(label, server_model, target, gold_key, sealed=False, kmax=4):
    """run_cell6v.py k=1..kmax 명령 목록과 출력."""
    def build(wt, port):
        cmds = []
        for k in range(1, kmax + 1):
            c = [PY, f"{wt}/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6v.py", "--port", str(port), "--model", server_model, "--label", label,
                 "--k", str(k), "--concurrency", "8", "--grounding-target", target, "--out-dir", str(CELLS), "--raw-dir", str(RAWP)]
            if GOLD[gold_key]:
                c += ["--gold", GOLD[gold_key], "--all-items"]
            if sealed:
                c += ["--sealed"]
            cmds.append(c)
        return cmds
    outs = [p for k in range(1, kmax + 1) for p in (CELLS / f"{label}_s{k}.json", CELLS / f"{label}_s{k}.log", RAWP / f"{label}_s{k}_raw.jsonl")]
    return build, outs


def j6():
    raw = MAIN / "training/generated/pilot_006/self_partial/raw/self_partial_raw.jsonl"
    man = MAIN / "training/generated/pilot_006/self_partial/manifest.json"

    def build(wt, port):
        return [[PY, f"{wt}/sft_dpo_inventory/pilot_006_prep/gpu_data/collect6.py", "--mode", "self", "--grounding-target", "partial", "--port", str(port),
                 "--label", "J6_self_partial", "--inputs", f"{wt}/sft_dpo_inventory/pilot_006_prep/gpu/inputs/self_questions.jsonl",
                 "--raw-out", str(raw), "--out", str(man), "--server-meta", str(VW)]]
    return build, [raw, man]


def teacher(job):
    tag, out = {"T0c": ("t0v3c", "teacher_t0v3c"), "TEACH": ("teach4", "teacher_v3")}[job]
    rec = MAIN / "sft_dpo_inventory/pilot_006/teacher"

    def build(wt, port):
        return [[PY, f"{wt}/sft_dpo_inventory/pilot_006/teacher/run_teacher6v4.py", "--main", str(MAIN), "--job", job]]
    return build, [MAIN / "training/generated/pilot_006" / out, rec / f"{tag}_summary.json"]


def selfs(job, inputs, target, samples=8, s32=False, round_seed="20261016", inputs_dir="inputs2d"):
    raw = MAIN / f"training/generated/pilot_006/self_2d/raw/{job}_raw.jsonl"
    man = MAIN / f"training/generated/pilot_006/self_2d/{job}_manifest.json"

    def build(wt, port):
        c = [PY, f"{wt}/sft_dpo_inventory/pilot_006_prep/gpu_data/collect6b.py", "--mode", "self", "--grounding-target", target, "--port", str(port),
             "--label", job, "--inputs", f"{wt}/sft_dpo_inventory/pilot_006_prep/gpu/{inputs_dir}/{inputs}.jsonl", "--raw-out", str(raw), "--out", str(man),
             "--server-meta", str(VW), "--samples", str(samples)]
        if s32:
            c += ["--no-greedy", "--round-seed", round_seed]
        return [c]
    return build, [raw, man]


def j13():
    base = MAIN / "training/generated/pilot_006/self_2c"

    def build(wt, port):
        cmds = []
        inp = f"{wt}/sft_dpo_inventory/pilot_006_prep/gpu/inputs2c/j13.jsonl"
        for target in ("partial", "full"):
            cmds.append([PY, f"{wt}/sft_dpo_inventory/pilot_006_prep/gpu_data/collect6b.py", "--mode", "self", "--grounding-target", target, "--port", str(port),
                         "--label", f"J13_{target}", "--inputs", inp, "--raw-out", str(base / f"raw/J13_{target}_raw.jsonl"),
                         "--out", str(base / f"J13_{target}_manifest.json"), "--server-meta", str(VW)])
        cmds.append([PY, f"{wt}/sft_dpo_inventory/pilot_006_prep/gpu_data/collect6b.py", "--mode", "first", "--port", str(port), "--label", "J13_first",
                     "--inputs", inp, "--raw-out", str(base / "raw/J13_first_raw.jsonl"), "--out", str(base / "J13_first.jsonl"), "--server-meta", str(VW)])
        return cmds
    return build, [base / f"raw/J13_{t}_raw.jsonl" for t in ("partial", "full", "first")] + [base / f"J13_{t}_manifest.json" for t in ("partial", "full")] + [base / "J13_first.jsonl"]


B17 = "b17408"


def train_diag(config):
    def build(wt, port):
        return [[PY, f"{wt}/sft_dpo_inventory/pilot_006/post/diag/train_diag.py", "--config", f"{wt}/{config}"]]
    return build, []


def train_a7(config):
    def build(wt, port):
        return [[PY, f"{wt}/sft_dpo_inventory/pilot_007/train_data/train_a7.py", "--config", f"{wt}/{config}"]]
    return build, []


def cells(specs):
    """specs: [{label, model, target, gold, k, seed_base, greedy}] — 한 서버에서 차례로."""
    def build(wt, port):
        cmds = []
        for c in specs:
            for k in range(1, c.get("k", 4) + 1):
                cmd = [PY, f"{wt}/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py", "--port", str(port), "--model", c["model"], "--label", c["label"],
                       "--k", str(k), "--concurrency", "8", "--grounding-target", c["target"], "--out-dir", str(CELLS), "--raw-dir", str(RAWP),
                       "--seed-base", str(c.get("seed_base", 20261100))]
                if c.get("greedy"):
                    cmd.append("--greedy")
                if GOLD[c["gold"]]:
                    cmd += ["--gold", GOLD[c["gold"]], "--all-items"]
                cmds.append(cmd)
        return cmds
    outs = [p for c in specs for k in range(1, c.get("k", 4) + 1)
            for p in (CELLS / f"{c['label']}_s{k}.json", CELLS / f"{c['label']}_s{k}.log", RAWP / f"{c['label']}_s{k}_raw.jsonl")]
    return build, outs


def raw_cmd(cmd, outs):
    def build(wt, port):
        return [[x.replace("{WT}", str(wt)).replace("{MAIN}", str(MAIN)).replace("{PORT}", str(port)) for x in cmd]]
    return build, [Path(o.replace("{MAIN}", str(MAIN))) for o in outs]


def to_job(j):
    t = j["type"]
    if t == "train_a7":
        define = (lambda c=j["config"]: train_a7(c))
    elif t == "train_diag":
        define = (lambda c=j["config"]: train_diag(c))
    elif t == "cells":
        define = (lambda s=j["cells"]: cells(s))
    else:
        define = (lambda c=j["cmd"], o=j.get("outputs", []): raw_cmd(c, o))
    return (j["prio"], j["id"], j["kind"], j["server"], j["est"], j.get("deps", []), define)


def load_jobs(path):
    return [to_job(j) for j in json.loads(Path(path).read_text(encoding="utf-8"))["jobs"]]


import sys as _sys  # noqa: E402
JOBS_PATH = _sys.argv[_sys.argv.index("--jobs") + 1]
JOBS = load_jobs(JOBS_PATH)
STATE = {j[1]: "pending" for j in JOBS}


def sched_commit():
    return sh(["git", "-C", str(SCHED_WT), "rev-parse", "HEAD"]).stdout.strip()


def worktrees_update(name, entry):
    with LOCK:
        p = G / "worktrees.json"
        data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"root": str(WTROOT), "worktrees": {}}
        data["worktrees"].setdefault(name, {}).update(entry)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def make_wt(commit, job_id):
    name = f"wt_{commit[:7]}_{job_id}"
    path = WTROOT / name
    with LOCK:
        r = sh(["git", "-C", str(MAIN), "worktree", "add", "--detach", str(path), commit])
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    worktrees_update(name, {"path": str(path), "commit": commit, "jobs": [job_id], "status": "in_use", "created": now()})
    return path, name


def remove_wt(path, name):
    with LOCK:
        r = sh(["git", "-C", str(MAIN), "worktree", "remove", "--force", str(path)])
    worktrees_update(name, {"status": "removed" if r.returncode == 0 else f"remove_failed: {r.stderr.strip()[:200]}", "removed": now()})


def ollama_loaded():
    try:
        return json.loads(sh(["curl", "-s", "localhost:11434/api/ps"]).stdout)["models"]
    except Exception:  # noqa: BLE001
        return ["unknown"]


def gpu_apps(uuid):
    out = sh(["nvidia-smi", "-i", uuid, "--query-compute-apps=pid", "--format=csv,noheader"]).stdout
    return [int(x) for x in out.split() if x.strip().isdigit()]


def descends(pid, root):
    while pid and pid > 1:
        if pid == root:
            return True
        try:
            pid = int(sh(["ps", "-o", "ppid=", "-p", str(pid)]).stdout.strip() or 0)
        except ValueError:
            return False
    return False


class Worker(threading.Thread):
    def __init__(self, index, uuid):
        super().__init__(daemon=True)
        self.index, self.uuid, self.port = index, uuid, 8620 + index
        self.ollama = uuid == OLLAMA_UUID
        self.server, self.server_pid, self.job, self.idle_since = None, None, None, time.time()
        self.cv = threading.Condition()

    def label(self):
        return f"GPU {self.index} ({self.uuid[:12]})"

    def stop_server(self):
        if self.server_pid:
            try:
                os.kill(self.server_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            for _ in range(60):
                if not gpu_apps(self.uuid):
                    break
                time.sleep(2)
            log(f"server stop {self.label()} kind {self.server}")
        (VW / f"server_{self.port}.pid").unlink(missing_ok=True)
        self.server, self.server_pid = None, None

    def start_server(self, kind):
        script = "serve7.sh"
        env = dict(ENV)
        if kind.startswith("lora32:"):  # 6g: rank 32 adapter(D-avg)는 serve6c.sh(--max-lora-rank 32만 다름)
            script = "serve6c.sh"
            env["LORAS"] = kind[len("lora32:"):]
        elif kind.startswith("lora:"):
            env["LORAS"] = kind[len("lora:"):]
        r = subprocess.run(["bash", (f"{SCHED_WT}/sft_dpo_inventory/pilot_007/gpu_data/{script}" if script == "serve7.sh" else f"{SCHED_WT}/sft_dpo_inventory/pilot_006_prep/gpu_data/{script}"), str(self.index), str(self.port), "bf16", "fi"],
                           env=env, cwd=str(SCHED_WT), capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"server start failed ({kind}): {r.stdout[-300:]} {r.stderr[-300:]}")
        self.server, self.server_pid = kind, int((VW / f"server_{self.port}.pid").read_text().strip())
        log(f"server ready {self.label()} kind {kind} pid {self.server_pid}")

    def clean(self, job_id):
        apps = gpu_apps(self.uuid)
        other = [p for p in apps if not (self.server_pid and descends(p, self.server_pid))]
        with LOCK, open(G / "gpu_check.txt", "a", encoding="utf-8") as f:
            f.write(f"## {now()} [s2] before {job_id} {self.label()} server {self.server} pid {self.server_pid}\n"
                    + sh(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory,process_name", "--format=csv,noheader"]).stdout
                    + "## ollama ps\n" + json.dumps(ollama_loaded()) + "\n")
        return other

    def assign(self, job):
        with self.cv:
            self.job = job
            self.cv.notify()

    def run(self):
        while True:
            with self.cv:
                while self.job is None:
                    if self.server and time.time() - self.idle_since > 600:
                        self.stop_server()
                    self.cv.wait(timeout=30)
                job = self.job
            try:
                self.execute(job)
            finally:
                self.job, self.idle_since = None, time.time()

    def execute(self, job):
        prio, job_id, kind, server, est, deps, define = job
        start = now()
        commit = sched_commit()
        outs, wt, name, rc, note = [], None, None, None, ""
        try:
            if define is None:
                build, outs, commit = ready_job(job_id)
            else:
                build, outs = define()
            if server in ("ollama", "train"):
                self.stop_server()
            elif self.server != server:
                self.stop_server()
                self.start_server(server)
            if server != "ollama":
                other = self.clean(job_id)
                if other:
                    raise RuntimeError(f"other process on {self.label()}: {other}")
            wt, name = make_wt(commit, job_id)
            log(f"{job_id} start {self.label()} server {self.server} worktree {name}")
            env = dict(ENV)
            if server == "train":
                env["CUDA_VISIBLE_DEVICES"] = str(self.index)
            try:
                cmds = build(wt, self.port, self.index)
            except TypeError:
                cmds = build(wt, self.port)
            with open(G / f"{job_id}.log", "a", encoding="utf-8") as lg:
                for c in cmds:
                    lg.write(f"$ {' '.join(map(str, c))}\n")
                    lg.flush()
                    rc = subprocess.run([str(x) for x in c], cwd=str(wt), env=env, stdout=lg, stderr=subprocess.STDOUT).returncode
                    if rc != 0:
                        break
        except Exception as error:  # noqa: BLE001 - 작업 실패로 기록하고 계속
            rc, note = rc if rc not in (None, 0) else 1, f"{type(error).__name__}: {error}"[:400]
        status = "ok" if rc == 0 else f"failed(exit {rc})"
        if rc != 0:
            for p in outs:
                p = Path(p)
                if p.exists():
                    p.rename(p.with_name("ABORTED_" + p.name))
        if wt is not None:
            remove_wt(wt, name)
            worktrees_update(name, {"job_status": status})
        with LOCK:
            subprocess.run(["python3", str(TL), "--file", str(G / "timeline.jsonl"), "--id", job_id, "--kind", kind,
                            "--uuid", self.uuid, "--commit", commit, "--start", start, "--end", now(), "--status", status,
                            "--note", (f"pilot_007 A2 scheduler8, server {self.server}; " + note).strip(), "--out", *[str(p) for p in outs]])
            STATE[job_id] = "ok" if rc == 0 else "failed"
            if server == "ollama":
                STATE["_ollama_done_at"] = time.time()
        log(f"{job_id} {status} {self.label()} {note}")


def ready(job):
    prio, job_id, kind, server, est, deps, define = job
    if STATE[job_id] != "pending":
        return False
    if (READY / f"{job_id}.skip").exists():
        STATE[job_id] = "skipped"
        log(f"{job_id} skipped (ready/{job_id}.skip)")
        subprocess.run(["python3", str(TL), "--file", str(G / "timeline.jsonl"), "--id", job_id, "--kind", kind, "--uuid", "-",
                        "--commit", "-", "--start", now(), "--end", now(), "--status", "skipped",
                        "--note", (READY / f"{job_id}.skip").read_text(encoding="utf-8")[:300]])
        return False
    for d in deps:
        if d.startswith("sel:"):
            pre = d[4:].split(",")
            if any(STATE.get(x) not in ("ok", "failed") for x in pre):
                return False
            v = MAIN / "sft_dpo_inventory/pilot_006/teacher/t0v4_verdict.json"
            sel = json.loads(v.read_text(encoding="utf-8")).get("selected") if v.exists() else None
            if sel not in ("v3a", "v3b", "v3c"):
                STATE[job_id] = "skipped"
                log(f"{job_id} skipped (selected={sel}, decision 151)")
                subprocess.run(["python3", str(TL), "--file", str(G / "timeline.jsonl"), "--id", job_id, "--kind", kind, "--uuid", "-",
                                "--commit", "-", "--start", now(), "--end", now(), "--status", "skipped", "--note", f"selected={sel} (decision 151)"])
                return False
        elif d.startswith("file:"):
            path, _, owner = d[5:].partition("|")
            if not Path(path).exists():
                if owner and STATE.get(owner) in ("failed", "skipped"):
                    STATE[job_id] = "skipped"
                    log(f"{job_id} skipped ({owner} {STATE.get(owner)}, {path} missing)")
                    subprocess.run(["python3", str(TL), "--file", str(G / "timeline.jsonl"), "--id", job_id, "--kind", kind, "--uuid", "-",
                                    "--commit", "-", "--start", now(), "--end", now(), "--status", "skipped", "--note", f"{owner} not ok; {path} missing"])
                return False
        elif d.startswith("done:"):
            if any(STATE.get(x) not in ("ok", "failed", "skipped") for x in d[5:].split(",")):
                return False
        elif d == "notrain":
            if any(STATE.get(x[1]) == "running" for x in JOBS if x[3] == "train"):
                return False
        elif d.startswith("ready:"):
            if not (READY / f"{d[6:]}.json").exists():
                return False
        elif STATE.get(d) != "ok":
            return False
    return True


def main():
    pid_dir = Path("/data/hwkim/sftdpo_work/pids")
    pid_dir.mkdir(parents=True, exist_ok=True)
    (pid_dir / "scheduler8.pid").write_text(str(os.getpid()))
    WTROOT.mkdir(parents=True, exist_ok=True)
    READY.mkdir(parents=True, exist_ok=True)
    rows = [l.split(", ") for l in sh(["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"]).stdout.strip().splitlines()]
    workers = [Worker(int(i), u) for i, u in rows if u in ALLOWED]  # 결정 180: 목록 밖 GPU(2 = 48f798cc)는 worker가 없음
    if DRY:
        jobs = [(j[0], j[1], j[3]) for j in sorted(JOBS)]
        print(json.dumps({"workers": [(w.index, w.uuid, "ollama_gpu" if w.ollama else "") for w in workers], "excluded": [u for _, u in rows if u not in ALLOWED],
                          "ollama_uuid": OLLAMA_UUID, "ollama_ps_models": ollama_loaded(), "jobs_in_order": jobs,
                          "ready_now": [j[1] for j in sorted(JOBS) if ready(j)],
                          "serve_env": {"OLLAMA_UUID": ENV.get("OLLAMA_UUID"), "ALLOWED_UUIDS": ENV.get("ALLOWED_UUIDS")}}, ensure_ascii=False, indent=1))
        (pid_dir / "scheduler8.pid").unlink(missing_ok=True)
        return
    for w in workers:
        w.start()
    log(f"scheduler start commit {sched_commit()} workers {[w.label() for w in workers]}")
    while True:
        with LOCK:
            try:
                for nj in load_jobs(JOBS_PATH):
                    if nj[1] not in STATE:
                        JOBS.append(nj)
                        STATE[nj[1]] = "pending"
                        log(f"job added {nj[1]}")
            except Exception as error:  # noqa: BLE001
                log(f"jobs reload failed: {error}")
            pending = [j for j in JOBS if STATE[j[1]] == "pending"]
        if not pending and all(w.job is None for w in workers):
            break
        busy_ollama = [w for w in workers if w.ollama and w.job is not None]
        if busy_ollama and ollama_loaded() and not STATE.get("_ollama_during_logged"):
            log(f"ollama model loaded DURING {busy_ollama[0].job[1]} on {busy_ollama[0].label()}: {ollama_loaded()} — 작업은 그대로 둠(결정 181)")
            STATE["_ollama_during_logged"] = True
        for w in sorted(workers, key=lambda w: w.ollama):
            if w.job is not None:
                continue
            cands = [j for j in sorted(JOBS) if ready(j)]
            pick = None
            if w.ollama:
                loaded = ollama_loaded()
                if loaded:
                    STATE.setdefault("_ollama_wait_since", time.time())
                    if not STATE.get("_ollama_wait_logged"):
                        log(f"ollama check {w.label()}: /api/ps not empty {loaded} — 작업 주지 않음, 다른 GPU부터(결정 181)")
                        STATE["_ollama_wait_logged"] = True
                    if time.time() - STATE["_ollama_wait_since"] > 1800 and not STATE.get("_ollama_30min"):
                        log(f"ollama check {w.label()}: 30분 넘게 모델이 내려가지 않음 — GPU 1 한 장으로 계속(결정 181, 보고 항목)")
                        STATE["_ollama_30min"] = True
                    continue
                STATE.pop("_ollama_wait_since", None)
                STATE.pop("_ollama_wait_logged", None)
                ollama_left = [j for j in JOBS if j[3] == "ollama" and STATE[j[1]] == "pending"]
                o_ready = [j for j in cands if j[3] == "ollama"]
                cooling = time.time() - STATE.get("_ollama_done_at", 0) < 3600 and bool(ollama_loaded())
                if o_ready:
                    pick = o_ready[0]
                elif not cooling and not ollama_loaded():
                    nonol = [j for j in cands if j[3] != "ollama" and (not ollama_left or j[4] <= 45)]
                    pick = nonol[0] if nonol else None
            else:
                nonol = [j for j in cands if j[3] != "ollama"]
                pick = nonol[0] if nonol else None
            if pick and w.ollama:
                log(f"ollama check before {pick[1]} on {w.label()}: /api/ps models = {ollama_loaded()} (빔 → 시작)")
            if pick:
                STATE[pick[1]] = "running"
                log(f"assign {pick[1]} -> {w.label()}")
                w.assign(pick)
        time.sleep(20)
    for w in workers:
        w.stop_server()
    log("scheduler end " + json.dumps({k: v for k, v in STATE.items() if not k.startswith("_")}))
    (pid_dir / "scheduler8.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
