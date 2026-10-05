# REVIEW_BATCH_002

**30 record: 사람이 수락하면 편입 가능한 후보 28 + 새 unsupported 경계 diagnostic 2. 모두 pending이고 자동 gold/decision/import/학습은 0건이다.** reviewed_gold_v001의 파일·manifest/hash와 split은 변경하지 않았다. RB001-10–20의 11 hold와 원본 diagnostic 50건도 유지한다.

## 검토 파일

- review_batch_002.xlsx: Trainable_review(28) / Diagnostic_boundaries(2) / Coverage_and_pairs. 모든 cell은 문자열이며 판정을 자동 반영하지 않는다.
- review_batch_002.jsonl: question, proposed chosen/rejected, 정확한 실제 모델 출력, 신뢰 근거, driver, strict/production 검사, ambiguity 및 추천.
- review_queue.jsonl + manifest.json: hash-bound authoritative queue. 이후 human workflow는 이 queue를 사용한다.
- coverage_expected.json: 승인 전 가정만으로 계산한 분포와 split feasibility. Training 데이터가 아니다.
- mining_audit.json: 제외된 과거 dev/validation 및 legacy target의 이유. 제외된 raw 출력을 새 training 후보에 넣지 않았다.

## 범위와 우선 검토

| ID | Category | 목적 |
|---|---|---|
| RB002-01–10 | rare_measure | fare/speed/passage_count/vacant_ratio/rpm 각 2문항. 단순 지역 교체가 아닌 서로 다른 통계/집계 의도 |
| RB002-11–12 | unsupported_boundary — diagnostic-only | 미지원 metric을 RPM/통행량으로 잘못 답하는 경계. Training 불가 |
| RB002-13–20 | actual_hard_negative | v001 accepted train chosen + 실제 Base/SFT/DPO 오답 8쌍 |
| RB002-21–26 | semantic_contrast | source/role/value, factor omission/hallucination, coherent fare→revenue |
| RB002-27–29 | aggregation_contrast | stage swap 2, bucket/rollup 묶음 누락 1 |
| RB002-30 | constraint_contrast | RPM 최솟값을 정의되지 않은 sum으로 바꾼 최소 domain constraint |

먼저 01/02(fare), 03/04(speed), 05/06(passage_count와 공간 차원), 07/08(drive 기록별 공차율)를 검토한다. 다음 13–20의 실측 multi-error와 21–23의 source/role/value를 구별한다. 27–29는 inner/outer와 bucket/rollup을, 30은 RPM sum의 정의 불가를 확인한다. 11–12는 semantic unsupported 정의 검토만 하며 training 수락 후보와 섞지 않는다.

## Semantic 정의와 provider 범위

Fare는 EVENT/trip + AMOUNT/fare이며 scope는 소속 지역이다. Revenue(operation)는 다른 양이다. Speed/RPM은 passage 발생 위치를 원문에 명시했다. Vacant ratio는 drive마다 기록된 비율이며 질문이 평균/최대를 취할 기록 단위를 명시한다. Passage_count는 passage 사건 수이고 trip_count/OD 축이 아니며, bottom ranking은 기록 있는 그룹에 한정한다고 원문에 명시했다. 가람구/가람시는 합성 literal 값으로 semantic 검토 대상이며 실제 scope를 생성하지 않는다.

[TIMS schema](/home/hwkim/assistant_univ/schemas/tims.yaml), [measure definitions](/home/hwkim/assistant_univ/geoflow/measures.py), [planner roles/source](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml)와 현 composer/validator/registry를 재사용했다. Grouped fare/speed의 TIMS compiler 제한, median 짝수/빈 표본/결측, 주 경계와 동률 등 실행 조건은 별도로 표시했다. Static compile 실패를 semantic unsupported로 바꾸지 않는다.

## DPO chosen과 rejected의 신뢰

실제 hard-negative 8건과 trusted-anchor synthetic 6건의 chosen은 v001의 accepted train record와 decision hash에 직접 연결했다. 신규 chosen을 사용하는 23(공차율 입력값 혼동)/25(speed time hallucination)/26(fare→revenue)/30(RPM sum)은 각각 08/03/01/09의 human gold 확인을 먼저 요구한다. 모든 rejected는 추가 human 판단이 필요하다. JSON syntax를 망가뜨린 negative는 없다.

Hard negative는 과거 raw_text를 그대로 보여주며 canonical rejected는 ID/ordering/공백을 안정화한 projection이다. Raw subtype/source/value/date 의미를 고쳐서 실측 출력이라고 주장하지 않는다. Base/SFT/DPO 출력이 없는 새 질문에는 unavailable을 표시한다. Driver로 연결한 다른 질문의 오답은 이 새 질문의 prediction이 아니다.

Synthetic 10쌍은 multi-field model 오류에서 역할/출처/입력값/factor/집계 차이를 분리한 작은 control이다. Stage-swap, fare→revenue 또는 RPM sum 자체를 pilot에서 직접 관측했다고 주장하지 않는다. 실제 concept/source/factor/aggregation 표현 오류와 coverage gap을 보완한다. 학습 편입에는 사람이 target과 잘못된 의미를 확인해야 한다.

## DPO 예상 분포 (모두 승인된다는 가정)

| 범위 | Semantic | Constraint | 총 쌍 |
|---|---:|---:|---:|
| 편입 가능 새 pair | 9 | 9 | 18 |
| 이 중 실제 모델 오답 | 0 | 8 | 8 |
| 이 중 synthetic control | 9 | 1 | 10 |
| 별도 unsupported diagnostic pair | 2 | 0 | 2 |
| v001 5쌍 + 편입 가능 새 pair | 14 | 9 | 23 |

Negative category는 현재 production assess 결과로 분류하고 strict_raw 결과도 함께 남겼다. Constraint는 실제 parser/composer failure인 경우가 많으며 G1–G7까지 도달하지 않았으면 validation_ok=null/codes=[]다. 실패한 G rule을 만들어 붙이지 않는다. Valid한 negative는 그래프/형식이 통과해도 원문 의미가 틀렸는지 확인한다.

## Coverage 예상과 한계

v001 14문항에 독립 신규 10문항이 모두 승인되면 union 24문항. MEASURE는 기존 operating_days 5 / revenue 4 / trip_count 5에 fare 2 / speed 2 / passage_count 2 / vacant_ratio 2 / rpm 2가 추가된다. 이것은 실제 새 corpus 산출물이 아니며 실제 승인 수는 아직 0이다.

Unsupported refusal family는 현재 Protection에서 한 family로 보호된다. 11/12가 semantic 경계상 분명하더라도 현재 코드·정책 그대로는 training gold나 DPO로 편입 불가다. Unsupported taxonomy/독립 split 정책을 향후 별도로 정해야 한다. RB001-10–16 관련 active count/ratio는 여전히 0이고 RPM 17–20도 hold다. 새 RPM 09/10은 발생 위치를 명시한 별도 단일 집계 질문이다.

단일 passage count와 여러 fare/speed 일반 family는 기존 평가 보호에 걸린다. 이 batch는 평가 질문의 지역·날짜만 바꾸어 우회하지 않고 별도 median/min/grouping 의도를 독립적으로 작성했다. 자동 family 검사 통과는 수동 paraphrase lineage 검토를 대신하지 않는다.

## 다음 pilot에 충분한가

승인된다면 OD만 있던 DPO에 실제 모델 constraint 오류와 semantic control이 생겨 제한적인 SFT/DPO pilot 신호를 볼 수 있다. 그러나 이 batch의 DPO train/validation 분포는 아직 확정되지 않았다. Trusted-anchor pair는 기존 train에 남겨야 하고, 신규 family 전체를 묶어 split해야 한다. 아래 preview는 확정된 dataset이 아니다.

```json
{
  "existing_v001_split_fixed": true,
  "new_intent_group_seed": 42,
  "new_gold_train": 8,
  "new_gold_valid": 2,
  "new_DPO_by_planned_split": {
    "train": {
      "constraint": 8,
      "semantic": 8
    },
    "valid": {
      "semantic": 1,
      "constraint": 1
    }
  },
  "new_valid_gold_review_ids": [
    "RB002-08",
    "RB002-09"
  ],
  "note": "Counts are a feasibility preview, not finalized split or checkpoint. New v002 assembly must explicitly preserve v001 validation.",
  "control_design_note": "Before human review or any model scoring, value/constraint controls were assigned to different new semantic families to ensure both categories are observable in the preview validation. Seed and prior v001 splits unchanged."
}
```

Source/role control과 실제 constraint 오답이 train-anchor에만 있어 해당 축의 새로운 독립 validation pair가 여전히 부족하다. 새 validation control은 semantic/constraint 각각 1건뿐이다. 추가 독립 validation, 새로운 사람 검토 holdout, unsupported 경계, active metrics 정의, subtype당 2문항의 희소성은 남는다. 평균 preference accuracy만으로 성공이라 하지 않는다.

v001은 immutable baseline이다. v002 조립에서 v001 validation을 training으로 옮기지 말고 기존 split을 보존해야 한다. 이 queue의 importer를 단독 실행하면 delta만 export하고 baseline 전체를 자동 carry-forward하지 않으므로 그것을 완전한 새 corpus라고 간주하지 않는다. 새 corpus 통합/동결/Base 재측정은 human review 후 별도 작업이다.

## 검토 후 기록 방법

현재 decisions.jsonl은 만들지 않았다. 추천 accepted를 status에 복사하지 않는다. Human 확인 후 기존 workflow decide를 이 새 queue에 사용할 수 있다. accepted는 semantic-checks-confirmed, pair는 negative-is-wrong을 실제 확인한 경우만 지정한다. Diagnostic 11/12의 acceptance가 protection을 우회하지 않는다.

```bash
python -m training.annotations.workflow decide \
  --queue /home/hwkim/assistant_univ/training/annotations/generated/review_batch_002 \
  --decisions /home/hwkim/assistant_univ/training/annotations/generated/review_batch_002/decisions.jsonl \
  --id ann-1f172450fd9dabbb82f6 --status needs_fix \
  --reviewer YOUR_NAME --reason '원문 의미·표본·lineage를 검토한 근거'
```

## 개별 의미 정의와 검토 ambiguity

### RB002-01 — rare_measure (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 15일 가람구 소속 택시의 실차 구간별 요금 중앙값은?

- 의미/생성 근거: 각 trip 요금 값의 중앙값; 영업일 매출(revenue)이 아님. Scope는 소속 지역.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): DPO pair가 아닌 신규 gold 후보
- Human 확인: 짝수 표본 median 구현과 빈 표본은 provider 실행 정의를 추가 확인; raw med 대응과 구별. / 신규 원문의 통계/공간 해석과 평가 paraphrase lineage를 사람이 확인해야 함.
- 권고: accepted (참고용); 실제 pending

### RB002-02 — rare_measure (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 가람구 소속 택시의 요금을 주마다 합산한 뒤, 주별 합계 중 가장 작은 값은?

- 의미/생성 근거: 주 안 trip fare 합계(sum), 주 합계들의 최솟값(min), 숫자 반환.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): DPO pair가 아닌 신규 gold 후보
- Human 확인: 주 경계/부분 주는 실행 계약에 위임; grouped fare의 default TIMS compile 제한은 semantic unsupported가 아님. / 신규 원문의 통계/공간 해석과 평가 paraphrase lineage를 사람이 확인해야 함.
- 권고: accepted (참고용); 실제 pending

### RB002-03 — rare_measure (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 15일 가람구에서 기록된 도로 통행의 주행 속도 최솟값은?

- 의미/생성 근거: 발생 위치 안 passage speed의 min; 소속 taxi cohort나 전체 평균 속도가 아님.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): DPO pair가 아닌 신규 gold 후보
- Human 확인: 미수집 speed/빈 표본 처리와 실제 관측 단위의 provider 수치 검증은 별도. / 신규 원문의 통계/공간 해석과 평가 paraphrase lineage를 사람이 확인해야 함.
- 권고: accepted (참고용); 실제 pending

### RB002-04 — rare_measure (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 가람구에서 기록된 도로 통행 속도의 주별 최댓값들 중 가장 작은 값은?

- 의미/생성 근거: 주별 passage speed max → min of weekly maxima, 숫자 반환.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): DPO pair가 아닌 신규 gold 후보
- Human 확인: Compiler의 grouped passage 계약 미확정은 실행 gap으로 보존; 속도 sum이나 최소 주 선택으로 바꾸지 않음. / 신규 원문의 통계/공간 해석과 평가 paraphrase lineage를 사람이 확인해야 함.
- 권고: accepted (참고용); 실제 pending

### RB002-05 — rare_measure (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 15일 가람시 안의 택시 통행을 읍면동별로 세어, 기록이 있는 그룹 중 건수가 적은 3곳은?

- 의미/생성 근거: passage 사건 수를 emd별로 집계하여 bottom 3. 기록 없는 행정구역 zero-fill을 요청하지 않음.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): DPO pair가 아닌 신규 gold 후보
- Human 확인: 가람시는 합성 literal 명칭; scope와 dimension의 포함 관계/동률 결과는 실제 provider 검증이 필요. / 신규 원문의 통계/공간 해석과 평가 paraphrase lineage를 사람이 확인해야 함.
- 권고: accepted (참고용); 실제 pending

### RB002-06 — rare_measure (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 15일 가람시 안의 택시 통행을 시군구별로 세어, 기록이 있는 그룹 중 건수가 적은 3곳은?

- 의미/생성 근거: passage 사건 수를 sigungu별로 집계하여 bottom 3; trip_count나 OD 승하차 차원이 아님.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): DPO pair가 아닌 신규 gold 후보
- Human 확인: 읍면동 질문과 다른 집계 수준. 합성 가람시 scope 포함 관계·동률·자료 없음 처리는 실행 검증 범위. / 신규 원문의 통계/공간 해석과 평가 paraphrase lineage를 사람이 확인해야 함.
- 권고: accepted (참고용); 실제 pending

### RB002-07 — rare_measure (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 15일 가람구 소속 개인택시의 각 전체 운행 경로에 기록된 공차율 값들을 산술평균하면?

- 의미/생성 근거: 각 drive 기록의 vacant_ratio를 동일 가중 평균. 전체 집단 active/registered 비율이나 총 공차거리/총거리와 다름.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): DPO pair가 아닌 신규 gold 후보
- Human 확인: 개별 drive 공차율의 세부 분자/분모와 단위는 provider 정의. 질문은 이미 기록된 비율 값의 평균을 명시. / 신규 원문의 통계/공간 해석과 평가 paraphrase lineage를 사람이 확인해야 함.
- 권고: accepted (참고용); 실제 pending

### RB002-08 — rare_measure (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 15일 가람구 소속 법인택시의 개별 전체 운행 경로에 기록된 공차율 최댓값은?

- 의미/생성 근거: 각 drive의 기록된 vacant_ratio 값 중 max; taxi_type=corporate.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): DPO pair가 아닌 신규 gold 후보
- Human 확인: 분모 0인 기록과 공차율 값의 세부 정의는 실행 계약 확인 필요; 가동률로 치환하지 않음. / 신규 원문의 통계/공간 해석과 평가 paraphrase lineage를 사람이 확인해야 함.
- 권고: accepted (참고용); 실제 pending

### RB002-09 — rare_measure (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 15일 가람구에서 관측된 도로 통행의 엔진 회전수 최솟값은?

- 의미/생성 근거: 장소는 passage 발생 위치라고 원문에 명시. 단일 구간 RPM min.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): DPO pair가 아닌 신규 gold 후보
- Human 확인: RB001-17–20의 소속/발생 위치 모호한 원문을 재사용하지 않음. RPM 결측/빈 표본의 수치 실행은 별도. / 신규 원문의 통계/공간 해석과 평가 paraphrase lineage를 사람이 확인해야 함.
- 권고: accepted (참고용); 실제 pending

### RB002-10 — rare_measure (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 15일 가람구에서 관측된 도로 통행의 엔진 회전수 최댓값은?

- 의미/생성 근거: 장소는 passage 발생 위치. 단일 구간 RPM max; 미래 예측/소속 cohort 의미 없음.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): DPO pair가 아닌 신규 gold 후보
- Human 확인: RPM sum은 정의되지 않음; 기존 grouped RPM hold와 다른 명시적 단일 구간 질문. / 신규 원문의 통계/공간 해석과 평가 paraphrase lineage를 사람이 확인해야 함.
- 권고: accepted (참고용); 실제 pending

### RB002-11 — unsupported_boundary (DIAGNOSTIC_ONLY_NOT_TRAINABLE)

2026년 9월 15일 가람구에서 관측된 도로 통행의 타이어 공기압 최댓값은?

- 의미/생성 근거: 요청한 metric/사건 상태가 현재 ontology와 provider schema에 없음. 비슷한 지원 metric으로 대체하면 오답.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): 지원 analog의 RPM 또는 passage_count를 반환하면 실제로 묻지 않은 metric/사건을 답한다. JSON/graph가 valid여도 잘못된 강제 지원이다.
- Human 확인: Semantic unsupported와 provider 미구현을 혼동하지 않음. 현재 모든 unsupported는 보호 family이며 이 후보는 training 편입 불가.
- 권고: needs_fix (참고용); 실제 pending

### RB002-12 — unsupported_boundary (DIAGNOSTIC_ONLY_NOT_TRAINABLE)

2026년 9월 15일 가람시 안의 안전벨트 미착용 적발을 읍면동별로 세어, 기록이 있는 그룹 중 건수가 적은 3곳은?

- 의미/생성 근거: 요청한 metric/사건 상태가 현재 ontology와 provider schema에 없음. 비슷한 지원 metric으로 대체하면 오답.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): 지원 analog의 RPM 또는 passage_count를 반환하면 실제로 묻지 않은 metric/사건을 답한다. JSON/graph가 valid여도 잘못된 강제 지원이다.
- Human 확인: Semantic unsupported와 provider 미구현을 혼동하지 않음. 현재 모든 unsupported는 보호 family이며 이 후보는 training 편입 불가.
- 권고: needs_fix (참고용); 실제 pending

### RB002-13 — actual_hard_negative (TRAINABLE_AFTER_HUMAN_REVIEW)

지난달 수성구 개인택시의 주별 운행일수 합계를 평균 내면?

- 의미/생성 근거: Chosen은 v001의 accepted train gold이며, rejected는 실제 frozen Base/SFT/DPO 출력에서 가져온 다중 오류 grounding.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-d983889cf8c496178106", "prior_human_decision_hash": "efc95bcd0001d0d4a40213dea5c907f6f3f9330c976990422ece932012f1b734", "canonical_grounding_hash": "e11cabb32313e8d953e89f5f595feaf7723ed552f033b59742930a9f61079fce", "prior_batch_item_id": "RB001-01", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 실측 출력은 MISSING_CONCEPT_VALUE, concept_subtype, factor_omission, role, source_value 오류를 포함한다. 질문의 date/taxi_type/location이 사라지거나 EVENT source/role/value와 subtype가 잘못됨. 구문 손상으로 만든 negative가 아님.
- Human 확인: 여러 잘못된 필드가 함께 있어 단일 오류의 기여도를 추정하지 않음. Legacy normalization/repair 전 raw 계약과 production 결과를 함께 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-14 — actual_hard_negative (TRAINABLE_AFTER_HUMAN_REVIEW)

지난달 수성구 개인택시의 주별 운행일수 합계를 평균 내면?

- 의미/생성 근거: Chosen은 v001의 accepted train gold이며, rejected는 실제 frozen Base/SFT/DPO 출력에서 가져온 다중 오류 grounding.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-d983889cf8c496178106", "prior_human_decision_hash": "efc95bcd0001d0d4a40213dea5c907f6f3f9330c976990422ece932012f1b734", "canonical_grounding_hash": "e11cabb32313e8d953e89f5f595feaf7723ed552f033b59742930a9f61079fce", "prior_batch_item_id": "RB001-01", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 실측 출력은 MISSING_CONCEPT_VALUE, concept_subtype, factor_omission, role, source_value 오류를 포함한다. 질문의 date/taxi_type/location이 사라지거나 EVENT source/role/value와 subtype가 잘못됨. 구문 손상으로 만든 negative가 아님.
- Human 확인: 여러 잘못된 필드가 함께 있어 단일 오류의 기여도를 추정하지 않음. Legacy normalization/repair 전 raw 계약과 production 결과를 함께 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-15 — actual_hard_negative (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 상반기 동구 법인택시 월별 매출 평균 중 가장 큰 값은?

- 의미/생성 근거: Chosen은 v001의 accepted train gold이며, rejected는 실제 frozen Base/SFT/DPO 출력에서 가져온 다중 오류 grounding.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-cc38d74754ba7eab68a8", "prior_human_decision_hash": "d3111dd9b68a69a07d972502d899d0f673088817fe051a1ba3c93624a5fe8915", "canonical_grounding_hash": "69531db7e79e11b651ac2ec55df06a6f2bcda7467d09b0de14aacd189cbd3aef", "prior_batch_item_id": "RB001-02", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 실측 출력은 MISSING_CONCEPT_VALUE, aggregation_stage, concept_subtype, factor_omission, role, source_value 오류를 포함한다. 질문의 date/taxi_type/location이 사라지거나 EVENT source/role/value와 subtype가 잘못됨. 구문 손상으로 만든 negative가 아님.
- Human 확인: 여러 잘못된 필드가 함께 있어 단일 오류의 기여도를 추정하지 않음. Legacy normalization/repair 전 raw 계약과 production 결과를 함께 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-16 — actual_hard_negative (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 8월 나래구 개인택시 주별 매출 합계 중 가장 작은 값은?

- 의미/생성 근거: Chosen은 v001의 accepted train gold이며, rejected는 실제 frozen Base/SFT/DPO 출력에서 가져온 다중 오류 grounding.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-da98b3941dfa1c7ce800", "prior_human_decision_hash": "e07c9147fd7adac02c57d7dfbb4ed8a41993a0c30493b31d583113fc5022f0af", "canonical_grounding_hash": "4ddf600e8c90fb9bb5359942198baf84ba53ac7c02f06cfb372c3e5f40280fd1", "prior_batch_item_id": "RB001-03", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 실측 출력은 INVALID_FACTOR, aggregation_stage, concept_subtype, factor_omission, factor_value, role, source_value 오류를 포함한다. 질문의 date/taxi_type/location이 사라지거나 EVENT source/role/value와 subtype가 잘못됨. 구문 손상으로 만든 negative가 아님.
- Human 확인: 여러 잘못된 필드가 함께 있어 단일 오류의 기여도를 추정하지 않음. Legacy normalization/repair 전 raw 계약과 production 결과를 함께 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-17 — actual_hard_negative (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 8월 나래구 개인택시 주별 매출 합계 중 가장 작은 값은?

- 의미/생성 근거: Chosen은 v001의 accepted train gold이며, rejected는 실제 frozen Base/SFT/DPO 출력에서 가져온 다중 오류 grounding.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-da98b3941dfa1c7ce800", "prior_human_decision_hash": "e07c9147fd7adac02c57d7dfbb4ed8a41993a0c30493b31d583113fc5022f0af", "canonical_grounding_hash": "4ddf600e8c90fb9bb5359942198baf84ba53ac7c02f06cfb372c3e5f40280fd1", "prior_batch_item_id": "RB001-03", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 실측 출력은 INVALID_FACTOR, concept_subtype, factor_value, od_dimension, role, source_value 오류를 포함한다. 질문의 date/taxi_type/location이 사라지거나 EVENT source/role/value와 subtype가 잘못됨. 구문 손상으로 만든 negative가 아님.
- Human 확인: 여러 잘못된 필드가 함께 있어 단일 오류의 기여도를 추정하지 않음. Legacy normalization/repair 전 raw 계약과 production 결과를 함께 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-18 — actual_hard_negative (TRAINABLE_AFTER_HUMAN_REVIEW)

지난달 동구 법인택시 주별 운행일수 평균 중 가장 작은 값은?

- 의미/생성 근거: Chosen은 v001의 accepted train gold이며, rejected는 실제 frozen Base/SFT/DPO 출력에서 가져온 다중 오류 grounding.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-89f3d036b2d43dd431f0", "prior_human_decision_hash": "d6854f0e1d93211d6902359c65a0c8772b36d8f85910389df90e1e52aece3c6c", "canonical_grounding_hash": "ea8076684d58dea66817101ec0ecca0189c7542d3af4fb970eabf20acac75bf2", "prior_batch_item_id": "RB001-06", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 실측 출력은 MISSING_CONCEPT_VALUE, aggregation_stage, concept_subtype, factor_omission, role, source_value 오류를 포함한다. 질문의 date/taxi_type/location이 사라지거나 EVENT source/role/value와 subtype가 잘못됨. 구문 손상으로 만든 negative가 아님.
- Human 확인: 여러 잘못된 필드가 함께 있어 단일 오류의 기여도를 추정하지 않음. Legacy normalization/repair 전 raw 계약과 production 결과를 함께 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-19 — actual_hard_negative (TRAINABLE_AFTER_HUMAN_REVIEW)

지난달 동구 법인택시의 운행일수 평균이 가장 적었던 주는?

- 의미/생성 근거: Chosen은 v001의 accepted train gold이며, rejected는 실제 frozen Base/SFT/DPO 출력에서 가져온 다중 오류 grounding.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-aa1d7fd59c1d3d2ea97b", "prior_human_decision_hash": "932a3fb6f5ef622a14242c927f8112967a2f9933481243fd8cc3d14ef0989ccf", "canonical_grounding_hash": "eb89cfaeabc1d391ad685e49c1659152373707e6e514b64dd3482d93582e6b4f", "prior_batch_item_id": "RB001-07", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 실측 출력은 MISSING_CONCEPT_VALUE, concept_subtype, factor_omission, role, source_value 오류를 포함한다. 질문의 date/taxi_type/location이 사라지거나 EVENT source/role/value와 subtype가 잘못됨. 구문 손상으로 만든 negative가 아님.
- Human 확인: 여러 잘못된 필드가 함께 있어 단일 오류의 기여도를 추정하지 않음. Legacy normalization/repair 전 raw 계약과 production 결과를 함께 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-20 — actual_hard_negative (TRAINABLE_AFTER_HUMAN_REVIEW)

지난달 달서구 개인택시 주별 운행일수 평균들의 평균은?

- 의미/생성 근거: Chosen은 v001의 accepted train gold이며, rejected는 실제 frozen Base/SFT/DPO 출력에서 가져온 다중 오류 grounding.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-f8d44f2cfa96200b5a95", "prior_human_decision_hash": "f13df5805c9c749e5fe7b6d8ca92bbe8a9bc34c71f8873ad88ac5762ce7d717c", "canonical_grounding_hash": "6fc09d6a34926372f425c304ee78aa7a6a70c311ea76ee0bcd3679cde490cf6f", "prior_batch_item_id": "RB001-08", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 실측 출력은 MISSING_CONCEPT_VALUE, concept_subtype, factor_omission, role, source_value 오류를 포함한다. 질문의 date/taxi_type/location이 사라지거나 EVENT source/role/value와 subtype가 잘못됨. 구문 손상으로 만든 negative가 아님.
- Human 확인: 여러 잘못된 필드가 함께 있어 단일 오류의 기여도를 추정하지 않음. Legacy normalization/repair 전 raw 계약과 production 결과를 함께 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-21 — semantic_contrast (TRAINABLE_AFTER_HUMAN_REVIEW)

지난달 수성구 개인택시의 주별 운행일수 합계를 평균 내면?

- 의미/생성 근거: 원문의 장소명은 조회 전 SUBCOND. COND는 사용자가 직접 준 scope에 대응한다. 장소 value는 동일하더라도 raw role 의미가 잘못됨.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-d983889cf8c496178106", "prior_human_decision_hash": "efc95bcd0001d0d4a40213dea5c907f6f3f9330c976990422ece932012f1b734", "canonical_grounding_hash": "e11cabb32313e8d953e89f5f595feaf7723ed552f033b59742930a9f61079fce", "prior_batch_item_id": "RB001-01", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 원문의 장소명은 조회 전 SUBCOND. COND는 사용자가 직접 준 scope에 대응한다. 장소 value는 동일하더라도 raw role 의미가 잘못됨.
- Human 확인: Synthetic single-control는 실측 prediction이라고 주장하지 않음. Chosen과 rejected의 의미 및 변경 필드를 따로 사람이 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-22 — semantic_contrast (TRAINABLE_AFTER_HUMAN_REVIEW)

지난달 수성구 개인택시의 주별 운행일수 합계를 평균 내면?

- 의미/생성 근거: 수성구는 질문에서 제공된 장소 값이므로 source=user. implicit은 값 없는 EVENT/MEASURE에만 사용한다. Graph PASS가 이 source 오류를 잡지 못할 수 있음.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-d983889cf8c496178106", "prior_human_decision_hash": "efc95bcd0001d0d4a40213dea5c907f6f3f9330c976990422ece932012f1b734", "canonical_grounding_hash": "e11cabb32313e8d953e89f5f595feaf7723ed552f033b59742930a9f61079fce", "prior_batch_item_id": "RB001-01", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 수성구는 질문에서 제공된 장소 값이므로 source=user. implicit은 값 없는 EVENT/MEASURE에만 사용한다. Graph PASS가 이 source 오류를 잡지 못할 수 있음.
- Human 확인: Synthetic single-control는 실측 prediction이라고 주장하지 않음. Chosen과 rejected의 의미 및 변경 필드를 따로 사람이 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-23 — semantic_contrast (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 15일 가람구 소속 법인택시의 개별 전체 운행 경로에 기록된 공차율 최댓값은?

- 의미/생성 근거: 질문은 공차율 최댓값을 물었고 0.25라는 값을 제공하지 않았다. MEASURE는 implicit/value 없음이어야 하며 source=user+value=0.25는 결과/입력의 혼동.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "approval_dependency": "RB002-08", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): 질문은 공차율 최댓값을 물었고 0.25라는 값을 제공하지 않았다. MEASURE는 implicit/value 없음이어야 하며 source=user+value=0.25는 결과/입력의 혼동.
- Human 확인: Synthetic single-control는 실측 prediction이라고 주장하지 않음. Chosen과 rejected의 의미 및 변경 필드를 따로 사람이 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-24 — semantic_contrast (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 상반기 동구 법인택시 월별 매출 평균 중 가장 큰 값은?

- 의미/생성 근거: 법인택시가 명시되었는데 corporate factor를 제거하면 대상 집단이 달라진다. Optional factor라 구조가 valid여도 의미 오류.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-cc38d74754ba7eab68a8", "prior_human_decision_hash": "d3111dd9b68a69a07d972502d899d0f673088817fe051a1ba3c93624a5fe8915", "canonical_grounding_hash": "69531db7e79e11b651ac2ec55df06a6f2bcda7467d09b0de14aacd189cbd3aef", "prior_batch_item_id": "RB001-02", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 법인택시가 명시되었는데 corporate factor를 제거하면 대상 집단이 달라진다. Optional factor라 구조가 valid여도 의미 오류.
- Human 확인: Synthetic single-control는 실측 prediction이라고 주장하지 않음. Chosen과 rejected의 의미 및 변경 필드를 따로 사람이 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-25 — semantic_contrast (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 15일 가람구에서 기록된 도로 통행의 주행 속도 최솟값은?

- 의미/생성 근거: 시간대가 없는 속도 질문에 22:00–23:59:59를 추가하면 질문에 없는 관측 제한을 만든다. 기존 factor-hallucination 다중 오류를 분리한 control.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "approval_dependency": "RB002-03", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): 시간대가 없는 속도 질문에 22:00–23:59:59를 추가하면 질문에 없는 관측 제한을 만든다. 기존 factor-hallucination 다중 오류를 분리한 control.
- Human 확인: Synthetic single-control는 실측 prediction이라고 주장하지 않음. Chosen과 rejected의 의미 및 변경 필드를 따로 사람이 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-26 — semantic_contrast (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 15일 가람구 소속 택시의 실차 구간별 요금 중앙값은?

- 의미/생성 근거: 승객 요금은 trip/fare이고 1일 영업 수입은 operation/revenue다. EVENT까지 일관되게 바꾼 structurally valid semantic negative. Pilot에서 fare→revenue 자체가 관측되었다고 주장하지 않고 concept/subtype 오류와 신규 fare coverage를 보완한다.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "approval_dependency": "RB002-01", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): 승객 요금은 trip/fare이고 1일 영업 수입은 operation/revenue다. EVENT까지 일관되게 바꾼 structurally valid semantic negative. Pilot에서 fare→revenue 자체가 관측되었다고 주장하지 않고 concept/subtype 오류와 신규 fare coverage를 보완한다.
- Human 확인: Synthetic single-control는 실측 prediction이라고 주장하지 않음. Chosen과 rejected의 의미 및 변경 필드를 따로 사람이 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-27 — aggregation_contrast (TRAINABLE_AFTER_HUMAN_REVIEW)

지난달 수성구 개인택시의 주별 운행일수 합계를 평균 내면?

- 의미/생성 근거: 주별 운행일수 합계의 평균(sum→avg)을 주별 평균의 합(avg→sum)으로 바꾼다. 집계 두 축과 분모가 다르므로 일반적으로 다른 값.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-d983889cf8c496178106", "prior_human_decision_hash": "efc95bcd0001d0d4a40213dea5c907f6f3f9330c976990422ece932012f1b734", "canonical_grounding_hash": "e11cabb32313e8d953e89f5f595feaf7723ed552f033b59742930a9f61079fce", "prior_batch_item_id": "RB001-01", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 주별 운행일수 합계의 평균(sum→avg)을 주별 평균의 합(avg→sum)으로 바꾼다. 집계 두 축과 분모가 다르므로 일반적으로 다른 값.
- Human 확인: Synthetic single-control는 실측 prediction이라고 주장하지 않음. Chosen과 rejected의 의미 및 변경 필드를 따로 사람이 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-28 — aggregation_contrast (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 8월 나래구 개인택시 주별 매출 합계 중 가장 작은 값은?

- 의미/생성 근거: 주별 revenue 합계 중 최솟값(sum→min)을 주별 최소 revenue의 합(min→sum)으로 바꾼다. Chosen은 reference 범위에서 이미 검토된 통계.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-da98b3941dfa1c7ce800", "prior_human_decision_hash": "e07c9147fd7adac02c57d7dfbb4ed8a41993a0c30493b31d583113fc5022f0af", "canonical_grounding_hash": "4ddf600e8c90fb9bb5359942198baf84ba53ac7c02f06cfb372c3e5f40280fd1", "prior_batch_item_id": "RB001-03", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 주별 revenue 합계 중 최솟값(sum→min)을 주별 최소 revenue의 합(min→sum)으로 바꾼다. Chosen은 reference 범위에서 이미 검토된 통계.
- Human 확인: Synthetic single-control는 실측 prediction이라고 주장하지 않음. Chosen과 rejected의 의미 및 변경 필드를 따로 사람이 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-29 — aggregation_contrast (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 상반기 동구 법인택시 월별 매출 평균 중 가장 큰 값은?

- 의미/생성 근거: 월 평균들 중 최대를 전체 기간 평균 하나로 축약한다. JSON/graph가 valid여도 질문의 monthly grouping과 outer max가 사라짐.
- Chosen 신뢰: {"level": "reviewed_gold_v001_train", "corpus_manifest_hash": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9", "source_record_id": "ann-cc38d74754ba7eab68a8", "prior_human_decision_hash": "d3111dd9b68a69a07d972502d899d0f673088817fe051a1ba3c93624a5fe8915", "canonical_grounding_hash": "69531db7e79e11b651ac2ec55df06a6f2bcda7467d09b0de14aacd189cbd3aef", "prior_batch_item_id": "RB001-02", "human_rejected_confirmation_required": true}
- Rejected 오류(제안): 월 평균들 중 최대를 전체 기간 평균 하나로 축약한다. JSON/graph가 valid여도 질문의 monthly grouping과 outer max가 사라짐.
- Human 확인: Synthetic single-control는 실측 prediction이라고 주장하지 않음. Chosen과 rejected의 의미 및 변경 필드를 따로 사람이 확인.
- 권고: accepted (참고용); 실제 pending

### RB002-30 — constraint_contrast (TRAINABLE_AFTER_HUMAN_REVIEW)

2026년 9월 15일 가람구에서 관측된 도로 통행의 엔진 회전수 최솟값은?

- 의미/생성 근거: 원문은 passage RPM의 최솟값이다. sum으로 바꾸면 intensive quantity에 정의되지 않은 집계를 적용하여 기존 measure/composer 계약을 위반한다. JSON 손상이 아닌 최소 domain-constraint control.
- Chosen 신뢰: {"level": "proposed_not_reviewed", "approval_dependency": "RB002-09", "human_chosen_confirmation_required": true}
- Rejected 오류(제안): 원문은 passage RPM의 최솟값이다. sum으로 바꾸면 intensive quantity에 정의되지 않은 집계를 적용하여 기존 measure/composer 계약을 위반한다. JSON 손상이 아닌 최소 domain-constraint control.
- Human 확인: Synthetic single-control는 실측 prediction이라고 주장하지 않음. Chosen과 rejected의 의미 및 변경 필드를 따로 사람이 확인.
- 권고: accepted (참고용); 실제 pending

## 동결 확인

- 기준 corpus_manifest SHA256: `59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9`.
- production prompt hash: `522aa3b1716248b53a755ee1b236e7aef302c85504e9cfac3825f4d3cc817945`.
- seed: 42. 모든 old source/hash, v001 12 files, 기존 11 hold, 기존 queue 96 pending 및 protected 50을 무변경 확인.
- GPU 학습, 모델 inference, import, decisions 기록, production code/schema/prompt 변경은 하지 않았다.
