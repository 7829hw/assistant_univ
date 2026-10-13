# P0 SFT 1차 실험 결과(p0_sft_001)

2026-10-13. 사전 등록 `PLAN.md`(커밋 `e9a7b3f`), 결정 68. 숫자는 `analysis.json`, `items.csv`에서 왔다.

## 1. 결론

- **H1(Gold-only > Base): 기각, 반대 방향.**
  - 403문항 semantic correctness는 Base 73.0%(294)에서 Gold-only 64.8%(261)로 떨어졌다. 차이 −8.2%p, McNemar p = 0.0095.
  - malformed JSON(첫 응답 12 → 0)과 first-response structural error(41 → 35)는 줄었다.
  - 그러나 bucket·scope 역조회·vendor100에서 크게 나빠졌다.
- **H2(Clean-Hybrid ≥ Gold-only): 추가 이득 없음.**
  - 264 대 261. 차이 +0.7%p, 95% CI [−3.5, +5.0]%p, McNemar p = 0.82.
  - structural error는 35 → 18, grounding failure는 34 → 20으로 Clean-Hybrid가 적다.
- **H3(dimension_target): 지지.** 두 arm 모두 크게 좋아졌다.
  - dimension_target 문항: Base 44/89 → Gold-only 69/89, Clean-Hybrid 70/89(p < 0.001).
  - od_role ≠ dimension_target 문항: 16/35 → 27/35, 28/35(p ≈ 0.01).
- **가장 중요한 관찰: 두 SFT 모델 모두 thinking을 하지 않는다.**
  - 평가 생성 857호출 중 `<think>`가 있는 것은 0이다. Base는 487/487이다.
  - 원인은 승인 손실 범위 `json_only`(결정 24)와 답만 있는 레코드 형식의 결합이다.
    - 손실이 JSON + EOS에만 있다. Clean-Hybrid 70개 reasoning 예제의 thinking은 prompt 쪽에 있어 학습되지 않는다.
    - 학습되는 "assistant 다음 첫 token"은 답만 있는 레코드(Gold-only 154, Clean-Hybrid 84)의 `{`뿐이다.
  - 그래서 Clean-Hybrid도 추론 없이 바로 JSON을 내는 모델이 됐다. 이번 설계는 "P0-native reasoning을 학습하는 효과"를 실제로 재지 못했다. H2의 "차이 없음"은 이 조건에서의 결과다.

## 2. 데이터셋

| 항목 | 값 |
|---|---|
| 기반 | `reviewed_gold_v006_p0` 154(v005 111 + batch006 43, Gap C 0). batch006 확정(결정 68: 승인 43, 수정 7, 거부 0) |
| `legacy_conservative_family_overlap` | 16(v005, 보수 펼침 규칙에만 걸림, 소급 제거 안 함) |
| Gold-only | 154 = 답만 154 |
| Clean-Hybrid | 154 = reasoning 70 + 답만 84(trace 거부 21 + 정답 trace 없음 63) |
| 최종 답 | 두 arm 동일(Full gold → P0 canonical). 운영 경로 결과가 Full gold와 154/154 같음 |
| 손실 token | 두 arm 문항마다 동일(JSON + EOS) |

## 3. Trace 검토 결과(`TRACE_REVIEW.md`)

| 항목 | 수 |
|---|---:|
| 선택 trace | 91 |
| 승인 | 70 |
| 거부 | 21 |

- 거부 이유:
  - 묶음 단위어를 concept·장소로 만들 계획 7
  - 추론·답 충돌 7
  - 없는 규칙 3
  - unsupported 결론 2
  - Full 잔재 1
  - 반복 1
- Gap A 선택 12개 중 7개가 거부됐다. Clean-Hybrid의 Gap A reasoning 예제는 5개뿐이다.

## 4. 학습 설정(두 arm 동일, 승인 recipe)

| 항목 | 값 |
|---|---|
| base | `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218` |
| 정밀도·attention | BF16, SDPA, gradient checkpointing |
| LoRA | r16, α32, dropout 0.05, 7 projection |
| optimizer | AdamW, lr 5e-5 linear, warmup 1 step |
| batch | 1, accum 1 |
| 길이·epoch | max_seq_length 11,392, 2 epoch = 308 step |
| 저장 | 77·154·231·308 |
| seed | 42 |
| 손실 | `json_only` |
| 장비 | RTX PRO 6000 Blackwell(`GPU-d4308fbb…`), CUDA 12.8, PyTorch 2.11.0, Transformers 4.56.2 |

| arm | 시작–끝(UTC) | 시간 | 평균 loss(1 / 2 epoch) | 마지막 step loss | NaN·OOM·재시작 |
|---|---|---:|---|---:|---|
| Gold-only | 10:13:20–10:26:27 | 13분 | 0.117 / 0.011 | 0.0025 | 없음 |
| Clean-Hybrid | 10:26:38–10:40:42 | 14분 | 0.121 / 0.013 | 0.0023 | 없음 |

- 2 epoch 끝에서 train loss가 거의 0이다. 154문항을 거의 외웠다.
- checkpoint 경로·adapter sha256: `training/{arm}/checkpoints.txt`.

## 5. Checkpoint 선택

- 사전 등록대로 고정했다. 2 epoch 끝 최종 adapter(= checkpoint-308)다.
  - Gold-only `e3b76bc1…`, Clean-Hybrid `263cdae9…`
- 보호 평가셋과 selection_v1은 선택에 쓰지 않았다. 다른 checkpoint는 평가하지 않았다.

## 6. 전체 평가 결과

조건: P0 prompt(prompt hash `d7f4c12a`), HF greedy, thinking 켬, max_new_tokens 8192, 조건 계층 켬. code fingerprint `ab88a19e`.

| 지표(403문항 합) | Base | Gold-only | Clean-Hybrid |
|---|---:|---:|---:|
| semantic correctness | **73.0%** (294) | 64.8% (261) | 65.5% (264) |
| answerable semantic correctness | 73.6% | 65.5% | 66.8% |
| refusal correctness(20) | 60% | 50% | 40% |
| execution completion | 80.7% | 78.6% | 83.8% |
| grounding failure | 50 | 34 | **20** |
| grounding_ok | 261 | 234 | 244 |
| first-response structural error | 41 | 35 | **18** |
| malformed JSON(첫 / 최종) | 12 / 0 | 0 / 0 | 0 / 0 |
| 생성 token 중앙값 | 758 | 78 | 76 |
| thinking 글자 중앙값 | 2,590 | 0 | 0 |
| 생성 상한 도달 호출 | 24 | 0 | 0 |

셋별 semantic correctness:

| 셋(사용 이력) | Base | Gold-only | Clean-Hybrid |
|---|---:|---:|---:|
| sel154(P0.3 판정, ROOT_CAUSE·batch006 설계 동기) | 73.4% | 57.8% | 61.0% |
| valid98(P0.2 진단·P0.3 근거) | 64.3% | 67.3% | 64.3% |
| vendor100(prompt 개발) | 86.0% | 72.0% | 70.0% |
| aux_test_v1(P0 설계에 안 씀) | 62.7% | 66.7% | 72.5% |

- 네 셋 모두 prompt 분석 이력이 있어 independent final holdout이 아니다.
- historical reference: Full prompt HF-E의 vendor100 grounding_ok는 84다(옛 장비, 결정 9). 이번 P0 Base는 81이다. 조건이 달라 직접 비교하지 않는다.

## 7. dimension_target 분석

| 부분집합 | n | Base | Gold-only | Clean-Hybrid | Gold-only − Base McNemar p |
|---|---:|---:|---:|---:|---:|
| dimension_target 전체 | 89 | 44 | 69 | 70 | 0.0001 |
| pickup | 33 | 16 | 25 | 24 | 0.035 |
| dropoff | 30 | 14 | 26 | 26 | 0.002 |
| both | 26 | 14 | 18 | 20 | 0.39 |
| Gap A형 사건 표현(sel154 event) | 11 | 8 | 9 | 8 | 1.0 |

- Base의 dt 실패 중 많은 수는 structural(22)이었다. SFT 뒤에는 3개다.
- 21문항은 Base failed에서 두 arm 모두 match로 바뀌었다.
- Gap A형(11문항)은 Base가 이미 8/11이라 차이를 볼 수 없다.

## 8. od_role ≠ dimension_target 분석

| n | Base | Gold-only | Clean-Hybrid |
|---:|---:|---:|---:|
| 35 | 16 | 27 (p = 0.013) | 28 (p = 0.004) |

- structural error는 10 → 1, 1이다. batch006 Gap B 보강(17문항)과 같은 방향의 개선이다.
- sel154의 dt 실패 분석이 batch006 설계 동기였다는 점은 해석에 주의해야 한다(학습 문항 겹침은 0).

## 9. structural error

- first-response structural error: Base 41 → Gold-only 35 → Clean-Hybrid 18.
- malformed JSON(첫 응답): 12 → 0 → 0.
- 다만 새로 생긴 실패가 있다:
  - **bucket**(51문항): Base 41 → Gold-only 23, Clean-Hybrid 19(p < 0.001).
    - 도시 장소(대구·부산·서울)를 빠뜨리는 것(places 차이, Gold-only 9, Clean-Hybrid 16)이 많다.
    - aggregation·rollup 칸을 바꿔 쓰는 것(예: week·avg를 aggregation에 둠)도 많다.
    - v006의 bucket 문항은 23개(신규 0)뿐이다.
  - **scope 역조회**(9문항, 학습 0건): Base 8 → Gold-only 1, Clean-Hybrid 5. Gold-only는 structural error 6개다.
  - **refusal**(20문항): 12 → 10 → 8.

## 10. Gold-only vs Clean-Hybrid

| 묶음 | Gold-only | Clean-Hybrid | 차이 | McNemar p |
|---|---:|---:|---:|---:|
| 403 합 | 261 | 264 | +0.7%p | 0.82 |
| structural error | 35 | 18 | | |
| grounding failure | 34 | 20 | | |
| execution completion | 78.6% | 83.8% | | |
| dimension_target 89 | 69 | 70 | | 1.0 |
| bucket 51 | 23 | 19 | | 0.50 |
| scope 역조회 9 | 1 | 5 | | 0.13 |

- semantic correctness 차이는 없다.
- Clean-Hybrid는 구조 오류와 실행 실패가 절반 수준이다. 검증된 추론 문맥에서 JSON을 학습한 것이 출력 구조를 안정시켰을 수 있다.
- 다만 두 모델 모두 추론을 생성하지 않으므로, 이것은 "추론 학습" 효과가 아니다.
- **판정:** 이번 설정에서 reasoning trace의 추가 이득은 확인되지 않았다. Gold-only보다 나쁘지도 않다(지시 32절의 "Hybrid가 나쁨" 경우가 아님).

## 11. 한계

- 손실 `json_only`(결정 24, 사용자 선택)와 혼합 형식 때문에 두 SFT 모델은 thinking을 꺼 버렸다.
  - 평가는 thinking 켬 조건인데 모델은 추론 없이 답한다. Base(추론함)와의 비교는 "추론하는 base"와 "추론하지 않는 SFT 모델"의 비교다.
- 154문항을 2 epoch(train loss ≈ 0) 학습했다. 데이터 규모 대비 과적합 가능성이 있다. bucket·scope 역조회 등 학습 데이터가 적거나 없는 유형에서 떨어졌다.
- 평가셋 네 개 모두 이전 prompt 작업에 쓰였다. sel154는 batch006 설계의 간접 근거다.
- 평가 1회(greedy). sampling 반복은 하지 않았다.
- 이탈 2건(`PLAN_DEVIATIONS.md`). 둘 다 평가 도구 문제이고 측정 명세는 바꾸지 않았다.
  1. P0 adapter provenance 인식
  2. thinking 없는 답을 빈 응답으로 처리하던 평가 client. base 결과에는 영향이 없다.
- trace 검토는 Claude가 했다(사람 재검토 없음).

## 12. 다음 단계(제안, 시작하지 않음)

1. **추론 형식 문제를 먼저 정한다.** trace 양을 늘리기 전에 다음 중 하나를 별도 사전 등록으로 고른다.
   - (a) reasoning 예제에 `full_response` 손실을 쓰는 Clean-Hybrid. 답만 있는 예제를 어떻게 둘지도 함께 정한다.
   - (b) 모든 문항에 추론을 두는 방식. 정답 trace가 없는 63+21문항은 27B teacher 보충이 필요하고, 반입 승인이 필요하다.
   - (c) 평가도 thinking 끔 형식으로 맞추는 방식. 결정 9의 thinking 켬 원칙과 충돌하므로 사용자 결정이 필요하다.
2. **bucket·aggregation 보강.**
   - v006의 bucket 23문항(신규 0)이 부족하다.
   - 도시 장소 누락과 aggregation·rollup 칸 혼동을 다음 batch의 보강 과제로 둔다.
   - h3 편중 해소도 함께 한다.
3. scope 역조회는 학습 0건이고 SFT 뒤 크게 떨어졌다(Gold-only 1/9). future-data 문제로 계속 둔다.
4. 이번 결과로 STRUCTURALLY_REPAIRABLE 추가, DPO, P0 수정, P0.4, pruning을 시작하지 않는다.
