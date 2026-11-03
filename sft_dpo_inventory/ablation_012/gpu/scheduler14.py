# -*- coding: utf-8 -*-
"""ablation_012 GPU 큐(결정 262): ``ablation_011/gpu/scheduler13.py``(그대로 둠)의 사본(규칙 15: 새 파일). scheduler13과 다른 것:

- 기록 위치 ``ablation_012/gpu``(runs.log·timeline.jsonl·worktrees.json·gpu_check.txt), 셀 ``ablation_012/cells``, 원문 ``training/generated/ablation_012/cells_raw``,
  PID ``scheduler14.pid``, runs.log 태그 ``[s14a12]``. 쓰지 않는 옛 작업 종류(j6·teacher·selfs·j13·train_diag·train_a7·cells)는 뺐다(작업 표는 모두 ``raw``).
- 서버: ``ablation_011/gpu/serve_a11.sh``(그대로, 고정 worktree 안의 파일). server 값 ``lora:<이름=경로 ...>``(rank 16), ``lora64:<...>``(soup, rank 64),
  ``base``(LoRA 자리는 serve 기본값 pilot_003 final, 요청은 ``--model base``로 LoRA 없이 — client_test_10000 base 셀과 같은 구성).
- (a) **잘림 다시 돌리기 자동**(PLAN_S 5절 = PLAN_A11 5절): 평가 작업이 ok로 끝나면 그 작업의 셀마다 ``pilot_007/results/completeness_B.cell``로 잘림·서버 오류를 세어
  rdev 셀(label이 ``_rdevv2``로 끝남)은 잘림 호출 ≥ 2 또는 서버 오류 행 ≥ 2, 그 밖의 셀은 잘림 또는 서버 오류 > 1%면, 원본을 ``cells/replaced/``·``cells_raw/replaced/``로 옮기고
  같은 명령(같은 seed)의 작업 ``R12-NN``(prio 0)을 바로 큐에 넣는다. 셀마다 한 번만(다시 돌린 셀이 또 걸려도 그대로). 기록 ``ablation_012/RERUNS_A12.json``.
- 학습 작업이 실패(exit ≠ 0)하면 출력 디렉터리를 ``<dir>.failed1``로 옮기고(지우지 않음) 같은 작업을 ``<id>-retry``로 한 번 더 넣는다(OOM·NaN 한 번 다시).
  retry가 있는 동안 그 학습을 기다리는 평가 작업은 건너뛰지 않는다.
- ``--deadline <ISO>``: 이 시각 뒤에는 **어떤 작업도** 새로 시작하지 않는다(skipped; 결정 262 "시작 후 22시간").
- (b) 큐가 비고 모든 작업이 끝나면 ``gpu/DONE``(요약 한 줄 JSON)을 쓰고 runs.log에 ``scheduler end``를 남긴다. 예외로 죽으면 ``gpu/DONE``에 ``"status": "crashed"``와 예외를 쓴다.
- 나머지(작업 하나 = GPU 하나, 고정 worktree, 작업 표 다시 읽기(20초), 우선순위 = (prio, id) 순, 실패 출력 ``ABORTED_``, 학습 전 host UUID·메모리·다른 프로세스·torch UUID 확인,
  Ollama GPU는 컨테이너가 돌고 있으면 /api/ps가 비어야 작업을 줌(없으면 server_down = 빈 것), 컨테이너에 손대지 않음)는 scheduler13과 같다.

    runtime/envs/hf/bin/python <worktree>/sft_dpo_inventory/ablation_012/gpu/scheduler14.py --jobs <MAIN>/sft_dpo_inventory/ablation_012/gpu/jobs_a12.json \
        --gpus <UUID ...> --ollama-uuid GPU-48f798cc-9437-50ac-d604-448bbad7b311 --deadline <ISO> [--dry-run]
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SCHED_WT = Path(__file__).resolve().parents[3]
MAIN = Path("/home/hwkim/assistant_univ")
A12 = MAIN / "sft_dpo_inventory/ablation_012"
G = A12 / "gpu"
TL = SCHED_WT / "sft_dpo_inventory/pilot_006_prep/gpu_data/timeline.py"
SERVE = SCHED_WT / "sft_dpo_inventory/ablation_011/gpu/serve_a11.sh"
READY = G / "ready"
WTROOT = Path("/data/hwkim/sftdpo_work/worktrees")
VW = Path("/data/hwkim/sftdpo_work/pilot_006_prep/vllm")
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
CELLS = A12 / "cells"
RAWP = MAIN / "training/generated/ablation_012/cells_raw"
RERUNS = A12 / "RERUNS_A12.json"
ARGV = sys.argv
OLLAMA_UUID = ARGV[ARGV.index("--ollama-uuid") + 1]
ALLOWED = ARGV[ARGV.index("--gpus") + 1:]
ALLOWED = ALLOWED[:next((i for i, a in enumerate(ALLOWED) if a.startswith("--")), len(ALLOWED))]
DRY = "--dry-run" in ARGV
DEADLINE = datetime.fromisoformat(ARGV[ARGV.index("--deadline") + 1]) if "--deadline" in ARGV else None
JOBS_PATH = ARGV[ARGV.index("--jobs") + 1]
ENV = {**os.environ, "OLLAMA_UUID": OLLAMA_UUID, "ALLOWED_UUIDS": " ".join(ALLOWED), "HF_HOME": "/data/hwkim/sftdpo_work/hf-cache", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
       "TOKENIZERS_PARALLELISM": "false", "PYTHONDONTWRITEBYTECODE": "1", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}
ENV.pop("LORAS", None)
LOCK = threading.RLock()
sys.path.insert(0, str(SCHED_WT / "sft_dpo_inventory/pilot_007/results"))
import completeness_B as CB  # noqa: E402

CB.CELLS = CELLS


def now():
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def log(msg):
    with LOCK, open(G / "runs.log", "a", encoding="utf-8") as f:
        f.write(f"== [s14a12] {msg} {now()}\n")


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def tl(job_id, kind, uuid, commit, start, end, status, note, outs=()):
    subprocess.run(["python3", str(TL), "--file", str(G / "timeline.jsonl"), "--id", job_id, "--kind", kind, "--uuid", uuid, "--commit", commit,
                    "--start", start, "--end", end, "--status", status, "--note", note, "--out", *[str(p) for p in outs]])


class Job:
    """작업 표 한 줄. cmd = 명령(문자열 목록, {WT}·{MAIN}·{PORT} 치환) 또는 cells = [{name, label, k, cmd}](명령을 && 로 잇는다)."""

    def __init__(self, j):
        self.raw = j
        self.prio, self.id, self.kind, self.server, self.est = j["prio"], j["id"], j["kind"], j["server"], j["est"]
        self.deps = j.get("deps", [])
        self.cells = j.get("cells")
        self.retry_of = j.get("retry_of")

    def key(self):
        return (self.prio, self.id)

    def commands(self, wt, port):
        sub = lambda x: str(x).replace("{WT}", str(wt)).replace("{MAIN}", str(MAIN)).replace("{PORT}", str(port))  # noqa: E731
        if self.cells:
            return [["bash", "-c", " && ".join(sub(c["cmd"]) for c in self.cells)]]
        return [[sub(x) for x in self.raw["cmd"]]]

    def outputs(self):
        if not self.cells:
            return []
        return [p for c in self.cells for p in (CELLS / f"{c['name']}.json", CELLS / f"{c['name']}.log", RAWP / f"{c['name']}_raw.jsonl")]


def load_jobs(path):
    return [Job(j) for j in json.loads(Path(path).read_text(encoding="utf-8"))["jobs"]]


JOBS = load_jobs(JOBS_PATH)
STATE = {j.id: "pending" for j in JOBS}
RETRIES = {}  # 학습 id -> retry id


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


def ollama_running():
    r = sh(["docker", "inspect", "-f", "{{.State.Running}}", "ollama"])
    return r.returncode == 0 and r.stdout.strip() == "true"


def ollama_loaded():
    if not ollama_running():  # gpu_lib7 gpu_ok와 같음: 컨테이너가 없거나 멈춤 = server_down = 빈 것
        return []
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


def rerun_needed(cell):
    label, k = cell["name"].rsplit("_s", 1)
    r = CB.cell(label, int(k))
    if not r.get("exists"):
        return False, r
    if label.endswith("_rdevv2"):
        need = (r.get("truncated_calls") or 0) >= 2 or r.get("server_error_rows", 0) >= 2
    else:
        need = bool(r["rerun"])
    return need, r


def enqueue_reruns(job):
    """(a) 평가 작업이 ok로 끝난 직후: 셀마다 다시 돌리기 규칙 검사 → 원본 옮기고 R12-NN 작업을 넣는다."""
    with LOCK:
        rec = json.loads(RERUNS.read_text(encoding="utf-8")) if RERUNS.exists() else {"rule": "PLAN_S 5절: rdev 잘림 ≥ 2 또는 서버 오류 ≥ 2, 그 밖 > 1%; 같은 seed 한 번, 원본 replaced/, 결과와 무관하게 교체", "reruns": {}}
        todo = []
        for c in job.cells:
            if c["name"] in rec["reruns"] or (CELLS / "replaced" / f"{c['name']}.json").exists():
                continue
            need, r = rerun_needed(c)
            if need:
                todo.append((c, r))
        if not todo:
            return
        n = 1 + sum(1 for j in JOBS if j.id.startswith("R12-"))
        rid = f"R12-{n:02d}"
        (CELLS / "replaced").mkdir(exist_ok=True)
        (RAWP / "replaced").mkdir(parents=True, exist_ok=True)
        for c, r in todo:
            for src, dst in ((CELLS / f"{c['name']}.json", CELLS / "replaced"), (CELLS / f"{c['name']}.log", CELLS / "replaced"), (RAWP / f"{c['name']}_raw.jsonl", RAWP / "replaced")):
                if src.exists():
                    shutil.move(str(src), str(dst / src.name))
            rec["reruns"][c["name"]] = {"job": rid, "of_job": job.id, "truncated_calls": r.get("truncated_calls"), "raw_lines": r.get("raw_lines"),
                                         "truncated_pct": r.get("truncated_pct"), "server_error_rows": r.get("server_error_rows"),
                                         "rule": "rdev ≥ 2" if c["name"].rsplit("_s", 1)[0].endswith("_rdevv2") else "> 1%", "original_sha256": r.get("sha256"),
                                         "moved_to": "cells/replaced/", "queued": now()}
        RERUNS.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        nj = Job({"id": rid, "type": "raw", "kind": "rerun_cells_a12", "server": job.server, "est": max(5, job.est * len(todo) // max(1, len(job.cells))), "prio": 0,
                  "deps": [], "cells": [c for c, _ in todo], "rerun_of": [c["name"] for c, _ in todo]})
        JOBS.append(nj)
        STATE[rid] = "pending"
        log(f"rerun queued {rid} for {[c['name'] for c, _ in todo]} (of {job.id})")


def queue_retry(job):
    with LOCK:
        if job.retry_of or job.id in RETRIES:
            return
        cfg = job.raw["cmd"][-1].replace("{WT}/", "")
        out_dir = None
        try:
            import yaml
            out_dir = yaml.safe_load((MAIN / cfg).read_text(encoding="utf-8"))["training"]["output_dir"]
        except Exception as error:  # noqa: BLE001
            log(f"retry {job.id}: output_dir not read ({error})")
        if out_dir and Path(out_dir).exists():
            dst = Path(out_dir + ".failed1")
            Path(out_dir).rename(dst)
            log(f"retry {job.id}: moved {out_dir} -> {dst} (지우지 않음)")
        rid = f"{job.id}-retry"
        nj = Job(dict(job.raw, id=rid, retry_of=job.id))
        JOBS.append(nj)
        STATE[rid] = "pending"
        RETRIES[job.id] = rid
        log(f"train retry queued {rid} (OOM·NaN 한 번 다시)")


class Worker(threading.Thread):
    def __init__(self, index, uuid):
        super().__init__(daemon=True)
        self.index, self.uuid, self.port = index, uuid, 8640 + index
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
        env = dict(ENV, P3=str(G), MAX_LORA_RANK="16")
        if kind.startswith("lora64:"):
            env["LORAS"], env["MAX_LORA_RANK"] = kind[len("lora64:"):], "64"
        elif kind.startswith("lora:"):
            env["LORAS"] = kind[len("lora:"):]
        elif kind != "base":
            raise RuntimeError(f"unknown server kind {kind}")
        r = subprocess.run(["bash", str(SERVE), str(self.index), str(self.port), "bf16", "fi"], env=env, cwd=str(SCHED_WT), capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"server start failed ({kind}): {r.stdout[-300:]} {r.stderr[-300:]}")
        self.server, self.server_pid = kind, int((VW / f"server_{self.port}.pid").read_text().strip())
        log(f"server ready {self.label()} kind {kind} pid {self.server_pid}")

    def clean(self, job_id):
        apps = gpu_apps(self.uuid)
        other = [p for p in apps if not (self.server_pid and descends(p, self.server_pid))]
        with LOCK, open(G / "gpu_check.txt", "a", encoding="utf-8") as f:
            f.write(f"## {now()} [s14] before {job_id} {self.label()} server {self.server} pid {self.server_pid}\n"
                    + sh(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory,process_name", "--format=csv,noheader"]).stdout
                    + "## ollama ps\n" + json.dumps(ollama_loaded()) + "\n")
        return other

    def preflight_train(self, job_id):
        used = int(sh(["nvidia-smi", "-i", self.uuid, "--query-gpu=memory.used", "--format=csv,noheader,nounits"]).stdout.strip() or 99999)
        procs = gpu_apps(self.uuid)
        tu = sh([PY, "-c", "import torch; print('GPU-' + str(torch.cuda.get_device_properties(0).uuid))"], env={**ENV, "CUDA_VISIBLE_DEVICES": str(self.index)}).stdout.strip()
        ok = used < 100 and not procs and tu == self.uuid and not (self.ollama and ollama_loaded())
        with LOCK, open(G / "gpu_check.txt", "a", encoding="utf-8") as f:
            f.write(f"## {now()} [s14] train preflight {job_id} {self.label()} used={used}MiB procs={procs} torch_uuid={tu} ollama_running={ollama_running()} "
                    f"ollama_models={ollama_loaded()} -> {'ok' if ok else 'REFUSED'}\n")
        log(f"train preflight {job_id} {self.label()} used={used}MiB procs={len(procs)} torch_uuid_match={tu == self.uuid} -> {'ok' if ok else 'REFUSED'}")
        if not ok:
            raise RuntimeError(f"train preflight failed on {self.label()}: used={used} procs={procs} torch={tu}")

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
            except Exception as error:  # noqa: BLE001
                log(f"worker error {self.label()} {job.id}: {error!r}")
                STATE[job.id] = "failed"
            finally:
                self.job, self.idle_since = None, time.time()

    def execute(self, job):
        start = now()
        commit = sched_commit()
        outs, wt, name, rc, note = job.outputs(), None, None, None, ""
        try:
            if job.server == "train":
                self.stop_server()
            elif self.server != job.server:
                self.stop_server()
                self.start_server(job.server)
            other = self.clean(job.id)
            if other:
                raise RuntimeError(f"other process on {self.label()}: {other}")
            if job.server == "train":
                self.preflight_train(job.id)
            elif self.server and (VW / f"server_{self.port}.json").exists():
                (G / f"server_{job.id}.json").write_text((VW / f"server_{self.port}.json").read_text(encoding="utf-8"), encoding="utf-8")
            wt, name = make_wt(commit, job.id)
            log(f"{job.id} start {self.label()} server {self.server} worktree {name}")
            env = dict(ENV)
            if job.server == "train":
                env["CUDA_VISIBLE_DEVICES"] = str(self.index)
            with open(G / f"{job.id}.log", "a", encoding="utf-8") as lg:
                for c in job.commands(wt, self.port):
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
        if rc == 0 and job.cells:
            try:
                enqueue_reruns(job)
            except Exception as error:  # noqa: BLE001
                log(f"rerun check failed for {job.id}: {error!r}")
        if rc != 0 and job.server == "train":
            queue_retry(job)
        with LOCK:
            tl(job.id, job.kind, self.uuid, commit, start, now(), status, (f"ablation_012 scheduler14, server {self.server}; " + note).strip(), outs)
            STATE[job.id] = "ok" if rc == 0 else "failed"
        log(f"{job.id} {status} {self.label()} {note}")


def skip(job, why):
    STATE[job.id] = "skipped"
    log(f"{job.id} skipped ({why})")
    tl(job.id, job.kind, "-", "-", now(), now(), "skipped", why[:300])


def ready(job):
    if STATE[job.id] != "pending":
        return False
    if DEADLINE and datetime.now(ZoneInfo("Asia/Seoul")) > DEADLINE:
        skip(job, f"deadline {DEADLINE.isoformat()} passed (결정 262: 시작 22시간 뒤 새 작업 없음)")
        return False
    if (READY / f"{job.id}.skip").exists():
        skip(job, (READY / f"{job.id}.skip").read_text(encoding="utf-8")[:300])
        return False
    for d in job.deps:
        if d.startswith("file:"):
            path, _, owner = d[5:].partition("|")
            if not Path(path).exists():
                owners = [owner] + ([RETRIES[owner]] if owner in RETRIES else [])
                if owner and all(STATE.get(o) in ("failed", "skipped") for o in owners):  # retry는 실패 표시 전에 큐에 들어간다(execute)
                    skip(job, f"{owners} not ok; {path} missing")
                return False
        elif d.startswith("ready:"):
            if not (READY / f"{d[6:]}.json").exists():
                return False
        elif STATE.get(d) != "ok":
            return False
    return True


def write_done(status, extra=None):
    counts = {}
    for k, v in STATE.items():
        counts[v] = counts.get(v, 0) + 1
    line = {"status": status, "at": now(), "jobs": len(STATE), "states": counts,
            "failed": sorted(k for k, v in STATE.items() if v == "failed"), "skipped": sorted(k for k, v in STATE.items() if v == "skipped"),
            "reruns": sorted(j.id for j in JOBS if j.id.startswith("R12-")), "train_retries": sorted(RETRIES.values())}
    if extra:
        line["error"] = extra
    (G / "DONE").write_text(json.dumps(line, ensure_ascii=False) + "\n", encoding="utf-8")
    log("DONE " + json.dumps(line, ensure_ascii=False))


def loop(workers):
    while True:
        with LOCK:
            try:
                for nj in load_jobs(JOBS_PATH):
                    if nj.id not in STATE:
                        JOBS.append(nj)
                        STATE[nj.id] = "pending"
                        log(f"job added {nj.id}")
            except Exception as error:  # noqa: BLE001
                log(f"jobs reload failed: {error}")
            pending = [j for j in JOBS if STATE[j.id] == "pending"]
        if not pending and all(w.job is None for w in workers):
            break
        for w in sorted(workers, key=lambda w: w.ollama):
            if w.job is not None:
                continue
            if w.ollama:
                loaded = ollama_loaded()
                if loaded:
                    if not STATE.get("_ollama_wait_logged"):
                        log(f"ollama check {w.label()}: /api/ps not empty {loaded} — 작업 주지 않음(결정 181·191)")
                        STATE["_ollama_wait_logged"] = True
                    continue
                STATE.pop("_ollama_wait_logged", None)
            with LOCK:
                cands = [j for j in sorted(JOBS, key=Job.key) if ready(j)]
            pick = cands[0] if cands else None
            if pick:
                if w.ollama:
                    log(f"ollama check before {pick.id} on {w.label()}: /api/ps models = {ollama_loaded()} (빔 → 시작)")
                STATE[pick.id] = "running"
                log(f"assign {pick.id} -> {w.label()}")
                w.assign(pick)
        time.sleep(20)


def main():
    pid_dir = Path("/data/hwkim/sftdpo_work/pids")
    pid_dir.mkdir(parents=True, exist_ok=True)
    WTROOT.mkdir(parents=True, exist_ok=True)
    READY.mkdir(parents=True, exist_ok=True)
    rows = [l.split(", ") for l in sh(["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"]).stdout.strip().splitlines()]
    workers = [Worker(int(i), u) for i, u in rows if u in ALLOWED]
    if DRY:
        print(json.dumps({"workers": [(w.index, w.uuid, w.port, "ollama_gpu" if w.ollama else "") for w in workers], "excluded": [u for _, u in rows if u not in ALLOWED],
                          "ollama_uuid": OLLAMA_UUID, "ollama_running": ollama_running(), "ollama_ps_models": ollama_loaded(),
                          "jobs_in_order": [(j.prio, j.id, j.server[:40], j.est) for j in sorted(JOBS, key=Job.key)],
                          "ready_now": [j.id for j in sorted(JOBS, key=Job.key) if all(not d.startswith("ready:") for d in j.deps) and ready(j)],
                          "deadline": DEADLINE.isoformat() if DEADLINE else None}, ensure_ascii=False, indent=1))
        return
    (pid_dir / "scheduler14.pid").write_text(str(os.getpid()))
    (G / "DONE").unlink(missing_ok=True)
    for w in workers:
        w.start()
    log(f"scheduler start commit {sched_commit()} workers {[w.label() for w in workers]} deadline {DEADLINE}")
    try:
        loop(workers)
    except BaseException as error:  # noqa: BLE001
        write_done("crashed", f"{type(error).__name__}: {error}\n{traceback.format_exc()[-1500:]}")
        raise
    for w in workers:
        w.stop_server()
    log("scheduler end " + json.dumps({k: v for k, v in STATE.items() if not k.startswith("_")}))
    write_done("ok")
    (pid_dir / "scheduler14.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
