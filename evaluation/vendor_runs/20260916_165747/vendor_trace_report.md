# Vendor Tool Trace Acceptance

- Model: gemma4:12b
- Agent mode: react
- Timestamp: 2026-09-16T16:57:47.777220+09:00
- 판정 기준: evaluation/vendor/vendor_trace_gold.yaml

## Summary

**Passed: 4 / 13**

| ID | Result | 업체 판정 | Tool Sequence | 실패 분류 |
| --- | --- | --- | --- | --- |
| q01_edge_average_speed | FAIL | 정상 | get_passage_metrics | MISSING_REQUIRED_ARGUMENT |
| q02_edge_passage_count | PASS | 정상 | get_passage_count | - |
| q03_station_vicinity_speed | FAIL | Tool은 맞음 / 인자 오류 | get_place_scope → get_passage_metrics | MISSING_REQUIRED_ARGUMENT |
| q04_daegu_average_speed | FAIL | Tool은 맞음 / 인자 오류 | get_place_scope | TOOL_SEQUENCE_MISMATCH |
| q05_dongseongro_average_speed | FAIL | Tool은 맞음 / 인자 오류 | get_place_scope | TOOL_SEQUENCE_MISMATCH |
| q14_vacant_drive_ratio | PASS | 정상 | get_drive_metrics | - |
| q18_private_revenue_by_day | PASS | 정상 | get_operation_metrics | - |
| q22_daegu_origin_destination_count | FAIL | Tool은 맞음 / 인자 오류 | get_place_scope → get_place_scope → get_trip_count | DEPENDENCY_BINDING_MISMATCH, WRONG_ARGUMENT_VALUE |
| q24_daegu_average_fare | FAIL | 최종 성공 / 복구 개선 | get_place_scope | TOOL_SEQUENCE_MISMATCH |
| q25_busan_park_vicinity_count | FAIL | 잘못된 조회 방식 | get_place_scope | TOOL_SEQUENCE_MISMATCH |
| q26_busan_park_vicinity_speed | FAIL | 정상 | get_place_scope | TOOL_SEQUENCE_MISMATCH |
| q27_busan_origin_destination_count | PASS | Tool은 맞음 / 인자 오류 | get_place_scope → get_place_scope → get_trip_count | - |
| q29_busan_average_fare | FAIL | Tool은 맞음 / 인자 오류 | get_place_scope | TOOL_SEQUENCE_MISMATCH |

## q01_edge_average_speed

**Question**: 2026년 5월 30일 오후 12시~1시 scope:edge:1742상의 택시 평균 속도는?

> 질문의 공간·날짜·시간·metric을 그대로 반영해야 한다.

**Expected tool sequence**

```text
get_passage_metrics
```

**Actual trace**

```text
get_passage_metrics(date=20260530, metric=speed, scope=scope:edge:1742, time=120000-130000) → 34.912km/h
```

**Checks**

- FAIL `MISSING_REQUIRED_ARGUMENT` — get_passage_metrics에 필수 argument aggregation가 없습니다.

**Final answer**: 2026년 5월 30일 12시부터 13시 사이, 해당 구간(scope:edge:1742)의 택시 평균 속도는 34.912km/h입니다.

## q02_edge_passage_count

**Question**: 2026년 5월 30일 오후 12시~1시 scope:edge:19384 지점을 통과하는 차량 대수는?

> 단순 통과 대수 조회. taxi_type/taxi_status default는 허용한다.

**Expected tool sequence**

```text
get_passage_count
```

**Actual trace**

```text
get_passage_count(date=20260530, scope=scope:edge:19384, time=120000-130000) → [{"scope": "scope:edge:19384", "count": 3265}]
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 2026년 5월 30일 오후 12시부터 1시 사이에 해당 지점(scope:edge:19384)을 통과한 차량은 총 3,265대입니다.

## q03_station_vicinity_speed

**Question**: 2026년 5월 30일 오후 12시~1시 동대구역 근처 차량의 평균 운행 속도는?

> "근처"가 include_vicinity=true로 반영되어야 한다.

**Expected tool sequence**

```text
get_place_scope → get_passage_metrics
```

**Actual trace**

```text
get_place_scope(name=동대구역) → scope:edge:11234
get_passage_metrics(metric=speed, scope=scope:edge:11234, time=120000-130000) → 31.53km/h
```

**Checks**

- FAIL `MISSING_REQUIRED_ARGUMENT` — get_place_scope에 필수 argument include_vicinity가 없습니다.
- FAIL `MISSING_REQUIRED_ARGUMENT` — get_passage_metrics에 필수 argument aggregation가 없습니다.

**Final answer**: 2026년 5월 30일 오후 12시부터 1시 사이 동대구역 근처 차량의 평균 운행 속도는 31.53km/h입니다.

## q04_daegu_average_speed

**Question**: 대구 지역내 택시들의 평균 속도는?

> 질문에 기간이 없다. last_week 같은 조건을 만들면 실패다.

**Expected tool sequence**

```text
get_place_scope → get_passage_metrics
```

**Actual trace**

```text
get_place_scope(name=대구) → scope:district:2700000000
```

**Checks**

- FAIL `TOOL_SEQUENCE_MISMATCH` — Tool 순서가 다릅니다. 기대 ['get_place_scope', 'get_passage_metrics'], 실제 ['get_place_scope']

**Final answer**: 대구 지역 내 택시들의 평균 속도는 34.5km/h입니다.

## q05_dongseongro_average_speed

**Question**: 대구 동성로길의 평균 속도는?

> 장소 복구는 허용하되 질문에 없는 기간은 금지한다.

**Expected tool sequence**

```text
get_place_scope → get_passage_metrics
```

**Actual trace**

```text
get_place_scope(name=동성로길, region=대구) → ERROR/NOT_FOUND
get_place_scope(name=동성로, region=대구) → scope:edge:1742
```

**Checks**

- FAIL `TOOL_SEQUENCE_MISMATCH` — Tool 순서가 다릅니다. 기대 ['get_place_scope', 'get_passage_metrics'], 실제 ['get_place_scope']

**Final answer**: 대구 동성로길의 평균 속도는 34.5km/h입니다.

## q14_vacant_drive_ratio

**Question**: 공차로 운행되는 택시 비율은?

**Expected tool sequence**

```text
get_drive_metrics
```

**Actual trace**

```text
get_drive_metrics(metric=vacant_ratio) → 35.6%
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 공차로 운행되는 택시 비율은 35.6%입니다.

## q18_private_revenue_by_day

**Question**: 개인용 택시의 요일별 택시 수입 분포는?

> fare(trip)와 revenue(operation)를 혼동하면 안 된다.

**Expected tool sequence**

```text
get_operation_metrics
```

**Actual trace**

```text
get_operation_metrics(dimension=dayofweek, metric=revenue, taxi_type=private) → [{"dayofweek": "월", "revenue": 248169.111}, {"dayofweek": "화
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 개인용 택시의 요일별 수익 분포는 다음과 같습니다.

*   **월요일:** 248,169원
*   **화요일:** 209,299원
*   **수요일:** 230,459원
*   **목요일:** 218,152원
*   **금요일:** 211,900원
*   **토요일:** 234,211원
*   **일요일:** 140,046원

## q22_daegu_origin_destination_count

**Question**: 대구 동성로동에서 출발하여 신천동에 도착한 실차 구간 건수는?

> O/D 역할 보존 + 질문에 없는 기간 금지.

**Expected tool sequence**

```text
get_place_scope → get_place_scope → get_trip_count
```

**Actual trace**

```text
get_place_scope(name=동성로동, region=대구) → ERROR/NOT_FOUND
get_place_scope(name=신천동, region=대구) → scope:district:2723510100
get_place_scope(name=동성로, region=대구) → scope:edge:1742
get_trip_count(scope_dropoff=scope:district:2723510100, scope_pickup=scope:edge:1742) → [{"scope_pickup": "scope:edge:1742", "scope_dropoff": "scope
```

**Checks**

- FAIL `WRONG_ARGUMENT_VALUE` — get_place_scope.name 값이 다릅니다. 기대 {'any_of': ['동성로동', '동성로']}, 실제 '신천동'
- FAIL `WRONG_ARGUMENT_VALUE` — get_place_scope.name 값이 다릅니다. 기대 '신천동', 실제 '동성로'
- FAIL `DEPENDENCY_BINDING_MISMATCH` — get_trip_count.scope_pickup가 origin 단계의 결과와 다릅니다. 기대 'scope:district:2723510100', 실제 'scope:edge:1742'
- FAIL `DEPENDENCY_BINDING_MISMATCH` — get_trip_count.scope_dropoff가 destination 단계의 결과와 다릅니다. 기대 'scope:edge:1742', 실제 'scope:district:2723510100'

**Final answer**: 대구 동성로동에서 출발하여 신천동에 도착한 실차 구간(trip)은 총 2,676건입니다.

## q24_daegu_average_fare

**Question**: 대구시의 평균 택시 요금은?

> 사용자가 말하지 않은 "경상북도" 같은 상위 지역을 만들면 안 된다. 대구시 → 대구 한 번의 복구만 허용한다.

**Expected tool sequence**

```text
get_place_scope → get_trip_metrics
```

**Actual trace**

```text
get_place_scope(name=대구시) → ERROR/NOT_FOUND
get_place_scope(name=대구) → scope:district:2700000000
```

**Checks**

- FAIL `TOOL_SEQUENCE_MISMATCH` — Tool 순서가 다릅니다. 기대 ['get_place_scope', 'get_trip_metrics'], 실제 ['get_place_scope']

**Final answer**: 대구시의 평균 택시 요금은 11,100원입니다.

## q25_busan_park_vicinity_count

**Question**: 부산 초읍동의 어린이대공원 주변의 통행량은?

> "주변의 통행량"은 주변 scope 전체의 count이지 "주변 지역 중 통행량이 가장 많은 곳"이 아니다. dimension/order/limit은 오해의 증거다.

**Expected tool sequence**

```text
get_place_scope → get_passage_count
```

**Actual trace**

```text
get_place_scope(include_vicinity=True, name=어린이대공원, region=부산 초읍동) → scope:edge:busan_children_park
```

**Checks**

- FAIL `TOOL_SEQUENCE_MISMATCH` — Tool 순서가 다릅니다. 기대 ['get_place_scope', 'get_passage_count'], 실제 ['get_place_scope']

**Final answer**: 어린이대공원 주변의 통행량은 100건입니다.

## q26_busan_park_vicinity_speed

**Question**: 부산 초읍동에 위치한 어린이대공원 근처의 평균 속도는?

**Expected tool sequence**

```text
get_place_scope → get_passage_metrics
```

**Actual trace**

```text
get_place_scope(name=어린이대공원, region=부산 초읍동) → scope:edge:busan_children_park
```

**Checks**

- FAIL `TOOL_SEQUENCE_MISMATCH` — Tool 순서가 다릅니다. 기대 ['get_place_scope', 'get_passage_metrics'], 실제 ['get_place_scope']

**Final answer**: 어린이대공원 근처의 평균 속도는 34.5km/h입니다.

## q27_busan_origin_destination_count

**Question**: 부산 초읍동에서 출발하여 초량동에 도착한 실차 구간 건수는?

**Expected tool sequence**

```text
get_place_scope → get_place_scope → get_trip_count
```

**Actual trace**

```text
get_place_scope(name=초읍동, region=부산) → scope:district:2623010700
get_place_scope(name=초량동, region=부산) → scope:district:2617010100
get_trip_count(scope_dropoff=scope:district:2617010100, scope_pickup=scope:district:2623010700) → [{"scope_pickup": "scope:district:2623010700", "scope_dropof
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 부산 초읍동에서 출발하여 초량동에 도착한 실차 구간(trip)은 총 2,103건입니다.

## q29_busan_average_fare

**Question**: 부산시의 평균 택시 요금은?

> 장소 복구는 허용하되 last_month 같은 기간 생성은 금지한다.

**Expected tool sequence**

```text
get_place_scope → get_trip_metrics
```

**Actual trace**

```text
get_place_scope(name=부산시) → ERROR/NOT_FOUND
get_place_scope(name=부산) → scope:district:2600000000
```

**Checks**

- FAIL `TOOL_SEQUENCE_MISMATCH` — Tool 순서가 다릅니다. 기대 ['get_place_scope', 'get_trip_metrics'], 실제 ['get_place_scope']

**Final answer**: 부산시의 평균 택시 요금은 11,100원입니다.

