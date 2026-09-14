# -*- coding: utf-8 -*-
"""YAML Direct Tool 8개를 위한 deterministic Stub 구현."""

import hashlib
import json
import random


PLACE_FIXTURES = {
    "동대구역": {
        "scope": "scope:edge:11234",
        "aliases": ["동대구"],
        "parent": "scope:district:2721000000",
    },
    "동성로": {
        "scope": "scope:edge:1742",
        "aliases": ["동성로 거리"],
        "parent": "scope:district:2723000000",
    },
    "어린이대공원": {
        "scope": "scope:edge:busan_children_park",
        "aliases": [],
        "parent": "scope:district:2623010700",
    },
    "광안리": {
        "scope": "scope:edge:gwangalli",
        "aliases": [],
        "parent": "scope:district:2650010400",
    },
    "도심지": {
        "scope": "scope:h3:8830e1d8dffffff",
        "aliases": ["중심지역", "중심지"],
        "parent": "scope:district:2723000000",
    },
}

DISTRICT_FIXTURES = {
    "대구": {
        "scope": "scope:district:2700000000",
        "aliases": ["대구광역시"],
        "level": "sido",
        "parent": None,
    },
    "서울": {
        "scope": "scope:district:1100000000",
        "aliases": ["서울특별시"],
        "level": "sido",
        "parent": None,
    },
    "부산": {
        "scope": "scope:district:2600000000",
        "aliases": ["부산광역시"],
        "level": "sido",
        "parent": None,
    },
    "부산진구": {
        "scope": "scope:district:2623000000",
        "aliases": [],
        "level": "sigungu",
        "parent": "scope:district:2600000000",
    },
    "부산 동구": {
        "scope": "scope:district:2617000000",
        "aliases": [],
        "level": "sigungu",
        "parent": "scope:district:2600000000",
    },
    "수영구": {
        "scope": "scope:district:2650000000",
        "aliases": [],
        "level": "sigungu",
        "parent": "scope:district:2600000000",
    },
    "인천": {
        "scope": "scope:district:2800000000",
        "aliases": ["인천광역시"],
        "level": "sido",
        "parent": None,
    },
    "중구": {
        "scope": "scope:district:2723000000",
        "aliases": [],
        "level": "sigungu",
        "parent": "scope:district:2700000000",
    },
    "동구": {
        "scope": "scope:district:2721000000",
        "aliases": [],
        "level": "sigungu",
        "parent": "scope:district:2700000000",
    },
    "서구": {
        "scope": "scope:district:2722000000",
        "aliases": [],
        "level": "sigungu",
        "parent": "scope:district:2700000000",
    },
    "수성구": {
        "scope": "scope:district:2726000000",
        "aliases": [],
        "level": "sigungu",
        "parent": "scope:district:2700000000",
    },
    "달서구": {
        "scope": "scope:district:2729000000",
        "aliases": [],
        "level": "sigungu",
        "parent": "scope:district:2700000000",
    },
    "동인동": {
        "scope": "scope:district:2723010200",
        "aliases": [],
        "level": "emd",
        "parent": "scope:district:2723000000",
    },
    "중앙로동": {
        "scope": "scope:district:2723010300",
        "aliases": [],
        "level": "emd",
        "parent": "scope:district:2723000000",
    },
    "태평로동": {
        "scope": "scope:district:2723010100",
        "aliases": [],
        "level": "emd",
        "parent": "scope:district:2723000000",
    },
    "신천동": {
        "scope": "scope:district:2723510100",
        "aliases": [],
        "level": "emd",
        "parent": "scope:district:2721000000",
    },
    "두산동": {
        "scope": "scope:district:2726010100",
        "aliases": [],
        "level": "emd",
        "parent": "scope:district:2726000000",
    },
    "두류동": {
        "scope": "scope:district:2729010100",
        "aliases": [],
        "level": "emd",
        "parent": "scope:district:2729000000",
    },
    "초읍동": {
        "scope": "scope:district:2623010700",
        "aliases": [],
        "level": "emd",
        "parent": "scope:district:2623000000",
    },
    "초량동": {
        "scope": "scope:district:2617010100",
        "aliases": [],
        "level": "emd",
        "parent": "scope:district:2617000000",
    },
    "광안동": {
        "scope": "scope:district:2650010400",
        "aliases": [],
        "level": "emd",
        "parent": "scope:district:2650000000",
    },
}

H3_FIXTURES = (
    ("도심 H3-1", "scope:h3:8830e1d81ffffff", "scope:district:2723000000"),
    ("도심 H3-2", "scope:h3:8830e1d83ffffff", "scope:district:2723000000"),
    ("동구 H3-1", "scope:h3:8830e1d85ffffff", "scope:district:2721000000"),
    ("수성 H3-1", "scope:h3:8830e1d87ffffff", "scope:district:2726000000"),
    ("달서 H3-1", "scope:h3:8830e1d89ffffff", "scope:district:2729000000"),
)

ALL_FIXTURES = {**DISTRICT_FIXTURES, **PLACE_FIXTURES}
NAME_TO_FIXTURE = {}
for _canonical_name, _fixture in ALL_FIXTURES.items():
    NAME_TO_FIXTURE[_canonical_name] = (_canonical_name, _fixture)
    for _alias in _fixture.get("aliases", []):
        NAME_TO_FIXTURE[_alias] = (_canonical_name, _fixture)

SCOPE_TO_NAME = {
    fixture["scope"]: name
    for name, fixture in ALL_FIXTURES.items()
}
SCOPE_TO_NAME.update({
    scope: name for name, scope, _parent in H3_FIXTURES
})

PARENT_BY_SCOPE = {
    fixture["scope"]: fixture.get("parent")
    for fixture in ALL_FIXTURES.values()
}
PARENT_BY_SCOPE.update({
    scope: parent for _name, scope, parent in H3_FIXTURES
})

DIMENSION_SCOPES = {
    level: [
        fixture["scope"]
        for fixture in DISTRICT_FIXTURES.values()
        if fixture["level"] == level
    ]
    for level in ("sido", "sigungu", "emd")
}
DIMENSION_SCOPES["h3"] = [
    fixture["scope"]
    for fixture in PLACE_FIXTURES.values()
    if fixture["scope"].startswith("scope:h3:")
] + [scope for _name, scope, _parent in H3_FIXTURES]

DAY_OF_WEEK_LABELS = ["월", "화", "수", "목", "금", "토", "일"]


TOOL_DEFAULTS = {
    "get_place_scope": {"include_vicinity": False},
    "get_passage_count": {
        "taxi_type": "all",
        "taxi_status": "all",
    },
    "get_passage_metrics": {"aggregation": "avg"},
    "get_trip_metrics": {"aggregation": "avg"},
    "get_drive_metrics": {
        "taxi_type": "all",
        "aggregation": "avg",
    },
    "get_operation_metrics": {
        "taxi_type": "all",
        "aggregation": "avg",
    },
}

REGION_SCOPE_BY_TOKEN = {}
for _name, _fixture in DISTRICT_FIXTURES.items():
    REGION_SCOPE_BY_TOKEN[_name] = _fixture["scope"]
    for _alias in _fixture.get("aliases", []):
        REGION_SCOPE_BY_TOKEN[_alias] = _fixture["scope"]


def _error(error_code, message):
    return {
        "status": "ERROR",
        "error_code": error_code,
        "message": message,
    }


def _rng(tool_name, arguments, *, exclude=(), salt=None):
    """YAML default를 보완한 의미상 arguments로 재현 가능한 난수기를 만든다."""
    semantic_arguments = dict(arguments)
    for key, default in TOOL_DEFAULTS.get(tool_name, {}).items():
        semantic_arguments.setdefault(key, default)
    excluded = set(exclude)
    normalized = {
        key: value
        for key, value in semantic_arguments.items()
        if key not in excluded
    }
    payload = {
        "tool": tool_name,
        "arguments": normalized,
        "salt": salt,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")
    return random.Random(seed)


def _aggregate(values, aggregation=None):
    """현재 pt_aggregation의 lower-case 집계를 적용한다."""
    aggregation = aggregation or "avg"
    if not values:
        return None
    if aggregation == "max":
        return max(values)
    if aggregation == "min":
        return min(values)
    if aggregation == "sum":
        return round(sum(values), 3)
    if aggregation == "med":
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return round((ordered[middle - 1] + ordered[middle]) / 2, 3)
    if aggregation == "avg":
        return round(sum(values) / len(values), 3)
    raise ValueError(f"지원하지 않는 aggregation: {aggregation}")


def _metric_samples(tool_name, arguments, metric, *, salt=None, count=9):
    """metric별 현실적인 범위 안에서 여러 deterministic sample을 만든다."""
    rng = _rng(
        tool_name,
        arguments,
        exclude=("aggregation", "order", "limit", "rollup"),
        salt=salt,
    )
    if metric == "speed":
        return [round(rng.uniform(15, 45), 3) for _ in range(count)]
    if metric == "rpm":
        return [rng.randint(700, 3000) for _ in range(count)]
    if metric == "fare":
        return [rng.randint(4000, 35000) for _ in range(count)]
    if metric == "vacant_ratio":
        return [round(rng.uniform(0.05, 0.75), 4) for _ in range(count)]
    if metric == "revenue":
        return [rng.randint(50000, 400000) for _ in range(count)]
    if metric == "operating_count":
        return [rng.randint(1, 30) for _ in range(count)]
    if metric == "operating_ratio":
        return [round(rng.uniform(0.1, 0.95), 4) for _ in range(count)]
    if metric == "hours":
        return [round(rng.uniform(2, 14), 3) for _ in range(count)]
    raise ValueError(f"지원하지 않는 metric: {metric}")


def _metric_value(tool_name, arguments, metric, *, salt=None):
    samples = _metric_samples(tool_name, arguments, metric, salt=salt)
    return _aggregate(samples, arguments.get("aggregation"))


def _count_value(tool_name, arguments, *, salt=None):
    rng = _rng(
        tool_name,
        arguments,
        exclude=("order", "limit"),
        salt=salt,
    )
    return rng.randint(10, 5000)


def _is_within(candidate, root):
    current = candidate
    visited = set()
    while current is not None and current not in visited:
        if current == root:
            return True
        visited.add(current)
        current = PARENT_BY_SCOPE.get(current)
    return False


def _candidate_scopes(dimension, root_scope=None):
    candidates = list(DIMENSION_SCOPES.get(dimension, []))
    if root_scope in PARENT_BY_SCOPE:
        candidates = [
            candidate
            for candidate in candidates
            if _is_within(candidate, root_scope)
        ]
    return candidates


def _apply_order_limit(rows, value_key, arguments):
    rows = list(rows)
    order = arguments.get("order")
    if order:
        rows.sort(
            key=lambda row: row[value_key],
            reverse=order == "top",
        )
    limit = arguments.get("limit")
    if limit is not None:
        rows = rows[:limit]
    return rows


def _region_matches(fixture, region):
    if not region:
        return True

    constrained_scopes = {
        scope
        for token, scope in REGION_SCOPE_BY_TOKEN.items()
        if token and token in region
    }
    if not constrained_scopes:
        return False

    ancestor_scopes = set()
    current = fixture["scope"]
    while current is not None:
        ancestor_scopes.add(current)
        current = PARENT_BY_SCOPE.get(current)
    return constrained_scopes.issubset(ancestor_scopes)


def mock_get_place_scope(arguments):
    """장소·행정구역 이름을 canonical scope로 변환한다."""
    found = NAME_TO_FIXTURE.get(arguments.get("name"))
    if not found:
        return _error("NOT_FOUND", "일치하는 장소 또는 행정구역을 찾을 수 없습니다.")
    canonical_name, fixture = found
    region = arguments.get("region")
    if not _region_matches(fixture, region):
        return _error(
            "NOT_FOUND",
            f"{region}에서 {canonical_name}을 찾을 수 없습니다.",
        )
    return fixture["scope"]


def mock_get_scope_name(arguments):
    """canonical scope를 장소·행정구역 이름으로 변환한다."""
    name = SCOPE_TO_NAME.get(arguments.get("scope"))
    if name is None:
        return _error("NOT_FOUND", "scope에 대응하는 장소명을 찾을 수 없습니다.")
    return name


def mock_get_passage_count(arguments):
    """조건에 맞는 passage 건수를 Direct list 형태로 반환한다."""
    scope = arguments.get("scope")
    dimension = arguments.get("dimension")
    if not dimension:
        return [{
            "scope": scope,
            "count": _count_value("get_passage_count", arguments, salt=scope),
        }]

    candidates = _candidate_scopes(dimension, scope)
    if not candidates:
        return _error(
            "UNSUPPORTED_COMBINATION",
            "지정한 scope와 dimension에 해당하는 후보가 없습니다.",
        )
    rows = [
        {
            "scope": candidate,
            "count": _count_value(
                "get_passage_count",
                arguments,
                salt=candidate,
            ),
        }
        for candidate in candidates
    ]
    return _apply_order_limit(rows, "count", arguments)


def mock_get_passage_metrics(arguments):
    """passage metric을 집계한 Direct scalar를 반환한다."""
    metric = arguments.get("metric")
    value = _metric_value("get_passage_metrics", arguments, metric)
    if metric == "speed":
        return f"{value:g}km/h"
    return value


def mock_get_trip_count(arguments):
    """고정 O/D, 한쪽 고정 ranking, 전체 pair 또는 전체 count를 반환한다."""
    pickup = arguments.get("scope_pickup")
    dropoff = arguments.get("scope_dropoff")
    dimension = arguments.get("dimension")

    if pickup and dropoff:
        return [{
            "scope_pickup": pickup,
            "scope_dropoff": dropoff,
            "count": _count_value(
                "get_trip_count",
                arguments,
                salt=f"{pickup}>{dropoff}",
            ),
        }]

    if not dimension:
        row = {
            "count": _count_value("get_trip_count", arguments, salt="total"),
        }
        if pickup:
            row["scope_pickup"] = pickup
        if dropoff:
            row["scope_dropoff"] = dropoff
        return [row]

    candidates = _candidate_scopes(dimension)
    if not candidates:
        return _error("INVALID_ARGUMENT", "지원하지 않는 dimension입니다.")

    if pickup:
        rows = [
            {
                "scope_pickup": pickup,
                "scope_dropoff": candidate,
                "count": _count_value(
                    "get_trip_count",
                    arguments,
                    salt=f"{pickup}>{candidate}",
                ),
            }
            for candidate in candidates
        ]
    elif dropoff:
        rows = [
            {
                "scope_pickup": candidate,
                "scope_dropoff": dropoff,
                "count": _count_value(
                    "get_trip_count",
                    arguments,
                    salt=f"{candidate}>{dropoff}",
                ),
            }
            for candidate in candidates
        ]
    else:
        rows = [
            {
                "scope_pickup": candidate,
                "scope_dropoff": candidates[(index + 1) % len(candidates)],
                "count": _count_value(
                    "get_trip_count",
                    arguments,
                    salt=f"pair:{candidate}",
                ),
            }
            for index, candidate in enumerate(candidates)
        ]

    return _apply_order_limit(rows, "count", arguments)


def mock_get_trip_metrics(arguments):
    """택시 소속지역 조건을 반영한 fare Direct scalar를 반환한다."""
    return _metric_value(
        "get_trip_metrics",
        arguments,
        arguments.get("metric"),
    )


def mock_get_drive_metrics(arguments):
    """공차율을 여러 sample에서 집계해 percentage scalar로 반환한다."""
    value = _metric_value(
        "get_drive_metrics",
        arguments,
        arguments.get("metric"),
    )
    return f"{round(value * 100, 2):g}%"


def mock_get_operation_metrics(arguments):
    """일 단위 영업 metric을 scalar, dimension list 또는 rollup scalar로 반환한다."""
    metric = arguments.get("metric")
    dimension = arguments.get("dimension")
    bucket = arguments.get("bucket")
    rollup = arguments.get("rollup")

    if dimension and bucket:
        return _error(
            "UNSUPPORTED_COMBINATION",
            "dimension과 bucket은 동시에 사용할 수 없습니다.",
        )
    if bucket and not rollup:
        return _error("INVALID_ARGUMENT", "bucket을 사용하려면 rollup이 필요합니다.")
    if rollup and not bucket:
        return _error("INVALID_ARGUMENT", "rollup을 사용하려면 bucket이 필요합니다.")

    if dimension in ("sigungu", "emd", "h3") and not arguments.get("scope"):
        return _error(
            "UNSUPPORTED_COMBINATION",
            "sigungu, emd, h3 dimension을 사용하려면 scope가 필요합니다.",
        )

    if dimension:
        if dimension == "dayofweek":
            candidates = DAY_OF_WEEK_LABELS
        else:
            candidates = _candidate_scopes(dimension, arguments.get("scope"))
        if not candidates:
            return _error(
                "UNSUPPORTED_COMBINATION",
                "지정한 scope와 dimension에 해당하는 후보가 없습니다.",
            )
        rows = [
            {
                dimension: candidate,
                metric: _metric_value(
                    "get_operation_metrics",
                    arguments,
                    metric,
                    salt=f"{dimension}:{candidate}",
                ),
            }
            for candidate in candidates
        ]
        return _apply_order_limit(rows, metric, arguments)

    if bucket:
        bucket_values = [
            _metric_value(
                "get_operation_metrics",
                arguments,
                metric,
                salt=f"{bucket}:{index}",
            )
            for index in range(6)
        ]
        return _aggregate(bucket_values, rollup)

    return _metric_value("get_operation_metrics", arguments, metric)


MOCK_HANDLERS = {
    "get_place_scope": mock_get_place_scope,
    "get_scope_name": mock_get_scope_name,
    "get_passage_count": mock_get_passage_count,
    "get_passage_metrics": mock_get_passage_metrics,
    "get_trip_count": mock_get_trip_count,
    "get_trip_metrics": mock_get_trip_metrics,
    "get_drive_metrics": mock_get_drive_metrics,
    "get_operation_metrics": mock_get_operation_metrics,
}
