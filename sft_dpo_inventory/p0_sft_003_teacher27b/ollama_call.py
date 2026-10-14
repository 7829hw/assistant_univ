# -*- coding: utf-8 -*-
"""27B teacher 호출 공통(IMPORT_AND_TEACHER_PLAN.md G3·G4, 결정 80).

- 호출 전 `/api/ps`가 비어 있는지 확인한다(최대 60초 대기). 비지 않으면 예외.
- `/api/chat`(stream 없음, `think: true`, `keep_alive: 0`)을 보내는 동안 2초마다 `/api/ps`를 읽어 size·size_vram·context_length를 기록한다.
- 결과: 응답 원문 필드 + guard 관측값.
"""
import hashlib
import subprocess
import threading
import time

import httpx

HOST = "http://localhost:11434"
MODEL = "qwen3.8:27b"
EXPECTED_DIGEST = "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813"
GPU_UUID = "GPU-d4308fbb-d17f-3609-676a-935c6072c831"
TIMEOUT_S = 3600   # G2_SUPPLEMENT.md 4절: 호출당 1회, 재시도 없음


def ps():
    return httpx.get(f"{HOST}/api/ps", timeout=10).json().get("models") or []


def compute_apps():
    r = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name", "--format=csv,noheader"],
                       capture_output=True, text=True, timeout=60)
    return [x for x in r.stdout.splitlines() if x.strip()]


def wait_empty(limit=60):
    """`/api/ps` 빈 상태와 GPU compute 프로세스 0(직전 runner 종료)을 함께 기다린다."""
    t0 = time.time()
    while time.time() - t0 < limit:
        if not ps() and not compute_apps():
            return round(time.time() - t0, 1)
        time.sleep(1)
    raise RuntimeError("Ollama /api/ps가 비지 않거나 GPU compute 프로세스가 남아 있다")


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout.strip()


def precheck():
    """호출 전 GPU·컨테이너 확인(G2_SUPPLEMENT.md 4절). 어기면 예외."""
    rc_h, host = sh(["nvidia-smi", "-L"])
    rc_c, cont = sh(["docker", "exec", "ollama", "nvidia-smi", "-L"])
    _, state = sh(["docker", "inspect", "ollama", "--format", "{{.State.Status}} {{.RestartCount}} {{.State.StartedAt}}"])
    out = {"host_gpu_visible": rc_h == 0 and GPU_UUID in host, "container_gpu_visible": rc_c == 0 and GPU_UUID in cont,
           "compute_apps": compute_apps(), "container_state": state}
    bad = [k for k in ("host_gpu_visible", "container_gpu_visible") if not out[k]]
    if out["compute_apps"]:
        bad.append("compute_apps_nonzero")
    if not state.startswith("running "):
        bad.append("container_not_running")
    if bad:
        raise RuntimeError(f"precheck 실패: {bad} {out}")
    return out


def chat(messages, options):
    waited = wait_empty()
    pre = precheck()
    obs, stop = [], threading.Event()

    def poll():
        while not stop.is_set():
            try:
                for m in ps():
                    obs.append({"name": m.get("name"), "size": m.get("size"), "size_vram": m.get("size_vram"),
                                "context_length": m.get("context_length"), "digest": m.get("digest")})
            except Exception:  # noqa: BLE001
                pass
            stop.wait(2)
    th = threading.Thread(target=poll, daemon=True)
    th.start()
    t0 = time.perf_counter()
    try:
        r = httpx.post(f"{HOST}/api/chat", timeout=TIMEOUT_S, json={
            "model": MODEL, "messages": messages, "stream": False, "think": True, "options": options, "keep_alive": 0})
        status = r.status_code
        body = r.json()
    except Exception as error:  # noqa: BLE001 - 시간 초과·연결 오류는 실패 호출로 기록한다(재시도 없음)
        status, body = None, {"error": f"{type(error).__name__}: {error}"}
    finally:
        stop.set()
        th.join(timeout=5)
    wall = time.perf_counter() - t0
    msg = body.get("message") or {}
    target = [o for o in obs if o["name"] and o["name"].startswith("qwen3.8:27b")]
    guard = {"precheck": pre, "waited_empty_s": waited, "ps_samples": len(target),
             "gpu_full": bool(target) and all(o["size"] and o["size_vram"] == o["size"] for o in target),
             "context_length": target[0]["context_length"] if target else None,
             "ps_digest": target[0]["digest"] if target else None}
    ev, ed = body.get("eval_count"), body.get("eval_duration")
    return {"http_status": status, "error": body.get("error"), "thinking": msg.get("thinking") or "",
            "content": msg.get("content") or "", "done_reason": body.get("done_reason"),
            "eval_count": ev, "prompt_eval_count": body.get("prompt_eval_count"),
            "total_duration": body.get("total_duration"), "load_duration": body.get("load_duration"),
            "prompt_eval_duration": body.get("prompt_eval_duration"), "eval_duration": ed,
            "tok_per_s": round(ev / (ed / 1e9), 2) if ev and ed else None, "wall_s": round(wall, 1),
            "message_keys": sorted(msg), "response_keys": sorted(body), "guard": guard,
            "content_sha256": hashlib.sha256((msg.get("content") or "").encode()).hexdigest()}
