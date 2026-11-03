# 근접 대조 보강 설계 초안(D6) — ablation_012(결정 262)

**설계 초안이다. 확정하지 않는다.** 결정 262 D6에 따라 이번 작업에서는 문항 작성과 teacher 수집을 하지 않았다. 이 문서에도 질문 문장은 없다. 진단 결과를 바탕으로 한 제안이며 판정이 아니다.

## 1. 근거(진단, `analysis/results_a12.json` `overrefusal_types`)

거부 표본은 V4 6 seed(o43·o1016·o7 + A0 o1102·o211102·o2026113)에서 모았다. 정답 호출 서명은 ablation_011 교차표 도구(`xtab_a12.classify`)로 분류했다.

| 셋 | 거부 표본 / 거부 아닌 표본 | 비율 | 가장 몰린 tool |
|---|---|---:|---|
| E1(valid98·aux·rdev 대조, k=4) | 90 / 4,056 | 2.22% | `get_trip_metrics` 16/120 = **13.3%**, `get_billing_metrics` 30/1,320 = 2.3% |
| CT10K(10,000, k=1) | 881 / 60,000 | 1.47% | `get_trip_metrics` 362/6,156 = **5.9%**(나머지 tool 0.25–2.2%) |
| H-dev(2,000, k=1) | 202 / 12,000 | 1.68% | `get_trip_metrics` 78/1,026 = **7.6%**(나머지 0.4–1.7%) |

- 세 셋 모두 과잉 거부는 `get_trip_metrics`(정답 metric은 거의 `fare`, 요금 통계)에 몰려 있다.
  - CT10K에서는 이 tool이 거부 아닌 표본의 10%이고, 거부 표본의 41%다(362/881).
  - 지역 유형은 **시도**가 가장 많다(CT10K 2.05%, 다른 지역 0.2–1.35%).
- 세부 칸(`detail`) 기준으로, 6 seed 모두에서 거부가 나온 칸은 다음과 같다.
  - CT10K: `get_trip_metrics fare` × {med, avg, min} × {일, 기간} × 시도, 4–16%.
  - E1: `get_billing_metrics revenue avg` 월 × 시도 20.8%.
  - H-dev: `fare avg` 일 × 지역 없음 18.3%(6 seed 중 5개).
- **V4 학습 데이터에는 정답 tool이 `get_trip_metrics`인 질문이 없다**(5.2절 학습 관련 표: same_tool 0).
  - CT10K seed 간 편차 상위 그룹 중 요금 그룹(`6c262dd5`·`bd605b0e`·`1c3cb876`·`449f5bf2`)도 같은 서명이다.
  - batch013 요금 지표 근접 대조(결정 243 c1)는 `get_billing_metrics`(수입·활성 택시·운행 일수)였다. 운행 요금(`get_trip_metrics fare`)은 대상이 아니었다.
- 시도 단위 요금 지표(`get_billing_metrics` × 시도)는 E1에서 월 단위 9.0%, H-dev에서 일 단위 5.3%로 두 번째 몰림이다.

## 2. 보강 대상 유형 후보(우선순위 순)

| # | 유형(정답 호출 서명) | 근거(거부 비율, 6 seed) | 짝지을 거부 패턴(겉모습이 비슷하지만 도구로 답할 수 없음) | 예상 문항 수 |
|---|---|---|---|---:|
| T1 | `get_trip_metrics` metric=fare × aggregation {avg, med, min, max} × 시간 {일, 기간, 주} × 지역 {시도, 없음} | CT10K 4–16%, H-dev 4–18%, E1 13% | 개별 단위(기사·차량별 요금), 예측(앞으로의 요금), 지표 밖(팁·할증 내역 등 계약에 없는 요금 항목) | 36–48 |
| T2 | `get_trip_metrics` fare × 시군구·요일 유형(주말·휴일) | E1 12.5% | 위와 같음 + 묶음 단위 미지원(분기·시간대 bucket) | 8–12 |
| T3 | `get_billing_metrics` revenue·active_taxi_count·active_taxi_ratio × 시도 × {일, 월}, 차원 sido·dayofweek | E1 9–29%, H-dev 5–8% | 기사·회사별(개별 단위), 예측, 일 단위 값의 비지원 묶음 | 16–24 |
| T4 | `get_trip_count` 일 × 지역 없음·POI | E1 8.3%, CT10K 3.0%, H-dev 3.4% | 통행 목적·승객 속성(계약 밖 factor) | 8–12 |

- 합계 **약 70–95문항**이다.
- teacher 표본은 질문당 8개를 받고, 통과 trace는 결정 250처럼 질문당 최대 2개를 쓴다. 그러면 학습 레코드는 약 140–190개로 V4 1,984레코드의 7–10%다.
  - 근접 대조 비중은 A3/A3R 진단에서 정답률·과잉 거부와 함께 움직였다. 넣는 양은 V4 근접 대조 408레코드에 비해 크지 않게 잡았다.
- 장소·기간·묶음 길이는 batch012·013 작성 규칙과 같게 한다: mock 안 장소, mock 실행 조합, 기간과 묶음 길이 맞춤.
- 거부 패턴 목록(`pilot_009/protected_final_v2_pc_patterns.md`)에 해당하는 조합은 쓰지 않는다. 겹침 검사 대상은 RC7·batch011–013·refusal_dev v1·v2·**H-dev·H-final·CT10K**다. H-final은 문항 내용을 열지 않고, 도구가 정규화 문자열과 정답 뼈대만 비교한다.

## 3. 필요한 수집과 준비

| 단계 | 내용 | 필요 자원 |
|---|---|---|
| 작성 | T1–T4 초안(질문 + 정답 grounding), 검증 사슬·compile·mock 실행 통과, 겹침 검사 | CPU, 사람 검토(승인은 사용자) |
| teacher 수집 | 지시 `teacher_contrast_v2`(결정 248) 그대로, 질문당 표본 8, 연속 방식(결정 79), 결정 55 guard | **Ollama 컨테이너 복구가 먼저 필요하다.** 2026-10-29에 사람이 컨테이너를 내렸다. Claude Code는 컨테이너를 올리거나 바꾸지 않는다(CLAUDE.md 규칙 4). |
| 자체 표본 | base 정답 표본(8b, `json_only`), batch013과 같은 방식 | vLLM(HF 경로) GPU, Ollama 불필요 |
| 빌드 | V4 + 보강분(질문당 최대 2 trace), 유형 상한 C-1, 결정 250 빌드 검사 | CPU |
| 비교 | 안 2(V4 짝 비열등, CRITERIA_v2_DRAFT) — E1 + H-dev, seed 수는 검정력 결과에 따름 | GPU 3장 |

- teacher 없이 하는 대안도 있다. 자체 표본(`json_only`)만 넣는 것이다.
  - ablation_011 A1(근접 대조 teacher의 thinking 원문 학습을 끔)은 과잉 거부가 +10.5pp였다. 그래서 thinking 원문이 있는 teacher trace 쪽이 진단과 맞는다. 자체 표본만 넣으면 효과가 작을 수 있다.
- A3 − A3R 진단은 요금 대조의 고유 효과를 보였다(E1 정답률 −13.8, 과잉 거부 +12.1; H-dev −4.4, +3.0). 그러나 A3R은 근접 대조 비중이 A0보다 높아, 이 차이에는 근접 대조 전체 비중의 효과가 섞여 있다(RESULTS 1절).
  보강분을 넣을 때는 근접 대조 비중을 함께 보고하는 것을 권한다.

## 4. 사용자 결정(QUESTIONS.md 4)

1. 보강 대상 범위: T1만 / T1–T3 / T1–T4.
2. Ollama 컨테이너 복구 여부(teacher 수집에 필요). 복구하지 않으면 자체 표본만 쓸지.
3. 겹침 검사에 H-final을 넣는 방법(내용 비공개 비교 도구) 승인.
