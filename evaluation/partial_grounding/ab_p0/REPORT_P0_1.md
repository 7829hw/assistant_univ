# Partial-P0.1 결과 (Ollama qwen3:8b, 2026-10-10, 결정 58)

계획: `PLAN_P0_1.md`. smoke 통과, 셀 6개(greedy 1 + sampling 5) 모두 guard 중단 없음. Full·P0는 ab_p0 셀(2026-10-09).
분석: `analysis_p0_1.json`(Full vs P0.1), `analysis_p0_vs_p0_1.json`(P0 vs P0.1).

## 1. 판정(sampling 5회 평균)

| Gate | Full | P0 | P0.1 | P0.1 − Full | 결과 |
|---|---|---|---|---|---|
| semantic correctness | 81.0% | 83.4% | 74.2% | −6.8%p, CI [−14.2, +0.2], p=0.07 | **불통과** |
| answerable semantic correctness | 81.0% | 83.4% | 74.2% | −6.8%p | **불통과** |
| refusal correctness | — | — | — | — | 판정 불가(업체 100에 거부 문항 없음) |
| grounding failure(최종) | 4.8 | 6.8 | 9.4 | +4.6 | **불통과** |
| execution completion | 88.0% | 88.8% | 87.4% | −0.6%p | 통과 |
| structural errors(첫 응답) | 4.2 | 6.4 | 11.4 | +7.2 | **불통과** |
| final JSON tokens | 126.3 | 69.2 | 64.4 | −49.0% | 통과 |

P0 대비 P0.1: −9.2%p, CI [−16.6, −1.8], p=0.016. 회차별 P0.1 정답률 72/73/73/75/78, greedy 75.
eval_count 중앙값 749(Full) → 638(P0) → 528(P0.1), thinking 2216 → 2099 → 1647자.

## 2. 원인: scope 값 규칙이 output_format 교체로 빠졌다

P0 output_format에 있던 "장소(place)와 scope는 질문에 있는 값을 value에 적습니다"가 교체안에 없고, scope 예시도 없다.
P0.1은 `scope:…` id가 주어진 질문에서 scope concept에 text만 적고 value를 비웠다 → `MISSING_CONCEPT_VALUE`(6셀 46건).

| 문항 묶음 | Full | P0 | P0.1 |
|---|---|---|---|
| scope id 질문 8개(009, 029, 042, 051, 066, 082, 088, 094) | 87.5% | 90.0% | **0.0%** |
| 나머지 92개 | 80.4% | 82.8% | 80.7% |

체계적 차이(|k| ≥ 4, Full 대비) 8건 중 7건이 이 scope 문항이고(나머지 005는 P0.1 쪽이 낫다), 082(지역명 답)도 같은 원인이다.

## 3. P0.1이 겨냥한 오류는 줄었다

첫 응답 오류 합계(6셀):

| 오류 | Full | P0 | P0.1 |
|---|---|---|---|
| INVALID_CONCEPT(subtype 자리에 비-subtype) | 1 | 10 | 3 |
| UNKNOWN_ATTRIBUTE(place.attributes.dimension 등) | 1 | 8 | 0 |
| NO_MEASURE / MULTIPLE_MEASURES | 2 | 8 | 0 |
| MISSING_CONCEPT_VALUE(scope value 누락) | 1 | 0 | **46** |
| INVALID_FACTOR | 7 | 7 | 20 |

INVALID_FACTOR 증가: time 형식(`weekend`, `20260604000000-…`), dimension에 `pickup`(031, 071)·`week`(098, 5회 모두).
대부분 재질의로 회복됐다(최종 INVALID_FACTOR는 셀당 0–2건).

## 4. 결론

- P0.1은 불통과다. 하락의 거의 전부가 scope value 규칙 누락이라는 한 가지 원인이고, 이 원인을 뺀 92문항에서는 Full과
  같은 수준(80.7 vs 80.4)이지만 P0(82.8)보다는 낮다.
- 겨냥한 경계 오류(INVALID_CONCEPT, UNKNOWN_ATTRIBUTE, NO_MEASURE)는 25건 → 3건으로 줄었다.
- 다음 행동은 사용자가 정한다.
