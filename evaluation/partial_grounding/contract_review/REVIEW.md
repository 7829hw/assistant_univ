# dimension_target · od_role gold / 계약 검토

2026-10-12. 모델 호출 없음, gold 수정 없음.

- 근거 수치: sel154 run(`ab_p0_3/raw`, Full·P0·P0.3 sampling 5회).
- 산출물: `review.json`, `review_items.csv`(스크립트 `build_review.py`), 계약 문서 `CONTRACT.md`.
- 판정은 질문 문장과 gold를 사람 기준으로 읽은 검토 의견이다. 사람 승인이나 annotation 승인이 아니다(CLAUDE.md 규칙 8).

## 1. 결론

- **검토한 13문항 모두 CLEAR_GOLD다.** LIKELY_GOLD_ERROR, AMBIGUOUS_LANGUAGE 문항은 없다. 수정이 필요한 gold는 없다.
- **ROOT_CAUSE.md의 gold_review_candidate 두 문항은 다시 읽고 철회한다.**
  - n35: 끝점은 pickup으로 분명하다(3절).
  - k34: 의미는 분명하다. 문제는 아래 계약 쪽 표현이다.
- **계약 쪽 발견 1건: INTRA_AREA_SERIALIZATION.** "구역 안에서만 오간 운행"처럼 같은 장소가 양 끝을 거르는 질문의 표현이 셋이다.
  1. `od_role=both` 장소 하나
  2. 같은 장소의 pickup·dropoff 두 개
  3. od_role 없는 장소 하나. 조건 계층이 질문에서 보충할 때만 맞는다.
  - 1과 2는 Tool 호출이 같다(`geoflow/grounding.py`의 `OD_BOTH`: 같은 scope를 두 port에 채움). semantic correctness에서는 match다.
  - 그러나 `evaluate_vendor100._grounding_view`는 둘을 다르게 본다. grounding_ok·grounding_diffs에서만 차이로 잡힌다.
    - Tool 호출은 맞았는데 이 차이만 남은 관측: Full 11, P0 12, P0.3 12(sampling 합계).
  - gold 오류가 아니다. 표준 표기는 결정 47·29가 이미 (a) 한 장소 both로 정했다. 평가 gold(gold_text 역산)가 (b)이고 비교 정규형이 둘을 같게 보지 않는 것이 남은 문제다(`CONTRACT.md` 5절).
- **ROOT_CAUSE.md 정정:**
  - 10절 "both 유형 G 실패의 대부분도 같은 '구역 내부 이동' 계약 문제"는 일부만 맞다.
  - c04a, n09, k33에서 P0.3의 실제 실패는 표현 차이가 아니다. 장소에 od_role을 적지 않아(`1:None`) MISSING_RELATION_QUALIFIER로 실패하거나, pickup만 적은 실제 오류다.
  - 그 대신 P0.3는 양 끝 제한을 `dimension_target=both`(grouping)로 옮겨 적는다(4절).

## 2. 검토 대상

| 묶음 | 문항 | 선정 이유 |
|---|---|---|
| 사용자 지정 | n35, k34, c04a, n09, k33 | ROOT_CAUSE gold_review_candidate와 구역 내부 이동 |
| 같은 유형(구역 내부 이동, gold에 `$area.scope` 두 인자) | n10, m12, k32, c04c | sel154에서 같은 장소가 양 끝을 거르는 나머지 문항 전부 |
| 같은 유형(사건 표현 같은 끝, 세 arm 결정적 실패) | n05, k28, m03, m04 | ROOT_CAUSE에서 Full도 실패한 dt 문항 |

## 3. 문항별 판정

- A 자연어 의미의 끝점, B od_role, C dimension_target, D 장소 scope 구조.
- k는 Full / P0 / P0.3, 5회 중 정답 수.
- P0.3 첫 응답 장소 패턴은 `장소 수:od_role`이다.

| item | 질문(요약) | A | B | C | D | k | P0.3 첫 응답 장소 / dt | 판정 |
|---|---|---|---|---|---|---|---|---|
| indepv2/n35 | 휴일 아침 승차 건수를 시도 단위로, 제일 적은 두 곳 | pickup | 없음 | pickup | scope 없음 | 0/0/0 | 장소 없음 / dt None 5 | CLEAR_GOLD |
| indepv4/k34 | 대구 안에서 출발·도착이 다 이뤄진 운행을 내린 구 기준으로, 가장 적은 구 | 제한=양 끝, grouping=dropoff | 대구: both | dropoff | 두 scope(= both 하나) | 0/0/0 | `1:None` 5 / None 3, both 2 | CLEAR_GOLD + 계약 |
| contrast/c04a | 대구 안에서 이동한 읍면동 간 노선 상위 3 | 제한=양 끝, grouping=both | 대구: both | both | 두 scope | 3/2/2 | `1:None` 5 / both 4 | CLEAR_GOLD + 계약 |
| indepv2/n09 | 수성구 안에서만 오간 읍면동 간 노선 1 | 제한=양 끝, grouping=both | 수성구: both | both | 두 scope | 3/5/1 | `1:None` 5 / both 4 | CLEAR_GOLD + 계약 |
| indepv4/k33 | 중구 안에서만 움직인 운행을 동→동 경로로, 상위 2 | 제한=양 끝, grouping=both | 중구: both | both | 두 scope | 1/2/2 | `1:None` 4, `1:pickup` 1 / both 4 | CLEAR_GOLD + 계약 |
| indepv2/n10 | 부산 내부에서 출발·도착이 모두 이뤄진 실차 건수 | 제한=양 끝 | 부산: both | 없음 | 두 scope | 4/2/3 | 섞임 / both 3 | CLEAR_GOLD + 계약 |
| indepv3/m12 | 승차·하차가 둘 다 중구 안인 실차 건수 | 제한=양 끝 | 중구: both | 없음 | 두 scope | 0/4/5 | `2:pickup/dropoff` 4 | CLEAR_GOLD + 계약 |
| indepv4/k32 | 수영구 안에서 타고 내린 실차 건수 | 제한=양 끝 | 수영구: both | 없음 | 두 scope | 5/5/5 | `1:both` 3, `1:None` 2 | CLEAR_GOLD + 계약 |
| contrast/c04c | 부산 안에서 이동한 실차 구간 건수 | 제한=양 끝 | 부산: both | 없음 | 두 scope | 3/2/1 | `1:None` 5 | CLEAR_GOLD + 계약 |
| indepv2/n05 | 대구 안 어느 H3 셀에서 가장 많이 내렸는지 | dropoff | 대구: dropoff | dropoff | scope_dropoff | 3/1/0 | `1:None` 3, `1:dropoff` 2 / None 5 | CLEAR_GOLD |
| indepv4/k28 | 중구로 향한 손님들이 내린 위치를 H3 셀 기준으로 | dropoff | 중구: dropoff | dropoff | scope_dropoff | 0/1/0 | `1:dropoff` 3 / None 5 | CLEAR_GOLD |
| indepv3/m03 | 달서구에서 내린 손님이 가장 몰린 H3 셀 | dropoff | 달서구: dropoff | dropoff | scope_dropoff | 1/2/0 | None 5 | CLEAR_GOLD |
| indepv3/m04 | 중구 가운데 승차가 가장 뜸했던 동 세 곳 | pickup | 중구: pickup | pickup | scope_pickup | 0/0/0 | None 4 | CLEAR_GOLD(실패 주원인은 order) |

**n35 재검토.**

- "승차 건수를 시도 단위로 비교하면 제일 적은 두 곳"은 장소 둘을 답하라는 질문이다.
- dimension_target을 생략하면 기본값 both(출발-도착 시도 짝)가 되어 질문과 맞지 않는다. 승차 지역 시도별이 자연스러운 읽기다.
- "승차 건수"가 일상어로 "이용 건수"처럼 쓰이는 점은 측정값의 뜻 문제다. 결과를 장소로 답하는 문장에서 끝점을 바꾸지 않는다.

**k34.**

- 장소 제한(양 끝 대구)과 grouping(내린 구)이 다른 끝을 가리키는 문항이다.
- 세 arm 모두 "출발과 도착이 다"를 grouping 쪽(dimension_target=both)으로 옮기거나 dimension_target을 빼서 실패한다.
- gold는 분명하다.

## 4. 반복 패턴: 제한(od_role)과 grouping(dimension_target)의 자리 바꿈

| 방향 | 예 | 관측 |
|---|---|---|
| grouping 끝을 장소 제한으로만 씀 | n05, k28: 장소 dropoff, dimension_target 없음 | ROOT_CAUSE B형 |
| 양 끝 제한을 grouping으로 씀 | c04a, n09, k33, n10: 장소 od_role 없음, dimension_target=both | P0.3 첫 응답(네 문항 20관측): od_role 없는 장소 하나 15, dimension_target=both 15. MISSING_RELATION_QUALIFIER로 실패하거나, 조건 계층이 보충하면 맞음 |
| 제한과 grouping이 다른 끝일 때 섞음 | k34: grouping을 both로 | 세 arm 공통 |

이 패턴은 gold 문제가 아니라 모델이 두 축(장소가 거르는 끝 / 결과를 묶는 끝)을 하나로 다루는 의미 구분 문제다. 계약 문서(`CONTRACT.md`)에 두 축을 분리해 적었다. 이 문서는 prompt에 넣을 문구가 아니다.

## 5. 다음에 사람이 정할 것

1. **구역 내부 이동의 표준 직렬화는 이미 정해져 있다.**
   - 결정 47: "한 장소 both와 출발+도착 두 항목은 뜻이 같다. 계약이 정한 표기는 한 장소 both이고, gold는 이 표기로 둔다."
   - 결정 29: (b) 표기의 h03을 valid98에서 뺐다.
   - 학습 gold v005도 이 표기만 쓴다(both 20, 두 장소 0).
   - 새 결정은 필요 없다.
2. **남은 결정 하나: `_grounding_view`가 (a)와 (b)를 같은 것으로 보게 할지.**
   - 평가 gold는 gold_text 역산이라 (b)다. 지금 비교는 둘을 다르게 센다.
   - 평가 코드 변경이며 code fingerprint 범위 밖이다. 이번 단계에서는 바꾸지 않았다.
   - 바꾸면 grounding_ok 수치가 이전 기록과 달라지므로 결정과 함께 한다.
