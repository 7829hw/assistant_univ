# pilot_004 계획

고정: 2026-10-14, 학습 시작 전 고정. 학습을 시작한 뒤에는 고치지 않는다(이탈은 REPORT에 따로 적는다).

따르는 문서:
- `CLAUDE.md`(SFT/DPO 규칙, 15번 실행 중 스크립트 수정 금지, 결정 100의 GPU 3장)
- `../DECISIONS.md`(결정 1–100)
- `../vendor100_protocol/PROTOCOL_v4.md`(확정 2026-10-14, sha256 `9e75c2a63d17def9f82525392e72bd2a291593b71451c79a96925e7075a2d7b1`)

하지 않는 것:
- prompt 변경, `SEMANTIC_CODE` 변경(실행 의미 코드 지문 `791c4a68`).
- 학습 설정 탐색, 결과를 맞추기 위한 재학습·재평가·재실행. 장치 장애나 guard로 멈춘 실행만 원인이 풀린 뒤 처음부터 다시 할 수 있고, 그 사실과 이유를 기록한다.
- 업체 100은 중단 규칙을 통과했을 때 업체 100 평가 단계에서만 쓴다. 데이터·checkpoint 선택·설정에 쓰지 않는다.
- Ollama 모델 등록·삭제, 컨테이너 조작.

## 1. 데이터

| 항목 | 값 |
|---|---|
| 판 | `training/generated/thinking_pilot004_t2pc`(`data/summary.json`, `data/build_pilot004.py`) |
| sha256 | sft_train `7cf221e6061d09ca78ffe6ba4936ae8a2bbff2b7090ddeae794baf08ea34f5db`, dpo_train `6c52d0477d0a0aa4199bf57cfc27f544602e3abf1a5c6b6b87a896ca0099a96b`, manifest `ac7e7a7a03366f71184be8512dadb1dda223b76961db04b5db6ad71246789e1b` |
| 규모 | **SFT 467(131질문), DPO 385쌍(58질문)**. 모두 train. pilot_003의 460·348은 그대로 들어 있다(SFT는 `loss_scope` 표시만 더해짐) |
| 더한 것 | 실차 대조 묶음 vLLM 8b 표본(결정 98): SFT 7(plain 3, trip 2, vacant 2), DPO 37(plain 16, trip 8, vacant 13). occupied는 32표본×6문항에서 정답 0 |
| 손실 범위(결정 86) | teacher 233 `full_response`(손실 token 81.8%), 8b 자체 234 `json_only`(18.2%) |
| 유형 상한(결정 88·92) | 실차 대조 묶음은 예외. 상한으로 빠진 레코드 0. TV(질문/레코드/DPO) 0.117 / 0.127 / 0.189, 예외 제외 0.016 / 0.080 / 0.087 |
| 검사 | dry-run·tokenizer-check 통과(SFT·DPO), 출처별 손실 token 검사 467/467 통과(`data/loss_tokens.json`), 평가 셋 새 겹침 0(결정 54 기존 겹침만, `data/overlap.json`) |

## 2. 학습 설정(pilot_003과 같고, SFT 손실 범위만 결정 86)

**SFT** — `training/configs/qwen3_8b_t2pc_thinking_pilot004_sft.yaml`(sha256 `57537ccc8fad1e24…`)
- pilot_003 SFT config와 같다. 다른 것: 데이터 경로, 출력 위치, `thinking.loss_scope: by_source`.
- base Qwen/Qwen3-8B@b968826d, BF16, SDPA, gradient checkpointing, LoRA r16/α32/dropout 0.05(7개 projection), AdamW lr 5e-5, warmup 1 step,
  batch 1, accum 1, seed 42, max_seq_length 11,392. **2 epoch.**
- **저장: epoch 1과 2(`save_steps: 0.5`). 예상 step 467, 934**(실제 값은 기록에 남긴다).

**DPO** — `training/configs/qwen3_8b_t2pc_thinking_pilot004_dpo.yaml`(sha256 `f192eab842b0b931…`)
- pilot_003 DPO config와 같다. 다른 것: 데이터 경로, 출력 위치.
- 고른 SFT checkpoint에서 시작한다(실행 때 adapter 경로를 채운 사본을 `resolved/`에 둔다). reference는 고정 SFT, log-prob 미리 계산(결정 9).
  손실 `full_response`(결정 26). lr 1e-5, β 0.1, warmup 1 step, batch 1, seed 42. 한도 11,392 / prompt 7,424 / completion 4,096. **1 epoch.**
- **저장: 50%와 100%(`save_steps: 0.5`). 예상 step 193, 385.**

**공통**: `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`(결정 17). 학습은 GPU 1장(결정 100). adapter·checkpoint는 `/home/hwkim/sftdpo_work/pilot_004/`(저장소 밖)에
두고 경로와 sha256만 기록한다.

## 3. checkpoint 선택(PROTOCOL_v4 5·8절)

- 경로: **vLLM 0.30.0 BF16, flashinfer attention·sampler, adapter는 LoRA(병합하지 않음)**, 서버 인자는 PROTOCOL_v4 3절(`serve3.sh`, `LORAS`로 checkpoint 2개).
- 셋: selection_v2(98문항), k=4, PROTOCOL_v4 3절 sampling(temperature 0.6, top_p 0.95, top_k 20, min_p 0, repetition_penalty 1, presence·frequency 0,
  max_tokens 8192, 호출 seed `EV.call_seed(20261100+k, id, 호출)`), **동시 요청 8**(`run_cell4.py`).
- 기준값: pilot_prep_007 `serving_vllm_fp8/runs/vllm-bf16-base_s1–4.json`(PROTOCOL_v4 5절, 다시 씀).
- 선택: 문항 평균 grounding_ok 최대, 같으면 U 낮은 것, 그다음 늦은 step. SFT 2개 중 하나를 고르고 그 SFT에서 DPO를 학습해 DPO 2개 중 하나를 고른다.
  분석 `selection/analyze_selection4.py`(sha256 `036d69af1b215f2e…`).
- checkpoint마다 기록: loss, step당 시간, peak 메모리(`train_logs/*_summary.json`), 평균 정답률, U·조용한 오답, 생성 상한·루프 수, 실차 통행량 오독 수,
  vicinity 빠짐(결정 94·97), 오류 유형, 표본별 장치·동시 요청·커널·요청 로그 요약.
- 실행: `run_train_select4.sh`(sha256 `6ea1434c3357da50…`). SFT 학습 → 선택 셀 8개(2 checkpoint × k=4)를 서버 3개(GPU 0·1·2)에 나눔 → DPO 학습 → 선택 셀 8개 → 중단 규칙.

## 4. 중단 규칙(결정 96, PROTOCOL_v4 8절)

고른 최종 checkpoint(고른 DPO)와 vLLM-base를 selection_v2에서 비교해 **둘 다** 만족할 때만 업체 100으로 간다.
1. grounding_ok 차이의 95% CI 하한 > 0.
2. U 비율 차이의 95% CI 하한 ≤ 0.

하나라도 만족하지 않으면 업체 100을 평가하지 않고 보고한다.

## 5. 업체 100 평가(중단 규칙 통과 때만)

PROTOCOL_v4 5·6절 그대로: 주 비교 vLLM-base → vLLM-최종(업체 100, k=8, 동시 요청 8), 지연은 고정 30문항 순차(base 대비 1.5배), 참고 셀 E(Ollama 0.40.3, k=8)와
27b(Ollama `qwen3.8:27b`, k=4, 결정 97), aux_test_v1(base·최종·E, k=4), valid98(base·최종, k=4, 보조), vicinity 빠짐 감시(모든 셋).
Ollama 셀은 측정 전에 버전과 digest를 확인하고 결정 55 guard를 켠다.

## 6. GPU 배정(결정 100)

- GPU 3장(0 `2445b100`, 1 `a5ce83d0`, 2 `48f798cc`=Ollama GPU). 쓰기 전에 매번 UUID·상태·메모리·다른 사용자 프로세스를 확인한다(`gpu_ok`, 기록 `gpu_check.txt`).
- 학습은 GPU 1장(0→2 순서로 처음 쓸 수 있는 GPU). 선택 셀과 업체 100 vLLM 셀은 서버 3개에 나눈다. 셀마다 장치를 meta에 남긴다.
- Ollama 측정(E, 27b) 중에는 Ollama GPU에서 다른 작업을 하지 않고, vLLM 서버도 내린다. 한 비교 안의 셀은 같은 backend·sampler·동시 요청 수다.
