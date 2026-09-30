# 결과 보고 (채점기 v3, `evaluate_vendor100.py report`)

## 답 대상 대조 16(개발)

- 전: `evaluation/grounding_v4/runs/at_base.json` (코드 `3e57935b54`)
- 후: `evaluation/grounding_v4/runs/final_at_qwen3_8b.json` (코드 `a8664a2e24`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 9 | 8 |
| 오답 | 5 | 3 |
| 정당한 거부 | 1 | 2 |
| 부당한 거부 | 0 | 1 |
| 실행 실패 | 1 | 2 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 16 | 16 |

- 최종 grounding 정확(전, 조건 계층·정규화·재질의 뒤): 10/16
- 최종 grounding 정확(후, 조건 계층·정규화·재질의 뒤): 11/16

- 호출·지연(전): 계획 16, 재질의 4(재질의한 문항 4), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 14.5초, p90 21.6초, 최대 248.9초, 합계 473.0초; 전체 경과 477.5초
- 호출·지연(후): 계획 16, 재질의 2(재질의한 문항 2), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 12.7초, p90 17.9초, 최대 20.9초, 합계 215.1초; 전체 경과 219.6초

| 전→후 | 문항 |
|---|---|
| 실행 실패 → 부당한 거부 | t01b |
| 오답 → 정당한 거부 | t02b, t03b |
| 오답 → 정상 답변 | t04c |
| 정당한 거부 → 오답 | t02c |
| 정상 답변 → 실행 실패 | t04a, t04b |

- 새로 맞음 3: t02b, t03b, t04c
- 회귀(맞던 문항이 틀림) 3: t02c, t04a, t04b

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| t01a | answered | 정상 답변 | 정상 답변 |  | True→True |
| t01b | unsupported | 실행 실패 | 부당한 거부 | AMBIGUOUS_INNER_AGGREGATION | False→False |
| t01c | needs_clarification | 오답 | 오답 |  | False→False |
| t02a | answered | 정상 답변 | 정상 답변 |  | True→True |
| t02b | unsupported | 오답 | 정당한 거부 | UNVERIFIED_TIMS_CONTRACT | False→True |
| t02c | needs_clarification | 정당한 거부 | 오답 |  | True→False |
| t03a | answered | 정상 답변 | 정상 답변 |  | True→True |
| t03b | unsupported | 오답 | 정당한 거부 | UNVERIFIED_TIMS_CONTRACT | False→True |
| t04a | answered | 정상 답변 | 실행 실패 | VALUELESS_CONCEPT | True→False |
| t04b | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR_COMBINATION | True→True |
| t04c | answered | 오답 | 정상 답변 |  | False→True |
| t04d | answered | 정상 답변 | 정상 답변 |  | True→True |
| t05a | answered | 정상 답변 | 정상 답변 |  | True→True |
| t05b | needs_clarification | 오답 | 오답 |  | False→False |
| t05c | answered | 정상 답변 | 정상 답변 |  | True→True |
| t05d | answered | 정상 답변 | 정상 답변 |  | True→True |

## 업체 100(개발)

- 전: `evaluation/grounding_v3/runs/final_dev_qwen3_8b.json` (코드 `cad3bb895a`)
- 후: `evaluation/grounding_v4/runs/final_dev_qwen3_8b.json` (코드 `a8664a2e24`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 93 | 85 |
| 오답 | 3 | 3 |
| 정당한 거부 | 0 | 0 |
| 부당한 거부 | 1 | 2 |
| 실행 실패 | 3 | 10 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 100 | 100 |

- 최종 grounding 정확(전, 조건 계층·정규화·재질의 뒤): 90/100
- 최종 grounding 정확(후, 조건 계층·정규화·재질의 뒤): 82/100

- 호출·지연(전): 계획 100, 재질의 15(재질의한 문항 15), 실패 호출 기록 3, timeout 추정 0; 문항 지연 중앙값 13.2초, p90 21.1초, 최대 474.6초, 합계 2513.9초; 전체 경과 2544.7초
- 호출·지연(후): 계획 100, 재질의 20(재질의한 문항 20), 실패 호출 기록 2, timeout 추정 0; 문항 지연 중앙값 12.8초, p90 25.6초, 최대 523.0초, 합계 2339.6초; 전체 경과 2368.9초

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 실행 실패 | 095 |
| 실행 실패 → 정상 답변 | 006, 040, 066 |
| 오답 → 실행 실패 | 007 |
| 오답 → 정상 답변 | 064, 093 |
| 정상 답변 → 부당한 거부 | 005, 037 |
| 정상 답변 → 실행 실패 | 013, 015, 016, 030, 065, 070, 072, 078 |
| 정상 답변 → 오답 | 021, 044, 046 |

- 새로 맞음 5: 006, 040, 064, 066, 093
- 회귀(맞던 문항이 틀림) 13: 005, 013, 015, 016, 021, 030, 037, 044, 046, 065, 070, 072, 078

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| 001 | answered | 정상 답변 | 정상 답변 |  | True→False |
| 002 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 003 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 004 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 005 | answered | 정상 답변 | 부당한 거부 | UNCONSUMED_CONDITION | True→False |
| 006 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 007 | answered | 오답 | 실행 실패 | INVALID_FACTOR_COMBINATION | False→False |
| 008 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 009 | answered | 정상 답변 | 정상 답변 |  | False→True |
| 010 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 011 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 012 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 013 | answered | 정상 답변 | 실행 실패 | MISSING_RELATION_QUALIFIER | True→False |
| 014 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 015 | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR | True→False |
| 016 | answered | 정상 답변 | 실행 실패 | VALUELESS_CONCEPT | True→False |
| 017 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 018 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 019 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 020 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 021 | answered | 정상 답변 | 오답 | [["aggregation", "min", null]] | True→False |
| 022 | answered | 정상 답변 | 정상 답변 |  | True→False |
| 023 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 024 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 025 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 026 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 027 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 028 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 029 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 030 | answered | 정상 답변 | 실행 실패 | UNKNOWN_ATTRIBUTE | True→False |
| 031 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 032 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 033 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 034 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 035 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 036 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 037 | answered | 정상 답변 | 부당한 거부 | UNCONSUMED_CONDITION | True→False |
| 038 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 039 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 040 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 041 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 042 | answered | 정상 답변 | 정상 답변 |  | True→False |
| 043 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 044 | answered | 정상 답변 | 오답 | [["dimension", "emd", "sigungu"]] | True→False |
| 045 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 046 | answered | 정상 답변 | 오답 | [["dimension", "emd", "sigungu"]] | True→False |
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
| 064 | answered | 오답 | 정상 답변 |  | False→True |
| 065 | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR_COMBINATION | True→True |
| 066 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 067 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 068 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 069 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 070 | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR_COMBINATION | True→False |
| 071 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 072 | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR | False→False |
| 073 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 074 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 075 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 076 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 077 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 078 | answered | 정상 답변 | 실행 실패 | VALUELESS_CONCEPT | True→False |
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
| 093 | answered | 오답 | 정상 답변 |  | False→False |
| 094 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 095 | answered | 부당한 거부 | 실행 실패 | MISSING_RELATION_QUALIFIER | False→False |
| 096 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 097 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 098 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 099 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 100 | answered | 정상 답변 | 정상 답변 |  | True→True |

## 기존 44(개발)

- 전: `evaluation/grounding_v3/runs/final_old44_qwen3_8b.json` (코드 `cad3bb895a`)
- 후: `evaluation/grounding_v4/runs/final_old44_qwen3_8b.json` (코드 `a8664a2e24`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 35 | 26 |
| 오답 | 7 | 7 |
| 정당한 거부 | 1 | 2 |
| 부당한 거부 | 1 | 3 |
| 실행 실패 | 0 | 6 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 44 | 44 |

- 최종 grounding 정확(전, 조건 계층·정규화·재질의 뒤): 35/43 — 제외 g32(정답 grounding 없음)
- 최종 grounding 정확(후, 조건 계층·정규화·재질의 뒤): 29/43 — 제외 g32(정답 grounding 없음)

- 호출·지연(전): 계획 44, 재질의 7(재질의한 문항 7), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 12.4초, p90 18.7초, 최대 82.0초, 합계 699.8초; 전체 경과 712.9초
- 호출·지연(후): 계획 44, 재질의 8(재질의한 문항 8), 실패 호출 기록 1, timeout 추정 0; 문항 지연 중앙값 12.7초, p90 24.7초, 최대 312.8초, 합계 1099.2초; 전체 경과 1111.8초

| 전→후 | 문항 |
|---|---|
| 오답 → 부당한 거부 | g14 |
| 오답 → 실행 실패 | g33 |
| 오답 → 정당한 거부 | g32 |
| 오답 → 정상 답변 | g40 |
| 정상 답변 → 부당한 거부 | g34 |
| 정상 답변 → 실행 실패 | g02, g03, g05, g24, g35 |
| 정상 답변 → 오답 | g06, g07, g23, g43 |

- 새로 맞음 2: g32, g40
- 회귀(맞던 문항이 틀림) 10: g02, g03, g05, g06, g07, g23, g24, g34, g35, g43

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| g01 | answered | 정상 답변 | 정상 답변 |  | False→True |
| g02 | answered | 정상 답변 | 실행 실패 | MISSING_RELATION_QUALIFIER | True→False |
| g03 | answered | 정상 답변 | 실행 실패 | INVALID_CONCEPT | True→False |
| g04 | answered | 부당한 거부 | 부당한 거부 | UNCONSUMED_CONDITION | False→False |
| g05 | answered | 정상 답변 | 실행 실패 | UNUSED_CONCEPT | True→True |
| g06 | answered | 정상 답변 | 오답 | [["dimension", "emd", "sigungu"]] | True→False |
| g07 | answered | 정상 답변 | 오답 | [["time", "140000-170000", "140000-150000"]] | True→False |
| g08 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g09 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g10 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g11 | answered | 오답 | 오답 | [["scope_dropoff", "scope:district:2617010100", null], ["scope_pickup", null, "scope:district:2617010100"]] | False→False |
| g12 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g13 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g14 | answered | 오답 | 부당한 거부 | UNCONSUMED_CONDITION | False→False |
| g15 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g16 | answered | 오답 | 오답 | [["order", "bottom", "top"]] | False→False |
| g17 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→True |
| g18 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g19 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g20 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g21 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g22 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g23 | answered | 정상 답변 | 오답 | [["aggregation", "sum", null]] | True→False |
| g24 | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR_COMBINATION | True→False |
| g25 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g26 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g27 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g28 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g29 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g30 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g31 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g32 | unsupported | 오답 | 정당한 거부 | UNVERIFIED_TIMS_CONTRACT | None→None |
| g33 | answered | 오답 | 실행 실패 | INVALID_FACTOR_COMBINATION | False→False |
| g34 | answered | 정상 답변 | 부당한 거부 | NO_OPERATOR | True→True |
| g35 | answered | 정상 답변 | 실행 실패 | UNKNOWN_FACTOR | True→False |
| g36 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g37 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g38 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g39 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g40 | answered | 오답 | 정상 답변 |  | False→True |
| g41 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g42 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g43 | answered | 정상 답변 | 오답 | [["scope", "<조회 안 됨 부산>", null]] 장소 조회 횟수 불일치 | True→False |
| g44 | needs_clarification | 오답 | 오답 |  | False→False |

## 대조 31(개발)

- 전: `evaluation/grounding_v3/runs/final_contrast_qwen3_8b.json` (코드 `cad3bb895a`)
- 후: `evaluation/grounding_v4/runs/final_contrast_qwen3_8b.json` (코드 `a8664a2e24`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 26 | 25 |
| 오답 | 2 | 3 |
| 정당한 거부 | 0 | 1 |
| 부당한 거부 | 1 | 1 |
| 실행 실패 | 2 | 1 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 31 | 31 |

- 최종 grounding 정확(전, 조건 계층·정규화·재질의 뒤): 24/30 — 제외 c08c(정답 grounding 없음)
- 최종 grounding 정확(후, 조건 계층·정규화·재질의 뒤): 24/30 — 제외 c08c(정답 grounding 없음)

- 호출·지연(전): 계획 31, 재질의 5(재질의한 문항 5), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 13.1초, p90 22.8초, 최대 31.0초, 합계 483.3초; 전체 경과 492.4초
- 호출·지연(후): 계획 31, 재질의 9(재질의한 문항 9), 실패 호출 기록 1, timeout 추정 0; 문항 지연 중앙값 13.5초, p90 22.8초, 최대 330.6초, 합계 806.2초; 전체 경과 815.4초

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 정상 답변 | c07d |
| 실행 실패 → 정당한 거부 | c08c |
| 실행 실패 → 정상 답변 | c06b |
| 정상 답변 → 부당한 거부 | c06a |
| 정상 답변 → 실행 실패 | c10a |
| 정상 답변 → 오답 | c04a |

- 새로 맞음 3: c06b, c07d, c08c
- 회귀(맞던 문항이 틀림) 3: c04a, c06a, c10a

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
| c04a | answered | 정상 답변 | 오답 | [["scope_dropoff", "scope:district:2700000000", null]] | True→False |
| c04b | answered | 정상 답변 | 정상 답변 |  | True→True |
| c04c | answered | 오답 | 오답 | [["scope_dropoff", "scope:district:2600000000", null]] | False→False |
| c05a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c05b | answered | 정상 답변 | 정상 답변 |  | True→True |
| c05c | answered | 정상 답변 | 정상 답변 |  | True→True |
| c06a | answered | 정상 답변 | 부당한 거부 | UNSUPPORTED_AGGREGATION_COMBINATION | True→False |
| c06b | answered | 실행 실패 | 정상 답변 |  | False→True |
| c06c | answered | 정상 답변 | 정상 답변 |  | True→True |
| c07a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c07b | answered | 정상 답변 | 정상 답변 |  | True→True |
| c07c | answered | 정상 답변 | 정상 답변 |  | True→True |
| c07d | answered | 부당한 거부 | 정상 답변 |  | False→True |
| c08a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c08b | needs_clarification | 오답 | 오답 |  | False→False |
| c08c | unsupported | 실행 실패 | 정당한 거부 | UNVERIFIED_TIMS_CONTRACT | None→None |
| c08d | answered | 정상 답변 | 정상 답변 |  | True→True |
| c08e | answered | 정상 답변 | 정상 답변 |  | True→True |
| c09a | answered | 정상 답변 | 정상 답변 |  | True→True |
| c09b | answered | 정상 답변 | 정상 답변 |  | False→False |
| c10a | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR_COMBINATION | True→False |
| c10b | answered | 정상 답변 | 정상 답변 |  | True→True |

## 1차 독립 40(개발)

- 전: `evaluation/grounding_v3/runs/final_indepv2_qwen3_8b.json` (코드 `cad3bb895a`)
- 후: `evaluation/grounding_v4/runs/final_indepv2_qwen3_8b.json` (코드 `a8664a2e24`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 20 | 23 |
| 오답 | 8 | 5 |
| 정당한 거부 | 3 | 4 |
| 부당한 거부 | 3 | 0 |
| 실행 실패 | 6 | 8 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 40 | 40 |

- 최종 grounding 정확(전, 조건 계층·정규화·재질의 뒤): 24/39 — 제외 n24(정답 grounding 없음)
- 최종 grounding 정확(후, 조건 계층·정규화·재질의 뒤): 24/39 — 제외 n24(정답 grounding 없음)

- 호출·지연(전): 계획 40, 재질의 12(재질의한 문항 12), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 14.5초, p90 26.4초, 최대 164.9초, 합계 818.7초; 전체 경과 830.2초
- 호출·지연(후): 계획 40, 재질의 12(재질의한 문항 12), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 14.8초, p90 27.4초, 최대 57.2초, 합계 705.0초; 전체 경과 716.2초

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 실행 실패 | n14 |
| 부당한 거부 → 오답 | n03 |
| 부당한 거부 → 정상 답변 | n21 |
| 실행 실패 → 정상 답변 | n09, n18, n20 |
| 오답 → 실행 실패 | n12, n23 |
| 오답 → 정당한 거부 | n24 |
| 오답 → 정상 답변 | n05, n15, n36 |
| 정상 답변 → 실행 실패 | n10, n34 |
| 정상 답변 → 오답 | n13, n33 |

- 새로 맞음 8: n05, n09, n15, n18, n20, n21, n24, n36
- 회귀(맞던 문항이 틀림) 4: n10, n13, n33, n34

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| n01 | answered | 실행 실패 | 실행 실패 | INVALID_PLACE | False→False |
| n02 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n03 | answered | 부당한 거부 | 오답 | [["scope_dropoff", null, "scope:district:2726000000"], ["scope_pickup", "scope:district:2726000000", null]] | False→False |
| n04 | answered | 정상 답변 | 정상 답변 |  | True→False |
| n05 | answered | 오답 | 정상 답변 |  | False→True |
| n06 | answered | 오답 | 오답 | [["dimension_target", "dropoff", null]] | False→False |
| n07 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n08 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n09 | answered | 실행 실패 | 정상 답변 |  | False→False |
| n10 | answered | 정상 답변 | 실행 실패 | MISSING_RELATION_QUALIFIER | True→False |
| n11 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n12 | answered | 오답 | 실행 실패 | VALUELESS_CONCEPT | False→False |
| n13 | answered | 정상 답변 | 오답 | [["aggregation", "med", null]] | True→False |
| n14 | answered | 부당한 거부 | 실행 실패 | INVALID_FACTOR_COMBINATION | False→True |
| n15 | answered | 오답 | 정상 답변 |  | False→True |
| n16 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n17 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n18 | answered | 실행 실패 | 정상 답변 |  | False→True |
| n19 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n20 | answered | 실행 실패 | 정상 답변 |  | False→True |
| n21 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| n22 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n23 | needs_clarification | 오답 | 실행 실패 | INVALID_FACTOR_COMBINATION | False→False |
| n24 | unsupported | 오답 | 정당한 거부 | UNVERIFIED_TIMS_CONTRACT | None→None |
| n25 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→False |
| n26 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→True |
| n27 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→True |
| n28 | answered | 정상 답변 | 정상 답변 |  | True→False |
| n29 | answered | 실행 실패 | 실행 실패 | MISSING_RELATION_QUALIFIER | False→False |
| n30 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n31 | answered | 오답 | 오답 | 장소 조회 횟수 불일치 | True→True |
| n32 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n33 | answered | 정상 답변 | 오답 | [["taxi_status", "occupied", null]] | True→False |
| n34 | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR_COMBINATION | True→False |
| n35 | answered | 실행 실패 | 실행 실패 | INVALID_FACTOR_COMBINATION | False→False |
| n36 | answered | 오답 | 정상 답변 |  | False→True |
| n37 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n38 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n39 | answered | 정상 답변 | 정상 답변 |  | True→True |
| n40 | answered | 정상 답변 | 정상 답변 |  | True→True |

## 2차 독립 40(개발)

- 전: `evaluation/grounding_v3/runs/final_indepv3_qwen3_8b.json` (코드 `cad3bb895a`)
- 후: `evaluation/grounding_v4/runs/final_indepv3_qwen3_8b.json` (코드 `a8664a2e24`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 20 | 20 |
| 오답 | 9 | 5 |
| 정당한 거부 | 1 | 2 |
| 부당한 거부 | 2 | 3 |
| 실행 실패 | 8 | 10 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 40 | 40 |

- 최종 grounding 정확(전, 조건 계층·정규화·재질의 뒤): 20/38 — 제외 m25, m40(정답 grounding 없음)
- 최종 grounding 정확(후, 조건 계층·정규화·재질의 뒤): 21/38 — 제외 m25, m40(정답 grounding 없음)

- 호출·지연(전): 계획 40, 재질의 13(재질의한 문항 13), 실패 호출 기록 1, timeout 추정 0; 문항 지연 중앙값 13.0초, p90 20.4초, 최대 409.6초, 합계 978.8초; 전체 경과 991.2초
- 호출·지연(후): 계획 40, 재질의 7(재질의한 문항 7), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 12.0초, p90 19.1초, 최대 36.0초, 합계 589.8초; 전체 경과 600.8초

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 실행 실패 | m20 |
| 실행 실패 → 오답 | m13 |
| 실행 실패 → 정당한 거부 | m25 |
| 실행 실패 → 정상 답변 | m05, m12, m38 |
| 오답 → 실행 실패 | m03, m04, m27, m40 |
| 오답 → 정상 답변 | m26 |
| 정상 답변 → 부당한 거부 | m18, m22 |
| 정상 답변 → 실행 실패 | m01, m36 |

- 새로 맞음 5: m05, m12, m25, m26, m38
- 회귀(맞던 문항이 틀림) 4: m01, m18, m22, m36

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| m01 | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR_COMBINATION | True→True |
| m02 | answered | 실행 실패 | 실행 실패 | MULTIPLE_MEASURES | False→False |
| m03 | answered | 오답 | 실행 실패 | UNGROUNDED_SCOPE | False→False |
| m04 | answered | 오답 | 실행 실패 | INVALID_FACTOR_COMBINATION | False→False |
| m05 | answered | 실행 실패 | 정상 답변 |  | False→True |
| m06 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m07 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m08 | answered | 정상 답변 | 정상 답변 |  | False→True |
| m09 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m10 | answered | 오답 | 오답 | [["scope_pickup", "<조회 안 됨 부산진구>", "scope:district:2623000000"]] 장소 조회 횟수 불일치 | False→False |
| m11 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m12 | answered | 실행 실패 | 정상 답변 |  | False→False |
| m13 | answered | 실행 실패 | 오답 | [["dimension_target", "dropoff", null], ["scope_pickup", "scope:district:2600000000", null]] | False→False |
| m14 | answered | 정상 답변 | 정상 답변 |  | False→True |
| m15 | answered | 부당한 거부 | 부당한 거부 | UNSUPPORTED_AGGREGATION_COMBINATION | False→False |
| m16 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m17 | answered | 실행 실패 | 실행 실패 | INVALID_FACTOR | False→False |
| m18 | answered | 정상 답변 | 부당한 거부 | UNDEFINED_MEASURE_AGGREGATION | True→False |
| m19 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m20 | answered | 부당한 거부 | 실행 실패 | MISSING_CONCEPT_VALUE | False→False |
| m21 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m22 | answered | 정상 답변 | 부당한 거부 | UNVERIFIED_TIMS_CONTRACT | True→False |
| m23 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m24 | needs_clarification | 오답 | 오답 |  | False→False |
| m25 | unsupported | 실행 실패 | 정당한 거부 | UNVERIFIED_TIMS_CONTRACT | None→None |
| m26 | answered | 오답 | 정상 답변 |  | False→False |
| m27 | answered | 오답 | 실행 실패 | UNKNOWN_ATTRIBUTE | True→False |
| m28 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m29 | answered | 오답 | 오답 | [["scope", "<조회 안 됨 광안리>", "scope:gz:33212"]] | False→False |
| m30 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m31 | answered | 오답 | 오답 | 장소 조회 횟수 불일치 | False→True |
| m32 | answered | 실행 실패 | 실행 실패 | UNGROUNDED_SCOPE | False→False |
| m33 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m34 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m35 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m36 | answered | 정상 답변 | 실행 실패 | NO_MEASURE | True→False |
| m37 | answered | 정상 답변 | 정상 답변 |  | True→True |
| m38 | answered | 실행 실패 | 정상 답변 |  | False→True |
| m39 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→True |
| m40 | unsupported | 오답 | 실행 실패 | INVALID_FACTOR | None→None |

## v4 40(개발)

- 전: `evaluation/grounding_v3/runs/final_indepv4_qwen3_8b.json` (코드 `cad3bb895a`)
- 후: `evaluation/grounding_v4/runs/final_indepv4_qwen3_8b.json` (코드 `a8664a2e24`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 24 | 23 |
| 오답 | 4 | 5 |
| 정당한 거부 | 0 | 3 |
| 부당한 거부 | 7 | 4 |
| 실행 실패 | 5 | 5 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 40 | 40 |

- 최종 grounding 정확(전, 조건 계층·정규화·재질의 뒤): 21/38 — 제외 k24, k40(정답 grounding 없음)
- 최종 grounding 정확(후, 조건 계층·정규화·재질의 뒤): 23/38 — 제외 k24, k40(정답 grounding 없음)

- 호출·지연(전): 계획 40, 재질의 8(재질의한 문항 8), 실패 호출 기록 1, timeout 추정 0; 문항 지연 중앙값 12.7초, p90 18.2초, 최대 315.8초, 합계 866.1초; 전체 경과 878.5초
- 호출·지연(후): 계획 40, 재질의 10(재질의한 문항 10), 실패 호출 기록 1, timeout 추정 0; 문항 지연 중앙값 12.0초, p90 23.5초, 최대 332.7초, 합계 1013.3초; 전체 경과 1024.7초

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 실행 실패 | k22, k36 |
| 부당한 거부 → 정당한 거부 | k23 |
| 부당한 거부 → 정상 답변 | k35 |
| 실행 실패 → 부당한 거부 | k02 |
| 실행 실패 → 정상 답변 | k08, k26, k33 |
| 오답 → 정당한 거부 | k39, k40 |
| 정상 답변 → 실행 실패 | k09, k19 |
| 정상 답변 → 오답 | k03, k28, k31 |

- 새로 맞음 7: k08, k23, k26, k33, k35, k39, k40
- 회귀(맞던 문항이 틀림) 5: k03, k09, k19, k28, k31

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| k01 | answered | 부당한 거부 | 부당한 거부 | DATE_AMBIGUOUS | False→False |
| k02 | answered | 실행 실패 | 부당한 거부 | UNCONSUMED_CONDITION | False→False |
| k03 | answered | 정상 답변 | 오답 | [["taxi_status", "vacant", null]] | False→False |
| k04 | answered | 부당한 거부 | 부당한 거부 | DATE_AMBIGUOUS | False→False |
| k05 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k06 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k07 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k08 | answered | 실행 실패 | 정상 답변 |  | False→True |
| k09 | answered | 정상 답변 | 실행 실패 | VALUELESS_CONCEPT | True→False |
| k10 | answered | 정상 답변 | 정상 답변 |  | False→True |
| k11 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k12 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k13 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k14 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k15 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k16 | answered | 부당한 거부 | 부당한 거부 | DATE_AMBIGUOUS | False→False |
| k17 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k18 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k19 | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR_COMBINATION | True→True |
| k20 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k21 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k22 | answered | 부당한 거부 | 실행 실패 | INVALID_FACTOR_COMBINATION | False→False |
| k23 | unsupported | 부당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | False→True |
| k24 | unsupported | 실행 실패 | 실행 실패 | INVALID_PARAM_VALUE | None→None |
| k25 | answered | 오답 | 오답 | [["dimension_target", "pickup", null], ["scope_pickup", null, "scope:district:2617010100"]] | False→False |
| k26 | answered | 실행 실패 | 정상 답변 |  | False→True |
| k27 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k28 | answered | 정상 답변 | 오답 | [["dimension_target", "dropoff", null]] | True→False |
| k29 | answered | 정상 답변 | 정상 답변 |  | True→False |
| k30 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k31 | answered | 정상 답변 | 오답 | [["dimension_target", "pickup", null]] | False→False |
| k32 | answered | 정상 답변 | 정상 답변 |  | True→False |
| k33 | answered | 실행 실패 | 정상 답변 |  | False→False |
| k34 | answered | 오답 | 오답 | [["dimension_target", "dropoff", null]] | False→False |
| k35 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| k36 | answered | 부당한 거부 | 실행 실패 | INVALID_FACTOR | False→False |
| k37 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k38 | answered | 정상 답변 | 정상 답변 |  | True→True |
| k39 | needs_clarification | 오답 | 정당한 거부 | AMBIGUOUS_INNER_AGGREGATION | False→True |
| k40 | unsupported | 오답 | 정당한 거부 | UNVERIFIED_TIMS_CONTRACT | None→None |

