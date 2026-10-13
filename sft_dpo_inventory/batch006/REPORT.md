# batch006 검토 결과와 reviewed_gold_v006_p0

2026-10-13. 결정 67. 모델 호출 없음.

## 1. 누가 어떻게 검토했나

- 사용자 지시(2026-10-13)로 Claude가 Gap A·B 43건을 한 건씩 읽고 판정했다.
- 결정 45의 "사람 승인" 자리에 사용자가 위임한 검토다. 판정과 이유는 모두 `review_decisions.json`에 있고, 사용자가 뒤집을 수 있다.
- 기준(지시 5–9절): 자연어 자연스러움, measure, od_role, dimension_target, dimension, 실행 가능성(UNCONSUMED_CONDITION 없음).
  대조쌍 유효성과 mock 데이터 유무는 따로 본다.
- 검토 중 새 문항은 더하지 않았다(지시 10절).

## 2. 판정

| 판정 | 수 | id |
|---|---:|---|
| APPROVE | 33 | 나머지 |
| APPROVE_WITHOUT_MOCK | 3 | b006-13, 22, 41 |
| EDIT_REQUIRED → 수정 뒤 재검사 통과 → 승인 | 7 | b006-09, 17, 21, 26, 27, 33, 39 |
| REJECT | 0 | |
| Gap C(scope 역조회) | 10 제외 | b006-44–53. 결정 67: v006의 Gap C 승인 = 0 |

수정 7건의 이유와 내용:

| id | 문제 | 수정 |
|---|---|---|
| b006-09 | measure text "실차"가 질문에 없다 | gold에서 measure text 삭제(v005의 text 없는 implicit measure 관례) |
| b006-21 | 같음 | 같음 |
| b006-27 | measure text "택시"가 택시 대수(active_taxi_count)와 섞일 수 있다 | measure text 삭제 |
| b006-17 | "부산진구로 들어온"은 외부에서 들어온 운행으로 읽힐 수 있는데 gold는 하차 제한만 있다. "한산한"도 흐리다 | "이번 달 부산 부산진구에서 손님을 내려준 곳 중 하차가 가장 적은 H3 셀 세 개는?"(measure text "하차") |
| b006-33 | "대구로 들어온"이 같은 문제 | "지난달 대구에 도착한 실차를 출발한 시도 기준으로 나눠 보여줘" |
| b006-26 | "손님을 태운 곳 가운데 실차가 가장 적게 시작된"이 같은 뜻을 두 번 말하는 합성 문장 | "이번 달 대구 수성구에서 손님을 가장 적게 태운 H3 셀 세 곳은?" |
| b006-39 | measure text "운행"이 운행일수·운행률(operation)과 혼동된다 | "운행" → "실차" |

- 원문 `candidates_draft.yaml`은 고치지 않았다. `apply_review.py`가 revision을 적용해 `approved.jsonl`을 만든다(원문은 `original` 필드에 남는다).
- 수정 뒤 승인 43건 전체를 같은 자동 검사(`check_candidates.py --source approved.jsonl`)에 다시 넣었다. 43/43 auto_ok, 계약 실패 0, 겹침 0
  (`evaluation/partial_grounding/sft_p0/approved_checks.jsonl`, `overlap_report_approved.json`).

## 3. mock 데이터가 없는 5건

- b006-13, 17, 22, 39, 41.
- semantic·계약 검사(thor 계약, T2PC 운영 경로의 조건 계층·compose·validate·compile, P0 변환 불변식)는 모두 통과한다.
- mock 실행기에 그 장소·조합의 응답 데이터가 없어 실행 단계에서 `UNSUPPORTED_COMBINATION`으로 끝난다. 계약 문제가 아니다.
- v006 metadata에 `mock_available: false`로 표시했다.

## 4. 대조쌍: 초안의 "12쌍 모두 끝점만 바꾼 최소 대조쌍"은 틀렸다

| 쌍 | 판정 | 이유 |
|---|---|---|
| a1(01·02), a3(05·06), a4(10·11), a7(19·20), a8(24·25), b6(42·43) | 유효 | 끝점만 바뀐다 |
| a2(03·04) | 무효 | 순위 방향 top↔bottom과 표현(몰린↔드물었던)도 바뀐다 |
| b1(27·28) | 무효 | 순위 조건(없음↔top 5)도 바뀐다 |
| b2(29·30) | 무효 | top 3↔bottom 3 |
| b3(31·32) | 무효 | 장소(대구↔부산)와 순위도 바뀐다 |
| b4(36·37) | 무효 | dimension(emd↔h3)도 바뀐다 |
| b5(40·41) | 무효 | 순위 조건(없음↔top 5)도 바뀐다 |

- 유효 6쌍(12문항). 무효 6쌍은 일반 승인 문항으로 둔다(v006 metadata `pair`는 유효 쌍만).
- 문장을 고쳐 대조쌍을 맞추지 않았다(검토 중 새 문항 금지와 같은 취지).
- 이전 검토 시트(`AUGMENTATION_REVIEW.md` 3절)의 "끝점 하나만 바꾼 최소 대조쌍이다"는 틀린 기술이었다.

## 5. reviewed_gold_v006_p0

- `training/generated/reviewed_gold_v006_p0/sft_train.jsonl`(154건), `manifest.json`. v005는 덮어쓰지 않았다.
- 구성: v005 111(`source=v005`) + Gap A 26(`source=augment_dt_event`) + Gap B 17(`source=augment_od_vs_dt`). Gap C 0.
- 신규 레코드 metadata: batch(b006), review_decision, edited, pair, mock_available, target_full(Full canonical gold),
  dataset_version, prompt_sha256(P0 `d7f4c12a…`).
- P0 target은 Full gold에서 `build_targets.convert`로만 만든다(손으로 관리하지 않음).

## 6. v006 전체 검사(`evaluation/partial_grounding/sft_p0/verify_v006.py` → `v006_verification.json`)

- 154/154: Full gold를 다시 변환하면 저장된 P0 target과 같다(결정적).
- 154/154: Full과 P0가 같은 운영 경로에서 같은 실행 결과(parse·outcome·error code·validation·operators·compile), 같은 의미 서명
  (EVENT 제외: 측정값·장소·scope·od_role·dimension·dimension_target·bucket·집계·rollup·answer·taxi_type·taxi_status·date·time·order·limit),
  같은 평가 비교 정규형.
- 오염(질문·id·template·family; 보호 원본 전체, 확장 지문, vendor100·valid98·sel154·aux_test_v1, 한 장소 both를 펼친 형태):
  - 신규 43건: 0.
  - 질문·id 겹침: 154건 모두 0.
  - v005 111건 중 40건에 template·family 수준 겹침이 있다. 새로 생긴 것이 아니다.
    - 직접 키(평가셋 template·family) 11건: ann-f7808786, ann-e645cbc1, ann-7fae41a3, b004-05, 06, 15, 20, 21, 23, 30, 31.
      결정 15·54에서 허용한 예외 목록과 정확히 같다.
    - 이번 batch006에서 처음 도입한 보수 규칙(한 장소 both를 두 장소로 펼친 키)에만 걸리는 것 16건(b004-24, b005-01–10, 31, 32, 38, 39, 42).
      v005 승인 때는 없던 규칙이다.
    - 확장 지문(batch004 extended_fingerprints)에만 걸리는 것 13건.
  - v006은 "v005 + 승인분"으로 정의되어 있어 v005 문항은 빼지 않았다. 펼친 키 16건을 소급 적용할지는 사용자 결정으로 남긴다.

## 7. 분포(`evaluation/partial_grounding/sft_p0/dataset_stats_v006.json`)

| | v005 | 신규 43 | v006 154 |
|---|---:|---:|---:|
| dimension_target pickup / dropoff / both | 13 / 11 / 7 | 22 / 18 / 3 | 35 / 29 / 10 |
| 장소 od_role pickup / dropoff / both | 9 / 16 / 20 | 14 / 14 / 2 | 23 / 30 / 22 |
| od_role와 dimension_target 동시 존재 | 20 | 28 | 48 |
| 그중 od_role ≠ dimension_target | 15 | 16 | 31 |
| dimension h3 / sido / sigungu / emd / dayofweek | 3 / 5 / 13 / 23 / 3 | 25 / 6 / 8 / 4 / 0 | 28 / 11 / 21 / 27 / 3 |
| bucket week / month | 14 / 9 | 0 / 0 | 14 / 9 |
| scope 역조회 | 0 | 0 | 0 |

- od_role ≠ dimension_target 정의: dimension_target 값이 장소 od_role 값 집합에 없다. Gap B 17건 중 b006-40·41(대구 pickup + 부산 dropoff 제한,
  한 끝으로 grouping)은 이 정의로 "같음"에 들어가 Gap B의 다름은 15건이다. Gap A의 1건은 b006-22(dropoff 제한, both grouping)다.
- **h3 편중:** 신규 43건 중 25건(58%)이 h3다. v006 전체에서는 h3 28 / dimension 있는 90건(31%). 이번 batch에서 다른 dimension을
  억지로 더하지 않았다. trip_count의 emd·sigungu 조합 다수가 보호 family라 막힌 것이 원인이며, 다음 batch의 보강 과제로 남긴다.
- 신규 bucket 0, dayofweek 0, both grouping 3건.
