# -*- coding: utf-8 -*-
"""path_repeat_001 셀 전환 확인(PLAN.md 4절). 판정 규칙은 바꾸지 않고 실행 조건만 지킨다.

    python cell_guard.py precheck --path ollama|hf --out PRE.json
    python cell_guard.py wait-empty --out WAIT.json            # Ollama keep_alive가 끝나 /api/ps가 빌 때까지
    python cell_guard.py watch --pid PID --rows RUN.jsonl --out GUARD.json --min-rate R
    python cell_guard.py precheck --path ollama --resident --out PRE.json   # 상주 run(결정 62): 모델이 올라와 있어야 한다
    python cell_guard.py warmup --out WARMUP.json --min-rate R              # 상주 run 시작 전 1회(판정 무관)
    python cell_guard.py residency --pid RUN_PID --out RESIDENCY.json      # 상주 run 전체 동안 unload·reload 감시

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

상주 실행(결정 62, 2026-10-12): multi-cell run에서는 모델을 한 번 올리고 run이 끝날 때까지 내리지 않는다.
- ``precheck --resident``: 빈 GPU 대신 목표 모델이 올라와 있고 100% GPU·context 40960이며 GPU의 compute 프로세스가 Ollama
  runner뿐인지 본다. 버전·digest·컨테이너 GPU 검사는 같다. 셀 사이에 ``wait-empty``를 쓰지 않는다.
- ``warmup``: 판정에 쓰지 않는 짧은 chat 호출(harness와 같은 options: num_ctx·think를 넣지 않음, 생성 상한만)을 보내 모델을
  올리고, 마지막 호출의 생성 속도(eval_count/eval_duration)가 ``--min-rate`` 이상이고 100% GPU인지 본다. 모델을 내리지 않는다.
- ``residency``: run 프로세스(``--pid``)가 끝날 때까지 ``/api/ps``와 GPU compute 프로세스를 주기적으로 보고, 모델이 사라진
  횟수(unload), 다시 올라오거나 runner PID가 바뀐 횟수(reload), 컨테이너 StartedAt 변화(restart)를 기록한다. 모델을 부르지 않는다.
- chat 요청에는 keep_alive가 없어(ollama_client.py, code fingerprint 범위) 서버 기본 keep_alive(5분)가 적용된다. 셀 사이 간격을
  짧게 두는 것으로 상주를 유지하고, 실제 상주 여부는 ``residency`` 기록으로 확인한다.
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
# 기본은 0.40.1. 컨테이너 버전이 바뀐 run은 계획 기록과 함께 CELL_GUARD_OLLAMA_VERSION으로 기대 버전을 지정한다(ab_p0_3, 2026-10-12).
VERSION = os.environ.get("CELL_GUARD_OLLAMA_VERSION", "0.40.1")
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


def target_model(ps):
    found = [m for m in ps if m.get("name") == MODEL or m.get("model") == MODEL]
    return found[0] if found else None


def ollama_runner_only(apps):
    """GPU compute 프로세스가 모두 Ollama runner인가(상주 run에서 다른 프로세스가 GPU를 쓰지 않는지)."""
    lines = [line for line in (apps or "").splitlines() if line.strip()]
    return bool(lines) and all("ollama" in line or "llama" in line for line in lines)


def runner_pids(apps):
    return sorted(line.split(",")[0].strip() for line in (apps or "").splitlines()
                  if line.strip() and ("ollama" in line or "llama" in line))


def container_started_at():
    return sh(["docker", "inspect", "ollama", "--format", "{{.State.StartedAt}}"])


def precheck(args):
    gpu = gpu_state()
    ps = loaded_models()
    out = {"checked_at": now(), "path": args.path, "resident": bool(getattr(args, "resident", False)), "gpu": gpu,
           "ollama_ps": ps, "gpu_present": GPU in gpu["nvidia_smi_L"]}
    if out["resident"]:
        m = target_model(ps) or {}
        out.update({"model_resident": bool(m), "resident_gpu_100": bool(m.get("size")) and m.get("size_vram") == m.get("size"),
                    "resident_context_ok": m.get("context_length") == CONTEXT_LENGTH,
                    "only_one_model": len(ps) == 1, "compute_apps_ollama_only": ollama_runner_only(gpu["compute_apps"]),
                    "runner_pids": runner_pids(gpu["compute_apps"]), "container_started_at": container_started_at()})
        checks = ["gpu_present", "model_resident", "resident_gpu_100", "resident_context_ok", "only_one_model",
                  "compute_apps_ollama_only"]
    else:
        out.update({"no_compute_apps": not gpu["compute_apps"],
                    "memory_at_baseline": gpu["memory_used_mib"] is not None
                    and gpu["memory_used_mib"] <= BASELINE_MIB + TOLERANCE_MIB,
                    "no_model_loaded": not ps})
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


def warmup(args):
    """판정에 쓰지 않는 warm-up chat 호출. 모델을 올리고 속도·GPU를 확인한다. 모델을 내리지 않는다."""
    out = {"started_at": now(), "container_started_at": container_started_at(), "calls": []}
    for index in range(args.calls):
        payload = {"model": MODEL, "stream": False, "options": {"num_predict": args.num_predict},
                   "messages": [{"role": "user", "content": "warm-up입니다. 1부터 100까지 쉼표로 이어서 세어 주세요."}]}
        started = time.monotonic()
        try:
            r = httpx.post(f"{HOST}/api/chat", json=payload, timeout=600).json()
        except httpx.HTTPError as error:
            out["calls"].append({"index": index, "error": f"{type(error).__name__}: {error}"[:300]})
            break
        eval_ns = r.get("eval_duration") or 0
        out["calls"].append({"index": index, "at": now(), "wall_s": round(time.monotonic() - started, 2),
                             "load_s": round((r.get("load_duration") or 0) / 1e9, 2), "eval_count": r.get("eval_count"),
                             "tok_s": round(r["eval_count"] / (eval_ns / 1e9), 1) if eval_ns and r.get("eval_count") else None})
    m = target_model(loaded_models()) or {}
    gpu = gpu_state()
    last = out["calls"][-1] if out["calls"] else {}
    out.update({"finished_at": now(), "model_loaded_at": out["calls"][0].get("at") if out["calls"] else None,
                "gpu_100": bool(m.get("size")) and m.get("size_vram") == m.get("size"),
                "context_ok": m.get("context_length") == CONTEXT_LENGTH, "runner_pids": runner_pids(gpu["compute_apps"]),
                "ollama_ps": sh(["docker", "exec", "ollama", "ollama", "ps"]), "min_rate": args.min_rate,
                "rate_ok": (last.get("tok_s") or 0) >= args.min_rate})
    out["ok"] = out["gpu_100"] and out["context_ok"] and out["rate_ok"] and len(out["calls"]) == args.calls
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"ok": out["ok"], "rates": [c.get("tok_s") for c in out["calls"]],
                      "gpu_100": out["gpu_100"], "context_ok": out["context_ok"]}), flush=True)
    return 0 if out["ok"] else 1


def residency(args):
    """run 프로세스가 끝날 때까지 상주 여부를 기록한다. 모델·서버·컨테이너를 건드리지 않는다."""
    out_path = Path(args.out)
    state = {"pid": args.pid, "started_at": now(), "container_started_at_start": container_started_at(),
             "polls": 0, "poll_errors": 0, "loaded_polls": 0, "unloaded_polls": 0,
             "runner_pids_seen": [], "events": [], "unload_events": 0, "reload_events": 0}
    loaded_before, pids_before = None, None

    def save():
        out_path.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    while alive(args.pid):
        try:
            m = target_model(loaded_models())
        except httpx.HTTPError:
            state["poll_errors"] += 1
            time.sleep(args.interval)
            continue
        pids = runner_pids(gpu_state()["compute_apps"]) if m else []
        state["polls"] += 1
        state["loaded_polls" if m else "unloaded_polls"] += 1
        for pid in pids:
            if pid not in state["runner_pids_seen"]:
                state["runner_pids_seen"].append(pid)
        if loaded_before is True and not m:
            state["unload_events"] += 1
            state["events"].append({"at": now(), "event": "unload"})
        if loaded_before is False and m:
            state["reload_events"] += 1
            state["events"].append({"at": now(), "event": "reload"})
        elif m and pids_before and pids and pids != pids_before:
            state["reload_events"] += 1
            state["events"].append({"at": now(), "event": "runner_pid_changed", "from": pids_before, "to": pids})
        if loaded_before is None:
            state["model_loaded_at_start"] = bool(m)
        loaded_before = bool(m)
        if pids:
            pids_before = pids
        if state["polls"] % 12 == 1:
            save()
        time.sleep(args.interval)
    state["finished_at"] = now()
    state["container_started_at_end"] = container_started_at()
    state["container_restart"] = state["container_started_at_end"] != state["container_started_at_start"]
    state["ok"] = (state.get("model_loaded_at_start") is True and state["unload_events"] == 0
                   and state["reload_events"] == 0 and not state["container_restart"])
    save()
    print(json.dumps({k: state.get(k) for k in ("ok", "unload_events", "reload_events", "container_restart",
                                                  "polls")}), flush=True)
    return 0 if state["ok"] else 4


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
    p.add_argument("--resident", action="store_true", help="상주 run(결정 62): 목표 모델이 올라와 있어야 한다")
    u = sub.add_parser("warmup")
    u.add_argument("--out", required=True)
    u.add_argument("--min-rate", type=float, required=True)
    u.add_argument("--calls", type=int, default=2)
    u.add_argument("--num-predict", type=int, default=256)
    r = sub.add_parser("residency")
    r.add_argument("--pid", type=int, required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--interval", type=float, default=5.0)
    e = sub.add_parser("wait-empty")
    e.add_argument("--out", required=True)
    e.add_argument("--timeout", type=float, default=420.0)
    w = sub.add_parser("watch")
    w.add_argument("--pid", type=int, required=True)
    w.add_argument("--rows", required=True)
    w.add_argument("--out", required=True)
    w.add_argument("--min-rate", type=float, required=True)
    args = parser.parse_args()
    return {"precheck": precheck, "wait-empty": wait_empty, "watch": watch, "warmup": warmup,
            "residency": residency}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
