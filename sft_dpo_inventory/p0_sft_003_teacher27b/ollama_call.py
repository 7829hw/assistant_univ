# -*- coding: utf-8 -*-
"""27B teacher 호출 공통(IMPORT_AND_TEACHER_PLAN.md G3·G4, 결정 80).

- 호출 전 `/api/ps`가 비어 있는지 확인한다(최대 60초 대기). 비지 않으면 예외.
- `/api/chat`(stream 없음, `think: true`, `keep_alive: 0`)을 보내는 동안 2초마다 `/api/ps`를 읽어 size·size_vram·context_length를 기록한다.
- 결과: 응답 원문 필드 + guard 관측값.
"""
import hashlib
import threading
import time

import httpx

HOST = "http://localhost:11434"
MODEL = "qwen3.8:27b"
EXPECTED_DIGEST = "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813"


def ps():
    return httpx.get(f"{HOST}/api/ps", timeout=10).json().get("models") or []


def wait_empty(limit=60):
    t0 = time.time()
    while time.time() - t0 < limit:
        if not ps():
            return round(time.time() - t0, 1)
        time.sleep(1)
    raise RuntimeError("Ollama /api/ps가 비지 않는다(다른 모델이 올라와 있음)")


def chat(messages, options):
    waited = wait_empty()
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
        r = httpx.post(f"{HOST}/api/chat", timeout=3600, json={
            "model": MODEL, "messages": messages, "stream": False, "think": True, "options": options, "keep_alive": 0})
        status = r.status_code
        body = r.json()
    finally:
        stop.set()
        th.join(timeout=5)
    wall = time.perf_counter() - t0
    msg = body.get("message") or {}
    target = [o for o in obs if o["name"] and o["name"].startswith("qwen3.8:27b")]
    guard = {"waited_empty_s": waited, "ps_samples": len(target),
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
