# -*- coding: utf-8 -*-
"""pilot_006 준비 세션 2c 공유 GPU 큐(결정 114 D9, 124 F3, 137 G7, 144–147 K7–K10). ``scheduler6b.py``의 사본에서 작업 표·teacher 실행기·READY 위치만 바꿨다(규칙 15).
이 파일은 고정 커밋의 worktree에서 실행한다.

    /data/hwkim/sftdpo_work/runtime/envs/hf/bin/python <worktree>/sft_dpo_inventory/pilot_006_prep/gpu_data/scheduler6c.py

- 동작은 scheduler6과 같다: GPU마다 작업자 하나, 빈 GPU에 조건이 풀린 작업 중 우선순위가 가장 높은 것(20초마다), 작업마다 worktree를 만들고 끝나면 지움,
  출력은 본 저장소(절대 경로), ``timeline.jsonl``·``worktrees.json``·``gpu_check.txt``·``runs.log``(``[s2c]``).
- Ollama 작업(T0b, T0a, TEACH)은 Ollama GPU(48f798cc)에서만, 그 동안 그 GPU에 vLLM을 올리지 않는다. Ollama 작업이 남아 있는데 아직 준비되지 않았을 때만
  45분 이하 vLLM 작업을 붙인다. Ollama 작업 뒤에는 ``/api/ps``가 빌 때까지 vLLM을 올리지 않는다(직접 내리지 않음).
- TEACH는 T0b·T0a가 끝나고 ``pilot_006/teacher/t0v3_verdict.json``의 ``selected``가 v3a/v3b일 때만 준비된다(``sel:``). "none"이면 건너뛴다(결정 144).
- 스케줄러 PID는 ``/data/hwkim/sftdpo_work/pids/scheduler6c.pid``(결정 147 K10; 끝낼 때는 그 PID로만 kill).
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

SCHED_WT = Path(__file__).resolve().parents[3]
MAIN = Path("/home/hwkim/assistant_univ")
G = MAIN / "sft_dpo_inventory/pilot_006_prep/gpu"
READY = G / "session2c_ready"
WTROOT = Path("/data/hwkim/sftdpo_work/worktrees")
VW = Path("/data/hwkim/sftdpo_work/pilot_006_prep/vllm")
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
CELLS = MAIN / "sft_dpo_inventory/pilot_006_prep/cells"
RAWP = MAIN / "training/generated/pilot_006_prep/raw"
OLLAMA_UUID = "GPU-48f798cc-9437-50ac-d604-448bbad7b311"
ADAPTER_467 = "/data/hwkim/sftdpo_work/pilot_005/checkpoints/v1/checkpoint-467"
GOLD = {"sel": None, "holdout": "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml",
        "valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml"}
ENV = {**os.environ, "HF_HOME": "/data/hwkim/sftdpo_work/hf-cache", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
       "TOKENIZERS_PARALLELISM": "false", "PYTHONDONTWRITEBYTECODE": "1", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}
LOCK = threading.RLock()


def now():
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def log(msg):
    with LOCK, open(G / "runs.log", "a", encoding="utf-8") as f:
        f.write(f"== [s2c] {msg} {now()}\n")


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def cell(label, server_model, target, gold_key, sealed=False):
    """run_cell6v.py k=1..4 명령 목록과 출력."""
    def build(wt, port):
        cmds = []
        for k in (1, 2, 3, 4):
            c = [PY, f"{wt}/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6v.py", "--port", str(port), "--model", server_model, "--label", label,
                 "--k", str(k), "--concurrency", "8", "--grounding-target", target, "--out-dir", str(CELLS), "--raw-dir", str(RAWP)]
            if GOLD[gold_key]:
                c += ["--gold", GOLD[gold_key], "--all-items"]
            if sealed:
                c += ["--sealed"]
            cmds.append(c)
        return cmds
    outs = [p for k in (1, 2, 3, 4) for p in (CELLS / f"{label}_s{k}.json", CELLS / f"{label}_s{k}.log", RAWP / f"{label}_s{k}_raw.jsonl")]
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
    tag, out = {"T0b": ("t0v3b", "teacher_t0v3b"), "T0a": ("t0v3a", "teacher_t0v3a"), "TEACH": ("teach3", "teacher_v3")}[job]
    rec = MAIN / "sft_dpo_inventory/pilot_006/teacher"

    def build(wt, port):
        return [[PY, f"{wt}/sft_dpo_inventory/pilot_006/teacher/run_teacher6v3.py", "--main", str(MAIN), "--job", job]]
    return build, [MAIN / "training/generated/pilot_006" / out, rec / f"{tag}_summary.json"]


def selfs(job, inputs, target, samples=8, s32=False, round_seed="20261016", inputs_dir="inputs2c"):
    raw = MAIN / f"training/generated/pilot_006/self_2c/raw/{job}_raw.jsonl"
    man = MAIN / f"training/generated/pilot_006/self_2c/{job}_manifest.json"

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
JOBS = [  # (우선, ID, 종류, 서버, 예상 분, 의존, 정의) — 지시 2.2 표의 우선순위
    (1, "T0b", "teacher_v3b_check_27b", "ollama", 35, [], lambda: teacher("T0b")),
    (2, "T0a", "teacher_v3a_check_27b", "ollama", 35, [], lambda: teacher("T0a")),
    (3, "TEACH", "teacher_v3_collect_27b", "ollama", 300, ["sel:T0b,T0a"], lambda: teacher("TEACH")),
    (4, "S64P", "self_partial_s64_still_no_correct", B17, 150, [], lambda: selfs("S64P", "s64p", "partial", 64, True, "20261017")),
    (5, "S64F", "self_full_s64_still_no_correct", B17, 215, [], lambda: selfs("S64F", "s64f", "full", 64, True, "20261017")),
    (6, "J13", "self_both_and_first_w1_exception", B17, 15, [], j13),
]
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
        script = "serve6b.sh"
        env = dict(ENV)
        r = subprocess.run(["bash", f"{SCHED_WT}/sft_dpo_inventory/pilot_006_prep/gpu_data/{script}", str(self.index), str(self.port), "bf16", "fi"],
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
            subprocess.run(["python3", str(SCHED_WT / "sft_dpo_inventory/pilot_006_prep/gpu_data/timeline.py"), "--file", str(G / "timeline.jsonl"), "--id", job_id, "--kind", kind,
                            "--uuid", self.uuid, "--commit", commit, "--start", start, "--end", now(), "--status", status,
                            "--note", (f"session2c scheduler, server {self.server}; " + note).strip(), "--out", *[str(p) for p in outs]])
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
        log(f"{job_id} skipped (session2c_ready/{job_id}.skip)")
        subprocess.run(["python3", str(SCHED_WT / "sft_dpo_inventory/pilot_006_prep/gpu_data/timeline.py"), "--file", str(G / "timeline.jsonl"), "--id", job_id, "--kind", kind, "--uuid", "-",
                        "--commit", "-", "--start", now(), "--end", now(), "--status", "skipped",
                        "--note", (READY / f"{job_id}.skip").read_text(encoding="utf-8")[:300]])
        return False
    for d in deps:
        if d.startswith("sel:"):
            pre = d[4:].split(",")
            if any(STATE.get(x) not in ("ok", "failed") for x in pre):
                return False
            v = MAIN / "sft_dpo_inventory/pilot_006/teacher/t0v3_verdict.json"
            sel = json.loads(v.read_text(encoding="utf-8")).get("selected") if v.exists() else None
            if sel not in ("v3a", "v3b"):
                STATE[job_id] = "skipped"
                log(f"{job_id} skipped (T0'' selected={sel}, decision 144)")
                subprocess.run(["python3", str(SCHED_WT / "sft_dpo_inventory/pilot_006_prep/gpu_data/timeline.py"), "--file", str(G / "timeline.jsonl"), "--id", job_id, "--kind", kind, "--uuid", "-",
                                "--commit", "-", "--start", now(), "--end", now(), "--status", "skipped", "--note", f"T0'' selected={sel} (decision 144)"])
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
    (pid_dir / "scheduler6c.pid").write_text(str(os.getpid()))
    WTROOT.mkdir(parents=True, exist_ok=True)
    READY.mkdir(parents=True, exist_ok=True)
    rows = [l.split(", ") for l in sh(["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"]).stdout.strip().splitlines()]
    workers = [Worker(int(i), u) for i, u in rows]
    for w in workers:
        w.start()
    log(f"scheduler start commit {sched_commit()} workers {[w.label() for w in workers]}")
    while True:
        with LOCK:
            pending = [j for j in JOBS if STATE[j[1]] == "pending"]
        if not pending and all(w.job is None for w in workers):
            break
        for w in sorted(workers, key=lambda w: w.ollama):
            if w.job is not None:
                continue
            cands = [j for j in sorted(JOBS) if ready(j)]
            pick = None
            if w.ollama:
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
            if pick:
                STATE[pick[1]] = "running"
                log(f"assign {pick[1]} -> {w.label()}")
                w.assign(pick)
        time.sleep(20)
    for w in workers:
        w.stop_server()
    log("scheduler end " + json.dumps({k: v for k, v in STATE.items() if not k.startswith("_")}))
    (pid_dir / "scheduler6c.pid").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
