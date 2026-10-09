# pilot_002 운영 경로 U 문항 검토

`build_u_review.py`가 기록에서 만든다(모델 호출 없음, 판정은 바꾸지 않음). 사람 검토용이다. thinking 원문은 넣지 않았다.

- 대상: 업체 100 Ollama-최종의 U 9문항. 참고로 Ollama-SFT에만 있는 U 2문항(044, 085)을 붙였다.
- 셀 기록: E `sft_dpo_inventory/pilot_prep_003/ollama/E.json`, B-conv `sft_dpo_inventory/pilot_prep_003/ollama/B-conv.json`, HF-최종 `sft_dpo_inventory/pilot_002/vendor100/HF-final.json`, Ollama-최종 `sft_dpo_inventory/pilot_002/vendor100/Ollama-final.json`, Ollama-SFT `sft_dpo_inventory/pilot_002/vendor100/Ollama-sft.json`, HF-SFT `sft_dpo_inventory/pilot_002/vendor100/HF-sft.json`.
- 분류 코드는 `vendor100/judge.py`와 같다(`baseline_conditions_001/compare_cells.py`, `evaluation/grounding_v13/report.py`의 `unacceptable`).
  - U1: 정답 호출에 있는 모집단 조건(date·time·taxi_type·taxi_status·dimension)을 버리고 답함. 또는 그 조건 때문에 멈춰야 하는 문항에서 답함.
  - U2: 범위 인자(scope, scope_pickup, scope_dropoff, dimension_target)가 정답 호출과 다름, 또는 장소 출처·주변 오류.
  - U3: 측정 도구(tool) 또는 metric이 정답 호출과 다름. U4: 모집단 조건 값이 바뀜.
  - 판정은 기대 결과가 answered인 문항에서 모델이 answered로 끝났을 때 최종 Tool 호출을 정답 호출과 비교한 결과다.
- family: 결정 54 겹침 검사(`data/overlap.json`)에서 pilot_002 학습 질문과 family가 같은 업체 100 문항. template 겹침도 따로 적었다.

## 요약

| 문항 | 질문 | family(결정 54) | E | B-conv | HF-최종 | Ollama-최종 | Ollama-SFT | 오류 유형(Ollama 셀) | 같은 adapter의 HF 셀은 U 아님·Ollama만 U |
|---|---|---|---|---|---|---|---|---|---|
| 013 | 2026년 6월 4일 대구 동성로의 실차 통행량은? | 밖 | **U** | **U** | 정상 | **U** | **U** | 조건 누락(taxi_status); 측정값(도구 get_passage_count → get_trip_count); 범위·장소(도구 변경에 따른 scope 인자) | ✔ |
| 016 | 대구 수성구에서 출발한 실차 구간의 도착 읍면동 상위 3곳은? | 안 | 정상 | 정상 | 정상 | **U** | 정상 | 집계(묶음 끝점 dimension_target 누락) | ✔ |
| 026 | 대구에서 출발해 부산에 도착한 실차 중 대구의 승차 읍면동 상위 2곳은? | 밖 | 정상 | 정상 | 정상 | **U** | **U** | 집계(묶음 끝점 dimension_target 누락) | ✔ |
| 037 | 지난달 대구 수성구의 읍면동별 실차 택시 통행량 중 가장 많은 곳은? | 안 | 안전한 실패 | 안전한 실패 | 안전한 실패 | **U** | **U** | 조건 누락(taxi_status); 측정값(도구 get_passage_count → get_trip_count); 범위·장소(도구 변경에 따른 scope 인자) | ✔ |
| 040 | 휴일 오후 6시부터 8시까지 부산의 승차 읍면동 중 가장 많은 곳은? | 밖 | 정상 | **U** | 정상 | **U** | **U** | 집계(묶음 끝점 dimension_target 누락) | ✔ |
| 041 | 이번 달 부산에서 하차 건수가 적은 읍면동 하위 2곳은? | 밖 | 정상 | 정상 | 정상 | **U** | **U** | 범위·장소(출발·도착 역할) | ✔ |
| 054 | 부산 광안동의 실차 택시 통행량은? | 밖 | **U** | 정상 | 안전한 실패 | **U** | 정상 | 조건 누락(taxi_status); 측정값(도구 get_passage_count → get_trip_count); 범위·장소(도구 변경에 따른 scope 인자) | ✔ |
| 074 | 휴일 부산 초읍동 어린이대공원 주변의 실차 택시 통행량은? | 밖 | 정상 | **U** | 안전한 실패 | **U** | 정상 | 조건 누락(taxi_status); 측정값(도구 get_passage_count → get_trip_count); 범위·장소(도구 변경에 따른 scope 인자) | ✔ |
| 093 | 이번 달 부산 안에서 이용이 적은 읍면동 간 OD 노선 하위 2개는? | 안, template | 안전한 실패 | **U** | 안전한 실패 | **U** | 정상 | 범위·장소(출발·도착 역할) | ✔ |
| 044(SFT만, 참고) | 지난 주 대구에서 승차 건수가 적은 읍면동 하위 2곳은? | 밖 | 정상 | 정상 | 정상 | 정상 | **U** | 집계(묶음 끝점 dimension_target 누락); 집계(dimension emd → sigungu, U 아님) | ✔(HF-SFT 정상) |
| 085(SFT만, 참고) | 이번 주 대구에 도착한 실차의 하차 읍면동을 많은 순서로 3곳 알려줘. | 밖 | 정상 | 정상 | 정상 | 정상 | **U** | 집계(묶음 끝점 dimension_target 누락) | ✔(HF-SFT 정상) |

- **같은 adapter인데 HF-최종에서는 U가 아니고 Ollama-최종에서만 U인 문항: 9/9**(013, 016, 026, 037, 040, 041, 054, 074, 093).
  HF-최종에서 이 문항들의 분류: 013 정상, 016 정상, 026 정상, 037 안전한 실패, 040 정상, 041 정상, 054 안전한 실패, 074 안전한 실패, 093 안전한 실패.
- Ollama-최종 U 9문항 중 직접 변환한 base(B-conv)에서도 U인 문항: 013, 040, 074, 093.
- E에서도 U인 문항: 013, 054.

## 같은 adapter의 HF와 Ollama grounding 비교(기록 그대로)

측정 대상(MEASURE subtype), 장소의 출발·도착 역할(od_role), 묶음 끝점(factors.dimension_target), taxi_status, 결과.
SFT 참고 문항은 HF-SFT와 Ollama-SFT를 비교한다. 원인 판단은 하지 않는다.

| 문항 | gold | HF | Ollama |
|---|---|---|---|
| 013 | passage_count / od - / dt - / status occupied | HF-최종: passage_count / od - / dt - / status occupied / answered | Ollama-최종: trip_count / od both / dt - / status - / answered |
| 016 | trip_count / od pickup / dt dropoff / status - | HF-최종: trip_count / od pickup / dt dropoff / status - / answered | Ollama-최종: trip_count / od pickup / dt - / status - / answered |
| 026 | trip_count / od pickup,dropoff / dt pickup / status - | HF-최종: trip_count / od pickup,dropoff / dt pickup / status - / answered | Ollama-최종: trip_count / od pickup,dropoff / dt - / status - / answered |
| 037 | passage_count / od - / dt - / status occupied | HF-최종: trip_count / od - / dt - / status - / failed:MISSING_RELATION_QUALIFIER | Ollama-최종: trip_count / od pickup / dt - / status - / answered |
| 040 | trip_count / od pickup / dt pickup / status - | HF-최종: trip_count / od pickup / dt pickup / status - / answered | Ollama-최종: trip_count / od pickup / dt - / status - / answered |
| 041 | trip_count / od dropoff / dt dropoff / status - | HF-최종: trip_count / od dropoff / dt dropoff / status - / answered | Ollama-최종: trip_count / od pickup / dt dropoff / status - / answered |
| 054 | passage_count / od - / dt - / status occupied | HF-최종: trip_count / od - / dt - / status - / failed:MISSING_RELATION_QUALIFIER | Ollama-최종: trip_count / od pickup / dt - / status - / answered |
| 074 | passage_count / od - / dt - / status occupied | HF-최종: trip_count / od - / dt - / status - / failed:MISSING_RELATION_QUALIFIER | Ollama-최종: trip_count / od both / dt - / status - / answered |
| 093 | trip_count / od pickup,dropoff / dt both / status - | HF-최종: trip_count / od both / dt both / status - / unsupported:UNCONSUMED_CONDITION | Ollama-최종: trip_count / od pickup / dt - / status - / answered |
| 044 | trip_count / od pickup / dt pickup / status - | HF-SFT: trip_count / od pickup / dt pickup / status - / answered | Ollama-SFT: trip_count / od pickup / dt - / status - / answered |
| 085 | trip_count / od dropoff / dt dropoff / status - | HF-SFT: trip_count / od dropoff / dt dropoff / status - / answered | Ollama-SFT: trip_count / od dropoff / dt - / status - / answered |

기록에서 보이는 사실(원인 판단 아님):

- 정답에 묶음 끝점(dimension_target)이 있고 HF grounding에는 있는데 Ollama grounding에서 빠진 문항: 016, 026, 040, 093, 044, 085.
- 정답이 `passage_count` + `taxi_status=occupied`(실차 통행량)인 문항: 013, 037, 054, 074.
  - HF-최종: 013 정답 구조로 답함, 037 failed:MISSING_RELATION_QUALIFIER, 054 failed:MISSING_RELATION_QUALIFIER, 074 failed:MISSING_RELATION_QUALIFIER.
  - Ollama-최종: 013 trip_count / od both로 answered, 037 trip_count / od pickup로 answered, 054 trip_count / od pickup로 answered, 074 trip_count / od both로 answered.


## 013

- 질문: 2026년 6월 4일 대구 동성로의 실차 통행량은?
- 결정 54: family 밖
- 기대 결과: answered
- 정답 호출: `get_place_scope(name=동성로, region=대구)` → `get_passage_count(scope=$resolve.scope, date=20260604, taxi_status=occupied)`
- gold grounding: `LOCATION/place[SUBCOND]={"name": "동성로", "region": "대구"}; EVENT/passage[SUPPORT]; AMOUNT/passage_count[MEASURE] | factors: date=20260604, taxi_status=occupied`

| 셀 | 분류 | grounding_ok | 결과 | 멈춘 코드 | gold와 다른 grounding 항목 | thinking 글자 수(호출별) | U flag |
|---|---|---|---|---|---|---|---|
| E | **U** | X | answered | - | factor:taxi_status, measure, places | plan:3116, repair:1225 | U1:taxi_status, U2:scope, U2:scope_pickup, U3:tool |
| B-conv | **U** | X | answered | - | factor:aggregation_spec, factor:taxi_status, measure, places | plan:4864, repair:1766 | U1:taxi_status, U2:scope, U2:scope_pickup, U3:tool |
| HF-최종 | 정상 | O | answered | - | - | plan:4209 | - |
| Ollama-최종 | **U** | X | answered | - | factor:taxi_status, measure, places | plan:None, plan:2777, repair:6604 | U1:taxi_status, U2:scope, U2:scope_dropoff, U2:scope_pickup, U3:tool |
| Ollama-SFT | **U** | X | answered | - | factor:taxi_status, measure, places | plan:1608, repair:4293 | U1:taxi_status, U2:scope, U2:scope_dropoff, U2:scope_pickup, U3:tool |

셀별 grounding:

- E: `LOCATION/place[SUBCOND, pickup]={"name": "동성로", "region": "대구"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=20260604`
- B-conv: `LOCATION/place[SUBCOND, pickup]={"name": "동성로", "region": "대구"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=20260604, aggregation=sum | aggregation: {"inner": "sum"}`
- HF-최종: `LOCATION/place[SUBCOND]={"name": "동성로", "region": "대구"}; EVENT/passage[SUPPORT]; AMOUNT/passage_count[MEASURE] | factors: date=20260604, taxi_status=occupied`
- Ollama-최종: `LOCATION/place[SUBCOND, both]={"name": "동성로", "region": "대구"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=20260604`
- Ollama-SFT: `LOCATION/place[SUBCOND, both]={"name": "동성로", "region": "대구"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=20260604`

Ollama-최종의 Tool 호출과 최종 답:

1. `get_place_scope(name=동성로, region=대구, include_vicinity=False) → "scope:edge:1742"`
2. `get_trip_count(scope_pickup=scope:edge:1742, scope_dropoff=scope:edge:1742, date=20260604) → {"count": 20}`

- 최종 답: 대구 동성로 20260604 실차 구간 건수: 20건

U로 분류된 이유(Ollama-최종):

- 측정 도구가 정답과 다르다(`tool_ok` false → U3:tool): 정답 마지막 호출 `get_passage_count`, 모델 `get_trip_count`.
- 인자 `scope`: 정답 `scope:edge:1742` → 모델 `None` (U2:scope).
- 인자 `scope_dropoff`: 정답 `None` → 모델 `scope:edge:1742` (U2:scope_dropoff).
- 인자 `scope_pickup`: 정답 `None` → 모델 `scope:edge:1742` (U2:scope_pickup).
- 인자 `taxi_status`: 정답 `occupied` → 모델 `None` (U1:taxi_status).
- Ollama-SFT도 U(U1:taxi_status, U2:scope, U2:scope_dropoff, U2:scope_pickup, U3:tool).

## 016

- 질문: 대구 수성구에서 출발한 실차 구간의 도착 읍면동 상위 3곳은?
- 결정 54: family 안
- 기대 결과: answered
- 정답 호출: `get_place_scope(name=수성구, region=대구)` → `get_trip_count(scope_pickup=$pickup.scope, dimension=emd, dimension_target=dropoff, order=top, limit=3)`
- gold grounding: `LOCATION/place[SUBCOND, pickup]={"name": "수성구", "region": "대구"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: dimension=emd, dimension_target=dropoff, order=top, limit=3`

| 셀 | 분류 | grounding_ok | 결과 | 멈춘 코드 | gold와 다른 grounding 항목 | thinking 글자 수(호출별) | U flag |
|---|---|---|---|---|---|---|---|
| E | 정상 | O | answered | - | - | plan:2302 | - |
| B-conv | 정상 | O | answered | - | - | plan:1580 | - |
| HF-최종 | 정상 | O | answered | - | - | plan:1775 | - |
| Ollama-최종 | **U** | X | answered | - | factor:dimension_target | plan:1930 | U2:dimension_target |
| Ollama-SFT | 정상 | O | answered | - | - | plan:3895 | - |

셀별 grounding:

- E: `LOCATION/place[SUBCOND, pickup]={"name": "수성구", "region": "대구"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: dimension=emd, dimension_target=dropoff, order=top, limit=3`
- B-conv: `LOCATION/place[SUBCOND, pickup]={"name": "수성구", "region": "대구"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: dimension=emd, dimension_target=dropoff, order=top, limit=3`
- HF-최종: `LOCATION/place[SUBCOND, pickup]={"name": "수성구", "region": "대구"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: dimension=emd, dimension_target=dropoff, order=top, limit=3`
- Ollama-최종: `LOCATION/place[SUBCOND, pickup]={"name": "수성구", "region": "대구"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: dimension=emd, order=top, limit=3`
- Ollama-SFT: `LOCATION/place[SUBCOND, pickup]={"name": "수성구", "region": "대구"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: dimension=emd, order=top, limit=3, dimension_target=dropoff`

Ollama-최종의 Tool 호출과 최종 답:

1. `get_place_scope(name=수성구, region=대구, include_vicinity=False) → "scope:district:2726000000"`
2. `get_trip_count(scope_pickup=scope:district:2726000000, dimension=emd, limit=3, order=top) → [{"pickup": "두산동", "dropoff": "동인동", "count": 20}, {"pickup": "두산동", "dropoff": "중앙로동", "count": 20}, {"pickup": "두산동", "dropoff": "태평로동", "count": 20}]`

- 최종 답: 대구 수성구 출발 읍면동별 상위 3개 실차 구간 건수 / - 두산동 → 동인동: 20건 / - 두산동 → 중앙로동: 20건 / - 두산동 → 태평로동: 20건

U로 분류된 이유(Ollama-최종):

- 인자 `dimension_target`: 정답 `dropoff` → 모델 `None` (U2:dimension_target).

## 026

- 질문: 대구에서 출발해 부산에 도착한 실차 중 대구의 승차 읍면동 상위 2곳은?
- 결정 54: family 밖
- 기대 결과: answered
- 정답 호출: `get_place_scope(name=대구)` → `get_place_scope(name=부산)` → `get_trip_count(scope_pickup=$pickup.scope, scope_dropoff=$dropoff.scope, dimension=emd, dimension_target=pickup, order=top, limit=2)`
- gold grounding: `LOCATION/place[SUBCOND, pickup]={"name": "대구", "region": ""}; LOCATION/place[SUBCOND, dropoff]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: dimension=emd, dimension_target=pickup, order=top, limit=2`

| 셀 | 분류 | grounding_ok | 결과 | 멈춘 코드 | gold와 다른 grounding 항목 | thinking 글자 수(호출별) | U flag |
|---|---|---|---|---|---|---|---|
| E | 정상 | O | answered | - | - | plan:1413 | - |
| B-conv | 정상 | O | answered | - | - | plan:4004 | - |
| HF-최종 | 정상 | O | answered | - | - | plan:2846 | - |
| Ollama-최종 | **U** | X | answered | - | factor:dimension_target | plan:1750 | U2:dimension_target |
| Ollama-SFT | **U** | X | answered | - | factor:dimension_target | plan:1616 | U2:dimension_target |

셀별 grounding:

- E: `LOCATION/place[SUBCOND, pickup]={"name": "대구", "region": ""}; LOCATION/place[SUBCOND, dropoff]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: dimension=emd, dimension_target=pickup, order=top, limit=2`
- B-conv: `LOCATION/place[SUBCOND, pickup]={"name": "대구", "region": ""}; LOCATION/place[SUBCOND, dropoff]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: order=top, limit=2, dimension=emd, dimension_target=pickup`
- HF-최종: `LOCATION/place[SUBCOND, pickup]={"name": "대구", "region": ""}; LOCATION/place[SUBCOND, dropoff]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: order=top, limit=2, dimension=emd, dimension_target=pickup`
- Ollama-최종: `LOCATION/place[SUBCOND, pickup]={"name": "대구", "region": ""}; LOCATION/place[SUBCOND, dropoff]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: dimension=emd, order=top, limit=2`
- Ollama-SFT: `LOCATION/place[SUBCOND, pickup]={"name": "대구", "region": ""}; LOCATION/place[SUBCOND, dropoff]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: dimension=emd, order=top, limit=2`

Ollama-최종의 Tool 호출과 최종 답:

1. `get_place_scope(name=대구, include_vicinity=False) → "scope:district:2700000000"`
2. `get_place_scope(name=부산, include_vicinity=False) → "scope:district:2600000000"`
3. `get_trip_count(scope_pickup=scope:district:2700000000, scope_dropoff=scope:district:2600000000, dimension=emd, limit=2, order=top) → [{"pickup": "동인동", "dropoff": "초읍동", "count": 20}, {"pickup": "중앙로동", "dropoff": "초량동", "count": 20}]`

- 최종 답: 대구 → 부산 읍면동별 상위 2개 실차 구간 건수 / - 동인동 → 초읍동: 20건 / - 중앙로동 → 초량동: 20건

U로 분류된 이유(Ollama-최종):

- 인자 `dimension_target`: 정답 `pickup` → 모델 `None` (U2:dimension_target).
- Ollama-SFT도 U(U2:dimension_target).

## 037

- 질문: 지난달 대구 수성구의 읍면동별 실차 택시 통행량 중 가장 많은 곳은?
- 결정 54: family 안
- 기대 결과: answered
- 정답 호출: `get_place_scope(name=수성구, region=대구)` → `get_passage_count(scope=$resolve.scope, date=last_month, taxi_status=occupied, dimension=emd, order=top, limit=1)`
- gold grounding: `LOCATION/place[SUBCOND]={"name": "수성구", "region": "대구"}; EVENT/passage[SUPPORT]; AMOUNT/passage_count[MEASURE] | factors: date=last_month, taxi_status=occupied, dimension=emd, order=top, limit=1`

| 셀 | 분류 | grounding_ok | 결과 | 멈춘 코드 | gold와 다른 grounding 항목 | thinking 글자 수(호출별) | U flag |
|---|---|---|---|---|---|---|---|
| E | 안전한 실패 | X | failed | MISSING_RELATION_QUALIFIER | factor:taxi_status, measure | plan:2666, repair:1255 | - |
| B-conv | 안전한 실패 | X | failed | MISSING_RELATION_QUALIFIER | factor:aggregation_spec, factor:taxi_status, measure | plan:6075, repair:7071 | - |
| HF-최종 | 안전한 실패 | X | failed | MISSING_RELATION_QUALIFIER | factor:taxi_status, measure | plan:2696, repair:4870 | - |
| Ollama-최종 | **U** | X | answered | - | factor:taxi_status, measure, places | plan:2984, repair:2829 | U1:taxi_status, U2:scope, U2:scope_pickup, U3:tool |
| Ollama-SFT | **U** | X | answered | - | factor:aggregation_spec, factor:taxi_status, measure, places | plan:2066, repair:1134 | U1:taxi_status, U2:scope, U2:scope_dropoff, U2:scope_pickup, U3:tool |

셀별 grounding:

- E: `EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE]; LOCATION/place[COND]={"name": "수성구", "region": "대구"} | factors: date=last_month, dimension=emd, order=top, limit=1`
- B-conv: `EVENT/trip[SUPPORT]; LOCATION/place[COND]={"name": "수성구", "region": "대구"}; AMOUNT/trip_count[MEASURE] | factors: date=last_month, dimension=emd, order=top, limit=1, aggregation=sum | aggregation: {"inner": "sum"}`
- HF-최종: `LOCATION/place[SUBCOND]={"name": "수성구", "region": "대구"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=last_month, dimension=emd, order=top, limit=1`
- Ollama-최종: `LOCATION/place[SUBCOND, pickup]={"name": "수성구", "region": "대구"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=last_month, dimension=emd, order=top, limit=1`
- Ollama-SFT: `LOCATION/place[SUBCOND, both]={"name": "수성구", "region": "대구"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=last_month, dimension=emd, order=top, limit=1, aggregation=sum | aggregation: {"inner": "sum"}`

Ollama-최종의 Tool 호출과 최종 답:

1. `get_place_scope(name=수성구, region=대구, include_vicinity=False) → "scope:district:2726000000"`
2. `get_trip_count(scope_pickup=scope:district:2726000000, date=last_month, dimension=emd, limit=1, order=top) → [{"pickup": "두산동", "dropoff": "동인동", "count": 20}]`

- 최종 답: 대구 수성구 출발 지난달 읍면동별 상위 1개 실차 구간 건수 / - 두산동 → 동인동: 20건

U로 분류된 이유(Ollama-최종):

- 측정 도구가 정답과 다르다(`tool_ok` false → U3:tool): 정답 마지막 호출 `get_passage_count`, 모델 `get_trip_count`.
- 인자 `scope`: 정답 `scope:district:2726000000` → 모델 `None` (U2:scope).
- 인자 `scope_pickup`: 정답 `None` → 모델 `scope:district:2726000000` (U2:scope_pickup).
- 인자 `taxi_status`: 정답 `occupied` → 모델 `None` (U1:taxi_status).
- Ollama-SFT도 U(U1:taxi_status, U2:scope, U2:scope_dropoff, U2:scope_pickup, U3:tool).

## 040

- 질문: 휴일 오후 6시부터 8시까지 부산의 승차 읍면동 중 가장 많은 곳은?
- 결정 54: family 밖
- 기대 결과: answered
- 정답 호출: `get_place_scope(name=부산)` → `get_trip_count(scope_pickup=$pickup.scope, date=holiday, time=180000-200000, dimension=emd, dimension_target=pickup, order=top, limit=1)`
- gold grounding: `LOCATION/place[SUBCOND, pickup]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=holiday, time=180000-200000, dimension=emd, dimension_target=pickup, order=top, limit=1`

| 셀 | 분류 | grounding_ok | 결과 | 멈춘 코드 | gold와 다른 grounding 항목 | thinking 글자 수(호출별) | U flag |
|---|---|---|---|---|---|---|---|
| E | 정상 | X | answered | - | factor:aggregation_spec | plan:1750, repair:1208 | - |
| B-conv | **U** | X | answered | - | factor:dimension_target | plan:2334, repair:1310 | U2:dimension_target |
| HF-최종 | 정상 | O | answered | - | - | plan:3237, repair:1434 | - |
| Ollama-최종 | **U** | X | answered | - | factor:dimension_target | plan:1900 | U2:dimension_target |
| Ollama-SFT | **U** | X | answered | - | factor:aggregation_spec, factor:dimension_target | plan:3928, repair:1427 | U2:dimension_target |

셀별 grounding:

- E: `LOCATION/place[SUBCOND, pickup]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=holiday, time=180000-200000, aggregation=sum, dimension=emd, dimension_target=pickup, order=top, limit=1 | aggregation: {"inner": "sum"}`
- B-conv: `LOCATION/place[SUBCOND, pickup]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=holiday, time=180000-200000, dimension=emd, order=top, limit=1`
- HF-최종: `LOCATION/place[SUBCOND, pickup]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=holiday, time=180000-200000, order=top, limit=1, dimension=emd, dimension_target=pickup`
- Ollama-최종: `LOCATION/place[SUBCOND, pickup]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=holiday, time=180000-200000, dimension=emd, order=top, limit=1`
- Ollama-SFT: `LOCATION/place[SUBCOND, pickup]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=holiday, time=180000-200000, dimension=emd, order=top, limit=1, aggregation=sum | aggregation: {"inner": "sum"}`

Ollama-최종의 Tool 호출과 최종 답:

1. `get_place_scope(name=부산, include_vicinity=False) → "scope:district:2600000000"`
2. `get_trip_count(scope_pickup=scope:district:2600000000, date=holiday, dimension=emd, limit=1, order=top, time=180000-200000) → [{"pickup": "초읍동", "dropoff": "동인동", "count": 20}]`

- 최종 답: 부산 출발 휴일 180000-200000 읍면동별 상위 1개 실차 구간 건수 / - 초읍동 → 동인동: 20건

U로 분류된 이유(Ollama-최종):

- 인자 `dimension_target`: 정답 `pickup` → 모델 `None` (U2:dimension_target).
- Ollama-SFT도 U(U2:dimension_target).

## 041

- 질문: 이번 달 부산에서 하차 건수가 적은 읍면동 하위 2곳은?
- 결정 54: family 밖
- 기대 결과: answered
- 정답 호출: `get_place_scope(name=부산)` → `get_trip_count(scope_dropoff=$dropoff.scope, date=this_month, dimension=emd, dimension_target=dropoff, order=bottom, limit=2)`
- gold grounding: `LOCATION/place[SUBCOND, dropoff]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_month, dimension=emd, dimension_target=dropoff, order=bottom, limit=2`

| 셀 | 분류 | grounding_ok | 결과 | 멈춘 코드 | gold와 다른 grounding 항목 | thinking 글자 수(호출별) | U flag |
|---|---|---|---|---|---|---|---|
| E | 정상 | X | answered | - | factor:aggregation_spec | plan:4497, repair:1494 | - |
| B-conv | 정상 | O | answered | - | - | plan:3113, repair:6059 | - |
| HF-최종 | 정상 | O | answered | - | - | plan:1938, repair:1784 | - |
| Ollama-최종 | **U** | X | answered | - | places | plan:4893, repair:89202 | U2:scope_dropoff, U2:scope_pickup |
| Ollama-SFT | **U** | X | answered | - | factor:dimension_target | plan:3340, repair:59271 | U2:dimension_target |

셀별 grounding:

- E: `EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE]; LOCATION/place[COND, dropoff]={"name": "부산", "region": ""} | factors: dimension=emd, dimension_target=dropoff, order=bottom, limit=2, date=this_month, aggregation=sum | aggregation: {"inner": "sum"}`
- B-conv: `LOCATION/place[COND, dropoff]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_month, dimension=emd, dimension_target=dropoff, order=bottom, limit=2`
- HF-최종: `LOCATION/place[SUBCOND, dropoff]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_month, dimension=emd, dimension_target=dropoff, order=bottom, limit=2`
- Ollama-최종: `LOCATION/place[SUBCOND, pickup]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_month, dimension=emd, dimension_target=dropoff, order=bottom, limit=2`
- Ollama-SFT: `LOCATION/place[SUBCOND, dropoff]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_month, dimension=emd, order=bottom, limit=2`

Ollama-최종의 Tool 호출과 최종 답:

1. `get_place_scope(name=부산, include_vicinity=False) → "scope:district:2600000000"`
2. `get_trip_count(scope_pickup=scope:district:2600000000, date=this_month, dimension=emd, dimension_target=dropoff, limit=2, order=bottom) → [{"dropoff": "동인동", "count": 20}, {"dropoff": "중앙로동", "count": 20}]`

- 최종 답: 부산 출발 이번 달 읍면동별 하차 지역 기준 하위 2개 실차 구간 건수 / - 동인동: 20건 / - 중앙로동: 20건

U로 분류된 이유(Ollama-최종):

- 인자 `scope_dropoff`: 정답 `scope:district:2600000000` → 모델 `None` (U2:scope_dropoff).
- 인자 `scope_pickup`: 정답 `None` → 모델 `scope:district:2600000000` (U2:scope_pickup).
- Ollama-SFT도 U(U2:dimension_target).

## 054

- 질문: 부산 광안동의 실차 택시 통행량은?
- 결정 54: family 밖
- 기대 결과: answered
- 정답 호출: `get_place_scope(name=광안동, region=부산)` → `get_passage_count(scope=$resolve.scope, taxi_status=occupied)`
- gold grounding: `LOCATION/place[SUBCOND]={"name": "광안동", "region": "부산"}; EVENT/passage[SUPPORT]; AMOUNT/passage_count[MEASURE] | factors: taxi_status=occupied`

| 셀 | 분류 | grounding_ok | 결과 | 멈춘 코드 | gold와 다른 grounding 항목 | thinking 글자 수(호출별) | U flag |
|---|---|---|---|---|---|---|---|
| E | **U** | X | answered | - | factor:taxi_status, measure, places | plan:2329, repair:2239 | U1:taxi_status, U2:scope, U2:scope_pickup, U3:tool |
| B-conv | 정상 | O | answered | - | - | plan:4807 | - |
| HF-최종 | 안전한 실패 | X | failed | MISSING_RELATION_QUALIFIER | factor:taxi_status, measure | plan:2221, repair:2238 | - |
| Ollama-최종 | **U** | X | answered | - | factor:taxi_status, measure, places | plan:7813, repair:2908 | U1:taxi_status, U2:scope, U2:scope_pickup, U3:tool |
| Ollama-SFT | 정상 | O | answered | - | - | plan:8630 | - |

셀별 grounding:

- E: `LOCATION/place[SUBCOND, pickup]={"name": "광안동", "region": "부산"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: -`
- B-conv: `LOCATION/place[SUBCOND]={"name": "광안동", "region": "부산"}; EVENT/passage[SUPPORT]; AMOUNT/passage_count[MEASURE] | factors: taxi_status=occupied`
- HF-최종: `LOCATION/place[SUBCOND]={"name": "광안동", "region": "부산"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: -`
- Ollama-최종: `LOCATION/place[SUBCOND, pickup]={"name": "광안동", "region": "부산"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: -`
- Ollama-SFT: `LOCATION/place[SUBCOND]={"name": "광안동", "region": "부산"}; EVENT/passage[SUPPORT]; AMOUNT/passage_count[MEASURE] | factors: taxi_status=occupied`

Ollama-최종의 Tool 호출과 최종 답:

1. `get_place_scope(name=광안동, region=부산, include_vicinity=False) → "scope:district:2650010400"`
2. `get_trip_count(scope_pickup=scope:district:2650010400) → {"count": 20}`

- 최종 답: 부산 광안동 출발 실차 구간 건수: 20건

U로 분류된 이유(Ollama-최종):

- 측정 도구가 정답과 다르다(`tool_ok` false → U3:tool): 정답 마지막 호출 `get_passage_count`, 모델 `get_trip_count`.
- 인자 `scope`: 정답 `scope:district:2650010400` → 모델 `None` (U2:scope).
- 인자 `scope_pickup`: 정답 `None` → 모델 `scope:district:2650010400` (U2:scope_pickup).
- 인자 `taxi_status`: 정답 `occupied` → 모델 `None` (U1:taxi_status).

## 074

- 질문: 휴일 부산 초읍동 어린이대공원 주변의 실차 택시 통행량은?
- 결정 54: family 밖
- 기대 결과: answered
- 정답 호출: `get_place_scope(name=어린이대공원, region=부산 초읍동, include_vicinity=true)` → `get_passage_count(scope=$resolve.scope, date=holiday, taxi_status=occupied)`
- gold grounding: `LOCATION/place[SUBCOND]={"name": "어린이대공원", "region": "부산 초읍동"}; EVENT/passage[SUPPORT]; AMOUNT/passage_count[MEASURE] | factors: vicinity=True, date=holiday, taxi_status=occupied`

| 셀 | 분류 | grounding_ok | 결과 | 멈춘 코드 | gold와 다른 grounding 항목 | thinking 글자 수(호출별) | U flag |
|---|---|---|---|---|---|---|---|
| E | 정상 | O | answered | - | - | plan:4153 | - |
| B-conv | **U** | X | answered | - | factor:taxi_status, measure, places | plan:4220, repair:4681 | U1:taxi_status, U2:scope, U2:scope_pickup, U3:tool |
| HF-최종 | 안전한 실패 | X | failed | MISSING_RELATION_QUALIFIER | factor:taxi_status, measure | plan:3743, repair:3127 | - |
| Ollama-최종 | **U** | X | answered | - | factor:taxi_status, measure, places | plan:2003, repair:2692 | U1:taxi_status, U2:scope, U2:scope_dropoff, U2:scope_pickup, U3:tool |
| Ollama-SFT | 정상 | O | answered | - | - | plan:1883 | - |

셀별 grounding:

- E: `LOCATION/place[SUBCOND]={"name": "어린이대공원", "region": "부산 초읍동"}; EVENT/passage[SUPPORT]; AMOUNT/passage_count[MEASURE] | factors: date=holiday, vicinity=True, taxi_status=occupied`
- B-conv: `LOCATION/place[SUBCOND, pickup]={"name": "어린이대공원", "region": "부산 초읍동"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: vicinity=True, date=holiday`
- HF-최종: `LOCATION/place[SUBCOND]={"name": "어린이대공원", "region": "부산 초읍동"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: vicinity=True, date=holiday`
- Ollama-최종: `LOCATION/place[SUBCOND, both]={"name": "어린이대공원", "region": "부산 초읍동"}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: vicinity=True, date=holiday`
- Ollama-SFT: `LOCATION/place[SUBCOND]={"name": "어린이대공원", "region": "부산 초읍동"}; EVENT/passage[SUPPORT]; AMOUNT/passage_count[MEASURE] | factors: date=holiday, vicinity=True, taxi_status=occupied`

Ollama-최종의 Tool 호출과 최종 답:

1. `get_place_scope(name=어린이대공원, region=부산 초읍동, include_vicinity=True) → "scope:gz:3982"`
2. `get_trip_count(scope_pickup=scope:gz:3982, scope_dropoff=scope:gz:3982, date=holiday) → {"count": 20}`

- 최종 답: 부산 초읍동 어린이대공원 주변 휴일 실차 구간 건수: 20건

U로 분류된 이유(Ollama-최종):

- 측정 도구가 정답과 다르다(`tool_ok` false → U3:tool): 정답 마지막 호출 `get_passage_count`, 모델 `get_trip_count`.
- 인자 `scope`: 정답 `scope:gz:3982` → 모델 `None` (U2:scope).
- 인자 `scope_dropoff`: 정답 `None` → 모델 `scope:gz:3982` (U2:scope_dropoff).
- 인자 `scope_pickup`: 정답 `None` → 모델 `scope:gz:3982` (U2:scope_pickup).
- 인자 `taxi_status`: 정답 `occupied` → 모델 `None` (U1:taxi_status).

## 093

- 질문: 이번 달 부산 안에서 이용이 적은 읍면동 간 OD 노선 하위 2개는?
- 결정 54: family 안, template도 겹침
- 기대 결과: answered
- 정답 호출: `get_place_scope(name=부산)` → `get_trip_count(scope_pickup=$area.scope, scope_dropoff=$area.scope, date=this_month, dimension=emd, dimension_target=both, order=bottom, limit=2)`
- gold grounding: `LOCATION/place[SUBCOND, pickup]={"name": "부산", "region": ""}; LOCATION/place[SUBCOND, dropoff]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_month, dimension=emd, dimension_target=both, order=bottom, limit=2`

| 셀 | 분류 | grounding_ok | 결과 | 멈춘 코드 | gold와 다른 grounding 항목 | thinking 글자 수(호출별) | U flag |
|---|---|---|---|---|---|---|---|
| E | 안전한 실패 | X | failed | MISSING_RELATION_QUALIFIER | places | plan:2138, repair:55539 | - |
| B-conv | **U** | X | answered | - | places | plan:1735 | U2:scope_dropoff |
| HF-최종 | 안전한 실패 | X | unsupported | UNCONSUMED_CONDITION | factor:aggregation_spec, places | plan:5977, repair:11132 | - |
| Ollama-최종 | **U** | X | answered | - | places | plan:2230 | U2:scope_dropoff |
| Ollama-SFT | 정상 | X | answered | - | places | plan:2364, repair:1641 | - |

셀별 grounding:

- E: `LOCATION/place[SUBCOND]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_month, dimension=emd, dimension_target=both, order=bottom, limit=2`
- B-conv: `LOCATION/place[SUBCOND, pickup]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_month, dimension=emd, dimension_target=both, order=bottom, limit=2`
- HF-최종: `LOCATION/place[COND, both]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_month, dimension=emd, dimension_target=both, order=bottom, limit=2, aggregation=min | aggregation: {"inner": "min"}`
- Ollama-최종: `LOCATION/place[SUBCOND, pickup]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_month, dimension=emd, order=bottom, limit=2`
- Ollama-SFT: `LOCATION/place[SUBCOND, both]={"name": "부산", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_month, dimension=emd, order=bottom, limit=2, dimension_target=both`

Ollama-최종의 Tool 호출과 최종 답:

1. `get_place_scope(name=부산, include_vicinity=False) → "scope:district:2600000000"`
2. `get_trip_count(scope_pickup=scope:district:2600000000, date=this_month, dimension=emd, limit=2, order=bottom) → [{"pickup": "초읍동", "dropoff": "동인동", "count": 20}, {"pickup": "초량동", "dropoff": "중앙로동", "count": 20}]`

- 최종 답: 부산 출발 이번 달 읍면동별 하위 2개 실차 구간 건수 / - 초읍동 → 동인동: 20건 / - 초량동 → 중앙로동: 20건

U로 분류된 이유(Ollama-최종):

- 인자 `scope_dropoff`: 정답 `scope:district:2600000000` → 모델 `None` (U2:scope_dropoff).

## 044 (참고: Ollama-SFT에만 U)

- 질문: 지난 주 대구에서 승차 건수가 적은 읍면동 하위 2곳은?
- 결정 54: family 밖
- 기대 결과: answered
- 정답 호출: `get_place_scope(name=대구)` → `get_trip_count(scope_pickup=$pickup.scope, date=last_week, dimension=emd, dimension_target=pickup, order=bottom, limit=2)`
- gold grounding: `LOCATION/place[SUBCOND, pickup]={"name": "대구", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=last_week, dimension=emd, dimension_target=pickup, order=bottom, limit=2`

| 셀 | 분류 | grounding_ok | 결과 | 멈춘 코드 | gold와 다른 grounding 항목 | thinking 글자 수(호출별) | U flag |
|---|---|---|---|---|---|---|---|
| E | 정상 | O | answered | - | - | plan:2154 | - |
| B-conv | 정상 | O | answered | - | - | plan:2396, repair:2345 | - |
| HF-최종 | 정상 | O | answered | - | - | plan:2602, repair:1236 | - |
| Ollama-최종 | 정상 | O | answered | - | - | plan:2430, repair:1153 | - |
| Ollama-SFT | **U** | X | answered | - | factor:dimension, factor:dimension_target | plan:2559, repair:1063 | U2:dimension_target |
| HF-SFT | 정상 | O | answered | - | - | plan:2415, repair:1247 | - |

셀별 grounding:

- E: `LOCATION/place[SUBCOND, pickup]={"name": "대구", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=last_week, dimension=emd, dimension_target=pickup, order=bottom, limit=2`
- B-conv: `EVENT/trip[SUPPORT]; LOCATION/place[SUBCOND, pickup]={"name": "대구", "region": ""}; AMOUNT/trip_count[MEASURE] | factors: date=last_week, dimension=emd, dimension_target=pickup, order=bottom, limit=2`
- HF-최종: `LOCATION/place[SUBCOND, pickup]={"name": "대구", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=last_week, dimension=emd, dimension_target=pickup, order=bottom, limit=2`
- Ollama-최종: `LOCATION/place[SUBCOND, pickup]={"name": "대구", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=last_week, dimension=emd, dimension_target=pickup, order=bottom, limit=2`
- Ollama-SFT: `LOCATION/place[SUBCOND, pickup]={"name": "대구", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=last_week, dimension=sigungu, order=bottom, limit=2`
- HF-SFT: `LOCATION/place[SUBCOND, pickup]={"name": "대구", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=last_week, dimension=emd, dimension_target=pickup, order=bottom, limit=2`

Ollama-SFT의 Tool 호출과 최종 답:

1. `get_place_scope(name=대구, include_vicinity=False) → "scope:district:2700000000"`
2. `get_trip_count(scope_pickup=scope:district:2700000000, date=last_week, dimension=sigungu, limit=2, order=bottom) → [{"pickup": "중구", "dropoff": "부산진구", "count": 20}, {"pickup": "동구", "dropoff": "부산 동구", "count": 20}]`

- 최종 답: 대구 출발 지난주 시군구별 하위 2개 실차 구간 건수 / - 중구 → 부산진구: 20건 / - 동구 → 부산 동구: 20건

U로 분류된 이유(Ollama-SFT):

- 인자 `dimension`: 정답 `emd` → 모델 `sigungu` (U 아님).
- 인자 `dimension_target`: 정답 `pickup` → 모델 `None` (U2:dimension_target).

## 085 (참고: Ollama-SFT에만 U)

- 질문: 이번 주 대구에 도착한 실차의 하차 읍면동을 많은 순서로 3곳 알려줘.
- 결정 54: family 밖
- 기대 결과: answered
- 정답 호출: `get_place_scope(name=대구)` → `get_trip_count(scope_dropoff=$dropoff.scope, date=this_week, dimension=emd, dimension_target=dropoff, order=top, limit=3)`
- gold grounding: `LOCATION/place[SUBCOND, dropoff]={"name": "대구", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_week, dimension=emd, dimension_target=dropoff, order=top, limit=3`

| 셀 | 분류 | grounding_ok | 결과 | 멈춘 코드 | gold와 다른 grounding 항목 | thinking 글자 수(호출별) | U flag |
|---|---|---|---|---|---|---|---|
| E | 정상 | O | answered | - | - | plan:7602, repair:37999 | - |
| B-conv | 정상 | O | answered | - | - | plan:2302, repair:1006 | - |
| HF-최종 | 정상 | O | answered | - | - | plan:1871, repair:1728 | - |
| Ollama-최종 | 정상 | O | answered | - | - | plan:4667, repair:4161 | - |
| Ollama-SFT | **U** | X | answered | - | factor:dimension_target | plan:1613, repair:1165 | U2:dimension_target |
| HF-SFT | 정상 | O | answered | - | - | plan:2694 | - |

셀별 grounding:

- E: `LOCATION/place[SUBCOND, dropoff]={"name": "대구", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: dimension=emd, dimension_target=dropoff, order=top, limit=3, date=this_week`
- B-conv: `LOCATION/place[SUBCOND, dropoff]={"name": "대구", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_week, dimension=emd, dimension_target=dropoff, order=top, limit=3`
- HF-최종: `LOCATION/place[SUBCOND, dropoff]={"name": "대구", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_week, dimension=emd, dimension_target=dropoff, order=top, limit=3`
- Ollama-최종: `LOCATION/place[SUBCOND, dropoff]={"name": "대구", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_week, dimension=emd, dimension_target=dropoff, order=top, limit=3`
- Ollama-SFT: `LOCATION/place[SUBCOND, dropoff]={"name": "대구", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_week, dimension=emd, order=top, limit=3`
- HF-SFT: `LOCATION/place[SUBCOND, dropoff]={"name": "대구", "region": ""}; EVENT/trip[SUPPORT]; AMOUNT/trip_count[MEASURE] | factors: date=this_week, dimension=emd, dimension_target=dropoff, order=top, limit=3`

Ollama-SFT의 Tool 호출과 최종 답:

1. `get_place_scope(name=대구, include_vicinity=False) → "scope:district:2700000000"`
2. `get_trip_count(scope_dropoff=scope:district:2700000000, date=this_week, dimension=emd, limit=3, order=top) → [{"pickup": "동인동", "dropoff": "동인동", "count": 20}, {"pickup": "중앙로동", "dropoff": "중앙로동", "count": 20}, {"pickup": "태평로동", "dropoff": "태평로동", "count": 20}]`

- 최종 답: 대구 도착 이번 주 읍면동별 상위 3개 실차 구간 건수 / - 동인동 → 동인동: 20건 / - 중앙로동 → 중앙로동: 20건 / - 태평로동 → 태평로동: 20건

U로 분류된 이유(Ollama-SFT):

- 인자 `dimension_target`: 정답 `dropoff` → 모델 `None` (U2:dimension_target).
