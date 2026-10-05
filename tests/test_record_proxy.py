# -*- coding: utf-8 -*-
"""기록 프록시(evaluation/grounding_v14/record_proxy.py)의 연결 종료 전달과 upstream 상한. 짧은 timeout의 로컬 가짜 서버로 확인한다."""

import importlib.util
import json
import select
import socket
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "record_proxy", HERE.parent / "evaluation" / "grounding_v14" / "record_proxy.py")
P = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(P)


class SlowUpstream:
    """요청마다 delay초 동안 응답을 미루며, 그 사이 프록시가 연결을 끊으면 끊긴 시각을 기록한다."""

    def __init__(self, delay):
        self.delay = delay
        self.disconnects = []    # 요청 시작부터 끊김을 본 시각까지(초)
        self.completed = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                return

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                started = time.time()
                while time.time() - started < owner.delay:
                    readable, _, _ = select.select([self.connection], [], [], 0.02)
                    if readable:
                        try:
                            gone = self.connection.recv(1, socket.MSG_PEEK) == b""
                        except OSError:
                            gone = True
                        if gone:
                            owner.disconnects.append(time.time() - started)
                            return
                body = json.dumps({"message": {"content": "ok"}, "done_reason": "stop"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                owner.completed += 1

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self):
        self.server.shutdown()


class RecordProxyTest(unittest.TestCase):
    def start(self, delay, upstream_timeout):
        self.upstream = SlowUpstream(delay)
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "proxy.jsonl"
        self.previous = P.UPSTREAM_TIMEOUT
        P.UPSTREAM_TIMEOUT = upstream_timeout
        self.proxy = ThreadingHTTPServer(("127.0.0.1", 0), P.make_handler(self.upstream.url, str(self.log)))
        threading.Thread(target=self.proxy.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.proxy.server_address[1]}"

    def tearDown(self):
        P.UPSTREAM_TIMEOUT = self.previous
        self.proxy.shutdown()
        self.upstream.close()
        self.tmp.cleanup()

    def records(self):
        deadline = time.time() + 3
        while time.time() < deadline:
            if self.log.is_file() and self.log.read_text().strip():
                return [json.loads(line) for line in self.log.read_text().splitlines()]
            time.sleep(0.02)
        return []

    def test_client_disconnect_closes_upstream_promptly(self):
        self.start(delay=5.0, upstream_timeout=30.0)
        with self.assertRaises(httpx.TimeoutException):
            httpx.post(self.url + "/api/chat", json={"messages": []}, timeout=0.3)
        deadline = time.time() + 3
        while not self.upstream.disconnects and time.time() < deadline:
            time.sleep(0.02)
        self.assertEqual(len(self.upstream.disconnects), 1)
        self.assertLess(self.upstream.disconnects[0], 1.5)      # upstream 상한(30초)이 아니라 클라이언트 종료로 닫혔다
        self.assertEqual(self.upstream.completed, 0)
        self.assertIn("client disconnected", self.records()[0]["error"])

    def test_upstream_timeout_is_only_an_upper_bound(self):
        self.start(delay=5.0, upstream_timeout=0.4)
        with self.assertRaises(httpx.HTTPError):
            httpx.post(self.url + "/api/chat", json={"messages": []}, timeout=10.0)
        deadline = time.time() + 3
        while not self.upstream.disconnects and time.time() < deadline:
            time.sleep(0.02)
        self.assertEqual(len(self.upstream.disconnects), 1)
        self.assertLess(self.upstream.disconnects[0], 2.0)
        self.assertIn("upstream timeout", self.records()[0]["error"])

    def test_normal_response_is_forwarded_and_recorded(self):
        self.start(delay=0.05, upstream_timeout=5.0)
        response = httpx.post(self.url + "/api/chat", json={"messages": [{"role": "user", "content": "q"}]}, timeout=5)
        self.assertEqual(response.json()["message"]["content"], "ok")
        record = self.records()[0]
        self.assertEqual(record["status"], 200)
        self.assertEqual(record["response"]["content"], "ok")
        self.assertEqual(record["request"]["messages"][0]["content"], "q")


if __name__ == "__main__":
    unittest.main()
