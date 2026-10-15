# -*- coding: utf-8 -*-
"""pilot_005 학습 변형 셋 동시 학습과 후보 평가, 선택·중단 규칙(PLAN.md, PROTOCOL_v5, 결정 101–105).

    nohup /home/hwkim/sftdpo_work/hfvenv/bin/python sft_dpo_inventory/pilot_005/run_pilot005.py [--variants v1,v2,v3] > ... &

1. 사전 확인: PLAN 고정 표시, 코드 지문 791c4a68, 데이터·출발 adapter·PROTOCOL_v5 sha256, 출력 폴더가 없음.
2. 변형마다 스레드 하나: 배정 GPU(UUID로 고정, PLAN 4절)를 ``gpu_ok``(UUID·상태·메모리·다른 프로세스·Ollama 적재)로 확인하고 학습한다.
   끝나면 학습 기록(loss, step 시간, peak 메모리, adapter sha256)을 남기고 커밋·push한다.
   실패하면 출력 폴더를 ``ABORTED_<variant>_<시각>``으로 옮기고 기록한다. 다시 돌릴지는 사람이 원인을 보고 정한다(결정 105, 이 스크립트를 ``--variants``로 다시 실행).
3. 같은 스레드가 학습이 끝난 GPU에서 평가 일꾼이 된다(결정 105): 자기 변형의 셀부터, 그다음 다른 끝난 변형의 셀을 맡는다. 서버(serve5.sh, 포트 8500+GPU 번호)에는
   그때까지 끝난 adapter를 모두 LoRA로 올리고, 맡은 셀의 adapter가 없으면 서버를 내리고 새 목록으로 다시 띄운다. 서버마다 한 번에 셀 하나(동시 요청 8, run_cell5.py).
4. 셀이 모두 끝나면 서버를 내리고 셀을 커밋한 뒤 ``analyze_selection5.py``(선택·중단 규칙)를 돌려 커밋·push한다.
셀이나 서버가 실패하면 새 셀을 맡지 않고 멈춘다(돌던 셀은 끝까지 둔다). 다시 재는 것은 사람이 원인을 보고 정한다(PROTOCOL_v4 3절 재측정 규칙).
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"
WORK = Path("/home/hwkim/sftdpo_work/pilot_005")
VW = Path("/data/hwkim/sftdpo_work/pilot_005/vllm")
GPU_LIB = ROOT / "sft_dpo_inventory/pilot_003/gpu_lib.sh"
LOG = HERE / "runs.log"
GPUCHECK = HERE / "gpu_check.txt"
VARIANTS = {   # 변형 → (stage, config, GPU UUID, 평가할 checkpoint step)
    "v1": ("sft", "training/configs/qwen3_8b_t2pc_thinking_pilot005_v1_sft.yaml", "GPU-2445b100-70d8-e384-3a24-0249eeefc64d", (467, 934)),
    "v2": ("sft", "training/configs/qwen3_8b_t2pc_thinking_pilot005_v2_sft.yaml", "GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555", (934, 1401)),
    "v3": ("dpo", "training/configs/qwen3_8b_t2pc_thinking_pilot005_v3_dpo.yaml", "GPU-48f798cc-9437-50ac-d604-448bbad7b311", (97, 193)),
}
SHA = {
    "training/generated/thinking_pilot004_t2pc/sft_train.jsonl": "7cf221e6061d09ca78ffe6ba4936ae8a2bbff2b7090ddeae794baf08ea34f5db",
    "training/generated/thinking_pilot004_t2pc/dpo_train.jsonl": "6c52d0477d0a0aa4199bf57cfc27f544602e3abf1a5c6b6b87a896ca0099a96b",
    "training/generated/thinking_pilot004_t2pc/manifest.json": "ac7e7a7a03366f71184be8512dadb1dda223b76961db04b5db6ad71246789e1b",
    "/home/hwkim/sftdpo_work/pilot_004/checkpoints/sft/checkpoint-934/adapter_model.safetensors": "ca66b0173f16a46e578d239eea8f2b3c9e07bc20907060575c6a083ed8fc3319",
    "sft_dpo_inventory/vendor100_protocol/PROTOCOL_v5.md": "2de1264161a6171a42083a4d6f748ed346ecf77d5259d0c4a38dd8887c215e0f",
}
ENV = {**os.environ, "HF_HOME": "/home/hwkim/sftdpo_work/hf-cache", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
       "TOKENIZERS_PARALLELISM": "false", "PYTHONDONTWRITEBYTECODE": "1", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True"}
GIT_LOCK = threading.Lock()
STATE = threading.Lock()
status = {}            # variant → "training" | "done" | "failed"
adapters = {}          # label → adapter path (끝난 변형)
pending = []           # (variant, label, k) 아직 맡지 않은 셀
failed = threading.Event()


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"== {msg} {datetime.now().astimezone().isoformat(timespec='seconds')}\n")


def die(msg):
    log(msg)
    sys.exit(1)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def index_of(uuid):
    out = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid", "--format=csv,noheader"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        i, u = [x.strip() for x in line.split(",")]
        if u == uuid:
            return i
    return None


def gpu_ok(g, label):
    cmd = f'source {GPU_LIB}; P3={HERE}; gpu_ok {g} "{label}"'
    return subprocess.run(["bash", "-c", cmd], env=ENV).returncode == 0


def git(*args):
    return subprocess.run(["git", "-c", "user.name=Hyeongwoo Kim", "-c", "user.email=7829hw@gmail.com", *args], cwd=ROOT,
                          capture_output=True, text=True)


def commit(msg, paths):
    paths = [str(p) for p in paths] + [str(LOG), str(GPUCHECK)]
    body = msg + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG"
    with GIT_LOCK:
        for attempt in range(40):
            a = git("add", "--", *paths)
            c = git("commit", "-q", "-m", body, "--", *paths) if a.returncode == 0 else a
            if c.returncode == 0:
                break
            if "nothing to commit" in c.stdout + c.stderr or "no changes added" in c.stdout + c.stderr:
                log(f"commit skipped (nothing to commit): {msg}")
                return
            if "index.lock" not in c.stderr:
                log(f"STOP: commit failed: {msg}: {c.stderr.strip()[:300]}")
                failed.set()
                return
            time.sleep(15)
        else:
            log(f"STOP: commit failed after retries (index.lock): {msg}")
            failed.set()
            return
        for attempt in range(3):
            p = git("push", "-q", "origin", "geoflow/sft-dpo-t2pc")
            if p.returncode == 0:
                log(f"commit+push {git('rev-parse', '--short', 'HEAD').stdout.strip()}: {msg}")
                return
            time.sleep(20)
        log(f"push rejected (rule 14 manual): {msg}: {p.stderr.strip()[:300]}")


def train(v):
    stage, config, uuid, steps = VARIANTS[v]
    g = index_of(uuid)
    if g is None or not gpu_ok(g, f"pilot_005 train {v}"):
        log(f"STOP: {v} GPU {uuid} not usable")
        return None, False
    logs = HERE / "train_logs"
    out = WORK / "checkpoints" / v
    log(f"{v} train start (CUDA {g}, {uuid}) config {config}")
    (logs / f"{v}_gpu.txt").write_text(f"{g} {uuid}\n")
    smi = subprocess.Popen(["nvidia-smi", "-i", uuid, "--query-gpu=memory.used", "--format=csv,noheader,nounits", "-lms", "500"],
                           stdout=open(logs / f"{v}_nvidia_smi.txt", "w"), stderr=subprocess.STDOUT)
    t0 = time.time()
    with open(logs / f"{v}.log", "w") as lf:
        rc = subprocess.run([PY, "-m", f"training.train_{stage}", "--config", config], cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT,
                            env={**ENV, "CUDA_VISIBLE_DEVICES": g}).returncode
    smi.terminate()
    smi.wait()
    log(f"{v} train exit={rc} (CUDA {g}) {round((time.time() - t0) / 3600, 2)} h")
    if rc != 0:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if out.exists():
            out.rename(out.parent / f"ABORTED_{v}_{ts}")
        for f in logs.glob(f"{v}*"):
            f.rename(logs / f"ABORTED_{ts}_{f.name}")
        commit(f"train(pilot_005): {v} 학습 실패 기록(exit {rc}, ABORTED_{ts}, 다시 돌릴지는 원인 확인 뒤)", [logs])
        return g, False
    shutil.copy(WORK / "metrics" / f"{v}_profile.json", logs / f"{v}_profile.json")
    cks = sorted(out.glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[1]))
    state = json.loads((cks[-1] / "trainer_state.json").read_text())
    (logs / f"{v}_log_history.json").write_text(json.dumps(state["log_history"], indent=1))
    found = [int(c.name.split("-")[1]) for c in cks]
    use = [c for c in cks if int(c.name.split("-")[1]) in steps]
    if found != list(steps):
        log(f"WARN: {v} checkpoints {found} != planned {list(steps)}; evaluating only planned ones present")
    subprocess.run([PY, str(HERE / "train_summary5.py"), v, stage, *map(str, use)], cwd=ROOT, env=ENV, stdout=subprocess.DEVNULL, check=True)
    commit(f"train(pilot_005): {v} 학습 기록(checkpoint {', '.join(str(int(c.name.split('-')[1])) for c in use)}, adapter는 저장소 밖)", [logs])
    with STATE:
        for c in use:
            label = f"{v}_step{int(c.name.split('-')[1])}"
            adapters[label] = str(c / "policy") if stage == "dpo" else str(c)
            pending.extend((v, label, k) for k in (1, 2, 3, 4))
    return g, True


class Server:
    def __init__(self, g):
        self.g, self.port, self.loaded = g, 8500 + int(g), set()

    def stop(self):
        pf = VW / f"server_{self.port}.pid"
        if pf.exists():
            subprocess.run(["kill", pf.read_text().strip()])
            pf.unlink()
            for _ in range(60):
                time.sleep(5)
                used = subprocess.run(["nvidia-smi", "-i", self.g, "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                      capture_output=True, text=True).stdout.strip()
                if used.isdigit() and int(used) < 100:
                    break
            log(f"vllm server port {self.port} stopped")
        self.loaded = set()

    def ensure(self, label):
        if label in self.loaded:
            return True
        self.stop()
        with STATE:
            loras = dict(adapters)
        env = {**ENV, "LORAS": " ".join(f"{k}={p}" for k, p in sorted(loras.items()))}
        rc = subprocess.run(["bash", str(HERE / "serve5.sh"), self.g, str(self.port), "bf16", "fi"], cwd=ROOT, env=env).returncode
        if rc != 0:
            return False
        self.loaded = set(loras)
        log(f"vllm server port {self.port} GPU {self.g} loras {sorted(loras)}")
        return True


def evaluate(v, g):
    srv = Server(g)
    while not failed.is_set():
        with STATE:
            mine = [c for c in pending if c[0] == v]
            job = (mine or pending or [None])[0]
            if job:
                pending.remove(job)
            training = any(s == "training" for s in status.values())
        if job is None:
            if training:
                time.sleep(30)
                continue
            break
        _, label, k = job
        if not srv.ensure(label):
            log(f"STOP: server GPU {g} failed for {label}")
            failed.set()
            break
        log(f"cell {label} s{k} start port {srv.port} (GPU {g})")
        rc = subprocess.run([PY, str(HERE / "run_cell5.py"), "--port", str(srv.port), "--model", label, "--label", label, "--k", str(k),
                             "--concurrency", "8", "--out-dir", str(HERE / "runs")], cwd=ROOT, env=ENV,
                            stdout=open(LOG, "a"), stderr=subprocess.STDOUT).returncode
        if rc != 0:
            log(f"STOP: cell {label} s{k} failed (GPU {g})")
            failed.set()
            break
        log(f"cell {label} s{k} done port {srv.port}")
    srv.stop()


def worker(v):
    g, ok = train(v)
    with STATE:
        status[v] = "done" if ok else "failed"
    if g is not None and not failed.is_set():
        evaluate(v, g)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--variants", default="v1,v2,v3")
    args = p.parse_args()
    vs = args.variants.split(",")
    log(f"pilot_005 start variants {vs}")
    if "학습 시작 전 고정" not in (HERE / "PLAN.md").read_text(encoding="utf-8"):
        die("STOP: PLAN.md not fixed")
    fp = subprocess.run([PY, "-c", 'import execution_spec as e;print(e.code_fingerprint(".")["sha256"][:8])'], cwd=ROOT,
                        capture_output=True, text=True).stdout.strip()
    if fp != "791c4a68":
        die(f"STOP: fingerprint {fp}")
    for f, h in SHA.items():
        if sha(ROOT / f if not f.startswith("/") else f) != h:
            die(f"STOP: sha256 mismatch {f}")
    for v in vs:
        if (WORK / "checkpoints" / v).exists():
            die(f"STOP: {WORK / 'checkpoints' / v} exists")
    (HERE / "train_logs").mkdir(exist_ok=True)
    (HERE / "runs").mkdir(exist_ok=True)
    VW.mkdir(parents=True, exist_ok=True)
    with STATE:
        for v in vs:
            status[v] = "training"
    threads = [threading.Thread(target=worker, args=(v,)) for v in vs]
    for t in threads:
        t.start()
        time.sleep(20)   # 같은 시각의 모델 적재를 조금 어긋나게
    for t in threads:
        t.join()
    if failed.is_set():
        commit("eval(pilot_005): 후보 셀 일부(실패로 멈춤, runs.log 참고)", [HERE / "runs"])
        die("STOP: pilot_005 stopped on failure")
    commit("eval(pilot_005): 후보 셀 selection_v2 k=4(vLLM BF16 flashinfer LoRA, 동시 요청 8)", [HERE / "runs"])
    if any(s != "done" for s in status.values()):
        log(f"WARN: variants not done {status}; selection waits for the rerun")
        return
    rc = subprocess.run([PY, str(HERE / "analyze_selection5.py")], cwd=ROOT, env=ENV, stdout=open(HERE / "selection.log", "w"),
                        stderr=subprocess.STDOUT).returncode
    if rc != 0:
        die("STOP: selection analysis failed")
    sel = json.loads((HERE / "selection.json").read_text(encoding="utf-8"))
    sr = sel["stop_rule(decision 103)"]
    log(f"selected {sel['selected'] and sel['selected']['label']} stop_rule proceed={sr['proceed_to_vendor100']}")
    commit(f"eval(pilot_005): 후보 7개 비교·선택 {sel['selected'] and sel['selected']['label']}, 중단 규칙(결정 103) 진행={sr['proceed_to_vendor100']}",
           [HERE / "selection.json", HERE / "selection_table.md", HERE / "selection.log"])
    log("pilot_005 train/select done")


if __name__ == "__main__":
    main()
