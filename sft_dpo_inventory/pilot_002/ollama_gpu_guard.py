# -*- coding: utf-8 -*-
"""결정 55: Ollama 셀이 GPU에서 도는지 확인한다. 판정 규칙은 바꾸지 않고 실행 조건만 지킨다.

    python ollama_gpu_guard.py precheck --out PRE.json
    python ollama_gpu_guard.py watch --pid PID --rows RUN.jsonl --model M --out GUARD.json [--min-rate 30]

precheck(셀 시작 전)
- ``docker exec ollama nvidia-smi -L``에 GPU 2(UUID ``GPU-a644de12…``)가 보인다.
- Ollama 버전, 올라간 모델 없음(``/api/ps``), host GPU 2에 다른 compute 프로세스 없음.
- 하나라도 아니면 exit 1(셀을 시작하지 않는다).

watch(셀 측정 중, 측정 프로세스 PID를 지켜본다)
- 첫 문항 동안 ``/api/ps``로 그 모델이 올라온 것을 잡아 ``size_vram == size``(``ollama ps``의 PROCESSOR 100% GPU)인지 본다.
  ``docker exec ollama ollama ps`` 출력과 host GPU 2 메모리도 함께 남긴다. 첫 문항 안에 잡지 못하면 다음 문항에서 다시 본다.
- 문항 기록이 하나 쌓일 때마다 호출별 생성 속도를 본다.
  - 평가 기록(``llm_calls``): ``eval_count / (duration_ms - load_duration_ms)``. 기록에 ``eval_duration``이 없어
    prompt 처리 시간이 분모에 들어간다(감사와 같은 계산, ``ollama_gpu_audit.md``).
  - 렌더링 확인 기록(``eval_tok_s``): ``eval_count / eval_duration``.
- 기준(``PLAN_DEVIATIONS.md`` 1번): 호출 하나라도 ``--min-rate``(30 tok/s) 미만이거나 PROCESSOR가 100% GPU가 아니면
  측정 프로세스를 즉시 멈추고(SIGTERM) exit 2. 컨테이너와 모델은 건드리지 않는다.
- 측정 프로세스가 끝나면 끝까지 본 기록으로 판단을 남긴다. GPU 확인을 끝내 하지 못했으면 exit 3.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

HOST = "http://localhost:11434"
GPU2 = "GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21"


def now():
    return datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")


def sh(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return (p.stdout + p.stderr).strip()


def gpu2_state():
    return {"memory_used": sh(["nvidia-smi", "-i", GPU2, "--query-gpu=memory.used", "--format=csv,noheader"]),
            "apps": sh(["nvidia-smi", "-i", GPU2, "--query-compute-apps=pid,process_name,used_memory",
                        "--format=csv,noheader"])}


def precheck(args):
    container = sh(["docker", "exec", "ollama", "nvidia-smi", "-L"])
    version = httpx.get(f"{HOST}/api/version", timeout=10).json().get("version")
    ps = httpx.get(f"{HOST}/api/ps", timeout=10).json()
    out = {"checked_at": now(), "container_nvidia_smi": container, "container_sees_gpu2": GPU2 in container,
           "ollama_version": version, "version_ok": version == args.version, "ps": ps,
           "no_model_loaded": not ps.get("models"), "host_gpu2": gpu2_state()}
    out["host_gpu2_free"] = not out["host_gpu2"]["apps"]
    out["ok"] = out["container_sees_gpu2"] and out["version_ok"] and out["no_model_loaded"] and out["host_gpu2_free"]
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("container_sees_gpu2", "ollama_version", "no_model_loaded", "host_gpu2_free",
                                          "ok")}, ensure_ascii=False))
    return 0 if out["ok"] else 1


def rates(record):
    if "llm_calls" in record:
        label = record.get("id")
        for k, call in enumerate(record.get("llm_calls") or []):
            gen_ms = (call.get("duration_ms") or 0) - (call.get("load_duration_ms") or 0)
            if call.get("failed") or call.get("replayed") or not call.get("eval_count") or gen_ms <= 0:
                continue
            yield f"{label}#{k}", call["eval_count"] / (gen_ms / 1000)
    elif record.get("eval_tok_s") is not None:
        yield record.get("id"), record["eval_tok_s"]


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # 끝났지만 거둬지지 않은 프로세스(zombie)는 끝난 것으로 본다.
    try:
        return Path(f"/proc/{pid}/stat").read_text().split(")")[-1].split()[0] != "Z"
    except OSError:
        return False


def watch(args):
    rows_path, out_path = Path(args.rows), Path(args.out)
    state = {"model": args.model, "pid": args.pid, "min_rate": args.min_rate, "started_at": now(),
             "gpu_check": None, "records": 0, "calls": 0, "min_rate_seen": None, "slow_calls": [], "stopped": None}
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
                models = [m for m in httpx.get(f"{HOST}/api/ps", timeout=10).json().get("models") or []
                          if m.get("name") == args.model or m.get("model") == args.model]
            except httpx.HTTPError:
                models = []
            if models:
                m = models[0]
                state["gpu_check"] = {"at": now(), "during_record": state["records"] + 1, "size": m.get("size"),
                                      "size_vram": m.get("size_vram"),
                                      "gpu_100": bool(m.get("size")) and m.get("size_vram") == m.get("size"),
                                      "ollama_ps": sh(["docker", "exec", "ollama", "ollama", "ps"]),
                                      "host_gpu2": gpu2_state()}
                save()
                print("GPU check", json.dumps({k: state["gpu_check"][k] for k in ("during_record", "gpu_100")}),
                      flush=True)
                if not state["gpu_check"]["gpu_100"]:
                    return stop("ollama ps PROCESSOR is not 100% GPU")
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
                for label, rate in rates(record):
                    state["calls"] += 1
                    state["min_rate_seen"] = round(rate if state["min_rate_seen"] is None else
                                                   min(rate, state["min_rate_seen"]), 1)
                    if rate < args.min_rate:
                        state["slow_calls"].append({"call": label, "tok_s": round(rate, 1)})
                save()
                if state["slow_calls"]:
                    return stop(f"generation rate below {args.min_rate} tok/s: {state['slow_calls']}")
                if state["gpu_check"] is None and state["records"] >= 3:
                    return stop("could not confirm the model on GPU during the first 3 records")
        if not running:
            break
        time.sleep(1)
    state["finished_at"] = now()
    save()
    if state["gpu_check"] is None:
        print("GPU check missing", flush=True)
        return 3
    print("OK", json.dumps({k: state[k] for k in ("records", "calls", "min_rate_seen")}), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("precheck")
    p.add_argument("--out", required=True)
    p.add_argument("--version", default="0.35.1")
    w = sub.add_parser("watch")
    w.add_argument("--pid", type=int, required=True)
    w.add_argument("--rows", required=True)
    w.add_argument("--model", required=True)
    w.add_argument("--out", required=True)
    w.add_argument("--min-rate", type=float, default=30.0)
    args = parser.parse_args()
    return precheck(args) if args.cmd == "precheck" else watch(args)


if __name__ == "__main__":
    sys.exit(main())
