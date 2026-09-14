# -*- coding: utf-8 -*-
"""CLI와 Web이 공유하는 UI 독립 Assistant 실행 Runtime."""

import copy
import time

from agent_graph import run_agent_graph


MAX_TOOL_HOPS = 10


def _duration_ms(started_at):
    return round((time.perf_counter() - started_at) * 1000, 3)


class AssistantRuntime:
    """외부에서 받은 client와 YAML Config 값으로 질문을 실행한다."""

    def __init__(self, *, client, tools, system_prompt, tool_executor, model=None):
        self.client = client
        self.tools = tools
        self.system_prompt = system_prompt
        self.tool_executor = tool_executor
        self.model = model if model is not None else getattr(client, "model", None)

    def initial_messages(self, question):
        """전달받은 System Prompt를 변경 없이 첫 message에 사용한다."""
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": question},
        ]

    def turn_messages(self, question, history):
        """System Prompt와 이전 대화, 현재 질문으로 새 Turn 입력을 만든다."""
        return [
            {"role": "system", "content": self.system_prompt},
            *_copy_messages(history),
            {"role": "user", "content": question},
        ]

    def run_question(
        self,
        question,
        *,
        max_hops=MAX_TOOL_HOPS,
        event_handler=None,
        cancel_checker=None,
    ):
        """질문 하나를 실행하고 UI에 독립적인 구조화 결과를 반환한다."""
        started_at = time.perf_counter()
        result = {
            "question": question,
            "model": self.model,
            "hop_log": [],
            "model_calls": [],
            "final_answer": None,
            "runtime_error": None,
            "cancelled": False,
            "total_duration_ms": 0.0,
        }

        if cancel_checker is not None and cancel_checker():
            result["cancelled"] = True
            result["total_duration_ms"] = _duration_ms(started_at)
            return result

        try:
            state = run_agent_graph(
                self.client,
                self.initial_messages(question),
                self.tools,
                self.tool_executor,
                max_hops=max_hops,
                event_handler=event_handler,
                cancel_checker=cancel_checker,
            )
        except Exception as error:
            result["runtime_error"] = f"LangGraph 실행 실패: {error}"
            result["total_duration_ms"] = _duration_ms(started_at)
            return result

        result.update({
            "hop_log": state.get("hop_log") or [],
            "model_calls": state.get("model_calls") or [],
            "final_answer": state.get("final_answer"),
            "runtime_error": state.get("error"),
            "cancelled": bool(state.get("cancelled")),
        })
        result["total_duration_ms"] = _duration_ms(started_at)
        return result

    def run_turn(
        self,
        question,
        *,
        history,
        known_scopes,
        max_hops=MAX_TOOL_HOPS,
        event_handler=None,
        cancel_checker=None,
    ):
        """이전 대화 상태로 Turn을 실행하고 commit 전 후보 상태를 반환한다."""
        started_at = time.perf_counter()
        previous_messages = _copy_messages(history)
        previous_scopes = sorted(set(known_scopes))
        result = {
            "question": question,
            "model": self.model,
            "hop_log": [],
            "model_calls": [],
            "final_answer": None,
            "runtime_error": None,
            "cancelled": False,
            "messages": previous_messages,
            "known_scopes": previous_scopes,
            "total_duration_ms": 0.0,
        }

        if cancel_checker is not None and cancel_checker():
            result["cancelled"] = True
            result["total_duration_ms"] = _duration_ms(started_at)
            return result

        try:
            state = run_agent_graph(
                self.client,
                self.turn_messages(question, previous_messages),
                self.tools,
                self.tool_executor,
                max_hops=max_hops,
                event_handler=event_handler,
                cancel_checker=cancel_checker,
                initial_known_scopes=previous_scopes,
            )
        except Exception as error:
            result["runtime_error"] = f"LangGraph 실행 실패: {error}"
            result["total_duration_ms"] = _duration_ms(started_at)
            return result

        state_messages = list(state.get("messages") or [])
        result.update({
            "hop_log": state.get("hop_log") or [],
            "model_calls": state.get("model_calls") or [],
            "final_answer": state.get("final_answer"),
            "runtime_error": state.get("error"),
            "cancelled": bool(state.get("cancelled")),
            "messages": _copy_messages(state_messages[1:]),
            "known_scopes": list(state.get("known_scopes") or []),
        })
        result["total_duration_ms"] = _duration_ms(started_at)
        return result


def _copy_messages(messages):
    """Conversation 전체가 아닌 mutable message 목록만 복사한다."""
    return copy.deepcopy(list(messages or []))
