# -*- coding: utf-8 -*-
"""단일 Query와 YAML Query Suite를 실행하는 Standalone 평가 CLI."""

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from assistant_runtime import (
    AGENT_MODE_GEOFLOW,
    AGENT_MODE_REACT,
    AGENT_MODES,
    DEFAULT_AGENT_MODE,
    AssistantRuntime,
)
from build import build
from geoflow.errors import GeoFlowError
from geoflow.pipeline import GeoFlowPipeline
from query_loader import (
    QuerySelectionError,
    QueryValidationError,
    load_queries,
    select_queries,
)
from ollama_client import (
    DEFAULT_CHAT_TIMEOUT,
    THINK_CHOICES,
    OllamaClient,
    chat_options,
    resolve_chat_timeout,
    resolve_think,
)
from tool_executor import ToolExecutor
from tool_handlers import (
    DEFAULT_TOOL_PROVIDER,
    TOOL_PROVIDER_ENV,
    get_tool_handlers,
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNS_DIR = os.path.join(BASE_DIR, "evaluation", "runs")

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL_NAME = "qwen3-coder:30b"
MAX_TOOL_HOPS = 10
OLLAMA_OPTIONS = {"temperature": 0}

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
MODEL_NAME = os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL_NAME)
CHAT_TIMEOUT = DEFAULT_CHAT_TIMEOUT
OLLAMA_CLIENT = None
AGENT_MODE = DEFAULT_AGENT_MODE

ARRAY_PREVIEW_LIMIT = 3
INLINE_RESULT_LIMIT = 8
TRACE_LINE_WIDTH = 112
RESULT_METADATA_KEYS = {
    "status", "operation", "data_status", "result_count", "period",
}

verbose = None

def configure_ollama_client(host, model, chat_timeout=None, think=None,
                           num_predict=None):
    """CLI/환경변수로 확정된 설정을 모든 실행 경로에 적용한다."""
    global OLLAMA_HOST, MODEL_NAME, CHAT_TIMEOUT, OLLAMA_CLIENT
    OLLAMA_HOST = host.rstrip("/")
    MODEL_NAME = model
    CHAT_TIMEOUT = resolve_chat_timeout(chat_timeout)
    OLLAMA_CLIENT = OllamaClient(
        OLLAMA_HOST,
        MODEL_NAME,
        chat_options(OLLAMA_OPTIONS, num_predict),
        chat_timeout=CHAT_TIMEOUT,
        think=think,
    )
    return OLLAMA_CLIENT


def get_ollama_client():
    if OLLAMA_CLIENT is None:
        return configure_ollama_client(OLLAMA_HOST, MODEL_NAME)
    return OLLAMA_CLIENT


def configure_agent_mode(agent_mode):
    """CLI가 선택한 실행 모드를 전역 설정에 반영한다."""
    global AGENT_MODE
    if agent_mode not in AGENT_MODES:
        raise SystemExit(
            f"지원하지 않는 agent mode입니다: {agent_mode} "
            f"(사용 가능: {', '.join(AGENT_MODES)})"
        )
    AGENT_MODE = agent_mode
    return AGENT_MODE


def check_ollama_connection():
    """Ollama 연결, 모델 존재 여부, 실제 capability를 확인한다."""
    client = get_ollama_client()
    try:
        models = client.list_models()
    except Exception as error:
        print(f"✗ Ollama에 연결할 수 없습니다: {OLLAMA_HOST}")
        print(f"  오류 내용: {error}")
        raise SystemExit(1)

    model_names = [item.get("name") or item.get("model") for item in models]
    if MODEL_NAME not in model_names:
        print(f"✗ 모델 '{MODEL_NAME}'을 찾을 수 없습니다.")
        print(f"  사용 가능한 모델: {model_names}")
        print(f"  받는 방법: ollama pull {MODEL_NAME}")
        raise SystemExit(1)

    try:
        capabilities = client.get_capabilities()
    except Exception as error:
        print(f"✗ 모델 capability를 확인할 수 없습니다: {MODEL_NAME}")
        print(f"  오류 내용: {error}")
        raise SystemExit(1)

    # geoflow mode의 Planner는 tools 없이 JSON만 생성하므로 native Tool
    # capability를 요구하지 않는다. react mode의 요구 조건은 그대로 둔다.
    if AGENT_MODE == AGENT_MODE_REACT and "tools" not in set(capabilities):
        print(f"✗ {MODEL_NAME} 모델은 native Tool Calling을 지원하지 않습니다.")
        print("  react mode 실행에는 capabilities의 tools가 필수입니다.")
        print("  /api/show의 capabilities에 tools가 있는 모델을 선택하세요.")
        raise SystemExit(1)

    print(f"✓ Ollama 연결 확인 완료 (모델: {MODEL_NAME})")
    print(f"  capabilities: {', '.join(capabilities) or '(없음)'}")
    print(
        "  실행 모드: "
        + (
            "GEOFLOW_PLANNER"
            if AGENT_MODE == AGENT_MODE_GEOFLOW
            else "NATIVE_TOOL_AGENT"
        )
    )


def list_installed_models(host):
    """설치 모델별 실제 capability와 native Tool 가능 여부를 출력한다."""
    discovery_client = OllamaClient(host, "", dict(OLLAMA_OPTIONS))
    try:
        models = discovery_client.list_models()
    except Exception as error:
        print(f"✗ Ollama 모델 목록을 가져올 수 없습니다: {error}")
        return False

    rows = []
    for item in models:
        model_name = item.get("name") or item.get("model")
        if not model_name:
            continue
        client = OllamaClient(host, model_name, dict(OLLAMA_OPTIONS))
        try:
            capabilities = client.get_capabilities()
            rows.append((
                model_name,
                ", ".join(capabilities) or "-",
                "YES" if client.supports_tools() else "NO",
            ))
        except Exception as error:
            rows.append((model_name, f"ERROR: {error}", "ERROR"))

    headers = ("MODEL", "CAPABILITIES", "NATIVE TOOLS")
    widths = [len(headers[index]) for index in range(3)]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    print("  ".join(headers[index].ljust(widths[index]) for index in range(3)))
    for row in rows:
        print("  ".join(row[index].ljust(widths[index]) for index in range(3)))
    return True


def _format_value(value):
    """trace 한 줄에 들어갈 값을 원본 변경 없이 짧게 표현한다."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        shown = list(value[:ARRAY_PREVIEW_LIMIT])
        body = ", ".join(_format_value(item) for item in shown)
        if len(value) > ARRAY_PREVIEW_LIMIT:
            return f"[{body}, …] (총 {len(value)}개)"
        return f"[{body}]"
    if isinstance(value, dict):
        body = ", ".join(
            f"{key}={_format_value(item)}" for key, item in value.items()
        )
        return "{" + body + "}"
    return str(value)


def _wrap_trace_items(prefix, items, continuation="     ", separator=" | "):
    """구분자로 연결한 trace 항목을 읽기 좋은 폭에서 줄바꿈한다."""
    if not items:
        return [prefix.rstrip()]

    lines = []
    current = prefix + items[0]
    for item in items[1:]:
        addition = separator + item
        if len(current) + len(addition) <= TRACE_LINE_WIDTH:
            current += addition
        else:
            lines.append(current)
            current = continuation + item
    lines.append(current)
    return lines


def _format_argument_items(arguments):
    """Direct Tool 인자를 전달된 이름과 값 그대로 표시한다."""
    if not isinstance(arguments, dict):
        return [f"arguments={_format_value(arguments)}"]

    return [
        f"{key}={_format_value(value)}" for key, value in arguments.items()
    ]


def _format_period(period):
    """결과 period를 날짜 범위 한 항목으로 만든다."""
    if not isinstance(period, dict):
        return None
    start = period.get("date_start")
    end = period.get("date_end")
    if start is not None or end is not None:
        value = _format_value(start)
        if end != start:
            value += f"~{_format_value(end)}"
        return f"date={value}"
    relative = period.get("time_relative_date")
    if relative is not None:
        return f"period={_format_value(relative)}"
    return None


def _metric_name(key, metric):
    if key == "value" and metric:
        return str(metric).lower()
    return key


def _value_with_unit(value, unit):
    shown = _format_value(value)
    return f"{shown} {unit}" if unit else shown


def _format_result_row(row, metric=None, unit=None):
    """TIMS 행 하나를 식별자와 측정값 중심으로 압축한다."""
    if not isinstance(row, dict):
        return _value_with_unit(row, unit)

    values = dict(row)
    label = None
    if "district_origin" in values or "district_destination" in values:
        origin = values.pop("district_origin", None)
        destination = values.pop("district_destination", None)
        label = f"{_format_value(origin)}→{_format_value(destination)}"
    elif "district_name" in values:
        label = _format_value(values.pop("district_name"))
        values.pop("district_code", None)
    elif "week_start" in values or "week_end" in values:
        start = values.pop("week_start", None)
        end = values.pop("week_end", None)
        label = _format_value(start)
        if end != start:
            label += f"~{_format_value(end)}"
    else:
        for key in ("place_name", "day_of_week", "date", "month", "edge", "h3"):
            if key in values:
                label = _format_value(values.pop(key))
                break

    formatted = [
        f"{_metric_name(key, metric)}={_value_with_unit(value, unit)}"
        for key, value in values.items()
        if value is not None
    ]
    if not formatted:
        return label or "결과 없음"
    if label is None:
        return ", ".join(formatted)
    if len(formatted) == 1:
        return f"{label}={formatted[0].split('=', 1)[1]}"
    return f"{label}({', '.join(formatted)})"


def _format_success_result(result):
    period = _format_period(result.get("period"))
    results = result.get("results")
    metric = result.get("metric")
    unit = result.get("unit")

    if isinstance(results, list):
        rows = [_format_result_row(row, metric, unit) for row in results]
        if not rows:
            items = ["결과 없음"]
        elif len(rows) <= INLINE_RESULT_LIMIT:
            lines = _wrap_trace_items("  ← ", rows, separator=", ")
            if period:
                period_addition = f" | {period}"
                if len(lines[-1]) + len(period_addition) <= TRACE_LINE_WIDTH:
                    lines[-1] += period_addition
                else:
                    lines.append(f"     {period}")
            return lines
        else:
            header = f"{len(rows)}건"
            if period:
                header += f" | {period}"
            return [f"  ← {header}", *[
                f"     {index}. {row}" for index, row in enumerate(rows, start=1)
            ]]
        if period:
            items.append(period)
        return _wrap_trace_items("  ← ", items)

    visible = {
        key: value
        for key, value in result.items()
        if key not in RESULT_METADATA_KEYS and value is not None
    }
    label = None
    for key in ("district_name", "place_name"):
        if key in visible:
            label = _format_value(visible.pop(key))
            break
    items = ([label] if label else []) + [
        f"{key}={_format_value(value)}" for key, value in visible.items()
    ]
    if period:
        items.append(period)
    return _wrap_trace_items("  ← ", items or ["SUCCESS"])


def _format_error_result(result):
    code = _format_value(result.get("error_code"))
    lines = [f"  ← ERROR | {code}"]
    message = result.get("message")
    if message is not None:
        lines.append(f"     {_format_value(message)}")
    details = [
        f"{key}={_format_value(value)}"
        for key, value in result.items()
        if key not in {"status", "error_code", "operation", "message"}
        and value is not None
    ]
    lines.extend(_wrap_trace_items("     ", details) if details else [])
    return lines


def _format_result_lines(result):
    if not isinstance(result, dict):
        return [f"  ← {_format_value(result)}"]
    if result.get("status") == "ERROR":
        return _format_error_result(result)
    return _format_success_result(result)


def _format_hop(
    hop_number,
    tool_name,
    arguments,
    result,
    *,
    markdown=False,
    tool_index=1,
    tool_count=1,
):
    """콘솔과 Markdown이 공유하는 compact Tool trace를 만든다."""
    if tool_count > 1:
        heading = (
            f"#### Tool {tool_index}/{tool_count} — {tool_name}"
            if markdown else f"[Tool {tool_index}/{tool_count}] {tool_name}"
        )
    else:
        heading = (
            f"### Hop {hop_number} — {tool_name}"
            if markdown else f"[Hop {hop_number}] {tool_name}"
        )
    argument_lines = _wrap_trace_items("  → ", _format_argument_items(arguments))
    return "\n".join([heading, *argument_lines, *_format_result_lines(result)])


def _format_outcome(final_answer, runtime_error, *, markdown=False):
    answer_heading = "### Answer" if markdown else "[Answer]"
    runtime_heading = "### Runtime" if markdown else "[Runtime]"
    answer = final_answer if final_answer is not None else "(없음)"
    runtime = f"ERROR\n{runtime_error}" if runtime_error else "OK"
    separator = "\n\n" if markdown else "\n"
    runtime_line = f"{runtime_heading}\n{runtime}" if markdown else f"{runtime_heading} {runtime}"
    return f"{answer_heading}\n{answer}{separator}{runtime_line}"


def _make_graph_event_handler():
    """StateGraph 사건을 compact trace 형식으로 출력한다."""
    def handle(event, payload):
        hop = payload.get("hop")
        if event == "model_response":
            if verbose:
                thinking = (payload["message"].get("thinking") or "").strip()
                if thinking:
                    if verbose == 'short':
                        thinking = thinking[:400] + ("..." if len(thinking) > 400 else "")
                    print(f"\n[Thinking | Model Hop {hop}]\n{thinking}")
        elif event == "multiple_tool_calls":
            print(
                f"\n[Model Hop {hop}] "
                f"{payload['count']}개의 Tool Call이 동시에 생성됨"
            )
        elif event == "tool_call":
            tool_count = payload.get("tool_count", 1)
            if tool_count > 1:
                print(
                    f"\n  [Tool {payload['tool_index']}/{tool_count}] "
                    f"{payload['tool_name']}"
                )
                print("\n".join(_wrap_trace_items(
                    "    → ", _format_argument_items(payload["arguments"]),
                    continuation="       ",
                )))
            else:
                print(f"\n[Hop {payload.get('model_hop', hop)}] {payload['tool_name']}")
                print("\n".join(_wrap_trace_items(
                    "  → ", _format_argument_items(payload["arguments"]),
                )))
        elif event == "tool_result":
            result_lines = _format_result_lines(payload["result"])
            if payload.get("tool_count", 1) > 1:
                result_lines = [f"  {line}" for line in result_lines]
            print("\n".join(result_lines))
        elif event == "model_error":
            print(f"\n[Model Hop {hop}] ERROR | {payload['error']}")
        elif event == "tool_error":
            indent = "    " if payload.get("tool_count", 1) > 1 else "  "
            print(f"{indent}← ERROR\n{indent}   {payload['error']}")
        elif event == "max_hops":
            print(f"\n[Max Hops] ERROR | {payload['error']}")
        elif event == "geoflow_plan":
            macros = payload.get("applied_macros") or []
            print(f"\n[Compose] {' + '.join(macros) or payload['template']}")
            print("\n".join(_wrap_trace_items(
                "  → ", _format_argument_items(payload["slots"]),
            )))
        elif event == "geoflow_validation":
            report = payload["report"]
            status = report.get("status")
            if status == "OK":
                print(f"[Validation] OK | {len(report['checked_rules'])}개 규칙 통과")
            else:
                print(f"[Validation] ERROR | {', '.join(report['failed_rules'])}")
                for item in report["errors"]:
                    print(f"     {item['message']}")
        elif event == "geoflow_repair":
            failure = payload["failure"]
            if "concept" in failure:
                print(
                    f"\n[Repair {payload['attempt']}] "
                    f"concept={failure['concept']} name={failure['name']} "
                    f"조회 실패 → Planner에 값 수정 요청"
                )
            else:
                # 계획 단계 재질의(조건 보완 등). payload 모양이 장소 조회와 다르다.
                print(
                    f"\n[Repair {payload['attempt']}] "
                    f"{failure.get('stage')}/{failure.get('code')} "
                    f"({failure.get('kind')}) → Planner에 수정 요청"
                )
        elif event == "geoflow_execution_plan":
            steps = payload["execution_plan"]["steps"]
            names = " → ".join(step["tool_name"] for step in steps)
            print(f"[Execution Plan] {len(steps)} step | {names}")

    return handle


def _print_result_footer(result):
    if not result["hop_log"]:
        print("\n[Tool] 호출 없음")
    print("\n" + _format_outcome(
        result["final_answer"], result["runtime_error"],
    ))


def _new_runtime(tools, system_prompt, *, tool_handlers=None, agent_mode=None):
    """현재 CLI 설정과 YAML Config로 UI 독립 Runtime을 만든다."""
    selected_handlers = (
        get_tool_handlers() if tool_handlers is None else tool_handlers
    )
    selected_mode = AGENT_MODE if agent_mode is None else agent_mode
    client = get_ollama_client()
    tool_executor = ToolExecutor(tools=tools, handlers=selected_handlers)
    geoflow = None
    if selected_mode == AGENT_MODE_GEOFLOW:
        try:
            geoflow = GeoFlowPipeline.create(
                client=client,
                tool_executor=tool_executor,
                model=MODEL_NAME,
            )
        except GeoFlowError as error:
            raise SystemExit(f"GeoFlow 구성 실패: {error.detail}") from error
    return AssistantRuntime(
        client=client,
        tools=tools,
        system_prompt=system_prompt,
        tool_executor=tool_executor,
        model=MODEL_NAME,
        agent_mode=selected_mode,
        geoflow=geoflow,
    )


def run_agent_question(
    question,
    tools,
    system_prompt,
    max_hops=MAX_TOOL_HOPS,
    runtime=None,
):
    """native Tool 모델의 AssistantRuntime 실행 경로."""
    selected_runtime = runtime or _new_runtime(tools, system_prompt)
    result = selected_runtime.run_question(
        question,
        max_hops=max_hops,
        event_handler=_make_graph_event_handler(),
    )
    if (
        result["runtime_error"]
        and str(result["runtime_error"]).startswith("LangGraph 실행 실패:")
    ):
        print(f"\n[ERROR] {result['runtime_error']}")

    _print_result_footer(result)
    return result


def _now_local():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def _new_run_id():
    return _now_local().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _write_json(path, value):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)


def _sha256_text(source):
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _baseline_config_sources():
    """현재 baseline Config YAML 원본을 읽는다."""
    paths = [Path(BASE_DIR) / "prompts" / "system.yaml"]
    paths.extend(sorted((Path(BASE_DIR) / "schemas").glob("*.yaml")))
    return {
        path.relative_to(BASE_DIR).as_posix(): path.read_text(encoding="utf-8")
        for path in paths
    }


def _build_with_config_snapshot(max_attempts=3):
    """build 전후 Config가 같은 revision일 때 결과와 source를 함께 확정한다."""
    for _attempt in range(max_attempts):
        before = _baseline_config_sources()
        tools, system_prompt = build()
        after = _baseline_config_sources()
        if before == after:
            return tools, system_prompt, before
    raise RuntimeError(
        f"Config가 build 중 계속 변경되어 {max_attempts}회 시도 후 중단했습니다."
    )


def _load_queries_with_source(path):
    """같은 파일 revision에서 Query 목록과 snapshot source를 함께 얻는다."""
    path = Path(path)
    for _attempt in range(3):
        before = path.read_text(encoding="utf-8")
        queries = load_queries(path)
        after = path.read_text(encoding="utf-8")
        if before == after:
            return queries, before
    raise QueryValidationError(
        f"Query 파일이 로딩 중 계속 변경되었습니다: {path}"
    )


def _raw_record(item, result):
    record = {
        "id": item["id"],
        "question": item["question"],
        "agent_mode": result.get("agent_mode", AGENT_MODE_REACT),
        "hops": [dict(hop) for hop in result["hop_log"]],
        "model_calls": [dict(call) for call in result.get("model_calls", [])],
        "total_duration_ms": result.get("total_duration_ms"),
        "final_answer": result["final_answer"],
        "runtime_error": result["runtime_error"],
        "runtime_status": "ERROR" if result["runtime_error"] else "OK",
        "cancelled": bool(result.get("cancelled")),
    }
    geoflow = result.get("geoflow")
    if geoflow is not None:
        # planner output / template / slots / plan / validation /
        # execution plan / trace / 단계별 소요 시간을 그대로 보존한다.
        record["geoflow"] = geoflow
    return record


def _geoflow_report_lines(geoflow):
    """geoflow mode 실행의 planning 과정을 사람이 읽을 수 있게 정리한다."""
    lines = ["### Grounding", ""]
    grounding = geoflow.get("grounding") or {}
    concepts = grounding.get("concepts") or []
    if concepts:
        for node in concepts:
            text = f" \"{node['text']}\"" if node.get("text") else ""
            lines.append(
                f"- `{node['id']}`{text} = {node['concept']}/{node['subtype']}"
                f" role={node['role']} source={node['source']}"
            )
    else:
        lines.append("- (grounding 실패)")
    factors = grounding.get("factors") or {}
    if factors:
        lines.append("- Factors:")
        for key, value in factors.items():
            lines.append(f"  - `{key}` = {_format_value(value)}")
    duration = (geoflow.get("durations") or {}).get("planner_ms")
    if duration is not None:
        lines.append(f"- Planner 소요: {duration:g} ms")
    lines.append("")

    macros = geoflow.get("applied_macros") or []
    lines.extend(["### Macro Composition", ""])
    lines.append(
        "- 적용된 조각: "
        + (" + ".join(f"`{name}`" for name in macros) or "(합성 실패)")
    )
    unused = (geoflow.get("plan") or {}).get("unused_factors") or {}
    if unused:
        lines.append(
            "- 이 Tool이 받지 않아 빠진 조건: "
            + ", ".join(f"`{key}`" for key in unused)
        )
    lines.append("")

    plan = geoflow.get("plan")
    if plan:
        lines.extend(["### GeoFlow", "", "```text"])
        for node in plan["concepts"]:
            lines.append(
                f"[{node['id']}] {node['concept']}/{node['subtype']} "
                f"role={node['role']} source={node['source']}"
            )
        for transformation in plan["transformations"]:
            inputs = ", ".join(
                f"{port}←{ref['$ref']}"
                + (f".{ref['field']}" if ref.get("field") else "")
                for port, ref in transformation["inputs"].items()
            )
            outputs = ", ".join(transformation["outputs"])
            lines.append(
                f"({transformation['id']}) {transformation['operator']}"
                f"({inputs}) → {outputs}"
            )
        lines.append(f"final_node = {plan['final_node']}")
        lines.extend(["```", ""])

    validation = geoflow.get("validation")
    if validation:
        lines.extend(["### Validation", ""])
        if validation["status"] == "OK":
            lines.append(
                f"OK — {', '.join(validation['checked_rules'])} 통과"
            )
        else:
            lines.append(f"ERROR — {', '.join(validation['failed_rules'])}")
            for error in validation["errors"]:
                lines.append(f"- [{error['rule']}] {error['message']}")
        lines.append("")

    execution_plan = geoflow.get("execution_plan")
    if execution_plan:
        lines.extend(["### Tool Steps", ""])
        for index, step in enumerate(execution_plan["steps"], start=1):
            covers = ", ".join(step.get("covers") or [])
            group = (step.get("group") or {}).get("label")
            lines.append(
                f"{index}. `{step['operator']}` → `{step['tool_name']}`"
                + (f" (의미 단계: {covers})" if covers else "")
                + (f" [구간 {group}]" if group else "")
            )
        for node_id, reason in (execution_plan.get("unobserved") or {}).items():
            lines.append(f"- `{node_id}`: {reason}")
        for step_id, period in (execution_plan.get("periods") or {}).items():
            lines.append(
                f"- `{step_id}` 기간 {period['period']} → {period['resolved']} "
                f"({period['bucket']} {len(period['groups'])}개, {period['boundary']})"
            )
        lines.append("")

    error = geoflow.get("error")
    if error:
        lines.extend([
            "### GeoFlow Error",
            "",
            f"- Stage: {error.get('stage')}",
            f"- Code: {error.get('code')}",
            f"- Detail: {error.get('detail')}",
            "",
        ])
    return lines


def _write_query_report(path, records, timestamp):
    lines = [
        "# Query Suite Raw Execution Report",
        "",
        f"- Model: {MODEL_NAME}",
        f"- Agent mode: {AGENT_MODE}",
        f"- Timestamp: {timestamp}",
        "- 실행 trace만 기록하며 응답의 정답 여부는 판정하지 않습니다.",
        "",
    ]
    for index, record in enumerate(records, start=1):
        repeat_label = (
            f" / Repeat {record['repeat_index']}"
            if record.get("repeat_index") is not None
            else ""
        )
        lines.extend([
            f"## Q{index}. {record['id']}{repeat_label}",
            "",
            record["question"],
            "",
        ])
        if record.get("geoflow"):
            lines.extend(_geoflow_report_lines(record["geoflow"]))
        if record["hops"]:
            for hop_index, hop in enumerate(record["hops"], start=1):
                lines.extend([
                    _format_hop(
                        hop.get("model_hop", hop_index),
                        hop["tool"],
                        hop["arguments"],
                        hop["result"],
                        markdown=True,
                        tool_index=hop.get("tool_index", 1),
                        tool_count=hop.get("tool_count", 1),
                    ),
                    "",
                ])
        else:
            lines.extend(["Tool Calls: 없음", ""])
        lines.extend([
            _format_outcome(
                record["final_answer"],
                record["runtime_error"],
                markdown=True,
            ),
            "",
        ])
    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


def _save_query_run(
    timestamp,
    records,
    *,
    repeat=1,
    requested_query_ids=None,
    query_source=None,
    query_source_type="yaml",
    config_sources=None,
    tool_provider=DEFAULT_TOOL_PROVIDER,
):
    run_id = _new_run_id()
    run_dir = os.path.join(RUNS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=False)
    requested_query_ids = list(requested_query_ids or [])
    config_sources = dict(config_sources or {})
    config_hash = {
        relative: _sha256_text(source)
        for relative, source in config_sources.items()
    }
    raw = {
        "model": MODEL_NAME,
        "agent_mode": AGENT_MODE,
        "chat_timeout_seconds": CHAT_TIMEOUT,
        "timestamp": timestamp,
        "query_count": len(records),
        "query_source_type": query_source_type,
        "query_source_sha256": (
            _sha256_text(query_source) if query_source is not None else None
        ),
        "requested_query_ids": requested_query_ids,
        "repeat": repeat,
        "requested_attempt_count": len(requested_query_ids) * repeat,
        "tool_provider": tool_provider,
        "config_hash": config_hash,
        "queries": records,
    }
    for relative, source in config_sources.items():
        target = os.path.join(run_dir, "config", relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as file:
            file.write(source)
    if query_source is not None:
        input_dir = os.path.join(run_dir, "input")
        os.makedirs(input_dir, exist_ok=True)
        with open(
            os.path.join(input_dir, "stub_query.yaml"),
            "w",
            encoding="utf-8",
        ) as file:
            file.write(query_source)
    _write_json(os.path.join(run_dir, "query_raw.json"), raw)
    _write_query_report(
        os.path.join(run_dir, "query_report.md"),
        records,
        timestamp,
    )
    return run_dir


def run_query_suite(
    queries,
    tools,
    system_prompt,
    *,
    repeat=1,
    runtime_factory=None,
    tool_handlers=None,
    save=True,
    query_source=None,
    query_source_type="yaml",
    tool_provider=None,
    config_sources=None,
):
    """각 Query/repeat마다 독립 Runtime state로 실행한다."""
    if repeat < 1:
        raise ValueError("repeat는 1 이상이어야 합니다.")
    make_runtime = runtime_factory or (
        lambda: _new_runtime(
            tools,
            system_prompt,
            tool_handlers=tool_handlers,
        )
    )
    if save and config_sources is None:
        raise ValueError(
            "저장 실행에는 build와 함께 확정한 config_sources가 필요합니다."
        )
    config_sources = dict(config_sources or {})
    records = []
    for item in queries:
        for repeat_index in range(1, repeat + 1):
            print("\n" + "=" * 50)
            print(f"{item['id']} / Repeat {repeat_index}")
            print(item["question"])
            print("=" * 50)
            runtime = make_runtime()
            result = run_agent_question(
                item["question"],
                tools,
                system_prompt,
                runtime=runtime,
            )
            record = _raw_record(item, result)
            record["repeat_index"] = repeat_index
            records.append(record)

    timestamp = _now_local().isoformat()
    run_dir = (
        _save_query_run(
            timestamp,
            records,
            repeat=repeat,
            requested_query_ids=[item["id"] for item in queries],
            query_source=query_source,
            query_source_type=query_source_type,
            config_sources=config_sources,
            tool_provider=(
                tool_provider
                or os.environ.get(TOOL_PROVIDER_ENV, DEFAULT_TOOL_PROVIDER)
            ),
        )
        if save else None
    )
    runtime_error_count = sum(
        1 for record in records if record["runtime_error"]
    )
    print(f"\nQuery {len(records)}개 실행 완료")
    print(f"정상 실행: {len(records) - runtime_error_count}")
    print(f"Runtime error: {runtime_error_count}")
    if run_dir:
        print(f"결과 파일: {run_dir}")
    return {"records": records, "run_dir": run_dir}


def positive_int(value):
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("1 이상의 정수여야 합니다.")
    return parsed


def positive_chat_timeout(value):
    try:
        return resolve_chat_timeout(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="GBTA Assistant Standalone Query 평가 CLI",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL_NAME),
        help=f"Ollama 모델명(기본: {DEFAULT_MODEL_NAME})",
    )
    parser.add_argument(
        "--ollama-host",
        default=os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST),
        help=f"Ollama 주소(기본: {DEFAULT_OLLAMA_HOST})",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="설치 모델과 native Tool capability를 출력하고 종료",
    )
    parser.add_argument(
        "--agent-mode",
        choices=AGENT_MODES,
        default=DEFAULT_AGENT_MODE,
        help=(
            "실행 모드. react=기존 순차 Tool Calling, "
            f"geoflow=GeoFlow planning 후 결정적 실행(기본: {DEFAULT_AGENT_MODE})"
        ),
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--query", help="실행할 단일 자연어 Query")
    source.add_argument("--query-file", help="실행할 Query YAML 경로")
    parser.add_argument(
        "--query-id",
        action="append",
        help="Query YAML에서 실행할 전체 ID 또는 qNN 단축 ID(여러 번 지정 가능)",
    )
    parser.add_argument(
        "--chat-timeout",
        type=positive_chat_timeout,
        help="Ollama /api/chat 요청별 timeout(초)",
    )
    parser.add_argument(
        "--repeat",
        type=positive_int,
        default=1,
        help="각 Query의 독립 반복 실행 횟수(기본: 1)",
    )
    parser.add_argument(
        "--verbose",
        choices=("full", "short"),
        help="model thinking 출력 수준",
    )
    parser.add_argument(
        "--model-think",
        choices=THINK_CHOICES,
        default="auto",
        help=(
            "모델 thinking 사용 여부. auto=모델 기본값, on/off=명시 지정"
            "(기본: auto). --verbose는 출력 수준이고 이것은 모델 동작이다."
        ),
    )
    parser.add_argument(
        "--num-predict",
        type=positive_int,
        help="model 응답 1회의 생성 토큰 상한(기본: 모델 기본값)",
    )
    args = parser.parse_args(argv)
    if not args.list_models and args.query is None and args.query_file is None:
        parser.error("--query 또는 --query-file 중 하나가 필요합니다.")
    if args.query_id and args.query_file is None:
        parser.error("--query-id는 --query-file과 함께 사용해야 합니다.")
    try:
        args.chat_timeout = resolve_chat_timeout(args.chat_timeout)
    except ValueError as error:
        parser.error(str(error))
    return args


def main(argv=None):
    global verbose
    args = parse_args(argv)
    verbose = args.verbose
    if args.list_models:
        raise SystemExit(
            0 if list_installed_models(args.ollama_host) else 1
        )

    if args.query is not None:
        question = args.query.strip()
        if not question:
            raise SystemExit("--query는 비어 있을 수 없습니다.")
        queries = [{"id": "cli_query", "question": question}]
        query_source = None
        query_source_type = "cli_query"
    else:
        try:
            queries, query_source = _load_queries_with_source(args.query_file)
            queries = select_queries(queries, args.query_id)
            query_source_type = "yaml"
        except (QueryValidationError, QuerySelectionError) as error:
            raise SystemExit(str(error)) from error

    try:
        tool_handlers = get_tool_handlers()
    except ValueError as error:
        raise SystemExit(str(error)) from error

    configure_agent_mode(args.agent_mode)
    configure_ollama_client(
        args.ollama_host,
        args.model,
        args.chat_timeout,
        think=resolve_think(args.model_think),
        num_predict=args.num_predict,
    )
    print(
        f"설정 — 모델: {MODEL_NAME} / 주소: {OLLAMA_HOST} "
        f"/ chat timeout: {CHAT_TIMEOUT:g}초 / agent mode: {AGENT_MODE} "
        f"/ think: {args.model_think} "
        f"/ num_predict: {args.num_predict or '모델 기본값'}"
    )
    check_ollama_connection()
    try:
        tools, system_prompt, config_sources = _build_with_config_snapshot()
    except (OSError, RuntimeError) as error:
        raise SystemExit(str(error)) from error
    return run_query_suite(
        queries,
        tools,
        system_prompt.strip(),
        repeat=args.repeat,
        tool_handlers=tool_handlers,
        query_source=query_source,
        query_source_type=query_source_type,
        tool_provider=os.environ.get(
            TOOL_PROVIDER_ENV, DEFAULT_TOOL_PROVIDER
        ),
        config_sources=config_sources,
    )


if __name__ == "__main__":
    main()
