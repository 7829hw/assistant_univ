# DIAGNOSIS_T1 — 운행 요금(T1) 실패 유형 (Stage 1, 기존 추론 결과만, GPU 미사용)

데이터: 기존 CT10K(10,000)·H-dev(2,000) 셀. A = 기존 A0 r1, B = Semantic-balanced r1. 문항 유형 T1…T5는 평가 문항의 **정답 호출**로 정하고(문항을 기술, 모델 출력 아님), 실패 유형은 셀 행의 채점 필드(`category`, `error_code`, `checks`)로 정한다. 근거가 없으면 `unclassified`. 분류 스크립트 `analysis/stage1_failure_types.py`, 표 `tables/stage1_failure_types.csv`, `tables/stage1_region_split.csv`.
진단용 seed 1102·211102·2026131은 기존 결과를 보고 고른 표본이며 seed 모집단의 무작위 표본이 아니다.

## 1. T1 실패 유형 분포 (CT10K, T1 1,020문항 × 5 seed = 5,100, %)
| 유형 | A | B |
|---|---|---|
| 정답(match) | 77.4 | 47.3 |
| **wrong_region = 정답에 있는 `get_place_scope` 조회를 모델이 생략** | 8.8 | **36.3** |
| refused_unsupported | 11.4 | 13.6 |
| wrong_time | 1.5 | 1.0 |
| wrong_aggregation | 0.0 | 0.2 |
| failed(compiler/validator) | 0.9 | 1.4 |
| truncation | 0.1 | 0.2 |
| wrong_tool / wrong_metric / wrong_od / grounding_ok_exec_differs / unclassified | 0.0 | 0.0 |

- `wrong_region`은 전부 한 하위 유형이다: T1 `wrong_region` 중 `no_place_lookup`이 A 448/448, B 1,852/1,852 (다른 장소 조회 0, 조회 개수 불일치 0). 즉 **"요금" 문항에서 지역(시도) 조건을 주는 LOCATION 개념/장소 조회가 빠지는 현상**이다. Tool·Metric·Aggregation·OD는 틀리지 않았다(요금 metric은 맞게 고른다).
- 사례 (H-dev, B-o211102; 같은 문항에서 A는 정답): "2025년 11월 29일부터 12월 5일까지 대구 소속 택시의 평균 요금은?" → A 계획: `AMOUNT fare + EVENT trip + LOCATION place(대구)`, B 계획: `AMOUNT fare + EVENT trip` 만 있고 LOCATION이 없으며 `factors.taxi_type: private`가 추가됨 → 실행 `get_trip_metrics(avg, date, fare)` (지역 없음), 결과 12000. 같은 형태가 "2024년 6월 28일~7월 11일 대구 …", "2025년 4월 14일 부산 … 중간값"에서도 확인.
- refusal의 성격도 다르다 (T1 refused 건): A는 `NO_OPERATOR` 492 / `UNSUPPORTED_QUESTION` 88, B는 `UNSUPPORTED_QUESTION` 674 / `NO_OPERATOR` 19. 거부 총량은 비슷해도 메커니즘이 다르다.

## 2. Seed별 (CT10K T1 1,020문항): match / 장소 조회 생략 / 거부
| seed | A | B |
|---|---|---|
| 1102 | 804 / 76 / 127 | 187 / 561 / 213 |
| 211102 | 965 / 5 / 46 | 99 / 706 / 174 |
| 2026131 | 525 / 291 / 112 | 757 / 138 / 111 |
| 2026113 | (96.2%) | 66.2% |
| 2026117 | (66.1%) | 67.9% |

- A의 **최악 seed(o2026131)도 같은 실패 유형**(조회 생략 291건, T1 51.5%)이다. 같은 실패 모드가 A에서도 seed에 따라 나타나므로 "B만의 새 오류 유형"이 아니라, **seed마다 켜졌다 꺼지는 모드의 발생 빈도**가 B에서 높아진 것이다(seed 2026131에서는 B가 A보다 오히려 좋다).
- **반복 쌍(H-dev T1, 171문항, seed o2026131)**: 같은 설정·순서 재학습인데 A r1 87 → A r2 47 정답(50.9 → 27.5%), B r1 131 → B r2 57 정답(76.6 → 33.3%). T1의 B−A는 r1 +25.7pp, r2 +5.8pp. **T1 정답률이 재학습만으로 20~43pp 움직인다.**

## 3. 해석 (증거 수준 표시)
- 확인됨: (a) T1 악화는 "지역 개념 생략"이라는 단일 실패 모드에 거의 전부 대응; (b) 이 모드는 A·B 모두에, 재학습마다 크게 변동하며 나타난다; (c) V4 학습 데이터에는 `get_trip_metrics`/요금(fare) 직접 학습 레코드가 없다(`SIGNATURE_AUDIT.md`) → T1은 비슷한 billing "소속 택시" 문항(LOCATION 포함)에서 **일반화**해야 하는 영역이다.
- 미확인(가설): 순서가 이 일반화 안정성에 영향을 주는지 (`CAUSAL_HYPOTHESES.md` M1–M3). 이 단계에서 "B 순서 때문에 틀림"이라고 분류하지 않는다.
