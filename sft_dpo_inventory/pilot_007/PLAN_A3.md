# pilot_007 A3단계 계획 — 고정본(학습 전)

작성 2026-10-20. 바탕: 결정 185–193, `A2_RESULTS.md`(teacher를 통째로 뺀 RC3c는 업데이트를 맞춰도 개발 셋 약 6%p 낮음, 업데이트를 늘리면 크게 좋아지고 끝까지 오르는 중).
고정: `freeze_a3.py` → `FREEZE_A3.json`. **학습 전에 고정한다. 결과를 본 뒤 4절 규칙을 바꾸지 않는다.** GPU 세 장, Ollama GPU = GPU 2(결정 191), Ollama 호출 없음.

## 0. 질문

teacher trace를 빼지 않고 (ii) 문장만 줄 단위로 지운 데이터(c2, RC5)에서, 업데이트 양을 더 늘린 1 epoch recipe 두 개(lr 1e-4·2e-4) 가운데
선택 규칙(결정 167·188)을 통과하는 것이 있는가. Full arm만 학습한다.

## 1. 데이터: RC5 Full(`build/RC5`, 결정 185·187)

| 항목 | 값 |
|---|---|
| 구성 | RC3 레코드(386질문) + teacher c2 편집(`teacher/c2_records_full.jsonl`) + batch010 승인분(승인 corpus v3) + S-focus 정답 표본 |
| c2 | 편집 350 trace·지운 줄 372, 빠짐 19(2.27%, 내용 손실), teacher 레코드 817(RC3c 339), teacher 질문 209 그대로(`teacher_c2.json`) |
| 질문 | 391(기존 343 + batch010 48), 유형 상한 칸에서 batch010 우선 → 밀려난 기존 39, 상한 초과 4, TV 0.0892 |
| Full 레코드 | 1,811(teacher 763 + 8b 1,048), teacher loss token 68.6%, sha256 `fd2ea453…` |
| 검사 | 두 arm dry-run·tokenizer-check·손실 token·마스크 audit 통과, 질문 목록 `22406d92…` 같음, 순서 파일 3개, 최대 길이 ≤ 12,288 |
| PF4 | 초안 protected_final_v1과 같은 grounding 3질문(Full 16 레코드) — 고치지 않음 |

## 2. recipe(`train/configs_a3/`, `train/make_a3_configs.py`, lr 확인 `train/configs_a3/lr_check.json`, wrapper `train/train_a7.py`)

| | R1'(A3-R1p) | R1''(A3-R1pp) |
|---|---|---|
| epoch / lr 끝 | 1 / 0 | 1 / 0 |
| batch / accumulation / warmup | 1 / 1 / 1 step | 같음 |
| learning rate | 1e-4 | 2e-4 |
| optimizer step | 1,811 | 1,811 |
| lr 합 | **0.0906** | **0.1811** |
| 저장 | 25·50·75·100% = 453·906·1358·1811 | 같음 |

- 나머지 pilot_006 F와 같음(Qwen3-8B@b968826d BF16, LoRA r16/α32/0.05 7개 projection, max_seq_length 12,288, by_source, thinking ON).
- 데이터 순서 seed 43·20261016·7, 모델 seed 43. 학습 6개. 판정은 100%(lr 0) checkpoint만, 25·50·75%는 보고만.
- 참고: pilot_006 F43 epoch 1 지점 lr 합 0.0698, A2 R1' 0.0678(RC3c), A2 (a) 0.0508. dry-run·tokenizer-check 12/12 통과(`train/configs_a3/dryrun.log`).

## 3. 평가 셀(PROTOCOL_v5, vLLM 0.30.0 BF16, LoRA 비병합, 동시 8, 17,408, seed_base 20261100)

- 학습 여섯 모델마다 100% checkpoint로 주 셋 151(selection_v2 98 + holdout 53)·valid98·aux, 각 k=4. 셀 라벨 `a3_r1p_o43_*` 등.
- 선택(보고만): 25·50·75% checkpoint, 주 셋 greedy k=1.

## 4. 선택 규칙(`analysis/select_a3.py`, 결정 188 = 결정 167 문턱 그대로)

1. recipe마다 **주 셋 seed sd** = 세 모델 주 셋 정답률(문항 정답률 평균)의 표본 표준편차(ddof 1) ≤ **3.0%p**.
2. recipe마다 **개발 셋 평균** = 모델마다 valid98 + aux 149문항 평균, 세 모델 평균 ≥ **64.19**(pilot_006 F s43·s7 기준값 66.19 − 2).
3. 둘 다 통과면 sd가 작은 쪽, 두 sd 차 < 0.5%p면 개발 셋 평균이 높은 쪽. 하나만 통과면 그쪽.
4. 통과 recipe가 있으면 다음 세션 B단계. 없으면 B단계로 가지 않고 보고.

주 셋 평균은 선택에 쓰지 않는다(sd와 진단에만). seed 3개 sd는 자유도 2라 흔들린다.

## 5. 보고 항목

결과표(recipe × 순서 seed: 주 셋·valid98·aux·구조 오류·`"od_role":"none"`·출력 (ii) 문장·영어 생각 비율), recipe별 sd·개발 셋 평균, 4절 결과,
pilot_006 F·A2 (a)·R1'·A단계 R1·R2와 데이터·lr 합 비교, c2가 출력 (ii) 문장을 줄였는지(pilot_006 모델 56–77%), 궤적, S = 3·5 예상 반폭(결정 190).

## 6. GPU 작업(`gpu/jobs_A3.json`, `gpu/scheduler8.py --gpus <세 장> --ollama-uuid <GPU 2>`, 예상 `gpu/plan_A3.json`)

| 작업 표 우선 | 작업 |
|---:|---|
| 1 | A3-R1p-o43, A3-R1pp-o43, A3-R1p-o1016 |
| 2 | A3-R1pp-o1016, A3-R1p-o7, A3-R1pp-o7 |
| 3 | E-A3 × 6 |
| 4 | E-A3q × 6(선택) |

(지시 표의 우선 1·2·3을 바퀴 나눔 때문에 1·2·3·4로 적음.) GPU 2 작업은 시작 전 `/api/ps` 빔 확인(결정 191).

## 7. 고정 대상(`freeze_a3.py`)

이 PLAN, 결정 185–193, c2 도구·결과, RC5 두 arm 데이터·manifest·검사·순서 파일, config 6개·DIFF·lr 확인·dry-run 로그, 학습 wrapper, 선택 도구(`select_a3.py`, `select_a.py`),
작업 표·스케줄러·서버, 지문 세 개.
