# -*- coding: utf-8 -*-
"""path_repeat_001 셀 전환 확인(PLAN.md 4절). 판정 규칙은 바꾸지 않고 실행 조건만 지킨다.

    python cell_guard.py precheck --path ollama|hf --out PRE.json
    python cell_guard.py wait-empty --out WAIT.json            # Ollama keep_alive가 끝나 /api/ps가 빌 때까지
    python cell_guard.py watch --pid PID --rows RUN.jsonl --out GUARD.json --min-rate R

precheck(셀 시작 직전과 끝난 직후)
- 공통: host ``nvidia-smi``에 이 장비의 GPU(UUID ``GPU-d4308fbb…``)가 있고 compute 프로세스가 없다.
  사용 중 메모리가 기준선(4 MiB) + 200 MiB 이하다. Ollama ``/api/ps``가 비어 있다.
- ollama: 서버 0.40.1, ``qwen3:8b`` digest ``500a1f06…``, ``docker exec ollama nvidia-smi -L``에 같은 UUID.
- 하나라도 아니면 exit 1(셀을 시작하지 않는다).

wait-empty
- 모델을 내리는 호출, 서버 재시작, 컨테이너 조작을 하지 않는다. ``OllamaStateReset``은 문항 시작 전에 내리므로 마지막 문항의
  모델은 keep_alive(5분) 동안 남는다. 그것이 끝나 ``/api/ps``가 빌 때까지 기다린다. 420초 안에 비지 않으면 exit 1.

watch(Ollama 셀 측정 중, 측정 프로세스 PID를 지켜본다)
- 모델이 올라와 있는 동안 ``/api/ps``로 ``size_vram == size``(100% GPU)와 ``context_length == 40960``을 본다.
- 문항 기록마다 생성 속도 = 성공 호출의 ``Σ eval_count / Σ (duration_ms − load_duration_ms)``(초 단위)를 본다.
- ``--min-rate`` 미만인 문항, 100% GPU가 아님, context 길이가 다름 중 하나면 측정 프로세스를 즉시 SIGTERM으로 멈추고 exit 2.
  서버와 모델은 건드리지 않는다.
- 측정 프로세스가 끝나면 끝까지 본 기록으로 판단을 남긴다. GPU 확인을 끝내 하지 못했으면 exit 3.
"""
import argparse
import json
import os
import signal
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

HOST = "http://localhost:11434"
GPU = "GPU-d4308fbb-d17f-3609-676a-935c6072c831"
MODEL = "qwen3:8b"
DIGEST = "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"
VERSION = "0.40.1"
CONTEXT_LENGTH = 40960
BASELINE_MIB = 4
TOLERANCE_MIB = 200


def now():
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def sh(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        return f"error: {type(error).__name__}: {error}"
    return (p.stdout + p.stderr).strip()


def gpu_state():
    listing = sh(["nvidia-smi", "-L"])
    used = sh(["nvidia-smi", "-i", GPU, "--query-gpu=memory.used", "--format=csv,noheader,nounits"])
    apps = sh(["nvidia-smi", "-i", GPU, "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"])
    try:
        used_mib = int(used.strip())
    except ValueError:
        used_mib = None
    return {"nvidia_smi_L": listing, "memory_used_mib": used_mib, "compute_apps": apps}


def loaded_models():
    return httpx.get(f"{HOST}/api/ps", timeout=10).json().get("models") or []


def precheck(args):
    gpu = gpu_state()
    ps = loaded_models()
    out = {"checked_at": now(), "path": args.path, "gpu": gpu, "ollama_ps": ps,
           "gpu_present": GPU in gpu["nvidia_smi_L"], "no_compute_apps": not gpu["compute_apps"],
           "memory_at_baseline": gpu["memory_used_mib"] is not None
           and gpu["memory_used_mib"] <= BASELINE_MIB + TOLERANCE_MIB,
           "no_model_loaded": not ps}
    checks = ["gpu_present", "no_compute_apps", "memory_at_baseline", "no_model_loaded"]
    if args.path == "ollama":
        version = httpx.get(f"{HOST}/api/version", timeout=10).json().get("version")
        tags = {m.get("name"): m.get("digest") for m in httpx.get(f"{HOST}/api/tags", timeout=10).json()["models"]}
        container = sh(["docker", "exec", "ollama", "nvidia-smi", "-L"])
        out.update({"ollama_version": version, "version_ok": version == VERSION, "digest": tags.get(MODEL),
                    "digest_ok": tags.get(MODEL) == DIGEST, "container_nvidia_smi_L": container,
                    "container_sees_gpu": GPU in container})
        checks += ["version_ok", "digest_ok", "container_sees_gpu"]
    out["ok"] = all(out[name] for name in checks)
    out["failed_checks"] = [name for name in checks if not out[name]]
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"path": args.path, "memory_used_mib": gpu["memory_used_mib"], "ok": out["ok"],
                      "failed_checks": out["failed_checks"]}, ensure_ascii=False), flush=True)
    return 0 if out["ok"] else 1


def wait_empty(args):
    started = time.monotonic()
    out = {"started_at": now(), "polls": 0}
    while True:
        models = loaded_models()
        out["polls"] += 1
        if not models:
            out.update({"empty_at": now(), "waited_s": round(time.monotonic() - started, 1), "ok": True})
            break
        out["last_loaded"] = [{"name": m.get("name"), "expires_at": m.get("expires_at")} for m in models]
        if time.monotonic() - started > args.timeout:
            out.update({"gave_up_at": now(), "ok": False})
            break
        time.sleep(5)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out.get(k) for k in ("ok", "waited_s")}), flush=True)
    return 0 if out["ok"] else 1


def item_rate(record):
    """문항의 성공 호출 Σ eval_count / Σ 생성 시간(초). 셀 수 없으면 None."""
    tokens, ms = 0, 0.0
    for call in record.get("llm_calls") or []:
        gen_ms = (call.get("duration_ms") or 0) - (call.get("load_duration_ms") or 0)
        if call.get("failed") or call.get("replayed") or not call.get("eval_count") or gen_ms <= 0:
            continue
        tokens += call["eval_count"]
        ms += gen_ms
    return tokens / (ms / 1000) if ms > 0 else None


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(")")[-1].split()[0] != "Z"
    except OSError:
        return False


def watch(args):
    rows_path, out_path = Path(args.rows), Path(args.out)
    state = {"pid": args.pid, "min_rate": args.min_rate, "started_at": now(), "gpu_check": None, "records": 0,
             "rates": {}, "slow_items": [], "stopped": None}
    offset, buffer = 0, ""

    def save():
        out_path.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    def stop(reason):
        state["stopped"] = {"at": now(), "reason": reason}
        try:
            os.kill(args.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        save()
        print("STOP", reason, flush=True)
        return 2

    save()
    while True:
        running = alive(args.pid)
        if state["gpu_check"] is None:
            try:
                models = [m for m in loaded_models() if m.get("name") == MODEL or m.get("model") == MODEL]
            except httpx.HTTPError:
                models = []
            if models:
                m = models[0]
                state["gpu_check"] = {
                    "at": now(), "during_record": state["records"] + 1, "size": m.get("size"),
                    "size_vram": m.get("size_vram"), "context_length": m.get("context_length"),
                    "gpu_100": bool(m.get("size")) and m.get("size_vram") == m.get("size"),
                    "context_ok": m.get("context_length") == CONTEXT_LENGTH,
                    "ollama_ps": sh(["docker", "exec", "ollama", "ollama", "ps"]), "gpu": gpu_state()}
                save()
                print("GPU check", json.dumps({k: state["gpu_check"][k] for k in
                                               ("during_record", "gpu_100", "context_length")}), flush=True)
                if not state["gpu_check"]["gpu_100"]:
                    return stop("ollama ps PROCESSOR is not 100% GPU")
                if not state["gpu_check"]["context_ok"]:
                    return stop(f"context_length {m.get('context_length')} != {CONTEXT_LENGTH}")
        if rows_path.exists():
            with rows_path.open(encoding="utf-8") as handle:
                handle.seek(offset)
                chunk = handle.read()
                offset = handle.tell()
            buffer += chunk
            *lines, buffer = buffer.split("\n")
            for line in lines:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                state["records"] += 1
                rate = item_rate(record)
                if rate is not None:
                    state["rates"][record.get("id")] = round(rate, 1)
                    if args.min_rate is not None and rate < args.min_rate:
                        state["slow_items"].append({"id": record.get("id"), "tok_s": round(rate, 1)})
                save()
                if state["slow_items"]:
                    return stop(f"item generation rate below {args.min_rate} tok/s: {state['slow_items']}")
                if state["gpu_check"] is None and state["records"] >= 3:
                    return stop("could not confirm the model on GPU during the first 3 records")
        if not running:
            break
        time.sleep(1)
    values = list(state["rates"].values())
    state["finished_at"] = now()
    state["rate_median"] = round(statistics.median(values), 1) if values else None
    state["rate_min"] = min(values) if values else None
    save()
    if state["gpu_check"] is None:
        print("GPU check missing", flush=True)
        return 3
    print("OK", json.dumps({k: state[k] for k in ("records", "rate_median", "rate_min")}), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("precheck")
    p.add_argument("--path", choices=("ollama", "hf"), required=True)
    p.add_argument("--out", required=True)
    e = sub.add_parser("wait-empty")
    e.add_argument("--out", required=True)
    e.add_argument("--timeout", type=float, default=420.0)
    w = sub.add_parser("watch")
    w.add_argument("--pid", type=int, required=True)
    w.add_argument("--rows", required=True)
    w.add_argument("--out", required=True)
    w.add_argument("--min-rate", type=float, required=True)
    args = parser.parse_args()
    return {"precheck": precheck, "wait-empty": wait_empty, "watch": watch}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
