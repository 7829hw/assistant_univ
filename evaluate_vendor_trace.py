# -*- coding: utf-8 -*-
"""업체 13개 질문의 Tool trace acceptance 평가.

Planner 출력만 보지 않고 실제 Tool execution trace를 판정 대상으로 삼는다.
실행 engine은 기존 AssistantRuntime / GeoFlowPipeline / ToolExecutor를 그대로
재사용하며, 판정 기준은 전부 evaluation/vendor/vendor_trace_gold.yaml에서 온다.

사용법:
    python evaluate_vendor_trace.py --model qwen3.8:27b --agent-mode geoflow
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from assistant_runtime import (
    AGENT_MODE_GEOFLOW,
    AGENT_MODES,
    DEFAULT_AGENT_MODE,
    AssistantRuntime,
)
from build import build
from geoflow.errors import GeoFlowError
from geoflow.pipeline import GeoFlowPipeline
from ollama_client import OllamaClient, resolve_chat_timeout
from query_loader import QueryValidationError, load_queries
from tool_executor import ToolExecutor
from tool_handlers import get_tool_handlers
from vendor_trace_contract import (
    DEFAULT_GOLD_FILE,
    analysis_calls,
    evaluate_case,
    load_gold,
)

BASE_DIR = Path(__file__).resolve().parent
VENDOR_DIR = BASE_DIR / "evaluation" / "vendor"
RESULT_DIR = BASE_DIR / "evaluation" / "vendor_runs"
DEFAULT_QUERY_FILE = VENDOR_DIR / "vendor_queries.yaml"
DEFAULT_OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_OPTIONS = {"temperature": 0}
MAX_TOOL_HOPS = 10


def _now_local():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def format_call(call):
    arguments = call.get("arguments") or {}
    body = ", ".join(
        f"{key}={value}" for key, value in arguments.items()
    )
    result = call.get("result")
    if isinstance(result, dict) and result.get("status") == "ERROR":
        shown = f"ERROR/{result.get('error_code')}"
    elif isinstance(result, (list, dict)):
        shown = json.dumps(result, ensure_ascii=False)[:60]
    else:
        shown = str(result)[:60]
    return f"{call.get('tool')}({body}) → {shown}"


def build_runtime(model, host, chat_timeout, agent_mode):
    tools, system_prompt = build()
    client = OllamaClient(
        host, model, dict(OLLAMA_OPTIONS), chat_timeout=chat_timeout,
    )
    tool_executor = ToolExecutor(tools=tools, handlers=get_tool_handlers())
    geoflow = None
    if agent_mode == AGENT_MODE_GEOFLOW:
        geoflow = GeoFlowPipeline.create(
            client=client, tool_executor=tool_executor, model=model,
        )
    return AssistantRuntime(
        client=client,
        tools=tools,
        system_prompt=system_prompt.strip(),
        tool_executor=tool_executor,
        model=model,
        agent_mode=agent_mode,
        geoflow=geoflow,
    )


def evaluate(queries, gold, *, model, host, chat_timeout, agent_mode,
             repeat, verbose):
    records = []
    for item in queries:
        contract = gold.get(item["id"])
        if contract is None:
            raise SystemExit(f"gold contract가 없습니다: {item['id']}")
        for attempt in range(1, repeat + 1):
            runtime = build_runtime(model, host, chat_timeout, agent_mode)
            try:
                result = runtime.run_question(
                    item["question"], max_hops=MAX_TOOL_HOPS,
                )
            except GeoFlowError as error:
                result = {
                    "hop_log": [], "final_answer": None,
                    "runtime_error": error.detail, "geoflow": None,
                }
            problems, sequence = evaluate_case(
                contract,
                item["question"],
                result.get("hop_log") or [],
                runtime_error=result.get("runtime_error"),
            )
            record = {
                "id": item["id"],
                "repeat_index": attempt,
                "question": item["question"],
                "vendor_verdict": contract.vendor_verdict,
                "note": contract.note,
                "passed": not problems,
                "failure_categories": sorted(
                    {problem["category"] for problem in problems}
                ),
                "problems": problems,
                "expected_tool_sequence": sequence["expected"],
                "actual_tool_sequence": sequence["actual"],
                "actual_trace": [
                    {
                        "tool": call.get("tool"),
                        "arguments": call.get("arguments"),
                        "result": call.get("result"),
                    }
                    for call in analysis_calls(result.get("hop_log") or [])
                ],
                "final_answer": result.get("final_answer"),
                "runtime_error": result.get("runtime_error"),
                "template": (result.get("geoflow") or {}).get("template"),
            }
            records.append(record)
            mark = "PASS" if record["passed"] else "FAIL"
            print(f"[{mark}] {item['id']}")
            if verbose or not record["passed"]:
                for call in record["actual_trace"]:
                    print(f"        {format_call(call)}")
                for problem in problems:
                    print(f"     !  [{problem['category']}] {problem['message']}")
    return records


def write_report(path, records, *, model, agent_mode, timestamp):
    passed = sum(1 for record in records if record["passed"])
    lines = [
        "# Vendor Tool Trace Acceptance",
        "",
        f"- Model: {model}",
        f"- Agent mode: {agent_mode}",
        f"- Timestamp: {timestamp}",
        "- 판정 기준: evaluation/vendor/vendor_trace_gold.yaml",
        "",
        "## Summary",
        "",
        f"**Passed: {passed} / {len(records)}**",
        "",
        "| ID | Result | 업체 판정 | Tool Sequence | 실패 분류 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in records:
        sequence = " → ".join(record["actual_tool_sequence"]) or "(없음)"
        categories = ", ".join(record["failure_categories"]) or "-"
        lines.append(
            f"| {record['id']} | {'PASS' if record['passed'] else 'FAIL'} "
            f"| {record['vendor_verdict']} | {sequence} | {categories} |"
        )
    lines.append("")

    for record in records:
        lines.extend([
            f"## {record['id']}",
            "",
            f"**Question**: {record['question']}",
            "",
        ])
        if record["note"]:
            lines.extend([f"> {record['note']}", ""])
        lines.extend(["**Expected tool sequence**", "", "```text"])
        lines.append(" → ".join(record["expected_tool_sequence"]))
        lines.extend(["```", "", "**Actual trace**", "", "```text"])
        if record["actual_trace"]:
            for call in record["actual_trace"]:
                lines.append(format_call(call))
        else:
            lines.append("(Tool 호출 없음)")
        lines.extend(["```", "", "**Checks**", ""])
        if record["passed"]:
            lines.append("- PASS — gold contract의 모든 조건을 만족합니다.")
        else:
            for problem in record["problems"]:
                lines.append(
                    f"- FAIL `{problem['category']}` — {problem['message']}"
                )
        lines.extend([
            "",
            f"**Final answer**: {record['final_answer'] or '(없음)'}",
            "",
        ])
        if record["runtime_error"]:
            lines.extend([f"**Runtime error**: {record['runtime_error']}", ""])
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="업체 13개 질문 Tool trace acceptance 평가",
    )
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL"))
    parser.add_argument(
        "--agent-mode", choices=AGENT_MODES, default=DEFAULT_AGENT_MODE,
    )
    parser.add_argument("--ollama-host", default=DEFAULT_OLLAMA_HOST)
    parser.add_argument("--query-file", default=str(DEFAULT_QUERY_FILE))
    parser.add_argument("--gold-file", default=str(DEFAULT_GOLD_FILE))
    parser.add_argument("--chat-timeout", type=float, default=None)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--query-id", action="append")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args(argv)
    if not args.model:
        parser.error("--model이 필요합니다.")
    if args.repeat < 1:
        parser.error("--repeat는 1 이상이어야 합니다.")
    return args


def main(argv=None):
    args = parse_args(argv)
    chat_timeout = resolve_chat_timeout(args.chat_timeout)
    try:
        queries = load_queries(args.query_file)
    except QueryValidationError as error:
        raise SystemExit(str(error)) from error
    if args.query_id:
        wanted = set(args.query_id)
        queries = [item for item in queries if item["id"] in wanted]
        if not queries:
            raise SystemExit(f"선택한 query가 없습니다: {sorted(wanted)}")
    gold = load_gold(args.gold_file)

    print(
        f"설정 — 모델: {args.model} / agent mode: {args.agent_mode} "
        f"/ query {len(queries)}건 × repeat {args.repeat}"
    )
    records = evaluate(
        queries, gold,
        model=args.model, host=args.ollama_host, chat_timeout=chat_timeout,
        agent_mode=args.agent_mode, repeat=args.repeat, verbose=args.verbose,
    )

    passed = sum(1 for record in records if record["passed"])
    print(f"\n{'=' * 52}\nPassed: {passed} / {len(records)}")
    if passed != len(records):
        print("실패 목록:")
        for record in records:
            if not record["passed"]:
                print(
                    f"  - {record['id']}: "
                    f"{', '.join(record['failure_categories'])}"
                )

    if args.no_save:
        return records

    timestamp = _now_local().isoformat()
    run_dir = RESULT_DIR / _now_local().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "vendor_trace_raw.json").write_text(
        json.dumps({
            "model": args.model,
            "agent_mode": args.agent_mode,
            "timestamp": timestamp,
            "query_file": str(args.query_file),
            "gold_file": str(args.gold_file),
            "repeat": args.repeat,
            "passed": passed,
            "total": len(records),
            "records": records,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_report(
        run_dir / "vendor_trace_report.md", records,
        model=args.model, agent_mode=args.agent_mode, timestamp=timestamp,
    )
    print(f"결과 파일: {run_dir}")
    return records


if __name__ == "__main__":
    main()
