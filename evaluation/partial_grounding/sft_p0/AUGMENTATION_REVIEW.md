# batch006 P0 SFT 보강 후보 검토

2026-10-13. **승인이 아니다.** 결정 45 절차(Claude 초안 → 자동 계약 검사 → 사람 승인 → training set 편입)의 세 번째 단계 앞에서 멈춘 상태다. 초안 gold와 자동 검사 통과는 승인이 아니다.

- 초안: `sft_dpo_inventory/batch006/write_drafts.py` → `candidates_draft.yaml`
  - 위치 이유: `evaluation/**/*.yaml`은 보호 원본이라, 그 아래에 두면 초안이 자기 자신과 겹친 것으로 잡힌다.
- 자동 검사: `sft_dpo_inventory/batch006/check_candidates.py` → `augmentation_candidates.jsonl`, `overlap_report.json`
- 분포: `dataset_stats.py` → `dataset_stats.json`
- 이 표: `sft_dpo_inventory/batch006/render_review.py`

## 1. 요약

| 항목 | 값 |
|---|---:|
| 초안 | 53(Gap A 26, Gap B 17, Gap C 10) |
| 자동 계약 검사 통과 | 43(A 26, B 17) |
| 평가셋·보호 셋 겹침으로 제외 | 10(Gap C 전부) |
| 후보끼리 질문 중복 | 0 |
| 학습(v005)과 질문 중복 | 0(family 겹침 6, 정보로만) |
| 사람 검토 필요 | 43(통과분 전부) + Gap C 처리 결정 1 |

**자동 검사.** batch005와 같은 검사에 P0 검사를 더했다.

- thor 계약(normalize 끔·켬)
- T2PC 운영 경로(조건 계층, compose, validate, compile)
- mock 실행
- P0 변환 불변식: 실행 결과·operator·의미 서명·평가 비교 정규형이 Full과 같음
- 보호 원본과 확장 지문
- 평가셋 4종(vendor100, valid98, sel154, aux_test_v1)과 질문·id·template·family 대조
- 보수 규칙: 한 장소 `od_role=both`를 두 장소로 펼친 형태도 대조

**초안 단계에서 고친 것(검토 전):**

- 4건(b006-24, 25, 42, 43)에 개인·법인택시 조건을 넣었다가 계약 위반으로 뺐다. `get_trip_count`는 `taxi_type`을 받지 않는다(UNCONSUMED_CONDITION).
- 질문 문장도 그에 맞게 고쳤다.

**mock 데이터 없음 5건(b006-13, 17, 22, 39, 41):**

- 계약과 compile은 통과한다. mock 실행기에 그 장소·조합의 응답 데이터가 없어 `UNSUPPORTED_COMBINATION`으로 끝난다.
- 결정 7(compile 정지 학습 문항 포함)과 같은 취지로 실패로 보지 않았다. 검토 때 그대로 둘지 정한다.

## 2. Gap C(scope 역조회): 기존 기준으로는 넣을 수 없다

- scope 역조회의 Full gold는 사용자 scope 하나와 값 없는 답 place 하나뿐이다. semantic family(`family_key`: 측정값·od_role·집계·dimension 구조)가 모든 문항에서 하나로 같다.
- 이 family는 평가셋 4종 모두에 있다. vendor100, valid98, sel154(n40, k21 등), aux_test_v1이 template·family 모두 겹친다.
- 문장·scope id를 바꿔도 family가 같으므로, 기존 오염 기준(질문·id·template·family)을 그대로 쓰면 이 유형은 학습에 넣을 수 없다.
- 선택지(사용자 결정):
  1. 기준을 지킨다. Gap C 없이 진행하고, scope 역조회 약점은 학습으로 다루지 않는다.
  2. 결정 15처럼 명시적 예외를 둔다. 예: "scope 역조회 family는 질문·id·template 겹침 0인 새 문장에 한해 학습 허용, 평가셋 결과는 이 family를 따로 보고".
     - 이 경우 평가 해석에서 이 family의 결과는 오염 가능성을 안고 따로 본다.
- 이번에는 10건을 모두 제외 상태로 두었다. 초안은 표에 남겨 결정에 쓸 수 있게 했다.

## 3. 분포 변화(`dataset_stats.json`)

| | v005 | batch006 통과분 | 예상 v006(통과분 모두 승인 시) |
|---|---:|---:|---:|
| 문항 | 111 | 43 | 154 |
| dimension_target pickup / dropoff / both | 13 / 11 / 7 | 22 / 18 / 3 | 35 / 29 / 10 |
| dimension h3 / sido / sigungu / emd / dayofweek | 3 / 5 / 13 / 23 / 3 | 25 / 6 / 8 / 4 / 0 | 28 / 11 / 21 / 27 / 3 |
| 장소 od_role pickup / dropoff / both | 9 / 16 / 20 | 14 / 14 / 2 | 23 / 30 / 22 |
| od_role과 dimension_target 동시 | 20 | 28 | 48 |
| 그중 서로 다른 끝 | 15 | 16 | 31 |
| bucket week / month | 14 / 9 | 0 / 0 | 14 / 9 |
| scope 역조회 | 0 | 0 | 0 |

**치우침(검토 때 볼 것):**

- 통과분의 dimension이 h3에 몰렸다(25/43). 이유는 다음과 같다.
  - 측정값 trip_count에서 emd·sigungu와 끝점·order의 조합 다수가 이미 보호 family다(평가셋에 같은 구조가 있음).
  - 계산 결과 dimension_target 조합 180개 중 60개가 막혀 있고, emd 조합이 가장 많이 막혔다.
- emd를 더 넣으려면 보호 family와 겹치지 않는 order·끝점 조합(예: 장소 없음 + pickup + 순위 없음)을 더 찾아야 한다.
- both grouping은 3건이다. 자연스러운 문장만 만들고 억지로 늘리지 않았다.

**대조쌍:** 12쌍(a1–a4, a7, a8, b1–b6)이다. 끝점 하나만 바꾼 최소 대조쌍이다. a5·a6 표시 후보는 대조 상대가 없다.

**표현 다양성(사건 표현, `~별` 없음):** "손님을 태운 위치", "내려준 위치", "하차가 가장 많이 몰린", "승차가 가장 드물었던", "택시를 탄 건수", "출발한 곳을 … 단위로 나눠", "어디서 타서 어디서 내렸는지 짝", "정확히 어디서 끝났는지", "들어온 손님들이 내린 곳" 등.

## 4. 검토 방법

- 각 행에서 다음 셋을 확인한다.
  1. 질문만 읽었을 때 장소 제한(od_role)과 결과 grouping(dimension_target)이 표의 요약과 같은지(`../contract_review/CONTRACT.md` 4절).
  2. 한국어가 자연스러운지.
  3. 날짜·순위·개수가 맞는지.
- 승인 칸에 "승인 / 수정(문장 또는 gold) / 제외"를 적는다. 수정은 batch005처럼 문장만 고치거나 gold를 고친 뒤 자동 검사를 다시 돌린다.
- 승인분만 `reviewed_gold_v006_p0`(v005 111 + 승인분, provenance `source=v005 | augment_dt_event | augment_od_vs_dt | augment_scope_reverse`)로 만든다. v005는 덮어쓰지 않는다.

## 5. 후보 표

P0 target 요약: 장소 `이름:od_role`, dt = dimension_target, dim = dimension.

<!-- review-table:begin -->
| id | gap | 대조쌍 | 질문 | P0 target 요약 | 자동 검사 | 비고 | 승인 |
|---|---|---|---|---|---|---|---|
| b006-01 | A | a1 | 지난주 손님을 태운 위치를 H3 셀 단위로 나눠서 보여줘 | 장소 없음, dt=pickup, dim=h3, date=last_week | 통과 |  | 대기 |
| b006-02 | A | a1 | 지난주 손님을 내려준 위치를 H3 셀 단위로 나눠서 보여줘 | 장소 없음, dt=dropoff, dim=h3, date=last_week | 통과 |  | 대기 |
| b006-03 | A | a2 | 이번 달 하차가 가장 많이 몰린 H3 셀 다섯 개는? | 장소 없음, dt=dropoff, dim=h3, top 5, date=this_month | 통과 |  | 대기 |
| b006-04 | A | a2 | 이번 달 승차가 가장 드물었던 H3 셀 다섯 개는? | 장소 없음, dt=pickup, dim=h3, bottom 5, date=this_month | 통과 |  | 대기 |
| b006-05 | A | a3 | 지난달 택시를 탄 건수가 가장 많은 시도는? | 장소 없음, dt=pickup, dim=sido, top 1, date=last_month | 통과 |  | 대기 |
| b006-06 | A | a3 | 지난달 택시에서 내린 건수가 가장 많은 시도는? | 장소 없음, dt=dropoff, dim=sido, top 1, date=last_month | 통과 |  | 대기 |
| b006-07 | A |  | 2026년 8월 실차 하차가 가장 적었던 시도 두 곳은? | 장소 없음, dt=dropoff, dim=sido, bottom 2, date=20260801-20260831 | 통과 |  | 대기 |
| b006-08 | A |  | 지난주 실차가 가장 적게 출발한 읍면동 세 곳은? | 장소 없음, dt=pickup, dim=emd, bottom 3, date=last_week | 통과 |  | 대기 |
| b006-09 | A |  | 지난주 어디서 타서 어디서 내렸는지를 동 단위 짝으로 묶었을 때 가장 드문 세 가지는? | 장소 없음, dt=both, dim=emd, bottom 3, date=last_week | 통과 |  | 대기 |
| b006-10 | A | a4 | 이번 주 실차가 출발한 곳을 시군구 단위로 나눠 건수를 보여줘 | 장소 없음, dt=pickup, dim=sigungu, date=this_week | 통과 |  | 대기 |
| b006-11 | A | a4 | 이번 주 실차가 도착한 곳을 시군구 단위로 나눠 건수를 보여줘 | 장소 없음, dt=dropoff, dim=sigungu, date=this_week | 통과 |  | 대기 |
| b006-12 | A | a5 | 지난달 대구 수성구에서 손님이 탄 위치를 H3 셀로 나눠 실차 건수를 보여줘 | 장소 수성구:pickup, dt=pickup, dim=h3, date=last_month | 통과 |  | 대기 |
| b006-13 | A |  | 이번 주 부산 수영구에서 승차가 가장 뜸했던 H3 셀 두 곳은? | 장소 수영구:pickup, dt=pickup, dim=h3, bottom 2, date=this_week | 통과 | mock 데이터 없음 | 대기 |
| b006-14 | A |  | 지난주 대구에서 실차가 출발한 곳을 구 단위로 나눠 보여줘 | 장소 대구:pickup, dt=pickup, dim=sigungu, date=last_week | 통과 |  | 대기 |
| b006-15 | A | a6 | 2026년 8월 부산에서 손님을 태운 건수가 가장 적은 구 두 곳은? | 장소 부산:pickup, dt=pickup, dim=sigungu, bottom 2, date=20260801-20260831 | 통과 |  | 대기 |
| b006-16 | A |  | 지난달 대구 달서구에 도착한 실차가 정확히 어디서 끝났는지 H3 셀 단위로 보여줘 | 장소 달서구:dropoff, dt=dropoff, dim=h3, date=last_month | 통과 |  | 대기 |
| b006-17 | A |  | 이번 달 부산 부산진구로 들어온 손님들이 내린 곳 중 가장 한산한 H3 셀 세 개는? | 장소 부산진구:dropoff, dt=dropoff, dim=h3, bottom 3, date=this_month | 통과 | mock 데이터 없음 | 대기 |
| b006-18 | A |  | 지난주 부산에 도착한 실차가 가장 많이 끝난 구 세 곳은? | 장소 부산:dropoff, dt=dropoff, dim=sigungu, top 3, date=last_week | 통과 |  | 대기 |
| b006-19 | A | a7 | 지난달 대구에서 하차가 가장 적었던 구는? | 장소 대구:dropoff, dt=dropoff, dim=sigungu, bottom 1, date=last_month | 통과 |  | 대기 |
| b006-20 | A | a7 | 지난달 대구에서 승차가 가장 적었던 구는? | 장소 대구:pickup, dt=pickup, dim=sigungu, bottom 1, date=last_month | 통과 |  | 대기 |
| b006-21 | A |  | 지난달 손님이 탄 셀과 내린 셀을 짝지었을 때 가장 흔한 조합 세 개는? | 장소 없음, dt=both, dim=h3, top 3, date=last_month | 통과 |  | 대기 |
| b006-22 | A |  | 지난주 동대구역으로 온 실차들이 어느 셀에서 출발해 어느 셀에서 끝났는지 짝으로 보면 가장 많은 두 가지는? | 장소 동대구역:dropoff, dt=both, dim=h3, top 2, date=last_week | 통과 | mock 데이터 없음 | 대기 |
| b006-23 | A |  | 2026년 9월 1일 하루 동안 실차가 어느 동에서 시작됐는지 건수로 보여줘 | 장소 없음, dt=pickup, dim=emd, date=20260901 | 통과 |  | 대기 |
| b006-24 | A | a8 | 2026년 9월 1일부터 7일까지 손님을 태운 H3 셀 중 가장 적었던 세 곳은? | 장소 없음, dt=pickup, dim=h3, bottom 3, date=20260901-20260907 | 통과 |  | 대기 |
| b006-25 | A | a8 | 2026년 9월 1일부터 7일까지 손님을 내려준 H3 셀 중 가장 적었던 세 곳은? | 장소 없음, dt=dropoff, dim=h3, bottom 3, date=20260901-20260907 | 통과 |  | 대기 |
| b006-26 | A |  | 이번 달 대구 수성구에서 손님을 태운 곳 가운데 실차가 가장 적게 시작된 H3 셀 세 곳은? | 장소 수성구:pickup, dt=pickup, dim=h3, bottom 3, date=this_month | 통과 |  | 대기 |
| b006-27 | B | b1 | 지난달 동성로에서 손님을 태운 택시가 손님을 내려준 위치를 H3 셀로 나눠 보여줘 | 장소 동성로:pickup, dt=dropoff, dim=h3, date=last_month | 통과 |  | 대기 |
| b006-28 | B | b1 | 지난달 동성로에서 내린 손님들이 어느 H3 셀에서 탔는지, 가장 많은 다섯 곳은? | 장소 동성로:dropoff, dt=pickup, dim=h3, top 5, date=last_month | 통과 |  | 대기 |
| b006-29 | B | b2 | 이번 주 동대구역에서 출발한 실차가 가장 많이 도착한 H3 셀 세 개는? | 장소 동대구역:pickup, dt=dropoff, dim=h3, top 3, date=this_week | 통과 |  | 대기 |
| b006-30 | B | b2 | 이번 주 동대구역에 도착한 실차가 출발한 곳 중 가장 드문 H3 셀 세 개는? | 장소 동대구역:dropoff, dt=pickup, dim=h3, bottom 3, date=this_week | 통과 |  | 대기 |
| b006-31 | B | b3 | 2026년 8월 대구에서 출발한 실차가 내린 시도 중 가장 적은 두 곳은? | 장소 대구:pickup, dt=dropoff, dim=sido, bottom 2, date=20260801-20260831 | 통과 |  | 대기 |
| b006-32 | B | b3 | 2026년 8월 부산에 도착한 실차가 어느 시도에서 출발했는지 가장 많은 세 곳은? | 장소 부산:dropoff, dt=pickup, dim=sido, top 3, date=20260801-20260831 | 통과 |  | 대기 |
| b006-33 | B |  | 지난달 대구로 들어온 실차를 출발한 시도 기준으로 나눠 보여줘 | 장소 대구:dropoff, dt=pickup, dim=sido, date=last_month | 통과 |  | 대기 |
| b006-34 | B |  | 지난달 대구 수성구에서 탄 손님들이 내린 곳 중 가장 드문 H3 셀 두 곳은? | 장소 수성구:pickup, dt=dropoff, dim=h3, bottom 2, date=last_month | 통과 |  | 대기 |
| b006-35 | B |  | 지난주 대구 중구에 도착한 실차가 어느 구에서 출발했는지 구 단위로 보여줘 | 장소 중구:dropoff, dt=pickup, dim=sigungu, date=last_week | 통과 |  | 대기 |
| b006-36 | B | b4 | 이번 달 부산 수영구에서 내린 손님들이 탄 동을 기준으로 실차 건수를 나눠 줘 | 장소 수영구:dropoff, dt=pickup, dim=emd, date=this_month | 통과 |  | 대기 |
| b006-37 | B | b4 | 이번 달 부산 수영구에서 탄 손님들이 내린 셀을 기준으로 실차 건수를 나눠 줘 | 장소 수영구:pickup, dt=dropoff, dim=h3, date=this_month | 통과 |  | 대기 |
| b006-38 | B |  | 이번 주 대구 중구 안에서만 오간 실차를 도착한 H3 셀 기준으로 나눠 보여줘 | 장소 중구:both, dt=dropoff, dim=h3, date=this_week | 통과 |  | 대기 |
| b006-39 | B |  | 지난달 부산진구 안에서 출발과 도착이 모두 이뤄진 운행 중 출발이 가장 많았던 H3 셀 세 개는? | 장소 부산진구:both, dt=pickup, dim=h3, top 3, date=last_month | 통과 | mock 데이터 없음 | 대기 |
| b006-40 | B | b5 | 지난주 대구에서 출발해 부산에 도착한 실차를 출발 지점의 H3 셀로 나눠 보여줘 | 장소 부산:dropoff, 대구:pickup, dt=pickup, dim=h3, date=last_week | 통과 |  | 대기 |
| b006-41 | B | b5 | 지난주 대구에서 출발해 부산에 도착한 실차가 끝난 곳을 H3 셀 기준으로 볼 때 가장 많은 다섯 곳은? | 장소 부산:dropoff, 대구:pickup, dt=dropoff, dim=h3, top 5, date=last_week | 통과 | mock 데이터 없음 | 대기 |
| b006-42 | B | b6 | 지난달 부산 광안리에서 태운 손님을 내려준 위치 중 가장 많은 H3 셀 세 개는? | 장소 광안리:pickup, dt=dropoff, dim=h3, top 3, date=last_month | 통과 |  | 대기 |
| b006-43 | B | b6 | 지난달 부산 광안리에 내려준 손님을 태웠던 위치 중 가장 많은 H3 셀 세 개는? | 장소 광안리:dropoff, dt=pickup, dim=h3, top 3, date=last_month | 통과 |  | 대기 |
| b006-44 | C |  | scope:district:2726000000은 어느 구를 가리켜? | scope `scope:district:2726000000` + 값 없는 답 place | 제외(겹침) | extended_family, extended_template, protected_semantic_family, protected_semantic_template, 평가셋:aux_test_v1, 평가셋:sel154, 평가셋:valid98, 평가셋:vendor100 | 대기 |
| b006-45 | C |  | scope:edge:11234가 무슨 장소인지 알려줘 | scope `scope:edge:11234` + 값 없는 답 place | 제외(겹침) | extended_family, extended_template, protected_semantic_family, protected_semantic_template, 평가셋:aux_test_v1, 평가셋:sel154, 평가셋:valid98, 평가셋:vendor100 | 대기 |
| b006-46 | C |  | 보고서에 scope:district:2729010100이라고 적혀 있는데 어느 동이야? | scope `scope:district:2729010100` + 값 없는 답 place | 제외(겹침) | extended_family, extended_template, protected_semantic_family, protected_semantic_template, 평가셋:aux_test_v1, 평가셋:sel154, 평가셋:valid98, 평가셋:vendor100 | 대기 |
| b006-47 | C |  | scope:gz:33212는 어디야? | scope `scope:gz:33212` + 값 없는 답 place | 제외(겹침) | extended_family, extended_template, protected_semantic_family, protected_semantic_template, 평가셋:aux_test_v1, 평가셋:sel154, 평가셋:valid98, 평가셋:vendor100 | 대기 |
| b006-48 | C |  | scope:district:2650000000의 지역 이름은? | scope `scope:district:2650000000` + 값 없는 답 place | 제외(겹침) | extended_family, extended_template, protected_semantic_family, protected_semantic_template, 평가셋:aux_test_v1, 평가셋:sel154, 평가셋:valid98, 평가셋:vendor100 | 대기 |
| b006-49 | C |  | scope:district:2623000000이 가리키는 곳 이름 좀 알려줘 | scope `scope:district:2623000000` + 값 없는 답 place | 제외(겹침) | extended_family, extended_template, protected_semantic_family, protected_semantic_template, 평가셋:aux_test_v1, 평가셋:sel154, 평가셋:valid98, 평가셋:vendor100 | 대기 |
| b006-50 | C |  | scope:edge:1742는 어떤 거리야? | scope `scope:edge:1742` + 값 없는 답 place | 제외(겹침) | extended_family, extended_template, protected_semantic_family, protected_semantic_template, 평가셋:aux_test_v1, 평가셋:sel154, 평가셋:valid98, 평가셋:vendor100 | 대기 |
| b006-51 | C |  | scope:district:2723510100은 무슨 동이지? | scope `scope:district:2723510100` + 값 없는 답 place | 제외(겹침) | extended_family, extended_template, protected_semantic_family, protected_semantic_template, 평가셋:aux_test_v1, 평가셋:sel154, 평가셋:valid98, 평가셋:vendor100 | 대기 |
| b006-52 | C |  | scope:district:2700000000이 어느 시도인지 알려 줘 | scope `scope:district:2700000000` + 값 없는 답 place | 제외(겹침) | extended_family, extended_template, protected_semantic_family, protected_semantic_template, 평가셋:aux_test_v1, 평가셋:sel154, 평가셋:valid98, 평가셋:vendor100 | 대기 |
| b006-53 | C |  | 집계 결과에 나온 scope:district:2650010400이 어디인지 이름으로 알려줘 | scope `scope:district:2650010400` + 값 없는 답 place | 제외(겹침) | extended_family, extended_template, protected_semantic_family, protected_semantic_template, 평가셋:aux_test_v1, 평가셋:sel154, 평가셋:valid98, 평가셋:vendor100 | 대기 |
<!-- review-table:end -->

## 6. 한계

- `_grounding_view`는 한 장소 `od_role=both`와 같은 장소 pickup·dropoff 두 표기를 grounding_ok에서 다르게 셀 수 있다(결정 65). 실행과 semantic correctness는 같다.
- 자동 검사에서 겹침 0인 것은 의미가 옳다는 증명이 아니다. paraphrase 계통은 사람이 본다(Protection 설명과 같음).
