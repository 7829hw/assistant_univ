# -*- coding: utf-8 -*-
"""녹화한 /api/chat 요청 본문을 서버 상태만 바꿔 다시 보낸다(진단용). 요청 본문은 바이트 단위로 같다.

    python evaluation/grounding_v14/replay_requests.py PROXY_LOG OUT.jsonl --model M

시나리오(질문 X, Y는 로그의 첫 계획 요청 두 개):
  S1 해제 → X → X → X        (적재 직후와 연속 반복)
  S2 해제 → Y → X            (다른 요청 직후의 X)
  S3 해제 → X                (적재 직후 재현)
각 응답의 내용·thinking hash, prompt_eval_count, load_duration을 기록한다.
"""
import argparse
import hashlib
import json
import time

import httpx

HOST = "http://localhost:11434"


def sha(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]


def unload(model):
    loaded = [m["name"] for m in httpx.get(f"{HOST}/api/ps", timeout=5).json().get("models") or []]
    for name in set(loaded) | {model}:
        httpx.post(f"{HOST}/api/generate", json={"model": name, "keep_alive": 0}, timeout=60)
    for _ in range(100):
        if not httpx.get(f"{HOST}/api/ps", timeout=5).json().get("models"):
            return
        time.sleep(0.2)
    raise RuntimeError("unload failed")


def send(body):
    data = httpx.post(f"{HOST}/api/chat", content=body, headers={"Content-Type": "application/json"}, timeout=900).json()
    message = data.get("message") or {}
    return {"content": sha(message.get("content")), "thinking": sha(message.get("thinking")),
            "prompt_eval_count": data.get("prompt_eval_count"), "eval_count": data.get("eval_count"),
            "load_ms": round((data.get("load_duration") or 0) / 1e6)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("log")
    parser.add_argument("out")
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    firsts, seen = [], set()
    for line in open(args.log, encoding="utf-8"):
        rec = json.loads(line)
        if rec["path"].startswith("/api/chat") and "request" in rec:
            users = [m for m in rec["request"]["messages"] if m["role"] == "user"]
            q = users[0]["content"]
            if q not in seen:
                seen.add(q)
                request = dict(rec["request"], model=args.model)  # 같은 messages·options를 다른 모델에 보낼 때
                firsts.append((q, json.dumps(request, ensure_ascii=False).encode("utf-8")))
    (qx, x), (qy, y) = firsts[1], firsts[0]
    results = []
    plan = [("S1", [("X", x), ("X", x), ("X", x)]), ("S2", [("Y", y), ("X", x)]), ("S3", [("X", x)])]
    for name, steps in plan:
        unload(args.model)
        for i, (label, body) in enumerate(steps, 1):
            r = {"scenario": name, "step": i, "request": label, **send(body)}
            results.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"X": qx, "Y": qy, "results": results}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
