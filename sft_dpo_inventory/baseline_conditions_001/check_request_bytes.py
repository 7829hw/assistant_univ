# -*- coding: utf-8 -*-
"""--model-think 추가 뒤 기본 실행(auto)의 요청이 이전 기록과 같은지 모델 호출 없이 확인한다.

    python sft_dpo_inventory/baseline_conditions_001/check_request_bytes.py --code-root WT --record RUN.json

1. messages: 업체 100 문항마다 code root의 planner가 만드는 첫 계획 요청 messages의 hash(harness ``_request_sha``)를
   기록의 첫 plan 호출 ``request_sha256``과 비교한다. request_sha256은 messages만 덮는다.
2. payload: harness와 같은 방식으로 만든 OllamaClient의 ``_http.post``를 가짜 transport로 바꿔 실제 /api/chat
   payload를 잡는다. auto는 think key가 없어야 하고(이전 harness와 같은 payload), off/on은 think=false/true가 들어가야 한다.
네트워크 호출은 없다.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-root", required=True)
    parser.add_argument("--record", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sys.argv = ["evaluate_vendor100.py", "--code-root", args.code_root]
    sys.path.insert(0, str(ROOT))
    import evaluate_vendor100 as EV   # import 시 sys.path를 code root로 바꾼다
    from geoflow.planner import GeoFlowPlanner
    from ollama_client import OllamaClient, resolve_think

    record = json.loads(Path(args.record).read_text(encoding="utf-8"))
    rows = {r["id"]: r for r in record["rows"]}
    planner = GeoFlowPlanner(client=None)
    prompt_sha = hashlib.sha256(planner.system_prompt().encode("utf-8")).hexdigest()
    same, differ, missing = 0, [], []
    payloads = {}
    for item in EV.load_gold(None)["items"]:
        if item["id"] not in rows:      # 기록이 일부 문항만 가진 경우
            continue
        messages = planner.messages(item["question"])
        calls = [c for c in rows[item["id"]].get("llm_calls") or [] if c.get("kind") == "plan"]
        if not calls or not calls[0].get("request_sha256"):
            missing.append(item["id"])
            continue
        if EV._request_sha(messages) == calls[0]["request_sha256"]:
            same += 1
        else:
            differ.append(item["id"])

    class Fake:
        def __init__(self):
            self.payload = None

        def post(self, url, json=None, timeout=None):
            self.payload = json

            class R:
                status_code = 200

                def json(self):
                    return {"message": {"content": "{}"}, "done_reason": "stop"}
            return R()

    sample = planner.messages("검사용")
    for choice in ("auto", "off", "on"):
        client = OllamaClient("http://localhost:11434", "qwen3:8b", {"temperature": 0},
                              chat_timeout=300.0, think=resolve_think(choice))
        fake = Fake()
        client._http = fake
        client._check_response = lambda response: None
        client.chat(sample)
        payload = fake.payload
        payloads[choice] = {"keys": sorted(payload), "options": payload["options"],
                            "think": payload.get("think", "<absent>"),
                            "sha256": hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True)
                                                     .encode("utf-8")).hexdigest()}
    result = {"code_root": args.code_root, "record": args.record, "prompt_sha256": prompt_sha,
              "record_prompt_sha256": record["meta"].get("planner_prompt_sha256"),
              "messages_same": same, "messages_differ": differ, "messages_missing": missing,
              "payload_by_think": payloads,
              "auto_payload_has_no_think": payloads["auto"]["think"] == "<absent>",
              "ok": not differ and payloads["auto"]["think"] == "<absent>"
              and payloads["off"]["think"] is False and payloads["on"]["think"] is True}
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
