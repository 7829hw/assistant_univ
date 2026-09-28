# v2 평가 사전 등록 (holdout_v2, stub v2)

2026-09-29 작성. 모델 실행 전에 이 문서, 문항 파일, 채점기(`evaluate_v2.py`)를 한 커밋으로 고정한다.
결과를 본 뒤 라벨·기준·채점 규칙을 바꾸지 않는다. 문항과 라벨은 Claude가 썼고 **사람이 검토하지
않았다**(registry `review.status: unreviewed`). 그래서 이 평가셋의 결과는 잠정치다.

## 1. 목적

업체 v2 계약(`get_billing_metrics`, 측정값 revenue·active_taxi_count·active_taxi_ratio·
operating_days)으로 바꾸면서 v1 고정 corpus의 intent 36개가 지원 범위 밖이 되었다(registry
`v2_contract.retired`). 그중 두 단계 집계·국소 집계·의미 검증 평가를 떠받치던 27개를 v2에서 뜻이
정해진 질문으로 되살리고, v2 거부 동작과 경계 동작을 따로 잰다. 기존 corpus와 이력은 그대로 둔다.

| 되살린 corpus | 빠진 intent | 새 intent |
| --- | ---: | --- |
| paraphrases_aggregation_holdout | 10 (a01·a04·a05·a06·a11·a12·a13·a15·a17·a18) | w01–w10 |
| paraphrases_local_aggregation_holdout | 10 (l02·l03·l04·l07·l08·l10·l12·l13·l15·l20) | w11–w20 |
| paraphrases_verifier_holdout | 7 (v01·v03·v04·v07·v08·v10·v20) | w21–w27 |

metric 이름만 바꾸지 않았다. 각 intent가 검사하던 능력(구간 안/구간별 집계의 조합, stage-swap,
구간 안 집계 미지정, 구간 없는 대조군, 택시 유형·장소 조건, verifier family)을 `capability`에 적고,
그 능력을 v2 측정값으로 다시 묻는 질문을 새로 썼다.

## 2. 설계 기준

측정값의 집계 의미는 `geoflow/measures.py`가 기준이다(근거 문장 포함). 계약에 뜻이 없는 집계는
정답으로 두지 않는다.

- 두 단계 집계(구간 안 → 구간별)는 기록마다 값이 있는 측정값으로만 답을 기대한다: 요금(fare, trip
  기록), 운행일수(operating_days, 택시별 기간 집계, 합만 하루 분해 가능), 공차율(vacant_ratio,
  drive 기록 비율, 최대·최소), 속도(speed, 최대·최소).
- 고유 대수(활성택시 대수)와 집단 비율(가동률)은 하루 값으로 기간 값을 만들 수 없고, 합계는 뜻이
  없다. 이런 질문은 거부를 기대한다(w30–w32).
- 비율·속도의 합계, 고유 대수의 합계는 `UNDEFINED_MEASURE_AGGREGATION`으로 거부한다.
- 구간 안 평균(avg)은 하루 값으로 다시 만들 수 없고 구간 범위 호출은 `range_inclusive`가 확인되지
  않아(OBSERVED), 현재 계약(mock + legacy)에서는 실행하지 않는다. 이런 질문(w05·w06·w12·w18)은
  `expected_outcome: unsupported`이고 의미 graph(구간·구간 안·구간별 집계)는 따로 채점한다.
- 구간 안 집계가 질문에 없으면 `needs_clarification`(w04·w10·w14·w17·w22).
- 실행 완료율을 잴 수 있게 두 단계 질문에는 기간을 넣었다(하루 분해 상한 62일 이하: 지난달,
  2026년 7월부터 8월까지, 이번 달).
- 이번 주/달, 올해는 v2 pt_date 토큰(this_*)이다. 로컬 분할의 기간은 애플리케이션 정책(기간 시작일
  부터 기준일까지, 월요일 시작, Asia/Seoul)이며 TIMS 계약이 아니다(`geoflow/periods.py`).
- 부모 라벨(expected_macros/operators)은 golden grounding을 실제 composer로 조합해 얻었다.

## 3. 구성

| 절 | 내용 | intent | answered | needs_clarification | unsupported |
| --- | --- | ---: | ---: | ---: | ---: |
| A | aggregation holdout 복원 | 10 | 6 | 2 | 2 |
| B | local aggregation holdout 복원 | 10 | 6 | 2 | 2 |
| C | verifier holdout 복원 | 7 | 6 | 1 | 0 |
| D | v2 거부(없어진 측정값, 뜻 없는 집계, schema 금지 조합) | 7 | 0 | 0 | 7 |
| E | v2 경계(dimension_target, this_*, {count}·지역명·단위 문자열) | 8 | 8 | 0 | 0 |
| 합계 | | 42 | 26 | 5 | 11 |

intent마다 paraphrase 3개(원문·어순·절), 모두 126문장. 문구 규칙은 `evaluation/paraphrases.yaml`과
같다(어순·조사·수식어 위치만 바꾸고 동의어를 쓰지 않는다). stage-swap으로 오답이 되는 두 단계
answered intent는 11개다(v1 마이그레이션 뒤 aggregation holdout에 남은 것은 4개).

stub v2(5문항)는 `evaluation/v2/stub_v2_gold.yaml`에 기대 결과·인자·근거를 적었다.

## 4. 중복·누수 점검 (모델 실행 전)

`tests/test_v2_holdout.py` LeakTest가 고정한다.

- 질문 문장: 기존 corpus 전체, 부모 파일, stub(v1·v2·boundary), 구조화 질문 셋, 예시 저장소, 업체
  100문항(`assistant_univ_questions_100_v3.yaml`)과 정규화 문장이 겹치지 않는다.
- 질문 구조(`paraphrase_corpus.structure_signature`: 측정값, 장소·승하차 역할, scope, 조건 값, 집계
  의미): registry의 모든 corpus golden과 예시 저장소 grounding과 겹치지 않는다.
- 측정값·집계·조건 종류만 같고 값(기간·장소·유형)이 다른 것은 네 개다. 새 토큰이나 조건을 검사하는
  문항이라 남겼다: w07·w39(요금 평균 ↔ f10·v24는 장소·기간이 다름), w40(올해 법인 공차율 ↔ h05
  지난달 법인 공차율, this_year 토큰 검사), w20(개인택시 평균 운행일수 ↔ 예시 ex01, 중구·지난달·법인).
  예시 검색은 production 기본값에서 꺼져 있어 평가 실행에 들어가지 않는다.

## 5. 실행

- 설정: production CLI 기본값. geoflow, flat grounding, condition_check 끔, provider mock, TIMS legacy,
  예시 검색 끔, Ollama options `{"temperature": 0}`, think=auto(모델 기본값), chat timeout 300초.
- 기준일: 2026-09-25(`paraphrase_corpus.EVALUATION_REFERENCE_DATE`), pipeline clock 고정.
- 격리: 관측마다 모델을 내리고(`/api/generate keep_alive=0`, `/api/ps` 확인) 첫 호출의 cold load
  (≥ 500ms)를 확인한다. planner 재시도가 생기면 한 번 새로 시작하고, 그래도 생기면 무효 관측이다.
- 기록: `evaluation/v2/runs/<run_id>/`에 meta.json(커밋, dirty 경로, 명령, 모델 이름·digest·크기·
  양자화, Ollama 버전, 설정, 기준일, planner prompt·vendor schema·system prompt sha256, 입력 파일
  sha256), observations.jsonl(관측마다 전체 기록), summary.json.
- 명령: `python evaluate_v2.py run --model qwen3:8b --sets stub,holdout_v2 --label v2_qwen3_8b`

## 6. 채점 (evaluate_v2.py, 고정)

관측마다 범주 하나를 준다.

- expected_outcome=answered
  - `correct`: 답을 냈고 측정값·라벨·집계 의미·최종 Tool 인자·답변 형식이 모두 맞다.
  - `grounding_error`(답을 냈지만 측정값·라벨이 다름), `aggregation_error`(집계 의미가 다름),
    `wrong_tool_args`(최종 Tool 인자가 expected_tool_args와 다름 — 장소는 mock gazetteer에서 지역 없이
    조회한 scope가 같으면 같다 — 또는 holdout에서 최종 grounding의 조건(집계 제외: 기간, 시간, 택시
    유형, 주변, dimension 등)이 golden과 다름; taxi_type=all 같은 조건 없는 값은 없는 것과 같다),
    `answer_format_error`
    (원시 object·행 덤프·None·중복 단위·질문에 없는 scope 노출·값 없음).
  - `refused_supported`(unsupported·needs_clarification으로 멈춤), `grounding_failure`(planner·합성·
    검증 단계 실패), `execution_failure`(그 뒤 단계 실패).
- expected_outcome=unsupported | needs_clarification
  - `correct`: 기대한 종류로 멈췄다(strict).
  - `answered_instead_of_refusal`, `wrong_refusal_kind`, `failed_instead_of_refusal`.
- 보고: 평가셋별로 분모와 건수를 함께 적는다. 실행 완료율 = answered 기대 문항 중 답을 낸 수,
  의미 정답률(전체, answered 기대 문항), 거부 정확도 strict(기대 종류) / lenient(답하지 않음).
- mock은 고정값을 돌려주므로 수치의 정확성은 채점하지 않는다. 요청한 인자와 의미 graph가 기준이다.

## 7. 사용 규칙

- 이 holdout의 결과로 prompt·예시 검색·채점 규칙을 조정하면 이 holdout은 development가 되고, 최종
  평가에는 새 holdout을 써야 한다. 이번 작업에서는 조정하지 않는다.
- 실행 뒤 라벨 오류를 찾으면 파일을 고치지 않고 별도 정정 분석으로 적는다. 사전 등록 점수는 바꾸지
  않는다.
- 사람 검토 전이므로 README와 보고서에는 잠정치로 표시한다.

## 8. 변경 기록

- 075a6a5: 이 문서, 문항, 채점기 고정.
- 그 뒤 채점 규칙과 무관한 실행기 변경: 서버에 닿지 않으면 빈 run 디렉터리를 남기지 않음,
  run meta의 미커밋 변경 검사 경로에 `evaluate_v2.py`·`evaluation/v2`·mock 파일 등을 더함.
- 2026-09-29 작업 시점에는 로컬 Ollama 컨테이너가 중지되어 있어 모델을 실행하지 못했다. 공용
  서버라 컨테이너를 임의로 다시 켜지 않았다. 이 holdout은 아직 어떤 모델 결과도 보지 않은
  fresh_holdout이다.

