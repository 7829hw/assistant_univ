# pilot_002 계획

고정: 2026-10-08, 학습 시작 전. 학습을 시작한 뒤에는 고치지 않는다(이탈은 REPORT에 따로 적는다).

따르는 문서:
- `CLAUDE.md`(SFT/DPO 규칙)
- `../DECISIONS.md`(결정 1–54)
- `../vendor100_protocol/PROTOCOL_v2.md`(확정 2026-10-08, sha256 `f129bdd9dab64b61bd728078c78dc38ad9316da9f1c3c92c3b291f0940eae031`)

하지 않는 것:
- prompt 변경, SEMANTIC_CODE 변경.
- 학습 설정 탐색, 결과를 맞추기 위한 재학습·재평가·재실행.
- 업체 100은 6단계(평가)에서만 쓴다. 데이터·checkpoint 선택·설정에 쓰지 않는다.

실행 의미 코드 지문은 `791c4a68`이다.

## 1. 데이터

| 항목 | 값 |
|---|---|
| 판 | `training/generated/thinking_pilot002_t2pc`(`data/README.md`, `data/summary.json`) |
| sha256 | sft_train `398d19912b3dc6682e734979baf300a448bcf3c5c1031fcb7bd774350e63a14c`, dpo_train `4047769f3ed7753e70c50fd243f476ef3dfae68ee17893780c8a0fb36cbd0992`, manifest `ca029a3eb09b1e24ead921527323c6ab907b11c1df4cf02616c0f071c12770aa` |
| 규모 | SFT 379(107질문), DPO 288쌍(45질문). 모두 train |
| 출처 | gold `reviewed_gold_v005_t2pc`. SFT는 HF base trace 210 + teacher(qwen3.8:27b) 169. DPO는 HF base trace 쌍만 |
| SFT 손실 | `json_only`(결정 24). 379/379 레코드에서 손실 token이 `</think>` 뒤 JSON + EOS에만 있다(132–338개, `data/loss_tokens.json`) |
| 겹침 | 질문·id는 네 평가 셋 모두 0. valid98·업체 100의 template·family 겹침은 결정 54로 그대로 둔다(`data/overlap.json`) |

## 2. config(pilot_001과 같음, 결정 53)

**SFT** — `training/configs/qwen3_8b_t2pc_thinking_pilot002_sft.yaml`(sha256 `ff2c3b9a…`)
- pilot_001 SFT config와 같다. 다른 것은 데이터 경로와 출력 위치뿐이다.
- base Qwen/Qwen3-8B@b968826d, BF16, SDPA, gradient checkpointing.
- LoRA r16 / α32 / dropout 0.05, 7개 projection.
- AdamW, lr 5e-5 linear, warmup 1 step, batch 1, accum 1, seed 42. max_seq_length 11,392.
- **2 epoch = 758 step. 저장: 전체 step의 25%(= 0.5 epoch, 190 step)마다 → 190, 380, 570, 758.**

**DPO** — `training/configs/qwen3_8b_t2pc_thinking_pilot002_dpo.yaml`(sha256 `93eb7491…`)
- pilot_001 DPO config와 같다. 다른 것은 데이터 경로와 출력 위치뿐이다.
- 고른 SFT checkpoint에서 시작한다. 실행 때 adapter 경로를 채운 사본을 `resolved/`에 둔다.
- reference는 고정 SFT이고, log-prob을 미리 계산한다(결정 9). 손실은 `full_response`(결정 26).
- lr 1e-5, β 0.1, warmup 1 step, batch 1, accum 1, seed 42.
- 한도: max_length 11,392, max_prompt_length 7,424, max_completion_length 4,096.
- **1 epoch = 288 step. 저장: 25%마다 → 72, 144, 216, 288.**

**공통**
- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`(결정 17).
- adapter·checkpoint·merge 모델·GGUF는 `/home/hwkim/sftdpo_work/pilot_002/`와 `/home/hwkim/sftdpo_work/gguf/`(저장소 밖)에 둔다. 경로와 sha256만 기록한다.
- 저장 step은 trainer가 `save_steps: 0.25`를 올림해 정한다. 위 숫자는 예상값이고, 실제 값은 기록에 남긴다.

## 3. checkpoint 선택(결정 28·41·53)

- 단계마다 저장한 4개 checkpoint를 selection_v1으로 잰다.
- **selection_v1 grounding_ok가 가장 높은 checkpoint를 고른다. 동점이면 더 이른 step을 고른다.** 다른 지표로 동점을 풀지 않는다(`../pipeline_pilot_001/select_checkpoint.py`).
- DPO 선택 후보는 DPO checkpoint 4개뿐이다.
- valid98은 고른 SFT와 최종에 대해서만 한 번씩 보조로 잰다. 선택에 쓰지 않는다.

## 4. selection_v1 평가 조건

- 셋: `../pilot_prep_005/sets/selection_items.json`(100문항, sha256 `405af9c8…`, PROTOCOL_v2 7절). base HF-E 기준값은 82다.
- 조건은 HF-E와 같다.
  - base + adapter, prompt 87048d0c, `enable_thinking=True`, greedy, max_new_tokens 8192, BF16/SDPA.
  - pipeline: flat, 조건 계층 켬, condition_notes 끔, provider mock, 기준일 2026-09-25.
- 스크립트: `../pilot_prep_005/sets/eval_set.py`(sha256 `cc63995c…`). base 기준값을 잰 것과 같다.
- 실행: `run_train_select.sh`.
- 기록(checkpoint마다, `selection/SUMMARY`):
  - 학습: loss, step당 시간, peak 메모리(nvidia-smi·torch).
  - selection_v1: grounding_ok, 분류, 지연, 생성 상한 호출 수, 루프 판정 수(결정 40-D 기준을 모든 호출의 thinking에 적용), 평가 GPU UUID.
- valid98 보조: `../pilot_001/valid98/eval_valid98.py`, 같은 조건(sha256 `512be78d…` 목록).

**GPU(CLAUDE.md 5·6번)**
- 단계마다 host `nvidia-smi`로 UUID, 메모리, 다른 프로세스를 확인한다(`gpu_check.txt`).
- GPU 3에 다른 사용자 프로세스가 없으면 학습과 평가에 GPU 3을 쓴다. 있으면 Ollama 모델이 올라가 있지 않은 GPU 2를 쓴다. 둘 다 안 되면 멈춘다.
- checkpoint 평가는 두 GPU가 모두 비어 있으면 둘에 나눠 돌린다. HF 경로는 두 장치에서 같은 출력을 냈다(결정 43).
- 학습·평가 중에는 Ollama를 부르지 않는다. aux_test_v1의 Ollama 기준 셀(작업 1)이 끝난 뒤에 시작한다.

## 5. 학습 모델 등록(결정 20·31·53)

- 고른 SFT와 최종(고른 DPO) adapter를 각각 base snapshot(b968826d)에 bfloat16으로 merge한다(`training.merge_adapter`, CPU).
- `../pilot_prep_001/gguf_convert.sh`로 Q4_K_M으로 변환한다(llama.cpp b11434, bf16 → Q4_K_M). base 변환본과 같다.
- base와 같은 방식(API blob + create, 같은 TEMPLATE·PARAMETER)으로 새 이름에 등록한다. 기존 모델은 덮어쓰거나 지우지 않는다.
  - `geoflow-qwen3-8b-pilot002-sft:q4km-hfthink`
  - `geoflow-qwen3-8b-pilot002-final:q4km-hfthink`
- **결정 31: 모델마다 렌더링 확인 10문항을 통과해야 다음 단계로 간다.**
  - 확인 항목: token 수 = HF, think 미지정 시 thinking 켬, thinking·본문 분리.
  - 문항은 base·pilot_001 때와 같은 10개다(`../pilot_001/ollama/render_check.py`).
  - 통과하지 못하면 그 모델의 Ollama 측정은 하지 않고 보고한다.

## 6. 평가(PROTOCOL_v2 그대로)

**셀과 기준**(PROTOCOL_v2 3절)

| 경로 | 기준 | 비교 |
|---|---|---|
| HF | HF-E: 업체 100 84, aux_test_v1 27 | HF-SFT, HF-최종 |
| 운영(Ollama) | E: 업체 100 79, aux_test_v1(작업 1의 첫 측정) | Ollama-SFT, Ollama-최종 |
| 삼자(보조, ADDENDUM) | E · B-conv(업체 100 77, aux 작업 1) · 학습 모델 | |

- 주 비교는 최종 대 기준이다. SFT는 참고다. 판정은 업체 100으로만 한다. aux_test_v1은 같은 셀·지표로 함께 보고한다.

**명령**
- HF 업체 100: `../thinking_prep_001/hf_eval_thinking.py --condition-check --adapter …`(pilot_001과 같음).
- HF aux: `../pilot_prep_005/sets/eval_set.py --items aux_test_items.json --adapter …`(base 기준값과 같은 스크립트).
- Ollama: `evaluate_vendor100.py --gold {업체 100 gold.yaml | aux_test/aux_test_gold.yaml} llm --model M --reference-date 2026-09-25 --condition-check --model-think auto`.
  - Q4_K_M, num_predict 미지정, 문항마다 모델 내림.

**순서**
1. HF 셀: SFT → 최종. 각각 업체 100 → aux.
2. Ollama 버전 확인(결정 31).
   - 0.35.1이면 기존 E·B-conv(업체 100 79·77, aux 작업 1 값)를 쓴다.
   - 다르면 E와 B-conv를 그 버전에서 업체 100·aux 모두 다시 잰 뒤 학습 모델을 잰다(이전 값도 기록).
3. Ollama 셀: SFT → 최종. 각각 업체 100 → aux.

**격리**
- Ollama 측정 중에는 다른 Ollama 호출이나 HF 작업을 하지 않는다.
- HF 셀은 Ollama 모델이 내려간 상태에서 한다.
- 셀마다 한 번만 잰다. 기반 장애만 PROTOCOL 5절대로 처리한다. 측정이 끝날 때마다 커밋·push한다.

**판정**(PROTOCOL_v2 2.1절과 PROTOCOL 7절)
- 개선: McNemar 양측 p < 0.05(증가), U 순증 ≤ 2, 조용한 오답 순증 ≤ 2.
- 악화: 반대 방향 유의, U 순증 ≥ 3, 조용한 오답 순증 ≥ 3, 운영 셀 지연 중앙값 > 기준 × 1.5.
- 판정은 HF 경로와 운영 경로를 따로 적는다.

**보조 분석**(판정에 쓰지 않음)
- ADDENDUM_three_way(E·B-conv·학습 모델).
- family 분리(결정 15, 결정 54의 겹침 문항 포함).
- 지연, 루프.

**산출물**: `vendor100/`(업체 100), `aux_test/`(aux_test_v1), `REPORT.md`, `../VENDOR100_ACCURACY.md`의 pilot_002 절.

## 7. 결정 31의 안전장치

- 등록한 학습 모델마다 렌더링 확인 10문항을 통과해야 그 모델의 Ollama 셀을 잰다.
- 학습 모델의 Ollama 측정 직전에 버전을 확인한다. E·B-conv를 잰 버전(0.35.1)과 다르면 E·B-conv를 먼저 같은 버전에서 다시 잰다.
  - 판정과 삼자 비교에는 같은 버전의 값을 쓰고, 이전 값도 함께 적는다.
- 장치: 업체 100의 E·B-conv는 GPU 3 기록을 재사용한다(결정 32-1). 학습 모델 셀은 GPU 2에서 재므로, 기준 셀과 장치가 다르다는 점을 결과에 적는다.
  - aux_test_v1의 E·B-conv는 GPU 2에서 쟀다.

## 8. 성공 기준

- 위 단계가 끝까지 돌고 산출물이 남는 것.
- 판정 결과(개선·차이 없음·악화)는 성공 기준이 아니며, 나온 그대로 적는다.
