# Vendor Tool Trace Acceptance

- Model: qwen3:8b
- Agent mode: react
- Timestamp: 2026-09-15T15:46:31.959738+09:00
- 판정 기준: evaluation/vendor/vendor_trace_gold.yaml

## Summary

**Passed: 7 / 13**

| ID | Result | 업체 판정 | Tool Sequence | 실패 분류 |
| --- | --- | --- | --- | --- |
| q01_edge_average_speed | PASS | 정상 | get_passage_metrics | - |
| q02_edge_passage_count | PASS | 정상 | get_passage_count | - |
| q03_station_vicinity_speed | FAIL | Tool은 맞음 / 인자 오류 | (없음) | EXECUTION_ERROR, TOOL_SEQUENCE_MISMATCH, UNEXPECTED_RETRY |
| q04_daegu_average_speed | FAIL | Tool은 맞음 / 인자 오류 | get_place_scope → get_passage_metrics | FORBIDDEN_ARGUMENT |
| q05_dongseongro_average_speed | FAIL | Tool은 맞음 / 인자 오류 | get_place_scope → get_passage_metrics | FORBIDDEN_ARGUMENT |
| q14_vacant_drive_ratio | PASS | 정상 | get_drive_metrics | - |
| q18_private_revenue_by_day | PASS | 정상 | get_operation_metrics | - |
| q22_daegu_origin_destination_count | FAIL | Tool은 맞음 / 인자 오류 | (없음) | EXECUTION_ERROR, FORBIDDEN_ARGUMENT, SCOPE_PROVENANCE_VIOLATION, TOOL_SEQUENCE_MISMATCH, UNEXPECTED_RETRY, UNGROUNDED_ARGUMENT |
| q24_daegu_average_fare | PASS | 최종 성공 / 복구 개선 | get_place_scope → get_trip_metrics | - |
| q25_busan_park_vicinity_count | FAIL | 잘못된 조회 방식 | get_place_scope → get_passage_count | FORBIDDEN_ARGUMENT |
| q26_busan_park_vicinity_speed | PASS | 정상 | get_place_scope → get_passage_metrics | - |
| q27_busan_origin_destination_count | PASS | Tool은 맞음 / 인자 오류 | get_place_scope → get_place_scope → get_trip_count | - |
| q29_busan_average_fare | FAIL | Tool은 맞음 / 인자 오류 | get_place_scope → get_trip_metrics | FORBIDDEN_ARGUMENT, UNGROUNDED_ARGUMENT, WRONG_ARGUMENT_VALUE |

## q01_edge_average_speed

**Question**: 2026년 5월 30일 오후 12시~1시 scope:edge:1742상의 택시 평균 속도는?

> 질문의 공간·날짜·시간·metric을 그대로 반영해야 한다.

**Expected tool sequence**

```text
get_passage_metrics
```

**Actual trace**

```text
get_passage_metrics(metric=speed, scope=scope:edge:1742, time=120000-130000, aggregation=avg, date=20260530) → 34.912km/h
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 2026년 5월 30일 12:00~13:00, scope:edge:1742 지역의 택시 평균 속도는 **34.912km/h**입니다.

## q02_edge_passage_count

**Question**: 2026년 5월 30일 오후 12시~1시 scope:edge:19384 지점을 통과하는 차량 대수는?

> 단순 통과 대수 조회. taxi_type/taxi_status default는 허용한다.

**Expected tool sequence**

```text
get_passage_count
```

**Actual trace**

```text
get_passage_count(date=20260530, time=120000-130000, scope=scope:edge:19384, taxi_status=all, taxi_type=all) → [{"scope": "scope:edge:19384", "count": 3265}]
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 2026년 5월 30일 12:00~13:00 사이에 scope:edge:19384 지점을 통과한 차량 대수는 **3,265대**입니다.

## q03_station_vicinity_speed

**Question**: 2026년 5월 30일 오후 12시~1시 동대구역 근처 차량의 평균 운행 속도는?

> "근처"가 include_vicinity=true로 반영되어야 한다.

**Expected tool sequence**

```text
get_place_scope → get_passage_metrics
```

**Actual trace**

```text
get_place_scope(name=Daegu Station, region=Daegu, include_vicinity=True) → ERROR/NOT_FOUND
get_place_scope(name=Daegu Station, region=Gyeongbuk, include_vicinity=True) → ERROR/NOT_FOUND
get_place_scope(include_vicinity=True, name=Station, region=Daegu) → ERROR/NOT_FOUND
get_place_scope(include_vicinity=True, name=Daegu Station) → ERROR/NOT_FOUND
get_place_scope(include_vicinity=True, name=Dongdaegu, region=Daegu) → ERROR/NOT_FOUND
get_place_scope(name=Daegu Station, region=Gyeongbuk) → ERROR/NOT_FOUND
get_place_scope(name=Daegu, region=Daegu) → ERROR/NOT_FOUND
get_place_scope(name=Daegu, region=Daegu) → ERROR/NOT_FOUND
```

**Checks**

- FAIL `EXECUTION_ERROR` — 실행이 실패했습니다: 동일한 Tool 오류가 반복됨(get_place_scope/NOT_FOUND): 일치하는 장소 또는 행정구역을 찾을 수 없습니다.
- FAIL `UNEXPECTED_RETRY` — 실패한 Tool 호출이 8회로 허용치(0)를 넘었습니다.
- FAIL `TOOL_SEQUENCE_MISMATCH` — Tool 순서가 다릅니다. 기대 ['get_place_scope', 'get_passage_metrics'], 실제 []

**Final answer**: (없음)

**Runtime error**: 동일한 Tool 오류가 반복됨(get_place_scope/NOT_FOUND): 일치하는 장소 또는 행정구역을 찾을 수 없습니다.

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
get_passage_metrics(date=last_week, metric=speed, aggregation=avg, scope=scope:district:2700000000) → 24.932km/h
```

**Checks**

- FAIL `FORBIDDEN_ARGUMENT` — get_passage_metrics에 질문 근거가 없는 date='last_week'가 있습니다.

**Final answer**: 대구 지역 내 택시들의 지난 주 평균 속도는 **24.932km/h**입니다.

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
get_passage_metrics(date=last_week, metric=speed, scope=scope:edge:1742) → 24.508km/h
```

**Checks**

- FAIL `FORBIDDEN_ARGUMENT` — get_passage_metrics에 질문 근거가 없는 date='last_week'가 있습니다.

**Final answer**: 대구 동성로의 평균 속도는 **24.508km/h**입니다. 이 값은 지난 주간의 운행 데이터를 기반으로 계산한 결과입니다.

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

**Final answer**: 택시가 공차 상태로 운행된 비율은 **35.6%**입니다. 이는 전체 운행 시간 중 승객이 없는 상태로 이동한 시간의 비율을 나타냅니다.

## q18_private_revenue_by_day

**Question**: 개인용 택시의 요일별 택시 수입 분포는?

> fare(trip)와 revenue(operation)를 혼동하면 안 된다.

**Expected tool sequence**

```text
get_operation_metrics
```

**Actual trace**

```text
get_operation_metrics(aggregation=sum, metric=revenue, dimension=dayofweek, taxi_type=private) → [{"dayofweek": "월", "revenue": 2233522}, {"dayofweek": "화", 
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 개인용 택시의 요일별 수입 분포는 다음과 같습니다:

- **월요일**: 2,233,522 원  
- **화요일**: 1,883,689 원  
- **수요일**: 2,074,129 원  
- **목요일**: 1,963,370 원  
- **금요일**: 1,907,104 원  
- **토요일**: 2,107,896 원  
- **일요일**: 1,260,415 원  

**특징**:  
- **월요일**이 가장 높은 수입을 기록했고, **일요일**이 가장 낮은 수입을 보였습니다.  
- 주중(월~금) 수입은 주말(토, 일)에 비해 약 10~20% 높은 흐름을 보입니다.

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
get_place_scope(name=동성로동, region=대구광역시) → ERROR/NOT_FOUND
get_trip_count(date=last_week, scope_pickup=scope:district:2729000000, scope_dropoff=scope:district:2729000001) → ERROR/INVALID_ARGUMENT
get_place_scope(name=동성로동, region=대구광역시) → ERROR/NOT_FOUND
```

**Checks**

- FAIL `EXECUTION_ERROR` — 실행이 실패했습니다: 동일한 Tool 오류가 반복됨(get_place_scope/NOT_FOUND): 일치하는 장소 또는 행정구역을 찾을 수 없습니다.
- FAIL `UNEXPECTED_RETRY` — 실패한 Tool 호출이 4회로 허용치(2)를 넘었습니다.
- FAIL `UNGROUNDED_ARGUMENT` — get_place_scope의 region='대구광역시'가 질문에 없는 값입니다.
- FAIL `FORBIDDEN_ARGUMENT` — get_trip_count에 질문 근거가 없는 date='last_week'가 있습니다.
- FAIL `SCOPE_PROVENANCE_VIOLATION` — get_trip_count에 출처 불명 scope scope:district:2729000000가 전달되었습니다.
- FAIL `SCOPE_PROVENANCE_VIOLATION` — get_trip_count에 출처 불명 scope scope:district:2729000001가 전달되었습니다.
- FAIL `UNGROUNDED_ARGUMENT` — get_place_scope의 region='대구광역시'가 질문에 없는 값입니다.
- FAIL `TOOL_SEQUENCE_MISMATCH` — Tool 순서가 다릅니다. 기대 ['get_place_scope', 'get_place_scope', 'get_trip_count'], 실제 []

**Final answer**: (없음)

**Runtime error**: 동일한 Tool 오류가 반복됨(get_place_scope/NOT_FOUND): 일치하는 장소 또는 행정구역을 찾을 수 없습니다.

## q24_daegu_average_fare

**Question**: 대구시의 평균 택시 요금은?

> 사용자가 말하지 않은 "경상북도" 같은 상위 지역을 만들면 안 된다. 대구시 → 대구 한 번의 복구만 허용한다.

**Expected tool sequence**

```text
get_place_scope → get_trip_metrics
```

**Actual trace**

```text
get_place_scope(name=대구, region=대구시) → scope:district:2700000000
get_trip_metrics(aggregation=avg, metric=fare, scope=scope:district:2700000000) → 13289.667
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 대구시의 평균 택시 요금은 약 **13,289.67 원**입니다.  
(단위: KRW, 통계 기준: 택시 요금 평균값)

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
get_passage_count(date=last_week, scope=scope:edge:busan_children_park) → [{"scope": "scope:edge:busan_children_park", "count": 1075}]
```

**Checks**

- FAIL `FORBIDDEN_ARGUMENT` — get_passage_count에 질문 근거가 없는 date='last_week'가 있습니다.

**Final answer**: 부산 초읍동 어린이대공원 주변의 지난 주 통행량은 **1,075건**입니다.  
이 통행량은 해당 지역 및 주변 도로망(edge)을 포함한 집계 결과입니다.

## q26_busan_park_vicinity_speed

**Question**: 부산 초읍동에 위치한 어린이대공원 근처의 평균 속도는?

**Expected tool sequence**

```text
get_place_scope → get_passage_metrics
```

**Actual trace**

```text
get_place_scope(include_vicinity=True, name=어린이대공원, region=부산 초읍동) → scope:edge:busan_children_park
get_passage_metrics(aggregation=avg, metric=speed, scope=scope:edge:busan_children_park) → 26.8km/h
```

**Checks**

- PASS — gold contract의 모든 조건을 만족합니다.

**Final answer**: 부산 초읍동 어린이대공원 근처의 평균 속도는 **26.8km/h**입니다.

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

**Final answer**: 부산 초읍동(.scope:district:2623010700)에서 초량동(.scope:district:2617010100)으로 운행한 실차 구간 건수는 **2,103건**입니다.

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
get_place_scope(name=부산광역시, region=) → scope:district:2600000000
get_trip_metrics(aggregation=avg, date=last_month, metric=fare, scope=scope:district:2600000000) → 26329.667
```

**Checks**

- FAIL `UNGROUNDED_ARGUMENT` — get_place_scope의 name='부산광역시'가 질문에 없는 값입니다.
- FAIL `FORBIDDEN_ARGUMENT` — get_trip_metrics에 질문 근거가 없는 date='last_month'가 있습니다.
- FAIL `WRONG_ARGUMENT_VALUE` — get_place_scope.name 값이 다릅니다. 기대 {'any_of': ['부산시', '부산']}, 실제 '부산광역시'

**Final answer**: 부산광역시의 평균 택시 요금은 지난 달 기준 **26,329.67 원**입니다.  

이 데이터는 도로 공간 범위 `scope:district:2600000000` (부산광역시 전체)을 기준으로 계산되었습니다.  
추가적으로 특정 지역 또는 시간대별로 분석이 필요하시면 알려주세요!

