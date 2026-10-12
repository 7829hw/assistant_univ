# P0.3 실패 원인 분석

2026-10-12. 기존 sel154 결과(commit `7baf67b`)만 다시 읽었다. 새 모델 호출, 재측정, prompt·gold·parser 수정은 없다.

- 산출물: `root_cause.json`, `root_cause_items.csv`(154문항 전체, dt 문항은 패턴·실패 분류 포함), 스크립트 `root_cause.py`.
- 모든 분류는 결과를 본 뒤의 진단이다. gate나 판정에 쓰지 않는다.
- 기준점(바꾸지 않음):
  - P0.3 `8b157c9a`, fingerprint `ab88a19e`.
  - semantic correctness: Full 71.82 / P0 71.30 / P0.3 71.69%.
  - dimension_target 누락: 27 / 26 / 43%.
  - week/month-as-dimension: 5 / 4 / 13.

## 1. 결론

- **thinking 원문이 기록되지 않았다.**
  - `evaluate_vendor100.py`는 `thinking_chars`만 남긴다.
  - 그래서 Type I(알고도 빠뜨림)과 Type II·III(의미 구분 실패)을 직접 가를 수 없다.
  - 5·6절은 thinking 길이와 첫 응답 JSON 구조로 대신 분석했고, 그 한계를 그대로 적는다.
- **dimension_target 누락 증가는 role 제거 때문이 아니다.**
  - P0도 role·Full schema가 없지만 dt 누락이 Full과 같다(26 vs 27%).
  - scope 역조회 문항의 답 place concept도 P0에서는 10회 중 9회 유지된다.
  - 증가분은 P0 → P0.1/P0.2/P0.3로 이어진 Partial 경계 규칙 계열에서 생겼다.
    - vendor100 기록(0.40.1): Full 11, P0 9, P0.1 29, P0.2 34.
    - sel154에서 P0.3 − P0 = +17건.
- **증가분은 '사건 표현' 문항에 몰려 있다.** 끝점이 사건 안에 들어 있는 질문이다(예: "승차가 가장 많은 읍면동", "내린 위치를 H3 셀 기준으로").
  - 이 유형의 누락률: Full 34.5%, P0 29.1%, P0.3 61.8%.
  - 명시적 그룹 표현과 both 유형에서는 P0.3가 더 나쁘지 않다. both는 세 arm 모두 누락 0이다.
- **실패 형태는 끝점 정보를 첫 응답에서 통째로 빼는 쪽이다(43건 중 33건).**
  - od_role만 쓰고 dt를 빼는 형태(사용자 지시 Type II 후보)는 10건뿐이다.
  - 첫 응답에 dt가 들어 있는 비율은 Full 70%, P0 67%, P0.3 53%다. 목적지를 명시한 rule 11이 dt 출력을 오히려 줄였다.
- **sampling noise가 주원인이 아니다.**
  - P0.3는 문항 단위로 덜 불안정하다. 불안정 문항은 28개로 Full 35개보다 적다.
  - dt 누락의 절반 가까이(20/43)는 5회 모두 누락한 문항 4개에서 나왔다.
  - 회차 간 흔들림(66.9–76.0%)은 독립 가정 기대보다 크다(p ≈ 0.04, 보정 없는 단일 검정). 근거는 약하다.
- **gold·계약 모호성은 일부다.**
  - gold_review_candidate는 n35("승차 건수"의 끝점 모호), k34("대구 안에서 출발과 도착이 다 이뤄진" 운행의 od_role=both 대 양쪽 scope 계약) 두 문항(누락 10건)이다.
  - both 유형 실패의 대부분도 같은 '구역 내부 이동' 계약 문제다(10절 J2).
- **추천:** prompt 규칙을 더하는 P0.4(후보 A)나 role-lite scaffold(후보 B)는 이 자료로 뒷받침되지 않는다. 짧은 계약 정리(후보 D) 뒤 Partial SFT(후보 C)를 검토할 것을 추천한다(12절).

## 2. 분석 대상

| 자료 | 내용 |
|---|---|
| raw | `raw/{full,p0,p0_3}_{greedy,sample_r1..r5}.json`. 문항별 첫 응답 원문(content), 재질의, 최종 grounding 차이, category, thinking_chars |
| gold | `sel154_gold.yaml`(154). dt 부분집합 20, bucket 24, refusal 10(PLAN 고정) |
| 기록 없음 | thinking 원문. HF·Ollama 어느 경로에도 없다. 새 호출 없이는 만들 수 없다 |

## 3. dimension_target 실패 분해

**dt 문항 표.**

- 첫 응답 패턴(sampling 5회):
  - `dt✓`: gold와 같은 dt
  - `dt✗(x)`: 다른 dt 값
  - `od만`: dt 없이 od_role만
  - `없음`: dt도 od_role도 없음
  - `dimension=x`: dimension에 끝점 값
- 실패 분류는 P0.3 실패 관측만 센다. 분류 정의는 아래 "실패 관측 분류" 표에 있다.

| item | 표현 | gold dimension | gold dt | gold od_role scope | k F/P0/P0.3 | Full 첫 응답 | P0 첫 응답 | P0.3 첫 응답 | P0.3 실패 분류 |
|---|---|---|---|---|---|---|---|---|---|
| old44/g12 | event | emd | pickup | pickup | 2/3/2 | dt✓3 없음2 | dt✓4 dimension=pickup1 | 없음2 dt✓2 od만1 | A2 B1 |
| contrast/c01a | event | emd | pickup | pickup | 4/4/2 | dt✓4 없음1 | dt✓4 dimension=pickup1 | dt✓3 없음2 | A2 G1 |
| contrast/c04b | both | emd | both | pickup+dropoff | 5/5/5 | dt✓5 | dt✓5 | dt✓4 od만1 | — |
| indepv2/n06 | event | emd | dropoff | dropoff | 2/1/3 | dt✓5 | dt✓4 od만1 | dt✓4 없음1 | A1 G1 |
| indepv2/n34 | event | emd | pickup | pickup | 1/2/2 | dt✓3 없음2 | dt✓3 없음2 | 없음3 dt✓2 | A3 |
| indepv2/n35 | event | sido | pickup | — | 0/0/0 | 없음4 od만1 | 없음4 dt✓1 | 없음5 | A5 |
| indepv3/m03 | event | h3 | dropoff | dropoff | 1/2/0 | dt✓3 없음2 | dt✓3 od만1 없음1 | 없음4 od만1 | A3 B1 E1 |
| indepv3/m04 | event | emd | pickup | pickup | 0/0/0 | 없음3 dt✓2 | dt✓3 od만2 | 없음4 dt✓1 | A4 G1 |
| indepv3/m05 | both | emd | both | pickup | 3/2/1 | dt✓5 | dt✓4 dt✗(dropoff)1 | dt✓5 | G4 |
| indepv3/m09 | explicit | emd | pickup | pickup+dropoff | 3/4/5 | dt✓4 od만1 | dt✓4 dimension=pickup1 | dt✓5 | — |
| indepv4/k26 | cross_end | sigungu | dropoff | pickup | 3/1/2 | dt✓4 없음1 | dt✓3 없음2 | dt✓4 od만1 | B1 G2 |
| indepv4/k27 | event | emd | pickup | pickup | 2/0/1 | dimension=pickup3 dt✓2 | dimension=pickup5 | dt✓2 없음1 od만1 dimension=pickup1 | A1 B1 C1 E1 |
| indepv4/k28 | event | h3 | dropoff | dropoff | 0/1/0 | dt✓2 없음2 od만1 | dt✓3 없음1 od만1 | od만3 없음2 | A2 B3 |
| contrast/c01b | event | emd | dropoff | dropoff | 5/3/5 | dt✓5 | dt✓4 없음1 | dt✓5 | — |
| contrast/c04a | both | emd | both | pickup+dropoff | 3/2/2 | dt✓4 없음1 | dt✓4 od만1 | dt✓4 없음1 | G3 |
| indepv2/n05 | event | h3 | dropoff | dropoff | 3/1/0 | dt✓4 없음1 | dt✓3 없음1 dimension=dropoff1 | 없음3 od만2 | A3 B2 |
| indepv2/n09 | both | emd | both | pickup+dropoff | 3/5/1 | dt✓4 없음1 | dt✓3 od만1 없음1 | dt✓4 없음1 | G4 |
| indepv3/m02 | cross_end | sigungu | dropoff | pickup | 3/1/2 | dt✓3 od만2 | od만3 dt✓2 | dt✓2 없음2 od만1 | A2 B1 |
| indepv4/k33 | both | emd | both | pickup+dropoff | 1/2/2 | dt✓5 | dt✓5 | dt✓4 없음1 | G3 |
| indepv4/k34 | explicit | sigungu | dropoff | pickup+dropoff | 0/0/0 | 없음3 dt✗(both)2 | dt✗(both)3 없음2 | 없음3 dt✗(both)2 | A5 |

**실패 관측 분류(dt 부분집합, sampling 합계):**

| 분류 | 정의 | Full | P0 | P0.3 |
|---|---|---:|---:|---:|
| A | 최종 dimension_target 누락이고 첫 응답에 od_role도 없음 | 22 | 13 | **33** |
| B | 최종 dimension_target 누락이고 첫 응답에 od_role만 있음 | 3 | 10 | 10 |
| C | 첫 응답 dimension에 pickup/dropoff/both | 3 | 9 | 1 |
| D | 잘못된 dimension_target 값(최종) | 0 | 0 | 0 |
| E | 최종 grounding 없음(measure·place 등에서 막힘) | 6 | 12 | 2 |
| F | grounding은 맞고 downstream에서 실패 | 0 | 0 | 0 |
| G(보조) | dimension_target은 맞고 다른 요소가 틀림 | 22 | 17 | 19 |

- 분류는 C > E > A·B > D > F > G 순서로 하나만 붙인다.
- k34의 첫 응답 `dt=both`는 최종 grounding에서 dropoff 누락으로 잡혀 A로 셌다.
- P0.3의 증가는 A(+11, Full 대비)에 몰려 있다. P0의 약점이던 C(9)와 E(12)는 P0.3에서 거의 사라졌다(1, 2).
- 정리하면, rule 11은 "dimension에 끝점을 넣지 말라"는 쪽은 지켜졌다. 그러나 "dimension_target에 적으라"는 쪽은 사건 표현에서 지켜지지 않았다.

## 4. 질문 표현 유형별 결과

유형은 질문 문장만 보고 사후에 하나씩 붙였다(`root_cause.py`의 `EXPRESSION`).

| 유형 | 문항 | 지표 | Full | P0 | P0.3 |
|---|---|---|---:|---:|---:|
| 1. 명시적 그룹 표현(끝점이 그룹 단위를 직접 꾸밈: "승차 동네", "내린 구 기준") | m09, k34 | 정답률 | 30% | 40% | 50% |
| | | dt 누락률 | 60% | 50% | 50% |
| | | od_role-only | 10% | 0% | 0% |
| | | 첫 응답 dimension=끝점 | 0% | 10% | 0% |
| 2. 사건 표현에 끝점(그룹 단위는 따로) | g12, c01a, c01b, n06, n34, n35, m03, m04, k27, k28, n05 | 정답률 | 36.4% | 30.9% | 27.3% |
| | | dt 누락률 | 34.5% | 29.1% | **61.8%** |
| | | od_role-only | 3.6% | 9.1% | 14.5% |
| | | 첫 응답 dimension=끝점 | 5.5% | 14.5% | 1.8% |
| 3. 장소 제한 끝과 그룹 끝이 다름 | k26, m02 | 정답률 | 60% | 20% | 40% |
| | | dt 누락률 | 20% | 50% | 40% |
| | | od_role-only | 20% | 30% | 20% |
| | | 첫 응답 dimension=끝점 | 0% | 0% | 0% |
| 4. both(노선·경로·짝) | c04a, c04b, n09, k33, m05 | 정답률 | 60% | 64% | 44% |
| | | dt 누락률 | 0% | 0% | 0% |
| | | od_role-only | 0% | 8% | 4% |
| | | 첫 응답 dimension=끝점 | 0% | 0% | 0% |

- **명시적 그룹 표현:** 사용자 정의의 "승차 지역별"과 같은 문자 그대로의 표현은 sel154 dt 문항에 없다. 가장 가까운 꼴(끝점 + 그룹 단위)인 m09·k34 두 문항만 이 유형에 들어간다.
- **보조 묶음(사용자 유형 3, 장소 제한 + grouping 동시 존재, 겹침 허용):**

  | 묶음 | 문항 수 | dt 누락률 Full / P0 / P0.3 |
  |---|---:|---|
  | 같은 끝(장소 pickup + pickup 기준) | 12 | 35.0 / 28.3 / 56.7% |
  | 다른 끝 | 2 | 20 / 50 / 40% |
  | od_role scope 없음(n35) | 1 | 80 / 80 / 100% |

- **해석:**
  - P0.3의 누락은 "장소를 X 끝으로 제한하고, 같은 X 끝으로 묶는다"는 같은 끝 사건 표현에 몰린다.
  - 이때 한 단어("승차", "내린")가 od_role과 dimension_target 두 곳에 함께 쓰여야 한다.
  - rule 11 B의 예시는 "승차 지역별"처럼 그룹 표현이 따로 있는 꼴뿐이다. 모델이 사건 표현 안의 끝점을 그룹 기준으로 일반화하지 못한 것과 맞아떨어진다(사후 해석).
- **both 유형:** dt는 세 arm 모두 거의 완벽하다. P0.3의 낮은 정답률은 '구역 안에서만 오간' 운행의 places 계약 문제다(G, 10절 J2).

## 5. thinking 비교

thinking 원문은 기록에 없다. 사용자 지시 Type I–IV를 직접 판정할 수 없다. 대신 아래를 본다.

| thinking 대체 지표(첫 계획 호출, 문자 수 중앙값) | Full | P0 | P0.3 |
|---|---:|---:|---:|
| 전체 문항 | 2217 | 2228 | 1754 |
| dt 문항 | 2594 | 2260 | 1814 |
| dt 누락 관측 | 2970 (n=27) | 2398 (n=26) | 1868 (n=43) |
| 첫 응답에 dt가 있는 관측 | 2390 (n=70) | 2180 (n=67) | 1820 (n=53) |

- P0.3의 thinking은 문항 전반에서 약 20% 짧다. dt 문항만의 현상이 아니다.
- P0.3 안에서는 누락 관측과 dt를 낸 관측의 thinking 길이가 거의 같다(1868 vs 1820). "생각을 덜 해서 빠뜨린다"는 근거는 없다.
- Full에서는 누락 관측의 thinking이 오히려 길다(2970 vs 2390). 어려운 문항에서 망설이다 빠뜨리는 쪽에 가깝다.
- Type별 대체 근거(첫 응답 구조 기준, 확정 아님):

  | Type | 대체 근거 | P0.3 관측 |
  |---|---|---|
  | Type I(알고도 출력에서 빠뜨림) | 같은 문항의 다른 회차에서 dt를 냈음 | 누락 23건(9문항). "모델이 할 수는 있다"는 근거일 뿐, 그 관측의 thinking에 dt 판단이 있었는지는 알 수 없다 |
  | Type II(od_role로만 해석) | 첫 응답에 od_role만 있음 | 10건 |
  | Type III(질문을 다른 의미로 해석) | — | thinking 없이 구분 불가. A 33건 안에 섞여 있다 |
  | Type IV(다른 factor와 혼동) | 첫 응답 dimension=끝점(1건), week/month→dimension(bucket, 13건) | bucket 쪽은 repair로 최종 오류 0 |

## 6. Full / P0 / P0.3 reasoning 차이

Full의 첫 응답은 모든 dt 관측(100/100)에서 다음 구조를 쓴다.

- 암묵적 사건 concept `{"concept": "EVENT", "subtype": "trip", "role": "SUPPORT"}`
- 측정값 concept `role: MEASURE`
- 장소 concept `role: SUBCOND/COND`

P0(1/100)과 P0.3(0/100)에는 이 사건 concept가 없다.

| | Full | P0 | P0.3 |
|---|---:|---:|---:|
| trip 사건 concept 있음(dt 문항 첫 응답) | 100% | 1% | 0% |
| 첫 응답에 dt 있음(dt 문항) | 70% | 67% | 53% |
| 최종 dt 누락 | 27% | 26% | 43% |

- **role/schema scaffold 손실 가설은 dt에 대해서는 뒷받침되지 않는다.**
  - role과 사건 concept를 모두 잃은 P0가 dt 누락에서 Full과 같다(26 vs 27%).
  - scope 역조회에서도 P0는 답 place를 유지한다(10절).
  - 문항 단위로 P0 누락이 Full보다 많은 문항(n05, n06, m02, k26)은 있지만, 합계로는 상쇄된다.
- **P0와 P0.3의 차이는 role이 아니라 output_format 규칙이다.**
  - P0.1 교체안이 들어왔다. 그 규칙 4는 "pickup·dropoff·both는 장소의 od_role"이라고만 하고 dimension_target은 말하지 않는다.
  - 그 위에 P0.2 규칙 10과 P0.3 규칙 11이 더해졌다.
  - sel154에는 P0.1·P0.2 측정이 없어서 이 안에서 어느 규칙이 기여했는지는 가를 수 없다. vendor100(0.40.1)에서는 P0.1에서 이미 누락이 늘었다(9 → 29).
- thinking이 기록되지 않아 "Full은 MEASURE/COND/SUPPORT 단계로 정리하는데 P0.3는 바로 JSON 필드로 간다"는 가설은 이번 자료로 검증할 수 없다. 출력 JSON에 보이는 구조 차이만 확인된다.

## 7. sampling instability

문항별 k/5를 stable_correct(4–5), unstable(2–3), stable_wrong(0–1)으로 나눴다.

| 전체 154 | Full | P0 | P0.3 |
|---|---:|---:|---:|
| stable_correct | 95 | 95 | 99 |
| unstable | 35 | 34 | 28 |
| stable_wrong | 24 | 25 | 27 |
| 문항 Bernoulli 분산 평균 | 0.094 | 0.097 | 0.077 |
| 회차 정답률(%) | 72.1/70.1/73.4/70.8/72.7 | 71.4/72.7/71.4/70.8/70.1 | 69.5/66.9/73.4/76.0/72.7 |
| 관측 회차 SD / 독립 가정 기대 SD(%p) | 1.35 / 2.47 | 0.96 / 2.50 | 3.54 / 2.23 |

- **Full → P0.3 전이(전체):**

  | Full \ P0.3 | stable_correct | unstable | stable_wrong |
  |---|---:|---:|---:|
  | stable_correct | 81 | 11 | 3 |
  | unstable | 14 | 11 | 10 |
  | stable_wrong | 4 | 6 | 14 |

  - stable_correct → stable_wrong 3문항: n08, n40, k21.
  - stable_wrong → stable_correct 4문항: c07a, m12, m32, k02.
- **dt 부분집합:**
  - Full: stable_correct 3 / unstable 10 / stable_wrong 7.
  - P0.3: stable_correct 3 / unstable 8 / stable_wrong 9.
  - Full unstable → P0.3 stable_wrong: m05, k27, n05, n09.
- **dt 누락의 문항 내 일관성(5회 중 누락 횟수별 문항 수):**

  | 5회 중 누락 | 0 | 1 | 2 | 3 | 4 | 5 |
  |---|---:|---:|---:|---:|---:|---:|
  | Full | 8 | 4 | 4 | 2 | 1 | 1 |
  | P0 | 9 | 2 | 6 | 1 | 1 | 1 |
  | P0.3 | 7 | 2 | 2 | 3 | 2 | 4 |

- **해석:**
  - P0.3는 문항 단위로 더 불안정하지 않다. 오히려 맞거나 틀리는 쪽으로 더 굳는다.
  - dt 누락은 Full보다 결정적이다. 5회 모두 누락한 문항이 4개(n05, n35, k28, k34)로 Full의 1개보다 많다.
  - 회차 간 SD만 독립 가정 기대보다 크다(카이제곱 근사 p ≈ 0.04). 세 arm 중 하나에서 본 보정 없는 결과라 약한 근거다.
  - 같은 회차의 seed는 세 arm이 같고 문항마다 따로 정해진다. 문항 사이에 공유되는 회차 요인이 무엇인지는 이 자료로 알 수 없다.

## 8. greedy vs sampling

| 구분 | 정의 | 전체 Full / P0 / P0.3 | dt Full / P0 / P0.3 |
|---|---|---|---|
| greedy만 맞음 | greedy 정답, k ≤ 1 | 8 / 5 / 3 | 3 / 2 / 3 |
| sampling에서만 맞음 | greedy 오답, k ≥ 4 | 5 / 11 / 4 | 1 / 2 / 0 |
| 둘 다 안정적으로 틀림 | greedy 오답, k ≤ 1 | 16 / 20 / 24 | 4 / 7 / 6 |
| greedy 정답률 | | 77.9 / 68.8 / 74.0% | 50 / 25 / 45% |
| sampling 정답률 | | 71.8 / 71.3 / 71.7% | 44 / 39 / 35% |

- P0.3 greedy 74.0%는 sampling 회차 범위(66.9–76.0%) 안이다. greedy와 sampling이 다른 행동을 보인다는 근거는 없다.
- dt에서 P0.3의 "둘 다 안정적으로 틀림" 6문항은 n35, m03, m04, k28, n09, k34다. P0.3 dt 실패의 중심은 sampling noise가 아니라 결정적 실패다.
- greedy만 맞는 dt 문항(m05, k27, n05)은 P0.3가 할 수는 있지만 sampling에서 대부분 놓치는 경우다.

## 9. gold sanity check

대상은 dt 문항 중 P0.3 ≤ 1/5이고 Full ≤ 1/5인 5문항이다. gold를 수정하지 않았고, 아래는 질문 문장을 읽은 검토 의견이다(사람 승인이 아님).

| item | 질문 | 실패 원인(세 arm 합계) | 검토 | 표시 |
|---|---|---|---|---|
| indepv2/n35 | 휴일 아침 6–8시 승차 건수를 시도 단위로 비교, 제일 적은 두 곳 | 세 arm 모두 dt 누락(4/4/5) | "승차 건수"는 일상어로 "이용 건수"와 같은 뜻으로도 쓰인다. 그래서 결과를 승차 끝 시도로 묶으라는 뜻이 문장만으로 확실하지 않다. ontology상 gold(pickup)는 타당하지만 자연어상 모호하다 | **gold_review_candidate** |
| indepv3/m03 | 달서구에서 내린 손님이 가장 몰린 H3 셀 | dt 누락, no_grounding | "내린 손님이 몰린 셀"은 하차 끝 기준이 분명하다. Full greedy는 맞힌다 | 아님(모델 실패) |
| indepv3/m04 | 대구 중구 가운데 택시 승차가 가장 뜸했던 동 세 곳 | 세 arm 모두 order 5/5(bottom → top), dt 누락은 일부 | "가장 뜸했던"을 top으로 읽는 어휘 해석 실패다. gold의 order=bottom과 dt=pickup은 분명하다 | 아님(모델 어휘 실패) |
| indepv4/k28 | 대구 중구로 향한 손님들이 실제로 내린 위치를 H3 셀 기준으로 | dt 누락(P0.3 5/5) | 하차 끝 기준이 분명하다. Full greedy는 맞힌다 | 아님(모델 실패) |
| indepv4/k34 | 대구 안에서 출발과 도착이 다 이뤄진 운행을 내린 구 기준으로 세면 가장 적은 구 | 세 arm 모두 places 5/5(od_role=both 1개 대 gold pickup·dropoff scope 2개), dt는 both나 누락 | "내린 구 기준"은 분명하다. 그러나 '구역 안 이동'을 od_role=both 하나로 쓰는 것이 gold의 두 scope와 다른 것으로 채점되는 것은 평가 계약 문제다 | **gold_review_candidate**(계약) |

## 10. scope 역조회 실패

indepv2/n40 "scope:gz:3982는 어떤 장소야?", indepv4/k21 "…scope:district:2723010100 이라고 나와 있는데 이게 어느 동이야?". gold는 `get_scope_name(scope=…)`이다.

| | Full | P0 | P0.3 |
|---|---|---|---|
| 첫 응답 concept(sampling 10관측) | scope + 값 없는 place 10/10 | scope + place 9/10, scope만 1 | scope만 8/10, 빈 응답(거부) 2/10 |
| 첫 응답 오류 | 없음 | NO_MEASURE 1 | NO_MEASURE 8, UNSUPPORTED_QUESTION 2 |
| repair | 0 | 0 | 0(NO_MEASURE에는 재질의 경로가 없다) |
| 최종 | match 10/10, greedy 2/2 | match 9/10, greedy 2/2 | 0/10, greedy 둘 다 refused_unsupported |
| 첫 계획 thinking 길이(중앙값, 문자) | 2524 | 5080 | 1647 |

- **답:**
  - role이나 Full schema가 "답이 될 장소도 concept로 출력"하게 하는 scaffold라는 가설은 지지되지 않는다. role이 없는 P0도 답 place를 유지한다.
  - 차이는 P0 → P0.3 사이의 output_format 규칙에서 생긴다.
    - P0.1의 output_format 교체가 있다. 규칙 6에는 장소명 답 한 줄이 남아 있다.
    - rule 11 A의 예시는 모두 값이 있는 place다.
    - 이 가운데 어느 것이 원인인지는 가를 수 없다.
  - dimension_target과는 별개 문제이므로 같은 수정으로 묶지 않는다.

**J2(사후, 탐색): 구역 내부 이동 계약.**

- "대구 안에서 이동한", "수성구 안에서만 오간", "출발과 도착이 다 이뤄진" 같은 질문이다.
- gold는 같은 장소를 pickup·dropoff 두 scope로 둔다. 모델은 od_role=both 하나, pickup만, od_role 없음 중 하나로 쓴다.
- 이 문제는 c04a, n09, k33, k34에서 세 arm 모두에 나타난다. both 유형 G 실패의 대부분이다.

## 11. 원인별 기여도

**P0.3 최종 dimension_target 누락 43건.**

한 관측이 여러 원인에 들 수 있다. 분리되지 않는 것은 unclear로 남긴다.

| 원인 | 관측 | 대표 문항 | 근거 |
|---|---:|---|---|
| 1. instruction following | 확정 불가. 후보 23/43 | g12, c01a, n34, m03, m04, k27 | 같은 문항의 다른 회차에서는 dt를 냈다. thinking이 없어 "알고도 빠뜨렸는지"는 확인할 수 없다 |
| 2a. semantic distinction(끝점을 od_role로만 씀) | 10/43 | k28 3, n05 2 | 첫 응답에 od_role만 있음 |
| 2b. semantic ambiguity / gold·계약 | 10/43 | n35 5, k34 5 | gold_review_candidate 두 문항 |
| 2c. unclear(끝점 정보를 통째로 뺌) | 33/43 | n35, n05, m04, n34 | od_role도 dt도 없다. 의미 구분 실패인지 출력 누락인지 thinking 없이 가를 수 없다 |
| 3. schema scaffold loss(role 제거) | 합계 기여 0. 문항 단위 후보 10/43 | n05, n06, m02, k26 | P0 누락 26 = Full 27. 문항 단위로 P0 > Full인 문항이 있지만 상쇄된다 |
| 3'. Partial 경계 규칙 계열(P0.1 → P0.3) | P0 대비 +17 | k28 +4, n05 +3, g12 +3, c01a·m03·m04 +2 | 증가분이 사건 표현 같은 끝 문항에 몰린다 |
| 4. sampling instability | 23/43(문항 내 1–4회 누락) | g12, c01a, n34, m02 | 문항 단위 불안정성은 Full보다 낮다. 증가분의 주원인은 아니다 |
| 결정적 누락(5/5) | 20/43 | n05, n35, k28, k34 | sampling으로 설명되지 않는다 |

- **주원인:** Partial 경계 규칙 계열에서 생긴 사건 표현 끝점의 의미 구분·일반화 실패다(3' + 2a/2c). 결정적 형태로 나타난다.
- **role scaffold 손실과 sampling noise:** 주원인이 아니다.
- **gold·계약 모호성:** 일부(10/43)다.
- **instruction following:** thinking 기록 없이 비율을 확정할 수 없다.

## 12. 다음 실험 추천

이번 단계에서는 실행하지 않는다.

| 후보 | 조건 | 이번 자료 | 판단 |
|---|---|---|---|
| A. P0.4 destination clarification | 의미 구분은 하지만 JSON 목적지만 빠뜨림 | 끝점을 통째로 빼는 A형이 33/43이다. 목적지를 명시한 P0.3에서 첫 응답 dt가 오히려 줄었다(67 → 53%) | 비추천 |
| B. role-lite scaffold | role이 의미 구분 scaffold로 작동 | role 없는 P0가 dt 누락·scope 역조회에서 Full과 같다 | 비추천(dt 기준) |
| C. training(Partial SFT) | instruction은 명확한데 8B가 안정적으로 못 따름 | Full도 사건 표현 dt를 35% 놓친다. 규칙을 더할수록 다른 곳이 나빠진다(dt, scope 역조회) | **추천(주 방향)** |
| D. gold·task 모호성 정리 | 세 arm이 같은 문항에서 지속 실패 | n35, k34와 구역 내부 이동 계약(c04a, n09, k33)이 세 arm 공통 실패다 | **추천(C의 선행, 작게)** |

**추천 순서:**

1. **D(짧게):**
   - n35, k34와 '구역 내부 이동' 계약(od_role=both 대 pickup·dropoff 두 scope)을 사람이 검토한다.
   - 평가 계약을 확정한다. SFT는 계약을 학습시키므로 먼저 정해야 한다.
   - gold 변경은 사람 승인 뒤에만 한다.
2. **C 준비:**
   - Partial SFT 후보를 정할 때, 출력 계약의 출발점은 P0.3보다 P0가 근거가 있다.
     - P0는 semantic correctness(71.30%)와 dt 누락(26%)이 Full과 같고, JSON token은 −45%다.
     - P0.1 이후 규칙들은 dt·scope 역조회에서 새 오류를 만들었다.
   - 어느 쪽을 쓸지는 사용자 결정이다.
3. **측정 보강:**
   - 앞으로 모든 측정에서 thinking 원문을 기록하도록 harness 기록을 늘리는 것을 제안한다.
   - `evaluate_vendor100.py`는 code fingerprint 범위 밖이다. 출력에는 영향이 없고 기록 크기만 는다.
   - 그래야 Type I–IV를 직접 판정할 수 있다.
4. **하지 않는 것:** P0.4 작성, rule·예시 추가, HF reproduction, sel154 재측정, gold 수정.
