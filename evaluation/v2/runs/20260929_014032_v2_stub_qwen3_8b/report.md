# v2 평가 보고서: 20260929_014032_v2_stub_qwen3_8b

잠정치: 평가셋은 사람이 검토하지 않았다(registry review.status unreviewed). mock 고정값으로 실행했으므로 수치의 정확성이 아니라 요청 인자·집계 의미·결과 종류를 채점했다.

- 커밋 14cb4b9e2dc1a238591e5dbf72f844897bada2d2 (dirty []), 명령 `evaluate_v2.py run --model qwen3:8b --sets stub --label v2_stub_qwen3_8b`
- 모델 qwen3:8b digest 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 {'family': 'qwen3', 'parameter_size': '8.2B', 'quantization_level': 'Q4_K_M', 'format': 'gguf'}, Ollama 0.34.4
- 설정 {"agent_mode": "geoflow", "aggregation_grounding": "flat", "condition_check": false, "provider": "mock", "tims_execution": "legacy", "example_retrieval": "off", "ollama_options": {"temperature": 0}, "think": "auto"}, chat timeout 300.0
- 기준일 2026-09-25 (Asia/Seoul), 시작 2026-09-29T01:40:32.447466+09:00
- planner prompt sha256 db113124b2e26aa9b47b7f6d9e56387becd19e6add2debaab54657598c171ba8
- 입력 sha256 {"stub_query.yaml": "71ede4275aae87bdccda8f348e77b61e3ed3a34989667db14de903119d143e02", "evaluation/v2/stub_v2_gold.yaml": "1cde411c0a52ea78dccf4faa6558ee4e68ed52469f7b805164102aff91ab46d0", "mock_stub.yaml": "180550f4e4b7810a2476bec9f4192c035c21e4e32369766b0802208db5a12889"}

## 전체 (문장 단위)

| 지표 | 값 |
| --- | --- |
| 의미 정답(전체) | 3/5 (60.0%) |
| 실행 완료(answered 기대 문장 중 답함) | 4/5 (80.0%) |
| 의미 정답(answered 기대 문장) | 3/5 (60.0%) |
| 거부 정확도 strict(기대 종류로 멈춤) | - |
| 보조: 거부 기대 문장에서 답하지 않음 | - |

intent 단위(5개): 모든 문장 정답 3/5 (60.0%), 과반 문장 정답 3/5 (60.0%).

## 기대 결과별

| 기대 결과 | 문장 정답 | intent(모든 문장) 정답 | intent(과반) 정답 |
| --- | --- | --- | --- |
| answered | 3/5 (60.0%) | 3/5 (60.0%) | 3/5 (60.0%) |
| needs_clarification | - | - | - |
| unsupported | - | - | - |

## 기대 결과 × 실제 결과 (문장)

| 기대 \ 실제 | answered | needs_clarification | unsupported | failed |
| --- | --- | --- | --- | --- |
| answered | 4 | 0 | 0 | 1 |
| needs_clarification | 0 | 0 | 0 | 0 |
| unsupported | 0 | 0 | 0 | 0 |

## 절별

| 절 | 문장 정답 | 실행 완료 | 거부 strict | intent(모든 문장) |
| --- | --- | --- | --- | --- |

stage-swap 대상 두 단계 answered intent 0개: 문장 정답 -, intent(모든 문장) -.

## 범주

| 범주 | 문장 |
| --- | --- |
| correct | 3 |
| grounding_failure | 1 |
| wrong_tool_args | 1 |

unsupported 기대 문장에서 답하지 않은 경우의 결과·코드: {}

## intent별

| intent | 기대 | p0 | p1 | p2 |
| --- | --- | --- | --- | --- |
| q01_edge_average_speed | answered | correct |
| q12_vacant_drive_ratio | answered | correct |
| q16_1_private_revenue_by_day | answered | grounding_failure (INVALID_SUBTYPE) |
| q18_daegu_origin_destination_count | answered | wrong_tool_args |
| q20_daegu_average_fare | answered | correct |

## 실패 목록

- `q16_1_private_revenue_by_day` 개인용 택시의 요일별 택시 수입 분포는? — 기대 answered, 실제 failed / grounding_failure / INVALID_SUBTYPE; 인자 차이 None; 집계 None (기대 None); tools []
- `q18_daegu_origin_destination_count` 대구 동성로동에서 출발하여 신천동에 도착한 실차 구간 건수는? — 기대 answered, 실제 answered / wrong_tool_args / None; 인자 차이 [['scope_pickup', 'scope:district:2711012300', 'scope:edge:1742']]; 집계 None (기대 None); tools ['get_place_scope', 'get_place_scope', 'get_place_scope', 'get_trip_count']
