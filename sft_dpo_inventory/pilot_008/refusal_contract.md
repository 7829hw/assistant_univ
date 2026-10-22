# pilot_008 P1: 거부 계약과 채점 정리(2026-10-22)

진단 기록. protected_final_v1은 쓰지 않았다(결정 220) — 그 셋에 대해서는 이미 보고한 집계(결정 217)만 인용한다. 계산: `analysis/refusal_p1.py` → `analysis/refusal_p1.json`.

## 1. Full 계약에서 거부가 표현되는 곳

**거부 target 형식은 정해져 있다**(지시 5절 "형식 미정"에 해당하지 않음).

| 경로 | 누가 정하나 | 모델 출력 | 파이프라인 결과 | 오류 코드 |
|---|---|---|---|---|
| (M) 모델 거부 | 모델 | `{"unsupported": true}` 하나(`geoflow/planner.py` `UNSUPPORTED_KEY`) | `unsupported` | `UNSUPPORTED_QUESTION`(planner 단계, `_validate_payload`) |
| (P) 프로그램 거부 | 프로그램 | 질문을 그대로 옮긴 grounding | `unsupported` | `UNSUPPORTED_CODES`의 나머지 21개(예: UNCONSUMED_CONDITION, NO_OPERATOR, UNSUPPORTED_AGGREGATION_COMBINATION, UNVERIFIED_TIMS_CONTRACT, PARAM_VALUE_*) |
| (C) 확인 요청 | 프로그램 | grounding(집계 단계를 정하지 않음 등) | `needs_clarification` | 오류 context `needs_clarification`(예: AMBIGUOUS_INNER_AGGREGATION, AMBIGUOUS_AGGREGATION_STAGE, PLACE_NOT_IN_QUESTION) |
| 실패 | – | 구조 오류 JSON 등 | `failed` | INVALID_*, NOT_FOUND, UNSUPPORTED_COMBINATION 등 |

- prompt(`prompts/geoflow_planner.yaml`, 87048d0c)의 규칙: **(M)은 좁게** — "질문을 해석할 수 없거나 측정값·조건을 이 문서의 개념과 factor로 적을 수 없을 때만",
  "측정 개념이 목록에 없으면 비슷한 값으로 바꾸지 말고", 출발·도착을 읽을 수 없을 때, 고칠 방법이 없을 때(repair). **그 밖은 (P)** — "그 조합을 실제로 계산할 수 있는지와 관계없이
  그대로 적습니다. 계산할 수 있는지와 멈출 이유는 프로그램이 판단합니다."
- 계약상 (M)이 맞는 질문의 예: 목록에 없는 측정값(승객 수, 대기 시간, 사고 건수 등), factor로 적을 수 없는 조건(묶음 단위 일·시간·분기 — `bucket`은 week·month뿐;
  미래 날짜 표현 — `date`는 과거·현재 표현과 YYYYMMDD만), 계약 개념이 없는 대상(개별 차량·기사, 버스·지하철 등 다른 교통수단, 도메인 밖 질문).
- PLAN_FINAL 4절 채점(최종 판정): 거부 문항 = outcome ∈ {unsupported, needs_clarification}이고 분석 tool 실행 없음 → 정답(경로 M·P·C 모두 인정);
  거부 아닌 문항 = grounding_ok 그리고 거부로 끝나지 않음.

## 2. base와 F-o11의 거부·과잉 거부(주 셋·개발 셋, 같은 분류)

과잉 거부 = 거부 아닌 문항 표본 중 (M)·(P)·(C)로 끝난 비율(%).

| 셋 | base 과잉 거부(M / P / C) | F-o11 과잉 거부(M / P / C) |
|---|---|---|
| selection_v2(base k=12, F k=4) | 4.58 (0 / 3.85 / 0.73) | 0.82 (0 / 0.82 / 0) |
| holdout(base k=8) | 3.07 (0 / 2.83 / 0.24) | 1.42 (0 / 1.42 / 0) |
| valid98 | 4.30 (0 / 4.03 / 0.27) | 0.00 |
| aux | 7.07 (0 / 7.07 / 0) | 0.00 |

- base의 과잉 거부는 거의 모두 (P) — UNCONSUMED_CONDITION·NO_OPERATOR(질문에 없는 조건을 넣거나 조건을 남김). **(M)은 두 모델 모두 0**.
- 비교: protected_final_v1(결정 217 집계)의 과잉 거부 표본은 base 231/880(26.3%), 후보 211/880(24.0%)로 주·개발 셋(0–7%)보다 훨씬 높다.
  그 셋의 결과 상태 분해는 하지 않았다(문항 단위 값을 열지 않음). 주·개발 셋 기준으로는 F-o11이 과잉 거부를 늘리지 않았다.

거부 문항(gold `expected_outcome` ≠ answered)의 올바른 거부 표본:

| 셋(거부 문항 수) | base | F-o11 | 올바른 거부의 경로 |
|---|---:|---:|---|
| selection_v2(7: 미지원 5·확인 2) | 62/84(73.8%) | 21/28(75.0%) | base·F 모두 (P) UNCONSUMED_CONDITION 대부분 + (C) |
| valid98(5: 미지원 2·확인 3) | 12/20(60%) | 5/20(25%) | base (P) UNVERIFIED_TIMS_CONTRACT 8 + (C) 4; F (P) 5, (C) 0 |
| aux(5: 미지원 2·확인 3) | 11/20(55%) | 6/20(30%) | base (P) 7 + (C) 4; F (P) 4 + (C) 2 |
| protected_final_v1(10, 결정 217 집계) | 38/80 | 4/80 | 분해 안 함 |

- 기존 개발 셋의 거부 문항은 모두 (P)·(C)로 거부되는 문항이다. **(M) 모델 거부로 거부된 표본은 base·F 모두 0** — "도구로 답할 수 없는 질문" 유형이 개발 셋에 없다.
- F-o11이 잃은 것: (C) 확인 요청(valid98 base 4 → F 0)과 일부 (P). protected_final_v1의 큰 낙차(38 → 4)는 그 셋의 거부 문항이 "지원하지 않는 질문"(작성 지침)이라
  (M)에 가까운 문항일 가능성이 크다 — 가설(문항을 열지 않음).

## 3. 학습 데이터의 거부 target

| 데이터 | 질문 / 레코드 | (M) `{"unsupported": true}` target | (P) 프로그램 거부로 끝나는 target(mock) | 실패로 끝나는 target |
|---|---|---:|---|---|
| RC3 Full(pilot_006) | 386 / 1,861 | **0** | 9 질문 / 67 레코드(모두 trunk, UNCONSUMED_CONDITION) | 51 질문 / 251 레코드 |
| RC5 Full(pilot_007 B2) | 391 / 1,811 | **0** | 9 질문 / 63 레코드(모두 trunk) | 47 질문 / 224 레코드(UNSUPPORTED_COMBINATION 39·NOT_FOUND 7·MISSING_REQUIRED_INPUT 1) |
| 승인 corpus v3 | 630 | 0(semantics `unsupported` 0) | 20 | 83 |

- 학습 데이터에는 **(M) 거부 예시가 하나도 없다**. 모든 target이 grounding JSON이라, 1 epoch 학습 뒤 모델은 어떤 질문에도 grounding을 쓰는 쪽으로 옮겨 간 것으로 본다(가설).
- (P)·(C) 쪽은 target이 grounding 자체라 거부를 따로 배우지 않는다 — 질문을 정확히 옮기면 프로그램이 거부한다. (C)를 만드는 grounding(집계 단계를 정하지 않음) 예시도 RC5에 거의 없다.

## 4. base가 거부를 배운 곳

- **system prompt 규칙 문장뿐**: planner prompt의 (M) 규칙(위 1절, 7곳: 고칠 방법이 없을 때·필요한 조건을 정할 수 없을 때·측정 개념이 목록에 없을 때·출발/도착을 읽을 수 없을 때·출력 형식).
- prompt의 고정 예시 5개에는 거부 예시가 없다. 예시 저장소(`geoflow_examples/question_graph_examples.yaml`, 16개 중 unsupported 2·확인 1)는 retrieval로만 쓰이는데,
  평가 경로(`vllm_eval_thinking5.py`, PipelineCreate 기본)는 retrieval을 쓰지 않는다(셀 행 `planner_trace`에 retrieval 없음).
- 따라서 학습이 prompt 규칙의 (M) 행동을 덮어쓴 것으로 보이고, 되살리려면 (M) target 레코드(그리고 (C)·(P) 근접 대조)가 필요하다 → batch011.
