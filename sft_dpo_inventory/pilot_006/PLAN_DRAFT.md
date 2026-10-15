초안, 사용자 승인 전

# pilot_006 계획 초안(Full vs Partial, SFT만)

작성: 2026-10-15(pilot_006 준비 세션 1, W9). **고정하지 않았다.** 학습·teacher 수집을 시작하기 전에 사용자가 고치고 확정한다.
따르는 것: `CLAUDE.md`(SFT/DPO 규칙 1–15), `../DECISIONS.md`(결정 1–115, 특히 106–114 = D1–D9), `../vendor100_protocol/PROTOCOL_v5.md`(v4·v3를 이어받음),
계획서 v2(`../pilot_006_prep/inputs/two_branch_integration_and_300_dataset_plan_v2.md`, 지시 3절 보정이 우선).

## 0. 실험 질문

pilot_005 수준의 학습(V1 recipe, SFT만)에서 Partial target을 학습한 모델(P)이 Full target을 학습한 모델(F)과 의미 정확도가 비열등하면서,
dt·조용한 오답·구조 오류를 악화시키지 않고 생성 비용(지연)을 줄이는가.

## 1. 데이터 구성(추정, `plan_estimates.py` → `plan_estimates.json`)

| 출처 | 질문 | canonical 검증 사슬 통과 | 상태 |
|---|---:|---:|---|
| trunk pilot_004 판(`reviewed_gold_v006_t2pc`) | 131 | 131 | 승인됨 |
| pg `reviewed_reasoning_v001`(trunk와 겹치는 v005 111 제외, pg batch006 Gap A·B) | 47 | 47 | pg 승인 상태 그대로(trunk 승인 아님, 사용자 확인 필요). pg batch006 43 + v005 질문 중 trunk pilot_004 판에 없는 4(b004-19·35, b005-11·60) |
| aug300 train(결정 106 적용) | 220 | 218(134·135 실패) | 초안(검토 필요) |
| batch007 | 27 | 27 | 초안(검토 필요) |
| batch008 남은 후보 | 10 | 10 | 초안(검토 필요). 약한 겹침으로 뺀 20건의 처리 결정 필요 |
| **합계(모두 승인될 때 최대)** | **435** | 433 | |

- 유형 상한(결정 88·92, τ 0.09, 결정 92 예외 = trunk 실차 대조 + batch007, 51질문): 상한 전 TV 0.145 → 상한 뒤 예상 **약 402질문, TV 0.111**
  (예외 때문에 0.09를 넘는다. 결정 92대로 그 값을 기록한다). 상한이 줄이는 칸: "집계 있음·dim 없음" 160 → 127, "집계 없음·dim 있음·dt 있음" 비예외 115 → 102 등.
- 두 arm의 질문 목록은 sha256까지 같아야 한다(계획서 v2 7절). Full·Partial target은 같은 canonical semantics에서 렌더링한다(W5, 466/466 + aug300 271/273 통과).
- 평가 셋 겹침 검사: W6 기준(강한 겹침 = 질문·Jaccard ≥ 0.5·같은 grounding)과 결정 54식 약한 겹침 기록. aug300 제안 15건(`../pilot_006_prep/aug300/status_proposals.json`)은 사용자 결정 뒤 반영.
- 레코드: 질문당 teacher ≤ 4(결정 48·50), 8b 자체 정답 표본(J1·J6), 결정 86 출처별 손실 범위(D2). pilot_004 판은 질문당 약 3.6레코드였다 → **SFT 레코드 약 1,400–1,500 예상**.

## 2. 두 arm recipe(D2·D5·D7, pilot_005 V1 설정)

| 항목 | 값 |
|---|---|
| base | Qwen/Qwen3-8B@b968826d, BF16, SDPA, gradient checkpointing |
| LoRA | r16 / α32 / dropout 0.05, 7개 projection |
| 최적화 | AdamW lr 5e-5, warmup 1 step, batch 1, accum 1, max_seq_length 11,392 |
| 길이 | 2 epoch, epoch 1·2 저장. **epoch 1 checkpoint를 미리 고정**(D7), epoch 2는 보고만 |
| seed | 하나, 두 arm 같게(초안: 20261016) |
| 손실 범위 | 결정 86 by_source(teacher `full_response`, 8b 자체 `json_only`) 두 arm 공통 |
| DPO | 없음(D5) |
| target | F = `render_full`(trunk Full 계약, prompt 87048d0c), P = `render_partial`(P0 계약, prompt P0.3 결합 sha256 `8b157c9a…`) |
| 학습 코드 | trunk 그대로. P arm은 "system prompt가 P0.3이고 답 JSON이 Partial target인 thinking 레코드"를 trunk 검사에 통과시키는 `grounding_target` 분기 하나를 데이터 판 생성 때 더한다(지금은 없음, inventory 1.4) |
| 감시 | P arm thinking p90이 base 대비 30% 넘게 줄면 보고(D2). base p90: selection_v2 1,313, 지연 30문항 1,101 |

## 3. 다음 세션 trace 수집 계획(승인 뒤)

- **teacher(Ollama `qwen3.8:27b`, Ollama GPU `48f798cc…`)**: 표현 중립 지시 초안(계획서 v2 8.1) — 출력 필드 이름(concept·role·id·EVENT 등)을 쓰지 않고 의미 판단만 적게 한다:
  무엇을 세는가(통행 passage vs 실차 trip), 어느 끝인가(승차·하차·둘 다), 무엇으로 묶는가(묶음 단위 dimension vs 기간 구간 bucket), 집계어가 질문에 있는가,
  장소와 주변(vicinity). 자동 검사 (a) trace에 arm 전용 필드 이름이 없다, (b) trace 결론(dt, od_role, measure, aggregation)이 두 arm의 JSON과 일치한다.
  같은 trace에 Full JSON과 Partial JSON을 붙여 두 arm에 쓴다. 대상 우선순위: 8b 자체 정답 표본이 없는 질문 → dt·OD endpoint·실차 통행량·vicinity·집계 유무·bucket/dimension.
  결정 55 guard, 연속 방식(결정 79), 질문당 표본 8·최대 4개 사용(결정 48).
- **8b 자체**: arm마다 자기 prompt, 같은 sampling(vLLM BF16, greedy 1 + 표본 8, 0.6/0.95/20, 8192). Full은 J1(이번 세션)이 401문항 원문을 모았다.
  Partial(J6)은 **아직 못 모았다**(4절 결정 필요). 판정·필터(조건 계층 전 원응답 vs canonical)는 승인 뒤 다음 세션에서 한다. 원문은 ignore(결정 98).

## 4. 먼저 정해야 하는 것(사용자 결정)

1. **Partial 경로 생성 길이 한도.** P0.3 입력이 8,729 token이라 PROTOCOL_v5 서버(`--max-model-len 16384`, max_tokens 8,192)에서 모든 요청이 400으로 거부된다
   (J5S·J5R 무효, `../pilot_006_prep/integration/gpu_partial_smoke/ABORTED_*`). Full 입력은 7,270 token(합 15,462). 선택지:
   - (a) **권장**: pilot_006 모든 vLLM 셀(base·F·P·참고)과 표본 수집의 `--max-model-len`을 17,408(입력 최대 + 8,192 + 여유)로 올린다. sampling·정밀도·커널·동시 요청은 그대로.
     요청별 출력에는 영향이 없을 것으로 보지만 서버 인자가 바뀌므로, 비교에 쓰는 base 셀(selection_v2, holdout, valid98, aux)은 새 인자로 다시 잰다(PROTOCOL_v5 재측정 규칙).
     J2 holdout base 셀(이번 세션, 16,384)은 그때 참고로 두거나 다시 잰다.
   - (b) Partial만 max_tokens를 16,384 − 입력(약 7,650)으로 줄인다. 생성 한도가 arm마다 달라져 Gate E·잘림 비교가 흐려진다.
   - (c) P0.3 prompt를 줄인다. Partial 계약이 바뀌어 pg 기록과 이어지지 않는다.
2. aug300 semantics 초안 273(`../pilot_006_prep/aug300_review/`), 상태 제안 15(그중 코드 실패 134·135).
3. batch007 27(검토 전), batch008 10 + **약한 겹침만으로 뺀 20건을 결정 54식 예외로 둘지**.
4. pg 자산(`../pg_imports/`)을 trunk 학습 데이터로 받아들일지(pg 승인 상태 그대로, EDIT_REQUIRED 7행 포함 여부), conflicts(0건).
5. 이 초안의 Gate·주 셋·seed·중단 규칙(5절), `protected_final_v1` 계획(8절).
6. W4 6(b) 해석(`../pilot_006_prep/integration/integration_check.json`): Partial grounding_ok 출력 51건이 gold 호출과 다르지만 모두 Full arm과 같다(경로 차이 0). 통과로 볼지.

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

- 채택 조건: A–E 모두 통과. JSON token 감소만으로 채택하지 않는다.
- W8 검정력(`../pilot_006_prep/analysis/power.json`): 151문항 예상 반폭 약 2.6–4.2%p. 진짜 차이 0일 때 Gate A 통과 확률 약 0.81(−1%p 0.63, −2%p 0.44).
  반폭이 마진보다 크게 나오면 Gate A 불통과는 "열등"이 아니라 "판정 불가"로 보고한다.
- W8 지연(`latency.json`): pilot_005 고른 후보의 지연 비 1.566은 thinking 증가(중앙값 626 → 944) 때문이었다. Partial의 최종 JSON 감소만으로는 1.42–1.44로 추정된다
  (thinking 불변 가정). F는 pilot_005와 같은 recipe라 **F 자체가 E(1)에서 걸릴 가능성이 크다**. 이 경우 P만 통과해도 비교는 보고만 한다(선행 조건 아님, Gate E는 P 채택 조건).

## 6. 다음 세션 GPU 일정표(D9, 결정 114; 5.4절 형식)

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

## 7. 남은 승인 항목(이번 세션 산출)

| 항목 | 위치 | 건수 |
|---|---|---:|
| aug300 semantics 초안 | `../pilot_006_prep/aug300_review/review/aug300_review.xlsx`(aug300 시트) | 273(train 220, holdout 53) |
| aug300 base 출력 비교(J3) | 같은 파일 vllm_outputs 시트 | 69쌍 |
| aug300 상태 제안 | 같은 파일 status_proposals 시트, `../pilot_006_prep/aug300/status_proposals.json` | 15 |
| batch007 | `../batch007/review/batch007_review.xlsx` | 27 + 쌍 25 |
| batch008 | `../batch008/candidates_checked.json`(남음 10), `../batch008/excluded.json`(약한 겹침만 20, 강한 사유 8) | 10 + 20 결정 |
| conflicts | `../pilot_006_prep/canonical/conflicts.json` | 0 |
| pg 자산 수용 | `../pg_imports/README.md` | pg_batch006 43(EDIT_REQUIRED 7 포함), reasoning 154 |

## 8. `protected_final_v1` 작성 계획(D1)

- 목적: F와 P 중 채택 후보 하나를 한 번만 판정하는 새 보호 셋. 업체 100은 pilot_006부터 개발 셋이다(결정 106).
- 작성: 보호 셋(업체 100, selection_v1·v2, valid98, aux_test_v1, augmentation_holdout_v1)과 학습 데이터를 **보지 않고** 새로 쓴다(batch007 방식).
  약 100문항, 7개 의미 유형과 hard factor(dt, od≠dt, 동사형 endpoint, occupied 통행량, vicinity, bucket/dimension, 집계 유무)를 고르게. 정답은 업체 형식 호출.
- 검사: 현재 코드 compile·mock 실행, 모든 셋과의 겹침(W6 기준, 강한 겹침 0이어야 함). 사람 검토·승인 뒤 목록과 sha256을 커밋해 고정한다.
- 고정 뒤 어떤 모델 출력도 만들지 않는다. 채택 후보가 정해진 뒤 base와 그 후보만 k=8로 한 번 잰다(PROTOCOL_v4 6절 판정 규칙, 보정 없음).
- 작성 시점: 다음 세션 초반(CPU). 학습과 겹쳐도 된다.
