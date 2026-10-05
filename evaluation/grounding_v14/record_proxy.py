# -*- coding: utf-8 -*-
"""Ollama 요청·응답 기록 프록시(진단용). 받은 요청을 그대로 Ollama로 넘기고, 요청 본문과 응답의 주요 필드를 JSONL로 남긴다.

    python evaluation/grounding_v14/record_proxy.py --listen 11500 --upstream http://localhost:11434 --log OUT.jsonl

애플리케이션이 실제로 보내는 요청(messages·options·think·keep_alive)과 서버 쪽 처리량(prompt_eval_count = 이번 요청에서 새로
계산한 prompt 토큰 수, load_duration)을 비교하려는 도구다. 동시 요청은 순서대로 기록되며, 각 기록에 받은 순서와 시각을 적는다.
"""
import argparse
import hashlib
import itertools
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

LOCK = threading.Lock()
#: Ollama 요청의 최대 대기. 평가·CLI의 chat timeout(300초)과 같게 둔다(--upstream-timeout).
UPSTREAM_TIMEOUT = 300.0
COUNTER = itertools.count(1)


def make_handler(upstream, log_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # 표준 출력 기록은 끈다
            return

        def _forward(self, method):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            seq = next(COUNTER)
            started = time.time()
            # 클라이언트(chat timeout)와 같은 시간에 Ollama 연결을 닫는다. 그래야 클라이언트가 포기한 생성이 서버에서
            # 계속 돌며 다음 요청을 막지 않는다(프록시가 없을 때와 같은 동작). 2026-10-05 첫 구현은 900초를 써서, B의 연속
            # 실행에서 버려진 재질의가 다음 질문을 timeout시켰다(runs/ops/b_proxy_artifact).
            try:
                response = httpx.request(method, upstream + self.path, content=body,
                                         headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
                                         timeout=UPSTREAM_TIMEOUT)
            except httpx.TimeoutException as error:
                self._log({"seq": seq, "t": started, "elapsed_s": round(time.time() - started, 3), "method": method,
                           "path": self.path, "status": None, "error": f"upstream {type(error).__name__}",
                           "request_sha256": hashlib.sha256(body).hexdigest() if body else None})
                self.close_connection = True
                return
            elapsed = time.time() - started
            try:
                self.send_response(response.status_code)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(response.content)))
                self.end_headers()
                self.wfile.write(response.content)
            except (BrokenPipeError, ConnectionResetError):
                pass   # 클라이언트가 먼저 끊었다. 기록은 남긴다.
            record = {"seq": seq, "t": started, "elapsed_s": round(elapsed, 3), "method": method, "path": self.path,
                      "status": response.status_code}
            if body:
                try:
                    request = json.loads(body)
                except ValueError:
                    request = None
                record["request_sha256"] = hashlib.sha256(body).hexdigest()
                if isinstance(request, dict):
                    record["request"] = request
            if self.path.startswith("/api/chat") or self.path.startswith("/api/generate"):
                try:
                    data = response.json()
                except ValueError:
                    data = {}
                message = data.get("message") or {}
                record["response"] = {k: data.get(k) for k in (
                    "model", "done_reason", "prompt_eval_count", "eval_count", "load_duration",
                    "prompt_eval_duration", "eval_duration", "total_duration")}
                record["response"]["content"] = message.get("content", data.get("response"))
                record["response"]["thinking_sha256"] = hashlib.sha256(
                    (message.get("thinking") or "").encode("utf-8")).hexdigest()
            self._log(record)

        def _log(self, record):
            with LOCK, open(log_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        def do_GET(self):
            self._forward("GET")

        def do_POST(self):
            self._forward("POST")

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen", type=int, default=11500)
    parser.add_argument("--upstream", default="http://localhost:11434")
    parser.add_argument("--log", required=True)
    parser.add_argument("--upstream-timeout", type=float, default=300.0)
    args = parser.parse_args()
    global UPSTREAM_TIMEOUT
    UPSTREAM_TIMEOUT = args.upstream_timeout
    server = ThreadingHTTPServer(("127.0.0.1", args.listen), make_handler(args.upstream.rstrip("/"), args.log))
    server.serve_forever()


if __name__ == "__main__":
    main()
