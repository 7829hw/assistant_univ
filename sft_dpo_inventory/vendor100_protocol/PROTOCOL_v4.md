# 업체 100 평가 절차 v4 (pilot_004) — **확정(2026-10-14, 사용자)**

작성: 2026-10-14(결정 90–94). 상태: **확정(2026-10-14, 사용자; 결정 95–100).** 정밀도 BF16(결정 95), 중단 규칙의 U 조건(결정 96), 참고 셀 27b와 vicinity 보고 범위(결정 97), GPU 배정(결정 100)을 반영했다.

- PROTOCOL_v3(확정 2026-10-12, sha256 `9964cc70f3a8ce2b995f1d3ec426194730756deab9c034c6bf1f6142fe53bafa`)을 이어받는다. 아래에서 바꾼 것만 다르고, 나머지는 v3 원문이 우선한다.
- v1–v3, `ADDENDUM_three_way.md`는 고치지 않는다. 확정한 뒤에는 이 문서를 고치지 않고, 바꿔야 하면 새 판을 만든다.
- 근거 자료: `../serving_vllm/REPORT.md`(vLLM BF16 경로 확인), `../serving_vllm_fp8/REPORT.md`(flashinfer, FP8, 동시 요청, 지연), `../pilot_prep_007/REPORT.md`.

## 1. 바뀌는 것

| 항목 | v3 | v4 |
|---|---|---|
| 운영 경로 | HF transformers BF16(결정 76) | **vLLM 0.30.0**(OpenAI 호환 서버), base Qwen3-8B@b968826d + 학습 adapter를 LoRA로(병합하지 않음) |
| attention·sampler | transformers SDPA, HF `generate` | **flashinfer attention backend + flashinfer sampler**(결정 90, 서버 로그로 확인) |
| 정밀도 | BF16 | **BF16**(결정 95, 4절) |
| 입력 | HF `render_prompt` | 같은 HF `render_prompt` + 같은 tokenizer의 **token id열을 직접** `/v1/completions`에 넘김 |
| 생성 단위 | 프로세스 하나, 순차 | **동시 요청**(정답률 셀), 지연은 순차로 따로(결정 93) |
| seed | 호출별 seed로 표본 재현 | 호출별 seed를 그대로 주지만 **표본은 바이트 재현되지 않는다**(결정 93). 판단은 통계로만 |
| 실제 적용 sampling 값 | 결과 meta(요청값) | **서버 요청 로그**로 확인해 셀 meta에 요약(결정 93) |
| checkpoint 선택·업체 100 판정 | HF BF16 sampling | **vLLM 동시 요청 sampling**(같은 정밀도·커널·동시 요청 수) |
| 지연 기준 | 같은 경로 HF-base 대비 1.5배 | **같은 경로·같은 정밀도의 base 대비 1.5배, 고정 문항 일부의 순차 측정** |
| 참고 셀 | E(Ollama 0.35.1 기록), 연속 방식 | **E(Ollama 0.40.3, 결정 87)**와 **27b(Ollama `qwen3.8:27b`, 결정 97)**, 연속 방식 |
| 중단 규칙 | 정답률 CI 하한 > 0 | **정답률 CI 하한 > 0 그리고 U 차이 CI 하한 ≤ 0**(결정 96, 8절) |
| 감시 지표 | – | **vicinity 빠짐**(결정 94), 판정에 쓰지 않음 |

그대로인 것: 셋(2절), 판정 지표·규칙(6절), k(선택 4, 업체 100 8, aux 4), 업체 100·aux_test_v1은 평가 전용, U·조용한 오답 정의, family 분리 보고, 결정 55 guard.

## 2. 셋

v3 2절과 같다(selection_v2 98, aux_test_v1 51, 업체 100 100, sha256 그대로).

## 3. 생성 설정과 실행 조건

| 항목 | 운영 경로(vLLM, 판정) | 참고 셀 E(Ollama) |
|---|---|---|
| 엔진 | vLLM **0.30.0**, venv `/home/hwkim/sftdpo_work/vllmvenv`(uv 0.12.20의 standalone CPython 3.12.14, 결정 90), torch 2.13.0+cu130, flashinfer 0.6.18.post1, venv의 CUDA 13 툴킷(nvcc·crt·nvvm 13.0.88), `libcudart.so` 링크 폴더(`/home/hwkim/sftdpo_work/cuda_link`) | Ollama **0.40.3**, `qwen3:8b`(digest `500a1f067a9f`), 공식 TEMPLATE |
| 서버 인자 | `--dtype bfloat16 --max-model-len 16384 --enable-lora --max-lora-rank 16 --max-logprobs 64 --gpu-memory-utilization 0.85 --generation-config vllm --seed 0 --attention-backend FLASHINFER --enable-log-requests`, `VLLM_USE_FLASHINFER_SAMPLER=1`. FP8이면 `--quantization fp8`(온라인 per-tensor) 추가. prefix cache 기본(켬) | `--model-state keep_loaded`(연속) |
| 모델 | base Qwen/Qwen3-8B@`b968826d`, 학습 모델은 PEFT adapter를 `--lora-modules`로(병합하지 않음). checkpoint 여럿을 한 서버에 올릴 때는 `--max-loras`를 그 수로 | – |
| sampling | temperature 0.6, top_p 0.95, top_k 20, min_p 0, repetition_penalty 1, presence·frequency 0, max_tokens 8192, `skip_special_tokens` | 같은 값(repeat_penalty 1) |
| seed | 회차 `S_k = 20261100 + k`, 호출 seed `EV.call_seed(S_k, 문항 id, 호출 번호)`를 요청마다 준다. 재현되지 않음을 받아들인다(결정 93) | 같은 규칙 |
| 입력 | HF `render_prompt`(enable_thinking) id열 직접 전달. 셀 meta에 서버가 받은 id열과 보낸 id열이 같은지(`prompt_ids_echo_equal`) 남긴다 | – |
| client | `serving_vllm/vllm_thinking.py`·`vllm_eval_thinking.py`(SEMANTIC_CODE 밖), 동시 요청 실행기 `serving_vllm_fp8/run_cell.py` | `evaluate_vendor100.py llm` |
| 동시 요청 | **정답률 셀은 8**(문항을 8묶음으로 나눈 평가 프로세스 8개). 한 비교 안의 셀은 같은 수. 셀 meta `vllm.concurrency` | 1(순차, 기존과 같음) |

- **실행 조건**(셀마다):
  - 서버를 띄운 뒤 로그에서 attention backend(`FLASHINFER`)와 sampler("Using FlashInfer for top-p & top-k sampling"), FP8이면 양자화 커널을 찾아 셀 meta(`vllm.kernels`)에 남긴다.
    flashinfer가 쓰이지 않았으면 그 셀은 재지 않고 보고한다(결정 90: 빌드·실행 실패 때만 기존 설정으로 돌아가고, 그 경우 한 비교의 모든 셀을 같은 설정으로 다시 잰다).
  - 서버 요청 로그에서 셀 시간 동안의 요청 수, seed를 뺀 SamplingParams 종류(1종이어야 함), LoRA 이름별 수를 셀 meta(`vllm.request_log`)에 요약한다. 요청 로그 원문은 저장소 밖.
  - **입력 일치 확인**: 서버를 새 설정(정밀도·커널·판)으로 처음 띄울 때 selection_v2 앞 10문항의 id열을 확인한다(`serving_vllm/check_inputs.py`). 다르면 재지 않는다.
  - **장치**(결정 100): GPU 3장(같은 RTX 6000 Ada, 드라이버 595.99.02)을 쓴다. 학습은 1장, 표본 수집·checkpoint 평가·업체 100 평가는 3장에 나눈다.
    vLLM은 seed로 표본이 재현되지 않으므로(결정 93) 장치 일치 확인 대신 통계로 판단하고, 한 비교 안의 셀은 같은 backend·sampler·동시 요청 수·정밀도로 잰다.
    표본마다 GPU UUID를 셀 meta와 실행 기록에 남긴다. Ollama 측정(E, 27b) 중에는 Ollama GPU(UUID `48f798cc…`)에서 다른 작업을 하지 않는다.
    GPU 확인(UUID·메모리·다른 사용자 프로세스)은 `pilot_003/gpu_lib.sh` `gpu_ok`와 같다.
  - Ollama 측정(E) 중에는 vLLM 서버를 내리고 다른 모델 작업을 하지 않는다. E는 결정 55 guard를 그대로 쓴다.
  - 지문 `791c4a68`, prompt `87048d0c…`, gold sha, adapter sha256을 실행 전에 대조하고 meta에 남긴다.
- **재측정**: 셀(표본)마다 한 번만 잰다. 예외는 기반 장애와 결정 55 중단이다. 다시 잰 사실과 이유를 기록한다.

## 4. 정밀도: **BF16**(결정 95)

후보 규칙(아래를 모두 만족하면 FP8, 아니면 BF16)과 적용 결과(`../serving_vllm_fp8/REPORT.md` 7절, pilot_003 최종 adapter, selection_v2, k=4, 동시 요청 8, flashinfer):

| 조건 | 값 | 만족 |
|---|---|---|
| 1. FP8 학습 신호 보존율 ≥ 0.9 | 0.987(기울기 0.924, 상관 0.899) | 예 |
| 2. FP8-최종 대 BF16-최종 정답률 차이 CI가 0을 포함 | −3.83 [−7.40, −0.51] | **아니오** |
| 3. FP8에서 U·조용한 오답 증가가 확인되지 않음 | U +0.77 [−1.79, 3.06], 조용한 오답 +0.26 [−1.02, 1.53] | 예 |
| 4. FP8이 BF16보다 빠름(순차 측정) | 문항 쌍 생성 속도 1.397 [1.395, 1.400] | 예 |
| 결과 | **BF16** | 사용자 확인(결정 95) |

- 이 판의 모든 판정·선택 셀은 vLLM BF16(`--dtype bfloat16`, 양자화 없음)이다. 참고: BF16의 문항 지연은 E의 약 2.5배다(고정 30문항 순차).

## 5. 셀과 k

| 단계 | 셋 | 셀 | k |
|---|---|---|---|
| checkpoint 선택 | selection_v2 | vLLM-base(기준값), 단계(SFT, DPO)마다 checkpoint 2개 | 4 |
| 판정 | 업체 100 | **vLLM-base(기준), vLLM-최종(주 비교)**, E(참고) | 8 |
| 참고(결정 97) | 업체 100 | 27b(Ollama `qwen3.8:27b`) | 4 |
| 함께 보고 | aux_test_v1 | vLLM-base, vLLM-최종, E(참고) | 4 |
| 보조 보고 | valid98(98) | vLLM-base, vLLM-최종 | 4 |
| 지연(판정의 지연 조건) | selection_v2 고정 30문항(`../serving_vllm_fp8/latency_ids.txt`, sha256 `b511a6c7…`) | vLLM-base, vLLM-최종(같은 정밀도), E(참고) | 1(순차) |

- 주 비교(판정): vLLM-base → vLLM-최종, 같은 정밀도·커널·동시 요청 수·GPU.
- 참고 비교(판정 없음): E → vLLM-base, E → vLLM-최종, 27b → vLLM-최종.
- **selection 기준값(vLLM-base, selection_v2, k=4)**: `../serving_vllm_fp8/runs/vllm-bf16-base_s1–4.json`(pilot_prep_007)을 다시 쓴다.
  같은 vLLM 0.30.0·BF16·flashinfer attention과 sampler·동시 요청 8·sampling 값·seed 규칙·selection_v2 98문항·code 지문 `791c4a68`이고,
  서버도 `--enable-lora`(LoRA 커널 경로) 설정이었다. 다른 점은 서버에 올라 있던 adapter(pilot_003 최종)와 GPU(0)뿐인데, base 요청은 adapter를 쓰지 않고
  결정 93·100으로 장치 일치를 요구하지 않는다. 그래서 새로 재지 않는다. 같은 조건이 깨지면(판·커널·동시 요청·sampling 변경) 새로 잰다.
- **27b 참고 셀(결정 97)**: Ollama `qwen3.8:27b`(측정 전 digest 확인), prompt `87048d0c`, thinking 켬(`--model-think on`), sampling 값은 3절과 같다(temperature 0.6,
  top_p 0.95, top_k 20, min_p 0, repeat_penalty 1, presence·frequency 0, 호출 seed 규칙), 연속 방식, 결정 55 guard. **실제 운영 조건(greedy)과 다르다**고 보고서에 적는다.
- HF 경로 셀은 재지 않는다. v3의 HF 기록과 v4의 vLLM 기록을 직접 비교하지 않는다(경로가 다르다). 비교가 필요하면 같은 셋에서 두 경로를 함께 잰다.

## 6. 판정 규칙

v3 6절과 같다(문항 단위 쌍 bootstrap 10,000회, `default_rng(20261109)`, A = vLLM-base, B = vLLM-최종). 지연 조건만 바뀐다.

- **지연 조건**: 고정 30문항 순차 측정에서 vLLM-최종의 문항 모델 시간 중앙값이 같은 정밀도 vLLM-base의 1.5배 이하이면 만족, 넘으면 악화.
  정답률 셀(동시 요청)의 지연 값은 판정에 쓰지 않는다.
- 함께 적는 것: v3과 같다. 더해서 셀별 동시 요청 수, attention backend·sampler, 요청 로그 요약, 생성 속도(tok/s), vicinity 빠짐(7절).

## 7. 감시 지표: vicinity 빠짐(결정 94·97)

- 정의: gold grounding의 `factors.vicinity`가 참인 문항의 표본 중 출력 grounding에 vicinity가 없는 표본의 비율. 셀마다(분모: gold vicinity 문항 수 × k) 보고하고,
  짝 비교에서는 문항 평균 차이와 bootstrap CI를 함께 적는다. 판정에는 쓰지 않는다.
- 대상 셋(결정 97): 측정하는 모든 셋 — selection_v2, valid98, aux_test_v1, 업체 100.
- 계산: `../serving_vllm_fp8/analyze_fp8.py`의 `vicinity`와 같은 정의.
- 참고: selection_v2의 gold vicinity 문항은 1개뿐이다.

## 8. checkpoint 선택과 중단 규칙

v3 7절과 같다. 측정 경로만 vLLM(BF16, flashinfer, 동시 요청 8, adapter는 LoRA)이다.

**중단 규칙(결정 96)**: 선택 셋(selection_v2)에서 가장 높은 checkpoint(고른 최종 checkpoint)와 vLLM-base를 비교해 다음 둘을 **모두** 만족할 때만 업체 100으로 간다.

1. grounding_ok 차이(base → checkpoint)의 문항 단위 쌍 bootstrap 95% CI 하한 > 0.
2. 같은 비교에서 U 비율 차이의 CI 하한 ≤ 0(U 증가가 확인되지 않음).

하나라도 만족하지 않으면 업체 100 평가 전에 멈추고 보고한다.

## 9. 예상 평가 시간

`../serving_vllm_fp8` 실측(GPU 1장, 동시 요청 8): BF16 98문항 표본 하나 약 5.5–8분. 순차 30문항 BF16 약 8–11분. E: 100문항 표본 약 15분, 30문항 약 5분.
27b: pilot_003 teacher 수집 기록의 생성 속도(최소 77.8 tok/s)로 E의 약 1.5배를 잡아 100문항 표본 약 25분.

| 셀 | 셋(문항) | k | GPU 1장 기준 |
|---|---|---|---|
| vLLM-base 기준값 | selection_v2(98) | 4 | 0(pilot_prep_007 셀을 다시 씀) |
| checkpoint 4개(SFT 2, DPO 2) | selection_v2(98) | 4 | 약 1.6시간 |
| vLLM-base, vLLM-최종 | 업체 100(100) | 8 | 약 1.6시간 |
| E(참고) | 업체 100(100) | 8 | 약 2시간(Ollama GPU) |
| 27b(참고) | 업체 100(100) | 4 | 약 1.7시간(Ollama GPU) |
| vLLM-base, vLLM-최종 | aux_test_v1(51) | 4 | 약 0.4시간 |
| E(참고) | aux_test_v1(51) | 4 | 약 0.6시간(Ollama GPU) |
| vLLM-base, vLLM-최종 | valid98(98) | 4 | 약 0.8시간 |
| 지연: base, 최종(순차), E | 고정 30 | 1 | 약 0.4시간 |

- 합계: GPU 1장으로 약 9시간. 결정 100으로 vLLM 셀을 GPU 3장에 나누면 vLLM 셀은 약 1–1.5시간이고, Ollama 셀(E, 27b, 약 4.3시간)은 Ollama GPU에서 다른 작업 없이 순서대로 잰다.
  학습(SFT 약 1.5시간, DPO 약 2.2시간)은 별도.

## 10. 산출물

v3 10절과 같다. 더해서: 서버 기록(`server_<port>.json`: 인자, 환경, 로그에서 찾은 커널), 셀 meta의 `vllm.concurrency`·`vllm.kernels`·`vllm.request_log`, 지연 측정 결과, vicinity 빠짐.
요청 로그 원문·서버 로그·응답 원문은 저장소 밖이나 ignore 경로에 둔다. 확정본의 sha256은 `../DECISIONS.md`가 아니라 pilot_004 `PLAN.md`에 기록한다(이 문서 안에는 자기 sha256을 적을 수 없다).
