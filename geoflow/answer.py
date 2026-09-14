# -*- coding: utf-8 -*-
"""GeoFlow 실행 결과의 최종 답변 생성.

v1은 코드 기반 format만 사용한다. 현재 5개 template의 결과가 모두 scalar,
count, 또는 분포 목록이라 LLM 없이 정확하게 표현할 수 있고, Tool 결과에 없는
수치가 섞여 들어갈 여지를 아예 없앨 수 있기 때문이다.
"""

from geoflow.types import GeoFlowPlan

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

_COUNT_KEYS = ("count",)
_MAX_LISTED_ROWS = 24


def format_answer(plan: GeoFlowPlan, execution_result, *, answer=None):
    """실행 결과만 근거로 사용자 답변 문자열을 만든다."""
    settings = dict(answer or {})
    subject = _subject(plan, settings)
    value = execution_result.final_value
    label = settings.get("label") or "결과"
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
        lines.append(f"- {_row_text(row, unit)}")
    if len(rows) > _MAX_LISTED_ROWS:
        lines.append(f"- (총 {len(rows)}건 중 {_MAX_LISTED_ROWS}건 표시)")
    return "\n".join(lines)


def _subject(plan, settings):
    """slot에 실제로 들어 있는 조건만 모아 답변 앞머리를 만든다."""
    slots = plan.slots
    parts = []

    origin = _place_text(slots.get("origin"))
    destination = _place_text(slots.get("destination"))
    if origin and destination:
        parts.append(f"{origin} → {destination}")
    else:
        place = _place_text(slots.get("place"))
        if place:
            suffix = "주변" if settings.get("vicinity") else ""
            parts.append(f"{place}{(' ' + suffix) if suffix else ''}")
        elif slots.get("scope"):
            parts.append(str(slots["scope"]))

    if slots.get("date"):
        parts.append(str(slots["date"]))
    if slots.get("time"):
        parts.append(str(slots["time"]))
    taxi_type = slots.get("taxi_type")
    if taxi_type and taxi_type != "all":
        parts.append(f"{_TAXI_TYPE_LABEL.get(taxi_type, taxi_type)} 택시")
    dimension = slots.get("dimension")
    if dimension:
        parts.append(_DIMENSION_LABEL.get(dimension, f"{dimension}별"))
    aggregation = slots.get("aggregation")
    if aggregation:
        parts.append(_AGGREGATION_LABEL.get(aggregation, aggregation))

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


def _row_text(row, unit):
    label_keys = (
        "dayofweek", "day_of_week", "place_name", "district_name",
        "sido", "sigungu", "emd", "h3", "scope", "date", "month",
    )
    label = None
    for key in label_keys:
        if key in row:
            label = str(row[key])
            break
    if "scope_pickup" in row and "scope_dropoff" in row:
        label = f"{row['scope_pickup']} → {row['scope_dropoff']}"
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
