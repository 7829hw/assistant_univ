# -*- coding: utf-8 -*-
"""LangGraph ``StateGraph`` 기반 GBTA Tool Agent 실행 루프."""

import json
import re
import time
from typing import Any, Callable, Literal, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from tool_executor import invalid_argument_result


class ToolHop(TypedDict):
    """Tool Call 하나와 이를 생성한 model response 위치를 보존한다."""

    model_hop: int
    tool_index: int
    tool_count: int
    tool: str
    arguments: Any
    result: Any
    error: NotRequired[str]
    duration_ms: float


class AgentState(TypedDict):
    """Ollama native dict message와 사람이 검토할 실행 로그를 보존하는 상태."""

    messages: list[dict]
    hop_log: list[ToolHop]
    model_calls: list[dict]
    hop_count: int
    final_answer: str | None
    error: str | None
    last_response: dict | None
    error_counts: dict[str, int]
    known_scopes: list[str]
    cancelled: bool


EventHandler = Callable[[str, dict], None]
CancelChecker = Callable[[], bool]


def _duration_ms(started_at):
    """단조 시계 기준 경과 시간을 millisecond로 반환한다."""
    return round((time.perf_counter() - started_at) * 1000, 3)


def build_tool_result_message(tool_name, result):
    """Ollama native Tool 결과 message를 만든다."""
    return {
        "role": "tool",
        "tool_name": tool_name,
        "content": json.dumps(result, ensure_ascii=False),
    }


SCOPE_PATTERN = re.compile(r"scope:[A-Za-z0-9_:.-]+")


def extract_scopes(value):
    """성공한 Tool 결과의 중첩 구조에서 scope 값을 재귀적으로 수집한다."""
    if isinstance(value, str):
        return set(SCOPE_PATTERN.findall(value))
    if isinstance(value, (list, tuple)):
        scopes = set()
        for item in value:
            scopes.update(extract_scopes(item))
        return scopes
    if isinstance(value, dict):
        if value.get("status") == "ERROR":
            return set()
        scopes = set()
        for item in value.values():
            scopes.update(extract_scopes(item))
        return scopes
    return set()


def scope_arguments(arguments):
    """현재와 향후 scope 계열 argument의 canonical 문자열을 수집한다."""
    if not isinstance(arguments, dict):
        return set()
    return {
        value
        for name, value in arguments.items()
        if (name == "scope" or name.startswith("scope_"))
        and isinstance(value, str)
        and SCOPE_PATTERN.fullmatch(value)
    }


def user_provided_scopes(messages):
    """System Prompt 예시는 제외하고 사용자 발화의 scope만 신뢰한다."""
    scopes = set()
    for message in messages:
        if message.get("role") == "user":
            scopes.update(extract_scopes(message.get("content")))
    return scopes


def build_agent_graph(
    client, tools, tool_executor, *, max_hops, event_handler=None,
    cancel_checker=None,
):
    """model↔execute_tools 반복을 수행하는 compiled ``StateGraph``를 만든다.

    ``max_hops``는 LangGraph step 수가 아니라 기존과 같은 model 호출 횟수다.
    """
    if max_hops < 1:
        raise ValueError("max_hops는 1 이상이어야 합니다.")

    def emit(event, **payload):
        if event_handler is not None:
            event_handler(event, payload)

    def cancellation_requested():
        return cancel_checker is not None and cancel_checker()

    def model_node(state: AgentState):
        hop = state["hop_count"] + 1
        model_calls = list(state["model_calls"])
        if cancellation_requested():
            emit("cancelled", phase="before_model", hop=hop)
            return {"cancelled": True, "last_response": None}
        started_at = time.perf_counter()
        try:
            body = client.chat(state["messages"], tools=tools)
        except Exception as error:
            duration_ms = _duration_ms(started_at)
            model_calls.append({
                "event": "model_call",
                "model_hop": hop,
                "phase": "agent",
                "duration_ms": duration_ms,
                "error": str(error),
            })
            emit("model_error", hop=hop, error=error, duration_ms=duration_ms)
            return {
                "hop_count": hop,
                "last_response": None,
                "error": str(error),
                "model_calls": model_calls,
            }

        duration_ms = _duration_ms(started_at)
        raw_message = body.get("message", {})
        raw_tool_calls = list(raw_message.get("tool_calls") or [])
        tool_calls = raw_tool_calls[:1]
        message = dict(raw_message)
        if tool_calls:
            message["tool_calls"] = tool_calls
        else:
            message.pop("tool_calls", None)

        if len(raw_tool_calls) > 1:
            emit(
                "multiple_tool_calls",
                hop=hop,
                count=len(raw_tool_calls),
                executed_count=1,
            )

        assistant_message = {
            "role": "assistant",
            "content": message.get("content", ""),
        }
        if tool_calls:
            assistant_message["tool_calls"] = tool_calls

        final_answer = None
        if not tool_calls:
            final_answer = (message.get("content") or "").strip()

        model_calls.append({
            "event": "model_call",
            "model_hop": hop,
            "phase": "tool_selection" if tool_calls else "final_response",
            "duration_ms": duration_ms,
            "error": None,
        })

        emit(
            "model_response",
            hop=hop,
            message=message,
            tool_calls=tool_calls,
            final_answer=final_answer,
            duration_ms=duration_ms,
        )
        return {
            "messages": [*state["messages"], assistant_message],
            "hop_count": hop,
            "last_response": message,
            "final_answer": final_answer,
            "model_calls": model_calls,
        }

    def route_after_model(state: AgentState) -> Literal["execute_tools", "__end__"]:
        if state.get("error") or state.get("cancelled"):
            return END
        message = state.get("last_response") or {}
        if message.get("tool_calls"):
            return "execute_tools"
        return END

    def execute_tools_node(state: AgentState):
        message = state.get("last_response") or {}
        tool_calls = message.get("tool_calls") or []
        hop = state["hop_count"]
        messages = list(state["messages"])
        hop_log = list(state["hop_log"])
        error_counts = dict(state["error_counts"])
        known_scopes = set(state["known_scopes"])
        event_position = {
            "model_hop": hop,
            "tool_index": 1,
            "tool_count": 1,
        }

        if cancellation_requested():
            emit("cancelled", phase="before_tool", hop=hop, **event_position)
            return {
                "messages": messages,
                "hop_log": hop_log,
                "error_counts": error_counts,
                "cancelled": True,
            }

        try:
            function = tool_calls[0]["function"]
            tool_name = function["name"]
            arguments = function["arguments"]
        except (IndexError, KeyError, TypeError) as error:
            detail = f"잘못된 Tool Call 형식: {error}"
            emit("tool_error", hop=hop, error=detail, **event_position)
            return {"messages": messages, "hop_log": hop_log, "error": detail}

        emit(
            "tool_call",
            hop=hop,
            tool_name=tool_name,
            arguments=arguments,
            **event_position,
        )
        tool_started_at = time.perf_counter()
        unverified_scopes = sorted(scope_arguments(arguments) - known_scopes)
        if unverified_scopes:
            shown = ", ".join(unverified_scopes)
            tool_result = invalid_argument_result(
                "이 scope는 사용자 입력 또는 이전 Tool 결과에서 확인되지 "
                f"않았습니다: {shown}. 장소 또는 지역의 scope가 필요하면 "
                "get_place_scope를 먼저 호출하세요. scope 값을 직접 생성하지 마세요."
            )
        else:
            try:
                tool_result = tool_executor.execute(tool_name, arguments)
            except Exception as error:
                duration_ms = _duration_ms(tool_started_at)
                exception_detail = f"{type(error).__name__}: {error}"
                hop_log.append({
                    **event_position,
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": None,
                    "error": exception_detail,
                    "duration_ms": duration_ms,
                })
                detail = f"ToolExecutor 실행 실패({tool_name}): {error}"
                emit(
                    "tool_error",
                    hop=hop,
                    error=detail,
                    tool_name=tool_name,
                    duration_ms=duration_ms,
                    **event_position,
                )
                return {"messages": messages, "hop_log": hop_log, "error": detail}

        duration_ms = _duration_ms(tool_started_at)
        hop_log.append({
            **event_position,
            "tool": tool_name,
            "arguments": arguments,
            "result": tool_result,
            "duration_ms": duration_ms,
        })
        messages.append(build_tool_result_message(tool_name, tool_result))
        emit(
            "tool_result",
            hop=hop,
            tool_name=tool_name,
            result=tool_result,
            duration_ms=duration_ms,
            **event_position,
        )

        is_error = (
            isinstance(tool_result, dict)
            and tool_result.get("status") == "ERROR"
        )
        if not is_error:
            known_scopes.update(extract_scopes(tool_result))
        else:
            error_code = tool_result.get("error_code", "TOOL_ERROR")
            error_message = tool_result.get("message", "Tool 실행 오류")
            if error_code == "TOOL_ERROR" or not tool_result.get("retryable", False):
                detail = (
                    f"재시도할 수 없는 Tool 오류({tool_name}/{error_code}): "
                    f"{error_message}"
                )
                emit(
                    "tool_error",
                    hop=hop,
                    error=detail,
                    tool_name=tool_name,
                    **event_position,
                )
                return {
                    "messages": messages,
                    "hop_log": hop_log,
                    "error_counts": error_counts,
                    "known_scopes": sorted(known_scopes),
                    "error": detail,
                }

            signature = json.dumps(
                {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "error_code": error_code,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            error_counts[signature] = error_counts.get(signature, 0) + 1
            if error_counts[signature] >= 2:
                detail = (
                    f"동일한 Tool 오류가 반복됨({tool_name}/{error_code}): "
                    f"{error_message}"
                )
                emit(
                    "tool_error",
                    hop=hop,
                    error=detail,
                    tool_name=tool_name,
                    **event_position,
                )
                return {
                    "messages": messages,
                    "hop_log": hop_log,
                    "error_counts": error_counts,
                    "known_scopes": sorted(known_scopes),
                    "error": detail,
                }

        if hop >= max_hops:
            detail = f"{max_hops}번 안에 최종 답변까지 못 감"
            emit("max_hops", hop=hop, max_hops=max_hops, error=detail)
            return {
                "messages": messages,
                "hop_log": hop_log,
                "error_counts": error_counts,
                "known_scopes": sorted(known_scopes),
                "error": detail,
            }

        return {
            "messages": messages,
            "hop_log": hop_log,
            "error_counts": error_counts,
            "known_scopes": sorted(known_scopes),
        }

    def route_after_tools(state: AgentState) -> Literal["model", "__end__"]:
        return END if state.get("error") or state.get("cancelled") else "model"

    graph = StateGraph(AgentState)
    graph.add_node("model", model_node)
    graph.add_node("execute_tools", execute_tools_node)
    graph.add_edge(START, "model")
    graph.add_conditional_edges(
        "model",
        route_after_model,
        {"execute_tools": "execute_tools", END: END},
    )
    graph.add_conditional_edges(
        "execute_tools",
        route_after_tools,
        {"model": "model", END: END},
    )
    return graph.compile()


def run_agent_graph(
    client,
    messages,
    tools,
    tool_executor,
    *,
    max_hops,
    event_handler=None,
    cancel_checker=None,
    initial_known_scopes=None,
):
    """초기 message를 받아 graph를 실행하고 최종 ``AgentState``를 반환한다."""
    graph = build_agent_graph(
        client,
        tools,
        tool_executor,
        max_hops=max_hops,
        event_handler=event_handler,
        cancel_checker=cancel_checker,
    )
    known_scopes = set(initial_known_scopes or ())
    known_scopes.update(user_provided_scopes(messages))
    initial_state: AgentState = {
        "messages": list(messages),
        "hop_log": [],
        "model_calls": [],
        "hop_count": 0,
        "final_answer": None,
        "error": None,
        "last_response": None,
        "error_counts": {},
        "known_scopes": sorted(known_scopes),
        "cancelled": False,
    }
    # model/execute_tools가 model hop마다 최대 2개 step을 사용하므로 LangGraph
    # 자체 recursion limit은 별도로 넉넉하게 두고 실제 제한은 hop_count로 지킨다.
    recursion_limit = max(2 * max_hops + 5, 25)
    return graph.invoke(initial_state, config={"recursion_limit": recursion_limit})
