# 두 단계 집계 grounding: H1 재생 결과와 H2 설계 질문

상태: **설계 검토. 제품 구현 없음.**
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
