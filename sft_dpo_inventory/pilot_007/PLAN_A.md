# pilot_007 A단계 계획 — 고정본(학습 전)

작성 2026-10-18. 바탕: 결정 165–174(`../DECISIONS.md`), 세션 4 사후 분석(`../pilot_006/post/POSTMORTEM.md`). 고정: `freeze_a.py` → `FREEZE_A.json`.
**학습을 시작하기 전에 고정한다. 결과를 본 뒤 3절 선택 규칙을 바꾸지 않는다.**

## 0. 질문

pilot_006 recipe(batch 1·accum 1, lr 5e-5, 2 epoch 일정의 epoch 1 지점 사용)는 주 셋 정답률이 데이터 순서 seed에 따라 약 10%p 달랐다(세션 4 2×2: 순서 효과 +7.45).
같은 데이터(RC3c)에서 lr이 끝까지 감쇠하는 1 epoch 일정(R1), 거기에 큰 batch를 더한 일정(R2)이 순서 seed 사이 흔들림을 줄이면서 개발 셋 성능을 지키는가.
Full arm만 학습한다(P arm 학습 없음).

## 1. 데이터: RC3c(`build/RC3c`)

| 항목 | 값 |
|---|---|
| 빌드 | `build/build7c.py` = RC3 + teacher 정리(결정 166: (a)–(e)·(ii) 불통과 teacher 레코드 통째로 제외, 문장 편집 없음) |
| 질문 | 369(RC3 386에서 17 빠짐) |
| Full 레코드 | 1,356(teacher 339 + 8b 1,017), `sft_train.jsonl` sha256 `8329ca84…`, teacher loss token 49.0% |
| Partial 레코드 | 1,312(B단계용, A단계 학습에 안 씀) |
| 검사 | 두 arm dry-run·tokenizer-check·손실 token·마스크 audit 통과(`build/RC3c/checks_summary.json`) |
| 정리 보고 | `teacher_cleanup.json`(빠진 trace 이유별, 약점 커버리지 전후). "소속" teacher 질문 4 → 1(정지 규칙 보고 항목, 56문항은 8b로 모두 남음) |

## 2. recipe와 학습(`train/configs/A-*.yaml`, `train/make_a_configs.py`, wrapper `train/train_a7.py`)

| | R1(감쇠 끝까지) | R2(감쇠 + 큰 batch) |
|---|---|---|
| epoch | 1(linear, 끝에서 lr 0) | 1 |
| batch / accumulation | 1 / 1 | 1 / 16 |
| learning rate | 5e-5 | 2e-4 |
| warmup | 1 step | 3%(= 3 step) |
| optimizer step | 1,356 | 85 |
| 저장(25·50·75·100%) | 339·678·1017·1356 | 21·42·64·85 |

- 나머지는 pilot_006 F와 같다(Qwen3-8B@b968826d BF16, LoRA r16/α32/dropout 0.05 7개 projection, max_seq_length 12,288, AdamW, by_source 손실, thinking ON).
- 모델 seed 43 고정, 데이터 순서 seed(`data_seed`) 43·20261016·7 → 학습 6개 `A-R{1,2}-o{43,1016,7}`.
- lr 계획은 dry-run 로그(`train/configs/dryrun.log`)로 확인: 두 recipe 모두 epoch 1 끝에서 lr 0, R2 accumulation 16·warmup 3.
- 쓰는 checkpoint는 100%(lr 0)뿐. 25·50·75%는 보고만.

## 3. 평가와 선택 규칙(`analysis/select_a.py`, 결정 167)

평가 셀(PROTOCOL_v5, vLLM 0.30.0 BF16, LoRA 비병합, 동시 8, 17,408, sampling seed_base 20261100): 학습한 모델마다 주 셋 151(selection_v2 98 + holdout 53), valid98, aux, 각 k=4.

1. recipe마다 **주 셋 seed sd** = 순서 seed 세 모델의 주 셋 정답률(문항 정답률 평균) 표본 표준편차(ddof 1).
2. recipe마다 **개발 셋 평균** = 모델마다 valid98 + aux 149문항의 문항 정답률 평균(문항 수 가중), 세 모델 평균.
3. 통과 = seed sd ≤ **3.0%p** 그리고 개발 셋 평균 ≥ **64.19**(= pilot_006 F 기준값 66.19 − 2%p; 기준값 = F-s43 e1 67.11과 D-F7 100% 65.27의 평균, 세션 4 채점).
4. 둘 다 통과면 seed sd가 작은 쪽. 두 sd 차가 0.5%p 미만이면 개발 셋 평균이 높은 쪽. 하나만 통과면 그쪽.
5. 둘 다 불통과면 B단계로 가지 않고 보고한다(B단계 초안은 그 상태로만 쓴다).

- **주 셋 평균은 선택 기준에 넣지 않는다**(B단계 판정 셋 오염 방지). 주 셋은 sd에만 쓴다.
- 한계: seed 3개로 낸 sd는 자유도 2라 그 자체가 크게 흔들린다. 문항 재표집 bootstrap 범위를 참고로 적지만 선택에 쓰지 않는다.

## 4. 보고 항목

recipe × 순서 seed 결과표(주 셋·valid98·aux), recipe별 seed sd·개발 셋 평균, 선택 결과와 근거, pilot_006 F(seed 셋 75.99 ± 5.74, 개발 셋 66.19)와 비교,
epoch 안 궤적(25·50·75% greedy k=1 — 시간이 있을 때만, 선택에 안 씀), 학습 시간·loss.

## 5. GPU 작업(`gpu/jobs_A.json`, `gpu/scheduler7.py` 스케줄러 하나, 예상 `gpu/plan_A.json`)

| 우선 | 작업 | 조건 |
|---:|---|---|
| 1 | A-R1-o43·o1016·o7 학습 | 이 PLAN 고정 |
| 2 | A-R2-o43·o1016·o7 학습 | 이 PLAN 고정 |
| 3 | E-A_<학습>(주 셋·valid98·aux k=4) | 그 학습 끝 |
| 4 | S-focus(결정 169) | 목록 커밋 뒤 작업 표에 추가 |
| 5 | J-b010 | batch010 겹침 검사 뒤 추가 |
| 6 | E-Aq_<학습>(25·50·75% greedy, 선택) | 그 학습 끝 |

작업 하나 = GPU 하나, 고정 worktree(이 고정 커밋), timeline `gpu/timeline.jsonl`. Ollama 안 씀(결정 172, `/api/ps` 빔 확인).

## 6. 고정 대상(`freeze_a.py`)

이 PLAN, RC3c 두 arm 데이터·manifest·검사 결과, 정리 도구(`build/build7c.py`, `teacher/teacher_checks7.py`, `build/rc_checks7.py`), 학습 wrapper·config 6개·DIFF·dry-run 로그,
선택 도구(`analysis/select_a.py`), 작업 표·스케줄러, 지문(SEMANTIC_CODE `791c4a68`, Full prompt `87048d0c`, Partial system `8b157c9a`).
