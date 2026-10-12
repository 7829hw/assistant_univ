# 경로별 token 확률 비교(결정 75, 작업 2)

작성: 2026-10-12. GPU 3(`GPU-48f798cc…`), 생성 없음, Ollama 서버를 부르지 않았다. 학습·prompt·`SEMANTIC_CODE` 변경 없음, 지문 `791c4a68…`.
응답 원문·token 열·확률 파일은 저장소 밖(`/data/hwkim/sftdpo_work/logprob_diag/`)에 있고 커밋하지 않았다.

## 1. 방법

- **기준 응답 60개**(`build_sequences.py`, `sequences_manifest.json`, seed 20261012).
  - (i) `sft` 30: pilot_002 SFT 학습 레코드(HF 출처 15, teacher 출처 15). 학습과 같은 렌더링(`render_records`).
  - (ii) `cal` 30: calibration_001 selection_v1 HF-최종 표본. (HF-최종 정답 비율 − Ollama-최종 정답 비율)이 큰 문항부터 골랐다
    (차이 1.0 1문항, 0.75 2, 0.5 9, 0.25 18). 문항마다 HF-최종이 맞고 호출이 하나뿐인 표본 하나. prompt는 같은 pipeline 구성으로
    첫 호출 messages를 잡아(모델 호출 없음) 렌더링했고, prompt token 수가 HF 평가 기록과 30/30 같다. 응답 token 수는 29/30 같다
    (1개는 다시 tokenize해 1 token 차이).
  - 입력은 HF thinking 켬 렌더링의 token id열로 고정했다. 모든 경로에 같은 id열을 넣었다(문자열로 다시 tokenize하지 않음).
  - 응답 token 71,372개(thinking 58,501, JSON 12,871). prompt는 7.3k token 안팎.
- **경로 12개**(`run_scores.sh`, `runs.log`에 파일 sha256).
  - HF(`score_hf.py`, transformers 4.56.2, BF16, SDPA): base, 최종 HF+adapter(PEFT), 최종 병합본.
  - llama.cpp b11434(`5e03bdd8`) CUDA 직접 실행(`token_logprobs.cpp`, 같은 소스를 `build-cuda`로 빌드, n_ctx 16384, flash attention auto, KV f16):
    GGUF BF16, Q8_0, 자체 Q4_K_M, 공식 방식 Q4(base·최종 각각), 공식 qwen3:8b blob(`a3de86cd…`).
  - 자체 Q4·Q8 파일은 Ollama에 등록된 B-conv·(d)·Ollama-최종·(e)를 만든 그 GGUF다(`runs.log`의 sha256).
- **지표**(`analyze_logprob.py`, `analysis.json`): 응답 token마다 log 확률(온도 1, 원래 분포)과 top-64.
  - 기준과의 차이: 평균 |Δlog p|, KL 근사(기준 top-64 + 나머지 묶음, nat/token), top-1 불일치 비율. 기준은 최종은 HF+adapter, base는 HF BF16.
  - 학습 신호 s_P = log p_최종,P − log p_base,P. HF의 s와 비교: 상관, 기울기, 강한 학습 token(|s_HF| ≥ 1)의 기울기와 부호 일치.
  - 결정 token(JSON): `dimension_target` 키·값, `od_role` 값, `subtype` 값, `aggregation` 키·값.

### 계획과 다른 점

- "GGUF F16 병합본" 대신 **GGUF BF16**을 썼다. 자체 Q4·Q8을 만든 입력이 BF16 GGUF이고, BF16은 HF 가중치를 그대로 담는다(F16은 반올림이 한 번 더 생긴다).
- llama.cpp는 b11434다. Ollama 0.35.1 안의 llama.cpp 판은 확인하지 못했고, Ollama는 flash attention을 끈다(`OLLAMA_FLASH_ATTENTION:false`). 이번 값은 "같은 가중치를 llama.cpp로 계산한 값"이지 Ollama 실행 그 자체가 아니다.

## 2. 기준과의 차이(응답 전체, 괄호는 thinking / JSON)

| 경로 | 평균 \|Δlog p\| | KL 근사 | top-1 불일치 % |
|---|---|---|---|
| 최종: HF 병합 BF16 | 0.0127 (0.0153 / 0.0007) | 0.00083 | 0.71 (0.85 / 0.03) |
| 최종: GGUF BF16 | 0.0118 (0.0143 / 0.0006) | 0.00066 | 0.73 (0.89 / 0.00) |
| 최종: GGUF Q8_0 | 0.0168 (0.0203 / 0.0008) | 0.00138 | 1.06 (1.29 / 0.04) |
| 최종: 자체 Q4_K_M | **0.0957** (0.1158 / 0.0045) | **0.0375** | **4.90** (5.94 / 0.20) |
| 최종: 공식 방식 Q4 | 0.0794 (0.0959 / 0.0041) | 0.0276 | 4.17 (5.04 / 0.20) |
| base: GGUF BF16 | 0.0111 | 0.00056 | 0.84 |
| base: GGUF Q8_0 | 0.0169 | 0.00140 | 1.13 |
| base: 자체 Q4_K_M | 0.1002 | 0.0399 | 4.93 |
| base: 공식 방식 Q4 | 0.0820 | 0.0287 | 4.12 |
| base: 공식 qwen3:8b blob | 0.0829 | 0.0293 | 4.20 |

- HF와 llama.cpp의 구현 차이(같은 BF16 가중치)는 |Δ| 약 0.011–0.013, KL 약 0.0006–0.0008이다. 병합(PEFT → 병합 BF16)도 같은 크기다.
- Q8_0은 그보다 조금 크다(KL 약 2배). **Q4는 KL이 Q8의 20–27배**다. 공식 방식 Q4는 자체 Q4보다 KL이 약 26% 작고, 공식 blob과 같은 수준이다.
- JSON 구간은 모든 경로에서 거의 결정적이다(|Δ| ≤ 0.008, top-1 불일치 ≤ 0.26%). 차이는 대부분 thinking 구간에 있다.

## 3. 학습 신호 보존

전체 평균 신호는 작다(token당 약 0.012 nat). 기준 응답이 두 모델 모두에게 익숙한 문장이 대부분이기 때문이다. 그래서 상관과 강한 학습 token을 함께 본다.

| 경로(최종 − 같은 경로 base) | 상관 thinking / JSON | 기울기 thinking / JSON | 강한 token 기울기(235개, thinking) | cal 묶음 thinking 강한 token 기울기(29개) |
|---|---|---|---|---|
| HF+adapter(기준) | 1 / 1 | 1 / 1 | 1 | 1 |
| HF 병합 BF16 | 0.974 / 1.000 | 0.971 / 0.980 | 0.959 | 1.057 |
| GGUF BF16 | 0.967 / 0.998 | 0.949 / 0.969 | 0.974 | 0.994 |
| GGUF Q8_0 | 0.936 / 0.997 | 0.956 / 0.955 | 0.983 | 1.133 |
| 자체 Q4_K_M | **0.528** / 0.919 | 0.874 / 0.839 | 0.930 | **0.228** |
| 공식 방식 Q4 | 0.674 / 0.943 | 0.875 / 0.859 | 0.913 | **0.225** |
| 참고: 자체 Q4 − 공식 qwen3:8b(주 비교 형태) | 0.572 / 0.937 | 0.916 / 0.873 | 0.958 | 0.159 |
| 참고: 공식 방식 Q4 − 공식 qwen3:8b | 0.678 / 0.945 | 0.866 / 0.862 | 0.879 | 0.230 |

- 상관이 낮은 것은 Q4 양자화 잡음(token당 |Δ| 약 0.06)이 학습 신호(약 0.012)보다 커서다. 평균 방향(기울기)은 0.84–0.88로 남는다.
- cal 묶음(HF-최종은 맞고 Ollama-최종은 자주 틀린 문항)의 강한 학습 token 29개에서 Q4는 신호의 약 23%만 남았다. Q8은 다 남았다. 표본이 29 token이라 근거는 약하다.

## 4. 결정 token(JSON 구간)

| 결정 token | 개수 | 값 | 모든 경로의 평균 확률 |
|---|---|---|---|
| `subtype` 값 | 172 | place 50, trip 28, trip_count 24, … | 1.000 |
| `dimension_target` 키·값 | 16·16 | pickup 9, dropoff 4, both 3 | 1.000 |
| `od_role` 값 | 27 | dropoff 12, pickup 8, both 7 | 1.000 |
| `aggregation` 값 | 27 | avg 11, sum 6, min 6, med 2, max 2 | 1.000 |
| `aggregation` 키 | 27 | — | HF 0.99, BF16 0.98–0.99, Q8 0.976·0.996, 자체 Q4 0.939·0.950, 공식 방식 Q4 0.924·0.923, 공식 blob 0.926 |

- JSON의 결정 token은 thinking이 끝난 뒤 거의 확률 1이다. 결정은 thinking 안에서 이미 내려진다. JSON 결정 token으로는 학습 효과의 경로별 차이를 볼 수 없었다.
- `aggregation` 키만 Q4에서 확률이 낮아지고(최소 0.06), 학습 신호의 부호도 경로마다 다르다(작음).

## 5. 결론

- **병합과 GGUF 변환(BF16)은 학습 신호를 남긴다 — 확인됨.** 기준과의 차이가 HF와 llama.cpp의 구현 차이와 같은 크기이고, 학습 신호의 상관이 0.97 이상이다.
- **Q8_0도 학습 신호를 대부분 남긴다 — 확인됨.** KL은 BF16의 약 2배지만 신호 상관 0.94(thinking)·0.997(JSON), 강한 token 기울기 0.98.
- **Q4 양자화에서 token 단위 학습 신호가 잡음에 묻힌다 — 확인됨(token 확률 수준).** thinking 상관 0.53(자체)·0.67(공식 방식), KL은 Q8의 20–27배다.
  이것이 sampling 정답률 차이로 이어지는지는 **가능성 있음**이다(cal 묶음 강한 token 23%만 남음, 29 token).
- **공식 방식 Q4는 자체 Q4보다 HF에 가깝다 — 확인됨**(KL 0.028 대 0.038, 상관 0.67 대 0.53). 그래도 Q8과의 차이가 훨씬 크다.
- **calibration_001에서 Q8(e)도 HF-최종보다 5.5%p 낮았던 이유는 이 측정으로 설명되지 않는다 — 미확인.** llama.cpp b11434에서 최종 Q8의 분포는
  HF-최종과 거의 같다. 남은 후보는 Ollama 실행 쪽 차이(llama.cpp 판, flash attention 끔), sampler 구현 차이(HF는 온도를 먼저
  적용한 뒤 top-k·top-p로 자르고, llama.cpp 기본 순서는 top-k·top-p 뒤 온도다. Ollama의 순서는 확인하지 않았다), 또는 그 비교의 CI가 0에 가까웠던 우연(CI 위 끝 −0.5)이다.

## 6. 한계

- teacher forcing이다. 경로마다 자기 출력에서 생기는 누적 차이(노출 편향)는 보지 않았다.
- KL은 top-64 근사라 실제보다 작게 나올 수 있다.
- 결정 token은 JSON 구간만 봤다. thinking 안의 결정 지점(예: "dimension_target을 넣을지" 판단 문장)은 따로 찾지 않았다.
- Ollama 0.35.1의 실행 경로 그 자체가 아니다(1절).
