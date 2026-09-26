# 두 단계 집계: 의미 graph와 TIMS 호출의 분리

> **정정(2026-09-26)**: 이 문서의 lowering 부분은 `tims_lowering_contract.md`가 대체한다.
> - 계약이 확인되지 않은 bucket/rollup 병합을 "경로·경계를 답변에 표시한다"로 정당화한 것(4·7절)은 틀렸다. 병합은 이제 기본 계약에서 쓰지 않는다.
> - 로컬 경로는 날짜 범위 호출이 아니라 일 단위 호출이다.
> - f03을 "golden 충돌"로 묶은 분류(6절)는 틀렸다(질문의 뜻으로 inner=sum이 정해진다).
>
> 아래 본문은 당시 기록으로 남긴다.

상태: 구현됨. production grounding prompt는 바꾸지 않았다(H0, sha256 앞 8자리 `64bbceb4`).
기준 commit: `c547e5c`. 재생 결과: `semantic_aggregation_graph_replay.json`.

## 1. 문제

`EVENT_TO_MEASURE` 변환 하나가 집계·구간·순위를 Tool 인자(`aggregation`, `bucket`, `rollup`,
`dimension`, `order`, `limit`)로 받았다. 계산 순서가 인자 셋으로 압축되어 다음이 드러나지 않았다.

| 질문 | 예전 표현 | 문제 |
|---|---|---|
| 주별 매출 합계의 평균 | `bucket=week, aggregation=sum, rollup=avg` | 중간 개념(주별 합계)이 graph에 없음 |
| (구간 안 집계 없음) `bucket=week, rollup=avg` | aggregation 생략 | Tool 기본값 avg가 조용히 구간 안 집계가 됨 |
| 합계가 가장 큰 **주** | 표현 불가 | rollup은 스칼라만 돌려줌. `rollup=max`로 적으면 값을 답함 |
| 법인택시 평균 속도 | `unused_factors={taxi_type}`로 기록 후 실행 | 조건을 잃은 채 전체 택시로 계산 |

## 2. 논문(§3.2–3.6, 부록 E·F)과의 대응

**논문에 명시된 것**

- G = (V, E, λ, ρ). node는 core concept와 functional role을 갖고, edge는 개념 변환이다(§3.2).
- G ↔ G′ factorization. 의미 graph를 operator–concept hypergraph로 바꾸고 factor node가
  보조 parameter를 나타낸다(§3.3).
- G1–G5(비순환, role 순서, 타입, 실행 가능성, 연결성)(§3.3).
- macro-template `g_k = (V_k, E_k, in_k, out_k)`. 목록에 FILTER-AGGREGATE-MEASURE가 있다(§3.4, 부록 E).
- 위상 순서로 실행하고 모든 중간 상태를 trace에 남긴다. 답변은 그 trace에 근거한다(§3.6, 부록 F).

**이 프로젝트의 설계 선택**

- 구간별 중간 값은 새 core concept가 아니라 측정값과 같은 `(AMOUNT, revenue)`에 속성
  `group_by={"bucket": "week"}`를 붙여 나타낸다.
- 그 node의 role은 SUPPORT다. 부록 B.2의 SUPPORT("파생 개념을 계산하는 기반")에 해당하기
  때문이며, G2를 통과시키려고 고른 것이 아니다. COND로 두면 EVENT(SUPPORT) → COND가 되어 G2를
  위반한다. 그러나 선택 근거는 정의이지 이 검사가 아니다.
- 기간·택시 유형 같은 조건은 논문의 TEXTENT node가 아니라 factor node(transformation params)로
  남겼다. 기존 구조를 유지하기 위해서다(차이점은 7절).
- G7_AGGREGATION_SEMANTICS를 새로 두었다. 논문에 없는 규칙이다.
- 로컬 분해의 주 경계(월요일 시작, 기간 경계에서 자름)와 상대 기간 해석(last_month = 기준일
  전달)은 이 프로젝트가 정한 것이다. TIMS schema에는 bucket 경계가 적혀 있지 않다.

## 3. 구조

```text
grounding (H0 flat factor | 구조화 aggregation_plan, 테스트·후속 arm 전용)
  ↓ geoflow/aggregation.py      AggregationSpec(bucket, inner, outer, select)
  ↓ composer                    목표 조각을 집계 형태로 고름
                                EVENT_TO_MEASURE (scalar) | EVENT_TO_GROUPED_MEASURE (grouped)
GeoFlowPlan = 의미 graph G
  ↓ validator G1–G7
  ↓ compiler lowering           합칠 수 있으면 TIMS 호출 하나 / 아니면 기간 분할 + 로컬 계산
  ↓ verify_lowering             실행 단계가 G의 조건·집계를 빠짐없이 옮겼는지 대조
ExecutionPlan = G′  (step.covers, argument_sources, semantic_map, unobserved, periods)
  ↓ executor                    tool step + local step(COLLECT_GROUPS, REDUCE_GROUPS, SELECT_GROUP)
  ↓ answer                      기간(해석한 날짜)·범위·택시 유형·집계 뜻·계산 경로·구간별 값
```

| 파일 | 역할 |
|---|---|
| `geoflow/aggregation.py` | 집계 의미 표현, flat → spec 결정적 lift, 구조화 표기 parser |
| `geoflow_macros/event_to_grouped_measure.yaml` | FILTER-AGGREGATE-MEASURE 조각. 내부 node `groups` |
| `geoflow/macros.py`, `geoflow/composer.py` | 조각 안의 변환 사슬, `same_type_as`/`grouped`, 집계 형태로 조각 선택, 분석 연산자 binding, 소비되지 않은 조건 거부 |
| `geoflow/analysis_ops.py` | 로컬 분석 연산자. prompt 어휘(`OPERATORS`)와 분리 |
| `geoflow/operator_registry.py` | `BucketRollup` 선언(get_operation_metrics), count Tool의 `inherent_reducer="sum"`, `TOOL_DEFAULT_REDUCER` |
| `geoflow/validator.py` | G7 |
| `geoflow/periods.py` | 기간 해석, 구간 분할 |
| `geoflow/compiler.py` | lowering, `verify_lowering` |
| `geoflow/executor.py` | local step 실행, trace에 `phase`/`covers`/`group`/`output_nodes` |
| `geoflow/answer.py` | 구간별 답변, 한 단계 기본값 안내 |

## 4. 대표 질문: "지난달 대구 개인택시 매출 합계가 가장 큰 주는?"

정답 grounding(구조화 표기):
`factors = {date: last_month, taxi_type: private, aggregation_plan: {bucket: {unit: week, reducer: sum}, result: {select: max}}}`

의미 graph G:

```text
[place]          LOCATION/place   SUBCOND  user
[place_scope]    LOCATION/scope   COND     tool
[operation]      EVENT/operation  SUPPORT  implicit
[revenue_groups] AMOUNT/revenue   SUPPORT  tool     group_by={bucket: week}
[revenue]        AMOUNT/revenue   MEASURE  derived  returns=group

(resolve_scope)  RESOLVE_PLACE_SCOPE(place) → place_scope
(measure_groups) OPERATION_METRIC(operation, area←place_scope)
                 {metric: revenue, date: last_month, taxi_type: private, aggregation: sum} → revenue_groups
(combine_groups) SELECT_GROUP(revenue_groups) {select: max} → revenue
```

실행 계획 G′(기준일 2026-09-25):

```text
resolve_scope          get_place_scope(name=대구)                       covers=[resolve_scope]
measure_groups#1..#6   get_operation_metrics(scope, metric=revenue, taxi_type=private,
                       aggregation=sum, date=20260801-20260802 … 20260831-20260831)
                                                                        covers=[measure_groups]
measure_groups.collect local:COLLECT_GROUPS                              covers=[measure_groups]
combine_groups         local:SELECT_GROUP(select=max)                    covers=[combine_groups]
```

"주별 합계의 평균"은 같은 G 모양에 `REDUCE_GROUPS(reducer=avg)`를 쓴다. TIMS가 `bucket_rollup`을
선언했으므로 두 의미 단계가 호출 하나(`bucket=week, aggregation=sum, rollup=avg`)로 합쳐진다.
`argument_sources`에 `rollup ← combine_groups.params.reducer`가 남고, 구간별 값은 `unobserved`로
기록된다.

## 5. 거부 규칙

| code | 조건 |
|---|---|
| `AMBIGUOUS_INNER_AGGREGATION` | 구간이 있는데 구간 안 집계가 없음. 재질의하지 않음(L1이 구간 안 집계를 지어냈다) |
| `UNSUPPORTED_GROUPED_MEASURE` | 구간 안 집계를 받지 않는 Tool(개수 Tool), 또는 기간을 받지 않는 Tool |
| `UNSUPPORTED_AGGREGATION_COMBINATION` | 구간 + dimension/order/limit. schema에 없고 mock은 거절 |
| `UNSUPPORTED_AGGREGATION` | 그 측정값에 구간별 조각이 없음 |
| `UNCONSUMED_CONDITION` | 조건을 받는 변환이 없음. `taxi_type=all`처럼 조건을 걸지 않는 값과, 개수 Tool의 고유 집계(sum)는 예외 |
| `UNRESOLVED_PERIOD` | 로컬 분해가 필요한데 기간이 없거나 상대 기간을 풀 기준일이 없음 |
| `UNSUPPORTED_PERIOD_FOR_GROUPING` | weekday/weekend/holiday를 구간으로 나누려 함 |
| `LOWERING_MISMATCH` | 실행 단계가 G의 조건·집계·구간 분할과 다름 |
| `EMPTY_GROUP_VALUE`, `NON_SCALAR_GROUP_VALUE` | 구간 값이 없거나 스칼라가 아님. 0으로 채우지 않음 |

구간이 없는 한 단계 질문에 집계어가 없으면 기존대로 Tool 기본값(avg)을 쓴다(호환). 답변에
"질문에 집계 방식이 없어 TIMS 기본값(평균)이 적용되었습니다"라고 밝힌다.

## 6. 검증

**정답 grounding(LLM 없음)** — `tests/test_geoflow_aggregation_graph.py`, 46건. 구간마다 표본 수와
값이 다른 고정 자료를 쓰고 기대값은 손으로 계산했다. 합계 평균 1100/6, 평균 최댓값 300(W2),
전체 평균 1100/13 ≠ 평균의 평균 625/6, 최댓값 360과 그 주 W3, 합계 최대 주(W3) ≠ 평균 최대 주(W2),
조건 보존(조건을 빼면 W2/5300이 된다), 거부 경로, lowering 변조 탐지, trace 연결, scope provenance를 본다.

**기록된 LLM 응답 재판정(LLM 호출 없음)** — `geoflow_replay_compare.py`. development census이며
holdout이 아니다. 기준선은 `c547e5c` worktree에서 같은 스크립트로 계산했고, 그 결과는 기존
`failure_census.py` 결과와 같았다(M0: CORRECT 159 / SILENT 11 / …).

| run | model | 조용한 오답 | CORRECT | 계획 없이 거부한 지원 질의 |
|---|---|---|---|---|
| M0 census (210) | qwen3:8b | 11 → 6 | 159 → 153 | 9 → 20 |
| M2 census (211) | qwen3.8:27b | 8 → 8 | 180 → 156 | 0 → 24 |

바뀐 관측은 모두 `AMBIGUOUS_INNER_AGGREGATION`이다.

- 조용한 오답에서 거부로 바뀐 것(M0 5건): f01 ×4("월 단위로 **합산한** 수입의 평균", 모델이
  aggregation=sum을 빠뜨림), b24_p5.
- 정답에서 거부로 바뀐 것
  - **golden과 충돌(M0 5, M2 24)**: b21, b24, f03, f13, h12. corpus golden이 구간 안 집계를
    `unspecified`로 두고 Tool 기본값(avg)으로 실행되는 호출을 기대한다. 이번 요구("질문에 없는 집계를
    기본값으로 추측하지 않는다")와 정면으로 충돌한다. corpus 파일(sha256 고정)과 채점 규칙은 고치지
    않았다. 테스트는 `paraphrase_corpus.golden_inner_unspecified`로 이 intent를 구조에서 찾아 거부를
    확인한다.
  - **기본값과 우연히 일치(M0 f02_p1)**: 질문은 "주 단위로 평균 낸 뒤 최댓값"이고 모델은 aggregation을
    빠뜨렸다. Tool 기본값 avg가 golden과 같아 정답으로 세어졌다.
- 남은 조용한 오답은 모두 grounding 단계에서 생긴다. 결정적 계층은 grounding이 적은 뜻을 그대로
  옮길 뿐이다.
  - 두 단계 뒤바뀜: b24_p3, M2 f01_p3(`aggregation=avg, rollup=sum`)
  - taxi_type 누락: h04_p3, h12_p1, f13_p0
  - 범위 밖 비교·분포: f14, f15, h15

**live 동작 확인** — production 경로(H0 prompt, qwen3:8b, mock provider)로 대표 질문 4개를 한 번씩
실행했다. 측정이 아니다. 두 단계 질문 둘은 호출 하나로 합쳐져 실행됐다. "전체 매출의 평균"에서는
모델이 개인택시 조건을 grounding에서 빠뜨렸다. "합계가 가장 큰 주"에서는 모델이 order/limit을
적어 재질의 뒤 `INVALID_FACTOR_COMBINATION`으로 거부됐다. 이때 CLI 이벤트 처리기가 계획 단계
재질의 payload에서 `KeyError: 'concept'`로 멈추는 기존 버그가 드러나 고쳤다.

## 7. 남은 차이와 제한

- production grounding(H0 flat)은 "가장 큰 **주**"(SELECT_GROUP)를 표현할 수 없다. 구조화 표기는
  테스트와 이후 arm에서만 읽는다(`parse_grounding(..., structured_aggregation=True)`). production에
  넣으려면 fresh holdout에서 사전 등록한 판정 규칙으로 격리 측정해야 한다(H2 되돌림의 교훈).
- flat 표현에서 두 단계가 뒤바뀐 grounding(`aggregation=max, rollup=sum`)은 구조로 구분할 수 없다.
- golden 충돌 intent를 두고 제품 규칙과 corpus 중 무엇을 바꿀지는 사람이 정할 일이다.
  - 안 A: corpus를 새 버전으로 쓰고 이 intent의 기대 결과를 "되묻기"로 바꾼다.
  - 안 B: 측정값별로 "집계"라는 말을 합계로 읽는 규칙을 명시한다. 이것도 추측이므로 근거가 필요하다.
- 주 경계: 로컬 분해는 월요일 시작이다. TIMS bucket=week의 경계는 모른다. 그래서 같은 뜻이라도
  경로(호출 하나로 합침 / 기간 분할)에 따라 구간이 다를 수 있고, 답변은 경로와 경계를 함께 밝힌다.
  `last_month`는 로컬 분해에서만 기준일 전달로 풀고, 합친 호출에서는 TIMS가 해석한다.
- 기간·택시 유형은 논문의 TEXTENT/COND node가 아니라 factor node다. 조건 손실은 G5가 아니라
  `UNCONSUMED_CONDITION`과 `verify_lowering`이 잡는다.
- 공간 그룹(dimension)과 순위는 여전히 한 변환의 factor다. 결과가 곧 분포이고 다시 합치는 단계가
  없어 계산 순서를 잃지 않지만, 논문식으로 node를 나누지는 않았다.
- 구간별 개수(통행량 등)와 구간 × 공간 그룹은 거부한다.

## 8. 검색 기반 조합을 위한 확장 지점

- `MacroTemplate.aggregation`은 조각을 고르는 첫 filter다. 질문–graph 예시 검색(부록 E.1)이 붙으면
  검색된 예시의 조각 목록으로 후보를 좁히고, 이 filter와 port 계약이 그 결과를 다시 검증하면 된다.
- 조각 안의 변환 사슬(`_apply_key`)과 `same_type_as`/`grouped`는 조각 정의만으로 다단계 템플릿을
  늘릴 수 있게 한다(예: 구간별 비율, 구간 간 비교). 로컬 연산은 `analysis_ops`에 추가한다.
- `AggregationSpec`은 grounding 표기와 독립적이다. 검색된 예시 graph를 spec으로 바꾸면 같은
  composer·validator·lowering을 그대로 탄다.

## 9. 재현

```bash
python -m unittest discover -s tests -t .
python -m unittest tests.test_geoflow_aggregation_graph

git worktree add --detach /tmp/base c547e5cb1f4561f783b0e201cf1d3891416d3d57
cp geoflow_replay_compare.py /tmp/base/
RUN=$PWD/evaluation/prompt_ab/20260925_171514_model_M0_census
(cd /tmp/base && python geoflow_replay_compare.py $RUN --out /tmp/base.json)
python geoflow_replay_compare.py $RUN --out /tmp/head.json
python geoflow_replay_compare.py --diff /tmp/base.json /tmp/head.json
```

미실행: 구조화 집계 표기를 prompt에 넣은 grounding arm의 LLM 측정. 이 측정을 하려면 먼저 다음을
갖춰야 한다.

- fresh holdout (argmax 질문 포함)
- 판정 규칙의 사전 등록
- `evaluate_prompt_ab.py`에 arm 등록

그 뒤 `python evaluate_prompt_ab.py …`로 isolated_state_v1 측정을 한다.
