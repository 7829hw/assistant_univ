# 두 단계 집계 grounding: H1 재생 결과와 H2 설계 질문

상태: **H2는 production에 넣었다가 되돌렸다(8절). 현재 production은 H0.**
근거 run: `evaluation/prompt_ab/20260924_005520_census_head` (production, isolated_state_v1, 211 질문)
재생: `python aggregation_replay.py <run_dir>` → `aggregation_h1_replay.json`

## 1. 현재 의미 (코드 근거)

| 위치 | 내용 |
|---|---|
| `geoflow/factors.py` FactorSpec `aggregation` | "원시 값을 하나로 모으는 1차 집계. bucket이 있으면 각 구간 안에서, 없으면 전체에 적용. **질문에 집계 표현이 없으면 넣지 않는다**" |
| FactorSpec `rollup` | "bucket별 값들을 하나로 합치는 2차 집계. bucket과 짝으로만" |
| FactorSpec `bucket` | week, month. "구간마다 값을 먼저 구한 뒤 rollup으로 합친다" |
| FactorConstraint | `bucket → rollup`, `rollup → bucket` (H0). `describe_constraints()`로 system prompt에 들어간다 |
| operator | bucket을 받는 operator는 `OPERATION_METRIC` 하나 |
| `schemas/tims.yaml` `get_operation_metrics` | `bucket`: "지정 시 rollup 필수". `aggregation`: `pt_aggregation`, **default avg**. bucket이 aggregation을 요구한다는 말은 없다 |
| `mock_responses.py` | bucket↔rollup 짝을 검사, 구간 값들에 rollup 적용. `TOOL_DEFAULTS` aggregation avg |

실행 의미는 `원시 일 단위 값 --aggregation(기본 avg)--> 구간별 값 --rollup--> 최종 값`이다.
aggregation을 생략하면 Tool 기본값 avg가 적용된다.

## 2. H1 재생 결과 (LLM 호출 없음)

H1 = H0 + `bucket → aggregation`. bucket이 들어간 관측 32건을 분류했다.

| 분류 | 관측 | 내용 |
|---|---|---|
| H0이 이미 거부 | 17 | b21·b24·h12·f13. **17건 모두 바깥 집계 값을 aggregation에 적었다** (aggregation = 기대 rollup, rollup 없음) |
| 현재 조용한 오답, H1이 거부 | 5 | f01 ×4 (안쪽 `sum` 누락), b24_p5 (틀린 인자는 taxi_type, H1과 무관) |
| 현재 정답, H1이 새로 거부 | 6 | f03 ×4, b21_p4, f02_p1 (intent 3개) |
| H1에서도 유효, 정답 | 4 | b21_p0, f02 ×3 |

- 두 단계 집계 때문에 생긴 조용한 오답 5건(f01 ×4, b24_p3) 가운데 H1이 잡는 것은 **4건**이다.
- b24_p3의 첫 grounding(`aggregation=max`, rollup 없음)은 H0이 이미 거부했다. 재질의가 `rollup=sum`을 **덧붙여** 틀린 값이 됐다. 완성 patch는 값을 더하기만 하고 옮기지는 못한다. H1은 이 경우와 무관하다.
- H1이 새로 거부하는 6건 가운데 5건(f03 ×4 "월 단위 영업 횟수의 합계는?", b21_p4 "주 단위 집계 평균은?")은 질문에 안쪽 집계 표현이 없다. FactorSpec의 설명대로라면 aggregation을 넣지 않은 것이 **맞는 grounding**이다.
- f01의 틀린 grounding과 f03의 맞는 grounding은 구조가 같다(`bucket` + `rollup`, aggregation 없음). 차이는 질문에 "합산한"이 있느냐뿐이다.

## 3. H1 판정

| 채택 기준 | 결과 |
|---|---|
| 1. 두 단계 조용한 오답을 대부분 잡음 | 4/5 |
| 2. 기존 정답을 의미상 잘못 거부하지 않음 | **실패** (5건, intent 2개) |
| 3. 질문 문자열을 보지 않음 | 충족. 그러나 그래서 f01과 f03을 구분할 수 없음 |
| 4. factor 의미만으로 설명 가능 | **실패**. aggregation FactorSpec("표현이 없으면 넣지 않는다")과 모순됨 |
| 5. IR 변경 불필요 | 충족. 다만 FactorConstraint가 prompt에 들어가므로 prompt도 바뀜 |

**H1은 채택하지 않는다.**

## 4. H2가 필요한 근거 (`nested IR 도입 기준` 대조)

1. **inner/outer를 구조적으로 혼동함:** 17/17. 모델은 bucket이 있을 때 최종 집계를 `aggregation`에 적는다. bucket이 없을 때는 `aggregation`이 곧 최종 집계라서, 같은 이름이 bucket 유무에 따라 다른 단계를 뜻한다.
2. **flat 표현으로는 validator가 두 단계를 구분할 수 없음:** "안쪽을 생략함(질문에 없음, f03)"과 "안쪽을 빠뜨림(f01)"이 같은 모양이다.
3. **재질의가 어느 단계를 고치는지 모호함:** b24_p3. 바깥 값이 안쪽 자리에 있으면 완성 patch는 옮기지 못하고 새 값을 지어낸다.
4. **3단계 이상 집계:** 근거 없음. vendor 계약은 2단계까지다.

1~3의 근거가 있으므로 H2의 설계 질문에 답을 남긴다. 구현은 하지 않는다.

## 5. H2 후보: grounding 층에서만 두 단계를 명시

```yaml
factors:
  aggregation_plan:
    bucket: {unit: month, reducer: sum}   # 선택. 있으면 reducer 필수, "unspecified" 허용
    result: {reducer: avg}                 # 최종 집계. bucket이 있으면 필수
```

결정적 lowering (GeoFlowPlan, Transformation, Tool 계약은 그대로):

| grounding | lowering |
|---|---|
| `result.reducer` (bucket 없음) | `aggregation` |
| `bucket.unit` | `bucket` |
| `bucket.reducer` (`unspecified`면 생략 → Tool 기본 avg) | `aggregation` |
| `result.reducer` (bucket 있음) | `rollup` |

핵심은 **"최종 집계"를 가리키는 자리가 bucket 유무와 관계없이 하나**라는 점이다. 관측된 혼동 17건의 원인이 바로 이 이름 전환이다.

### 설계 질문에 대한 답

1. **bucket 없는 집계만:** `{result: {reducer: avg}}` → `aggregation=avg`.
2. **bucket + 안쪽 avg + 바깥 max:** `{bucket: {unit: week, reducer: avg}, result: {reducer: max}}` → `bucket=week, aggregation=avg, rollup=max` (f02).
3. **bucket + 안쪽 sum + 바깥 avg:** `{bucket: {unit: month, reducer: sum}, result: {reducer: avg}}` (f01).
4. **기본 avg를 명시하게 할지:** 명시하게 하지 않는다. 대신 bucket이 있으면 `bucket.reducer`를 필수로 두고 `unspecified`를 허용한다. 질문에 표현이 없으면 `unspecified`이므로 FactorSpec의 "지어내지 않는다"를 지킨다. 생략(빠뜨림)과 미지정(질문에 없음)이 서로 다른 모양이 된다. 다만 모델이 f01에서 `sum` 대신 `unspecified`를 고를 수도 있다. 결정적 보장이 아니므로 측정해야 한다.
5. **바깥 집계 없는 bucket:** 불법이다. vendor 계약("지정 시 rollup 필수")과 같다.
6. **전환 기간:** 두지 않는다. grounding 어휘에서 `bucket`·`aggregation`·`rollup`을 빼고 `aggregation_plan` 하나로 바꾼다. 세 이름은 GeoFlowPlan param과 Tool 인자로만 남는다.
7. **두 표현이 동시에 오면:** 고르지 않고 거부한다(기존 `UNKNOWN_FACTOR` 경로). authoritative source는 `aggregation_plan` 하나다.
8. **재질의 patch가 고치는 대상:** grounding 표현이다. 예를 들어 `aggregation_plan.bucket.reducer` 완성. lowering은 재질의가 끝난 뒤 한 번만 한다. 최종 집계 자리가 하나이므로 "값 옮기기" patch는 필요 없다(b24_p3 형태).

### H2의 비용과 조건

- grounding 계약이 바뀌므로 **system prompt가 바뀐다.** prompt 문구를 다듬는 것이 아니라 계약을 바꾸는 것이지만, production hash가 바뀌므로 isolated 측정이 필요하다.
- 측정 대상 cohort: b21, b24, h12, f13, f01, f02, f03 (development).
- 채택 판정용 **fresh aggregation holdout이 없다.** 측정 전에 새로 써야 한다.
- 영향 범위: grounding parser, FactorSpec과 FactorConstraint의 집계 부분, 재질의 완성 대상, `describe_*` prompt 렌더링. composer, operator, validator, compiler, executor는 바꾸지 않는다.

## 6. 하지 않은 것

- H1 제품 구현 (위 3번 이유)
- Phase B 격리 LLM 재질의 측정. 제품 후보가 없으므로 돌리지 않았다
- taxi_type 누락, 범위 밖 질의 뭉갬. 이번 범위가 아니다

## 7. H0 vs H2 측정 결과 (fresh holdout, 사전 등록 판정)

run `evaluation/prompt_ab/20260924_032103_aggregation_holdout_h0_h2_r2`, 요약 `aggregation_ab_summary.json`.
23 intent, 69 paraphrase × 2 arm. 무효 관측 4건(cold 첫 호출이 300초 안에 끝나지 않음, H0 3·H2 1)이 있는
paraphrase 4개는 두 arm 모두에서 뺐다(65 × 2).

| 지표 | H0 | H2 |
|---|---|---|
| 첫 응답 strict 정답 | 24 | 36 |
| 최종 strict 정답 | 26 | 36 |
| 조용한 오답 (관측) | 30 | 16 |
| 조용한 오답 intent | 14 | 9 |
| strict 정답 intent | 5 | 7 |
| 명시된 두 단계의 조용한 오답 | 17 | 11 |
| 단계 뒤바뀜 | 13 | 0 |
| 안쪽 집계 지어냄 | 0 | 0 |
| 구간 없음 strict 정답 | 11/12 | 12/12 |
| 재질의 | 15 | 0 |

판정은 Case A(검사 A~F 모두 성립)다. production 구현은 별도 단계에서 한다.

남은 한계:

- 질문에 적힌 구간 안 집계를 unspecified로 둔 조용한 오답 8건(a01, a04, a17, a19).
- "주마다"를 month로 읽은 3건. H0에도 같은 관측이 있다.
- 지원 범위 밖 질의를 계획으로 만든 5건. 두 arm 모두 같은 관측이다.
- "월별", "달마다" 같은 구간 표현을 dimension·date·time에도 적어 INVALID_FACTOR로 거부된 경우(H0 8, H2 9). 안전한 거부지만 두 arm에 공통인 새 family다.

## 8. production 통합과 되돌림 (422b952 → 244dabf)

422b952가 H2를 production grounding 계약으로 옮겼다(`geoflow/aggregation.py`, lowering 뒤
기존 경로). production system prompt는 측정한 H2_AGG와 byte 단위로 같았다(04d7baed).
재질의 문구는 그대로였다(5af4c744). 측정 뒤 acceptance guard E에 걸려 244dabf로 되돌렸다.
지금 production은 H0(64bbceb4)다.

통합 확인 (LLM 호출 없음):

- H0 census(20260924_005520)의 raw 응답 중 집계 factor가 없는 109건을 H2 경로로 재생하니 모두 같았다.
  flat 집계 factor가 있는 102건은 새 계약에서 `FLAT_AGGREGATION_FACTOR`로 거부된다. 계약이
  바뀐 결과이고 행동 회귀로 세지 않는다(`h0_raw_replay_under_h2.json`).
- corpus 네 개의 집계 golden 38개 모두 flat golden과 H2로 적어 내린 것의 Tool 호출이 같았다.

LLM 측정 (isolated_state_v1, 한 번씩, 판정용 아님):

| | 값 |
|---|---|
| aggregation corpus, production H2 (20260925_015316) | 유효 68/68 관측이 H2 arm과 같음(status, strict, silent, 예측 계획). 무효 a21_p1은 두 run 모두 같음 |
| census H0 → H2 (20260925_011212, 유효 209쌍) | strict 189 → 182, 첫 응답 strict 165 → 176, 조용한 오답 11 → 8, 조용한 오답 intent 7 → 5 |
| 단계 뒤바뀜 | 17 → 0 |
| 재질의 | 30 → 6 |
| 계획 없이 거부한 지원 질의 | 9 → 18 (INVALID_SUBTYPE 6 → 10, taxi_type을 개념으로 적음) |
| 실행 NOT_FOUND | 16 → 16 |

되돌린 이유는 H0 census에 없던 조용한 오답 구조가 H2 census에 생겼기 때문이다(guard E).
모두 질문 문자열이 아니라 grounding 구조로 판정했다.

| 관측 | 질문 | H2 grounding | H0 |
|---|---|---|---|
| f12_p0 | 지난주 영업 시간의 최소값은? | date=last_week + bucket week/unspecified + result min | 정답 |
| f04_p2 | 동대구역 평균 속도를 평일 기준으로 알려줘 | dimension=dayofweek, date 없음 | 정답 |
| h05_p2 | 공차율을 지난달 법인택시 기준으로 알려줘 | date=20260501-20260531 | 정답 |
| h06_p0 | 동대구역 주변 개인택시 통행량은? | taxi_type 없음 (기존 family) | 정답 |

H2에서만 조용한 오답인 intent는 네 개이고 모두 paraphrase 한 개다. H0에서만 조용한
오답이던 intent는 여섯 개가 해소됐다(b24, f13, f14, f15, h04, h12). 같은 prompt의 isolated
관측은 결정적이었다(aggregation corpus 68/68 일치). 그래서 이 차이는 표본 흔들림이 아니라
prompt가 바뀐 결과로 본다. f12_p0은 [집계 계획]의 구간 설명과 직접 관련된다. 나머지 둘은
날짜 조건이 흔들린 것이고 원인을 확정하지 않았다.

그대로 남은 것:

- f01 ×4: 질문에 적힌 구간 안 집계(합산)를 unspecified로 둔다. holdout과 같은 한계다.
- 구간 단위를 dimension·date·time에도 적는 경우는 census에 0건이다. aggregation corpus에서는
  14건(거부 11, 지원 범위 밖 거부 3)으로 측정 때와 같다. 모두 안전한 거부다.

## 9. 국소 집계 보정 L1 (evaluation-only, Case B로 폐기)

전역 H2의 비집계 부작용(8절)을 구조적으로 막으려고, 첫 grounding은 H0(64bbceb4) 그대로 두고
H0 grounding에 bucket이 있을 때만 집계 전용 호출(22c501ff)로 `inner_reducer`·`final_reducer`를
받아 aggregation·rollup만 고치는 L1을 쟀다(cb2d0e0, `aggregation_refinement.py`).

- trigger 재생(LLM 없음): H0 census 211 중 32 trigger, 단계 뒤바뀜 17/17, f12_p0·f04_p2·h05_p2·h06_p0 trigger 없음.
- fresh holdout `20260925_121002_local_aggregation_holdout_h0_l1` (24 intent × 3, 무효 쌍 l08_p2·l23_p1 제외 70쌍).
  첫 grounding 원문 70/70 동일. 보정 적용 33, fallback 0, scope 위반 0.

| | H0 | L1 |
|---|---|---|
| 최종 strict | 38 | 47 |
| 조용한 오답 | 19 | 14 |
| 조용한 오답 intent | 10 | 8 |
| strict 정답 intent | 10 | 12 |
| 집계 단계 조용한 오답 | 15 | 10 |
| 단계 뒤바뀜 | 5 | 0 |
| 명시된 구간 안 집계를 비움 | 7 | 0 |
| 구간 안 집계를 지어냄 | 4 | 9 |
| 계획 없이 거부한 지원 질의 | 13 | 9 |
| LLM 호출 / 총 지연 | 89 / 683초 | 104 / 677초 |

사전 등록 판정은 **Case B**(A·B 실패)다.

- A 실패: L1에서만 조용한 오답인 intent 2개. l09_p0("가장 높았던 주별 운행률")에서 구간 안 집계를
  max로, l12_p0·l12_p2("대구의 주별 영업 횟수 평균")에서 sum으로 지어냈다. H0는 셋 다 정답이었다.
- B 실패: 지원 범위 밖 대조군 l24_p1("지난주 대비 이번 주 수입 증가량")을 H0가 bucket으로 읽어
  보정이 불렸고 최종 인자가 바뀌었다. 두 arm 모두 조용한 오답이다.

L1은 명시된 두 단계(stage swap, 비워 둔 구간 안 집계)를 고쳤지만, 질문이 구간 안 집계를 말하지
않을 때 값을 지어내는 새 실패를 만들었다. production은 H0로 둔다.
