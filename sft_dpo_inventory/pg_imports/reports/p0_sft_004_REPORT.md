# P0 Full-Reasoning SFT 1차

2026-10-15. 사전 등록 `PLAN.md`(커밋 `3a277f9`), 결정 85–87. 분석 `analysis/metrics.json`(사전 고정 `analyze.py`).

## 1. 결론

- **최종 candidate: NONE. compression readiness: NOT_READY(결론 C).** 두 arm 모두 사전 등록 viable gate를 통과하지 못했다.
- **FULL154**는 Base를 거의 보존했다(semantic 71.96% vs 72.95%, −1.0pp, 95% CI [−5.7, +3.7], McNemar p 0.75). 그러나 first-response structural error가 Base 41 → 52로 늘어 gate 2에서 떨어졌다.
  - dimension_target은 Base와 같다(44/89). bucket은 +3.9pp, thinking 98.5%, malformed 12 → 7.
- **JSON154**는 Base보다 분명히 나쁘다: 62.28%, −10.7pp, CI [−15.9, −5.2], McNemar p 0.0001. gate 1–4를 통과하지 못했다.
- **reasoning supervision 효과(가장 깨끗한 비교)**: 같은 154 레코드·같은 input에서 loss mask만 다른데, FULL154가 JSON154보다 **+9.7pp**다(CI [4.5, 14.6], McNemar p 0.0004).
  - dt_any +12.4pp, od_ne_dt +25.7pp(p 0.004), implicit_endpoint_verb +21.9pp, bucket +13.7pp, structural 67 → 52.
  - 같은 reasoning을 context로만 보고 JSON만 학습시키면 일반화가 크게 망가진다. reasoning text 자체를 학습시키면 그 손상이 거의 사라진다.
- **한계**: 1 epoch로는 어려운 semantic을 배우지 못했다.
  - training recall이 Base 34/154 → FULL154 57/154에 그쳤다.
  - canonical 6은 세 모델 모두 0/6이다(implicit endpoint의 dimension_target·od_role 미습득). 평가 dimension_target도 Base와 같다.
  - 새 구조 오류가 생겼다: value 없는 place → MULTIPLE_MEASURES, scope 역조회 붕괴 8/9 → 1/9.

## 2. Git / 실행 무결성

- 시작 remote HEAD `1dda74f…`. 작업 단위마다 commit → push → fetch 뒤 local = remote를 확인했다. force push·amend 0.

| 단위 | commit |
|---|---|
| final-6 review + canonical | `ae46edf` |
| reviewed_reasoning_v001 freeze(결정 85) | `f1a37dc` |
| FULL154/JSON154 dataset + loss audit | `f31e61a` |
| SFT 사전 등록(결정 86) | `3a277f9` |
| FULL154 학습 | `7af7944` |
| JSON154 학습 | `2e92931` |
| smoke | `722b4ee` |
| Base 403 평가 | `e18ee16` |
| FULL154 403 평가 | `7563adf` |
| JSON154 403 평가 | `f945c45` |
| training recall | `e4cbf04` |
| 분석 | `fe787ea` |
| 이 REPORT + 결정 87 | 이 커밋 |

- 실행 이탈 2건(결과와 무관):
  1. 첫 FULL154 학습 호출이 로그 디렉터리가 없어 shell redirect 단계에서 실패했다. 프로세스가 시작되지 않았고 GPU 작업 0이었다. 디렉터리를 만든 뒤 같은 명령으로 실행했다.
  2. 분석 스크립트는 결과 전에 commit했다. 403 결과가 나온 뒤 recall이 끝나기 전에 한 번 돌렸고, recall 뒤 같은 코드로 다시 돌린 값이 최종이다.
- 환경: GPU RTX PRO 6000 Blackwell(`GPU-d4308fbb…`, 1장), torch 2.11.0+cu128, CUDA 12.8, transformers 4.56.2, trl 0.23.1, peft 0.17.1. 모든 학습·평가 전에 HF precheck 통과(compute 프로세스 0, Ollama `/api/ps` 빈 상태). Ollama 호출 0.

## 3. reviewed_reasoning_v001

- 154/154 reasoning, 답만 있는 레코드 0. sha256 `071ccdbe…`, 순서 sha256 `8522deaa…`(`reviewed_reasoning_v001/REPORT.md`).
- 무결성 8항목 154/154: 최종 답 = frozen v006 P0 gold, 결정적 변환, 운영 경로 실행·서명 = Full gold.
- 오염: question·id 겹침 0. template·family 겹침은 모두 v005 legacy 허용분이고, 새 겹침은 0이다.

## 4. Canonical 6

- b006-05·15·20·26(implicit pickup), b006-19(implicit dropoff), b006-34('H3 셀' 경계).
- gold 재검토 6/6 CLEAR_GOLD, canonical 6/6 APPROVE_CANONICAL. reasoning_source manual_canonical, teacher null, 각 1회.
- 결과: training recall 세 모델 모두 0/6(15절). 154 중 6개(supervised token 1.2%)를 1회 보여 주는 것만으로는 이 경계를 바꾸지 못했다.

## 5. Dataset provenance

| 출처 | 레코드 | FULL154 supervised 비중 | thinking token 평균 |
|---|---:|---:|---:|
| HF 8B(R70 70, M2 10, M3 3) | 83 | 62.2% | 907 |
| 27B(P1/P2 27, remaining 38) | 65 | 36.6% | 661 |
| manual canonical | 6 | 1.2% | 162 |

- supervised token의 대부분은 8B teacher(base와 같은 모델의 자기 trace)다. 27B는 1/3, canonical은 무시할 만큼 작다.
- 그래서 FULL154의 thinking 문체는 거의 Base 그대로다(18절). 27B 문체 표본은 0/20이었다.

## 6. Token / loss-mask audit(`datasets/loss_mask_audit.json`)

- input_ids FULL154 = JSON154: 154/154(실제 tensor 비교).
- FULL154: system·user MASK, `<think>`·thinking·`</think>`·JSON·EOS LOSS. JSON154: JSON·EOS만 LOSS.
- 첫 assistant token은 154개 모두 `<think>`다(FULL154 LOSS, JSON154 MASK). `{`를 첫 token으로 학습한 레코드는 0이다.
- supervised token: FULL154 133,366(thinking 119,851 + JSON 13,515), JSON154 13,515. 입력 1,199,997.
- 길이: total p50 7,721, p95 8,671, max 8,995. max_seq_length 11,392로 truncation 0.

## 7. FULL154 training

| 항목 | 값 |
|---|---|
| recipe | base Qwen3-8B@b968826d, BF16·SDPA, LoRA r16/α32/dropout 0.05(q,k,v,o,gate,up,down), adamw_torch, lr 5e-5 linear(warmup 1), batch 1·GA 1, seed 42, 1 epoch, max_seq 11,392 |
| step | 154(예상과 같음), 440초 |
| loss | 처음 10 step 평균 0.692 → 마지막 10 step 0.312, NaN 0, OOM 0, grad norm 최대 2.19 |
| checkpoint | 39·78·117·154. primary = checkpoint-154 / 최종 adapter sha256 `fafb7f93eeaeb7824e19dbc967aba383140fd3813e4cb88661c0fe0816c00d` |

## 8. JSON154 training

| 항목 | 값 |
|---|---|
| recipe | FULL154와 같음(loss_scope만 json_only), base에서 독립 시작 |
| step | 154, 450초 |
| loss | JSON token만: 0.514 → 0.020, NaN 0, OOM 0, grad norm 최대 4.24 |
| checkpoint | primary = checkpoint-154 / adapter sha256 `b21a88088844bedafa9f730f12ff699c0baa20b4c815ba1c3ec0ffc54143d4aa` |

## 9. Thinking behavior(403, 첫 plan 호출)

| | Base | FULL154 | JSON154 |
|---|---:|---:|---:|
| emission rate | 97.0% | 98.5% | 98.8% |
| direct-JSON 첫 응답 | 0% | 0% | 0% |
| thinking 글자 p50 / p90 | 2,590 / 7,950 | 2,610 / 6,654 | 2,035 / 3,955 |
| thinking token p50 / p90 | 641 / 1,925 | 633 / 1,691 | 492 / 993 |
| 생성 token p50 / p90 | 758 / 2,055 | 725 / 1,754 | 578 / 1,073 |
| 문항 wall p50(초) | 14.2 | 20.2 | 15.0 |

- smoke 18: thinking Base 17 · FULL154 18 · JSON154 17, JSON parse 17·18·17, hard failure 0.
- p0_sft_001과 달리 두 arm 모두 thinking을 유지했다. 답만 있는 레코드가 없으면 json_only도 thinking을 없애지 않는다(p0_sft_002 R70 결과와 같다).
- JSON154는 thinking이 짧아졌다(p90 기준 −50%). 길이 감소가 품질 하락과 같이 나타났다.
- FULL154의 wall 시간 증가는 thinking 길이가 아니라 repair 호출 증가(구조 오류) 때문으로 보인다.

## 10. 403문항 전체 결과(같은 harness, 1,209 평가)

| 지표 | Base | FULL154 | JSON154 | 참고: p0_sft_001 Gold-only | Clean-Hybrid |
|---|---:|---:|---:|---:|---:|
| **semantic correctness** | **72.95%(294)** | **71.96%(290)** | **62.28%(251)** | 64.76%(261) | 65.51%(264) |
| answerable semantic | 73.63% | 71.54% | 62.92% | | |
| refusal correctness(n=20) | 60% | 80% | 50% | | |
| execution completion | 80.68% | 79.63% | 75.20% | | |
| grounding failure | 50 | 51 | 68 | | |
| first-response structural error | 41 | 52 | 67 | 35 | 18 |
| malformed JSON(first / final) | 12 / 0 | 7 / 1 | 5 / 0 | 0 | 0 |

- 셋별 semantic:

| 셋 | Base | FULL154 | JSON154 |
|---|---:|---:|---:|
| sel154 | 73.4 | 70.1 | 63.6 |
| valid98 | 64.3 | 64.3 | 52.0 |
| vendor100 | 86.0 | 86.0 | 76.0 |
| aux_test_v1 | 62.7 | 64.7 | 51.0 |

- Base는 p0_sft_001 Base와 같은 값(294/403)이다. greedy 결정성이 재현됐다.
- p0_sft_001 값은 다른 실행이라 paired 통계에 넣지 않았다.
- 이 네 셋은 과거 prompt·data 분석에 쓴 development benchmark다. final holdout이 아니다.

## 11. dimension_target / od_role

| 부분집합 | n | Base | FULL154 | JSON154 | p0_sft_001 Gold-only / Clean-Hybrid |
|---|---:|---:|---:|---:|---:|
| dt_any | 89 | 44 | 44 | 33 | 69 / 70 |
| dt_pickup | 33 | 16 | 14 | 13 | |
| dt_dropoff | 30 | 14 | 15 | 9 | |
| dt_both | 26 | 14 | 15 | 11 | |
| od_role ≠ dt(Gap B-like) | 35 | 16 | 16 | 7 | 27 / 28 |
| emd | 63 | 39 | 40 | 28 | |
| sigungu | 37 | 9 | 14 | 10 | |
| sido | 27 | 11 | 11 | 12 | |
| h3 | 11 | 6 | 3 | 4 | |

- FULL154는 dt를 Base 수준으로 유지했지만 늘리지 못했다(전이 18 ↔ 18).
- p0_sft_001(2 epoch, 답 학습)은 dt를 크게 올렸지만(+25) thinking·bucket·scope를 잃었다. 이번 1 epoch는 그 반대다.
- JSON154는 od_ne_dt에서 −25.7pp(p 0.02)다.

## 12. Bucket / aggregation

| 부분집합 | n | Base | FULL154 | JSON154 | p0_sft_001 Gold-only / Clean-Hybrid |
|---|---:|---:|---:|---:|---:|
| bucket | 51 | 41(80.4%) | 43(84.3%) | 36(70.6%) | 23 / 19 |
| aggregation | 162 | 139 | 137 | 133 | |
| order | 129 | 58 | 62 | 57 | |

- FULL154는 p0_sft_001이 무너뜨린 bucket을 보존했다(오히려 +2).

## 13. Implicit endpoint subset(`subsets.json`, 결과 전 정의)

| 부분집합 | n | Base | FULL154 | JSON154 |
|---|---:|---:|---:|---:|
| implicit_endpoint_all | 76 | 43(56.6%) | 40(52.6%) | 32(42.1%) |
| implicit_endpoint_verb | 32 | 20(62.5%) | 19(59.4%) | 12(37.5%) |
| gap_a_like(sel154 사건 표현) | 11 | 8 | 4 | 4 |

- canonical 6의 implicit endpoint 교정은 평가셋으로 옮겨지지 않았다. FULL154는 Base와 비슷하거나 조금 낮다(−3.9pp, CI [−17, +9], 유의하지 않음).
- JSON154는 verb 꼴에서 −25pp다.

## 14. Structural errors

| first_error | Base | FULL154 | JSON154 |
|---|---:|---:|---:|
| JSON_NOT_FOUND | 12 | 6 | 5 |
| INVALID_CONCEPT | 11 | 9 | 10 |
| INVALID_FACTOR | 8 | 7 | 9 |
| **MULTIPLE_MEASURES** | 2 | **17** | 15 |
| **NO_MEASURE** | 1 | **10** | 25 |
| 기타 | 7 | 3 | 3 |
| 합계 | 41 | 52 | 67 |

- 새 오류의 두 원인:
  1. **value 없는 place**: `{"subtype":"place","text":"부산"}`. 계약상 답 place(measure)로 읽혀 측정값이 둘이 된다.
     - scope 역조회 밖 문항에서 Base 3, FULL154 18, JSON154 21이다. 학습 데이터 154에는 value 없는 place가 0인데도 생겼다. 원인은 이번 phase에서 밝히지 못했다.
  2. **scope 역조회 붕괴**(n=9): Base 8 → FULL154 1 → JSON154 0. 답 place 없이 scope만 내서 NO_MEASURE가 된다.
     - v006에 scope 역조회 학습 예가 0인 알려진 공백이다(결정 67).
- malformed JSON은 줄었다(12 → 7·5).

## 15. Training recall(154, 일반화 아님)

| | Base | FULL154 | JSON154 |
|---|---:|---:|---:|
| EXACT_OR_SEMANTIC_MATCH | 34(22.1%) | 57(37.0%) | 51(33.1%) |
| STRUCTURALLY_REPAIRABLE | 42 | 13 | 20 |
| SEMANTIC_MISMATCH | 76 | 82 | 80 |
| UNPARSEABLE / REFUSAL_MISMATCH | 2 / 0 | 0 / 2 | 3 / 0 |
| thinking rate | 98.7% | 100% | 98.1% |

- 출처별 EXACT(FULL154): R70 31/70, M2 7/10, M3 0/3, 27B P1/P2 4/27, 27B remaining 15/38, canonical 0/6.
- canonical 6(세 모델 모두 SEMANTIC_MISMATCH):

| id | 기대 | Base | FULL154 | JSON154 |
|---|---|---|---|---|
| b006-05 | dt pickup | dt 없음 | dt 없음 | dt 없음 |
| b006-15 | dt pickup, 부산 od pickup | 둘 다 없음 | 둘 다 없음 | 둘 다 없음 |
| b006-19 | dt dropoff, 대구 od dropoff | dt 맞음·od 없음 | dt 맞음·od 없음 | dt 맞음·od 없음 |
| b006-20 | dt pickup, 대구 od pickup | 둘 다 없음 | 둘 다 없음 | 둘 다 없음 |
| b006-26 | dt pickup, 수성구 od pickup | 둘 다 없음 | 둘 다 없음 | 둘 다 없음 |
| b006-34 | h3·dt dropoff, 수성구 od pickup, measure text ≠ 'H3 셀' | dt 없음, od 오류 | od 맞음·dt 없음, text '내린 곳' | od 맞음·dt 없음, text '손님들' |

- b006-34의 'H3 셀' text 오류는 세 모델 모두 재현되지 않았다. dimension은 h3로 맞췄지만 dimension_target이 빠졌다.
- 학습한 문항에서도 1 epoch 뒤 정답은 37%다. 학습 목표의 습득이 약하다. implicit endpoint 경계는 전혀 습득되지 않았다.

## 16. Paired regression / improvement(403)

| 비교 | 차이 | 95% CI | McNemar p | c→w | w→c |
|---|---:|---|---:|---:|---:|
| FULL154 − Base | −0.99pp | [−5.71, +3.72] | 0.75 | 48 | 44 |
| JSON154 − Base | −10.67pp | [−15.88, −5.21] | 0.0001 | 83 | 40 |
| FULL154 − JSON154 | +9.68pp | [+4.47, +14.64] | 0.0004 | 38 | 77 |

- Base → FULL154 회귀 48문항의 FULL154 오류 tag(다중):
  - STRUCTURAL 28, AGGREGATION 8, OD_ROLE 7, GENERATION 5, BUCKET 5, REFUSAL 5, PLACE_OMISSION 4
  - 부분집합: order 20, dt_any 18, implicit_endpoint 15, emd 13
- Base → FULL154 개선 44문항의 Base 오류 tag: STRUCTURAL 20, AGGREGATION 12, REFUSAL 11, OD_ROLE 8, BUCKET 7, GENERATION 6.
- FULL154는 Base의 일부 오류(refusal, aggregation, 생성 실패)를 고쳤다. 같은 수만큼 새 구조 오류를 만들었다.
- 문항별 목록: `analysis/paired_transitions.csv`, `analysis/error_attribution.csv`.

## 17. FULL154 vs JSON154(reasoning supervision 효과)

| 부분집합 | n | JSON154 | FULL154 | 차이 | McNemar p |
|---|---:|---:|---:|---:|---:|
| 전체 | 403 | 251 | 290 | +9.7pp | 0.0004 |
| dt_any | 89 | 33 | 44 | +12.4pp | 0.06 |
| od ≠ dt | 35 | 7 | 16 | +25.7pp | 0.004 |
| implicit_endpoint_all | 76 | 32 | 40 | +10.5pp | 0.22 |
| implicit_endpoint_verb | 32 | 12 | 19 | +21.9pp | 0.09 |
| bucket | 51 | 36 | 43 | +13.7pp | 0.12 |
| structural error | 403 | 67 | 52 | −15 | |

- 같은 레코드·같은 input에서 reasoning을 supervise한 쪽이 일관되게 낫다.
- JSON154의 개선 부족은 thinking을 context로만 본 채 JSON만 맞추는 학습이 다음을 만든 것으로 보인다:
  - thinking과 무관하게 final을 내는 습관(18절 충돌)
  - 묶음 단위어 place 오류
  - thinking 길이 축소
- 이번 실험은 지금까지 reasoning supervision 효과를 가장 깨끗하게 비교한 것이다. 효과는 "Base 대비 이득"이 아니라 **"JSON-only의 손상을 막는 것"**으로 나타났다.

## 18. Reasoning 원문 분석(`analysis/reasoning_analysis.json`, 모델마다 정답 10 + 오답 10)

| 오답 10의 tag(다중) | Base | FULL154 | JSON154 |
|---|---:|---:|---:|
| reasoning-final 충돌 | 0 | 4 | 3 |
| 근거 없는 내용(지어낸 날짜·규칙) | 0 | 3 | 0 |
| 묶음 단위 실수 | 1 | 2 | 2 |
| endpoint 추론 오류 | 3 | 1 | 3 |
| aggregation 흔들림 | 2 | 2 | 3 |
| scope 역조회 누락 | 0 | 1 | 1 |

- 정답 표본: Base 10/10, FULL154 10/10 reasoning-final 일치. JSON154는 9/10(1개는 '시도'를 value 없는 place로 넣고도 채점상 match).
- FULL154 오답의 특징: reasoning 결론은 맞는 방향인데 final JSON이 그것을 옮기지 못한다.
  - t26: od_role dropoff·dimension_target both를 결론 내고 final에서 빠뜨림
  - n02: measure 하나라고 하고 final에 둘
  - h21: reasoning h3인데 final emd
- 근거 없는 날짜('20231004')와 "어제는 유효한 date가 아니다" 같은 지어낸 규칙도 있다.
- FULL154의 thinking 문체는 Base와 같다("Okay, let's tackle this query"). 27B 문체 표본 0/20.
- quality_gate_v1은 평가 판정에 쓰지 않았다.

## 19. Success gate

| gate | FULL154 | JSON154 |
|---|---|---|
| 1 overall ≥ Base − 2.0pp(70.95%) | ✅ 71.96 | ❌ 62.28 |
| 2 structural ≤ Base(41) | **❌ 52** | ❌ 67 |
| 3 dt_any ≥ Base(44) | ✅ 44 | ❌ 33 |
| 4 bucket ≥ Base − 5pp(75.4%) | ✅ 84.3 | ❌ 70.6 |
| 5 thinking ≥ 95% | ✅ 98.5 | ✅ 98.8 |
| 6 malformed ≤ Base(12) | ✅ 7 | ✅ 5 |
| viable | **No** | **No** |
| strong success | No | No |

- 통계: FULL154 − Base는 유의하지 않다(p 0.75). practical gate는 structural 하나만 실패다.
- JSON154 − Base는 유의하게 나쁘다(p 0.0001).

## 20. 최종 candidate

- **SFT candidate = NONE**(PLAN 10절 규칙: 둘 다 viable 아님).
- **compression readiness = NOT_READY.** structured pruning으로 넘어가지 않는다. `PRUNING_READINESS.md`는 candidate가 없어 만들지 않았다.
- 결론은 **C. 둘 다 Base를 충분히 보존하지 못해 아직 compression 단계로 갈 준비가 안 됐다**이다.
  - FULL154는 overall은 보존했지만 structural 회귀가 사전 gate를 넘었다.
- 사전 규칙대로 2 epoch 재학습·LR 변경·canonical 수정·prompt 수정은 이 phase에서 하지 않았다.

## 21. 한계

- 1 epoch·LoRA r16·lr 5e-5에서 학습 신호가 약했다(training recall 37%). "reasoning이 일반화에 이득이 없다"가 아니라 "이 학습량에서 Base를 넘지 못했다"는 결과다.
- 평가 403은 development benchmark이고 부분집합 n이 작다(h3 11, scope_reverse 9, refusal 20). 1–2문항 차이는 해석하지 않는다.
- value 없는 place 회귀의 원인을 밝히지 못했다(학습 데이터에는 0).
- canonical 6은 데이터의 1.2%라 효과를 따로 잴 힘이 없다. 0/6 recall은 "형식이 틀렸다"가 아니라 "노출이 부족했다"일 가능성이 높다.
- 8B self-trace가 supervised token의 62%라, FULL154는 Base 자기 분포 쪽으로 강하게 묶여 있다.

## 22. 다음 단계(각각 새 결정·사전 등록 필요)

1. **FULL 계열 학습량 실험(권장 1순위)**:
   - 같은 reviewed_reasoning_v001(바꾸지 않음)로 full_response를 2–3 epoch로 사전 등록해 잰다.
   - 근거: p0_sft_001 2 epoch는 dt를 +25 올렸다. FULL154는 thinking·bucket을 지켰고 training recall은 아직 낮다.
   - gate는 이번과 같게 두고, structural을 따로 감시한다.
2. **구조 회귀 원인 진단**(모델 호출 없이 먼저):
   - FULL154·JSON154의 value 없는 place 18·21건 원문을 읽어 thinking 속 초안과 final의 관계를 본다.
   - scope 역조회 학습 예(batch007 후보, 결정 67 범위 확인)가 필요한지 정한다.
3. **reviewed_reasoning_v002 후보**:
   - implicit endpoint는 같은 6문항을 반복하는 대신 새 문항(Gap A 동사형)을 넣는다.
   - scope 역조회·refusal 예를 넣는다.
4. JSON-only 계열은 중단을 권장한다. 같은 데이터에서 full_response보다 −9.7pp다.
5. compression(structured pruning·quantization)은 candidate가 생기기 전에는 시작하지 않는다.
6. `qwen3.8:27b`는 store에 그대로 둔다(이번 phase에서 호출 0). 삭제 여부는 사용자 결정이다.
