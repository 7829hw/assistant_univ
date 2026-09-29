# 업체 Tool 위임과 GeoFlow 로컬 재계산의 책임 분리

상태: 구현됨(2026-09-29, 브랜치 `geoflow/dev-v2`, 기준 커밋 `962432d` 위 작업 트리).
관련 코드: `geoflow/tims_contract.py`, `geoflow/compiler.py`, `geoflow/calendar_terms.py`,
`geoflow/periods.py`, `geoflow/providers.py`, `geoflow/answer.py`.
평가: `evaluate_vendor100.py`, `evaluation/vendor100/`.

## 1. 배경을 코드와 자료로 확인한 결과

| 주장 | 확인 | 근거 |
|---|---|---|
| 업체에 전달한 프로그램은 aggregation/bucket/rollup을 Tool에 그대로 넘겼다 | 맞음 | `vendor-share-2026-09-19:geoflow_templates/operation_metric.yaml`의 `bucket: {slot: bucket}`, `rollup: {slot: rollup}`. 계약 검사 없음 |
| v2 schema와 업체 정답도 그 인터페이스를 유지한다 | 맞음 | `schemas/tims.yaml` get_billing_metrics `bucket`/`rollup`, xlsx 43·98·100의 정답 Tool |
| 현재 GeoFlow는 주 시작일·부분 구간·빈 구간·상대 날짜 기준이 확인되어야 그 호출을 허용한다 | 맞음 | 변경 전 `FUSED_BUCKET_ROLLUP.requires`에 네 항목(모두 UNKNOWN). 확인되더라도 `SEMANTIC_GROUP_DEFINITION`(월요일, 경계에서 자름, 빈 구간 undefined, Asia/Seoul)과 **같아야** 했다 |
| 그래서 업체가 정상으로 제시한 질문이 막힌다 | 맞음. 정답 grounding으로 43·98·100 모두 거부 | 43·98: 위임 거부 → 범위 계약 없음 → 구간 안 avg는 하루 값으로 재구성 불가 → `UNVERIFIED_TIMS_CONTRACT`. 100: 하루 분할 365회 > 62 → `UNSUPPORTED_PARTITION_SIZE` |
| 추가로 확인한 것: 로컬 재계산 쪽은 반대로 근거 없이 허용되고 있었다 | 맞음 | 변경 전 legacy 프로필은 `require_day_records=False`로 `day_records:<tool>`(OBSERVED/UNKNOWN)을 가정하고 하루 분할을 실행했다(`providers.LEGACY_TIMS_ASSUMPTIONS`의 `day_records:<tool>(구간별 하루 분할)`) |

두 문제는 같은 원인이다. 의미 graph에 로컬 달력 정책(월요일 시작 등)을 "질문의 뜻"으로 고정한 뒤,
위임 호출에는 그 정책과 같다는 증명을 요구하고, 로컬 재계산에는 그 정책을 쓴다는 이유로 동등성
근거 일부를 가정했다. 질문이 정하지 않은 구간 정의는 질문의 뜻이 아니다.

## 2. 책임 경계

```text
질문 → grounding(집계 단계 + 질문이 명시한 구간 정의만) → 의미 graph
                                                          │
                     ┌────────────────────────────────────┴───────────────────────┐
         업체 Tool에 위임(provider_delegated)                  GeoFlow 로컬 재계산(local_recomputation)
         bucket/aggregation/rollup 호출 하나                   구간마다 범위 호출 / 하루 호출 + 로컬 합성
         요구: 인자 ↔ 집계 단계 매핑 계약                        요구: 분해 전후 동등성의 근거 전부
         정의되지 않은 구간 정의 = 제공자 정의(provider_defined)   정의되지 않은 구간 정의 = 애플리케이션 정책
```

| | 위임 | 로컬 재계산 |
|---|---|---|
| 선행 조건 | Tool이 구간·집계 조합을 받음(`bucket_rollup` 능력 + enum), `inner_is_aggregation`, `rollup_unweighted`(모두 CONFIRMED). 질문이 정의를 명시했으면 `REQUIREMENT_ITEMS` 항목이 그 값으로 확인 | 범위: `range_inclusive`. 하루: `single_date` + `day_records:<tool>`, 구간 안 집계 ∈ {sum,max,min}, 측정값별 합성 가능성(`measures.day_composable`), 62회 이하. 질문이 빈 구간 처리를 명시하면 거부(구현하지 않음) |
| 요구하지 않는 것 | 주 시작일·부분 구간·빈 구간·상대 날짜 기준의 확인, 로컬 정책과의 일치 | 위임 가능 여부 |
| compile 검증(`verify_lowering`) | 기록된 전략이 그 경로의 기준을 만족(`strategy_problems` 재계산), bucket·aggregation·rollup이 의미 graph의 단계와 같음, 구간 안 집계 명시, 목록 인자 없음, 조건 보존 | 같은 재계산, 분할이 빈틈·겹침 없이 덮음(질문의 "온전한 구간만" 반영), COLLECT 구성·집계, 빈 날 처리 |
| 실행·답변 검증 | scope 출처(실행기), 반환값 그대로 답변(코드 format) | 같음 + 빈 값이면 멈춤(`EMPTY_GROUP_VALUE`) |
| 검증하지 않는 것(기록 `not_verified`) | 제공자 내부의 구간 경계·부분 구간·빈 구간·상대 날짜·평균의 분모 | 제공자가 `requires` 계약대로 동작하는지 |
| 기록 | `lowering.path/requires/semantics/delegated/checks/not_verified/rejected`, `date_semantics.responsibility=provider` | 같은 key + `periods`(구간, 경계 규칙, 뺀 구간, 질문 정의) |

전략 선택 순서는 위임 → 범위 → 하루다. 각 전략은 자기 기준으로만 판단한다(`compiler.strategy_problems`).
`--tims-execution strict`는 위임을 허용하지 않는 프로필이며, 호출 하나로 합치려면 제공자 정의가
애플리케이션 정의와 같다는 계약이 필요하다(변경 전 동작과 같음).

### 사용자가 구간 정의를 명시한 경우

`geoflow/calendar_terms.py`가 질문 원문에서 닫힌 어휘로 읽는다(LLM 출력이 아님, 항상 켜짐).

| 어휘 | 예 | 계약 항목 |
|---|---|---|
| `week_start` | "일요일부터 시작하는 주", "주 시작은 화요일", "월요일 기준 주" | `bucket_week_start` (+ last_week·this_week면 `relative_date_reference`) |
| `partial` | "온전한 주만", "부분 주는 제외"(exclude), "잘린 달도 포함"(include) | `bucket_partial` |
| `empty` | "자료가 없는 주는 0으로"(zero), "빈 구간은 빼고"(skip) | `bucket_empty` |

- 읽은 정의는 grounding → `group_by.calendar`, `plan.calendar`에 남는다. 질문이 말하지 않은 정의는 적지 않는다.
- 위임은 계약이 **그 값**으로 확인될 때만. 월요일 명시도 마찬가지다(로컬 기본값이 월요일이라는 것은 제공자 정의의 근거가 아니다).
- 위임이 안 되면 로컬(근거가 있을 때 그 정의로 분할), 둘 다 안 되면 `CALENDAR_REQUIREMENT_UNSUPPORTED`. 사용자 메시지에 "TIMS 기본 구간 정의로 바꿔 계산하지 않습니다".
- 단서는 있는데 읽지 못함(서로 다른 정의 포함) → `AMBIGUOUS_CALENDAR_REQUIREMENT`(needs_clarification). 받을 구간이 없음 → `UNCONSUMED_CONDITION`.
- 단위는 주·달·월이며 뒤에 조사·"별"·"마다"만 온다. "주차", "주행", "주말", 도로 "구간"("일부 구간의 평균 속도")은 정의로 읽지 않는다.
- 월 구간이라도 기간이 last_week·this_week이면 주 시작 요일은 기간에 걸린다(위임은 거부, 로컬은 그 요일로 기간을 푼다).
- 오탐 점검: 저장소의 질문 796개(업체 100문항 포함, 변형 제외)에서 읽힌 정의 0건.

### 독립 리뷰에서 고친 것 (구현 후 별도 agent 리뷰, 재현 스크립트로 확인)

1. 월 구간 + last_week에서 명시한 주 시작 요일이 사라짐 → group_by.calendar에 남기고 기간 해석·위임 판정에 씀.
2. 어휘에 단어 경계가 없어 "주차장", "주말", 도로 "구간"이 정의로 읽힘 → 경계 추가, "구간"은 단위에서 뺌.
3. `verify_lowering`이 분할 호출을 위임 전략으로 기록한 계획을 통과시킴 → 분할 호출은 local 경로여야 함.
4. strict에서 주 시작 요일을 명시하면 상대 기간 값 대조를 건너뜀 → 명시 여부와 무관하게 `date_argument_semantics`로 대조.
5. 기록의 규칙 문장이 명시한 요일과 다름, 위임 기록이 확인된 relative 계약을 provider로 적음, 답변이 애플리케이션 기본값까지 "질문에서 정한 기준"으로 적음 → 수정.
6. strict가 월 구간에 주 시작 계약, 명시 범위에 relative 계약을 요구 → 관련 항목만 요구. 반대로 strict가 range_inclusive 없이 범위를 위임 호출로 넘기던 것(변경 전부터)은 막음.
7. 평가기의 답변 값 검사가 값이 없거나 문자열일 때 참이 됨, 숫자 부분 일치 → 경계 대조, 목록은 분류 이름까지, 확인할 값이 없으면 거짓. 채점 규칙을 고친 뒤 모든 결과를 `rescore`로 다시 채점.

## 3. 바뀐 동작과 그 영향

| 질문 유형 | 변경 전(mock + legacy) | 변경 후 |
|---|---|---|
| billing 두 단계 집계, 구간 정의 미명시(43·98·100 등) | 구간 안 sum·max·min이면 하루 분할(가정), avg·med면 거부 | 위임 호출 하나 |
| 구간 선택("합계가 가장 큰 주"), bucket 없는 Tool(요금·속도·공차율)의 구간별 집계 | 하루 분할(`day_records` 가정) | `UNVERIFIED_TIMS_CONTRACT`(근거 없음) |
| 구간 정의를 명시한 질문 | 명시가 무시됨(읽지 않음) | 보장되는 경로만, 아니면 거부 |
| 기간 없는 두 단계 질문 | `UNRESOLVED_PERIOD` | 위임 호출(기간 인자 없음, 제공자 기본 기간) |

holdout_v2(사전 등록, 사람 미검토)의 기대 결과 9개 intent가 이 정책 변경으로 바뀐다. 사전 등록 파일은
두고 `evaluation/v2/label_revisions.yaml`(r1)에 개정과 이유를 적었다. 채점기는 개정을 적용하고 관측
기록에 사전 등록 값(`expected_outcome_prereg`)을 함께 남긴다. 뜻(집계·인자·라벨)은 바꾸지 않았다.
- answered → unsupported 7개: w01·w02·w11·w15·w41(요금), w13(공차율), w42(속도). bucket 없는 Tool이며 `day_records` 미확인.
- unsupported → answered 2개: w06(운행일수 월별 avg→min), w32(가동률 주별 max→avg). get_billing_metrics 위임.

## 4. 검증 결과

검증 층을 구분한다. 실행하지 않은 것은 없음으로 적는다.

### 4.1 Mock·단위 검증 (LLM 없음)

`python -m unittest discover -s tests -t .` — 969건 통과(예상 실패 1건은 기존). 새 파일
`tests/test_provider_delegation.py` 24건. 기존 테스트 중 정책이 바뀐 것은 기대를 새 정책으로 고쳤고,
로컬 경로 검증은 `LOCAL_CONTRACT`(테스트 가정, 계약 근거 아님)를 명시해 유지했다. 손 계산 값
(1150/6, 272.5 등)은 그대로다. 예: 부분 주를 버리는 fake 제공자는 위임 호출에서 272.5를 내고, 이는
질문이 부분 주를 정하지 않았으므로 제공자 정의의 값으로 받아들인다. "잘린 주도 포함"을 명시하면 위임하지
않고 로컬(근거 가정 시) 1150/6, "온전한 주만"을 명시하면 로컬 272.5(W1·W6 제외).

### 4.2 정답 grounding 기반 검증 (LLM 없음, mock provider)

`evaluate_vendor100.py gold`. 업체 정답 Tool 호출에서 grounding을 결정적으로 역산해 planner 자리에
넣는다. 기본값(taxi_type=all, taxi_status=all, dimension_target=both, aggregation=avg, region="")은
생략과 같게 본다(업체가 14·15·17·43에서 생략을 정상 판정). scope는 조회 결과 출처로 비교한다.

| | 변경 전 `962432d` | 변경 후 |
|---|---|---|
| 업체 정답 호출과 일치(Tool·인자·scope 출처·단일 분석 호출·답변 값) | 97/100 | 100/100 |
| 거부 | 43·98 `UNVERIFIED_TIMS_CONTRACT`, 100 `UNSUPPORTED_PARTITION_SIZE` | 0 |

- 43: `get_billing_metrics(metric=active_taxi_ratio, date=this_month, taxi_type=corporate, aggregation=avg, bucket=week, rollup=min)`
- 98: `get_billing_metrics(scope=<대구>, metric=operating_days, date=last_month, taxi_type=private, aggregation=avg, bucket=week, rollup=med)` — 업체가 지적한 단계 뒤바뀜 없음
- 100: `get_billing_metrics(scope=<대구>, metric=revenue, date=last_year, taxi_type=corporate, aggregation=sum, bucket=month, rollup=max)`
- 세 문항 모두 `path=provider_delegated`, `delegated`에 week_start(주 구간만)·partial·empty·relative_date.
- 로컬 재계산은 계속 막힘: 위임을 끄고 `day_records`를 가정해도 43·98은 구간 안 avg라 불가, 100은 365회 호출로 상한 초과.
  범위 계약까지 가정하면 43은 범위 분할이 가능하지만 이것은 애플리케이션 주 정의(월요일 시작)로 계산한 별개의 주장으로 기록된다.
- 93·95(한 지역 안의 OD)는 같은 장소를 두 번 조회한다(출발·도착 개념이 따로 있음). 결과는 같고 효율 차이이며 채점에서 실패로 보지 않고 `duplicate_place_lookups`로 남긴다.

명시 정의 변형 7문항(`evaluation/vendor100/stated_variants.yaml`, 업체 정답 없음, 기대는 정책에서 옴): 7/7 기대대로.
일요일 시작·월요일 시작·온전한 주만·운행 없는 주 0 → `CALENDAR_REQUIREMENT_UNSUPPORTED`, 일요일 시작 기준 지난 주(한 단계) →
같음(해석 기간 20260913-20260919 표시), 읽지 못한 정의 → `AMBIGUOUS_CALENDAR_REQUIREMENT`, 구간 없는 질문의 "부분 주 제외" →
`UNCONSUMED_CONDITION`. 어느 경우도 분석 Tool을 부르지 않는다.

### 4.3 실제 LLM을 포함한 전체 실행

`evaluate_vendor100.py llm`. 2026-09-29, `qwen3:8b`(digest `500a1f067a9f`), Ollama 0.34.4, production 기본 설정
(flat grounding, condition_check 끔, mock + legacy, 예시 검색 끔), temperature 0, think=auto, 기준일 2026-09-25,
질문마다 모델 unload. 변경 전은 `962432d` worktree, 변경 후는 그 위 작업 트리(`code_diff_sha256` `f9a36e4d…`와
새 파일 hash를 meta에 기록). 두 run의 grounding 100개가 모두 같았다(planner 차이 없음). 따라서 결과 차이는 모두
정책 변경에서 온다. 같은 grounding을 변경 전 코드로 다시 돌린 replay도 변경 전 run과 같았다.

| | 변경 전 | 변경 후 |
|---|---|---|
| 업체 정답과 일치 | 65 | 65 |
| 답했으나 불일치 | 13 | 14 |
| 거부(unsupported) | 4 | 3 |
| 실패(grounding·조회 단계) | 18 | 18 |

- 바뀐 문항은 100 하나: `UNSUPPORTED_PARTITION_SIZE` → 위임 호출. 그러나 LLM이 "월별 총 수입"을 aggregation=max로 읽고
  택시 유형(법인)을 빠뜨려 업체 정답과 다르다(`[aggregation sum≠max, taxi_type corporate≠없음]`). 업체가 이 문항에서
  지적한 것과 같은 오류이며 LLM grounding의 문제다. 정답 grounding(4.2)에서는 100이 정답 호출과 같다.
- 43(`INVALID_FACTOR`)과 98(`INVALID_PLACE`)은 두 run 모두 planner 출력 검증에서 멈췄다. 집계 lowering에 닿기 전의
  실패라 정책 변경의 영향을 받지 않는다. 대표 문항의 LLM 실측 개선은 없으며, grounding 품질이 다음 병목이다.
- 나머지 불일치·실패 유형(변경 전후 같음): taxi_status 누락 6, 요일 조건(weekend·weekday) 누락 3, 장소 역할 오류(scope ↔
  scope_pickup/dropoff) 2, 장소 조회 실패(NOT_FOUND) 6, od_role 누락 3 등. 이번 범위 밖이다.
- 원 관측: `evaluation/vendor100/results/llm_*_qwen3_8b.jsonl`(실행 당시 채점기), 최종 채점: 같은 이름 `.json`
  (`rescore`로 현재 채점 규칙 적용), 비교: `compare_llm_before_after.md`, `compare_llm_policy_effect.md`, `compare_gold.md`.

## 5. 남은 계약 불확실성 (업체 확인 필요)

| 항목 | 상태 | 영향 |
|---|---|---|
| `bucket_week_start` 주 시작 요일 | UNKNOWN | 위임 결과의 주 경계를 사용자에게 말할 수 없음. 명시 요청은 거부 |
| `bucket_partial` 기간 경계의 부분 구간 | UNKNOWN | 43(이번 달)처럼 부분 주가 생기는 질문의 값이 제공자 정의에 따름 |
| `bucket_empty` 빈 구간 | UNKNOWN | min·med rollup에 특히 영향 |
| `relative_date_reference` this_*·last_*의 기준·시간대·포함 범위 | UNKNOWN | 위임·한 단계 모두 제공자 정의 |
| `range_inclusive` 날짜 범위 양 끝 | OBSERVED(예시뿐) | 로컬 범위 분할 불가 |
| `day_records:<tool>` 기록의 날짜 귀속 | billing OBSERVED, 나머지 UNKNOWN | 로컬 하루 분할 불가(구간 선택, 요금·속도·공차율의 구간별 집계) |
| `null_result` 빈 결과 반환 | UNKNOWN | 로컬 합성에서 빈 날이면 멈춤 |
| `inner_avg_unit` avg의 분모 | OBSERVED | 위임 결과의 "평균" 뜻(택시·일 평균 등)을 사용자에게 말할 수 없음 |
| bucket과 dimension 동시 사용 | schema에 금지 문장 없음, mock은 거부 | GeoFlow는 구간별 집계에 목록 인자를 붙이지 않음(`UNSUPPORTED_AGGREGATION_COMBINATION`) |

이 항목들을 CONFIRMED로 바꾸려면 schema나 vendor parameter 정의에 문장이 있어야 한다(`evidence_problems`가 인용문을 대조).
이번 작업은 어떤 항목의 상태도 바꾸지 않았다.

## 6. 자료에서 발견한 것

- 업체 xlsx ↔ `assistant_univ_questions_100_v3.yaml`: 질문 문장 100/100 일치, 정답 호출 schema 위반 0건, scope+dimension 동시 사용 0건(`gold.yaml conflicts: []`).
- `query_loader.load_queries`(업체 제공 코드)는 id를 `yaml.safe_load`로 읽어 `010`→`"8"`, `008`→`"008"`처럼 바꾼다(YAML 1.1 8진수). 100문항 id가 원문과 달라진다(`--query-id 010`이 찾지 못함). 이번 범위 밖이라 고치지 않았다. 평가기는 BaseLoader로 읽는다.
- 업체 정답은 기본값(aggregation=avg 등)을 적기도 하고 생략하기도 한다. 생략을 정상으로 판정한 문항(14·15·17·43)이 있어 기본값과 생략을 같게 채점했다. 77·100의 "aggregation=sum 누락" 지적은 기본값 avg와 다르므로 오답으로 남는다.

## 7. 재현

```bash
python -m unittest discover -s tests -t .
python evaluate_vendor100.py extract                 # xlsx → gold.yaml (충돌 목록 출력)
python evaluate_vendor100.py gold --out evaluation/vendor100/results/gold_after.json
git worktree add --detach /tmp/base 962432d
python evaluate_vendor100.py --code-root /tmp/base gold --out evaluation/vendor100/results/gold_before.json
python evaluate_vendor100.py compare evaluation/vendor100/results/gold_before.json evaluation/vendor100/results/gold_after.json
python evaluate_vendor100.py --code-root /tmp/base llm --model qwen3:8b --out evaluation/vendor100/results/llm_before_qwen3_8b.json
python evaluate_vendor100.py llm --model qwen3:8b --out evaluation/vendor100/results/llm_after_qwen3_8b.json
python evaluate_vendor100.py rescore evaluation/vendor100/results/llm_after_qwen3_8b.json   # 채점 규칙을 바꾼 뒤
python evaluate_vendor100.py --code-root /tmp/base replay evaluation/vendor100/results/llm_after_qwen3_8b.json --out evaluation/vendor100/results/llm_after_replayed_on_base.json
```
