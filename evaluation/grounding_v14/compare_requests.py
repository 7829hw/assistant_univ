# -*- coding: utf-8 -*-
"""두 기록 프록시 로그(record_proxy.py)의 /api/chat 요청·응답을 질문별로 비교한다(모델 호출 없음).

    python evaluation/grounding_v14/compare_requests.py A.jsonl B.jsonl [--json OUT]

질문 = 마지막 user message의 내용. 같은 질문의 n번째 chat 요청끼리 비교한다(첫 계획, 재질의 순서).
요청: 본문 hash, 다른 최상위 필드(model·options·think·keep_alive·stream·tools), messages 수·역할·각 내용 hash.
응답: 내용 일치, prompt_eval_count(이번 요청에서 새로 계산한 prompt 토큰), load_duration.
"""
import argparse
import hashlib
import json
from collections import defaultdict


def _sha(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:12]


def chats(path):
    out = defaultdict(list)
    order = []
    for line in open(path, encoding="utf-8"):
        rec = json.loads(line)
        if not rec["path"].startswith("/api/chat") or "request" not in rec:
            continue
        msgs = rec["request"].get("messages") or []
        users = [m for m in msgs if m.get("role") == "user"]
        question = users[0]["content"] if users else ""
        out[question].append(rec)
        order.append(question)
    return out, order


def view(rec):
    req = rec["request"]
    return {
        "sha": rec["request_sha256"][:12],
        "top": {k: req.get(k) for k in sorted(req) if k != "messages"},
        "messages": [(m.get("role"), _sha(m.get("content")), len(m.get("content") or "")) for m in req.get("messages") or []],
        "content_sha": _sha((rec.get("response") or {}).get("content")),
        "prompt_eval_count": (rec.get("response") or {}).get("prompt_eval_count"),
        "load_ms": round(((rec.get("response") or {}).get("load_duration") or 0) / 1e6),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("a")
    parser.add_argument("b")
    parser.add_argument("--json", default="")
    args = parser.parse_args()
    a, order_a = chats(args.a)
    b, order_b = chats(args.b)
    report = {"a": args.a, "b": args.b, "questions": {}}
    for q in sorted(set(a) | set(b), key=lambda x: (order_a + order_b).index(x)):
        rows = []
        for i in range(max(len(a.get(q, [])), len(b.get(q, [])))):
            va = view(a[q][i]) if i < len(a.get(q, [])) else None
            vb = view(b[q][i]) if i < len(b.get(q, [])) else None
            rows.append({"n": i + 1, "a": va, "b": vb,
                         "same_request": bool(va and vb and va["sha"] == vb["sha"]),
                         "same_response": bool(va and vb and va["content_sha"] == vb["content_sha"])})
        report["questions"][q] = rows
    # 한 run 안에서 이전 질문의 내용이 다음 요청에 들어갔는가
    leaks = []
    for path in (args.a, args.b):
        seen = []
        for line in open(path, encoding="utf-8"):
            rec = json.loads(line)
            if not rec["path"].startswith("/api/chat") or "request" not in rec:
                continue
            body = json.dumps(rec["request"].get("messages"), ensure_ascii=False)
            users = [m for m in rec["request"].get("messages") or [] if m.get("role") == "user"]
            current = users[0]["content"] if users else ""
            for previous in seen:
                if previous != current and previous in body:
                    leaks.append({"log": path, "seq": rec["seq"], "previous_question": previous[:60]})
            if current not in seen:
                seen.append(current)
    report["cross_question_leaks"] = leaks
    if args.json:
        open(args.json, "w", encoding="utf-8").write(json.dumps(report, ensure_ascii=False, indent=1))
    for q, rows in report["questions"].items():
        for r in rows:
            va, vb = r["a"] or {}, r["b"] or {}
            print(f"{q[:38]:40s} #{r['n']} req_same={r['same_request']} resp_same={r['same_response']} "
                  f"pec {va.get('prompt_eval_count')}/{vb.get('prompt_eval_count')} load_ms {va.get('load_ms')}/{vb.get('load_ms')}")
            if va and vb and not r["same_request"]:
                print("    top a", va["top"]); print("    top b", vb["top"])
                print("    msgs a", va["messages"]); print("    msgs b", vb["messages"])
    print("leaks", leaks)


if __name__ == "__main__":
    main()
