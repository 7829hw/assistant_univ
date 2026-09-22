# -*- coding: utf-8 -*-
"""GeoFlow 실행 결과의 최종 답변 생성.

v1은 코드 기반 format만 사용한다. 현재 5개 template의 결과가 모두 scalar,
count, 또는 분포 목록이라 LLM 없이 정확하게 표현할 수 있고, Tool 결과에 없는
수치가 섞여 들어갈 여지를 아예 없앨 수 있기 때문이다.
"""

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
                  labels=None):
    """실행 결과만 근거로 사용자 답변 문자열을 만든다.

    ``labels``는 scope → 장소명 매핑이며, 없으면 scope를 그대로 보여준다.
    """
    settings = dict(
        answer_spec_for_plan(plan) if answer is None else answer
    )
    labels = dict(labels or {})
    subject = _subject(plan, settings, labels)
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


def _subject(plan, settings, labels=None):
    """slot에 실제로 들어 있는 조건만 모아 답변 앞머리를 만든다."""
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
        parts.append(_DATE_LABEL.get(date, str(date)))
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
