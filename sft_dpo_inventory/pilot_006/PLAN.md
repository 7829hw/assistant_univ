확정본, 사용자 승인 전, 고정 전 — 결정 157(자동 진행)의 조건 "미결 0"이 맞지 않아 고정·학습 전에 멈춤(9절 미결 1)

# pilot_006 계획(Full vs Partial, SFT만) — 확정본

작성: 2026-10-16(세션 2c 최종 후보) → 2026-10-17(세션 2d 확정본). 바탕: 결정 106–157(`../DECISIONS.md`), PROTOCOL_v5. 이전 판: `PLAN_DRAFT.md`(기록).
고정은 `freeze.py --rc RC3`로 한다. 이 세션에서는 `freeze.py --rc RC3 --dry-run`까지 했다(`FREEZE_DRYRUN.json`).

## 0. 실험 질문

pilot_005 수준의 학습(V1 recipe, SFT만)에서 Partial target을 학습한 모델(P)이 Full target을 학습한 모델(F)과 의미 정확도가 비열등하면서,
dt·조용한 오답·구조 오류를 악화시키지 않고 생성 비용(지연)을 줄이는가.

## 1. 데이터(확정값: RC3)

| 항목 | 값 |
|---|---|
| 빌드 | `build/RC3`(`build/build6rc.py --label RC3 --teach-variant v3b`), 상세 `build/RC3/README.md` |
| 질문 | 386(두 arm 질문 목록 sha256 `6b06bb2cbc1ff91dccf90432327c02d814a6c77fbe6e55c1b006991c48e4b773`) |
| 레코드 | Full 1,861(`sft_train.jsonl` sha256 `756160fe2d43c4b3d57a1c8ac9caa7a21f9ee13903cec0d540564bd7924cff71`), Partial 1,826(`00ce1f9e966773b64167a623cd2cd499cd124f7c7536a10b82150d065da3ab07`) |
| 출처 | teacher(v3b, `full_response`) 836 + 8b 자체(`json_only`) Full 1,025 / Partial 990. 손실 token teacher 비율 Full 71.3%, Partial 81.0%(pilot_004·005 81.8%) |
| teacher | 결정 149–152: v3b(L2 끌어냄 10/10, (iii) trace 통과 148/160), TEACH 245질문 × 8 → 통과 1,846, 질문당 최대 4 |
| 8b 자체 | J1·J6·J8·J9·S32·S64·S128·J10·J12·J13(vLLM BF16 base, 승인 gold 판정, 결정 133·146) |
| 승인 corpus | v2 580레코드(`../pilot_006_prep/approved/approved_train_v2.jsonl` sha256 `0482127e…`) |
| 규칙 | 결정 86 출처별 손실 범위, 유형 상한 τ 0.09(결정 88·92), 평가 셋 강한 겹침 제외(selection_v1·v2, valid98, aux, holdout), 업체 100 보고만(결정 143), max_seq_length 12,288(결정 125) |
| 검사 | 두 arm dry-run·tokenizer-check·출처별 손실 token·마스크 audit 통과(`build/RC3/checks_summary.json`) |

## 2. recipe(확정값)

| 항목 | 값 | 근거 |
|---|---|---|
| base | Qwen/Qwen3-8B@b968826d, BF16, SDPA, gradient checkpointing | pilot_005 V1 |
| LoRA | r16 / α32 / dropout 0.05, 7개 projection | pilot_005 V1 |
| 최적화 | AdamW lr 5e-5, warmup 1 step, batch 1, accum 1 | pilot_005 V1 |
| max_seq_length | 12,288 | 결정 125 |
| 길이 | 2 epoch, epoch 1·2 저장, **epoch 1 고정**, epoch 2는 보고만 | 결정 112·154 |
| seed | **두 arm 모두 43과 20261016 → 학습 넷 F-s43, P-s43, F-s1016, P-s1016** | 결정 154 |
| 손실 범위 | by_source(teacher `full_response`, 8b `json_only`) | 결정 86·107 |
| DPO | 없음 | 결정 110 |
| target | F = `render_full`(prompt 87048d0c), P = `render_partial`(P0.3 system `8b157c9a…`), 학습 코드 `grounding_target` 분기(`94c0fb6`) | 결정 111 |
| 설정 파일 | `run3/configs/pilot006_{F43,P43,F1016,P1016}.yaml`(`run3/make_jobs.py`, pilot_005 V1 config에서 데이터·grounding_target·seed·12,288·출력만 바꿈) | |
| checkpoint | epoch 1 = `checkpoint-1861`(F) / `checkpoint-1826`(P), epoch 2 = 두 배 | batch 1·accum 1 |
| 감시 | P thinking p90이 base 대비 30% 넘게 줄면 보고 | 결정 107 |

## 3. 평가 셀(PROTOCOL_v5: vLLM 0.30.0 BF16, flashinfer, LoRA 비병합, 동시 요청 8, 17,408)

| 셀 | 모델 | 셋 | k | 근거 |
|---|---|---|---:|---|
| base(기존) | vLLM-base | selection_v2(B1 + X2), holdout(B2), valid98(B3), aux(B4) | 4·8 | 결정 117·128 |
| base 셋째 | vLLM-base | selection_v2 | 4 | 결정 134 → selection_v2 base k=12 |
| e1 네 모델 | F-s43, P-s43, F-s1016, P-s1016 | 주 셋 151(selection_v2 98 + holdout 53) | 4 | 결정 154 |
| e1 s43 두 모델 | F-s43, P-s43 | valid98, aux_test_v1 k=4, 업체 100(개발 셋) k=8 | 4·8 | 결정 154 |
| e2(보고만) | 네 모델 | selection_v2 | 4 | 결정 112 |
| 지연 창 | base·F-s43 e1·P-s43 e1 | 고정 30문항 순차, 한 GPU, 다른 둘 비움 | 1 | 결정 113·154, `latency/latency6.py` |

- 작업 표: `run3/jobs.json`(24 작업, `scheduler6e.py`). selection_v2는 n33 포함·제외 둘 다 보고(결정 104).
- 결정 140 family(scope 이름 조회)와 결정 155 부분집합(implicit endpoint, 장소 이름 조회)은 셋마다 따로 표(진단, Gate 아님).
- Ollama production 측정 없음(결정 137).

## 4. 판정(`gates/compute_gates.py`, seed 묶음 커밋 `ed1b7c8`)

- **주 판정**: 문항별 정답률 = 두 seed × k=4(8표본) 평균, 문항 단위 쌍 bootstrap 10,000회 `default_rng(20261109)`(결정 154). seed별 결과도 보고하고,
  두 seed의 선행 조건·Gate A–D 통과가 갈리면 "seed에 민감"으로 표시(채택을 막지 않음).
- 선행 조건(arm마다 대 base, 주 셋 151): ok 차이 CI 하한 > 0, U 차이 CI 하한 ≤ 0(결정 112). base는 selection_v2 k=12, holdout B2 k=4.

| Gate | 통과 조건 | 근거 |
|---|---|---|
| A | P − F grounding_ok 95% CI 하한 ≥ −5%p | 결정 109 |
| B | P − F dt_missing CI 하한 ≤ 0 | 결정 153 |
| C | P − F answered_wrong CI 하한 ≤ 0 | 결정 153 |
| D | (1) MULTIPLE_MEASURES + NO_MEASURE P − F CI 하한 ≤ 0 그리고 (2) 구조 오류·grounding failure·repair 중 하나 이상 CI 상한 < 0 | 결정 153 |
| E | (1) P·F(s43) 각각 지연 중앙값 비 ≤ 1.5, (2) 최종 JSON token 중앙값 P ≤ 0.7·F, (3) 생성 token 중앙값 P ≤ F | 결정 113·154 |

- 채택: A–E 모두 통과. 반폭이 마진보다 크면 Gate A 불통과는 "판정 불가".
- 최종 판정(채택 후보 1개 대 base, k=8): `protected_final_v1`(120문항, 사람 작성·해시 고정, 학습 시작 조건 아님 — 결정 156). Claude는 판정 전에 해시 고정만 확인한다.

## 5. 세션 3 GPU 일정표(실측 기준)

근거: SFT step 5.9초(pilot_004 평균)–7.5/8.3초(M1b 12,288 상한, F/P). selection_v2 k=4 셀 22–27분, holdout 8–12분, valid98 21–29분, aux 15–16분,
업체 100 k=8 약 50분, 지연 셀 약 13분, 서버 기동 3–5분. 학습 step: F 3,722(2 epoch), P 3,652.

```text
작업          | GPU      | 시작 → 끝(T = 고정 시각)            | 근거
TR_F43        | 0        | T → T+6.1–7.8h(epoch 1 ≈ T+3.1–3.9h)  | 3,722 × 5.9–7.5초
TR_P43        | 1        | T → T+6.6–8.4h(epoch 1 ≈ T+3.3–4.2h)  | 3,652 × 6.5–8.3초
TR_F1016      | 2        | T → T+6.1–7.8h                       | 같은 seed 짝은 같은 시간대(F43·P43)
TR_P1016      | 처음 빈 GPU | ≈T+6.1–7.8h → T+12.7–16.2h          | 결정 154 배치
BASE3         | 그다음 빈 GPU | ≈T+6.6–8.4h, 25분                   | 결정 134
E1 s43(F·P)    | 빈 GPU     | ≈T+7–9h → +2.1h × 2                  | 주 셋 + valid98 + aux + 업체 100
E1 s1016·E2   | 빈 GPU     | ≈T+9–13h                             | 주 셋 37분 × 2, e2 25분 × 4
LAT           | 하나(다른 둘 비움) | 모든 셀·학습 뒤 ≈T+13–16.5h, 40분 | 결정 113
```

- 예상 끝 약 T+14–17h. 유휴: 학습 넷이 GPU 세 장을 쓰는 동안 평가는 기다린다(작업 하나 = GPU 하나). 지연 창 40분 동안 다른 두 GPU는 비운다.

## 6. PLAN_DRAFT·최종 후보(세션 2c) 대비 바뀐 것

| 항목 | 세션 2c 최종 후보 | 확정본 | 근거 |
|---|---|---|---|
| 데이터 | RC2(teacher 0, 280질문) | RC3(386질문, teacher 836/arm) | 결정 149–152 |
| teacher | 없음 | v3b(trace 단위 기준, 읽기 검사 통과) | 결정 149–151 |
| 8b 보강 | S64까지 | + S128 | 세션 2d 지시 2.2 |
| seed | 20261016 하나 | 43·20261016 두 개, 학습 넷 | 결정 154 |
| 평가 셀 | F·P e1 각 하나 | 네 모델 주 셋, s43만 개발 셋 | 결정 154 |
| 판정 | seed 하나 | seed 묶음 주 판정 + seed별·민감 표시 | 결정 154 |
| Gate B·C·D | 결정 번호 없음 | 결정 153 | 결정 153 |
| protected_final_v1 | 미결 | 학습 조건 아님, 판정 전 해시 확인 | 결정 156 |
| H4 부족분 | 미결 | TEACH로 채운 만큼, 나머지 수용·진단 보고 | 결정 155 |
| 일정 | 2 학습 | 4 학습(5절) | 결정 154 |

## 7. 고정 대상(`freeze.py`)

PLAN.md, gate 도구, 지연 도구, 빌드·검사 도구, 손실 token·마스크 검사, 승인 corpus v2·holdout·holdout gold, 학습 config 원본, 판정 도구, teacher 모듈, protected_final 명세,
PROTOCOL_v5, RC3 데이터(두 arm `sft_train.jsonl`·manifest, build_summary·lengths·questions·checks_summary), `run3/configs/*.yaml`·`run3/jobs.json`·`scheduler6e.py`,
지문(791c4a68, 87048d0c, 8b157c9a). dry-run: `FREEZE_DRYRUN.json`.

## 8. 결정 번호 정리

PLAN_DRAFT·최종 후보의 결정 항목은 세션 2c 최종 후보 8절과 같고, 세션 2d에서 teacher(149–152), Gate B·C·D(153), seed(154), H4(155), protected_final_v1(156),
세션 끝 동작(157)이 더해졌다.

## 9. 미결

1. **teacher trace의 받은 결론 의식 문장**(세션 2d에서 처음 확인, `teacher/TEACH_READ.md` 3절): RC3 teacher 레코드의 69%(Full 575/836, Partial 582/836)
   thinking에 "결론과 일치한다", "결론을 확인", "conclusion" 같은 문장이 있다. 학습 때는 결론이 입력에 없어, 모델이 없는 입력을 가리키는 문장을 배울 수 있다.
   선택지: (a) RC3 그대로 고정·학습, (b) 엄격 필터(통과 1,846 중 535 trace, teacher가 남는 질문 198/245) 판 RC3s, (c) 확인 문단만 기계적으로 지운 판.
   권고: (c)를 시험해 보고(원문 수정 규칙 확인 필요), 아니면 (a). (b)는 약점 문항 47질문을 잃는다.
   이 항목 때문에 결정 157의 "미결 0" 조건이 맞지 않아 고정·학습을 하지 않았다.
