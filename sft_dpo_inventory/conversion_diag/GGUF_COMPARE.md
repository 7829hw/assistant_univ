# 공식 qwen3:8b(E)와 직접 변환본(B-conv) GGUF 비교, 실제 적용 파라미터(작업 지시 1, 결정 63 E-1, 2026-10-09)

모델 호출 없음(CPU). 가중치·GGUF는 저장소 밖에 있고 커밋하지 않았다.

- 스크립트: `gguf_compare.py`, `gguf_compare_extra.py`(llamacpp_venv의 gguf-py, CPU). 결과: `gguf_compare.json`, `gguf_compare_extra.json`.
- 파일:
  - E: Ollama blob `sha256-a3de86cd…`(`qwen3:8b`, digest `500a1f06…`, 5,225,374,496 B).
  - B-conv: blob `sha256-f060d7cb…`(`geoflow-qwen3-8b-b968826d-base:q4km-hfthink`, llama.cpp b11434로 HF 원본에서 변환, 5,027,784,064 B).
- HF 원본: `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218` safetensors(BF16).

## 1. 메타데이터

| 항목 | E(공식) | B-conv(직접 변환) |
|---|---|---|
| general.name | `Qwen3 8B` | `B968826D9C46Dd6066D109Eabc6255188De91218`(snapshot 폴더 이름) |
| 출처 표기 | basename `Qwen3`, size_label `8B`, license apache-2.0 | base_model `Qwen3 8B Base`(Qwen, HF Qwen3-8B-Base), license link, tags, size_label `8.2B` |
| general.sampling.* | 없음 | temp 0.6, top_k 20, top_p 0.95(변환기가 generation_config에서 넣음) |
| file_type / quantization_version | 15(Q4_K_M) / 2 | 15(Q4_K_M) / 2 |
| imatrix 키(`quantize.imatrix.*`) | **없음** | **없음** |
| 구조 하이퍼파라미터(block 36, ctx 40960, emb 4096, ffn 12288, head 32/8, rope 1e6, eps 1e-6, key/value 128) | 같음 | 같음 |
| tokenizer(model gpt2, pre qwen2, tokens 151936, token_type, merges 151387, bos/eos/pad id 151643/151645/151643, add_bos false) | 같음(배열 sha256 같음) | 같음. `add_eos_token false` 키만 더 있음 |
| GGUF 안의 chat_template(jinja) | 4116자 `87a2728c…` | 4168자 `a55ee1b1…`(HF tokenizer_config의 것) |

- GGUF 안의 jinja chat_template은 Ollama 렌더링에 쓰이지 않는다. Ollama는 manifest의 TEMPLATE 층(Go template)을 쓴다(3절).
- `general.base_model`(Qwen3-8B-Base)은 HF model card 메타데이터를 변환기가 옮긴 것이다. 가중치 출처와는 관계없다(B-conv는 Qwen3-8B 원본에서 만들었다).

## 2. 텐서

- 텐서 이름·개수(399)·모양: **같다.** 한쪽에만 있는 텐서 0, 모양 차이 0. 원소 수 합계 8,190,735,360으로 같다.
- 텐서별 타입: 차이는 **attn_v 36개뿐**이다.
  - E: attn_v가 모두 **F16**이다.
  - B-conv: Q4_K_M 기본 규칙대로 Q6_K 18개와 Q4_K 18개다.
  - 나머지 363개 텐서는 타입이 같다(Q4_K 199, Q6_K 19, F32 145).
  - 파일 크기 차이(약 198 MB)는 이 attn_v 때문이다.
- 같은 타입 텐서의 양자화 바이트: F32 145개는 바이트가 같다. Q4_K 199개와 Q6_K 19개는 바이트가 다르다(0개 일치). 양자화 구현이나 버전이 다르다는 뜻이다(4절의 오차는 같은 수준).

## 3. 원본 가중치가 HF b968826d와 같은가

**결론: 같음.**

근거 1(결정적): E의 F16 텐서 attn_v 36개 층 전체를 HF BF16과 원소 단위로 비교했다(`gguf_compare_extra.json`).
- 층마다 4,194,304개 중 4,193,529–4,193,726개(99.98% 이상)가 정확히 같다.
- 나머지 원소의 최대 차이는 2.98e-8이다. BF16 → F16 변환에서 F16 최소 정규수보다 작은 값이 반올림된 것이다. 다른 가중치라면 나올 수 없는 일치다.

근거 2: 역양자화한 텐서를 HF BF16과 비교했다. 대상은 임베딩, 출력, 0·1·17·18·34·35층의 attention(q, k, v, o)·MLP(gate, up, down)·norm이다.

| 텐서(대표) | E 타입 | E 상대 오차 / 상관 | B-conv 타입 | B-conv 상대 오차 / 상관 | E ↔ B-conv 상대 차 |
|---|---|---|---|---|---|
| token_embd | Q4_K | 0.07145 / 0.99745 | Q4_K | 0.07145 / 0.99745 | 0.0034 |
| output | Q6_K | 0.01776 / 0.99984 | Q6_K | 0.01776 / 0.99984 | 0.0006 |
| blk.0.attn_q | Q4_K | 0.07171 / 0.99743 | Q4_K | 0.07171 / 0.99743 | 0.0030 |
| blk.0.attn_v | **F16** | **0 / 1.0** | Q6_K | 0.01805 / 0.99984 | 0.0180 |
| blk.0.ffn_down | Q6_K | 0.01816 / 0.99984 | Q6_K | 0.01816 / 0.99984 | 0.0006 |
| blk.17.ffn_down | Q4_K | 0.07333 / 0.99731 | Q4_K | 0.07333 / 0.99731 | 0.0030 |
| blk.18.attn_output | Q4_K | 0.07186 / 0.99742 | Q4_K | 0.07186 / 0.99742 | 0.0032 |
| blk.35.ffn_gate | Q4_K | 0.07216 / 0.99740 | Q4_K | 0.07216 / 0.99740 | 0.0031 |
| norm(F32) | F32 | 0 / 1.0 | F32 | 0 / 1.0 | 0 |

- 같은 타입의 양자화 텐서 50개 모두에서 E와 B-conv의 HF 대비 오차가 소수 다섯째 자리까지 같다. 전체 표는 `gguf_compare.json`의 `dequant_vs_hf`에 있다.
- 두 양자화본끼리의 차이(Q4_K 0.3%, Q6_K 0.06%)는 각자의 HF 대비 오차(7.2%, 1.8%)보다 훨씬 작다. 같은 원본을 서로 다른 구현으로 양자화한 경우의 모양이다.
- 그래서 E와 B-conv의 차이는 다음 셋이다. 원본 가중치는 차이가 아니다.
  - attn_v 정밀도(E는 F16, B-conv는 Q6_K/Q4_K).
  - 같은 타입 텐서의 양자화 반올림.
  - TEMPLATE.

## 4. 실제 적용 파라미터(결정 63 E-1, `/api/show`와 manifest)

`api_show/*.json`(`/api/show` 원문, license 제외)와 `api_show/manifests.json`(manifest 층, `manifest_layers.py`)이다.

| 모델 | 가중치 blob | TEMPLATE 층 | PARAMETER 층 | `/api/show` parameters | 실행 컨텍스트(`ollama ps`) |
|---|---|---|---|---|---|
| E `qwen3:8b` | `a3de86cd`(Q4_K_M) | `ae370d88`(공식, 1723 B) | `cff3f395` | stop `<|im_start|>`·`<|im_end|>`, temperature 0.6, top_k 20, top_p 0.95, repeat_penalty 1 | 40960 |
| B-conv | `f060d7cb`(Q4_K_M) | `e38a19eb`(HF 형식, 565 B) | `cff3f395` | 같음 | 40960 |
| pilot_002 SFT | `8cda8c95`(Q4_K_M) | `e38a19eb` | `cff3f395` | 같음 | 40960 |
| pilot_002 최종 | `ab359d09`(Q4_K_M) | `e38a19eb` | `cff3f395` | 같음 | 40960 |
| 진단 (c) | `a3de86cd`(E와 같은 blob) | `e38a19eb` | `cff3f395` | 같음 | 40960 |
| 진단 (d) | `6f7c42fd`(base Q8_0) | `e38a19eb` | `cff3f395` | 같음 | 40960 |
| 진단 (e) | `47ba910c`(최종 Q8_0) | `e38a19eb` | `cff3f395` | 같음 | 40960 |

- **PARAMETER 층은 모든 모델이 같은 blob `cff3f395`이다.** stop·temperature·top_k·top_p·repeat_penalty가 같다. num_ctx·num_predict·seed는 어느 모델에도 없다.
- 실행 컨텍스트: 모든 모델이 40960이다(`ollama ps` CONTEXT, 결정 55 확인 기록 `*_gpu_guard.json`). 컨테이너 환경 변수에 `OLLAMA_CONTEXT_LENGTH`는 없다.
- B-conv·학습 모델 GGUF의 `general.sampling.*`는 Modelfile PARAMETER와 값이 같다. `/api/show` 결과도 E와 같다.
- `/api/show`의 `template` 필드는 E 외의 모델에서 저장된 TEMPLATE 층이 아니라 GGUF의 jinja chat_template을 보여 준다(Ollama 0.35.1).
  - 그래서 TEMPLATE의 실제 내용은 manifest의 층 digest로 확인했다.
  - B-conv 등록 기록에도 같은 현상이 있다(`pilot_prep_003/ollama/registration.json`의 `show_template_equals_sent: false`).
- **평가 harness가 요청에 넣는 옵션**(`evaluate_vendor100.py llm` → `ollama_client.OllamaClient.chat`):
  - `options {"temperature": 0}`만 보낸다. top_k·top_p·repeat_penalty·num_ctx·num_predict·seed는 보내지 않는다.
  - `think`는 `--model-think auto`라 payload에 넣지 않는다. `stream false`, `tools` 없음.
  - 문항마다 모델을 내린다(`OllamaStateReset`).
  - temperature 0이면 다른 sampling 파라미터는 결과에 쓰이지 않는다(greedy).
- **다른 값의 목록: 없음.** 비교하는 모델들의 실제 적용 파라미터와 요청 옵션은 모두 같다. 모델마다 다른 것은 가중치와 TEMPLATE뿐이다.

## 5. 진단 모델 등록(작업 지시 2)

`registration/*.json`(이름, digest, 원천 sha256, Modelfile 내용, show 결과), `register_diag.py`.

| 기호 | 이름 | digest | 원천 | TEMPLATE |
|---|---|---|---|---|
| (a) | `geoflow-diag-qwen3-8b-official-p002final-lora:q4km` | **만들지 못함** | 공식 qwen3:8b + LoRA GGUF | 공식 |
| (b) | `geoflow-diag-qwen3-8b-official-p002final-lora-hftmpl:q4km` | **만들지 못함** | 공식 qwen3:8b + LoRA GGUF | HF 형식 |
| (c) | `geoflow-diag-qwen3-8b-official-hftmpl:q4km` | `f83b28a9…` | 공식 qwen3:8b(blob `a3de86cd`) | HF 형식(`e38a19eb`) |
| (d) | `geoflow-diag-qwen3-8b-b968826d-base:q8_0-hfthink` | `3c3843ae…` | `qwen3-8b-b968826d-base-Q8_0.gguf` sha256 `6f7c42fd…`(base BF16 GGUF `4bed31be…`를 llama.cpp b11434 `llama-quantize Q8_0`) | HF 형식 |
| (e) | `geoflow-diag-qwen3-8b-pilot002-final:q8_0-hfthink` | `b608abf0…` | `qwen3-8b-pilot002-final-Q8_0.gguf` sha256 `47ba910c…`(pilot_002 최종 병합 BF16 GGUF를 같은 방법으로) | HF 형식 |

- **(a)·(b):** 3절에서 원본 가중치가 "같음"이라 만들기로 했다.
  - LoRA GGUF를 만들었다: `convert_lora_to_gguf.py --outtype f32 --base Qwen3-8B@b968826d`. 원천은 DPO checkpoint-144 `policy`(adapter sha256 `60cf9ffe…`)이고, 결과 `qwen3-8b-pilot002-final-dpo144-lora-f32.gguf`의 sha256은 `c24d902cd9a8df74…`다(`registration/ab_lora_rejected.json`).
  - `POST /api/create`(`from: qwen3:8b`, `adapters`)는 **Ollama 0.35.1이 `400 {"error":"LoRA adapters are no longer supported"}`로 거부했다.** 두 모델 모두 등록되지 않았다.
  - 그래서 (a)·(b) 셀은 건너뛰었다.
  - create 전에 올린 LoRA blob(약 175 MB)이 Ollama blob 저장소에 남아 있다. 어떤 모델도 참조하지 않는다. 지우지 않았다.
- PARAMETER는 모두 E와 같은 값을 명시했다(manifest의 PARAMETER 층 blob이 E와 같다, 4절).
- 렌더링 확인(결정 31) + 결정 55 확인(`render/*.json`, `*_gpu_guard.json`): (c)·(d)·(e) 모두 10/10 통과했다.
  - 확인 항목: token 수 = HF `enable_thinking=True` 렌더링, think 미지정에서 thinking 켬, 분리.
  - 100% GPU였고, 호출 최저 속도는 113.7·81.2·80.7 tok/s다.
- 공식 TEMPLATE을 쓰는 진단 모델((a))은 만들지 못했으므로 "공식 E와 같은 렌더링" 확인은 할 대상이 없었다.
