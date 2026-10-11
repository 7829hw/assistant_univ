# Partial-P0.2 결과 (Ollama qwen3:8b, 2026-10-11, 결정 59)

계획: `PLAN_P0_2.md`. smoke 통과, 셀 6개(greedy 1 + sampling 5) 모두 guard 중단 없음. Full·P0·P0.1은 기존 셀.
분석: `analysis_p0_2.json`(Full vs P0.2), `analysis_p0_vs_p0_2.json`, `analysis_p0_1_vs_p0_2.json`.

## 1. 판정(sampling 5회 평균, Full 대비)

| Gate | Full | P0 | P0.1 | P0.2 | P0.2 − Full | 결과 |
|---|---|---|---|---|---|---|
| semantic correctness | 81.0% | 83.4% | 74.2% | 81.2% | +0.2%p, CI [−5.2, +5.6], p=1.0 | 통과(점 추정) |
| answerable semantic correctness | 81.0% | 83.4% | 74.2% | 81.2% | +0.2%p | 통과(점 추정) |
| refusal correctness | — | — | — | — | — | 판정 불가(업체 100에 거부 문항 없음) |
| grounding failure(최종) | 4.8 | 6.8 | 9.4 | 3.2 | −1.6 | 통과 |
| execution completion | 88.0% | 88.8% | 87.4% | 91.6% | +3.6%p | 통과 |
| structural errors(첫 응답) | 4.2 | 6.4 | 11.4 | 3.8 | −0.4 | 통과(근소) |
| final JSON tokens | 126.3 | 69.2 | 64.4 | 65.4 | −48.2% | 통과 |

- 회차별 P0.2: 81/83/82/80/80(Full 83/79/80/82/81). P0 대비 −2.2%p, CI [−7.8, +3.4], p=0.49.
- 모든 gate가 점 추정으로 통과다. 정답률 CI 하한(−5.2%p)은 −1%p 기준보다 아래라 non-inferiority가 통계적으로 확인된
  것은 아니다.
- eval_count 중앙값 749 → 521(−30%), thinking 2216 → 1675자. 
- greedy(판정에 쓰지 않음): Full 87 / P0 84 / P0.1 75 / **P0.2 78**. Full 정답·P0.2 오답 17, 반대 8. 차이 대부분은
  answered_mismatch(9)이고, OD·dimension_target 같은 factor 의미 오류(048, 056, 067, 069)와 `시군구 간`을
  pickup/dropoff concept로 쓴 078 등이다. 같은 문항이 sampling에서는 대부분 맞는다(체계적 차이에 들지 않음).

## 2. 가설 확인(P0.1 → P0.2)

| 문항 묶음 | Full | P0 | P0.1 | P0.2 |
|---|---|---|---|---|
| scope id 질문 8개 | 87.5% | 90.0% | 0.0% | 75.0% |
| 나머지 92개 | 80.4% | 82.8% | 80.7% | 81.7% |

- P0.1 대비 +7.0%p, CI [+1.2, +13.0], p=0.02. scope value 누락(`MISSING_CONCEPT_VALUE`) 46 → 0건.
  009·029·042·051·088·094가 0/5 → 4–5/5로 돌아왔다. 가설대로 P0.1 하락의 원인은 scope value 규칙 누락이었다.
- scope 8개 중 **082(지역명이 답)는 0/5로 남았다**: `{"unsupported": true}` 또는 scope만 적고 value 없는 place
  측정값을 빠뜨림(NO_MEASURE). Full 4/5, P0 3/5. P0.1·P0.2의 규칙 6·10 문구("어느 지역/읍면동/시군구")가 "가리키는
  지역명"을 덮지 못하는 것으로 보인다. 066도 Full 5 → P0.2 4로 낮다.

## 3. 첫 응답 오류 합계(6셀)

| 오류 | Full | P0 | P0.1 | P0.2 |
|---|---|---|---|---|
| INVALID_CONCEPT | 1 | 10 | 3 | 1 |
| UNKNOWN_ATTRIBUTE | 1 | 8 | 0 | 0 |
| NO_MEASURE / MULTIPLE_MEASURES | 2 | 8 | 0 | 4 |
| MISSING_CONCEPT_VALUE | 1 | 0 | 46 | 0 |
| UNGROUNDED_SCOPE | 7 | 3 | 0 | 0 |
| INVALID_FACTOR | 7 | 7 | 20 | 20 |
| UNSUPPORTED_QUESTION(첫 응답) | 0 | 0 | 3 | 4 |

INVALID_FACTOR(time 형식, dimension에 pickup·week)는 P0.1과 같은 수준으로 남았다(이번 버전에서 일부러 손대지 않음).
대부분 재질의로 회복되어 최종 grounding failure는 Full보다 적다. NO_MEASURE·UNSUPPORTED는 대부분 082다.

## 4. 결론

- P0.2는 사용자 gate를 모두(거부 gate 제외) 점 추정으로 통과했다. P0.1의 하락은 scope value 규칙 누락으로 설명된다.
- 남은 약점: 082(지역명 답) 0/5, factor 형식 오류 첫 응답 20건(재질의로 회복), greedy 78.
- 주의: P0.1·P0.2는 업체 100의 오류를 보고 고친 prompt라 업체 100 결과는 낙관적일 수 있다(결정 58).
