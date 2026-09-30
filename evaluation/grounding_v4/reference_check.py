# -*- coding: utf-8 -*-
"""reference provider에서 실제 모델로 "값 / 그 값을 가진 구간 / 구간 안 집계 없음"을 실행해 결과 종류를 본다.

reference provider는 합성 일 기록으로 구간 선택을 로컬에서 계산할 수 있다(TIMS와 달리 day_records 계약이 있다).
질문마다 모델을 내리고(격리) 첫 계획 응답부터 실행한다. 판정은 결과 종류다.

    python evaluation/grounding_v4/reference_check.py --mode flat --out evaluation/grounding_v4/runs/reference_flat.json
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE))
os.environ["ASSISTANT_TOOL_PROVIDER"] = "reference"

import evaluate_prompt_ab as A  # noqa: E402
from build import build  # noqa: E402
from geoflow.pipeline import GeoFlowPipeline  # noqa: E402
from geoflow.providers import REFERENCE, profile_for  # noqa: E402
from ollama_client import OllamaClient, resolve_think  # noqa: E402
from tool_executor import ToolExecutor  # noqa: E402
from tool_handlers import get_tool_handlers  # noqa: E402

REF_DATE = date(2026, 9, 25)
#: (id, 질문, 기대 결과 종류). bucket = 답이 구간(주)과 그 값, value = 스칼라 값.
QUESTIONS = (
    ("r1", "지난달 가람구 개인택시 매출 합계가 가장 큰 주는?", "bucket"),
    ("r2", "지난달 가람구 개인택시 주별 매출 합계 중 가장 큰 값은?", "value"),
    ("r3", "지난달 가람구 개인택시 주별 매출 중 가장 큰 값은?", "needs_clarification"),
    ("r4", "지난달 나래구 개인택시 주별 평균 매출이 가장 작은 주는 언제야?", "bucket"),
    ("r5", "지난달 나래구 개인택시 주별 평균 매출 중 가장 작은 값은?", "value"),
    ("r6", "지난달 가람구 개인택시 매출 평균은?", "value"),
)


def kind(run):
    if run.outcome != "answered":
        return run.outcome
    value = run.hop_log[-1].get("result") if run.hop_log else None
    return "bucket" if isinstance(value, dict) and value.get("groups") else "value"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("flat", "structured"), required=True)
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--host", default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    tools, _ = build()
    client = OllamaClient(args.host, args.model, {"temperature": 0}, chat_timeout=300.0,
                          think=resolve_think("auto"))
    reset = A.OllamaStateReset(args.host, args.model)
    rows = []
    for qid, question, expected in QUESTIONS:
        state = reset.reset()
        executor = ToolExecutor(tools=tools, handlers=get_tool_handlers(REFERENCE), provider=REFERENCE)
        run = GeoFlowPipeline.create(
            client=client, tool_executor=executor, aggregation_grounding=args.mode,
            clock=lambda: REF_DATE, condition_check=True, condition_notes=False,
            execution_profile=profile_for(REFERENCE)).run(question)
        record = run.to_dict()
        got = kind(run)
        rows.append({"id": qid, "question": question, "expected": expected, "observed": got,
                     "ok": got == expected, "reset_ok": state.succeeded,
                     "error_code": (record.get("error") or {}).get("code"),
                     "grounding": record.get("grounding"), "final_answer": run.final_answer})
        print(qid, expected, got, rows[-1]["error_code"] or "", flush=True)
    summary = {"mode": args.mode, "ok": sum(row["ok"] for row in rows), "of": len(rows)}
    Path(args.out).write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False,
                                         indent=1, default=str), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
