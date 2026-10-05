# Thor bounded pilot 002

Frozen commit: `65e9ea2ec98f8cec289cbb753ce543dee3efdd92`; seed42; unchanged prompt/model revision. Fresh Base SFT, fixed initial-SFT shared reference DPO.

## Planner quality: v002 validation (5 questions)

| Metric | Base | Best SFT | Best SFT+DPO |
|---|---:|---:|---:|
| JSON | 5/5 | 5/5 | 5/5 |
| Contract | 1/5 | 2/5 | 2/5 |
| Grounding | 0/5 | 0/5 | 0/5 |
| Factor | 1/5 | 1/5 | 1/5 |
| Compose | 1/5 | 1/5 | 1/5 |
| Validate | 1/5 | 1/5 | 1/5 |
| Repair | 0/5 | 0/5 | 0/5 |
| Concept | 3/12 | 6/12 | 6/12 |
| Subtype | 3/12 | 6/12 | 6/12 |
| Role | 2/12 | 5/12 | 5/12 |
| Execution | N/A (semantic-only) | N/A (semantic-only) | N/A (semantic-only) |

## Common v001 development (20 questions)

| Metric | Base | Best SFT | Best SFT+DPO |
|---|---:|---:|---:|
| JSON | 20/20 | 20/20 | 20/20 |
| Contract | 11/20 | 13/20 | 12/20 |
| Grounding | 7/20 | 9/20 | 8/20 |
| Factor | 8/20 | 10/20 | 9/20 |
| Compose | 10/20 | 13/20 | 12/20 |
| Validate | 10/20 | 13/20 | 12/20 |
| Repair | 1/20 | 0/20 | 0/20 |
| Concept | 23/43 | 28/43 | 26/43 |
| Subtype | 23/43 | 28/43 | 26/43 |
| Role | 23/43 | 28/43 | 26/43 |
| Execution | N/A (semantic-only) | N/A (semantic-only) | N/A (semantic-only) |

Concept/subtype/role counts are matched gold labels, not questions. Execution is deliberately N/A. No provider gap is classified as semantic unsupported.

## Step observations

### SFT

| Step | Grounding | Contract | Factor | Validation loss |
|---|---:|---:|---:|---:|
| 2 | 0/5 | 2/5 | 1/5 | 0.9948413968086243 |
| 6 | 0/5 | 1/5 | 0/5 | 0.6090123057365417 |
| 12 | 0/5 | 2/5 | 1/5 | 0.3559556007385254 |

### DPO

| Step | Grounding | Contract | Factor | Validation loss |
|---|---:|---:|---:|---:|
| 2 | 0/5 | 2/5 | 1/5 | 0.6727752685546875 |
| 4 | 0/5 | 2/5 | 1/5 | 0.6949270963668823 |
| 8 | 0/5 | 1/5 | 0/5 | 0.6929166913032532 |

Selected sft: step 2, `/home/hwkim/assistant_univ/training/experiments/thor_pilot_002/checkpoints/sft/checkpoint-2`.
Frozen generation selection criterion: ['grounding_exact_match', 'concept_accuracy', 'subtype_accuracy', 'role_accuracy', 'factor_exact_match', 'planner_contract_pass_rate', 'composition_success_rate', 'validation_pass_rate', 'json_parse_rate', 'earlier_step']. No train loss or external scores were used.

Selected dpo: step 2, `/home/hwkim/assistant_univ/training/experiments/thor_pilot_002/checkpoints/dpo/checkpoint-2/policy`.
Frozen generation selection criterion: ['grounding_exact_match', 'concept_accuracy', 'subtype_accuracy', 'role_accuracy', 'factor_exact_match', 'planner_contract_pass_rate', 'composition_success_rate', 'validation_pass_rate', 'json_parse_rate', 'earlier_step']. No train loss or external scores were used.

## Subtype and preference details

See `RESULTS.json` for fare/speed/rpm/OD/aggregation/source-role/factor cohort metrics, semantic/constraint/negative-type preferences, v001 common-question comparison and profiler phases.

## Exact-match transitions (non-training questions)

- base_to_sft_improvements: 2 (w36_p0, w38_p0)
- sft_to_dpo_improvements: 0 (none)
- sft_to_dpo_regressions: 1 (w36_p0)
- all_fail: 16 (ann-9d8392a4f8ca9ff8cfc2, ann-0e4edbda1cb1bec194c1, ann-0d51b49a28500bb47b0d, ann-2d254560f2214204db4b, ann-4cafcbdd3b76a67f42db, w02_p0, w03_p0, w05_p0, w06_p0, w09_p0, w12_p0, w22_p0, w35_p0, w37_p0, w39_p0, w40_p0)

### base_to_sft_improvements: w36_p0
지난달 하차가 가장 적은 시군구 2곳은?
Gold:
```json
{
  "concepts": [
    {
      "id": "trip",
      "concept": "EVENT",
      "subtype": "trip",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "count",
      "concept": "AMOUNT",
      "subtype": "trip_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "last_month",
    "dimension": "sigungu",
    "dimension_target": "dropoff",
    "order": "bottom",
    "limit": 2
  }
}
```
base (INVALID_FACTOR_COMBINATION):
```json
{
  "concepts": [
    {
      "id": "trip",
      "concept": "EVENT",
      "subtype": "trip",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "trip_count",
      "concept": "AMOUNT",
      "subtype": "trip_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "bucket": "month",
    "dimension": "sigungu",
    "dimension_target": "dropoff",
    "order": "bottom",
    "limit": 2
  }
}
```
sft_best (OK):
```json
{
  "concepts": [
    {
      "id": "trip",
      "concept": "EVENT",
      "subtype": "trip",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "trip_count",
      "concept": "AMOUNT",
      "subtype": "trip_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "last_month",
    "dimension": "sigungu",
    "dimension_target": "dropoff",
    "order": "bottom",
    "limit": 2
  }
}
```
dpo_best (MISSING_CONCEPT_VALUE):
```json
{
  "concepts": [
    {
      "id": "destination",
      "text": "하차",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "SUBCOND",
      "source": "user"
    },
    {
      "id": "trip",
      "concept": "EVENT",
      "subtype": "trip",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "trip_count",
      "text": "실차 구간 건수",
      "concept": "AMOUNT",
      "subtype": "trip_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "last_month",
    "dimension": "sigungu",
    "dimension_target": "dropoff",
    "order": "bottom",
    "limit": 2
  }
}
```

### base_to_sft_improvements: w38_p0
이번 주 동대구역 주변 택시 통행량은?
Gold:
```json
{
  "concepts": [
    {
      "id": "place",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "SUBCOND",
      "source": "user",
      "value": {
        "name": "동대구역",
        "region": ""
      }
    },
    {
      "id": "passage",
      "concept": "EVENT",
      "subtype": "passage",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "count",
      "concept": "AMOUNT",
      "subtype": "passage_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "this_week",
    "vicinity": true
  }
}
```
base (INVALID_FACTOR):
```json
{
  "concepts": [
    {
      "id": "place_1",
      "text": "동대구역",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "SUBCOND",
      "source": "user",
      "value": {"name": "동대구역", "region": ""}
    },
    {
      "id": "passage",
      "concept": "EVENT",
      "subtype": "passage",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "passage_count",
      "text": "통행량",
      "concept": "AMOUNT",
      "subtype": "passage_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "2023361",
    "vicinity": true
  }
}
```
sft_best (OK):
```json
{
  "concepts": [
    {
      "id": "place_1",
      "text": "동대구역",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "SUBCOND",
      "source": "user",
      "value": {"name": "동대구역", "region": ""}
    },
    {
      "id": "passage",
      "concept": "EVENT",
      "subtype": "passage",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "passage_count",
      "text": "통행량",
      "concept": "AMOUNT",
      "subtype": "passage_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "this_week",
    "vicinity": true
  }
}
```
dpo_best (OK):
```json
{
  "concepts": [
    {
      "id": "place_1",
      "text": "동대구역",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "SUBCOND",
      "source": "user",
      "value": {"name": "동대구역", "region": ""}
    },
    {
      "id": "passage",
      "concept": "EVENT",
      "subtype": "passage",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "passage_count",
      "text": "통행량",
      "concept": "AMOUNT",
      "subtype": "passage_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "this_week",
    "vicinity": true
  }
}
```

### sft_to_dpo_regressions: w36_p0
지난달 하차가 가장 적은 시군구 2곳은?
Gold:
```json
{
  "concepts": [
    {
      "id": "trip",
      "concept": "EVENT",
      "subtype": "trip",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "count",
      "concept": "AMOUNT",
      "subtype": "trip_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "last_month",
    "dimension": "sigungu",
    "dimension_target": "dropoff",
    "order": "bottom",
    "limit": 2
  }
}
```
base (INVALID_FACTOR_COMBINATION):
```json
{
  "concepts": [
    {
      "id": "trip",
      "concept": "EVENT",
      "subtype": "trip",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "trip_count",
      "concept": "AMOUNT",
      "subtype": "trip_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "bucket": "month",
    "dimension": "sigungu",
    "dimension_target": "dropoff",
    "order": "bottom",
    "limit": 2
  }
}
```
sft_best (OK):
```json
{
  "concepts": [
    {
      "id": "trip",
      "concept": "EVENT",
      "subtype": "trip",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "trip_count",
      "concept": "AMOUNT",
      "subtype": "trip_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "last_month",
    "dimension": "sigungu",
    "dimension_target": "dropoff",
    "order": "bottom",
    "limit": 2
  }
}
```
dpo_best (MISSING_CONCEPT_VALUE):
```json
{
  "concepts": [
    {
      "id": "destination",
      "text": "하차",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "SUBCOND",
      "source": "user"
    },
    {
      "id": "trip",
      "concept": "EVENT",
      "subtype": "trip",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "trip_count",
      "text": "실차 구간 건수",
      "concept": "AMOUNT",
      "subtype": "trip_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "last_month",
    "dimension": "sigungu",
    "dimension_target": "dropoff",
    "order": "bottom",
    "limit": 2
  }
}
```

### all_fail: ann-9d8392a4f8ca9ff8cfc2
2026년 상반기 중구 개인택시 운행일수 합계가 가장 많았던 달은?
Gold:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "operating_days"
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
      "text": "중구",
      "value": {
        "name": "중구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "sum",
    "answer": "bucket",
    "bucket": "month",
    "date": "20260101-20260630",
    "rollup": "max",
    "taxi_type": "private"
  }
}
```
base (OK):
```json
{
  "concepts": [
    {
      "id": "operation",
      "concept": "EVENT",
      "subtype": "operation",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "operating_days",
      "concept": "AMOUNT",
      "subtype": "operating_days",
      "role": "MEASURE",
      "source": "implicit"
    },
    {
      "id": "taxi_type",
      "concept": "OBJECT",
      "subtype": "private",
      "role": "COND",
      "source": "user"
    },
    {
      "id": "location",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "COND",
      "source": "user",
      "value": {"name": "중구", "region": ""}
    }
  ],
  "factors": {
    "date": "20260101-20260630",
    "bucket": "month",
    "aggregation": "sum",
    "rollup": "max",
    "answer": "bucket"
  }
}
```
sft_best (OK):
```json
{
  "concepts": [
    {
      "id": "operation",
      "concept": "EVENT",
      "subtype": "operation",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "operating_days",
      "concept": "AMOUNT",
      "subtype": "operating_days",
      "role": "MEASURE",
      "source": "implicit"
    },
    {
      "id": "taxi_type",
      "concept": "OBJECT",
      "subtype": "private",
      "role": "COND",
      "source": "user"
    },
    {
      "id": "location",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "COND",
      "source": "user",
      "value": {"name": "중구", "region": ""}
    }
  ],
  "factors": {
    "date": "20260101-20260630",
    "bucket": "month",
    "aggregation": "sum",
    "rollup": "max",
    "answer": "bucket"
  }
}
```
dpo_best (OK):
```json
{
  "concepts": [
    {
      "id": "operation",
      "concept": "EVENT",
      "subtype": "operation",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "operating_days",
      "concept": "AMOUNT",
      "subtype": "operating_days",
      "role": "MEASURE",
      "source": "implicit"
    },
    {
      "id": "taxi_type",
      "concept": "OBJECT",
      "subtype": "private",
      "role": "COND",
      "source": "user"
    },
    {
      "id": "location",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "COND",
      "source": "user",
      "value": {"name": "중구", "region": ""}
    }
  ],
  "factors": {
    "date": "20260101-20260630",
    "bucket": "month",
    "aggregation": "sum",
    "rollup": "max",
    "answer": "bucket"
  }
}
```

### all_fail: ann-0e4edbda1cb1bec194c1
2026년 9월 읍면동 승차지별 실차 구간 건수가 적은 4개 그룹은?
Gold:
```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260901-20260930",
    "dimension": "emd",
    "dimension_target": "pickup",
    "limit": 4,
    "order": "bottom"
  }
}
```
base (INVALID_FACTOR):
```json
{
  "concepts": [
    {
      "id": "pickup",
      "text": "읍면동",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "SUBCOND",
      "source": "user",
      "value": {"name": "읍면동", "region": ""}
    },
    {
      "id": "trip",
      "concept": "EVENT",
      "subtype": "trip",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "trip_count",
      "text": "실차 구간 건수",
      "concept": "AMOUNT",
      "subtype": "trip_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "202609",
    "dimension": "emd",
    "dimension_target": "pickup",
    "order": "bottom",
    "limit": 4
  }
}
```
sft_best (INVALID_FACTOR):
```json
{
  "concepts": [
    {
      "id": "pickup",
      "text": "읍면동",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "SUBCOND",
      "source": "user",
      "value": {"name": "읍면동", "region": ""}
    },
    {
      "id": "trip",
      "concept": "EVENT",
      "subtype": "trip",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "trip_count",
      "text": "실차 구간 건수",
      "concept": "AMOUNT",
      "subtype": "trip_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "202609",
    "dimension": "emd",
    "dimension_target": "pickup",
    "order": "bottom",
    "limit": 4
  }
}
```
dpo_best (INVALID_FACTOR):
```json
{
  "concepts": [
    {
      "id": "pickup",
      "text": "읍면동",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "SUBCOND",
      "source": "user",
      "value": {"name": "읍면동", "region": ""}
    },
    {
      "id": "trip",
      "concept": "EVENT",
      "subtype": "trip",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "trip_count",
      "text": "실차 구간 건수",
      "concept": "AMOUNT",
      "subtype": "trip_count",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "202609",
    "dimension": "emd",
    "dimension_target": "pickup",
    "order": "bottom",
    "limit": 4
  }
}
```

### new_fare: ann-a27c59659681a481ac2c
2026년 9월 가람구 소속 택시의 요금을 주마다 합산한 뒤, 주별 합계 중 가장 작은 값은?
Gold:
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
base (UNGROUNDED_SCOPE):
```json
{
  "concepts": [
    {
      "id": "location_1",
      "text": "가람구",
      "concept": "LOCATION",
      "subtype": "scope",
      "role": "COND",
      "source": "user",
      "value": "scope:sido:1234"
    },
    {
      "id": "operation",
      "concept": "EVENT",
      "subtype": "operation",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "fare",
      "text": "요금",
      "concept": "AMOUNT",
      "subtype": "fare",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "bucket": "month",
    "aggregation": "sum",
    "rollup": "min",
    "answer": "value"
  }
}
```
sft_best (UNGROUNDED_SCOPE):
```json
{
  "concepts": [
    {
      "id": "location_1",
      "text": "가람구",
      "concept": "LOCATION",
      "subtype": "scope",
      "role": "COND",
      "source": "user",
      "value": "scope:sido:1234"
    },
    {
      "id": "operation",
      "concept": "EVENT",
      "subtype": "operation",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "fare",
      "text": "요금",
      "concept": "AMOUNT",
      "subtype": "fare",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "bucket": "month",
    "aggregation": "sum",
    "rollup": "min",
    "answer": "value"
  }
}
```
dpo_best (UNGROUNDED_SCOPE):
```json
{
  "concepts": [
    {
      "id": "location_1",
      "text": "가람구",
      "concept": "LOCATION",
      "subtype": "scope",
      "role": "COND",
      "source": "user",
      "value": "scope:sido:1234"
    },
    {
      "id": "operation",
      "concept": "EVENT",
      "subtype": "operation",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "fare",
      "concept": "AMOUNT",
      "subtype": "fare",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "date": "20260901-20261231",
    "bucket": "month",
    "aggregation": "sum",
    "rollup": "min",
    "answer": "value"
  }
}
```

### new_speed: ann-914c48dad91bc9a62ab4
2026년 9월 가람구에서 기록된 도로 통행 속도의 주별 최댓값들 중 가장 작은 값은?
Gold:
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
base (UNUSED_CONCEPT):
```json
{
  "concepts": [
    {
      "id": "date", "text": "2026년 9월",
      "concept": "EVENT", "subtype": "passage", "role": "COND",
      "source": "user",
      "value": {"date": "20260901-20260930"}
    },
    {
      "id": "location", "text": "가람구",
      "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
      "source": "user",
      "value": {"name": "가람구", "region": ""}
    },
    {
      "id": "passage", "text": "도로 통행 속도",
      "concept": "EVENT", "subtype": "passage", "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "speed", "text": "도로 통행 속도",
      "concept": "AMOUNT", "subtype": "speed", "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "bucket": "week",
    "aggregation": "max",
    "rollup": "min"
  }
}
```
sft_best (UNUSED_CONCEPT):
```json
{
  "concepts": [
    {
      "id": "date", "text": "2026년 9월",
      "concept": "EVENT", "subtype": "passage", "role": "COND",
      "source": "user",
      "value": {"date": "20260901-20260930"}
    },
    {
      "id": "location", "text": "가람구",
      "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
      "source": "user",
      "value": {"name": "가람구", "region": ""}
    },
    {
      "id": "passage", "text": "도로 통행 속도",
      "concept": "EVENT", "subtype": "passage", "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "speed", "text": "도로 통행 속도",
      "concept": "AMOUNT", "subtype": "speed", "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "bucket": "week",
    "aggregation": "max",
    "rollup": "min"
  }
}
```
dpo_best (INVALID_CONCEPT):
```json
{
  "concepts": [
    {
      "id": "date", "text": "2026년 9월",
      "concept": "TIME", "subtype": "date", "role": "COND",
      "source": "user",
      "value": "202609"
    },
    {
      "id": "place_1", "text": "가람구",
      "concept": "LOCATION", "subtype": "place", "role": "SUBCOND",
      "source": "user",
      "value": {"name": "가람구", "region": ""}
    },
    {
      "id": "passage",
      "concept": "EVENT", "subtype": "passage", "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "speed", "text": "도로 통행 속도",
      "concept": "AMOUNT", "subtype": "speed", "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "bucket": "week",
    "aggregation": "max",
    "rollup": "min",
    "answer": "value"
  }
}
```

### new_rpm: ann-4cafcbdd3b76a67f42db
2026년 9월 15일 가람구에서 관측된 도로 통행의 엔진 회전수 최솟값은?
Gold:
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
      "text": "가람구",
      "value": {
        "name": "가람구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "min",
    "date": "20260915"
  }
}
```
base (INVALID_CONCEPT):
```json
{
  "concepts": [
    {
      "id": "date_1",
      "text": "2026년 9월 15일",
      "concept": "DATE",
      "subtype": "",
      "role": "COND",
      "source": "user",
      "value": "20260915"
    },
    {
      "id": "place_1",
      "text": "가람구",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "SUBCOND",
      "source": "user",
      "value": {"name": "가람구", "region": ""}
    },
    {
      "id": "passage",
      "concept": "EVENT",
      "subtype": "passage",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "rpm",
      "text": "엔진 회전수",
      "concept": "AMOUNT",
      "subtype": "rpm",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "aggregation": "min"
  }
}
```
sft_best (UNUSED_CONCEPT):
```json
{
  "concepts": [
    {
      "id": "date_1",
      "text": "2026년 9월 15일",
      "concept": "EVENT",
      "subtype": "passage",
      "role": "COND",
      "source": "user",
      "value": "20260915"
    },
    {
      "id": "location_1",
      "text": "가람구",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "SUBCOND",
      "source": "user",
      "value": {"name": "가람구", "region": ""}
    },
    {
      "id": "passage",
      "concept": "EVENT",
      "subtype": "passage",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "rpm",
      "text": "엔진 회전수",
      "concept": "AMOUNT",
      "subtype": "rpm",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "aggregation": "min"
  }
}
```
dpo_best (UNUSED_CONCEPT):
```json
{
  "concepts": [
    {
      "id": "date_1",
      "text": "2026년 9월 15일",
      "concept": "EVENT",
      "subtype": "passage",
      "role": "COND",
      "source": "user",
      "value": "20260915"
    },
    {
      "id": "location_1",
      "text": "가람구",
      "concept": "LOCATION",
      "subtype": "place",
      "role": "SUBCOND",
      "source": "user",
      "value": {"name": "가람구", "region": ""}
    },
    {
      "id": "passage",
      "concept": "EVENT",
      "subtype": "passage",
      "role": "SUPPORT",
      "source": "implicit"
    },
    {
      "id": "rpm",
      "text": "엔진 회전수",
      "concept": "AMOUNT",
      "subtype": "rpm",
      "role": "MEASURE",
      "source": "implicit"
    }
  ],
  "factors": {
    "aggregation": "min"
  }
}
```

## Limits and next decision

- 5 validation gold; RPM 1 validation item and no RPM SFT train item
- DPO valid semantic 3 all old OD; constraint 1 RPM; new semantic categories have no validation pairs
- No unsupported SFT gold; passage_count/vacant_ratio zero
- Semantic-only; no TIMS execution or synthetic execution certification
- Common external corpus is historical development evidence, not final benchmark
- Validation guided checkpoint selection; no unseen test claim

## v001 comparison on identical development questions

| Model | v001 exact | v002 exact |
|---|---:|---:|
| base | 7/20 | 7/20 |
| sft_best | 8/20 | 9/20 |
| dpo_best | 8/20 | 8/20 |

v001 validation had3 items; v002 has5 and different families. Those validation scores are not comparable. Even common-development changes of one question are weak evidence.

## DPO preference quality

| Checkpoint / split | Semantic correct | Semantic margin | Constraint correct | Constraint margin |
|---|---:|---:|---:|---:|
| dpo_best / train | 2/8 | -0.07062 | 7/8 | 0.18380 |
| dpo_best / valid | 3/3 | 0.03652 | 1/1 | 0.05527 |
| dpo_last / train | 6/8 | 0.06368 | 8/8 | 0.28560 |
| dpo_last / valid | 3/3 | 0.03956 | 0/1 | -0.11246 |

Preference margins use the frozen initial SFT reference and TRL beta0.1. Reference hashes were verified after training and per-pair replay. Preference success is not generation correctness.

## Overfitting / generalization observations

SFT generation train exact: best1/12, last3/12; validation remains0/5. Validation teacher-forced loss falls from0.995(step2) to0.356(step12), without exact-match improvement. This shows a training-fit/generalization gap, not proven complete memorization.
SFT step6 compose/validate0/5; steps2 and12 recover1/5. DPO step8 compose/validate0/5 vs selected step2 1/5. Later checkpoints are unstable; the bounded horizon does not identify a definitive overfit onset.
No new SFT→DPO exact improvement on the non-training cohort; one exact regression.

## Thor performance

| Stage | Optimizer steps | sec/step | Policy tokens/s | CUDA peak allocated GiB | CUDA peak reserved GiB | Min system available GiB |
|---|---:|---:|---:|---:|---:|---:|
| sft | 12 | 12.59 | 545.9 | 29.48 | 44.73 | 71.25 |
| dpo | 8 | 48.49 | 283.4 | 32.15 | 34.89 | 68.86 |

Whole-run GPU temperature range: 42.8–79.4C. SFT step timing after warmup stays about12.5s; DPO about48.4s. No clear step-time deterioration was observed; throttle counters were not available. No power/clock settings changed.
DPO policy token throughput counts chosen+rejected including prompt and excludes reference tokens; this is not output-generation throughput.
Training jobs including evaluation/save took274.5s(SFT) and674.4s(DPO). Repeated generation evaluations and per-pair reference analysis dominate experiment wall time.

## Recommendation: C — expand reviewed annotations before further training

There is a small SFT improvement on historical development questions, but no v002 validation exact improvement and no new fare/speed/rpm gold solved by the selected models. DPO does not improve generation and regresses one question. The current corpus is insufficient to conclude an improved semantic grounding model.
Priority1: temporal factor vs concept and source/role/value contrasts across diverse questions; OD dimension/dimension_target and stage definitions. Priority2: multiple disjoint reviewed fare/speed/rpm families in train AND validation; actual train-origin semantic hard negatives. Priority3: passage_count/vacant_ratio and supported/unsupported boundaries. Keep protected diagnostics and evaluation families out of training.
Do not expand synthetic negatives solely to increase pair count; separately cover semantic and constraint types in validation. Keep the corpus, contract, production prompt and deterministic runtime unchanged in this experiment.
