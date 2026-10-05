# REVIEW_DECISIONS_001 — semantic decision draft

추천 accepted 11 / rejected 0 / needs_fix 19. **실제 queue/status는 모두 pending이고 승인·import는 하지 않았다.** 이 draft는 assistant가 작성했으며 human review attestation이 아니다. `decisions_draft.jsonl`을 `--decisions`로 import하거나 status로 복사하지 않는다.

이전 batch의 heuristic 추천(accepted 16 / needs_fix 14)에서 RB001-03, 21–24를 needs_fix로 보류했다. 근거는 추가 CPU 확인에서 현재 mock 장소 조회가 실패하고 provider/corpus context 확정이 필요하다는 점이다. 의미 grounding이 틀렸다는 결론은 아니다.

## 검토 범위와 실행 관측

원문을 production prompt/ontology/roles, factor 정의, measure 통계 정의, deterministic OD mapping, TIMS 계약 및 compiler에 대조했다. 모든 proposed grounding의 strict raw parse→compose→G1~G7 PASS를 재확인했지만 이 사실로 semantic 정답을 판정하지 않았다.

- 기본 프로필: mock + TIMS legacy 계약, reference date 2026-09-25. GPU/model inference 없이 CPU에서 production compiler/executor 및 로컬 mock handlers만 사용했다.
- 30건 중 compile 23건 성공 / 7건 `UNVERIFIED_TIMS_CONTRACT`. Compile 성공 23건 중 mock execution 11건 성공 / 12건 장소 `NOT_FOUND`. 실패한 곳에서 통계 Tool의 동작을 검증했다고 주장하지 않는다.
- Mock 수치/순위는 고정 fixture이므로 실제 TIMS 통계 정답의 증거가 아니다. 저장소에는 실제 TIMS adapter가 없다. 실제 TIMS 성공률은 측정하지 않았다.
- RB001-03: 원본 ex05가 지정한 reference provider에서 30000을 재현했다. RB001-04: ex07 reference provider에서 최저 주 20260831-20260831(value=30000)을 재현했다. 모두 합성 결과이고 TIMS 계약에 전이하지 않는다.
- 나래구는 reference에만 있다. 솔빛동/해솔동/온유동은 현재 mock 및 reference 장소 사전에 없다. 해당 명칭이 실제 TIMS에도 없다는 증거는 아니며 질문 자체의 synthetic context 문제다.
- 동구/중구는 원문에 상위 도시가 없다. mock의 대구 mapping으로 원문에 없는 region을 채우지 않는다. Accepted 02/06은 literal grounding 기준의 추천이고 실제 지역 식별 의도는 사람이 확인한다.
- Support는 legacy의 provider-delegated 조건에서만 평가했다. strict mode, 상대 날짜 기준, 평균 분모, 빈 구간, 주 시작 규칙의 동일성을 가정하지 않았다.

## Correction에 관한 결론

확정된 JSON field correction은 없다. Accepted 추천의 target은 그대로 유지한다. Needs_fix의 주된 문제는 질문의 통계 정의 또는 corpus/provider 지원 context이다. 부족한 정의를 invented factor로 넣거나, 질문에 없는 대구·실제 장소를 넣거나, answer=bucket을 value로 바꾸어 실행을 통과시키지 않는다. 그래서 `corrected_grounding=null`과 각 항목의 correction 불가 사유를 명시했다.

04/05/07/17–20의 `support_policy_alternative`는 {"unsupported":true}라는 **조건부 정책 대안**이며 수정 정답이 아니다. Planner의 semantic 역할에 실행 책임을 옮기는 변경을 권장하지 않는다. 현재 queue의 answered outcome과 충돌하고 refusal 보호 family가 있어 그대로 import할 수 없다. 정책을 바꾸려면 별도 버전/재검토가 필요하다. active count/ratio에는 clarification JSON 계약도 없으므로 unsupported를 정답으로 확정하지 않았다.

## 전체 판정 요약

| ID | 추천 | 의미/보류 핵심 |
|---|---|---|
| RB001-01 | accepted | 각 주에서 대상 택시별 운행일수를 산출한 뒤 합계하고, 주별 합계들을 같은 가중치로 평균 낸다. 질문은 값을 묻는다. |
| RB001-02 | accepted | 2026년 1~6월 각각의 소속 지역 동구 법인택시 매출 평균을 구하고, 여섯 월별 평균 중 최댓값을 반환한다. 달 이름을 묻지 않는다. |
| RB001-03 | needs_fix | Grounding JSON의 잘못된 필드는 발견되지 않았다. Reference-only라는 용도/평가 metadata가 문제다. 나래구를 실제 지명으로 몰래 치환하거나 unsupported로 바꾸지 않는다. |
| RB001-04 | needs_fix | 의미 grounding은 그대로 맞다. 현재 TIMS 실행 제약을 grounding 내부 factor로 고칠 수 없다. 지원 경계를 별도 metadata로 보존할지 결정하기 전 corrected grounding을 확정할 수 없다. |
| RB001-05 | needs_fix | 현재 grounding은 질문의 select 의미를 보존한다. answer=value 또는 dimension=sido로 바꾸어 compile을 통과시키는 수정은 금지한다. 질문/지원 라벨 정책 없이 JSON-only correction은 없다. |
| RB001-06 | accepted | 지난달 동구 소속 법인택시의 주별 택시당 운행일수 평균들 중 가장 작은 숫자를 반환한다. 가장 작은 주를 반환하지 않는다. |
| RB001-07 | needs_fix | 기존 JSON의 select 뜻은 맞다. 미확인 range/day 계약은 grounding correction으로 해결할 수 없다. answer=value로 바꾸지 않는다. |
| RB001-08 | accepted | 지난달 달서구 소속 개인택시의 주별 택시당 운행일수 평균들을 구한 뒤 그 주별 평균의 무가중 평균을 구한다. |
| RB001-09 | accepted | 2026-09-10 개인택시의 소속 시도별 매출 평균을 비교해 높은 3개 시도를 반환한다. 명시된 한 장소 filter는 없다. |
| RB001-10 | needs_fix | daily-count mean을 나타내는 표본/분모 factor는 현재 schema에 없다. 임의 bucket=day/dimension=day를 추가할 수 없다. 질문과 provider 정의를 먼저 확정해야 정확한 corrected grounding을 정할 수 있다. |
| RB001-11 | needs_fix | 표본 단위/소속 의미를 정하기 전 JSON-only correction을 확정할 수 없다. private로 바꾸거나 임의 날짜/장소를 추가하지 않는다. |
| RB001-12 | needs_fix | aggregation=med라는 어휘 대응은 맞지만 표본 단위/분모를 표현할 raw factor가 없다. med를 avg로 바꾸거나 vacant_ratio로 치환하는 것은 수정이 아니라 오답이다. |
| RB001-13 | needs_fix | min→avg 매핑은 맞다. 표본 단위가 미정이라 현재 JSON만으로 의미를 확정하는 수정은 없다. day bucket을 만들거나 avg→min으로 바꾸지 않는다. |
| RB001-14 | needs_fix | min→avg 매핑은 맞다. 표본 단위가 미정이라 현재 JSON만으로 의미를 확정하는 수정은 없다. day bucket을 만들거나 avg→min으로 바꾸지 않는다. |
| RB001-15 | needs_fix | avg→min은 정확한 문법 대응이다. 질문/기간 측정 정의가 확정되기 전에는 새로운 corrected grounding을 만들 수 없다. |
| RB001-16 | needs_fix | avg→min은 정확한 문법 대응이다. 질문/기간 측정 정의가 확정되기 전에는 새로운 corrected grounding을 만들 수 없다. |
| RB001-17 | needs_fix | stage 및 subtype은 맞다. get_passage_metrics에 bucket/rollup이 없고 로컬 분해 근거가 미확인이므로 JSON 수정으로 같은 질문의 실행을 확보할 수 없다. 운영 대수/revenue로 바꾸지 않는다. |
| RB001-18 | needs_fix | stage 및 subtype은 맞다. get_passage_metrics에 bucket/rollup이 없고 로컬 분해 근거가 미확인이므로 JSON 수정으로 같은 질문의 실행을 확보할 수 없다. 운영 대수/revenue로 바꾸지 않는다. |
| RB001-19 | needs_fix | avg→max는 질문과 맞다. raw records/count가 없는 하루 평균들로 정확한 주 평균을 복원할 수 없다. factor를 뒤집거나 전체 기간 avg로 축소하지 않는다. |
| RB001-20 | needs_fix | avg→max는 질문과 맞다. raw records/count가 없는 하루 평균들로 정확한 주 평균을 복원할 수 없다. factor를 뒤집거나 전체 기간 avg로 축소하지 않는다. |
| RB001-21 | needs_fix | od_role=pickup, dimension_target=dropoff를 바꿀 이유가 없다. 장소를 다른 곳으로 수정하려면 질문도 바뀌므로 이 queue의 corrected_grounding으로 몰래 치환할 수 없다. |
| RB001-22 | needs_fix | od_role=pickup, dimension_target=dropoff를 바꿀 이유가 없다. 장소를 다른 곳으로 수정하려면 질문도 바뀌므로 이 queue의 corrected_grounding으로 몰래 치환할 수 없다. |
| RB001-23 | needs_fix | od_role=dropoff와 dimension_target=pickup은 맞다. 알 수 없는 장소를 임의의 실제 장소/scope로 바꾸지 않는다. |
| RB001-24 | needs_fix | od_role=dropoff와 dimension_target=pickup은 맞다. 알 수 없는 장소를 임의의 실제 장소/scope로 바꾸지 않는다. |
| RB001-25 | accepted | 모든 대상 trip을 읍면동 승차지별로 묶어 건수가 적은 4개 그룹을 반환한다. 이름을 가진 장소 filter는 없으며 dimension_target=pickup이다. |
| RB001-26 | accepted | 모든 대상 trip을 읍면동 승차지별로 묶어 건수가 적은 4개 그룹을 반환한다. 이름을 가진 장소 filter는 없으며 dimension_target=pickup이다. |
| RB001-27 | accepted | 출발 읍면동과 도착 읍면동의 순서 있는 조합(OD pair)별로 trip을 묶고 건수 하위 4개 조합을 반환한다. LOCATION 이름 filter나 한 장소의 od_role=both가 아니다. |
| RB001-28 | accepted | 출발 읍면동과 도착 읍면동의 순서 있는 조합(OD pair)별로 trip을 묶고 건수 하위 4개 조합을 반환한다. LOCATION 이름 filter나 한 장소의 od_role=both가 아니다. |
| RB001-29 | accepted | 모든 대상 trip을 읍면동 하차지별로 묶어 건수 하위 4개 그룹을 반환한다. 특정 하차 장소 filter는 없으며 dimension_target=dropoff이다. |
| RB001-30 | accepted | 모든 대상 trip을 읍면동 하차지별로 묶어 건수 하위 4개 그룹을 반환한다. 특정 하차 장소 filter는 없으며 dimension_target=dropoff이다. |

## 항목별 semantic review

### RB001-01 — accepted

- Candidate: `ann-d983889cf8c496178106`; 실제 status: pending.
- 질문: 지난달 수성구 개인택시의 주별 운행일수 합계를 평균 내면?
- 의미 판단: 각 주에서 대상 택시별 운행일수를 산출한 뒤 합계하고, 주별 합계들을 같은 가중치로 평균 낸다. 질문은 값을 묻는다.
- 집계/그룹 판단: week: sum → avg; answer=value(생략). 전체 기간 택시별 운행일수 평균으로 바꾸면 다른 질문이다.
- Concept/subtype: AMOUNT/operating_days MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"수성구","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=sum`: 질문의 각 구간 안 집계 또는 단일 집계 표현. week: sum → avg; answer=value(생략). 전체 기간 택시별 운행일수 평균으로 바꾸면 다른 질문이다.
- Factor `bucket=week`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=last_month`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=avg`: 구간별 값의 외부 집계/선택 방향. week: sum → avg; answer=value(생략). 전체 기간 택시별 운행일수 평균으로 바꾸면 다른 질문이다.
- Factor `taxi_type=private`: 질문의 개인택시/법인택시. 둘 다 없으면 factor를 넣지 않는다.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다.
- 수정 필요 판단: 질문에 맞는 현재 grounding을 유지한다. 확정된 JSON field 수정은 없다.
- Corrected grounding: null(수정 불필요; 현재 proposed grounding 유지).
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution PASS (fixture).
- 기존 prediction 대조:
  - Base: gold factor date='last_month'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / 측정에 필요한 EVENT/operation SUPPORT가 없고 기간 조건을 EVENT/COND로 대신한다. / 질문 장소의 user/value filter가 raw 출력에서 누락 또는 불일치한다.
  - DPO: gold factor date='last_month'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / area: 아직 scope가 아닌 place인데 role=COND / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / 측정에 필요한 EVENT/operation SUPPORT가 없고 기간 조건을 EVENT/COND로 대신한다.
  - SFT: gold factor date='last_month'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / 측정에 필요한 EVENT/operation SUPPORT가 없고 기간 조건을 EVENT/COND로 대신한다. / 질문 장소의 user/value filter가 raw 출력에서 누락 또는 불일치한다.
- 사람이 확정할 질문: 주 시작일·부분 주·빈 주 처리를 질문이 정하지 않아 TIMS에 위임하는 corpus 정책을 확인한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:101](/home/hwkim/assistant_univ/geoflow/measures.py:101), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67)

### RB001-02 — accepted

- Candidate: `ann-cc38d74754ba7eab68a8`; 실제 status: pending.
- 질문: 2026년 상반기 동구 법인택시 월별 매출 평균 중 가장 큰 값은?
- 의미 판단: 2026년 1~6월 각각의 소속 지역 동구 법인택시 매출 평균을 구하고, 여섯 월별 평균 중 최댓값을 반환한다. 달 이름을 묻지 않는다.
- 집계/그룹 판단: month: avg → max; answer=value(생략).
- Concept/subtype: AMOUNT/revenue MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"동구","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=avg`: 질문의 각 구간 안 집계 또는 단일 집계 표현. month: avg → max; answer=value(생략).
- Factor `bucket=month`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=20260101-20260630`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=max`: 구간별 값의 외부 집계/선택 방향. month: avg → max; answer=value(생략).
- Factor `taxi_type=corporate`: 질문의 개인택시/법인택시. 둘 다 없으면 factor를 넣지 않는다.
- Ambiguity: 동구만으로 상위 시도는 정해지지 않는다. 현재 mock은 대구 동구를 반환하지만 질문에 대구는 없다. region=""는 올바른 원문 보존이며 대구를 추정해 넣으면 안 된다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다.
- 수정 필요 판단: 질문에 맞는 현재 grounding을 유지한다. 확정된 JSON field 수정은 없다.
- Corrected grounding: null(수정 불필요; 현재 proposed grounding 유지).
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution PASS (fixture).
- 기존 prediction 대조:
  - Base: gold factor date='20260101-20260630'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='corporate'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date_range: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / location: 아직 scope가 아닌 place인데 role=COND / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / 측정에 필요한 EVENT/operation SUPPORT가 없고 기간 조건을 EVENT/COND로 대신한다.
  - DPO: gold factor date='20260101-20260630'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='corporate'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date_range: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / location: 아직 scope가 아닌 place인데 role=COND / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / 측정에 필요한 EVENT/operation SUPPORT가 없고 기간 조건을 EVENT/COND로 대신한다.
  - SFT: gold factor date='20260101-20260630'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='corporate'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date_range: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / location: 아직 scope가 아닌 place인데 role=COND / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / 측정에 필요한 EVENT/operation SUPPORT가 없고 기간 조건을 EVENT/COND로 대신한다.
- 사람이 확정할 질문: 질문의 동구가 어느 도시인지와 질문 밖 context가 허용되는지 확인한다. 지역의 통행 기록이 아니라 택시 소속 지역별 영업 통계다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:71](/home/hwkim/assistant_univ/geoflow/measures.py:71), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67)

### RB001-03 — needs_fix

- Candidate: `ann-da98b3941dfa1c7ce800`; 실제 status: pending.
- 질문: 2026년 8월 나래구 개인택시 주별 매출 합계 중 가장 작은 값은?
- 의미 판단: 2026년 8월 나래구 소속 개인택시의 각 주 매출 합계 중 가장 작은 금액을 묻는다. 현재 grounding의 sum→min이 원문과 맞다.
- 집계/그룹 판단: week: sum → min; answer=value(생략).
- Concept/subtype: AMOUNT/revenue MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"나래구","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=sum`: 질문의 각 구간 안 집계 또는 단일 집계 표현. week: sum → min; answer=value(생략).
- Factor `bucket=week`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=20260801-20260831`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=min`: 구간별 값의 외부 집계/선택 방향. week: sum → min; answer=value(생략).
- Factor `taxi_type=private`: 질문의 개인택시/법인택시. 둘 다 없으면 factor를 넣지 않는다.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / 현재 mock get_place_scope는 NOT_FOUND. 이는 실제 TIMS 장소 존재 여부의 판정이 아니며 LLM이 없는 장소를 hallucinate했다는 뜻도 아니다. 질문 자체의 합성 장소 context를 정해야 한다. / 원본 ex05의 reference.provider=reference, reference 결과 30000은 CPU 재실행과 일치했다. TIMS와 다른 합성 계약이므로 기본 mock 실행 PASS로 합치지 않는다.
- 수정 필요 판단: Grounding JSON의 잘못된 필드는 발견되지 않았다. Reference-only라는 용도/평가 metadata가 문제다. 나래구를 실제 지명으로 몰래 치환하거나 unsupported로 바꾸지 않는다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution FAIL NOT_FOUND.
- Reference 합성 실행 결과: `30000` (실제 TIMS 결과 아님).
- 기존 prediction 대조:
  - Base: gold factor date='20260801-20260831'와 raw model factor '202608'를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / 질문 장소의 user/value filter가 raw 출력에서 누락 또는 불일치한다.
  - DPO: gold factor date='20260801-20260831'와 raw model factor '202608'를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / 질문 장소의 user/value filter가 raw 출력에서 누락 또는 불일치한다.
  - SFT: gold factor date='20260801-20260831'와 raw model factor '202608'를 재대조; concept에 중복 배치한 값은 별도 확인 / 질문 장소의 user/value filter가 raw 출력에서 누락 또는 불일치한다.
- 사람이 확정할 질문: 원본 ex05는 명시적으로 reference provider의 합성 gold이다. 이번 corpus가 provider-independent grounding gold를 허용할지, 기본 TIMS에서 실행되는 answered gold만 허용할지 사람이 확정해야 한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:71](/home/hwkim/assistant_univ/geoflow/measures.py:71), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [reference_provider.py:4](/home/hwkim/assistant_univ/reference_provider.py:4)

### RB001-04 — needs_fix (상세 검토)

- Candidate: `ann-77e9dacb0b34a3273630`; 실제 status: pending.
- 질문: 2026년 8월 나래구 개인택시 매출 평균이 가장 낮았던 주는 언제야?
- 의미 판단: 매출 평균이 가장 낮은 주의 구간 식별자를 묻는다. 주 안 평균(avg), 주 간 최소 구간 선택(select=min)이다. rollup=min + answer=bucket은 flat 표현의 정확한 select 대응이다.
- 집계/그룹 판단: week: inner=avg → select=min; answer=bucket. rollup=min을 숫자 최솟값 반환으로 읽으면 오답이다.
- Concept/subtype: AMOUNT/revenue MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"나래구","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=avg`: 질문의 각 구간 안 집계 또는 단일 집계 표현. week: inner=avg → select=min; answer=bucket. rollup=min을 숫자 최솟값 반환으로 읽으면 오답이다.
- Factor `answer=bucket`: 질문이 해당 주/달 자체를 묻는다. value로 바꾸면 다른 질문이다.
- Factor `bucket=week`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=20260801-20260831`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=min`: 구간별 값의 외부 집계/선택 방향. week: inner=avg → select=min; answer=bucket. rollup=min을 숫자 최솟값 반환으로 읽으면 오답이다.
- Factor `taxi_type=private`: 질문의 개인택시/법인택시. 둘 다 없으면 factor를 넣지 않는다.
- Ambiguity: 해당 최솟값의 동률, 주 시작·부분 주·빈 주 규칙은 원문에 없다. TIMS는 구간 선택 경로를 제공하지 않아 현재 계약으로 이 기본값을 보장할 수 없다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / TIMS/mock legacy compiler: UNVERIFIED_TIMS_CONTRACT. Schema raw grounding은 표현되지만 계약상 정확한 실행 lowering이 없다. / 원본 ex07의 reference provider는 CPU 실행에서 20260831-20260831 구간을 선택했다(value=30000). 이 합성 결과가 TIMS 구간 선택 지원을 입증하지 않는다.
- 수정 필요 판단: 의미 grounding은 그대로 맞다. 현재 TIMS 실행 제약을 grounding 내부 factor로 고칠 수 없다. 지원 경계를 별도 metadata로 보존할지 결정하기 전 corrected grounding을 확정할 수 없다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile FAIL `UNVERIFIED_TIMS_CONTRACT` — measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_billing_metrics
- Reference 합성 실행 결과: `{"groups":[{"complete":false,"end":"20260831","label":"20260831-20260831","start":"20260831","unit":"week"}],"select":"min","value":30000.0}` (실제 TIMS 결과 아님).
- 기존 prediction 대조:
  - Base: gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / location_1: 아직 scope가 아닌 place인데 role=COND
  - DPO: gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / location_1: 아직 scope가 아닌 place인데 role=COND
  - SFT: gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / location: 아직 scope가 아닌 place인데 role=COND
- 사람이 확정할 질문: 원본 ex07는 reference 합성 예시다. Reference-local selected_groups gold와 TIMS answered label을 혼용할지 결정한다. 반환 목표를 value로 바꾸면 원래 질문을 바꾸는 것이다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:71](/home/hwkim/assistant_univ/geoflow/measures.py:71), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [reference_provider.py:4](/home/hwkim/assistant_univ/reference_provider.py:4)

검토 대상 grounding (수정본이 아니라 원문을 보존한 제안):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "revenue"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "나래구",
      "value": {
        "name": "나래구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "answer": "bucket",
    "bucket": "week",
    "date": "20260801-20260831",
    "rollup": "min",
    "taxi_type": "private"
  }
}
```

### RB001-05 — needs_fix (상세 검토)

- Candidate: `ann-9d8392a4f8ca9ff8cfc2`; 실제 status: pending.
- 질문: 2026년 상반기 중구 개인택시 운행일수 합계가 가장 많았던 달은?
- 의미 판단: 2026년 상반기 각 월의 중구 소속 개인택시 운행일수 합계를 비교해 합계가 가장 큰 달을 고른다. 운행일수는 각 택시의 해당 기간 운행일수를 먼저 센 다음 택시 전체에 sum을 적용한다.
- 집계/그룹 판단: month: inner=sum → select=max; answer=bucket. dimension=month/order=top/limit=1은 지원 어휘에도 없고 시간 구간 선택의 대체도 아니다.
- Concept/subtype: AMOUNT/operating_days MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"중구","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=sum`: 질문의 각 구간 안 집계 또는 단일 집계 표현. month: inner=sum → select=max; answer=bucket. dimension=month/order=top/limit=1은 지원 어휘에도 없고 시간 구간 선택의 대체도 아니다.
- Factor `answer=bucket`: 질문이 해당 주/달 자체를 묻는다. value로 바꾸면 다른 질문이다.
- Factor `bucket=month`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=20260101-20260630`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=max`: 구간별 값의 외부 집계/선택 방향. month: inner=sum → select=max; answer=bucket. dimension=month/order=top/limit=1은 지원 어휘에도 없고 시간 구간 선택의 대체도 아니다.
- Factor `taxi_type=private`: 질문의 개인택시/법인택시. 둘 다 없으면 factor를 넣지 않는다.
- Ambiguity: 중구의 상위 시도가 주어지지 않았다. mock의 대구 중구 mapping은 질문의 증거가 아니다. 동률일 때 단일 달/여러 달 중 어떤 출력을 원하는지도 지정되지 않았다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / TIMS/mock legacy compiler: UNVERIFIED_TIMS_CONTRACT. Schema raw grounding은 표현되지만 계약상 정확한 실행 lowering이 없다.
- 수정 필요 판단: 현재 grounding은 질문의 select 의미를 보존한다. answer=value 또는 dimension=sido로 바꾸어 compile을 통과시키는 수정은 금지한다. 질문/지원 라벨 정책 없이 JSON-only correction은 없다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile FAIL `UNVERIFIED_TIMS_CONTRACT` — measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_billing_metrics
- 기존 prediction 대조:
  - Base: gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / location: 아직 scope가 아닌 place인데 role=COND
  - DPO: gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / location: 아직 scope가 아닌 place인데 role=COND
  - SFT: gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / location: 아직 scope가 아닌 place인데 role=COND / dimension=month는 허용된 dimension이 아니며 bucket 선택을 region ranking으로 바꿀 수 없다.
- 사람이 확정할 질문: 월 이름을 반환하려는 의도와 provider-specific 지원 라벨을 확인한다. 지역을 확정하더라도 선택 lowering의 미확인 계약 문제는 남는다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:101](/home/hwkim/assistant_univ/geoflow/measures.py:101), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67)

검토 대상 grounding (수정본이 아니라 원문을 보존한 제안):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "operating_days"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "중구",
      "value": {
        "name": "중구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "sum",
    "answer": "bucket",
    "bucket": "month",
    "date": "20260101-20260630",
    "rollup": "max",
    "taxi_type": "private"
  }
}
```

### RB001-06 — accepted

- Candidate: `ann-89f3d036b2d43dd431f0`; 실제 status: pending.
- 질문: 지난달 동구 법인택시 주별 운행일수 평균 중 가장 작은 값은?
- 의미 판단: 지난달 동구 소속 법인택시의 주별 택시당 운행일수 평균들 중 가장 작은 숫자를 반환한다. 가장 작은 주를 반환하지 않는다.
- 집계/그룹 판단: week: avg → min; answer=value(생략).
- Concept/subtype: AMOUNT/operating_days MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"동구","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=avg`: 질문의 각 구간 안 집계 또는 단일 집계 표현. week: avg → min; answer=value(생략).
- Factor `bucket=week`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=last_month`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=min`: 구간별 값의 외부 집계/선택 방향. week: avg → min; answer=value(생략).
- Factor `taxi_type=corporate`: 질문의 개인택시/법인택시. 둘 다 없으면 factor를 넣지 않는다.
- Ambiguity: 동구 상위 시도가 없다. region=""를 유지하며 실제 조회의 지역 모호성은 별도 확인해야 한다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다.
- 수정 필요 판단: 질문에 맞는 현재 grounding을 유지한다. 확정된 JSON field 수정은 없다.
- Corrected grounding: null(수정 불필요; 현재 proposed grounding 유지).
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution PASS (fixture).
- 기존 prediction 대조:
  - Base: gold factor date='last_month'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='corporate'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / 측정에 필요한 EVENT/operation SUPPORT가 없고 기간 조건을 EVENT/COND로 대신한다.
  - DPO: gold factor date='last_month'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='corporate'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / 측정에 필요한 EVENT/operation SUPPORT가 없고 기간 조건을 EVENT/COND로 대신한다.
  - SFT: gold factor date='last_month'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='corporate'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / 측정에 필요한 EVENT/operation SUPPORT가 없고 기간 조건을 EVENT/COND로 대신한다.
- 사람이 확정할 질문: RB001-07과 값/구간 선택의 차이를 확인한다. 운영일수 평균의 택시 모집단·빈 주 처리는 제공자에 위임된 범위다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:101](/home/hwkim/assistant_univ/geoflow/measures.py:101), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67)

### RB001-07 — needs_fix (상세 검토)

- Candidate: `ann-aa1d7fd59c1d3d2ea97b`; 실제 status: pending.
- 질문: 지난달 동구 법인택시의 운행일수 평균이 가장 적었던 주는?
- 의미 판단: 지난달 동구 소속 법인택시의 각 주 택시당 운행일수 평균을 구하고 그 평균이 가장 작은 주를 선택한다. RB001-06의 숫자 답과 다르다.
- 집계/그룹 판단: week: inner=avg → select=min; answer=bucket.
- Concept/subtype: AMOUNT/operating_days MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"동구","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=avg`: 질문의 각 구간 안 집계 또는 단일 집계 표현. week: inner=avg → select=min; answer=bucket.
- Factor `answer=bucket`: 질문이 해당 주/달 자체를 묻는다. value로 바꾸면 다른 질문이다.
- Factor `bucket=week`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=last_month`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=min`: 구간별 값의 외부 집계/선택 방향. week: inner=avg → select=min; answer=bucket.
- Factor `taxi_type=corporate`: 질문의 개인택시/법인택시. 둘 다 없으면 factor를 넣지 않는다.
- Ambiguity: 동구의 상위 시도가 없다. 최저 주 동률·빈 주 처리와 상대 지난달 기준 시각은 질문에 명시되지 않았다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / TIMS/mock legacy compiler: UNVERIFIED_TIMS_CONTRACT. Schema raw grounding은 표현되지만 계약상 정확한 실행 lowering이 없다.
- 수정 필요 판단: 기존 JSON의 select 뜻은 맞다. 미확인 range/day 계약은 grounding correction으로 해결할 수 없다. answer=value로 바꾸지 않는다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile FAIL `UNVERIFIED_TIMS_CONTRACT` — measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_billing_metrics
- 기존 prediction 대조:
  - Base: gold factor date='last_month'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='corporate'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date_range: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다
  - DPO: gold factor date='last_month'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='corporate'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date_range: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다
  - SFT: gold factor date='last_month'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='corporate'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date_range: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다
- 사람이 확정할 질문: 현재 TIMS에서 selected bucket이 지원되지 않는 점과 숫자 값 반환을 구분한다. Source/role만 바로잡은 model output도 같은 compiler 제약을 갖는다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:101](/home/hwkim/assistant_univ/geoflow/measures.py:101), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67)

검토 대상 grounding (수정본이 아니라 원문을 보존한 제안):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "operating_days"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "동구",
      "value": {
        "name": "동구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "answer": "bucket",
    "bucket": "week",
    "date": "last_month",
    "rollup": "min",
    "taxi_type": "corporate"
  }
}
```

### RB001-08 — accepted

- Candidate: `ann-f8d44f2cfa96200b5a95`; 실제 status: pending.
- 질문: 지난달 달서구 개인택시 주별 운행일수 평균들의 평균은?
- 의미 판단: 지난달 달서구 소속 개인택시의 주별 택시당 운행일수 평균들을 구한 뒤 그 주별 평균의 무가중 평균을 구한다.
- 집계/그룹 판단: week: avg → avg; 각 주에 한 표. 전체 기간의 단일 평균이나 날 수/택시 수 가중 평균과 동일하다고 가정하지 않는다.
- Concept/subtype: AMOUNT/operating_days MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"달서구","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=avg`: 질문의 각 구간 안 집계 또는 단일 집계 표현. week: avg → avg; 각 주에 한 표. 전체 기간의 단일 평균이나 날 수/택시 수 가중 평균과 동일하다고 가정하지 않는다.
- Factor `bucket=week`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=last_month`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=avg`: 구간별 값의 외부 집계/선택 방향. week: avg → avg; 각 주에 한 표. 전체 기간의 단일 평균이나 날 수/택시 수 가중 평균과 동일하다고 가정하지 않는다.
- Factor `taxi_type=private`: 질문의 개인택시/법인택시. 둘 다 없으면 factor를 넣지 않는다.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다.
- 수정 필요 판단: 질문에 맞는 현재 grounding을 유지한다. 확정된 JSON field 수정은 없다.
- Corrected grounding: null(수정 불필요; 현재 proposed grounding 유지).
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution PASS (fixture).
- 기존 prediction 대조:
  - Base: gold factor date='last_month'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / location: 아직 scope가 아닌 place인데 role=COND / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / 측정에 필요한 EVENT/operation SUPPORT가 없고 기간 조건을 EVENT/COND로 대신한다.
  - DPO: gold factor date='last_month'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / location: 아직 scope가 아닌 place인데 role=COND / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / 측정에 필요한 EVENT/operation SUPPORT가 없고 기간 조건을 EVENT/COND로 대신한다.
  - SFT: gold factor date='last_month'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / gold factor taxi_type='private'와 raw model factor None를 재대조; concept에 중복 배치한 값은 별도 확인 / date: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / location: 아직 scope가 아닌 place인데 role=COND / taxi_type: user이지만 value가 없으며 날짜/택시 유형을 concept로 잘못 넣었을 수 있다 / 측정에 필요한 EVENT/operation SUPPORT가 없고 기간 조건을 EVENT/COND로 대신한다.
- 사람이 확정할 질문: 평균들의 평균이라는 원문을 유지하고 provider의 주 경계/빈 주 정의를 확인한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:101](/home/hwkim/assistant_univ/geoflow/measures.py:101), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67)

### RB001-09 — accepted

- Candidate: `ann-f78087861d0826ae8a7f`; 실제 status: pending.
- 질문: 2026년 9월 10일 개인택시 매출 평균이 높은 시도 3곳은?
- 의미 판단: 2026-09-10 개인택시의 소속 시도별 매출 평균을 비교해 높은 3개 시도를 반환한다. 명시된 한 장소 filter는 없다.
- 집계/그룹 판단: bucket/rollup 없음. 그룹별 avg 후 dimension=sido, order=top, limit=3.
- Concept/subtype: AMOUNT/revenue MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: 명명 장소 filter 없음. 시도/읍면동은 dimension이고 LOCATION/place를 만들지 않는다.
- Factor `aggregation=avg`: 질문의 각 구간 안 집계 또는 단일 집계 표현. bucket/rollup 없음. 그룹별 avg 후 dimension=sido, order=top, limit=3.
- Factor `date=20260910`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `dimension=sido`: 원문 시도별/읍면동별 group 단위; 이름을 가진 place value가 아니다.
- Factor `limit=3`: 원문 3곳/4곳/4개에 대응.
- Factor `order=top`: 많은/높은=top, 적은=bottom의 원문 방향.
- Factor `taxi_type=private`: 질문의 개인택시/법인택시. 둘 다 없으면 factor를 넣지 않는다.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다.
- 수정 필요 판단: 질문에 맞는 현재 grounding을 유지한다. 확정된 JSON field 수정은 없다.
- Corrected grounding: null(수정 불필요; 현재 proposed grounding 유지).
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution PASS (fixture).
- 기존 prediction 대조:
  - Base: 모델은 raw OBJECT/taxi_type condition concept을 출력하지만 production normalization에서 factors로 이동되어 기존 grounding exact는 True였다. Canonical target에 legacy condition concept을 채택하지 않는다.
  - DPO: 모델은 raw OBJECT/taxi_type condition concept을 출력하지만 production normalization에서 factors로 이동되어 기존 grounding exact는 True였다. Canonical target에 legacy condition concept을 채택하지 않는다.
  - SFT: 모델은 raw OBJECT/taxi_type condition concept을 출력하지만 production normalization에서 factors로 이동되어 기존 grounding exact는 True였다. Canonical target에 legacy condition concept을 채택하지 않는다.
- 사람이 확정할 질문: 시도별은 value를 가진 LOCATION/place가 아니라 dimension이다. 동률 정렬의 구체 정책과 mock 숫자는 실제 품질의 근거가 아니다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:71](/home/hwkim/assistant_univ/geoflow/measures.py:71)

### RB001-10 — needs_fix (상세 검토)

- Candidate: `ann-09781f452047f59303e6`; 실제 status: pending.
- 질문: 2026년 9월 솔빛동 주변 개인택시의 평균 가동 택시 대수는?
- 의미 판단: 평균 가동 택시 대수는 AMOUNT/active_taxi_count이고 EVENT/operation에 속한다. 개인은 taxi_type=private, 주변은 vicinity=true이다. 장소는 소속 지역 filter로만 사용된다.
- 집계/그룹 판단: bucket 없이 aggregation=avg. 일별 고유 활성 대수의 월 평균인지, 기간 고유 대수의 다른 통계인지 확정되지 않는다.
- Concept/subtype: AMOUNT/active_taxi_count MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"솔빛동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=avg`: 질문의 각 구간 안 집계 또는 단일 집계 표현. bucket 없이 aggregation=avg. 일별 고유 활성 대수의 월 평균인지, 기간 고유 대수의 다른 통계인지 확정되지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `taxi_type=private`: 질문의 개인택시/법인택시. 둘 다 없으면 factor를 넣지 않는다.
- Factor `vicinity=True`: 원문 주변에 대응; true는 place scope 변환의 include_vicinity로만 쓰인다.
- Ambiguity: 기간 평균의 표본 단위가 정의되지 않았다. 전체 등록 택시 대비 수가 아니라 고유 활성 대수이므로 sum은 대체할 수 없다. / 솔빛동 주변에서 운행한 택시를 뜻하는지, 그 주변에 소속된 택시를 뜻하는지 원문이 확정하지 않는다. get_billing_metrics scope는 후자다. / 명명 장소의 실제/합성 provider context가 제공되지 않았으며 현재 mock 사전에 없다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / active count/ratio의 기간 표본 단위·분모는 미정이다. Native billing delegation이 compile된다는 사실로 이 정의가 확정되지 않는다. 합계로 바꾸는 것은 금지한다. / 현재 mock get_place_scope는 NOT_FOUND. 이는 실제 TIMS 장소 존재 여부의 판정이 아니며 LLM이 없는 장소를 hallucinate했다는 뜻도 아니다. 질문 자체의 합성 장소 context를 정해야 한다.
- 수정 필요 판단: daily-count mean을 나타내는 표본/분모 factor는 현재 schema에 없다. 임의 bucket=day/dimension=day를 추가할 수 없다. 질문과 provider 정의를 먼저 확정해야 정확한 corrected grounding을 정할 수 있다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution FAIL NOT_FOUND.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: 일별 활성 대수의 평균인가? 일별 무영업일/결측일은 포함하는가? 소속 기준인지 통행 위치 기준인지? 솔빛동의 실제/합성 provider context는 무엇인가? / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:90](/home/hwkim/assistant_univ/geoflow/measures.py:90), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30)

검토 대상 grounding (수정본이 아니라 원문을 보존한 제안):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "active_taxi_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "date": "20260901-20260930",
    "taxi_type": "private",
    "vicinity": true
  }
}
```

### RB001-11 — needs_fix

- Candidate: `ann-6c2bd47856a19597967e`; 실제 status: pending.
- 질문: 2026년 9월 솔빛동 주변 법인택시의 평균 가동 택시 대수는?
- 의미 판단: RB001-10과 동일한 활성 대수 질문이며 명시된 법인택시만 taxi_type=corporate로 달라진다. 개인택시를 유지하면 factor 오류다.
- 집계/그룹 판단: bucket 없이 aggregation=avg; 기간 표본 단위 미확정.
- Concept/subtype: AMOUNT/active_taxi_count MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"솔빛동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=avg`: 질문의 각 구간 안 집계 또는 단일 집계 표현. bucket 없이 aggregation=avg; 기간 표본 단위 미확정.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `taxi_type=corporate`: 질문의 개인택시/법인택시. 둘 다 없으면 factor를 넣지 않는다.
- Factor `vicinity=True`: 원문 주변에 대응; true는 place scope 변환의 include_vicinity로만 쓰인다.
- Ambiguity: 일별 고유 활성 대수 평균인지 기간 고유 대수인지 정의가 없다. / 주변의 운행 위치와 소속 지역을 혼동할 수 있다. / 명명 장소의 실제/합성 provider context가 제공되지 않았으며 현재 mock 사전에 없다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / active count/ratio의 기간 표본 단위·분모는 미정이다. Native billing delegation이 compile된다는 사실로 이 정의가 확정되지 않는다. 합계로 바꾸는 것은 금지한다. / 현재 mock get_place_scope는 NOT_FOUND. 이는 실제 TIMS 장소 존재 여부의 판정이 아니며 LLM이 없는 장소를 hallucinate했다는 뜻도 아니다. 질문 자체의 합성 장소 context를 정해야 한다.
- 수정 필요 판단: 표본 단위/소속 의미를 정하기 전 JSON-only correction을 확정할 수 없다. private로 바꾸거나 임의 날짜/장소를 추가하지 않는다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution FAIL NOT_FOUND.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: RB001-10의 정의를 공동 확정하되 taxi_type contrast를 보존한다. 솔빛동 provider context를 확인한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:90](/home/hwkim/assistant_univ/geoflow/measures.py:90), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30)

### RB001-12 — needs_fix (상세 검토)

- Candidate: `ann-baaeabe98162ddefb291`; 실제 status: pending.
- 질문: 2026년 9월 해솔동 개인택시 가동률의 중앙값은?
- 의미 판단: 가동률은 PROPORTION/active_taxi_ratio = 활성택시/등록된 전체 택시이고 EVENT/operation이다. 공차율(vacant_ratio)이나 taxi별 운행 여부의 중앙값이 아니다.
- 집계/그룹 판단: bucket 없이 aggregation=med. 어느 관측의 비율들을 모아 중앙값을 내는지 원문/계약에 없다.
- Concept/subtype: PROPORTION/active_taxi_ratio MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"해솔동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=med`: 질문의 각 구간 안 집계 또는 단일 집계 표현. bucket 없이 aggregation=med. 어느 관측의 비율들을 모아 중앙값을 내는지 원문/계약에 없다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `taxi_type=private`: 질문의 개인택시/법인택시. 둘 다 없으면 factor를 넣지 않는다.
- Ambiguity: 일별 집단 비율의 월 중앙값인지, taxi별 비율인지 정해지지 않았다. 분모가 소속 지역·private 등록 택시에 맞춰지는지, 날짜마다 변하는지도 정의가 없다. / 명명 장소의 실제/합성 provider context가 제공되지 않았으며 현재 mock 사전에 없다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / active count/ratio의 기간 표본 단위·분모는 미정이다. Native billing delegation이 compile된다는 사실로 이 정의가 확정되지 않는다. 합계로 바꾸는 것은 금지한다. / 현재 mock get_place_scope는 NOT_FOUND. 이는 실제 TIMS 장소 존재 여부의 판정이 아니며 LLM이 없는 장소를 hallucinate했다는 뜻도 아니다. 질문 자체의 합성 장소 context를 정해야 한다.
- 수정 필요 판단: aggregation=med라는 어휘 대응은 맞지만 표본 단위/분모를 표현할 raw factor가 없다. med를 avg로 바꾸거나 vacant_ratio로 치환하는 것은 수정이 아니라 오답이다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution FAIL NOT_FOUND.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: median of daily active/registered ratios를 의도하는가? 날짜별 0/결측 처리는 무엇인가? private와 해솔동 scope가 분모에도 적용되는가? / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:94](/home/hwkim/assistant_univ/geoflow/measures.py:94), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30)

검토 대상 grounding (수정본이 아니라 원문을 보존한 제안):

```json
{
  "concepts": [
    {
      "concept": "EVENT",
      "id": "c1",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c2",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "해솔동",
      "value": {
        "name": "해솔동",
        "region": ""
      }
    },
    {
      "concept": "PROPORTION",
      "id": "c3",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "active_taxi_ratio"
    }
  ],
  "factors": {
    "aggregation": "med",
    "date": "20260901-20260930",
    "taxi_type": "private"
  }
}
```

### RB001-13 — needs_fix (상세 검토)

- Candidate: `ann-8e3ffbfb226687ea91f7`; 실제 status: pending.
- 질문: 2026년 8월과 9월 온유동의 월별 가동 택시 대수 최솟값의 평균은?
- 의미 판단: 8월과 9월을 각각 구간으로 나누고 각 월 안에서 가동 대수 최솟값을 구한 뒤 그 두 월 최솟값의 평균을 낸다는 stage 문법이다.
- 집계/그룹 판단: month: min → avg. 일별 활성 대수라는 해석을 전제할 때만 월 내 최소의 표본이 정해진다.
- Concept/subtype: AMOUNT/active_taxi_count MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"온유동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=min`: 질문의 각 구간 안 집계 또는 단일 집계 표현. month: min → avg. 일별 활성 대수라는 해석을 전제할 때만 월 내 최소의 표본이 정해진다.
- Factor `bucket=month`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=20260801-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=avg`: 구간별 값의 외부 집계/선택 방향. month: min → avg. 일별 활성 대수라는 해석을 전제할 때만 월 내 최소의 표본이 정해진다.
- Ambiguity: active_taxi_count는 하루 고유 대수만 정의한다. 질문이 일별 값의 월별 최소라는 뜻인지, 월별 고유 대수라는 뜻인지 명시하지 않는다. 월 최소/평균의 통계 단위가 미정이다. / 명명 장소의 실제/합성 provider context가 제공되지 않았으며 현재 mock 사전에 없다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / active count/ratio의 기간 표본 단위·분모는 미정이다. Native billing delegation이 compile된다는 사실로 이 정의가 확정되지 않는다. 합계로 바꾸는 것은 금지한다. / 현재 mock get_place_scope는 NOT_FOUND. 이는 실제 TIMS 장소 존재 여부의 판정이 아니며 LLM이 없는 장소를 hallucinate했다는 뜻도 아니다. 질문 자체의 합성 장소 context를 정해야 한다.
- 수정 필요 판단: min→avg 매핑은 맞다. 표본 단위가 미정이라 현재 JSON만으로 의미를 확정하는 수정은 없다. day bucket을 만들거나 avg→min으로 바꾸지 않는다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution FAIL NOT_FOUND.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: 일별 활성 대수 → 월별 최소 → 두 달 평균이라는 의도와 소속 기준을 먼저 확정한다. 계약이 통계 단위를 보장하는지 확인한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:90](/home/hwkim/assistant_univ/geoflow/measures.py:90), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30)

검토 대상 grounding (수정본이 아니라 원문을 보존한 제안):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "active_taxi_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "온유동",
      "value": {
        "name": "온유동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "min",
    "bucket": "month",
    "date": "20260801-20260930",
    "rollup": "avg"
  }
}
```

### RB001-14 — needs_fix

- Candidate: `ann-3e7a8b41ae12f1f07b6a`; 실제 status: pending.
- 질문: 2026년 8월과 9월 온유동의 월별 가동 택시 대수 최솟값의 평균은?
- 의미 판단: 8월과 9월을 각각 구간으로 나누고 각 월 안에서 가동 대수 최솟값을 구한 뒤 그 두 월 최솟값의 평균을 낸다는 stage 문법이다.
- 집계/그룹 판단: month: min → avg. 일별 활성 대수라는 해석을 전제할 때만 월 내 최소의 표본이 정해진다.
- Concept/subtype: AMOUNT/active_taxi_count MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"온유동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=min`: 질문의 각 구간 안 집계 또는 단일 집계 표현. month: min → avg. 일별 활성 대수라는 해석을 전제할 때만 월 내 최소의 표본이 정해진다.
- Factor `bucket=month`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=20260801-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=avg`: 구간별 값의 외부 집계/선택 방향. month: min → avg. 일별 활성 대수라는 해석을 전제할 때만 월 내 최소의 표본이 정해진다.
- Ambiguity: active_taxi_count는 하루 고유 대수만 정의한다. 질문이 일별 값의 월별 최소라는 뜻인지, 월별 고유 대수라는 뜻인지 명시하지 않는다. 월 최소/평균의 통계 단위가 미정이다. / 명명 장소의 실제/합성 provider context가 제공되지 않았으며 현재 mock 사전에 없다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / active count/ratio의 기간 표본 단위·분모는 미정이다. Native billing delegation이 compile된다는 사실로 이 정의가 확정되지 않는다. 합계로 바꾸는 것은 금지한다. / 현재 mock get_place_scope는 NOT_FOUND. 이는 실제 TIMS 장소 존재 여부의 판정이 아니며 LLM이 없는 장소를 hallucinate했다는 뜻도 아니다. 질문 자체의 합성 장소 context를 정해야 한다.
- 수정 필요 판단: min→avg 매핑은 맞다. 표본 단위가 미정이라 현재 JSON만으로 의미를 확정하는 수정은 없다. day bucket을 만들거나 avg→min으로 바꾸지 않는다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution FAIL NOT_FOUND.
- Pair chosen: aggregation=min, rollup=avg
- Pair rejected: aggregation=avg, rollup=min
- Rejected 의미가 다른 이유: 월 최소들의 평균을 월 평균들의 최소로 바꾼다. 일별 활성 대수라는 정의를 확정한 뒤에만 pair의 의미 선호를 최종 승인할 수 있다.
- 일별 활성 대수를 가정한 설명용 값: 8월 [2,8], 9월 [4,10]. avg(monthly min)=3, min(monthly avg)=5. 실제 provider 출력/검증 데이터가 아니다.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: 일별 활성 대수 → 월별 최소 → 두 달 평균이라는 의도와 소속 기준을 먼저 확정한다. 계약이 통계 단위를 보장하는지 확인한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:90](/home/hwkim/assistant_univ/geoflow/measures.py:90), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30)

비교 rejected grounding (이 record 자체를 rejected로 판정했다는 뜻이 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "active_taxi_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "온유동",
      "value": {
        "name": "온유동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "month",
    "date": "20260801-20260930",
    "rollup": "min"
  }
}
```

### RB001-15 — needs_fix

- Candidate: `ann-27dea2872a7d3a693dd3`; 실제 status: pending.
- 질문: 2026년 8월과 9월 온유동의 월별 평균 가동 택시 대수 중 최솟값은?
- 의미 판단: 각 월의 가동 대수 평균을 구한 뒤 두 월 평균 중 최솟값을 반환한다. 각 월 최소들의 평균이 아니다.
- 집계/그룹 판단: month: avg → min. answer=value(생략).
- Concept/subtype: AMOUNT/active_taxi_count MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"온유동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=avg`: 질문의 각 구간 안 집계 또는 단일 집계 표현. month: avg → min. answer=value(생략).
- Factor `bucket=month`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=20260801-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=min`: 구간별 값의 외부 집계/선택 방향. month: avg → min. answer=value(생략).
- Ambiguity: 각 월 평균의 표본이 일별 고유 활성 대수인지 정해지지 않았다. 날짜별 빈 값/모집단 처리도 계약에 없다. / 명명 장소의 실제/합성 provider context가 제공되지 않았으며 현재 mock 사전에 없다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / active count/ratio의 기간 표본 단위·분모는 미정이다. Native billing delegation이 compile된다는 사실로 이 정의가 확정되지 않는다. 합계로 바꾸는 것은 금지한다. / 현재 mock get_place_scope는 NOT_FOUND. 이는 실제 TIMS 장소 존재 여부의 판정이 아니며 LLM이 없는 장소를 hallucinate했다는 뜻도 아니다. 질문 자체의 합성 장소 context를 정해야 한다.
- 수정 필요 판단: avg→min은 정확한 문법 대응이다. 질문/기간 측정 정의가 확정되기 전에는 새로운 corrected grounding을 만들 수 없다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution FAIL NOT_FOUND.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: RB001-13과 stage 방향을 별도로 확인하고 일별 집단 대수라는 정의를 확정한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:90](/home/hwkim/assistant_univ/geoflow/measures.py:90), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30)

### RB001-16 — needs_fix

- Candidate: `ann-7fd10e4e8f2aafdd01e5`; 실제 status: pending.
- 질문: 2026년 8월과 9월 온유동의 월별 평균 가동 택시 대수 중 최솟값은?
- 의미 판단: 각 월의 가동 대수 평균을 구한 뒤 두 월 평균 중 최솟값을 반환한다. 각 월 최소들의 평균이 아니다.
- 집계/그룹 판단: month: avg → min. answer=value(생략).
- Concept/subtype: AMOUNT/active_taxi_count MEASURE implicit(value 없음); EVENT/operation SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"온유동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=avg`: 질문의 각 구간 안 집계 또는 단일 집계 표현. month: avg → min. answer=value(생략).
- Factor `bucket=month`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=20260801-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=min`: 구간별 값의 외부 집계/선택 방향. month: avg → min. answer=value(생략).
- Ambiguity: 각 월 평균의 표본이 일별 고유 활성 대수인지 정해지지 않았다. 날짜별 빈 값/모집단 처리도 계약에 없다. / 명명 장소의 실제/합성 provider context가 제공되지 않았으며 현재 mock 사전에 없다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / active count/ratio의 기간 표본 단위·분모는 미정이다. Native billing delegation이 compile된다는 사실로 이 정의가 확정되지 않는다. 합계로 바꾸는 것은 금지한다. / 현재 mock get_place_scope는 NOT_FOUND. 이는 실제 TIMS 장소 존재 여부의 판정이 아니며 LLM이 없는 장소를 hallucinate했다는 뜻도 아니다. 질문 자체의 합성 장소 context를 정해야 한다.
- 수정 필요 판단: avg→min은 정확한 문법 대응이다. 질문/기간 측정 정의가 확정되기 전에는 새로운 corrected grounding을 만들 수 없다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution FAIL NOT_FOUND.
- Pair chosen: aggregation=avg, rollup=min
- Pair rejected: aggregation=min, rollup=avg
- Rejected 의미가 다른 이유: 월 평균들의 최소를 월 최소들의 평균으로 바꾼다. 활성 대수의 기간 표본 정의가 필요하다.
- 일별 활성 대수를 가정한 설명용 값: 8월 [2,8], 9월 [4,10]. avg(monthly min)=3, min(monthly avg)=5. 실제 provider 출력/검증 데이터가 아니다.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: RB001-13과 stage 방향을 별도로 확인하고 일별 집단 대수라는 정의를 확정한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:90](/home/hwkim/assistant_univ/geoflow/measures.py:90), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30)

비교 rejected grounding (이 record 자체를 rejected로 판정했다는 뜻이 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "active_taxi_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "온유동",
      "value": {
        "name": "온유동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "min",
    "bucket": "month",
    "date": "20260801-20260930",
    "rollup": "avg"
  }
}
```

### RB001-17 — needs_fix (상세 검토)

- Candidate: `ann-24f8831f1b471e2206fd`; 실제 status: pending.
- 질문: 2026년 9월 솔빛동 택시의 주마다 구한 엔진 회전수 최댓값의 평균은?
- 의미 판단: RPM은 passage에 속하는 엔진 회전수다. 각 주 passage RPM의 최댓값을 구하고 주별 최댓값의 평균을 반환한다. 소속 지역의 택시가 아니라 passage가 발생한 공간 scope를 읽는다.
- 집계/그룹 판단: week: max → avg; answer=value. avg→max는 다른 통계다.
- Concept/subtype: AMOUNT/rpm MEASURE implicit(value 없음); EVENT/passage SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"솔빛동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=max`: 질문의 각 구간 안 집계 또는 단일 집계 표현. week: max → avg; answer=value. avg→max는 다른 통계다.
- Factor `bucket=week`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=avg`: 구간별 값의 외부 집계/선택 방향. week: max → avg; answer=value. avg→max는 다른 통계다.
- Ambiguity: 솔빛동 택시라는 표현만으로 그 동에서 발생한 passage인지 그 동 소속 택시의 모든 passage인지 완전히 명시되지는 않았다. 현재 passage scope는 발생 위치다. 주 경계/부분 주/빈 주도 명시되지 않았다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / TIMS/mock legacy compiler: UNVERIFIED_TIMS_CONTRACT. Schema raw grounding은 표현되지만 계약상 정확한 실행 lowering이 없다.
- 수정 필요 판단: stage 및 subtype은 맞다. get_passage_metrics에 bucket/rollup이 없고 로컬 분해 근거가 미확인이므로 JSON 수정으로 같은 질문의 실행을 확보할 수 없다. 운영 대수/revenue로 바꾸지 않는다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile FAIL `UNVERIFIED_TIMS_CONTRACT` — measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_passage_metrics
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: 솔빛동 내 passage로 한정하는 의도인지 확인한다. TIMS bucket 미지원과 로컬 재계산 계약 미확인은 명확한 실행 제약이다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [schemas/tims.yaml:53](/home/hwkim/assistant_univ/schemas/tims.yaml:53)

검토 대상 grounding (수정본이 아니라 원문을 보존한 제안):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "week",
    "date": "20260901-20260930",
    "rollup": "avg"
  }
}
```

### RB001-18 — needs_fix

- Candidate: `ann-54b0fa2b0c5279bf2201`; 실제 status: pending.
- 질문: 2026년 9월 솔빛동 택시의 주마다 구한 엔진 회전수 최댓값의 평균은?
- 의미 판단: RPM은 passage에 속하는 엔진 회전수다. 각 주 passage RPM의 최댓값을 구하고 주별 최댓값의 평균을 반환한다. 소속 지역의 택시가 아니라 passage가 발생한 공간 scope를 읽는다.
- 집계/그룹 판단: week: max → avg; answer=value. avg→max는 다른 통계다.
- Concept/subtype: AMOUNT/rpm MEASURE implicit(value 없음); EVENT/passage SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"솔빛동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=max`: 질문의 각 구간 안 집계 또는 단일 집계 표현. week: max → avg; answer=value. avg→max는 다른 통계다.
- Factor `bucket=week`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=avg`: 구간별 값의 외부 집계/선택 방향. week: max → avg; answer=value. avg→max는 다른 통계다.
- Ambiguity: 솔빛동 택시라는 표현만으로 그 동에서 발생한 passage인지 그 동 소속 택시의 모든 passage인지 완전히 명시되지는 않았다. 현재 passage scope는 발생 위치다. 주 경계/부분 주/빈 주도 명시되지 않았다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / TIMS/mock legacy compiler: UNVERIFIED_TIMS_CONTRACT. Schema raw grounding은 표현되지만 계약상 정확한 실행 lowering이 없다.
- 수정 필요 판단: stage 및 subtype은 맞다. get_passage_metrics에 bucket/rollup이 없고 로컬 분해 근거가 미확인이므로 JSON 수정으로 같은 질문의 실행을 확보할 수 없다. 운영 대수/revenue로 바꾸지 않는다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile FAIL `UNVERIFIED_TIMS_CONTRACT` — measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_passage_metrics
- Pair chosen: aggregation=max, rollup=avg
- Pair rejected: aggregation=avg, rollup=max
- Rejected 의미가 다른 이유: 주 최댓값들의 평균을 주 평균들의 최댓값으로 바꾼다. Stage 오류는 명확하지만 chosen도 현재 TIMS로 실행되지 않는다.
- 설명용 두 주 passage RPM [10,30], [20,100]: avg(weekly max)=65, max(weekly avg)=60. 실제 측정 결과가 아니다.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: 솔빛동 내 passage로 한정하는 의도인지 확인한다. TIMS bucket 미지원과 로컬 재계산 계약 미확인은 명확한 실행 제약이다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [schemas/tims.yaml:53](/home/hwkim/assistant_univ/schemas/tims.yaml:53)

비교 rejected grounding (이 record 자체를 rejected로 판정했다는 뜻이 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "week",
    "date": "20260901-20260930",
    "rollup": "max"
  }
}
```

### RB001-19 — needs_fix

- Candidate: `ann-779d38516eaca5162eb1`; 실제 status: pending.
- 질문: 2026년 9월 솔빛동 택시의 주마다 평균 낸 엔진 회전수 중 최댓값은?
- 의미 판단: 각 주 passage RPM의 평균을 구한 뒤 주별 평균 중 최댓값을 반환한다. 주별 RPM 최댓값들의 평균과 다르다.
- 집계/그룹 판단: week: avg → max; answer=value.
- Concept/subtype: AMOUNT/rpm MEASURE implicit(value 없음); EVENT/passage SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"솔빛동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=avg`: 질문의 각 구간 안 집계 또는 단일 집계 표현. week: avg → max; answer=value.
- Factor `bucket=week`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=max`: 구간별 값의 외부 집계/선택 방향. week: avg → max; answer=value.
- Ambiguity: 솔빛동 택시의 소속 지역인지 passage 발생 위치인지 명시가 필요할 수 있다. 주 구간 달력 규칙은 원문에 없다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / TIMS/mock legacy compiler: UNVERIFIED_TIMS_CONTRACT. Schema raw grounding은 표현되지만 계약상 정확한 실행 lowering이 없다.
- 수정 필요 판단: avg→max는 질문과 맞다. raw records/count가 없는 하루 평균들로 정확한 주 평균을 복원할 수 없다. factor를 뒤집거나 전체 기간 avg로 축소하지 않는다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile FAIL `UNVERIFIED_TIMS_CONTRACT` — measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_passage_metrics
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: avg는 하루 평균의 평균으로 재구성하면 표본 크기가 달라질 수 있다. RPM Tool의 bucket 미지원과 함께 로컬 평균 복원 한계를 확인한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [schemas/tims.yaml:53](/home/hwkim/assistant_univ/schemas/tims.yaml:53)

### RB001-20 — needs_fix

- Candidate: `ann-0f7e48b754510a2647d4`; 실제 status: pending.
- 질문: 2026년 9월 솔빛동 택시의 주마다 평균 낸 엔진 회전수 중 최댓값은?
- 의미 판단: 각 주 passage RPM의 평균을 구한 뒤 주별 평균 중 최댓값을 반환한다. 주별 RPM 최댓값들의 평균과 다르다.
- 집계/그룹 판단: week: avg → max; answer=value.
- Concept/subtype: AMOUNT/rpm MEASURE implicit(value 없음); EVENT/passage SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":null,"role":"SUBCOND","source":"user","value":{"name":"솔빛동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `aggregation=avg`: 질문의 각 구간 안 집계 또는 단일 집계 표현. week: avg → max; answer=value.
- Factor `bucket=week`: 원문 주/월 단위에 대응; 날짜 한 달이라는 이유만으로 month bucket을 생성하지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `rollup=max`: 구간별 값의 외부 집계/선택 방향. week: avg → max; answer=value.
- Ambiguity: 솔빛동 택시의 소속 지역인지 passage 발생 위치인지 명시가 필요할 수 있다. 주 구간 달력 규칙은 원문에 없다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / TIMS/mock legacy compiler: UNVERIFIED_TIMS_CONTRACT. Schema raw grounding은 표현되지만 계약상 정확한 실행 lowering이 없다.
- 수정 필요 판단: avg→max는 질문과 맞다. raw records/count가 없는 하루 평균들로 정확한 주 평균을 복원할 수 없다. factor를 뒤집거나 전체 기간 avg로 축소하지 않는다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile FAIL `UNVERIFIED_TIMS_CONTRACT` — measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_passage_metrics
- Pair chosen: aggregation=avg, rollup=max
- Pair rejected: aggregation=max, rollup=avg
- Rejected 의미가 다른 이유: 주 평균들의 최댓값을 주 최댓값들의 평균으로 바꾼다. Chosen의 평균 표본을 하루 평균의 평균으로 치환해서도 안 된다.
- 설명용 두 주 passage RPM [10,30], [20,100]: avg(weekly max)=65, max(weekly avg)=60. 실제 측정 결과가 아니다.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: avg는 하루 평균의 평균으로 재구성하면 표본 크기가 달라질 수 있다. RPM Tool의 bucket 미지원과 함께 로컬 평균 복원 한계를 확인한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [schemas/tims.yaml:53](/home/hwkim/assistant_univ/schemas/tims.yaml:53)

비교 rejected grounding (이 record 자체를 rejected로 판정했다는 뜻이 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "week",
    "date": "20260901-20260930",
    "rollup": "avg"
  }
}
```

### RB001-21 — needs_fix (상세 검토)

- Candidate: `ann-e645cbc11600d7348d68`; 실제 status: pending.
- 질문: 2026년 9월 솔빛동에서 승차한 실차 구간을 읍면동 하차지별로 세면 건수가 많은 4곳은?
- 의미 판단: 솔빛동은 승차 장소의 filter(od_role=pickup)다. 집계 그룹은 각 실차 구간의 읍면동 하차지(dimension=emd, dimension_target=dropoff)이며 건수 상위 4개다.
- 집계/그룹 판단: trip_count는 사건 수 자체의 합. aggregation을 추가하지 않는다. order=top, limit=4.
- Concept/subtype: AMOUNT/trip_count MEASURE implicit(value 없음); EVENT/trip SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":"pickup","role":"SUBCOND","source":"user","value":{"name":"솔빛동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `dimension=emd`: 원문 시도별/읍면동별 group 단위; 이름을 가진 place value가 아니다.
- Factor `dimension_target=dropoff`: 원문 승차지/하차지/두 위치 조합에 대응; 장소 filter od_role과 다르다.
- Factor `limit=4`: 원문 3곳/4곳/4개에 대응.
- Factor `order=top`: 많은/높은=top, 적은=bottom의 원문 방향.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / 현재 mock get_place_scope는 NOT_FOUND. 이는 실제 TIMS 장소 존재 여부의 판정이 아니며 LLM이 없는 장소를 hallucinate했다는 뜻도 아니다. 질문 자체의 합성 장소 context를 정해야 한다.
- 수정 필요 판단: od_role=pickup, dimension_target=dropoff를 바꿀 이유가 없다. 장소를 다른 곳으로 수정하려면 질문도 바뀌므로 이 queue의 corrected_grounding으로 몰래 치환할 수 없다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution FAIL NOT_FOUND.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: 방향/target은 원문에서 명확하다. 문제는 솔빛동이 현재 mock/reference 장소 사전에 없어 실행되지 않는 context다. 의미 gold를 합성 장소로 보존할지, 질문을 실제 장소로 새 버전화할지 결정한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12)

검토 대상 grounding (수정본이 아니라 원문을 보존한 제안):

```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "pickup"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c2",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c3",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260901-20260930",
    "dimension": "emd",
    "dimension_target": "dropoff",
    "limit": 4,
    "order": "top"
  }
}
```

### RB001-22 — needs_fix

- Candidate: `ann-e635a6d5297ba3797e8b`; 실제 status: pending.
- 질문: 2026년 9월 솔빛동에서 승차한 실차 구간을 읍면동 하차지별로 세면 건수가 많은 4곳은?
- 의미 판단: 솔빛동은 승차 장소의 filter(od_role=pickup)다. 집계 그룹은 각 실차 구간의 읍면동 하차지(dimension=emd, dimension_target=dropoff)이며 건수 상위 4개다.
- 집계/그룹 판단: trip_count는 사건 수 자체의 합. aggregation을 추가하지 않는다. order=top, limit=4.
- Concept/subtype: AMOUNT/trip_count MEASURE implicit(value 없음); EVENT/trip SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":"pickup","role":"SUBCOND","source":"user","value":{"name":"솔빛동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `dimension=emd`: 원문 시도별/읍면동별 group 단위; 이름을 가진 place value가 아니다.
- Factor `dimension_target=dropoff`: 원문 승차지/하차지/두 위치 조합에 대응; 장소 filter od_role과 다르다.
- Factor `limit=4`: 원문 3곳/4곳/4개에 대응.
- Factor `order=top`: 많은/높은=top, 적은=bottom의 원문 방향.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / 현재 mock get_place_scope는 NOT_FOUND. 이는 실제 TIMS 장소 존재 여부의 판정이 아니며 LLM이 없는 장소를 hallucinate했다는 뜻도 아니다. 질문 자체의 합성 장소 context를 정해야 한다.
- 수정 필요 판단: od_role=pickup, dimension_target=dropoff를 바꿀 이유가 없다. 장소를 다른 곳으로 수정하려면 질문도 바뀌므로 이 queue의 corrected_grounding으로 몰래 치환할 수 없다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution FAIL NOT_FOUND.
- Pair chosen: place.od_role=pickup
- Pair rejected: place.od_role=dropoff
- Rejected 의미가 다른 이유: 솔빛동에서 탄 trip이 아니라 솔빛동에서 내린 trip을 필터한다. dimension_target=dropoff는 그대로여서 하차 위치를 필터와 그룹 양쪽에 쓰는 다른 질문이다.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: 방향/target은 원문에서 명확하다. 문제는 솔빛동이 현재 mock/reference 장소 사전에 없어 실행되지 않는 context다. 의미 gold를 합성 장소로 보존할지, 질문을 실제 장소로 새 버전화할지 결정한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12)

비교 rejected grounding (이 record 자체를 rejected로 판정했다는 뜻이 아님):

```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "dropoff"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c2",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c3",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260901-20260930",
    "dimension": "emd",
    "dimension_target": "dropoff",
    "limit": 4,
    "order": "top"
  }
}
```

### RB001-23 — needs_fix

- Candidate: `ann-9b222bf86273d158269e`; 실제 status: pending.
- 질문: 2026년 9월 솔빛동에서 하차한 실차 구간을 읍면동 승차지별로 세면 건수가 많은 4곳은?
- 의미 판단: 솔빛동은 하차 장소의 filter(od_role=dropoff)다. 결과 그룹은 읍면동 승차지(dimension_target=pickup)이며 건수 상위 4개다. 에서라는 조사만으로 pickup이라고 읽으면 오답이다.
- 집계/그룹 판단: trip_count 사건 수; dimension=emd, order=top, limit=4.
- Concept/subtype: AMOUNT/trip_count MEASURE implicit(value 없음); EVENT/trip SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":"dropoff","role":"SUBCOND","source":"user","value":{"name":"솔빛동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `dimension=emd`: 원문 시도별/읍면동별 group 단위; 이름을 가진 place value가 아니다.
- Factor `dimension_target=pickup`: 원문 승차지/하차지/두 위치 조합에 대응; 장소 filter od_role과 다르다.
- Factor `limit=4`: 원문 3곳/4곳/4개에 대응.
- Factor `order=top`: 많은/높은=top, 적은=bottom의 원문 방향.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / 현재 mock get_place_scope는 NOT_FOUND. 이는 실제 TIMS 장소 존재 여부의 판정이 아니며 LLM이 없는 장소를 hallucinate했다는 뜻도 아니다. 질문 자체의 합성 장소 context를 정해야 한다.
- 수정 필요 판단: od_role=dropoff와 dimension_target=pickup은 맞다. 알 수 없는 장소를 임의의 실제 장소/scope로 바꾸지 않는다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution FAIL NOT_FOUND.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: 하차/승차 동사가 방향을 정한다. 솔빛동의 provider context는 RB001-21과 공동 확인한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12)

### RB001-24 — needs_fix

- Candidate: `ann-26222e9bd384b56dc4d5`; 실제 status: pending.
- 질문: 2026년 9월 솔빛동에서 하차한 실차 구간을 읍면동 승차지별로 세면 건수가 많은 4곳은?
- 의미 판단: 솔빛동은 하차 장소의 filter(od_role=dropoff)다. 결과 그룹은 읍면동 승차지(dimension_target=pickup)이며 건수 상위 4개다. 에서라는 조사만으로 pickup이라고 읽으면 오답이다.
- 집계/그룹 판단: trip_count 사건 수; dimension=emd, order=top, limit=4.
- Concept/subtype: AMOUNT/trip_count MEASURE implicit(value 없음); EVENT/trip SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: {"od_role":"dropoff","role":"SUBCOND","source":"user","value":{"name":"솔빛동","region":""}}. Place는 SUBCOND이고 scope 값은 생성하지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `dimension=emd`: 원문 시도별/읍면동별 group 단위; 이름을 가진 place value가 아니다.
- Factor `dimension_target=pickup`: 원문 승차지/하차지/두 위치 조합에 대응; 장소 filter od_role과 다르다.
- Factor `limit=4`: 원문 3곳/4곳/4개에 대응.
- Factor `order=top`: 많은/높은=top, 적은=bottom의 원문 방향.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다. / 현재 mock get_place_scope는 NOT_FOUND. 이는 실제 TIMS 장소 존재 여부의 판정이 아니며 LLM이 없는 장소를 hallucinate했다는 뜻도 아니다. 질문 자체의 합성 장소 context를 정해야 한다.
- 수정 필요 판단: od_role=dropoff와 dimension_target=pickup은 맞다. 알 수 없는 장소를 임의의 실제 장소/scope로 바꾸지 않는다.
- 정확한 corrected grounding: **미확정(null)**. 원문을 보존하는 JSON-only 변경을 확정하지 않았다.
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution FAIL NOT_FOUND.
- Pair chosen: place.od_role=dropoff
- Pair rejected: place.od_role=pickup
- Rejected 의미가 다른 이유: 솔빛동에서 내린 trip이 아니라 솔빛동에서 탄 trip을 필터한다. 에서라는 조사보다 하차 동사가 우선이다.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: 하차/승차 동사가 방향을 정한다. 솔빛동의 provider context는 RB001-21과 공동 확인한다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12)

비교 rejected grounding (이 record 자체를 rejected로 판정했다는 뜻이 아님):

```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "pickup"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c2",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c3",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260901-20260930",
    "dimension": "emd",
    "dimension_target": "pickup",
    "limit": 4,
    "order": "top"
  }
}
```

### RB001-25 — accepted

- Candidate: `ann-0e4edbda1cb1bec194c1`; 실제 status: pending.
- 질문: 2026년 9월 읍면동 승차지별 실차 구간 건수가 적은 4개 그룹은?
- 의미 판단: 모든 대상 trip을 읍면동 승차지별로 묶어 건수가 적은 4개 그룹을 반환한다. 이름을 가진 장소 filter는 없으며 dimension_target=pickup이다.
- 집계/그룹 판단: trip_count 사건 수; dimension=emd, order=bottom, limit=4.
- Concept/subtype: AMOUNT/trip_count MEASURE implicit(value 없음); EVENT/trip SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: 명명 장소 filter 없음. 시도/읍면동은 dimension이고 LOCATION/place를 만들지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `dimension=emd`: 원문 시도별/읍면동별 group 단위; 이름을 가진 place value가 아니다.
- Factor `dimension_target=pickup`: 원문 승차지/하차지/두 위치 조합에 대응; 장소 filter od_role과 다르다.
- Factor `limit=4`: 원문 3곳/4곳/4개에 대응.
- Factor `order=bottom`: 많은/높은=top, 적은=bottom의 원문 방향.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다.
- 수정 필요 판단: 질문에 맞는 현재 grounding을 유지한다. 확정된 JSON field 수정은 없다.
- Corrected grounding: null(수정 불필요; 현재 proposed grounding 유지).
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution PASS (fixture).
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: 건수 0인 지역도 포함하라는 뜻은 없다. 제공자가 반환한 group 중 bottom으로 읽는다. 0건 전수 지역을 요구하면 universe/zero-fill 정의가 별도로 필요하다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12)

### RB001-26 — accepted

- Candidate: `ann-99ce1d80b508f65f08de`; 실제 status: pending.
- 질문: 2026년 9월 읍면동 승차지별 실차 구간 건수가 적은 4개 그룹은?
- 의미 판단: 모든 대상 trip을 읍면동 승차지별로 묶어 건수가 적은 4개 그룹을 반환한다. 이름을 가진 장소 filter는 없으며 dimension_target=pickup이다.
- 집계/그룹 판단: trip_count 사건 수; dimension=emd, order=bottom, limit=4.
- Concept/subtype: AMOUNT/trip_count MEASURE implicit(value 없음); EVENT/trip SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: 명명 장소 filter 없음. 시도/읍면동은 dimension이고 LOCATION/place를 만들지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `dimension=emd`: 원문 시도별/읍면동별 group 단위; 이름을 가진 place value가 아니다.
- Factor `dimension_target=pickup`: 원문 승차지/하차지/두 위치 조합에 대응; 장소 filter od_role과 다르다.
- Factor `limit=4`: 원문 3곳/4곳/4개에 대응.
- Factor `order=bottom`: 많은/높은=top, 적은=bottom의 원문 방향.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다.
- 수정 필요 판단: 질문에 맞는 현재 grounding을 유지한다. 확정된 JSON field 수정은 없다.
- Corrected grounding: null(수정 불필요; 현재 proposed grounding 유지).
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution PASS (fixture).
- Pair chosen: dimension_target=pickup
- Pair rejected: dimension_target=dropoff
- Rejected 의미가 다른 이유: 승차 읍면동 그룹을 하차 읍면동 그룹으로 바꾼다. 이 질문의 named scope filter는 없으므로 둘은 유효한 다른 분포다.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: 건수 0인 지역도 포함하라는 뜻은 없다. 제공자가 반환한 group 중 bottom으로 읽는다. 0건 전수 지역을 요구하면 universe/zero-fill 정의가 별도로 필요하다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12)

비교 rejected grounding (이 record 자체를 rejected로 판정했다는 뜻이 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260901-20260930",
    "dimension": "emd",
    "dimension_target": "dropoff",
    "limit": 4,
    "order": "bottom"
  }
}
```

### RB001-27 — accepted (상세 검토)

- Candidate: `ann-2d254560f2214204db4b`; 실제 status: pending.
- 질문: 2026년 9월 읍면동 승차지와 하차지 조합별 실차 구간 건수가 적은 4개 그룹은?
- 의미 판단: 출발 읍면동과 도착 읍면동의 순서 있는 조합(OD pair)별로 trip을 묶고 건수 하위 4개 조합을 반환한다. LOCATION 이름 filter나 한 장소의 od_role=both가 아니다.
- 집계/그룹 판단: dimension=emd + dimension_target=both + order=bottom + limit=4. pickup별/ dropoff별 단독 집계로 바꾸면 다른 그룹이다.
- Concept/subtype: AMOUNT/trip_count MEASURE implicit(value 없음); EVENT/trip SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: 명명 장소 filter 없음. 시도/읍면동은 dimension이고 LOCATION/place를 만들지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `dimension=emd`: 원문 시도별/읍면동별 group 단위; 이름을 가진 place value가 아니다.
- Factor `dimension_target=both`: 원문 승차지/하차지/두 위치 조합에 대응; 장소 filter od_role과 다르다.
- Factor `limit=4`: 원문 3곳/4곳/4개에 대응.
- Factor `order=bottom`: 많은/높은=top, 적은=bottom의 원문 방향.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다.
- 수정 필요 판단: 질문에 맞는 현재 grounding을 유지한다. 확정된 JSON field 수정은 없다.
- Corrected grounding: null(수정 불필요; 현재 proposed grounding 유지).
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution PASS (fixture).
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: both는 승/하차 지역 조합을 그룹화한다. 하나의 named place 안에서 출발/도착한 trip 조건과 다르다. 미발생 조합을 0으로 채우라는 뜻은 없으며 그런 요구는 schema에 없다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12)

검토 대상 grounding (수정본이 아니라 원문을 보존한 제안):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260901-20260930",
    "dimension": "emd",
    "dimension_target": "both",
    "limit": 4,
    "order": "bottom"
  }
}
```

### RB001-28 — accepted

- Candidate: `ann-32d4211719d531d3a08b`; 실제 status: pending.
- 질문: 2026년 9월 읍면동 승차지와 하차지 조합별 실차 구간 건수가 적은 4개 그룹은?
- 의미 판단: 출발 읍면동과 도착 읍면동의 순서 있는 조합(OD pair)별로 trip을 묶고 건수 하위 4개 조합을 반환한다. LOCATION 이름 filter나 한 장소의 od_role=both가 아니다.
- 집계/그룹 판단: dimension=emd + dimension_target=both + order=bottom + limit=4. pickup별/ dropoff별 단독 집계로 바꾸면 다른 그룹이다.
- Concept/subtype: AMOUNT/trip_count MEASURE implicit(value 없음); EVENT/trip SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: 명명 장소 filter 없음. 시도/읍면동은 dimension이고 LOCATION/place를 만들지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `dimension=emd`: 원문 시도별/읍면동별 group 단위; 이름을 가진 place value가 아니다.
- Factor `dimension_target=both`: 원문 승차지/하차지/두 위치 조합에 대응; 장소 filter od_role과 다르다.
- Factor `limit=4`: 원문 3곳/4곳/4개에 대응.
- Factor `order=bottom`: 많은/높은=top, 적은=bottom의 원문 방향.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다.
- 수정 필요 판단: 질문에 맞는 현재 grounding을 유지한다. 확정된 JSON field 수정은 없다.
- Corrected grounding: null(수정 불필요; 현재 proposed grounding 유지).
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution PASS (fixture).
- Pair chosen: dimension_target=both
- Pair rejected: dimension_target=pickup
- Rejected 의미가 다른 이유: 승하차의 순서 있는 조합별 분포를 승차 지역만의 marginal 분포로 합친다. 한 승차지의 서로 다른 하차지가 합쳐져 group 수와 건수가 달라질 수 있다.
- 설명용 trip: A→B 2건, A→C 3건. both는 (A,B)=2,(A,C)=3이고 pickup만은 A=5로 합쳐진다. 실제 provider 관측이 아니다.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: both는 승/하차 지역 조합을 그룹화한다. 하나의 named place 안에서 출발/도착한 trip 조건과 다르다. 미발생 조합을 0으로 채우라는 뜻은 없으며 그런 요구는 schema에 없다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12)

비교 rejected grounding (이 record 자체를 rejected로 판정했다는 뜻이 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260901-20260930",
    "dimension": "emd",
    "dimension_target": "pickup",
    "limit": 4,
    "order": "bottom"
  }
}
```

### RB001-29 — accepted

- Candidate: `ann-0d51b49a28500bb47b0d`; 실제 status: pending.
- 질문: 2026년 9월 읍면동 하차지별 실차 구간 건수가 적은 4개 그룹은?
- 의미 판단: 모든 대상 trip을 읍면동 하차지별로 묶어 건수 하위 4개 그룹을 반환한다. 특정 하차 장소 filter는 없으며 dimension_target=dropoff이다.
- 집계/그룹 판단: trip_count 사건 수; dimension=emd, order=bottom, limit=4.
- Concept/subtype: AMOUNT/trip_count MEASURE implicit(value 없음); EVENT/trip SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: 명명 장소 filter 없음. 시도/읍면동은 dimension이고 LOCATION/place를 만들지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `dimension=emd`: 원문 시도별/읍면동별 group 단위; 이름을 가진 place value가 아니다.
- Factor `dimension_target=dropoff`: 원문 승차지/하차지/두 위치 조합에 대응; 장소 filter od_role과 다르다.
- Factor `limit=4`: 원문 3곳/4곳/4개에 대응.
- Factor `order=bottom`: 많은/높은=top, 적은=bottom의 원문 방향.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다.
- 수정 필요 판단: 질문에 맞는 현재 grounding을 유지한다. 확정된 JSON field 수정은 없다.
- Corrected grounding: null(수정 불필요; 현재 proposed grounding 유지).
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution PASS (fixture).
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: 승차지 기준이나 OD pair 기준으로 바꾸지 않는다. 반환된 그룹 외의 0건 지역 전체를 생성하는 의미가 아니다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12)

### RB001-30 — accepted

- Candidate: `ann-623aed550ed6e3dfdf4c`; 실제 status: pending.
- 질문: 2026년 9월 읍면동 하차지별 실차 구간 건수가 적은 4개 그룹은?
- 의미 판단: 모든 대상 trip을 읍면동 하차지별로 묶어 건수 하위 4개 그룹을 반환한다. 특정 하차 장소 filter는 없으며 dimension_target=dropoff이다.
- 집계/그룹 판단: trip_count 사건 수; dimension=emd, order=bottom, limit=4.
- Concept/subtype: AMOUNT/trip_count MEASURE implicit(value 없음); EVENT/trip SUPPORT implicit(value 없음). 질문 단어가 있다는 이유로 source=user로 바꾸지 않는다.
- 장소: 명명 장소 filter 없음. 시도/읍면동은 dimension이고 LOCATION/place를 만들지 않는다.
- Factor `date=20260901-20260930`: 질문의 명시 날짜/기간 또는 지난달. 지난달은 last_month를 유지하며 현재 시스템 날짜로 gold를 재작성하지 않는다.
- Factor `dimension=emd`: 원문 시도별/읍면동별 group 단위; 이름을 가진 place value가 아니다.
- Factor `dimension_target=dropoff`: 원문 승차지/하차지/두 위치 조합에 대응; 장소 filter od_role과 다르다.
- Factor `limit=4`: 원문 3곳/4곳/4개에 대응.
- Factor `order=bottom`: 많은/높은=top, 적은=bottom의 원문 방향.
- Ambiguity: 필수 stage/OD 방향/target은 원문에서 명확하다. 제공자 기본 달력/빈 결과 처리는 별도 한계다.
- Runtime/schema 한계: 실제 TIMS provider/데이터는 검증하지 않았다. Mock 결과는 고정 fixture로 정확한 수치·기간·통계 모집단을 검증하는 증거가 아니다. / legacy/TIMS 계약의 범위·상대 날짜/구간 정의는 provider에 위임하거나 미확인 상태로 남는다. strict profile에서 같은 지원을 주장하지 않는다.
- 수정 필요 판단: 질문에 맞는 현재 grounding을 유지한다. 확정된 JSON field 수정은 없다.
- Corrected grounding: null(수정 불필요; 현재 proposed grounding 유지).
- CPU 확인: strict parse/compose/G1~G7 PASS; TIMS legacy compile PASS; mock execution PASS (fixture).
- Pair chosen: dimension_target=dropoff
- Pair rejected: dimension_target=pickup
- Rejected 의미가 다른 이유: 하차 읍면동 그룹을 승차 읍면동 그룹으로 바꾼다. Scope와 dimension_target은 서로 대체되지 않는다.
- Base/SFT/DPO: 이 새 질문에 대한 과거 prediction 없음; 새 inference 미실행.
- 사람이 확정할 질문: 승차지 기준이나 OD pair 기준으로 바꾸지 않는다. 반환된 그룹 외의 0건 지역 전체를 생성하는 의미가 아니다. / Accepted 추천도 사람이 source/role/factor/stage/OD/support/lineage를 확인한 뒤에만 실제 decision으로 확정한다.
- 근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12)

비교 rejected grounding (이 record 자체를 rejected로 판정했다는 뜻이 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260901-20260930",
    "dimension": "emd",
    "dimension_target": "pickup",
    "limit": 4,
    "order": "bottom"
  }
}
```

## 사람이 draft를 확정한 뒤의 절차

1. 각 ID별 최종 status와 근거를 사람이 확정한다. Draft의 추천/assistant 표식을 human으로 자동 치환하지 않는다. 특히 needs_fix 19건과 동구/중구의 지역 의도를 확인한다. 모든 accepted에도 semantic/lineage attestation이 필요하다.
2. 최종 판정만 기존 workflow `decide`로 별도 `decisions.jsonl`에 기록한다. 이 단계는 아직 실행하지 않았다. 아래는 사람이 RB001-01을 실제 수락한 경우의 예이다.

```bash
python -m training.annotations.workflow decide \
  --queue training/annotations/generated/expansion_001 \
  --decisions training/annotations/generated/review_batch_001/decisions.jsonl \
  --id ann-d983889cf8c496178106 --status accepted \
  --reviewer YOUR_NAME --reason '직접 확인한 의미·지원 범위·family 근거' \
  --semantic-checks-confirmed
```

보류/폐기는 --status needs_fix/rejected로 기록하며 confirmation flag를 쓰지 않는다. Pair를 실제 수락하는 경우에만 chosen/rejected 의미를 각각 확인하고 --negative-is-wrong를 추가한다. 지원 outcome/질문을 바꾸는 수정은 이 불변 queue에 적용할 수 없다. 원문에서 도출되는 JSON field 수정이 추후 확정된 경우에만 --corrected-grounding FILE/--corrected-rejected FILE을 사용한다.

3. Actual accepted가 두 개 이상의 독립된 semantic/contrast family를 포함하고 split/coverage를 확인한 뒤 versioned import를 실행한다. Draft 파일을 직접 import하지 않는다.

```bash
python -m training.annotations.workflow import-reviewed \
  --queue training/annotations/generated/expansion_001 \
  --decisions training/annotations/generated/review_batch_001/decisions.jsonl \
  --version reviewed_gold_v001 \
  --output training/annotations/generated/corpora/reviewed_gold_v001 \
  --seed 42 --valid-fraction 0.2
```

Import는 human decision hash/attestation, source/prompt/queue hash, 보호된 family, identical pair, parse/compose/validation, split을 검사한다. Import 자체는 compiler의 실행 지원이나 실제 TIMS 의미를 자동 보장하지 않는다. 이번 draft에서 support를 따로 검토한 이유다. Import 이후에도 이번 작업에서는 학습을 시작하지 않는다.

## 재현 정보

- Git commit: `65e9ea2ec98f8cec289cbb753ce543dee3efdd92`; branch: `geoflow/dev-v2`.
- Queue SHA256: `880cca2920a68d5e84f7a6f1d43372a19fe46ec110cf41007f2ce050c7907808`.
- Batch SHA256: `6a0c1c944548caf67627f6db21555c2ddbc14af3d261533581bfc035ae1b622b`.
- Production prompt hash: `522aa3b1716248b53a755ee1b236e7aef302c85504e9cfac3825f4d3cc817945`.
- Drafted UTC: 2026-10-04T12:51:30.130398+00:00. JSONL의 각 record에는 candidate/view hash, definition/runtime/source hash, CPU diagnostics, item별 draft hash가 있다.
- 원본 96건은 전부 pending, 보호/diagnostic 50건은 그대로다. 결정 audit·reviewed corpus·GPU 학습은 생성/실행하지 않았다.
