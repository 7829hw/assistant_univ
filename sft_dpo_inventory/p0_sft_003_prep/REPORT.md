# P0 SFT 3차 준비 — R70 Semantic Degradation 분석

2026-10-14. 계획 `PLAN.md`(커밋 `40db3d8`), 결정 70·71. 새 모델 호출·학습 없음.

숫자는 다음 산출물에서 왔다:
- `coverage_analysis.json`, `failure_attribution.csv`
- `trace_quality_analysis.json`
- `arm_contrast.json`(사후 보조)
- `survival.json`, `missing_reasoning_manifest.json`

## 1. 결론

R70-full이 Base보다 낮은 이유는 한 가지가 아니다. **혼합 원인(Path D)** 이며, 무게는 coverage 쪽이 더 크다.

**H2 coverage 편향: 가장 강한 근거, 특히 dimension_target.**

- R70은 v006을 고르게 대표하지 않는다. dimension_target 35%, od_role ≠ dimension_target 32%, Gap A 19%, emd 22%, sido 18%, order 29%만 남았다. bucket·rollup은 78%가 남았다.
- dimension_target이 gold에 있는 panel 문항에서 이 field를 넣은 비율: Base 18/20, R70-full 10/20.
- 반대로 dimension_target을 154문항 모두로 학습한 p0_sft_001은 dimension_target이 크게 좋아졌다(Base 44/89 → 69/89). R70의 dimension_target 하락은 coverage 축소와 맞는다.
- panel regression 11 중 COVERAGE_GAP은 4다. 그중 3(scope 역조회 2, refusal 1)은 **v006 전체에도 없는 family**라서 teacher 보충으로 해결되지 않는다.

**H1 trace 품질: 부차적. 사전 등록 조건은 불충족.**

- 승인 70 trace는 전반적으로 noisy하다.
  - 중간에 gold와 다른 값을 말함: 75.7%. aggregation이 36건으로 가장 많다.
  - HESITANT: 60%.
  - 묶음 단위어를 장소로 말함(사후 지표): 28.6%.
- 그러나 regression과 관련된 trace는 70개 평균과 차이가 없다(SELF_CORRECTED +0.5%p, HESITANT −12.4%p). 사전 등록 조건(15%p 이상)을 만족하지 못한다.
- 같은 데이터로 학습한 R70-json 대비 R70-full만 틀린 문항은 5개다. 반대로 R70-json만 틀린 문항은 11개다. trace 문장 학습의 순효과는 +6이고, 비용은 일부 문항에 한정된다.

**H3 small-data specialization: 약한 근거.**

- Base 대비 R70-full의 출력 길이·factor 수·concept 수·thinking 길이는 거의 같다(JSON 중앙값 783 → 787자, factor 4.06 → 3.98).
- silent omission만으로 설명되는 regression은 1개다.
- 다만 regression 7개가 coverage가 있는 family(near 1–9개)에서 구조 오류로 실패했다.
  - 유형: 묶음 단위어를 concept·장소로 냄, 값 없는 place, MULTIPLE_MEASURES.
  - 작은 데이터 학습이 출력 구조를 흔든 영향일 수 있다.

## 2. Git / 데이터 무결성

- 시작: local = remote = `cbd0fbc`(작업 트리 깨끗함). 원격 이 branch에 새 커밋은 없었다(`geoflow/sft-dpo-t2pc`만 갱신).
- 작업 단위마다 commit → push → fetch 후 HEAD와 `origin/geoflow/partial-grounding` 일치를 확인했다.

| 단위 | commit |
|---|---|
| 계획(결정 70) | `40db3d8` |
| coverage·regression | `316b405` |
| trace 품질·arm 대조 | `5c18150` |
| survival·manifest | `0420513` |
| REPORT·TEACHER_PLAN(결정 71) | 이 커밋 |

- p0_sft_001·p0_sft_002 파일은 고치지 않았다. 모든 표는 스크립트 산출물에서 가져왔다.

## 3. R70 vs v006 coverage(`coverage_analysis.json` coverage_ratio)

| feature | v006 | R70 | 비율 |
|---|---:|---:|---:|
| dimension_target | 74 | 26 | 0.35 |
| dt pickup / dropoff / both | 35 / 29 / 10 | 11 / 12 / 3 | 0.31 / 0.41 / 0.30 |
| od_role ≠ dimension_target | 31 | 10 | 0.32 |
| bucket | 23 | 18 | 0.78 |
| aggregation / rollup | 40 / 23 | 24 / 18 | 0.60 / 0.78 |
| order | 59 | 17 | 0.29 |
| dimension h3 / emd / sigungu / sido | 28 / 27 / 21 / 11 | 13 / 6 / 8 / 2 | 0.46 / 0.22 / 0.38 / 0.18 |
| place / scope | 117 / 2 | 59 / 2 | 0.50 / 1.0 |
| measure trip_count | 94 | 38 | 0.40 |
| Gap A / Gap B | 26 / 17 | 5 / 11 | 0.19 / 0.65 |

- family 수: exact 104 → 55, near 28 → 25.
- 순위·grouping(order, emd·sido)과 dimension_target 계열이 가장 많이 줄었다.
- 시간 집계(bucket·rollup)는 잘 남았다. panel bucket에서 R70-full이 10/10을 유지한 것과 맞는다.

## 4. Teacher-easy selection bias(`survival.json`)

| feature | v006 | EXACT trace 있음 | 필터 통과(선택) | 승인 R70 | survival |
|---|---:|---:|---:|---:|---:|
| 전체 | 154 | 95 | 91 | 70 | 0.45 |
| bucket | 23 | 19 | 19 | 18 | 0.78 |
| dt pickup | 35 | 22 | 20 | 11 | 0.31 |
| dt dropoff | 29 | 18 | 17 | 12 | 0.41 |
| dt both | 10 | 4 | 4 | 3 | 0.30 |
| od_role ≠ dt | 31 | 16 | 16 | 10 | 0.32 |
| Gap A | 26 | 14 | 12 | 5 | 0.19 |
| Gap B | 17 | 13 | 13 | 11 | 0.65 |
| compile 정지 target | 12 | 6 | 5 | 4 | 0.33 |
| aggregation | 40 | 27 | 27 | 24 | 0.60 |

- dimension_target 계열은 두 단계에서 모두 많이 탈락한다. 8B가 정답을 못 내는 경우가 많고, 맞혀도 추론 검토에서 거부되는 경우가 많다(dt pickup 20 → 11).
- R70은 "teacher가 쉽게 푼 문항"(시간 집계, 단순 측정값)에 치우쳐 있다.

## 5. Base → R70-full regressions(panel 56, `failure_attribution.csv`)

그룹: A(둘 다 정답) 27, **B(regression) 11**, C(improvement) 7, D(둘 다 오답) 11.

| 문항 | stratum | R70-full 실패 | tag | R70-json |
|---|---|---|---|---|
| sel154 k20 | scope 역조회 | UNSUPPORTED | COVERAGE_GAP | 오답 |
| sel154 n40 | scope 역조회 | NO_MEASURE | COVERAGE_GAP, STRUCTURAL | 오답 |
| valid98 s02c | refusal | 답함(거부해야 함) | COVERAGE_GAP | 오답 |
| valid98 r03 | ordinary(가동률 시도 순위) | MULTIPLE_MEASURES(값 없는 place) | COVERAGE_GAP, STRUCTURAL | 정답 |
| valid98 t12 | od_ne_dt | INVALID_PLACE("하차 구"를 장소로) | STRUCTURAL | 오답 |
| vendor100 093 | od_ne_dt | INVALID_FACTOR("읍면동"을 장소로, aggregation "bottom") | STRUCTURAL | 오답 |
| vendor100 012 | od_ne_dt | dimension 누락 | SEMANTIC_OMISSION | 정답 |
| sel154 m09 | dimension_target | MULTIPLE_MEASURES(값 없는 place) | STRUCTURAL | 정답 |
| vendor100 024 | dimension_target | INVALID_CONCEPT(subtype emd concept) | STRUCTURAL | 정답 |
| vendor100 067 | dimension_target | 8192 생성 상한 | STRUCTURAL, GENERATION_LIMIT | 오답 |
| vendor100 030 | dimension_target | aggregation min 추가 → UNCONSUMED_CONDITION | UNCLEAR | 정답 |

- tag 합: COVERAGE_GAP 4, STRUCTURAL_FAILURE 7, SEMANTIC_OMISSION 1, GENERATION_LIMIT 1, UNCLEAR 1, TRACE_PATTERN_TRANSFER 0.
- coverage별 regression 비율:
  - "없거나 희소"(exact 0, near ≤ 1): Base 정답 20 중 4
  - coverage 있음: 18 중 7
  - coverage가 있는 dimension_target·od_ne_dt family에서도 구조 오류로 떨어졌다.
- 6개(k20, n40, s02c, t12, 093, 067)는 R70-json도 틀렸다(데이터 공통 효과). 5개(r03, 012, m09, 024, 030)는 R70-full만 틀렸다(trace 문장 학습 효과).

## 6. Base → R70-full improvements(C 7)

- refusal 3: k39, s01d, g44. Base는 답해 버렸고 R70-full은 정확히 거부했다. R70에 refusal target은 없다. 거부 판단은 학습된 추론 습관(질문 조건 확인)이 일반화된 것으로 보인다.
- dimension_target·od_ne_dt 2: k33, vendor100 020. near family 학습 1–2개가 있다.
- ordinary 2: r04 dayofweek 순위, f27 장소 두 개 건수.
- 관련 학습 trace 18개의 tag 분포는 70개 평균과 비슷하다(HESITANT 78%, SELF_CORRECTED 78%).

## 7. Reasoning trace 품질 분석(`trace_quality_analysis.json`, 승인 판정은 그대로)

| tag | 70개 중 |
|---|---:|
| SELF_CORRECTED(중간 wrong-value mention) | 53 (75.7%) |
| HESITANT | 42 (60%) |
| SCHEMA_BOOKKEEPING | 20 (28.6%) |
| VERBOSE(≥ 75 백분위) | 19 |
| CONTRASTIVE_REASONING | 9 |
| CLEAN_DIRECT | 9 (12.9%) |
| WEAK_JUSTIFICATION | 0 |

- wrong-value mention을 field별로 보면 aggregation 36, bucket 7, unsupported 7, dimension 6, dimension_target 6, od_role 5, rollup 5, measure 3이다. 부정문도 세므로 상한 추정이다.
- 묶음 단위어를 장소·concept로 말함(사후 지표): 20 (28.6%).
- 출처별 SELF_CORRECTED: v005 80%, Gap A 40%, Gap B 73%.
- thinking 길이 중앙값은 3,185자(793 token)다. 가장 긴 family는 active_taxi_ratio 순위(6,638자, 1개)와 dropoff grouping trip_count(6,511자, 4개)다.
- full_response는 이 중간 오판까지 학습한다. R70-full의 첫 응답에서 gold에 없는 aggregation이 14번 나왔다(Base 9, R70-json 11). trace의 aggregation 오판(36건)과 같은 방향이다(사후 관찰, 인과 증명 아님).

## 8. Semantic omission / forgetting 분석

| panel 56 | Base | R70-json | R70-full |
|---|---:|---:|---:|
| 최종 grounding 있음 | 52 | 43 | 44 |
| JSON 길이 중앙값 | 783 | 792 | 787 |
| factor 수 평균 | 4.06 | 3.91 | 3.98 |
| place 포함(gold 38) | 36 | 33 | 32 |
| bucket 포함(gold 16) | 16 | 14 | 16 |
| dimension_target 포함(gold 20) | 18 | 10 | 10 |

- 출력이 체계적으로 짧아지거나 field가 일반적으로 빠지지는 않는다. 그러나 **dimension_target 포함이 18 → 10으로 반 가까이 줄었다.** R70의 dimension_target coverage(35%)와 맞는 coverage-linked 약화다.
- coverage-linked regression(COVERAGE_GAP B) 4개 중 3개는 v006 전체에 없는 family다(scope 역조회·refusal). 이것은 R70 축소가 아니라 v006의 공백이다.
- 보조(403, p0_sft_001 기준):
  - 평가 문항 중 v006과 exact family가 같은 것은 16/403뿐이다. 오염 정책이 평가셋 family를 학습에서 빼기 때문이다.
  - 그래서 exact family coverage로 regression을 가르는 비교(covered 37.5%, uncovered 31.5%, Gold-only)는 정보가 거의 없다.

## 9. Missing reasoning 84문항

| 분류 | 수 |
|---|---:|
| M1 정답 trace 없음 | 59 |
| M2 검토 거부 | 21 |
| M3 필터 탈락 | 4 |

출처: v005 57, Gap A 21, Gap B 6.

## 10. Teacher supplementation priority(`missing_reasoning_manifest.json`)

| 우선순위 | 수 | M1 / M2 / M3 | 기준 |
|---|---:|---|---|
| P1 | 30 | 22 / 8 / 0 | exact family가 R70에 없고 near family가 regression 문항과 같음 |
| P2 | 17 | 9 / 6 / 2 | dimension_target·od_ne_dt·bucket·compile 정지이고 R70 near ≤ 2 |
| P3 | 37 | 28 / 7 / 2 | 그 밖 |

- action: M1은 SUPPLEMENT, M2는 REVIEW_OR_RESAMPLE, M3은 REFILTER.

## 11. 27B 필요성 판단(`TEACHER_PLAN.md`)

- **M1 59개는 8B가 9표본 모두 틀린 문항이다.** 8B를 더 뽑아도 수율이 낮을 가능성이 크다.
  - 그 중 P1·P2 31문항(대부분 dimension_target·trip_count 계열)은 coverage 회복의 핵심이다.
  - 따라서 **27B teacher 반입을 P1·P2의 M1 31문항부터 요청할 근거가 있다.**
- **M2 21·M3 4는 8B 추가 sampling·재필터로 먼저 시도할 수 있다.** 정답 JSON은 이미 냈고 추론만 문제였다.
- 짧은 canonical rationale(C)는 trace noise(75.7%)를 통제하는 대안이다. 다만 분포 차이 위험이 있어 별도 비교 실험 후보로만 둔다.
- v006에 없는 family(scope 역조회, refusal)는 teacher로 해결되지 않는다. 데이터 정책 결정이 필요하다.

## 12. 403문항 R70 평가 필요성

**하지 않는다.**

- panel regression 11은 다음으로 대부분 설명된다.
  - coverage(4, 그중 3은 v006 공백)
  - 구조 오류(7)
  - full 전용 trace 학습 비용(5, 같은 데이터 대조로 분리)
- R70은 dimension_target·order·emd를 크게 잃은 teacher-easy 편향 subset이다. production candidate가 아니므로 403 평가로 얻을 판단 정보가 적다.

## 13. 다음 SFT 추천(시작하지 않음)

- **데이터:** v006 154 전부 reasoning record로 만든다.
  - 답만 있는 레코드는 쓰지 않는다(결정 69의 기전).
  - 승인 70 + 보충(M1 P1·P2 → 27B, M2 → 8B 재표본, M3 → 재필터)으로 coverage를 회복하고, 특히 dimension_target 계열을 우선한다.
- **trace 품질:** 다음 검토에서는 정답 여부와 함께 aggregation 오판을 남긴 trace를 줄이는 쪽으로 선택한다(예: 같은 문항의 정답 표본 중 wrong-value mention이 적은 것 우선). 이 규칙은 결과 전에 고정한다.
- **손실:** full_response를 우선 후보로 둔다(아직 확정 아님). json_only도 reasoning-only 데이터에서는 thinking을 유지하므로 비교 arm으로 둘 수 있다.
- **학습량:** checkpoint 진단상 과적합 기여는 제한적이다. 1 epoch를 기본으로 하고, LR·LoRA 강도 축소는 구조 오류가 계속되면 검토한다.
- **v006 공백(scope 역조회, refusal):** 학습 데이터 0건이다. 평가 독립성 정책(결정 67)을 지키는 한 별도 데이터 결정 없이 해결되지 않는다.
- **사용자 결정이 필요한 것:**
  1. 27B teacher 반입 승인(M1 P1·P2 31문항부터)
  2. M2 8B 추가 sampling 진행
  3. trace 선택 기준(wrong-value mention 적은 표본 우선) 도입
