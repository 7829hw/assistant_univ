"""GPU 한 장(lane)에서 작업 목록을 차례로 돌린다(결정 114: 작업 하나 = GPU 하나). 커밋 고정 worktree에서 실행한다.

    python run_lane.py --jobs jobs.json --lane LANE --gpu INDEX --uuid UUID --main MAIN_REPO --port PORT

- 작업마다 시작 전에 host nvidia-smi로 그 GPU의 UUID·메모리(<100 MiB)·compute 프로세스(0개)를 확인하고, Ollama 컨테이너가 있고 이 GPU가
  Ollama GPU(48f798cc…)면 /api/ps가 비어야 시작한다. 확인 결과는 MAIN의 dissociation/gpu/gpu_check.jsonl에 남긴다.
- 작업 종류: "x12"(x12_score.py, HF), "train"(train_a11.py, cwd = worktree, 끝에 expect 파일 확인), "cells"(vLLM 서버를 serve_a11.sh로 띄우고 run_cell6x.py 셀들을 돌린 뒤 서버를 PID로 끈다).
- MAIN의 dissociation/gpu/timeline.jsonl에 시작·끝·상태·커밋·GPU를 한 줄씩 쓴다(flock).
- 이미 끝난 작업(출력의 완료 표시가 있음)은 건너뛴다.
"""
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

WT = Path(__file__).resolve().parents[3]
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
OLLAMA_UUID = "GPU-48f798cc-9437-50ac-d604-448bbad7b311"   # 결정 191
ALL_UUIDS = "GPU-2445b100-70d8-e384-3a24-0249eeefc64d GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555 GPU-48f798cc-9437-50ac-d604-448bbad7b311"
VW = Path("/data/hwkim/sftdpo_work/pilot_006_prep/vllm")
ENV = dict(os.environ, HF_HOME="/data/hwkim/sftdpo_work/hf-cache", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
           TOKENIZERS_PARALLELISM="false", PYTHONDONTWRITEBYTECODE="1", PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")


def now():
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def append(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)


def gpu_check(args, job_id, gdir):
    q = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout
    rows = {l.split(", ")[1]: l.split(", ") for l in q.strip().splitlines()}
    apps = subprocess.run(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory,process_name", "--format=csv,noheader"],
                          capture_output=True, text=True).stdout.strip().splitlines()
    mine = [a for a in apps if a.startswith(args.uuid)]
    ollama = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", "ollama"], capture_output=True, text=True).stdout.strip()
    ps = None
    if ollama == "true":
        ps = subprocess.run(["curl", "-s", "-m", "5", "localhost:11434/api/ps"], capture_output=True, text=True).stdout
    row = rows.get(args.uuid)
    ok = bool(row) and row[0].strip() == str(args.gpu) and int(row[2]) < 100 and not mine
    if ok and args.uuid == OLLAMA_UUID and ollama == "true":
        try:
            ok = len(json.loads(ps)["models"]) == 0
        except Exception:  # noqa: BLE001
            ok = False
    torch_uuid = subprocess.run([PY, "-c", "import torch;print('GPU-'+str(torch.cuda.get_device_properties(0).uuid))"],
                                capture_output=True, text=True, env=dict(ENV, CUDA_VISIBLE_DEVICES=str(args.gpu))).stdout.strip()
    ok = ok and torch_uuid == args.uuid
    append(gdir / "gpu_check.jsonl", {"at": now(), "job": job_id, "lane": args.lane, "gpu": args.gpu, "uuid": args.uuid, "row": row,
                                      "compute_apps_on_gpu": mine, "ollama_container_running": ollama or "absent", "ollama_ps": ps,
                                      "torch_uuid": torch_uuid, "ok": ok})
    return ok


def start_server(args, loras, gdir):
    env = dict(ENV, P3=str(gdir), OLLAMA_UUID=OLLAMA_UUID, ALLOWED_UUIDS=ALL_UUIDS, MAX_LORA_RANK="16", LORAS=loras)
    r = subprocess.run(["bash", str(WT / "sft_dpo_inventory/ablation_011/gpu/serve_a11.sh"), str(args.gpu), str(args.port), "bf16", "fi"],
                       env=env, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"server start failed: {r.stdout[-400:]} {r.stderr[-400:]}")
    return int((VW / f"server_{args.port}.pid").read_text().strip())


def stop_server(pid):
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(120):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(1)
    os.kill(pid, signal.SIGKILL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--lane", required=True)
    ap.add_argument("--gpu", type=int, required=True)
    ap.add_argument("--uuid", required=True)
    ap.add_argument("--main", required=True)
    ap.add_argument("--port", type=int, required=True)
    args = ap.parse_args()
    main_repo = Path(args.main)
    gdir = main_repo / "topic2_semantic_order/dissociation/gpu"
    commit = subprocess.run(["git", "-C", str(WT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    jobs = [j for j in json.loads(Path(args.jobs).read_text(encoding="utf-8"))["jobs"] if j["lane"] == args.lane]
    for j in jobs:
        done = main_repo / j["done_marker"]
        if done.exists():
            append(gdir / "timeline.jsonl", {"at": now(), "job": j["id"], "lane": args.lane, "event": "skip_done"})
            continue
        if not gpu_check(args, j["id"], gdir):
            append(gdir / "timeline.jsonl", {"at": now(), "job": j["id"], "lane": args.lane, "gpu": args.gpu, "uuid": args.uuid, "event": "STOP_gpu_check"})
            print(f"STOP gpu check failed before {j['id']}", flush=True)
            sys.exit(2)
        t0 = now()
        append(gdir / "timeline.jsonl", {"at": t0, "job": j["id"], "lane": args.lane, "gpu": args.gpu, "uuid": args.uuid, "commit": commit, "event": "start"})
        status, pid = "ok", None
        log = open(gdir / f"{j['id']}.log", "a", encoding="utf-8")
        try:
            if j["kind"] == "x12":
                cmd = [PY, str(WT / "topic2_semantic_order/dissociation/x12_score.py"), *[a.replace("{MAIN}", str(main_repo)) for a in j["args"]]]
                r = subprocess.run(cmd, env=dict(ENV, CUDA_VISIBLE_DEVICES=str(args.gpu)), stdout=log, stderr=subprocess.STDOUT)
                if r.returncode != 0:
                    status = f"fail rc={r.returncode}"
            elif j["kind"] == "train":
                cmd = [PY, str(WT / "sft_dpo_inventory/ablation_011/train/train_a11.py"), "--config", str(WT / j["config"])]
                r = subprocess.run(cmd, env=dict(ENV, CUDA_VISIBLE_DEVICES=str(args.gpu)), stdout=log, stderr=subprocess.STDOUT, cwd=str(WT))
                if r.returncode != 0 or not Path(j["expect"]).exists():
                    status = f"fail rc={r.returncode} expect={Path(j['expect']).exists()}"
            elif j["kind"] == "cells":
                pid = start_server(args, j["loras"], gdir)
                append(gdir / "timeline.jsonl", {"at": now(), "job": j["id"], "lane": args.lane, "event": "server_ready", "pid": pid,
                                                 "server_meta": str(VW / f"server_{args.port}.json")})
                for c in j["cells"]:
                    cmd = [PY, str(WT / "sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py"), "--port", str(args.port),
                           *[a.replace("{MAIN}", str(main_repo)).replace("{WT}", str(WT)) for a in c]]
                    r = subprocess.run(cmd, env=ENV, stdout=log, stderr=subprocess.STDOUT, cwd=str(WT))
                    if r.returncode != 0:
                        status = f"fail rc={r.returncode} cell {c}"
                        break
            else:
                status = f"unknown kind {j['kind']}"
        except Exception as e:  # noqa: BLE001
            status = f"error {e}"
        finally:
            if pid:
                stop_server(pid)
            log.close()
        if status == "ok":
            done.parent.mkdir(parents=True, exist_ok=True)
            done.write_text(json.dumps({"job": j["id"], "finished_at": now(), "commit": commit, "gpu": args.uuid}) + "\n")
        append(gdir / "timeline.jsonl", {"at": now(), "job": j["id"], "lane": args.lane, "gpu": args.gpu, "uuid": args.uuid, "started": t0,
                                         "event": "end", "status": status})
        if status != "ok":
            print(f"STOP {j['id']}: {status}", flush=True)
            sys.exit(1)
    append(gdir / "timeline.jsonl", {"at": now(), "lane": args.lane, "event": "lane_done"})
    print(json.dumps({"lane": args.lane, "done": True}), flush=True)


if __name__ == "__main__":
    main()
