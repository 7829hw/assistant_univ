# Full vs P0 vs Partial-P0.3 on sel154 (ab_p0_3) — 확정 2026-10-11(사용자, 결정 61)

질문: P0.2의 valid98 실패가 Partial Grounding 자체의 한계인가, 아니면 금지 규칙만 두고 값의 올바른 목적지를 알려주지 않은
prompt 설계 문제인가. P0.3는 이 질문 하나만 검증하도록 P0.2에 규칙 11만 더한 최소 변경이다.

이 문서는 모델 실행 전에 확정한다. 결과를 본 뒤 정의·gate·부분집합을 바꾸지 않는다. 결과가 나빠도 바로 P0.4를 만들지 않는다.

## 1. 고정 기준

| 항목 | 값 |
|---|---|
| Full prompt | `prompts/geoflow_planner.yaml`, `87048d0c…` |
| P0 prompt | `evaluation/partial_grounding/prompts/partial_p0.yaml`, `d7f4c12a…` |
| P0.3 prompt | `evaluation/partial_grounding/prompts/partial_p0_3.yaml`, `8b157c9a…` |
| P0.3 변경 | P0.2(`87fd3441…`) output_format에 규칙 11만 추가. 결합 prompt 기준 추가 97줄·삭제 0·변경 0. 새 예시 없음. task·의미 section·재질의 요청문·규칙 1–10·예시 1–6은 P0.2와 같다 |
| code | parser/composer `9cb8a39`, 실행 의미 code 지문 `ab88a19e…`. 평가 harness·scorer는 ab_valid98과 같다 |
| 모델·장비 | Ollama `qwen3:8b`(base, think 미지정 = thinking on). 결정 56 장비 절차, `cell_guard.py`(77.6 tok/s) |
| 설정 | ab_valid98 `PLAN.md` 1절과 같다: `--condition-check`, 기준일 2026-09-25, mock·legacy, unload_per_question, 문항 순서 file, `--record-env`. greedy = temperature 0, sampling = 0.6/0.95/20, seed 20261010–20261014(같은 회차 세 arm 같은 seed) |
| 셋 | sel154(결정 61): `ab_p0_3/sel154_gold.yaml` sha256 `aab80783…` |

## 2. 실행 전 검사(완료)

- `contract_check.py` → `contract_check.json`:
  - 정적 diff: 추가 97·삭제 0·변경 0. 추가 블록은 규칙 11 하나. 지문 `ab88a19e`.
  - A. 사용자 od_role payload(동성로 dropoff + trip_count) → answered, `get_trip_count(scope_dropoff=…)`.
  - B. valid98 gold의 dimension_target pickup(`heldout_v8/t14`)·dropoff(`t11`)·both(`t23`), od_role + dimension_target(`t11`) → Full·Partial 모두
    match, 결과 같음.
  - C. bucket week(`stage_v7/s01a`)·month(`s01c`) → Full·Partial 모두 match.
  - P0.3 예시 1–6 모두 answered.
  - valid98을 쓴 것은 이미 진단에 쓴 셋이기 때문이다(판정 셋 sel154는 열지 않았다).
- `survey_sets.py` → `survey_sets.json`: 후보 셋의 수만 셌다(질문 문장 없음).
- `build_holdout.py` → `sel154_gold.yaml`, `sel154_check.json`: 154문항 = answered 144, unsupported 5, needs_clarification 5.
  정답 grounding을 Full과 Partial로 넣은 결과가 154문항 모두 같고 정답 범주다(match 144, expected_refusal 10).

## 3. 셋 선택(결정 61)

| 셋 | 문항 | answered | unsupported | needs_clar. | OD | dimension_target | bucket | P0.x 설계에 씀 | 현재 조건(Ollama 0.40.1 qwen3:8b)으로 잼 |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| vendor100 | 100 | 100 | 0 | 0 | 33 | 21 | 3 | 예(P0–P0.2) | 예(ab_p0) |
| valid98 | 98 | 93 | 2 | 3 | 52 | 37 | 14 | 예(P0.3 근거) | 예(ab_valid98) |
| selection_v1 | 100 | 93 | 5 | 2 | 28 | 13 | 16 | 아니오 | 아니오(HF-E·pilot_002 SFT 선택만) |
| aux_test_v1 | 51 | 46 | 2 | 3 | 19 | 11 | 10 | 아니오 | 아니오(옛 장비 Ollama 0.35.1 E·B-conv) |
| selection pool 나머지 | 54 | 51 | 0 | 3 | 13 | 7 | 8 | 아니오 | 아니오 |
| **sel154(선택)** | 154 | 144 | 5 | 5 | 41 | 20 | 24 | 아니오 | 아니오 |

선택 이유와 오염 관계는 DECISIONS.md 결정 61. sel154는 판정 1회용이다. 결과를 보고 prompt를 고치지 않는다.

## 4. 셀(`run_all.sh`, 출력 `raw/`)

1. smoke: P0.3 greedy, `old44/g02,old44/g03,old44/g04`(셋 첫 세 문항). 통과 조건은 ab_p0 `smoke_check.py`(계약 오류 없음). 분석에 쓰지 않는다.
2. greedy: Full → P0 → P0.3.
3. sampling r1–r5: arm 순서를 회차마다 돌린다. r1 Full·P0·P0.3, r2 P0·P0.3·Full, r3 P0.3·Full·P0, r4 = r1, r5 = r2.

guard가 멈춘 셀은 `ABORTED_*`로 남기고 전체를 멈춘 뒤 보고한다. 결과가 이상해도 다시 돌리지 않는다. 예상 시간: 셀당 약 25분 + 대기 5분, 19셀 약 9시간.

## 5. 지표

정의는 ab_valid98 `analyze.py`와 같다. 판정은 sampling 5회 평균, greedy는 따로 적는다.

- Primary: semantic correctness(match + expected_refusal), answerable semantic correctness, refusal correctness, execution completion,
  final grounding failure.
- Structural: 첫 응답 structural error, malformed JSON(첫 응답·최종), repair 호출 수와 repair 성공률.
- Efficiency: 최종 JSON token(Qwen3-8B tokenizer), eval_count, thinking 길이, 문항 wall-clock, timeout, retry.
- Refusal confusion(arm별), 오류 census A–F(ab_valid98과 같은 heuristic).
- Paired(Full vs P0.3 주 비교, Full vs P0·P0 vs P0.3 보조): 문항별 k/5, 회차별 2×2, 일관된 개선·악화(|k차| ≥ 4), 거부 판단이 바뀐 문항,
  새 structural failure 문항, 문항 단위 paired bootstrap 95% CI(10000회, seed 0), sign-flip permutation p.

### 부분집합(gold factor 존재로 고정)

- `dt`: 정답 grounding factors에 `dimension_target`이 있는 문항(20).
- `bucket`: 정답 grounding factors에 `bucket`이 있는 문항(24).
- `refusal`: expected_outcome이 answered가 아닌 문항(10).
- 각 부분집합에서 arm별 정답률과 Full 대비 paired 차이·CI를 낸다.

### 특정 지표

- **dimension_target 누락률**: `dt` 문항 관측 중 `grounding_diffs`에 `factor:dimension_target`이 gold 값 → None인 비율.
  분모는 `dt` 문항의 모든 관측(5회 × 20). 최종 grounding이 없는 관측(no_grounding)은 누락으로 세지 않고 따로 센다.
  문항 단위 bootstrap CI를 같이 낸다.
- **week/month-as-dimension**: 첫 planner 응답 JSON의 factors.dimension이 week·month·day·hour인 관측 수(셋 전체, sampling 합계).
  `bucket` 문항 안의 수도 따로 센다.

## 6. 사전 가설

- H1: P0.3 semantic correctness ≥ Full − 1%p.
- H2: P0.3 answerable semantic correctness ≥ Full − 1%p.
- H3: P0.3 첫 응답 structural error ≤ Full.
- H4: `dt` 문항에서 P0.3 dimension_target 누락률 < P0 누락률. 또는 최소한 Full 누락률 + 5%p 이내.
- H5: `bucket` 문항(및 전체)에서 week/month-as-dimension이 P0.2 valid98 수준(sampling 15건, Full 1건)으로 재현되지 않는다.
  "뚜렷한 증가" = P0.3 sampling 합계가 Full 합계보다 5건 이상 많음.
- H6: P0.3 최종 JSON token < Full.

## 7. Gate

| Metric | Gate |
|---|---|
| semantic correctness | Full 대비 −1%p 이내 |
| answerable semantic correctness | Full 대비 −1%p 이내 |
| refusal correctness | 의미 있는 악화 없음(10문항이라 문항별로 본다) |
| execution completion | Full 대비 −1%p 이내 |
| final grounding failure | Full보다 증가하지 않음 |
| first-response structural error | Full보다 증가하지 않음 |
| malformed JSON | 거의 0 |
| dimension_target omission | P0보다 개선 |
| week/month-as-dimension | 뚜렷한 증가 없음(위 정의) |
| JSON token | Full보다 감소 |

점 추정으로 판정하고 CI를 함께 보인다. CI가 −1%p 비열등을 보이지 못하면 그렇게 적고 "증명되었다"고 쓰지 않는다.

## 8. Error attribution(관측 단위, 한 관측에 여러 범주 가능)

정답이 아닌 관측(match·expected_refusal 아님)을 아래 규칙으로 나눈다. 판정은 기록된 필드만 쓴다.

| 범주 | 규칙 |
|---|---|
| A. model semantic decision | answered_mismatch이고 아래 B–G에 들지 않는 grounding 차이(date, aggregation_spec, taxi_type/status, order/limit, dimension 값, time 등) |
| B. concept/factor/attribute boundary | 첫 응답 census A(비 subtype)·B(dimension 단어를 place로)·E1(dimension에 pickup/dropoff/both) 또는 첫 응답 오류 INVALID_CONCEPT·UNKNOWN_ATTRIBUTE·UNKNOWN_FACTOR |
| C. dimension_target omission | grounding_diffs `factor:dimension_target` gold 값 → None |
| D. od_role ↔ dimension_target confusion | `factor:dimension_target` 차이와 `places`(od_role 포함) 차이가 같은 관측에 함께 있음, 또는 gold에 dimension_target이 없는데 예측에 생김 |
| E. bucket ↔ dimension confusion | 첫 응답 dimension이 week/month/day/hour, 또는 `factor:bucket` 차이와 `factor:dimension` 차이가 함께 있음 |
| F. place/scope value omission | 첫 응답 오류 VALUELESS_CONCEPT·MISSING_CONCEPT_VALUE·UNGROUNDED_SCOPE, 또는 census D·F |
| G. measure omission | 첫 응답 오류 NO_MEASURE·MULTIPLE_MEASURES, 또는 `measure` 차이 |
| H. refusal error | 거부 문항에서 expected_refusal이 아님, 또는 answerable 문항에서 refused_unsupported·refused_clarification |
| I. parser/composer/repair failure | outcome failed이고 위 B·E·F·G·H에 들지 않음(repair 범위 이탈, 조합 오류 등). 기록된 final error code별로 센다 |

arm별(Full·P0·P0.3) sampling 합계와 Full 대비 증감을 표로 낸다.

## 9. 결과에 따른 다음 행동(사용자 지시 16절)

- A. P0.3가 Full 대비 gate 통과 → P0.3를 candidate로 동결하고 Full vs P0.3를 HF에서 재현. P0.2는 진단 기록으로 둔다.
- B. 전체 성능은 통과하지만 dimension_target 문제가 남음 → prompt를 더 고치지 않고 instruction following·semantic ambiguity·sampling
  instability로 분해.
- C. P0.3도 전체 semantic 성능이 악화 → P0.4가 아니라 role 제거의 영향 가설(P0 + role 일부 보존, semantic label을 reasoning scaffold로
  제공 등)을 먼저 세운다.

이번 단계에서 하지 않을 것: HF 재현, P1, thinking OFF, SFT, pruning, 082/h36 전용 수정, region heuristic, repair·parser·composer 변경,
valid98 재판정, push.
