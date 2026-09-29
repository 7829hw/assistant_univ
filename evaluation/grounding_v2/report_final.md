# 결과 보고 (채점기 v2, `evaluate_vendor100.py report`)

## 업체 100문항(개발)

- 전: `evaluation/grounding_v1/runs/final2_dev_qwen3_8b.json` (코드 `1cb307df8e`)
- 후: `evaluation/grounding_v2/runs/final_dev_qwen3_8b.json` (코드 `4f0c562417`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 93 | 99 |
| 오답 | 2 | 0 |
| 정당한 거부 | 0 | 0 |
| 부당한 거부 | 2 | 1 |
| 실행 실패 | 3 | 0 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 100 | 100 |

- LLM grounding 정확(전): 90/100
- LLM grounding 정확(후): 99/100

- 호출·지연(전): 계획 100, 재질의 13(재질의한 문항 13), 실패 호출 기록 0, timeout 추정 4(041, 044, 067, 100); 문항 지연 중앙값 12.4초, p90 20.7초, 최대 325.6초, 합계 2616.7초; 전체 경과 기록 없음(평가기 v1)
- 호출·지연(후): 계획 100, 재질의 0(재질의한 문항 0), 실패 호출 기록 2, timeout 추정 0; 문항 지연 중앙값 12.0초, p90 18.0초, 최대 316.2초, 합계 1881.6초; 전체 경과 1909.1초

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 정상 답변 | 064 |
| 실행 실패 → 정상 답변 | 006, 078, 093 |
| 오답 → 정상 답변 | 041, 067 |

- 새로 맞음 6: 006, 041, 064, 067, 078, 093
- 회귀(맞던 문항이 틀림) 0: -

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| 001 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 002 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 003 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 004 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 005 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 006 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 007 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 008 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 009 | answered | 정상 답변 | 정상 답변 |  | False→True |
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
| 040 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 041 | answered | 오답 | 정상 답변 |  | False→True |
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
| 056 | answered | 정상 답변 | 정상 답변 |  | False→True |
| 057 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 058 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 059 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 060 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 061 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 062 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 063 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 064 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| 065 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 066 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 067 | answered | 오답 | 정상 답변 |  | False→True |
| 068 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 069 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 070 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 071 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 072 | answered | 정상 답변 | 정상 답변 |  | False→True |
| 073 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 074 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 075 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 076 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 077 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 078 | answered | 실행 실패 | 정상 답변 |  | False→True |
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
| 093 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 094 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 095 | answered | 부당한 거부 | 부당한 거부 | PLACE_NOT_IN_QUESTION | False→False |
| 096 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 097 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 098 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 099 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 100 | answered | 정상 답변 | 정상 답변 |  | True→True |

## 기존 44문항(개발)

- 전: `evaluation/grounding_v1/runs/final_holdout_qwen3_8b.json` (코드 `1cb307df8e`)
- 후: `evaluation/grounding_v2/runs/final_old44_qwen3_8b.json` (코드 `4f0c562417`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 35 | 41 |
| 오답 | 6 | 0 |
| 정당한 거부 | 1 | 3 |
| 부당한 거부 | 1 | 0 |
| 실행 실패 | 1 | 0 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 44 | 44 |

- LLM grounding 정확(전): 35/43 — 제외 g32(정답 grounding 없음)
- LLM grounding 정확(후): 43/43 — 제외 g32(정답 grounding 없음)

- 호출·지연(전): 계획 44, 재질의 6(재질의한 문항 6), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 11.9초, p90 18.3초, 최대 38.7초, 합계 605.3초; 전체 경과 기록 없음(평가기 v1)
- 호출·지연(후): 계획 44, 재질의 0(재질의한 문항 0), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 11.9초, p90 17.1초, 최대 39.3초, 합계 583.9초; 전체 경과 596.3초

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 정상 답변 | g04 |
| 실행 실패 → 정상 답변 | g14 |
| 오답 → 정당한 거부 | g32, g44 |
| 오답 → 정상 답변 | g11, g16, g33, g40 |

- 새로 맞음 8: g04, g11, g14, g16, g32, g33, g40, g44
- 회귀(맞던 문항이 틀림) 0: -

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| g01 | answered | 정상 답변 | 정상 답변 |  | False→True |
| g02 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g03 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g04 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| g05 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g06 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g07 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g08 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g09 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g10 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g11 | answered | 오답 | 정상 답변 |  | False→True |
| g12 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g13 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g14 | answered | 실행 실패 | 정상 답변 |  | False→True |
| g15 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g16 | answered | 오답 | 정상 답변 |  | False→True |
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
| g32 | unsupported | 오답 | 정당한 거부 | BUCKET_SELECTION_UNSUPPORTED | None→None |
| g33 | answered | 오답 | 정상 답변 |  | False→True |
| g34 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g35 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g36 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g37 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g38 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g39 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g40 | answered | 오답 | 정상 답변 |  | False→True |
| g41 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g42 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g43 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g44 | needs_clarification | 오답 | 정당한 거부 | AMBIGUOUS_INNER_AGGREGATION | False→True |

## 대조 사례(개발)

- 전: `evaluation/grounding_v2/runs/contrast_base_qwen3_8b.json` (코드 `2011580708`)
- 후: `evaluation/grounding_v2/runs/final_contrast_qwen3_8b.json` (코드 `4f0c562417`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 22 | 29 |
| 오답 | 2 | 0 |
| 정당한 거부 | 0 | 2 |
| 부당한 거부 | 1 | 0 |
| 실행 실패 | 6 | 0 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 31 | 31 |

- LLM grounding 정확(전): 21/30 — 제외 c08c(정답 grounding 없음)
- LLM grounding 정확(후): 30/30 — 제외 c08c(정답 grounding 없음)

- 호출·지연(전): 계획 31, 재질의 5(재질의한 문항 5), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 12.8초, p90 21.2초, 최대 28.4초, 합계 468.4초; 전체 경과 476.7초
- 호출·지연(후): 계획 31, 재질의 0(재질의한 문항 0), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 12.3초, p90 20.8초, 최대 30.8초, 합계 447.0초; 전체 경과 455.9초

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 정상 답변 | c07d |
| 실행 실패 → 정당한 거부 | c08c |
| 실행 실패 → 정상 답변 | c04c, c06a, c06b, c07a, c07b |
| 오답 → 정당한 거부 | c08b |
| 오답 → 정상 답변 | c04a |

- 새로 맞음 9: c04a, c04c, c06a, c06b, c07a, c07b, c07d, c08b, c08c
- 회귀(맞던 문항이 틀림) 0: -

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| c01a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c01b | answered | 정상 답변 | 정상 답변 |  | False→True |
| c02a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c02b | answered | 정상 답변 | 정상 답변 |  | True→True |
| c02c | answered | 정상 답변 | 정상 답변 |  | True→True |
| c03a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c03b | answered | 정상 답변 | 정상 답변 |  | True→True |
| c03c | answered | 정상 답변 | 정상 답변 |  | True→True |
| c03d | answered | 정상 답변 | 정상 답변 |  | True→True |
| c04a | answered | 오답 | 정상 답변 |  | True→True |
| c04b | answered | 정상 답변 | 정상 답변 |  | True→True |
| c04c | answered | 실행 실패 | 정상 답변 |  | False→True |
| c05a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c05b | answered | 정상 답변 | 정상 답변 |  | True→True |
| c05c | answered | 정상 답변 | 정상 답변 |  | True→True |
| c06a | answered | 실행 실패 | 정상 답변 |  | False→True |
| c06b | answered | 실행 실패 | 정상 답변 |  | False→True |
| c06c | answered | 정상 답변 | 정상 답변 |  | True→True |
| c07a | answered | 실행 실패 | 정상 답변 |  | False→True |
| c07b | answered | 실행 실패 | 정상 답변 |  | False→True |
| c07c | answered | 정상 답변 | 정상 답변 |  | True→True |
| c07d | answered | 부당한 거부 | 정상 답변 |  | False→True |
| c08a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c08b | needs_clarification | 오답 | 정당한 거부 | AMBIGUOUS_INNER_AGGREGATION | False→True |
| c08c | unsupported | 실행 실패 | 정당한 거부 | BUCKET_SELECTION_UNSUPPORTED | None→None |
| c08d | answered | 정상 답변 | 정상 답변 |  | True→True |
| c08e | answered | 정상 답변 | 정상 답변 |  | True→True |
| c09a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c09b | answered | 정상 답변 | 정상 답변 |  | False→True |
| c10a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c10b | answered | 정상 답변 | 정상 답변 |  | True→True |

## 1차 독립셋(열람 후 개발)

- 전: `evaluation/grounding_v2/runs/base_indep_qwen3_8b.json` (코드 `2011580708`)
- 후: `evaluation/grounding_v2/runs/final_indepv2_qwen3_8b.json` (코드 `4f0c562417`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 19 | 28 |
| 오답 | 9 | 2 |
| 정당한 거부 | 3 | 5 |
| 부당한 거부 | 4 | 1 |
| 실행 실패 | 5 | 4 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 40 | 40 |

- LLM grounding 정확(전): 23/39 — 제외 n24(정답 grounding 없음)
- LLM grounding 정확(후): 32/39 — 제외 n24(정답 grounding 없음)

- 호출·지연(전): 계획 40, 재질의 11(재질의한 문항 11), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 13.1초, p90 31.1초, 최대 113.2초, 합계 757.6초; 전체 경과 767.7초
- 호출·지연(후): 계획 40, 재질의 4(재질의한 문항 4), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 12.5초, p90 22.7초, 최대 265.8초, 합계 853.0초; 전체 경과 864.5초

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 정상 답변 | n03, n14, n21 |
| 실행 실패 → 정상 답변 | n09, n16 |
| 오답 → 실행 실패 | n05 |
| 오답 → 정당한 거부 | n23, n24 |
| 오답 → 정상 답변 | n10, n12, n15, n33 |

- 새로 맞음 11: n03, n09, n10, n12, n14, n15, n16, n21, n23, n24, n33
- 회귀(맞던 문항이 틀림) 0: -

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| n01 | answered | 실행 실패 | 실행 실패 | INVALID_PLACE | False→False |
| n02 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n03 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| n04 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n05 | answered | 오답 | 실행 실패 | MISSING_RELATION_QUALIFIER | False→False |
| n06 | answered | 정상 답변 | 정상 답변 |  | False→True |
| n07 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n08 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n09 | answered | 실행 실패 | 정상 답변 |  | False→True |
| n10 | answered | 오답 | 정상 답변 |  | True→True |
| n11 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n12 | answered | 오답 | 정상 답변 |  | False→False |
| n13 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n14 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| n15 | answered | 오답 | 정상 답변 |  | False→True |
| n16 | answered | 실행 실패 | 정상 답변 |  | False→True |
| n17 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n18 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n19 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n20 | answered | 실행 실패 | 실행 실패 | UNGROUNDED_SCOPE | False→False |
| n21 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| n22 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n23 | needs_clarification | 오답 | 정당한 거부 | AMBIGUOUS_INNER_AGGREGATION | False→True |
| n24 | unsupported | 오답 | 정당한 거부 | BUCKET_SELECTION_UNSUPPORTED | None→None |
| n25 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→True |
| n26 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→True |
| n27 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→True |
| n28 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n29 | answered | 부당한 거부 | 부당한 거부 | UNCONSUMED_CONDITION | False→False |
| n30 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n31 | answered | 오답 | 오답 | 장소 조회 횟수 불일치 | True→True |
| n32 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n33 | answered | 오답 | 정상 답변 |  | False→True |
| n34 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n35 | answered | 실행 실패 | 실행 실패 | MISSING_CONCEPT_VALUE | False→False |
| n36 | answered | 오답 | 오답 | [["scope", "<조회 안 됨 대구>", null]] 장소 조회 횟수 불일치 | False→False |
| n37 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n38 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n39 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n40 | answered | 정상 답변 | 정상 답변 |  | True→True |

## 2차 독립셋(사전 등록)

- 전: `evaluation/grounding_v2/runs/base_indepv3_qwen3_8b.json` (코드 `2011580708`)
- 후: `evaluation/grounding_v2/runs/final_indepv3_qwen3_8b.json` (코드 `4f0c562417`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 18 | 21 |
| 오답 | 11 | 9 |
| 정당한 거부 | 1 | 3 |
| 부당한 거부 | 1 | 1 |
| 실행 실패 | 9 | 6 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 40 | 40 |

- LLM grounding 정확(전): 18/38 — 제외 m25, m40(정답 grounding 없음)
- LLM grounding 정확(후): 24/38 — 제외 m25, m40(정답 grounding 없음)

- 호출·지연(전): 계획 40, 재질의 11(재질의한 문항 11), 실패 호출 기록 2, timeout 추정 0; 문항 지연 중앙값 12.4초, p90 23.3초, 최대 425.8초, 합계 1498.3초; 전체 경과 1509.7초
- 호출·지연(후): 계획 40, 재질의 8(재질의한 문항 8), 실패 호출 기록 1, timeout 추정 0; 문항 지연 중앙값 12.2초, p90 18.8초, 최대 411.3초, 합계 935.6초; 전체 경과 947.3초

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 정상 답변 | m20 |
| 실행 실패 → 부당한 거부 | m17 |
| 실행 실패 → 정당한 거부 | m25 |
| 실행 실패 → 정상 답변 | m15 |
| 오답 → 정당한 거부 | m24 |
| 오답 → 정상 답변 | m03, m18 |
| 정상 답변 → 오답 | m22 |

- 새로 맞음 6: m03, m15, m18, m20, m24, m25
- 회귀(맞던 문항이 틀림) 1: m22

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| m01 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m02 | answered | 실행 실패 | 실행 실패 | MULTIPLE_MEASURES | False→False |
| m03 | answered | 오답 | 정상 답변 |  | False→True |
| m04 | answered | 오답 | 오답 | [["order", "bottom", "top"]] | False→False |
| m05 | answered | 실행 실패 | 실행 실패 | NOT_FOUND | False→False |
| m06 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m07 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m08 | answered | 정상 답변 | 정상 답변 |  | False→True |
| m09 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m10 | answered | 오답 | 오답 | [["scope_dropoff", "<조회 안 됨 중구>", "scope:district:2723000000"]] 장소 조회 횟수 불일치 | False→False |
| m11 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m12 | answered | 실행 실패 | 실행 실패 | MISSING_RELATION_QUALIFIER | False→False |
| m13 | answered | 실행 실패 | 실행 실패 | NO_MEASURE | False→False |
| m14 | answered | 오답 | 오답 | [["limit", 3, 1]] | False→False |
| m15 | answered | 실행 실패 | 정상 답변 |  | False→True |
| m16 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m17 | answered | 실행 실패 | 부당한 거부 | RELATION_EXPRESSION_AMBIGUOUS | False→False |
| m18 | answered | 오답 | 정상 답변 |  | False→True |
| m19 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m20 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| m21 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m22 | answered | 정상 답변 | 오답 | [["rollup", "max", "min"]] | True→False |
| m23 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m24 | needs_clarification | 오답 | 정당한 거부 | AMBIGUOUS_INNER_AGGREGATION | False→True |
| m25 | unsupported | 실행 실패 | 정당한 거부 | BUCKET_SELECTION_UNSUPPORTED | None→None |
| m26 | answered | 오답 | 오답 | [["taxi_status", "occupied", null], ["time", "100000-120000", "100000-130000"]] | False→False |
| m27 | answered | 오답 | 오답 | 장소 조회 횟수 불일치 | False→True |
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

## 정답 grounding 업체 100

- 전: `evaluation/grounding_v2/runs/gold_base_dev.json` (코드 `2011580708`)
- 후: `evaluation/grounding_v2/runs/gold_cand_dev.json` (코드 `4f0c562417`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 98 | 100 |
| 오답 | 2 | 0 |
| 정당한 거부 | 0 | 0 |
| 부당한 거부 | 0 | 0 |
| 실행 실패 | 0 | 0 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 100 | 100 |



| 전→후 | 문항 |
|---|---|
| 오답 → 정상 답변 | 093, 095 |

- 새로 맞음 2: 093, 095
- 회귀(맞던 문항이 틀림) 0: -

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| 001 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 002 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 003 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 004 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 005 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 006 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 007 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 008 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 009 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 010 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 011 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 012 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 013 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 014 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 015 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 016 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 017 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 018 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 019 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 020 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 021 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 022 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 023 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 024 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 025 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 026 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 027 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 028 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 029 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 030 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 031 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 032 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 033 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 034 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 035 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 036 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 037 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 038 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 039 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 040 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 041 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 042 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 043 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 044 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 045 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 046 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 047 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 048 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 049 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 050 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 051 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 052 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 053 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 054 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 055 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 056 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 057 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 058 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 059 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 060 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 061 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 062 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 063 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 064 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 065 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 066 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 067 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 068 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 069 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 070 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 071 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 072 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 073 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 074 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 075 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 076 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 077 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 078 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 079 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 080 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 081 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 082 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 083 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 084 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 085 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 086 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 087 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 088 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 089 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 090 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 091 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 092 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 093 | answered | 오답 | 정상 답변 |  | None→None |
| 094 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 095 | answered | 오답 | 정상 답변 |  | None→None |
| 096 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 097 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 098 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 099 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 100 | answered | 정상 답변 | 정상 답변 |  | None→None |

## 정답 grounding 기존 44

- 전: `evaluation/grounding_v2/runs/gold_base_old44.json` (코드 `2011580708`)
- 후: `evaluation/grounding_v2/runs/gold_cand_old44.json` (코드 `4f0c562417`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 40 | 41 |
| 오답 | 1 | 0 |
| 정당한 거부 | 2 | 2 |
| 부당한 거부 | 0 | 0 |
| 실행 실패 | 0 | 0 |
| 미실행 | 1 | 1 |
| **합계(분모)** | 44 | 44 |



| 전→후 | 문항 |
|---|---|
| 오답 → 정상 답변 | g14 |

- 새로 맞음 1: g14
- 회귀(맞던 문항이 틀림) 0: -

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| g01 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g02 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g03 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g04 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g05 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g06 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g07 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g08 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g09 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g10 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g11 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g12 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g13 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g14 | answered | 오답 | 정상 답변 |  | None→None |
| g15 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g16 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g17 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | None→None |
| g18 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g19 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g20 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g21 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g22 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g23 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g24 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g25 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g26 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g27 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g28 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g29 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g30 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g31 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g32 | unsupported | 미실행 | 미실행 |  | None→None |
| g33 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g34 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g35 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g36 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g37 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g38 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g39 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g40 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g41 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g42 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g43 | answered | 정상 답변 | 정상 답변 |  | None→None |
| g44 | needs_clarification | 정당한 거부 | 정당한 거부 | AMBIGUOUS_INNER_AGGREGATION | None→None |

## 정답 grounding 대조

- 전: `evaluation/grounding_v2/runs/gold_base_contrast.json` (코드 `2011580708`)
- 후: `evaluation/grounding_v2/runs/gold_cand_contrast.json` (코드 `4f0c562417`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 27 | 29 |
| 오답 | 2 | 0 |
| 정당한 거부 | 1 | 1 |
| 부당한 거부 | 0 | 0 |
| 실행 실패 | 0 | 0 |
| 미실행 | 1 | 1 |
| **합계(분모)** | 31 | 31 |



| 전→후 | 문항 |
|---|---|
| 오답 → 정상 답변 | c04a, c04c |

- 새로 맞음 2: c04a, c04c
- 회귀(맞던 문항이 틀림) 0: -

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| c01a | answered | 정상 답변 | 정상 답변 |  | None→None |
| c01b | answered | 정상 답변 | 정상 답변 |  | None→None |
| c02a | answered | 정상 답변 | 정상 답변 |  | None→None |
| c02b | answered | 정상 답변 | 정상 답변 |  | None→None |
| c02c | answered | 정상 답변 | 정상 답변 |  | None→None |
| c03a | answered | 정상 답변 | 정상 답변 |  | None→None |
| c03b | answered | 정상 답변 | 정상 답변 |  | None→None |
| c03c | answered | 정상 답변 | 정상 답변 |  | None→None |
| c03d | answered | 정상 답변 | 정상 답변 |  | None→None |
| c04a | answered | 오답 | 정상 답변 |  | None→None |
| c04b | answered | 정상 답변 | 정상 답변 |  | None→None |
| c04c | answered | 오답 | 정상 답변 |  | None→None |
| c05a | answered | 정상 답변 | 정상 답변 |  | None→None |
| c05b | answered | 정상 답변 | 정상 답변 |  | None→None |
| c05c | answered | 정상 답변 | 정상 답변 |  | None→None |
| c06a | answered | 정상 답변 | 정상 답변 |  | None→None |
| c06b | answered | 정상 답변 | 정상 답변 |  | None→None |
| c06c | answered | 정상 답변 | 정상 답변 |  | None→None |
| c07a | answered | 정상 답변 | 정상 답변 |  | None→None |
| c07b | answered | 정상 답변 | 정상 답변 |  | None→None |
| c07c | answered | 정상 답변 | 정상 답변 |  | None→None |
| c07d | answered | 정상 답변 | 정상 답변 |  | None→None |
| c08a | answered | 정상 답변 | 정상 답변 |  | None→None |
| c08b | needs_clarification | 정당한 거부 | 정당한 거부 | AMBIGUOUS_INNER_AGGREGATION | None→None |
| c08c | unsupported | 미실행 | 미실행 |  | None→None |
| c08d | answered | 정상 답변 | 정상 답변 |  | None→None |
| c08e | answered | 정상 답변 | 정상 답변 |  | None→None |
| c09a | answered | 정상 답변 | 정상 답변 |  | None→None |
| c09b | answered | 정상 답변 | 정상 답변 |  | None→None |
| c10a | answered | 정상 답변 | 정상 답변 |  | None→None |
| c10b | answered | 정상 답변 | 정상 답변 |  | None→None |

## 정답 grounding 1차 독립셋

- 전: `evaluation/grounding_v2/runs/gold_base_indep.json` (코드 `2011580708`)
- 후: `evaluation/grounding_v2/runs/gold_cand_indep.json` (코드 `4f0c562417`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 33 | 35 |
| 오답 | 2 | 0 |
| 정당한 거부 | 4 | 4 |
| 부당한 거부 | 0 | 0 |
| 실행 실패 | 0 | 0 |
| 미실행 | 1 | 1 |
| **합계(분모)** | 40 | 40 |



| 전→후 | 문항 |
|---|---|
| 오답 → 정상 답변 | n09, n10 |

- 새로 맞음 2: n09, n10
- 회귀(맞던 문항이 틀림) 0: -

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| n01 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n02 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n03 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n04 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n05 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n06 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n07 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n08 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n09 | answered | 오답 | 정상 답변 |  | None→None |
| n10 | answered | 오답 | 정상 답변 |  | None→None |
| n11 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n12 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n13 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n14 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n15 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n16 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n17 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n18 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n19 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n20 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n21 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n22 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n23 | needs_clarification | 정당한 거부 | 정당한 거부 | AMBIGUOUS_INNER_AGGREGATION | None→None |
| n24 | unsupported | 미실행 | 미실행 |  | None→None |
| n25 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | None→None |
| n26 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | None→None |
| n27 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | None→None |
| n28 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n29 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n30 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n31 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n32 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n33 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n34 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n35 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n36 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n37 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n38 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n39 | answered | 정상 답변 | 정상 답변 |  | None→None |
| n40 | answered | 정상 답변 | 정상 답변 |  | None→None |

## 정답 grounding 2차 독립셋

- 전: `evaluation/grounding_v2/runs/gold_base_indepv3.json` (코드 `2011580708`)
- 후: `evaluation/grounding_v2/runs/gold_cand_indepv3.json` (코드 `4f0c562417`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 33 | 36 |
| 오답 | 3 | 0 |
| 정당한 거부 | 2 | 2 |
| 부당한 거부 | 0 | 0 |
| 실행 실패 | 0 | 0 |
| 미실행 | 2 | 2 |
| **합계(분모)** | 40 | 40 |



| 전→후 | 문항 |
|---|---|
| 오답 → 정상 답변 | m12, m13, m14 |

- 새로 맞음 3: m12, m13, m14
- 회귀(맞던 문항이 틀림) 0: -

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| m01 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m02 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m03 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m04 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m05 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m06 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m07 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m08 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m09 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m10 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m11 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m12 | answered | 오답 | 정상 답변 |  | None→None |
| m13 | answered | 오답 | 정상 답변 |  | None→None |
| m14 | answered | 오답 | 정상 답변 |  | None→None |
| m15 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m16 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m17 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m18 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m19 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m20 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m21 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m22 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m23 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m24 | needs_clarification | 정당한 거부 | 정당한 거부 | AMBIGUOUS_INNER_AGGREGATION | None→None |
| m25 | unsupported | 미실행 | 미실행 |  | None→None |
| m26 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m27 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m28 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m29 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m30 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m31 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m32 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m33 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m34 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m35 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m36 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m37 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m38 | answered | 정상 답변 | 정상 답변 |  | None→None |
| m39 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | None→None |
| m40 | unsupported | 미실행 | 미실행 |  | None→None |

