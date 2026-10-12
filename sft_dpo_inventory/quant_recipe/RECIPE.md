# 공식 방식 Q4_K_M(결정 75, 작업 1)

작성: 2026-10-12. CPU만 썼다. GGUF는 저장소 밖(`/data/hwkim/sftdpo_work/gguf/quant_recipe/`)에 있고 커밋하지 않았다.

## 1. 방법

- 근거: `conversion_diag/GGUF_COMPARE.md` 2절. 공식 qwen3:8b와 자체 Q4_K_M은 텐서 399개 중 attn_v 36개의 타입만 달랐다(공식은 F16, 자체는 Q6_K 18 + Q4_K 18).
- 공식 방식: llama-quantize의 텐서별 타입 지정으로 attn_v만 F16에 두고, 나머지는 Q4_K_M 기본 규칙을 그대로 쓴다.
- llama.cpp: tag `b11434`, commit `5e03bdd8700948b9c41c54dd1b00f28a2aebc03f`(자체 Q4·Q8과 같은 빌드, CPU, `build/bin/llama-quantize`).
- 입력은 자체 Q4·Q8을 만들 때 쓴 BF16 GGUF 그대로다(다시 변환하지 않음, sha256은 각 영수증과 같음).
- 명령(`pilot_prep_001/gguf_convert.sh`의 새 선택 `QUANT_RECIPE=official FROM_BF16=…`; 기본 동작은 그대로):

```
llama-quantize --tensor-type attn_v=f16 <BF16.gguf> <NAME-Q4_K_M-official.gguf> Q4_K_M
```

- 로그: 두 파일 모두 attn_v 36개에 `applying manual override: q4_K -> f16`이 찍혔다(로그의 앞 타입은 층별 Q6_K 조정 전의 값이다). imatrix는 쓰지 않았다(공식 blob에도 imatrix 키가 없다).

## 2. 파일

| 이름 | 입력 BF16 GGUF(sha256) | 결과(sha256) | 바이트 |
|---|---|---|---|
| base 공식 방식 Q4 | `qwen3-8b-b968826d-base-bf16.gguf`(`4bed31be…`) | `qwen3-8b-b968826d-base-Q4_K_M-official.gguf` `c55752ae518c9f07e72b03e3ad031e7efb157eab09fea201da91c1f88d681a20` | 5,225,375,104 |
| 최종 공식 방식 Q4 | `qwen3-8b-pilot002-final-bf16.gguf`(`86def6bd…`, DPO step 144 병합본) | `qwen3-8b-pilot002-final-Q4_K_M-official.gguf` `6daac75369edf6662b0cd126d5063de5e566f87878b61ffdec7eca672e8f308f` | 5,225,374,624 |

- 참고: 공식 qwen3:8b blob은 5,225,374,496 B다. 차이(128–608 B)는 메타데이터(이름, chat_template 문자열 등) 길이다.
- 영수증: `qwen3-8b-b968826d-base.official.receipt.json`, `qwen3-8b-pilot002-final.official.receipt.json`.

## 3. 텐서 타입 비교(`compare_types.py`, `compare_types.json`)

| 파일 | 텐서 | 공식과 같은 타입 | 다른 타입 | 모양 차이 | 타입 구성 |
|---|---|---|---|---|---|
| 공식 qwen3:8b blob `a3de86cd…` | 399 | — | — | — | Q4_K 199, Q6_K 19, F16 36, F32 145 |
| base 자체 Q4_K_M | 399 | 363 | 36(attn_v: Q4_K 18, Q6_K 18) | 0 | Q4_K 217, Q6_K 37, F32 145 |
| 최종 자체 Q4_K_M | 399 | 363 | 36(같음) | 0 | Q4_K 217, Q6_K 37, F32 145 |
| **base 공식 방식 Q4** | 399 | **399** | 0 | 0 | Q4_K 199, Q6_K 19, F16 36, F32 145 |
| **최종 공식 방식 Q4** | 399 | **399** | 0 | 0 | Q4_K 199, Q6_K 19, F16 36, F32 145 |

- 두 공식 방식 파일 모두 텐서 399개의 타입이 공식 파일과 모두 같다(**확인됨**).
- 같은 타입 텐서의 양자화 바이트는 공식 blob과 다를 수 있다(GGUF_COMPARE 2절: 양자화 구현·버전 차이, 오차 수준은 같음). 이번에는 바이트 비교를 하지 않았다.
