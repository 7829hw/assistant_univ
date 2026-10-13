# pilot_003 계획

고정: 2026-10-13, 학습 시작 전 고정. 학습을 시작한 뒤에는 고치지 않는다(이탈은 REPORT에 따로 적는다).

따르는 문서:
- `CLAUDE.md`(SFT/DPO 규칙, 결정 83의 GPU 0–3 예외)
- `../DECISIONS.md`(결정 1–83)
- `../vendor100_protocol/PROTOCOL_v3.md`(확정 2026-10-12, sha256 `9964cc70f3a8ce2b995f1d3ec426194730756deab9c034c6bf1f6142fe53bafa`)

하지 않는 것:
- prompt 변경, `SEMANTIC_CODE` 변경(실행 의미 코드 지문 `791c4a68`).
- 학습 설정 탐색, 결과를 맞추기 위한 재학습·재평가·재실행. 결정 55나 장치 장애로 멈춘 표본만 원인이 풀린 뒤 처음부터 다시 잴 수 있고, 그 사실과 이유를 기록한다.
- 업체 100은 중단 규칙을 통과했을 때 업체 100 평가 단계에서만 쓴다. 데이터·checkpoint 선택·설정에 쓰지 않는다.
- Ollama 모델 등록·삭제(결정 82의 정리는 끝났다). 운영 경로는 HF BF16이다(결정 76).

## 1. 데이터

| 항목 | 값 |
|---|---|
| 판 | `training/generated/thinking_pilot003_t2pc`(`data/README.md`, `data/summary.json`) |
| sha256 | sft_train `f19a308bd51a023665c4e952182afb5b930f2e1e4ee4eab4490a17be79e31a4d`, dpo_train `64c109358ddb7b1a831fb3eea5e2eb0896b88830b757da6f7fd6bda25ad46e7e`, manifest `c16d4cb2e81c7dda92fa3ed5593b5b70393ddc80cccb045d9766585439c9a9c1` |
| 규모 | SFT 460(131질문), DPO 348쌍(53질문). 모두 train |
| gold | `reviewed_gold_v006_t2pc`(SFT 135 = v005 111 + batch006 24, 결정 80) |
| 검사 | dry-run·tokenizer-check 통과, SFT 손실 token이 JSON에만 있음(460/460), 평가 셋 새 겹침 0(결정 54 기존 겹침만) |

## 2. 학습 설정(pilot_002와 같음)

**SFT** — `training/configs/qwen3_8b_t2pc_thinking_pilot003_sft.yaml`(sha256 `70c4d06c1bcec1e0…`)
- pilot_002 SFT config와 같다. 다른 것은 데이터 경로, 출력 위치, 저장 시점뿐이다.
- base Qwen/Qwen3-8B@b968826d, BF16, SDPA, gradient checkpointing, LoRA r16/α32/dropout 0.05(7개 projection), AdamW lr 5e-5, warmup 1 step,
  batch 1, accum 1, seed 42, max_seq_length 11,392. 손실 `json_only`(결정 24). **2 epoch.**
- **저장: epoch 1과 2(`save_steps: 0.5`). 예상 step 460, 920**(실제 값은 기록에 남긴다).

**DPO** — `training/configs/qwen3_8b_t2pc_thinking_pilot003_dpo.yaml`(sha256 `7ee307331c9f3563…`)
- pilot_002 DPO config와 같다. 다른 것은 데이터 경로, 출력 위치, 저장 시점뿐이다.
- 고른 SFT checkpoint에서 시작한다(실행 때 adapter 경로를 채운 사본을 `resolved/`에 둔다). reference는 고정 SFT, log-prob 미리 계산(결정 9).
  손실 `full_response`(결정 26). lr 1e-5, β 0.1, warmup 1 step, batch 1, seed 42. 한도 11,392 / prompt 7,424 / completion 4,096. **1 epoch.**
- **저장: 50%와 100%(`save_steps: 0.5`). 예상 step 174, 348.**

**공통**: `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`(결정 17). 학습은 GPU 1장(결정 83). adapter·checkpoint는
`/home/hwkim/sftdpo_work/pilot_003/`(저장소 밖)에 두고 경로와 sha256만 기록한다.

## 3. checkpoint 선택(PROTOCOL_v3 7절, 결정 73·78)

- 경로: HF BF16(base + adapter, 병합하지 않음). Ollama 변환·등록은 하지 않는다.
- 셋: selection_v2(98문항, `../calibration_001/selection_v2_items.json` sha256 `ee5c02a8…`). 실행에는 selection_v1 모음(`../conversion_diag/selection_gold.yaml`)에
  `--only selection/selection_v2_ids.txt`(98개, sha256 `0db835ee…`)를 준다.
- 생성: PROTOCOL_v3 3절(sampling, temperature 0.6, top_p 0.95, top_k 20, min_p 0, repetition_penalty 1, enable_thinking, max_new_tokens 8192),
  k=4, 표본 k의 회차 seed 20261100+k, 호출 seed `EV.call_seed`. 스크립트 `../thinking_prep_001/hf_eval_thinking.py`(sha256 `b927f62f…`).
- **기준값: HF-base를 같은 조건으로 selection_v2, k=4로 새로 잰다(PROTOCOL_v3 7절 2: "한 번 잰다").** calibration_001의 HF-base(selection_v1, 같은 seed)
  기록은 선택 기준값으로 쓰지 않고, 재현 확인으로만 같은 98문항을 비교해 적는다.
- 선택(7절 4): 문항 평균 grounding_ok가 가장 높은 checkpoint. 같으면 U 비율이 낮은 것, 그다음 늦은 step. SFT 2개 중 하나를 고르고, 그 SFT에서 DPO를
  학습해 DPO 2개 중 하나를 고른다. 분석 `selection/analyze_selection.py`(sha256 `439a7e01…`, analyze_cal과 같은 계산, 비교마다
  `default_rng(20261109)`).
- checkpoint마다 기록: loss, step당 시간, peak 메모리(`train_logs/*_summary.json`), 문항 평균 정답률, U·조용한 오답 비율, 지연, 생성 상한 호출 수,
  루프 호출 수(결정 40-D 기준), 실차 통행량 오독(`occupied_misread`) 수, 오류 유형, 안정 정답 문항 수, 표본별 장치.
- 보조 기록(선택에 쓰지 않음): 고른 SFT와 최종의 valid98 greedy(`../pilot_001/valid98/eval_valid98.py`, pilot_002와 같은 조건). valid98 h30(실차 통행량) 확인에 쓴다.

## 4. 중단 규칙과 업체 100(PROTOCOL_v3 5–7절을 따른다)

- 중단 규칙(7절 5, 결정 73의 HF 경로 적용): 고른 최종 checkpoint(고른 DPO)의 HF-base → checkpoint grounding_ok 차이 95% CI 하한이 0보다 클 때만
  업체 100으로 간다. 아니면 업체 100을 재지 않고 보고한다.
- 업체 100 절차·판정·셀·k·지연 기준·재지 않는 셀은 PROTOCOL_v3 5·6절 그대로다(주 비교 HF-base → HF-최종 k=8, 참고 셀 E 연속 방식 k=8, aux_test_v1 HF-base·HF-최종 k=4).
  E 참고 셀 전에 Ollama 버전과 E digest를 확인한다(결정 31).

## 5. GPU 배정(결정 83)

- GPU 0–3을 쓴다. 쓰기 전에 매번 UUID·상태·메모리·다른 사용자 프로세스를 확인하고(`gpu_lib.sh` `gpu_ok`, 기록 `gpu_check.txt`), 다른 프로세스가 있으면 그 GPU를 쓰지 않는다.
- 장치 일치 확인(`device_check/compare.json`): HF sampling 5문항(8호출)이 GPU 0·1·2에서 GPU 3과 바이트 단위로 같았다. 그래서 **표본을 GPU에 자유롭게 나눈다.**
- 학습은 0→3 순서로 처음 쓸 수 있는 GPU 1장. 학습 중에는 나머지 GPU에서 표본을 돌린다(HF-base 기준값, valid98 보조).
- Ollama 측정(E 참고 셀) 중에는 GPU 3에서 HF를 돌리지 않는다. 학습·선택 중에는 Ollama를 부르지 않는다.
- 표본마다 장치를 결과 meta(`--record-env`)와 `runs.log`에 남긴다.

## 6. 실행

- `run_train_select.sh`(sha256 `f0b98c44…`): SFT 학습 ‖ HF-base 기준값 → SFT 선택 → DPO 학습 ‖ 고른 SFT valid98 → DPO 선택·중단 규칙 → 최종 valid98.
  단계마다 커밋·push. 표본 실행기 `hf_samples.sh`(sha256 `ce93eb71…`).
- 원문(thinking 포함)은 `training/generated/pilot_003/raw/`(ignore). 기록(json·log)은 커밋한다.
