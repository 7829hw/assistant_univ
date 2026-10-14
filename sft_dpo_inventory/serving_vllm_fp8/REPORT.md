# vLLM flashinfer 적용과 FP8 확인

작성: 2026-10-14. 결정 90(AE)·91(AF)·93(AH)·94(AI). 학습·prompt·`SEMANTIC_CODE` 변경 없음, 지문 `791c4a68`(모든 셀 meta).
셋은 selection_v2만 썼다(업체 100·aux_test_v1 안 씀). 응답 원문은 `training/generated/serving_vllm_fp8/raw/`(ignore), 서버 로그(요청 로그 원문 포함)와
채점 파일은 `/data/hwkim/sftdpo_work/serving_vllm_fp8/`(저장소 밖).

결론 표시: **확인됨 / 가능성 있음 / 미확인**.

## 0. 요약

| 질문 | 답 |
|---|---|
| flashinfer(attention·sampler)를 쓸 수 있는가 | **확인됨.** 두 번 빌드 실패 뒤 세 번째 기동부터 서버 로그에 `AttentionBackendEnum.FLASHINFER`와 "Using FlashInfer for top-p & top-k sampling"이 찍힌다 |
| flashinfer로 바꾼 뒤 입력·token 확률이 그대로인가 | **확인됨.** 입력 10/10 같음, HF와의 차이 \|Δlog p\| 0.0125(이전 PyTorch sampler 경로 0.0124와 같음) |
| FP8 base에 LoRA를 붙일 수 있는가 | **확인됨.** 온라인 FP8(`--quantization fp8`, per-tensor, CutlassFP8ScaledMM) + LoRA로 떴다. 병합 방식은 쓰지 않았다 |
| FP8에서 학습 효과가 유지되는가 | **token 수준은 대체로 유지(확인됨), 정답률 수준은 확인되지 않음.** 학습 신호 보존율 0.99·기울기 0.92. 정답률 학습 효과 FP8 +3.32 [−1.53, 8.16](CI 0 포함), BF16 +5.36 [1.02, 9.69]. 둘의 차이 −2.04 [−7.65, 3.57]은 구분 안 됨 |
| FP8은 BF16보다 얼마나 빠른가 | **확인됨: 생성 속도 1.40–1.44배**(문항 쌍 CI [1.395, 1.459]), 문항 지연 중앙값 0.71–0.72배 |
| FP8에서 U·조용한 오답이 늘었는가 | **증가가 확인되지 않음.** 최종: U +0.77 [−1.79, 3.06], 조용한 오답 +0.26 [−1.02, 1.53]. 다만 **FP8-최종 정답률이 BF16-최종보다 낮다(−3.83 [−7.40, −0.51], 확인됨)** |

## 1. flashinfer 적용(결정 90)

| 시도 | 결과 | 조치 |
|---|---|---|
| 1 | JIT 빌드 실패: nvcc 13.4.92와 CUDA 런타임 헤더 13.0(torch cu130) 불일치(CCCL 검사 `#error`) | venv에 `nvidia-cuda-nvcc`·`nvidia-cuda-crt`·`nvidia-nvvm` **13.0.88**(2025-09-04 공개) 설치(이전 13.4.92, `pip_before_nvcc.txt`는 저장소 밖). flashinfer JIT 캐시 지움 |
| 2 | JIT 링크 실패: `-lcudart` 없음(pip 런타임은 `libcudart.so.13`만) | 저장소·venv 밖 `/home/hwkim/sftdpo_work/cuda_link/libcudart.so → libcudart.so.13` 링크를 `LIBRARY_PATH`에 둠 |
| 3 | 성공 | 서버 로그: attention `FLASHINFER`(decode_backend flashinfer-native, arch sm89), sampler "Using FlashInfer for top-p & top-k sampling" |

- 서버 스크립트 `serve2.sh`(기존 `serving_vllm/serve.sh`는 고치지 않음): venv bin과 venv의 CUDA 13 툴킷을 PATH에, `CUDA_HOME`을 그 툴킷으로, `--attention-backend FLASHINFER`,
  `VLLM_USE_FLASHINFER_SAMPLER=1`, `--enable-log-requests`. 서버마다 로그에서 찾은 backend·sampler를 `server_<port>.json`에 남기고, 셀 meta(`vllm.kernels`)에 옮겼다.
- 오프라인 채점 엔진(`score_vllm2.py`)은 첫 실행(bf16 base)이 채점을 끝낸 뒤 종료 단계에서 `terminate called without an active exception`으로 0이 아닌 코드로 끝났다.
  출력은 완전했다(60개 시퀀스). 다음 판 실행기(`run_scores3.sh`)는 출력으로 완료를 판단하고 그 출력을 그대로 썼다. 나머지 셋은 0으로 끝났다.
- 요청 로그(결정 93): 모든 셀에서 seed를 뺀 SamplingParams가 셀마다 **한 종류**였고 요청값과 같다(temperature 0.6, top_p 0.95, top_k 20, min_p 0,
  repetition_penalty 1, presence·frequency 0, max_tokens 8192, skip_special_tokens). LoRA 이름도 셀과 맞다(셀 meta `vllm.request_log`).
  `watermarking=True`가 찍히지만 엔진에 `--watermark-config`가 없어 적용되지 않는다(vLLM 0.30.0 `create_watermark_config`는 설정이 없으면 None).

### 1.1 입력 일치(`input_check_bf16_fi.json`, `input_check_fp8_fi.json`)

selection_v2 앞 10문항: HF 렌더링 id 길이가 HF 기록과 10/10 같고, BF16·FP8 서버가 받은 id열이 base·final 모두 10/10 같다(서버 자체 렌더링도 같다). **확인됨.**

## 2. token 확률(`logprob_compare.json`, logprob_diag 기준 응답 60개)

| 비교 | \|Δlog p\| 전체 (thinking / JSON) | KL 근사 | top-1 불일치 % |
|---|---|---|---|
| HF base → vLLM BF16 base(flashinfer) | 0.0125 (0.0150 / 0.0010) | 0.00082 | 0.75 |
| HF+adapter → vLLM BF16 final(flashinfer) | 0.0122 (0.0148 / 0.0004) | 0.00080 | 0.70 |
| HF base → vLLM FP8 base | **0.0407** (0.0489 / 0.0033) | 0.00814 | 2.33 |
| HF+adapter → vLLM FP8 final | **0.0409** (0.0496 / 0.0014) | 0.00810 | 2.20 |
| 참고: HF → vLLM BF16(PyTorch sampler, `serving_vllm`) base / final | 0.0124 / 0.0121 | 0.00082 / 0.00079 | 0.74 / 0.69 |
| 참고(logprob_diag, pilot_002 최종): GGUF Q8_0 / Q4_K_M | 0.0168 / 0.0957 | 0.00138 / 0.0375 | 1.06 / 4.90 |

| 학습 신호(최종 − base) | 보존율 | 기울기 | 상관 | 강한 token 405개 기울기 / 부호 일치 | thinking 상관 | cal 묶음 thinking 강한 token(104) 기울기 |
|---|---|---|---|---|---|---|
| vLLM BF16 flashinfer | 1.003 | 0.979 | 0.984 | 0.989 / 100% | 0.973 | 0.964 |
| **vLLM FP8 flashinfer** | **0.987** | **0.924** | **0.899** | 0.929 / 98.8% | 0.832 | 0.862 |
| vLLM BF16 PyTorch(`serving_vllm`) | 1.004 | 0.977 | 0.984 | 0.987 / 100% | 0.973 | 0.981 |

- **확인됨:** flashinfer로 바꿔도 BF16의 token 확률과 학습 신호는 이전 경로와 같다.
- **확인됨:** FP8의 차이는 Q8_0(llama.cpp)의 약 2.4배, Q4_K_M의 약 0.43배다. 학습 신호는 평균으로 거의 남고(0.99) 기울기 0.92, 상관 0.90이다. Q4에서 상관이 0.53–0.67로 떨어진 것보다 작다.
  JSON 구간은 FP8에서도 거의 결정적이다(top-1 불일치 0.05–0.12%).

## 3. sampling 셀(selection_v2 98문항, k=4, 동시 요청 8, flashinfer, GPU 0 한 장, `cell_compare.json`)

- 측정: `run_cell.py`가 문항을 8묶음으로 나눠 평가 프로세스 8개를 동시에 돌린다(서버 동시 요청 최대 8). seed 규칙은 순차 측정과 같다(회차 20261100+k, 호출 `EV.call_seed`).
- 장치: 짝 비교의 셀이 모두 같은 GPU(GPU 0 `2445b100`)에 있다(결정 83 장치 규칙). BF16 셀을 잰 뒤 서버를 FP8로 바꿔 쟀다.
- 셀 표의 지연 중앙값은 동시 요청 아래의 값이라 지연 판단에 쓰지 않는다(5절이 지연).

| 셀 | 평균 | 표본별 | U | 조용한 오답 | 안정 정답 | 생성 상한 | 루프 | vicinity 빠짐(결정 94) | 실차 오독(표본) |
|---|---:|---|---:|---:|---:|---:|---:|---|---:|
| vLLM-BF16-base | 75.00 | 74 72 72 76 | 4.08 | 2.04 | 52 | 0 | 0 | 0/4(gold vicinity 1문항) | 8 |
| vLLM-BF16-최종 | 80.36 | 79 78 81 77 | 6.63 | 2.30 | 60 | 1 | 1 | 0/4 | 9 |
| vLLM-FP8-base | 73.21 | 74 69 73 71 | 3.32 | 3.32 | 46 | 0 | 0 | 0/4 | 11 |
| vLLM-FP8-최종 | 76.53 | 77 71 74 78 | 7.40 | 2.55 | 54 | 2 | 2 | 0/4 | 10 |

오류 유형(문항·표본 %):

| 셀 | aggregation_added | dt_missing | role_error | role_notation | occupied_misread |
|---|---:|---:|---:|---:|---:|
| BF16-base | 10.46 | 2.81 | 3.83 | 0.00 | 2.04 |
| BF16-최종 | 4.08 | 5.10 | 3.32 | 0.77 | 2.30 |
| FP8-base | 9.44 | 2.04 | 5.61 | 0.00 | 2.81 |
| FP8-최종 | 4.59 | 4.59 | 4.85 | 0.77 | 2.55 |

| 비교 | 차이 [95% CI] | U [CI] | 조용한 오답 [CI] |
|---|---|---|---|
| 정밀도: BF16-base → FP8-base | −1.79 [−6.89, 3.06] | −0.77 [−3.57, 1.79] | +1.28 [−0.77, 3.57] |
| **정밀도: BF16-최종 → FP8-최종** | **−3.83 [−7.40, −0.51]** | +0.77 [−1.79, 3.06] | +0.26 [−1.02, 1.53] |
| 학습: BF16-base → BF16-최종 | **+5.36 [1.02, 9.69]** | **+2.55 [0.26, 5.36]** | +0.26 [−1.28, 1.79] |
| 학습: FP8-base → FP8-최종 | +3.32 [−1.53, 8.16] | **+4.08 [1.53, 6.89]** | −0.77 [−3.06, 1.28] |
| 학습 효과 차이(FP8 − BF16, 문항별) | −2.04 [−7.65, 3.57] | +1.53 [−1.79, 4.85] | −1.02 [−3.57, 1.02] |
| 동시 요청·커널: 이전 순차 BF16-base → 새 BF16-base | +2.81 [−1.02, 6.63] | −0.51 [−2.55, 1.53] | 0.00 [−1.53, 1.53] |
| 동시 요청·커널: 이전 순차 BF16-최종 → 새 BF16-최종 | −0.26 [−3.32, 3.06] | +1.02 [−1.28, 3.57] | −0.26 [−1.79, 1.28] |

- **확인됨:** BF16에서 학습 효과의 CI 하한이 0보다 크다(+5.36). 이전 순차 측정(+8.42 [3.06, 13.78], `serving_vllm`)과 같은 방향이다.
- **확인됨:** FP8-최종은 BF16-최종보다 정답률이 낮다(CI 상한 −0.51). FP8에서 학습 효과는 CI가 0을 포함해 **확인되지 않는다**. 다만 두 정밀도의 학습 효과 차이는 구분되지 않는다.
- **확인됨:** U 증가가 학습 효과 비교에서 BF16(+2.55 [0.26, 5.36])·FP8(+4.08 [1.53, 6.89]) 모두 CI로 확인된다(selection_v2, pilot_003 최종). 정밀도 비교에서는 U·조용한 오답 증가가 확인되지 않는다.
- **동시 요청의 영향 — 구분되지 않음:** 이전 순차 셀(PyTorch sampler, 동시 요청 없음)과 새 셀(flashinfer, 동시 요청 8)의 차이는 base·최종 모두 CI가 0을 포함한다.
  이 비교는 커널과 동시 요청이 함께 바뀐 것이라 둘을 나누지 못한다.
- vicinity 빠짐: selection_v2에는 gold vicinity 문항이 1개뿐이라(16표본) 이 셋으로는 감시 지표의 크기를 거의 볼 수 없다(네 셀 모두 0).
- 새로 생긴 U 문항: FP8-최종 대 BF16-최종 1개(indepv4/k03), 학습 효과 BF16 8개·FP8 7개(목록은 `cell_compare.json`).
- 잡음 폭(같은 셀 반쪽 표본 차이): 네 셀 모두 CI가 0을 포함하고 폭은 약 ±6–8%p다.

## 4. (참고) 셀 측정 시간

| 셀 | 표본 하나 벽시계(98문항, 동시 요청 8) |
|---|---|
| BF16-base / 최종 | 325–361 s / 332–484 s |
| FP8-base / 최종 | 231–298 s / 210–345 s |
| 이전 순차 BF16-base / 최종(`serving_vllm`) | 1,963–2,151 s / 2,031–2,182 s |

## 5. 지연(결정 93, `latency.json`): 고정 30문항(`latency_ids.txt`, seed 20261014로 고름), 1표본, 동시 요청 없음

| 셀 | 문항 모델 시간 중앙값 | 생성 속도 중앙값 | 호출 수 | grounding_ok(30, 참고) |
|---|---:|---:|---:|---:|
| vLLM-BF16-base | 16.34 s | 50.6 tok/s | 36 | 20 |
| vLLM-BF16-최종 | 21.17 s | 47.5 tok/s | 37 | 24 |
| vLLM-FP8-base | 11.74 s | 72.4 tok/s | 37 | 19 |
| vLLM-FP8-최종 | 15.08 s | 66.4 tok/s | 37 | 19 |
| E(Ollama 0.40.3, Q4_K_M, 연속, GPU `48f798cc`) | 8.32 s | 114.3 tok/s | 41 | 18 |

| 비교 | 문항 지연 중앙값 비 | 생성 속도 비 | 문항 쌍 생성 속도 비(기하 평균) [95% CI] |
|---|---:|---:|---|
| BF16 → FP8(base) | 0.718 | 1.431 | **1.440 [1.429, 1.459]** |
| BF16 → FP8(최종) | 0.712 | 1.398 | **1.397 [1.395, 1.400]** |
| base → 최종(BF16) | 1.296 | 0.939 | – |
| base → 최종(FP8) | 1.284 | 0.917 | – |
| E → FP8-최종 | 1.812 | 0.581 | – |
| E → BF16-최종 | 2.544 | 0.416 | – |

- E 셀: 결정 55 guard 통과(최소 101.2 tok/s), sampler 적용 값이 요청과 같다(`latency/lat-E_s1_sampler_params.txt`). 측정 중 다른 모델 프로세스는 없었다(vLLM 서버를 내린 뒤 잼).
- **확인됨:** FP8은 BF16보다 생성 속도가 약 1.4배이고 문항 지연이 약 0.71배다.
- **확인됨:** E 수준에는 못 미친다. FP8-최종 문항 지연은 E의 1.8배, 생성 속도는 0.58배다.
- 지연 기준(같은 경로·정밀도 base 대비 1.5배)에는 BF16·FP8 모두 들어간다(1.30·1.28배). 문항마다 응답 길이가 달라 문항 지연 비에는 생성 길이 차이가 섞인다.

## 6. 결론

| 질문 | 결론 |
|---|---|
| flashinfer 적용 | **확인됨**(attention·sampler, 로그 확인). 입력·token 확률 변화 없음(**확인됨**) |
| FP8에서 학습 효과가 유지되는가 | token 신호는 대체로 유지(**확인됨**, 보존율 0.99·기울기 0.92). 정답률 학습 효과는 **확인되지 않음**(+3.32 [−1.53, 8.16]). BF16과의 차이는 구분 안 됨 |
| FP8은 BF16보다 얼마나 빠른가 | **확인됨:** 생성 속도 1.40–1.44배, 문항 지연 0.71–0.72배 |
| FP8에서 U·조용한 오답이 늘었는가 | 정밀도 비교에서 **증가가 확인되지 않음**. 다만 FP8-최종의 정답률이 BF16-최종보다 낮음(**확인됨**, −3.83 [−7.40, −0.51]) |
| 학습 모델의 U 증가 | BF16·FP8 모두 base → 최종에서 **확인됨**(selection_v2) |
| 동시 요청이 정답률 분포를 바꾸는가 | **구분되지 않음**(커널 변경과 섞임) |

## 7. PROTOCOL_v4 정밀도 후보 규칙 적용(결정하지 않음)

| 조건 | 값 | 만족 |
|---|---|---|
| FP8 학습 신호 보존율 ≥ 0.9 | 0.987(기울기 0.924) | 예 |
| FP8-최종 대 BF16-최종 정답률 차이 CI가 0을 포함 | −3.83 [−7.40, −0.51] | **아니오** |
| FP8에서 U·조용한 오답 증가가 확인되지 않음 | U +0.77 [−1.79, 3.06], 조용한 오답 +0.26 [−1.02, 1.53](최종) | 예 |
| FP8이 BF16보다 빠름이 순차 측정에서 확인 | 1.40배 [1.395, 1.400](최종) | 예 |
| **규칙 적용 결과** | 둘째 조건을 만족하지 않음 → **BF16** | 사용자 확인 대기 |

## 8. 산출물

- 스크립트: `serve2.sh`, `run_cell.py`, `run_gpu0.sh`, `score_vllm2.py`, `run_scores2.sh`(첫 판, 종료 크래시로 멈춤), `run_scores3.sh`, `run_e_latency.sh`, `analyze_fp8.py`.
- 기록: `input_check_*`, `runs/`, `latency/`, `logprob_compare.json`, `cell_compare.json`, `latency.json`, `latency_ids.txt`, `runs.log`, `gpu_check.txt`.
