# -*- coding: utf-8 -*-
"""결과에 포함된 scope를 사람이 읽을 장소명으로 바꾼다.

호출 횟수가 실행 결과의 행 수에 의존하므로 정적 ``ExecutionPlan``으로는 표현할
수 없다. 따라서 실행이 성공한 뒤 별도의 bounded 단계로 수행한다.

Planner는 이 단계에 관여하지 않으며, 실패해도 원본 scope를 그대로 보여주고
답변 생성을 계속한다. 표시용 보강이지 분석 결과의 일부가 아니기 때문이다.
"""

import time

from geoflow.operator_registry import (
    Operator,
    get_operator,
    is_scope_literal,
)

#: 한 답변에서 장소명을 조회할 scope 개수 상한. 무한 fan-out을 막는다.
MAX_LABEL_LOOKUPS = 20


def collect_scopes(value, limit=MAX_LABEL_LOOKUPS):
    """결과 구조에서 scope 문자열을 나온 순서대로 중복 없이 모은다."""
    found: list[str] = []

    def walk(item):
        if len(found) >= limit:
            return
        if is_scope_literal(item):
            if item not in found:
                found.append(item)
            return
        if isinstance(item, dict):
            for entry in item.values():
                walk(entry)
        elif isinstance(item, (list, tuple)):
            for entry in item:
                walk(entry)

    walk(value)
    return found


def resolve_scope_labels(
    value,
    tool_executor,
    *,
    limit=MAX_LABEL_LOOKUPS,
    event_handler=None,
    start_index=1,
):
    """scope → 장소명 매핑과 실행 trace를 반환한다.

    조회에 실패한 scope는 매핑에서 빠지며, 답변에는 원본 scope가 그대로 남는다.
    """
    scopes = collect_scopes(value, limit)
    if not scopes:
        return {}, []

    spec = get_operator(Operator.SCOPE_NAME)
    if spec is None or spec.tool_name not in set(tool_executor.tool_names):
        return {}, []

    labels: dict[str, str] = {}
    trace: list[dict] = []
    for offset, scope in enumerate(scopes):
        index = start_index + offset
        position = {"model_hop": index, "tool_index": 1, "tool_count": 1}
        arguments = {"scope": scope}
        if event_handler is not None:
            event_handler("tool_call", {
                "hop": index,
                "tool_name": spec.tool_name,
                "arguments": arguments,
                **position,
            })
        started_at = time.perf_counter()
        try:
            result = tool_executor.execute(spec.tool_name, arguments)
        except Exception as error:  # noqa: BLE001 - 표시용이므로 중단하지 않는다
            result = {
                "status": "ERROR",
                "error_code": "TOOL_ERROR",
                "message": f"{type(error).__name__}: {error}",
            }
        duration_ms = round((time.perf_counter() - started_at) * 1000, 3)

        trace.append({
            **position,
            "step_id": f"label_scope_{offset + 1}",
            "operator": spec.name,
            "tool": spec.tool_name,
            "arguments": arguments,
            "result": result,
            "duration_ms": duration_ms,
            "phase": "labeling",
        })
        if event_handler is not None:
            event_handler("tool_result", {
                "hop": index,
                "tool_name": spec.tool_name,
                "result": result,
                "duration_ms": duration_ms,
                **position,
            })

        if isinstance(result, str) and result.strip():
            labels[scope] = result.strip()
        elif isinstance(result, dict) and result.get("status") != "ERROR":
            name = result.get("name") or result.get("place_name")
            if isinstance(name, str) and name.strip():
                labels[scope] = name.strip()

    return labels, trace
