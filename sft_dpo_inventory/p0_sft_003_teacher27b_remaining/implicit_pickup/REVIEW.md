# Track B — implicit-pickup 4문항 검토

2026-10-14. 결정 83, `../PLAN.md` 7절. 새 모델 호출 0(8B 0, 27B 0).

- 읽은 자료:
  - 기존 27B 20 trace(`training/generated/p0_sft_003_teacher27b/raw/traces.jsonl`, sha256 `9933052e…`)
  - v006 gold
  - P0 prompt(`partial_p0.yaml`, 수정 없음)
- 산출물: `analysis.json`, `failure_matrix.csv`, `canonical_rationale_candidates.jsonl`(생성 스크립트 `build_analysis.py`).

## 1. 결론

- 4문항 모두 **CLEAR_GOLD**다. gold에는 문제가 없다(GOLD_PROBLEM 0).
- 20 call은 모두 같은 꼴로 실패했다:
  - 승차를 사건 동사("탄", "태운", "승차가")로만 말하면 승차 끝을 놓친다.
  - 놓치는 slot은 묶는 끝(dimension_target), 장소 제한의 끝(od_role), 또는 둘 다다.
- 틀린 값을 넣은 경우는 0이다. 전부 **생략**이다. 다른 factor는 20/20 gold와 같다.
- thinking 수준에서 20/20은 의미 이해 실패(SEMANTIC_UNDERSTANDING_FAILURE)다. reasoning에서 맞게 알고 JSON에서만 빠뜨린 경우(SERIALIZATION_OMISSION)는 0이다.
- 20/20에 PROMPT_COVERAGE_GAP이 겹친다. P0 prompt에는 이 꼴의 예가 없다. 오히려 "'손님을 태운 운행'은 trip"이라는 규칙을 27B가 근거로 인용해 끝 정보를 버렸다.
- teacher 표본을 더 늘리는 것보다 짧은 명시적 rationale이 더 맞는 supervision일 가능성이 높다(14절 Path B 판단 근거).

## 2. gold 판정(slot별)

장소 제한의 끝(od_role)과 묶는 끝(dimension_target)을 따로 판단했다.

| id | 질문 | measure | 장소 제한 | 장소 od_role | dimension | dimension_target | order·limit | 판정 |
|---|---|---|---|---|---|---|---|---|
| b006-05 | 지난달 택시를 탄 건수가 가장 많은 시도는? | trip_count | 없음 | 해당 없음 | sido | pickup | top 1 | CLEAR_GOLD |
| b006-15 | 2026년 8월 부산에서 손님을 태운 건수가 가장 적은 구 두 곳은? | trip_count | 부산 | pickup | sigungu | pickup | bottom 2 | CLEAR_GOLD |
| b006-20 | 지난달 대구에서 승차가 가장 적었던 구는? | trip_count | 대구 | pickup | sigungu | pickup | bottom 1 | CLEAR_GOLD |
| b006-26 | 이번 달 대구 수성구에서 손님을 가장 적게 태운 H3 셀 세 곳은? | trip_count | 대구 수성구 | pickup | h3 | pickup | bottom 3 | CLEAR_GOLD |

- **dimension_target**: "탄/태운/승차"는 승차 사건이다. 묻는 단위(시도·구·셀)는 한 끝의 지역이다.
  - both(조합)로는 "시도는?"처럼 지역 하나를 답할 수 없다. dropoff는 동사와 반대다. 그래서 pickup 하나로 정해진다.
- **od_role**: "부산에서 손님을 태운", "대구에서 승차"의 "~에서"는 승차 사건의 위치를 제한한다. "A에서 출발 → pickup"과 같은 꼴이다.
  - "부산 안의 구"라는 범위로 읽어도, 승차 끝 기준으로 묶으면 결과는 같다.
  - P0 계약은 "출발·도착이 드러나는 질문에서는 각 장소 개념에 od_role을 반드시" 붙이라고 한다. 그래서 od_role 없는 표현은 계약상 틀린 출력이다.
  - 언어 해석과 계약이 같은 답을 가리키므로 CONTRACT_DEPENDENT로 따로 두지 않았다.
- **h3**: P0 정의("실차 구간을 dimension으로 나누면 … 묶는 끝")는 dimension 종류를 가리지 않는다.
  - 27B 자신도 b006-17, b006-24(h3 + dimension_target)에서 맞혔다.
- LINGUISTICALLY_AMBIGUOUS 0, CONTRACT_DEPENDENT 0, GOLD_PROBLEM 0.

## 3. 기존 20 call failure matrix(`failure_matrix.csv`)

| | correct | omitted | wrong | 해당 없음 |
|---|---:|---:|---:|---:|
| dimension_target | 6 | 14 | 0 | 0 |
| od_role(장소 있는 15 call) | 0 | 15 | 0 | 5(b006-05) |

- 둘 다 맞음 0, 하나만 틀림 11, 둘 다 틀림 9.

| id | dimension_target | od_role |
|---|---|---|
| b006-05 | omitted 5 | 해당 없음 |
| b006-15 | omitted 5 | omitted 5 |
| b006-20 | **correct 5** | omitted 5 |
| b006-26 | omitted 4, correct 1(k=3) | omitted 5 |

- b006-20만 dimension_target을 5/5 맞혔다. "승차가 가장 적었던 구"가 prompt 예시 "승차가 많은 읍면동"과 거의 같은 꼴이기 때문이다(thinking에서 그 예시를 인용).
- od_role은 15/15 빠졌다. 장소 제한의 끝은 이 꼴에서 한 번도 회수되지 않았다.

## 4. thinking 수준 분류

| tag | call 수 | 내용 |
|---|---:|---|
| SEMANTIC_UNDERSTANDING_FAILURE | 20 | 승차 끝을 reasoning에서 알아보지 못하거나, 알아보고도 "끝 정보 없음"으로 결론 |
| SERIALIZATION_OMISSION | 0 | — |
| OD_ROLE_DIM_TARGET_COLLAPSE | 1 | b006-20 k=2: "대구는 일반 범위, 승차는 dimension_target이 처리한다"며 한 승차 신호를 한 slot에만 씀 |
| PROMPT_COVERAGE_GAP | 20 | 아래 5절 |

반복된 reasoning 꼴:

1. **"태운 = trip 이름"**(b006-05 5, b006-15 5, b006-26 다수)
   - P0의 "'실차', '실차 구간', '손님을 태운 운행'이 이 분석 대상을 가리키면 trip" 규칙을 인용한다.
   - 그 결과 "손님을 태운"을 끝 정보 없는 measure 이름으로 읽는다.
   - b006-15 k=2는 "picked up passengers"라고 번역하고도 "trip 자체"라며 생략했다.
2. **"pickup/dropoff를 특정하지 않았으니 생략(both)"**(b006-05 k=1·k=3, b006-15 k=1·k=2, b006-26 k=4)
   - 생략 = both 규칙을 알면서도, 질문이 한 끝을 말하고 있다는 것을 보지 못했다.
3. **"장소는 분석 범위"**(b006-15, b006-20, b006-26)
   - "부산/대구/수성구에서"를 region·EXTENT·검색 범위로만 본다. od_role 검토 자체가 없다(b006-15 k=3, b006-20 k=2만 검토하고 기각).
4. **"dimension_target은 행정구역에만"**(b006-26 k=1·k=2): prompt에 없는 제한을 만들었다.

## 5. P0 prompt와의 연결(수정하지 않음)

- dimension_target 예시는 그룹 표현("승차가 많은 읍면동", "출발 지역별", "도착 지역별", "출발지-도착지 조합")뿐이다. 사건 동사 "탄/태운"으로 끝을 정하는 예가 없다.
- od_role 예시는 "A에서 출발", "B에 도착", "C 안에서 오간"뿐이다. "A에서 승차/손님을 태운"이 장소 제한의 끝이라는 예가 없다.
- 장소 제한의 끝과 묶는 끝이 **같은 끝**인 예가 없다. 유일한 독립 예시는 서로 다른 끝(pickup / dropoff)이다.
- h3 + dimension_target 예가 없다.
- "'손님을 태운 운행'은 trip"이라는 규칙이 끝 정보를 지우는 근거로 쓰였다. 이 규칙은 taxi_status를 따로 적지 말라는 뜻이지만, 27B는 범위를 넓혀 읽었다.

## 6. canonical rationale candidates(`canonical_rationale_candidates.jsonl`)

- CLEAR_GOLD 4문항에 각 1개, 모두 4개다. 형식: measure / place restriction / od_role / grouping dimension / dimension_target / order + 한두 문장 bridge.
- 예(b006-15): "'손님을 태운'은 승차 사건이므로 구는 승차 끝 기준으로 묶는다. '부산에서'가 그 승차 위치를 제한하므로 부산의 od_role도 pickup이다. 두 판단은 따로 하지만 결론은 같은 끝이다."
- **training_inclusion = false, counted_in_coverage = false, replaces_teacher_trace = false.** 학습 포함 여부는 별도 결정이다.
