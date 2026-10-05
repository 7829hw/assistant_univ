# REVIEW_DECISIONS_003 — semantic decision draft

이 문서는 최종 human approval가 아니다. 원본 queue/status, v001/v002, production/schema/prompt/config를 변경하지 않았다. 실제 승인 0건, import·GPU 학습·model inference 0회. 권고만 `accepted / needs_fix / diagnostic_only`로 기록한다.

## 요약

```json
{
  "recommendations": {
    "accepted": 30,
    "needs_fix": 2,
    "diagnostic_only": 2
  },
  "recommended_sft_ids": [
    "RB003-03",
    "RB003-04",
    "RB003-05",
    "RB003-06",
    "RB003-07",
    "RB003-08",
    "RB003-09",
    "RB003-10",
    "RB003-11",
    "RB003-12",
    "RB003-13",
    "RB003-14",
    "RB003-15",
    "RB003-16",
    "RB003-17",
    "RB003-18",
    "RB003-19",
    "RB003-20"
  ],
  "recommended_dpo_ids": [
    "RB003-23",
    "RB003-24",
    "RB003-25",
    "RB003-26",
    "RB003-27",
    "RB003-28",
    "RB003-29",
    "RB003-30",
    "RB003-31",
    "RB003-32",
    "RB003-33",
    "RB003-34"
  ],
  "recommended_dpo_categories": {
    "semantic": 10,
    "constraint": 2
  },
  "lineage_conflicts": [
    "RB003-01",
    "RB003-02"
  ],
  "token_exceeded": [
    "RB003-13",
    "RB003-14",
    "RB003-15",
    "RB003-16",
    "RB003-17",
    "RB003-24",
    "RB003-30"
  ],
  "expected_v003_if_only_recommended_accepted_human_confirmed": {
    "sft_train": 19,
    "sft_valid": 16,
    "dpo_train": 18,
    "dpo_valid": 14,
    "dpo_semantic": 21,
    "dpo_constraint": 11
  },
  "upper_scenario_if_21_22_explicitly_approved_as_raw_contract_constraint_pairs": {
    "sft_train": 19,
    "sft_valid": 16,
    "dpo_train": 20,
    "dpo_valid": 14,
    "dpo_semantic": 21,
    "dpo_constraint": 13
  },
  "actual_approved": 0,
  "import_executed": false,
  "GPU_training": false
}
```

## 이전 추천과 달라진 핵심 판단

- **RB003-01·02는 diagnostic_only.** Tool-text gold를 직접 읽으면 protected `n31`/`k06`과 동일한 단일 단계 RPM 평균이다. 장소/날짜/record equal weighting 명시만으로 독립 family가 되지 않는다. `Protection.current`는 이 소스들의 gold_text를 structured grounding으로 해석하지 않아 자동 이유가 0개였지만, 수동 lineage 근거가 우선한다. 기존 generator/보호 로직은 이번 작업에서 고치지 않았다. 두 원본 후보를 바꾸거나 다른 family로 자동 재명명하지 않는다.
- **RB003-21·22는 needs_fix.** 첫 strict raw 오류는 두 건 모두 INVALID_SUBTYPE. private 값이 normalization 후 taxi_type으로 보존되고 원래 통계식·장소 필터가 유지된다. Canonical place role은 다르지만 pure query-semantic negative라고 할 수 없다. 같은 실제 rejected를 유지하고 raw-contract constraint로 metadata만 재분류할지, diagnostic으로 둘지 사람이 결정해야 한다. Missing value를 새로 채운 합성 응답을 실제 model 오답이라고 바꾸지 않는다.
- **27–29는 canonical annotation semantic contrast.** Runtime 숫자가 바뀌었다는 주장 없이, prompt가 정의한 user/implicit, SUBCOND/COND, implicit MEASURE/value 없음의 의미를 기준으로 판단했다. 이 층과 순수 통계식·필터 semantic contrast를 별도 ablation으로 분석할 수 있다.

## Source/role/value 판정 기준

질문에 속도·통행·실차 구간이라는 개념명이 등장하는 것과 이미 주어진 입력값이 있는 것은 다르다. 이 질문들은 관측 사건의 유형과 미지의 측정 결과를 지정하므로 EVENT/SUPPORT와 MEASURE는 implicit이며 결과 value를 갖지 않는다. User source는 발화에서 주어진 장소 값 또는 문자 그대로 주어진 scope 입력에 적용한다. EVENT/user에 날짜 object를 넣거나 MEASURE/user에 42를 넣어 입력값을 만드는 것은 이 구분을 위반한다. 순수 MISSING_CONCEPT_VALUE control을 새로 생성한 것은 아니며,22의 실제 첫 오류도 그 코드가 아니다.

## 독립 validation 검토

| Subtype/capability | Train candidate | Validation candidate | 독립성 근거 |
|---|---|---|---|
| RPM |09: week avg→max|03–04: week med→avg|01–02를 제외해도 09의 max-of-weekly-means와 03–04의 mean-of-weekly-medians는 다르다. Bare RPM median/avg dev family를 재사용하지 않는다.|
| Fare |05: week min→max, 10: week avg→max|06: month max→avg, 19–20: month min→max 및 selected month|집계식/구간/반환 target이 달라 날짜·장소 paraphrase로 분할한 것이 아니다.|
| Speed |07: week min→max|08/11–12: month avg→max 또는 max→avg|Stage siblings와 scope/place role contrast는 모두 같은 validation group에 둔다.|
| Date factor |09 등 명시 기간;01–02는 제외|03 last_month /04 explicit range,25–26 pairs|상대/명시 기간은 factor이며 같은 통계 family의 siblings는 validation 안에서만 contrast한다. 신규 this_week/last_week train contrast는 확보되지 않았다.|
| OD |13–14: two filters + sigungu/top|15–17: two filters + emd/bottom, pickup/dropoff/both|기존 v002 validation은 endpoint filters 없는 OD였다. 새 가족은 두 필터를 유지한 하위 행정단위 grouping. 단, train city grouping은 퇴화할 수 있어 ranking coverage를 과장하지 않는다.|
| Aggregation/answer |18: revenue med→min|19–20 및31–32|Outer reducer와 SELECT_GROUP를 구분; 양·음성 stage/answer siblings는 같은 validation group.|

5개 validation contrast group/9개 positive semantic fingerprint는 이전 labeled train/protection과 자동 교집합이 없다. Structured protection, 선언 family, template, SFT/DPO 질문과 gold, 실제 pilot train-origin 및 tool-text gold/질문 원문을 대조했다. 의미 family는 현재 프로젝트의 보수적인 capability 기준이다. 이 검토로 실제 장비 관측이나 통계적 독립성, 미래의 모든 paraphrase까지 증명한 것은 아니다.

## Token 문제는 의미와 별도

RB003-13–17·24·30의 7건은 현재 설정에서 preflight에 실패한다. 13–17/24는 total6912 초과,30은 DPO prompt6784 초과가 먼저 잡힌다(total도 초과). 기존 기록의 최대 total은 SFT6977/DPO6978. Semantic accepted 추천과 현재 설정에서 export/train 가능함을 혼동하지 않는다. 이 검토는 token limit을 변경하거나 질문/JSON을 잘라내지 않았다. 과거의7040 제안도 채택하지 않았다.

## 사람이 반드시 정할 항목

1. 21·22: raw-contract constraint pair로 보존할지 diagnostic으로 둘지. 원문 rejected는 유지하고 pure semantic label은 사용하지 않는다.
2. 13·14: top/bottom의 limit는 결과가 충분할 때 최대2개 요청이다. Filter 도시가 sigungu 하나이면 반환이 하나일 수 있다. 정확히 두 그룹 또는 풍부한 OD ranking 실험을 원하면 원문/가족 재검토가 필요하다.
3. 27–29: canonical source/role/value supervision을 semantic preference ablation으로 유지한다는 목적을 최종 확인. Runtime 결과가 틀렸다는 라벨을 붙이지 않는다.
4. 합성 장소/opaque scope와 provider 미구현 항목은 semantic gold로 검토하고 execution benchmark에서 계속 제외. 달력/빈 구간/분모/동률 정책은 실행 계약 확인 없이 확정하지 않는다.
5. 신규 pair25–34는 각각03/04/12/17/08/20/06 등 chosen의 실제 승인에 종속된다. Draft 추천을 승인 증거로 쓸 수 없다.

## 이후 확정/규모 조건

권고를 사람이 확정하면 SFT19/16, DPO18/14가 기본 예상이다.21·22를 별도 raw-contract constraint 정책으로 승인하면 DPO20/14까지 가능하다.01·02는 어떤 경우에도 현재 training corpus에 포함하지 않는다. Snapshot/ignored 원본 어느 쪽에서도 이 draft를 final decisions로 자동 import하지 않는다. 미래 v003 assembler는 v002 split 고정, split_plan, contrast siblings와 chosen dependency를 명시적으로 적용해야 한다. Standalone generic importer를 그대로 실행해 random re-split하지 않는다. Token gate도 별도로 해결되어야 하므로 지금 학습 준비 완료를 주장하지 않는다.

## 개별 검토

### RB003-01 — diagnostic_only 추천 / train

이번 주 하늘동에서 관측된 각 도로 통행 기록의 엔진 회전수 값을 동일 가중으로 산술평균하면?

- Family: `rb003-rpm-record-avg-date-contrast`; contrast group: `rb003-rpm-record-avg-date-contrast`.
- 판단: 관측 passage마다 저장된 엔진 회전수의 동일 가중 평균. RPM(분당 회전 속도)을 뜻한다면 avg/this_week가 맞지만, 누적 회전 횟수라는 해석은 별도 확인이 필요하다. 어떤 해석이든 기존 보호 RPM 평균 family를 새 train으로 편입하지 않는다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":null,"date_factor":"this_week","inner":"avg","measure":"rpm","observation_unit":"passage record","outer":null,"return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `protected_semantic_family`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":true,"execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `geoflow/factors.py`, `geoflow/grounding.py:205`, `geoflow/compiler.py:198`, `geoflow/providers.py:91`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "date": "this_week"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Manual protected anchors:
```json
[
  {
    "source": "evaluation/grounding_v2/independent_questions.yaml",
    "source_sha256": "c8f4f972390dba7d878492de1742d60aae2507df4e23b7653f90a2d7511a941b",
    "record_id": "n31",
    "question": "대구 두산동 도로에서 2026년 8월 3일부터 9일까지 기록된 RPM 평균치는?",
    "gold_text": "get_place_scope(name=두산동, region=대구)\nget_passage_metrics(metric=rpm, scope=$resolve.scope, date=20260803-20260809, aggregation=avg)",
    "comparison_basis": "get_passage_metrics(metric=rpm, aggregation=avg), one scalar, unresolved occurrence place; no bucket/rollup. Date/place/time differences do not create a new semantic family."
  },
  {
    "source": "evaluation/grounding_v3/independent_v4_questions.yaml",
    "source_sha256": "3d11e6d196896766af09522ed30c40a1911f62973d3d24490f32886cd9bce116",
    "record_id": "k06",
    "question": "지난달 대구 신천동 도로 위 택시들의 평균 엔진 회전수(RPM)는 어느 정도였어?",
    "gold_text": "get_place_scope(name=신천동, region=대구)\nget_passage_metrics(metric=rpm, scope=$resolve.scope, date=last_month, aggregation=avg)",
    "comparison_basis": "get_passage_metrics(metric=rpm, aggregation=avg), one scalar, unresolved occurrence place; no bucket/rollup. Date/place/time differences do not create a new semantic family."
  }
]
```

Ambiguity / 확인 사항:
- 엔진 회전수라는 표현이 분당 회전 속도(RPM)인지 누적 회전 횟수인지 명시되지 않았다. RPM이라도 보호 family이므로 현재 train 후보로 승인하면 안 된다.
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-02 — diagnostic_only 추천 / train

지난주 하늘동에서 관측된 각 도로 통행 기록의 엔진 회전수 값을 동일 가중으로 산술평균하면?

- Family: `rb003-rpm-record-avg-date-contrast`; contrast group: `rb003-rpm-record-avg-date-contrast`.
- 판단: 01과 같은 단일 단계 RPM 평균이며 기간만 last_week. 날짜 contrast는 정확하나 날짜·장소 변경만으로 보호 RPM 평균 family의 lineage가 독립되지는 않는다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":null,"date_factor":"last_week","inner":"avg","measure":"rpm","observation_unit":"passage record","outer":null,"return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `protected_semantic_family`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":true,"execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `geoflow/factors.py`, `geoflow/grounding.py:205`, `geoflow/compiler.py:198`, `geoflow/providers.py:91`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "date": "last_week"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Manual protected anchors:
```json
[
  {
    "source": "evaluation/grounding_v2/independent_questions.yaml",
    "source_sha256": "c8f4f972390dba7d878492de1742d60aae2507df4e23b7653f90a2d7511a941b",
    "record_id": "n31",
    "question": "대구 두산동 도로에서 2026년 8월 3일부터 9일까지 기록된 RPM 평균치는?",
    "gold_text": "get_place_scope(name=두산동, region=대구)\nget_passage_metrics(metric=rpm, scope=$resolve.scope, date=20260803-20260809, aggregation=avg)",
    "comparison_basis": "get_passage_metrics(metric=rpm, aggregation=avg), one scalar, unresolved occurrence place; no bucket/rollup. Date/place/time differences do not create a new semantic family."
  },
  {
    "source": "evaluation/grounding_v3/independent_v4_questions.yaml",
    "source_sha256": "3d11e6d196896766af09522ed30c40a1911f62973d3d24490f32886cd9bce116",
    "record_id": "k06",
    "question": "지난달 대구 신천동 도로 위 택시들의 평균 엔진 회전수(RPM)는 어느 정도였어?",
    "gold_text": "get_place_scope(name=신천동, region=대구)\nget_passage_metrics(metric=rpm, scope=$resolve.scope, date=last_month, aggregation=avg)",
    "comparison_basis": "get_passage_metrics(metric=rpm, aggregation=avg), one scalar, unresolved occurrence place; no bucket/rollup. Date/place/time differences do not create a new semantic family."
  }
]
```

Ambiguity / 확인 사항:
- 엔진 회전수라는 표현이 분당 회전 속도(RPM)인지 누적 회전 횟수인지 명시되지 않았다. RPM이라도 보호 family이므로 현재 train 후보로 승인하면 안 된다.
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-03 — accepted 추천 / valid

지난달 하늘동에서 관측된 도로 통행 RPM을 주마다 중앙값으로 요약한 뒤, 그 주별 중앙값들을 동일 가중으로 평균하면?

- Family: `rb003-rpm-week-median-mean-date-contrast`; contrast group: `rb003-rpm-week-median-mean-date-contrast`.
- 판단: passage별 RPM을 각 주 안에서 med로 요약하고, 주별 중앙값에 동일 가중 avg를 적용한다. 전체 RPM의 단일 중앙값이나 전체 기록 평균과 다르다. date=last_month.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"week","date_factor":"last_month","inner":"med","measure":"rpm","observation_unit":"passage record","outer":"avg","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 med는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `geoflow/factors.py`, `geoflow/grounding.py:205`, `geoflow/compiler.py:198`, `geoflow/providers.py:91`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "med",
    "bucket": "week",
    "date": "last_month",
    "rollup": "avg"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-04 — accepted 추천 / valid

2026년 7월 6일부터 8월 30일까지 하늘동에서 관측된 도로 통행 RPM을 주마다 중앙값으로 요약한 뒤, 그 주별 중앙값들을 동일 가중으로 평균하면?

- Family: `rb003-rpm-week-median-mean-date-contrast`; contrast group: `rb003-rpm-week-median-mean-date-contrast`.
- 판단: 03과 같은 med→avg이며 명시 기간은 20260706-20260830. 시작/종료 날짜를 factor로 보존하고 새 EVENT/date를 만들지 않는다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"week","date_factor":"20260706-20260830","inner":"med","measure":"rpm","observation_unit":"passage record","outer":"avg","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 med는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `geoflow/factors.py`, `geoflow/grounding.py:205`, `geoflow/compiler.py:198`, `geoflow/providers.py:91`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "med",
    "bucket": "week",
    "date": "20260706-20260830",
    "rollup": "avg"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-05 — accepted 추천 / train

2026년 7월과 8월 하늘구 소속 택시의 실차 구간별 요금을 주마다 최솟값으로 요약한 뒤, 그 주별 최솟값들 중 가장 큰 숫자는?

- Family: `rb003-fare-week-min-max`; contrast group: `rb003-fare-week-min-max`.
- 판단: 택시 소속 지역 안의 trip별 승객 요금을 매주 min으로 요약한 후 주별 최솟값의 max 숫자를 반환한다. 운행 위치 필터나 택시·일 revenue가 아니다.
- 통계 정의: `{"avg_denominator":null,"bucket":"week","date_factor":"20260701-20260831","inner":"min","measure":"fare","observation_unit":"trip (실차 구간)","outer":"max","return_type":"numeric scalar","select":null,"spatial_scope":"taxi affiliation"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_trip_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "fare"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘구",
      "value": {
        "name": "하늘구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "min",
    "bucket": "week",
    "date": "20260701-20260831",
    "rollup": "max"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-06 — accepted 추천 / valid

2026년 4월부터 6월까지 하늘구 소속 택시의 실차 구간별 요금 최댓값을 월마다 구하고, 그 월별 최댓값들의 동일 가중 평균은?

- Family: `rb003-fare-month-max-mean`; contrast group: `rb003-fare-month-max-mean`.
- 판단: 소속 지역의 trip fare를 매월 max로 요약한 뒤 월별 최댓값들의 동일 가중 avg. Train의 week/min→max와 구간 및 통계식이 달라 독립 validation family다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"month","date_factor":"20260401-20260630","inner":"max","measure":"fare","observation_unit":"trip (실차 구간)","outer":"avg","return_type":"numeric scalar","select":null,"spatial_scope":"taxi affiliation"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_trip_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "fare"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘구",
      "value": {
        "name": "하늘구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "avg"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-07 — accepted 추천 / train

2026년 7월과 8월 하늘동 안에서 관측된 도로 통행 속도의 주별 최솟값들 중 가장 큰 숫자는?

- Family: `rb003-speed-week-min-max`; contrast group: `rb003-speed-week-min-max`.
- 판단: 발생 위치가 하늘동인 passage speed의 week/min→max 숫자. 평균 주행 속도나 거리/시간 가중 평균을 새로 정의하지 않는다.
- 통계 정의: `{"avg_denominator":null,"bucket":"week","date_factor":"20260701-20260831","inner":"min","measure":"speed","observation_unit":"passage record","outer":"max","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "min",
    "bucket": "week",
    "date": "20260701-20260831",
    "rollup": "max"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-08 — accepted 추천 / valid

2026년 4월부터 6월까지 하늘동 안에서 관측된 도로 통행 속도를 월마다 산술평균하고, 그 월별 평균 중 가장 큰 숫자는?

- Family: `rb003-speed-month-stage-validation`; contrast group: `rb003-speed-month-stage-validation`.
- 판단: passage speed를 각 월의 기록별 산술평균으로 요약하고 월별 평균 중 max 숫자를 반환한다. max→avg와 바꾸면 다른 통계량이다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"month","date_factor":"20260401-20260630","inner":"avg","measure":"speed","observation_unit":"passage record","outer":"max","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "max"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-09 — accepted 추천 / train

2026년 7월과 8월 사용자가 지정한 도로 범위 scope:edge:2607 안에서 관측된 RPM을 주마다 평균한 뒤, 그 주별 평균 중 가장 큰 숫자는?

- Family: `rb003-rpm-week-average-max-scope`; contrast group: `rb003-rpm-week-average-max-scope`.
- 판단: 질문이 문자 그대로 제공한 scope:edge:2607을 COND/user/value로 사용한다. RPM week/avg→max이며 새로운 scope를 모델이 해결하거나 만들어서는 안 된다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"week","date_factor":"20260701-20260831","inner":"avg","measure":"rpm","observation_unit":"passage record","outer":"max","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "COND",
      "source": "user",
      "subtype": "scope",
      "value": "scope:edge:2607"
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "week",
    "date": "20260701-20260831",
    "rollup": "max"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["EVENT_TO_GROUPED_MEASURE"],"operators":["PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["EVENT_TO_GROUPED_MEASURE"],"operators":["PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-10 — accepted 추천 / train

2026년 7월과 8월 하늘구 소속 택시의 실차 구간 요금을 주마다 평균한 뒤, 그 주별 평균 중 가장 큰 숫자는?

- Family: `rb003-fare-week-average-max-place`; contrast group: `rb003-fare-week-average-max-place`.
- 판단: 미해결 소속 지역 하늘구는 SUBCOND/user/place 값이다. Trip fare week/avg→max. 질문에 taxi_type이 없으므로 임의 private/corporate를 넣지 않는다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"week","date_factor":"20260701-20260831","inner":"avg","measure":"fare","observation_unit":"trip (실차 구간)","outer":"max","return_type":"numeric scalar","select":null,"spatial_scope":"taxi affiliation"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_trip_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "fare"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘구",
      "value": {
        "name": "하늘구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "week",
    "date": "20260701-20260831",
    "rollup": "max"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-11 — accepted 추천 / valid

2026년 4월부터 6월까지 사용자가 지정한 도로 범위 scope:edge:2608 안에서 기록된 통행 속도를 월별 최댓값으로 요약한 뒤, 그 월별 최댓값들을 동일 가중 평균하면?

- Family: `rb003-speed-month-stage-validation`; contrast group: `rb003-speed-month-stage-validation`.
- 판단: 사용자가 명시한 scope:edge:2608의 passage speed month/max→avg. Scope는 COND/user이고 결과 speed와 측정 사건 passage는 implicit MEASURE/SUPPORT다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"month","date_factor":"20260401-20260630","inner":"max","measure":"speed","observation_unit":"passage record","outer":"avg","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "COND",
      "source": "user",
      "subtype": "scope",
      "value": "scope:edge:2608"
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "avg"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["EVENT_TO_GROUPED_MEASURE"],"operators":["PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["EVENT_TO_GROUPED_MEASURE"],"operators":["PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-12 — accepted 추천 / valid

2026년 4월부터 6월까지 하늘동에서 관측된 통행 속도를 월별 최댓값으로 요약한 뒤, 그 월별 최댓값들을 동일 가중 평균하면?

- Family: `rb003-speed-month-stage-validation`; contrast group: `rb003-speed-month-stage-validation`.
- 판단: 11과 같은 month/max→avg이나 하늘동이라는 미해결 장소를 SUBCOND/user로 조회한다. 명시 scope가 없는데 scope 값을 발명하지 않는다. 08/11/12는 한 validation contrast group이다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"month","date_factor":"20260401-20260630","inner":"max","measure":"speed","observation_unit":"passage record","outer":"avg","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "avg"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-13 — accepted 추천 / train

2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 시군구 승차지별 건수를 세어 기록이 있는 그룹 중 많은 2개 그룹은?

- Family: `rb003-od-two-filters-sigungu-top`; contrast group: `rb003-od-two-filters-sigungu-top`.
- 판단: 해온시 pickup AND 솔빛시 dropoff 필터를 먼저 적용하고 sigungu/pickup별 trip_count를 top 정렬해 앞에서 2개까지 요청한다. Endpoint filter와 grouping target은 별개다.
- 통계 정의: `{"avg_denominator":null,"bucket":null,"date_factor":"20260701-20260831","inner":null,"measure":"trip_count","observation_unit":"trip count","outer":null,"return_type":"OD/spatial dimension count list","select":null,"spatial_scope":"endpoint filters plus separate grouping"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: FAIL (의미 판정과 별개).
- 실행: code의 static diagnostic=`{"compile_ok":true,"execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:72`, `geoflow/grounding.py:60`, `geoflow_macros/od_event_to_measure.yaml`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "dropoff"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛시",
      "value": {
        "name": "솔빛시",
        "region": ""
      }
    },
    {
      "attributes": {
        "od_role": "pickup"
      },
      "concept": "LOCATION",
      "id": "c2",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "해온시",
      "value": {
        "name": "해온시",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c3",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c4",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260701-20260831",
    "dimension": "sigungu",
    "dimension_target": "pickup",
    "limit": 2,
    "order": "top"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 행정구역 시를 sigungu 하나로 resolve하면 target 그룹이 최대 하나일 수 있다. limit=2는 상한 요청으로 해석한다. 정확히 2개 결과 보장 의도라면 원문 수정을 먼저 승인해야 한다. 이 항목은 풍부한 ranking coverage의 증거가 아니다.
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-14 — accepted 추천 / train

2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 시군구 하차지별 건수를 세어 기록이 있는 그룹 중 많은 2개 그룹은?

- Family: `rb003-od-two-filters-sigungu-top`; contrast group: `rb003-od-two-filters-sigungu-top`.
- 판단: 13의 필터·관측 단위는 그대로이고 grouping만 sigungu/dropoff. 시군구 하나로 해석되는 도시 필터라면 그룹이 하나뿐일 수 있어 limit=2가 실제 두 결과를 보장하지 않는다.
- 통계 정의: `{"avg_denominator":null,"bucket":null,"date_factor":"20260701-20260831","inner":null,"measure":"trip_count","observation_unit":"trip count","outer":null,"return_type":"OD/spatial dimension count list","select":null,"spatial_scope":"endpoint filters plus separate grouping"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: FAIL (의미 판정과 별개).
- 실행: code의 static diagnostic=`{"compile_ok":true,"execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:72`, `geoflow/grounding.py:60`, `geoflow_macros/od_event_to_measure.yaml`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "dropoff"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛시",
      "value": {
        "name": "솔빛시",
        "region": ""
      }
    },
    {
      "attributes": {
        "od_role": "pickup"
      },
      "concept": "LOCATION",
      "id": "c2",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "해온시",
      "value": {
        "name": "해온시",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c3",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c4",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260701-20260831",
    "dimension": "sigungu",
    "dimension_target": "dropoff",
    "limit": 2,
    "order": "top"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 행정구역 시를 sigungu 하나로 resolve하면 target 그룹이 최대 하나일 수 있다. limit=2는 상한 요청으로 해석한다. 정확히 2개 결과 보장 의도라면 원문 수정을 먼저 승인해야 한다. 이 항목은 풍부한 ranking coverage의 증거가 아니다.
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-15 — accepted 추천 / valid

2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 읍면동 승차지별 건수를 세어 기록이 있는 그룹 중 적은 2개 그룹은?

- Family: `rb003-od-two-filters-emd-bottom`; contrast group: `rb003-od-two-filters-emd-bottom`.
- 판단: 두 endpoint 필터 안의 trip을 emd/pickup으로 나눠 관측된 그룹만 bottom/limit2. Zero-count 지역을 새로 생성하거나 필터를 dimension으로 대신하지 않는다.
- 통계 정의: `{"avg_denominator":null,"bucket":null,"date_factor":"20260701-20260831","inner":null,"measure":"trip_count","observation_unit":"trip count","outer":null,"return_type":"OD/spatial dimension count list","select":null,"spatial_scope":"endpoint filters plus separate grouping"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: FAIL (의미 판정과 별개).
- 실행: code의 static diagnostic=`{"compile_ok":true,"execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:72`, `geoflow/grounding.py:60`, `geoflow_macros/od_event_to_measure.yaml`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "dropoff"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛시",
      "value": {
        "name": "솔빛시",
        "region": ""
      }
    },
    {
      "attributes": {
        "od_role": "pickup"
      },
      "concept": "LOCATION",
      "id": "c2",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "해온시",
      "value": {
        "name": "해온시",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c3",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c4",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260701-20260831",
    "dimension": "emd",
    "dimension_target": "pickup",
    "limit": 2,
    "order": "bottom"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-16 — accepted 추천 / valid

2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 읍면동 하차지별 건수를 세어 기록이 있는 그룹 중 적은 2개 그룹은?

- Family: `rb003-od-two-filters-emd-bottom`; contrast group: `rb003-od-two-filters-emd-bottom`.
- 판단: 15와 같지만 emd/dropoff로 집계. Pickup 필터가 있어도 grouping target을 pickup으로 강제할 이유는 없다.
- 통계 정의: `{"avg_denominator":null,"bucket":null,"date_factor":"20260701-20260831","inner":null,"measure":"trip_count","observation_unit":"trip count","outer":null,"return_type":"OD/spatial dimension count list","select":null,"spatial_scope":"endpoint filters plus separate grouping"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: FAIL (의미 판정과 별개).
- 실행: code의 static diagnostic=`{"compile_ok":true,"execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:72`, `geoflow/grounding.py:60`, `geoflow_macros/od_event_to_measure.yaml`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "dropoff"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛시",
      "value": {
        "name": "솔빛시",
        "region": ""
      }
    },
    {
      "attributes": {
        "od_role": "pickup"
      },
      "concept": "LOCATION",
      "id": "c2",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "해온시",
      "value": {
        "name": "해온시",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c3",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c4",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260701-20260831",
    "dimension": "emd",
    "dimension_target": "dropoff",
    "limit": 2,
    "order": "bottom"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-17 — accepted 추천 / valid

2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 읍면동 승차지와 하차지의 조합별 건수를 세어 기록이 있는 그룹 중 적은 2개 그룹은?

- Family: `rb003-od-two-filters-emd-bottom`; contrast group: `rb003-od-two-filters-emd-bottom`.
- 판단: Pickup과 dropoff의 두 필터는 그대로 유지하고 emd 출발지-도착지 조합별 trip_count를 bottom/limit2. both는 LOCATION의 od_role=both가 아니라 두 축의 grouping factor다.
- 통계 정의: `{"avg_denominator":null,"bucket":null,"date_factor":"20260701-20260831","inner":null,"measure":"trip_count","observation_unit":"trip count","outer":null,"return_type":"OD/spatial dimension count list","select":null,"spatial_scope":"endpoint filters plus separate grouping"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: FAIL (의미 판정과 별개).
- 실행: code의 static diagnostic=`{"compile_ok":true,"execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:72`, `geoflow/grounding.py:60`, `geoflow_macros/od_event_to_measure.yaml`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "dropoff"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛시",
      "value": {
        "name": "솔빛시",
        "region": ""
      }
    },
    {
      "attributes": {
        "od_role": "pickup"
      },
      "concept": "LOCATION",
      "id": "c2",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "해온시",
      "value": {
        "name": "해온시",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c3",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c4",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260701-20260831",
    "dimension": "emd",
    "dimension_target": "both",
    "limit": 2,
    "order": "bottom"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-18 — accepted 추천 / train

2026년 4월부터 6월까지 하늘구 소속 법인택시의 택시·일 매출 기록을 월마다 중앙값으로 요약한 뒤, 그 월별 중앙값 중 가장 작은 숫자는?

- Family: `rb003-revenue-month-median-min`; contrast group: `rb003-revenue-month-median-min`.
- 판단: 하늘구 소속 corporate 택시의 택시·일 revenue 기록을 월 안에서 med로 요약하고 월별 중앙값 중 min 숫자를 반환한다. Taxi당 기간 합계나 fare가 아니다.
- 통계 정의: `{"avg_denominator":null,"bucket":"month","date_factor":"20260401-20260630","inner":"med","measure":"revenue","observation_unit":"taxi-day operation record","outer":"min","return_type":"numeric scalar","select":null,"spatial_scope":"taxi affiliation"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":true,"execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "revenue"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘구",
      "value": {
        "name": "하늘구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "med",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "min",
    "taxi_type": "corporate"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","OPERATION_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","OPERATION_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-19 — accepted 추천 / valid

2026년 4월부터 6월까지 하늘구 소속 택시의 실차 구간 요금 최솟값을 월마다 구했을 때, 가장 큰 숫자는?

- Family: `rb003-fare-month-min-max-answer-contrast`; contrast group: `rb003-fare-month-min-max-answer-contrast`.
- 판단: 월마다 trip fare min을 구한 뒤 max 숫자를 반환한다. Bucket label이 정답이 아니므로 answer=bucket를 넣지 않는다.
- 통계 정의: `{"avg_denominator":null,"bucket":"month","date_factor":"20260401-20260630","inner":"min","measure":"fare","observation_unit":"trip (실차 구간)","outer":"max","return_type":"numeric scalar","select":null,"spatial_scope":"taxi affiliation"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_trip_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "fare"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘구",
      "value": {
        "name": "하늘구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "min",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "max"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-20 — accepted 추천 / valid

2026년 4월부터 6월까지 하늘구 소속 택시의 실차 구간 요금 최솟값을 월마다 구했을 때, 가장 큰 최솟값이 나온 달은?

- Family: `rb003-fare-month-min-max-answer-contrast`; contrast group: `rb003-fare-month-min-max-answer-contrast`.
- 판단: 19와 같은 월별 trip fare min을 비교하되 max가 발생한 월을 반환한다. answer=bucket은 rollup=max를 select=max로 해석하게 하며 SELECT_GROUP 경로로 간다.
- 통계 정의: `{"avg_denominator":null,"bucket":"month","date_factor":"20260401-20260630","inner":"min","measure":"fare","observation_unit":"trip (실차 구간)","outer":null,"return_type":"selected period label(s), auxiliary statistic allowed","select":"max","spatial_scope":"taxi affiliation"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_trip_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "fare"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘구",
      "value": {
        "name": "하늘구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "min",
    "answer": "bucket",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "max"
  }
}
```

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.
- 로컬 SELECT_GROUP는 동률인 모든 group을 돌려준다. 한 달/한 주만 임의 선택하는 정책을 새로 가정하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","SELECT_GROUP"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","SELECT_GROUP"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-21 — needs_fix 추천 / train

2026년 8월 나래구 개인택시 매출 평균이 가장 낮았던 주는 언제야?

- Family: `intent-dcef4aa325e7c899`; contrast group: `intent-dcef4aa325e7c899`.
- 판단: 기승인 v002 train의 revenue week/avg 후 최저 주 선택. Date와 taxi_type 의미는 rejected의 legacy concept에서 normalization 후 정확히 복원된다. 미해결 place의 COND는 canonical role 위반이지만 실행 통계식·조건은 chosen과 같아 순수 semantic preference로 확정할 수 없다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"week","date_factor":"20260801-20260831","inner":"avg","measure":"revenue","observation_unit":"taxi-day operation record","outer":null,"return_type":"selected period label(s), auxiliary statistic allowed","select":"min","spatial_scope":"taxi affiliation"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: reviewed_gold_v002_train; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_billing_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:404`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "revenue"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "나래구",
      "value": {
        "name": "나래구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "answer": "bucket",
    "bucket": "week",
    "date": "20260801-20260831",
    "rollup": "min",
    "taxi_type": "private"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "revenue"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "COND",
      "source": "user",
      "subtype": "place",
      "value": {
        "name": "나래구",
        "region": ""
      }
    },
    {
      "concept": "LOCATION",
      "id": "c4",
      "role": "COND",
      "source": "user",
      "subtype": "taxi_type",
      "value": "private"
    }
  ],
  "factors": {
    "aggregation": "avg",
    "answer": "bucket",
    "bucket": "week",
    "date": "20260801-20260831",
    "rollup": "min"
  }
}
```
- 오답 판정: `{"error_scope":"raw_contract_and_canonical_role_only","normalized_query_conditions_and_statistic_equivalent":true,"observed_model_output_preserved":true,"original_category":"semantic","production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","OPERATION_METRIC","SELECT_GROUP"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"pure_query_semantic_negative_confirmed":false,"recommended_category":null,"strict_raw":{"compose_ok":null,"error_code":"INVALID_SUBTYPE","error_detail":"concepts[3]: LOCATION에 없는 subtype입니다: 'taxi_type'. 허용: place, scope, vicinity_scope","outcome":null,"parse_ok":false,"validation_codes":[],"validation_ok":null},"strict_raw_category":"constraint","synthetic":false,"wrongness_basis":"기승인 v002 train의 revenue week/avg 후 최저 주 선택. Date와 taxi_type 의미는 rejected의 legacy concept에서 normalization 후 정확히 복원된다. 미해결 place의 COND는 canonical role 위반이지만 실행 통계식·조건은 chosen과 같아 순수 semantic preference로 확정할 수 없다."}`

Correction proposal: payload는 위 chosen/rejected 그대로; `negative_category=constraint`, `negative_type=raw_contract_legacy_condition_role`로 metadata만 수정하는 안. 이 변경도 사람이 선택하기 전에는 적용하지 않는다.

Ambiguity / 확인 사항:
- raw canonical contract/role 학습을 위한 constraint pair로 유지할지, normalized 실행 의미가 같으므로 diagnostic으로 남길지 사람이 선택해야 한다. pure semantic pair로 승인하면 안 된다.
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.
- 로컬 SELECT_GROUP는 동률인 모든 group을 돌려준다. 한 달/한 주만 임의 선택하는 정책을 새로 가정하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","OPERATION_METRIC","SELECT_GROUP"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","OPERATION_METRIC","SELECT_GROUP"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-22 — needs_fix 추천 / train

2026년 8월 나래구 개인택시 매출 평균이 가장 낮았던 주는 언제야?

- Family: `intent-dcef4aa325e7c899`; contrast group: `intent-dcef4aa325e7c899`.
- 판단: 21과 같은 chosen. OBJECT/private는 strict raw 어휘 위반이며 value도 없다. 그러나 production hoister가 private subtype을 taxi_type factor로 옮기므로 MISSING_CONCEPT_VALUE라고 단정하면 틀린다. 실제 첫 strict 오류는 INVALID_SUBTYPE다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"week","date_factor":"20260801-20260831","inner":"avg","measure":"revenue","observation_unit":"taxi-day operation record","outer":null,"return_type":"selected period label(s), auxiliary statistic allowed","select":"min","spatial_scope":"taxi affiliation"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: reviewed_gold_v002_train; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_billing_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:404`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "revenue"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "나래구",
      "value": {
        "name": "나래구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "answer": "bucket",
    "bucket": "week",
    "date": "20260801-20260831",
    "rollup": "min",
    "taxi_type": "private"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "revenue"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "COND",
      "source": "user",
      "subtype": "place",
      "value": {
        "name": "나래구",
        "region": ""
      }
    },
    {
      "concept": "OBJECT",
      "id": "c4",
      "role": "COND",
      "source": "user",
      "subtype": "private"
    }
  ],
  "factors": {
    "aggregation": "avg",
    "answer": "bucket",
    "bucket": "week",
    "date": "20260801-20260831",
    "rollup": "min"
  }
}
```
- 오답 판정: `{"error_scope":"raw_contract_and_canonical_role_only","normalized_query_conditions_and_statistic_equivalent":true,"observed_model_output_preserved":true,"original_category":"semantic","production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","OPERATION_METRIC","SELECT_GROUP"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"pure_query_semantic_negative_confirmed":false,"recommended_category":null,"strict_raw":{"compose_ok":null,"error_code":"INVALID_SUBTYPE","error_detail":"concepts[3]: OBJECT에 없는 subtype입니다: 'private'. 허용: (이 concept에는 사용할 수 있는 subtype이 없습니다)","outcome":null,"parse_ok":false,"validation_codes":[],"validation_ok":null},"strict_raw_category":"constraint","synthetic":false,"wrongness_basis":"21과 같은 chosen. OBJECT/private는 strict raw 어휘 위반이며 value도 없다. 그러나 production hoister가 private subtype을 taxi_type factor로 옮기므로 MISSING_CONCEPT_VALUE라고 단정하면 틀린다. 실제 첫 strict 오류는 INVALID_SUBTYPE다."}`

Correction proposal: payload는 위 chosen/rejected 그대로; `negative_category=constraint`, `negative_type=raw_contract_legacy_condition_role`로 metadata만 수정하는 안. 이 변경도 사람이 선택하기 전에는 적용하지 않는다.

Ambiguity / 확인 사항:
- raw canonical contract/role 학습을 위한 constraint pair로 유지할지, normalized 실행 의미가 같으므로 diagnostic으로 남길지 사람이 선택해야 한다. pure semantic pair로 승인하면 안 된다.
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.
- 로컬 SELECT_GROUP는 동률인 모든 group을 돌려준다. 한 달/한 주만 임의 선택하는 정책을 새로 가정하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","OPERATION_METRIC","SELECT_GROUP"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","OPERATION_METRIC","SELECT_GROUP"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-23 — accepted 추천 / train

2026년 9월 가람구 소속 택시의 요금을 주마다 합산한 뒤, 주별 합계 중 가장 작은 값은?

- Family: `rb002-fare-week-sum-min`; contrast group: `rb002-fare-week-sum-min`.
- 판단: 기승인 v002 train fare week/sum→min. 실제 rejected는 trip 대신 EVENT/operation, 질문에 없는 scope:sido:1234, date 누락, bucket=month를 포함한다. 첫 오류 UNGROUNDED_SCOPE와 의미 오류를 함께 가진 실제 constraint negative다.
- 통계 정의: `{"avg_denominator":null,"bucket":"week","date_factor":"20260901-20260930","inner":"sum","measure":"fare","observation_unit":"trip (실차 구간)","outer":"min","return_type":"numeric scalar","select":null,"spatial_scope":"taxi affiliation"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: reviewed_gold_v002_train; dependency=None; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_trip_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "fare"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "가람구",
      "value": {
        "name": "가람구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "sum",
    "bucket": "week",
    "date": "20260901-20260930",
    "rollup": "min"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "fare",
      "text": "요금"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "COND",
      "source": "user",
      "subtype": "scope",
      "text": "가람구",
      "value": "scope:sido:1234"
    }
  ],
  "factors": {
    "aggregation": "sum",
    "answer": "value",
    "bucket": "month",
    "rollup": "min"
  }
}
```
- 오답 판정: `{"error_scope":"constraint_and_question_semantics","observed_model_output_preserved":true,"original_category":"constraint","production":{"compose_ok":null,"error_code":"UNGROUNDED_SCOPE","error_detail":"concepts[2]: 사용자 발화에 없는 scope입니다: 'scope:sido:1234'. scope 값을 직접 생성할 수 없습니다.","outcome":null,"parse_ok":false,"validation_codes":[],"validation_ok":null},"pure_query_semantic_negative_confirmed":false,"recommended_category":"constraint","strict_raw":{"compose_ok":null,"error_code":"UNGROUNDED_SCOPE","error_detail":"concepts[2]: 사용자 발화에 없는 scope입니다: 'scope:sido:1234'. scope 값을 직접 생성할 수 없습니다.","outcome":null,"parse_ok":false,"validation_codes":[],"validation_ok":null},"strict_raw_category":"constraint","synthetic":false,"wrongness_basis":"기승인 v002 train fare week/sum→min. 실제 rejected는 trip 대신 EVENT/operation, 질문에 없는 scope:sido:1234, date 누락, bucket=month를 포함한다. 첫 오류 UNGROUNDED_SCOPE와 의미 오류를 함께 가진 실제 constraint negative다."}`

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-24 — accepted 추천 / train

2026년 9월 가람구에서 기록된 도로 통행 속도의 주별 최댓값들 중 가장 작은 값은?

- Family: `rb002-speed-week-max-min`; contrast group: `rb002-speed-week-max-min`.
- 판단: 기승인 v002 train speed week/max→min. 실제 rejected는 날짜를 EVENT/passage COND의 value로 넣어 date factor를 누락한다. Parser는 받지만 Composer의 UNUSED_CONCEPT로 막히는 실제 constraint negative다.
- 통계 정의: `{"avg_denominator":null,"bucket":"week","date_factor":"20260901-20260930","inner":"max","measure":"speed","observation_unit":"passage record","outer":"min","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: reviewed_gold_v002_train; dependency=None; 실제 approval 없음.
- Token gate: FAIL (의미 판정과 별개).
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "가람구",
      "value": {
        "name": "가람구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "week",
    "date": "20260901-20260930",
    "rollup": "min"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed",
      "text": "도로 통행 속도"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "COND",
      "source": "user",
      "subtype": "passage",
      "text": "2026년 9월",
      "value": {
        "date": "20260901-20260930"
      }
    },
    {
      "concept": "EVENT",
      "id": "c3",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage",
      "text": "도로 통행 속도"
    },
    {
      "concept": "LOCATION",
      "id": "c4",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "가람구",
      "value": {
        "name": "가람구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "week",
    "rollup": "min"
  }
}
```
- 오답 판정: `{"error_scope":"constraint_and_question_semantics","observed_model_output_preserved":true,"original_category":"constraint","production":{"compose_ok":false,"error_code":"UNUSED_CONCEPT","error_detail":"질문의 조건을 계획에 반영하지 못했습니다: c2","outcome":null,"parse_ok":true,"validation_codes":[],"validation_ok":null},"pure_query_semantic_negative_confirmed":false,"recommended_category":"constraint","strict_raw":{"compose_ok":false,"error_code":"UNUSED_CONCEPT","error_detail":"질문의 조건을 계획에 반영하지 못했습니다: c2","outcome":null,"parse_ok":true,"validation_codes":[],"validation_ok":null},"strict_raw_category":"constraint","synthetic":false,"wrongness_basis":"기승인 v002 train speed week/max→min. 실제 rejected는 날짜를 EVENT/passage COND의 value로 넣어 date factor를 누락한다. Parser는 받지만 Composer의 UNUSED_CONCEPT로 막히는 실제 constraint negative다."}`

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-25 — accepted 추천 / valid

지난달 하늘동에서 관측된 도로 통행 RPM을 주마다 중앙값으로 요약한 뒤, 그 주별 중앙값들을 동일 가중으로 평균하면?

- Family: `rb003-rpm-week-median-mean-date-contrast`; contrast group: `rb003-rpm-week-median-mean-date-contrast`.
- 판단: Chosen은 03의 last_month/weekly med→avg. Rejected의 last_week는 기간 조건을 바꾼다. 다른 필드를 고치거나 삭제하지 않은 실제 날짜 의미 contrast다(합성).
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"week","date_factor":"last_month","inner":"med","measure":"rpm","observation_unit":"passage record","outer":"avg","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=RB003-03; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 med는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `geoflow/factors.py`, `geoflow/grounding.py:205`, `geoflow/compiler.py:198`, `geoflow/providers.py:91`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "med",
    "bucket": "week",
    "date": "last_month",
    "rollup": "avg"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "med",
    "bucket": "week",
    "date": "last_week",
    "rollup": "avg"
  }
}
```
- 오답 판정: `{"error_scope":"question_statistic_or_condition_or_answer","observed_model_output_preserved":false,"original_category":"semantic","production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"pure_query_semantic_negative_confirmed":true,"recommended_category":"semantic","strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw_category":"semantic","synthetic":true,"wrongness_basis":"Chosen은 03의 last_month/weekly med→avg. Rejected의 last_week는 기간 조건을 바꾼다. 다른 필드를 고치거나 삭제하지 않은 실제 날짜 의미 contrast다(합성)."}`

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.
- RB003-03의 human approval와 동일 validation split 유지가 pair 승인 선행 조건이다. Draft의 accepted 추천은 선행 approval가 아니다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-26 — accepted 추천 / valid

2026년 7월 6일부터 8월 30일까지 하늘동에서 관측된 도로 통행 RPM을 주마다 중앙값으로 요약한 뒤, 그 주별 중앙값들을 동일 가중으로 평균하면?

- Family: `rb003-rpm-week-median-mean-date-contrast`; contrast group: `rb003-rpm-week-median-mean-date-contrast`.
- 판단: Chosen은 04의 명시 기간. Rejected는 date factor를 제거해 원문의 기간 조건을 잃는다. Runtime이 허용하는 무기간 집계가 원문의 정답은 아니다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"week","date_factor":"20260706-20260830","inner":"med","measure":"rpm","observation_unit":"passage record","outer":"avg","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=RB003-04; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 med는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `geoflow/factors.py`, `geoflow/grounding.py:205`, `geoflow/compiler.py:198`, `geoflow/providers.py:91`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "med",
    "bucket": "week",
    "date": "20260706-20260830",
    "rollup": "avg"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "med",
    "bucket": "week",
    "rollup": "avg"
  }
}
```
- 오답 판정: `{"error_scope":"question_statistic_or_condition_or_answer","observed_model_output_preserved":false,"original_category":"semantic","production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"pure_query_semantic_negative_confirmed":true,"recommended_category":"semantic","strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw_category":"semantic","synthetic":true,"wrongness_basis":"Chosen은 04의 명시 기간. Rejected는 date factor를 제거해 원문의 기간 조건을 잃는다. Runtime이 허용하는 무기간 집계가 원문의 정답은 아니다."}`

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.
- RB003-04의 human approval와 동일 validation split 유지가 pair 승인 선행 조건이다. Draft의 accepted 추천은 선행 approval가 아니다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-27 — accepted 추천 / valid

2026년 4월부터 6월까지 하늘동에서 관측된 통행 속도를 월별 최댓값으로 요약한 뒤, 그 월별 최댓값들을 동일 가중 평균하면?

- Family: `rb003-speed-month-stage-validation`; contrast group: `rb003-speed-month-stage-validation`.
- 판단: Chosen은 12. 발화에서 명시된 하늘동을 implicit으로 바꾸고 value를 유지한 rejected는 user 출처와 implicit 제한을 위반한다. 숫자 실행 오류를 증명한 것은 아니며 grounding provenance label 오류다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"month","date_factor":"20260401-20260630","inner":"max","measure":"speed","observation_unit":"passage record","outer":"avg","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=RB003-12; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "avg"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "implicit",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "avg"
  }
}
```
- 오답 판정: `{"error_scope":"canonical_annotation_source_role_value","observed_model_output_preserved":false,"original_category":"semantic","production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"pure_query_semantic_negative_confirmed":false,"recommended_category":"semantic","strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw_category":"semantic","synthetic":true,"wrongness_basis":"Chosen은 12. 발화에서 명시된 하늘동을 implicit으로 바꾸고 value를 유지한 rejected는 user 출처와 implicit 제한을 위반한다. 숫자 실행 오류를 증명한 것은 아니며 grounding provenance label 오류다."}`

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.
- 원문↔canonical source/role/value annotation이 판단 기준이다. Runtime scalar 변경 또는 downstream failure가 있다는 주장이 아니다.
- RB003-12의 human approval와 동일 validation split 유지가 pair 승인 선행 조건이다. Draft의 accepted 추천은 선행 approval가 아니다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-28 — accepted 추천 / valid

2026년 4월부터 6월까지 하늘동에서 관측된 통행 속도를 월별 최댓값으로 요약한 뒤, 그 월별 최댓값들을 동일 가중 평균하면?

- Family: `rb003-speed-month-stage-validation`; contrast group: `rb003-speed-month-stage-validation`.
- 판단: Chosen은 12. 미해결 장소에 COND를 붙인 rejected는 production prompt의 SUBCOND 정의와 다르다. PLACE_TO_SCOPE는 COND도 받아 그래프가 같을 수 있지만 canonical role supervision에서는 오답이다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"month","date_factor":"20260401-20260630","inner":"max","measure":"speed","observation_unit":"passage record","outer":"avg","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=RB003-12; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "avg"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "COND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "avg"
  }
}
```
- 오답 판정: `{"error_scope":"canonical_annotation_source_role_value","observed_model_output_preserved":false,"original_category":"semantic","production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"pure_query_semantic_negative_confirmed":false,"recommended_category":"semantic","strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw_category":"semantic","synthetic":true,"wrongness_basis":"Chosen은 12. 미해결 장소에 COND를 붙인 rejected는 production prompt의 SUBCOND 정의와 다르다. PLACE_TO_SCOPE는 COND도 받아 그래프가 같을 수 있지만 canonical role supervision에서는 오답이다."}`

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.
- 원문↔canonical source/role/value annotation이 판단 기준이다. Runtime scalar 변경 또는 downstream failure가 있다는 주장이 아니다.
- RB003-12의 human approval와 동일 validation split 유지가 pair 승인 선행 조건이다. Draft의 accepted 추천은 선행 approval가 아니다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-29 — accepted 추천 / valid

2026년 4월부터 6월까지 하늘동에서 관측된 통행 속도를 월별 최댓값으로 요약한 뒤, 그 월별 최댓값들을 동일 가중 평균하면?

- Family: `rb003-speed-month-stage-validation`; contrast group: `rb003-speed-month-stage-validation`.
- 판단: Chosen은 12. 질문에 없는 속도값 42를 MEASURE/user/value 입력으로 만든 rejected는 hallucination이다. 원문은 speed 결과를 요구하므로 implicit/value 없음이 맞다. 결측값 누락 control과는 구분한다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"month","date_factor":"20260401-20260630","inner":"max","measure":"speed","observation_unit":"passage record","outer":"avg","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=RB003-12; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "avg"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "user",
      "subtype": "speed",
      "value": 42
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "avg"
  }
}
```
- 오답 판정: `{"error_scope":"canonical_annotation_source_role_value","observed_model_output_preserved":false,"original_category":"semantic","production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"pure_query_semantic_negative_confirmed":false,"recommended_category":"semantic","strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw_category":"semantic","synthetic":true,"wrongness_basis":"Chosen은 12. 질문에 없는 속도값 42를 MEASURE/user/value 입력으로 만든 rejected는 hallucination이다. 원문은 speed 결과를 요구하므로 implicit/value 없음이 맞다. 결측값 누락 control과는 구분한다."}`

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.
- 원문↔canonical source/role/value annotation이 판단 기준이다. Runtime scalar 변경 또는 downstream failure가 있다는 주장이 아니다.
- RB003-12의 human approval와 동일 validation split 유지가 pair 승인 선행 조건이다. Draft의 accepted 추천은 선행 approval가 아니다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-30 — accepted 추천 / valid

2026년 7월과 8월 해온시에서 승차하고 솔빛시에서 하차한 실차 구간만 대상으로, 읍면동 승차지와 하차지의 조합별 건수를 세어 기록이 있는 그룹 중 적은 2개 그룹은?

- Family: `rb003-od-two-filters-emd-bottom`; contrast group: `rb003-od-two-filters-emd-bottom`.
- 판단: Chosen은 17의 emd OD pair 그룹. Rejected가 dimension_target만 dropoff로 바꾸면 승차지 축을 합쳐 하차지역 단독 집계가 된다. 두 필터가 남아 있어도 정답 grouping은 사라진다.
- 통계 정의: `{"avg_denominator":null,"bucket":null,"date_factor":"20260701-20260831","inner":null,"measure":"trip_count","observation_unit":"trip count","outer":null,"return_type":"OD/spatial dimension count list","select":null,"spatial_scope":"endpoint filters plus separate grouping"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=RB003-17; 실제 approval 없음.
- Token gate: FAIL (의미 판정과 별개).
- 실행: code의 static diagnostic=`{"compile_ok":true,"execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:72`, `geoflow/grounding.py:60`, `geoflow_macros/od_event_to_measure.yaml`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "dropoff"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛시",
      "value": {
        "name": "솔빛시",
        "region": ""
      }
    },
    {
      "attributes": {
        "od_role": "pickup"
      },
      "concept": "LOCATION",
      "id": "c2",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "해온시",
      "value": {
        "name": "해온시",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c3",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c4",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260701-20260831",
    "dimension": "emd",
    "dimension_target": "both",
    "limit": 2,
    "order": "bottom"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "dropoff"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛시",
      "value": {
        "name": "솔빛시",
        "region": ""
      }
    },
    {
      "attributes": {
        "od_role": "pickup"
      },
      "concept": "LOCATION",
      "id": "c2",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "해온시",
      "value": {
        "name": "해온시",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c3",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c4",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260701-20260831",
    "dimension": "emd",
    "dimension_target": "dropoff",
    "limit": 2,
    "order": "bottom"
  }
}
```
- 오답 판정: `{"error_scope":"question_statistic_or_condition_or_answer","observed_model_output_preserved":false,"original_category":"semantic","production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"pure_query_semantic_negative_confirmed":true,"recommended_category":"semantic","strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw_category":"semantic","synthetic":true,"wrongness_basis":"Chosen은 17의 emd OD pair 그룹. Rejected가 dimension_target만 dropoff로 바꾸면 승차지 축을 합쳐 하차지역 단독 집계가 된다. 두 필터가 남아 있어도 정답 grouping은 사라진다."}`

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- RB003-17의 human approval와 동일 validation split 유지가 pair 승인 선행 조건이다. Draft의 accepted 추천은 선행 approval가 아니다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","PLACE_TO_SCOPE","OD_EVENT_TO_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","RESOLVE_PLACE_SCOPE","TRIP_COUNT"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-31 — accepted 추천 / valid

2026년 4월부터 6월까지 하늘동 안에서 관측된 도로 통행 속도를 월마다 산술평균하고, 그 월별 평균 중 가장 큰 숫자는?

- Family: `rb003-speed-month-stage-validation`; contrast group: `rb003-speed-month-stage-validation`.
- 판단: Chosen은 08의 month/avg→max. Rejected의 month/max→avg는 평균들의 최대와 최대들의 평균을 뒤바꾼 다른 통계식이다. 12의 positive 통계식과 같지만 질문이 다르며 둘 모두 validation에 둔다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"month","date_factor":"20260401-20260630","inner":"avg","measure":"speed","observation_unit":"passage record","outer":"max","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=RB003-08; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "max"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "avg"
  }
}
```
- 오답 판정: `{"error_scope":"question_statistic_or_condition_or_answer","observed_model_output_preserved":false,"original_category":"semantic","production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"pure_query_semantic_negative_confirmed":true,"recommended_category":"semantic","strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw_category":"semantic","synthetic":true,"wrongness_basis":"Chosen은 08의 month/avg→max. Rejected의 month/max→avg는 평균들의 최대와 최대들의 평균을 뒤바꾼 다른 통계식이다. 12의 positive 통계식과 같지만 질문이 다르며 둘 모두 validation에 둔다."}`

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.
- RB003-08의 human approval와 동일 validation split 유지가 pair 승인 선행 조건이다. Draft의 accepted 추천은 선행 approval가 아니다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-32 — accepted 추천 / valid

2026년 4월부터 6월까지 하늘구 소속 택시의 실차 구간 요금 최솟값을 월마다 구했을 때, 가장 큰 최솟값이 나온 달은?

- Family: `rb003-fare-month-min-max-answer-contrast`; contrast group: `rb003-fare-month-min-max-answer-contrast`.
- 판단: Chosen은 20의 최대 월별 최솟값이 발생한 달. Rejected가 answer=bucket를 제거하면 REDUCE_GROUPS의 숫자 반환으로 바뀐다. 우연히 같은 숫자가 나오는지와 무관하게 답의 형태가 틀리다.
- 통계 정의: `{"avg_denominator":null,"bucket":"month","date_factor":"20260401-20260630","inner":"min","measure":"fare","observation_unit":"trip (실차 구간)","outer":null,"return_type":"selected period label(s), auxiliary statistic allowed","select":"max","spatial_scope":"taxi affiliation"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=RB003-20; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_trip_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "fare"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘구",
      "value": {
        "name": "하늘구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "min",
    "answer": "bucket",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "max"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "fare"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘구",
      "value": {
        "name": "하늘구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "min",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "max"
  }
}
```
- 오답 판정: `{"error_scope":"question_statistic_or_condition_or_answer","observed_model_output_preserved":false,"original_category":"semantic","production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"pure_query_semantic_negative_confirmed":true,"recommended_category":"semantic","strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw_category":"semantic","synthetic":true,"wrongness_basis":"Chosen은 20의 최대 월별 최솟값이 발생한 달. Rejected가 answer=bucket를 제거하면 REDUCE_GROUPS의 숫자 반환으로 바뀐다. 우연히 같은 숫자가 나오는지와 무관하게 답의 형태가 틀리다."}`

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.
- 로컬 SELECT_GROUP는 동률인 모든 group을 돌려준다. 한 달/한 주만 임의 선택하는 정책을 새로 가정하지 않는다.
- RB003-20의 human approval와 동일 validation split 유지가 pair 승인 선행 조건이다. Draft의 accepted 추천은 선행 approval가 아니다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","SELECT_GROUP"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","SELECT_GROUP"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-33 — accepted 추천 / valid

2026년 4월부터 6월까지 하늘구 소속 택시의 실차 구간별 요금 최댓값을 월마다 구하고, 그 월별 최댓값들의 동일 가중 평균은?

- Family: `rb003-fare-month-max-mean`; contrast group: `rb003-fare-month-max-mean`.
- 판단: Chosen은 06의 trip fare month/max→avg. Rejected는 measure를 revenue, EVENT를 operation으로 함께 바꿔 택시·일 매출 통계로 만든다. 구조가 valid하더라도 관측 단위와 측정값이 다르다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"month","date_factor":"20260401-20260630","inner":"max","measure":"fare","observation_unit":"trip (실차 구간)","outer":"avg","return_type":"numeric scalar","select":null,"spatial_scope":"taxi affiliation"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=RB003-06; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_trip_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "fare"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘구",
      "value": {
        "name": "하늘구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "avg"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "revenue"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘구",
      "value": {
        "name": "하늘구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "avg"
  }
}
```
- 오답 판정: `{"error_scope":"question_statistic_or_condition_or_answer","observed_model_output_preserved":false,"original_category":"semantic","production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","OPERATION_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"pure_query_semantic_negative_confirmed":true,"recommended_category":"semantic","strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","OPERATION_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw_category":"semantic","synthetic":true,"wrongness_basis":"Chosen은 06의 trip fare month/max→avg. Rejected는 measure를 revenue, EVENT를 operation으로 함께 바꿔 택시·일 매출 통계로 만든다. 구조가 valid하더라도 관측 단위와 측정값이 다르다."}`

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.
- RB003-06의 human approval와 동일 validation split 유지가 pair 승인 선행 조건이다. Draft의 accepted 추천은 선행 approval가 아니다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","TRIP_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

### RB003-34 — accepted 추천 / valid

2026년 4월부터 6월까지 하늘동 안에서 관측된 도로 통행 속도를 월마다 산술평균하고, 그 월별 평균 중 가장 큰 숫자는?

- Family: `rb003-speed-month-stage-validation`; contrast group: `rb003-speed-month-stage-validation`.
- 판단: Chosen은 08의 passage speed month/avg→max. Rejected는 동일 기록·집계에서 measure만 rpm으로 바꾼다. km/h 속도와 분당 회전 속도는 다른 물리량이다.
- 통계 정의: `{"avg_denominator":"inside: observed records per bucket; outside: available bucket summaries, each equally weighted. Empty/missing policy is not invented.","bucket":"month","date_factor":"20260401-20260630","inner":"avg","measure":"speed","observation_unit":"passage record","outer":"max","return_type":"numeric scalar","select":null,"spatial_scope":"passage occurrence location"}`
- Lineage: `no_conflict_found_in_reviewed_sources`; automatic reasons=`[]`.
- Chosen: pending_new_gold; dependency=RB003-08; 실제 approval 없음.
- Token gate: PASS.
- 실행: code의 static diagnostic=`{"compile_ok":false,"error_code":"UNVERIFIED_TIMS_CONTRACT","error_detail":"measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_passage_metrics","execution_tested":false,"mode":"legacy","provider":"mock/TIMS","reference_date":"2026-09-25"}`; 이번 수치 실행은 없음.
- 근거: `prompts/geoflow_planner.yaml:163`, `prompts/geoflow_planner.yaml:185`, `prompts/geoflow_planner.yaml:222`, `prompts/geoflow_planner.yaml:275`, `prompts/geoflow_planner.yaml:312`, `prompts/geoflow_planner.yaml:326`, `schemas/tims.yaml:51`, `schemas/tims.yaml:110`, `geoflow/operator_registry.py:385`, `geoflow/operator_registry.py:473`, `geoflow/measures.py`, `geoflow/aggregation.py:91`, `geoflow_macros/event_to_grouped_measure.yaml`, `geoflow/analysis_ops.py:223`, `geoflow/compiler.py:713`, `geoflow/providers.py:49`, `prompts/geoflow_planner.yaml:326`, `geoflow/grounding.py:452`, `geoflow_macros/place_to_scope.yaml`

Proposed gold/chosen:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "speed"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "max"
  }
}
```

Rejected (원본 canonical 후보 그대로):
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "하늘동",
      "value": {
        "name": "하늘동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "month",
    "date": "20260401-20260630",
    "rollup": "max"
  }
}
```
- 오답 판정: `{"error_scope":"question_statistic_or_condition_or_answer","observed_model_output_preserved":false,"original_category":"semantic","production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"pure_query_semantic_negative_confirmed":true,"recommended_category":"semantic","strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw_category":"semantic","synthetic":true,"wrongness_basis":"Chosen은 08의 passage speed month/avg→max. Rejected는 동일 기록·집계에서 measure만 rpm으로 바꾼다. km/h 속도와 분당 회전 속도는 다른 물리량이다."}`

Corrected grounding/pair: 없음. Diagnostic01·02는 grounding 교체로 lineage 보호를 우회하지 않는다.

Ambiguity / 확인 사항:
- 이 판정은 code/prompt에 맞는 semantic annotation 추천이며 provider 수치 정답이나 human approval가 아니다.
- 합성 장소는 literal 값이며 상위 지역을 발명하지 않고 region=""를 유지한다. 실행 benchmark 편입은 별도 검증이다.
- 주 시작·부분 구간·결측/빈 구간·짝수 중앙값의 TIMS 정의는 실행 계약의 별도 문제다. zero-fill이나 임의 분모를 annotation에 추가하지 않는다.
- RB003-08의 human approval와 동일 validation split 유지가 pair 승인 선행 조건이다. Draft의 accepted 추천은 선행 approval가 아니다.

- 재검증 chosen: `{"production":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true},"strict_raw":{"compose_ok":true,"error_code":null,"macros":["PLACE_TO_SCOPE","EVENT_TO_GROUPED_MEASURE"],"operators":["RESOLVE_PLACE_SCOPE","PASSAGE_METRIC","REDUCE_GROUPS"],"outcome":"answered","parse_ok":true,"validation_codes":[],"validation_ok":true}}`

## Provenance 및 불변성

다음 JSON은 재검증 당시 source/hash를 고정한다. 기록 원본의 기존 SHA와 approval/status는 수정하지 않았다. 검토 draft 자체의 integrity는 파일 SHA와 Git commit으로 관리한다.

```json
{
  "reviewed_at": "2026-10-05T06:20:58.418344+00:00",
  "work_branch": "geoflow/sft-dpo-thor",
  "commit_before_review": "356e80f037da90070e3d50031e9c5849cde1c1fd",
  "seed": 42,
  "prompt_sha256": "522aa3b1716248b53a755ee1b236e7aef302c85504e9cfac3825f4d3cc817945",
  "source_queue_sha256": "830efaad4ba7893146487442c660a22515d31dd7315a932a3dc3837e05a9fe3e",
  "view_sha256": "d2b9b0e2c600598058e69fa614d4b4611e8255ee9069fba66c43c4d7d07dd05e",
  "token_report_sha256": "7394d8c6b86954ca613da0cd9169d3960e101c53facc957a97a06b258815c134",
  "production_and_config_hashes": {
    "geoflow/grounding.py": "4d55d062e584d28822ebef57b1db2765f23e52372b13f48ba82da5d98ec821bb",
    "geoflow/composer.py": "09a0f440b7115709eb7584ee5649b83edc6532a64b988e8637c0a7ad63472ebe",
    "geoflow/validator.py": "9629045fb0bee2528379b0bbd2f2e72455ff810d09a39760117ed0032a632824",
    "geoflow/compiler.py": "3c379f75fca84a87f6d9728e1689d2d3ffcf509973f0a0661f9474e1a721b549",
    "geoflow/operator_mapping.py": "b40419493a99765407d6d1480746175abb441a1176f27f7659120c50b9238ee3",
    "geoflow/operator_registry.py": "81e0132ae22cb457d9e81b1fcef8e4996aebf22a738f37ae2345cb0c9bd17fb9",
    "geoflow/factors.py": "f524b30ad51ab7c564db36c4ac7b766ce6ad96405cb79eee2ed25d1ec524c322",
    "geoflow/types.py": "689760613b09d1737dbe435361dc42c13da779fe43bc5ea58178c858796b074b",
    "geoflow/aggregation.py": "f75ba44df0a1c9504dc2efc6a4953cf0d94693ecd7a905f6e2f4256d48d5e866",
    "geoflow/measures.py": "c67ef1155a68edb6ce3a59290a35ce0be4131da1a4a6d950cb8f3b8867615d33",
    "geoflow/providers.py": "84f57e3afe37de5068e650627c9a211f605567426d9b3e2f077b16922a511706",
    "geoflow/tims_contract.py": "d5f304be70c09dbe5159ddcc828918c6206c367850046a3d5fd7774cdd11bdcb",
    "geoflow/analysis_ops.py": "4de0518b28392ceca9aa3483d9d0044c29ecb942c2dc2f30ac55dc31c47f382d",
    "prompts/geoflow_planner.yaml": "9d4bd132e267ecab8d04db5e23c0f59220848eae67fdc720e1c7ec3f35c4a49a",
    "schemas/tims.yaml": "8065cfffd951b578cb0210114211f7c22f9972cfa014d9ab17e8d00cb218b764",
    "schemas/_common.yaml": "b3479ffbd07ae1749ddacaf39332b503ca57abd2ddcf84fbb7ba497174306397",
    "training/configs/qwen_sft.yaml": "997afd5d4e55be73ff44dffe17d00780449251d363bf57b17c5c2ffaf8f503d7",
    "training/configs/qwen3_8b_thor_smoke_sft.yaml": "82845949839a014490acbf52effdfe9fcf14a7dfc373b9836d66afb79bddc18c",
    "training/configs/qwen_dpo.yaml": "b9bc73ec041301b2ef9ea4ca025894544b6b32686321c0fbf5a3265fe863e070",
    "training/configs/qwen3_8b_thor_sft.yaml": "2761b87e4a96d42eaf2951115bbb4646c76ff33a23d9e5e21d2578e65d277c61",
    "training/configs/qwen3_8b_thor_dpo.yaml": "003598f897771102fff0b4ffd6b837de912eec3fde236364083276a9a7723791",
    "training/configs/qwen3_8b_thor_smoke_dpo.yaml": "081ad0dc4d73376fcb316a3d9f60923793984fdf1483979a4268e305e80eceb8"
  },
  "protected_source_hashes": {
    "/home/hwkim/assistant_univ/training/annotations/generated/corpora/reviewed_gold_v002/corpus_manifest.json": "b7a07c3a61d73f0dd7d4a88d0a899cf213d9a9d46048f5da5ea1beb531fbc84a",
    "/home/hwkim/assistant_univ/assistant_univ_questions_100_v3.yaml": "3b92d9623236f7cc391589c6b1462babc839fd9aea9bc657933f8eae67e35e9f",
    "/home/hwkim/assistant_univ/evaluation/aggregation_holdout_parents.yaml": "979479b85b9f098b1d3a1d173571812468a13bc310ccd5770af0b9b8b86a38fd",
    "/home/hwkim/assistant_univ/evaluation/corpus_registry.yaml": "e1fd7b19ce1dde51883554892c297c4032cab5d5702c349a1e9c90988a3a4e1c",
    "/home/hwkim/assistant_univ/evaluation/factor_holdout_parents.yaml": "1eed9781961b72c570bdf22d07f9f84ed72b07dd4eaeeb0f817e35c423fcb56f",
    "/home/hwkim/assistant_univ/evaluation/grounding_v1/holdout_questions.yaml": "fac171e6c97ef20aee9a824a1c20217825266970e81b7abdb66b090ee91456d7",
    "/home/hwkim/assistant_univ/evaluation/grounding_v2/contrast_questions.yaml": "7880d96a8e3bd83ba6d058aea93624a4c06111c924886a9c543fafb0be91b756",
    "/home/hwkim/assistant_univ/evaluation/grounding_v2/independent_questions.yaml": "c8f4f972390dba7d878492de1742d60aae2507df4e23b7653f90a2d7511a941b",
    "/home/hwkim/assistant_univ/evaluation/grounding_v2/independent_v3_questions.yaml": "f2d46cb26b19a32d08f6ed0322077cc13412c664d9101e25b7cf204e13c6e435",
    "/home/hwkim/assistant_univ/evaluation/grounding_v3/independent_v4_questions.yaml": "3d11e6d196896766af09522ed30c40a1911f62973d3d24490f32886cd9bce116",
    "/home/hwkim/assistant_univ/evaluation/grounding_v4/answer_target_questions.yaml": "78707de11e293874e7d8da1e0e45e699eff9caf85f27fd638abb08c505b0cfc4",
    "/home/hwkim/assistant_univ/evaluation/grounding_v7/stage_contrast_questions.yaml": "14e0150ba3a9037369a0f386b94cffbdb498353675f970644ded047f0e95e81b",
    "/home/hwkim/assistant_univ/evaluation/grounding_v8/heldout_questions.yaml": "662be1d555777f03252e439e049ba28363fbbb39bbb364ad064857d41001f3d0",
    "/home/hwkim/assistant_univ/evaluation/grounding_v8/od_contrast_questions.yaml": "1c702d130ab0ce0c5bf3013fc973638169bfe74829ce1e8f705e4a472545b3f9",
    "/home/hwkim/assistant_univ/evaluation/grounding_v8/prompts/P2.yaml": "f619069d6ea725dd725b68f7f0d0cc160681d1632ab0668d321afaae7b54c109",
    "/home/hwkim/assistant_univ/evaluation/grounding_v8/prompts/P3.yaml": "f21efb315349d0cb951aa03bc56f73caf019ede784fbae771810fecf5790f851",
    "/home/hwkim/assistant_univ/evaluation/grounding_v8/prompts/P5.yaml": "86a7deae3af2436f6582b82e041e7d8d633e2278172aa1bc98107c941811e319",
    "/home/hwkim/assistant_univ/evaluation/grounding_v9/heldout_questions.yaml": "94a7113d5f7ccc24b36f1a9d14de30c8c65e7cd2477e4b611805d1b4a315a717",
    "/home/hwkim/assistant_univ/evaluation/holdout_parents.yaml": "88f665cb1b1adcda1a36cf190339be66fd1e9cd47ca45cbcb4fcbb7fba199500",
    "/home/hwkim/assistant_univ/evaluation/labels/aggregation_semantics_v2.yaml": "66081b0f67d22c354311f781c25c464c55ad4e52061f6b7a8b0d729e9653a733",
    "/home/hwkim/assistant_univ/evaluation/labels/condition_date_equivalents_v1.yaml": "e5fc21ddb8ee6b588d53f5a988174feba488c3599cbd24871b058ff46e27cdd2",
    "/home/hwkim/assistant_univ/evaluation/local_aggregation_holdout_parents.yaml": "7f057c3e0b429508ca9babed386ae0d02bfc1829b9682743144cf082bf85d64a",
    "/home/hwkim/assistant_univ/evaluation/paraphrases.yaml": "046d7cca8a31b7851998554e534bf65c002853cb24654c305a4c1ffba81db45c",
    "/home/hwkim/assistant_univ/evaluation/paraphrases_aggregation_holdout.yaml": "2d5b65b3542feae63464de6c0b5a8ac3209bbec5b4269fb8d714fa9b5bfcd899",
    "/home/hwkim/assistant_univ/evaluation/paraphrases_factor_holdout.yaml": "9f186d77d015d62294a4bd1d164f020831e7283e94284fd430e92ac35fae009b",
    "/home/hwkim/assistant_univ/evaluation/paraphrases_holdout.yaml": "ad6459a48fe07e40c6de18d131b01c5ee02fabd2531aa35fb7274b48c34ade50",
    "/home/hwkim/assistant_univ/evaluation/paraphrases_local_aggregation_holdout.yaml": "67fb0215947315e91c97e28ed2b4c91bcb7d04dbc361d3ee5d51a9c3c47ec136",
    "/home/hwkim/assistant_univ/evaluation/paraphrases_verifier_holdout.yaml": "4d739cf5cd8d0b6004f8f2385acb3e5f33c7c500b16f8203aeef289ef07f00d3",
    "/home/hwkim/assistant_univ/evaluation/prompt_ab/pinned/v2_db113124/geoflow_planner.yaml": "c5f4ad6bff56f732d14fedea6082bf63fee5ad5d35d10d058c4a73d1f0cb390c",
    "/home/hwkim/assistant_univ/evaluation/reference/reference_questions_v1.yaml": "967b0463c9e73bfedbe802c0c46d43582d7fd85e8f4e9bc65af5d8b5cded078d",
    "/home/hwkim/assistant_univ/evaluation/retrieval/retrieval_eval_v1.yaml": "af5a8f49a31c803bb3d3469725cfcdb2af09374bd9a5fac5662e219e30b72bb3",
    "/home/hwkim/assistant_univ/evaluation/structured_grounding/dev_questions.yaml": "5a97e975d8b7b377ffab3c25c54cd9c00ce66087951bb2b78d01bace147c35e1",
    "/home/hwkim/assistant_univ/evaluation/structured_grounding/eval_questions_conditions_v1.yaml": "e396eb15d06f416eb250345744a41079e4baf6e43c2e3851e9d0b3d9f0894111",
    "/home/hwkim/assistant_univ/evaluation/structured_grounding/eval_questions_conditions_v2.yaml": "a3769d6efec9db01f816848270629ec5b9e95e94e6be05b39dee77acfbae3469",
    "/home/hwkim/assistant_univ/evaluation/structured_grounding/eval_questions_v1.yaml": "8d13681a90f3091c73f9ec0a3499781468a08c9c36ba8fab3532ac47467d6f6f",
    "/home/hwkim/assistant_univ/evaluation/stub_query_v1.yaml": "f4c8b9873b5fbc37256e53a49a4fc4c91c6715c359e6a8f6a18b63f24afac4ac",
    "/home/hwkim/assistant_univ/evaluation/v2/holdout_v2_parents.yaml": "25d2d350bb750d073172292d1ce611f125ca69937ea4e564e5047cd5328dc24c",
    "/home/hwkim/assistant_univ/evaluation/v2/label_revisions.yaml": "82bd9f93ef5017c58ba3f5def7d980a1928f746c0c78f094c03d816374ed1e01",
    "/home/hwkim/assistant_univ/evaluation/v2/paraphrases_holdout_v2.yaml": "d1884be436d8f61e1ac20370e3654ccc39a3480602cde95e4c181cb6bc0f614e",
    "/home/hwkim/assistant_univ/evaluation/v2/stub_v2_gold.yaml": "1cde411c0a52ea78dccf4faa6558ee4e68ed52469f7b805164102aff91ab46d0",
    "/home/hwkim/assistant_univ/evaluation/vendor/vendor_queries.yaml": "0591fe0eeaf46275774fecd75e80c1083e3813568124b24ef627dea3b9c393bb",
    "/home/hwkim/assistant_univ/evaluation/vendor/vendor_trace_gold.yaml": "e443793eeea369a04cffc65f1a468889daa502380f8800dfb427e64ad3fd79a7",
    "/home/hwkim/assistant_univ/evaluation/vendor100/gold.yaml": "f99bc5fdef623e973901e5b339ede3c7f4e36cfa133887ea933e9683a7d8b4f0",
    "/home/hwkim/assistant_univ/evaluation/vendor100/stated_variants.yaml": "e95222c68430f8617ece65a2f2aae139b339f3e2050c08e4a8ed93c082fd56a5",
    "/home/hwkim/assistant_univ/evaluation/verifier_holdout_parents.yaml": "0519952370a3184c21521084c8c9082f0766f511b09ab895843f547e38875c05",
    "/home/hwkim/assistant_univ/stub_query.yaml": "71ede4275aae87bdccda8f348e77b61e3ed3a34989667db14de903119d143e02",
    "/home/hwkim/assistant_univ/stub_query_boundary.yaml": "006585880a40f51ef41223baabe44a98fdea492aa0176c2e84139a81c4af73c5",
    "/home/hwkim/assistant_univ/training/annotations/generated/corpora/reviewed_gold_v001/sft_valid.jsonl": "1ef55c6f31803c46228877313675771e51ad943c87c5a138821ebe8329e2cbfd",
    "/home/hwkim/assistant_univ/training/annotations/generated/corpora/reviewed_gold_v002/sft_valid.jsonl": "94e879b32138244d2e740773f3975d78ffc740d429fbb96f9d65e5991f1097c1",
    "/home/hwkim/assistant_univ/training/generated/sft_valid.jsonl": "c38308e04c5623baa4e13bb3eb4a39fdcdb2cde2b7aeea07e9dab31d467a5354",
    "/home/hwkim/assistant_univ/training/experiments/thor_pilot_001/items.json": "2cd307d9b109c82bda817f77b6687bdffaff0ef9b6fe35904fe17cda51576f13",
    "/home/hwkim/assistant_univ/training/experiments/thor_pilot_002/items.json": "2ec17baafc0d68f6f3ac53f50fbbeb5c55b0e91e79f05f2bc261f6c98756a762"
  },
  "frozen_prior_sha256": {
    "training/annotations/generated/review_batch_003/coverage_expected.json": "9856f9511e4b9bbfa5e91c3a118c15fbb439ba860973cf8c0eb9f993fecebbf8",
    "training/annotations/generated/review_batch_003/test_review_batch_003.py": "ebef61525376df40efd94d208628b8dad6ce6cbcc6a40135a82fe38a7a9483c5",
    "training/annotations/generated/review_batch_003/REVIEW_BATCH_003.md": "e8d59714384254cc2549d5456dfaf61d7b37b071bdbf93a7d6cea641feac1066",
    "training/annotations/generated/review_batch_003/split_plan.json": "a4c43408704509b35915b77c39b1901431451bf3b84fa1209c7c7207d56698f0",
    "training/annotations/generated/review_batch_003/generation_recipe.py": "6af32b6f6a3483fcd288876f26c779b7c594299cc0c23b1c66b64733980fcbfa",
    "training/annotations/generated/review_batch_003/mining_audit.json": "2dd62b9b236673ff9bd7343932b5c468857bca71b35c27af432bde4aa3eda2b0",
    "training/annotations/generated/review_batch_003/VALIDATION_BATCH_003.json": "5e2665dd81287357e45e68dab0f17b1f69f045a2859aadad8af49b57334f9b40",
    "training/annotations/generated/review_batch_003/review_batch_003.xlsx": "639520ac4082496492f49071fbc75955943ad51938d807ee800b014a85889e42",
    "training/annotations/generated/review_batch_003/token_validation.json": "7394d8c6b86954ca613da0cd9169d3960e101c53facc957a97a06b258815c134",
    "training/annotations/generated/review_batch_003/manifest.json": "e522680b60be076a425fe59deb3e26b523678b2715d778a43cdaf1667836a6a4",
    "training/annotations/generated/review_batch_003/review_batch_003.jsonl": "d2b9b0e2c600598058e69fa614d4b4611e8255ee9069fba66c43c4d7d07dd05e",
    "training/annotations/generated/review_batch_003/review_queue.jsonl": "830efaad4ba7893146487442c660a22515d31dd7315a932a3dc3837e05a9fe3e",
    "training/annotations/generated/review_batch_001/REVIEW_DECISIONS_001.md": "135694470d816d783c43f6fe34dd36a3ff05c97839884292a9bff00c15c6f430",
    "training/annotations/generated/review_batch_001/resolution_001.jsonl": "b1112178ae4b8cf4ad48a48a0b2903bc3d3a99892f4933ed65432060b8a1962c",
    "training/annotations/generated/review_batch_001/IMPORT_VALIDATION_001.json": "268b17e11d480ea5e6357fa81e8a6813e7f8b2b91ca0b99180ed50d2612b8f05",
    "training/annotations/generated/review_batch_001/review_batch_001.xlsx": "f3fa5250174b10886559a68a0ec2168f95106760dda1321abf528270cd3aac36",
    "training/annotations/generated/review_batch_001/RESOLUTION_001.md": "da3e253263e612072feb8d9b3ed8507287c00d6586f51082b8b80b676b2dfe9f",
    "training/annotations/generated/review_batch_001/review_batch_001.jsonl": "6a0c1c944548caf67627f6db21555c2ddbc14af3d261533581bfc035ae1b622b",
    "training/annotations/generated/review_batch_001/eligible_46_priority.jsonl": "6639cb0a5d23b5ea35405f0f46da33641b4526315e9b610091ba5a2d950778ab",
    "training/annotations/generated/review_batch_001/decisions.jsonl": "9b2cde3199641d89cb75836d233cdd7a97ee7f97595ae793599647dd799d5ca5",
    "training/annotations/generated/review_batch_001/REVIEW_BATCH_001.md": "a3dd35786d2d627678bf5f88e5a0c376ad71cf7a94c4e812689727eba9d7034e",
    "training/annotations/generated/review_batch_001/PRODUCT_DECISIONS_001.md": "378395e26758aacd631621ed7ed66dd5c963569a4c83d414496642601290d487",
    "training/annotations/generated/review_batch_001/decisions_draft.jsonl": "88cf474eb2a9d9ac827303f307681738a7eb0b3cdd033f202827d36da5ef62fe",
    "training/annotations/generated/review_batch_001/batch_manifest.json": "47f48ec84c867fc166e9532e5f07a02d353406a1100393fa0fcd187f16319f39",
    "training/annotations/generated/review_batch_002/REVIEW_DECISIONS_002.md": "9c9f4fc6de40171c1bc5528dfa3e04e787df7a2886541821c805c06995e39847",
    "training/annotations/generated/review_batch_002/coverage_expected.json": "e4ed410668c0e666385d79d66bdb38d185cc837eb7a48c49814c8e9b19b55477",
    "training/annotations/generated/review_batch_002/review_batch_002.jsonl": "94b7ebe7bc57c1fef24d41434b43e436c3c26d5b63639087ce1067dfa6e1257c",
    "training/annotations/generated/review_batch_002/generation_recipe.py": "fd0c9f3beb5b08d6381f3f319eb2abc080173652434d27d4c21630de35d0c31c",
    "training/annotations/generated/review_batch_002/IMPORT_VALIDATION_002.json": "6a5b3fdbc51a3043942749b5813345bf7c3a71e85069f0365a672f45d0b761f4",
    "training/annotations/generated/review_batch_002/mining_audit.json": "0960de44322e234ea1750fbc919373d959b76337870c10ebd7e82423f6f70caa",
    "training/annotations/generated/review_batch_002/review_batch_002.xlsx": "b2be1180b5fb2a00ea938a63c2010045a0345bda193f32bf13a3a829f9b84798",
    "training/annotations/generated/review_batch_002/VALIDATION_BATCH_002.json": "bc4e2772a8189d1750f1600dc98c062584c6f38918cae12e414d09a91f311f2b",
    "training/annotations/generated/review_batch_002/REVIEW_BATCH_002.md": "d9a9b461f9f50e5e97164b265c404c23e8210ed5c124853f0b0a286e1748af6c",
    "training/annotations/generated/review_batch_002/manifest.json": "8d1f9d8afb2cd00ff156440a2129c5e69008f74dee6d0417a43c6127b894ff23",
    "training/annotations/generated/review_batch_002/decisions_002.jsonl": "07fb30ed3ea6f83065dc706b03bafbc0db1e0e8df7e0b2e947ecaad485865bf4",
    "training/annotations/generated/review_batch_002/decisions_draft_002.jsonl": "ebe24acb871e56bc7bd5669bd2a3acf1df939efd94e8e094515476eb52805a79",
    "training/annotations/generated/review_batch_002/review_queue.jsonl": "5103eb7c64f49ed55276552d2764942c387359da9ea4eae64fff508286b3a3e6",
    "training/annotations/generated/expansion_001/review_queue.xlsx": "91d0136399c1aca7a379c0cd69bae106c8c8ac26ca28b7ab0562f6d060aaf05b",
    "training/annotations/generated/expansion_001/coverage.json": "721510247fa2cf82f5d8a3a3a7f39678bb12a93e73a8bfb524f6aaf3cd0be8bb",
    "training/annotations/generated/expansion_001/manifest.json": "3ecfae5f669034a52bac98306f4204ba1e3bcfb36414dde67ae4ac2f0746e372",
    "training/annotations/generated/expansion_001/review_queue.jsonl": "880cca2920a68d5e84f7a6f1d43372a19fe46ec110cf41007f2ce050c7907808",
    "training/annotations/generated/review_batch_001/validation_evidence_001/strict_reviewed_dpo_replay.py": "d1c89328c7a87be78e5d537d0e6243e3a66a49bdae05a780a736b233abb122ba",
    "training/annotations/generated/review_batch_001/validation_evidence_001/strict_sft_manifest.json": "08b6f2f097419426c941bbb2867168f6fe4171021566ede790aab91b3592b541",
    "training/annotations/generated/review_batch_001/validation_evidence_001/strict_dpo_manifest.json": "23b23f24a873ea8b1d81b2fdbb49c65c77590df095d251a41fdcfe3d5e2cdf7e",
    "training/annotations/generated/corpora/reviewed_gold_v001/dpo_valid.jsonl": "87b3cb8d28b76406138271635b7f12d01203bedc8c1cf22858b3567585d662cb",
    "training/annotations/generated/corpora/reviewed_gold_v001/sft_valid.jsonl": "1ef55c6f31803c46228877313675771e51ad943c87c5a138821ebe8329e2cbfd",
    "training/annotations/generated/corpora/reviewed_gold_v001/policy_and_scope.json": "2b42e7dfeb526ddb71baa9aebca1498659e49f2befa91b67bfee66cf7e2e495d",
    "training/annotations/generated/corpora/reviewed_gold_v001/sft_train.jsonl": "393d7d6344ea09354870736e673e969ff4cf5681f338666ae9f623bd119c6d27",
    "training/annotations/generated/corpora/reviewed_gold_v001/dpo_train.jsonl": "0ac506eadea2d0aa4e732e8fb7986ec4fef3cc205fcf03744879322c8dd48f62",
    "training/annotations/generated/corpora/reviewed_gold_v001/README.md": "d6b1722433308cb5bf519dc21519e026dce53b0e73e2bad4c26f81ea3d4c15d2",
    "training/annotations/generated/corpora/reviewed_gold_v001/manifest.json": "41c56df444c69f07e68de2564e5294d9f521ad3884456b3d00d89e23c4e9b38e",
    "training/annotations/generated/corpora/reviewed_gold_v001/reviewed_annotations.yaml": "989527b72a446dd20bd1f9e316088df7762bdb3189c648ff928e4889481d4843",
    "training/annotations/generated/corpora/reviewed_gold_v001/coverage_before_after.json": "4ffcef669c36f888cccc018d34e1af2d32deea438473b984c1c7698fe8ff89d9",
    "training/annotations/generated/corpora/reviewed_gold_v001/corpus_manifest.json": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9",
    "training/annotations/generated/corpora/reviewed_gold_v001/validation_report.json": "e23b4640ef1f345db70f97525c0aef37dadabc8a9cc8843568ab7989c1e5fe8d",
    "training/annotations/generated/corpora/reviewed_gold_v001/review_decisions.jsonl": "9b2cde3199641d89cb75836d233cdd7a97ee7f97595ae793599647dd799d5ca5",
    "training/annotations/generated/corpora/reviewed_gold_v002/strict_validation.json": "02c0a88542117b0864e49090547a6071a4cec5003adccbe94d20fad9b3952629",
    "training/annotations/generated/corpora/reviewed_gold_v002/dpo_valid.jsonl": "8420e8df412c442c3618f906b6736c86b066ec44cdfe5e9d161eb11a71961104",
    "training/annotations/generated/corpora/reviewed_gold_v002/sft_valid.jsonl": "94e879b32138244d2e740773f3975d78ffc740d429fbb96f9d65e5991f1097c1",
    "training/annotations/generated/corpora/reviewed_gold_v002/policy_and_scope.json": "0c21c526e38da5f0c70e6b95d36e861f58583aba5ddb76255512a661dd2aba06",
    "training/annotations/generated/corpora/reviewed_gold_v002/generation_recipe.py": "d5788d49473aee431532e55e4ecb9e756faed21591302dd9c2b3ffed235b0475",
    "training/annotations/generated/corpora/reviewed_gold_v002/sft_train.jsonl": "dd6a4e7c238b1100ab8cd6b1cc78e7c5b83e2ac2e5668cab7a68d9258c91793a",
    "training/annotations/generated/corpora/reviewed_gold_v002/dpo_distribution.json": "6b2e63b0b1774e8abe07597f2ce3c622315e123e08bc44285f992035afe94892",
    "training/annotations/generated/corpora/reviewed_gold_v002/lineage_audit.json": "2e4062d8eee7e4b558b8792000f6127c75af374a869735d1832743807d001fed",
    "training/annotations/generated/corpora/reviewed_gold_v002/pair_validation.json": "bb07e3e868f08d8df3ed0ec6c45d8d3c1e55f85ddb91069a1dd24ff4ec4f9b81",
    "training/annotations/generated/corpora/reviewed_gold_v002/dpo_train.jsonl": "135e1f16fac9f6ae8a5bb5553b207b7bf2a7b83975efabcedbfb79cb4bacd018",
    "training/annotations/generated/corpora/reviewed_gold_v002/README.md": "813c9bae27ab718f1bfd196aee3c304a4ec07bf6b899928849a484286c84e4a0",
    "training/annotations/generated/corpora/reviewed_gold_v002/token_validation.json": "5cae786339c41422f9039e9e783bfec2867ea3119e8d74da74cf8f6be999d8f6",
    "training/annotations/generated/corpora/reviewed_gold_v002/manifest.json": "3bce8b6e67b7f5625f8a8a62385ea9c1c45d86add8d9d119cf72cdc8e2633304",
    "training/annotations/generated/corpora/reviewed_gold_v002/reviewed_annotations.yaml": "2fd85499ad6dec494cd3681a9546556b555f135afe9d84ff641dd3b3a9c4a88a",
    "training/annotations/generated/corpora/reviewed_gold_v002/decisions_002.jsonl": "07fb30ed3ea6f83065dc706b03bafbc0db1e0e8df7e0b2e947ecaad485865bf4",
    "training/annotations/generated/corpora/reviewed_gold_v002/coverage_before_after.json": "ba2038e93cb9ffec1d59d7be9dbfe8c4af63c83d67809a129ca95c1af2750ff8",
    "training/annotations/generated/corpora/reviewed_gold_v002/corpus_manifest.json": "b7a07c3a61d73f0dd7d4a88d0a899cf213d9a9d46048f5da5ea1beb531fbc84a",
    "training/annotations/generated/corpora/reviewed_gold_v002/validation_report.json": "09d2734d8919247b4e5e995d0039f267be0e74edda5abeb3797dfd61125cfe0c",
    "training/annotations/generated/corpora/reviewed_gold_v002/review_decisions.jsonl": "730d2a95ef765f72c43f7251d5f36a5e9f0a965df10df44c384487726764b4b0",
    "training/annotations/generated/corpora/reviewed_gold_v002/configs/qwen3_8b_thor_v002_dpo.yaml": "66bcffb57e84eb09e383a2c3e9bc693cdd470ca028239a449f2965e58f4aebe6",
    "training/annotations/generated/corpora/reviewed_gold_v002/configs/qwen3_8b_thor_v002_sft.yaml": "b96d13a0e1d91157dd04568fe8b16646dde32c2711780493d800b1b2649b275b",
    "training/annotations/generated/corpora/reviewed_gold_v002/validation_evidence/dpo_replay/dpo_valid.jsonl": "4f4c6f23f16405fb426c6e82e2028afc750108a179ddbb7faaa74ca29e22af1c",
    "training/annotations/generated/corpora/reviewed_gold_v002/validation_evidence/dpo_replay/dpo_train.jsonl": "9ff3c333e2b5084560476db17d1c13dccbbf64f07215cc203775222f3390672e",
    "training/annotations/generated/corpora/reviewed_gold_v002/validation_evidence/dpo_replay/manifest.json": "cea622089018a5cf74560add6fc8f48a0e79fee2e0b099a533a29dd85adfe615",
    "training/annotations/generated/corpora/reviewed_gold_v002/validation_evidence/sft_replay/sft_valid.jsonl": "61354febbef619c78f7904de6c9f150adcfee252ee33f31e0693679d2300a53f",
    "training/annotations/generated/corpora/reviewed_gold_v002/validation_evidence/sft_replay/sft_train.jsonl": "4944b9e913a2bb96502b2ac3006dec27c96f8253e7b4c7988098d2eb310896da",
    "training/annotations/generated/corpora/reviewed_gold_v002/validation_evidence/sft_replay/manifest.json": "0cbdecd93f5eac9afb512e1d6b176a29379e70b39870ae28a1abf1af976f6ae3",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v001/README.md": "d6b1722433308cb5bf519dc21519e026dce53b0e73e2bad4c26f81ea3d4c15d2",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v001/corpus_manifest.json": "59afe134830827bebac98181cc6a19fd4d789abf5471e2132fc9e7ef889367f9",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v001/manifest.json": "41c56df444c69f07e68de2564e5294d9f521ad3884456b3d00d89e23c4e9b38e",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v001/coverage_before_after.json": "4ffcef669c36f888cccc018d34e1af2d32deea438473b984c1c7698fe8ff89d9",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v001/policy_and_scope.json": "2b42e7dfeb526ddb71baa9aebca1498659e49f2befa91b67bfee66cf7e2e495d",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v001/review_decisions.jsonl": "9b2cde3199641d89cb75836d233cdd7a97ee7f97595ae793599647dd799d5ca5",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v001/reviewed_annotations.yaml": "989527b72a446dd20bd1f9e316088df7762bdb3189c648ff928e4889481d4843",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v001/validation_report.json": "e23b4640ef1f345db70f97525c0aef37dadabc8a9cc8843568ab7989c1e5fe8d",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/README.md": "813c9bae27ab718f1bfd196aee3c304a4ec07bf6b899928849a484286c84e4a0",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/corpus_manifest.json": "b7a07c3a61d73f0dd7d4a88d0a899cf213d9a9d46048f5da5ea1beb531fbc84a",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/manifest.json": "3bce8b6e67b7f5625f8a8a62385ea9c1c45d86add8d9d119cf72cdc8e2633304",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/coverage_before_after.json": "ba2038e93cb9ffec1d59d7be9dbfe8c4af63c83d67809a129ca95c1af2750ff8",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/policy_and_scope.json": "0c21c526e38da5f0c70e6b95d36e861f58583aba5ddb76255512a661dd2aba06",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/review_decisions.jsonl": "730d2a95ef765f72c43f7251d5f36a5e9f0a965df10df44c384487726764b4b0",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/reviewed_annotations.yaml": "2fd85499ad6dec494cd3681a9546556b555f135afe9d84ff641dd3b3a9c4a88a",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/validation_report.json": "09d2734d8919247b4e5e995d0039f267be0e74edda5abeb3797dfd61125cfe0c",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/decisions_002.jsonl": "07fb30ed3ea6f83065dc706b03bafbc0db1e0e8df7e0b2e947ecaad485865bf4",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/dpo_distribution.json": "6b2e63b0b1774e8abe07597f2ce3c622315e123e08bc44285f992035afe94892",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/lineage_audit.json": "2e4062d8eee7e4b558b8792000f6127c75af374a869735d1832743807d001fed",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/pair_validation.json": "bb07e3e868f08d8df3ed0ec6c45d8d3c1e55f85ddb91069a1dd24ff4ec4f9b81",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/strict_validation.json": "02c0a88542117b0864e49090547a6071a4cec5003adccbe94d20fad9b3952629",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/token_validation.json": "5cae786339c41422f9039e9e783bfec2867ea3119e8d74da74cf8f6be999d8f6",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/configs/qwen3_8b_thor_v002_sft.yaml": "b96d13a0e1d91157dd04568fe8b16646dde32c2711780493d800b1b2649b275b",
    "/home/hwkim/assistant_univ/training/records/corpora/reviewed_gold_v002/configs/qwen3_8b_thor_v002_dpo.yaml": "66bcffb57e84eb09e383a2c3e9bc693cdd470ca028239a449f2965e58f4aebe6",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_001/REVIEW_BATCH_001.md": "a3dd35786d2d627678bf5f88e5a0c376ad71cf7a94c4e812689727eba9d7034e",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_001/REVIEW_DECISIONS_001.md": "135694470d816d783c43f6fe34dd36a3ff05c97839884292a9bff00c15c6f430",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_001/PRODUCT_DECISIONS_001.md": "378395e26758aacd631621ed7ed66dd5c963569a4c83d414496642601290d487",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_001/RESOLUTION_001.md": "da3e253263e612072feb8d9b3ed8507287c00d6586f51082b8b80b676b2dfe9f",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_001/decisions.jsonl": "9b2cde3199641d89cb75836d233cdd7a97ee7f97595ae793599647dd799d5ca5",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_001/batch_manifest.json": "47f48ec84c867fc166e9532e5f07a02d353406a1100393fa0fcd187f16319f39",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_001/IMPORT_VALIDATION_001.json": "268b17e11d480ea5e6357fa81e8a6813e7f8b2b91ca0b99180ed50d2612b8f05",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_001/review_batch_001.jsonl": "6a0c1c944548caf67627f6db21555c2ddbc14af3d261533581bfc035ae1b622b",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_002/REVIEW_BATCH_002.md": "d9a9b461f9f50e5e97164b265c404c23e8210ed5c124853f0b0a286e1748af6c",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_002/REVIEW_DECISIONS_002.md": "9c9f4fc6de40171c1bc5528dfa3e04e787df7a2886541821c805c06995e39847",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_002/decisions_002.jsonl": "07fb30ed3ea6f83065dc706b03bafbc0db1e0e8df7e0b2e947ecaad485865bf4",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_002/manifest.json": "8d1f9d8afb2cd00ff156440a2129c5e69008f74dee6d0417a43c6127b894ff23",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_002/mining_audit.json": "0960de44322e234ea1750fbc919373d959b76337870c10ebd7e82423f6f70caa",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_002/coverage_expected.json": "e4ed410668c0e666385d79d66bdb38d185cc837eb7a48c49814c8e9b19b55477",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_002/VALIDATION_BATCH_002.json": "bc4e2772a8189d1750f1600dc98c062584c6f38918cae12e414d09a91f311f2b",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_002/IMPORT_VALIDATION_002.json": "6a5b3fdbc51a3043942749b5813345bf7c3a71e85069f0365a672f45d0b761f4",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_002/review_queue.jsonl": "5103eb7c64f49ed55276552d2764942c387359da9ea4eae64fff508286b3a3e6",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_002/review_batch_002.jsonl": "94b7ebe7bc57c1fef24d41434b43e436c3c26d5b63639087ce1067dfa6e1257c",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_003/REVIEW_BATCH_003.md": "e8d59714384254cc2549d5456dfaf61d7b37b071bdbf93a7d6cea641feac1066",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_003/manifest.json": "e522680b60be076a425fe59deb3e26b523678b2715d778a43cdaf1667836a6a4",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_003/coverage_expected.json": "9856f9511e4b9bbfa5e91c3a118c15fbb439ba860973cf8c0eb9f993fecebbf8",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_003/split_plan.json": "a4c43408704509b35915b77c39b1901431451bf3b84fa1209c7c7207d56698f0",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_003/mining_audit.json": "2dd62b9b236673ff9bd7343932b5c468857bca71b35c27af432bde4aa3eda2b0",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_003/review_queue.jsonl": "830efaad4ba7893146487442c660a22515d31dd7315a932a3dc3837e05a9fe3e",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_003/review_batch_003.jsonl": "d2b9b0e2c600598058e69fa614d4b4611e8255ee9069fba66c43c4d7d07dd05e",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_003/token_validation.json": "7394d8c6b86954ca613da0cd9169d3960e101c53facc957a97a06b258815c134",
    "/home/hwkim/assistant_univ/training/records/reviews/review_batch_003/VALIDATION_BATCH_003.json": "5e2665dd81287357e45e68dab0f17b1f69f045a2859aadad8af49b57334f9b40",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/manifest.json": "aef40e66496ee2efbcce26f893cb7f945ec23f98bdb9aaf5555805f6ccbbf3c7",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/best_sft.json": "54809df13369bb043f3ba5481dd4477e2698ba02c7571f89e9be3318500a1067",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/best_dpo.json": "e426978cfbe8964eff64da4c697633b2d59ab03cadd2e9923bda71d2a309aa83",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/selected_models.json": "b57c7a8eb764604e20bb90408c771efc3aa9d1b352007a8f566fa8bcf9161822",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/resume_evidence.json": "62a9ddbd0a3fc40c920b7f9b197bfb9c33986b08ea0a7589131c5c6f845028df",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/thor_environment.json": "94727b3b76e394c2b26a742c0d949e3ebf7bacf1cd349ab62ee03992a683b115",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/thor_host_environment.json": "b193de297200d92a4b5db3213b2d92abaefe52a759217336d46f6d3baabd3b55",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/thor_sft_tokens.json": "6809948f9aeea5004ebf6ff2cf4f59fefb0fdc5df36adf6f0a1fceb37f2ec0b9",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/thor_dpo_tokens.json": "a86501d8ad74a6d8581f29e29b48a600e739b4ff8c648221e9f25e2055ed3e4e",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/prompt_token_observation.json": "821e1f46fe79361c77f6b72f92ca0fc093571972693e524b0295930650d1e684",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/metrics/comparison_counts.json": "810c08fe7e87f40b509bda7b31d4dc95731afa763b8c2598d4ff98cbf90de577",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/metrics/paired_counts.json": "42bcf914814cbf13ed83677e5e1c4773afc5e38069202aa41eedb6a96210c3de",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/metrics/learning_curves.json": "8fad6d15964bf93bfab7d3a520eab14b2a47dfe03053b43368faa4383630c931",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/metrics/learning_curves.csv": "539becc43564b63c782eb7d6a649ab5c20d3cbcc63e6d3ac14cf954be585a502",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/metrics/telemetry_summary.json": "4ccf8de80c9294e9f2eaaf2fcab310c4d43573f07537f9fc6f309f2e901caaec",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/metrics/dpo_best_preferences.json": "5fe6f2ebdc598d0079551c75d0966eeffb84bbadaf9091589b91fa6a75d8e540",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/metrics/base.json": "cf5534ea4b7a5abe31c1e9374a267a888d2e4f99b9b39cbe86a9b51310b12074",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/metrics/sft_best.json": "c8b1f956ea7f293ab12c933473b12facf59f70417a0e857cca0db039af79493d",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/metrics/dpo_best.json": "641e234df912549d23160e93384baa4c2e546ea06ab3a8591d15976a266624c6",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/metrics/sft_1_profile.json": "1e6f6f3f4e3632ee2572ce34bd098a6f500f268700dd18f5178798f5e9833a43",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/metrics/dpo_3_profile.json": "2d3bb3f7f41fc4b724d0482bc76183d2ada71e8d2172b05c542422fd2e625067",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/configs/sft_1.yaml": "52d354aef81300ca31ac93bc6f9d8e540972c8df7063557bf0d42f808f96f949",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_001/configs/dpo_3.yaml": "1dd47e599418253f601a1fa8cfb1a7cc10ae5f789924bbbf7c47ae3fd7399b53",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/manifest.json": "f407174f1a619b6aa2ed122e328db9ba7b7d91e9e35125d4b6c7f14c16bc4d0c",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/best_sft.json": "5f511b764c27b3c3ac267890f8094dd8d2c88e9bc2d53d7ba3e6be8a8cf36941",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/best_dpo.json": "9b99b6fc1c49d522ceb31a91dcf823ed6c1e6b863d3dcd79bd0aa1364528b251",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/REPORT.md": "7c890d6a391d290ded62bc5585e7596db18e904541297a9e2e48829931963f84",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/RESULTS.json": "33782f8e18d72bde30812d2de0e40bcec2c91b0282810da5e3f867fd2e3dbbd9",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/VALIDATION.json": "457c3d97cc1608aa6c38858bd6c60b5632b5e579a113a3d0dabeb4d6ac7b814d",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/artifact_manifest.json": "1364f4af53c8c63bcc6debc393c6055e86519c4b6a21fa751171548852545c99",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/environment.json": "dd7a87746874504ae88e87abc0109c5c0a53aacd627b4a29bb8c71a883090aa6",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/host_environment.json": "0567c3b3b749646db47dcc99946a453d931b7bba3ecf123bd9ff9454860c3599",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/dpo_initialization.json": "cb5279ebdd8422f110379084a2e31512d687350a3121f40b7e79ff4b6598b7ce",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/configs/sft_template.yaml": "627ec0c6c530dc8160d2db6bd5e500300b6aeaaca9026278aa7187964de9a64d",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/configs/dpo_template.yaml": "4f66536ce8cfdf78c21cc8681123d5120b0d956ce3df6806eb1f7bbad5917406",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/configs/dpo_resolved.yaml": "e53c7531dda0cb23b8041104de334da2133b105c189b0369a8d6c6118cafd169",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/metrics/base.json": "badf0f88d4584e241f6734b14e76fec7e8f72c734c8bcb7daec535b21ca76b71",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/metrics/sft_best.json": "92841ed7b97dd9f3b0a2cbb67b32b7c1fd4edd567219a9e0f25eb16cc7e95597",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/metrics/dpo_best.json": "c3282973d06670bcc89960027ac4fca7aec9a5154af1f451667c413ad0e56d26",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/metrics/dpo_best_preferences.json": "1fd053540aa7ad70e58bd2b92220ddc36305d3d2deec08e89117002b46d47e45",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/metrics/dpo_last_preferences.json": "cd6d0907f78e68785541701031e59096c36b6bd0c5fd007add761af844c10c9e",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/metrics/sft_profile.json": "b621cc189fce3e4904b3f66246965e6ac9a03595aa70dfb33a8f4f28ed7ef585",
    "/home/hwkim/assistant_univ/training/records/pilots/thor_pilot_002/metrics/dpo_profile.json": "99c1006147ad25558ba040ab5dcc80884e7d147f008d86f0dccfd4d2a6322f8a",
    "geoflow/grounding.py": "4d55d062e584d28822ebef57b1db2765f23e52372b13f48ba82da5d98ec821bb",
    "geoflow/composer.py": "09a0f440b7115709eb7584ee5649b83edc6532a64b988e8637c0a7ad63472ebe",
    "geoflow/validator.py": "9629045fb0bee2528379b0bbd2f2e72455ff810d09a39760117ed0032a632824",
    "geoflow/compiler.py": "3c379f75fca84a87f6d9728e1689d2d3ffcf509973f0a0661f9474e1a721b549",
    "geoflow/operator_mapping.py": "b40419493a99765407d6d1480746175abb441a1176f27f7659120c50b9238ee3",
    "geoflow/operator_registry.py": "81e0132ae22cb457d9e81b1fcef8e4996aebf22a738f37ae2345cb0c9bd17fb9",
    "geoflow/factors.py": "f524b30ad51ab7c564db36c4ac7b766ce6ad96405cb79eee2ed25d1ec524c322",
    "geoflow/types.py": "689760613b09d1737dbe435361dc42c13da779fe43bc5ea58178c858796b074b",
    "geoflow/aggregation.py": "f75ba44df0a1c9504dc2efc6a4953cf0d94693ecd7a905f6e2f4256d48d5e866",
    "geoflow/measures.py": "c67ef1155a68edb6ce3a59290a35ce0be4131da1a4a6d950cb8f3b8867615d33",
    "geoflow/providers.py": "84f57e3afe37de5068e650627c9a211f605567426d9b3e2f077b16922a511706",
    "geoflow/tims_contract.py": "d5f304be70c09dbe5159ddcc828918c6206c367850046a3d5fd7774cdd11bdcb",
    "geoflow/analysis_ops.py": "4de0518b28392ceca9aa3483d9d0044c29ecb942c2dc2f30ac55dc31c47f382d",
    "prompts/geoflow_planner.yaml": "9d4bd132e267ecab8d04db5e23c0f59220848eae67fdc720e1c7ec3f35c4a49a",
    "schemas/tims.yaml": "8065cfffd951b578cb0210114211f7c22f9972cfa014d9ab17e8d00cb218b764",
    "schemas/_common.yaml": "b3479ffbd07ae1749ddacaf39332b503ca57abd2ddcf84fbb7ba497174306397",
    "training/configs/qwen_sft.yaml": "997afd5d4e55be73ff44dffe17d00780449251d363bf57b17c5c2ffaf8f503d7",
    "training/configs/qwen3_8b_thor_smoke_sft.yaml": "82845949839a014490acbf52effdfe9fcf14a7dfc373b9836d66afb79bddc18c",
    "training/configs/qwen_dpo.yaml": "b9bc73ec041301b2ef9ea4ca025894544b6b32686321c0fbf5a3265fe863e070",
    "training/configs/qwen3_8b_thor_sft.yaml": "2761b87e4a96d42eaf2951115bbb4646c76ff33a23d9e5e21d2578e65d277c61",
    "training/configs/qwen3_8b_thor_dpo.yaml": "003598f897771102fff0b4ffd6b837de912eec3fde236364083276a9a7723791",
    "training/configs/qwen3_8b_thor_smoke_dpo.yaml": "081ad0dc4d73376fcb316a3d9f60923793984fdf1483979a4268e305e80eceb8"
  }
}
```

## 검증 명령

```bash
python -m unittest tests.test_training_review_decisions_003 tests.test_training_annotations tests.test_training_review_batch tests.test_training_data -q
git diff --check
```

Model/tokenizer/GPU 초기화 없이 실행 가능한 검토 artifact tests다. 테스트는 semantic 정답을 자동 승인하지 않으며, 수동으로 지정한 판단 근거·source hashes·dependency·보호 경계·엄격 chosen pipeline의 일관성을 확인한다.


## 이번 검증 결과

관련 unit tests75개(신규 draft checks12개 포함)와 원본 batch artifact checks15개가 모두 통과했다. Frozen source/corpus/config/snapshot hashes199개를 재확인했고, 원본 artifact suite도 기존 manifest 불변성을 검사했다. 모든 원본 queue row는 pending이며 두 draft mirror는 byte-identical하다. GPU/model inference/import 및 token config 변경은 없었다. 이 검증은 최종 semantic approval를 대신하지 않는다.
