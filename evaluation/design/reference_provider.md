# reference provider와 provider별 실행 계약

상태: 2026-09-26. HEAD `0f2daaa` 위의 작업이다. 실제 TIMS 계약의 미확인 항목은 그대로 두었다.

이번 작업은 **명시적 계약을 가진 별도 실행 환경**을 만든 것이다. 그 위에서 의미 graph의 조합·lowering·
실제 계산·답변을 끝까지 검증했다. reference provider는 작은 **합성 데이터**를 계산한다. 여기서의 성공은
논문 재현도, 실제 TIMS 정확성의 검증도 아니다.

## 1. provider 계약과 질문 해석 옵션의 분리

**이전 상태(`0f2daaa`)의 문제.** condition_check를 켜면 compiler가 strict(`guaranteed`) 정책으로 바뀌었다.
그래서 해석 옵션 하나가 실행 가능한 연산을 바꿨다. 기본 경로는 날짜별 기록 계약을 가정해 하루 분할을 실행했다.

**이번 원칙.**
- condition_check는 질문 조건의 해석·검증만 한다.
- 실행 가능한 연산과 lowering 전략은 **실행 프로필**(`geoflow/providers.py`)이 정한다. 프로필은 provider와 그 계약으로 이루어진다.

| 프로필 | 계약 | 기간 정책 | 쓰임 |
|---|---|---|---|
| `mock` + `legacy`(기본) | TIMS `DEFAULT_CONTRACT` | legacy: 상대 토큰·범위를 그대로 넘기고, 구간별 하루 분할을 실행. **가정한 TIMS 항목**을 `legacy_assumptions`, `date_semantics`, step `assumptions`에 기록 | 기존 동작 재현 |
| `mock` + `strict` | TIMS `DEFAULT_CONTRACT` | guaranteed: 확인된 것만 실행(단일 날짜, 기간 없음) | TIMS 계약 범위 확인 |
| `reference` | `REFERENCE_CONTRACT`(합성 데이터의 계약) | guaranteed: 계약상 확인된 명시 범위·하루 합성을 실행 | 의미 graph의 end-to-end 검증 |

- TIMS의 `ITEMS`는 하나도 바꾸지 않았다. 여전히 `range_inclusive=observed`, `relative_date_reference=unknown`, `day_records:*=observed/unknown`이다.
- `REFERENCE_CONTRACT`는 별도 객체다(`provider="reference"`). 확인 항목마다 `reference_provider.py` 머리의 문장을 인용한다(`evidence_problems`가 대조).
- `ToolExecutor(provider=...)`와 실행 프로필의 provider가 다르면 파이프라인 구성이 실패한다(`PROVIDER_PROFILE_MISMATCH`). 그래서 reference 계약이 mock/TIMS 호출에 붙을 수 없다.
- 하루 단위 합성에서 null인 날의 처리도 계약이 정한다(`compiler.empty_day_policy`).
  - "null = 조건에 맞는 기록 없음"이 확인된 provider(reference)는 그날을 빼고 합친다. sum·max·min에 영향이 없다.
  - TIMS처럼 `null_result`가 미확인이면 지금처럼 멈춘다(`EMPTY_GROUP_VALUE`).
  - `verify_lowering`은 이 정책이 계약과 같은지 다시 본다.

**CLI 호환성과 결과 변화.**

| 사용법 | 이전(`0f2daaa`) | 이번 |
|---|---|---|
| 옵션 없음 | mock, legacy | 같음(재생으로 확인: cond_v1 64/64, census 421/421) |
| `--condition-check` | 조건 해석 + **strict 실행**(상대 기간·범위·구간별 집계는 멈춤) | 조건 해석 + **legacy 실행**(상대 기간·범위를 가정으로 실행, 검증 요약은 미검증으로 표시). `120c462` 시절의 cc 결과와 같음(32/32) |
| `--condition-check --tims-execution strict` | 없음 | `0f2daaa`의 `--condition-check`와 같음(재생 cond 32/32, census 421/421) |
| `--tims-execution strict` | 없음 | 해석은 기존대로 하고 실행만 strict |
| `ASSISTANT_TOOL_PROVIDER=reference` | 오류 | reference provider와 그 계약. `--tims-execution`은 적용되지 않음 |

`0f2daaa`의 condition_check 확인 평가(Case K)는 `--condition-check --tims-execution strict` 조합의 결과다.
재생 도구도 같은 옵션을 받는다: `geoflow_replay_compare.py --tims-execution`, `condition_replay.py --tims-execution`.

## 2. 합성 데이터

`reference_data/synthetic_operation_days.csv`, 27행. **손으로 만든 합성 데이터**이며 지명(가람구, 나래구)도 가상이다.

- **한 행은 택시 한 대의 영업일 하루(택시·일)다.** 열은 record_id, taxi_id, service_date(영업일, Asia/Seoul), closed_at(영업 종료 시각 +09:00), scope, taxi_type, revenue_krw(원 단위 정수, 빈칸 = 결측)다.
- 결과에 차이가 드러나도록 넣은 것:

| 차이 | 넣은 방식 |
|---|---|
| 그룹별 표본 수 | 가람구 개인택시 주별 레코드 수 1·3·2·4·1·1 |
| 개인/법인 | 가람구 법인 4건(평균 62,500), 나래구 법인 1건(500,000) |
| 지역 | 나래구 개인 7건 |
| 월 경계의 부분 주 | 8/1–2(토·일), 8/31(월) |
| 데이터가 없는 날짜 | 가람구 개인은 8/2, 8/4, 8/6–9 등. 법인은 1·4·6주 전체가 빔 |
| 최댓값 동률 | 가람구 개인 2주·3주 합계 300,000 |
| 경계 밖 날짜 | 7/31(999,000), 9/1(888,000) |
| 자정 넘은 종료 | r02: 영업일 8/1, 종료 8/2 01:10 → 8/1에 속함 |
| 결측 매출 | r08(8/14) → 모든 집계와 분모에서 제외 |

## 3. reference 계약(`reference_provider.py` 머리 = `REFERENCE_CONTRACT`)

| 항목 | 정의 |
|---|---|
| 시간대 | 모든 날짜는 Asia/Seoul 달력 날짜. 레코드는 service_date로만 거름(closed_at 아님) |
| 단일 날짜 | `YYYYMMDD` = service_date가 그 날인 레코드 |
| 범위 | `YYYYMMDD-YYYYMMDD`, 양 끝 포함 |
| 상대 날짜 | provider는 받지 않음(`UNSUPPORTED_BY_PROVIDER`). compiler가 pipeline clock(Asia/Seoul 기준일)으로 명시 범위로 풀어 보냄 |
| 기간 없음 | 데이터 전체 기간 |
| 주 시작일·부분 주 | provider는 bucket을 지원하지 않음. 로컬 분석이 정함: 월요일 시작, 기간 경계에서 자르고 `complete=false`로 표시 |
| 빈 날짜·빈 그룹 | 조건에 맞는 레코드가 없으면 null(0으로 채우지 않음). 구간별 집계에서 빈 주는 `EMPTY_GROUP_VALUE`로 멈춤. 하루 합성에서 빈 날은 계약에 따라 뺌 |
| null(결측) | revenue_krw 결측 레코드는 모든 집계와 개수에서 제외 |
| 평균 | 분모 = 조건에 맞는 결측 아닌 레코드 수, 가중치 없음. 주별 평균의 평균은 주마다 한 표(`REDUCE_GROUPS`) |
| 동률 | 로컬 `SELECT_GROUP`이 같은 값을 가진 구간을 모두 돌려줌. 답변에 "(동률)" |
| 반환 | 스칼라 숫자 하나. sum·max·min은 원 단위 정수, avg·med는 반올림하지 않은 실수. 답변은 소수 셋째 자리까지 표시 |
| 지원 범위 | `get_operation_metrics`의 metric=revenue와 scope·date·taxi_type·aggregation, `get_place_scope`, `get_scope_name`. 그 밖의 인자(dimension·order·limit·bucket·rollup·include_vicinity), metric, 도구는 mock으로 넘기지 않고 `UNSUPPORTED_BY_PROVIDER`로 반환. pipeline은 이를 지원 불가로 분류 |

기존 TIMS schema를 재해석하지 않았다. 같은 도구 이름과 인자를 쓰되, reference가 어떤 인자와 값을 어떤
뜻으로 받는지를 자기 계약으로 적었다. 새 오류 코드 `UNSUPPORTED_BY_PROVIDER` 하나만 명시적으로 추가했다
(`tool_executor.py`, retryable=false).

## 4. 네 대표 질문

조건은 가람구 개인택시, 지난달(기준일 2026-09-25 → 2026-08-01~08-31)이다. 모두 기존 구조화 grounding
(`aggregation_plan`), `AggregationSpec`, macro `PLACE_TO_SCOPE` + (`EVENT_TO_MEASURE` | `EVENT_TO_GROUPED_MEASURE`),
compiler, 로컬 분석 연산을 그대로 쓴다. 질문별 분기는 없다.

| # | 질문 의미 | 의미 graph | 실행 계획 | 결과 | 손 계산 |
|---|---|---|---|---|---|
| 1 | 전체 매출 평균 | RESOLVE_PLACE_SCOPE → OPERATION_METRIC(avg) | get_place_scope 1 + 범위 호출 1(`20260801-20260831`, explicit_range) | 103,333.333 | 1,240,000 / 12 |
| 2 | 주별 합계의 평균 | … → OPERATION_METRIC(sum, group_by week) → REDUCE_GROUPS(avg) | range_partition: 주 6개 범위 호출 → COLLECT_GROUPS → REDUCE_GROUPS | 206,666.667 | (100,000+300,000+300,000+280,000+200,000+60,000) / 6 |
| 3 | 주별 평균의 최댓값 | … → OPERATION_METRIC(avg, week) → REDUCE_GROUPS(max) | 주 6개 범위 호출(각 avg) → COLLECT → REDUCE | 200,000(8/24–30) | 주별 평균 100k·100k·150k·70k·200k·60k |
| 4 | 합계가 가장 큰 주 | … → OPERATION_METRIC(sum, week) → SELECT_GROUP(max) | 주 6개 범위 호출 → COLLECT → SELECT | 8/3–9, 8/10–16 (동률), 300,000 | 주별 합계 최대 300,000이 둘 |

- **전체 평균과 주별 평균의 평균을 구분한다.** 1번은 103,333.33, 주별 평균의 평균은 113,333.33(680,000/6)이다.
- **최댓값과 그 주를 구분한다.** 3번은 값을 돌려준다(`REDUCE_GROUPS max`). 4번은 구간을 돌려준다(`SELECT_GROUP`, 동률이면 모두).
- **조건은 모든 측정 호출에 들어간다.** 주별 호출 6개 모두 scope=가람구, taxi_type=private, 기간 안의 범위다(테스트).
- **평균은 재구성하지 않는다.** 주별 평균은 각 주의 범위 호출에서 provider가 레코드로 계산한다. 범위 계약이 없는 변형 계약에서는 일별 값으로 만들지 않고 `UNVERIFIED_TIMS_CONTRACT`로 멈춘다.
- **fused(bucket/rollup)는 쓰지 않는다.** reference에는 bucket 계약이 없다(bucket_* unknown). 대신 범위 계약이 있어 range_partition을 쓴다. `execution_plan.lowering`에 거부 이유가 남는다.
- **trace.** `semantic_map`이 의미 단계를 실행 단계에 잇는다(`measure_groups` → `measure_groups#1..6` + `measure_groups.collect`). hop_log에는 단계마다 phase(tool/local), covers, group, 결과가 남는다(부록 F의 (s_i, Σ)).
- **답변.** 값, 구간별 값, 계산 경로 다음에 세 줄을 붙인다.
  - "계산 환경: reference provider — 고정 합성 데이터…실제 교통 데이터나 TIMS 결과가 아닙니다"
  - 적용 기간(질문 기간, 기준일, 양 끝 포함, service_date 기준)
  - 계산 의미(레코드 단위, 평균 분모, 주 경계)

## 5. 검증(정답 grounding, LLM 없음)

`tests/test_reference_provider.py` 37건이다. 전체는 849건 통과(기대된 실패 1).

기대값의 근거는 두 가지이며, 둘 다 provider·compiler 코드를 쓰지 않는다.
1. 손 계산 상수(위 표).
2. `reference_data/expected_results.sql`을 SQLite로 CSV에 돌린 값. 주 구간은 SQL의 달력 CTE로 따로 만든다.

테스트는 SQL 값과 손 계산이 같은지, 파이프라인 결과가 손 계산과 같은지를 각각 확인한다.

| 검증 | 결과 |
|---|---|
| 네 대표 질문의 수치·선택 결과 | 일치 |
| 개인↔법인↔전체 | 103,333 / 62,500 / 93,125 |
| 가람↔나래 | 나래: 50,000 / 58,333 / 70,000 / 8/10–16 단독 100,000 |
| 날짜 범위 변경 | 8/1–15 평균 116,667. 8/4–31이면 2주가 잘려 동률이 풀림 |
| 전체 평균 ≠ 주별 평균의 평균 | 103,333 ≠ 113,333 |
| 부분 주 | 첫·마지막 주 `complete=false`, 답변에 "(부분 구간)" |
| 빈 그룹 | 법인 주별 집계는 `EMPTY_GROUP_VALUE`(0으로 채우지 않음) |
| 빈 기간 | null → "결과 없음" |
| 자정 넘은 종료 | 8/2 하루 합계 null, 8/1 하루 100,000 |
| 결측 매출 | 3주 평균 분모 2 |
| 직접 집계 ↔ 분해 실행 | 계약상 동등한 sum만 비교: range_partition = daily_partition(빈 날 skip) = 206,666.67, 범위 한 번의 합 = 주별 합의 합. avg는 일 분해를 거부 |
| 잘못된 조건·단계 뒤바뀜 | 한 주의 taxi_type 누락, 주 범위 변조, 안/밖 reducer 교환, 조건 변조, 빈 날 정책 변조 → `LOWERING_MISMATCH` |
| reference 계약이 TIMS에 적용되지 않음 | TIMS ITEMS 상태 불변, mock 프로필 = DEFAULT_CONTRACT, strict TIMS는 같은 질문에 range 호출을 만들지 않음, provider 불일치 구성 거부 |
| provider 전환 누출 | handler 사전을 매번 새로 만듦(mock 사본 포함). reference → mock → reference 결과 동일, mock 답에 합성 표기 없음 |
| 미지원 | 다른 도구·metric·dimension·상대 토큰·미등록 장소 → `UNSUPPORTED_BY_PROVIDER`/`NOT_FOUND`, pipeline outcome=unsupported |
| CLI | provider 환경 변수와 `--tims-execution`으로 프로필을 만듦. 실제 CLI 실행(qwen3:8b, cc 켬)에서 네 번째 대표 질문이 동률 두 주로 답함 |
| 검증 요약 | provider 층을 실행 프로필의 계약으로 판정. reference는 "reference provider 계약으로 확인: 기간, 택시 유형", TIMS legacy는 같은 질문에서 기간 미검증. CLI 확인 중 TIMS 계약으로 판정하던 결함을 찾아 고침 |

**기존 경로 영향(재생, LLM 호출 없음).**
- 기본 경로(mock legacy)는 cond_v1 flat·structured, census M0·M2가 변경 전과 같다.
- cc + strict는 `0f2daaa`의 cc 결과와 같다(cond 32/32, census 421/421).
- cc + legacy는 `120c462`의 녹화된 cc 결과와 같다(32/32).

## 6. LLM 기능 확인(성능 평가 아님)

질문 6개(`evaluation/reference/reference_questions_v1.yaml`, 실행 전 고정)는 대표 질문 4개와 조건만 바꾼 2개(나래구, 법인)다.
- qwen3:8b, temperature 0, 기준일 2026-09-25, reference provider, 1회
- run `20260926_194817_reference_functional_check`(flat, structured)와 `20260926_195024_reference_functional_check_cc`(flat+cc, structured+cc)
- 채점은 v2.6 `analyses/v2.6-functional`. 기대값은 손 계산 값이다.
- **기능 확인이며 성능 평가가 아니다.**

| 질문 | flat | structured | flat+cc | structured+cc |
|---|---|---|---|---|
| r1 전체 평균 | ✓ | ✗ 해석(기간 5월, 유형 누락) → "결과 없음" | ✓ | ✓ |
| r2 주별 합계의 평균 | 확인 요청(구간 안 집계 없음) | ✗ 해석(dimension=week) → INVALID_FACTOR | 확인 요청 | ✗ 해석(같음) |
| r3 주별 평균의 최댓값 | ✗ 해석(order/limit) → 실패 | ✗ 해석(값 대신 주 선택) → 답함 | ✗ 해석 → 실패 | ✗ 해석(주 선택) → 답함 |
| r4 합계가 가장 큰 주 | ✗ 해석(order/limit) → 실패 | ✓ (동률 두 주) | ✗ 해석 → 실패 | ✓ |
| r5 나래구, 가장 큰 주 | ✗ 해석(유형 누락, order/limit) | ✗ 해석(유형 누락) → 전체 택시로 답함 | ✗ 해석(order/limit) | ✓ |
| r6 법인 전체 평균 | ✓ | ✗ 해석(기간 5월, 유형 누락) | ✓ | ✓ |
| gold 답과 같음 | 2 | 1 | 2 | 4 |

- **실패는 모두 질문 해석(grounding) 단계에서 났다.** grounding과 집계 계획이 맞은 관측은 모두 손 계산과 같은 값을 냈다. 실행 단계 오류(호출·lowering·로컬 계산)는 0건이다.
- **해석 오류의 종류.**
  - 구조화 prompt의 기간 오변환(`지난달` → `20260501-20260531`)과 택시 유형 누락. condition_check가 모두 바로잡았다(structured+cc r1·r5·r6).
  - flat의 order/limit 오용: "가장 큰 주"를 순위 1개로 적어 조합 오류가 났다. flat 계약에는 구간 선택이 없다.
  - 구조화의 dimension=week 오용
  - "평균 중 가장 큰 값"을 구간 선택으로 해석한 것(r3). 값 반환과 구간 선택이 뒤바뀐 조용한 의미 오류다. 채점기가 plan 불일치로 잡았다.
- 데모를 위해 원문이나 결과를 고치지 않았다. 표본 6문항 1회라 비교 결론을 내지 않는다.

## 7. 채점기 보완(`condition_scoring.py` v2.4–v2.6)

- **v2.4**: dimension·order·limit(group key, 순위, 개수)을 판정한다. gold에 structure가 없으면 셋 다 "없음"이 기대값이다. 구간 단위와 안/밖 reducer, 값 반환과 구간 선택은 plan 비교에 이미 있었다.
  - 이전 36문항 run에는 **정정 분석만** 추가했다(`analyses/v2.4-structure`, v2.3 분석 연결). flat+cc d35가 조용한 오류로 바뀐다(0→1). 계약상 실행 가능한 질문의 정답은 18→17이다.
  - 사전 판정(v2.3, Case K)과 기존 분석 파일은 바꾸지 않았다. 36문항을 holdout으로 다시 쓰지 않았다.
- **v2.5**: gold answer(값과 선택 구간, 동률 포함)를 비교한다. reference 관측은 provider 의미를 reference 계약으로 판정하고, mock 정답은 해당 없음으로 둔다.
- **v2.6**: 주마다 부른 범위 호출이 gold 기간을 빈틈없이 덮으면 요청 인자 보존으로 인정한다. 기능 확인 첫 채점(v2.5)에서 드러난 공백이다. 첫 채점 분석은 두고 v2.6 분석을 연결했다.

## 8. 논문(§3.3–3.4, 부록 E·F)과의 대응

| 구분 | 내용 |
|---|---|
| 이미 구현되어 있던 것 | core concept·role(LOCATION/EVENT/AMOUNT, SUBCOND/SUPPORT/MEASURE), G ↔ G′ 인수분해(semantic operator ↔ Tool, factor = params), G1–G5와 G7 검증, macro 조합(PLACE_TO_SCOPE, EVENT_TO_(GROUPED_)MEASURE ≈ FILTER-AGGREGATE-MEASURE), 위상 순서 실행과 trace |
| 이번에 실제 계산으로 검증한 것 | 두 단계 집계 graph(구간 안 → REDUCE/SELECT)가 lowering 후에도 같은 값을 내는지를 독립 기준 결과와 비교. 조건이 모든 호출에 보존되는지. 단계 뒤바뀜을 탐지하는지. 부록 F의 trace가 의미 단계와 실제 호출·로컬 연산을 잇는지. 답변이 계산 결과(Σ_M)에 근거하는지 |
| 프로젝트가 더한 설계 | provider 계약(확인/관찰/미확인)과 계약별 lowering 전략, 실행 프로필, 조건 provenance와 검증 범위, 빈 날·빈 구간 정책, 합성 데이터 표기 |
| 아직 없는 것 | 질문–그래프 예시 검색(부록 E.1, 이후 선택 기능으로 추가: `question_graph_retrieval.md`. 임베딩이 아닌 lexical 검색), LLM이 graph를 직접 drafting하는 단계(지금은 grounding → 고정 macro 조합), SFT/DPO, 부록 E의 다른 템플릿(경로·최적화·방위 등)과 GIS 연산 |

## 9. vendor 확인이 필요한 질문(TIMS)

1. `YYYYMMDD-YYYYMMDD`의 양 끝이 포함되는가(`range_inclusive`)
2. `last_week`·`last_month`·`last_year`의 기준 시각·시간대·주 시작일(`relative_date_reference`)
3. `get_operation_metrics`의 aggregation이 택시·일 기록에 바로 적용되는가, 기간 전체의 택시별 중간 집계가 있는가(`day_records`). trip·passage·drive의 날짜 귀속(자정 넘는 기록)
4. `bucket=week`의 주 시작일, 부분 주, 빈 주 처리(`bucket_*`)
5. 조건에 맞는 기록이 없을 때의 반환값(null/0/오류, `null_result`)
6. `weekday`/`weekend`/`holiday` 토큰이 가리키는 기간과 휴일 달력

## 10. 남은 차이와 다음 작업

- reference provider는 매출 하나와 단일 집계를 다룬다. 주·월 구간의 두 단계 집계는 로컬 분할(range_partition, `geoflow/periods.py`의 주·달력 월 규칙)로 실행된다. dimension 목록, OD, 다른 metric은 지원하지 않는다(구조화된 미지원). (정정 2026-09-26: 이전 판은 month 구간도 지원하지 않는다고 적었으나, 월 구간은 주 구간과 같은 로컬 분할로 계산되며 `tests/test_example_retrieval.py`가 독립 SQL과 대조한다.)
- LLM 기능 확인에서 실패는 모두 질문 해석(grounding) 단계에서 났다. 실행 단계 오류는 없었다. 실패 유형은 기간 오변환, 택시 유형 누락, "가장 큰 값"을 구간 선택으로 해석한 것이다(§6).
- 다음 최소 작업은 다음과 같다.
  1. vendor 답변으로 TIMS 항목을 확인하면 그 항목만 CONFIRMED로 올린다(인용 필요).
  2. reference에 month 구간이나 두 번째 metric을 더해 구간 단위 일반화를 확인한다.
  3. 기능 확인에서 드러난 grounding 오류는 condition_check·구조화 grounding의 개선 과제로 따로 잰다.

## 11. 재현

```bash
python -m unittest tests.test_reference_provider tests.test_condition_scoring
ASSISTANT_TOOL_PROVIDER=reference python assistant_cli.py --agent-mode geoflow \
  --aggregation-grounding structured --query "지난달 가람구 개인택시의 매출 합계가 가장 컸던 주는 언제야?"
python structured_grounding_eval.py run evaluation/reference/reference_questions_v1.yaml \
  --name reference_functional_check --arms flat,structured --provider reference
python condition_scoring.py RUN_DIR --analysis-id v2.6-functional
python geoflow_replay_compare.py evaluation/prompt_ab/20260925_171514_model_M0_census \
  --condition-check --tims-execution strict --out X.json   # 0f2daaa cc 결과 재현
```
