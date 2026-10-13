# p0_sft_001 사전 등록: P0 Gold-only vs Clean-Hybrid SFT

고정: 2026-10-13, 학습 시작 전. 이 커밋 뒤에는 hyperparameter·데이터·평가·분석 정의를 고치지 않는다. 바꿔야 하면 새 실험으로 나눈다.
따르는 문서: `CLAUDE.md`, `../DECISIONS.md`(결정 1–68).

## 1. 질문과 가설

**질문:** P0의 단순한 출력 contract를 clean gold로만 학습하면 충분한가, 아니면 검증된 P0-native thinking trace를 일부 넣는 것이 더 도움이 되는가?

- **H1 Gold-only 효과:** Gold-only SFT > Base(P0). 특히 first-response structural error가 줄어든다.
- **H2 Clean-Hybrid 추가 효과:** Clean-Hybrid ≥ Gold-only. semantic correctness에서 추가 이득이 있는지 본다.
- **H3 dimension_target:** v006 보강이 평가의 dimension_target, od_role ≠ dimension_target 성능을 올리는가.

**판정 규칙**(주 결과 = 네 셋 합친 403문항, semantic correctness, 문항 단위 paired):

| 결과 | 조건 |
|---|---|
| 개선 | 뒤 모델 − 앞 모델 > 0, exact McNemar 양측 p < 0.05 |
| 악화 | 차이 < 0, p < 0.05 |
| 차이 없음 | p ≥ 0.05. bootstrap 95% CI를 함께 적는다 |

- H2 해석:
  - 개선 → reasoning trace가 도움이 된다는 근거다.
  - 차이 없음 → 추가 이득 없음이다.
  - 악화 → trace가 noise일 가능성을 먼저 검토한다.
- H3는 부분집합 크기가 작아(아래 표) 기술 통계와 McNemar만 적고, 판정은 주 결과로만 한다.
- scope 역조회(9문항)는 학습 데이터 0건이라 성공 조건으로 삼지 않는다. 값만 기록한다.

## 2. 데이터

| 항목 | 값 |
|---|---|
| 기반 | `reviewed_gold_v006_p0` 154(v005 111 + batch006 43, 결정 67·68), sha256 `e792ee5e…` |
| Gold-only | `training/generated/p0_sft_001/gold_only/sft_train.jsonl` sha256 `bc71b940…`, 154 = 답만 154 |
| Clean-Hybrid | `training/generated/p0_sft_001/clean_hybrid/sft_train.jsonl` sha256 `f1cfdad0…`, 154 = reasoning 70 + 답만 84 |
| valid | 두 arm 모두 비움(고정 checkpoint) |
| 최종 답 | 두 arm 모두 Full canonical gold → P0 결정적 변환. 154/154 같음, 운영 경로 결과가 Full gold와 154/154 같음(`integrity.json`) |
| 손실 | `json_only`(결정 24). 손실 token은 두 arm에서 문항마다 같다(JSON + EOS). Hybrid의 thinking은 prompt 쪽 문맥 |
| trace | `selected_traces.jsonl`(sha256 `4016b8f9…`), 검토 `trace_review.json`(`79dcb129…`) |
| 오염 | 신규 43 겹침 0. `legacy_conservative_family_overlap = 16`(v005, 결정 68). 결정 15·54의 기존 예외 11 |
| Gap C(scope 역조회) | 0건 |

- 답만 있는 레코드는 기존 형식이다(`<|im_start|>assistant\n` 뒤에 JSON + EOS, 가짜 `<think>` 없음). 따라서 Gold-only는 thinking 없이 바로 JSON을 내는 쪽으로 학습될 수 있다. 결과 해석에서 thinking 길이를 함께 본다.

**평가 셋 사용 이력(independent final holdout이 아니다):**

| 셋 | 문항 | 이력 |
|---|---:|---|
| vendor100 | 100 | 평가 전용(결정 36). P0–P0.2 prompt 개발(ab_p0)에 썼다. v005와 template·family 겹침은 결정 15·54 예외 |
| valid98 | 98 | pilot_001 checkpoint 선택, P0.2 진단과 P0.3 설계 근거(ab_valid98). v005와 template·family 겹침은 결정 54 예외 |
| sel154 | 154 | P0.3 판정 1회(결정 61). 100문항은 pilot_002 checkpoint 선택에 쓴 selection_v1. 문항별 dt 실패를 ROOT_CAUSE에서 분석했고, 그 결과가 batch006 Gap A/B 설계의 동기가 됐다(학습 문항 겹침은 0) |
| aux_test_v1 | 51 | 판정에 쓰지 않는 보조 시험(결정 42). Ollama 기준 셀만 쟀고 P0 설계에는 쓰지 않았다 |

## 3. 학습 설정(두 arm 동일, 승인 recipe = pilot_001·002, 결정 24·28·53)

- config: `training/configs/qwen3_8b_p0_sft001_{gold_only,clean_hybrid}.yaml`(sha256 `4cedfa25…` / `b4450a92…`).
  - 다른 것은 data·output·profile 경로뿐이다(diff 확인).
- base: `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`(tokenizer 같음).
  - `HF_HOME=/data/hwkim/path_repeat_001/hf-cache`, offline. 받지 않는다.
- BF16, SDPA, gradient checkpointing(use_reentrant false), `enable_thinking=True` 렌더링.
- LoRA r16, α32, dropout 0.05. 대상은 q/k/v/o/gate/up/down_proj.
- AdamW(adamw_torch), lr 5e-5, linear scheduler, warmup 1 step.
- batch 1, accum 1, seed 42, max_seq_length 11,392.
- 2 epoch: 154 × 2 = 308 step 예상. 저장은 0.25마다(77, 154, 231, 308 예상), save_total_limit 6.
- early stopping 없음. hyperparameter 탐색 없음.
- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`(결정 17). checkpoint·adapter는 `/data/hwkim/p0_sft_001/`(저장소 밖)에 둔다.

## 4. checkpoint 선택(결정 68, 사용자 선택)

- **고정:** 각 arm의 2 epoch 끝 최종 adapter(`output_dir`의 save_model, 마지막 checkpoint와 같은 step)만 평가한다.
- 보호 평가셋(vendor100·valid98·sel154·aux_test_v1)과 selection_v1은 checkpoint 선택에 쓰지 않는다.
- 다른 checkpoint는 저장만 하고 평가하지 않는다. 학습 loss는 기록한다.

## 5. 실행 순서(`run_all.sh`, sha256 `e83978ff…`)

1. Gold-only 학습 → GPU 확인 → Clean-Hybrid 학습. 학습 전 `cell_guard precheck --path hf`(Ollama 모델 없음, GPU compute 프로세스 없음, 메모리 기준선).
2. 평가는 base → gold_only → clean_hybrid 순서다. 모델마다 sel154 → valid98 → vendor100 → aux_test_v1이며, 셀마다 precheck를 한다.
3. `analyze.py`.

- 순서는 결과를 보고 바꾸지 않는다. Ollama는 부르지 않는다(GPU 1장을 Ollama와 같이 쓰므로 모델이 올라와 있으면 시작하지 않는다).

## 6. 평가 조건(세 모델 동일)

- 스크립트: `eval_p0_hf.py`(sha256 `6179587f…`).
  - `thinking_prep_001/hf_eval_thinking.py`에서 P0 planner prompt와 `--gold`만 바꿨다.
- prompt: P0(`partial_p0.yaml`, prompt hash `d7f4c12a`). P0.1–P0.3는 쓰지 않는다.
- HF greedy, `enable_thinking=True`, max_new_tokens 8192, BF16·SDPA. 학습 모델은 base + adapter.
- pipeline:
  - flat, 조건 계층 켬, condition_notes 끔
  - provider mock·legacy, 기준일 2026-09-25
  - 재질의는 harness 기본
- code fingerprint `ab88a19e`, parser/composer 기준 `9cb8a39`.
- 셋(gold sha256): sel154 `aab80783…`, valid98 `2b9283b1…`, vendor100 `f99bc5fd…`, aux_test_v1 `3758d0dc…`.
- 원문: `training/generated/p0_sft_001/eval_raw/`(결정 33에 따라 커밋). 결과: `evaluation/{model}/{set}.json`.
- Full baseline은 historical reference로만 적는다(같은 조건으로 다시 재지 않는다).

## 7. 분석(`analyze.py`, sha256 `b9777eaa…`, 결과 전에 고정)

- **지표:** ab_p0_3·ab_valid98 함수 그대로다.
  - semantic correctness, answerable semantic correctness, refusal correctness
  - execution completion, grounding failure, grounding_ok
  - first-response structural error, malformed JSON(첫·최종)
  - eval_count·thinking 글자 중앙값
- **부분집합**(gold로 고정, 크기는 결과 전에 확인):

| 부분집합 | 문항 |
|---|---:|
| dimension_target 있음 | 89 (pickup 33, dropoff 30, both 26) |
| od_role ≠ dimension_target(Gap B형) | 35 |
| Gap A형 사건 표현(sel154 사전 분류 event) | 11 |
| bucket | 51 |
| scope 역조회 | 9 |
| refusal | 20 |

- **비교:** gold_only − base, clean_hybrid − gold_only, clean_hybrid − base.
  - 정답 0/1 차이 평균, paired bootstrap 95% CI, permutation p(seed 20261009)
  - 엇갈린 문항 수, exact McNemar p
  - 주 결과는 403문항 합, 셋별·부분집합별 값을 함께 적는다.

## 8. 중단·이탈 규칙

- **기반 장애**(crash, OOM, NaN loss, GPU 오류)면 그 단계에서 멈추고 `runs.log`에 남긴다.
  - 원인을 고친 뒤 그 단계만 같은 명세로 처음부터 다시 잰다. 이는 무효 측정을 대체하는 것이며 이탈로 적는다.
- 결과가 나쁘다고 다시 돌리거나, 데이터·trace 검토·hyperparameter를 바꾸지 않는다.
- Arm A 결과를 보고 Arm B 데이터를 고치지 않는다. 두 데이터는 학습 전에 freeze했다(커밋 `aabb789`).
- NaN, OOM, 재시작은 숨기지 않고 REPORT에 적는다.

## 9. 기록

- **학습(arm마다, `training/{arm}/`):**
  - GPU·CUDA·PyTorch·Transformers 판, checkpoint revision, dataset hash, seed
  - 시작·끝 시각, step별 training loss(trainer_state), checkpoint 경로·adapter sha256
- **평가:** 셀마다 시작·끝 시각, 장치 UUID, 생성 상한 도달 수.
- **산출물:** `REPORT.md`(한국어). STRUCTURALLY_REPAIRABLE 추가·27B teacher 반입·DPO·P0 수정·P0.4·pruning은 다음 단계로 미룬다.
