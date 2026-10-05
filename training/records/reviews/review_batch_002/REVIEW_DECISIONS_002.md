# REVIEW_DECISIONS_002

30건 전체의 assistant semantic review **draft**다. accepted 추천 24 / needs_fix 4 / diagnostic_only 2. 실제 human 승인·queue status 변경·import·v002 생성·GPU 학습은 0건이다. 기존 v001 및 RB001 hold는 동결 그대로다.

## 권고와 승인 의존성

신규 SFT 01–10은 의미상 수락 추천이다. 기존 gold chosen 14개 pair(13–22,24,27–29)는 수락 추천이다. 23/25/26/30도 의미상 정당한 pair지만 신규 chosen이 실제 승인되지 않았으므로 needs_fix로 보류했다. 이 4건에는 JSON 오류가 없고 corrected grounding을 만들 이유도 없다. 의존 대상 08/03/01/09가 사람이 accepted로 확정된 뒤에만 pair를 재확정한다. 대상이 수정/반려되면 pair 양쪽을 다시 검토한다.

| Pair | 승인 선행 gold | 현재 추천 | 선행 승인 후 |
|---|---|---|---|
| RB002-23 | RB002-08 | needs_fix: dependency | accepted 추천 가능 |
| RB002-25 | RB002-03 | needs_fix: dependency | accepted 추천 가능 |
| RB002-26 | RB002-01 | needs_fix: dependency | accepted 추천 가능 |
| RB002-30 | RB002-09 | needs_fix: dependency | accepted 추천 가능 |

## 판정 기준과 지원 범위

MEASURE/implicit는 결과 variable을 뜻하며 단어가 질문에 등장했다는 이유로 source=user로 바꾸지 않는다. EVENT/SUPPORT/implicit도 특정 사건 값이 아닌 측정 맥락이다. Place name은 user value + SUBCOND, scope literal은 COND이며 상위 지역이 없으면 region=""다. Date/taxi_type는 factors이지 value 없는 EVENT/OBJECT가 아니다.

Fare=trip별 운임, revenue=operation 영업 수입; passage_count는 edge passage 사건 수로 unique taxi/수요/trip_count가 아니다. Vacant ratio는 drive마다 기록된 비율의 집계이며 pooled ratio/active_taxi_ratio로 치환하지 않는다. RPM/speed는 발생 위치를 명시해 RB001의 모호한 RPM hold와 구분했다.

RB002-02/04의 주별 fare/speed는 semantic schema·composer가 표현하나 현재 TIMS legacy static compile은 UNVERIFIED_TIMS_CONTRACT다. RB002-19의 최소 주 선택도 TIMS 계약상 lowering 한계가 있다. Semantic gold로 유지 가능하되 해당 실행 benchmark에서 제외한다. 나머지 static compile 성공도 실제 TIMS 수치 정답/합성 장소 존재를 입증하지 않는다. 주 경계·결측·빈 구간·median 짝수 표본·동률은 원문이 지정하지 않은 provider 실행 정책으로 기록하며, grounded factor를 임의로 더하지 않는다.

RB002-11/12는 미지원 물리량/적발 사건을 다른 지원 metric으로 치환한 semantic 오류다. 공급자 구현 부족만을 근거로 unsupported라 하지 않았다. 의미가 명확해도 protected unsupported family이므로 diagnostic 전용이며 학습 이동은 금지한다.

## 개별 판정 요약

| ID | 추천 | Kind | Dependency | Rejected 오류 / 신규 gold 의미 |
|---|---|---|---|---|
| RB002-01 | accepted | SFT gold | — | 가람구 소속 택시의 해당 일자 trip별 승객 운임의 중앙값을 묻는다. |
| RB002-02 | accepted | SFT gold | — | 9월의 각 주 안 trip 요금을 합산하고 주 합계들 중 최솟값 하나를 반환한다. |
| RB002-03 | accepted | SFT gold | — | 가람구에서 발생·기록된 edge 통행의 speed 최솟값이다. 가람구 소속 택시 cohort가 아니다. |
| RB002-04 | accepted | SFT gold | — | 9월의 주별 passage 속도 최댓값을 구한 뒤 그 값들 중 최솟값을 묻는다. |
| RB002-05 | accepted | SFT gold | — | 가람시 안의 passage 사건을 읍면동별로 세어 기록 있는 그룹의 하위 3곳을 반환한다. |
| RB002-06 | accepted | SFT gold | — | 가람시 안의 passage 사건을 시군구별로 세어 기록 있는 그룹의 하위 3곳을 반환한다. |
| RB002-07 | accepted | SFT gold | — | 소속 지역·개인택시 조건에 해당하는 각 drive에 이미 기록된 공차율의 산술평균이다. |
| RB002-08 | accepted | SFT gold | — | 소속 지역·법인택시 조건에 해당하는 개별 drive 공차율의 최댓값이다. |
| RB002-09 | accepted | SFT gold | — | 가람구에서 관측된 passage의 분당 엔진 회전수 최솟값이다. |
| RB002-10 | accepted | SFT gold | — | 가람구에서 관측된 passage의 분당 엔진 회전수 최댓값이다. |
| RB002-11 | diagnostic_only | semantic DPO | — | rejected는 타이어 공기압을 passage/rpm 최대값으로 치환한다. 같은 장소·날짜·max라도 다른 물리량이며 structurally valid한 강제 지원 오답이다. |
| RB002-12 | diagnostic_only | semantic DPO | — | rejected는 안전벨트 미착용 적발을 모든 passage 건수로 바꾼다. taxi_status도 안전벨트 상태가 아니므로 통행량은 적발 건수의 대용값이 될 수 없다. |
| RB002-13 | accepted | constraint DPO | — | date가 factors에서 빠지고 지난달이 value 없는 EVENT/operation COND로 들어갔다. private도 value 없는 OBJECT/taxi_type로 옮겨졌다. 장소는 SUBCOND가 아닌 COND이다. 실제 날짜/택시 조건과 source/role가 틀리며 parser는 MISSING_CONCEPT_VALUE로 거부한다. |
| RB002-14 | accepted | constraint DPO | — | 13의 잘못된 날짜·택시 concept 인코딩에 더해 수성구 LOCATION 자체를 누락했다. 시간·택시·공간 모집단을 잃은 실제 모델 오답이다. MISSING_CONCEPT_VALUE는 첫 오류이며 전체 의미 오류를 대표하지 않는다. |
| RB002-15 | accepted | constraint DPO | — | 상반기와 법인택시를 값 없는 EVENT/operation COND로 인코딩하고 date/corporate factors를 누락했다. 장소 role도 COND이다. 월 stage는 맞더라도 모집단 조건이 잘못되어 chosen을 선호해야 한다. |
| RB002-16 | accepted | constraint DPO | — | 나래구 LOCATION과 private 조건을 누락했고 날짜를 비계약 202608로 출력했다. answer=value는 중복 명시이며 이것 하나만 오답 근거로 삼지 않는다. 모집단 누락과 날짜 표현 오류가 실제 핵심이다. |
| RB002-17 | accepted | constraint DPO | — | 나래구 scope를 누락하고 질문에 없는 dimension=sido를 추가하여 전국 시도 그룹으로 바꿨다. 날짜도 비계약 202608이다. private 유지 여부와 무관하게 공간 모집단·반환 형태가 다르다. |
| RB002-18 | accepted | constraint DPO | — | 법인택시와 지난달을 EVENT/operation COND/source=user로 넣고 value를 제공하지 않았으며 date/corporate factors도 누락했다. answer=value가 있는 것 자체보다 cohort/time 누락과 잘못된 concept/source가 문제다. |
| RB002-19 | accepted | constraint DPO | — | answer=bucket stage는 맞지만 지난달을 값 없는 EVENT COND로, corporate를 값 없는 OBJECT/taxi_type로 인코딩했다. factors date/corporate 누락이 cohort/time을 잃는다. |
| RB002-20 | accepted | constraint DPO | — | private와 last_month를 값 없는 EVENT/operation COND로 인코딩하고 date/taxi_type factors를 삭제했다. 장소도 COND로 잘못 표기했다. stage가 유지되어도 의미·contract 오답이다. |
| RB002-21 | accepted | semantic DPO | — | 장소명 수성구를 즉시 사용 가능한 COND로 바꿨다. prompt는 장소명=SUBCOND, 직접 scope=COND로 구분한다. Composer가 같은 graph로 수용해도 raw semantic grounding role의 오답이다. |
| RB002-22 | accepted | semantic DPO | — | LOCATION source를 implicit으로 바꾸면서 user place value를 유지했다. 사용자 명시 값이라는 출처를 잃고 implicit에는 value를 두지 않는 prompt 규칙을 어긴다. downstream graph 통과는 이 출처 의미를 검증하지 않는다. |
| RB002-23 | needs_fix | semantic DPO | RB002-08 | MEASURE source=user/value=0.25를 추가해 계산할 결과를 사용자 입력으로 가장했다. 0.25와 percent 변환 논쟁이 아니라 원문에 없는 값·출처 자체가 오류다. |
| RB002-24 | accepted | semantic DPO | — | taxi_type=corporate를 제거하여 법인택시에서 유형 제한 없는 전체 택시로 대상을 바꿨다. factor가 optional이라는 schema 사실은 원문의 조건을 생략해도 된다는 뜻이 아니다. |
| RB002-25 | needs_fix | semantic DPO | RB002-03 | time=220000-235959를 환각하여 하루 기록을 야간 일부로 줄였다. 그 구간의 최솟값과 전체 일자의 최솟값은 일반적으로 다르다. |
| RB002-26 | needs_fix | semantic DPO | RB002-01 | fare→revenue와 trip→operation을 일관되게 바꿔 valid한 다른 measure graph를 만들었다. 금액이라는 concept만 같고 관측 단위/물리량이 다르므로 의미 오답이다. |
| RB002-27 | accepted | semantic DPO | — | sum→avg를 avg→sum으로 바꿔 inner 분모 n_w와 outer 분모 k를 서로 바꿨다. stage swap이며 일반적으로 계산이 다르다. 특수 데이터에서 우연히 값이 같아도 질문 의미는 다르다. |
| RB002-28 | accepted | semantic DPO | — | 주별 합계의 최솟값을 주별 최소 기록값들의 합으로 바꿨다. inner/outer의 대상과 값이 달라 동일 통계가 아니다. |
| RB002-29 | accepted | semantic DPO | — | bucket=month와 rollup=max를 삭제해 전체 기간 평균 하나로 축약했다. 남은 avg factor는 monthly maximum을 표현하지 못한다. |
| RB002-30 | needs_fix | constraint DPO | RB002-09 | 최솟값을 sum으로 바꿨고 measures.py는 RPM intensive value의 sum을 undefined로 정의한다. composer의 UNDEFINED_MEASURE_AGGREGATION은 의미 오답과 맞는 실제 constraint 근거다. |

## 예상 v002 규모 — 아직 corpus가 아님

| 조건 | SFT unique | DPO pairs | Semantic / Constraint |
|---|---:|---:|---:|
| frozen v001 | 14 (train 10 / valid 4) | 5 | 5 / 0 |
| accepted 추천 24건만 최종 확정 | 24 (+10 gold) | 19 (+14 pairs) | 11 / 8 |
| 4개 chosen 의존성까지 해소하여 28건 확정 | 24 | 23 (+18 pairs) | 14 / 9 |

기존 seed42 split preview를 보존하면 전체 SFT train18/valid6, 의존성 해소 후 DPO train18/valid5다. 신규 valid gold는 08/09, 이들에 연결된 23/30이 새 valid pair다. 승인 전에는 해당 pair가 실제 validation에 존재하지 않는다. 기존 v001 valid를 train으로 옮기지 않는다. Draft만 복사해서 importer에 넣거나 baseline/delta를 무작정 합치지 않는다.

새 MEASURE fare/speed/passage_count/vacant_ratio/rpm은 각각2개지만 validation에 모두 독립 예제가 있는 것은 아니다. Unsupported train0, active count/ratio0, 독립 source/role/factor validation 부족은 남는다. Parent/semantic family가 보호 영역과 겹치지 않는 자동 검사는 재실행했지만 수동 paraphrase lineage 판정을 대체하지 않는다.

## 30건 상세 검토

### RB002-01 — accepted

2026년 9월 15일 가람구 소속 택시의 실차 구간별 요금 중앙값은?

- 의미 판단: 가람구 소속 택시의 해당 일자 trip별 승객 운임의 중앙값을 묻는다.
- 통계/반환 정의: 표본 X={해당 일자·소속 scope의 trip fare}; median(X). 일 영업 revenue나 택시별 매출 중앙값이 아니다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: 신규 미승인 proposal; 질문과 vocabulary의 의미 일치 확인. 실제 human 승인은 별도.
- Rejected 오류: 해당 없음 — 신규 SFT 후보
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: med enum은 명시적으로 제공된다. 짝수 표본/결측/빈 표본의 세부 수치 계약과 합성 장소 해소는 실행 benchmark에서 확인해야 한다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / med enum은 명시적으로 제공된다. 짝수 표본/결측/빈 표본의 세부 수치 계약과 합성 장소 해소는 실행 benchmark에서 확인해야 한다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"fare"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"trip"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}}],"factors":{"aggregation":"med","date":"20260915"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37)

### RB002-02 — accepted

2026년 9월 가람구 소속 택시의 요금을 주마다 합산한 뒤, 주별 합계 중 가장 작은 값은?

- 의미 판단: 9월의 각 주 안 trip 요금을 합산하고 주 합계들 중 최솟값 하나를 반환한다.
- 통계/반환 정의: F_w=Σ trip fare in week w; result=min_w(F_w). inner=sum, bucket=week, outer=min, answer=value(생략). 최소 주의 이름을 요청하지 않는다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: 신규 미승인 proposal; 질문과 vocabulary의 의미 일치 확인. 실제 human 승인은 별도.
- Rejected 오류: 해당 없음 — 신규 SFT 후보
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: TIMS get_trip_metrics에는 bucket/rollup이 없고 현재 계약으로 로컬 분해도 보장되지 않는다. semantic 표현 가능 / mock-TIMS legacy static compile UNVERIFIED_TIMS_CONTRACT. execution benchmark 제외. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / TIMS get_trip_metrics에는 bucket/rollup이 없고 현재 계약으로 로컬 분해도 보장되지 않는다. semantic 표현 가능 / mock-TIMS legacy static compile UNVERIFIED_TIMS_CONTRACT. execution benchmark 제외.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"fare"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"trip"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}}],"factors":{"aggregation":"sum","bucket":"week","date":"20260901-20260930","rollup":"min"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |

Static compile: UNVERIFIED_TIMS_CONTRACT (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-03 — accepted

2026년 9월 15일 가람구에서 기록된 도로 통행의 주행 속도 최솟값은?

- 의미 판단: 가람구에서 발생·기록된 edge 통행의 speed 최솟값이다. 가람구 소속 택시 cohort가 아니다.
- 통계/반환 정의: 해당 날짜·발생 scope 안 passage 기록의 speed min. 고유 택시 수나 총 이동거리/총 시간으로 바꾸지 않는다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: 신규 미승인 proposal; 질문과 vocabulary의 의미 일치 확인. 실제 human 승인은 별도.
- Rejected 오류: 해당 없음 — 신규 SFT 후보
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 결측 speed 제외 방식·빈 표본 처리·합성 장소 해소는 provider 수치 계약 범위다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / 결측 speed 제외 방식·빈 표본 처리·합성 장소 해소는 provider 수치 계약 범위다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"speed"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"passage"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}}],"factors":{"aggregation":"min","date":"20260915"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37)

### RB002-04 — accepted

2026년 9월 가람구에서 기록된 도로 통행 속도의 주별 최댓값들 중 가장 작은 값은?

- 의미 판단: 9월의 주별 passage 속도 최댓값을 구한 뒤 그 값들 중 최솟값을 묻는다.
- 통계/반환 정의: M_w=max(speed records in w); result=min_w(M_w). inner=max, bucket=week, outer=min, 숫자 반환.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: 신규 미승인 proposal; 질문과 vocabulary의 의미 일치 확인. 실제 human 승인은 별도.
- Rejected 오류: 해당 없음 — 신규 SFT 후보
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: TIMS get_passage_metrics는 bucket/rollup을 받지 않는다. 현재 로컬 range/day 계약 미확인으로 static compile UNVERIFIED_TIMS_CONTRACT; semantic gold와 실행 제외를 분리한다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / TIMS get_passage_metrics는 bucket/rollup을 받지 않는다. 현재 로컬 range/day 계약 미확인으로 static compile UNVERIFIED_TIMS_CONTRACT; semantic gold와 실행 제외를 분리한다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"speed"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"passage"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}}],"factors":{"aggregation":"max","bucket":"week","date":"20260901-20260930","rollup":"min"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |

Static compile: UNVERIFIED_TIMS_CONTRACT (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-05 — accepted

2026년 9월 15일 가람시 안의 택시 통행을 읍면동별로 세어, 기록이 있는 그룹 중 건수가 적은 3곳은?

- 의미 판단: 가람시 안의 passage 사건을 읍면동별로 세어 기록 있는 그룹의 하위 3곳을 반환한다.
- 통계/반환 정의: N_g=#passage records within scope grouped by emd; order=bottom, limit=3. 동일 택시의 다른 edge/진입은 별도 사건; unique taxis나 trip 건수가 아니다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: 신규 미승인 proposal; 질문과 vocabulary의 의미 일치 확인. 실제 human 승인은 별도.
- Rejected 오류: 해당 없음 — 신규 SFT 후보
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 0건 지역 전수 생성이 아니다. 동률 순서 및 가람시의 실제 포함 영역은 실행 계약에서 확인한다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / 0건 지역 전수 생성이 아니다. 동률 순서 및 가람시의 실제 포함 영역은 실행 계약에서 확인한다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"passage_count"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"passage"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람시","value":{"name":"가람시","region":""}}],"factors":{"date":"20260915","dimension":"emd","limit":3,"order":"bottom"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [system.yaml:44](/home/hwkim/assistant_univ/prompts/system.yaml:44)

### RB002-06 — accepted

2026년 9월 15일 가람시 안의 택시 통행을 시군구별로 세어, 기록이 있는 그룹 중 건수가 적은 3곳은?

- 의미 판단: 가람시 안의 passage 사건을 시군구별로 세어 기록 있는 그룹의 하위 3곳을 반환한다.
- 통계/반환 정의: N_g=#passage records grouped by sigungu; bottom 3. 05와 dimension만 다르며 읍면동/OD 축을 대신 쓰지 않는다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: 신규 미승인 proposal; 질문과 vocabulary의 의미 일치 확인. 실제 human 승인은 별도.
- Rejected 오류: 해당 없음 — 신규 SFT 후보
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 합성 가람시가 여러 시군구를 포함한다는 실제 gazetteer 결과는 검증되지 않았다. semantic 예제 정책상 허용하되 실제 3개 그룹 존재/동률을 보장하지 않는다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / 합성 가람시가 여러 시군구를 포함한다는 실제 gazetteer 결과는 검증되지 않았다. semantic 예제 정책상 허용하되 실제 3개 그룹 존재/동률을 보장하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"passage_count"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"passage"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람시","value":{"name":"가람시","region":""}}],"factors":{"date":"20260915","dimension":"sigungu","limit":3,"order":"bottom"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [system.yaml:44](/home/hwkim/assistant_univ/prompts/system.yaml:44)

### RB002-07 — accepted

2026년 9월 15일 가람구 소속 개인택시의 각 전체 운행 경로에 기록된 공차율 값들을 산술평균하면?

- 의미 판단: 소속 지역·개인택시 조건에 해당하는 각 drive에 이미 기록된 공차율의 산술평균이다.
- 통계/반환 정의: r_i=개별 drive의 기록된 vacant_ratio; result=Σr_i/n (동일 가중). 총 공차거리/총 거리, 활성/등록 택시 비율, taxi별 평균의 평균을 요청하지 않는다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: 신규 미승인 proposal; 질문과 vocabulary의 의미 일치 확인. 실제 human 승인은 별도.
- Rejected 오류: 해당 없음 — 신규 SFT 후보
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 개별 r_i의 분자/분모·단위·결측 규칙은 provider 정의에 남는다. 질문은 이미 기록된 비율을 대상으로 명시하므로 pooled ratio로 교정하지 않는다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / 개별 r_i의 분자/분모·단위·결측 규칙은 provider 정의에 남는다. 질문은 이미 기록된 비율을 대상으로 명시하므로 pooled ratio로 교정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"EVENT","id":"c1","role":"SUPPORT","source":"implicit","subtype":"drive"},{"concept":"LOCATION","id":"c2","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}},{"concept":"PROPORTION","id":"c3","role":"MEASURE","source":"implicit","subtype":"vacant_ratio"}],"factors":{"aggregation":"avg","date":"20260915","taxi_type":"private"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [tims.yaml:140](/home/hwkim/assistant_univ/schemas/tims.yaml:140)

### RB002-08 — accepted

2026년 9월 15일 가람구 소속 법인택시의 개별 전체 운행 경로에 기록된 공차율 최댓값은?

- 의미 판단: 소속 지역·법인택시 조건에 해당하는 개별 drive 공차율의 최댓값이다.
- 통계/반환 정의: result=max_i(r_i), r_i=drive의 기록된 vacant_ratio; taxi_type=corporate. 활성택시 가동률 max가 아니다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: 신규 미승인 proposal; 질문과 vocabulary의 의미 일치 확인. 실제 human 승인은 별도.
- Rejected 오류: 해당 없음 — 신규 SFT 후보
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 분모 0인 drive의 기록 생성/결측 처리와 합성 장소 해소는 실제 실행 검증 과제다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / 분모 0인 drive의 기록 생성/결측 처리와 합성 장소 해소는 실제 실행 검증 과제다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"EVENT","id":"c1","role":"SUPPORT","source":"implicit","subtype":"drive"},{"concept":"LOCATION","id":"c2","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}},{"concept":"PROPORTION","id":"c3","role":"MEASURE","source":"implicit","subtype":"vacant_ratio"}],"factors":{"aggregation":"max","date":"20260915","taxi_type":"corporate"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [tims.yaml:140](/home/hwkim/assistant_univ/schemas/tims.yaml:140)

### RB002-09 — accepted

2026년 9월 15일 가람구에서 관측된 도로 통행의 엔진 회전수 최솟값은?

- 의미 판단: 가람구에서 관측된 passage의 분당 엔진 회전수 최솟값이다.
- 통계/반환 정의: result=min(RPM passage records in date and occurrence scope). 소속 택시 RPM이나 누적 회전량을 의미하지 않는다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: 신규 미승인 proposal; 질문과 vocabulary의 의미 일치 확인. 실제 human 승인은 별도.
- Rejected 오류: 해당 없음 — 신규 SFT 후보
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 원문이 발생 위치를 명시하므로 RB001-17–20의 모호한 질문과 다르다. 그 hold를 해제하지 않는다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / 원문이 발생 위치를 명시하므로 RB001-17–20의 모호한 질문과 다르다. 그 hold를 해제하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"rpm"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"passage"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}}],"factors":{"aggregation":"min","date":"20260915"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37)

### RB002-10 — accepted

2026년 9월 15일 가람구에서 관측된 도로 통행의 엔진 회전수 최댓값은?

- 의미 판단: 가람구에서 관측된 passage의 분당 엔진 회전수 최댓값이다.
- 통계/반환 정의: result=max(RPM passage records in date and occurrence scope). sum이나 일별 평균 max로 바꾸지 않는다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: 신규 미승인 proposal; 질문과 vocabulary의 의미 일치 확인. 실제 human 승인은 별도.
- Rejected 오류: 해당 없음 — 신규 SFT 후보
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: RPM 결측/빈 표본·합성 장소는 실행 범위. RB001 RPM hold와 독립이다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / RPM 결측/빈 표본·합성 장소는 실행 범위. RB001 RPM hold와 독립이다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"rpm"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"passage"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}}],"factors":{"aggregation":"max","date":"20260915"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37)

### RB002-11 — diagnostic_only

2026년 9월 15일 가람구에서 관측된 도로 통행의 타이어 공기압 최댓값은?

- 의미 판단: 통행 관측의 타이어 공기압 최대를 요구하지만 현재 ontology/metric에는 타이어 공기압이 없다.
- 통계/반환 정의: 요구 metric=tyre pressure, max. 현재 grounding vocabulary로 정확히 표현할 수 없어 unsupported 응답이 맞다.
- 추천 근거: 의미상 unsupported pair가 맞지만 기존 보호 family에 속하므로 diagnostic 전용으로 유지한다.
- Chosen 신뢰: {"human_chosen_confirmation_required": true, "level": "proposed_not_reviewed"}
- Rejected 오류: rejected는 타이어 공기압을 passage/rpm 최대값으로 치환한다. 같은 장소·날짜·max라도 다른 물리량이며 structurally valid한 강제 지원 오답이다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: provider 미구현만으로 unsupported라 한 것이 아니라 요청 metric 자체가 허용 vocabulary에 없다. 보호 family에 속하므로 semantic 판정과 무관하게 diagnostic 전용. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: Unsupported 의미 판정을 확인해도 training으로 이동하지 않는다. diagnostic_only 보호를 유지한다. / 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"unsupported":true}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"rpm"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"passage"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}}],"factors":{"aggregation":"max","date":"20260915"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | — | — | — |
| chosen / strict_raw | PASS | — | — | — |
| rejected / production | PASS | PASS | PASS | — |
| rejected / strict_raw | PASS | PASS | PASS | — |

Static compile: unsupported refusal — 그래프/compile 대상 없음

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37)

### RB002-12 — diagnostic_only

2026년 9월 15일 가람시 안의 안전벨트 미착용 적발을 읍면동별로 세어, 기록이 있는 그룹 중 건수가 적은 3곳은?

- 의미 판단: 안전벨트 미착용 적발 사건의 지역별 건수 하위 3곳을 요구한다.
- 통계/반환 정의: 요구 사건=seatbelt violation detection, grouped emd bottom 3. 현재 ontology와 provider schema에 적발 사건/필터가 없다.
- 추천 근거: 의미상 unsupported pair가 맞지만 기존 보호 family에 속하므로 diagnostic 전용으로 유지한다.
- Chosen 신뢰: {"human_chosen_confirmation_required": true, "level": "proposed_not_reviewed"}
- Rejected 오류: rejected는 안전벨트 미착용 적발을 모든 passage 건수로 바꾼다. taxi_status도 안전벨트 상태가 아니므로 통행량은 적발 건수의 대용값이 될 수 없다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 새 supported event를 만들지 않는다. 기존 unsupported 보호 family를 우회할 수 없어 diagnostic 전용이다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: Unsupported 의미 판정을 확인해도 training으로 이동하지 않는다. diagnostic_only 보호를 유지한다. / 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"unsupported":true}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"passage_count"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"passage"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람시","value":{"name":"가람시","region":""}}],"factors":{"date":"20260915","dimension":"emd","limit":3,"order":"bottom"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | — | — | — |
| chosen / strict_raw | PASS | — | — | — |
| rejected / production | PASS | PASS | PASS | — |
| rejected / strict_raw | PASS | PASS | PASS | — |

Static compile: unsupported refusal — 그래프/compile 대상 없음

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [system.yaml:44](/home/hwkim/assistant_univ/prompts/system.yaml:44)

### RB002-13 — accepted

지난달 수성구 개인택시의 주별 운행일수 합계를 평균 내면?

- 의미 판단: 지난달 수성구 소속 개인택시의 주별 택시 운행일수 합계들의 평균이다.
- 통계/반환 정의: d_t,w=택시 t의 주 w 기간 운행일수; S_w=Σ_t d_t,w; result=avg_w S_w. date=last_month, private, inner=sum→outer=avg.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "e11cabb32313e8d953e89f5f595feaf7723ed552f033b59742930a9f61079fce", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-01", "prior_human_decision_hash": "efc95bcd0001d0d4a40213dea5c907f6f3f9330c976990422ece932012f1b734", "source_record_id": "ann-d983889cf8c496178106"}
- Rejected 오류: date가 factors에서 빠지고 지난달이 value 없는 EVENT/operation COND로 들어갔다. private도 value 없는 OBJECT/taxi_type로 옮겨졌다. 장소는 SUBCOND가 아닌 COND이다. 실제 날짜/택시 조건과 source/role가 틀리며 parser는 MISSING_CONCEPT_VALUE로 거부한다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: v001 RB001-01 chosen과 동일. 평균의 주별 표본·주 경계/빈 주 처리와 last_month 기준일은 provider/application 위임 범위를 넘겨 확정하지 않는다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"수성구","value":{"name":"수성구","region":""}}],"factors":{"aggregation":"sum","bucket":"week","date":"last_month","rollup":"avg","taxi_type":"private"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days","text":"운행일수"},{"concept":"EVENT","id":"c2","role":"COND","source":"user","subtype":"operation","text":"지난달"},{"concept":"LOCATION","id":"c3","role":"COND","source":"user","subtype":"place","text":"수성구","value":{"name":"수성구","region":""}},{"concept":"OBJECT","id":"c4","role":"COND","source":"user","subtype":"taxi_type","text":"개인택시"}],"factors":{"aggregation":"sum","bucket":"week","rollup":"avg"}}
```

- 실제 prediction 출처: dpo_best / ex03 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/dpo_best.json
- 원문 raw_text와 canonical rejected 일치를 재검증했다. 실제 raw_text는 JSONL pair_review.actual_rejected_observations에 보존했다.

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | FAIL | — | — | MISSING_CONCEPT_VALUE |
| rejected / strict_raw | FAIL | — | — | MISSING_CONCEPT_VALUE |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-14 — accepted

지난달 수성구 개인택시의 주별 운행일수 합계를 평균 내면?

- 의미 판단: 13과 같은 수성구 개인택시 주별 운행일수 합계의 평균이다.
- 통계/반환 정의: Σ_t d_t,w → avg_w; last_month/private/수성구 scope를 모두 적용해야 한다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "e11cabb32313e8d953e89f5f595feaf7723ed552f033b59742930a9f61079fce", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-01", "prior_human_decision_hash": "efc95bcd0001d0d4a40213dea5c907f6f3f9330c976990422ece932012f1b734", "source_record_id": "ann-d983889cf8c496178106"}
- Rejected 오류: 13의 잘못된 날짜·택시 concept 인코딩에 더해 수성구 LOCATION 자체를 누락했다. 시간·택시·공간 모집단을 잃은 실제 모델 오답이다. MISSING_CONCEPT_VALUE는 첫 오류이며 전체 의미 오류를 대표하지 않는다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: chosen은 RB001-01 승인 gold. 13과 같은 prompt의 다른 실제 rejected이며 독립 질문으로 SFT에 중복 추가하지 않는다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"수성구","value":{"name":"수성구","region":""}}],"factors":{"aggregation":"sum","bucket":"week","date":"last_month","rollup":"avg","taxi_type":"private"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days","text":"운행일수"},{"concept":"EVENT","id":"c2","role":"COND","source":"user","subtype":"operation","text":"지난달"},{"concept":"OBJECT","id":"c3","role":"COND","source":"user","subtype":"taxi_type","text":"개인택시"}],"factors":{"aggregation":"sum","bucket":"week","rollup":"avg"}}
```

- 실제 prediction 출처: base / ex03 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/base.json; sft_best / ex03 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/sft_best.json
- 원문 raw_text와 canonical rejected 일치를 재검증했다. 실제 raw_text는 JSONL pair_review.actual_rejected_observations에 보존했다.

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | FAIL | — | — | MISSING_CONCEPT_VALUE |
| rejected / strict_raw | FAIL | — | — | MISSING_CONCEPT_VALUE |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-15 — accepted

2026년 상반기 동구 법인택시 월별 매출 평균 중 가장 큰 값은?

- 의미 판단: 상반기 동구 소속 법인택시의 월별 매출 평균 중 가장 큰 값이다.
- 통계/반환 정의: X_m=해당 월 operation revenue 표본; μ_m=avg(X_m); result=max_m μ_m. Jan1–Jun30, month/avg/max, corporate.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "69531db7e79e11b651ac2ec55df06a6f2bcda7467d09b0de14aacd189cbd3aef", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-02", "prior_human_decision_hash": "d3111dd9b68a69a07d972502d899d0f673088817fe051a1ba3c93624a5fe8915", "source_record_id": "ann-cc38d74754ba7eab68a8"}
- Rejected 오류: 상반기와 법인택시를 값 없는 EVENT/operation COND로 인코딩하고 date/corporate factors를 누락했다. 장소 role도 COND이다. 월 stage는 맞더라도 모집단 조건이 잘못되어 chosen을 선호해야 한다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 동구 region=""는 채택 정책이다. avg의 provider 표본 세부 정의를 새로 확정하지 않으며 실제 동구 상위 도시를 만들어 넣지 않는다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"revenue"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"동구","value":{"name":"동구","region":""}}],"factors":{"aggregation":"avg","bucket":"month","date":"20260101-20260630","rollup":"max","taxi_type":"corporate"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"revenue","text":"매출"},{"concept":"EVENT","id":"c2","role":"COND","source":"user","subtype":"operation","text":"2026년 상반기"},{"concept":"EVENT","id":"c3","role":"COND","source":"user","subtype":"operation","text":"법인택시"},{"concept":"LOCATION","id":"c4","role":"COND","source":"user","subtype":"place","text":"동구","value":{"name":"동구","region":""}}],"factors":{"aggregation":"avg","answer":"value","bucket":"month","rollup":"max"}}
```

- 실제 prediction 출처: base / ex04 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/base.json; sft_best / ex04 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/sft_best.json; dpo_best / ex04 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/dpo_best.json
- 원문 raw_text와 canonical rejected 일치를 재검증했다. 실제 raw_text는 JSONL pair_review.actual_rejected_observations에 보존했다.

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | FAIL | — | — | MISSING_CONCEPT_VALUE |
| rejected / strict_raw | FAIL | — | — | MISSING_CONCEPT_VALUE |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-16 — accepted

2026년 8월 나래구 개인택시 주별 매출 합계 중 가장 작은 값은?

- 의미 판단: 8월 나래구 소속 개인택시의 주별 영업 매출 합계 중 최솟값이다.
- 통계/반환 정의: R_w=Σ operation revenue in w for private cohort; result=min_w R_w, 숫자 반환. Aug1–Aug31.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "4ddf600e8c90fb9bb5359942198baf84ba53ac7c02f06cfb372c3e5f40280fd1", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-03", "prior_human_decision_hash": "e07c9147fd7adac02c57d7dfbb4ed8a41993a0c30493b31d583113fc5022f0af", "source_record_id": "ann-da98b3941dfa1c7ce800"}
- Rejected 오류: 나래구 LOCATION과 private 조건을 누락했고 날짜를 비계약 202608로 출력했다. answer=value는 중복 명시이며 이것 하나만 오답 근거로 삼지 않는다. 모집단 누락과 날짜 표현 오류가 실제 핵심이다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: v001 RB001-03/reference 기반 semantic chosen; TIMS legacy와 reference 실행 가능성을 구분한다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"revenue"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"나래구","value":{"name":"나래구","region":""}}],"factors":{"aggregation":"sum","bucket":"week","date":"20260801-20260831","rollup":"min","taxi_type":"private"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"revenue"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"}],"factors":{"aggregation":"sum","answer":"value","bucket":"week","date":"202608","rollup":"min"}}
```

- 실제 prediction 출처: base / ex05 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/base.json; dpo_best / ex05 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/dpo_best.json
- 원문 raw_text와 canonical rejected 일치를 재검증했다. 실제 raw_text는 JSONL pair_review.actual_rejected_observations에 보존했다.

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | FAIL | — | — | INVALID_FACTOR |
| rejected / strict_raw | FAIL | — | — | INVALID_FACTOR |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-17 — accepted

2026년 8월 나래구 개인택시 주별 매출 합계 중 가장 작은 값은?

- 의미 판단: 16과 같은 주별 매출 합계 최솟값 질문이다.
- 통계/반환 정의: 나래구 소속 private, August 범위; sum week → min scalar.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "4ddf600e8c90fb9bb5359942198baf84ba53ac7c02f06cfb372c3e5f40280fd1", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-03", "prior_human_decision_hash": "e07c9147fd7adac02c57d7dfbb4ed8a41993a0c30493b31d583113fc5022f0af", "source_record_id": "ann-da98b3941dfa1c7ce800"}
- Rejected 오류: 나래구 scope를 누락하고 질문에 없는 dimension=sido를 추가하여 전국 시도 그룹으로 바꿨다. 날짜도 비계약 202608이다. private 유지 여부와 무관하게 공간 모집단·반환 형태가 다르다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 실측 SFT variant를 보존한다. 16과 동일 chosen이라 SFT 새 질문 수를 늘리지 않는다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"revenue"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"나래구","value":{"name":"나래구","region":""}}],"factors":{"aggregation":"sum","bucket":"week","date":"20260801-20260831","rollup":"min","taxi_type":"private"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"revenue"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"}],"factors":{"aggregation":"sum","bucket":"week","date":"202608","dimension":"sido","rollup":"min","taxi_type":"private"}}
```

- 실제 prediction 출처: sft_best / ex05 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/sft_best.json
- 원문 raw_text와 canonical rejected 일치를 재검증했다. 실제 raw_text는 JSONL pair_review.actual_rejected_observations에 보존했다.

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | FAIL | — | — | INVALID_FACTOR |
| rejected / strict_raw | FAIL | — | — | INVALID_FACTOR |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-18 — accepted

지난달 동구 법인택시 주별 운행일수 평균 중 가장 작은 값은?

- 의미 판단: 지난달 동구 소속 법인택시의 각 주 운행일수 평균들 중 최소 값이다.
- 통계/반환 정의: a_w=avg_t d_t,w; result=min_w a_w. inner=avg, week, outer=min, scalar.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "ea8076684d58dea66817101ec0ecca0189c7542d3af4fb970eabf20acac75bf2", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-06", "prior_human_decision_hash": "d6854f0e1d93211d6902359c65a0c8772b36d8f85910389df90e1e52aece3c6c", "source_record_id": "ann-89f3d036b2d43dd431f0"}
- Rejected 오류: 법인택시와 지난달을 EVENT/operation COND/source=user로 넣고 value를 제공하지 않았으며 date/corporate factors도 누락했다. answer=value가 있는 것 자체보다 cohort/time 누락과 잘못된 concept/source가 문제다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: v001 RB001-06 chosen. 상위 지역 없음 정책을 유지; 숫자 반환과 주 선택을 혼동하지 않는다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"동구","value":{"name":"동구","region":""}}],"factors":{"aggregation":"avg","bucket":"week","date":"last_month","rollup":"min","taxi_type":"corporate"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days","text":"운행일수"},{"concept":"EVENT","id":"c2","role":"COND","source":"user","subtype":"operation","text":"법인택시"},{"concept":"EVENT","id":"c3","role":"COND","source":"user","subtype":"operation","text":"지난달"},{"concept":"LOCATION","id":"c4","role":"SUBCOND","source":"user","subtype":"place","text":"동구","value":{"name":"동구","region":""}}],"factors":{"aggregation":"avg","answer":"value","bucket":"week","rollup":"min"}}
```

- 실제 prediction 출처: base / ex09 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/base.json; sft_best / ex09 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/sft_best.json; dpo_best / ex09 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/dpo_best.json
- 원문 raw_text와 canonical rejected 일치를 재검증했다. 실제 raw_text는 JSONL pair_review.actual_rejected_observations에 보존했다.

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | FAIL | — | — | MISSING_CONCEPT_VALUE |
| rejected / strict_raw | FAIL | — | — | MISSING_CONCEPT_VALUE |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-19 — accepted

지난달 동구 법인택시의 운행일수 평균이 가장 적었던 주는?

- 의미 판단: 지난달 동구 소속 법인택시의 주별 택시 운행일수 평균이 최소인 주를 선택한다.
- 통계/반환 정의: a_w=avg_t d_t,w; result=argmin_w a_w. answer=bucket, week, rollup=min. numeric min을 답하지 않는다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "eb89cfaeabc1d391ad685e49c1659152373707e6e514b64dd3482d93582e6b4f", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-07", "prior_human_decision_hash": "932a3fb6f5ef622a14242c927f8112967a2f9933481243fd8cc3d14ef0989ccf", "source_record_id": "ann-aa1d7fd59c1d3d2ea97b"}
- Rejected 오류: answer=bucket stage는 맞지만 지난달을 값 없는 EVENT COND로, corporate를 값 없는 OBJECT/taxi_type로 인코딩했다. factors date/corporate 누락이 cohort/time을 잃는다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: v001 RB001-07 chosen. SELECT_GROUP의 TIMS 직접 lowering 한계는 semantic unsupported가 아니다. 동률 주 선택은 실행 정책 확인 대상. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"동구","value":{"name":"동구","region":""}}],"factors":{"aggregation":"avg","answer":"bucket","bucket":"week","date":"last_month","rollup":"min","taxi_type":"corporate"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"COND","source":"user","subtype":"operation","text":"지난달"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"동구","value":{"name":"동구","region":""}},{"concept":"OBJECT","id":"c4","role":"COND","source":"user","subtype":"taxi_type","text":"법인택시"}],"factors":{"aggregation":"avg","answer":"bucket","bucket":"week","rollup":"min"}}
```

- 실제 prediction 출처: base / ex10 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/base.json; sft_best / ex10 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/sft_best.json; dpo_best / ex10 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/dpo_best.json
- 원문 raw_text와 canonical rejected 일치를 재검증했다. 실제 raw_text는 JSONL pair_review.actual_rejected_observations에 보존했다.

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | FAIL | — | — | MISSING_CONCEPT_VALUE |
| rejected / strict_raw | FAIL | — | — | MISSING_CONCEPT_VALUE |

Static compile: UNVERIFIED_TIMS_CONTRACT (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-20 — accepted

지난달 달서구 개인택시 주별 운행일수 평균들의 평균은?

- 의미 판단: 지난달 달서구 개인택시의 주별 택시 운행일수 평균들의 평균이다.
- 통계/반환 정의: a_w=Σ_t d_t,w/n_w; result=Σ_w a_w/k. 주별 동일 가중 avg→avg. 전체 기간 운행일수 평균이나 합으로 바꾸지 않는다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "6fc09d6a34926372f425c304ee78aa7a6a70c311ea76ee0bcd3679cde490cf6f", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-08", "prior_human_decision_hash": "f13df5805c9c749e5fe7b6d8ca92bbe8a9bc34c71f8873ad88ac5762ce7d717c", "source_record_id": "ann-f8d44f2cfa96200b5a95"}
- Rejected 오류: private와 last_month를 값 없는 EVENT/operation COND로 인코딩하고 date/taxi_type factors를 삭제했다. 장소도 COND로 잘못 표기했다. stage가 유지되어도 의미·contract 오답이다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: v001 RB001-08 chosen; avg의 대상 택시 cohort/결측 처리는 기존 provider 위임 범위로 유지한다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"달서구","value":{"name":"달서구","region":""}}],"factors":{"aggregation":"avg","bucket":"week","date":"last_month","rollup":"avg","taxi_type":"private"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"COND","source":"user","subtype":"operation","text":"개인택시"},{"concept":"EVENT","id":"c3","role":"COND","source":"user","subtype":"operation","text":"지난달"},{"concept":"LOCATION","id":"c4","role":"COND","source":"user","subtype":"place","text":"달서구","value":{"name":"달서구","region":""}}],"factors":{"aggregation":"avg","bucket":"week","rollup":"avg"}}
```

- 실제 prediction 출처: base / ex15 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/base.json; sft_best / ex15 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/sft_best.json; dpo_best / ex15 / train / /home/hwkim/assistant_univ/training/experiments/thor_pilot_001/metrics/dpo_best.json
- 원문 raw_text와 canonical rejected 일치를 재검증했다. 실제 raw_text는 JSONL pair_review.actual_rejected_observations에 보존했다.

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | FAIL | — | — | MISSING_CONCEPT_VALUE |
| rejected / strict_raw | FAIL | — | — | MISSING_CONCEPT_VALUE |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-21 — accepted

지난달 수성구 개인택시의 주별 운행일수 합계를 평균 내면?

- 의미 판단: 수성구 개인택시 주별 운행일수 합계의 평균; 장소명은 조회 전 조건이다.
- 통계/반환 정의: Σ_t d_t,w → avg_w; 나머지 chosen factor·source·value는 RB001-01 그대로다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "e11cabb32313e8d953e89f5f595feaf7723ed552f033b59742930a9f61079fce", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-01", "prior_human_decision_hash": "efc95bcd0001d0d4a40213dea5c907f6f3f9330c976990422ece932012f1b734", "source_record_id": "ann-d983889cf8c496178106"}
- Rejected 오류: 장소명 수성구를 즉시 사용 가능한 COND로 바꿨다. prompt는 장소명=SUBCOND, 직접 scope=COND로 구분한다. Composer가 같은 graph로 수용해도 raw semantic grounding role의 오답이다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 출력 숫자 차이가 입증된 negative가 아니라 planner role contract를 학습하는 contrast임을 승인 시 확인한다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / 계산 결과가 같을 수 있어도 raw planner source/role/value contract 오류를 DPO 학습 목표로 유지하는지 확인한다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"수성구","value":{"name":"수성구","region":""}}],"factors":{"aggregation":"sum","bucket":"week","date":"last_month","rollup":"avg","taxi_type":"private"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"COND","source":"user","subtype":"place","text":"수성구","value":{"name":"수성구","region":""}}],"factors":{"aggregation":"sum","bucket":"week","date":"last_month","rollup":"avg","taxi_type":"private"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | PASS | PASS | PASS | — |
| rejected / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-22 — accepted

지난달 수성구 개인택시의 주별 운행일수 합계를 평균 내면?

- 의미 판단: 21과 같은 질문이며 수성구라는 장소 값을 사용자가 제공했다.
- 통계/반환 정의: 질문에 존재하는 LOCATION/place는 user/value={name:수성구,region:""}; EVENT와 MEASURE만 value 없는 implicit 맥락이다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "e11cabb32313e8d953e89f5f595feaf7723ed552f033b59742930a9f61079fce", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-01", "prior_human_decision_hash": "efc95bcd0001d0d4a40213dea5c907f6f3f9330c976990422ece932012f1b734", "source_record_id": "ann-d983889cf8c496178106"}
- Rejected 오류: LOCATION source를 implicit으로 바꾸면서 user place value를 유지했다. 사용자 명시 값이라는 출처를 잃고 implicit에는 value를 두지 않는 prompt 규칙을 어긴다. downstream graph 통과는 이 출처 의미를 검증하지 않는다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 수치 결과 차이가 아니라 명시 값/implicit 맥락의 production contract contrast다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / 계산 결과가 같을 수 있어도 raw planner source/role/value contract 오류를 DPO 학습 목표로 유지하는지 확인한다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"수성구","value":{"name":"수성구","region":""}}],"factors":{"aggregation":"sum","bucket":"week","date":"last_month","rollup":"avg","taxi_type":"private"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"implicit","subtype":"place","text":"수성구","value":{"name":"수성구","region":""}}],"factors":{"aggregation":"sum","bucket":"week","date":"last_month","rollup":"avg","taxi_type":"private"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | PASS | PASS | PASS | — |
| rejected / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-23 — needs_fix

2026년 9월 15일 가람구 소속 법인택시의 개별 전체 운행 경로에 기록된 공차율 최댓값은?

- 의미 판단: 08과 동일한 법인택시 drive 공차율 최댓값 질문이다.
- 통계/반환 정의: max_i vacant_ratio(drive_i); MEASURE는 implicit/value 없음. 질문은 공차율 0.25라는 입력을 주지 않았다.
- 추천 근거: 의미는 일치하지만 RB002-08 신규 chosen의 실제 human 승인이 아직 없어 dependency hold. JSON 교정은 필요하지 않다.
- Chosen 신뢰: {"approval_dependency": "RB002-08", "human_chosen_confirmation_required": true, "level": "proposed_not_reviewed"}
- Rejected 오류: MEASURE source=user/value=0.25를 추가해 계산할 결과를 사용자 입력으로 가장했다. 0.25와 percent 변환 논쟁이 아니라 원문에 없는 값·출처 자체가 오류다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 08 실제 승인 전에는 pair 승인 불가. 현재 draft의 needs_fix는 dependency hold이며 grounding JSON 수정 요청이 아니다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: RB002-08를 실제 accepted로 확정해야 이 pair를 승인할 수 있다. 반려/수정되면 chosen 및 rejected를 다시 검토한다. / 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / 계산 결과가 같을 수 있어도 raw planner source/role/value contract 오류를 DPO 학습 목표로 유지하는지 확인한다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"EVENT","id":"c1","role":"SUPPORT","source":"implicit","subtype":"drive"},{"concept":"LOCATION","id":"c2","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}},{"concept":"PROPORTION","id":"c3","role":"MEASURE","source":"implicit","subtype":"vacant_ratio"}],"factors":{"aggregation":"max","date":"20260915","taxi_type":"corporate"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"EVENT","id":"c1","role":"SUPPORT","source":"implicit","subtype":"drive"},{"concept":"LOCATION","id":"c2","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}},{"concept":"PROPORTION","id":"c3","role":"MEASURE","source":"user","subtype":"vacant_ratio","value":0.25}],"factors":{"aggregation":"max","date":"20260915","taxi_type":"corporate"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | PASS | PASS | PASS | — |
| rejected / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [tims.yaml:140](/home/hwkim/assistant_univ/schemas/tims.yaml:140)

### RB002-24 — accepted

2026년 상반기 동구 법인택시 월별 매출 평균 중 가장 큰 값은?

- 의미 판단: 상반기 동구 법인택시의 월별 매출 평균 최댓값이다.
- 통계/반환 정의: monthly operation revenue avg→max, corporate cohort.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "69531db7e79e11b651ac2ec55df06a6f2bcda7467d09b0de14aacd189cbd3aef", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-02", "prior_human_decision_hash": "d3111dd9b68a69a07d972502d899d0f673088817fe051a1ba3c93624a5fe8915", "source_record_id": "ann-cc38d74754ba7eab68a8"}
- Rejected 오류: taxi_type=corporate를 제거하여 법인택시에서 유형 제한 없는 전체 택시로 대상을 바꿨다. factor가 optional이라는 schema 사실은 원문의 조건을 생략해도 된다는 뜻이 아니다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: chosen RB001-02 승인 gold. 동구 상위 도시를 임의로 추가하지 않는다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"revenue"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"동구","value":{"name":"동구","region":""}}],"factors":{"aggregation":"avg","bucket":"month","date":"20260101-20260630","rollup":"max","taxi_type":"corporate"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"revenue"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"동구","value":{"name":"동구","region":""}}],"factors":{"aggregation":"avg","bucket":"month","date":"20260101-20260630","rollup":"max"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | PASS | PASS | PASS | — |
| rejected / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-25 — needs_fix

2026년 9월 15일 가람구에서 기록된 도로 통행의 주행 속도 최솟값은?

- 의미 판단: 03과 같은 날짜·발생 scope의 passage speed 최솟값이다.
- 통계/반환 정의: 하루 안 기록 전부의 speed min; 별도 시각 제한을 원문이 주지 않았다.
- 추천 근거: 의미는 일치하지만 RB002-03 신규 chosen의 실제 human 승인이 아직 없어 dependency hold. JSON 교정은 필요하지 않다.
- Chosen 신뢰: {"approval_dependency": "RB002-03", "human_chosen_confirmation_required": true, "level": "proposed_not_reviewed"}
- Rejected 오류: time=220000-235959를 환각하여 하루 기록을 야간 일부로 줄였다. 그 구간의 최솟값과 전체 일자의 최솟값은 일반적으로 다르다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 03 실제 승인 전 pair 승인 불가. 신규 JSON은 수정 없이 유지 가능하나 dependency를 해소해야 한다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: RB002-03를 실제 accepted로 확정해야 이 pair를 승인할 수 있다. 반려/수정되면 chosen 및 rejected를 다시 검토한다. / 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"speed"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"passage"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}}],"factors":{"aggregation":"min","date":"20260915"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"speed"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"passage"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}}],"factors":{"aggregation":"min","date":"20260915","time":"220000-235959"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | PASS | PASS | PASS | — |
| rejected / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37)

### RB002-26 — needs_fix

2026년 9월 15일 가람구 소속 택시의 실차 구간별 요금 중앙값은?

- 의미 판단: 01과 같은 trip 운임 중앙값 질문이다.
- 통계/반환 정의: median(trip fare); operation의 택시·일 revenue median이 아니다.
- 추천 근거: 의미는 일치하지만 RB002-01 신규 chosen의 실제 human 승인이 아직 없어 dependency hold. JSON 교정은 필요하지 않다.
- Chosen 신뢰: {"approval_dependency": "RB002-01", "human_chosen_confirmation_required": true, "level": "proposed_not_reviewed"}
- Rejected 오류: fare→revenue와 trip→operation을 일관되게 바꿔 valid한 다른 measure graph를 만들었다. 금액이라는 concept만 같고 관측 단위/물리량이 다르므로 의미 오답이다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 01 실제 승인 전 pair 승인 불가. 두 subtype을 함께 바꾸는 synthetic contrast이며 실제 fare swap 관측이라고 주장하지 않는다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: RB002-01를 실제 accepted로 확정해야 이 pair를 승인할 수 있다. 반려/수정되면 chosen 및 rejected를 다시 검토한다. / 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"fare"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"trip"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}}],"factors":{"aggregation":"med","date":"20260915"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"revenue"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}}],"factors":{"aggregation":"med","date":"20260915"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | PASS | PASS | PASS | — |
| rejected / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37)

### RB002-27 — accepted

지난달 수성구 개인택시의 주별 운행일수 합계를 평균 내면?

- 의미 판단: 주별 운행일수 합계를 평균 낸다.
- 통계/반환 정의: chosen: S_w=Σ_t d_t,w; result=Σ_w S_w/k. rejected: a_w=Σ_t d_t,w/n_w; result=Σ_w a_w.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "e11cabb32313e8d953e89f5f595feaf7723ed552f033b59742930a9f61079fce", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-01", "prior_human_decision_hash": "efc95bcd0001d0d4a40213dea5c907f6f3f9330c976990422ece932012f1b734", "source_record_id": "ann-d983889cf8c496178106"}
- Rejected 오류: sum→avg를 avg→sum으로 바꿔 inner 분모 n_w와 outer 분모 k를 서로 바꿨다. stage swap이며 일반적으로 계산이 다르다. 특수 데이터에서 우연히 값이 같아도 질문 의미는 다르다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 빈 주/택시 포함은 위임 범위. 새로운 통계 product 결정을 몰래 채워 넣지 않는다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"수성구","value":{"name":"수성구","region":""}}],"factors":{"aggregation":"sum","bucket":"week","date":"last_month","rollup":"avg","taxi_type":"private"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"operating_days"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"수성구","value":{"name":"수성구","region":""}}],"factors":{"aggregation":"avg","bucket":"week","date":"last_month","rollup":"sum","taxi_type":"private"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | PASS | PASS | PASS | — |
| rejected / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-28 — accepted

2026년 8월 나래구 개인택시 주별 매출 합계 중 가장 작은 값은?

- 의미 판단: 주별 revenue 합계 중 최솟값을 반환한다.
- 통계/반환 정의: chosen=min_w Σ_i revenue_i,w; rejected=Σ_w min_i revenue_i,w.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "4ddf600e8c90fb9bb5359942198baf84ba53ac7c02f06cfb372c3e5f40280fd1", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-03", "prior_human_decision_hash": "e07c9147fd7adac02c57d7dfbb4ed8a41993a0c30493b31d583113fc5022f0af", "source_record_id": "ann-da98b3941dfa1c7ce800"}
- Rejected 오류: 주별 합계의 최솟값을 주별 최소 기록값들의 합으로 바꿨다. inner/outer의 대상과 값이 달라 동일 통계가 아니다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: v001 reference 기반 chosen 그대로. 실제 TIMS numeric 검증을 했다는 뜻이 아니다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"revenue"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"나래구","value":{"name":"나래구","region":""}}],"factors":{"aggregation":"sum","bucket":"week","date":"20260801-20260831","rollup":"min","taxi_type":"private"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"revenue"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"나래구","value":{"name":"나래구","region":""}}],"factors":{"aggregation":"min","bucket":"week","date":"20260801-20260831","rollup":"sum","taxi_type":"private"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | PASS | PASS | PASS | — |
| rejected / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-29 — accepted

2026년 상반기 동구 법인택시 월별 매출 평균 중 가장 큰 값은?

- 의미 판단: 상반기의 월 평균 매출들 중 최댓값이다.
- 통계/반환 정의: chosen=max_m avg(X_m); rejected=avg(∪_m X_m). 월 grouping과 outer max를 둘 다 보존해야 한다.
- 추천 근거: 질문의 표본·measure·source/role/value·factor·집계 단계와 일치한다. DPO는 rejected의 구체적 의미 오류를 확인했다. 실제 승인은 사람이 별도 확정한다.
- Chosen 신뢰: {"canonical_grounding_hash": "69531db7e79e11b651ac2ec55df06a6f2bcda7467d09b0de14aacd189cbd3aef", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "human_rejected_confirmation_required": true, "level": "reviewed_gold_v001_train", "prior_batch_item_id": "RB001-02", "prior_human_decision_hash": "d3111dd9b68a69a07d972502d899d0f673088817fe051a1ba3c93624a5fe8915", "source_record_id": "ann-cc38d74754ba7eab68a8"}
- Rejected 오류: bucket=month와 rollup=max를 삭제해 전체 기간 평균 하나로 축약했다. 남은 avg factor는 monthly maximum을 표현하지 못한다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 동구 region="" 정책 그대로; avg 표본/결측 정의는 provider 범위. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"revenue"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"동구","value":{"name":"동구","region":""}}],"factors":{"aggregation":"avg","bucket":"month","date":"20260101-20260630","rollup":"max","taxi_type":"corporate"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"revenue"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"operation"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"동구","value":{"name":"동구","region":""}}],"factors":{"aggregation":"avg","date":"20260101-20260630","taxi_type":"corporate"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | PASS | PASS | PASS | — |
| rejected / strict_raw | PASS | PASS | PASS | — |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [event_to_grouped_measure.yaml:1](/home/hwkim/assistant_univ/geoflow_macros/event_to_grouped_measure.yaml:1), [compiler.py:431](/home/hwkim/assistant_univ/geoflow/compiler.py:431), [README.md:447](/home/hwkim/assistant_univ/README.md:447)

### RB002-30 — needs_fix

2026년 9월 15일 가람구에서 관측된 도로 통행의 엔진 회전수 최솟값은?

- 의미 판단: 09와 같은 passage RPM 최솟값 질문이다.
- 통계/반환 정의: chosen=min(RPM passage records); rejected=sum(RPM passage records).
- 추천 근거: 의미는 일치하지만 RB002-09 신규 chosen의 실제 human 승인이 아직 없어 dependency hold. JSON 교정은 필요하지 않다.
- Chosen 신뢰: {"approval_dependency": "RB002-09", "human_chosen_confirmation_required": true, "level": "proposed_not_reviewed"}
- Rejected 오류: 최솟값을 sum으로 바꿨고 measures.py는 RPM intensive value의 sum을 undefined로 정의한다. composer의 UNDEFINED_MEASURE_AGGREGATION은 의미 오답과 맞는 실제 constraint 근거다.
- 교정: 필요 없음. corrected_grounding/pair=null. dependency hold를 grounding 오류로 간주하지 않는다.
- Semantic ambiguity: 원문→grounding에서 별도 선택이 필요한 미해결 의미 충돌은 발견하지 못했다. 아래 실행/lineage 확인은 별개다.
- Provider/실행 한계: 09 실제 승인 전 pair 승인 불가. RPM sum 자체는 synthetic control이며 기존 RPM hold를 승인하지 않는다. / 실제 TIMS 호출·executor·model inference 미실행. Static compile PASS는 실제 수치/장소/기간 실행 검증이 아니다.
- 사람 확인: RB002-09를 실제 accepted로 확정해야 이 pair를 승인할 수 있다. 반려/수정되면 chosen 및 rejected를 다시 검토한다. / 평가/dev 질문의 paraphrase나 날짜·지역만 바꾼 파생인지 최종 lineage 확인. 자동 보호 검사 통과는 이 확인을 대신하지 않는다. / 추천을 검토한 뒤 실제 human decision을 별도 기록한다. 이 draft는 승인 감사 기록이 아니다. / Chosen이 맞고 rejected가 틀리다는 의미 판단을 pair 전체에 대해 확인한다. Validator PASS만으로 정하지 않는다.
- Source/role/value: 모든 chosen은 event=implicit SUPPORT, 결과=implicit MEASURE/value 없음, 명시 장소=user SUBCOND/value(name,region). unsupported는 concepts가 없다.

Chosen / proposed grounding:
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"rpm"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"passage"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}}],"factors":{"aggregation":"min","date":"20260915"}}
```

Rejected (이 출력을 고쳐서 실제 모델 오답이라고 주장하지 않음):
```json
{"concepts":[{"concept":"AMOUNT","id":"c1","role":"MEASURE","source":"implicit","subtype":"rpm"},{"concept":"EVENT","id":"c2","role":"SUPPORT","source":"implicit","subtype":"passage"},{"concept":"LOCATION","id":"c3","role":"SUBCOND","source":"user","subtype":"place","text":"가람구","value":{"name":"가람구","region":""}}],"factors":{"aggregation":"sum","date":"20260915"}}
```

CPU 재검증 (의미 판단과 별개; `—`는 미도달/해당 없음):

| Target / mode | Parse | Compose | Validate | Error / failed G codes |
|---|---|---|---|---|
| chosen / production | PASS | PASS | PASS | — |
| chosen / strict_raw | PASS | PASS | PASS | — |
| rejected / production | PASS | FAIL | — | UNDEFINED_MEASURE_AGGREGATION |
| rejected / strict_raw | PASS | FAIL | — | UNDEFINED_MEASURE_AGGREGATION |

Static compile: PASS (mock/TIMS legacy, 실제 실행 미검증)

코드 근거: [geoflow_planner.yaml:165](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:165), [geoflow_planner.yaml:185](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:185), [geoflow_planner.yaml:232](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:232), [geoflow_planner.yaml:326](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:326), [measures.py:53](/home/hwkim/assistant_univ/geoflow/measures.py:53), [tims.yaml:1](/home/hwkim/assistant_univ/schemas/tims.yaml:1), [_common.yaml:37](/home/hwkim/assistant_univ/schemas/_common.yaml:37), [composer.py:839](/home/hwkim/assistant_univ/geoflow/composer.py:839)

## 재현성과 비변경 검증

- Commit/branch: 65e9ea2ec98f8cec289cbb753ce543dee3efdd92 / geoflow/dev-v2
- Production prompt hash: 522aa3b1716248b53a755ee1b236e7aef302c85504e9cfac3825f4d3cc817945
- Queue SHA256: 5103eb7c64f49ed55276552d2764942c387359da9ea4eae64fff508286b3a3e6
- Frozen v001 corpus_manifest SHA256: 59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9
- Draft SHA256: ebe24acb871e56bc7bd5669bd2a3acf1df939efd94e8e094515476eb52805a79
- 기존 artifact/source/protection 115개 파일의 SHA256를 시작/끝에 대조했다. 기존 queue/status/manifest/v001/hold/protected 데이터와 production git diff는 동일하다.
- CPU chosen strict_raw/production parse→compose→validate 재실행: answered 28건 모두 PASS, unsupported2건은 refusal contract 검사만(그래프 없음). DPO20건 양쪽을 재검사하고 category와 원문 실제prediction을 검증했다. G rule까지 도달하지 않은 오류에 G 실패를 붙이지 않았다.
- 모든 추천은 assistant draft이며 human 감사 레코드가 아니다. 신규 실제 accepted 0, queue pending30. 코드/schema/prompt 변경 없음, GPU/학습/새 inference/실제 TIMS 호출/import/v002 생성 없음.

추가 artifact 검증 9개가 모두 통과했다: 30건/hash 연결, 추천 분포, 승인 의존성, diagnostic 보호, target 무변경, downstream/category 분포, 실측 raw prediction 일치, 실제 승인/import 없음, 기존 동결 파일 무변경.

## 최종 확정 절차

사람이 01–10 및 trusted chosen pair를 검토한 뒤 기존 workflow decide로 실제 decision을 별도 기록한다. 23/25/26/30은 선행 gold의 실제 accepted decision 확인 후 pair 양쪽을 재확정한다. 11/12는 diagnostic 전용 보호를 유지한다. 이 draft의 reviewer_kind=assistant는 importer가 요구하는 human decision을 대신할 수 없다. v002 조립/import는 이 작업에 포함하지 않았다.
