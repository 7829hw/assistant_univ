# 결과 보고 (채점기 v2, `evaluate_vendor100.py report`)

## 새 독립셋 v4(사전 등록): v2 전체 보정 → 최종

- 전: `evaluation/grounding_v3/runs/v2full_indepv4_qwen3_8b.json` (코드 `3d72ec3084`)
- 후: `evaluation/grounding_v3/runs/final_indepv4_qwen3_8b.json` (코드 `cad3bb895a`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 24 | 24 |
| 오답 | 6 | 4 |
| 정당한 거부 | 1 | 0 |
| 부당한 거부 | 5 | 7 |
| 실행 실패 | 4 | 5 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 40 | 40 |

- 최종 grounding 정확(전, 조건 계층·정규화·재질의 뒤): 24/38 — 제외 k24, k40(정답 grounding 없음)
- 최종 grounding 정확(후, 조건 계층·정규화·재질의 뒤): 21/38 — 제외 k24, k40(정답 grounding 없음)

- 호출·지연(전): 계획 40, 재질의 3(재질의한 문항 3), 실패 호출 기록 1, timeout 추정 0; 문항 지연 중앙값 12.7초, p90 15.6초, 최대 315.9초, 합계 843.7초; 전체 경과 855.9초
- 호출·지연(후): 계획 40, 재질의 8(재질의한 문항 8), 실패 호출 기록 1, timeout 추정 0; 문항 지연 중앙값 12.7초, p90 18.2초, 최대 315.8초, 합계 866.1초; 전체 경과 878.5초

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 정상 답변 | k37 |
| 오답 → 부당한 거부 | k22, k35 |
| 오답 → 정상 답변 | k28 |
| 정당한 거부 → 오답 | k40 |
| 정상 답변 → 부당한 거부 | k36 |
| 정상 답변 → 실행 실패 | k08 |

- 새로 맞음 2: k28, k37
- 회귀(맞던 문항이 틀림) 3: k08, k36, k40

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| k01 | answered | 부당한 거부 | 부당한 거부 | DATE_AMBIGUOUS | False→False |
| k02 | answered | 실행 실패 | 실행 실패 | INVALID_FACTOR | False→False |
| k03 | answered | 정상 답변 | 정상 답변 |  | True→False |
| k04 | answered | 부당한 거부 | 부당한 거부 | DATE_AMBIGUOUS | False→False |
| k05 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k06 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k07 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k08 | answered | 정상 답변 | 실행 실패 | MISSING_RELATION_QUALIFIER | True→False |
| k09 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k10 | answered | 정상 답변 | 정상 답변 |  | True→False |
| k11 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k12 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k13 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k14 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k15 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k16 | answered | 부당한 거부 | 부당한 거부 | DATE_AMBIGUOUS | False→False |
| k17 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k18 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k19 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k20 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k21 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k22 | answered | 오답 | 부당한 거부 | UNCONSUMED_CONDITION | False→False |
| k23 | unsupported | 부당한 거부 | 부당한 거부 | AMBIGUOUS_INNER_AGGREGATION | False→False |
| k24 | unsupported | 실행 실패 | 실행 실패 | INVALID_PARAM_VALUE | None→None |
| k25 | answered | 오답 | 오답 | [["dimension_target", "pickup", "dropoff"]] | False→False |
| k26 | answered | 실행 실패 | 실행 실패 | UNSUPPORTED_COMBINATION | False→False |
| k27 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k28 | answered | 오답 | 정상 답변 |  | False→True |
| k29 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k30 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k31 | answered | 정상 답변 | 정상 답변 |  | True→False |
| k32 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k33 | answered | 실행 실패 | 실행 실패 | AMBIGUOUS_LOCATION_RELATION | False→False |
| k34 | answered | 오답 | 오답 | [["dimension_target", "dropoff", null]] | False→False |
| k35 | answered | 오답 | 부당한 거부 | UNSUPPORTED_AGGREGATION_COMBINATION | False→False |
| k36 | answered | 정상 답변 | 부당한 거부 | UNSUPPORTED_AGGREGATION_COMBINATION | True→False |
| k37 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| k38 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k39 | needs_clarification | 오답 | 오답 |  | False→False |
| k40 | unsupported | 정당한 거부 | 오답 |  | None→None |

## 업체 100(개발)

- 전: `evaluation/grounding_v2/runs/final_dev_qwen3_8b.json` (코드 `4f0c562417`)
- 후: `evaluation/grounding_v3/runs/final_dev_qwen3_8b.json` (코드 `cad3bb895a`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 99 | 93 |
| 오답 | 0 | 3 |
| 정당한 거부 | 0 | 0 |
| 부당한 거부 | 1 | 1 |
| 실행 실패 | 0 | 3 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 100 | 100 |

- 최종 grounding 정확(전, 조건 계층·정규화·재질의 뒤): 99/100
- 최종 grounding 정확(후, 조건 계층·정규화·재질의 뒤): 90/100

- 호출·지연(전): 계획 100, 재질의 0(재질의한 문항 0), 실패 호출 기록 2, timeout 추정 0; 문항 지연 중앙값 12.0초, p90 18.0초, 최대 316.2초, 합계 1881.6초; 전체 경과 1909.1초
- 호출·지연(후): 계획 100, 재질의 15(재질의한 문항 15), 실패 호출 기록 3, timeout 추정 0; 문항 지연 중앙값 13.2초, p90 21.1초, 최대 474.6초, 합계 2513.9초; 전체 경과 2544.7초

| 전→후 | 문항 |
|---|---|
| 정상 답변 → 실행 실패 | 006, 040, 066 |
| 정상 답변 → 오답 | 007, 064, 093 |

- 새로 맞음 0: -
- 회귀(맞던 문항이 틀림) 6: 006, 007, 040, 064, 066, 093

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| 001 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 002 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 003 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 004 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 005 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 006 | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR | True→False |
| 007 | answered | 정상 답변 | 오답 | [["dimension_target", "pickup", null]] | True→False |
| 008 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 009 | answered | 정상 답변 | 정상 답변 |  | True→False |
| 010 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 011 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 012 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 013 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 014 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 015 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 016 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 017 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 018 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 019 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 020 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 021 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 022 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 023 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 024 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 025 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 026 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 027 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 028 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 029 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 030 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 031 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 032 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 033 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 034 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 035 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 036 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 037 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 038 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 039 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 040 | answered | 정상 답변 | 실행 실패 | MISSING_RELATION_QUALIFIER | True→False |
| 041 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 042 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 043 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 044 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 045 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 046 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 047 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 048 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 049 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 050 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 051 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 052 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 053 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 054 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 055 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 056 | answered | 정상 답변 | 정상 답변 |  | True→False |
| 057 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 058 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 059 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 060 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 061 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 062 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 063 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 064 | answered | 정상 답변 | 오답 | [["metric", "rpm", "speed"]] | True→False |
| 065 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 066 | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR_COMBINATION | True→False |
| 067 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 068 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 069 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 070 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 071 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 072 | answered | 정상 답변 | 정상 답변 |  | True→False |
| 073 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 074 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 075 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 076 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 077 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 078 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 079 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 080 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 081 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 082 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 083 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 084 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 085 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 086 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 087 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 088 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 089 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 090 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 091 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 092 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 093 | answered | 정상 답변 | 오답 | [["scope_dropoff", "scope:district:2600000000", null]] | True→False |
| 094 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 095 | answered | 부당한 거부 | 부당한 거부 | PLACE_NOT_IN_QUESTION | False→False |
| 096 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 097 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 098 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 099 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 100 | answered | 정상 답변 | 정상 답변 |  | True→True |

## 기존 44(개발)

- 전: `evaluation/grounding_v2/runs/final_old44_qwen3_8b.json` (코드 `4f0c562417`)
- 후: `evaluation/grounding_v3/runs/final_old44_qwen3_8b.json` (코드 `cad3bb895a`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 41 | 35 |
| 오답 | 0 | 7 |
| 정당한 거부 | 3 | 1 |
| 부당한 거부 | 0 | 1 |
| 실행 실패 | 0 | 0 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 44 | 44 |

- 최종 grounding 정확(전, 조건 계층·정규화·재질의 뒤): 43/43 — 제외 g32(정답 grounding 없음)
- 최종 grounding 정확(후, 조건 계층·정규화·재질의 뒤): 35/43 — 제외 g32(정답 grounding 없음)

- 호출·지연(전): 계획 44, 재질의 0(재질의한 문항 0), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 11.9초, p90 17.1초, 최대 39.3초, 합계 583.9초; 전체 경과 596.3초
- 호출·지연(후): 계획 44, 재질의 7(재질의한 문항 7), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 12.4초, p90 18.7초, 최대 82.0초, 합계 699.8초; 전체 경과 712.9초

| 전→후 | 문항 |
|---|---|
| 정당한 거부 → 오답 | g32, g44 |
| 정상 답변 → 부당한 거부 | g04 |
| 정상 답변 → 오답 | g11, g14, g16, g33, g40 |

- 새로 맞음 0: -
- 회귀(맞던 문항이 틀림) 8: g04, g11, g14, g16, g32, g33, g40, g44

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| g01 | answered | 정상 답변 | 정상 답변 |  | True→False |
| g02 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g03 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g04 | answered | 정상 답변 | 부당한 거부 | NO_OPERATOR | True→False |
| g05 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g06 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g07 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g08 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g09 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g10 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g11 | answered | 정상 답변 | 오답 | [["scope_dropoff", "scope:district:2617010100", null], ["scope_pickup", null, "scope:district:2617010100"]] | True→False |
| g12 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g13 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g14 | answered | 정상 답변 | 오답 | [["scope_dropoff", "scope:district:2700000000", null]] | True→False |
| g15 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g16 | answered | 정상 답변 | 오답 | [["order", "bottom", "top"]] | True→False |
| g17 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→True |
| g18 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g19 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g20 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g21 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g22 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g23 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g24 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g25 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g26 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g27 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g28 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g29 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g30 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g31 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g32 | unsupported | 정당한 거부 | 오답 |  | None→None |
| g33 | answered | 정상 답변 | 오답 | [["aggregation", "sum", null]] | True→False |
| g34 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g35 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g36 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g37 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g38 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g39 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g40 | answered | 정상 답변 | 오답 | [["order", "bottom", "top"]] | True→False |
| g41 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g42 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g43 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g44 | needs_clarification | 정당한 거부 | 오답 |  | True→False |

## 대조 31(개발)

- 전: `evaluation/grounding_v2/runs/final_contrast_qwen3_8b.json` (코드 `4f0c562417`)
- 후: `evaluation/grounding_v3/runs/final_contrast_qwen3_8b.json` (코드 `cad3bb895a`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 29 | 26 |
| 오답 | 0 | 2 |
| 정당한 거부 | 2 | 0 |
| 부당한 거부 | 0 | 1 |
| 실행 실패 | 0 | 2 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 31 | 31 |

- 최종 grounding 정확(전, 조건 계층·정규화·재질의 뒤): 30/30 — 제외 c08c(정답 grounding 없음)
- 최종 grounding 정확(후, 조건 계층·정규화·재질의 뒤): 24/30 — 제외 c08c(정답 grounding 없음)

- 호출·지연(전): 계획 31, 재질의 0(재질의한 문항 0), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 12.3초, p90 20.8초, 최대 30.8초, 합계 447.0초; 전체 경과 455.9초
- 호출·지연(후): 계획 31, 재질의 5(재질의한 문항 5), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 13.1초, p90 22.8초, 최대 31.0초, 합계 483.3초; 전체 경과 492.4초

| 전→후 | 문항 |
|---|---|
| 정당한 거부 → 실행 실패 | c08c |
| 정당한 거부 → 오답 | c08b |
| 정상 답변 → 부당한 거부 | c07d |
| 정상 답변 → 실행 실패 | c06b |
| 정상 답변 → 오답 | c04c |

- 새로 맞음 0: -
- 회귀(맞던 문항이 틀림) 5: c04c, c06b, c07d, c08b, c08c

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| c01a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c01b | answered | 정상 답변 | 정상 답변 |  | True→False |
| c02a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c02b | answered | 정상 답변 | 정상 답변 |  | True→True |
| c02c | answered | 정상 답변 | 정상 답변 |  | True→True |
| c03a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c03b | answered | 정상 답변 | 정상 답변 |  | True→True |
| c03c | answered | 정상 답변 | 정상 답변 |  | True→True |
| c03d | answered | 정상 답변 | 정상 답변 |  | True→True |
| c04a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c04b | answered | 정상 답변 | 정상 답변 |  | True→True |
| c04c | answered | 정상 답변 | 오답 | [["scope_dropoff", "scope:district:2600000000", null]] | True→False |
| c05a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c05b | answered | 정상 답변 | 정상 답변 |  | True→True |
| c05c | answered | 정상 답변 | 정상 답변 |  | True→True |
| c06a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c06b | answered | 정상 답변 | 실행 실패 | UNKNOWN_ATTRIBUTE | True→False |
| c06c | answered | 정상 답변 | 정상 답변 |  | True→True |
| c07a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c07b | answered | 정상 답변 | 정상 답변 |  | True→True |
| c07c | answered | 정상 답변 | 정상 답변 |  | True→True |
| c07d | answered | 정상 답변 | 부당한 거부 | NO_OPERATOR | True→False |
| c08a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c08b | needs_clarification | 정당한 거부 | 오답 |  | True→False |
| c08c | unsupported | 정당한 거부 | 실행 실패 | INVALID_FACTOR_COMBINATION | None→None |
| c08d | answered | 정상 답변 | 정상 답변 |  | True→True |
| c08e | answered | 정상 답변 | 정상 답변 |  | True→True |
| c09a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c09b | answered | 정상 답변 | 정상 답변 |  | True→False |
| c10a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c10b | answered | 정상 답변 | 정상 답변 |  | True→True |

## 1차 독립 40(개발)

- 전: `evaluation/grounding_v2/runs/final_indepv2_qwen3_8b.json` (코드 `4f0c562417`)
- 후: `evaluation/grounding_v3/runs/final_indepv2_qwen3_8b.json` (코드 `cad3bb895a`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 28 | 20 |
| 오답 | 2 | 8 |
| 정당한 거부 | 5 | 3 |
| 부당한 거부 | 1 | 3 |
| 실행 실패 | 4 | 6 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 40 | 40 |

- 최종 grounding 정확(전, 조건 계층·정규화·재질의 뒤): 32/39 — 제외 n24(정답 grounding 없음)
- 최종 grounding 정확(후, 조건 계층·정규화·재질의 뒤): 24/39 — 제외 n24(정답 grounding 없음)

- 호출·지연(전): 계획 40, 재질의 4(재질의한 문항 4), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 12.5초, p90 22.7초, 최대 265.8초, 합계 853.0초; 전체 경과 864.5초
- 호출·지연(후): 계획 40, 재질의 12(재질의한 문항 12), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 14.5초, p90 26.4초, 최대 164.9초, 합계 818.7초; 전체 경과 830.2초

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 실행 실패 | n29 |
| 실행 실패 → 오답 | n05 |
| 정당한 거부 → 오답 | n23, n24 |
| 정상 답변 → 부당한 거부 | n03, n14, n21 |
| 정상 답변 → 실행 실패 | n09, n18 |
| 정상 답변 → 오답 | n06, n12, n15 |

- 새로 맞음 0: -
- 회귀(맞던 문항이 틀림) 10: n03, n06, n09, n12, n14, n15, n18, n21, n23, n24

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| n01 | answered | 실행 실패 | 실행 실패 | INVALID_PLACE | False→False |
| n02 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n03 | answered | 정상 답변 | 부당한 거부 | UNCONSUMED_CONDITION | True→False |
| n04 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n05 | answered | 실행 실패 | 오답 | [["dimension_target", "dropoff", null]] | False→False |
| n06 | answered | 정상 답변 | 오답 | [["dimension_target", "dropoff", null]] | True→False |
| n07 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n08 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n09 | answered | 정상 답변 | 실행 실패 | MISSING_RELATION_QUALIFIER | True→False |
| n10 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n11 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n12 | answered | 정상 답변 | 오답 | [["dimension", "sigungu", "emd"]] | False→False |
| n13 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n14 | answered | 정상 답변 | 부당한 거부 | UNSUPPORTED_AGGREGATION_COMBINATION | True→False |
| n15 | answered | 정상 답변 | 오답 | [["aggregation", "min", null]] | True→False |
| n16 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n17 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n18 | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR_COMBINATION | True→False |
| n19 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n20 | answered | 실행 실패 | 실행 실패 | UNGROUNDED_SCOPE | False→False |
| n21 | answered | 정상 답변 | 부당한 거부 | AMBIGUOUS_INNER_AGGREGATION | True→False |
| n22 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n23 | needs_clarification | 정당한 거부 | 오답 |  | True→False |
| n24 | unsupported | 정당한 거부 | 오답 |  | None→None |
| n25 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→True |
| n26 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→True |
| n27 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→True |
| n28 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n29 | answered | 부당한 거부 | 실행 실패 | MISSING_RELATION_QUALIFIER | False→False |
| n30 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n31 | answered | 오답 | 오답 | 장소 조회 횟수 불일치 | True→True |
| n32 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n33 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n34 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n35 | answered | 실행 실패 | 실행 실패 | MISSING_CONCEPT_VALUE | False→False |
| n36 | answered | 오답 | 오답 | [["scope", "<조회 안 됨 대구>", null]] 장소 조회 횟수 불일치 | False→False |
| n37 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n38 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n39 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n40 | answered | 정상 답변 | 정상 답변 |  | True→True |

## 2차 독립 40(개발)

- 전: `evaluation/grounding_v2/runs/final_indepv3_qwen3_8b.json` (코드 `4f0c562417`)
- 후: `evaluation/grounding_v3/runs/final_indepv3_qwen3_8b.json` (코드 `cad3bb895a`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 21 | 20 |
| 오답 | 9 | 9 |
| 정당한 거부 | 3 | 1 |
| 부당한 거부 | 1 | 2 |
| 실행 실패 | 6 | 8 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 40 | 40 |

- 최종 grounding 정확(전, 조건 계층·정규화·재질의 뒤): 24/38 — 제외 m25, m40(정답 grounding 없음)
- 최종 grounding 정확(후, 조건 계층·정규화·재질의 뒤): 20/38 — 제외 m25, m40(정답 grounding 없음)

- 호출·지연(전): 계획 40, 재질의 8(재질의한 문항 8), 실패 호출 기록 1, timeout 추정 0; 문항 지연 중앙값 12.2초, p90 18.8초, 최대 411.3초, 합계 935.6초; 전체 경과 947.3초
- 호출·지연(후): 계획 40, 재질의 13(재질의한 문항 13), 실패 호출 기록 1, timeout 추정 0; 문항 지연 중앙값 13.0초, p90 20.4초, 최대 409.6초, 합계 978.8초; 전체 경과 991.2초

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 실행 실패 | m17 |
| 오답 → 정상 답변 | m14, m22 |
| 정당한 거부 → 실행 실패 | m25 |
| 정당한 거부 → 오답 | m24 |
| 정상 답변 → 부당한 거부 | m15, m20 |
| 정상 답변 → 오답 | m03 |

- 새로 맞음 2: m14, m22
- 회귀(맞던 문항이 틀림) 5: m03, m15, m20, m24, m25

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| m01 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m02 | answered | 실행 실패 | 실행 실패 | MULTIPLE_MEASURES | False→False |
| m03 | answered | 정상 답변 | 오답 | [["dimension", "h3", "emd"]] | True→False |
| m04 | answered | 오답 | 오답 | [["order", "bottom", "top"]] | False→False |
| m05 | answered | 실행 실패 | 실행 실패 | INVALID_FACTOR | False→False |
| m06 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m07 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m08 | answered | 정상 답변 | 정상 답변 |  | True→False |
| m09 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m10 | answered | 오답 | 오답 | [["scope_dropoff", "<조회 안 됨 중구>", "scope:district:2723000000"]] 장소 조회 횟수 불일치 | False→False |
| m11 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m12 | answered | 실행 실패 | 실행 실패 | NOT_FOUND | False→False |
| m13 | answered | 실행 실패 | 실행 실패 | NO_MEASURE | False→False |
| m14 | answered | 오답 | 정상 답변 |  | False→False |
| m15 | answered | 정상 답변 | 부당한 거부 | UNSUPPORTED_AGGREGATION_COMBINATION | True→False |
| m16 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m17 | answered | 부당한 거부 | 실행 실패 | VALUELESS_CONCEPT | False→False |
| m18 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m19 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m20 | answered | 정상 답변 | 부당한 거부 | UNSUPPORTED_AGGREGATION_COMBINATION | True→False |
| m21 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m22 | answered | 오답 | 정상 답변 |  | False→True |
| m23 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m24 | needs_clarification | 정당한 거부 | 오답 |  | True→False |
| m25 | unsupported | 정당한 거부 | 실행 실패 | INVALID_FACTOR_COMBINATION | None→None |
| m26 | answered | 오답 | 오답 | [["taxi_status", "occupied", null], ["time", "100000-120000", "100000-130000"]] | False→False |
| m27 | answered | 오답 | 오답 | 장소 조회 횟수 불일치 | True→True |
| m28 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m29 | answered | 오답 | 오답 | [["scope", "<조회 안 됨 광안리>", "scope:gz:33212"]] | False→False |
| m30 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m31 | answered | 오답 | 오답 | [["scope", "<조회 안 됨 부산진구>", "scope:district:2623000000"]] | False→False |
| m32 | answered | 실행 실패 | 실행 실패 | UNGROUNDED_SCOPE | False→False |
| m33 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m34 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m35 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m36 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m37 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m38 | answered | 실행 실패 | 실행 실패 | VALUELESS_CONCEPT | False→False |
| m39 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→True |
| m40 | unsupported | 오답 | 오답 |  | None→None |

## 정답 grounding 실행기 v4

- 전: `evaluation/grounding_v3/runs/gold_v2full_indepv4.json` (코드 `3d72ec3084`)
- 후: `evaluation/grounding_v3/runs/gold_final_indepv4.json` (코드 `cad3bb895a`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 36 | 36 |
| 오답 | 0 | 0 |
| 정당한 거부 | 2 | 2 |
| 부당한 거부 | 0 | 0 |
| 실행 실패 | 0 | 0 |
| 미실행 | 2 | 2 |
| **합계(분모)** | 40 | 40 |



| 전→후 | 문항 |
|---|---|

- 새로 맞음 0: -
- 회귀(맞던 문항이 틀림) 0: -

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| k01 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k02 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k03 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k04 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k05 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k06 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k07 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k08 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k09 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k10 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k11 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k12 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k13 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k14 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k15 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k16 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k17 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k18 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k19 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k20 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k21 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k22 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k23 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | None→None |
| k24 | unsupported | 미실행 | 미실행 |  | None→None |
| k25 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k26 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k27 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k28 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k29 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k30 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k31 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k32 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k33 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k34 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k35 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k36 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k37 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k38 | answered | 정상 답변 | 정상 답변 |  | None→None |
| k39 | needs_clarification | 정당한 거부 | 정당한 거부 | AMBIGUOUS_INNER_AGGREGATION | None→None |
| k40 | unsupported | 미실행 | 미실행 |  | None→None |

