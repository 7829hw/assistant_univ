# conversion_diag 실행 조건(측정 전에 적음, 2026-10-09)

결정 59–63에 따른 학습 없는 진단이다. 업체 100과 aux_test_v1은 쓰지 않는다. prompt와 `SEMANTIC_CODE`는 바꾸지 않는다(지문 `791c4a68…`).

## 1. selection_v1 Ollama 셀

- 셋: `selection_gold.yaml`(`build_selection_yaml.py`). selection_v1(`selection_items.json`, sha256 `405af9c8…`, 100문항)의 원본 문항·라벨을
  그대로 옮기고 id만 HF 기록과 같은 `set/id`로 바꿨다. 순서는 HF-base 기록(`pilot_prep_005/sets/runs/selection_base.json`)과 같다.
- 명령: PROTOCOL_v2 운영 셀과 같다(aux_test 셀과 같은 명령).
  `evaluate_vendor100.py --gold selection_gold.yaml llm --model M --reference-date 2026-09-25 --condition-check --model-think auto`
  - 요청 options `{"temperature": 0}`, think 미지정, num_predict 미지정, 문항마다 모델 내림(harness 기본).
- 셀(만든 모델만): E, (c), B-conv, (d), (b), (a), Ollama-최종, (e). 셀마다 한 번 잰다. 결과가 예상과 달라도 다시 재지 않는다.
- HF 측정과 동시에 돌리지 않는다(이번 작업에는 HF 측정이 없다). Ollama 측정 중에는 다른 Ollama 호출을 하지 않는다.

## 2. 결정 55 확인

- 셀과 렌더링 확인마다 `pilot_002/ollama_gpu_guard.py`의 precheck(컨테이너 GPU 2, 버전 0.35.1, 올라간 모델 없음, GPU 2에 다른 프로세스 없음)와
  watch(첫 문항 100% GPU, 호출별 생성 속도)를 붙인다.
- 생성 속도 기준: **30 tok/s**(pilot_002와 같은 값, `pilot_002/PLAN_DEVIATIONS.md` 1번).
  - Q4_K_M 모델의 GPU 기록은 호출당 최저 약 89 tok/s다(aux_test E·B-conv). CPU로 돌 때는 약 5 tok/s였다.
  - Q8_0 모델과 실행 중 LoRA를 얹은 모델은 GPU에서도 Q4_K_M보다 느릴 수 있다. 그래도 CPU 수준(약 5 tok/s)과는 크게 차이 나므로
    같은 30 tok/s를 쓴다. 측정 전에 정한 값이며 측정 뒤 바꾸지 않는다.
- guard가 멈춘 셀은 `ABORTED_gpu_*`로 남기고 판정·비교에 쓰지 않는다. 컨테이너는 건드리지 않는다.

## 3. 렌더링 확인(결정 31)

- `pilot_002/ollama/render_check.py`(v004 학습 질문 10개, `keep_alive 0`, 요청은 평가 harness와 같은 형태)를 모델마다 돌린다.
- HF 형식 TEMPLATE 모델((b), (c), (d), (e)): 기존과 같이 10/10이 `prompt_eval_count = HF token 수`, thinking 켬, 분리.
- 공식 TEMPLATE 모델((a)): `prompt_eval_count`가 E(공식 qwen3:8b)의 같은 문항 값과 같고, thinking 켬, 분리.
  E는 HF 렌더링과 2 token 다르다(system 앞 줄바꿈, 마지막 user 턴의 ` /think`, `thinking_prep_001/REPORT.md` 6절). 그래서 E도 같은 확인을 돌려 기준으로 쓴다.
- TEMPLATE의 실제 내용은 `/api/show`의 `template`이 아니라 manifest의 template 층 digest로 확인한다(`manifest_layers.py`).
  Ollama 0.35.1의 `/api/show`는 GGUF의 `tokenizer.chat_template`을 보여 준다(B-conv 등록 때부터 `show_template_equals_sent: false`).
- 확인을 통과하지 못한 모델은 selection_v1 셀을 재지 않고 기록한다.
