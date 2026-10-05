# REVIEW_BATCH_003

34 pending candidates = 20 new SFT gold proposals + 14 DPO pairs. Auto accepted/import/export/inference/training: 0. Frozen v001/v002, original holds and diagnostics are unchanged.

## Review files

- review_batch_003.xlsx: Train_candidates / Validation_candidates / Coverage_and_plan / Token_budget. Frozen header and wrapped text; no formulas.
- review_batch_003.jsonl + review_queue.jsonl: hash-bound source of question, chosen/rejected, recommendations, actual predictions, provenance and strict/normalized diagnostics.
- coverage_expected.json and split_plan.json: conditional coverage and pre-review family-level split reservations. Not training data.

## Review priorities

RB003-01–04: date as factor; this_week/last_week siblings stay train; last_month/explicit interval siblings stay validation.
RB003-05–08: fare/speed distinct multi-stage statistic families. RPM train and validation are covered by01–04.
RB003-09–12: already-provided scope(COND/user/value) vs unresolved place(SUBCOND/user/value); event/measure implicit/value absent.
RB003-13–17: two endpoint filters plus separate grouping dimension; validation expands pickup/dropoff/both.
RB003-18–20: inner/outer reducers, numeric value vs selected month; positive contrast siblings stay validation.
RB003-21–24: actual train-origin model negatives, all chosen hash-linked to approved v002 train records.
RB003-25–34: explicitly synthetic, single-control semantic negatives. Each needs its new chosen approved first.

## Why these families are independent

Family guard ignores wording/place/date/source changes and keeps measure, aggregation, answer, dimension/target/order and endpoint filter semantics. Checks use Protection.current(v002), inferred family fingerprints, templates and explicit contrast groups, plus all historical train families. No existing protected family is moved to training. New validation fingerprints are absent from previous labeled protected development/pilot corpora and existing train.

Bare RPM median was explicitly avoided: assistant_univ_questions_100_v3.yaml already has that dev question despite no structured gold. RPM validation uses a genuinely different multi-week median→mean statistic, not date/place-only substitution. All question-only reserved sets still require human paraphrase lineage review; absence of an automatic family match is not proof of independence.

Train/valid stage-swapped positive siblings and numeric-vs-dimension siblings are kept together via contrast_group, even when inferred fingerprints differ. Nontrain pilot errors are evidence drivers only; they never become training rejected predictions. A new question with no inference has predictions.available=false.

## Statistical and runtime meaning

Fare = trip fare, with Billing所属-region scope (provider definition), not taxi-day revenue. Speed/RPM = passage records at occurrence location; arithmetic means are record-weighted inside the bucket and bucket summaries equally weighted outside. Period counts/missing-day denominators are not changed. OD uses two LOCATION/place filters (pickup and dropoff) and distinct dimension_target grouping. Place names are synthetic literal contexts with region empty; scope literals occur explicitly in questions. No user scope is invented by the assistant.

Raw targets are the canonical production flat contract. parse_grounding(normalize=False/True), MacroComposer and all G1–G7 are reused. Static TIMS compilation is diagnostic only; grouped measure compiler limits or synthetic geography do not mean semantic unsupported. New candidates are excluded from actual execution benchmark until separate provider/location validation.

## Actual negatives vs semantic controls

Only two production-valid actual train semantic negatives were available. They contain legacy taxi-type normalization and place-role differences; strict raw may fail while production composes. They are advisory needs_fix pending human confirmation of the raw semantic/contract boundary. No raw prediction is silently corrected or relabelled as a pure single-field semantic error. Two additional real fare/speed failures retain date/source/concept errors as constraint pairs. All four actual negatives are new relative to existing v002 DPO pairs.

The ten synthetic controls isolate the observed failure capabilities and guarantee non-OD semantic validation: date relative confusion/omission, place source, place role, hallucinated measure input value, OD target, stage swap, answer-dimension omission, fare→revenue and speed→RPM. They are not new model observations. Graph PASS is deliberately insufficient; source/role/value can be wrong even when downstream accepts it.

## Split/import policy

Planned splits are reservations, not approved status. Preserve v00212/5 and16/4 exactly. Accepted chosen and every pair must remain on the reserved family side; hard negatives stay with their existing train anchors. **Do not run the standalone generic importer to randomly re-split this batch**: it currently ignores planned_split and does not merge the v002 baseline. After human review, reviewed v003 assembly must explicitly apply split_plan.json, chosen dependencies, contrast groups, baseline carry-forward and the same protection checks. No importer/code/schema change is made in this task.

## Expected coverage if all approved

```json
{
  "summary": {
    "total_candidates": 34,
    "category_counts": {
      "date_factor": 4,
      "rare_measure": 4,
      "source_role_value": 4,
      "od": 5,
      "aggregation": 3,
      "actual_hard_negative": 4,
      "semantic_contrast": 10
    },
    "split_candidate_counts": {
      "train": 13,
      "valid": 21
    },
    "new_sft_gold": {
      "train": 9,
      "valid": 11
    },
    "new_dpo_pairs": {
      "train": 4,
      "valid": 10
    },
    "dpo_category": {
      "semantic": 12,
      "constraint": 2
    },
    "strict_raw_dpo_category": {
      "constraint": 4,
      "semantic": 10
    },
    "actual_hard_negative_count": 4,
    "actual_hard_negative_production_categories": {
      "semantic": 2,
      "constraint": 2
    },
    "synthetic_controls": 10,
    "pending": 34,
    "accepted": 0,
    "GPU_training": false,
    "inference": false,
    "exported": false
  },
  "SFT_before": {
    "train": 12,
    "valid": 5
  },
  "SFT_after": {
    "train": 21,
    "valid": 16
  },
  "DPO_before": {
    "train": 16,
    "valid": 4
  },
  "DPO_after": {
    "train": 20,
    "valid": 14
  },
  "new_DPO_split_category": {
    "train": {
      "semantic": 2,
      "constraint": 2
    },
    "valid": {
      "semantic": 10
    }
  },
  "validation_families": [
    {
      "family": "rb003-fare-month-max-mean",
      "ids": [
        "RB003-06"
      ],
      "fingerprints": [
        "c2a56609c963f75f49f0b948ba90a7668c4ad20f40895a7781286ba965d9cb49"
      ],
      "categories": [
        "rare_measure"
      ],
      "measures": [
        "fare"
      ],
      "planned_split": "valid",
      "new_to_existing_train_and_protection": true
    },
    {
      "family": "rb003-fare-month-min-max-answer-contrast",
      "ids": [
        "RB003-19",
        "RB003-20"
      ],
      "fingerprints": [
        "11ee32d6eaf4be5ce125919762dc52dfda3bb20e5ebd2eb3ba8bb9f460f6ebf0",
        "c17fee0ad5bf706cb8a725acafd5a7b3b8139d6d57d828ae87556ae435b29169"
      ],
      "categories": [
        "aggregation"
      ],
      "measures": [
        "fare"
      ],
      "planned_split": "valid",
      "new_to_existing_train_and_protection": true
    },
    {
      "family": "rb003-od-two-filters-emd-bottom",
      "ids": [
        "RB003-15",
        "RB003-16",
        "RB003-17"
      ],
      "fingerprints": [
        "8ae2f49fd112d635a17440344ab0a7fb6e1f524b33b444b345f46ebe58cd0120",
        "a356f3283ab9852926175adf2ae92bf3be02eb02b7b63acd8ea166a0285b17ad",
        "f82d7d48cc2e312bdc0ae3277ce7670ca06a431a3798d414e7f7c8401e868548"
      ],
      "categories": [
        "od"
      ],
      "measures": [
        "trip_count"
      ],
      "planned_split": "valid",
      "new_to_existing_train_and_protection": true
    },
    {
      "family": "rb003-rpm-week-median-mean-date-contrast",
      "ids": [
        "RB003-03",
        "RB003-04"
      ],
      "fingerprints": [
        "106ae9946c99f10c747e0a29ab9cd2f3bd6c97b0c466878a2283cc697d9b15ef"
      ],
      "categories": [
        "date_factor"
      ],
      "measures": [
        "rpm"
      ],
      "planned_split": "valid",
      "new_to_existing_train_and_protection": true
    },
    {
      "family": "rb003-speed-month-stage-validation",
      "ids": [
        "RB003-08",
        "RB003-11",
        "RB003-12"
      ],
      "fingerprints": [
        "38ab38e61d6639ed15376aaeb8a46714c9f7f1133d13bf55dfb43012268db00d",
        "476a486ed21bed533cb4992ea31db7bfd30c262d0b6dd674e1842a8839c921d3"
      ],
      "categories": [
        "rare_measure",
        "source_role_value"
      ],
      "measures": [
        "speed"
      ],
      "planned_split": "valid",
      "new_to_existing_train_and_protection": true
    }
  ]
}
```

## Human review process

Review question vs proposed gold, statistics, location meaning, source/role/value and lineage; then pair-specific chosen correctness/rejected wrongness. Recommendations are advisory. No decisions.jsonl is created. Record separate hash-bound final decisions only after review; approve each new chosen before its dependent pair. Needs_fix is preferable to forced unsupported when semantics are unclear. XLSX edits are not imported automatically.

## Remaining gaps

Rare subtypes still have very few independent families. Plain single-stage fare/speed families collide with protected dev; the resulting batch is intentionally rich in multi-stage tasks and does not resolve broad single-stage coverage. Passage_count/vacant_ratio and unsupported remain unexpanded. EVENT SUPPORT omission/role constraints are observed in actual multi-error negatives but not isolated as semantic validation pairs. No numerical TIMS execution, missing-data/zero-fill/median-even/tie policy certification. New validation is held from training but is not a final benchmark; checkpoint selection will consume it.

## Individual review definitions

### RB003-01 — date_factor / train
이번 주 하늘동에서 관측된 각 도로 통행 기록의 엔진 회전수 값을 동일 가중으로 산술평균하면?
- Meaning: 관측 기록별 RPM의 산술평균; this_week는 factor이고 DATE/EVENT COND가 아니다.
- Family: rb003-rpm-record-avg-date-contrast; contrast group: rb003-rpm-record-avg-date-contrast
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-02 — date_factor / train
지난주 하늘동에서 관측된 각 도로 통행 기록의 엔진 회전수 값을 동일 가중으로 산술평균하면?
- Meaning: 같은 평균 정의, 대상 기간만 last_week. 이번 주와의 contrast는 같은 train family.
- Family: rb003-rpm-record-avg-date-contrast; contrast group: rb003-rpm-record-avg-date-contrast
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-03 — date_factor / valid
지난달 하늘동에서 관측된 도로 통행 RPM을 주마다 중앙값으로 요약한 뒤, 그 주별 중앙값들을 동일 가중으로 평균하면?
- Meaning: 주 안 기록의 median → 주별 median들의 equal-weight avg; 전체 RPM median/평균과 다르다.
- Family: rb003-rpm-week-median-mean-date-contrast; contrast group: rb003-rpm-week-median-mean-date-contrast
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-04 — date_factor / valid
2026년 7월 6일부터 8월 30일까지 하늘동에서 관측된 도로 통행 RPM을 주마다 중앙값으로 요약한 뒤, 그 주별 중앙값들을 동일 가중으로 평균하면?
- Meaning: 명시된 양 끝 날짜를 factor 범위로 유지. 같은 validation family의 last_month 대비 absolute range contrast.
- Family: rb003-rpm-week-median-mean-date-contrast; contrast group: rb003-rpm-week-median-mean-date-contrast
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-05 — rare_measure / train
2026년 7월과 8월 하늘구 소속 택시의 실차 구간별 요금을 주마다 최솟값으로 요약한 뒤, 그 주별 최솟값들 중 가장 큰 숫자는?
- Meaning: trip fare의 주별 min → max, 숫자 반환. Billing 소속 지역 filter; revenue가 아니다.
- Family: rb003-fare-week-min-max; contrast group: rb003-fare-week-min-max
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-06 — rare_measure / valid
2026년 4월부터 6월까지 하늘구 소속 택시의 실차 구간별 요금 최댓값을 월마다 구하고, 그 월별 최댓값들의 동일 가중 평균은?
- Meaning: 월 안 trip fare max → 월별 maxima avg. Fare validation은 train의 주별 min/max와 다른 family.
- Family: rb003-fare-month-max-mean; contrast group: rb003-fare-month-max-mean
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-07 — rare_measure / train
2026년 7월과 8월 하늘동 안에서 관측된 도로 통행 속도의 주별 최솟값들 중 가장 큰 숫자는?
- Meaning: passage speed 주별 min → max. 운행 발생 위치이며 소속 택시 집단/속도의 합계가 아니다.
- Family: rb003-speed-week-min-max; contrast group: rb003-speed-week-min-max
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-08 — rare_measure / valid
2026년 4월부터 6월까지 하늘동 안에서 관측된 도로 통행 속도를 월마다 산술평균하고, 그 월별 평균 중 가장 큰 숫자는?
- Meaning: 월 안 passage-record speed avg → max of monthly means; 숫자 반환.
- Family: rb003-speed-month-stage-validation; contrast group: rb003-speed-month-stage-validation
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-09 — source_role_value / train
2026년 7월과 8월 사용자가 지정한 도로 범위 scope:edge:2607 안에서 관측된 RPM을 주마다 평균한 뒤, 그 주별 평균 중 가장 큰 숫자는?
- Meaning: scope literal을 user/value + COND로 복사; EVENT passage SUPPORT와 결과 RPM MEASURE는 implicit/value 없음.
- Family: rb003-rpm-week-average-max-scope; contrast group: rb003-rpm-week-average-max-scope
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-10 — source_role_value / train
2026년 7월과 8월 하늘구 소속 택시의 실차 구간 요금을 주마다 평균한 뒤, 그 주별 평균 중 가장 큰 숫자는?
- Meaning: 장소명은 user/value+SUBCOND, date는 factor. 택시 유형은 질문에 없으므로 추가하지 않는다. 사용자가 알려준 수치가 없으므로 fare MEASURE value를 만들지 않는다.
- Family: rb003-fare-week-average-max-place; contrast group: rb003-fare-week-average-max-place
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-11 — source_role_value / valid
2026년 4월부터 6월까지 사용자가 지정한 도로 범위 scope:edge:2608 안에서 기록된 통행 속도를 월별 최댓값으로 요약한 뒤, 그 월별 최댓값들을 동일 가중 평균하면?
- Meaning: 이미 주어진 scope만 COND/user/value. 월별 speed max → avg; SUPPORT/MEASURE에 user numeric value를 할당하지 않는다.
- Family: rb003-speed-month-stage-validation; contrast group: rb003-speed-month-stage-validation
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-12 — source_role_value / valid
2026년 4월부터 6월까지 하늘동에서 관측된 통행 속도를 월별 최댓값으로 요약한 뒤, 그 월별 최댓값들을 동일 가중 평균하면?
- Meaning: 같은 validation stage contrast group. 미해결 장소명 하늘동은 SUBCOND/user/name+region, scope literal로 지어내지 않음.
- Family: rb003-speed-month-stage-validation; contrast group: rb003-speed-month-stage-validation
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-13 — od / train
2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 시군구 승차지별 건수를 세어 기록이 있는 그룹 중 많은 2개 그룹은?
- Meaning: 해온시 pickup / 솔빛시 dropoff는 각각 장소 filter; dimension_target은 별도 그룹 축. Trip 건수이고 passage_count가 아님. 새 validation은 two-filter + emd/bottom, 기존 no-filter emd/bottom과 독립.
- Family: rb003-od-two-filters-sigungu-top; contrast group: rb003-od-two-filters-sigungu-top
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-14 — od / train
2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 시군구 하차지별 건수를 세어 기록이 있는 그룹 중 많은 2개 그룹은?
- Meaning: 해온시 pickup / 솔빛시 dropoff는 각각 장소 filter; dimension_target은 별도 그룹 축. Trip 건수이고 passage_count가 아님. 새 validation은 two-filter + emd/bottom, 기존 no-filter emd/bottom과 독립.
- Family: rb003-od-two-filters-sigungu-top; contrast group: rb003-od-two-filters-sigungu-top
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-15 — od / valid
2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 읍면동 승차지별 건수를 세어 기록이 있는 그룹 중 적은 2개 그룹은?
- Meaning: 해온시 pickup / 솔빛시 dropoff는 각각 장소 filter; dimension_target은 별도 그룹 축. Trip 건수이고 passage_count가 아님. 새 validation은 two-filter + emd/bottom, 기존 no-filter emd/bottom과 독립.
- Family: rb003-od-two-filters-emd-bottom; contrast group: rb003-od-two-filters-emd-bottom
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-16 — od / valid
2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 읍면동 하차지별 건수를 세어 기록이 있는 그룹 중 적은 2개 그룹은?
- Meaning: 해온시 pickup / 솔빛시 dropoff는 각각 장소 filter; dimension_target은 별도 그룹 축. Trip 건수이고 passage_count가 아님. 새 validation은 two-filter + emd/bottom, 기존 no-filter emd/bottom과 독립.
- Family: rb003-od-two-filters-emd-bottom; contrast group: rb003-od-two-filters-emd-bottom
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-17 — od / valid
2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 읍면동 승차지와 하차지의 조합별 건수를 세어 기록이 있는 그룹 중 적은 2개 그룹은?
- Meaning: 해온시 pickup / 솔빛시 dropoff는 각각 장소 filter; dimension_target은 별도 그룹 축. Trip 건수이고 passage_count가 아님. 새 validation은 two-filter + emd/bottom, 기존 no-filter emd/bottom과 독립.
- Family: rb003-od-two-filters-emd-bottom; contrast group: rb003-od-two-filters-emd-bottom
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-18 — aggregation / train
2026년 4월부터 6월까지 하늘구 소속 법인택시의 택시·일 매출 기록을 월마다 중앙값으로 요약한 뒤, 그 월별 중앙값 중 가장 작은 숫자는?
- Meaning: inner=median of billing taxi-day revenue records, outer=min over month summaries. Numeric answer; missing days are not implicitly zero-filled.
- Family: rb003-revenue-month-median-min; contrast group: rb003-revenue-month-median-min
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-19 — aggregation / valid
2026년 4월부터 6월까지 하늘구 소속 택시의 실차 구간 요금 최솟값을 월마다 구했을 때, 가장 큰 숫자는?
- Meaning: 월 안 trip fare min; 월별 minima의 최대 숫자 또는 해당 월 반환. 두 positive는 같은 validation contrast group; answer=bucket일 때 max는 selection.
- Family: rb003-fare-month-min-max-answer-contrast; contrast group: rb003-fare-month-min-max-answer-contrast
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-20 — aggregation / valid
2026년 4월부터 6월까지 하늘구 소속 택시의 실차 구간 요금 최솟값을 월마다 구했을 때, 가장 큰 최솟값이 나온 달은?
- Meaning: 월 안 trip fare min; 월별 minima의 최대 숫자 또는 해당 월 반환. 두 positive는 같은 validation contrast group; answer=bucket일 때 max는 selection.
- Family: rb003-fare-month-min-max-answer-contrast; contrast group: rb003-fare-month-min-max-answer-contrast
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "human_approval_required": true}
- Rejected: SFT-only gold proposal
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-21 — actual_hard_negative / train
2026년 8월 나래구 개인택시 매출 평균이 가장 낮았던 주는 언제야?
- Meaning: Chosen은 v002에서 이미 승인된 train gold. Rejected는 pilot_002 raw output을 canonical serialization만 수행한 관측값.
- Family: intent-dcef4aa325e7c899; contrast group: intent-dcef4aa325e7c899
- Recommendation: needs_fix (advisory); actual pending
- Chosen dependency/trust: {"level": "reviewed_gold_v002_train", "source_record_id": "ann-77e9dacb0b34a3273630", "sft_record_hash": "43a750f8986b43dc1aecc035287bd20b30b3af65f7ed79cedac3b0d015efe351", "corpus_manifest_hash": "b7a07c3a61d73f0dd7d4a88d0a899cf213d9a9d46048f5da5ea1beb531fbc84a", "prior_decision_hash": "5aaf799ab40e154b44179fdf86b0494a258ce5ce3a55340a4de64b8a4aa758a8", "human_rejected_error_confirmation_required": true}
- Rejected: 원문의 date/taxi_type을 factor로 두지 않거나 장소 role과 source/value를 잘못 표현. 실제 raw/normalized 검사와 의미 오류를 함께 검토.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "legacy_normalization_boundary": true, "checks": ["Production-normalized graph PASS는 strict raw contract와 semantic correctness를 보증하지 않음.", "Rejected를 수정하면 실제 model output이 아닌 새 synthetic control로 provenance를 다시 구분해야 함."]}

### RB003-22 — actual_hard_negative / train
2026년 8월 나래구 개인택시 매출 평균이 가장 낮았던 주는 언제야?
- Meaning: Chosen은 v002에서 이미 승인된 train gold. Rejected는 pilot_002 raw output을 canonical serialization만 수행한 관측값.
- Family: intent-dcef4aa325e7c899; contrast group: intent-dcef4aa325e7c899
- Recommendation: needs_fix (advisory); actual pending
- Chosen dependency/trust: {"level": "reviewed_gold_v002_train", "source_record_id": "ann-77e9dacb0b34a3273630", "sft_record_hash": "43a750f8986b43dc1aecc035287bd20b30b3af65f7ed79cedac3b0d015efe351", "corpus_manifest_hash": "b7a07c3a61d73f0dd7d4a88d0a899cf213d9a9d46048f5da5ea1beb531fbc84a", "prior_decision_hash": "5aaf799ab40e154b44179fdf86b0494a258ce5ce3a55340a4de64b8a4aa758a8", "human_rejected_error_confirmation_required": true}
- Rejected: 원문의 date/taxi_type을 factor로 두지 않거나 장소 role과 source/value를 잘못 표현. 실제 raw/normalized 검사와 의미 오류를 함께 검토.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "legacy_normalization_boundary": true, "checks": ["Production-normalized graph PASS는 strict raw contract와 semantic correctness를 보증하지 않음.", "Rejected를 수정하면 실제 model output이 아닌 새 synthetic control로 provenance를 다시 구분해야 함."]}

### RB003-23 — actual_hard_negative / train
2026년 9월 가람구 소속 택시의 요금을 주마다 합산한 뒤, 주별 합계 중 가장 작은 값은?
- Meaning: Chosen은 v002에서 이미 승인된 train gold. Rejected는 pilot_002 raw output을 canonical serialization만 수행한 관측값.
- Family: rb002-fare-week-sum-min; contrast group: rb002-fare-week-sum-min
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "reviewed_gold_v002_train", "source_record_id": "ann-a27c59659681a481ac2c", "sft_record_hash": "5f3b888df4cdb67b15acb36e541a11f0f39274079f1b70f6f40f397f8c80bdb7", "corpus_manifest_hash": "b7a07c3a61d73f0dd7d4a88d0a899cf213d9a9d46048f5da5ea1beb531fbc84a", "prior_decision_hash": "d01dd3a7bcf1dbadd3afe17ff2d8889481bbf69091d6cf96b2834272e88d4fd4", "human_rejected_error_confirmation_required": true}
- Rejected: 원문의 date/taxi_type을 factor로 두지 않거나 장소 role과 source/value를 잘못 표현. 실제 raw/normalized 검사와 의미 오류를 함께 검토.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "legacy_normalization_boundary": false, "checks": ["Production-normalized graph PASS는 strict raw contract와 semantic correctness를 보증하지 않음.", "Rejected를 수정하면 실제 model output이 아닌 새 synthetic control로 provenance를 다시 구분해야 함."]}

### RB003-24 — actual_hard_negative / train
2026년 9월 가람구에서 기록된 도로 통행 속도의 주별 최댓값들 중 가장 작은 값은?
- Meaning: Chosen은 v002에서 이미 승인된 train gold. Rejected는 pilot_002 raw output을 canonical serialization만 수행한 관측값.
- Family: rb002-speed-week-max-min; contrast group: rb002-speed-week-max-min
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "reviewed_gold_v002_train", "source_record_id": "ann-914c48dad91bc9a62ab4", "sft_record_hash": "82259bb1f2dae2947d174f48b22150efb0f425e4fb0bf56d4970e6f1aaa7a0cb", "corpus_manifest_hash": "b7a07c3a61d73f0dd7d4a88d0a899cf213d9a9d46048f5da5ea1beb531fbc84a", "prior_decision_hash": "30c2cff08ed2a53b164f9dc5b918afe911ac86595918dafbdccbf90ca8e026d3", "human_rejected_error_confirmation_required": true}
- Rejected: 원문의 date/taxi_type을 factor로 두지 않거나 장소 role과 source/value를 잘못 표현. 실제 raw/normalized 검사와 의미 오류를 함께 검토.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "legacy_normalization_boundary": false, "checks": ["Production-normalized graph PASS는 strict raw contract와 semantic correctness를 보증하지 않음.", "Rejected를 수정하면 실제 model output이 아닌 새 synthetic control로 provenance를 다시 구분해야 함."]}

### RB003-25 — semantic_contrast / valid
지난달 하늘동에서 관측된 도로 통행 RPM을 주마다 중앙값으로 요약한 뒤, 그 주별 중앙값들을 동일 가중으로 평균하면?
- Meaning: 주 안 기록의 median → 주별 median들의 equal-weight avg; 전체 RPM median/평균과 다르다.
- Family: rb003-rpm-week-median-mean-date-contrast; contrast group: rb003-rpm-week-median-mean-date-contrast
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "approval_dependency": "RB003-03", "candidate_id": "ann-56366f545130c8b38940", "human_chosen_approval_required": true}
- Rejected: 지난달을 지난주로 바꾸면 관측 기간과 포함되는 주가 달라진다. 다른 필드는 그대로.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-26 — semantic_contrast / valid
2026년 7월 6일부터 8월 30일까지 하늘동에서 관측된 도로 통행 RPM을 주마다 중앙값으로 요약한 뒤, 그 주별 중앙값들을 동일 가중으로 평균하면?
- Meaning: 명시된 양 끝 날짜를 factor 범위로 유지. 같은 validation family의 last_month 대비 absolute range contrast.
- Family: rb003-rpm-week-median-mean-date-contrast; contrast group: rb003-rpm-week-median-mean-date-contrast
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "approval_dependency": "RB003-04", "candidate_id": "ann-5c88583c249cfeba80ef", "human_chosen_approval_required": true}
- Rejected: 명시된 기간을 제거하면 질문의 날짜 조건이 사라진다. DATE concept를 억지로 추가하지 않는 structurally valid omission control.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-27 — semantic_contrast / valid
2026년 4월부터 6월까지 하늘동에서 관측된 통행 속도를 월별 최댓값으로 요약한 뒤, 그 월별 최댓값들을 동일 가중 평균하면?
- Meaning: 같은 validation stage contrast group. 미해결 장소명 하늘동은 SUBCOND/user/name+region, scope literal로 지어내지 않음.
- Family: rb003-speed-month-stage-validation; contrast group: rb003-speed-month-stage-validation
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "approval_dependency": "RB003-12", "candidate_id": "ann-206f99f94e6aeb1e3e65", "human_chosen_approval_required": true}
- Rejected: 질문에 주어진 장소명은 user이며 implicit이 아니다. Runtime PASS가 잘못된 source/value 조합을 잡지 못해도 semantic target은 틀렸다.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-28 — semantic_contrast / valid
2026년 4월부터 6월까지 하늘동에서 관측된 통행 속도를 월별 최댓값으로 요약한 뒤, 그 월별 최댓값들을 동일 가중 평균하면?
- Meaning: 같은 validation stage contrast group. 미해결 장소명 하늘동은 SUBCOND/user/name+region, scope literal로 지어내지 않음.
- Family: rb003-speed-month-stage-validation; contrast group: rb003-speed-month-stage-validation
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "approval_dependency": "RB003-12", "candidate_id": "ann-206f99f94e6aeb1e3e65", "human_chosen_approval_required": true}
- Rejected: 미해결 장소명은 SUBCOND; 이미 제공된 scope의 COND로 바꾸면 role 정의를 위반한다.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-29 — semantic_contrast / valid
2026년 4월부터 6월까지 하늘동에서 관측된 통행 속도를 월별 최댓값으로 요약한 뒤, 그 월별 최댓값들을 동일 가중 평균하면?
- Meaning: 같은 validation stage contrast group. 미해결 장소명 하늘동은 SUBCOND/user/name+region, scope literal로 지어내지 않음.
- Family: rb003-speed-month-stage-validation; contrast group: rb003-speed-month-stage-validation
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "approval_dependency": "RB003-12", "candidate_id": "ann-206f99f94e6aeb1e3e65", "human_chosen_approval_required": true}
- Rejected: 질문에 없는 속도 42를 입력값으로 지어낸다. 결과로 채울 MEASURE는 implicit이며 value가 없어야 한다.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-30 — semantic_contrast / valid
2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 읍면동 승차지와 하차지의 조합별 건수를 세어 기록이 있는 그룹 중 적은 2개 그룹은?
- Meaning: 해온시 pickup / 솔빛시 dropoff는 각각 장소 filter; dimension_target은 별도 그룹 축. Trip 건수이고 passage_count가 아님. 새 validation은 two-filter + emd/bottom, 기존 no-filter emd/bottom과 독립.
- Family: rb003-od-two-filters-emd-bottom; contrast group: rb003-od-two-filters-emd-bottom
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "approval_dependency": "RB003-17", "candidate_id": "ann-7fae41a3ed86d08a23f0", "human_chosen_approval_required": true}
- Rejected: 두 endpoint filter는 유지하지만 승하차 조합 그룹을 하차지 단독 그룹으로 축약한다.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-31 — semantic_contrast / valid
2026년 4월부터 6월까지 하늘동 안에서 관측된 도로 통행 속도를 월마다 산술평균하고, 그 월별 평균 중 가장 큰 숫자는?
- Meaning: 월 안 passage-record speed avg → max of monthly means; 숫자 반환.
- Family: rb003-speed-month-stage-validation; contrast group: rb003-speed-month-stage-validation
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "approval_dependency": "RB003-08", "candidate_id": "ann-f2cd5753e5bbdc07eef9", "human_chosen_approval_required": true}
- Rejected: 월별 평균의 최대(avg→max)를 월별 최대의 평균(max→avg)으로 바꾼다. Val positive stage contrast와 같은 group에 둔다.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-32 — semantic_contrast / valid
2026년 4월부터 6월까지 하늘구 소속 택시의 실차 구간 요금 최솟값을 월마다 구했을 때, 가장 큰 최솟값이 나온 달은?
- Meaning: 월 안 trip fare min; 월별 minima의 최대 숫자 또는 해당 월 반환. 두 positive는 같은 validation contrast group; answer=bucket일 때 max는 selection.
- Family: rb003-fare-month-min-max-answer-contrast; contrast group: rb003-fare-month-min-max-answer-contrast
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "approval_dependency": "RB003-20", "candidate_id": "ann-29dcb56f51da6d6a361f", "human_chosen_approval_required": true}
- Rejected: 가장 큰 최소요금이 발생한 달을 물었는데 numeric value를 반환하는 grounding으로 바꾼다.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-33 — semantic_contrast / valid
2026년 4월부터 6월까지 하늘구 소속 택시의 실차 구간별 요금 최댓값을 월마다 구하고, 그 월별 최댓값들의 동일 가중 평균은?
- Meaning: 월 안 trip fare max → 월별 maxima avg. Fare validation은 train의 주별 min/max와 다른 family.
- Family: rb003-fare-month-max-mean; contrast group: rb003-fare-month-max-mean
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "approval_dependency": "RB003-06", "candidate_id": "ann-fb7938d64ca0888db425", "human_chosen_approval_required": true}
- Rejected: Trip별 승객 요금을 Billing 택시·일 매출로 치환. Event를 함께 바꿔 구조는 valid해도 관측 단위와 measure가 달라진다.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}

### RB003-34 — semantic_contrast / valid
2026년 4월부터 6월까지 하늘동 안에서 관측된 도로 통행 속도를 월마다 산술평균하고, 그 월별 평균 중 가장 큰 숫자는?
- Meaning: 월 안 passage-record speed avg → max of monthly means; 숫자 반환.
- Family: rb003-speed-month-stage-validation; contrast group: rb003-speed-month-stage-validation
- Recommendation: accepted (advisory); actual pending
- Chosen dependency/trust: {"level": "pending_new_gold", "approval_dependency": "RB003-08", "candidate_id": "ann-f2cd5753e5bbdc07eef9", "human_chosen_approval_required": true}
- Rejected: 속도를 엔진 RPM으로 바꾼다. Event passage와 집계는 그대로라 valid하지만 다른 측정값이다.
- Check: {"semantic_ambiguity_identified": false, "human_semantic_and_lineage_confirmation_required": true, "checks": ["Synthetic place/scope is literal annotation context; no actual location resolution/execution performed.", "Bucket boundaries, empty/missing buckets and ties follow runtime; no new zero-fill or denominator policy."]}


## Token budget gate (CPU tokenizer only)

Seven candidates exceed the current pilot_002 limits: RB003-13–17,24,30. Production prompt is unchanged. SFT max6977; DPO max6978; DPO prompt max6789 > current6784. They are semantic review proposals, not ready-to-train records under the old config. No text or JSON was truncated.

Proposed next-pilot limits: total7040, prompt6912, completion256. All34 pass existing render_records token boundary/length guards with those proposed limits. These are NOT applied config changes; after review/assembly, future GPU smoke and memory profiling are required. Token_budget sheet and each JSONL view flag show affected IDs.

A grouped fare proposal with taxi_type was not included: current MacroComposer returns UNCONSUMED_CONDITION for that combination. The source/role positive was independently specified without taxi_type in BOTH question and target. No runtime rule was changed and no explicit question condition was silently dropped.

## CPU verification receipt

15 artifact checks and 39 existing annotation/review tests passed. VALIDATION_BATCH_003.json records frozen-source hashes, pending status, family/split checks, XLSX checks and tokenizer limits. These checks do not approve semantic correctness; human review remains required.
