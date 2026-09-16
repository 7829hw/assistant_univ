# Vendor Tool Trace Acceptance

- Model: qwen3.5:9b
- Agent mode: react
- Timestamp: 2026-09-16T16:39:31.326694+09:00
- 판정 기준: evaluation/vendor/vendor_trace_gold.yaml

## Summary

**Passed: 9 / 13**

| ID | Result | 업체 판정 | Tool Sequence | 실패 분류 |
| --- | --- | --- | --- | --- |
| q01_edge_average_speed | PASS | 정상 | get_passage_metrics | - |
| q02_edge_passage_count | PASS | 정상 | get_passage_count | - |
| q03_station_vicinity_speed | FAIL | Tool은 맞음 / 인자 오류 | get_place_scope → get_passage_metrics | MISSING_REQUIRED_ARGUMENT |
| q04_daegu_average_speed | PASS | Tool은 맞음 / 인자 오류 | get_place_scope → get_passage_metrics | - |
| q05_dongseongro_average_speed | PASS | Tool은 맞음 / 인자 오류 | get_place_scope → get_passage_metrics | - |
| q14_vacant_drive_ratio | FAIL | 정상 | get_place_scope → get_drive_metrics | TOOL_SEQUENCE_MISMATCH, UNEXPECTED_RETRY |
| q18_private_revenue_by_day | PASS | 정상 | get_operation_metrics | - |
| q22_daegu_origin_destination_count | FAIL | Tool은 맞음 / 인자 오류 | get_place_scope → get_place_scope → get_trip_count → get_scope_name | TOOL_SEQUENCE_MISMATCH |
| q24_daegu_average_fare | PASS | 최종 성공 / 복구 개선 | get_place_scope → get_trip_metrics | - |
| q25_busan_park_vicinity_count | PASS | 잘못된 조회 방식 | get_place_scope → get_passage_count | - |
| q26_busan_park_vicinity_speed | FAIL | 정상 | get_place_scope → get_passage_metrics | MISSING_REQUIRED_ARGUMENT |
| q27_busan_origin_destination_count | PASS | Tool은 맞음 / 인자 오류 | get_place_scope → get_place_scope → get_trip_count | - |
| q29_busan_average_fare | PASS | Tool은 맞음 / 인자 오류 | get_place_scope → get_trip_metrics | - |

## q01_edge_average_speed

**Question**: 2026년 5월 30일 오후 12시~1시 scope:edge:1742상의 택시 평균 속도는?

> 질문의 공간·날짜·시간·metric을 그대로 반영해야 한다.

**Expected tool sequence**

```text
get_passage_metrics
```

**Actual trace**

```text
get_passage_metrics(metric=speed, scope=scope:edge:1742, date=20260530, time=120000-130000, aggregation=avg) → 34.912km/h
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 2026년 5월 30일 오후 12시~1시 scope:edge:1742상의 택시 평균 속도는 **34.912km/h**입니다.

## q02_edge_passage_count

**Question**: 2026년 5월 30일 오후 12시~1시 scope:edge:19384 지점을 통과하는 차량 대수는?

> 단순 통과 대수 조회. taxi_type/taxi_status default는 허용한다.

**Expected tool sequence**

```text
get_passage_count
```

**Actual trace**

```text
get_passage_count(scope=scope:edge:19384, date=20260530, time=120000-130000) → [{"scope": "scope:edge:19384", "count": 3265}]
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 2026년 5월 30일 오후 12시~1시 사이, scope:edge:19384 지점을 통과하는 차량 대수는 총 **3,265대**입니다.

## q03_station_vicinity_speed

**Question**: 2026년 5월 30일 오후 12시~1시 동대구역 근처 차량의 평균 운행 속도는?

> "근처"가 include_vicinity=true로 반영되어야 한다.

**Expected tool sequence**

```text
get_place_scope → get_passage_metrics
```

**Actual trace**

```text
get_place_scope(name=동대구역, region=) → scope:edge:11234
get_passage_metrics(metric=speed, scope=scope:edge:11234, date=20260530, time=120000-130000, aggregation=avg) → 26.558km/h
```

**Checks**

- FAIL `MISSING_REQUIRED_ARGUMENT` — get_place_scope에 필수 argument include_vicinity가 없습니다.

**Final answer**: 2026년 5월 30일 오후 12시~1시 동대구역 근처 차량의 평균 운행 속도는 **26.558km/h**입니다.

## q04_daegu_average_speed

**Question**: 대구 지역내 택시들의 평균 속도는?

> 질문에 기간이 없다. last_week 같은 조건을 만들면 실패다.

**Expected tool sequence**

```text
get_place_scope → get_passage_metrics
```

**Actual trace**

```text
get_place_scope(name=대구, region=, include_vicinity=False) → scope:district:2700000000
get_passage_metrics(metric=speed, scope=scope:district:2700000000, aggregation=avg) → 27.702km/h
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 대구 지역 내 택시들의 평균 속도는 **27.702km/h**입니다.

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
get_passage_metrics(metric=speed, scope=scope:edge:1742, aggregation=avg) → 30.136km/h
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 대구 동성로의 평균 속도는 **30.136km/h**입니다.

## q14_vacant_drive_ratio

**Question**: 공차로 운행되는 택시 비율은?

**Expected tool sequence**

```text
get_drive_metrics
```

**Actual trace**

```text
get_place_scope(name=대한민국) → ERROR/NOT_FOUND
get_place_scope(name=서울) → scope:district:1100000000
get_drive_metrics(metric=vacant_ratio, scope=scope:district:1100000000) → 29.8%
```

**Checks**

- FAIL `UNEXPECTED_RETRY` — 실패한 Tool 호출이 1회로 허용치(0)를 넘었습니다.
- FAIL `TOOL_SEQUENCE_MISMATCH` — Tool 순서가 다릅니다. 기대 ['get_drive_metrics'], 실제 ['get_place_scope', 'get_drive_metrics']

**Final answer**: 서울 지역의 공차 운행 비율은 29.8%입니다.

## q18_private_revenue_by_day

**Question**: 개인용 택시의 요일별 택시 수입 분포는?

> fare(trip)와 revenue(operation)를 혼동하면 안 된다.

**Expected tool sequence**

```text
get_operation_metrics
```

**Actual trace**

```text
get_operation_metrics(metric=revenue, taxi_type=private, dimension=dayofweek) → [{"dayofweek": "월", "revenue": 248169.111}, {"dayofweek": "화
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 개인용 택시의 요일별 수입 분포는 다음과 같습니다:

| 요일 | 수입 (원) |
|------|-----------|
| 월 | 248,169.11 |
| 화 | 209,298.78 |
| 수 | 230,458.78 |
| 목 | 218,152.22 |
| 금 | 211,900.44 |
| 토 | 234,210.67 |
| 일 | 140,046.11 |

**요약:**
- **가장 많은 수입**: 월요일 (약 248,169 원)
- **가장 적은 수입**: 일요일 (약 140,046 원)
- **주중 평균**: 약 223,596 원
- **주말 평균**: 약 187,128 원

월요일이 가장 높은 수입을 기록하고 있으며, 일요일은 다른 요일들에 비해 상대적으로 낮은 수입을 보입니다.

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
get_place_scope(name=동성로동) → ERROR/NOT_FOUND
get_place_scope(name=신천동) → scope:district:2723510100
get_place_scope(name=동성로, region=대구) → scope:edge:1742
get_trip_count(scope_pickup=scope:edge:1742, scope_dropoff=scope:district:2723510100) → [{"scope_pickup": "scope:edge:1742", "scope_dropoff": "scope
get_scope_name(scope=scope:edge:1742) → 동성로
```

**Checks**

- FAIL `TOOL_SEQUENCE_MISMATCH` — Tool 순서가 다릅니다. 기대 ['get_place_scope', 'get_place_scope', 'get_trip_count'], 실제 ['get_place_scope', 'get_place_scope', 'get_trip_count', 'get_scope_name']

**Final answer**: 대구 동성로에서 신천동으로 출발하여 도착한 실차 구간(trip) 건수는 **2,676건**입니다.

## q24_daegu_average_fare

**Question**: 대구시의 평균 택시 요금은?

> 사용자가 말하지 않은 "경상북도" 같은 상위 지역을 만들면 안 된다. 대구시 → 대구 한 번의 복구만 허용한다.

**Expected tool sequence**

```text
get_place_scope → get_trip_metrics
```

**Actual trace**

```text
get_place_scope(name=대구시, region=) → ERROR/NOT_FOUND
get_place_scope(name=대구, region=) → scope:district:2700000000
get_trip_metrics(metric=fare, scope=scope:district:2700000000, aggregation=avg) → 13289.667
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 대구시의 평균 택시 요금은 **13,289.67원**입니다.

## q25_busan_park_vicinity_count

**Question**: 부산 초읍동의 어린이대공원 주변의 통행량은?

> "주변의 통행량"은 주변 scope 전체의 count이지 "주변 지역 중 통행량이 가장 많은 곳"이 아니다. dimension/order/limit은 오해의 증거다.

**Expected tool sequence**

```text
get_place_scope → get_passage_count
```

**Actual trace**

```text
get_place_scope(name=어린이대공원, region=부산 초읍동, include_vicinity=True) → scope:edge:busan_children_park
get_passage_count(scope=scope:edge:busan_children_park) → [{"scope": "scope:edge:busan_children_park", "count": 3959}]
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 부산 초읍동의 어린이대공원 주변의 통행량은 **3,959건**입니다.

## q26_busan_park_vicinity_speed

**Question**: 부산 초읍동에 위치한 어린이대공원 근처의 평균 속도는?

**Expected tool sequence**

```text
get_place_scope → get_passage_metrics
```

**Actual trace**

```text
get_place_scope(name=어린이대공원, region=부산 초읍동) → scope:edge:busan_children_park
get_passage_metrics(metric=speed, scope=scope:edge:busan_children_park, aggregation=avg) → 26.8km/h
```

**Checks**

- FAIL `MISSING_REQUIRED_ARGUMENT` — get_place_scope에 필수 argument include_vicinity가 없습니다.

**Final answer**: 부산 초읍동에 위치한 어린이대공원 근처의 평균 속도는 **26.8km/h**입니다.

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
get_trip_count(scope_pickup=scope:district:2623010700, scope_dropoff=scope:district:2617010100) → [{"scope_pickup": "scope:district:2623010700", "scope_dropof
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 부산 초읍동에서 출발하여 초량동에 도착한 실차 구간(trip) 건수는 **2,103건**입니다.

## q29_busan_average_fare

**Question**: 부산시의 평균 택시 요금은?

> 장소 복구는 허용하되 last_month 같은 기간 생성은 금지한다.

**Expected tool sequence**

```text
get_place_scope → get_trip_metrics
```

**Actual trace**

```text
get_place_scope(name=부산시, region=) → ERROR/NOT_FOUND
get_place_scope(name=부산, region=) → scope:district:2600000000
get_trip_metrics(metric=fare, scope=scope:district:2600000000, aggregation=avg) → 18028.111
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 부산시의 평균 택시 요금은 **18,028.111 원**입니다.

