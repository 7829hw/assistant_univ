# quality_gate_v1

2026-10-14. 결정 75·76. 규칙은 `quality_gate_v1.py`로 commit `0c42288`에 고정했고, 그 뒤 기존 trace에 **한 번** replay했다(`quality_gate_v1_replay.json`). replay 결과를 보고 규칙을 고치지 않았다. 27B 결과를 본 뒤에도 고치지 않는다.

## 1. 성격

- 자동 승인기가 아니다. 사람이 먼저 볼 위험 trace를 위로 올리는 risk flag이며, 문항 안 후보의 ranking에 쓴다.
- 최종 trace는 문항당 1개를 사람이 읽는다. top 1이 거부되면 다른 표본으로 바꾸지 않는다.
- 27B 대상 31문항 선정에는 쓰지 않는다.

## 2. 설계 원칙(high precision)

- 문장 근거 flag는 thinking의 결론 구간(마지막 30%)에서만 찾는다. 중간에 말했다 고친 오판은 잡지 않는다.
- 구조 flag는 trace 자신의 최종 응답 JSON을 본다.
- 묶음 단위어 등장만으로는 flag하지 않는다. concept·place로 만든다는 명시적 문장이나 실제 JSON 구조가 있어야 한다.
- dimension vocabulary는 ontology(`geoflow.factors.FACTOR_SPECS["dimension"].values` = h3·sido·sigungu·emd·dayofweek)에서 읽는다.

## 3. flag

| flag | 구조 조건(응답 JSON) | 문장 조건(결론 구간) |
|---|---|---|
| GROUPING_UNIT_AS_CONCEPT | concept subtype이 dimension 값 또는 "dimension" | "<단위> … as a concept", "subtype <단위>" |
| GROUPING_UNIT_AS_PLACE | place의 text·value.name이 묶음 단위어 자체 | "<단위> … as a place/location/SUBCOND" |
| HALLUCINATED_SCHEMA_RULE | answer bucket인데 bucket 없음 | "answer is bucket because" |
| UNRETRACTED_WRONG_AGGREGATION | – | 마지막 "aggregation is <값>" 뒤에 철회 표현이 없고 응답 aggregation과 다름 |
| OD_ROLE_DIM_TARGET_CONFUSION | dimension이 pickup·dropoff·both, dimension 없이 dimension_target, place·scope 아닌 concept의 od_role | – |
| CONCLUDED_UNSUPPORTED | – | unsupported 결론 문장 + 응답은 unsupported 아님 |
| REASONING_FINAL_CONFLICT | – | thinking 마지막 JSON 초안의 factors ≠ 응답 factors |

**ranking**(작을수록 앞):

1. flag 수
2. thinking 길이
3. "Wait"·"Hmm" 수
4. greedy 먼저, 그다음 sample index

길이는 hard reject가 아니라 동률 처리에만 쓴다.

## 4. 기존 trace replay(사람 판정 기준)

대상: R70 선택 trace 91(승인 70·거부 21), M2 16(승인 10·거부 6), M3 4(승인 3·거부 1). 합 승인 83·거부 28.

| | 승인 83 | 거부 28 |
|---|---:|---:|
| flag 1개 이상 | 8 (9.6%) | 19 (67.9%) |

- flag가 걸린 trace 중 실제 거부 비율(precision)은 0.70이다.
- p0_sft_003_recovery의 자동 tier는 승인 10 중 SELF_CORRECTED 9, 거부 6 중 CLEAN_DIRECT 3으로 사실상 구분을 못 했다. 그보다 크게 낫다.

| flag | 승인에 걸림 | 거부에 걸림 | precision |
|---|---:|---:|---:|
| GROUPING_UNIT_AS_CONCEPT | 0 | 6 | 1.00 |
| GROUPING_UNIT_AS_PLACE | 4 | 6 | 0.60 |
| HALLUCINATED_SCHEMA_RULE | 1 | 4 | 0.80 |
| UNRETRACTED_WRONG_AGGREGATION | 3 | 4 | 0.57 |
| OD_ROLE_DIM_TARGET_CONFUSION | 0 | 1 | 1.00 |
| CONCLUDED_UNSUPPORTED | 0 | 2 | 1.00 |
| REASONING_FINAL_CONFLICT | 0 | 0 | – |

세트별 flag 비율:

| | 승인 | 거부 |
|---|---:|---:|
| R70 | 5/70 | 13/21 |
| M2 | 3/10 | 5/6 |
| M3 | 0/3 | 1/1 |

거부 이유별 탐지:

| 사람의 거부 이유 | 탐지 |
|---|---|
| INVALID_STRUCTURE_PLAN | 10/12 |
| HALLUCINATED_RULE | 3/4 |
| CONCLUDED_UNSUPPORTED | 2/2 |
| REASONING_ANSWER_CONFLICT | 4/8 |
| FULL_CONTRACT_RESIDUE | 0/1 |
| DEGENERATE_REPETITION | 0/1 |

## 5. 주요 false positive(승인인데 flag)

- **b006-04:m2sample:6(GROUPING_UNIT_AS_PLACE)**: 결론 구간에 "So the concept should be the H3 cells as a place"가 있다. 그 뒤 "can't create … dimension"으로 결론을 바꾼다. 결론 구간 안에서 망설이다 바로잡은 경우다.
- **ann-29dc…:m2sample:6(HALLUCINATED_SCHEMA_RULE)**: "The answer is 'bucket' because the question is asking for the month"는 bucket month가 있는 정당한 이유다. 문장 규칙이 정당한 bucket answer를 구별하지 못했다(구조 조건은 걸리지 않음).
- UNRETRACTED_WRONG_AGGREGATION 3(ann-5149…, ann-dd83…, b006-35)은 "aggregation would be sum … but" 꼴이다. 철회 표현이 목록 밖이었다.

## 6. 주요 false negative(거부인데 flag 없음)

- **REASONING_ANSWER_CONFLICT 4(b004-18 R70, b005-33 R70·M2, b006-14)**: aggregation sum을 결론 구간 이전에 말하고 끝까지 철회하지 않은 경우다. 결론 구간 밖이라 잡지 못했다.
- **INVALID_STRUCTURE_PLAN 2(b006-02 R70, b006-08 R70)**: "H3 셀을 place로" 계획이 결론 구간 밖에 있었고, 응답 JSON에는 구조 흔적이 남지 않았다.
- **FULL_CONTRACT_RESIDUE·DEGENERATE_REPETITION**: 범위 밖 유형이다(v1 flag 없음).
- **HALLUCINATED_RULE 1(ann-29dc… greedy)**: 결론 구간 밖 규칙 주장이다.

## 7. 한계와 사용 방침

- recall 0.68: 거부 대상의 약 1/3은 flag 없이 지나간다. 그래서 사람 검토가 계속 필수다.
- precision 0.70: flag가 걸려도 30%는 승인할 만한 trace다. flag는 거부 사유가 아니라 우선 검토 표시다.
- 27B trace에도 그대로 적용한다. v1 결함은 기록만 하고, 고친다면 v2를 별도 결정으로 만든다.
