# 모델에게 전달하는 계약과 실행 계약의 정합, 답 대상 표현 (grounding_v4)

- **변경 전 기준:** 재정렬 버전 `cad3bb8`. 실측 기록은 `evaluation/grounding_v3/runs/final_*`이다.
- **참고 비교:** v2 전체 보정 `3d72ec3`.
- **최종:** `c2f1728`. prompt sha256 `522aa3b1`이고 코드는 answer 계약 커밋 `a8664a2`와 같다.
- **평가셋:** 이번 단계의 모든 셋은 이미 열람한 **개발·회귀셋**이다. 새 독립셋은 만들지 않았다.
- **작성·검토:** 모든 합성 셋은 Claude가 썼고 사람이 검토하지 않았다.

## 1. 선택한 grounding 계약과 이유

구분해야 할 네 경우와 그 표현·실행은 다음과 같다.

| 질문 | grounding(flat) | 집계 IR | 실행 |
|---|---|---|---|
| 구간별 값의 최댓값 | bucket, aggregation, rollup=max (answer 생략 = value) | outer=max | TIMS 위임 호출 |
| 그 최댓값을 가진 구간 | bucket, aggregation, rollup=max, **answer=bucket** | select=max | 계약이 정함. reference는 로컬 선택, TIMS는 `UNVERIFIED_TIMS_CONTRACT` |
| 구간 안 집계가 없음 | bucket, rollup (aggregation 없음) | inner=unspecified | `AMBIGUOUS_INNER_AGGREGATION`(확인 요청) |
| 의미는 명확하지만 provider가 못 함 | 위와 같이 표현됨 | | compiler가 provider 계약으로 거부 |

후보는 가설이 있는 셋으로 제한했다. 답 대상 대조 16문항과 reference provider 6문항으로 격리 실측했다.

| 후보 | 가설 | 답 대상 16 맞음(오답) | reference 6 | 관측 |
|---|---|---|---|---|
| 기준(select 안내 없음) | | 10 (5) | 표현 불가 | 구간 질문을 값으로 답함 |
| A. flat `select` 안내 | IR과 같은 factor 하나면 충분 | 10 (4) | 4 | 지역·요일 순위에 구간을 붙임. 값 질문(r3)을 구간으로 답함 |
| B. 구조화 `aggregation_plan` | result.reducer/select가 답 대상을 1급으로 적음 | 5 | 2 | 형식 실패(INVALID_FACTOR 등), 값 질문에 select |
| **C. flat `answer: value \| bucket`** | 답 대상을 이지선다로 묻고, select라는 미끼를 없앤다 | **10 (2)** | 4~5 | 구간 질문 3/3을 실행 계약 이유로 멈춤. 답 대상 뒤바뀜 없음 |

- **C를 고른 이유:**
  - `select`는 있으면 뜻이 뒤집히는 factor였다. "가장 큰"이라는 말에 끌려 값 질문에도 붙었다.
  - `answer`는 질문이 묻는 것을 직접 이지선다로 적게 한다. 생략하면 value라서, 단순한 구간 질문(`bucket` + `rollup`)은 그대로 쓴다.
  - 집계 IR·합성·lowering은 그대로다. `from_flat`이 `answer=bucket` + `rollup=max|min`을 IR의 `select`로 올린다.
- **B를 배제하는 근거:** B의 실패는 이번 실측(qwen3:8b, 16문항) 기준이다. 표현 방식 자체를 영구 배제하는 근거는 아니다. 구조화 표기는 계속 선택 기능으로 남고 계약 정합 시험도 받는다.
- **표현과 prompt 영향을 가른 추가 실측:**
  - 같은 C 표현에서 prompt 두 줄만 바꾼 변형을 돌렸다(`ede43190`, both 문구에서 이동 표현을 빼고 answer를 주·월로 한정).
  - 7개 셋 맞음이 224 → 213이었고, 대조 31은 26 → 18이었다.
  - qwen3:8b에서는 문구를 조금 바꿔도 결과가 표현 자체의 효과보다 크게 흔들린다. 그래서 더 고치지 않고 C를 최종으로 두었다(`c2f1728`).

## 2. 모델에게 전달하는 계약과 실행 계약의 정합

| 항목 | 이전(`cad3bb8`) | 최종 |
|---|---|---|
| 파서가 받는 factor와 prompt | `select`를 받지만 prompt에 없음 | 파서가 받는 factor·값은 모두 prompt에 있다(`FLAT_PROMPT_EXCLUDED` 비움) |
| 검증이 요구하는 짝과 prompt | order→limit을 검증만 요구(모델은 모름) | [짝을 이루는 factor]에 같은 표로 적는다 |
| 재질의가 채울 수 있는 조건 | limit을 prompt가 모르는 채 요구 | 재질의가 채우는 조건은 모두 prompt에 안내된 factor다 |
| 장소 역할 값 | `both`를 파서만 받음(관계 재질의 문구에만) | prompt의 od_role 규칙에 `both` |
| 답 대상 | flat에서 표현 불가 | `answer` |

- `tests/test_contract_parity.py`가 flat·structured 두 계약에서 위 정합을 검사한다.
- 모델이 모르는 필수 조건 때문에 재질의가 생기는지:
  - order가 있는 첫 응답 113개가 모두 limit을 적었다. 이전 계약에서는 limit 누락이 factor 재질의를 불렀다.
  - `answer`는 필수가 아니다(생략 = value). bucket 질문마다 재질의가 생기지 않는다.

## 3. 답 대상 혼동의 해결 여부

**셋별 구간 질문(8문항: t01b·t02b·t03b·g32·c08c·n24·m25·k40)**

| | 기준 `cad3bb8` | 최종 |
|---|---|---|
| 구간을 묻는 질문 | 0/8. 값으로 답함(조용한 오답) 5, 실행 실패 3 | 7/8. 모두 `UNVERIFIED_TIMS_CONTRACT`(의미 표현 성공, provider 실행 불가). 1개(t01b)는 모델이 구간 안 합계를 빠뜨려 확인 요청 |
| 값을 묻는 두 단계 질문(13) | 13 | 12(t01a: rollup을 min으로 적음. 답 대상 문제가 아니다) |
| 구간 안 집계 없음(8) | 1 | 1. 모델이 구간 안 집계를 지어낸다. 원문 재해석을 복원하지 않았으므로 그대로 남는다 |
| 지역·요일 순위 guard(t04a·t04b) | 2/2 | 0/2. `answer=bucket` 오용이 형식 실패로 끝남(조용한 오답 아님) |

- **reference provider(실제 모델, 격리):** 구간 질문 r1·r4는 두 주의 이름과 값을 답했다. 값 질문 r2·r5·r6은 값을 답했다. r3("주별 매출 중 가장 큰 값", 구간 안 집계 없음)은 모델이 구간 안 집계를 지어내 값으로 답했다.
- **TIMS에서 표현 실패와 실행 불가의 구분:**
  - 구간 질문의 거부 이유가 `UNVERIFIED_TIMS_CONTRACT`이면 표현 성공·실행 불가다.
  - 다른 코드(형식·조합 오류)면 표현 실패다.
  - 답 대상 셋은 `expected_error`로 이 둘을 따로 채점한다(채점기 v3).
- **남은 오용:** `answer=bucket`이 구간이 아닌 질문에 21번 붙었다(7개 셋 첫 응답 합계, 주로 "가장 높은 요일"). 검증(`answer` → `bucket` 짝, `INVALID_ANSWER_TARGET`)이 막아 조용한 오답으로는 가지 않는다. 대신 형식 실패·부당한 거부가 된다.

## 4. 층별 성능과 전체 회귀 (qwen3:8b, 격리, 채점기 v3)

**의미 정확(원출력 → 형식 정규화 → 조건 보존 → 재질의 뒤 최종 grounding)**

| 셋 | 기준 `cad3bb8` | 최종 |
|---|---|---|
| 업체 100 | 57 → 63 → 78 → 90 | 50 → 57 → 70 → 82 |
| v4 40(/38) | 15 → 18 → 19 → 21 | 17 → 17 → 20 → 23 |
| 답 대상 16 | `layers_base_at.md` | 10 → 10 → 11 → 11 |

형식 정규화·조건 보존의 훼손은 모든 셋에서 0이다(`layers_final.md`).

**최종 결과(맞음 = 정상 답변 + 정당한 거부)**

| 셋 | 기준 맞음 (오답 / 부당한 거부 / 실패) | 최종 맞음 (오답 / 부당한 거부 / 실패) | 참고: v2 전체 보정 맞음 |
|---|---|---|---|
| 답 대상 16 | 10 (5 / 0 / 1) | 10 (3 / 1 / 2) | – |
| 업체 100 | 93 (3 / 1 / 3) | 85 (3 / 2 / 10) | 99 |
| 기존 44 | 36 (7 / 1 / 0) | 28 (7 / 3 / 6) | 44 |
| 대조 31 | 26 (2 / 1 / 2) | 26 (3 / 1 / 1) | 31 |
| 1차 독립 40 | 23 (8 / 3 / 6) | 27 (5 / 0 / 8) | 33 |
| 2차 독립 40 | 21 (9 / 2 / 8) | 22 (5 / 3 / 10) | 24 |
| v4 40 | 24 (4 / 7 / 5) | 26 (5 / 4 / 5) | 25 |
| **합계 311** | **233 (38 / 15 / 25)** | **224 (31 / 14 / 42)** | |

- **정당한 거부:** 6 → 14(구간 질문 7, 확인 요청 등).
- **조용한 오답:** 38 → 31. 실행 실패는 25 → 42로 늘었다.
- **늘어난 실패의 원인은 대부분 prompt 변경 뒤의 출력 변동이다.**
  - 업체 100의 13문항 감소: "실차 통행량"을 trip_count로(005·013·037), 값 없는 단위 말 장소(016·078), 시간 형식·factor 이름 형식 오류(030·072), 요일 순위에 `answer`(015·065) 등.
  - 대부분 답 대상과 무관하다.
  - v2 grounding_v1에서 기준 prompt(238ac8d6)를 업체 100으로 골랐으므로, 어떤 문구 변경이든 그 셋에서 선택 이점을 잃는다.
  - 기준 prompt를 고르는 데 쓰지 않은 셋(1차·2차·v4·대조·답 대상)의 합은 104 → 111이다.
- **업체 100의 이전 잔여 오류:** 006·040·064·066·093은 이번 실측에서 맞았다. 007·095는 남았다. 모두 규칙 추가 없이 출력 변동으로 바뀐 것이라 개선 효과로 세지 않는다.

**재질의·지연 (7개 셋 합)**

| | 기준 | 최종 |
|---|---|---|
| 재질의 | 64 | 68 |
| 문항 지연 합계 | 6834초 | 6768초 |

- 업체 100: 재질의 15 → 20, 중앙값 13.2 → 12.8초, p90 21.1 → 25.6초, 최대 474.6 → 523.0초(timeout 뒤 재시도).
- 긴 지연은 빼지 않았다(`report_final.md`).
- 같은 지역 OD: 첫 응답이 `both`를 쓴 경우는 13문항 중 1개였다. 나머지는 관계 재질의(34회)에 기댄다.

## 5. 연도 없는 날짜: 정책과 평가의 분리

- **라벨의 근거:** k01("9월 14일부터 18일까지"), k04("9월 25일"), k16("9월 1일부터 20일까지")의 정답은 모두 2026년이다. 근거는 작성 에이전트의 파일 머리 설명 "연도 없이 적은 날짜는 2026년이다"뿐이다. 제품 정책이 아니라 **라벨 작성자의 가정**이다.
- **현재 정책:** dev 이래 연도 없는 날짜를 모호로 보고 확인을 요청한다(`DATE_AMBIGUOUS`). v2 전체 보정과 최종 코드 모두 같다. 이번에도 바꾸지 않았다.
- **판단:**
  - 이 세 문항의 멈춤은 정책 미정 상태의 라벨 가정과 정책의 차이다. 보정 계층의 구현 오류로 단정하지 않는다.
  - grounding_v3 사전 등록의 H1 결과(부분 미충족)는 그대로 둔다.
  - 구현 오류(정책과 다르게 동작)는 발견되지 않았다. 세 문항 모두 정책대로 멈췄다.
- **정책 결정이 필요한 이유:** 기준일이 9월 말이면 "9월 25일"은 대부분 올해지만, 연초의 "12월 3일"은 지난해일 수 있다. 조용히 한 연도로 정하면 틀린 기간으로 답할 수 있다.
- **선택지:**
  - (1) 지금처럼 확인 요청
  - (2) 기준일 연도로 해석하고 미래면 지난해로 해석(답변에 가정을 밝힘)
  - (3) 기준일 연도로만 해석

## 6. 남은 한계

- **답 대상 오용:** 구간이 아닌 순위(특히 요일)에 `answer=bucket`이 붙는다. 조용한 오답은 아니지만 형식 실패가 늘었다.
- **구간 안 집계를 모델이 지어냄:** 8문항 중 7문항. 코드가 원문을 다시 읽지 않으므로 확인 요청으로 바뀌지 않는다.
- **같은 지역 OD:** 첫 grounding에서 `both`를 거의 쓰지 않는다. 관계 재질의가 맡는다.
- **prompt 변동:** qwen3:8b는 prompt 문구 변경에 크게 흔들린다. 계약 정합을 위한 문구 추가가 업체 100·기존 44에서 8문항씩 출력 변동을 만들었다.
- **provider 실행:** TIMS는 구간 선택을 실행하지 못한다(bucket/rollup은 대표값만, day_records 계약 없음). reference provider에서만 실행된다.
- **모든 셋이 개발셋이다.** 16~100문항에서 몇 문항 차이는 일반 오류율이 아니다.

## 7. 재현

```bash
PY=python
$PY -m unittest discover -s tests -t .                  # 계약 정합: tests/test_contract_parity.py
S=evaluation/grounding_v4
$PY evaluate_vendor100.py --gold $S/answer_target_questions.yaml gold --out gold.json           # 정답 grounding → 실행기
$PY evaluate_vendor100.py --gold $S/answer_target_questions.yaml llm --model qwen3:8b --condition-check --out at.json
$PY evaluate_vendor100.py --gold $S/answer_target_questions.yaml llm --model qwen3:8b --condition-check --aggregation-grounding structured --out at_structured.json
$PY $S/reference_check.py --mode flat --out reference.json                                       # reference provider, 실제 모델
$PY evaluate_vendor100.py layers --run at at.json                                                 # 층별
$PY evaluate_vendor100.py report --items --pair at $S/runs/at_base.json at.json                  # 비교(분모·합계·지연)
```

기록:
- `runs/`
  - 후보 A: `at_flat`, `reference_flat`
  - 후보 B: `at_structured`, `reference_structured`
  - 후보 C 1차: `at_answer`, `reference_answer`
  - 최종: `final_*`, `final_reference`
- `runs2/`: 문구 수정 변형
- 표: `report_final.md`, `layers_final.md`, `gold_audit_final.md`
