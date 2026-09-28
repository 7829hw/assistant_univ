# -*- coding: utf-8 -*-
"""YAML Direct Tool 8개를 위한 deterministic Stub 구현."""

from pathlib import Path

import copy
import yaml


DEFAULT_MOCK_STUB_PATH = Path(__file__).resolve().parent / "mock_stub.yaml"
_REQUIRED_TIMS_VALUES = {
    "get_passage_count": ("count",),
    "get_passage_metrics": ("speed", "rpm"),
    "get_trip_count": ("count",),
    "get_trip_metrics": ("fare",),
    "get_drive_metrics": ("vacant_ratio",),
    "get_billing_metrics": (
        "revenue", "active_taxi_count", "active_taxi_ratio", "operating_days",
    ),
}


class MockStubError(ValueError):
    """mock_stub.yaml 구조나 필수 값이 올바르지 않음."""


def load_mock_stub(path=DEFAULT_MOCK_STUB_PATH):
    """Mock 데이터를 한 번 읽고 실행에 필요한 최소 계약을 검증한다."""
    stub_path = Path(path).expanduser().resolve()
    try:
        document = yaml.safe_load(stub_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise MockStubError(
            f"Mock Stub을 읽을 수 없습니다: {stub_path}\n{error}"
        ) from error
    if not isinstance(document, dict) or document.get("version") != 1:
        raise MockStubError("mock_stub.yaml의 version은 1이어야 합니다.")

    gazetteer = document.get("gazetteer")
    tims = document.get("tims")
    if not isinstance(gazetteer, dict) or not isinstance(tims, dict):
        raise MockStubError("mock_stub.yaml에 gazetteer와 tims object가 필요합니다.")
    for section in ("places", "districts"):
        fixtures = gazetteer.get(section)
        if not isinstance(fixtures, dict) or not fixtures:
            raise MockStubError(f"gazetteer.{section}는 비어 있지 않은 object여야 합니다.")
        for name, fixture in fixtures.items():
            if not isinstance(name, str) or not isinstance(fixture, dict):
                raise MockStubError(f"gazetteer.{section} entry가 잘못되었습니다.")
            if not isinstance(fixture.get("scope"), str):
                raise MockStubError(f"gazetteer.{section}.{name}.scope가 필요합니다.")
            if not isinstance(fixture.get("aliases"), list):
                raise MockStubError(f"gazetteer.{section}.{name}.aliases는 list여야 합니다.")
            parent = fixture.get("parent")
            if parent is not None and not isinstance(parent, str):
                raise MockStubError(f"gazetteer.{section}.{name}.parent가 잘못되었습니다.")
            if section == "districts" and fixture.get("level") not in {
                "sido", "sigungu", "emd",
            }:
                raise MockStubError(f"gazetteer.districts.{name}.level이 잘못되었습니다.")
    h3 = gazetteer.get("h3")
    if not isinstance(h3, list) or any(
        not isinstance(item, list)
        or len(item) != 3
        or not all(isinstance(value, str) for value in item)
        for item in h3
    ):
        raise MockStubError("gazetteer.h3는 [name, scope, parent] 목록이어야 합니다.")
    for tool_name, value_names in _REQUIRED_TIMS_VALUES.items():
        values = tims.get(tool_name)
        if not isinstance(values, dict):
            raise MockStubError(f"tims.{tool_name} object가 필요합니다.")
        for value_name in value_names:
            value = values.get(value_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise MockStubError(
                    f"tims.{tool_name}.{value_name} 숫자 값이 필요합니다."
                )
        cases = values.get("cases", [])
        if not isinstance(cases, list):
            raise MockStubError(f"tims.{tool_name}.cases는 list여야 합니다.")
        for index, case in enumerate(cases, start=1):
            if not isinstance(case, dict):
                raise MockStubError(
                    f"tims.{tool_name}.cases[{index}]는 object여야 합니다."
                )
            if not isinstance(case.get("when"), dict):
                raise MockStubError(
                    f"tims.{tool_name}.cases[{index}].when은 object여야 합니다."
                )
            if "result" not in case:
                raise MockStubError(
                    f"tims.{tool_name}.cases[{index}].result가 필요합니다."
                )
    return document


DEFAULT_MOCK_STUB = load_mock_stub()
_GAZETTEER = DEFAULT_MOCK_STUB["gazetteer"]
TIMS_STUB = DEFAULT_MOCK_STUB["tims"]
PLACE_FIXTURES = _GAZETTEER["places"]
DISTRICT_FIXTURES = _GAZETTEER["districts"]
H3_FIXTURES = tuple(tuple(item) for item in _GAZETTEER["h3"])

ALL_FIXTURES = {**DISTRICT_FIXTURES, **PLACE_FIXTURES}
NAME_TO_FIXTURE = {}
for _canonical_name, _fixture in ALL_FIXTURES.items():
    NAME_TO_FIXTURE[_canonical_name] = (_canonical_name, _fixture)
    for _alias in _fixture.get("aliases", []):
        NAME_TO_FIXTURE[_alias] = (_canonical_name, _fixture)

SCOPE_TO_NAME = {fixture["scope"]: name for name, fixture in ALL_FIXTURES.items()}
SCOPE_TO_NAME.update({scope: name for name, scope, _parent in H3_FIXTURES})
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


def _fixed_metric(tool_name, metric):
    """YAML에 선언된 Tool metric 고정값을 반환한다."""
    try:
        return TIMS_STUB[tool_name][metric]
    except KeyError as error:
        raise ValueError(f"지원하지 않는 metric: {metric}") from error


def _fixed_count(tool_name):
    """YAML에 선언된 Tool count 고정값을 반환한다."""
    return TIMS_STUB[tool_name]["count"]


def _find_mock_case(tool_name, arguments):
    """arguments와 모든 when 항목이 같은 첫 YAML case 결과를 반환한다."""
    for case in TIMS_STUB[tool_name].get("cases", []):
        if all(arguments.get(key) == value for key, value in case["when"].items()):
            return copy.deepcopy(case["result"])
    return None


def _apply_case_limit(result, arguments):
    """YAML에 이미 정렬된 case 결과에는 재정렬 없이 limit만 적용한다."""
    if not isinstance(result, list):
        return result
    limit = arguments.get("limit", 10000)
    return result[:limit] if limit is not None else result


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
    """passage count를 object 또는 지명별 list 형태로 반환한다."""
    scope = arguments.get("scope")
    dimension = arguments.get("dimension")
    if not dimension:
        return {"count": _fixed_count("get_passage_count")}

    case_result = _find_mock_case("get_passage_count", arguments)
    if case_result is not None:
        return _apply_case_limit(case_result, arguments)

    candidates = _candidate_scopes(dimension, scope)
    if not candidates:
        return _error(
            "UNSUPPORTED_COMBINATION",
            "지정한 scope와 dimension에 해당하는 후보가 없습니다.",
        )
    rows = [
        {
            dimension: SCOPE_TO_NAME[candidate],
            "count": _fixed_count("get_passage_count"),
        }
        for candidate in candidates
    ]
    return _apply_order_limit(rows, "count", arguments)


def mock_get_passage_metrics(arguments):
    """passage metric을 집계한 Direct scalar를 반환한다."""
    metric = arguments.get("metric")
    value = _fixed_metric("get_passage_metrics", metric)
    if metric == "speed":
        return f"{value:g}km/h"
    return value


def mock_get_trip_count(arguments):
    """trip count를 object 또는 dimension_target별 지명 list로 반환한다."""
    dimension = arguments.get("dimension")
    if not dimension:
        return {"count": _fixed_count("get_trip_count")}

    target = arguments.get("dimension_target") or "both"
    pickup_scope = arguments.get("scope_pickup")
    dropoff_scope = arguments.get("scope_dropoff")
    target_scope = {
        "pickup": pickup_scope,
        "dropoff": dropoff_scope,
    }.get(target)

    if target != "both" and target_scope is None:
        case_result = _find_mock_case("get_trip_count", arguments)
        if case_result is not None:
            return _apply_case_limit(case_result, arguments)

    if target == "pickup":
        names = [
            SCOPE_TO_NAME[candidate]
            for candidate in _candidate_scopes(dimension, pickup_scope)
        ]
        rows = [
            {"pickup": name, "count": _fixed_count("get_trip_count")}
            for name in names
        ]
    elif target == "dropoff":
        names = [
            SCOPE_TO_NAME[candidate]
            for candidate in _candidate_scopes(dimension, dropoff_scope)
        ]
        rows = [
            {"dropoff": name, "count": _fixed_count("get_trip_count")}
            for name in names
        ]
    else:
        pickup_names = [
            SCOPE_TO_NAME[candidate]
            for candidate in _candidate_scopes(dimension, pickup_scope)
        ]
        dropoff_names = [
            SCOPE_TO_NAME[candidate]
            for candidate in _candidate_scopes(dimension, dropoff_scope)
        ]
        if not pickup_names or not dropoff_names:
            rows = []
        else:
            row_count = max(len(pickup_names), len(dropoff_names))
            rows = [
                {
                    "pickup": pickup_names[index % len(pickup_names)],
                    "dropoff": dropoff_names[index % len(dropoff_names)],
                    "count": _fixed_count("get_trip_count"),
                }
                for index in range(row_count)
            ]

    if not rows:
        return _error(
            "UNSUPPORTED_COMBINATION",
            "지정한 승하차 scope와 dimension에 해당하는 후보가 없습니다.",
        )
    return _apply_order_limit(rows, "count", arguments)

def mock_get_trip_metrics(arguments):
    """택시 소속지역 조건을 반영한 fare Direct scalar를 반환한다."""
    return _fixed_metric("get_trip_metrics", arguments.get("metric"))


def mock_get_drive_metrics(arguments):
    """YAML의 고정 공차율을 percentage scalar로 반환한다."""
    value = _fixed_metric("get_drive_metrics", arguments.get("metric"))
    return f"{round(value * 100, 2):g}%"


def mock_get_billing_metrics(arguments):
    """일 단위 영업 metric을 scalar, dimension list 또는 rollup scalar로 반환한다."""
    metric = arguments.get("metric")
    dimension = arguments.get("dimension")
    bucket = arguments.get("bucket")
    rollup = arguments.get("rollup")

    if arguments.get("scope") and dimension:
        return _error(
            "UNSUPPORTED_COMBINATION",
            "scope와 dimension은 동시에 사용할 수 없습니다.",
        )
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
            "scope가 없을 때는 sido, dayofweek dimension만 사용할 수 있습니다.",
        )

    if dimension:
        case_result = _find_mock_case("get_billing_metrics", arguments)
        if case_result is not None:
            return _apply_case_limit(case_result, arguments)

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
                dimension: (
                    candidate
                    if dimension == "dayofweek"
                    else SCOPE_TO_NAME[candidate]
                ),
                metric: _fixed_metric("get_billing_metrics", metric),
            }
            for candidate in candidates
        ]
        return _apply_order_limit(rows, metric, arguments)

    if bucket:
        bucket_values = [
            _fixed_metric("get_billing_metrics", metric)
            for _ in range(6)
        ]
        return _aggregate(bucket_values, rollup)

    return _fixed_metric("get_billing_metrics", metric)


MOCK_HANDLERS = {
    "get_place_scope": mock_get_place_scope,
    "get_scope_name": mock_get_scope_name,
    "get_passage_count": mock_get_passage_count,
    "get_passage_metrics": mock_get_passage_metrics,
    "get_trip_count": mock_get_trip_count,
    "get_trip_metrics": mock_get_trip_metrics,
    "get_drive_metrics": mock_get_drive_metrics,
    "get_billing_metrics": mock_get_billing_metrics,
}
