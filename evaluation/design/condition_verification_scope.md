# condition_check 검증 범위 정비

상태: 2026-09-26. HEAD `120c462` 위의 작업. 이번 단계는 **검증 범위를 정비하는 작업**이다. 정확도를
올리는 작업이 아니다. 기본 설정(condition_check 끔, flat 집계)은 바꾸지 않았다. 모델, prompt,
TIMS 계약도 바꾸지 않았다. mock 평가 수치는 실제 TIMS 정답률이 아니다.

## 1. 이전 보고의 판정 기준 확인

이전 보고(`condition_preservation.md` §5)의 세 표현은 모두 **최종 grounding의 글자**를 기준으로
판정했다. `structured_grounding_eval.judge` v1, `summary.json` 기준이다.

| 표현 | 판정 단계 | 기준 | 보지 않은 것 |
|---|---|---|---|
| 조건 전부 정확(conditions_ok) | 조건 보정 뒤 최종 grounding의 factors·장소 | gold pt_date 글자(`last_month`)와 같음. taxi_type all은 생략과 같게 셈 | 실행 인자, provider가 그 인자를 어떤 기간으로 읽는지, 같은 뜻의 절대 범위 |
| 조용한 오답(silent_wrong) | outcome=answered + grounding 판정 | answered인데 plan 또는 조건이 gold와 다름 | 실제 값(mock 포함), provider 의미 |
| 나빠진 관측 없음 | 같은 질문의 끔→켬 범주 비교 | 위 두 판정으로 만든 범주 | 같음 |

추가로 확인한 채점 결함은 다음과 같다.
- `condition_missing` 요약은 grounding이 거부된 관측을 "조건 누락"으로 셌다. 조건별 표(`condition_status`)는 `not_judgeable`로 나눴지만 요약 수는 섞였다.
- 보정 품질(`correction_quality`)만 taxi_type all 정규화가 빠져 있었다. 이것이 Case N의 원인인 c04다.
- gold가 상대 기간을 글자로만 적었다. 그래서 "지난달"을 손으로 센 범위와 같게 적은 답도 `changed`로 셌다.
- 재채점이 `summary_rescored.json`이라는 고정된 이름에 썼다. 세 번째 채점이면 두 번째 결과를 덮어쓴다.

**mock과 실제 의미의 구분.** mock은 인자를 해석하지 않고 인자 전체의 hash로 값을 만든다
(`mock_responses._rng`). 이전 "정답 24"는 "gold와 같은 요청 인자"라는 뜻이었다. 그 24건 중 20건은
`last_month`·범위를 그대로 넘겼다. TIMS가 이 인자를 KST 달력의 직전 달이나 양 끝 포함 범위로
읽는다는 계약은 없다. 기간 의미가 계약으로 확인되는 답은 4건(단일 날짜)뿐이었다.

## 2. 상대 날짜: 해석·요청 인자·provider 의미의 분리

### 이전 동작

condition_check는 "지난달"을 KST 범위(`20260801-20260831`)로 풀어 **기록만** 했다. 단일 집계
호출에는 `last_month`를 넘기고, 답변에 "TIMS의 해석과 같다는 보장은 없음"을 붙여 정상 답으로 냈다.

### 이번 동작

`compile_plan(date_policy=...)`에 두 정책을 두었다.

| | legacy(기본 경로) | guaranteed(condition_check 경로) |
|---|---|---|
| 단일 날짜 `YYYYMMDD` | 그대로 | 그대로. 계약 `single_date`로 확인됨 |
| 기간 없음 | 그대로 | 그대로. provider 기본 기간은 문서에 없어 `not_requested`로 기록 |
| 상대 토큰 `last_*` | 그대로 넘기고 `unverified`로 기록 | ① `relative_date_reference`가 확인되고 값이 "Asia/Seoul calendar"이면 토큰 그대로 ② `range_inclusive`가 확인되면 코드가 푼 명시 범위 ③ 하루 단위 합성이 가능하면 하루씩 호출 ④ 모두 아니면 `DATE_EXECUTION_UNVERIFIED` |
| 범위 `A-B` | 그대로, `unverified` | ②→③→④ |
| `weekday`/`weekend`/`holiday` | 그대로, `unverified` | 연속 기간이 아니므로 ④ |
| 구간별 집계의 하루 분할 | 사용, step `assumptions`에 `day_records:<tool>` 추가 | `day_records:<tool>`이 확인되어야 사용. 아니면 `UNVERIFIED_TIMS_CONTRACT` |

기본 계약에서는 ①②③이 모두 막혀 있다. 그래서 **condition_check 경로가 실행하는 기간은 단일 날짜와
"기간 없음"뿐이다.** `execution.date_semantics[transformation]`은 네 층을 나눠 기록한다.
- `value`: 의미 graph의 기간
- `interpreted_range`: 코드의 해석
- `request`: 실제 요청 인자
- `provider`: 계약상 확인 여부, 필요한 항목, 빠진 항목

**"지난달"이 최종 요청까지 가는 길(condition_check 켬, 기준일 2026-09-25):**
1. 질문의 "지난달"을 `conditions.scan_dates`가 `last_month`로 읽는다(`status=interpreted`, LLM 값과 다르면 `conflict`+`corrected`).
2. 기록 범위는 `20260801-20260831`이다.
3. compiler가 요청 인자를 정한다. 토큰 의미(`relative_date_reference`)와 범위 의미(`range_inclusive`)는 확인되지 않았다. 하루 합성은 aggregation과 Tool 기록 계약을 본다(avg면 불가, sum이어도 `day_records:get_operation_metrics`가 관찰 상태라 불가).
4. 결과는 `DATE_EXECUTION_UNVERIFIED`다. 측정 호출은 한 번도 나가지 않는다. 오류 context에 해석 범위와 빠진 계약이 남는다.

### 하루 단위 합성(`tims_contract.daily_composition`)

- 수학 조건: 집계가 sum·max·min이어야 한다. avg·med는 표본 수·원시 값이 없으므로 합치지 않는다. 고유 개수와 비율의 비율도 합치지 않는다. 지금 Tool 중 결과가 고유 개수인 것은 없다.
- 데이터 조건: 기록이 하루 하나에만 속하고, aggregation이 그 기록에 바로 적용되어야 한다. max·min도 기간 전체에서 택시별 중간 집계가 먼저 있으면 하루 최댓값으로 다시 만들 수 없다.
  - get_operation_metrics: schema는 "일 단위 택시 영업"이라고 적는다. 그러나 "운행률은 기간으로 합산하면 평균 운행일이 산출됨"은 택시별 중간 집계의 여지를 남긴다. 그래서 **관찰(OBSERVED)** 로 두었다.
  - trip·passage·drive: 날짜 귀속 규칙이 없다. **알 수 없음**이다.
- 목록 결과(dimension·order·limit)는 합치지 않는다. 호출 상한은 62번이다.
- 합성 경로는 코드와 검증(`_verify_relowered_period`)까지 있다. 하지만 기본 계약에서는 열리지 않는다. 테스트는 가정한 계약(`assuming`)으로만 연다.

### mock provider의 명시적 계약

`tims_contract.MOCK_PROVIDER_CONTRACT`는 "날짜 문자열을 해석하지 않음, 합성 불가"를 적는다.
compiler는 이것을 쓰지 않는다. TIMS 계약으로 승격하지도 않았다. 채점기가 mock 정답과 provider 의미를
나누는 근거다.

## 3. 조건 상태: 문법 미인식과 조건 부재의 구분

| 상태 | 뜻 | 처리(action) | 근거 기록(basis) 예 |
|---|---|---|---|
| interpreted | 지원 문법으로 읽고 값을 정함 | confirmed / filled / confirmed_equivalent | question_expression |
| conflict | 읽은 값과 LLM 값이 다름 | corrected(질문 표현을 따름) | question_expression_over_llm_value |
| ambiguous | 표현은 있으나 뜻이 하나가 아님 | 확인 요청(DATE_AMBIGUOUS, DATE_CONFLICT) | yearless_date, relative_and_explicit |
| unverifiable | 단서는 있으나 읽지 못함 | held(LLM 값을 쓰되 검증 안 됨) / flagged(값이 없음) | unparsed_date_cue, unparsed_type_cue, unparsed_date_cue_beside_expression |
| absent | 표현도 단서도 없음 | none / removed_no_evidence | llm_value_has_no_anchor_and_no_date_cue |
| unsupported | 읽었지만 지원하지 않는 계산 | 지원 불가 | unsupported_expression, negation, multiple_types |

- **삭제 기준.** LLM 값의 근거 표현이 질문에 없고, 그 조건을 말하는 단서도 없을 때만 지운다. 근거 표현은 연·월 숫자, "9/24" 같은 숫자 표기, 상대어, "개인"·"법인" 등이다. 규칙이 매칭되지 않았다는 이유만으로는 지우지 않는다.
- **보류(held).** 값은 실행에 쓰이지만 `status=unverifiable`이다. `audit.held`에 오르고, `verification.verified`에서 빠지며, 답변에 "현재 문법으로 검증하지 못한 LLM 값"이 붙는다. 날짜를 보류했으면 guaranteed 정책이 따로 적용된다. 단일 날짜가 아니면 멈춘다.
- **flagged.** 단서는 있는데 LLM 값도 없다("영업용 택시", "지난 금요일"). 조건 부재로 확정하지 않는다.
- **읽은 표현 옆의 달력 단서.** "지난주 금요일", "지난달 말"에서 요일·초·말이 남으면 읽은 부분(`last_week`)으로 확정하지 않고 보류한다. 확인 평가 셋을 쓰다 알아챈 결함이다.
- **전체 택시.** `all`은 생략과 실행 의미가 같다(계약 `taxi_type_all_unrestricted`, CONFIRMED, 인용 "all=조건 미적용"). 사용자가 명시했으면 `stated=explicit_all`, `action=confirmed_equivalent`로 남긴다. 보정으로 세지 않는다.
- **범위 밖.** core concept, 집계 구조, scope provenance는 바꾸지 않는다. `reconcile_payload`가 끝에서 확인한다.

**미지원 목록 확장에 기대지 않은 부분.** 새 상태는 "단서가 남았는가"와 "LLM 값의 근거 표현이 있는가"라는
일반 조건으로 판정한다. 단서 목록 자체는 여전히 닫힌 어휘다. 목록 밖 표현이 단서조차 남기지 않으면
(예: "택시 유형 구분 없이") `absent`로 판정된다. 이것이 남은 한계다(§7).

### 장소 감사

- 장소 검사는 **이름이 질문에 있다는 문자열 근거만** 본다(`semantics=name_evidence_only`). "서구"가 어느 도시의 서구인지는 보지 않는다.
- 여러 장소 중 하나만 출력돼도 **탐지하지 못한다**. 테스트 `test_one_of_two_places_output_is_not_detected_and_not_reported_complete`가 이 한계를 고정한다.
- 그래서 `verification.complete`는 언제나 거짓이다. place는 언제나 `unverified`에 들어간다. 답변의 "검증 범위" 줄은 "장소는 이름 근거만 확인(지역 의미·누락은 미검증)"이라고 적는다.

## 4. 평가·채점 정리

### 채점기 v2(`condition_scoring.py`)

- 기간은 gold의 `accept` 목록으로 비교한다. v1 gold는 원본을 두고 `evaluation/labels/condition_date_equivalents_v1.yaml`(손으로 센 동치 범위)을 더한다.
- taxi_type all은 생략과 같게 비교한다. `taxi_stated`(explicit_all / not_stated)는 따로 보존한다. private·corporate는 all과 합치지 않는다.
- grounding이 거부되면 `not_judgeable`이다. 누락으로 세지 않는다.
- 지표를 따로 센다.
  1. 해석(`interpretation_ok`)
  2. 요청 인자 보존(`request_ok`)
  3. provider 의미 확인(`provider_date_confirmed`, 채점기 안의 정규식. 단일 날짜 호출 하나 또는 기간 없음만 확인. 여러 날짜 합성은 `day_records` 미확인이라 미확인)
  4. mock 정답(gold 요청 인자와 같은 호출. 하루 합성은 `mock_not_comparable`)
  5. 실제 데이터 정답(`not_measured`)
  6. 조용한 의미 오류와 `answered_provider_unverified`
  7. 부당한 거부와 `contract_refusal`
  8. 보정(good / bad / unnecessary / wrong_to_wrong)
- 거부 원인을 contract / condition / aggregation / other로 나눈다. 계약 코드로 멈췄더라도 집계 계획이 틀렸으면 aggregation으로 센다(v2.1).
- 검증 상태가 unverifiable인 조건은 값이 맞아도 `verified_ok`로 세지 않는다.

채점기 버전 이력: v2.0→v2.1(계약 거부와 집계 오류 구분)→v2.2(여러 날짜 합성은 provider 미확인)→
v2.3(`correct_contract_executable` 추가). 모두 확인 평가 전에 바꿨고, v2.3으로 고정한 뒤 측정했다.

### 기록 보호(`evaluation_records.py`)

- 새 채점은 `RUN_DIR/analyses/<id>/`에 쓴다. 같은 id가 있으면 `-2`를 붙인다. 파일은 `"x"` 모드로만 연다.
- `manifest.json`에 채점기 이름·버전·소스 hash, 설정, 원자료 hash, 출력 hash, 정정 연결(`corrects`: 이전 경로와 이유)을 남긴다.
- `structured_grounding_eval.score`는 `summary.json`이 없을 때만 새 파일로 쓴다. 이미 있으면 `analyses/legacy-v1.1/`에 쓴다.
- `verify_inputs()`는 원자료가 바뀌었는지 확인한다.
- 없는 원본을 추정해서 다시 만들지 않았다. eval_v1 run에는 실행 인자 기록이 없어서 요청·provider 층은 `request_not_recorded`로 둔다.

### Case N 정정 분석(cond_v1_4arms)

최초 판정 **Case N은 삭제하거나 바꾸지 않는다.** `summary.json`, `judged.json`, `summary_rescored.json`,
`judged_rescored.json`도 그대로 둔다. 정정 분석은 `analyses/v2-corrected/`(채점기 v2.1)에 두고, manifest가
위 두 summary를 `corrects`로 가리킨다. 여러 날짜 호출이 없는 run이라 v2.2·v2.3에서도 수치가 같다.

| 지표(32문항, 1회) | flat | flat+cc | structured | structured+cc |
|---|---|---|---|---|
| 최초 정답(v1 summary.json) | 20 | 24 | 16 | 24 |
| 정정 정답(v2, 요청 인자 기준) | 20 | 24 | 17 | 24 |
| 그중 provider 기간 의미 확인 | 4 | 4 | 3 | 4 |
| provider 의미 미확인 답 | 18 | 20 | 15 | 20 |
| 조용한 의미 오류 | 5 | 0 | 10 | 1 |
| 해석 정확 / 판정 가능 | 22/26 | 26/26 | 19/28 | 26/26 |
| 판정 불가(grounding 거부) | 6 | 6 | 4 | 6 |
| 보정 good / bad / unnecessary | – | 5/0/1 | – | 7/0/2 |
| 부당한 거부 | 3 | 1 | 2 | 0 |

정정 사항과 근거는 다음과 같다.
- (a) c04의 "잘못된 보정"은 all 정규화 누락 때문이다. v2에서는 `unnecessary`로 셈한다. 실행 인자의 의미는 같다.
- (b) structured의 정답 16→17과 조용한 오류 11→10: "지난달"을 같은 뜻의 절대 범위로 적은 관측 1건을 인정했다(addendum).
- (c) flat+cc의 부당한 거부 1(c25)은 집계 오류(지어낸 `bucket: month`)로 멈춘 것이다.

결과를 본 뒤 정정했으므로 이 표는 **독립 확인이 아니다.** 판정의 근거는 §6의 확인 평가다.

## 5. 결정적 테스트(A)

`tests/test_geoflow_conditions.py` 51건, `tests/test_condition_scoring.py` 9건이다. 전체는 806건 통과(기대된 실패 1).
기대값은 달력과 FakeTims 자료에서 손으로 셌다. 예: 2026년 8월 대구 개인택시 매출 합계 1150.
- 같은 "지난달"을 다른 기준 시각·시간대에서 푼다(UTC·LA 시각 → KST 9/1 → 8월, 9/30 → 8월, 10/1 → 9월).
- provider 상대 기준이 로컬과 다르면(가정 "UTC calendar") 통과하지 않는다. 같으면(가정 "Asia/Seoul calendar") 토큰을 넘긴다.
- 범위 계약이 없으면 명시 범위로 바꾸지 않는다. 가정하면 `explicit_range`로 바꾼다.
- sum·max·min은 합성 가능하고 avg·med는 불가다. 목록 결과, 62일 초과, 기록 계약 없음, trip 개수도 불가다. 가정한 계약에서 31번 하루 호출의 합이 1150이다.
- 미지원 표현의 맞는 LLM 값을 지우지 않는다("개인 사업자 택시", "9/24", "지난달 15일", "지난주 금요일", "지난달 말"). 단서만 있고 값이 없으면 flagged로 둔다.
- 명백한 누락(개인택시 보완)과 추가(근거 없는 법인·날짜 삭제)는 탐지한다.
- 장소 일부가 빠져도 탐지하지 못하지만, 전체 검증 완료로 표시하지 않는다.
- 재질의가 근거 기록·aggregation_plan·장소 이력을 보존한다.
- 채점 정규화(같은 의미 = 같은 점수, private/corporate ≠ all, 거부 ≠ 누락, 보류 ≠ 검증, 요청 인자 ≠ provider 의미, good/bad/unnecessary)와 기록 보호가 동작한다.
- 정상 수용: 단일 날짜 질문은 보정 없이 또는 보정 후 실행한다(`verified=[date, taxi_type]`).

## 6. 기존 자료 재생(B)

근거 파일은 `condition_verification_replay.json`이다. LLM 호출 없이 기록된 원문을 구 코드(`120c462`, worktree)와 새 코드로 돌렸다.

**재현.**
- 구 코드 재생은 녹화 결과와 같다(cond_v1 128/128, eval_v1 cc 없이 60/60).
- 구 채점기를 다시 계산하면 `summary_rescored.json`과 같다. `summary.json`과는 bad_corrections만 다르다.
- 새 코드의 기본 경로(cc 끔)는 구 코드와 같다(cond 64/64, eval 60/60, census M0 210/210, M2 211/211).

**cc 켬, 구 코드 → 새 코드 전이.**

| 자료 | 정답→거부 | 오답→거부 | 오답→정답 | 검증됨→미검증 | 계약으로 확인된 답(구→새) |
|---|---|---|---|---|---|
| cond_v1 flat+cc(32) | 20(모두 계약 거부) | 0 | 0 | 0 | 4→4 |
| cond_v1 structured+cc(32) | 20 | 1(c25, 집계 오류가 계약 코드로 멈춤) | 0 | 0 | 4→4 |
| eval_v1 flat+cc(30, 두 단계) | 8 | 5 | 0 | 0 | 0→0 |
| eval_v1 structured+cc(30) | 11 | 9 | 0 | 0 | 0→0 |
| census M0(210) | 24 | 0 | 0 | 0 | 116→116 |
| census M2(211) | 27 | 0 | 0 | 0 | 125→125 |

새로 생긴 거부는 모두 `DATE_EXECUTION_UNVERIFIED`나 `UNVERIFIED_TIMS_CONTRACT`다. 사라진 답은 모두 provider
의미가 확인되지 않은 답이었다. **정확성이 좋아진 것이 아니라 보장하지 못하는 답을 거부로 바꾼 것이다.**
eval_v1의 두 단계 질문은 `day_records` 미확인으로 cc 경로에서 모두 멈춘다. 이것이 확인되어 이 셋은 더 돌리지 않았다.
구조화 경로의 회귀는 이 재생과 결정적 테스트로만 확인했다.

## 7. 확인 평가(C)

run `evaluation/structured_grounding/20260926_184342_cond_v2_flat_vs_cc`, 채점
`analyses/v2.3-preregistered/`. 판정 규칙은 `evaluation/prompt_ab/variants/condition_check_v2_decision_rule.md`로
측정 전에 고정했다. 실행기가 자동으로 쓴 `summary.json`·`judged.json`은 v1 채점기 출력이다. v2 gold
형식(`accept` 목록)에 맞지 않으므로 판정에 쓰지 않는다(삭제하지 않고 둔다).

조건은 다음과 같다.
- 새 셋 36문항: 답할 수 있음 28(계약상 실행 가능 22), 미지원 6, 확인 필요 2. 문장 틀·미지원 표현·조건 부재·명시적 전체·상대 기간·여러 장소를 포함한다.
- qwen3:8b, temperature 0, flat prompt `64bbceb4`, 기준일 2026-09-25 Asia/Seoul, mock provider, `DEFAULT_CONTRACT`, timeout 300초
- 반복 1회, arm 순서 회전, 관측마다 unload와 cold load 확인. 무효 0, crash 0

| 지표 | flat | flat+cc |
|---|---|---|
| 1. 조건 해석 정확 / 판정 가능 | 22 / 29 | 25 / 26 |
| 판정 불가(grounding 거부 또는 조건 계층이 계획 전에 멈춤) | 7 | 10 |
| 2. 요청 인자 보존 / 측정 호출이 나간 관측 | 21 / 27 | 18 / 18 |
| 3. provider 기간 의미 확인(측정 호출 관측 중) | 18 | 18 |
| 4. mock 기준 정답(gold 요청 인자와 같은 호출) | 21 | 18 |
| 5. 실제 데이터 기준 정답 | 미측정 | 미측정 |
| 정답(요청 인자 의미 기준) | 21 | 18 |
| 계약상 실행 가능한 질문(22)의 정답 | 15 | 18 |
| 6. 조용한 의미 오류 | 6 | 0 |
| provider 의미가 확인되지 않은 답 | 6 | 0 |
| 7. 부당한 거부(답할 수 있는 28 중) | 4 | 4 |
| 계약 한계로 멈춤(답할 수 있지만 계약상 실행 불가 6 중) | 0 | 6 |
| 확인 요청이 맞음(2) | 0 | 2 |
| 8. 보정 good / bad / unnecessary | – | 3 / 0 / 0 |
| 검증했다고 적은 조건: 맞음 / 틀림 / 보류 | – | 50 / 0 / 2 |
| 거부 원인 contract / condition / aggregation / other | 0/3/0/6 | 7/6/0/5 |
| LLM 호출 / Tool 호출 | 37 / 56 | 37 / 38 |

전이(flat → flat+cc, 같은 질문):
- 정답→정답 15
- 조용한 오답→정답 2(d03, d04: "어제"·"오늘"을 LLM이 다른 날로 적은 것을 보정)
- 조용한 오답→올바른 미지원·확인 요청 3(d25, d27, d29)
- 조용한 오답→거부 1(d06: "지난주 금요일". 보류한 LLM 값이 `last_week`라 계약 한계로 멈춤. 계약상 실행 가능한 질문이므로 부당한 거부로 셈)
- 부당한 거부→정답 1(d35: 첫 응답은 두 arm이 같고 `order=bottom`을 dimension 없이 적어 조합 오류가 났다. cc는 날짜 `20260529`를 "어제"로 보정했다. 이어진 재질의에서 flat은 `unsupported`, cc는 `dimension=emd`를 더해 실행했다. 조건 보정의 효과라기보다 재질의 응답의 차이이고, 목록 질의가 된 답을 채점기가 정답으로 셌다. 아래 한계 참고)
- 형식 오류 실패→올바른 미지원·확인 요청 3(d24, d26, d28)
- **정답→계약 한계 거부 6**(d18~d23: 상대 기간·범위. flat은 provider 의미 확인 없이 답했다)
- 양쪽 모두 부당한 거부 3(d02, d05, d12: LLM grounding 실패 INVALID_CONCEPT·INVALID_PLACE. 조건 계층 앞 단계)
- 양쪽 모두 gold와 다른 실패 2(d17, d32: 미지원이 기대이나 INVALID_CONCEPT·AMBIGUOUS_LOCATION_RELATION으로 실패)

**사전 규칙 판정: Case K**(K1~K9 모두 충족).
- K1: 조용한 오류 6→0
- K2: 잘못된 보정 0
- K3: 검증 오판 0
- K4: 미확인 답 0
- K5: 계약상 실행 가능한 질문의 부당한 거부 4→4
- K6: 계약상 실행 가능한 질문의 정답 15→18
- K7: 해석 22→25
- K8: LLM 37→37, Tool 56→38
- K9: crash 0, 무효 0

해석은 다음과 같다.
- condition_check는 **계약 안에서** 조건을 더 정확히 보존한다. 보장하지 못하는 답은 내지 않는다.
- 대가로 상대 기간·범위 질문 6건을 계약 한계로 멈춘다. flat이 답하던 질문들이다. 전체 정답 수는 21→18로 줄었다.
- 이것은 정확성 저하가 아니다. 보장 범위 밖의 답을 거부로 바꾼 것이다. 다만 사용자가 보는 답의 수는 줄어든다.
- 표본은 36문항 1회다. 지명과 측정값 어휘가 기존 셋과 겹치고, d06은 개발 중 인지한 사례다. 차이를 일반 성능으로 확대 해석하지 않는다.
- 기본 설정은 바꾸지 않았다. Case K는 "선택 기능 후보로 유지"의 근거이지 production 기본값 전환의 근거가 아니다.

측정 중 발견한 한계(사후에 기준·코드를 바꾸지 않았다):
- d13 "택시 유형 구분 없이": 실행 의미는 맞다(LLM all ≡ 생략). 그러나 어휘 밖 표현이라 `stated=not_stated`로 기록된다. 규칙 미매칭으로 "명시 안 함"을 확정한 provenance 결함이다.
- d06: 요일 단서로 보류는 했다. 그러나 보류한 LLM 값이 틀려 멈췄다. 보류는 오류를 막을 뿐 바른 날짜를 만들지 않는다.
- d35: cc 쪽 grounding에 `dimension=emd`, `order=bottom`이 붙었다. 채점기는 dimension·order를 판정하지 않는다. 두 arm에 같은 한계다.

## 8. 남은 제한과 다음 작업

- **condition_check의 실용성은 vendor 계약에 달려 있다.** `range_inclusive`, `relative_date_reference`(기준 시각·시간대), `day_records:<tool>`(날짜 귀속과 aggregation 단위)이 확인되기 전에는 상대 기간·범위·두 단계 질문을 이 경로에서 실행하지 않는다. vendor 문서나 실제 provider 응답(mock 아님)으로 확인해야 한다.
- 조건 단서 어휘는 닫혀 있다. 목록 밖 표현이 단서도 남기지 않으면 부재로 판정된다(예: "유형 구분 없이"는 all과 생략의 실행 의미가 같아 해가 없다. "법인이 아닌"은 부정 단서를 요구하는 표현이다).
- 장소 누락·지역 의미·출발/도착 의미는 검증하지 않는다. Gazetteer 목록 대조나 별도 검증이 필요하다.
- 기본 경로의 구간별 하루 분할은 `day_records`를 가정한 채 실행된다(assumptions에 기록). 기본 경로에도 같은 제한을 걸지는 사용자가 판단할 일이다.
- 실제 데이터 기준 정답은 측정하지 않았다.

## 9. 재현

```bash
python -m unittest discover -s tests
python condition_scoring.py evaluation/structured_grounding/20260926_133550_cond_v1_4arms \
  --analysis-id v2-corrected --addendum evaluation/labels/condition_date_equivalents_v1.yaml \
  --corrects .../summary.json .../summary_rescored.json --reason "..."
git worktree add /tmp/old 120c462 && cp condition_replay.py geoflow_replay_compare.py /tmp/old/
python condition_replay.py RUN_DIR --arm flat --condition-check on --label flat+cc --out X.jsonl
python geoflow_replay_compare.py evaluation/prompt_ab/20260925_171514_model_M0_census --condition-check --out Y.json
python structured_grounding_eval.py run evaluation/structured_grounding/eval_questions_conditions_v2.yaml \
  --name cond_v2_flat_vs_cc --arms flat,flat+cc
python condition_scoring.py RUN_DIR --analysis-id v2.3-preregistered
```
