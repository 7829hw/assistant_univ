# 실제 LLM 질문 해석 개선 (grounding_v1)

상태: 구현·검증 완료(2026-09-29). 기준 B0 = `a0d7b18`(위임·로컬 책임 분리 `e828ba9` + query_loader id 수정
`cfd1bd0` + 평가기 기록 보강). 최종 = `d090e3c`(측정 코드, 실측 commit `1cb307d`는 CLAUDE.md만 추가).
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

### C3c 전체 실측과 추가 보강(C3d)

C3c 구성의 개발셋 격리 실측(`runs/final_dev_qwen3_8b.json`)은 90 match였지만 B0 성공 5개가 회귀해 사전 등록 규칙 2(≤2)를
어겼다. 그래서 독립셋 실행을 멈추고(예정된 실행을 시작 전에 중단) 원 출력을 봤다. 모두 prompt 변경 뒤 새로 나온 형태였다.

| 문항 | 원 출력 | 처리 |
|---|---|---|
| 063 | subtype 없는 OBJECT(value private), 같은 taxi_type factor가 이미 있음 | 되풀이된 개념 제거(값이 같을 때만) |
| 066 | dimension 없이 dimension_target만, 질문에 그룹 표현 없음 | 근거 없는 값 제거(조건 계층) |
| 089 | `{"holiday": true}`(날짜 토큰을 factor 이름으로), date 없음 | date로 옮김(다른 date가 있으면 거부 유지) |
| 064 | "RPM 중간값"을 speed로 | 고치지 않음. 질문의 측정값 말 한 계열과 어긋나면 확인 요청(`MEASURE_EXPRESSION_CONFLICT`). 개발셋 98/100 판정 가능, 잘못된 충돌 0 |
| 006 | `dimension: "both"` + `dimension_target: pickup` | 되돌릴 방법이 하나로 정해지지 않아 거부 유지 |

C3d(= C3c + 위 4개, `d090e3c`)를 C3c 원 출력으로 재생했을 때 regressions는 006·064와 재질의 변동 1건(044: 같은 계획, 비격리 재질의가
다른 개념 id를 고름)이었다. 그 뒤 C3d를 격리 실측했다.

## 5. 최종 결과 (같은 기준: qwen3:8b, temperature 0, think=auto, 질문마다 unload, 기준일 2026-09-25, mock + legacy, 같은 채점기)

### 5.1 정답 grounding 기반 실행 정확도 (LLM 없음)

| | B0 | 최종 |
|---|---|---|
| 개발셋 100 | 100/100 | 100/100 |
| 독립셋 44 | match 41 + 기대한 거부 2 (g32 제외) | 같음 |

grounding 이후(합성·컴파일·실행·답변) 경로는 두 코드에서 같은 정답을 낸다. 아래 차이는 모두 grounding에서 온다.

### 5.2 실제 LLM 실행 (개발셋 = 업체 100문항, 개선에 사용한 셋)

| | B0 `a0d7b18` | 최종 `d090e3c` |
|---|---|---|
| LLM grounding 정확(최종 grounding = 정답 grounding) | 63/100 | 90/100 |
| Tool·인자·scope 출처·답변 값 모두 일치(match) | 65 | **93** |
| 잘못된 답변(answered_mismatch) | 14 | 2 (041, 067: 하차 기준인데 출발 장소로) |
| 거부 | 3 (unsupported) | 2 (확인 요청: 064 측정값 충돌, 095 장소 'Daegu') |
| 실행 실패 | 18 | 3 (006, 078, 093) |
| LLM 호출(계획 + 재질의) | 100 + 22 | 100 + 13 |
| 관측 지연 중앙값 / p90 | 12.3초 / 25.0초 | 12.4초 / 20.9초 |

- B0 성공 65개 중 회귀 2개: 006(prompt 변경 뒤 dimension에 both를 적음, 실패), 064(측정값 충돌로 확인 요청. 이 가드가 없으면 잘못된 답).
  사전 등록 규칙 1~3 충족.
- 합계 지연은 비교하지 않는다. 양쪽에 chat timeout(300초) 근처의 외부 지연이 2~3건 섞였다(044·030 / 044·041·100).
- 43·98·100은 모두 업체 정답 호출과 같다. 원 출력부터의 변화는 다음과 같다.
  - 43: 모델이 두 단계를 `bucket=week, aggregation=avg, rollup=min`으로 바로 적음(prompt 두 단계 규칙). "이번 달"은 빠졌고 조건 계층이
    this_month로 채움. 택시 유형은 `OBJECT/taxi_type=corporate`로 적혀 factor로 옮김.
  - 98: 장소 `{"name": "대구"}`, `aggregation=avg, rollup=med`를 바로 적음. "개인택시"는 빠졌고 조건 계층이 채움.
  - 100: `aggregation=sum, rollup=max, taxi_type=corporate`를 바로 적음.

**개발셋 결과는 이 셋으로 원인을 찾고 후보를 고른 결과이므로 일반화 성능이 아니다.**

### 5.3 독립셋 (44문항, 후보 선택에 쓰지 않음, B0와 최종에서 각 1회)

| | B0 `a0d7b18` | 최종 `d090e3c` |
|---|---|---|
| LLM grounding 정확 | 22/43 | 35/43 |
| match + 기대한 거부 | 22 (21 + 1) | **36** (35 + 1) |
| 잘못된 답변 | 7 | 4 |
| 답하지 말아야 할 문항에 답함 | 2 (g32, g44) | 2 (g32, g44) |
| 다른 종류로 거부 | 3 | 1 (g04 NO_OPERATOR) |
| 실행 실패 | 10 | 1 (g14) |
| LLM 호출(계획 + 재질의) | 44 + 6 | 44 + 6 |
| 관측 지연 중앙값 / p90 | 12.1초 / 22.7초 | 12.0초 / 18.3초 |

- B0에서 맞던 문항의 회귀 0. 새로 맞은 14와 B0에서의 원인(기록 대조):
  - 겨냥한 원인이 고쳐진 것(8): 운행 상태 누락·오류(g01 + 택시 유형 누락, g03, g34), "실차 통행량"을 trip_count로(g02: prompt 통행량
    규칙 + 조건 계층의 운행 상태), 그룹 단위를 장소로(g15: 단위 말 제거 기록), 두 단계에서 구간 안 집계 누락(g27·g30·g42, B0는
    AMBIGUOUS_INNER_AGGREGATION으로 멈춤, prompt 두 단계 규칙).
  - 겨냥하지 않았고 prompt 변경 뒤 모델 출력이 달라져 맞은 것(6): g24(time 자리에 this_year), g28(dimension에 month), g29("개인택시"를
    장소로), g31(TIME 개념), g35(od_role을 factor 이름으로), g38(지어낸 region "부산"). 최종 원 출력에서 해당 형태가 사라졌고 어떤 규칙도
    작동하지 않았다. 이 여섯은 개선 효과로 세지 않는다(같은 종류의 변동이 개발셋 006에서는 반대 방향으로 나타났다). 43·98·100 유형의 표현 변경(g41·g42·g43)과 새 조건 조합(g01 수영구+공차+개인, g03 달서구+휴일+
  대기영업+법인, g28 서울+월별+평균→최솟값, g30 주별 최대 활성택시 대수→중간값)에서 맞았다.
- 남은 실패(최종): g11(도착 장소를 출발로), g16·g40("하위"를 top으로), g33(시도별 "총 수입"에서 sum 누락), g14("대구 안에서" 관계),
  g04(그룹 질문 구성 실패), g32(구간을 묻는 질문에 값으로 답함 — flat grounding이 구간 선택을 표현하지 못함), g44(구간 안 집계를 지어냄).
- 이 셋은 이 결과를 열람했으므로 이제 development다. 이 결과로 규칙을 고치면 새 독립셋이 필요하다.

### 5.4 판정 (사전 등록 규칙)

1 개발셋 match 65 → 93 ✔ · 2 회귀 2개(006·064, 원인 설명) ✔ · 3 잘못된 답변 14 → 2 ✔ · 4 독립셋 22 → 36 ✔ ·
5 추가 모델 호출 없음(재질의는 22 → 13으로 줄었다). **채택.**

## 6. 남은 문제

- 출발·도착 역할(041·067·g11): "부산에서 하차가 많은 읍면동"처럼 장소 조사(에서)와 기준(하차)이 어긋나는 표현. 규칙으로 정하면 "수성구에서
  출발한 … 도착 읍면동"(q16)과 구분할 수 없어 두었다.
- 순위 방향(g16·g40 "하위"→top): 조건 계층은 빈 값만 채우고 LLM 값을 바꾸지 않는다. 방향 대조를 넣을지는 새 개발 근거가 필요하다.
- 구간 선택 질문(g32)과 구간 안 집계 미지정(g44)은 여전히 답한다. flat grounding의 표현 한계와 모델의 집계 지어내기다(이전 평가에서도
  같은 결과, structured grounding 기록 참고).
- 한 지역 안의 OD("대구 안에서", 093·g14), 값 없는 장소(078).
- prompt 변경은 관련 없는 문항에도 출력 변동을 만든다(006·064). 실측 전체 run 없이 prompt를 바꾸지 않는다.
- 답변에 사용자 scope 문자열("scope:district:…")과 HHMMSS가 그대로 나온다(기존 답변 형식, 이번 범위 밖).

## 7. 재현

```bash
PY=python   # requirements.txt + openpyxl
$PY -m unittest discover -s tests -t .
# 기준(B0)
git worktree add --detach /tmp/b0 a0d7b18
$PY evaluate_vendor100.py --code-root /tmp/b0 llm --model qwen3:8b --out runs/b0_dev.json
$PY evaluate_vendor100.py --code-root /tmp/b0 --gold evaluation/grounding_v1/holdout_questions.yaml llm --model qwen3:8b --out runs/b0_holdout.json
# 최종(production CLI 기본과 같은 조건 계층 켬, 감사 문구 없음)
$PY evaluate_vendor100.py llm --model qwen3:8b --condition-check --out runs/final_dev.json
$PY evaluate_vendor100.py --gold evaluation/grounding_v1/holdout_questions.yaml llm --model qwen3:8b --condition-check --out runs/final_holdout.json
# 정답 grounding 층(LLM 없음)
$PY evaluate_vendor100.py gold --out runs/dev_gold.json
$PY evaluate_vendor100.py --gold evaluation/grounding_v1/holdout_questions.yaml gold --out runs/holdout_gold.json
# 코드 후보를 기록된 계획 응답으로 재생(prompt hash가 같을 때만, 재질의는 실제 호출·비격리)
$PY evaluate_vendor100.py llm --model qwen3:8b --condition-check --replay-from evaluation/grounding_v1/runs/b0_qwen3_8b.json --out runs/replay.json
```

기록: `evaluation/grounding_v1/runs/`(B0 `b0_*`, 재생 `replay_*`, prompt 후보 `c3*_subset_live*`, 최종 `final2_dev_qwen3_8b.*`,
`final_holdout_qwen3_8b.*`. `final_dev_qwen3_8b.*`는 규칙 2를 어긴 C3c 실측). B0 개발셋 meta의 `code_dirty`는 run이 끝날 때 기록되어 실행
중에 고친 작업 트리를 가리킨다. 실행 코드는 시작 시 읽은 `a0d7b18`이며, grounding 100개가 이전 두 run과 같았다.
