# p0_sft_003 준비: R70 semantic degradation 원인 분석 계획

고정: 2026-10-14, 분석 스크립트 실행 전. 결정 70.

- 새 모델 호출, 새 SFT, 27B 반입은 하지 않는다. 기존 자료만 쓴다.
- p0_sft_001·p0_sft_002 파일은 고치지 않는다.
- 이미 아는 것: p0_sft_002 REPORT의 panel 합계(Base 38, R70-json 28, R70-full 34)와 stratum 합계.
  - 문항별 regression 목록과 trace tag는 아직 보지 않았다.
  - 아래 정의는 그 전에 고정한다.

## 1. 질문과 가설

R70-full은 thinking을 정상적으로 유지하는데, 왜 Base보다 semantic correctness가 낮은가?

| 가설 | 내용 |
|---|---|
| H1 | reasoning trace 품질 문제(잘못된 중간 판단·망설임까지 full_response로 학습) |
| H2 | 70문항의 semantic coverage 편향 / catastrophic forgetting |
| H3 | 작은 데이터에서 LoRA SFT가 특정 출력 행동으로 과도하게 specialization됨 |

## 2. 자료

| 자료 | 내용 |
|---|---|
| v006 154 | `training/generated/reviewed_gold_v006_p0/sft_train.jsonl`(metadata.target_full) |
| trace 원문 | `training/generated/thinking_traces/p0_v006_hf/traces.jsonl` |
| trace 판정 | `p0_sft_001/selected_traces.jsonl`, `trace_review.json`, `evaluation/partial_grounding/sft_p0/trace_quality.json` |
| R70 70 | `training/generated/p0_sft_002/r70/sft_train.jsonl` |
| panel 56 | `p0_sft_002/diagnostic_panel*.{json,yaml}` |
| panel 결과 | Base(p0_sft_001 base 결과), R70-json·R70-full(`p0_sft_002/mechanism_probe/`, 원문 `training/generated/p0_sft_002/mechanism_raw/`) |
| 보조 | p0_sft_001 403문항 결과(Base·Gold-only·Clean-Hybrid). family coverage와 regression의 관계를 더 큰 표본으로 본다 |

## 3. semantic family 정의(결과를 보지 않고 고정)

gold payload(평가 문항은 `evaluate_vendor100.gold_grounding`, 학습 문항은 Full canonical gold)로 계산한다.

- **feature**:
  - measure subtype
  - dimension, dimension_target
  - od_role 구조: 값 있는 장소·scope의 od_role 정렬 목록
  - od_ne_dt
  - bucket, aggregation, rollup, order, answer(value는 기본으로 생략)
  - vicinity
  - 장소 구조: 값 있는 place 수, 값 있는 scope 유무, 값 없는 답 place 유무
  - taxi_type
  - refusal kind(expected_outcome이 answered가 아니면 그 값)
  - 표면 문장, 장소 이름, 날짜는 넣지 않는다.
- **exact family**: 기존 `training.annotations.inventory.family_key`(measure·od_role·aggregation·rollup·bucket·answer·dimension·dimension_target·order·vicinity) + 장소 구조 + refusal kind.
- **near family**: (measure, dimension 유무, dimension_target, bucket, 값 있는 place 유무, 값 있는 scope 유무, refusal kind).
- **coverage 수**(panel 문항마다 R70 70 안에서 센다):
  - exact_family_count, near_family_count, same_measure_count
  - same_dimension_target_count(문항에 dimension_target이 있을 때)
  - same_bucket_count(bucket 값 같음)
  - same_od_role_pattern_count, same_scope_pattern_count(장소 구조 같음)
- **"없거나 매우 희소"**: exact_family_count == 0 그리고 near_family_count ≤ 1.

## 4. panel 그룹과 regression tag

- 그룹(semantic correctness 기준):

| 그룹 | Base | R70-full |
|---|---|---|
| A | 정답 | 정답 |
| B(regression) | 정답 | 오답 |
| C(improvement) | 오답 | 정답 |
| D | 오답 | 오답 |

- B 문항마다 tag를 여러 개 줄 수 있다. 하나도 해당하지 않으면 UNCLEAR다.

| tag | 조건 |
|---|---|
| COVERAGE_GAP | "없거나 매우 희소"(3절). 이 tag가 붙은 B를 coverage-linked regression(catastrophic forgetting 후보)으로 부른다. 인과 증명은 아니다 |
| STRUCTURAL_FAILURE | R70-full 첫 응답 structural error 또는 malformed JSON |
| GENERATION_LIMIT | R70-full 호출 중 하나라도 done_reason length |
| SEMANTIC_OMISSION | R70-full 최종 grounding이 있고, gold에 있는 값이 예측에 없다. 장소 누락, gold factor 누락, measure 누락이 해당한다 |
| TRACE_PATTERN_TRANSFER | R70-full이 gold와 다른 non-null 값을 넣었고(commission), 그 값이 R70 학습 target에서 같은 field의 최빈 값 또는 그 문항 near family 학습 target의 값과 같다 |

- C 문항은 같은 coverage 수와 직접 지원 family(exact·near family 학습 문항 ID)를 기록한다.
- 결과 표: `failure_attribution.csv`. 항목은 item, family, Base·R70-full 결과, 두 grounding, diff, coverage, 관련 학습 trace ID다.

## 5. trace quality tag(승인 70, 승인·거부 판정은 바꾸지 않음)

thinking 원문에서 규칙으로 계산한다(영어 원문 기준 정규식, 수동 조정 없음).

**wrong-value mention(중간에 gold와 다른 값을 말함)**

- field별로 thinking에 나온 값 중 gold와 다른 값이 있는지 본다.
  - measure subtype 이름
  - dimension 값
  - dimension_target 값
  - od_role 값(장소가 있는 문항)
  - aggregation·rollup 값
  - bucket 값
  - unsupported 판단(`"unsupported": true` 또는 "unsupported")
- 이 문항들은 최종 답이 맞으므로 이것은 "중간에 말했다가 바뀐 값"의 근사다. 부정문("not X")도 세므로 상한 추정이다.
- 장소 해석 오류는 자동화하지 않는다.

**tag**(여러 개 허용)

| tag | 조건 |
|---|---|
| SELF_CORRECTED | wrong-value mention 1개 이상 |
| HESITANT | "Wait"·"Hmm"·"maybe"·"not sure"·"confus" 출현 합 ≥ 4 |
| VERBOSE | thinking_chars ≥ 70개 중 75 백분위 |
| SCHEMA_BOOKKEEPING | Full 구조어(role, MEASURE, SUBCOND, COND, SUPPORT, EVENT, implicit, source) 합 ≥ 3 |
| WEAK_JUSTIFICATION | gold에 있는 dimension_target·bucket·aggregation·rollup·order·od_role 중 하나라도 이름과 값이 모두 thinking에 없음 |
| CONTRASTIVE_REASONING | "rather than", "instead of", "as opposed to", "not ... but", "distinguish", "vs" 중 하나 |
| CLEAN_DIRECT | wrong-value mention 0, "Wait"·"Hmm" 합 ≤ 1, thinking_chars ≤ 중앙값 |

- 길이: thinking_chars와 thinking_tokens(HF 원문 생성 token 수에서 답 부분을 뺀 근사)의 분포를 family별로 본다.
- **H1 지원 조건:** B 문항과 관련된 학습 trace의 SELF_CORRECTED·HESITANT·wrong-value 비율이 70개 전체보다 뚜렷이 높다.
  - 관련 trace = exact·near family 학습 문항, 없으면 같은 measure 학습 문항.
  - 뚜렷이 = 15%p 이상.
- 반대로 B가 주로 COVERAGE_GAP이면 H2가 더 강하다.

## 6. H3 specialization 지표(panel 56, Base vs R70-full, R70-json은 참고)

- 최종 JSON 길이, thinking 길이, factor 수, concept 수
- place 포함률(gold에 값 있는 place가 있는 문항에서)
- dimension_target·bucket 포함률(gold에 있을 때)과 과잉 포함(gold에 없는데 넣음)
- silent omission: B 중 STRUCTURAL·GENERATION_LIMIT 없이 SEMANTIC_OMISSION만 있는 수

## 7. 보조: 403문항에서 family coverage와 regression(p0_sft_001)

- 평가 문항마다 exact family가 v006 154 안에 있는지 본다.
- Base 정답 → Gold-only·Clean-Hybrid 오답 비율을 covered와 uncovered로 나눈다.
- 이 모델들은 thinking이 없으므로 R70과 같은 조건은 아니다. 표본 크기 보조로만 쓴다.
- panel 문항과 R70 학습 문항은 겹치지 않는다(평가셋·학습셋 분리). "학습한 문항 자체 성능"은 기존 기록에 없다. family 수준으로만 본다.

## 8. survival과 missing 84

- **survival 단계**: v006 154 → EXACT_OR_SEMANTIC_MATCH trace 있음 → 필터 통과 trace 있음 → 선택 → 승인(R70).
  - feature별로 센다: bucket, dt pickup, dt dropoff, dt both, od_ne_dt, Gap A, Gap B, measure별, 장소 있음, scope 있음, compile 정지 target.
- **M 분류**(R70 밖 84):

| 분류 | 조건 |
|---|---|
| M1 | EXACT trace가 하나도 없음 |
| M2 | 선택 trace가 사람 검토에서 거부 |
| M3 | EXACT trace는 있지만 필터(tokenize 왕복·루프·길이)에서 모두 빠짐 |

## 9. teacher 보충 우선순위(`missing_reasoning_manifest.json`)

| 우선순위 | 조건 |
|---|---|
| P1 | exact family가 R70에 없고, near family가 panel B(regression) 문항과 같다 |
| P2 | P1이 아니고, dimension_target·od_ne_dt·bucket·compile 정지 target 중 하나이며, R70 near family 수 ≤ 2 |
| P3 | 그 밖 |

| 권고 action | 대상 |
|---|---|
| SUPPLEMENT | M1. teacher 보충 대상 |
| REVIEW_OR_RESAMPLE | M2. correct trace는 있었으므로 8B 추가 표본 또는 거부 사유 보완 |
| REFILTER | M3. 필터 이유 재확인 |

- teacher 호출은 하지 않는다.

## 10. 판정 규칙(결과 뒤 해석에 쓴다)

| 경로 | 조건 |
|---|---|
| Path A(coverage) | B 중 COVERAGE_GAP ≥ 50%. 7절 보조에서 uncovered regression 비율이 covered보다 높다 |
| Path B(trace quality) | 5절 H1 지원 조건을 만족하고, B 중 COVERAGE_GAP < 50% |
| Path C(specialization) | B 중 SEMANTIC_OMISSION·TRACE_PATTERN_TRANSFER가 COVERAGE_GAP과 겹치지 않고 다수이며, 6절에서 출력이 체계적으로 짧아지거나 field가 빠진다 |
| Path D | 둘 이상이 함께 성립 |

- 56문항이라 B는 소수다. 숫자가 작으면 판정 대신 기술로 남긴다.

## 11. 산출물(모두 스크립트가 만든다)

- `coverage_analysis.py` → `coverage_analysis.json`, `failure_attribution.csv`
- `trace_quality_analysis.py` → `trace_quality_analysis.json`
- `build_teacher_manifest.py` → `missing_reasoning_manifest.json`
- `TEACHER_PLAN.md`(A 27B / B 8B 추가 표본 / C 짧은 canonical rationale 비교, 생성 안 함)
- `REPORT.md`
