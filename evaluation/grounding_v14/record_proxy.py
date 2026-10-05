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
            response = httpx.request(method, upstream + self.path, content=body,
                                     headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
                                     timeout=900.0)
            elapsed = time.time() - started
            self.send_response(response.status_code)
            self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(response.content)))
            self.end_headers()
            self.wfile.write(response.content)
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
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.listen), make_handler(args.upstream.rstrip("/"), args.log))
    server.serve_forever()


if __name__ == "__main__":
    main()
