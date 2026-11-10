# DIAGNOSIS_T5 — T5(OD 상위 N) 및 대조 유형 T3·T4 (Stage 1)

방법·데이터는 `DIAGNOSIS_T1.md`와 같다(5 seed 합, %).

| 유형 (CT10K) | 항목 수 | A match | B match | 주된 차이 |
|---|---|---|---|---|
| T5 (OD top-N) | 10,325 | 78.6 | 75.2 | failed(compiler/validator) 14.3 → 15.1, refused 0.5 → 2.6, truncation 0.3 → 1.2 |
| T3 (billing 시도·일) | 2,665 | 95.5 | 90.2 | refused 1.1 → 7.3 |
| T4 (trip_count 일) | 465 | 98.9 | 99.8 | 변화 없음 |
| T1 (요금) | 5,100 | 77.4 | 47.3 | 지역 조회 생략 8.8 → 36.3 |

- **T5의 큰 실패는 A·B 공통의 구조적 실패**다: `failed_compiler_validator` 14~16% (A: `UNUSED_CONCEPT` 697, `AMBIGUOUS_PORT` 626; B: `AMBIGUOUS_PORT` 960, `UNUSED_CONCEPT` 326). 코드 종류의 비율은 달라졌지만 총량은 비슷 → 순서 효과로 단정할 근거 없음. B의 추가 변화는 refused_unsupported(+2.1pp)와 잘림(+0.9pp).
- T5의 wrong_region(4.8 → 5.0)·wrong_od(0.4 → 0.2)는 변하지 않았다.
- **B의 refusal 증가는 T1뿐 아니라 T3·T5에도 있다**(T3 +6.2pp, T5 +2.1pp). 요금(T1)만의 현상이 아니라 B 전반의 "더 자주 거절" 경향이며, T1의 큰 하락은 거기에 지역 개념 생략 모드가 겹친 것이다.
- T5 seed 편차는 B가 작다(SD 10.8 → 6.0pp; 단 A의 편차는 o2026131 62.0%에서 나온다).
- 분류하지 못한 항목: `answered_mismatch_unclassified`, `grounding_ok_exec_differs`는 본 분석 범위에서 0에 가깝다(상세 `tables/stage1_failure_types.csv`).
