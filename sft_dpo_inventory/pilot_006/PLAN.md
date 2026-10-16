최종 후보, 사용자 승인 전, 고정 전

# pilot_006 계획(Full vs Partial, SFT만) — 최종 후보

작성: 2026-10-16(세션 2c P8). 바탕: `PLAN_DRAFT.md`(세션 1–2b), 결정 106–148(`../DECISIONS.md`), PROTOCOL_v5(`../vendor100_protocol/PROTOCOL_v5.md`).
고정은 사용자가 이 문서를 승인한 뒤 세션 3에서 `freeze.py --rc <RC>`로 한다(결정 148). 이 세션에서는 `freeze.py --dry-run`까지만 했다(`FREEZE_DRYRUN.json`).

> **먼저 볼 것 — 미결 1(teacher)**: teacher 확인(T0' v2, T0'' v3a·v3b)이 모두 미리 정한 규칙에 못 미쳐 teacher 본 수집을 하지 않았다. 그래서 RC2는 **teacher 0**이다
> (결정 86 출처 구성, pilot_004·005 teacher 손실 token 81.8%와 다름). 이 문서의 데이터 항목은 RC2를 적어 두었지만, teacher를 넣은 RC3로 갈지 RC2로 학습할지는 사용자 결정이다(9절 1).

## 0. 실험 질문

pilot_005 수준의 학습(V1 recipe, SFT만)에서 Partial target을 학습한 모델(P)이 Full target을 학습한 모델(F)과 의미 정확도가 비열등하면서,
dt·조용한 오답·구조 오류를 악화시키지 않고 생성 비용(지연)을 줄이는가.

## 1. 데이터(확정값: RC2)

| 항목 | 값 |
|---|---|
| 빌드 | `build/RC2`(`build/build6rc.py --label RC2`, 커밋 `7868608`), 상세 `build/RC2/README.md` |
| 질문 | 280(두 arm 질문 목록 sha256 `ff9068ac4cedcbb6af7ecd5e1b657a91bb21e8fee4b1d2355898baf846228f6c`) |
| 레코드 | Full 885(`sft_train.jsonl` sha256 `7f0c6502…`), Partial 896(`94eac6bc…`) — 모두 8b 자체 `json_only`, teacher 0 |
| 승인 corpus | v2 580레코드(`../pilot_006_prep/approved/approved_train_v2.jsonl` sha256 `0482127e…`; trunk 131, pg 154, aug300 207, batch007 27, batch008 10, batch009 51) |
| holdout | augmentation_holdout_v1 53(고정값 `69d3af19…`/`23ee1bc8…`, 평가 전용) |
| 규칙 | 결정 86 출처별 손실 범위, 유형 상한 τ 0.09(결정 88·92), 평가 셋 강한 겹침 제외(selection_v1·v2, valid98, aux, holdout), 업체 100 겹침은 보고만(결정 143), max_seq_length 12,288(결정 125) |
| 검사 | 두 arm dry-run·tokenizer-check·출처별 손실 token·마스크 audit 통과(`build/RC2/checks_summary.json`) |

## 2. 두 arm recipe(확정값)

| 항목 | 값 | 근거 |
|---|---|---|
| base | Qwen/Qwen3-8B@b968826d, BF16, SDPA, gradient checkpointing | pilot_005 V1 |
| LoRA | r16 / α32 / dropout 0.05, 7개 projection | pilot_005 V1 |
| 최적화 | AdamW lr 5e-5, warmup 1 step, batch 1, accum 1 | pilot_005 V1 |
| max_seq_length | **12,288** | 결정 125 규칙 3(M1b, `build/LENGTH_FINAL.md`) |
| 길이 | 2 epoch, epoch 1·2 저장, **epoch 1 checkpoint 고정**, epoch 2는 보고만 | 결정 112(D7) |
| seed | **20261016**, 두 arm 같음 | PLAN_DRAFT 9.3(pilot_005 V1의 43에서 바꿈) |
| 손실 범위 | by_source(teacher `full_response`, 8b 자체 `json_only`) | 결정 86·107(D2) |
| DPO | 없음 | 결정 110(D5) |
| target | F = `render_full`(prompt 87048d0c), P = `render_partial`(P0.3 system `8b157c9a…`), 학습 코드 `grounding_target` 분기(`94c0fb6`) | 결정 111(D6) |
| 설정 파일 | `training/configs/qwen3_8b_t2pc_thinking_pilot005_v1_sft.yaml`에서 데이터·max_seq_length·seed·출력만 바꾼 두 파일(세션 3 고정 때 커밋) | |
| 감시 | P thinking p90이 base 대비 30% 넘게 줄면 보고 | 결정 107 |
| 실행 | 한 arm = GPU 1장, `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` | 결정 105·114, 규칙 11 |

## 3. 평가 셀(PROTOCOL_v5: vLLM 0.30.0 BF16, flashinfer, LoRA 비병합, 동시 요청 8, `--max-model-len` 17,408)

| 셀 | 모델 | target | 셋 | k | 역할 | 근거 |
|---|---|---|---|---:|---|---|
| base(기존) | vLLM-base | Full | selection_v2(B1+X2 = k=8), holdout(B2), valid98(B3), aux(B4) | 4·8 | 기준 | 결정 117·128 |
| **base 셋째** | vLLM-base | Full | selection_v2 | 4 | F·P와 같은 날 → selection_v2 base k=12 | 결정 134(G4) |
| **F e1** | pilot_006 Full epoch 1 | Full | 주 셋 151(selection_v2 98 + holdout 53), valid98, aux, 업체 100(개발 셋) | 4(업체 100 8) | 학습된 Full | 결정 108·109 |
| **P e1** | pilot_006 Partial epoch 1 | Partial | 같음 | 같음 | 핵심 실험군 | |
| F e2·P e2 | epoch 2 | | selection_v2 | 4 | 보고만 | 결정 112 |
| 지연 | base·F e1·P e1 | | 고정 30문항 순차, 한 GPU, 다른 둘 비움 | 1 | Gate E(1) | 결정 113, `latency/latency6.py`(`50d5088`) |

- 참고 셀(판정 없음, 이미 잼): R2(P0.3 base), R3(pilot_005 v1_step467). holdout 셀(J2·B2·R2h·R3b)은 F·P 판정 때까지 봉인.
- selection_v2는 n33 포함·제외 둘 다 보고(결정 104, batch007 학습).
- **결정 140 family(scope 이름 조회) 문항**: selection_v2·holdout·valid98·aux 각각에서 이 family 문항의 결과를 따로 표로 보고한다(판정에는 전체 결과를 쓴다).
- Ollama production 측정(E·27b 참고 셀, Ollama 지연, 업체 100 Ollama)은 하지 않는다(결정 137).

## 4. 판정(도구 `gates/compute_gates.py`, 커밋 `d501d7b`·채점 등록 `18202c6`; 문항 단위 쌍 bootstrap 10,000회 `default_rng(20261109)`)

### 4.1 arm별 선행 조건(결정 112 D7, 보정 없음)

각 arm(e1) 대 base, 주 셋 151, k=4: grounding_ok 차이 95% CI 하한 > 0, 그리고 U 비율 차이 95% CI 하한 ≤ 0. F가 못 넘으면 F vs P는 보고만.

### 4.2 F vs P Gate(주 셋 151, 같은 표본; selection_v2만의 결과도 보고)

| Gate | 통과 조건 | 근거 |
|---|---|---|
| A 의미 비열등 | P − F grounding_ok 95% CI 하한 ≥ −5%p | 결정 109(D4) |
| B dimension_target | P − F dt_missing 95% CI 하한 ≤ 0 | 계획서 v2 11절·PLAN_DRAFT 5.3(결정 번호 없음 — 미결 2) |
| C 조용한 오답 | P − F answered_wrong 95% CI 하한 ≤ 0 | 같음 |
| D 구조 | (1) MULTIPLE_MEASURES + NO_MEASURE: P − F CI 하한 ≤ 0, 그리고 (2) 구조 오류·grounding failure·repair 셋 중 하나 이상 CI 상한 < 0 | 같음 |
| E 효율 | (1) P와 F 각각 고정 30문항 base 대비 중앙값 비 ≤ 1.5, (2) 최종 JSON token 중앙값 P가 F보다 30% 이상 적음, (3) 생성 token 중앙값 P ≤ F | 결정 113(D8) + 계획서 v2 |

- 채택: A–E 모두 통과. 반폭이 마진보다 크면 Gate A 불통과는 "판정 불가"로 보고(W8 검정력: 151문항 반폭 약 2.6–4.2%p).
- 최종 판정(채택 후보 1개 대 base, k=8, 한 번): `protected_final_v1`(120문항, 사람 작성, 결정 135·138; 도구 `protected_final/`). 작성 상태는 미결 3.

## 5. 세션 3 GPU 일정표(세션 2·2b·2c 실측)

근거: selection_v2 k=4 셀 22–27분(B1 24.9, X2 22.2, R3a 26.8), holdout 8–12분, valid98 21–29분, aux 15–16분, 업체 100 k=8 약 50분(selection_v2 속도),
SFT step 5.9초(pilot_004 평균)–7.5/8.3초(M1b 12,288 상한, Full/Partial), 지연 셀 약 13분(pilot_005 813초), teacher 27b 7.5초/trace(T0'' 320 trace 40.2분).
RC2 레코드: Full 885, Partial 896 → 2 epoch 1,770 / 1,792 step. T3 = PLAN 고정 시각.

```text
ID  | 작업                                                    | 의존           | 예상(근거)                                    | GPU
V1  | F 학습 2 epoch(RC2)                                     | 고정           | 1,770 × 5.9–7.5초 ≈ 2.9–3.7h                  | 0
V2  | P 학습 2 epoch(RC2)                                     | 고정           | 1,792 × 6.5–8.3초 ≈ 3.2–4.1h                  | 1
V3  | base 셋째 selection_v2 k=4(결정 134)                     | 없음           | 25분                                          | 2
V4  | F e1 셀: 주 셋 151 + valid98 + aux k=4, 업체 100 k=8      | V1 epoch 1(≈T3+1.6h) | 25 + 12 + 25 + 15 + 50 ≈ 2.1h            | 2(V3 뒤)
V5  | P e1 셀: 같음                                           | V2 epoch 1(≈T3+1.8h) | ≈ 2.1h                                   | V1이 끝난 GPU 0(≈T3+3.7h)
V6  | F e2·P e2 selection_v2 k=4(보고)                         | V1·V2          | 각 25분                                       | 끝난 GPU
V7  | 지연 창: base·F e1·P e1(고정 30문항, 한 GPU, 다른 둘 비움)  | V4·V5          | 3 × 13분 ≈ 40분                               | 하나(≈T3+6h)
```

- 예상 끝: 약 T3+6.5h. 유휴: GPU 2는 V3 뒤 F epoch 1 저장까지 약 1.2h 의존 대기, 지연 창 40분 동안 다른 두 GPU는 비운다(결정 113).
- teacher를 넣는 경우(9절 1): 그 앞에 지시 확인 약 40분(두 안 × 160 trace) + TEACH 245질문 × 8 × 7.5초 ≈ 4.1h(Ollama GPU) + RC3 빌드·검사 약 10분이 붙고,
  학습 레코드가 늘어 V1·V2가 각각 약 1.5–2h 길어진다.

## 6. PLAN_DRAFT 대비 바뀐 것

| 항목 | PLAN_DRAFT | 이 문서 | 근거 |
|---|---|---|---|
| 데이터 | 추정 약 1,400–1,500레코드, teacher 포함 | RC2 885/896, teacher 0 | 결정 131·144(T0'·T0'' 불통과) |
| 승인 corpus | 초안 기준 415질문 | v2 580레코드(473질문) | 결정 130·139–142 |
| max_seq_length | 11,392 | 12,288 | 결정 125 |
| 8b 자체 표본 | pilot_004 판(HF) + J1·J6 | vLLM 표본만(J1·J6·J8·J9·S32·S64·J10·J12·J13), pilot_003 HF trace 안 씀 | 결정 133 |
| teacher | pilot_004·pg teacher 재사용 가능 | 이전 teacher 안 씀, 표현 중립 v3 지시로만(아직 없음) | 결정 132·145 |
| base | B1 + X2 | + 세션 3 셋째 셀(k=12) | 결정 134 |
| 업체 100 겹침 | 빌드에서 뺌 | 보고만 | 결정 143 |
| scope 이름 조회 | 결정 120으로 모두 뺌 | family 예외 + 따로 보고 | 결정 140·141 |
| Ollama production 셀 | (없었음) | 하지 않음 명시 | 결정 137 |
| protected_final_v1 | 약 100문항 계획 | 120문항·k=8, 사람 작성(이름 기록 안 함), 도구 준비 | 결정 135·138 |
| seed | 초안 20261016 | 20261016 확정값으로 적음 | PLAN_DRAFT 9.3 |
| 일정 | 세션 1·2 추정 | 5절(실측) | |

## 7. 고정 대상(`freeze.py`)

PLAN.md, gate 도구, 지연 도구, 빌드 도구·검사 도구, 손실 token·마스크 검사, 승인 corpus v2·holdout·holdout gold, 학습 config 원본, 판정 도구, teacher 모듈, protected_final 명세,
PROTOCOL_v5, RC 데이터(두 arm `sft_train.jsonl`·manifest, build_summary·lengths·questions·checks_summary), 지문(791c4a68, 87048d0c, 8b157c9a). dry-run 결과: `FREEZE_DRYRUN.json`.

## 8. 결정 번호 정리(PLAN_DRAFT 4절·9절의 결정 항목)

| PLAN_DRAFT 항목 | 결정 |
|---|---|
| Partial 생성 길이 한도 | 117(E2) |
| aug300·batch007·batch008·pg 검토 | 119–121, 130(G0), 139(K2) |
| W4 6(b) | 118(E3) |
| J5S' 판정 | 122(F1) |
| 학습 길이 | 125(F4) |
| 27b guard | 126(F5) |
| 참고 셀 | 128(F7) |
| teacher 지시·범위 | 131·132(G1·G2), 144·145(K7·K8) |
| 8b 표본 | 133(G3), 146(K9) |
| base 셋째 | 134(G4) |
| protected_final_v1 | 106(D1), 135(G5), 138(K1) |
| 업체 100 | 106(D1), 143(K6) |
| scope 이름 조회 | 140·141(K3·K4) |
| aug300-348 | 142(K5) |

## 9. 미결(사용자 결정)

1. **teacher**: (a) RC2(teacher 0)로 학습 / (b) 지시를 다시 고쳐(`teacher/T0V3_REPORT.md` 제안: "부근" 등 주변 표현, 영어 생각 금지 보강, v3b 다섯 줄 뒤 문장 금지)
   새 20문항으로 확인 → TEACH → RC3 / (c) (a)·(b) 검사를 학습 필터로만 쓰는 규칙으로 바꿔 v3a로 수집. (b)·(c)는 세션 3 앞에 약 5h가 붙는다.
   권고: (b). RC2는 약점 문항(장소 이름 조회 18, Partial 정답이 없는 문항)이 빠져 Partial 약점을 학습할 재료가 없다(H4: 장소 이름 조회 1/30).
2. Gate B·C·D의 기준은 계획서 v2·PLAN_DRAFT 5.3에만 있고 결정 번호가 없다. 이 문서의 표대로 사전 등록할지 확인.
3. `protected_final_v1` 작성(사람, 120문항) — 작성·검사·해시 고정이 채택 후보 판정 전에 끝나야 한다.
4. H4 부족분(최소 30): implicit endpoint 16, 장소 이름 조회 1 — teacher로 채울지, 받아들일지.
5. seed 20261016 확정(pilot_005 V1은 43).
