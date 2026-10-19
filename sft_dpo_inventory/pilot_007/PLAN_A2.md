# pilot_007 A2단계 계획 — 고정본(학습 전)

작성 2026-10-19. 바탕: 결정 175–183, `A_RESULTS.md`(A단계 두 recipe 불통과, 데이터·일정 효과 분리 불가). 고정: `freeze_a2.py` → `FREEZE_A2.json`.
**학습 전에 고정한다. 결과를 본 뒤 4절 규칙을 바꾸지 않는다.** GPU는 0·1만(결정 180), Ollama 안 씀, GPU 0은 Ollama GPU(결정 181).

## 0. 질문

1. (a) A단계 하락의 원인이 teacher 정리(RC3c)인가, 학습 일정인가 — pilot_006 F recipe를 그대로 RC3c에 쓴 모델을 pilot_006 F(RC3)와 같은 seed로 비교한다(진단).
2. (b) 업데이트 양을 pilot_006 수준으로 맞춘 1 epoch recipe(R1')가 선택 규칙(결정 167)을 통과하는가.

## 1. 데이터

RC3c Full(`build/RC3c/full`, 1,356 레코드, sha256 `8329ca84…`) — A단계와 같다. A2에서 데이터는 바꾸지 않는다.

## 2. 학습(`train/configs_a2/`, `train/make_a2_configs.py`, lr 확인 `train/configs_a2/lr_check.json`)

| | (a) 대조 C-s<seed> | (b) R1' R1p-o<seed> |
|---|---|---|
| recipe | pilot_006 F 그대로: batch 1·accum 1, lr 5e-5, warmup 1, **2 epoch 선형 감쇠**, epoch 1 끝(step 1,356)에서 멈춤(`pilot_006/post/diag/train_diag.py`) | R1과 같음(1 epoch, 끝 lr 0, batch 1·accum 1, warmup 1), **lr 1e-4**(`train/train_a7.py`) |
| seed | 43·20261016·7, 모델 seed = 데이터 순서 seed(pilot_006 F 방식) | 데이터 순서 43·20261016·7, 모델 seed 43 |
| 멈춤 지점 lr | 2.50e-5(pilot_006 F43 epoch 1 지점 2.50e-5와 같음) | 끝에서 0 |
| lr 합(멈춤까지) | **0.0508**(pilot_006 F43 0.0698 × 1356/1861; 결정 183: 그대로 진행) | **0.0678**(의도 ≈ 0.068) |
| 저장 | 25·50·75·100% = step 339·678·1017·1356 | 같음 |
| 비교 대상 | pilot_006 F 같은 seed: F-s43 e1, F-s1016 e1, D-F7 100%(세션 4) | A단계 R1·R2 |

dry-run·tokenizer-check 12/12 통과(`train/configs_a2/dryrun.log`).

## 3. 평가 셀(PROTOCOL_v5, vLLM 0.30.0 BF16, LoRA 비병합, 동시 8, 17,408, seed_base 20261100)

- 학습 여섯 모델마다 100% checkpoint로 주 셋 151(selection_v2 98 + holdout 53)·valid98·aux, 각 k=4.
- 기준 셀 E-ref_F1016dev: pilot_006 F-s1016 e1 adapter(기존)로 valid98·aux k=4 — pilot_006에 s1016 개발 셋 셀이 없어 (a) 해석의 s1016 짝용으로 잰다(학습 아님).
- 선택(보고만): (b) 세 모델의 25·50·75% checkpoint, 주 셋 greedy k=1.

## 4. 판정과 해석 규칙(`analysis/select_a2.py`, 결정 179)

**(b) R1' 선택**(결정 167 규칙·문턱 그대로): 주 셋 seed sd(ddof 1) ≤ **3.0%p** 그리고 개발 셋 평균(세 모델 평균, valid98 + aux 149문항 평균) ≥ **64.19**.
둘 다 통과면 R1'를 B단계 recipe 후보로 둔다(B단계는 이 세션에 시작하지 않음). 아니면 후보 없음.

**(a) 해석(진단, 판정 아님)**: 같은 seed 짝 (a) − pilot_006 F를 개발 셋·주 셋에서 각각 낸다(짝: s43 = C-s43 대 F-s43 e1, s1016 = C-s1016 대 F-s1016 e1, s7 = C-s7 대 D-F7 100%).
- 개발 셋 평균 차(세 짝 평균) **≥ −2%p → "teacher 정리는 성능을 떨어뜨리지 않았다"** — A단계 하락의 주 원인은 학습 일정.
- **< −2%p → "teacher 정리가 성능을 떨어뜨렸다".**
- 두 해석에 따라 B단계 데이터 선택지(RC3c 사용 / 정리 기준 재검토 (c))를 정리해 보고. (a)의 업데이트 양이 pilot_006 F의 73%라는 점(결정 183)을 함께 적는다.

주 셋 평균은 recipe 선택에 쓰지 않는다(sd와 진단에만).

## 5. 보고 항목

표 1((a) 대 pilot_006 F 같은 seed: 주 셋·valid98·aux·구조 오류율), 표 2((b): 주 셋 sd·개발 셋 평균·구조 오류율, R1·R2와 비교), 4절 규칙 결과, lr 합·마지막 구간 loss·궤적,
A + A2를 합친 원인 해석(진단), `"od_role":"none"` 분석(C3), RC4 검증(C2), B단계 초안 갱신(C5), GPU 0·1 사용률·유휴·GPU 2 미사용 기록, Ollama `/api/ps` 확인 기록.

## 6. GPU 작업(`gpu/jobs_A2.json`, `gpu/scheduler8.py --gpus <GPU 0·1 UUID> --ollama-uuid <GPU 0 UUID>`, 예상 `gpu/plan_A2.json`)

| 우선 | 작업 |
|---:|---|
| 1 | C-s43, R1p-o43 |
| 2 | R1p-o1016, C-s1016 |
| 3 | C-s7, R1p-o7 |
| 4 | E-A2 × 6, E-ref_F1016dev |
| 5 | E-A2q × 3(선택) |

학습을 먼저 모두 돌리고 평가를 붙인다(지시 2.2). GPU를 고정하지 않으므로 GPU 0이 Ollama로 막히면 GPU 1이 다음 작업을 받는다(결정 181).

## 7. 고정 대상(`freeze_a2.py`)

이 PLAN, 결정 175–183, config 6개·DIFF·lr 확인·dry-run 로그, 학습 wrapper(`train_diag.py`, `train_a7.py`), 판정 도구(`select_a2.py`, `select_a.py`), 작업 표·스케줄러·서버(`scheduler8.py`, `serve7.sh`, `gpu_lib7.sh`), RC3c Full 데이터, 지문 세 개.
