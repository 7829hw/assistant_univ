# 계약 표기(한 장소 od_role both + dimension_target both)의 실행 여부(결정 63 E-2, 2026-10-09)

모델 호출 없음. 코드와 라벨은 고치지 않았다. 판단은 사람이 한다.

- 스크립트: `canonical_both.py`. 결과: `canonical_both.json`(mock provider), `canonical_both_reference.json`(reference provider 대조).
- 방법:
  - 고정한 planner 출력(JSON)을 `ReplayClient`로 넣는다.
  - pilot_002 평가와 같은 pipeline(`provider_eval.make_pipeline`: flat, 조건 계층 켬, condition_notes 끔, 기준일 2026-09-25, provider mock)으로 돌린다.
  - 조건 계층이 질문 문장을 읽으므로, 변형마다 그 grounding과 맞는 질문 문장을 틀로 만든다.
  - 093은 HF-최종의 최종 grounding만 입력으로 썼다. 질문 원문은 결과에 넣지 않았다(업체 100 문항, 작업 지시 4의 대상).
- 실행 의미 코드 지문은 실행 전후 모두 `791c4a68`이다.

## 1. 결론

**같은 조건에서 계약 표기(한 장소 both)는 옛 표기(같은 장소를 pickup·dropoff 두 개로 적음), 한쪽 끝(pickup) 표기와 결과가 모두 같았다.**
- 격자 90칸(장소 단위 3 × dimension 5 × order·limit 유무 2 × 날짜 형식 3) 모두에서 같다. 표기 때문에 결과가 달라진 칸은 0이다.
- 멈춘 경우는 모두 표기와 무관한 조건 때문이다(3절).

**093 HF-최종이 멈춘 이유는 계약 표기가 아니라 질문에 없는 `aggregation: min`이다.**
- 멈춘 코드는 `UNCONSUMED_CONDITION`이고, 소비되지 않은 조건은 `aggregation`이다(`error_context.unconsumed`). 실행 전 합성 단계에서 멈췄다.
- `aggregation`만 빼면 같은 grounding(role COND든 SUBCOND든)이 실행된다.
  - 호출: `get_trip_count`, `scope_pickup = scope_dropoff = 부산 scope`, `dimension emd`, `dimension_target both`, `order bottom`, `limit 2`, `date this_month`.
  - gold의 옛 표기(장소 두 개)도 같은 호출을 만든다.
- 093 HF-최종의 첫 출력에는 od_role이 없었고(role COND), 재질의 응답이 `od_role both`를 붙였다. `aggregation: min`은 첫 출력부터 있었다.
- b004-24 정답 grounding(수성구, 9월 범위, emd, top 3)도 그대로 실행된다.

## 2. 093과 b004-24(mock)

| 경우 | 결과 | 코드 | 비고 |
|---|---|---|---|
| 093 HF-최종 최종 grounding 그대로(role COND, both, dt both, bottom 2, aggregation min) | unsupported | UNCONSUMED_CONDITION | unconsumed: aggregation, 측정 호출 없음 |
| 위에서 aggregation만 뺌(role COND) | answered | – | 호출은 위 1절과 같음 |
| aggregation 뺌, role SUBCOND(계약 표기 그대로) | answered | – | 같은 호출 |
| role SUBCOND + aggregation min | unsupported | UNCONSUMED_CONDITION | role과 무관 |
| gold 옛 표기(부산 pickup·dropoff 두 개, dt both) | answered | – | 같은 호출 |
| b004-24 정답 grounding 그대로 | answered | – | `get_trip_count`, 수성구 scope 양끝, emd, both, top 3, 20260901-20260930 |

## 3. 조건을 하나씩 바꾼 표(mock, role SUBCOND, aggregation 없음)

칸마다 날짜 형식 3개(`this_month`, `20260901-20260930`, `20260915`) × order·limit(bottom 2) 있음·없음 = 6개를 돌렸다.
세 표기(both, 옛 표기, pickup) 모두 6개 결과가 같아서 한 칸에 하나로 적는다.
장소: 시도 `부산`, 시군구 `대구 수성구`, 읍면동 `대구 중구 동인동`(mock 장소 사전에 있는 이름).

| 장소 단위 \ dimension | emd | sigungu | sido | h3 | dayofweek |
|---|---|---|---|---|---|
| 시도(부산) | 실행 | 실행 | 실행 | 멈춤 UNSUPPORTED_COMBINATION(실행 단계) | 멈춤 INVALID_PARAM_VALUE(합성 단계) |
| 시군구(수성구) | 실행 | 실행 | 멈춤 UNSUPPORTED_COMBINATION | 실행 | 멈춤 INVALID_PARAM_VALUE |
| 읍면동(동인동) | 실행 | 멈춤 UNSUPPORTED_COMBINATION | 멈춤 UNSUPPORTED_COMBINATION | 멈춤 UNSUPPORTED_COMBINATION | 멈춤 INVALID_PARAM_VALUE |

- **날짜 형식과 order·limit 유무는 결과를 바꾸지 않았다**(모든 칸에서 6개가 같음).
- **멈춤의 원인(표기와 무관):**
  - `INVALID_PARAM_VALUE`(dayofweek): 합성 단계 `operator_mapping._check_param_contract`. `get_trip_count`의 `dimension` 허용값에 dayofweek가 없다. 측정 호출 전에 멈춘다.
  - `UNSUPPORTED_COMBINATION`: 실행 단계. `get_trip_count` 호출까지 만들어진 뒤 mock 도구(`mock_responses.py` `mock_get_trip_count`)가
    "지정한 승하차 scope와 dimension에 해당하는 후보가 없습니다"를 돌려준다.
    - 장소보다 같거나 넓은 단위로 묶는 경우다(읍면동 장소를 시군구·시도로, 시군구 장소를 시도로). h3는 mock 고정 자료에 후보가 있는 장소에서만 실행된다(수성구).
    - mock의 고정 자료에 따른 결과다. 실제 도구에서도 같은지는 이 확인으로 알 수 없다.
    - 시도 장소를 시도로 묶는 칸(부산 × sido)은 mock에서 실행됐다.
- **dimension_target 변경**(부산, emd, bottom 2, 이번 달): pickup·dropoff·생략 모두 실행.
- **dimension 없음**(한 장소 both, 단일 값): 시도·시군구·읍면동 모두 both·옛 표기 모두 실행.

### reference provider 대조(`canonical_both_reference.json`)

- 같은 격자를 reference provider로 돌렸다. dayofweek 칸은 같은 `INVALID_PARAM_VALUE`(합성 단계)였다.
- 나머지는 모두 장소 조회에서 `NOT_FOUND`였다(부산·수성구·동인동 모두). reference provider의 장소 사전에 이 이름이 없어서다.
- 그래서 실행 단계의 대조로는 쓸 수 없다. 표기별 차이는 여기서도 0이다.

## 4. 학습 데이터의 같은 조건 정답 수(`reviewed_gold_v005_t2pc`)

sft_train 111개, dpo_train 75개(chosen). valid 파일은 비어 있다.

| 조건 | sft_train | dpo_train(chosen) |
|---|---:|---:|
| 한 장소 od_role both | 20 | 11 |
| 그중 dimension_target both(계약 표기 그대로) | **1**(b004-24, 시군구 + emd) | 0 |
| 한 장소 both + dimension | 6: emd 5(시군구 장소: b004-24, b005-31·32·38·39), sigungu 1(시도 `대구`: b005-42) | 3: emd 2, sigungu 1 |
| 한 장소 both + 시도 장소 + emd(093과 같은 조합) | 0 | 0 |
| 같은 장소 pickup·dropoff 두 개(옛 표기) | 0 | 0 |
| trip_count + aggregation | 0 | 0 |
| trip_count + dimension dayofweek | 0 | 0 |

- 093에서 멈춘 원인(trip_count + 질문에 없는 aggregation)과 같은 정답은 학습 데이터에 0개다. aggregation을 넣지 않는 정답은 모든 trip_count 정답이 그렇다.
- 계약 표기 자체(both + dt both)의 정답은 1개다.

## 5. 사람이 판단할 근거

- **계약과 코드의 불일치인가:** 이번 확인에서 계약 표기 때문에 멈춘 경우는 없다. 같은 조건의 옛 표기와 결과가 모두 같다.
  - 그러므로 "계약 표기가 실행되지 않는다"는 근거는 찾지 못했다.
- **멈추는 경우가 의도한 지원 범위인가:** 두 종류가 있다. 둘 다 표기와 무관하다.
  - dayofweek로 실차 구간을 묶는 것: 합성 단계에서 막는다(도구 명세의 허용값). 학습 정답 0개.
  - 장소보다 같거나 넓은 단위로 묶는 것, 그리고 일부 h3: mock 도구의 고정 자료가 막는다. 실제 도구의 지원 범위는 이 확인으로 알 수 없다. 학습 정답 0개.
- **093:** 멈춘 원인은 질문에 없는 aggregation이다. U 판정 문서(결정 62)의 "093 gold는 옛 표기"와는 별개의 사실이다.
