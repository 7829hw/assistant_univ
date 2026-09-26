# -*- coding: utf-8 -*-
"""GeoFlow 실행 결과의 최종 답변 생성.

v1은 코드 기반 format만 사용한다. 현재 5개 template의 결과가 모두 scalar,
count, 또는 분포 목록이라 LLM 없이 정확하게 표현할 수 있고, Tool 결과에 없는
수치가 섞여 들어갈 여지를 아예 없앨 수 있기 때문이다.
"""

from geoflow import analysis_ops
from geoflow.aggregation import BUCKET_LABELS, REDUCER_LABELS, SELECT_LABELS
from geoflow.operator_registry import TOOL_DEFAULT_REDUCER, get_operator
from geoflow.periods import BOUNDARY_RULES
from geoflow.types import CoreConcept, GeoFlowPlan, Subtype

#: template의 answer.kind 값.
KIND_COUNT = "count"
KIND_METRIC = "metric"
KIND_DISTRIBUTION = "distribution"

_AGGREGATION_LABEL = {
    "avg": "평균",
    "max": "최대",
    "min": "최소",
    "sum": "합계",
    "med": "중간값",
}
_TAXI_TYPE_LABEL = {
    "private": "개인",
    "corporate": "법인",
    "all": "전체",
}
_DIMENSION_LABEL = {
    "dayofweek": "요일별",
    "sido": "시도별",
    "sigungu": "시군구별",
    "emd": "읍면동별",
    "h3": "H3 셀별",
}

_ORDER_LABEL = {"top": "상위", "bottom": "하위"}

_BUCKET_LABEL = {"week": "주 단위", "month": "월 단위"}

_DATE_LABEL = {
    "last_week": "지난주",
    "last_month": "지난달",
    "last_year": "작년",
    "weekday": "주중",
    "weekend": "주말",
    "holiday": "휴일",
}

#: metric slot이 있는 template은 template의 일반 label 대신 이 이름을 쓴다.
_METRIC_LABEL = {
    "speed": "속도",
    "rpm": "RPM",
    "fare": "택시 요금",
    "vacant_ratio": "공차율",
    "revenue": "영업 수익",
    "operating_count": "영업 횟수",
    "operating_ratio": "영업 운행률",
    "hours": "영업 시간",
}

_COUNT_KEYS = ("count",)
_MAX_LISTED_ROWS = 24

#: 최종 concept (concept, subtype)별 답변 표현. 예전에는 template YAML의
#: ``answer:`` 블록이 갖고 있었지만, 이것은 질문 유형이 아니라 측정값 자체의
#: 성질이므로 concept에 붙이는 편이 맞다. macro 조각은 답변 형식을 모른다.
ANSWER_SPECS = {
    (CoreConcept.AMOUNT, Subtype.SPEED): {
        "kind": KIND_METRIC, "label": "속도",
    },
    (CoreConcept.AMOUNT, Subtype.RPM): {
        "kind": KIND_METRIC, "label": "RPM",
    },
    (CoreConcept.AMOUNT, Subtype.PASSAGE_COUNT): {
        "kind": KIND_COUNT, "label": "통행량", "unit": "건",
    },
    (CoreConcept.AMOUNT, Subtype.TRIP_COUNT): {
        "kind": KIND_COUNT, "label": "실차 구간 건수", "unit": "건",
    },
    (CoreConcept.AMOUNT, Subtype.FARE): {
        "kind": KIND_METRIC, "label": "택시 요금",
    },
    (CoreConcept.AMOUNT, Subtype.REVENUE): {
        "kind": KIND_METRIC, "label": "영업 수익",
    },
    (CoreConcept.AMOUNT, Subtype.OPERATING_COUNT): {
        "kind": KIND_METRIC, "label": "영업 횟수",
    },
    (CoreConcept.AMOUNT, Subtype.HOURS): {
        "kind": KIND_METRIC, "label": "영업 시간",
    },
    (CoreConcept.PROPORTION, Subtype.VACANT_RATIO): {
        "kind": KIND_METRIC, "label": "공차율",
    },
    (CoreConcept.PROPORTION, Subtype.OPERATING_RATIO): {
        "kind": KIND_METRIC, "label": "영업 운행률",
    },
    (CoreConcept.LOCATION, Subtype.PLACE): {
        "kind": KIND_METRIC, "label": "장소명",
    },
}


def answer_spec_for_plan(plan: GeoFlowPlan):
    """최종 node의 concept에서 답변 표현을 정한다.

    dimension이 있으면 분포로, 주변 영역을 쓴 계획이면 "주변"을 붙인다.
    둘 다 계획에 이미 드러나 있는 사실이므로 따로 선언할 필요가 없다.
    """
    node = plan.node(plan.final_node)
    settings = dict(
        ANSWER_SPECS.get(
            (node.concept, node.subtype) if node is not None else None,
            {"kind": KIND_METRIC, "label": "결과"},
        )
    )
    if plan.slots.get("dimension"):
        settings["kind"] = KIND_DISTRIBUTION
    if any(
        item.subtype == Subtype.VICINITY_SCOPE for item in plan.concepts
    ):
        settings["vicinity"] = True
    return settings


def format_answer(plan: GeoFlowPlan, execution_result, *, answer=None,
                  labels=None, execution_plan=None):
    """실행 결과만 근거로 사용자 답변 문자열을 만든다.

    ``labels``는 scope → 장소명 매핑이며, 없으면 scope를 그대로 보여준다.
    구간별 집계 계획이면 계산 순서와 실제 계산 경로를 함께 적는다.
    """
    settings = dict(
        answer_spec_for_plan(plan) if answer is None else answer
    )
    labels = dict(labels or {})
    stages = grouped_stages(plan)
    if stages is not None:
        return _grouped_answer(plan, execution_result, settings, labels,
                               stages, execution_plan)
    subject = _subject(plan, settings, labels)
    text = _single_stage_answer(plan, execution_result, settings, labels, subject)
    note = _default_reducer_note(plan)
    return f"{text}\n{note}" if note else text


def _default_reducer_note(plan):
    """집계 방식을 받는 Tool에 질문이 집계를 정하지 않았으면 적용된 기본값을 밝힌다."""
    producer = next(
        (item for item in plan.transformations if plan.final_node in item.outputs),
        None,
    )
    spec = get_operator(producer.operator) if producer is not None else None
    if spec is None or not spec.accepts_reducer or "aggregation" in producer.params:
        return ""
    label = _AGGREGATION_LABEL.get(TOOL_DEFAULT_REDUCER, TOOL_DEFAULT_REDUCER)
    return f"- 집계: 질문에 집계 방식이 없어 TIMS 기본값({label})이 적용되었습니다."


def _single_stage_answer(plan, execution_result, settings, labels, subject):
    value = execution_result.final_value
    label = _METRIC_LABEL.get(
        plan.slots.get("metric"), settings.get("label") or "결과",
    )
    unit = settings.get("unit") or ""

    rows = _rows(value)
    if rows is None:
        body = _scalar_text(value, unit)
        return f"{subject} {label}: {body}".strip()

    if len(rows) == 1 and not settings.get("kind") == KIND_DISTRIBUTION:
        body = _scalar_text(_row_value(rows[0]), unit)
        return f"{subject} {label}: {body}".strip()

    lines = [f"{subject} {label}".strip()]
    for row in rows[:_MAX_LISTED_ROWS]:
        lines.append(f"- {_row_text(row, unit, labels)}")
    if len(rows) > _MAX_LISTED_ROWS:
        lines.append(f"- (총 {len(rows)}건 중 {_MAX_LISTED_ROWS}건 표시)")
    return "\n".join(lines)


def _subject(plan, settings, labels=None, *, grouped=False, period=None):
    """slot에 실제로 들어 있는 조건만 모아 답변 앞머리를 만든다.

    ``grouped``이면 집계 표현은 계획의 단계에서 따로 만들므로 여기서 뺀다.
    ``period``는 로컬에서 날짜로 푼 기간이다. 상대 기간 옆에 함께 보여 준다.
    """
    labels = labels or {}
    slots = plan.slots
    parts = []

    origin = _place_text(slots.get("origin"))
    destination = _place_text(slots.get("destination"))
    if origin and destination:
        parts.append(f"{origin} → {destination}")
    elif origin:
        parts.append(f"{origin} 출발")
    elif destination:
        parts.append(f"{destination} 도착")
    else:
        place = _place_text(slots.get("place"))
        if place:
            suffix = "주변" if settings.get("vicinity") else ""
            parts.append(f"{place}{(' ' + suffix) if suffix else ''}")
        elif slots.get("scope"):
            scope = str(slots["scope"])
            parts.append(labels.get(scope, scope))

    date = slots.get("date")
    if date:
        shown = _DATE_LABEL.get(date, str(date))
        if period and period != date:
            shown = f"{shown}({period})"
        parts.append(shown)
    if slots.get("time"):
        parts.append(str(slots["time"]))
    taxi_type = slots.get("taxi_type")
    if taxi_type and taxi_type != "all":
        parts.append(f"{_TAXI_TYPE_LABEL.get(taxi_type, taxi_type)} 택시")
    dimension = slots.get("dimension")
    if dimension:
        parts.append(_DIMENSION_LABEL.get(dimension, f"{dimension}별"))
    # 순위·개수 제한이 적용되었다면 답변에 드러낸다.
    order = slots.get("order")
    if order:
        parts.append(_ORDER_LABEL.get(order, order))
    limit = slots.get("limit")
    if limit:
        parts.append(f"{limit}개")
    if grouped:
        return " ".join(parts)
    # bucket/rollup 2단계 집계는 "주 단위 평균"처럼 순서대로 보여준다.
    bucket = slots.get("bucket")
    if bucket:
        parts.append(_BUCKET_LABEL.get(bucket, bucket))
    aggregation = slots.get("aggregation")
    if aggregation:
        parts.append(_AGGREGATION_LABEL.get(aggregation, aggregation))
    rollup = slots.get("rollup")
    if rollup:
        parts.append(_AGGREGATION_LABEL.get(rollup, rollup))

    return " ".join(parts)


def _place_text(place):
    if isinstance(place, str):
        return place
    if not isinstance(place, dict):
        return ""
    name = place.get("name") or ""
    region = place.get("region") or ""
    return f"{region} {name}".strip()


def _rows(value):
    if isinstance(value, list) and all(
        isinstance(item, dict) for item in value
    ):
        return value
    return None


def _row_value(row):
    for key in _COUNT_KEYS:
        if key in row:
            return row[key]
    numeric = [
        item for key, item in row.items()
        if isinstance(item, (int, float)) and not isinstance(item, bool)
    ]
    if len(numeric) == 1:
        return numeric[0]
    return row


def _row_text(row, unit, labels=None):
    label_keys = (
        "dayofweek", "day_of_week", "place_name", "district_name",
        "sido", "sigungu", "emd", "h3", "scope", "date", "month",
    )
    labels = labels or {}

    def shown(value):
        text = str(value)
        return labels.get(text, text)

    label = None
    for key in label_keys:
        if key in row:
            label = shown(row[key])
            break
    if "scope_pickup" in row and "scope_dropoff" in row:
        label = f"{shown(row['scope_pickup'])} → {shown(row['scope_dropoff'])}"
    value = _row_value(row)
    if isinstance(value, dict):
        return ", ".join(f"{key}={item}" for key, item in value.items())
    body = _scalar_text(value, unit)
    return f"{label}: {body}" if label else body


def _scalar_text(value, unit):
    if value is None:
        return "결과 없음"
    if isinstance(value, bool):
        return "예" if value else "아니오"
    if isinstance(value, int):
        return f"{value:,}{unit}"
    if isinstance(value, float):
        return f"{f'{value:,.3f}'.rstrip('0').rstrip('.')}{unit}"
    if isinstance(value, str):
        # Provider가 이미 단위를 붙여 반환한 경우 단위를 중복해 붙이지 않는다.
        return value
    return str(value)


# -- 구간별 집계 ---------------------------------------------------------------


def grouped_stages(plan):
    """구간별 집계의 세 단계(구간 안 집계, 구간별 node, 합치기/고르기)를 찾는다.

    구간별 계획이 아니면 None이다. 답변은 Tool 인자가 아니라 이 단계에서
    집계 표현을 만든다. 호출 하나로 합쳐졌든 나눠 불렀든 질문의 뜻은 같다.
    """
    grouped = next(
        (node for node in plan.concepts if analysis_ops.is_grouped(node)), None,
    )
    if grouped is None:
        return None
    produce = next(
        (item for item in plan.transformations if grouped.id in item.outputs), None,
    )
    combine = next(
        (
            item for item in plan.transformations
            if any(ref.node_id == grouped.id for ref in item.inputs.values())
        ),
        None,
    )
    if produce is None or combine is None:
        return None
    return {
        "bucket": grouped.attributes[analysis_ops.GROUP_BY]["bucket"],
        "inner": produce.params.get("aggregation"),
        "reducer": combine.params.get("reducer"),
        "select": combine.params.get("select"),
        "produce": produce.id,
        "combine": combine.id,
        "groups_node": grouped.id,
    }


def describe_stages(stages):
    """"주별 합계의 평균", "주별 합계가 가장 큰 주"."""
    unit = BUCKET_LABELS.get(stages["bucket"], stages["bucket"])
    inner = REDUCER_LABELS.get(stages["inner"], stages["inner"])
    if stages["select"]:
        return (f"{unit}별 {_josa(inner, '이', '가')} "
                f"{SELECT_LABELS[stages['select']]} {unit}")
    return f"{unit}별 {inner}의 {REDUCER_LABELS.get(stages['reducer'])}"


def _grouped_answer(plan, execution_result, settings, labels, stages,
                    execution_plan):
    period = None
    detail = None
    if execution_plan is not None:
        detail = execution_plan.periods.get(stages["produce"])
        if detail:
            period = detail["resolved"]
    subject = _subject(plan, settings, labels, grouped=True, period=period)
    label = _METRIC_LABEL.get(
        plan.slots.get("metric"), settings.get("label") or "결과",
    )
    unit = settings.get("unit") or ""
    value = execution_result.final_value
    phrase = describe_stages(stages)

    if stages["select"]:
        groups = (value or {}).get("groups") or []
        shown = ", ".join(_group_text(group) for group in groups) or "결과 없음"
        tie = " (동률)" if len(groups) > 1 else ""
        body = f"{shown}{tie}, {_scalar_text((value or {}).get('value'), unit)}"
    else:
        body = _scalar_text(value, unit)
    lines = [f"{subject} {label} — {phrase}: {body}".strip()]
    lines.append(f"- 계산: {_route_text(stages, execution_plan, detail)}")
    rows = execution_result.state.get(stages["groups_node"])
    if isinstance(rows, list):
        inner = REDUCER_LABELS.get(stages["inner"], stages["inner"])
        lines.append(f"- 구간별 {inner}:")
        for row in rows[:_MAX_LISTED_ROWS]:
            lines.append(
                f"  - {_group_text(row['group'])}: {_scalar_text(row['value'], unit)}"
            )
    return "\n".join(lines)


def _josa(word, with_batchim, without_batchim):
    """마지막 글자의 받침에 맞는 조사를 붙인다."""
    last = word[-1] if word else ""
    has = "가" <= last <= "힣" and (ord(last) - ord("가")) % 28 != 0
    return f"{word}{with_batchim if has else without_batchim}"


def _group_text(group):
    text = group.get("label", "")
    if group.get("complete") is False:
        text += "(부분 구간)"
    return text


def _route_text(stages, execution_plan, detail):
    """실제로 어떻게 계산했는지. 같은 뜻이라도 경로에 따라 구간 경계가 다르다."""
    unit = BUCKET_LABELS.get(stages["bucket"], stages["bucket"])
    inner = REDUCER_LABELS.get(stages["inner"], stages["inner"])
    if detail:
        last = (
            f"{SELECT_LABELS[stages['select']]} {_josa(unit, '을', '를')} 골랐습니다"
            if stages["select"]
            else f"구간별 값의 "
                 f"{_josa(REDUCER_LABELS.get(stages['reducer']), '을', '를')} 계산했습니다"
        )
        return (
            f"기간 {detail['resolved']}을 {unit} 구간 {len(detail['groups'])}개"
            f"({BOUNDARY_RULES[stages['bucket']]})로 나눠 구간마다 "
            f"{_josa(inner, '을', '를')} 조회한 뒤 로컬에서 {last}."
        )
    if execution_plan is not None and stages["groups_node"] in execution_plan.unobserved:
        return (
            f"TIMS가 {unit} 구간마다 {_josa(inner, '을', '를')} 구한 뒤 그 값들의 "
            f"{_josa(REDUCER_LABELS.get(stages['reducer']), '을', '를')} 한 번에 계산했습니다 "
            f"(bucket={stages['bucket']}, aggregation={stages['inner']}, "
            f"rollup={stages['reducer']}). 구간 경계는 TIMS 정의를 따릅니다."
        )
    return describe_stages(stages)
