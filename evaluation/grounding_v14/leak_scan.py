# -*- coding: utf-8 -*-
"""기록 프록시 로그에서 질문 사이 누출을 찾는다: 어떤 /api/chat 요청에 같은 run의 다른 질문 원문이 들어 있는가."""
import gzip
import json
import sys


def _open(path):
    """기록 프록시 로그(.jsonl 또는 압축한 .jsonl.gz)."""
    return gzip.open(path, "rt", encoding="utf-8") if str(path).endswith(".gz") else open(path, encoding="utf-8")


def scan(path):
    requests, questions = [], []
    for line in _open(path):
        rec = json.loads(line)
        if not rec["path"].startswith("/api/chat") or "request" not in rec:
            continue
        messages = rec["request"].get("messages") or []
        users = [m for m in messages if m.get("role") == "user"]
        current = users[0]["content"] if users else ""
        requests.append((rec["seq"], current, json.dumps(messages, ensure_ascii=False)))
        if current not in questions:
            questions.append(current)
    leaks = [(seq, other[:40]) for seq, current, body in requests for other in questions
             if other != current and other in body]
    return {"chat_requests": len(requests), "questions": len(questions), "leaks": leaks}


if __name__ == "__main__":
    for path in sys.argv[1:]:
        print(path, scan(path))
