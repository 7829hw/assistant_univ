# vLLM 서빙 경로 확인

작성: 2026-10-14. 결정 89(AD). 학습·prompt·`SEMANTIC_CODE` 변경 없음, 지문 `791c4a68`(모든 셀 meta에 같은 값). 업체 100과 aux_test_v1은 쓰지 않았다
(지연 비교에 작업 1의 aux E 셀 생성 속도만 옮겼다, 4절). 응답 원문은 `training/generated/serving_vllm/raw/`(ignore), 채점 파일은
`/data/hwkim/sftdpo_work/serving_vllm/scores/`(저장소 밖).

결론 표시: **확인됨 / 가능성 있음 / 미확인**.

## 0. 요약

| 질문 | 답 |
|---|---|
| vLLM이 받는 입력이 HF와 같은가 | **확인됨.** selection_v2 10문항 모두 token id열이 같다(서버 자체 렌더링도 같다) |
| token 확률이 HF와 같은가 | **확인됨(구현 차이 수준).** 평균 \|Δlog p\| 0.012, top-1 불일치 0.7%. logprob_diag의 HF 병합본·GGUF BF16과 같은 크기 |
| 학습 효과가 vLLM에서도 유지되는가 | **확인됨(같은 방향, 크기 차이는 구분 안 됨).** HF +6.89 [1.28, 13.01], vLLM +8.42 [3.06, 13.78], 효과 차이 +1.53 [−5.61, 8.16]. token 학습 신호 보존율 1.00 |
| 지연이 E 수준에 가까운가 | **아니다(가능성 있음 수준의 비교).** 호출당 생성 속도 vLLM 48–51 tok/s, E 117 tok/s(aux 셀), HF 31–38 tok/s. 문항 지연 중앙값 vLLM 16.5–17.2 s, HF 22.5–27.3 s, E 8.7 s(셋이 다름) |
| seed 재현성 | **확인됨: 바이트 재현되지 않는다.** 같은 서버에서 같은 seed로 두 번 생성해도 5문항 중 4문항(base)·5문항(최종)의 원문이 달랐다 |

## 1. 설치와 실행 조건

| 항목 | 값 |
|---|---|
| vLLM | **0.30.0**(PyPI 공개 2026-09-22, 결정 89의 "2주 이상"; 0.31.0은 2026-10-05라 쓰지 않음) |
| 설치 | `/home/hwkim/sftdpo_work/vllmvenv`(저장소 밖). `python -m venv` → `pip install "vllm==0.30.0"`. torch 2.13.0+cu130, transformers 5.19.0 |
| Python | uv 0.12.20(2026-09-28 공개, `/home/hwkim/sftdpo_work/uvtool`)으로 받은 standalone CPython 3.12.14(`/home/hwkim/sftdpo_work/uv-python`). 시스템 Python·다른 환경은 건드리지 않았다 |
| CUDA·드라이버 | 드라이버 595.99.02(CUDA 13.2까지 지원), torch CUDA 13.0 → 호환. GPU RTX 6000 Ada 48 GB |
| 서버 | `vllm serve Qwen/Qwen3-8B --revision b968826d… --dtype bfloat16 --max-model-len 16384 --enable-lora --lora-modules final=<DPO checkpoint-174 policy> --max-lora-rank 16 --max-logprobs 64 --gpu-memory-utilization 0.85 --generation-config vllm --seed 0`(`serve.sh`, 기록 `server_<port>.json`은 저장소 밖) |
| adapter | pilot_003 최종(DPO checkpoint-174 policy), sha256 `bf6e2f87…`, LoRA r16, 7 projection. 병합하지 않음 |
| 환경 변수 | `VLLM_USE_FLASHINFER_SAMPLER=0`(PyTorch sampler), venv bin을 PATH에. attention backend FLASH_ATTN(자동 선택), prefix cache 켬(기본) |
| GPU | 서버 A GPU 0 `2445b100`(입력 확인·재현성·셀 전부), 서버 B GPU 1 `a5ce83d0`(입력 확인·재현성만), 채점 GPU 2 `48f798cc`(aux E 측정이 끝나고 Ollama 모델이 내려간 뒤) |

- **기동 실패 두 번(측정 전, 기록 `runs.log`)**: (1) 시스템 Python에 개발 헤더(`Python.h`)가 없어 Triton이 C 도우미를 빌드하지 못함 → 헤더가 든 standalone Python으로 venv를 다시 만듦.
  (2) flashinfer sampler JIT에 `ninja`가 PATH에 없음 → venv bin을 PATH에 두고 flashinfer sampler를 끔. 측정은 이 설정으로만 했다.
- 생성 설정(모든 셀, 요청 본문이 각 결과 meta `vllm.request_example`에 있음): temperature 0.6, top_p 0.95, top_k 20, min_p 0, repetition_penalty 1,
  presence·frequency 0, seed(호출별 `EV.call_seed`), max_tokens 8192, `--generation-config vllm`(모델 기본 sampling 값을 덮어쓰지 않음).
  서버 쪽 요청 로그는 켜지 않아 **서버가 실제 적용한 값은 미확인**이다(요청에 준 값만 확인).
- 평가 client: `vllm_thinking.py`·`vllm_eval_thinking.py`(`SEMANTIC_CODE` 밖). HF 평가와 같은 pipeline·채점·seed 규칙이고 모델 호출만 `/v1/completions`다.

## 2. 입력 일치(측정 전, `input_check_8100.json`, `input_check_8101.json`)

- selection_v2 앞 10문항의 첫 호출 prompt(7,269–7,289 token):
  - HF 평가 렌더링(`render_prompt`, enable_thinking)의 id 길이가 pilot_003 HF-base 기록의 prompt token 수와 10/10 같다.
  - 그 id열을 vLLM에 직접 넘겼을 때 서버가 받은 id열(`prompt_token_ids`)이 base·final 모두 10/10 같다(두 서버 모두).
  - 참고: vLLM 서버 자체 렌더링(`/tokenize`, messages + enable_thinking)도 10/10 같다.
- **확인됨.** 평가 client는 id열을 직접 넘기므로 렌더링 차이가 없다. 모든 셀 호출에서 서버가 돌려준 id열이 보낸 것과 같았다(`echo_mismatch_calls` 0).

## 3. token 확률(`logprob_compare.json`, logprob_diag 기준 응답 60개, 응답 token 71,372개)

| 비교 | 평균 \|Δlog p\| (thinking / JSON) | KL 근사 | top-1 불일치 % |
|---|---|---|---|
| HF base → vLLM base | 0.0124 (0.0150 / 0.0009) | 0.00082 | 0.74 |
| HF+adapter → vLLM+LoRA | 0.0121 (0.0147 / 0.0004) | 0.00079 | 0.69 |
| 참고: HF base → HF+adapter(학습 차이) | 0.0545 | 0.0157 | 2.60 |
| 참고(logprob_diag): HF+adapter → HF 병합 BF16 / GGUF BF16 / Q4_K_M | 0.0127 / 0.0118 / 0.0957 | 0.00083 / 0.00066 / 0.0375 | 0.71 / 0.73 / 4.90 |

| 학습 신호(최종 − base) | 보존율(평균 비) | 기울기 | 상관 | 강한 token(\|s_HF\| ≥ 1) 수 / 기울기 |
|---|---|---|---|---|
| 응답 전체 | 1.004 | 0.977 | 0.984 | 405 / 0.987 |
| thinking | 1.005 | 0.965 | 0.973 | 376 / 0.982 |
| JSON | 1.000 | 0.992 | 0.999 | 29 / 0.992 |
| cal 묶음 thinking | 0.985 | 0.954 | 0.962 | 104 / 0.981 |

- HF 채점: base는 logprob_diag의 `hf_base.bin`, 최종은 같은 스크립트의 사본(`score_hf_p3.py`, adapter만 pilot_003). vLLM 채점: `score_vllm.py`(오프라인 엔진, prompt_logprobs top-64, prefix cache 끔).
- **확인됨:** vLLM BF16과 HF의 차이는 같은 BF16 가중치를 다른 구현으로 돌린 차이(HF 병합본, llama.cpp BF16)와 같은 크기이고, LoRA를 붙인 경로의 학습 신호가 거의 그대로 남는다.
  Q4에서 신호가 크게 줄던 것(logprob_diag)과 다르다.

## 4. sampling 셀(selection_v2 98문항, k=4, `cell_compare.json`)

### 4.1 seed 재현성(`repro/compare.json`, 5문항, seed 20261101)

| 모델 | 같은 서버 두 번(A1·A2) | 다른 GPU(A1·B1) |
|---|---|---|
| base | 첫 호출 원문 5문항 중 1개 같음(호출 수도 다름) | 6/6 호출 같음(둘 다 새로 뜬 서버의 첫 실행) |
| 최종(LoRA) | 0/5 | 0/5 |

- **확인됨:** 같은 seed라도 원문이 바이트 단위로 재현되지 않는다. 새로 뜬 서버의 첫 실행끼리는 GPU가 달라도 같았으므로(base), 서버 상태(prefix cache 등)가 결과를 바꾸는 것으로 보인다(**가능성 있음**, 원인 미확인).
  LoRA 쪽은 첫 실행끼리도 달랐다(**미확인**: LoRA 커널의 비결정성 가능성).
- 이 결과로 결정 83의 장치 규칙(GPU 사이 원문이 다르면 한 셀과 짝 셀을 한 GPU에서)을 따라, 두 셀의 8표본을 모두 서버 A(GPU 0)에서 차례로 쟀다(`runs.log`).

### 4.2 셀 결과

| 셀 | 평균 | 표본별 | U | 조용한 오답 | 안정 정답 | 문항 지연 중앙값 | 생성 상한 | 루프 |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| HF-base(pilot_003) | 75.26 | 74 75 73 73 | 4.59 | 1.53 | 56 | 22.49 s | 0 | 0 |
| HF-최종(pilot_003 DPO 174) | 82.14 | 79 79 84 80 | 7.40 | 2.04 | 63 | 27.25 s | 1 | 1 |
| **vLLM-base** | 72.19 | 73 66 70 74 | 4.59 | 2.04 | 52 | 16.53 s | 0 | 0 |
| **vLLM-최종** | 80.61 | 79 78 79 80 | 5.61 | 2.55 | 61 | 17.24 s | 0 | 0 |

오류 유형(문항·표본 %):

| 셀 | aggregation_added | dt_missing | role_error | role_notation | occupied_misread |
|---|---:|---:|---:|---:|---:|
| HF-base | 11.73 | 2.55 | 4.34 | 0.00 | 2.30 |
| HF-최종 | 2.55 | 3.83 | 4.08 | 0.51 | 2.55 |
| vLLM-base | 11.48 | 3.57 | 5.36 | 0.00 | 2.04 |
| vLLM-최종 | 4.34 | 4.08 | 2.81 | 0.51 | 2.30 |

| 비교 | 차이 [95% CI] | U [CI] | 조용한 오답 [CI] | 지연 비 |
|---|---|---|---|---:|
| 경로: HF-base → vLLM-base | −3.06 [−7.40, 1.28] | 0.00 [−2.55, 2.55] | +0.51 [−1.02, 2.55] | 0.74 |
| 경로: HF-최종 → vLLM-최종 | −1.53 [−6.63, 3.32] | −1.79 [−5.10, 1.53] | +0.51 [−0.77, 2.04] | 0.63 |
| 학습 효과: HF-base → HF-최종 | +6.89 [1.28, 13.01] | +2.81 [−0.51, 6.38] | +0.51 [−1.28, 2.30] | 1.21 |
| **학습 효과: vLLM-base → vLLM-최종** | **+8.42 [3.06, 13.78]** | +1.02 [−1.02, 3.06] | +0.51 [−1.28, 2.30] | 1.04 |
| 학습 효과 차이(vLLM − HF, 문항별) | +1.53 [−5.61, 8.16] | −1.79 [−5.87, 2.30] | 0.00 [−2.30, 2.04] | – |

- 원문 일치: 같은 문항·표본·seed의 첫 호출 원문이 HF와 같은 경우 0/392(base), 0/392(최종). 커널이 달라 sampling 경로가 갈라진다.
- **확인됨:** vLLM에서도 학습 효과의 CI 하한이 0보다 크다(+8.42 [3.06, 13.78]). HF와 같은 방향이고, 두 경로의 효과 차이는 CI가 0을 포함해 구분되지 않는다.
  pilot_003 최종은 selection_v2에서 같은 표본으로 고른 checkpoint라, HF 값에는 선택 편향이 있고 vLLM 값은 그 표본과 무관한 새 표본이다.
- 경로 차이(HF → vLLM)는 base·최종 모두 CI가 0을 포함한다(**구분되지 않음**). 오류 유형 분포도 같은 모양이다(학습으로 aggregation_added가 크게 줄어듦).
- 같은 seed 규칙이지만 원문이 달라 HF와 vLLM 셀은 서로 다른 표본이다. 비교는 문항 단위 쌍 bootstrap이다.

## 5. 지연(`cell_compare.json` `latency`)

| 셀 | 호출당 생성 속도 중앙값 | 문항 모델 시간 중앙값 | 표본 하나 벽시계(98문항) | 문항/시간 |
|---|---:|---:|---|---:|
| HF-base | 37.5 tok/s | 22.49 s | 2,726–2,958 s | 124 |
| HF-최종 | 30.8 tok/s | 27.25 s | 3,248–3,669 s | 103 |
| vLLM-base | 50.8 tok/s | 16.53 s | 1,963–2,151 s | 174 |
| vLLM-최종(LoRA) | 47.7 tok/s | 17.24 s | 2,031–2,182 s | 168 |
| 참고: E(Ollama 0.40.3, Q4_K_M, aux_test_v1 51문항 k=4) | 116.8 tok/s | 8.70 s | 487–669 s(51문항) | 327 |

- 측정 방식: 서버 하나에 한 번에 요청 하나(문항 순서대로). 처리량은 이 단일 요청 조건의 값이고, 여러 요청을 묶는 vLLM 배치 처리량은 재지 않았다.
- 생성 속도는 prefill(약 7.3k token prompt)을 포함한 호출 시간 기준이다.
- **확인됨:** vLLM은 HF보다 문항 지연이 26–37% 짧다(같은 셋). LoRA를 붙여도 거의 느려지지 않는다(1.04배).
- **E 수준에는 못 미친다(가능성 있음):** 생성 속도가 E의 약 0.4배다. E는 Q4 가중치(약 5 GB)라 BF16(약 16 GB)보다 한 token에 읽는 메모리가 적다.
  E의 문항 지연은 다른 셋(aux)에서 잰 값이라 직접 비교가 아니다. 같은 셋의 E 지연이 필요하면 selection_v2에서 E를 재야 한다(이번에는 재지 않음).

## 6. 결론

| 질문 | 결론 |
|---|---|
| 입력 일치 | **확인됨** |
| token 확률·학습 신호 보존 | **확인됨** |
| 학습 효과가 vLLM에서도 유지되는가 | **확인됨**(같은 방향, CI 하한 > 0. 크기 차이는 구분되지 않음) |
| 정답률이 HF와 같은가 | **구분되지 않음**(base −3.06 [−7.40, 1.28], 최종 −1.53 [−6.63, 3.32]) |
| 지연이 E 수준에 가까운가 | **아니다**: 단일 요청 생성 속도가 E의 약 0.4배. 같은 셋 비교는 **미확인** |
| seed로 표본을 바이트 재현할 수 있는가 | **아니다(확인됨)**. 원인(prefix cache, LoRA 커널)은 **미확인** |

## 7. 산출물

- 스크립트: `vllm_thinking.py`, `vllm_eval_thinking.py`, `serve.sh`, `check_inputs.py`, `score_vllm.py`, `score_hf_p3.py`, `run_phase1.sh`, `run_phase2.sh`,
  `run_scores.sh`(HF 부분), `run_scores_vllm.sh`(vLLM 부분 재실행), `analyze_vllm_logprob.py`, `analyze_vllm_cells.py`.
- 기록: `input_check_*.json`, `repro/`, `runs/`(셀 결과·log), `logprob_compare.json`, `cell_compare.json`, `runs.log`, `gpu_check.txt`.
