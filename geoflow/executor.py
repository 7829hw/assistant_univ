# -*- coding: utf-8 -*-
"""ExecutionPlan의 deterministic 실행.

다음 Tool을 LLM에게 묻지 않고 compiler가 만든 순서대로 실행한다. 실제 Tool
호출과 JSON Schema 검증은 기존 ``ToolExecutor``를 그대로 재사용하며,
``agent_graph``의 scope provenance 정책도 여기서 한 번 더 확인한다.
"""

import time

from agent_graph import extract_scopes, scope_arguments
from tool_executor import invalid_argument_result

from geoflow.errors import ExecutionError
from geoflow.operator_registry import extract_output
from geoflow.types import ExecutionPlan, ExecutionResult, ValueRef

STATUS_OK = "OK"
STATUS_TOOL_ERROR = "TOOL_ERROR"
STATUS_EXECUTOR_ERROR = "EXECUTOR_ERROR"
STATUS_CANCELLED = "CANCELLED"


def _duration_ms(started_at):
    return round((time.perf_counter() - started_at) * 1000, 3)


def resolve_refs(arguments, state):
    """실행 직전에 ``ValueRef``를 state 값으로 바꾼다.

    해소되지 않은 참조는 ToolExecutor로 보내지 않고 executor 오류로 만든다.
    """
    resolved = {}
    for name, value in arguments.items():
        if not isinstance(value, ValueRef):
            resolved[name] = value
            continue
        if value.node_id not in state:
            raise ExecutionError(
                f"아직 값이 없는 참조입니다: {value.describe()}",
                code="UNRESOLVED_REF",
                context={"argument": name, "node_id": value.node_id},
            )
        bound = state[value.node_id]
        if value.field is not None:
            if not isinstance(bound, dict) or value.field not in bound:
                raise ExecutionError(
                    f"참조 field를 찾을 수 없습니다: {value.describe()}",
                    code="UNRESOLVED_FIELD",
                    context={"argument": name, "node_id": value.node_id},
                )
            bound = bound[value.field]
        if bound is None:
            raise ExecutionError(
                f"참조 값이 비어 있습니다: {value.describe()}",
                code="EMPTY_REF",
                context={"argument": name, "node_id": value.node_id},
            )
        resolved[name] = bound
    return resolved


def execute_plan(
    execution_plan: ExecutionPlan,
    tool_executor,
    *,
    known_scopes=(),
    event_handler=None,
    cancel_checker=None,
):
    """실행 계획을 순서대로 수행하고 구조화된 결과를 반환한다."""
    state = dict(execution_plan.seed_state)
    verified_scopes = set(known_scopes)
    trace: list[dict] = []

    def emit(event, **payload):
        if event_handler is not None:
            event_handler(event, payload)

    for index, step in enumerate(execution_plan.steps, start=1):
        position = {"model_hop": index, "tool_index": 1, "tool_count": 1}
        if cancel_checker is not None and cancel_checker():
            emit("cancelled", phase="before_tool", hop=index, **position)
            return ExecutionResult(
                status=STATUS_CANCELLED,
                state=state,
                trace=trace,
                final_node=execution_plan.final_node,
            )

        try:
            arguments = resolve_refs(step.arguments, state)
        except ExecutionError as error:
            return _failure(
                execution_plan, state, trace, step, index, error.to_dict(),
                emit, detail=error.detail,
            )

        unverified = sorted(scope_arguments(arguments) - verified_scopes)
        emit("tool_call", hop=index, tool_name=step.tool_name,
             arguments=arguments, **position)
        started_at = time.perf_counter()

        if unverified:
            # agent_graph와 동일한 provenance 정책을 실행 시점에 한 번 더 적용한다.
            result = invalid_argument_result(
                "이 scope는 사용자 입력 또는 이전 Tool 결과에서 확인되지 "
                f"않았습니다: {', '.join(unverified)}. scope 값을 직접 생성할 "
                "수 없습니다."
            )
        else:
            try:
                result = tool_executor.execute(step.tool_name, arguments)
            except Exception as error:  # noqa: BLE001 - 실행 실패를 구조화해 반환
                duration_ms = _duration_ms(started_at)
                detail = (
                    f"ToolExecutor 실행 실패({step.tool_name}): "
                    f"{type(error).__name__}: {error}"
                )
                entry = _trace_entry(
                    index, step, arguments, None, duration_ms, error=detail,
                )
                trace.append(entry)
                return _failure(
                    execution_plan, state, trace, step, index,
                    {
                        "stage": "execution",
                        "code": "TOOL_EXCEPTION",
                        "detail": detail,
                        "user_message": "Tool 실행에 실패했습니다.",
                        "context": {"tool_name": step.tool_name},
                    },
                    emit,
                    detail=detail,
                    already_traced=True,
                )

        duration_ms = _duration_ms(started_at)
        trace.append(_trace_entry(index, step, arguments, result, duration_ms))
        emit("tool_result", hop=index, tool_name=step.tool_name,
             result=result, duration_ms=duration_ms, **position)

        if isinstance(result, dict) and result.get("status") == "ERROR":
            error_code = result.get("error_code", "TOOL_ERROR")
            message = result.get("message", "Tool 실행 오류")
            detail = (
                f"Tool 오류({step.tool_name}/{error_code}): {message}"
            )
            return _failure(
                execution_plan, state, trace, step, index,
                {
                    "stage": "execution",
                    "code": error_code,
                    "detail": detail,
                    "user_message": message,
                    "context": {
                        "tool_name": step.tool_name,
                        "step_id": step.id,
                        "retryable": bool(result.get("retryable", False)),
                    },
                },
                emit,
                detail=detail,
                status=STATUS_TOOL_ERROR,
                already_traced=True,
            )

        verified_scopes.update(extract_scopes(result))
        try:
            _bind_outputs(step, result, state)
        except ExecutionError as error:
            return _failure(
                execution_plan, state, trace, step, index, error.to_dict(),
                emit, detail=error.detail, already_traced=True,
            )

    return ExecutionResult(
        status=STATUS_OK,
        state=state,
        trace=trace,
        final_node=execution_plan.final_node,
        final_value=state.get(execution_plan.final_node),
    )


def _bind_outputs(step, result, state):
    for selector, node_id in step.output_bindings.items():
        state[node_id] = extract_output(
            selector, result, step_id=step.id, tool_name=step.tool_name,
        )


def _trace_entry(index, step, arguments, result, duration_ms, error=None):
    """기존 react hop_log와 호환되는 형태로 실행 기록을 남긴다."""
    entry = {
        "model_hop": index,
        "tool_index": 1,
        "tool_count": 1,
        "step_id": step.id,
        "operator": step.operator,
        "tool": step.tool_name,
        "arguments": arguments,
        "result": result,
        "duration_ms": duration_ms,
    }
    if error is not None:
        entry["error"] = error
    return entry


def _failure(
    execution_plan,
    state,
    trace,
    step,
    index,
    error,
    emit,
    *,
    detail,
    status=STATUS_EXECUTOR_ERROR,
    already_traced=False,
):
    if not already_traced:
        # 미해소 ValueRef가 남아 있을 수 있으므로 직렬화 가능한 형태로 남긴다.
        arguments = {
            name: value.to_dict() if isinstance(value, ValueRef) else value
            for name, value in step.arguments.items()
        }
        trace.append(_trace_entry(
            index, step, arguments, None, 0.0, error=detail,
        ))
    emit(
        "tool_error",
        hop=index,
        error=detail,
        tool_name=step.tool_name,
        model_hop=index,
        tool_index=1,
        tool_count=1,
    )
    return ExecutionResult(
        status=status,
        state=state,
        trace=trace,
        final_node=execution_plan.final_node,
        error={**error, "step_id": step.id},
    )
