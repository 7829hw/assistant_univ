# 실제 LLM 질문 해석 개선 (grounding_v1)

상태: 구현·검증 완료(2026-09-29). 기준 B0 = `a0d7b18`(위임·로컬 책임 분리 `e828ba9` + query_loader id 수정
`cfd1bd0` + 평가기 기록 보강). 최종 = `9650d29`(`b841406` + 평가기 인자 호환).
사전 등록: `preregistration.md`. 개발·회귀셋 = 업체 100문항, 독립셋 = `holdout_questions.yaml`(44).

## 0. 평가의 신뢰성 (선행 작업)

- `query_loader.load_queries`는 `yaml.safe_load`(YAML 1.1)로 id를 읽어 업체 100문항 중 63개 id가 원문과 달랐다
  (`001`→`"1"`, `010`→`"8"`). CLI `--query-id 010`은 아무것도 고르지 못했다. 원문 문자열로 읽도록 고쳤다(`cfd1bd0`,
  `tests/test_query_loader.py`).
- 이전 평가 결과 5개 파일(gold·llm 전후·replay)은 업체 xlsx의 번호와 BaseLoader로 문항을 이어서 영향이 없었다: 모두 100행,
  중복·누락 0, 질문 ↔ id ↔ gold 연결 오류 0. 다시 채점할 필요가 없었다.
- B0를 원 출력·재질의·LLM 호출·grounding 비교까지 기록하는 평가기로 다시 실행했다. 이전 두 run과 grounding 100개,
  범주 100개가 모두 같았다(세 번째 동일 재현). 이 결정성 덕분에 코드 후보는 B0의 원 출력을 재생해 비교했다.

## 1. 실패 35문항의 원인 (B0 실행 기록 기준)

분류: A = 모델이 의미·조건을 잘못 해석, B = 의미는 맞지만 출력 형식이 계약 위반, C = 파서·정규화·검증기가 올바른 표현을
잘못 거부, D = grounding 이후(합성·컴파일·실행·답변·채점)에서 실패.

| 문항 | B0 결과 | 분류 | 원 출력에서 확인한 원인 |
|---|---|---|---|
| 001 | answered_mismatch  | A | taxi_status 누락(공차) |
| 005 | answered_mismatch  | A | taxi_status 누락(실차) |
| 009 | answered_mismatch  | A | taxi_status 누락(대기영업) |
| 010 | failed NOT_FOUND | A | "전국"을 장소로 |
| 013 | failed MISSING_RELATION_QUALIFIER | A | 측정값 혼동: "실차 통행량"을 trip_count로 |
| 014 | failed INVALID_SUBTYPE | B | 택시 유형을 OBJECT/private 개념으로 |
| 016 | failed VALUELESS_CONCEPT | A | dimension 대상("도착 읍면동")을 값 없는 장소 개념으로 |
| 020 | failed MISSING_RELATION_QUALIFIER | A | 그룹 단위("읍면동")를 장소로 |
| 024 | failed NOT_FOUND | A | 그룹 단위("읍면동")를 출발·도착 장소로 |
| 025 | refused_unsupported UNCONSUMED_CONDITION | A | 순위("가장 적은 곳")를 aggregation=min으로 |
| 037 | answered_mismatch  | A | 측정값 혼동: "실차 택시 통행량"을 trip_count+pickup으로, taxi_status 누락 |
| 038 | failed NOT_FOUND | A | 그룹 단위("시도")를 장소로 |
| 041 | answered_mismatch  | A | od_role 오류(하차 기준인데 pickup) |
| 043 | failed INVALID_FACTOR | A+B | date "202310"(YYYYMM, 존재하지 않는 달), "가장 낮은 값"을 order/limit으로, rollup 누락 |
| 050 | answered_mismatch  | A | date 누락(주말) |
| 052 | answered_mismatch  | B+D | region이 name과 같음("대구","대구"). 실행 scope는 맞았으나 조회 인자가 업체 정답과 다름 |
| 054 | failed MISSING_RELATION_QUALIFIER | A | 측정값 혼동: "실차 택시 통행량"을 trip_count로 |
| 055 | answered_mismatch  | A | taxi_status 값 오류(대기영업→vacant) |
| 067 | failed NOT_FOUND | A | 그룹 단위를 장소로(region 부산), 재질의가 od_role을 pickup으로 |
| 070 | refused_unsupported NO_OPERATOR | A | 그룹 단위를 장소로(region 부산)+passage에 od_role |
| 074 | answered_mismatch  | A | taxi_status 누락(실차) |
| 075 | failed AMBIGUOUS_LOCATION_RELATION | A | od_role 누락. 재질의 1회를 dimension 보충에 써서 관계 재질의 못함 |
| 078 | failed NOT_FOUND | A | 그룹 단위("시군구")를 장소로 |
| 079 | failed INVALID_FACTOR | B | date "202310"(이번 달을 YYYYMM으로) |
| 080 | refused_unsupported UNCONSUMED_CONDITION | A | 측정값 혼동: "공차 택시 통행량"을 vacant_ratio로 |
| 084 | answered_mismatch  | A | date 누락(주말) |
| 085 | failed NOT_FOUND | A | 그룹 단위를 장소로(region 대구) |
| 088 | answered_mismatch  | A | taxi_status 누락(실차), 개수 Tool에 aggregation=sum(무해) |
| 090 | failed INVALID_PLACE | B | name "" region "서울"(장소가 region 자리에) |
| 092 | answered_mismatch  | A | date 누락(주중) |
| 093 | failed VALUELESS_CONCEPT | A | "부산 안에서" 값 없는 장소 개념 2개 |
| 094 | failed INVALID_FACTOR | B | date "202605"(이번 달을 YYYYMM으로) |
| 095 | answered_mismatch  | A | "대구 안에서" 장소 누락(장소 개념 없음) |
| 098 | failed INVALID_PLACE | A+B | name "" region "대구"(자리), med를 aggregation에, rollup 누락("주별 평균" 소실) |
| 100 | answered_mismatch  | A | "총 수입"(sum) 대신 max, "가장 큰 값"을 두 단계 모두에, taxi_type(법인) 누락 |

요약: A 28, B 4, A+B 2(43·98), B+D 1(052). C(올바른 표현의 잘못된 거부)는 B0 경로에서 관측되지 않았다. 거부는 모두
실제로 계약을 어긴 출력이었다. 다만 조건 계층을 켰다면 읽지 못했을 표현(scope 문자열 숫자, "법인 실차 택시")이 있었다(2절).

**대표 문항**
- 43: 원 출력 `date: "202310"`(이번 달을 존재하지 않는 연월로), `bucket: week, aggregation: avg`, `order: bottom, limit: 1`
  ("가장 낮은 값"을 순위로), rollup 없음, `taxi_type: corporate`. 첫 거부 규칙은 factor 형식 검사(`FactorSpec` date 패턴,
  `INVALID_FACTOR`). 날짜가 맞았어도 order·limit에 dimension이 없고(`INVALID_FACTOR_COMBINATION`) rollup이 없다.
- 98: 원 출력 장소 `{"name": "", "region": "대구"}`(`INVALID_PLACE`, 장소 값 검사), `aggregation: med`, rollup 없음. "주별 평균
  운행 일수의 중간값"에서 평균(구간 안)이 사라지고 중간값이 aggregation 자리에 갔다.
- 100: `aggregation: max, rollup: max`("가장 큰 값"을 두 단계 모두에), "총"(sum) 소실, "법인택시" 누락.

**성공 문항과의 차이(같은 특징의 성공률)**: 운행 상태가 있는 질문 5/16, "이번 달" 3/12(YYYYMM 환각은 이번 달에서만),
두 단계 집계 0/3, 장소 없는 그룹 질문 4/8. 반면 "소속" 질문 17/21, 출발·도착 두 장소 10/14는 대체로 성공했다. 즉 실패는
표현 계열에 몰려 있다.

## 2. 이미 있던 기능이 막지 못한 이유

| 기능 | 막지 못한 이유 |
|---|---|
| planner prompt의 두 단계 설명(`factors.FACTOR_STAGE_NOTE`) | "구간 표현과 함께 나온 집계어는 rollup"이라고만 적어, 집계어가 둘인 질문("주별 평균 … 중 최솟값")에서 구간 안 집계를 버리거나 자리를 바꾸게 했다(43·98·100) |
| factor 설명 | taxi_status는 "운행 상태 조건."뿐이라 실차·공차·대기영업 대응이 없었다. 날짜 토큰의 한국어(주말·주중) 대응도 없었다 |
| 조건 계층(`--condition-check`) | 기본 꺼짐. 32문항 개발셋에서 조용한 오답 5 → 0이었으나 fresh 셋 재측정 전이라 채택하지 않았다(condition_preservation.md). 켜도 운행 상태를 읽지 않았고, scope 문자열의 숫자가 날짜 단서로 잡혀 "휴일"을 보류했고, "법인 실차 택시"의 유형을 읽지 못했다 |
| 재질의 | 질문당 1회. 계획 단계 재질의가 dimension 보충에 쓰이면 관계 재질의를 못 한다(075). 장소 NOT_FOUND 재질의는 "읍면동" 같은 단위 말을 고칠 수 없다(모델이 unsupported) |
| grounding 검증 | 형식 오류(빈 name, region=name, OBJECT/private)를 정확히 거부했지만 자리만 바로잡으면 되는 것까지 실패로 끝냈다 |
| prompt 문구로 막기 | 택시 유형을 개념으로 적는 오류는 prompt 문구로 줄지 않았다는 기존 측정(test_taxi_type_contract 머리)이 있다 |

## 3. 후보와 선택 (개발셋)

코드 후보는 B0의 계획 응답을 재생했다(prompt hash가 같을 때만 재생, 재질의는 실제 호출). 재생은 격리 초기화를 하지 않아
**재질의 결과는 실행마다 다를 수 있다**(007·041이 그랬다). 재생 수치는 후보 선택용이며 최종 판단은 격리 실측이다.

| 후보 | 방법 | match | 잘못된 답 | 거부 | 실패 | grounding 정확 |
|---|---|---|---|---|---|---|
| B0 | 기준(실측) | 65 | 14 | 3 | 18 | 63 |
| r1 | 조건 계층 켬 + 운행 상태·읽기 빈틈 보강 (재생) | 77 | 3 | 4 | 16 | 74 |
| r2 | 장소 자리 바로잡기 (재생) | 73 | 12 | 3 | 12 | 71 |
| r3 | r1 + r2 (재생) | 85 | 3 | 4 | 8 | 82 |

prompt 후보는 prompt가 바뀌므로 실측했다. 표본 = B0 실패 35 + B0 성공 20(시드 20260929 무작위, `runs/subset_ids_c3.txt`).

| 후보 | 변경 | B0 실패 35 → match | B0 성공 20 → match |
|---|---|---|---|
| r3 (재생) | 코드만 | 20 | 20 |
| C3 (실측) | prompt 6개 규칙(두 단계, 운행 상태·날짜 설명, 통행량, 소속·단위 말, 순위) | 22 | 19 |
| C3b (실측) | prompt 2개 규칙(두 단계, 통행량과 운행 상태) + OBJECT/taxi_type 옮기기 | 28 | 18 |
| C3c (C3b 재생) | + 단일 최상급 limit=1, 승하차 기준 채우기 | 30 | 20 |

- C3는 43·100의 집계를 바로 읽게 했지만 모델이 `OBJECT/taxi_type`(값 없음)을 새로 만들었고, 단위 말 규칙은 값 없는 장소를,
  순위 규칙은 limit 누락을 불렀다. 코드가 이미 결정적으로 처리하는 것(운행 상태, 날짜 토큰, 장소 자리)은 prompt에서 뺐다.
- 최종 = C3c 구성. prompt 규칙 2개, 조건 계층(기본 켬), 장소·조건 자리 바로잡기.

## 4. 구현 (규칙마다 해석의 선택이 없는 경우만)

| 층 | 규칙 | 조용한 덮어쓰기를 막는 장치 |
|---|---|---|
| 조건 계층 `conditions.py` | 운행 상태: 상태 말 + (유형) + 택시/통행량일 때만. "공차율", "실차 구간/중/의"는 조건 아님 | 여러 상태·부정은 거부, 근거 없는 LLM 값만 제거, 단서만 있으면 보류 |
| | scope 문자열의 숫자는 날짜 단서가 아님, "법인 실차 택시"의 유형 읽기 | 기존 규칙과 같음 |
| | "가장 …"이고 개수 표현이 없으면 limit=1(업체 규칙) | 빈 값일 때만 채움, 감사 기록 |
| | 실차 구간 건수에서 승차/하차 한쪽만 말하면 dimension_target | 빈 값·trip_count·dimension 있을 때만, 출발/도착만 있으면 읽지 않음 |
| grounding `normalize_place_concepts` | name 빈 장소의 region 이동, region=name 제거, 단위 말·"전국"은 장소 아님 | 값을 만들지 않음, `normalizations` 기록 |
| grounding `hoist_condition_concepts` | OBJECT/private, */taxi_type(+enum 값)을 factor로 | 충돌·값 없음(근거 factor도 없음)은 거부 유지, 재질의로 열지 않음 |
| prompt | 두 단계 집계를 집계어 자리로, 통행량과 운행 상태 구분 | 개발셋 문장을 예시로 쓰지 않음 |
| CLI | 조건 계층 기본 켬(`--no-condition-check`), 감사 문구는 `--condition-check`일 때만 | 기록(condition_audit)은 늘 남음 |
| 답변 | 운행 상태를 주어에 복창("공차 법인 택시 통행량") | - |

LLM은 개념·조건만 적고, macro 합성·Tool 선택·컴파일·실행은 그대로 코드가 한다. 문항 id·원문 문자열·정답을 보는 규칙은 없다.
추가 모델 호출은 도입하지 않았다(재질의 1회 상한 그대로).

부수 변경: prompt A/B 고정 변형(D_PRE·T0 등)은 production prompt에서 파생되던 것을 v2 원천(`evaluation/prompt_ab/pinned/
v2_db113124`)에서 만들도록 바꿔 같은 이름이 같은 계약(db113124)을 가리킨다. 측정용 planner는 이전 grounding 계약
(normalize 끔)을 쓴다. production prompt sha256 앞 8자리: db113124 → 238ac8d6.
