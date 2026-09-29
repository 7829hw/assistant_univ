# 결과 보고 (채점기 v2, `evaluate_vendor100.py report`)

## 업체 100문항(개발): grounding_v1 B0 → 최종

- 전: `evaluation/grounding_v1/runs/b0_qwen3_8b.json` (코드 `a0d7b18aaa`)
- 후: `evaluation/grounding_v1/runs/final2_dev_qwen3_8b.json` (코드 `1cb307df8e`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 65 | 93 |
| 오답 | 14 | 2 |
| 정당한 거부 | 0 | 0 |
| 부당한 거부 | 3 | 2 |
| 실행 실패 | 18 | 3 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 100 | 100 |

- LLM grounding 정확(전): 63/100
- LLM grounding 정확(후): 90/100

- 호출·지연(전): 계획 100, 재질의 22(재질의한 문항 22), 실패 호출 기록 0, timeout 추정 1(044); 문항 지연 중앙값 12.2초, p90 24.2초, 최대 444.2초, 합계 2098.5초; 전체 경과 기록 없음(평가기 v1)
- 호출·지연(후): 계획 100, 재질의 13(재질의한 문항 13), 실패 호출 기록 0, timeout 추정 4(041, 044, 067, 100); 문항 지연 중앙값 12.4초, p90 20.7초, 최대 325.6초, 합계 2616.7초; 전체 경과 기록 없음(평가기 v1)

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 정상 답변 | 025, 070, 080 |
| 실행 실패 → 오답 | 067 |
| 실행 실패 → 정상 답변 | 010, 013, 014, 016, 020, 024, 038, 043, 054, 075, 079, 085, 090, 094, 098 |
| 오답 → 부당한 거부 | 095 |
| 오답 → 정상 답변 | 001, 005, 009, 037, 050, 052, 055, 074, 084, 088, 092, 100 |
| 정상 답변 → 부당한 거부 | 064 |
| 정상 답변 → 실행 실패 | 006 |

- 새로 맞음 30: 001, 005, 009, 010, 013, 014, 016, 020, 024, 025, 037, 038, 043, 050, 052, 054, 055, 070, 074, 075, 079, 080, 084, 085, 088, 090, 092, 094, 098, 100
- 회귀(맞던 문항이 틀림) 2: 006, 064

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| 001 | answered | 오답 | 정상 답변 |  | False→True |
| 002 | answered | 정상 답변 | 정상 답변 |  | False→True |
| 003 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 004 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 005 | answered | 오답 | 정상 답변 |  | False→True |
| 006 | answered | 정상 답변 | 실행 실패 | INVALID_FACTOR | True→False |
| 007 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 008 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 009 | answered | 오답 | 정상 답변 |  | False→False |
| 010 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 011 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 012 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 013 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 014 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 015 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 016 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 017 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 018 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 019 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 020 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 021 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 022 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 023 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 024 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 025 | answered | 부당한 거부 | 정상 답변 |  | False→True |
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
| 037 | answered | 오답 | 정상 답변 |  | False→True |
| 038 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 039 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 040 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 041 | answered | 오답 | 오답 | [["scope_dropoff", "scope:district:2600000000", null], ["scope_pickup", null, "scope:district:2600000000"]] | False→False |
| 042 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 043 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 044 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 045 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 046 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 047 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 048 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 049 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 050 | answered | 오답 | 정상 답변 |  | False→True |
| 051 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 052 | answered | 오답 | 정상 답변 |  | False→True |
| 053 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 054 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 055 | answered | 오답 | 정상 답변 |  | False→True |
| 056 | answered | 정상 답변 | 정상 답변 |  | False→False |
| 057 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 058 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 059 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 060 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 061 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 062 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 063 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 064 | answered | 정상 답변 | 부당한 거부 | MEASURE_EXPRESSION_CONFLICT | True→False |
| 065 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 066 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 067 | answered | 실행 실패 | 오답 | [["scope_dropoff", "scope:district:2600000000", null], ["scope_pickup", null, "scope:district:2600000000"]] | False→False |
| 068 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 069 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 070 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| 071 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 072 | answered | 정상 답변 | 정상 답변 |  | True→False |
| 073 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 074 | answered | 오답 | 정상 답변 |  | False→True |
| 075 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 076 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 077 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 078 | answered | 실행 실패 | 실행 실패 | VALUELESS_CONCEPT | False→False |
| 079 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 080 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| 081 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 082 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 083 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 084 | answered | 오답 | 정상 답변 |  | False→True |
| 085 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 086 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 087 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 088 | answered | 오답 | 정상 답변 |  | False→True |
| 089 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 090 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 091 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 092 | answered | 오답 | 정상 답변 |  | False→True |
| 093 | answered | 실행 실패 | 실행 실패 | MISSING_RELATION_QUALIFIER | False→False |
| 094 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 095 | answered | 오답 | 부당한 거부 | PLACE_NOT_IN_QUESTION | False→False |
| 096 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 097 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 098 | answered | 실행 실패 | 정상 답변 |  | False→True |
| 099 | answered | 정상 답변 | 정상 답변 |  | True→True |
| 100 | answered | 오답 | 정상 답변 |  | False→True |

## 기존 44문항: grounding_v1 B0 → 최종

- 전: `evaluation/grounding_v1/runs/b0_holdout_qwen3_8b.json` (코드 `a0d7b18aaa`)
- 후: `evaluation/grounding_v1/runs/final_holdout_qwen3_8b.json` (코드 `1cb307df8e`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 21 | 35 |
| 오답 | 9 | 6 |
| 정당한 거부 | 1 | 1 |
| 부당한 거부 | 3 | 1 |
| 실행 실패 | 10 | 1 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 44 | 44 |

- LLM grounding 정확(전): 22/43 — 제외 g32(정답 grounding 없음)
- LLM grounding 정확(후): 35/43 — 제외 g32(정답 grounding 없음)

- 호출·지연(전): 계획 44, 재질의 6(재질의한 문항 6), 실패 호출 기록 0, timeout 추정 1(g12); 문항 지연 중앙값 12.0초, p90 22.7초, 최대 330.4초, 합계 1151.1초; 전체 경과 기록 없음(평가기 v1)
- 호출·지연(후): 계획 44, 재질의 6(재질의한 문항 6), 실패 호출 기록 0, timeout 추정 0; 문항 지연 중앙값 11.9초, p90 18.3초, 최대 38.7초, 합계 605.3초; 전체 경과 기록 없음(평가기 v1)

| 전→후 | 문항 |
|---|---|
| 부당한 거부 → 정상 답변 | g27, g30, g42 |
| 실행 실패 → 오답 | g16, g33, g40 |
| 실행 실패 → 정상 답변 | g02, g15, g24, g28, g29, g31, g35 |
| 오답 → 부당한 거부 | g04 |
| 오답 → 실행 실패 | g14 |
| 오답 → 정상 답변 | g01, g03, g34, g38 |

- 새로 맞음 14: g01, g02, g03, g15, g24, g27, g28, g29, g30, g31, g34, g35, g38, g42
- 회귀(맞던 문항이 틀림) 0: -

| 문항 | 기대 | 전 | 후 | 후 오류 코드 / 인자 차이 | grounding 전→후 |
|---|---|---|---|---|---|
| g01 | answered | 오답 | 정상 답변 |  | False→False |
| g02 | answered | 실행 실패 | 정상 답변 |  | False→True |
| g03 | answered | 오답 | 정상 답변 |  | False→True |
| g04 | answered | 오답 | 부당한 거부 | NO_OPERATOR | False→False |
| g05 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g06 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g07 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g08 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g09 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g10 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g11 | answered | 오답 | 오답 | [["scope_dropoff", "scope:district:2617010100", null], ["scope_pickup", null, "scope:district:2617010100"]] | False→False |
| g12 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g13 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g14 | answered | 오답 | 실행 실패 | MISSING_RELATION_QUALIFIER | False→False |
| g15 | answered | 실행 실패 | 정상 답변 |  | False→True |
| g16 | answered | 실행 실패 | 오답 | [["order", "bottom", "top"]] | False→False |
| g17 | unsupported | 정당한 거부 | 정당한 거부 | UNCONSUMED_CONDITION | True→True |
| g18 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g19 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g20 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g21 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g22 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g23 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g24 | answered | 실행 실패 | 정상 답변 |  | False→True |
| g25 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g26 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g27 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| g28 | answered | 실행 실패 | 정상 답변 |  | False→True |
| g29 | answered | 실행 실패 | 정상 답변 |  | False→True |
| g30 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| g31 | answered | 실행 실패 | 정상 답변 |  | False→True |
| g32 | unsupported | 오답 | 오답 |  | None→None |
| g33 | answered | 실행 실패 | 오답 | [["aggregation", "sum", null]] | False→False |
| g34 | answered | 오답 | 정상 답변 |  | False→True |
| g35 | answered | 실행 실패 | 정상 답변 |  | False→True |
| g36 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g37 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g38 | answered | 오답 | 정상 답변 |  | False→True |
| g39 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g40 | answered | 실행 실패 | 오답 | [["order", "bottom", "top"]] | False→False |
| g41 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g42 | answered | 부당한 거부 | 정상 답변 |  | False→True |
| g43 | answered | 정상 답변 | 정상 답변 |  | True→True |
| g44 | needs_clarification | 오답 | 오답 |  | False→False |

## 정답 grounding 층 업체 100문항(grounding_v1 최종 코드)

- 전: `evaluation/grounding_v1/runs/dev_gold_final.json` (코드 `9650d29fa0`)
- 후: `evaluation/grounding_v1/runs/dev_gold_final.json` (코드 `9650d29fa0`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 98 | 98 |
| 오답 | 2 | 2 |
| 정당한 거부 | 0 | 0 |
| 부당한 거부 | 0 | 0 |
| 실행 실패 | 0 | 0 |
| 미실행 | 0 | 0 |
| **합계(분모)** | 100 | 100 |



| 전→후 | 문항 |
|---|---|

- 새로 맞음 0: -
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
| 093 | answered | 오답 | 오답 | 장소 조회 횟수 불일치 | None→None |
| 094 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 095 | answered | 오답 | 오답 | 장소 조회 횟수 불일치 | None→None |
| 096 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 097 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 098 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 099 | answered | 정상 답변 | 정상 답변 |  | None→None |
| 100 | answered | 정상 답변 | 정상 답변 |  | None→None |

## 정답 grounding 층 기존 44문항: B0 → 최종

- 전: `evaluation/grounding_v1/runs/holdout_gold_b0.json` (코드 `a0d7b18aaa`)
- 후: `evaluation/grounding_v1/runs/holdout_gold_final.json` (코드 `9650d29fa0`)

| 결과 분류 | 전 | 후 |
|---|---|---|
| 정상 답변 | 40 | 40 |
| 오답 | 1 | 1 |
| 정당한 거부 | 2 | 2 |
| 부당한 거부 | 0 | 0 |
| 실행 실패 | 0 | 0 |
| 미실행 | 1 | 1 |
| **합계(분모)** | 44 | 44 |



| 전→후 | 문항 |
|---|---|

- 새로 맞음 0: -
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
| g14 | answered | 오답 | 오답 | 장소 조회 횟수 불일치 | None→None |
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

