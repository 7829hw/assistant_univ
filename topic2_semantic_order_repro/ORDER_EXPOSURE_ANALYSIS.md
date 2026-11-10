# ORDER_EXPOSURE_ANALYSIS — A(O4′)와 B(Semantic-balanced)의 순서 구조 (Stage 1)

스크립트 `analysis/stage1_order_exposure.py`, 표 `tables/stage1_order_exposure*.csv`. 학습 데이터 V4 1,984 레코드, LR = 선형 감쇠 2e-4 → 0(1,984 step, warmup 1 step, 레코드 1개 = 1 step). 가중치 = 레코드 `metadata.tokens`(모든 대상 레코드에 있음, 학습 토큰 근사; 학습 시 실제 loss 토큰 수와는 다를 수 있음). 레코드별 손실 로그는 없다(학습 로그에는 step 평균 loss만 있음) → 레코드 단위 손실·gradient 분석은 하지 않았다.

## 핵심 관찰 (5 seed 평균, B 순서는 seed 간 통계가 거의 동일)
| 집합 | 레코드 | 평균 위치(0=처음,1=끝) A → B | 마지막 25% 구간 레코드 A → B | LR-가중 토큰 비중 / 토큰 비중 A → B |
|---|---|---|---|---|
| **teacher `full_response` 전체** | 1,079 | 0.496 → **0.356** | | 53.9% → **69.3%** (토큰 비중 53.5%) |
| **hf `json_only` 전체** | 905 | 0.504 → **0.671** | | 46.1% → **30.7%** (토큰 비중 46.5%) |
| contrast teacher 전체 | 408 | 0.494 → 0.294 | 101 → 14 | 1.01 → 1.42 |
| **billing contrast teacher** | 298 | 0.495 → **0.279** | 73 → **5** | 1.01 → **1.45** |
| billing 전체 | 655 | 0.504 → 0.500 | 165 → 163 | 0.99 → 1.00 |
| trip_count | 655 | 0.500 → 0.500 | 161 → 164 | 1.00 → 1.00 |
| scope_name(place) | 124 | 0.502 → 0.500 | 32 → 31 | 0.99 → 1.00 |
| refusal | 79 | 0.515 → 0.500 | | 0.97 → 1.01 |
| fare 측정 직접 레코드 | **0** | — | — | — |

1. **B는 의미 그룹 균형(그룹별 평균 위치 0.5)은 달성했지만 학습 스타일이 다른 레코드(teacher 장문 reasoning vs json_only)의 시간 배치를 크게 바꿨다.** 한 질문 안에서 teacher가 json_only보다 먼저 오도록 한 규칙(`within_key`)과 질문별 deficit 스케줄이 겹쳐, teacher 레코드는 학습 앞쪽·높은 LR 구간으로, json_only는 뒤쪽·낮은 LR 구간으로 이동한다. 이는 "의미만 균형 맞춘 순서"가 아니라 **학습 스타일과 LR 위상까지 바꾼 처치**다. A/B 비교의 해석에서 이 혼입을 분리할 수 없다.
2. **T1과 가장 가까운 학습 신호(billing contrast teacher 298개, "소속 택시…수입/매출" 계열)가 B에서 앞쪽으로 몰렸다**: 평균 위치 0.495 → 0.279, 마지막 25%에 5개(A 73개). 이후 약 70% 구간은 이들이 거의 등장하지 않고 json_only가 길게 이어진다.
3. 인접 구조: billing contrast teacher 이웃(앞·뒤 레코드)의 coarse 그룹은 B에서 trip_count 47.3%(A 31.7%), billing revenue 7.4%(A 10.5%)로 바뀐다(`stage1_billing_ct_neighbour_coarse.json`). 자기 그룹 직전 비율(prev_in_same_group)은 0.165 → 0.214.
4. 같은 질문 연속 최대 길이 ≤ 4, 모든 레코드 한 번씩(G2/G3) 등 사전 게이트는 만족한다. 문제는 게이트가 보지 않은 축(학습 스타일·LR 위상)이다.

## 한계
- B 순서는 seed마다 위 통계가 거의 같다(위치 SD ≤ 0.003) → **seed마다 달랐던 T1 결과(1102·211102는 붕괴, 2026131은 개선)는 이 노출 통계만으로는 설명되지 않는다.** 노출 편향은 "모든 B seed에 공통인 처치"이고, seed별 변동은 재학습 변동/초기 상태 영향과 구분되지 않는다(Stage 2·3).
- 노출과 정확도의 관계는 상관 관찰이며 인과 증명이 아니다(M1/M2 `inconclusive` 가능).
