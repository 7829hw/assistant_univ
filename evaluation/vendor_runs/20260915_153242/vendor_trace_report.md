# Vendor Tool Trace Acceptance

- Model: qwen3.8:27b
- Agent mode: react
- Timestamp: 2026-09-15T15:32:42.857465+09:00
- 판정 기준: evaluation/vendor/vendor_trace_gold.yaml

## Summary

**Passed: 13 / 13**

| ID | Result | 업체 판정 | Tool Sequence | 실패 분류 |
| --- | --- | --- | --- | --- |
| q01_edge_average_speed | PASS | 정상 | get_passage_metrics | - |
| q02_edge_passage_count | PASS | 정상 | get_passage_count | - |
| q03_station_vicinity_speed | PASS | Tool은 맞음 / 인자 오류 | get_place_scope → get_passage_metrics | - |
| q04_daegu_average_speed | PASS | Tool은 맞음 / 인자 오류 | get_place_scope → get_passage_metrics | - |
| q05_dongseongro_average_speed | PASS | Tool은 맞음 / 인자 오류 | get_place_scope → get_passage_metrics | - |
| q14_vacant_drive_ratio | PASS | 정상 | get_drive_metrics | - |
| q18_private_revenue_by_day | PASS | 정상 | get_operation_metrics | - |
| q22_daegu_origin_destination_count | PASS | Tool은 맞음 / 인자 오류 | get_place_scope → get_place_scope → get_trip_count | - |
| q24_daegu_average_fare | PASS | 최종 성공 / 복구 개선 | get_place_scope → get_trip_metrics | - |
| q25_busan_park_vicinity_count | PASS | 잘못된 조회 방식 | get_place_scope → get_passage_count | - |
| q26_busan_park_vicinity_speed | PASS | 정상 | get_place_scope → get_passage_metrics | - |
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

**Final answer**: 2026년 5월 30일 오후 12시~1시 기준, 해당 도로(scope:edge:1742)의 택시 평균 속도는 **34.912 km/h**입니다.

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

**Final answer**: 2026년 5월 30일 오후 12시~1시 사이에 **scope:edge:19384** 지점을 통과한 택시 통행량은 **3,265건**입니다.

## q03_station_vicinity_speed

**Question**: 2026년 5월 30일 오후 12시~1시 동대구역 근처 차량의 평균 운행 속도는?

> "근처"가 include_vicinity=true로 반영되어야 한다.

**Expected tool sequence**

```text
get_place_scope → get_passage_metrics
```

**Actual trace**

```text
get_place_scope(name=동대구역, region=, include_vicinity=True) → scope:edge:11234
get_passage_metrics(metric=speed, scope=scope:edge:11234, date=20260530, time=120000-130000, aggregation=avg) → 26.558km/h
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 2026년 5월 30일 오후 12시~1시 기준, **동대구역 근처**의 차량 평균 운행 속도는 **26.56 km/h**입니다.

## q04_daegu_average_speed

**Question**: 대구 지역내 택시들의 평균 속도는?

> 질문에 기간이 없다. last_week 같은 조건을 만들면 실패다.

**Expected tool sequence**

```text
get_place_scope → get_passage_metrics
```

**Actual trace**

```text
get_place_scope(name=대구, region=) → scope:district:2700000000
get_passage_metrics(metric=speed, scope=scope:district:2700000000, aggregation=avg) → 27.702km/h
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 대구 지역 내 택시의 평균 속도는 **27.70 km/h**입니다.

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

**Final answer**: 대구 동성로길의 평균 속도는 **30.14 km/h**입니다.

## q14_vacant_drive_ratio

**Question**: 공차로 운행되는 택시 비율은?

**Expected tool sequence**

```text
get_drive_metrics
```

**Actual trace**

```text
get_drive_metrics(metric=vacant_ratio, aggregation=avg) → 35.6%
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 공차로 운행되는 택시 비율(공차율)은 **35.6%** 입니다.

이는 택시가 기동부터 운행 종료까지 전체 운행 경로 중 공차(승객 없이 운행) 상태로 주행한 비율의 평균값입니다.

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

**Final answer**: 개인용 택시의 요일별 평균 일일 수입(영업 수익)은 다음과 같습니다.

| 요일 | 평균 수입 (원) |
|------|---------------|
| 월 | 248,169 |
| 화 | 209,299 |
| 수 | 230,459 |
| 목 | 218,152 |
| 금 | 211,900 |
| 토 | 234,211 |
| 일 | 140,046 |

**요약:**
- **월요일**이 가장 높은 평균 수입(약 24.8만 원)을 기록하고 있습니다.
- **일요일**이 가장 낮으며(약 14.0만 원), 월요일 대비 약 43% 낮은 수준입니다.
- 평일(월~금)은 대체로 21만~25만 원대, 토요일은 23.4만 원대로 평일과 유사한 수준을 유지합니다.

> ※ 위 수치는 개인용 택시 1대 기준의 일평균 영업 수익입니다.

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
get_place_scope(name=동성로, region=대구) → scope:edge:1742
get_place_scope(name=신천동, region=대구) → scope:district:2723510100
get_trip_count(scope_pickup=scope:edge:1742, scope_dropoff=scope:district:2723510100) → [{"scope_pickup": "scope:edge:1742", "scope_dropoff": "scope
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 대구 **동성로**에서 출발하여 **신천동**에 도착한 실차(승객 탑승) 구간 건수는 **2,676건**입니다.

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

**Final answer**: 대구시의 평균 택시 요금은 **약 13,290원**입니다.

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

**Final answer**: 부산 초읍동 어린이대공원 주변의 통행량(택시 passage 수)은 **3,959건**입니다.

## q26_busan_park_vicinity_speed

**Question**: 부산 초읍동에 위치한 어린이대공원 근처의 평균 속도는?

**Expected tool sequence**

```text
get_place_scope → get_passage_metrics
```

**Actual trace**

```text
get_place_scope(name=어린이대공원, region=부산 초읍동, include_vicinity=True) → scope:edge:busan_children_park
get_passage_metrics(metric=speed, scope=scope:edge:busan_children_park, aggregation=avg) → 26.8km/h
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 부산 초읍동 어린이대공원 근처의 평균 속도는 **26.8 km/h**입니다.

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

**Final answer**: 부산 **초읍동**에서 출발하여 **초량동**에 도착한 실차 구간(trip) 건수는 **2,103건**입니다.

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

**Final answer**: 부산시의 평균 택시 요금은 **약 18,028원**입니다.

