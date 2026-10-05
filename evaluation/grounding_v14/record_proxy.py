# -*- coding: utf-8 -*-
"""Ollama 요청·응답 기록 프록시(진단용). 받은 요청을 그대로 Ollama로 넘기고, 요청 본문과 응답의 주요 필드를 JSONL로 남긴다.

    python evaluation/grounding_v14/record_proxy.py --listen 11500 --upstream http://localhost:11434 --log OUT.jsonl

애플리케이션이 실제로 보내는 요청(messages·options·think·keep_alive)과 서버 쪽 처리량(prompt_eval_count = 이번 요청에서 새로
계산한 prompt 토큰 수, load_duration)을 비교하려는 도구다. 동시 요청은 순서대로 기록되며, 각 기록에 받은 순서와 시각을 적는다.

연결 종료 전달(무엇을 보장하는가):
- 클라이언트가 응답을 받기 전에 연결을 끊으면(timeout·중단), 프록시는 그것을 약 POLL_INTERVAL 안에 감지해 upstream 연결을
  바로 닫는다. Ollama는 연결이 끊긴 요청의 생성을 멈춘다. 프록시가 없을 때와 같은 동작을 노린 것이다.
  (감지 방법: 응답을 기다리는 동안 클라이언트 소켓이 EOF·reset이 되었는지 확인한다.)
- 클라이언트가 끊지 않아도 upstream 대기는 UPSTREAM_TIMEOUT(기본 300초)을 넘지 않는다. 이것은 상한일 뿐이며 연결 종료 전달과는
  다른 보장이다.
- 보장하지 않는 것: Ollama가 연결 종료를 받은 뒤 생성을 실제로 멈추기까지의 시간, 프록시 프로세스 자체가 죽었을 때의 동작.

기록(2026-10-05): 첫 구현은 upstream timeout 900초에 종료 전달이 없어, B의 연속 실행에서 버려진 재질의가 다음 질문을
timeout시켰다(grounding_v14 runs/ops/b_proxy_artifact). 두 번째 구현(B W1·W3 재측정에 사용)은 upstream timeout만 300초로 맞췄다.
종료 전달은 grounding_v15에서 넣었고 tests/test_record_proxy.py가 짧은 timeout의 가짜 서버로 확인한다.
"""
import argparse
import hashlib
import http.client
import itertools
import json
import select
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOCK = threading.Lock()
#: Ollama 요청의 최대 대기(상한). 평가·CLI의 chat timeout(300초)과 같게 둔다(--upstream-timeout).
UPSTREAM_TIMEOUT = 300.0
#: 응답을 기다리는 동안 클라이언트 연결 종료를 확인하는 간격(초).
POLL_INTERVAL = 0.05
COUNTER = itertools.count(1)


def _client_disconnected(sock):
    """응답을 기다리는 중인 클라이언트 소켓이 닫혔는가. 읽을 것이 있는데 EOF(b"")거나 reset이면 닫힌 것이다."""
    try:
        readable, _, _ = select.select([sock], [], [], 0)
        if not readable:
            return False
        return sock.recv(1, socket.MSG_PEEK) == b""
    except (ConnectionResetError, OSError, ValueError):
        return True


def make_handler(upstream, log_path):
    target = urllib.parse.urlsplit(upstream)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # 표준 출력 기록은 끈다
            return

        def _log(self, record):
            with LOCK, open(log_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        def _upstream(self, method, body):
            """upstream 요청을 작업 스레드에서 보내고, 그동안 클라이언트 연결 종료를 감시한다."""
            connection = http.client.HTTPConnection(target.hostname, target.port, timeout=UPSTREAM_TIMEOUT)
            result = {}

            def work():
                try:
                    connection.request(method, self.path, body=body,
                                       headers={"Content-Type": self.headers.get("Content-Type", "application/json")})
                    response = connection.getresponse()
                    result["status"] = response.status
                    result["content_type"] = response.getheader("Content-Type", "application/json")
                    result["content"] = response.read()
                except Exception as error:  # noqa: BLE001 - 기록으로 남긴다
                    result["error"] = error
                    connection.close()   # 상한 초과·오류에서도 upstream 연결을 바로 닫는다(생성을 멈추게)

            worker = threading.Thread(target=work, daemon=True)
            worker.start()
            while worker.is_alive():
                worker.join(POLL_INTERVAL)
                if worker.is_alive() and _client_disconnected(self.connection):
                    result["client_disconnected"] = True
                    try:
                        if connection.sock is not None:
                            connection.sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    connection.close()
                    worker.join(5)
                    break
            return result

        def _forward(self, method):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            seq = next(COUNTER)
            started = time.time()
            result = self._upstream(method, body)
            elapsed = time.time() - started
            record = {"seq": seq, "t": started, "elapsed_s": round(elapsed, 3), "method": method, "path": self.path,
                      "status": result.get("status")}
            if body:
                record["request_sha256"] = hashlib.sha256(body).hexdigest()
                try:
                    request = json.loads(body)
                except ValueError:
                    request = None
                if isinstance(request, dict):
                    record["request"] = request
            if result.get("client_disconnected"):
                record["error"] = "client disconnected; upstream closed"
                self.close_connection = True
                self._log(record)
                return
            if "error" in result:
                kind = "upstream timeout" if isinstance(result["error"], (socket.timeout, TimeoutError)) else "upstream error"
                record["error"] = f"{kind}: {type(result['error']).__name__}"
                self.close_connection = True
                self._log(record)
                return
            try:
                self.send_response(result["status"])
                self.send_header("Content-Type", result["content_type"])
                self.send_header("Content-Length", str(len(result["content"])))
                self.end_headers()
                self.wfile.write(result["content"])
            except (BrokenPipeError, ConnectionResetError):
                record["error"] = "client disconnected before response was written"
            if self.path.startswith("/api/chat") or self.path.startswith("/api/generate"):
                try:
                    data = json.loads(result["content"])
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
