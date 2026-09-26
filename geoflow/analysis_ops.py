# -*- coding: utf-8 -*-
"""로컬 분석 연산자. Tool을 부르지 않고 이미 얻은 중간 결과만 계산한다.

``operator_registry``의 operator는 TIMS Tool 하나에 대응한다. 여기 있는 연산자는
대응하는 Tool이 없고, 의미 graph에서 "구간별 값 → 최종 값" 변환을 나타낸다.
Planner prompt의 어휘는 ``operator_registry.OPERATORS``에서 만들어지므로 이
registry는 prompt에 영향을 주지 않는다.

    REDUCE_GROUPS  구간별 값들 → 값      (outer 집계)
    SELECT_GROUP   구간별 값들 → 구간    (가장 큰/작은 구간)
    COLLECT_GROUPS 구간마다 부른 Tool 결과 → 구간별 값 목록 (lowering 전용)

입력은 언제나 **구간별 값 자체**다. 원시 값이나 충분 통계가 없으므로 "구간별
평균들의 평균"을 "전체 평균"으로 바꿔 쓰는 식의 계산은 여기서 할 수 없고, 의미
graph도 그런 변환을 표현하지 않는다(validator G7).
"""

from dataclasses import dataclass

from geoflow.aggregation import REDUCERS, SELECTIONS
from geoflow.errors import ExecutionError

REDUCE_GROUPS = "REDUCE_GROUPS"
SELECT_GROUP = "SELECT_GROUP"
COLLECT_GROUPS = "COLLECT_GROUPS"

#: 구간별 값을 담은 node의 속성 key. 값은 {"bucket": "week"} 형태다.
GROUP_BY = "group_by"
#: SELECT_GROUP이 만든 node의 속성. 답이 값이 아니라 구간이라는 뜻이다.
RETURNS = "returns"
RETURNS_GROUP = "group"


@dataclass(frozen=True)
class AnalysisOperatorSpec:
    name: str
    params: frozenset[str]
    #: 의미 graph에 나타나는가. COLLECT_GROUPS는 lowering이 만든다.
    semantic: bool = True


ANALYSIS_OPERATORS = {
    spec.name: spec for spec in (
        AnalysisOperatorSpec(REDUCE_GROUPS, frozenset({"reducer"})),
        AnalysisOperatorSpec(SELECT_GROUP, frozenset({"select"})),
        AnalysisOperatorSpec(COLLECT_GROUPS, frozenset(), semantic=False),
    )
}


def is_analysis_operator(name):
    return name in ANALYSIS_OPERATORS


def is_grouped(node):
    return bool(node is not None and node.attributes.get(GROUP_BY))


def param_problems(operator, params):
    """params가 연산자 계약에 맞지 않는 이유 목록."""
    spec = ANALYSIS_OPERATORS[operator]
    problems = []
    unknown = sorted(set(params) - spec.params)
    if unknown:
        problems.append(f"{operator}이 받지 않는 parameter: {', '.join(unknown)}")
    if operator == REDUCE_GROUPS and params.get("reducer") not in REDUCERS:
        problems.append(f"reducer가 올바르지 않습니다: {params.get('reducer')!r}")
    if operator == SELECT_GROUP and params.get("select") not in SELECTIONS:
        problems.append(f"select가 올바르지 않습니다: {params.get('select')!r}")
    return problems


# -- 실행 -------------------------------------------------------------------


def _number(value, *, where):
    if value is None:
        raise ExecutionError(
            f"{where}: 구간 값이 비어 있습니다. 자료가 없는 구간을 0으로 볼지 "
            "알 수 없으므로 계산하지 않습니다.",
            code="EMPTY_GROUP_VALUE",
            user_message="값이 없는 구간이 있어 구간별 계산을 할 수 없습니다.",
            context={"where": where},
        )
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExecutionError(
            f"{where}: 구간 값이 스칼라 숫자가 아닙니다: {value!r}",
            code="NON_SCALAR_GROUP_VALUE",
            user_message="구간별 값의 형식이 예상과 달라 계산하지 않았습니다.",
            context={"where": where},
        )
    return value


def reduce_values(values, reducer):
    """값 목록에 집계를 적용한다. 반올림하지 않는다."""
    if not values:
        raise ExecutionError(
            "집계할 구간이 없습니다.",
            code="EMPTY_GROUPS",
            user_message="계산할 구간이 없습니다.",
        )
    if reducer == "sum":
        return sum(values)
    if reducer == "avg":
        return sum(values) / len(values)
    if reducer == "max":
        return max(values)
    if reducer == "min":
        return min(values)
    if reducer == "med":
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / 2
    raise ExecutionError(f"알 수 없는 reducer: {reducer!r}", code="UNKNOWN_REDUCER")


def run(step, state):
    """로컬 step 하나를 실행하고 결과를 돌려준다."""
    if step.operator == COLLECT_GROUPS:
        groups = step.arguments.get("groups") or []
        if len(groups) != len(step.inputs):
            raise ExecutionError(
                f"{step.id}: 구간 수와 입력 수가 다릅니다.",
                code="GROUP_ARITY",
            )
        rows = []
        for group, key in zip(groups, step.inputs):
            if key not in state:
                raise ExecutionError(
                    f"{step.id}: 구간 값이 아직 없습니다: {key}",
                    code="UNRESOLVED_REF",
                    context={"node_id": key},
                )
            rows.append({
                "group": dict(group),
                "value": _number(state[key], where=f"{step.id}[{group['label']}]"),
            })
        return rows

    rows = _group_rows(step, state)
    values = [row["value"] for row in rows]
    if step.operator == REDUCE_GROUPS:
        return reduce_values(values, step.arguments["reducer"])
    if step.operator == SELECT_GROUP:
        chosen = max(values) if step.arguments["select"] == "max" else min(values)
        # 동률이면 하나를 임의로 고르지 않고 모두 돌려준다.
        return {
            "select": step.arguments["select"],
            "value": chosen,
            "groups": [dict(row["group"]) for row in rows if row["value"] == chosen],
        }
    raise ExecutionError(f"알 수 없는 로컬 연산자: {step.operator}",
                         code="UNKNOWN_OPERATOR")


def _group_rows(step, state):
    (key,) = step.inputs
    rows = state.get(key)
    if not isinstance(rows, list) or not all(
        isinstance(row, dict) and "group" in row and "value" in row for row in rows
    ):
        raise ExecutionError(
            f"{step.id}: 구간별 값 목록이 아닙니다: {key}",
            code="NOT_GROUPED_INPUT",
            context={"node_id": key},
        )
    for row in rows:
        _number(row["value"], where=f"{step.id}[{row['group'].get('label')}]")
    return rows
