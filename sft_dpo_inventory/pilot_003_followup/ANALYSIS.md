# pilot_003 후속: 기록으로 본 원인 분석

작성: 2026-10-14. 결정 85(Z). **모델을 부르지 않았다.** pilot_003의 기록(`../pilot_003/`)과 학습 데이터(`training/generated/thinking_pilot00{2,3}_t2pc`),
ignore 경로의 원문(`training/generated/pilot_003/raw/`)만 읽었다.
스크립트 `analyze_followup.py`, 결과 `analysis.json`(원문 문장 없음). 업체 100 문항은 설명에만 쓴다(결정 36).

결론 표시: **확인됨**(기록에서 직접 셀 수 있음) / **가능성 있음**(기록과 맞지만 다른 설명을 배제하지 못함) / **미확인**(기록으로 판단할 수 없음).

## a. aux_test_v1의 U 증가

pilot_003 aux 비교(`../pilot_003/aux_test/comparison.json`): U 3.92% → 8.82%, 차이 +4.90 [1.47, 8.82]. U 문항(표본 하나 이상) 5 → 9.

### a.1 새로 U가 된 5문항(문항당 4표본)

| 문항 | gold의 형태 | HF-base 정답 / U | HF-최종 정답 / U | HF-최종 U 표본의 U 종류와 차이 |
|---|---|---|---|---|
| final_v12/f02 | dimension sigungu, dimension_target pickup, 장소 dropoff | 3/4, 0 | 2/4, 1 | s1: U2:dimension_target. dimension emd(gold sigungu), dimension_target 빠짐. s2는 dimension만 틀린 조용한 오답 |
| final_v12/f31 | 실차 통행량(passage_count + taxi_status occupied) | 0/4, 0 | 0/4, 1 | s4: U1:taxi_status, U2:scope(…), U3:tool. measure trip_count, 장소 od_role both, aggregation sum, taxi_status 빠짐. 나머지 3표본은 aggregation 추가(정상 답변 분류의 오답) |
| final_v12/f33 | vicinity, taxi_status vacant | 3/4, 0 | 2/4, 1 | s3: U2:vicinity. vicinity 빠짐(나머지는 맞음). s1은 NO_MEASURE로 안전한 실패 |
| final_v12/f50 | 장소 서울, avg·month·max | 4/4, 0 | 3/4, 1 | s1: U2:scope. 장소(서울)가 빠짐 |
| final_v12/f53 | vicinity, aggregation max | 4/4, 0 | 3/4, 1 | s4: U2:vicinity. vicinity 빠짐 |

- **확인됨:** 5문항 모두 HF-최종에서 4표본 중 **1표본만** U다. 같은 문항의 다른 표본은 정답이거나 U가 아니다.
  aux의 U 증가(표본 8 → 18)는 소수 표본의 흔들림이 여러 문항에 퍼진 모양이다. 고정된 오류로 바뀐 문항은 없다.
- **확인됨:** HF-최종 U 표본의 종류는 vicinity 빠짐 2, dimension_target 빠짐 1, 장소 빠짐 1, 실차 오독 1이다. 한 종류로 모이지 않는다.

### a.2 세 셋의 U 종류(표본 수, HF-base → HF-최종)

| U 종류 | selection_v2(98×4) | aux_test_v1(51×4) | 업체 100(100×8, 설명에만) |
|---|---|---|---|
| U가 있는 문항·표본 | 18 → 29 | 8 → 18 | 31 → 32 |
| U1:taxi_status | 5 → 9 | 0 → 1 | 7 → 12 |
| U2:dimension_target | 12 → 13 | 6 → 10 | 16 → 19 |
| U2:scope(장소) | 3 → 9 | 0 → 2 | 8 → 12 |
| U2:scope_pickup / dropoff | 5 → 11 / 3 → 10 | 0 → 1 / 2 → 1 | 7 → 12 / 8 → 8 |
| U2:vicinity | 0 → 2 | 2 → 6 | 0 → 1 |
| U3:tool | 3 → 8 | 0 → 1 | 7 → 12 |
| U4:time | 1 → 0 | 0 → 0 | 2 → 0 |

(한 표본에 여러 종류가 붙을 수 있어 종류별 합은 표본 수보다 크다.)

- **확인됨:** selection_v2에서도 U 표본이 18 → 29로 늘었다(차이 +2.81 [−0.51, 6.38], `../pilot_003/selection_dpo.json`). CI가 0을 포함해 "증가 확인"은 아니지만
  방향은 aux와 같다. 업체 100은 31 → 32로 거의 같다(+0.12 [−1.88, 2.00]).
- **확인됨:** vicinity 빠짐은 HF-base에서 selection_v2·업체 100에 없었고 HF-최종에서 세 셋 모두에 나타났다(2, 6, 1표본).
  장소 범위 U(scope)와 U3:tool도 세 셋 모두에서 늘었다.
- **가능성 있음:** aux의 U 증가는 aux만의 현상이 아니라, 학습 모델이 장소·주변·dimension_target 같은 조건을 가끔 빠뜨리는 경향이 세 셋에 공통으로 생긴 것이다.
  aux에서 CI가 0을 넘은 것은 이 셋에서 해당 형태(vicinity 문항 등)가 많기 때문일 수 있다. 문항 구성 차이로 셋마다 크기가 다른 것은 기록으로 가르지 못한다.

### a.3 학습 데이터 형태(레코드 수, `analysis.json` `training_data_features`)

| 형태(gold JSON 기준) | pilot_002 SFT(HF / teacher) | pilot_003 SFT(HF / teacher) | pilot_002 DPO chosen | pilot_003 DPO chosen |
|---|---|---|---|---|
| vicinity | 84(40 / 44) | 116(44 / 72) | 46 | 54 |
| od_role both | 68(21 / 47) | 76(21 / 55) | 40 | 40 |
| dimension_target | 99(33 / 66) | 120(42 / 78) | 82 | 106 |
| 장소 없음 | 52(20 / 32) | 52(20 / 32) | 59 | 59 |
| taxi_status occupied | 0 | 24(0 / 24) | 0 | 0 |
| taxi_status vacant | 2(2 / 0) | 18(6 / 12) | 4 | 24 |

- **확인됨:** batch006로 vicinity·dimension_target·실차 대조 레코드가 늘었고, 늘어난 SFT는 대부분 teacher 출처다(vicinity +32 중 teacher +28).
- **가능성 있음:** f31 s4의 "장소 od_role both + trip_count"는 batch006 대조 묶음(b006-08, 결정 80)의 장소 형태와 같다. 다만 od_role both 레코드는 68 → 76으로 조금 늘었을 뿐이다.
- **미확인:** vicinity 레코드가 늘었는데 vicinity 빠짐이 생긴 이유. 학습 데이터에서 vicinity를 빠뜨린 응답을 배운 흔적은 레코드 수로 보이지 않는다.
  sampling 4–8표본 중 1표본 수준의 흔들림이라, 원인을 레코드 형태로 가르려면 그 형태의 문항을 더 많이 재야 한다.

## b. 실차 통행량이 고쳐지지 않은 이유

### b.1 HF 모델의 thinking(첫 계획 호출, 원문은 ignore 경로, 수만 적음)

| 문항 | 셀 | 표본 | "real trip"으로 옮김 | 실차 ↔ trip_count를 잇는 문장 | occupied 언급 | 첫 계획 measure | 첫 계획 taxi_status occupied |
|---|---|---:|---:|---:|---:|---|---:|
| selection_v2 old44/g02 | HF-base | 4 | 4 | 4 | 0 | passage 2, trip 2 | 0 |
| | SFT 920 | 4 | 2 | 4 | 0 | trip 4 | 0 |
| | 최종 DPO 174 | 4 | 4 | 4 | 0 | trip 4 | 0 |
| selection_v2 old44/g04 | HF-base | 4 | 1 | 2 | 1 | trip 3, passage 1 | 0 |
| | SFT 920 | 4 | 1 | 3 | 0 | trip 2, passage 2 | 0 |
| | 최종 DPO 174 | 4 | 0 | 3 | 1 | trip 2, passage 2 | 0 |
| selection_v2 indepv2/n33 | HF-base | 4 | 2 | 0 | 0 | trip 4 | 0 |
| | SFT 920 | 4 | 1 | 0 | 0 | trip 4 | 0 |
| | 최종 DPO 174 | 4 | 3 | 1 | 0 | trip 4 | 0 |
| valid98 h30(greedy) | SFT 920 | 1 | 0 | 0 | 1 | trip | 1 |
| | 최종 DPO 174 | 1 | 0 | 0 | 0 | trip | 0 |

(정규식 판정: `analyze_followup.py`의 `REAL_TRIP`, `TRIP_READ`, `OCCUPIED`. 같은 줄 안에서만 본다.)

- **확인됨:** 학습 뒤에도 HF-최종의 thinking은 "실차"를 trip(real trip, trip_count)으로 읽는다. 첫 계획에 taxi_status occupied를 넣은 경우는
  selection_v2 세 문항 12표본 중 0이다. 요지: "실차는 실제 운행(trip)이므로 trip_count"로 추론하고, passage_count를 언급하는 경우에도
  "실차"를 근거로 trip_count를 고른다(한 표본은 지침에 "실차 통행량"이 passage_count라고 적혀 있다고 쓴 뒤에도 trip_count를 골랐다).
- **확인됨:** 학습 전후로 이 비율이 거의 같다(g02는 학습 뒤 passage 2 → 0으로 오히려 trip 쪽이 늘었다).
- valid98 h30: SFT는 첫 계획에 occupied를 넣었지만 measure는 trip_count였다. 최종은 둘 다 틀렸다. 두 모델 모두 최종 결과가 틀렸다(`../pilot_003/REPORT.md` 7절).

### b.2 학습 데이터의 실차(taxi_status occupied) 레코드

| 출처 | SFT 레코드(질문) | DPO 쌍 |
|---|---:|---:|
| HF 자체 trace | 0(0) | 0 |
| teacher(qwen3.8:27b, batch006) | 24(6) | – |
| 합계 | 24(6) | **0** |

- **확인됨:** occupied 변형 6질문은 HF base가 8표본 중 한 번도 맞히지 못해(`../pilot_003/traces/batch006/summary.json`) HF trace가 없다. 그래서 SFT는 teacher만,
  DPO 쌍은 0이다. 결정 48·50·81로 교차 DPO(teacher chosen × HF rejected)는 만들지 않았다.
- **확인됨:** SFT 손실은 `json_only`(결정 24)라 teacher 레코드의 thinking은 손실 없이 입력으로만 쓰였다(`../pilot_003/data/loss_tokens.json`: 460/460 레코드에서 손실 token이 `</think>` 뒤 JSON+EOS에만 있음).
  DPO는 `full_response`지만 occupied 쌍이 없다.

### b.3 가설: `json_only`에서 teacher 추론은 입력으로만 쓰여 8b 자신의 추론이 바뀌지 않았다

- 기록과 맞는 점:
  - 학습 뒤에도 thinking의 "실차 → trip" 추론이 그대로다(b.1).
  - 실차 형태에서 추론을 직접 바꾸는 신호(teacher thinking 손실, DPO 쌍)가 학습에 없었다(b.2).
  - 같은 batch006에서 HF 정답 trace가 있어 DPO 쌍이 생긴 다른 변형(plain, trip, vacant)과 달리, occupied만 DPO가 0이다.
- 배제하지 못한 설명:
  - occupied 레코드가 6질문 24개로 적다(전체 SFT 460 중 5.2%).
  - 평가 문항의 문장 형태(묶음 없는 "실차 통행량", 결정 81)가 대조 묶음 형태와 달라 옮겨 가지 않았을 수 있다.
  - JSON만 학습해도 thinking 뒤 JSON을 맞히도록 배우는데, 추론 때 8b가 스스로 쓴 thinking이 "trip"으로 결론을 내리면 그 결론을 따른다. 이 효과와 양 부족을 기록으로 가르지 못한다.
- **판단: 가능성 있음.** 기록은 가설과 맞지만, 표본 수와 문장 형태 차이를 배제하지 못한다. 확인하려면 학습 조건을 바꾼 비교가 필요하다(결정 86(AA)의 teacher `full_response`가 그 조건이다. 이번에는 학습하지 않는다).

## 요약

| 질문 | 결론 |
|---|---|
| aux U 증가의 모양 | **확인됨:** 5문항 각 1/4표본의 흔들림. 종류는 vicinity 2, 장소 1, dimension_target 1, 실차 1 |
| U 증가가 aux만의 것인가 | **가능성 있음:** selection_v2도 같은 방향(18 → 29, CI가 0 포함), 업체 100은 거의 같음. vicinity 빠짐은 세 셋 모두에 새로 나타남(확인됨) |
| 학습 데이터 형태와의 관계 | **미확인:** vicinity·dimension_target 레코드는 오히려 늘었다. f31의 od_role both는 batch006 형태와 같다(가능성 있음) |
| HF-최종이 여전히 "실차 → trip"으로 추론하는가 | **확인됨** |
| occupied 학습 신호 | **확인됨:** SFT teacher 24(손실은 JSON만), HF 0, DPO 0 |
| `json_only` 때문에 추론이 바뀌지 않았다는 가설 | **가능성 있음** |
