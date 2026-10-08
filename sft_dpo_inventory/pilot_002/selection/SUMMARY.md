# pilot_002 checkpoint 기록(selection_v1)

`summarize.py`가 만든다. 선택 규칙: selection_v1 grounding_ok 최고, 동점이면 이른 step(PLAN 3절).

base HF-E: grounding_ok 82/100, 생성 상한 0, 루프 호출 0, 문항 초 중앙 22.35(`sft_dpo_inventory/pilot_prep_005/sets/runs/selection_base.json`).

## SFT

- 758 step, 4676초, step당 6.1초, GPU `2 GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21`.
- 메모리: torch max allocated 38.3 GiB / reserved 42.3 GiB(단계 전체), nvidia-smi peak 43882 MiB.
- 선택: step 380(grounding_ok 75).

| step | loss(그 step / 구간 평균) | step당 초 | nvidia-smi peak MiB(그 step까지) | grounding_ok | 첫 응답 일치 | 정상 종료 answered | 생성 상한 호출 | 루프 호출(문항) | 문항 초 중앙 | 평가 GPU |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 190 | 0.0015 / 0.01546 | 6.11 | 43878 | **74** | 48 | 78 | 4 | 4(2) | 30.0 | `GPU-a644de12…` |
| 380 | 0.0033 / 0.00849 | 6.08 | 43880 | **75** | 58 | 81 | 2 | 2(1) | 28.05 | `GPU-a644de12…` |
| 570 | 0.0111 / 0.00582 | 6.1 | 43882 | **75** | 58 | 84 | 0 | 0(0) | 26.7 | `GPU-a644de12…` |
| 758 | 0.0034 / 0.00465 | 6.12 | 43882 | **73** | 55 | 78 | 4 | 4(2) | 27.8 | `GPU-a644de12…` |

결과 분류(outcome:error_code):

- step 190: answered:None 78, unsupported:UNCONSUMED_CONDITION 6, failed:INVALID_FACTOR_COMBINATION 4, failed:MISSING_RELATION_QUALIFIER 3, unsupported:NO_OPERATOR 3, failed:VALUELESS_CONCEPT 2, needs_clarification:AMBIGUOUS_AGGREGATION_STAGE 1, failed:OUTPUT_TRUNCATED 1, needs_clarification:AMBIGUOUS_INNER_AGGREGATION 1, failed:UNSUPPORTED_COMBINATION 1
- step 380: answered:None 81, unsupported:UNCONSUMED_CONDITION 6, failed:MISSING_RELATION_QUALIFIER 3, unsupported:NO_OPERATOR 3, failed:OUTPUT_TRUNCATED 1, failed:INVALID_CONCEPT 1, failed:MISSING_CONCEPT_VALUE 1, failed:UNKNOWN_ATTRIBUTE 1, needs_clarification:AMBIGUOUS_INNER_AGGREGATION 1, failed:VALUELESS_CONCEPT 1, failed:INVALID_FACTOR_COMBINATION 1
- step 570: answered:None 84, unsupported:UNCONSUMED_CONDITION 5, unsupported:NO_OPERATOR 2, failed:INVALID_FACTOR_COMBINATION 2, failed:NO_MEASURE 1, needs_clarification:AMBIGUOUS_AGGREGATION_STAGE 1, failed:INVALID_CONCEPT 1, failed:MISSING_RELATION_QUALIFIER 1, needs_clarification:AMBIGUOUS_INNER_AGGREGATION 1, failed:UNSUPPORTED_COMBINATION 1, failed:INVALID_FACTOR 1
- step 758: answered:None 78, unsupported:UNCONSUMED_CONDITION 7, failed:MISSING_RELATION_QUALIFIER 3, failed:OUTPUT_TRUNCATED 2, unsupported:NO_OPERATOR 2, needs_clarification:AMBIGUOUS_INNER_AGGREGATION 1, failed:INVALID_FACTOR 1, failed:VALUELESS_CONCEPT 1, failed:INVALID_CONCEPT 1, failed:NOT_FOUND 1, failed:UNKNOWN_FACTOR 1, failed:AMBIGUOUS_LOCATION_RELATION 1, failed:INVALID_FACTOR_COMBINATION 1

## DPO

- 288 step, 6829초, step당 18.64초, GPU `2 GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21`.
- 메모리: torch max allocated 42.6 GiB / reserved 43.6 GiB(단계 전체), nvidia-smi peak 45130 MiB.
- 선택: step 144(grounding_ok 80).

| step | loss(그 step / 구간 평균) | step당 초 | nvidia-smi peak MiB(그 step까지) | grounding_ok | 첫 응답 일치 | 정상 종료 answered | 생성 상한 호출 | 루프 호출(문항) | 문항 초 중앙 | 평가 GPU |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 72 | 0.3052 / 0.61363 | 18.69 | 33382 | **72** | 56 | 84 | 4 | 4(2) | 28.0 | `GPU-a644de12…` |
| 144 | 1.1323 / 0.53934 | 18.87 | 45130 | **80** | 59 | 86 | 4 | 4(2) | 25.5 | `GPU-48f798cc…` |
| 216 | 0.33 / 0.32022 | 18.65 | 45130 | **78** | 57 | 84 | 2 | 2(1) | 27.1 | `GPU-a644de12…` |
| 288 | 0.0001 / 0.33292 | 18.36 | 45130 | **78** | 57 | 81 | 10 | 10(5) | 27.45 | `GPU-48f798cc…` |

결과 분류(outcome:error_code):

- step 72: answered:None 84, unsupported:UNCONSUMED_CONDITION 5, unsupported:NO_OPERATOR 3, failed:OUTPUT_TRUNCATED 2, failed:MISSING_RELATION_QUALIFIER 2, needs_clarification:AMBIGUOUS_INNER_AGGREGATION 1, failed:NOT_FOUND 1, failed:UNKNOWN_ATTRIBUTE 1, failed:INVALID_FACTOR_COMBINATION 1
- step 144: answered:None 86, unsupported:UNCONSUMED_CONDITION 6, failed:OUTPUT_TRUNCATED 2, failed:NOT_FOUND 2, failed:MISSING_RELATION_QUALIFIER 1, needs_clarification:AMBIGUOUS_AGGREGATION_STAGE 1, failed:INVALID_FACTOR_COMBINATION 1, unsupported:NO_OPERATOR 1
- step 216: answered:None 84, unsupported:UNCONSUMED_CONDITION 5, unsupported:NO_OPERATOR 4, failed:INVALID_FACTOR_COMBINATION 2, failed:UNUSED_CONCEPT 1, needs_clarification:AMBIGUOUS_AGGREGATION_STAGE 1, needs_clarification:AMBIGUOUS_INNER_AGGREGATION 1, failed:NOT_FOUND 1, failed:INVALID_PARAM_VALUE 1
- step 288: answered:None 81, unsupported:UNCONSUMED_CONDITION 4, failed:OUTPUT_TRUNCATED 3, failed:INVALID_FACTOR_COMBINATION 2, unsupported:NO_OPERATOR 2, needs_clarification:AMBIGUOUS_AGGREGATION_STAGE 1, failed:MISSING_CONCEPT_VALUE 1, failed:UNUSED_CONCEPT 1, unsupported:PARAM_VALUE_REQUIRES_INPUT 1, failed:NOT_FOUND 1, failed:INVALID_CONCEPT 1, failed:UNSUPPORTED_COMBINATION 1, failed:VALUELESS_CONCEPT 1

DPO 구간 평균: step 72 reward acc 0.625 margin 0.344; step 144 reward acc 0.75 margin 0.719; step 216 reward acc 0.917 margin 1.467; step 288 reward acc 0.875 margin 1.731
