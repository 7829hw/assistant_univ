# v2 평가 보고서: 20260929_014313_v2_holdout_qwen3_8b

잠정치: 평가셋은 사람이 검토하지 않았다(registry review.status unreviewed). mock 고정값으로 실행했으므로 수치의 정확성이 아니라 요청 인자·집계 의미·결과 종류를 채점했다.

- 커밋 5c2991ea281c51994af3a4ad3db003e0d069749a (dirty []), 명령 `evaluate_v2.py run --model qwen3:8b --sets holdout_v2 --label v2_holdout_qwen3_8b`
- 모델 qwen3:8b digest 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 {'family': 'qwen3', 'parameter_size': '8.2B', 'quantization_level': 'Q4_K_M', 'format': 'gguf'}, Ollama 0.34.4
- 설정 {"agent_mode": "geoflow", "aggregation_grounding": "flat", "condition_check": false, "provider": "mock", "tims_execution": "legacy", "example_retrieval": "off", "ollama_options": {"temperature": 0}, "think": "auto"}, chat timeout 300.0
- 기준일 2026-09-25 (Asia/Seoul), 시작 2026-09-29T01:43:13.315026+09:00
- planner prompt sha256 db113124b2e26aa9b47b7f6d9e56387becd19e6add2debaab54657598c171ba8
- 입력 sha256 {"evaluation/v2/paraphrases_holdout_v2.yaml": "d1884be436d8f61e1ac20370e3654ccc39a3480602cde95e4c181cb6bc0f614e", "evaluation/v2/holdout_v2_parents.yaml": "25d2d350bb750d073172292d1ce611f125ca69937ea4e564e5047cd5328dc24c", "mock_stub.yaml": "180550f4e4b7810a2476bec9f4192c035c21e4e32369766b0802208db5a12889"}

## 전체 (문장 단위)

| 지표 | 값 |
| --- | --- |
| 의미 정답(전체) | 52/126 (41.3%) |
| 실행 완료(answered 기대 문장 중 답함) | 46/78 (59.0%) |
| 의미 정답(answered 기대 문장) | 42/78 (53.8%) |
| 거부 정확도 strict(기대 종류로 멈춤) | 10/48 (20.8%) |
| 보조: 거부 기대 문장에서 답하지 않음 | 42/48 (87.5%) |

intent 단위(42개): 모든 문장 정답 10/42 (23.8%), 과반 문장 정답 16/42 (38.1%).

## 기대 결과별

| 기대 결과 | 문장 정답 | intent(모든 문장) 정답 | intent(과반) 정답 |
| --- | --- | --- | --- |
| answered | 42/78 (53.8%) | 9/26 (34.6%) | 13/26 (50.0%) |
| needs_clarification | 0/15 (0.0%) | 0/5 (0.0%) | 0/5 (0.0%) |
| unsupported | 10/33 (30.3%) | 1/11 (9.1%) | 3/11 (27.3%) |

## 기대 결과 × 실제 결과 (문장)

| 기대 \ 실제 | answered | needs_clarification | unsupported | failed |
| --- | --- | --- | --- | --- |
| answered | 46 | 11 | 2 | 19 |
| needs_clarification | 3 | 0 | 5 | 7 |
| unsupported | 3 | 4 | 10 | 16 |

## 절별

| 절 | 문장 정답 | 실행 완료 | 거부 strict | intent(모든 문장) |
| --- | --- | --- | --- | --- |
| A aggregation holdout 복원 | 7/30 (23.3%) | 8/18 (44.4%) | 1/12 (8.3%) | 1/10 (10.0%) |
| B local aggregation holdout 복원 | 8/30 (26.7%) | 9/18 (50.0%) | 0/12 (0.0%) | 2/10 (20.0%) |
| C verifier holdout 복원 | 16/21 (76.2%) | 16/18 (88.9%) | 0/3 (0.0%) | 5/7 (71.4%) |
| D v2 거부 | 9/21 (42.9%) | - | 9/21 (42.9%) | 1/7 (14.3%) |
| E v2 경계 | 12/24 (50.0%) | 13/24 (54.2%) | - | 1/8 (12.5%) |

stage-swap 대상 두 단계 answered intent 11개: 문장 정답 9/33 (27.3%), intent(모든 문장) 0/11 (0.0%).

## 범주

| 범주 | 문장 |
| --- | --- |
| correct | 52 |
| failed_instead_of_refusal | 23 |
| grounding_failure | 15 |
| refused_supported | 13 |
| wrong_refusal_kind | 9 |
| answered_instead_of_refusal | 6 |
| execution_failure | 4 |
| aggregation_error | 3 |
| wrong_tool_args | 1 |

unsupported 기대 문장에서 답하지 않은 경우의 결과·코드: {"failed:INVALID_FACTOR": 11, "unsupported:UNVERIFIED_TIMS_CONTRACT": 2, "failed:INVALID_SUBTYPE": 3, "failed:INVALID_CONCEPT": 2, "unsupported:UNDEFINED_MEASURE_AGGREGATION": 4, "needs_clarification:AMBIGUOUS_INNER_AGGREGATION": 4, "unsupported:PARAM_VALUE_FORBIDS_INPUT": 2, "unsupported:PARAM_VALUE_REQUIRES_INPUT": 2}

## intent별

| intent | 기대 | p0 | p1 | p2 |
| --- | --- | --- | --- | --- |
| w01_last_month_week_sum_then_avg_fare | answered | refused_supported (UNVERIFIED_TIMS_CONTRACT) | correct | aggregation_error |
| w02_last_month_week_min_then_avg_fare | answered | refused_supported (AMBIGUOUS_INNER_AGGREGATION) | correct | refused_supported (AMBIGUOUS_INNER_AGGREGATION) |
| w03_jul_aug_month_sum_then_min_days | answered | grounding_failure (INVALID_FACTOR) | aggregation_error | grounding_failure (INVALID_FACTOR) |
| w04_last_month_week_unspecified_max_fare | needs_clarification | answered_instead_of_refusal | answered_instead_of_refusal | answered_instead_of_refusal |
| w05_jul_aug_month_avg_then_sum_fare | unsupported | failed_instead_of_refusal (INVALID_FACTOR) | failed_instead_of_refusal (INVALID_FACTOR) | correct (UNVERIFIED_TIMS_CONTRACT) |
| w06_jul_aug_month_avg_then_min_days | unsupported | failed_instead_of_refusal (INVALID_FACTOR) | failed_instead_of_refusal (INVALID_FACTOR) | failed_instead_of_refusal (INVALID_FACTOR) |
| w07_last_week_avg_fare | answered | correct | correct | correct |
| w08_aug_sum_days | answered | grounding_failure (INVALID_FACTOR) | grounding_failure (INVALID_FACTOR) | grounding_failure (INVALID_FACTOR) |
| w09_jul_aug_private_month_sum_then_avg_days | answered | correct | refused_supported (AMBIGUOUS_INNER_AGGREGATION) | grounding_failure (INVALID_FACTOR) |
| w10_last_month_corporate_week_unspecified_max_vacant | needs_clarification | failed_instead_of_refusal (INVALID_FACTOR_COMBINATION) | failed_instead_of_refusal (INVALID_SUBTYPE) | failed_instead_of_refusal (INVALID_FACTOR_COMBINATION) |
| w11_jul_aug_month_sum_then_max_fare | answered | refused_supported (AMBIGUOUS_INNER_AGGREGATION) | grounding_failure (INVALID_FACTOR) | grounding_failure (INVALID_FACTOR) |
| w12_jul_aug_month_avg_then_min_vacant | unsupported | failed_instead_of_refusal (INVALID_FACTOR) | failed_instead_of_refusal (INVALID_FACTOR) | failed_instead_of_refusal (INVALID_FACTOR) |
| w13_last_month_week_min_then_avg_vacant | answered | correct | refused_supported (AMBIGUOUS_INNER_AGGREGATION) | refused_supported (AMBIGUOUS_INNER_AGGREGATION) |
| w14_jul_aug_month_unspecified_avg_days | needs_clarification | failed_instead_of_refusal (INVALID_FACTOR) | wrong_refusal_kind (UNVERIFIED_TIMS_CONTRACT) | failed_instead_of_refusal (INVALID_FACTOR) |
| w15_jul_aug_month_sum_then_avg_fare_final_first | answered | aggregation_error | grounding_failure (INVALID_FACTOR) | refused_supported (AMBIGUOUS_INNER_AGGREGATION) |
| w16_jul_aug_corporate_month_sum_then_min_days | answered | refused_supported (UNVERIFIED_TIMS_CONTRACT) | grounding_failure (INVALID_FACTOR) | correct |
| w17_last_month_daegu_week_unspecified_avg_vacant | needs_clarification | wrong_refusal_kind (UNVERIFIED_TIMS_CONTRACT) | wrong_refusal_kind (UNVERIFIED_TIMS_CONTRACT) | wrong_refusal_kind (UNVERIFIED_TIMS_CONTRACT) |
| w18_jul_aug_busan_month_avg_then_max_fare | unsupported | failed_instead_of_refusal (INVALID_FACTOR) | failed_instead_of_refusal (INVALID_FACTOR) | failed_instead_of_refusal (INVALID_FACTOR) |
| w19_last_week_min_fare | answered | correct | correct | correct |
| w20_private_avg_days | answered | correct | correct | correct |
| w21_last_month_week_sum_then_max_days | answered | correct | refused_supported (AMBIGUOUS_INNER_AGGREGATION) | refused_supported (AMBIGUOUS_INNER_AGGREGATION) |
| w22_jul_aug_month_unspecified_med_fare | needs_clarification | failed_instead_of_refusal (INVALID_FACTOR) | wrong_refusal_kind (UNVERIFIED_TIMS_CONTRACT) | failed_instead_of_refusal (INVALID_FACTOR) |
| w23_control_min_fare | answered | correct | correct | correct |
| w24_last_month_private_sum_days | answered | correct | correct | correct |
| w25_control_max_days | answered | correct | correct | correct |
| w26_weekend_sum_fare | answered | correct | correct | correct |
| w27_control_days_by_day | answered | correct | correct | correct |
| w28_last_month_corporate_avg_hours | unsupported | failed_instead_of_refusal (INVALID_SUBTYPE) | failed_instead_of_refusal (INVALID_SUBTYPE) | failed_instead_of_refusal (INVALID_SUBTYPE) |
| w29_private_operating_count_top_sido | unsupported | answered_instead_of_refusal | failed_instead_of_refusal (INVALID_CONCEPT) | answered_instead_of_refusal |
| w30_last_month_ratio_sum | unsupported | correct (UNDEFINED_MEASURE_AGGREGATION) | correct (UNDEFINED_MEASURE_AGGREGATION) | correct (UNDEFINED_MEASURE_AGGREGATION) |
| w31_jul_aug_week_sum_active_count_avg | unsupported | wrong_refusal_kind (AMBIGUOUS_INNER_AGGREGATION) | correct (UNDEFINED_MEASURE_AGGREGATION) | wrong_refusal_kind (AMBIGUOUS_INNER_AGGREGATION) |
| w32_last_month_week_max_then_avg_ratio | unsupported | wrong_refusal_kind (AMBIGUOUS_INNER_AGGREGATION) | wrong_refusal_kind (AMBIGUOUS_INNER_AGGREGATION) | correct (UNVERIFIED_TIMS_CONTRACT) |
| w33_daegu_revenue_by_day | unsupported | correct (PARAM_VALUE_FORBIDS_INPUT) | correct (PARAM_VALUE_FORBIDS_INPUT) | answered_instead_of_refusal |
| w34_revenue_top_sigungu | unsupported | failed_instead_of_refusal (INVALID_CONCEPT) | correct (PARAM_VALUE_REQUIRES_INPUT) | correct (PARAM_VALUE_REQUIRES_INPUT) |
| w35_last_month_top_pickup_emd | answered | correct | correct | execution_failure (NOT_FOUND) |
| w36_last_month_bottom_dropoff_sigungu | answered | grounding_failure (INVALID_CONCEPT) | execution_failure (NOT_FOUND) | execution_failure (NOT_FOUND) |
| w37_last_month_top_od_routes_emd | answered | grounding_failure (VALUELESS_CONCEPT) | grounding_failure (VALUELESS_CONCEPT) | execution_failure (NOT_FOUND) |
| w38_this_week_dongdaegu_vicinity_passage_count | answered | correct | correct | correct |
| w39_this_month_busan_avg_fare | answered | grounding_failure (INVALID_FACTOR) | correct | correct |
| w40_this_year_corporate_vacant | answered | correct | correct | grounding_failure (INVALID_FACTOR) |
| w41_this_month_week_sum_then_max_fare | answered | correct | wrong_tool_args | refused_supported (AMBIGUOUS_INNER_AGGREGATION) |
| w42_last_month_dongdaegu_week_max_then_avg_speed | answered | correct | refused_supported (AMBIGUOUS_INNER_AGGREGATION) | correct |

## 실패 목록

- `w01_p0` 지난달 주마다 합한 택시 요금의 평균은? — 기대 answered, 실제 unsupported / refused_supported / UNVERIFIED_TIMS_CONTRACT; 인자 차이 [['aggregation', 'sum', 'avg']]; 집계 {'bucket': 'week', 'inner': 'avg', 'final': 'avg'} (기대 {'bucket': 'week', 'inner': 'sum', 'final': 'avg'}); tools []
- `w01_p2` 지난달 택시 요금을 주마다 합하면 그 평균은? — 기대 answered, 실제 answered / aggregation_error / None; 인자 차이 [['bucket', 'week', 'month']]; 집계 {'bucket': 'month', 'inner': 'sum', 'final': 'avg'} (기대 {'bucket': 'week', 'inner': 'sum', 'final': 'avg'}); tools ['get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'local:COLLECT_GROUPS', 'local:REDUCE_GROUPS']
- `w02_p0` 지난달 매주 가장 낮았던 택시 요금의 평균은? — 기대 answered, 실제 needs_clarification / refused_supported / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 {'bucket': 'week', 'inner': 'min', 'final': 'avg'}); tools []
- `w02_p2` 매주 가장 낮았던 택시 요금을 지난달 기준으로 평균 내면? — 기대 answered, 실제 needs_clarification / refused_supported / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 {'bucket': 'week', 'inner': 'min', 'final': 'avg'}); tools []
- `w03_p0` 2026년 7월부터 8월까지 달마다 합한 운행일수 가운데 가장 작은 값은? — 기대 answered, 실제 failed / grounding_failure / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'sum', 'final': 'min'}); tools []
- `w03_p1` 달마다 합한 운행일수 가운데 2026년 7월부터 8월까지 가장 작은 값은? — 기대 answered, 실제 answered / aggregation_error / None; 인자 차이 [['bucket', 'month', None], ['aggregation', 'sum', 'min'], ['rollup', 'min', None]]; 집계 {'final': 'min'} (기대 {'bucket': 'month', 'inner': 'sum', 'final': 'min'}); tools ['get_billing_metrics']
- `w03_p2` 2026년 7월부터 8월까지 운행일수를 달마다 합한 값 가운데 가장 작은 값은? — 기대 answered, 실제 failed / grounding_failure / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'sum', 'final': 'min'}); tools []
- `w04_p0` 지난달 주별 택시 요금의 최댓값은? — 기대 needs_clarification, 실제 answered / answered_instead_of_refusal / None; 인자 차이 [['aggregation', None, 'max']]; 집계 {'bucket': 'week', 'inner': 'max', 'final': 'max'} (기대 {'bucket': 'week', 'inner': 'unspecified', 'final': 'max'}); tools ['get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'local:COLLECT_GROUPS', 'local:REDUCE_GROUPS']
- `w04_p1` 택시 요금의 지난달 주별 최댓값은? — 기대 needs_clarification, 실제 answered / answered_instead_of_refusal / None; 인자 차이 [['aggregation', None, 'max']]; 집계 {'bucket': 'week', 'inner': 'max', 'final': 'max'} (기대 {'bucket': 'week', 'inner': 'unspecified', 'final': 'max'}); tools ['get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'local:COLLECT_GROUPS', 'local:REDUCE_GROUPS']
- `w04_p2` 지난달 택시 요금을 주별로 보면 최댓값은? — 기대 needs_clarification, 실제 answered / answered_instead_of_refusal / None; 인자 차이 [['aggregation', None, 'max']]; 집계 {'bucket': 'week', 'inner': 'max', 'final': 'max'} (기대 {'bucket': 'week', 'inner': 'unspecified', 'final': 'max'}); tools ['get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'local:COLLECT_GROUPS', 'local:REDUCE_GROUPS']
- `w05_p0` 2026년 7월부터 8월까지 달마다 평균 낸 택시 요금을 모두 합하면? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'avg', 'final': 'sum'}); tools []
- `w05_p1` 달마다 평균 낸 택시 요금을 2026년 7월부터 8월까지 모두 합하면? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'avg', 'final': 'sum'}); tools []
- `w06_p0` 2026년 7월부터 8월까지 각 달의 평균 운행일수 중 가장 작은 값은? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'avg', 'final': 'min'}); tools []
- `w06_p1` 각 달의 평균 운행일수 중 2026년 7월부터 8월까지 가장 작은 값은? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'avg', 'final': 'min'}); tools []
- `w06_p2` 2026년 7월부터 8월까지 운행일수를 각 달의 평균으로 보면 가장 작은 값은? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'avg', 'final': 'min'}); tools []
- `w08_p0` 2026년 8월 택시 운행일수의 합계는? — 기대 answered, 실제 failed / grounding_failure / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'final': 'sum'}); tools []
- `w08_p1` 택시 운행일수의 2026년 8월 합계는? — 기대 answered, 실제 failed / grounding_failure / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'final': 'sum'}); tools []
- `w08_p2` 2026년 8월의 택시 운행일수 합계는 얼마인가요? — 기대 answered, 실제 failed / grounding_failure / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'final': 'sum'}); tools []
- `w09_p1` 개인택시 운행일수를 2026년 7월부터 8월까지 달마다 합한 값의 평균은? — 기대 answered, 실제 needs_clarification / refused_supported / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'sum', 'final': 'avg'}); tools []
- `w09_p2` 2026년 7월부터 8월까지 달마다 합한 개인택시 운행일수의 평균은? — 기대 answered, 실제 failed / grounding_failure / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'sum', 'final': 'avg'}); tools []
- `w10_p0` 지난달 법인택시의 주별 공차율 최댓값은? — 기대 needs_clarification, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR_COMBINATION; 인자 차이 None; 집계 None (기대 {'bucket': 'week', 'inner': 'unspecified', 'final': 'max'}); tools []
- `w10_p1` 법인택시의 지난달 주별 공차율 최댓값은? — 기대 needs_clarification, 실제 failed / failed_instead_of_refusal / INVALID_SUBTYPE; 인자 차이 None; 집계 None (기대 {'bucket': 'week', 'inner': 'unspecified', 'final': 'max'}); tools []
- `w10_p2` 지난달 주별 공차율 최댓값을 법인택시 기준으로 알려줘 — 기대 needs_clarification, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR_COMBINATION; 인자 차이 None; 집계 None (기대 {'bucket': 'week', 'inner': 'unspecified', 'final': 'max'}); tools []
- `w11_p0` 2026년 7월부터 8월까지 월마다 택시 요금을 합산하면 그중 최댓값은? — 기대 answered, 실제 needs_clarification / refused_supported / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'sum', 'final': 'max'}); tools []
- `w11_p1` 월마다 택시 요금을 2026년 7월부터 8월까지 합산하면 그중 최댓값은? — 기대 answered, 실제 failed / grounding_failure / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'sum', 'final': 'max'}); tools []
- `w11_p2` 2026년 7월부터 8월까지 택시 요금을 월마다 합산하면 그중 최댓값은? — 기대 answered, 실제 failed / grounding_failure / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'sum', 'final': 'max'}); tools []
- `w12_p0` 2026년 7월부터 8월까지 달마다 평균 낸 공차율 중 가장 낮은 값은? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'avg', 'final': 'min'}); tools []
- `w12_p1` 달마다 평균 낸 공차율 중 2026년 7월부터 8월까지 가장 낮은 값은? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'avg', 'final': 'min'}); tools []
- `w12_p2` 2026년 7월부터 8월까지 공차율을 달마다 평균 낸 값 중 가장 낮은 값은? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'avg', 'final': 'min'}); tools []
- `w13_p1` 주마다 가장 낮았던 공차율을 지난달 기준으로 평균하면? — 기대 answered, 실제 needs_clarification / refused_supported / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 {'bucket': 'week', 'inner': 'min', 'final': 'avg'}); tools []
- `w13_p2` 지난달 공차율이 주마다 가장 낮았던 값을 평균하면? — 기대 answered, 실제 needs_clarification / refused_supported / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 {'bucket': 'week', 'inner': 'min', 'final': 'avg'}); tools []
- `w14_p0` 2026년 7월부터 8월까지 월 단위 운행일수의 평균은? — 기대 needs_clarification, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'unspecified', 'final': 'avg'}); tools []
- `w14_p1` 월 단위 운행일수의 2026년 7월부터 8월까지 평균은? — 기대 needs_clarification, 실제 unsupported / wrong_refusal_kind / UNVERIFIED_TIMS_CONTRACT; 인자 차이 []; 집계 {'bucket': 'month', 'inner': 'avg', 'final': 'avg'} (기대 {'bucket': 'month', 'inner': 'unspecified', 'final': 'avg'}); tools []
- `w14_p2` 2026년 7월부터 8월까지 운행일수를 월 단위로 본 평균은? — 기대 needs_clarification, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'unspecified', 'final': 'avg'}); tools []
- `w15_p0` 2026년 7월부터 8월까지 평균적으로 한 달 택시 요금 합계는 얼마인가요? — 기대 answered, 실제 answered / aggregation_error / None; 인자 차이 [['bucket', 'month', None], ['aggregation', 'sum', 'avg'], ['rollup', 'avg', None]]; 집계 {'final': 'avg'} (기대 {'bucket': 'month', 'inner': 'sum', 'final': 'avg'}); tools ['get_trip_metrics']
- `w15_p1` 평균적으로 한 달 택시 요금 합계는 2026년 7월부터 8월까지 얼마인가요? — 기대 answered, 실제 failed / grounding_failure / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'sum', 'final': 'avg'}); tools []
- `w15_p2` 2026년 7월부터 8월까지 한 달 택시 요금 합계는 평균적으로 얼마인가요? — 기대 answered, 실제 needs_clarification / refused_supported / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'sum', 'final': 'avg'}); tools []
- `w16_p0` 2026년 7월부터 8월까지 법인택시의 달별 운행일수 합계 중 최솟값은? — 기대 answered, 실제 unsupported / refused_supported / UNVERIFIED_TIMS_CONTRACT; 인자 차이 [['date', '20260701-20260831', '20260731-20260831'], ['aggregation', 'sum', 'min'], ['rollup', 'min', 'sum'], ['condition:date', '20260701-20260831', '20260731-20260831']]; 집계 {'bucket': 'month', 'inner': 'min', 'final': 'sum'} (기대 {'bucket': 'month', 'inner': 'sum', 'final': 'min'}); tools []
- `w16_p1` 법인택시의 2026년 7월부터 8월까지 달별 운행일수 합계 중 최솟값은? — 기대 answered, 실제 failed / grounding_failure / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'sum', 'final': 'min'}); tools []
- `w17_p0` 지난달 대구의 주별 공차율 평균은? — 기대 needs_clarification, 실제 unsupported / wrong_refusal_kind / UNVERIFIED_TIMS_CONTRACT; 인자 차이 []; 집계 {'bucket': 'week', 'inner': 'avg', 'final': 'avg'} (기대 {'bucket': 'week', 'inner': 'unspecified', 'final': 'avg'}); tools []
- `w17_p1` 대구의 지난달 주별 공차율 평균은? — 기대 needs_clarification, 실제 unsupported / wrong_refusal_kind / UNVERIFIED_TIMS_CONTRACT; 인자 차이 []; 집계 {'bucket': 'week', 'inner': 'avg', 'final': 'avg'} (기대 {'bucket': 'week', 'inner': 'unspecified', 'final': 'avg'}); tools []
- `w17_p2` 지난달 주별 공차율의 대구 평균은? — 기대 needs_clarification, 실제 unsupported / wrong_refusal_kind / UNVERIFIED_TIMS_CONTRACT; 인자 차이 []; 집계 {'bucket': 'week', 'inner': 'avg', 'final': 'avg'} (기대 {'bucket': 'week', 'inner': 'unspecified', 'final': 'avg'}); tools []
- `w18_p0` 2026년 7월부터 8월까지 부산에서 달마다 평균 낸 택시 요금의 최댓값은? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'avg', 'final': 'max'}); tools []
- `w18_p1` 부산에서 2026년 7월부터 8월까지 달마다 평균 낸 택시 요금의 최댓값은? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'avg', 'final': 'max'}); tools []
- `w18_p2` 2026년 7월부터 8월까지 달마다 평균 낸 부산 택시 요금의 최댓값은? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'avg', 'final': 'max'}); tools []
- `w21_p1` 운행일수를 지난달 주마다 더했을 때 가장 큰 값은? — 기대 answered, 실제 needs_clarification / refused_supported / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 {'bucket': 'week', 'inner': 'sum', 'final': 'max'}); tools []
- `w21_p2` 지난달 주별 운행일수 합계의 최댓값은? — 기대 answered, 실제 needs_clarification / refused_supported / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 {'bucket': 'week', 'inner': 'sum', 'final': 'max'}); tools []
- `w22_p0` 2026년 7월부터 8월까지 월별 택시 요금의 중간값은? — 기대 needs_clarification, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'unspecified', 'final': 'med'}); tools []
- `w22_p1` 택시 요금을 2026년 7월부터 8월까지 월별로 보면 중간값은? — 기대 needs_clarification, 실제 unsupported / wrong_refusal_kind / UNVERIFIED_TIMS_CONTRACT; 인자 차이 [['date', '20260701-20260831', None], ['aggregation', None, 'med'], ['condition:date', '20260701-20260831', None]]; 집계 {'bucket': 'month', 'inner': 'med', 'final': 'med'} (기대 {'bucket': 'month', 'inner': 'unspecified', 'final': 'med'}); tools []
- `w22_p2` 2026년 7월부터 8월까지 월 단위 택시 요금 중간값은 얼마인가요? — 기대 needs_clarification, 실제 failed / failed_instead_of_refusal / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'bucket': 'month', 'inner': 'unspecified', 'final': 'med'}); tools []
- `w28_p0` 지난달 법인택시의 평균 영업 시간은? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_SUBTYPE; 인자 차이 None; 집계 None (기대 None); tools []
- `w28_p1` 법인택시의 지난달 평균 영업 시간은? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_SUBTYPE; 인자 차이 None; 집계 None (기대 None); tools []
- `w28_p2` 지난달 평균 영업 시간을 법인택시 기준으로 알려줘 — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_SUBTYPE; 인자 차이 None; 집계 None (기대 None); tools []
- `w29_p0` 개인택시 영업 횟수가 가장 많은 시도 2곳은? — 기대 unsupported, 실제 answered / answered_instead_of_refusal / None; 인자 차이 []; 집계 {'final': 'sum'} (기대 None); tools ['get_billing_metrics']
- `w29_p1` 영업 횟수가 가장 많은 시도 2곳을 개인택시 기준으로 알려줘 — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_CONCEPT; 인자 차이 None; 집계 None (기대 None); tools []
- `w29_p2` 시도 중 개인택시 영업 횟수가 가장 많은 2곳은? — 기대 unsupported, 실제 answered / answered_instead_of_refusal / None; 인자 차이 []; 집계 None (기대 None); tools ['get_billing_metrics']
- `w31_p0` 2026년 7월부터 8월까지 주별 활성택시 대수 합계의 평균은? — 기대 unsupported, 실제 needs_clarification / wrong_refusal_kind / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 None); tools []
- `w31_p2` 2026년 7월부터 8월까지 활성택시 대수를 주별로 합한 값의 평균은? — 기대 unsupported, 실제 needs_clarification / wrong_refusal_kind / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 None); tools []
- `w32_p0` 지난달 주별 최고 가동률의 평균은? — 기대 unsupported, 실제 needs_clarification / wrong_refusal_kind / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 {'bucket': 'week', 'inner': 'max', 'final': 'avg'}); tools []
- `w32_p1` 주별 최고 가동률의 지난달 평균은? — 기대 unsupported, 실제 needs_clarification / wrong_refusal_kind / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 {'bucket': 'week', 'inner': 'max', 'final': 'avg'}); tools []
- `w33_p2` 대구 택시 수입을 요일별로 알려줘 — 기대 unsupported, 실제 answered / answered_instead_of_refusal / None; 인자 차이 []; 집계 None (기대 None); tools ['get_billing_metrics']
- `w34_p0` 시군구별 택시 수입 상위 3곳은? — 기대 unsupported, 실제 failed / failed_instead_of_refusal / INVALID_CONCEPT; 인자 차이 None; 집계 None (기대 None); tools []
- `w35_p2` 지난달 읍면동 중 승차가 가장 많은 3곳은? — 기대 answered, 실제 failed / execution_failure / NOT_FOUND; 인자 차이 [['date', 'last_month', '20260501-20260531'], ['scope_pickup', None, '@place:읍면동'], ['condition:date', 'last_month', '20260501-20260531']]; 집계 None (기대 None); tools ['get_place_scope']
- `w36_p0` 지난달 하차가 가장 적은 시군구 2곳은? — 기대 answered, 실제 failed / grounding_failure / INVALID_CONCEPT; 인자 차이 None; 집계 None (기대 None); tools []
- `w36_p1` 하차가 가장 적은 시군구 2곳을 지난달 기준으로 알려줘 — 기대 answered, 실제 failed / execution_failure / NOT_FOUND; 인자 차이 []; 집계 None (기대 None); tools ['get_place_scope']
- `w36_p2` 지난달 시군구 중 하차가 가장 적은 2곳은? — 기대 answered, 실제 failed / execution_failure / NOT_FOUND; 인자 차이 []; 집계 None (기대 None); tools ['get_place_scope']
- `w37_p0` 지난달 승하차 건수가 가장 많은 읍면동 간 노선 상위 3개는? — 기대 answered, 실제 failed / grounding_failure / VALUELESS_CONCEPT; 인자 차이 None; 집계 None (기대 None); tools []
- `w37_p1` 읍면동 간 노선 중 지난달 승하차 건수가 가장 많은 상위 3개는? — 기대 answered, 실제 failed / grounding_failure / VALUELESS_CONCEPT; 인자 차이 None; 집계 None (기대 None); tools []
- `w37_p2` 지난달 읍면동 간 승하차 노선 중 건수 상위 3개는? — 기대 answered, 실제 failed / execution_failure / NOT_FOUND; 인자 차이 [['date', 'last_month', None], ['condition:date', 'last_month', None]]; 집계 None (기대 None); tools ['get_place_scope', 'get_place_scope']
- `w39_p0` 이번 달 부산 택시의 평균 요금은? — 기대 answered, 실제 failed / grounding_failure / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 {'final': 'avg'}); tools []
- `w40_p2` 올해 공차율을 법인택시 기준으로 알려줘 — 기대 answered, 실제 failed / grounding_failure / INVALID_FACTOR; 인자 차이 None; 집계 None (기대 None); tools []
- `w41_p1` 택시 요금의 이번 달 주별 합계 중 최댓값은? — 기대 answered, 실제 answered / wrong_tool_args / None; 인자 차이 [['date', 'this_month', '20260501-20260531'], ['condition:date', 'this_month', '20260501-20260531']]; 집계 {'bucket': 'week', 'inner': 'sum', 'final': 'max'} (기대 {'bucket': 'week', 'inner': 'sum', 'final': 'max'}); tools ['get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'get_trip_metrics', 'local:COLLECT_GROUPS', 'local:REDUCE_GROUPS']
- `w41_p2` 이번 달 택시 요금을 주별로 합한 값의 최댓값은? — 기대 answered, 실제 needs_clarification / refused_supported / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 {'bucket': 'week', 'inner': 'sum', 'final': 'max'}); tools []
- `w42_p1` 동대구역 택시의 지난달 주별 최고 속도를 평균하면? — 기대 answered, 실제 needs_clarification / refused_supported / AMBIGUOUS_INNER_AGGREGATION; 인자 차이 None; 집계 None (기대 {'bucket': 'week', 'inner': 'max', 'final': 'avg'}); tools []
