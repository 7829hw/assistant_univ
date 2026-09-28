# v2 최초 실측 분석: qwen3:8b (holdout_v2, stub v2)

**잠정치.** 평가셋·기대값은 Claude가 작성했고 사람이 검토하지 않았다(registry `review.status:
unreviewed`). mock 고정값으로 실행했으므로 실제 데이터의 수치 정확도는 검증하지 않았다. 채점 대상은
결과 종류, 측정값·라벨, 집계 의미, 최종 Tool 인자·조건, 답변 형식이다(`evaluation/v2/preregistration_v2.md`).
숫자는 모두 **문장(관측) 단위**이고, intent 단위는 따로 표시한다. 자동 집계는 `report.md`,
`report.json`(생성: `evaluation/v2/report_v2.py`), 원 기록은 `observations.jsonl`이다.

## 실행 조건

| 항목 | holdout | stub(개발용) |
| --- | --- | --- |
| run | `20260929_014313_v2_holdout_qwen3_8b` | `20260929_014032_v2_stub_qwen3_8b` |
| 커밋 | `5c2991e` (dirty 없음) | `14cb4b9` (dirty 없음) |
| 명령 | `python evaluate_v2.py run --model qwen3:8b --sets holdout_v2 --label v2_holdout_qwen3_8b` | `... --sets stub --label v2_stub_qwen3_8b` |
| 시각(KST) | 2026-09-29 01:43:13 – 02:11:56 | 01:40:32 – 01:42:19 |
| 관측 | 126 (유효 126, 재시작 0) | 5 (유효 5) |

- 모델 `qwen3:8b` digest `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`
  (qwen3, 8.2B, Q4_K_M, gguf), Ollama 0.34.4, options `{"temperature": 0}`, think=auto, chat timeout 300초.
- production 기본 설정: geoflow, flat grounding, condition_check 끔, mock + TIMS legacy, 예시 검색 끔.
- 기준일 2026-09-25(Asia/Seoul, pipeline clock 고정).
- planner prompt sha256 `db113124b2e26aa9b47b7f6d9e56387becd19e6add2debaab54657598c171ba8`.
- 입력 sha256: holdout `d1884be4…`, 부모 `25d2d350…`, stub gold `1cde411c…`, mock_stub `180550f4…`
  (registry 값과 같음). 채점기는 사전 등록(`075a6a5`) 이후 문서화된 두 변경(run 디렉터리 생성 순서,
  dirty 검사 경로)만 있고 채점 코드는 바뀌지 않았다.
- 격리: 실행 시작 시 서버에 올라간 모델은 없었고(`/api/ps` 비어 있음), 관측마다 `qwen3:8b`만 내리고
  cold load(≥ 500ms)를 확인했다. 다른 사용자의 GPU 프로세스(0·1번 GPU)나 컨테이너는 건드리지 않았다.
- 기록 한계: 재계획 LLM 호출도 `llm_calls[].phase`가 `initial`로 남는다(RecordingClient phase를
  파이프라인이 바꾸지 않음). 유효성 판정·채점에는 영향이 없다.

## stub v2 (개발용, 이미 본 질의)

의미 정답 3/5, 실행 완료 4/5.

| id | 기대 | 실제 | 범주 | 원인 |
| --- | --- | --- | --- | --- |
| q01 | answered | answered | correct | |
| q12 | answered | answered | correct | |
| q16_1 | answered | failed | grounding_failure | "개인용 택시"를 `OBJECT/taxi_type` 개념으로 만듦 → `INVALID_SUBTYPE` |
| q18 | answered | answered | wrong_tool_args | 동성로동(region 대구) NOT_FOUND(mock 계층 결함) → 재계획이 동성로(도로 edge)로 바꿈. `scope_pickup` 기대 `scope:district:2711012300`, 실제 `scope:edge:1742` |
| q20 | answered | answered | correct | |

두 실패 모두 모델 오답(q18은 mock 결함이 촉발)이며 실행기 결함이 아니다. holdout 전에 실행기를 바꾸지 않았다.

## holdout_v2 핵심 수치 (문장 단위, 분모 126)

| 지표 | 값 |
| --- | --- |
| 의미 정답(전체) | 52/126 (41.3%) |
| 실행 완료(answered 기대 문장 중 답함) | 46/78 (59.0%) |
| 의미 정답(answered 기대 문장) | 42/78 (53.8%) |
| 거부 정확도 strict(기대 종류로 멈춤) | 10/48 (20.8%) |
| 보조: 거부 기대 문장에서 답하지 않음 | 42/48 (87.5%) |

보조 지표(답하지 않음)는 올바른 거부가 아니다. 42건 가운데 23건은 planner 단계 실패(`failed`), 9건은
다른 종류의 거부다. 사전 등록 점수는 strict다.

intent 단위(42): 세 문장 모두 정답 10/42 (23.8%), 과반 정답 16/42 (38.1%).

### 기대 결과별

| 기대 결과 | 문장 정답 | intent(3/3) | intent(≥2/3) |
| --- | --- | --- | --- |
| answered (26 intent) | 42/78 (53.8%) | 9/26 | 13/26 |
| needs_clarification (5 intent) | 0/15 (0.0%) | 0/5 | 0/5 |
| unsupported (11 intent) | 10/33 (30.3%) | 1/11 | 3/11 |

### 기대 × 실제 (문장)

| 기대 \ 실제 | answered | needs_clarification | unsupported | failed |
| --- | --- | --- | --- | --- |
| answered (78) | 46 | 11 | 2 | 19 |
| needs_clarification (15) | 3 | 0 | 5 | 7 |
| unsupported (33) | 3 | 4 | 10 | 16 |

### 절별

| 절 | 문장 정답 | 실행 완료 | 거부 strict | intent(3/3) |
| --- | --- | --- | --- | --- |
| A aggregation holdout 복원 (10) | 7/30 | 8/18 | 1/12 | 1/10 |
| B local aggregation holdout 복원 (10) | 8/30 | 9/18 | 0/12 | 2/10 |
| C verifier holdout 복원 (7) | 16/21 | 16/18 | 0/3 | 5/7 |
| D v2 거부 (7) | 9/21 | - | 9/21 | 1/7 |
| E v2 경계 (8) | 12/24 | 13/24 | - | 1/8 |

stage-swap 대상 두 단계 answered intent 11개: 문장 정답 9/33 (27.3%), intent(3/3) 0/11. 그중 순서를
실제로 뒤바꾼 것은 1건(w16_p0: 구간 안 min·구간별 sum, 기대 sum→min)이고, 나머지 실패는 날짜 형식과
구간 안 집계 누락이다. 구간 없는 대조군(w07·w19·w20·w23·w25·w26·w27)은 21/21 정답이다.

### 범주 (문장)

correct 52, failed_instead_of_refusal 23, grounding_failure 15, refused_supported 13,
wrong_refusal_kind 9, answered_instead_of_refusal 6, execution_failure 4, aggregation_error 3,
wrong_tool_args 1, answer_format_error 0.

## 실패 원인 (관측 trace 기준)

1. **월 단위 기간을 YYYYMM으로 적음 — 28문장.** "2026년 7월부터 8월까지" → `"202607-202608"`,
   "2026년 8월" → `"202608"`, "올해" → `"2024"`. pt_date 형식이 아니어서 grounding 검증에서
   `INVALID_FACTOR`로 끝난다. answered 기대 12문장이 grounding_failure, 거부 기대 16문장이
   failed_instead_of_refusal. A·B절 두 단계 문항 대부분이 여기서 막혀 집계 판단까지 가지 못했다.
   예: w08_p0 "2026년 8월 택시 운행일수의 합계는?" → `{"date": "202608", "aggregation": "sum"}`.
   production 기본값은 condition_check가 꺼져 있어 질문 원문으로 날짜를 다시 정하지 않는다
   (condition_check는 이 형식을 보정하는 규칙이 있다 — 효과는 이번에 재지 않았다).
2. **명시된 구간 안 집계를 빠뜨림 — 15문장**(answered 기대 11, unsupported 기대 4). 예: w21_p1 "운행일수를 지난달 주마다 더했을 때 가장 큰
   값은?" → `{"bucket": "week", "rollup": "max"}`(aggregation=sum 누락) → 제품이
   `AMBIGUOUS_INNER_AGGREGATION`으로 확인 요청 → refused_supported. 두 단계 answered 문항의 주된 실패다.
3. **구간 안 집계가 없는 질문에 집계를 지어냄 — needs_clarification 0/15.** w04 "지난달 주별 택시 요금의
   최댓값은?" 세 문장 모두 `{"bucket": "week", "aggregation": "max"}`로 답했다(answered_instead_of_refusal).
   w14·w17·w22는 avg·med를 구간 안 집계로 넣어 계약 미확인(UNVERIFIED_TIMS_CONTRACT) unsupported가
   되었다(wrong_refusal_kind). flat 표기에서 bucket과 함께 쓴 aggregation은 구간 안 집계로 읽힌다.
4. **모델은 한 번도 `{"unsupported": true}`를 내지 않았다(0/126).** 올바른 거부 10건은 모두 제품 검사에서
   나왔다: `UNDEFINED_MEASURE_AGGREGATION` 4(w30 3/3, w31_p1), `PARAM_VALUE_FORBIDS_INPUT` 2(w33),
   `PARAM_VALUE_REQUIRES_INPUT` 2(w34), `UNVERIFIED_TIMS_CONTRACT` 2(w05_p2, w32_p2).
   - 없어진 측정값: w28(영업 시간)은 `hours`를 내지 않고 측정값 없이 `OBJECT/taxi_type`만 만들어
     `INVALID_SUBTYPE` failed(3/3). w29(영업 횟수)는 `operating_days`로 바꿔 답했다(2/3,
     answered_instead_of_refusal) — v2 prompt가 금지한 "비슷한 측정값으로 바꾸기"다.
   - w33_p2는 "대구"를 버리고 요일별 수입만 답했다(조건 누락으로 답함).
   - w31·w32는 고유 대수·가동률 질문에서 구간 안 집계를 빠뜨려 needs_clarification으로 멈췄다(4건).
5. **그룹 단어를 장소로 만듦 — 4문장(E절).** w36_p1 "하차가 가장 적은 시군구 2곳" → LOCATION/place
   `{"name": "시군구"}` → `get_place_scope` NOT_FOUND → execution_failure. w37 두 문장은 값 없는 장소
   개념(VALUELESS_CONCEPT). dimension_target 자체는 w35·w36·w37의 grounding 대부분이 맞게 적었다
   (pickup/dropoff/both). 
6. **상대 기간을 절대 날짜로 틀리게 적음 — 4문장.** 지난달·이번 달 → `"20260501-20260531"`
   (기준일 2026-09-25와 무관한 날짜). w41_p1은 wrong_tool_args, 나머지는 다른 오류와 겹쳤다.
   this_* 토큰은 12문장 중 9문장에서 맞게 썼다(this_week 3/3, this_month 4/6, this_year 2/3).
7. **택시 유형을 개념으로 만듦 — 4문장**(w10_p1, w28 3건), stub q16_1과 같은 유형.

실행기·채점기 결함은 찾지 못했다. 답한 52문장 모두 답변 형식 검사를 통과했고, 단위 문자열 결과
(w13 "35%", w42 "30km/h")도 정상 표시되었다. 원인 설명 1–7은 관측된 LLM 원문 출력과 오류 코드에서
직접 읽은 것이다. 모델이 왜 그렇게 출력했는지(예: 월 단위 날짜 형식을 prompt 예시에서 배우지 못함)는
추정이며 검증하지 않았다.

## 해석 시 주의

- golden 주입 테스트(42/42 정답)와 가짜 서버 배선 테스트는 채점기의 자기 점검이며 모델 실측이 아니다.
- v1 README의 모델별 정확도와 직접 비교할 수 없다: 계약(측정값 어휘, Tool 이름, scope·dimension 규칙),
  질의(v1 stub 14 + boundary 24 vs v2 stub 5 + holdout_v2 126), 채점 범위(v1은 grounding·합성 단계,
  v2는 실행과 답변까지), 격리 절차가 다르다.
- 이 결과를 본 뒤 holdout_v2는 development로 취급한다(registry). 이 결과로 prompt·검색·조건 보정을
  바꾸면 그 개선의 최종 평가에는 새 holdout이 필요하다.
