# Ollama 등록 절차(문서만, 실행하지 않음)

`ollama create`는 공유 Ollama 서버(GPU 3, `localhost:11434`)의 상태를 바꾼다. 사용자 승인 뒤에만 실행한다. 이 문서의 명령과 Modelfile은 모두 **미검증 초안**이다.

## 준비된 것

| 항목 | 위치 | 상태 |
|---|---|---|
| base GGUF(Q4_K_M) | `/home/hwkim/sftdpo_work/gguf/qwen3-8b-b968826d-base-Q4_K_M.gguf`(저장소 밖) | 변환 완료. sha256과 명령은 `../gguf/qwen3-8b-b968826d-base.receipt.json` |
| 변환 스크립트 | `../gguf_convert.sh HF_MODEL_DIR OUT_DIR NAME` | llama.cpp b11434(commit 5e03bdd8) CPU 빌드, bf16 변환 뒤 Q4_K_M |
| Modelfile | `Modelfile.base.draft`, `Modelfile.trained.draft` | TEMPLATE은 HF 렌더링과 같도록 쓴 초안(미검증) |

## 승인되면 할 일(순서)

1. **base 변환본 등록.** 양자화와 template 효과를 학습 효과와 나누는 기준이다.
   ```bash
   ollama create geoflow-qwen3-8b-b968826d-base:q4km-hftmpl -f sft_dpo_inventory/pilot_prep_001/ollama/Modelfile.base.draft
   ```
2. **template 확인.** Ollama 측정이 돌지 않을 때 한다.
   - 업체 100 첫 계획 요청의 `prompt_eval_count`가 HF `apply_chat_template(enable_thinking=False)` token 수와 문항마다 같은지 본다(`template_compare.py`와 같은 방법).
   - 다르면 TEMPLATE을 고치고 다시 등록한다. 같지 않으면 다음 단계로 가지 않는다.
   - think 설정: 초안 TEMPLATE은 think 값과 관계없이 빈 think block을 렌더링한다. 평가는 `--model-think auto`(요청에 think를 넣지 않음)로 한다.
   - TEMPLATE이 `.Thinking`·`.IsThinkSet`을 쓰지 않으므로 Ollama가 이 모델을 thinking 가능 모델로 보지 않을 수 있다. 그러면 `think=false` 요청이 거부될 수 있다(미확인).
3. **base 변환본 셀(Ollama-F-conv).**
   ```bash
   python evaluate_vendor100.py --gold evaluation/vendor100/gold.yaml llm \
     --model geoflow-qwen3-8b-b968826d-base:q4km-hftmpl --condition-check --model-think auto \
     --reference-date 2026-09-25 --out sft_dpo_inventory/<dir>/Ollama-F-conv.json
   ```
   - 문항마다 모델을 내린다(기본). 기준일·조건은 Ollama F와 같다.
   - Ollama F(라이브러리 qwen3:8b, think=false)와 비교하면 변환본·template 차이가 나온다.
   - HF-F와 비교하면 양자화·client 차이가 나온다.
4. **학습 모델 변환과 등록.**
   - 순서: 학습 adapter → `python -m training.merge_adapter --base Qwen/Qwen3-8B --adapter <adapter> --output <merged> --dtype bfloat16` → `gguf_convert.sh <merged> /home/hwkim/sftdpo_work/gguf <TRAINED_NAME>` → `Modelfile.trained.draft`의 FROM을 채워 `ollama create`.
   - base와 같은 llama.cpp commit, 같은 양자화, 같은 TEMPLATE·PARAMETER를 쓴다.
5. **학습 모델 셀.**
   - 3과 같은 명령으로 잰다. 학습 효과는 이 셀과 3의 셀을 비교해 본다(같은 변환·양자화·template).
   - 학습 쪽 HF 셀(HF-F와 같은 경로, `--adapter`)과도 비교해, 양자화 뒤에도 차이가 유지되는지 본다.
6. **정리.** 측정이 끝나면 등록한 모델을 지울지 사용자와 정한다(`ollama rm`, 서버 상태 변경).

## 검증 명세

- 학습 모델을 운영 조합으로 쓰려면 `assistant_cli.py GEOFLOW_VERIFIED_SPECS`에 새 조합이 필요하다.
  - 항목: 모델 이름과 digest, prompt 87048d0c, 코드 지문 `791c4a68…`, settings(think 포함).
  - 측정 결과를 본 뒤 별도 작업으로 정한다.
