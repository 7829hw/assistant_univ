# 진짜 pilot 계획 (pilot_001)

고정: 2026-10-06, 학습 시작 전. 시작한 뒤에는 고치지 않는다(이탈은 REPORT에 따로 적는다).
따르는 문서: `CLAUDE.md`(SFT/DPO 규칙), `../DECISIONS.md`(결정 1–31), `../vendor100_protocol/PROTOCOL.md`(확정판),
`../vendor100_protocol/ADDENDUM_three_way.md`(보조 분석).

- 하지 않는 것: prompt 변경, SEMANTIC_CODE 변경, 학습 설정 탐색, 결과를 맞추기 위한 재학습·재평가·재실행.
- 실행 의미 코드 지문 `791c4a68`.
- 업체 100은 5단계(업체 100 평가)에서만 쓰고, checkpoint 선택·데이터·설정에 쓰지 않는다.

## 1. 데이터

| 항목 | 값 |
|---|---|
| 판 | `training/generated/thinking_v004_t2pc_r1`(ignored), 결정 27 적용(`data/summary.json`) |
| sha256 | sft_train b1b9d9b0…, dpo_train 3e10f7f5…, manifest 05fb982d… |
| 규모 | SFT 124(34문항), DPO 212쌍(26문항, constraint·semantic). 모두 train |
| 출처 | reviewed_gold_v004_t2pc(53문항) gold, base Qwen3-8B thinking trace(greedy + 표본 8) |
| SFT 손실 | `json_only`(결정 24). 124/124 레코드에서 손실 token이 `</think>` 뒤 JSON + EOS에만 있다(155–325개, `data/loss_tokens.json`) |

## 2. config(thor profile, 탐색 없음)

- **SFT** — `training/configs/qwen3_8b_t2pc_thinking_pilot001_sft.yaml`(sha256 0bc34687…)
  - base Qwen/Qwen3-8B@b968826d, BF16, SDPA, gradient checkpointing.
  - LoRA r16 / α32 / dropout 0.05, 7개 projection. AdamW, lr 5e-5 linear, warmup 1 step, batch 1, accum 1, seed 42.
  - max_seq_length 11,392.
  - **2 epoch = 248 step. 저장: 25%(= 0.5 epoch)마다 → step 62, 124, 186, 248.**
- **DPO** — `training/configs/qwen3_8b_t2pc_thinking_pilot001_dpo.yaml`(sha256 52e82df2…)
  - 고른 SFT checkpoint에서 시작(실행 때 adapter 경로를 채운 사본 `resolved/`).
  - reference: 고정 SFT, log-prob 미리 계산(결정 9). `full_response`(결정 26).
  - lr 1e-5, β 0.1, warmup 1 step, batch 1, accum 1, seed 42. 한도 11,392 / 7,424 / 4,096.
  - **1 epoch = 212 step. 저장: 25%마다 → step 53, 106, 159, 212.**
- 공통: `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`(결정 17). adapter·checkpoint는 `/home/hwkim/sftdpo_work/pilot_001/`(저장소 밖), 경로와 sha256만 기록한다.

## 3. checkpoint 선택(결정 28)

- 단계마다 저장한 4개 checkpoint를 valid98로 잰다.
- **grounding_ok가 가장 높은 checkpoint를 고른다. 동점이면 더 이른 step을 고른다.** 다른 지표로 동점을 풀지 않는다.
- DPO 선택 후보는 DPO checkpoint 4개뿐이다.

## 4. valid98 평가 조건

- 셋: `valid98/valid98_items.json`(sha256 512be78d…). valid100에서 heldout_v9/h03·heldout_v8/t10을 뺐다(결정 29). gold를 넣으면 98/98이다.
- 조건은 HF-E와 같다: base + adapter, prompt 87048d0c, `enable_thinking=True`, greedy, max_new_tokens 8192, BF16/SDPA.
- pipeline: flat, 조건 계층 켬, condition_notes 끔, provider mock(결정 16), 기준일 2026-09-25.
- 스크립트: `valid98/eval_valid98.py`.
- 기록(checkpoint마다):
  - 학습: loss, step당 시간, peak 메모리(nvidia-smi·torch).
  - valid98: grounding_ok, 분류, 지연, 생성 상한 호출 수, 평가 GPU UUID.
- GPU:
  - 학습은 GPU 2다.
  - checkpoint 평가는 GPU 2와, Ollama를 쓰지 않는 동안 GPU 3을 같이 쓴다.
  - GPU 3을 쓰기 전마다 host `nvidia-smi`로 GPU 3에 프로세스·메모리가 없는지와, `/api/ps`가 비었는지 확인한다.
  - 평가 GPU가 checkpoint마다 다를 수 있다(같은 RTX 6000 Ada). 장치 간 출력 동일성은 측정하지 않았다. 셀마다 장치를 기록한다.

## 5. 학습 모델 등록(결정 20, 31)

- 고른 SFT와 최종(고른 DPO) adapter를 각각 base snapshot(b968826d)에 bfloat16으로 merge한다(`training.merge_adapter`).
- `pilot_prep_001/gguf_convert.sh`로 base 변환본과 같은 llama.cpp b11434, bf16 → Q4_K_M으로 변환한다.
- base와 같은 방식(API blob + create, 같은 TEMPLATE·PARAMETER)으로 새 이름에 등록한다. 기존 모델은 덮어쓰거나 지우지 않는다.
  - `geoflow-qwen3-8b-pilot001-sft:q4km-hfthink`
  - `geoflow-qwen3-8b-pilot001-final:q4km-hfthink`
- **결정 31: 모델마다 렌더링 확인 10문항을 통과해야 업체 100을 잰다.**
  - 확인 항목: token 수 = HF, think 미지정 시 thinking 켬, thinking·본문 분리.
  - 문항은 base 때와 같은 v004 학습 질문 10개다.
  - 통과하지 못하면 그 모델의 Ollama 측정은 하지 않고 보고한다.

## 6. 업체 100 평가(PROTOCOL 확정판 + ADDENDUM)

- **HF 경로(GPU 2):** `thinking_prep_001/hf_eval_thinking.py --condition-check --adapter …`. SFT, 최종 각 1회.
  - 기준 HF-E(84)는 같은 명세(지문 791c4a68, prompt, revision, 생성 설정, 기준일, provider, gold, 순서, GPU 2)라 기록을 쓴다.
- **운영 경로(Ollama, GPU 3):** `evaluate_vendor100.py … llm --model M --reference-date 2026-09-25 --condition-check --model-think auto`. 문항마다 모델 내림. SFT, 최종 각 1회.
  - **결정 31:** 학습 모델 측정 직전에 Ollama 버전을 확인한다.
    - 0.35.1이면 pilot_prep_003의 E(79)·B-conv(77)를 쓴다.
    - 다르면 E와 B-conv를 같은 버전에서 다시 잰 뒤 학습 모델을 잰다(이전 값도 기록).
- **순서:** HF 셀(SFT → 최종) → Ollama 버전 확인 → Ollama 셀(SFT → 최종). Ollama 측정 중 다른 Ollama 호출이나 HF 측정을 하지 않는다.
- **판정:** PROTOCOL 7절(주 비교 = 최종 대 기준, SFT는 참고).
  - 개선: McNemar 양측 p < 0.05(증가), U 순증 ≤ 0, 조용한 오답 순증 ≤ 0.
  - 악화: 반대 방향 유의, U·조용한 오답 순증 > 0, 운영 셀 지연 중앙값 > 기준 × 1.5.
  - 판정은 HF 경로와 운영 경로를 따로 적는다.
- **보조 분석:** ADDENDUM_three_way(E·B-conv·학습 모델), family 분리(결정 15). 판정에 쓰지 않는다.
- 재실행하지 않는다. 기반 장애만 PROTOCOL 5절대로 처리한다. 측정이 끝날 때마다 커밋·push한다.

## 7. 성공 기준

- 위 단계가 끝까지 돌고 산출물이 남는 것.
- 판정 결과(개선·차이 없음·악화)는 성공 기준이 아니며, 나온 그대로 적는다.
