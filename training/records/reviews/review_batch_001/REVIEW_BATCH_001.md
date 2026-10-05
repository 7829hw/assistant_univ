# REVIEW_BATCH_001

첫 human review 자료다. **추천은 참고용이며 actual status는 전부 pending**이다. GPU inference/training, 새 candidate 생성, production 수정, 자동 승인을 하지 않았다.

30 record / 21개 서로 다른 질문. 같은 질문의 gold와 DPO contrast는 별도 승인 단위다. Corpus에는 동일 gold 질문을 한 번만 저장한다.

## 파일과 검토 순서

`review_batch_001.xlsx`의 첫 sheet는 question/proposed/existing/Base/SFT/DPO/contrast/검증을 나란히 보여준다. JSON은 wrap된 cell을 선택하거나 JSONL에서 전체를 확인한다. 새 질문에 과거 prediction이 없으면 없다고 적었다. 다른 dev 질문의 예측을 붙이지 않았다.

`Eligible_46_priority` sheet 및 `eligible_46_priority.jsonl`에 포함 가능한 46건 전체를 우선순위대로 정리했다. 기존 gold 15건 중 보호된 6건은 batch에 넣지 않았다. 보호/진단 전용 50건은 원본 queue에 그대로 유지한다.

| Priority | Category | Eligible | Batch |
|---:|---|---:|---:|
| 1 | 기존 gold 재검토 | 9 | 9 |
| 2 | source/role/value/factor | 3 | 3 |
| 3 | inner/outer 집계 및 stage contrast | 8 | 8 |
| 4 | OD direction/dimension/target | 10 | 10 |
| 5 | rare MEASURE | 4 | 0 |
| 6 | unsupported/ambiguity | 0 | 0 |
| 7 | train-origin hard negative | 12 | 0 |

추천: accepted 16, rejected 0, needs_fix 14. 실제 accepted=0.

## 사람이 판정할 내용

- user source는 단어가 질문에 등장한다는 의미가 아니라 주어진 값의 출처다. 장소 value와 SUBCOND, implicit EVENT SUPPORT/MEASURE, date/taxi_type factors를 확인한다.
- aggregation은 구간 안, rollup은 구간 간이다. answer=value와 answer=bucket, 평균들의 평균과 전체 평균을 구분한다.
- OD scope의 od_role은 장소 filter이고 dimension_target은 결과를 묶을 승/하차 쪽이다. Gold와 contrast 둘 다 validator PASS여도 둘 다 맞는 것은 아니다.
- active_taxi_count/ratio의 기간 평균·중앙값/표본 단위는 정의를 확인해야 한다. 임의로 sum/unsupported로 바꾸지 않는다.
- 추가 TIMS legacy static compilation은 production 모듈을 읽기 전용으로 재사용한 진단이며 실제 execution은 하지 않았다. 구간 선택 및 RPM bucket에서 UNVERIFIED_TIMS_CONTRACT가 발생한다. Grounding 의미가 명확해도 product 지원 라벨은 재검토해야 한다.
- Base/SFT/DPO는 저장된 실제 raw 출력이다. strict raw 검사, production normalization 검사, 과거 pilot 결과를 구분한다. 실행 실패를 곧 grounding 오답으로 간주하지 않는다.
- 합성 지명을 포함한 질문은 corpus의 grounding 용도와 실제 provider의 장소 지원을 구분해서 검토한다. Parent/paraphrase lineage도 확인한다.

### 추천 needs_fix 항목

- **RB001-04** (ann-77e9dacb0b34a3273630): 2026년 8월 나래구 개인택시 매출 평균이 가장 낮았던 주는 언제야? — aggregation_stage_review_required, gold_vs_model_requires_review, independent_paraphrase_lineage_review, legacy_normalization_masks_raw_contract, production_support_boundary_uncertain, synthetic_location_context_review
- **RB001-05** (ann-9d8392a4f8ca9ff8cfc2): 2026년 상반기 중구 개인택시 운행일수 합계가 가장 많았던 달은? — aggregation_stage_review_required, gold_vs_model_requires_review, independent_paraphrase_lineage_review, legacy_normalization_masks_raw_contract, production_support_boundary_uncertain
- **RB001-07** (ann-aa1d7fd59c1d3d2ea97b): 지난달 동구 법인택시의 운행일수 평균이 가장 적었던 주는? — aggregation_stage_review_required, gold_vs_model_requires_review, independent_paraphrase_lineage_review, production_support_boundary_uncertain
- **RB001-10** (ann-09781f452047f59303e6): 2026년 9월 솔빛동 주변 개인택시의 평균 가동 택시 대수는? — independent_paraphrase_lineage_review, semantic_ambiguity, subtype_definition_uncertain, synthetic_location_context_review
- **RB001-11** (ann-6c2bd47856a19597967e): 2026년 9월 솔빛동 주변 법인택시의 평균 가동 택시 대수는? — independent_paraphrase_lineage_review, semantic_ambiguity, subtype_definition_uncertain, synthetic_location_context_review
- **RB001-12** (ann-baaeabe98162ddefb291): 2026년 9월 해솔동 개인택시 가동률의 중앙값은? — independent_paraphrase_lineage_review, semantic_ambiguity, subtype_definition_uncertain, synthetic_location_context_review
- **RB001-13** (ann-8e3ffbfb226687ea91f7): 2026년 8월과 9월 온유동의 월별 가동 택시 대수 최솟값의 평균은? — aggregation_stage_interpretation_uncertain, aggregation_stage_review_required, independent_paraphrase_lineage_review, semantic_ambiguity, subtype_definition_uncertain, synthetic_location_context_review
- **RB001-14** (ann-3e7a8b41ae12f1f07b6a): 2026년 8월과 9월 온유동의 월별 가동 택시 대수 최솟값의 평균은? — aggregation_stage_interpretation_uncertain, aggregation_stage_review_required, chosen_rejected_semantic_preference_review, independent_paraphrase_lineage_review, semantic_ambiguity, subtype_definition_uncertain, synthetic_location_context_review
- **RB001-15** (ann-27dea2872a7d3a693dd3): 2026년 8월과 9월 온유동의 월별 평균 가동 택시 대수 중 최솟값은? — aggregation_stage_interpretation_uncertain, aggregation_stage_review_required, independent_paraphrase_lineage_review, semantic_ambiguity, subtype_definition_uncertain, synthetic_location_context_review
- **RB001-16** (ann-7fd10e4e8f2aafdd01e5): 2026년 8월과 9월 온유동의 월별 평균 가동 택시 대수 중 최솟값은? — aggregation_stage_interpretation_uncertain, aggregation_stage_review_required, chosen_rejected_semantic_preference_review, independent_paraphrase_lineage_review, semantic_ambiguity, subtype_definition_uncertain, synthetic_location_context_review
- **RB001-17** (ann-24f8831f1b471e2206fd): 2026년 9월 솔빛동 택시의 주마다 구한 엔진 회전수 최댓값의 평균은? — aggregation_stage_review_required, independent_paraphrase_lineage_review, production_support_boundary_uncertain, synthetic_location_context_review
- **RB001-18** (ann-54b0fa2b0c5279bf2201): 2026년 9월 솔빛동 택시의 주마다 구한 엔진 회전수 최댓값의 평균은? — aggregation_stage_review_required, chosen_rejected_semantic_preference_review, independent_paraphrase_lineage_review, production_support_boundary_uncertain, synthetic_location_context_review
- **RB001-19** (ann-779d38516eaca5162eb1): 2026년 9월 솔빛동 택시의 주마다 평균 낸 엔진 회전수 중 최댓값은? — aggregation_stage_review_required, independent_paraphrase_lineage_review, production_support_boundary_uncertain, synthetic_location_context_review
- **RB001-20** (ann-0f7e48b754510a2647d4): 2026년 9월 솔빛동 택시의 주마다 평균 낸 엔진 회전수 중 최댓값은? — aggregation_stage_review_required, chosen_rejected_semantic_preference_review, independent_paraphrase_lineage_review, production_support_boundary_uncertain, synthetic_location_context_review

## 실제 판정 기록

XLSX/JSONL은 비교용 view이다. 추천을 status로 복사하지 않는다. 검토 후 아래 명령으로 원본 candidate ID/hash에 판정을 남긴다. 사람이 판단한 경우에만 confirmation flag를 쓴다. 응답을 RB001-번호별로 제공해도 원본 candidate ID로 대응할 수 있다.

```bash
python -m training.annotations.workflow decide \
  --queue /home/hwkim/assistant_univ/training/annotations/generated/expansion_001 \
  --decisions /home/hwkim/assistant_univ/training/annotations/generated/review_batch_001/decisions.jsonl \
  --id ann-d983889cf8c496178106 --status needs_fix \
  --reviewer YOUR_NAME --reason '검토한 근거와 수정 필요 내용을 입력'
```

`--status accepted`에는 `--semantic-checks-confirmed`가 필요하다. Contrast/pair에는 chosen이 맞고 rejected가 틀린 이유를 적고 `--negative-is-wrong`도 지정한다. 수정할 JSON이 있으면 `--corrected-grounding` 또는 `--corrected-rejected`를 사용한다. `rejected`/`needs_fix`는 export되지 않는다.

## 검토 후 import

원본 96건 queue를 대상으로 batch 전용 decision audit만 읽는다. View JSONL을 training builder에 직접 넣지 않는다. Accepted gold가 서로 분리 가능한 2개 이상의 semantic/contrast family를 포함해야 train/validation export가 가능하다. 최소 DPO split coverage도 확인하고 아직 학습은 시작하지 않는다.

```bash
python -m training.annotations.workflow import-reviewed \
  --queue /home/hwkim/assistant_univ/training/annotations/generated/expansion_001 \
  --decisions /home/hwkim/assistant_univ/training/annotations/generated/review_batch_001/decisions.jsonl \
  --version reviewed_gold_v001 \
  --output /home/hwkim/assistant_univ/training/annotations/generated/corpora/reviewed_gold_v001 \
  --seed 42 --valid-fraction 0.2
```

Import는 queue/source/protection/prompt hash와 실제 semantic review attestation, canonical planner JSON, parse/compose/G1~G7, group leakage, identical pair를 다시 검사한다. 추천 accepted는 이 검사를 대신하지 않는다.
