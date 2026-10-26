# protected_final_v2 P·C 거부 패턴 목록(결정 239 Z7)

현재 코드(지문 `791c4a68`)와 mock에서 업체 형식 호출 뼈대가 실제로 어떤 결과로 끝나는지 확인한 목록이다. **질문 문장은 쓰지 않는다. 뼈대만 쓴다.** 모델 호출은 없다.

- 확인 도구는 `protected_final_v2/pc_patterns9.py`이고, 결과는 `pc_patterns9.json`이다.
- 뼈대의 `<장소>`·`<기간>`·`<여러 달 기간>`은 자리표시다. 확인할 때는 두 벌로 채워 돌렸다.
  - 1벌: 대구 / last_month / last_year
  - 2벌: 부산 / this_month / this_year
- 두 벌의 결과가 같고 기대 결과(P = `unsupported`, C = `needs_clarification`)와 맞으면 "확인"으로 적었다.
- 실행 경로는 `derive_grounding` → `_pipeline(_GoldPlanner)`로, `validate_pf2.py`가 P·C 행을 검사하는 경로와 같다.
  - 이 경로의 결과는 정답 호출(grounding)만으로 정해진다. 질문 문장에 따른 조건 검사(날짜 표현, 장소 근거)는 이 경로에서 결과를 바꾸지 않았다.
- 작성 시 주의: P·C 문항의 정답 호출은 "질문을 그대로 옮긴 호출"이다.
  - 질문이 그 조건을 실제로 말해야 한다. P는 뼈대의 조건이 질문에 있어야 하고, C는 빠진 조건이 질문에 정말 없어야 한다.
  - 결과는 서식 검사(`validate_pf2.py`)가 문항마다 다시 확인한다.

## 1. 설계표 후보의 실제 결과

| 후보 | 내용 | 뼈대 | 결과 | 오류 코드 | 판단 |
|---|---|---|---|---|---|
| P-1 | 통행 지표에 택시 유형 | `get_place_scope(name=<장소>) → get_trip_metrics(metric=fare, scope=$resolve.scope, date=<기간>, taxi_type=private, aggregation=avg)` | unsupported | UNCONSUMED_CONDITION | 확인 |
| P-2 | 통과량 지표에 택시 유형 | `get_place_scope(name=<장소>) → get_passage_metrics(metric=speed, scope=$resolve.scope, date=<기간>, taxi_type=private, aggregation=avg)` | unsupported | UNCONSUMED_CONDITION | 확인 |
| P-3 | 통과량 지표에 운행 상태 | `get_place_scope(name=<장소>) → get_passage_metrics(metric=speed, scope=$resolve.scope, date=<기간>, taxi_status=occupied, aggregation=avg)` | unsupported | UNCONSUMED_CONDITION | 확인 |
| P-4 | 운행 지표에 차원 | `get_place_scope(name=<장소>) → get_drive_metrics(metric=vacant_ratio, scope=$resolve.scope, date=<기간>, dimension=sigungu, aggregation=avg)` | unsupported | UNCONSUMED_CONDITION | 확인 |
| P-5 | 운행 지표에 묶음·rollup | `get_place_scope(name=<장소>) → get_drive_metrics(metric=vacant_ratio, scope=$resolve.scope, date=<여러 달 기간>, aggregation=avg, bucket=month, rollup=max)` | unsupported | UNVERIFIED_TIMS_CONTRACT | 확인 |
| C-1 | 요금 지표에 묶음·rollup만, 구간 안 집계 없음 | `get_place_scope(name=<장소>) → get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<여러 달 기간>, bucket=month, rollup=max)` | needs_clarification | AMBIGUOUS_INNER_AGGREGATION | 확인 |
| C-2 | 요금 지표에 묶음만, 집계 없음 | `get_place_scope(name=<장소>) → get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<여러 달 기간>, bucket=month)` | needs_clarification | INVALID_FACTOR_COMBINATION | 확인 |
| C-3 | 질문에 장소 이름 없음("거기" 등) — 정답 호출에 장소 없음 | `get_trip_count(date=<기간>)` | answered | - | 답함 |

- **C-3은 거부로 끝나지 않는다**(답함). 정답 호출에 장소가 없으면 전국 범위로 계산한다. 질문의 "거기"는 이 경로에서 확인 요청이 되지 않는다.
  C-3은 C 패턴으로 쓰지 않는다. 대신 아래 C 대체 패턴을 쓴다.

## 2. 확보한 대체 패턴(모두 "확인")

| 번호 | 형 | 상황 | 뼈대 | 결과 | 오류 코드 |
|---|---|---|---|---|---|
| P-a | P | 요금 지표: 장소 scope와 시도 차원을 함께(scope가 막는 차원) | `get_place_scope(name=<장소>) → get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<기간>, dimension=sido)` | unsupported | PARAM_VALUE_FORBIDS_INPUT |
| P-b | P | 요금 지표: H3 차원인데 장소 scope 없음 | `get_billing_metrics(metric=revenue, date=<기간>, dimension=h3)` | unsupported | PARAM_VALUE_REQUIRES_INPUT |
| P-c | P | 속도의 합계(정의되지 않은 측정값 집계) | `get_place_scope(name=<장소>) → get_passage_metrics(metric=speed, scope=$resolve.scope, date=<기간>, aggregation=sum)` | unsupported | UNDEFINED_MEASURE_AGGREGATION |
| P-d | P | 공차율의 합계(정의되지 않은 측정값 집계) | `get_place_scope(name=<장소>) → get_drive_metrics(metric=vacant_ratio, scope=$resolve.scope, date=<기간>, aggregation=sum)` | unsupported | UNDEFINED_MEASURE_AGGREGATION |
| P-e | P | 통행 건수에 월 묶음(묶음을 받지 않는 측정값) | `get_place_scope(name=<장소>) → get_trip_count(scope_pickup=$resolve.scope, date=<여러 달 기간>, bucket=month, aggregation=sum, rollup=avg)` | unsupported | UNSUPPORTED_GROUPED_MEASURE |
| P-f | P | 요금 지표: 요일 차원과 월 묶음을 함께 | `get_place_scope(name=<장소>) → get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<여러 달 기간>, dimension=dayofweek, aggregation=sum, bucket=month, rollup=avg)` | unsupported | UNSUPPORTED_AGGREGATION_COMBINATION |
| P-g | P | 통과량 지표에 묶음·rollup | `get_place_scope(name=<장소>) → get_passage_metrics(metric=rpm, scope=$resolve.scope, date=<여러 달 기간>, aggregation=avg, bucket=month, rollup=max)` | unsupported | UNVERIFIED_TIMS_CONTRACT |
| P-h | P | 통행 건수에 택시 유형 | `get_place_scope(name=<장소>) → get_trip_count(scope_pickup=$resolve.scope, date=<기간>, taxi_type=private)` | unsupported | UNCONSUMED_CONDITION |
| P-i | P | 요금 지표에 운행 상태 | `get_place_scope(name=<장소>) → get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<기간>, taxi_status=occupied, aggregation=sum)` | unsupported | UNCONSUMED_CONDITION |
| C-a | C | 요금 지표: 묶음과 구간 안 집계는 있으나 구간별 결과를 모으는 방법(rollup) 없음 | `get_place_scope(name=<장소>) → get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<여러 달 기간>, aggregation=sum, bucket=month)` | needs_clarification | INVALID_FACTOR_COMBINATION |
| C-b | C | 요금 지표: rollup만 있고 묶음 없음 | `get_place_scope(name=<장소>) → get_billing_metrics(metric=revenue, scope=$resolve.scope, date=<여러 달 기간>, aggregation=sum, rollup=max)` | needs_clarification | INVALID_FACTOR_COMBINATION |
| C-c | C | 통과량 건수: 차원·순위 방향만, 개수(limit) 없음 | `get_place_scope(name=<장소>) → get_passage_count(scope=$resolve.scope, date=<기간>, dimension=h3, order=top)` | needs_clarification | INVALID_FACTOR_COMBINATION |
| C-d | C | 운행 지표: 묶음·rollup만, 구간 안 집계 없음 | `get_place_scope(name=<장소>) → get_drive_metrics(metric=vacant_ratio, scope=$resolve.scope, date=<여러 달 기간>, bucket=month, rollup=max)` | needs_clarification | AMBIGUOUS_INNER_AGGREGATION |
| C-e | C | 운행 지표: 차원 없이 순위·개수 | `get_place_scope(name=<장소>) → get_drive_metrics(metric=vacant_ratio, scope=$resolve.scope, date=<기간>, order=top, limit=3)` | needs_clarification | INVALID_FACTOR_COMBINATION |

## 3. 요약

- P(확인 14): P-1, P-2, P-3, P-4, P-5, P-a, P-b, P-c, P-d, P-e, P-f, P-g, P-h, P-i.
  - 오류 코드 7가지: UNCONSUMED_CONDITION 6, UNVERIFIED_TIMS_CONTRACT 2, PARAM_VALUE_FORBIDS_INPUT 1, PARAM_VALUE_REQUIRES_INPUT 1, UNDEFINED_MEASURE_AGGREGATION 2, UNSUPPORTED_GROUPED_MEASURE 1, UNSUPPORTED_AGGREGATION_COMBINATION 1.
  - 명세 3.3의 "서로 다른 오류 유형 4가지 이상"을 채울 수 있다.
- C(확인 7): C-1, C-2, C-a, C-b, C-c, C-d, C-e.
  - 오류 코드는 2가지(AMBIGUOUS_INNER_AGGREGATION 2, INVALID_FACTOR_COMBINATION 5)다.
  - 상황으로는 6가지로 나뉜다.
    1. 구간 안 집계 없음: C-1, C-d
    2. 묶음만 있음: C-2
    3. rollup 없음: C-a
    4. 묶음 없는 rollup: C-b
    5. 순위에 개수 없음: C-c
    6. 차원 없는 순위: C-e
  - 명세 3.3의 "3가지 이상 상황"을 채울 수 있다.
  - 다만 오류 코드 기준으로는 2가지뿐이다. 서식의 "거부 범주"에는 패턴 번호를 적는다.
- 명세의 P·C 최소 개수(P 10, 범주 4 이상; C 6, 범주 3 이상)는 바꾸지 않는다.
