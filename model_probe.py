# -*- coding: utf-8 -*-
"""모델 비교 전 timeout probe. 같은 production prompt와 생성 옵션으로 cold 첫 호출만 본다.

정확도를 보지 않는다. 모델이 정상 생성으로 끝나는데 느린 것인지, 끝나지 않는 생성인지만
본다. 생성 옵션은 production(temperature 0, think 미지정)과 같다. stream으로 받아
진행을 기록하고 cap에서 끊는다.

사용: python model_probe.py --out <json> --cap 300 MODEL...
"""

import argparse
import json
import sys
import time

import httpx

import evaluate_prompt_ab as A

#: 결과를 보기 전에 고른 질문. 두 단계 집계, taxi_type, 지원 범위 밖 비교.
PROBE_IDS = ("f01_p0", "b05_p0", "b20_p0")


def unload_all(host):
    for item in httpx.get(f"{host}/api/ps", timeout=10).json().get("models", []):
        httpx.post(f"{host}/api/generate", json={"model": item["name"], "keep_alive": 0},
                   timeout=60)
    deadline = time.time() + 60
    while httpx.get(f"{host}/api/ps", timeout=10).json().get("models") and time.time() < deadline:
        time.sleep(1)


def probe(host, model, prompt, question, cap):
    unload_all(host)
    started = time.time()
    thinking, content, final = [], [], None
    payload = {"model": model, "stream": True, "options": {"temperature": 0},
               "messages": [{"role": "system", "content": prompt},
                            {"role": "user", "content": question}]}
    with httpx.stream("POST", f"{host}/api/chat", json=payload, timeout=None) as response:
        for line in response.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            message = data.get("message") or {}
            thinking.append(message.get("thinking") or "")
            content.append(message.get("content") or "")
            if data.get("done"):
                final = data
                break
            if time.time() - started > cap:
                break
    text = "".join(thinking)
    return {"model": model, "question": question, "wall_s": round(time.time() - started, 1),
            "finished": final is not None,
            "done_reason": final and final.get("done_reason"),
            "eval_count": final and final.get("eval_count"),
            "load_s": final and round(final.get("load_duration", 0) / 1e9, 2),
            "thinking_chars": len(text), "content_chars": len("".join(content)),
            "thinking_tail": text[-300:]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("models", nargs="+")
    parser.add_argument("--out", required=True)
    parser.add_argument("--cap", type=float, default=300)
    parser.add_argument("--host", default=A.DEFAULT_HOST)
    args = parser.parse_args(argv)
    prompt = A.build_variant("PRODUCTION").prompt
    questions = {item["id"]: item["question"] for item in A.census_items()}
    results = []
    for model in args.models:
        for qid in PROBE_IDS:
            result = {"id": qid, **probe(args.host, model, prompt, questions[qid], args.cap)}
            results.append(result)
            print(json.dumps({k: v for k, v in result.items() if k != "thinking_tail"},
                             ensure_ascii=False), flush=True)
    unload_all(args.host)
    with open(args.out, "x", encoding="utf-8") as handle:
        json.dump({"cap_s": args.cap, "prompt_sha256": A.build_variant("PRODUCTION").sha256,
                   "options": {"temperature": 0, "think": "unset"}, "results": results},
                  handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.exit(main())
