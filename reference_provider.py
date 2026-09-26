# -*- coding: utf-8 -*-
"""작은 고정 합성 데이터를 실제로 필터링·집계하는 reference provider.

**합성 데이터다.** ``reference_data/synthetic_operation_days.csv``의 27행은 계산 경로를
검증하려고 손으로 만든 값이다. 실제 교통 데이터나 TIMS 결과가 아니다. 지명(가람구, 나래구)도
가상이다. 이 provider가 맞게 계산했다는 것은 TIMS의 동작이나 정확성에 대해 아무것도 말하지 않는다.

mock(``mock_responses``)과 달리 인자의 hash로 값을 만들지 않고, 질문별 정답도 없다. 인자로
레코드를 걸러 집계한다. 도구 이름과 인자 schema는 TIMS와 같은 것(``schemas/*.yaml``)을 받지만,
아래 계약에 적은 인자·값만 해석한다. 그 밖의 인자, 값, 도구는 mock으로 넘기지 않고
``UNSUPPORTED_BY_PROVIDER``로 돌려준다.

원시 레코드
    한 행 = 택시 한 대의 영업일 하루(택시·일). 열:
    record_id, taxi_id, service_date(영업일, Asia/Seoul 달력 날짜), closed_at(영업 종료 시각,
    +09:00, 자정을 넘을 수 있음), scope(소속 지역), taxi_type(private | corporate),
    revenue_krw(그 영업일의 매출, 원 단위 정수. 비어 있으면 결측).

reference 계약 (geoflow/providers.py REFERENCE_CONTRACT가 이 문장들을 근거로 인용한다)
    [시간대] 날짜는 모두 Asia/Seoul 달력 날짜이며 레코드는 service_date로만 거른다.
    [단일 날짜] YYYYMMDD는 service_date가 그 날짜인 레코드를 뜻한다.
    [범위] YYYYMMDD-YYYYMMDD는 양 끝을 포함한다.
    [상대 날짜] 상대 날짜 토큰(last_week 등)과 요일 토큰은 받지 않는다. 호출 전에 명시 범위로 풀어야 한다.
    [기간 없음] date를 생략하면 데이터 전체 기간이다.
    [기록 단위] 각 레코드는 하나의 service_date에만 속하며 aggregation은 레코드에 바로 적용된다.
    [결측] revenue_krw가 비어 있는 레코드는 모든 집계와 개수에서 뺀다.
    [빈 결과] 조건에 맞는 레코드가 없으면 null을 반환한다(0으로 채우지 않는다).
    [평균] avg의 분모는 조건에 맞는 결측 아닌 레코드 수이며 가중치는 없다.
    [기본 집계] aggregation을 생략하면 avg다.
    [택시 유형] taxi_type=all은 유형 조건 없음과 같다.
    [반환] get_operation_metrics는 스칼라 숫자 하나를 반환한다. sum·max·min은 원 단위 정수, avg·med는 반올림하지 않은 원 단위 실수다.
    [구간] bucket·rollup·dimension·order·limit은 지원하지 않는다. 주 단위 구간과 동률 처리는 이 provider가 아니라 로컬 분석 연산(geoflow/periods.py, geoflow/analysis_ops.py)이 정한다.
"""

import csv
from datetime import date
from pathlib import Path
from types import MappingProxyType

PROVIDER_NAME = "reference"
DATA_PATH = Path(__file__).resolve().parent / "reference_data" / "synthetic_operation_days.csv"

#: 가상 지명 → scope. 실제 행정구역이 아니다.
PLACES = MappingProxyType({
    "가람구": "scope:ref:district:garam",
    "나래구": "scope:ref:district:narae",
})
ALIASES = MappingProxyType({"가람": "가람구", "나래": "나래구"})
SCOPE_NAMES = MappingProxyType({scope: name for name, scope in PLACES.items()})

SUPPORTED_OPERATION_ARGUMENTS = frozenset({"metric", "scope", "date", "taxi_type", "aggregation"})
SUPPORTED_METRICS = frozenset({"revenue"})
DEFAULT_AGGREGATION = "avg"
UNSUPPORTED = "UNSUPPORTED_BY_PROVIDER"


def _error(code, message):
    return {"status": "ERROR", "error_code": code, "message": message,
            "provider": PROVIDER_NAME}


def _unsupported(message):
    return _error(UNSUPPORTED, f"reference provider는 {message}")


def _parse_day(text):
    return date(int(text[:4]), int(text[4:6]), int(text[6:8]))


def load_records(path=DATA_PATH):
    """CSV를 읽어 불변 튜플로 돌려준다. 호출마다 새로 읽지 않고 provider 생성 시 한 번 읽는다."""
    rows = []
    with open(path, encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            revenue = row["revenue_krw"].strip()
            rows.append(MappingProxyType({
                "record_id": row["record_id"],
                "taxi_id": row["taxi_id"],
                "service_date": date.fromisoformat(row["service_date"]),
                "closed_at": row["closed_at"],
                "scope": row["scope"],
                "taxi_type": row["taxi_type"],
                "revenue_krw": int(revenue) if revenue else None,
            }))
    return tuple(rows)


def _period(value):
    """date 인자 → (시작, 끝) 또는 오류. 둘 다 포함한다."""
    if value is None:
        return None, None
    text = str(value)
    head, sep, tail = text.partition("-")
    if not head.isdigit() or len(head) != 8 or (sep and (not tail.isdigit() or len(tail) != 8)):
        return None, _unsupported(f"date={text!r}를 받지 않습니다. YYYYMMDD 또는 "
                                  "YYYYMMDD-YYYYMMDD(양 끝 포함)만 받습니다.")
    try:
        start = _parse_day(head)
        end = _parse_day(tail) if sep else start
    except ValueError:
        return None, _error("INVALID_ARGUMENT", f"존재하지 않는 날짜입니다: {text}")
    if end < start:
        return None, _error("INVALID_ARGUMENT", f"기간의 끝이 시작보다 앞입니다: {text}")
    return (start, end), None


def _aggregate(values, how):
    if not values:
        return None
    if how == "sum":
        return sum(values)
    if how == "max":
        return max(values)
    if how == "min":
        return min(values)
    if how == "avg":
        return sum(values) / len(values)
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


class ReferenceProvider:
    """고정 레코드 위의 계산기. 상태는 생성 시 읽은 불변 레코드뿐이다."""

    def __init__(self, records=None):
        self.records = load_records() if records is None else tuple(records)

    def operation_metrics(self, arguments):
        extra = sorted(set(arguments) - SUPPORTED_OPERATION_ARGUMENTS)
        if extra:
            return _unsupported(f"다음 인자를 지원하지 않습니다: {', '.join(extra)}")
        metric = arguments.get("metric")
        if metric not in SUPPORTED_METRICS:
            return _unsupported(f"metric={metric!r}를 지원하지 않습니다(revenue만 지원).")
        scope = arguments.get("scope")
        if scope is not None and scope not in SCOPE_NAMES:
            return _error("NOT_FOUND", f"reference 데이터에 없는 scope입니다: {scope}")
        span, error = _period(arguments.get("date"))
        if error is not None:
            return error
        taxi_type = arguments.get("taxi_type", "all")
        how = arguments.get("aggregation", DEFAULT_AGGREGATION)
        values = [
            record["revenue_krw"] for record in self.records
            if (scope is None or record["scope"] == scope)
            and (taxi_type == "all" or record["taxi_type"] == taxi_type)
            and (span is None or span[0] <= record["service_date"] <= span[1])
            and record["revenue_krw"] is not None
        ]
        return _aggregate(values, how)

    @staticmethod
    def place_scope(arguments):
        if arguments.get("include_vicinity"):
            return _unsupported("주변(include_vicinity)을 지원하지 않습니다.")
        name = arguments.get("name")
        canonical = ALIASES.get(name, name)
        if canonical not in PLACES:
            return {"status": "ERROR", "error_code": "NOT_FOUND",
                    "message": f"reference 데이터에 없는 장소입니다: {name}",
                    "provider": PROVIDER_NAME}
        return {"scope": PLACES[canonical], "name": canonical}

    @staticmethod
    def scope_name(arguments):
        scope = arguments.get("scope")
        if scope not in SCOPE_NAMES:
            return _error("NOT_FOUND", f"reference 데이터에 없는 scope입니다: {scope}")
        return {"scope": scope, "name": SCOPE_NAMES[scope]}


#: TIMS·Gazetteer schema의 도구 중 reference가 받지 않는 것. mock으로 넘기지 않는다.
_UNSUPPORTED_TOOLS = ("get_passage_count", "get_passage_metrics", "get_trip_count",
                      "get_trip_metrics", "get_drive_metrics")


def reference_handlers(provider=None):
    """ToolExecutor에 넘길 handler 사전. 부를 때마다 새 사전을 만든다."""
    provider = provider or ReferenceProvider()
    handlers = {
        "get_operation_metrics": provider.operation_metrics,
        "get_place_scope": provider.place_scope,
        "get_scope_name": provider.scope_name,
    }
    for name in _UNSUPPORTED_TOOLS:
        handlers[name] = (lambda tool: lambda arguments: _unsupported(
            f"{tool} 도구를 지원하지 않습니다."))(name)
    return handlers
