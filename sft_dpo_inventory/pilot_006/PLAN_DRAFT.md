초안, 사용자 승인 전

# pilot_006 계획 초안(Full vs Partial, SFT만)

작성: 2026-10-15(pilot_006 준비 세션 1, W9), 갱신 2026-10-15(세션 1b: 결정 116–121 = E1–E6 반영, 2a·2b),
갱신 2026-10-16(세션 2 C12: 결정 122–129 = F1–F8 반영, C1 base 권고, C9 R2 참고, C11 학습 길이, T0·C5 제안, 세션 3 일정표·시작 조건 = 6절·9절),
갱신 2026-10-16(세션 2b H9: 결정 130–137 = G0–G7, R0·R1, T0' 불통과, 8b 표본 보강, batch009, RC1 = **10절**, 세션 3 일정표 = 6.2절, 시작 조건 = 9절 다시 씀). **고정하지 않았다.** 학습·teacher 수집을 시작하기 전에 사용자가 고치고 확정한다.
따르는 것: `CLAUDE.md`(SFT/DPO 규칙 1–15), `../DECISIONS.md`(결정 1–115, 특히 106–114 = D1–D9), `../vendor100_protocol/PROTOCOL_v5.md`(v4·v3를 이어받음),
계획서 v2(`../pilot_006_prep/inputs/two_branch_integration_and_300_dataset_plan_v2.md`, 지시 3절 보정이 우선).

## 0. 실험 질문

pilot_005 수준의 학습(V1 recipe, SFT만)에서 Partial target을 학습한 모델(P)이 Full target을 학습한 모델(F)과 의미 정확도가 비열등하면서,
dt·조용한 오답·구조 오류를 악화시키지 않고 생성 비용(지연)을 줄이는가.

## 1. 데이터 구성(추정, `plan_estimates.py` → `plan_estimates.json`)

| 출처 | 질문 | canonical 검증 사슬 통과 | 상태 |
|---|---:|---:|---|
| trunk pilot_004 판(`reviewed_gold_v006_t2pc`) | 131 | 131 | 승인됨 |
| pg `reviewed_reasoning_v001`(trunk와 겹치는 v005 111 제외, pg batch006 Gap A·B) | ~~47~~ **40** | 40 | pg 승인 상태 그대로(trunk 승인 아님, 사용자 확인 필요). pg batch006 43 + v005 질문 중 trunk pilot_004 판에 없는 4(b004-19·35, b005-11·60) |
| aug300 train(결정 106 → 결정 119 E4 적용) | ~~220~~ **207** | 207 | 초안(검토 필요). E4: 134·135와 평가·보호 셋 강한 겹침 11건 제외, 학습 데이터와만 겹쳐 병합할 문항 0 |
| batch007 | 27 | 27 | 초안(검토 필요) |
| batch008 남은 후보 | 10 | 10 | 초안(검토 필요). 결정 120(E5) 재분류: 되살림 0, 계속 뺌 18, 분류 밖 2(b008-12·34, 보고) |
| **합계(모두 승인될 때 최대)** | ~~435~~ **415** | 415 | E6: pg EDIT_REQUIRED 7행(pg-b006-09·17·21·26·27·33·39)은 사람 검토 전까지 뺌 |

- 유형 상한(결정 88·92, τ 0.09, 결정 92 예외 = trunk 실차 대조 + batch007, 51질문): 상한 전 TV 0.145 → 상한 뒤 예상 **약 402질문, TV 0.111**(세션 1의 435 기준; E4·E6 뒤 415 기준으로 다음 세션에 다시 계산)
  (예외 때문에 0.09를 넘는다. 결정 92대로 그 값을 기록한다). 상한이 줄이는 칸: "집계 있음·dim 없음" 160 → 127, "집계 없음·dim 있음·dt 있음" 비예외 115 → 102 등.
- 두 arm의 질문 목록은 sha256까지 같아야 한다(계획서 v2 7절). Full·Partial target은 같은 canonical semantics에서 렌더링한다(W5, 466/466 + aug300 271/273 통과).
- 평가 셋 겹침 검사: W6 기준(강한 겹침 = 질문·Jaccard ≥ 0.5·같은 grounding)과 결정 54식 약한 겹침 기록. aug300 제안 15건(`../pilot_006_prep/aug300/status_proposals.json`)은 사용자 결정 뒤 반영.
- 레코드: 질문당 teacher ≤ 4(결정 48·50), 8b 자체 정답 표본(J1·J6), 결정 86 출처별 손실 범위(D2). pilot_004 판은 질문당 약 3.6레코드였다 → **SFT 레코드 약 1,400–1,500 예상**.

## 2. 두 arm recipe(D2·D5·D7, pilot_005 V1 설정)

| 항목 | 값 |
|---|---|
| base | Qwen/Qwen3-8B@b968826d, BF16, SDPA, gradient checkpointing |
| LoRA | r16 / α32 / dropout 0.05, 7개 projection |
| 최적화 | AdamW lr 5e-5, warmup 1 step, batch 1, accum 1, **max_seq_length 12,288**(결정 125 규칙 3, C11 `build/LENGTH_FINAL.md`; pilot_005 V1의 11,392에서 이 값만 바꿈) |
| 길이 | 2 epoch, epoch 1·2 저장. **epoch 1 checkpoint를 미리 고정**(D7), epoch 2는 보고만 |
| seed | 하나, 두 arm 같게(초안: 20261016) |
| 손실 범위 | 결정 86 by_source(teacher `full_response`, 8b 자체 `json_only`) 두 arm 공통 |
| DPO | 없음(D5) |
| target | F = `render_full`(trunk Full 계약, prompt 87048d0c), P = `render_partial`(P0 계약, prompt P0.3 결합 sha256 `8b157c9a…`) |
| 학습 코드 | trunk에 `grounding_target` 분기 하나를 더했다(세션 2 C6, `94c0fb6`, `tests/test_trainer_grounding_target.py`): data의 `grounding_target: partial`이면 system prompt P0.3과 Partial 답 JSON 검사를 쓴다. Full은 바뀌지 않음 |
| 감시 | P arm thinking p90이 base 대비 30% 넘게 줄면 보고(D2). base p90: selection_v2 1,313, 지연 30문항 1,101 |

## 3. 다음 세션 trace 수집 계획(승인 뒤)

> 세션 2 갱신: J6(Partial 8b 자체 표본 401질문 × 9)은 세션 2에 끝났다(결정 122 F1). 판정(C3): draft 181/234, pg 85/147 질문에 정답 표본.
> 두 arm 중 하나라도 정답 표본이 없는 질문 **135**(J1 103 ∪ J6 115, 겹침 83)가 teacher 필수 대상이다. trunk 131질문은 J1·J6 대상이 아니어서
> **Partial 8b 자체 표본이 없다**(세션 3에서 131 × 9 수집, J6 속도로 약 40분). teacher는 T0 결과(아래 3.1)를 반영한 지시로 모은다.

- **teacher(Ollama `qwen3.8:27b`, Ollama GPU `48f798cc…`)**: 표현 중립 지시 초안(계획서 v2 8.1) — 출력 필드 이름(concept·role·id·EVENT 등)을 쓰지 않고 의미 판단만 적게 한다:
  무엇을 세는가(통행 passage vs 실차 trip), 어느 끝인가(승차·하차·둘 다), 무엇으로 묶는가(묶음 단위 dimension vs 기간 구간 bucket), 집계어가 질문에 있는가,
  장소와 주변(vicinity). 자동 검사 (a) trace에 arm 전용 필드 이름이 없다, (b) trace 결론(dt, od_role, measure, aggregation)이 두 arm의 JSON과 일치한다.
  같은 trace에 Full JSON과 Partial JSON을 붙여 두 arm에 쓴다. 대상 우선순위: 8b 자체 정답 표본이 없는 질문 → dt·OD endpoint·실차 통행량·vicinity·집계 유무·bucket/dimension.
  결정 55 guard, 연속 방식(결정 79), 질문당 표본 8·최대 4개 사용(결정 48).
- **8b 자체**: arm마다 자기 prompt, 같은 sampling(vLLM BF16, greedy 1 + 표본 8, 0.6/0.95/20, 8192). Full은 J1(이번 세션)이 401문항 원문을 모았다.
  Partial(J6)은 **아직 못 모았다**(4절 결정 필요). 판정·필터(조건 계층 전 원응답 vs canonical)는 승인 뒤 다음 세션에서 한다. 원문은 ignore(결정 98).

### 3.1 T0(teacher 표현 중립 지시 smoke, 세션 2)과 지시 수정 제안(C5, `teacher/T0_REPORT.md`)

- 20질문 × 8 = 160 trace, 31.5분(trace당 약 11.8초), 결정 126(F5) guard 기준 **33.55 tok/s**(G0 중앙값 67.09의 0.5배, `PLAN_DEVIATIONS.md` 1번), 최저 78.8 tok/s로 통과.
- 자동 검사: (a) arm 전용 필드 이름 없음 **0/160**(좁은 기준도 0/160), (b) 결론 일치 121/160, 최종 JSON 일치 133/160(차이는 모두 aggregation_spec 27).
- 제안(지시 파일은 고치지 않음): teacher 전용 system prompt(형식 어휘 제거, JSON 대신 우리말 결론 다섯 줄), 생각은 한국어, (a) 목록 좁히기는 사전 등록 때 결정,
  **수정 지시로 T0 재측정(같은 20질문, 약 30분)** 뒤 본 수집. 집계 차이 27건은 사람이 한 번 본다.
- 결정 필요: trunk 131질문의 기존 pilot_004 teacher(표현 중립 아님, `teacher_neutral: false`)를 그대로 쓸지, 새 지시로 다시 모을지(9절 3).

## 4. 먼저 정해야 하는 것(사용자 결정)

> 세션 2 갱신: 1(결정 117), 4(결정 121), 6(결정 118), 7(결정 122 F1, 결과를 본 뒤 기준 변경으로 기록), 8(결정 125 F4 → C11: 12,288),
> 9(결정 126 F5 → 기준 33.55 tok/s)는 정해졌다. 남은 것은 2·3(검토)·5(사전 등록)와 9절의 결정들이다.

1. ~~**Partial 경로 생성 길이 한도.**~~ **결정 117(E2)로 (a) 채택**: 모든 vLLM 셀·표본 수집 `--max-model-len` 17,408(`serve6b.sh`). base 셀 B1–B4 재측정(세션 1b).
   J2(16,384)는 봉인한 채 참고만, J1(16,384)은 학습 데이터 후보로 그대로(요청이 모두 한도 안). 원래 내용: P0.3 입력이 8,729 token이라 PROTOCOL_v5 서버(`--max-model-len 16384`, max_tokens 8,192)에서 모든 요청이 400으로 거부된다
   (J5S·J5R 무효, `../pilot_006_prep/integration/gpu_partial_smoke/ABORTED_*`). Full 입력은 7,270 token(합 15,462). 선택지:
   - (a) **권장**: pilot_006 모든 vLLM 셀(base·F·P·참고)과 표본 수집의 `--max-model-len`을 17,408(입력 최대 + 8,192 + 여유)로 올린다. sampling·정밀도·커널·동시 요청은 그대로.
     요청별 출력에는 영향이 없을 것으로 보지만 서버 인자가 바뀌므로, 비교에 쓰는 base 셀(selection_v2, holdout, valid98, aux)은 새 인자로 다시 잰다(PROTOCOL_v5 재측정 규칙).
     J2 holdout base 셀(이번 세션, 16,384)은 그때 참고로 두거나 다시 잰다.
   - (b) Partial만 max_tokens를 16,384 − 입력(약 7,650)으로 줄인다. 생성 한도가 arm마다 달라져 Gate E·잘림 비교가 흐려진다.
   - (c) P0.3 prompt를 줄인다. Partial 계약이 바뀌어 pg 기록과 이어지지 않는다.
2. aug300 semantics 초안 273(E4로 train 207·holdout 53 대상)(`../pilot_006_prep/aug300_review/`), 상태 제안 15(그중 코드 실패 134·135).
3. batch007 27(검토 전), batch008 10. 약한 겹침 20건은 결정 120(E5)으로 재분류(되살림 0, 분류 밖 2건은 사용자 확인).
4. ~~pg 자산 수용~~ 결정 121(E6): pg 승인 상태 그대로 후보 147(`../pg_imports/acceptance_e6.json`), EDIT_REQUIRED 7행은 사람 검토 대기. conflicts 0건.
5. 이 초안의 Gate·주 셋·seed·중단 규칙(5절), `protected_final_v1` 계획(8절).
6. ~~W4 6(b) 해석~~ 결정 118(E3): 통과("Partial 경로가 같은 출력에 대해 Full 경로와 다른 호출을 만들지 않는다").
7. **J5S'(Partial smoke, 17,408 서버) 불통과**(세션 1b): 요청 10/10 처리, 비교 가능 6건은 경로 불일치 0, 그러나 base 모델의 P0.3 출력 4건이 실패
   (MISSING_RELATION_QUALIFIER 3 — old44/g02·g04·g12, Full 경로 J4에서는 셋 다 정답; UNCONSUMED_CONDITION 1 — g17, Full과 같은 올바른 거부)
   → 미리 정한 "비교 가능 ≥ 8/10"에 못 미침. J5R'(R2)와 J6(Partial 8b 자체 표본)은 시작하지 않았다. 선택지: (i) smoke 기준을 "요청 > 0이고 비교 가능한 문항의
   경로 불일치 0"으로 보고 J5R'·J6 진행(이 기준은 harness 확인용이었다), (ii) 다른 10문항으로 smoke를 다시, (iii) Partial 쪽 GPU 작업을 멈춘 채 둔다.
8. **학습 길이(2a, `../pilot_006_prep/analysis/seq_length.json`)**: max_seq_length 11,392에서 응답(thinking + JSON)에 쓸 수 있는 몫은 Full 약 4,065–4,122,
   Partial 약 2,606–2,663 token(질문 길이에 따라). 한도를 넘는 레코드: pilot_004 판 Full 0 / Partial 4(0.86%, 모두 8b 자체 json_only, 4질문),
   J1 원문 전체(3,602레코드, 401질문) Full 3 / Partial 36(1.0%; Partial만 33, 0.92%; 출처별 Partial만 aug300 7·batch007 3·pg 23).
   Partial만 넘는 비율 전체 0.91%(5% 기준 아래). 넘는 레코드가 있는 질문: pilot_004 판 4, J1 26. 선택지(고르지 않음):
   (A) 두 arm 모두 max_seq_length를 같은 값(예: 13,312 이상)으로 올린다 — 메모리 확인(다음 세션 GPU, pilot_004 peak 43.9 GB / 48 GB),
   (B) 어느 arm에서든 넘는 레코드가 있는 질문은 두 arm 모두에서 뺀다(질문 목록은 seq_length.json).
9. **teacher 수집(N1)의 결정 55 속도 기준**: 27b는 Ollama 0.35.1(pilot_003 teacher, 128호출)에서 최저 77.8 tok/s였지만, 0.40.3(pilot_005 27b 참고 셀)에서는
   첫 호출이 27.6 tok/s로 기준 30 아래라 멈췄다(`../pilot_005/vendor100/ABORTED_gpu_v100-27b_s1_gpu_guard.json`). 같은 조건이면 N1도 guard에 걸릴 수 있다.
   27b 전용 기준(기존 GPU 기록에서 미리 정해 plan-deviation 기록에 적음, 규칙 13)이나 원인 확인(0.40.3에서 27b 속도)이 먼저 필요하다.
   세션 1b의 선택 작업 T0(teacher 지시 smoke)도 같은 이유로 돌리지 않았다.

## 5. 평가 셀과 판정

### 5.1 셀(D3: vLLM 0.30.0 BF16, flashinfer, LoRA 비병합, 동시 요청 8, PROTOCOL_v4 3절 sampling; 4절 1의 서버 인자 결정 반영)

| 셀 | 모델 | target | 셋 | k | 역할 |
|---|---|---|---|---:|---|
| base | vLLM-base | Full | 주 셋 151(selection_v2 98 + holdout 53), valid98, aux_test_v1 | 4 | 기준 |
| R2 | vLLM-base | Partial(P0.3) | selection_v2 | 4 | prompt-only Partial 참고(판정 없음) |
| R3 | pilot_005 v1_step467 | Full | selection_v2(기록 재사용), holdout | 4 | 현재 최선 Full 참고(데이터가 다름, 판정 없음) |
| **F e1** | pilot_006 Full epoch 1 | Full | 주 셋 151, valid98, aux, 업체 100(개발 셋, D1) | 4(업체 100 8) | 학습된 Full |
| **P e1** | pilot_006 Partial epoch 1 | Partial | 같음 | 같음 | 핵심 실험군 |
| F e2·P e2 | epoch 2 | | selection_v2 | 4 | 보고만(D7) |
| 지연 | base·F e1·P e1 | | 고정 30문항 순차 | 1 | D8 |

- selection_v2는 n33 포함·제외 둘 다 보고(결정 104, batch007로 학습하는 경우).

### 5.2 arm별 선행 조건(D7, 보정 없음)

각 arm(e1) 대 base, 주 셋 151, k=4: 정답률(grounding_ok) 차이 95% CI(문항 단위 쌍 bootstrap 10,000회, `default_rng(20261109)`) 하한 > 0, 그리고
U 비율 차이 95% CI 하한 ≤ 0. F가 통과하지 못하면 F vs P는 해석하지 않고 보고만 한다(계획서 v2 11.2, Bonferroni 없음 — 지시 3절 2).

### 5.3 F vs P Gate(모두 주 셋 151, 같은 표본, 문항 단위 쌍 bootstrap; selection_v2만의 결과도 함께 보고)

| Gate | 지표 | 통과 조건 |
|---|---|---|
| A 의미 비열등 | grounding_ok | P − F 차이 95% CI 하한 ≥ **−5%p**(D4) |
| B dimension_target | dt_missing 비율 | P − F 95% CI 하한 ≤ 0 |
| C 조용한 오답 | answered_wrong 비율 | P − F 95% CI 하한 ≤ 0 |
| D 구조 | first-response 구조 오류(MULTIPLE_MEASURES, NO_MEASURE, INVALID_*, JSON_NOT_FOUND), grounding failure, repair 호출 비율 | (1) MULTIPLE_MEASURES + NO_MEASURE: P − F 95% CI 하한 ≤ 0, **그리고** (2) 셋 중 하나 이상에서 P − F 95% CI 상한 < 0 |
| E 효율(지시 3절 3) | 지연·token | (1) **P와 F 각각** 순차 고정 30문항 base 대비 중앙값 비 ≤ **1.5**(D8, 가장 중요), (2) 최종 JSON token 중앙값 P가 F보다 **30% 이상** 적음, (3) 생성 token 중앙값 P ≤ F |

- Gate E 함께 보고(판정에 쓰지 않음): 입력 token(Full 7,270 / Partial 8,729, 질문에 따라 ±40), prefix cache 상태(vLLM 0.30.0 기본값 켜짐, 적중률),
  thinking·최종 JSON token(D8), 첫 문항(캐시 없음) 시간. 2b 추정(`latency_v2.json`): 입력 증가 비용은 캐시 있음 ≈ 0, 캐시 없음 문항당 약 0.20초(prefill ≈ 7,300 tok/s).
- 채택 조건: A–E 모두 통과. JSON token 감소만으로 채택하지 않는다.
- W8 검정력(`../pilot_006_prep/analysis/power.json`): 151문항 예상 반폭 약 2.6–4.2%p. 진짜 차이 0일 때 Gate A 통과 확률 약 0.81(−1%p 0.63, −2%p 0.44).
  반폭이 마진보다 크게 나오면 Gate A 불통과는 "열등"이 아니라 "판정 불가"로 보고한다.
- W8 지연(`latency.json`): pilot_005 고른 후보의 지연 비 1.566은 thinking 증가(중앙값 626 → 944) 때문이었다. Partial의 최종 JSON 감소만으로는 1.42–1.44로 추정된다
  (thinking 불변 가정). F는 pilot_005와 같은 recipe라 **F 자체가 E(1)에서 걸릴 가능성이 크다**. 이 경우 P만 통과해도 비교는 보고만 한다(선행 조건 아님, Gate E는 P 채택 조건).

### 5.4 세션 2 참고 결과(판정 아님, 기준은 바꾸지 않음)

- **base(C1, `../pilot_006_prep/analysis/base_drift.md`)**: 환경 변화 흔적 없음(X1 16,384 대 pilot_prep_007 −1.53 [−5.61, 2.30], R3a = pilot_005 v1_step467 기록 0.00).
  B1(66.3%) 대 X2(70.2%) −3.06 [−7.40, 1.28]은 실행 간 변동. pilot_005 판정 영향 없음. **권고: selection_v2 base = B1 + X2(k=8), 세션 3에서 F·P와 같은 시간대에
  base k=4를 한 번 더 재서 k=12**(사전 등록). Gate A–E(F 대 P)는 base를 쓰지 않는다.
- **R2(P0.3 prompt만, base 모델) 대 Full base(C9, `../pilot_006_prep/analysis/r2_vs_base.json`)**:

  | 셋 | grounding_ok Partial − Full | dt 누락 | 구조 오류 | MM+NM | 최종 JSON token 중앙값 | thinking 중앙값 |
  |---|---|---|---|---|---|---|
  | selection_v2(98, base = B1+X2) | −6.63 [−13.65, 0.26] | +3.32 [0.77, 6.25] | +0.51 [−4.08, 5.23] | +2.42 [0.13, 5.49] | 207 → 112(−46%) | 683 → 517 |
  | valid98 | −2.81 [−10.20, 4.59] | +9.18 [5.10, 13.78] | −4.08 [−8.42, 0.51] | +0.77 [−0.51, 2.55] | 215 → 114(−47%) | 841 → 616 |
  | aux_test_v1 | −1.96 [−11.27, 7.35] | +4.90 [1.47, 8.82] | −3.43 [−12.25, 5.39] | +3.43 [−0.98, 9.80] | 214 → 115(−46%) | 790 → 555 |

  - Gate D·E 예상 범위(참고): E(2) JSON 30% 감소는 prompt만으로도 약 46%라 넉넉하다. E(3) 생성 token도 Partial이 적다(889 → 621). D(1) MM+NM은 prompt만으로는
    Partial이 늘었다(selection_v2 CI 하한 0.13 > 0) — 학습 뒤에도 남으면 D 불통과 위험. 원인 일부: 값 없는 장소 문항(scope_reverse 4문항 등)에서 Partial이 MEASURE를 내지 않음(ok 0%).
  - Gate B(dt) 위험: prompt만으로는 Partial dt 누락이 세 셋 모두 늘었다(J5S'·J6 판정과 같은 패턴, dt_pickup 문항에서 가장 큼). 학습 데이터의 dt 대조(teacher 우선 대상)가 핵심이다.
  - holdout(R2h, B2, R3b, J2)은 봉인이라 쓰지 않았다(존재·줄 수·sha256만 확인, `../pilot_006_prep/cells/sealed_check.json`).

## 6. 다음 세션 GPU 일정표(D9, 결정 114; 5.4절 형식)

> **세션 2(C12)에서 다시 계산한 일정은 6.1절이다.** 아래 표는 세션 1 추정으로, 기록으로 남긴다.

T0 = 사용자 승인과 4절 결정이 끝난 시각. 시간 근거: SFT 5.91초/step(`../pilot_004/train_logs`, PROTOCOL_v5 7절), selection_v2 표본 1개 5.5–8분(동시 8),
holdout 표본 1개 약 3분(J2: 4표본 12분), teacher 27b 표본 8개 질문당 약 88초(`../pilot_003/teacher/batch006_no_correct.log`), 8b 자체 표본 401문항 × 9 약 2.4시간
(J1, `../pilot_006_prep/gpu/timeline.jsonl`), 지연 셀 30문항 약 8–13분(pilot_005 813초).

```text
ID  | 작업                                         | 의존                         | 예상 시간(근거)                         | GPU(UUID)          | 시작 예정 | 끝 예정
N1  | teacher 27b 수집(새 질문 중 8b 정답 없는 것 우선) | 승인, Ollama 버전·digest·guard | 120–300질문 × 88초 ≈ 3–7.5h(pilot_003)   | 48f798cc(Ollama)   | T0        | T0+3–7.5h
N2  | J6 Partial 8b 자체 표본(401 × 9)              | 4절 1 결정, J5 smoke 재실행 통과 | 2.4h(J1)                                | 2445b100           | T0        | T0+2.5h
N3  | J5 smoke 10 → R2(selection_v2 P0.3 k=4)       | 4절 1 결정                    | 0.1h + 0.5h                             | a5ce83d0           | T0        | T0+0.6h
N4  | base 셀 재측정(4절 1(a)일 때: selection_v2·holdout k=4, valid98·aux k=4) | N3 서버 재사용      | 0.5 + 0.2 + 0.5 + 0.25 ≈ 1.5h             | a5ce83d0           | T0+0.6h   | T0+2.1h
N5  | R3 holdout(v1_step467 Full k=4)              | 없음                          | 0.2h                                    | a5ce83d0           | T0+2.1h   | T0+2.3h
N6  | 데이터 판 생성·검사(CPU: 판정·필터, 두 arm, 손실 token, 겹침) | N1, N2, J1             | CPU 0.5h                                | –                  | T0+7.5h   | T0+8h
N7  | F 학습(2 epoch, ≈1,450 레코드/epoch)           | N6                            | 2 × 1,450 × 5.91초 ≈ 4.8h               | 2445b100           | T0+8h     | T0+12.8h
N8  | P 학습(같음)                                   | N6                            | ≈4.8h(입력이 1,459 token 길어 약간 느릴 수 있음) | a5ce83d0      | T0+8h     | T0+12.8h
N9  | 업체 100 base(개발 셋, k=8)                    | 4절 1                         | 1h                                      | 48f798cc           | T0+8h     | T0+9h
N10 | F e1·P e1 셀(주 셋 151 k=4, valid98, aux k=4, 업체 100 k=8) | N7·N8 epoch 1 저장 뒤(학습 끝난 GPU부터) | arm당 0.7 + 0.5 + 0.25 + 1 ≈ 2.5h | 끝난 GPU 3장에 셀 단위 | T0+12.8h | T0+14.5h
N11 | F e2·P e2 selection_v2 k=4(보고)               | N7·N8                         | arm당 0.5h                              | 남는 GPU           | T0+13.5h  | T0+14.5h
N12 | 지연 base·F e1·P e1(고정 30문항 순차, 한 GPU)   | N10                           | 3 × ≈13분 ≈ 40분                         | 2445b100(다른 둘 비움) | T0+14.5h | T0+15.2h
```

GPU별 예상 유휴 구간과 이유:
- `2445b100`: T0+2.5h–T0+8h(약 5.5h) — **의존 대기**(데이터 판이 teacher 수집 N1 끝을 기다림).
- `a5ce83d0`: T0+2.3h–T0+8h(약 5.7h) — 의존 대기(같은 이유).
- `48f798cc`: T0+9h–T0+12.8h(약 3.8h) — 준비된 작업 없음(학습 중에는 평가할 adapter가 없다).
- 지연 측정 N12 동안 나머지 두 GPU는 예외 7로 비운다(약 40분).

더 나은 배치 제안(근거):
1. **N1을 두 단계로 나눈다**: 먼저 J1·J6에서 8b 정답 표본이 없는 질문만 teacher로 모으고(데이터 판의 필수 부분), 우선순위 표현 묶음의 추가 teacher는 학습과 겹쳐 모은다.
   데이터 판이 N1 전체를 기다리지 않아 두 GPU의 5.5h 유휴가 1–3h로 준다(필수 질문 수에 따라).
2. 의존 대기 구간에 **다른 판의 필요 작업**(예: protected_final_v1 base 셀은 최종 판정 전에 쓰지 않으므로 넣지 않는다)이 아니라, 이 판의 참고 셀(R2 k=8로 늘리기 등)은 넣지 않는다.
   판정에 쓰지 않는 측정을 늘리면 결과를 본 뒤 선택이 생길 수 있다. 유휴는 그대로 기록한다.
3. N9(업체 100 base, 개발 셋)를 Ollama GPU 학습 대기 구간에 넣었다. Ollama 측정(N1)과 겹치지 않게 N1이 끝난 뒤에만 시작한다.

### 6.1 세션 3 GPU 일정표(세션 1·2 timeline 실제 시간으로 다시 계산)

근거(`../pilot_006_prep/gpu/timeline.jsonl`): J1(Full 8b 401 × 9) 158.8분, J6(Partial 같은 양) 120.7분, T0(27b 20질문 × 8) 31.5분(trace당 11.8초),
selection_v2 k=4 셀 Full 22–27분(B1 24.9, X1 23.9, X2 22.2, R3a 26.8)·Partial 16.7분(J5R2), holdout k=4 8–12분(B2 11.7, R2h 7.9, R3b 12.2), valid98 k=4 21–29분(R2v 21.4, B3 29.0),
aux k=4 15–16분(B4 14.6, R2a 15.8), M1 단계 3–5분, SFT step 7.5초(Full)·8.3초(Partial)(M1b, 12,288에서 가장 긴 레코드 — 상한값; pilot_004 평균 5.91초),
지연 셀 30문항 약 13분(pilot_005 813초). T3 = 승인·사전 등록이 끝난 시각. GPU: index 0 = `2445b100`, 1 = `a5ce83d0`, 2 = `48f798cc`(Ollama).

```text
ID  | 작업                                                    | 의존                       | 예상 시간(근거)                                  | GPU          | 시작      | 끝
S1  | T0' teacher 수정 지시 smoke(같은 20질문 × 8)              | 지시 수정 승인, guard      | 32분(T0)                                         | 2(Ollama)    | T3        | T3+0.5h
S2  | trunk 131질문 Partial 8b 자체 표본(131 × 9)               | 승인                       | 131/401 × 120.7분 ≈ 40분(J6)                     | 0            | T3        | T3+0.7h
S3  | base selection_v2 k=4(세 번째 base, 결정 시)              | 없음                       | 25분(B1·X2)                                      | 1            | T3        | T3+0.5h
S4  | teacher 필수 135질문 × 8                                  | S1 (a)(b) 확인             | 1,080 × 11.8초 ≈ 3.5h(T0)                        | 2(Ollama)    | T3+0.5h   | T3+4.0h
S5  | 데이터 판 생성·검사(CPU: 판정·필터·두 arm·손실 token·겹침·길이 12,288) | S2, S4, 승인       | CPU 0.5h                                         | –            | T3+4.0h   | T3+4.5h
S6  | F 학습 2 epoch(≈1,450 레코드/epoch)                       | S5                         | 2,900 step × 5.9–7.5초 ≈ 4.8–6.0h                | 0            | T3+4.5h   | T3+9.3–10.5h
S7  | P 학습 2 epoch                                            | S5                         | 2,900 × 6.5–8.3초 ≈ 5.2–6.7h(입력 1,459 token 길다) | 1            | T3+4.5h   | T3+9.7–11.2h
S8  | 업체 100 base(개발 셋, k=8)                                | S4 끝(Ollama 측정 없음)     | 약 1h(100문항 × 8, selection_v2 속도)            | 2            | T3+4.5h   | T3+5.5h
S9  | teacher 추가(우선순위 표현 묶음, 결정 시)                  | S4                         | 질문 수 × 95초                                   | 2(Ollama)    | T3+5.5h   | 학습 끝 전
S10 | F e1·P e1 셀(주 셋 151, valid98, aux k=4, 업체 100 k=8)   | S6·S7 epoch 1 저장 뒤      | arm당 25 + 12 + 25 + 15 + 60분 ≈ 2.3h            | 끝난 GPU부터 | T3+7.0h~  | T3+12h
S11 | F e2·P e2 selection_v2 k=4(보고만)                         | S6·S7 끝                   | arm당 25분                                       | 남는 GPU     | T3+10.5h  | T3+12h
S12 | 지연 base·F e1·P e1(고정 30문항 순차, 한 GPU, 다른 둘 비움) | S10                        | 3 × 13분 ≈ 40분(`latency/latency6.py`)            | 0            | T3+12h    | T3+12.7h
```

- epoch 1 checkpoint는 학습 중간(약 T3+7–8h)에 저장되므로, S10의 epoch 1 셀은 학습이 끝난 GPU가 없으면 Ollama GPU(2)에서 먼저 시작할 수 있다(S8·S9 뒤, Ollama 모델이 올라가 있지 않음을 확인).
- 예상 유휴: GPU 0·1은 T3+0.7h(또는 +0.5h)부터 T3+4.5h까지 **약 3.8h 의존 대기**(데이터 판이 teacher 필수 수집 S4를 기다림). 줄이는 방법: teacher 필수 대상을 arm별 "정답 표본 없음" 질문에서
  두 arm 모두 없는 83질문으로 먼저 줄이고(약 2.2h) 나머지는 S9로 넘기면 대기가 약 2.5h가 된다(사용자 결정, 9절 4).
- `protected_final_v1` 측정(채택 후보 대 base k=8, 120 × 8 × 2, 약 1–2h)은 채택 후보가 정해진 뒤(세션 3 끝 또는 세션 4).

## 7. 남은 승인 항목(이번 세션 산출)

> 세션 2 갱신: 검토 보조 자료 v2(C4, `../pilot_006_prep/review_guide.md`, `../pilot_006_prep/review/priority_counts.json`) — 예상 약 478분(약 8시간).
>
> | 자료 | 위치 | 우선순위별 건수 |
> |---|---|---|
> | aug300 | `../pilot_006_prep/aug300_review/review/aug300_review_v2.xlsx` | 높음 90, 보통 57, 낮음 113, 검토 불필요(결정 119 제외) 13, 모델 출력 비교 64쌍 |
> | batch007 | `../batch007/review/batch007_review_v2.xlsx` | 높음 27(+ 쌍 25) |
> | batch008 | `../batch008/review/batch008_review_v1.xlsx` | 높음 5, 보통 5 |
> | pg EDIT_REQUIRED | `../pg_imports/review/pg_edit_required_v1.xlsx` | 높음 7(수정안 초안 포함) |


| 항목 | 위치 | 건수 |
|---|---|---:|
| aug300 semantics 초안 | `../pilot_006_prep/aug300_review/review/aug300_review.xlsx`(aug300 시트) | 273(train 220, holdout 53) |
| aug300 base 출력 비교(J3) | 같은 파일 vllm_outputs 시트 | 69쌍 |
| aug300 상태 제안 | 같은 파일 status_proposals 시트, `../pilot_006_prep/aug300/status_proposals.json` | 15 |
| batch007 | `../batch007/review/batch007_review.xlsx` | 27 + 쌍 25 |
| batch008 | `../batch008/candidates_checked.json`(남음 10), `../batch008/excluded.json`(약한 겹침만 20, 강한 사유 8) | 10 + 20 결정 |
| conflicts | `../pilot_006_prep/canonical/conflicts.json` | 0 |
| pg 자산 수용 | `../pg_imports/README.md` | pg_batch006 43(EDIT_REQUIRED 7 포함), reasoning 154 |

## 7b. 결정 116–121(E1–E6) 반영 상태(세션 1b)

| 결정 | 내용 | 반영 |
|---|---|---|
| 116 E1 | 업체 원본 xlsx 커밋 문제없음, `.gitignore` 문구 정정 | `ade2654` |
| 117 E2 | `--max-model-len` 17,408, base 셀 재측정, J2 참고만, J1 그대로 | `ade2654`(serve6b.sh·jobs6b.sh), B1–B4 실행 |
| 118 E3 | W4 6(b) 통과 기준 문구 | `integration_check.json`(`4c9aa95`) |
| 119 E4 | aug300 상태: train 207, 제외 18, holdout 53, 축소 22 | `aug300/status_e4.json`(`4c9aa95`) |
| 120 E5 | batch008 재분류: 되살림 0(J7b 대상 없음), 분류 밖 2 | `batch008/e5_reclassification.json`, README 5절(`4c9aa95`) |
| 121 E6 | pg 수용 147, EDIT_REQUIRED 7 보류 | `pg_imports/acceptance_e6.json`(`4c9aa95`) |

## 7c. 결정 122–129(F1–F8) 반영 상태(세션 2)

| 결정 | 내용 | 반영 |
|---|---|---|
| 122 F1 | J5S' 통과(기준 "요청 > 0, 비교 가능 문항 경로 불일치 0", 결과를 본 뒤 바꾼 기준임을 기록) → J5R'·J6 진행 | `2228f2e`, J5R2·J6 실행(`fd807ef`) |
| 123 F2 | J1 원문 이름 되돌림(`self_full_raw.jsonl`), manifest·timeline 정정 | `2228f2e` |
| 124 F3 | worktree `/home/hwkim/sftdpo_work/worktrees/wt_<sha7>_<ID>`, `worktrees.json`, 작업 끝나면 직접 지움 | `2228f2e`(scheduler6.py), 세션 2 worktree 모두 지움 |
| 125 F4 | 학습 길이 사전 등록(L_req → M1 → 12,288 → B') | M1 `a627e43`, M1b `50d5088`, 결론 C11 `ea19539`: **12,288** |
| 126 F5 | 27b guard = G0 중앙값 × 0.5 | G0 67.09 tok/s → **33.55**, `PLAN_DEVIATIONS.md` 1번, T0 통과(`7fca0d0`) |
| 127 F6 | b008-12·34 계속 뺌 | `2228f2e`, batch008 검토 시트에서 제외 |
| 128 F7 | 참고 셀 R2h·R2v·R2a·R3a·R3b, holdout 셀 봉인 | 실행 `cfc3c0d`·`18202c6`, 봉인 해시 `sealed_check.json` |
| 129 F8 | M1만 학습 예외, adapter·checkpoint 삭제 | M1·M1b adapter·checkpoint 삭제 확인(각 run `deleted_outputs: true`, `/home/hwkim/sftdpo_work/pilot_006/m1_tmp` 비어 있음) |

## 8. `protected_final_v1` 작성 계획(D1)

> 세션 2 갱신: 명세는 `protected_final_v1_SPEC.md`(C10, `a71ef9c`)가 대신한다 — **120문항, k=8**(후보 대 base 우월 검정력 δ=8%p 0.86), 7유형 + 거부 10, hard factor 최소 수,
> 사람 작성 권고(Claude는 보호 셋을 읽었으므로 기계 검사만), 저장소 밖 보관·manifest 해시 먼저 커밋·열람 기록·1회 사용. 아래는 세션 1 초안(기록).

- 목적: F와 P 중 채택 후보 하나를 한 번만 판정하는 새 보호 셋. 업체 100은 pilot_006부터 개발 셋이다(결정 106).
- 작성: 보호 셋(업체 100, selection_v1·v2, valid98, aux_test_v1, augmentation_holdout_v1)과 학습 데이터를 **보지 않고** 새로 쓴다(batch007 방식).
  약 100문항, 7개 의미 유형과 hard factor(dt, od≠dt, 동사형 endpoint, occupied 통행량, vicinity, bucket/dimension, 집계 유무)를 고르게. 정답은 업체 형식 호출.
- 검사: 현재 코드 compile·mock 실행, 모든 셋과의 겹침(W6 기준, 강한 겹침 0이어야 함). 사람 검토·승인 뒤 목록과 sha256을 커밋해 고정한다.
- 고정 뒤 어떤 모델 출력도 만들지 않는다. 채택 후보가 정해진 뒤 base와 그 후보만 k=8로 한 번 잰다(PROTOCOL_v4 6절 판정 규칙, 보정 없음).
- 작성 시점: 다음 세션 초반(CPU). 학습과 겹쳐도 된다.

## 9. 세션 3 시작 조건(체크리스트, 세션 2b에서 다시 씀)

### 9.1 승인(사람)

- [x] aug300·batch007·batch008·pg EDIT_REQUIRED 검토 결정(결정 130 G0, R0 `dec42ac`): 승인 289, 수정 9 반영(aug300-348 보류), 제외 5.
- [ ] **aug300-348**(질문 수정 뒤 aux_test_v1·valid98과 Jaccard ≥ 0.5): 보류 유지 / 제외 / 다른 문구 — 사용자 결정(대체 수정안은 만들지 않았다).
- [ ] **batch009 43 후보** 검토(Claude 2차 검토 권고 → 사용자 결정, `../batch009/review/batch009_review_v1.xlsx`). w1(값 없는 장소) 0건 대안 결정(`../batch009/README.md` 4절).
- [ ] **teacher 지시 v3**(`teacher/T0V2_REPORT.md` 제안) 승인 여부와 T0''(새 20문항) 통과 규칙.

### 9.2 데이터

- [x] 8b 자체 표본: trunk 131 두 arm(J8·J9), 보강 32표본(S32P/F-a·b), batch008·질문 변경(J10) — 모두 승인 gold 판정(`../pilot_006_prep/self_samples/r1/`).
- [x] RC1(`build/RC1`): 234질문, 두 arm 검사 통과. **teacher 0**.
- [ ] teacher 수집(T0'' 통과 뒤 TEACH, G2 범위 189질문, `self_samples/r1/teacher_targets_h6.json`) → RC2 빌드·검사(`build/RC1/README.md` 명령).
- [ ] batch009 승인분 J12 판정 → RC2에 포함.
- [ ] H4 부족분(implicit endpoint 11/30, 값 없는 장소·scope 역조회 1/30) 처리 방침.

### 9.3 사전 등록(PLAN 고정, `freeze.py --rc RC2`; 이 세션에서는 실행하지 않음)

- [ ] Gate A–E·마진 −5%p·주 셋 151·selection_v2 n33 포함·제외 보고(5절, 바꾸지 않음).
- [ ] base: B1 + X2 + 세션 3 base k=4(결정 134 G4) = k=12.
- [ ] seed 20261016(두 arm 같음), epoch 1 고정(D7), max_seq_length 12,288(결정 125).
- [ ] teacher 자동 검사 (a)(b) 규칙(v3 기준), 레코드 제외 규칙.
- [ ] `protected_final_v1`: 사람 작성(결정 135), `protected_final/` 도구로 검사·해시 고정. 작성자 이름 기록(지시의 작성자 칸이 비어 있었다).
- [ ] 지연 측정: `latency/latency6.py`(vLLM, 한 GPU·다른 둘 비움, 고정 30문항). Ollama production 측정은 넣지 않는다(결정 137 G7).

### 9.4 GPU 준비

- [ ] 세 GPU UUID·다른 사용자 프로세스·`/api/ps` 확인, Ollama 컨테이너 GPU `48f798cc`(규칙 13). Ollama는 teacher 수집에만(G7), guard 33.55 tok/s.
- [ ] vLLM 0.30.0 `serve6b.sh`(17,408), 학습 GPU 1장씩, Ollama GPU 학습 전 모델 미적재 확인, worktree는 `/home/hwkim/sftdpo_work/worktrees/`.

### 9.5 남은 사용자 결정

1. teacher 지시 v3 채택과 T0'' 규칙(새 20문항, 같은 (a)(b) 기준 또는 조정) — T0' 불통과(결정 131).
2. aug300-348 처리.
3. batch009 검토(43)와 w1 대안(결정 120 예외 / 그대로 0건).
4. H4 부족분 최소 질문 수(제안 30)와 보강 방법.
5. RC2 없이 RC1(teacher 0)로 학습할지 — 권하지 않음(결정 86 출처 구성과 다르고, 정답 표본 없는 98질문이 빠짐).
6. protected_final_v1 작성자 이름.

## 10. 세션 2b 결과(결정 130–137)

| 결정 | 내용 | 반영 |
|---|---|---|
| 130 G0 | 검토 결정 채택(승인 289·수정 10·제외 5) | R0 `1d897d4`(목록)·`dec42ac`(기록·corpus): 수정 9 통과, 348 보류. holdout 고정값 그대로 |
| 131 G1 | teacher v2, T0' 규칙 | `c607731`(지시·규칙), T0' **불통과**((a) 158/160, (b) 53/160) `de81b5f` |
| 132 G2 | TEACH 범위 | 대상 216 고정(`c607731`), **실행 안 함**(T0' 불통과). 재계산 189(H6) |
| 133 G3 | 8b 표본(vLLM 새로, S32 보강, 질문 변경 재수집) | J8·J9·S32*·J10 판정 `4198a91`–`a118c6b` |
| 134 G4 | 세 번째 base 셀 | 6.2절 일정에 넣음 |
| 135 G5 | protected_final_v1 120·k=8, 사람 작성 | 도구 `727433c` |
| 136 G6 | CPU 순서, 예상 유휴 | `gpu/session2b_plan.json`, 실제 사용률은 보고 |
| 137 G7 | Ollama는 teacher만 | PLAN에 production Ollama 측정 항목 없음(확인), 6.2절에도 넣지 않음 |

- 승인 corpus(`../pilot_006_prep/approved/`): train 523레코드(trunk 131, pg 154, aug300 201, batch007 27, batch008 10; 정규화 질문으로 합치면 416), holdout 53.
- 8b 정답 표본이 있는 질문(416 중): Full 339, Partial 348. 한 arm이라도 없는 질문 98(두 arm 모두 없음 47).
- RC1: 234질문, Full 776·Partial 779(모두 8b 자체). 상세 `build/RC1/README.md`.

### 6.2 세션 3 GPU 일정표(세션 2b 실측 기준)

근거(`../pilot_006_prep/gpu/timeline.jsonl`): T0' 27b 320 trace 29.6분(5.6초/trace), J8 131 × 9 43분, J9 57분, S32P-a 112 × 32 126분, S32F-a 105 × 32 165분,
selection_v2 k=4 셀 22–27분, holdout 8–12분, valid98 21–29분, aux 15–16분, SFT step 5.9–8.3초(pilot_004 평균·M1b 상한). T3 = 승인·사전 등록 끝.

```text
ID  | 작업                                                   | 의존                    | 예상(근거)                                  | GPU
U1  | T0'' teacher v3 확인(새 20문항 × 8 + 참고)              | v3 승인, 규칙 커밋       | 30분(T0')                                   | 2(Ollama)
U2  | TEACH v3(G2 범위 189질문 × 8)                           | U1 통과                  | 1,512 × 5.6초 ≈ 2.4h(T0')                   | 2(Ollama)
U3  | batch009 승인분 추가 teacher·8b 판정(J12 원문 재사용)    | batch009 승인            | teacher ≤ 43 × 8 × 5.6초 ≈ 0.5h             | 2(Ollama)
U4  | RC2 빌드·검사(CPU)                                      | U2·U3                    | CPU 10분                                    | –
U5  | base selection_v2 k=4(G4, 세 번째)                      | 없음(F·P 평가와 같은 날)  | 25분                                        | 0 또는 1
U6  | F 학습 2 epoch(RC2 약 1,300–1,500 레코드/epoch 추정)     | U4, PLAN 고정            | 2,800 × 5.9–7.5초 ≈ 4.6–5.8h               | 0
U7  | P 학습 2 epoch                                          | U4, PLAN 고정            | 2,800 × 6.5–8.3초 ≈ 5.1–6.5h               | 1
U8  | F e1·P e1 셀(주 셋 151, valid98, aux k=4, 업체 100 k=8) | U6·U7 epoch 1            | arm당 25 + 12 + 25 + 15 + 60분 ≈ 2.3h       | 끝난 GPU부터(2 포함)
U9  | F e2·P e2 selection_v2 k=4(보고)                        | U6·U7                    | arm당 25분                                  | 남는 GPU
U10 | 지연 창: base·F e1·P e1(vLLM, 고정 30문항 순차)         | U8                       | 3 × 13분 ≈ 40분, 다른 두 GPU 비움            | 하나
```

- 예상 유휴: GPU 0·1은 U4(RC2)까지 약 3h 의존 대기(teacher 수집이 학습 데이터의 선행 조건). 그 사이 U5(base 셋째 셀)만 넣을 수 있다.
  줄이는 방법(사용자 결정): teacher 필수 98질문을 먼저 모으고(약 1.2h) 나머지 G2 범위(trunk 재수집)는 학습과 겹쳐 모으되 RC2에는 먼저 끝난 것만 넣기 — 단 이 경우 두 arm
  trunk 질문의 teacher 출처가 일부만 v3가 되므로 G2 취지(두 arm 같은 지시)와 맞는지 확인이 필요하다.
- Ollama production 측정(E·27b 참고 셀, Ollama 지연, 업체 100 Ollama)은 없음(결정 137 G7).
