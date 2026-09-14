# -*- coding: utf-8 -*-
"""CLI와 Web이 공유하는 UI 독립 Assistant 실행 Runtime."""

import copy
import time

from agent_graph import extract_scopes, run_agent_graph


MAX_TOOL_HOPS = 10

#: agent 실행 모드. 기존 동작 보존을 위해 기본값은 react다.
AGENT_MODE_REACT = "react"
AGENT_MODE_GEOFLOW = "geoflow"
AGENT_MODES = (AGENT_MODE_REACT, AGENT_MODE_GEOFLOW)
DEFAULT_AGENT_MODE = AGENT_MODE_REACT


def _duration_ms(started_at):
    return round((time.perf_counter() - started_at) * 1000, 3)


class AssistantRuntime:
    """외부에서 받은 client와 YAML Config 값으로 질문을 실행한다."""

    def __init__(
        self,
        *,
        client,
        tools,
        system_prompt,
        tool_executor,
        model=None,
        agent_mode=DEFAULT_AGENT_MODE,
        geoflow=None,
    ):
        if agent_mode not in AGENT_MODES:
            raise ValueError(
                f"지원하지 않는 agent mode입니다: {agent_mode} "
                f"(사용 가능: {', '.join(AGENT_MODES)})"
            )
        if agent_mode == AGENT_MODE_GEOFLOW and geoflow is None:
            raise ValueError("geoflow mode에는 GeoFlow pipeline이 필요합니다.")
        self.client = client
        self.tools = tools
        self.system_prompt = system_prompt
        self.tool_executor = tool_executor
        self.model = model if model is not None else getattr(client, "model", None)
        self.agent_mode = agent_mode
        self.geoflow = geoflow

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
            "agent_mode": self.agent_mode,
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

        if self.agent_mode == AGENT_MODE_GEOFLOW:
            self._run_geoflow(
                question,
                result,
                event_handler=event_handler,
                cancel_checker=cancel_checker,
            )
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

    def _run_geoflow(self, question, result, *, event_handler, cancel_checker):
        """GeoFlow 파이프라인 결과를 기존 결과 계약에 맞춰 채운다."""
        try:
            run = self.geoflow.run(
                question,
                event_handler=event_handler,
                cancel_checker=cancel_checker,
            )
        except Exception as error:  # noqa: BLE001 - 예기치 못한 실패도 결과로 반환
            result["runtime_error"] = (
                f"GeoFlow 실행 실패: {type(error).__name__}: {error}"
            )
            return result

        planner_duration = run.durations.get("planner_ms")
        result.update({
            "hop_log": [dict(entry) for entry in run.hop_log],
            "model_calls": [{
                "event": "model_call",
                "model_hop": 1,
                "phase": "geoflow_planner",
                "duration_ms": planner_duration,
                "error": (
                    run.error.get("detail")
                    if run.error and run.error.get("stage") == "planner"
                    else None
                ),
            }],
            "final_answer": run.final_answer,
            "runtime_error": run.runtime_error,
            "cancelled": bool(run.cancelled),
            "geoflow": run.to_dict(),
        })
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
            "agent_mode": self.agent_mode,
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

        if self.agent_mode == AGENT_MODE_GEOFLOW:
            # GeoFlow v1은 turn별 독립 실행이다. 이전 대화는 참조하지 않지만
            # 확인된 scope와 대화 기록은 기존 계약대로 이어서 반환한다.
            self._run_geoflow(
                question,
                result,
                event_handler=event_handler,
                cancel_checker=cancel_checker,
            )
            answer = result["final_answer"]
            result["messages"] = [
                *previous_messages,
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer or ""},
            ]
            result["known_scopes"] = sorted(
                set(previous_scopes)
                | set(extract_scopes(question))
                | _trace_scopes(result["hop_log"])
            )
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


def _trace_scopes(hop_log):
    """GeoFlow 실행 trace의 성공 결과에서 확인된 scope를 모은다."""
    scopes = set()
    for entry in hop_log or ():
        scopes.update(extract_scopes(entry.get("result")))
    return scopes
