# -*- coding: utf-8 -*-
"""등록한 모델(base 변환본·학습 모델)의 렌더링을 업체 100이 아닌 질문(v004 학습 질문 일부)으로 확인한다. 하나라도 다르면 B-conv를 재지 않는다.

    python sft_dpo_inventory/pilot_001/ollama/render_check.py --model NAME --out RESULT.json

- pilot_prep_003과 같은 확인이다(결정 31). 문항도 같은 v004 학습 질문 10개(같은 선택 규칙)다.
- pilot_002 사본: ``pilot_001/ollama/render_check.py``와 확인·문항·요청이 같다. 결정 55의 생성 속도 확인을 위해 행마다
  ``eval_duration_ms``, ``total_duration_ms``, ``eval_tok_s``(= eval_count / eval_duration)를 더 남기는 것만 다르다.

- 질문: v004 학습 레코드 중 출처별로 고른 10개(v003 train 4, v003 valid 3, batch004 3. 각 출처의 파일 순서 앞쪽).
- 요청: 평가 harness와 같은 형태(``GeoFlowPlanner.messages``, ``/api/chat``, ``options {"temperature": 0}``, ``think`` 미지정,
  stream 없음). prompt cache가 ``prompt_eval_count``에 섞이지 않도록 ``keep_alive: 0``으로 요청마다 모델을 내린다.
- 확인(문항마다):
  1. ``prompt_eval_count`` = HF tokenizer ``apply_chat_template(..., add_generation_prompt=True, enable_thinking=True)``의
     token 수(Qwen/Qwen3-8B@b968826d, 학습 렌더링과 같음).
  2. think를 지정하지 않으면 thinking 켬으로 동작: ``message.thinking``이 비어 있지 않다.
  3. thinking과 본문이 분리된다: ``message.content``에 ``<think>``·``</think>``가 없고, thinking에 ``</think>``가 없다.
- 결과는 ``render_check.json``(원문 없이 token 수와 판정만).
"""
import argparse
import json
import os
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sft_dpo_inventory/thinking_prep_001"))

HOST = "http://localhost:11434"
V004 = ROOT / "training/generated/reviewed_gold_v004_t2pc/sft_train.jsonl"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    MODEL = args.model
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from transformers import AutoTokenizer
    import hf_thinking as H
    from geoflow.planner import GeoFlowPlanner
    from training.data.common import read_jsonl
    tok = AutoTokenizer.from_pretrained(H.MODEL, revision=H.REVISION)
    valid_ids = {r["metadata"]["source_record_id"] for r in read_jsonl(ROOT / "training/generated/reviewed_gold_v003_t2pc/sft_valid.jsonl")}
    rows = read_jsonl(V004)
    groups = {"v003_train": [], "v003_valid": [], "batch004": []}
    for r in rows:
        sid = r["metadata"]["source_record_id"]
        groups["batch004" if sid.startswith("b004-") else "v003_valid" if sid in valid_ids else "v003_train"].append(r)
    picked = groups["v003_train"][:4] + groups["v003_valid"][:3] + groups["batch004"][:3]
    planner = GeoFlowPlanner(client=None)
    results = []
    for r in picked:
        question = r["messages"][1]["content"]
        messages = planner.messages(question)
        hf_tokens = len(tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, enable_thinking=True))
        response = httpx.post(f"{HOST}/api/chat", json={"model": MODEL, "messages": messages, "stream": False,
                                                         "options": {"temperature": 0}, "keep_alive": 0},
                              timeout=1800).json()
        message = response.get("message") or {}
        thinking, content = message.get("thinking") or "", message.get("content") or ""
        row = {"id": r["metadata"]["source_record_id"], "prompt_eval_count": response.get("prompt_eval_count"),
               "hf_tokens": hf_tokens, "token_match": response.get("prompt_eval_count") == hf_tokens,
               "thinking_chars": len(thinking), "thinking_on_without_think": bool(thinking.strip()),
               "separated": "<think>" not in content and "</think>" not in content and "</think>" not in thinking,
               "eval_count": response.get("eval_count"), "done_reason": response.get("done_reason"),
               "eval_duration_ms": round((response.get("eval_duration") or 0) / 1e6, 1),
               "total_duration_ms": round((response.get("total_duration") or 0) / 1e6, 1),
               "eval_tok_s": round(response["eval_count"] / (response["eval_duration"] / 1e9), 1)
               if response.get("eval_count") and response.get("eval_duration") else None}
        row["ok"] = row["token_match"] and row["thinking_on_without_think"] and row["separated"]
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    summary = {"model": MODEL, "checked": len(results), "all_ok": all(r["ok"] for r in results),
               "token_match": sum(r["token_match"] for r in results),
               "thinking_on_without_think": sum(r["thinking_on_without_think"] for r in results),
               "separated": sum(r["separated"] for r in results),
               "ollama_version": httpx.get(f"{HOST}/api/version", timeout=10).json()["version"], "rows": results}
    Path(args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("checked", "all_ok", "token_match", "thinking_on_without_think",
                                              "separated")}, ensure_ascii=False))
    return 0 if summary["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
