# thinking 파이프라인 pilot 계획 (pipeline_pilot_001)

고정: 2026-10-06, 학습 시작 전. 결정은 `sft_dpo_inventory/DECISIONS.md`(2026-10-06)를 따른다.

## 목적과 범위

- 학습 → checkpoint 선택 → 평가가 끝까지 도는지 확인한다.
- 결과는 채택 판단에 쓰지 않는다.
- 업체 100, Ollama 호출, `ollama create`, prompt·SEMANTIC_CODE 변경은 없다.
- 실행 의미 코드 지문은 `791c4a68…`로 유지한다.
- 설정 탐색, 결과를 맞추기 위한 재학습·재평가는 하지 않는다.
- 단계가 실패하면 그 자리에서 멈추고 기록한다.

## 데이터

출처: `data/summary.json`. 생성물은 `training/generated/thinking_v003_t2pc_pilot/`(ignored)에 있다.

| | 레코드 | 질문 | 비고 |
|---|---:|---:|---|
| SFT | 40 | 12 | greedy 2, 표본 38. `compile_stop` 19 |
| DPO | 48 | 9 | constraint 38, semantic 10. `compile_stop` 25 |

- sha256: `sft_train.jsonl` 98fe815a…, `dpo_train.jsonl` 26f61ea0…, `manifest.json` d6c1bb74….
- 길이(`data/token_lengths_*.json`): 모두 한도 안이다.
  - SFT total 최대 9,133 / 9,216.
  - DPO prompt 7,314 / 7,424, chosen 1,593·rejected 1,270 / 1,920, total 8,898 / 9,216.

## 학습 설정

thor pilot_003 profile을 그대로 쓴다. 탐색은 없다.

- **SFT** — `training/configs/qwen3_8b_t2pc_thinking_pilot_sft.yaml`
  - base Qwen/Qwen3-8B@b968826d, BF16, SDPA, gradient checkpointing, AdamW(torch).
  - LoRA r 16 / alpha 32 / dropout 0.05. 대상: q, k, v, o, gate, up, down projection.
  - learning rate 5e-5, linear scheduler, warmup 1 step.
  - batch 1, accumulation 1, max_steps 12, seed 42. 40레코드 중 12개를 보므로 1 epoch가 되지 않는다(thor profile 그대로).
  - max_seq_length 9216. `thinking.loss_scope: full_response`(결정 3).
  - trainer 평가는 꺼진다. thinking valid 레코드가 없어 valid split이 비어 있기 때문이다.
- **DPO** — `training/configs/qwen3_8b_t2pc_thinking_pilot_dpo.yaml`
  - 고른 SFT checkpoint에서 시작한다. 실행 때 `resolved/`에 adapter 경로를 채운 사본을 만들어 쓴다.
  - reference: `strategy: precompute`(결정 9). 고정 SFT reference adapter로 log-prob을 학습 전에 계산한다.
  - learning rate 1e-5, beta 0.1, warmup 1 step, batch 1, accumulation 1, max_steps 8, seed 42.
  - 한도 9216 / 7424 / 1920. 같은 LoRA 설정.

## checkpoint 저장과 선택

- **저장 시점.**
  - SFT: 2 step마다(2, 4, 6, 8, 10, 12).
  - DPO: 2 step마다(2, 4, 6, 8).
  - config의 `save_steps: 2`, `save_total_limit: 6`이라 모두 남는다.
- **선택 규칙**(`select_checkpoint.py`):
  - 그 단계에서 저장한 checkpoint 중 valid grounding_ok가 가장 높은 것을 고른다.
  - 동점이면 더 이른 step을 고른다. 다른 지표로 동점을 풀지 않는다.
  - DPO 선택 후보는 DPO checkpoint뿐이다. base와 고른 SFT는 기준값으로만 남긴다.

## 평가 조건(HF-E와 같다)

- 스크립트: `eval_valid.py`.
- 세트: `reviewed_gold_v003_t2pc/sft_valid.jsonl` 16문항(sha256은 결과 meta에 남긴다).
- 모델·생성: base Qwen3-8B@b968826d(+ adapter), prompt 87048d0c, `enable_thinking=True`, greedy, max_new_tokens 8192, BF16/SDPA.
- pipeline: flat, 조건 계층 켬, condition_notes 끔, mock·legacy, 기준일 2026-09-25. `evaluate_vendor100.run_item`을 쓴다.
- 채점: 최종 grounding(정규화·조건 계층·검증 뒤)을 reviewed gold와 `evaluate_vendor100.grounding_check`로 비교한다(`grounding_ok`).
  - 첫 계획 응답 JSON의 일치(`first_raw_ok`)와 결과 종류는 참고로만 남긴다.
- 알려진 제약(결과 해석에 영향):
  - mock provider는 valid의 합성 장소명을 모른다. 해당 문항은 4cafcbdd(가람구), dbfd9d05·dd838f31·7fae41a3(솔빛시·해온시)다.
    - 장소 조회가 실패하면 운영 경로대로 모델에 장소 재질의가 간다. 재질의 수를 문항마다 남긴다.
    - gold grounding을 넣으면 16문항 모두 grounding_ok다(CPU 확인).
  - 16문항 중 9개는 gold도 `UNVERIFIED_TIMS_CONTRACT`로 멈춘다. 이 문항도 grounding으로 비교한다.
  - valid 16문항은 학습 질문과 같은 분포의 작은 세트다. 이 수치로 학습 효과를 판단하지 않는다.

## GPU

- 학습과 모든 valid 평가는 GPU 2(`CUDA_VISIBLE_DEVICES=2`)에서 순서대로 한다. HF-E와 같은 장치라서 장치 차이가 평가에 섞이지 않는다.
  - 시작 전에 `CLAUDE.md` 6번 확인을 한다(`gpu_check.txt`).
- GPU 3은 결정 9의 메모리 비교 측정(`memory_probe_precompute.py`)에만 쓴다.
  - 쓰기 전에 host `nvidia-smi`로 GPU 3의 사용 메모리와 프로세스를 확인한다. Ollama 모델이 있으면 쓰지 않는다.
  - Ollama API는 부르지 않는다.
- **메모리 비교 측정.**
  - thinking_prep_001의 shared_adapter 측정(48,200 MiB)과 같은 config·데이터·가장 긴 레코드로 잰다(LR 0, 3 step).
  - reference 방식만 precompute로 바꾼다. 학습이 아니며 adapter는 지운다.
  - 본 DPO 학습의 peak(`train_logs/dpo_nvidia_smi.txt`, profile)도 함께 기록한다. 다만 데이터가 달라(최대 total 8,898 대 9,133) 직접 비교하지 않는다.

## 실행 순서(`run_pilot.sh`)

1. GPU 확인.
2. base valid.
3. SFT 학습.
4. SFT checkpoint 6개 valid.
5. SFT 선택.
6. DPO config 확정.
7. DPO 학습.
8. DPO checkpoint 4개 valid.
9. DPO 선택.

메모리 비교 측정은 GPU 3에서 따로 돌린다.

## 성공 기준

파이프라인이 끝까지 돌고 다음 산출물이 모두 남는 것이다. 수치 기준은 없다.

- `gpu_check.txt`, `runs.log`.
- `valid/` 결과 11개: base 1, SFT 6, DPO 4. 원문은 `training/generated/pipeline_pilot_001/`(ignored)에 둔다.
- `train_logs/`: SFT·DPO 로그와 nvidia-smi 기록. profile과 trainer_state(loss, step 시간, 메모리)는 저장소 밖에서 복사한다.
- `selection_sft.json`, `selection_dpo.json`, `resolved/` DPO config.
- adapter·checkpoint는 저장소 밖 `/home/hwkim/sftdpo_work/pipeline_pilot_001/checkpoints/`에 둔다. 보고서에는 경로와 sha256만 적는다.
- `memory_compare/` 측정 결과.
- 끝에 실행 의미 코드 지문 `791c4a68` 확인.
