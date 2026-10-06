# thinking 켬 학습·평가 준비 (thinking_prep_001)

작성: 2026-10-06. 브랜치 `geoflow/sft-dpo-t2pc`. pilot 학습, `ollama create`, prompt 변경, SEMANTIC_CODE 변경은 없다.
실행 의미 코드 지문은 작업 시작과 끝 모두 `791c4a68…`이다. 업체 100 결과는 평가 전용이며 학습·checkpoint 선택·trace 선택에 쓰지 않았다.

## 0. 요약

- **결정 기록.** `CLAUDE.md` 9번에 학습·평가 thinking 켬과 비교 기준(Ollama E, HF-E)을 적었다. 기존 nonthinking 기록은 그대로 두었다.
- **HF-E(업체 100).** grounding_ok 84, 정상 91, U 2. 두 번 잰 첫 응답(thinking 포함)이 100/100 바이트 단위로 같다.
  - Ollama E(79)와 같은 문항으로 비교하면 grounding_ok가 17문항에서 바뀐다(얻음 11, 잃음 6).
  - 지연 중앙값은 22.0초로 Ollama E(11.9초)의 약 2배다.
  - 생성 상한(8192)에 걸린 응답은 1문항, 2회다(095의 재질의).
- **trace.** v003_t2pc 학습 split 19문항. greedy 정답 3, pass@8 12, 정답 표본이 없는 문항 7.
  - 계약 통과로 거른 뒤 SFT 후보는 42개(12문항), DPO 쌍은 204개다.
  - DPO 쌍 204개 중 139개는 rejected가 조건 계층을 거치면 맞는다.
- **형식.** thinking SFT·DPO 형식을 추가했다. 학습 prompt 렌더링은 추론 렌더링(`enable_thinking=True`)과 token 단위로 같다.
  - **생성 token과의 일치:** 171개 trace 중 10개는 decode한 문자열을 다시 tokenize하면 생성 token과 분절이 다르다(SFT 후보에서 2개).
- **메모리(새 한도 SFT 9216, DPO 9216/7424/1920).**
  - SFT: peak 40.0GB, 6.2초/step.
  - DPO: peak 48,200MiB(전체 49,140MiB), 23.3초/step.
  - **DPO는 통과했지만 여유가 1GB 미만이다.**
- **Ollama template.** thinking 초안은 Python 옮김에서 HF와 6/6 바이트 동일하다(미검증 3항목).
- **작업 중 사용자 지시.** CUDA 2·3을 모두 썼다(3절). 그리고 금지된 Ollama 읽기 호출(`/api/ps`) 1회가 있었다(3절).

## 1. 결정 기록

- `CLAUDE.md`에 9번 규칙을 추가했다(`008515c`).
  - 학습 대상은 qwen3:8b + T2PC 코드·prompt 87048d0c이고, 학습·평가 모두 thinking 켬이다.
  - 비교 기준: Ollama 경로는 E(think 미지정 = 켬, 79), HF 경로는 HF-E.
  - 새 데이터·config·평가 셀에서 nonthinking으로 돌아가지 않는다.
- 기존 nonthinking 기록은 지우거나 고치지 않았다: F, HF-F, v003_t2pc nonthinking export, nonthinking config.

## 2. HF-E 기준 셀(`hf_eval_thinking.py`, 결과 `hf_e/`)

- **조건.**
  - 모델·렌더링: base Qwen/Qwen3-8B@b968826d, prompt 87048d0c, `enable_thinking=True`, greedy, BF16·SDPA.
  - max_new_tokens 8192: 측정 전에 정했고 바꾸지 않았다.
  - 기준일 2026-09-25: Ollama E와 같다.
  - pipeline·채점은 `evaluate_vendor100`과 같다.
  - 응답은 `</think>` 기준으로 thinking과 본문을 나눠 Ollama 기록과 같은 형식으로 남겼다.
  - thinking 원문은 `training/generated/thinking_prep_001/`(ignored)에 두었다.
- **실행.**
  - 1회차·2회차 모두 CUDA 2(host GPU 2)에서 돌렸다. 각 약 52분, peak 17.5GiB.
  - 2회차와 trace 수집은 서로 다른 GPU에서 동시에 돌았다(3절).

| 셀 | grounding_ok | 정상 | U | 조용한 오답(U 아님) | 안전한 실패 | 첫 응답 raw 유효 / 일치 | + 조건 계층 일치 | 지연 중앙값 / p90 | thinking(첫 계획) 중앙값 / 최대 | 재질의 호출 |
|---|---:|---:|---:|---:|---:|---|---:|---|---|---:|
| Ollama E(qwen3:8b Q4_K_M, think 미지정) | 79 | 84 | 3(U1 2, U2 3, U3 2) | 1 | 12 | 92 / 59 | 73 | 11.9 / 17.1초 | 2,101 / 8,987자 | 17 |
| HF-E 1회 | 84 | 91 | 2(U1 1, U2 2, U3 1) | 0 | 7 | 94 / 64 | 79 | 22.0 / 50.3초 | 2,301 / 10,070자 | 18 |
| HF-E 2회 | 84 | 91 | 2 | 0 | 7 | 94 / 64 | 79 | 22.0 / 50.3초 | 같음 | 18 |

- **반복성.** 1·2회차의 첫 계획 원문(thinking 포함, sha256)이 100/100 같다. 분류도 모두 같다.
- **생성 상한.**
  - 118회 호출 중 2회가 8192 token에서 잘렸다(1문항, 095). 첫 계획은 751 token이었고, 재질의 두 번이 모두 상한에 걸려 실패로 끝났다.
  - 생성 token 중앙값은 767이다.
- **Ollama E → HF-E(같은 100문항).**

| grounding_ok 전이 | 문항 |
|---|---:|
| 일치 → 일치 | 73 |
| 일치 → 불일치 | 6 |
| 불일치 → 일치 | 11 |
| 불일치 → 불일치 | 10 |

- 분류가 바뀐 문항은 14개다.
  - 안전한 실패 → 정상 6, U → 정상 3, 조용한 오답 → 정상 1.
  - 정상 → 안전한 실패 2, 정상 → U 1, 안전한 실패 → U 1.
  - 첫 응답 본문이 같은 문항은 19개다. 문항 목록은 `hf_e/comparison.json`에 있다.
- **원인 후보**(정하지 않는다. 여러 조건이 함께 작용할 수 있다):
  - 렌더링: Ollama의 thinking 켬 렌더링은 마지막 user 턴에 ` /think`를 붙이고 system 앞에 줄바꿈을 하나 더 넣는다. HF `enable_thinking=True`에는 둘 다 없다(5절, 2 token 차이).
  - 양자화: Q4_K_M 대 BF16.
  - 생성 구현: llama.cpp 대 transformers.
  - 생성 상한: Ollama E는 num_predict를 지정하지 않았고, HF-E는 8192다.
  - Modelfile 기본값: top_k·top_p. harness는 temperature 0만 보낸다.

## 3. GPU와 Ollama 관련 기록

- **GPU 확인(`gpu_uuid_check.txt`).**
  - Ollama 컨테이너 안 `nvidia-smi -L`은 계속 `Failed to initialize NVML: Unknown Error`다.
  - 지난번 사용자가 승인한 대체 근거로 확인했다: 컨테이너 장치는 `/dev/nvidia3`(host GPU 3, PCI BD), torch CUDA 2는 PCI 0xAB(host GPU 2).
- **사용자 지시로 CUDA 3도 썼다.** 작업 중 사용자가 "CUDA 기준 2, 3번을 모두 사용해서 작업해"라고 지시했다.
  - CUDA 3은 host GPU 3(`GPU-48f798cc`), 즉 Ollama 컨테이너에 배정된 GPU다. 시작 전 사용량은 2MiB였다.
  - CUDA 3에서 돌린 것: trace 수집(약 37분, peak 29.1GiB), thinking 메모리 확인.
  - HF-E 2회차는 CUDA 2에서 같은 시간에 돌았다. HF 작업끼리만 동시에 돌았고, Ollama 측정은 없었다.
  - CLAUDE.md 5·6번(학습·HF는 GPU 2만)은 바꾸지 않았다. 이번 작업에 한한 지시로 기록한다.
  - 처음 순서대로 기다리던 trace 대기 스크립트(`run_traces.sh`)는 멈추고 `run_traces_cuda3.sh`로 바꿨다. 실행 순서와 시각은 `gpu_runs.log`에 있다.
- **금지된 Ollama 읽기 호출 1회.**
  - CUDA 3 상태를 확인하는 명령에 `curl localhost:11434/api/ps`가 들어가 있었다. 이번 작업은 `/api/show` 같은 읽기 호출도 금지했다.
  - 모델 호출이나 상태 변경은 없었다. 그 뒤로 Ollama를 호출하지 않았다.

## 4. 학습용 thinking trace(`collect_traces.py`, 요약 `traces/`)

- **조건.**
  - 대상: `reviewed_gold_v003_t2pc` 학습 split 19문항. batch004는 쓰지 않았다(같은 스크립트에 `--corpus`·`--split`을 주면 다시 돈다).
  - 생성: 질문마다 greedy 1 + 표본 8. 표본 설정은 temperature 0.6, top_p 0.95, top_k 20, seed 20261006 + 문항 순번이다.
  - 그 밖: `enable_thinking=True`, max_new_tokens 8192. 잘린 생성은 0이다.
  - gold를 힌트로 주는 방식은 쓰지 않았다.
  - trace 원문은 `training/generated/thinking_traces/v003_t2pc_train/traces.jsonl`(ignored)에 있다. sha256 `23b9c8cd…`.
- **판정.** 조건 계층을 거치기 전 모델 출력의 JSON을 gold와 `grounding_check`로 비교했다.

| 항목 | 값 |
|---|---|
| greedy 정답 | 3/19 |
| pass@8(표본 8개 중 하나 이상 정답) | 12/19 |
| 정답 표본이 하나도 없는 문항 | 7: ann-77e9dacb(compile 정지), ann-e645cbc1, ann-9b222bf8, ann-a27c5965(RB002-02, compile 정지), ann-914c48da(RB002-04, compile 정지), ann-8b23b657(RB003-13), ann-51491e86(RB003-14) |
| 조건 계층을 거친 뒤에만 맞는 표본 | 74 |
| SFT 후보(같은 질문의 같은 원문은 하나로) | 44 → 계약 판정을 통과한 42(12문항, greedy 2·표본 40) |
| DPO 쌍(정답 표본 × 오답 표본) | 214 → chosen 계약 실패 제외 후 204(semantic 89, constraint 115) |
| DPO 쌍 중 rejected가 조건 계층을 거치면 맞는 쌍 | 139/204 |
| rejected 오류 태그(중복 집계) | factor_date 95, factor_taxi_type 78, places 38, aggregation_spec 19, dimension 8, time 4, taxi_status 4, limit 3, order 3, scopes 2 |

- **계약 실패 제외.** `grounding_check`가 맞다고 본 표본 2개(1문항)가 기존 계약 판정에서 `INVALID_FACTOR_COMBINATION`이었다. 학습 target으로 쓸 수 없어 builder가 빼고 숫자를 남긴다(그 표본을 chosen으로 쓰는 DPO 쌍 10개도 뺐다).
- **v003 표시는 그대로 붙였다.**
  - SFT: `compile_stop:UNVERIFIED_TIMS_CONTRACT` 19개.
  - DPO: `compile_stop:UNVERIFIED_TIMS_CONTRACT` 88쌍, `t2pc_rejected_equals_chosen`(factor_omission_taxi_type) 20쌍, `t2pc_constraint_rejected_passes_contract` 8쌍.
- **사람이 읽어 볼 표본 10개**(seed 7): `traces/summary.json`의 `human_review_sample_trace_ids`. 추론 문장은 사람이 검토하지 않았다.
- **정답 표본이 없는 7문항의 대안**(선택지만, 효과는 추정하지 않음):
  1. 표본 수를 늘린다(같은 base, 비용만 증가).
  2. teacher 모델을 쓴다. 예를 들어 Ollama qwen3.8:27b(T2PC 기본)의 thinking 출력을 쓴다. 단 Ollama 사용·GPU 상태 확인이 선행되어야 하고, 학생과 다른 모델의 추론 분포가 된다.
  3. 이 문항은 thinking SFT에서 비우고 nonthinking gold만 남긴다. thinking 결정과 섞이므로 사용자 판단이 필요하다.

## 5. thinking 학습 데이터 형식·길이·메모리

- **형식.**
  - `training/data/thinking.py`, `build_thinking.py`를 추가하고 `trainer_common`에 연결했다. nonthinking 경로는 그대로다.
  - assistant 내용은 모델이 생성한 원문(`<think>…</think>` + JSON) 그대로다.
  - loss 범위는 config `thinking.loss_scope`(`full_response` | `json_only`)이며 기본값이 없다. SFT config는 자리표시자라서, 정하지 않으면 trainer가 멈춘다.
  - DPO는 `full_response`만 동작한다. chosen·rejected의 추론이 달라 `json_only`의 공유 prompt를 만들 수 없기 때문이다.
- **테스트(`tests/test_training_thinking.py`).**
  - 학습 prompt = 추론 렌더링이다(token 단위, `apply_chat_template(enable_thinking=True)`와 같음).
  - json_only 분리, DPO 범위 거부, 필수 설정 거부를 확인한다.
  - decode 왕복은 171/171이다.
  - **completion token = 생성 token은 모든 trace에서 성립하지 않는다.**
    - 171개 중 10개(greedy 1, 표본 9)는 같은 문자열을 다시 tokenize하면 분절이 다르다(길이 차이 최대 5 token, `traces/tokenization_check.json`).
    - SFT 후보 2개, DPO에 쓰인 trace 5개가 해당한다.
    - 이 테스트는 그 사실을 드러내도록 expected failure로 두었다.
  - 선택지(고르지 않음):
    - (a) 텍스트 기반 그대로(tokenizer 기본 분절로 학습).
    - (b) 생성 token id를 저장해 그대로 학습하도록 trainer를 바꾼다.
    - (c) 불일치 trace를 뺀다.
- **길이**(`token_lengths_{sft,dpo}.json`, 재구성 데이터 `training/generated/thinking_v003_t2pc_train/`):

| | prompt 최대 | 응답 p50 / 최대 | total p50 / 최대 |
|---|---:|---|---|
| SFT 42 | 7,314 | 1,041 / 1,851 | 8,325 / 9,133 |
| DPO 204 | 7,314 | chosen 1,047 / 1,851, rejected 966 / 1,633 | 8,465 / 9,133 |

- **config(`training/configs/qwen3_8b_t2pc_thinking_{sft,dpo}.yaml`).**
  - 한도: SFT 9216, DPO total 9216 / prompt 7424 / completion 1920.
  - `enable_thinking: true`.
  - dry-run과 DPO tokenizer check를 통과했다. SFT tokenizer check는 loss_scope 자리표시자 때문에 의도대로 멈춘다.
  - 새 trace(batch004 등)는 더 길 수 있다. HF-E의 생성은 최대 8192까지 갔다.
- **메모리**(`memory_probe_thinking.py`, CUDA 3 = host GPU 3, 가장 긴 레코드, LR 0, 3 step, SFT loss_scope는 측정 때만 full_response):

| 단계 | TRL 길이 | torch allocated / reserved | nvidia-smi peak | step 시간 | 결과 |
|---|---|---|---|---|---|
| SFT | input 9,132 | 33.92 / 38.53 GiB | 39,982 MiB | 6.2초 | PASS |
| DPO | prompt 7,281, chosen 1,851, rejected 918 | 42.12 / 46.55 GiB | **48,200 MiB / 49,140** | 23.3초 | PASS(여유 1GB 미만) |

- 임시 adapter는 저장소 밖에 두었다가 지웠다.
- DPO는 chosen·rejected가 둘 다 1,920 한도에 가까운 쌍이면 OOM 가능성이 높다(측정하지 않음).
- 설정은 바꾸지 않았다. 선택지와 학습 조건에 미치는 영향은 다음과 같다.
  - **DPO reference precompute**(thor `reference.strategy: precompute`): reference forward를 미리 계산해 메모리를 줄인다. 시간은 는다. 학습 조건(고정 reference)은 같다.
  - **completion 상한 낮추기**: 긴 추론 응답이 학습에서 빠지거나 잘린다. thor 규칙상 자르지 않으므로 빠진다. 학습 분포가 짧은 추론 쪽으로 기운다.
  - **4-bit(QLoRA)**: base 정밀도가 평가와 달라진다.
  - **LoRA rank·target 줄이기**: 학습 용량이 바뀐다.
  - **DPO를 다른 장비나 2 GPU로 나누기**: 설정이 바뀌고 별도 검증이 필요하다.

## 6. Ollama template 초안(thinking용, 등록 안 함)

- **근거.** `pilot_prep_001/template/ollama_qwen3_8b.template`(Ollama 0.34.4 qwen3:8b 사본, 이번에 다시 읽지 않음).
- **초안.** `template/Modelfile.template.thinking.draft`.
  - think 미지정·켬: HF `enable_thinking=True`와 같다(` /think` 없음, system 앞 줄바꿈 없음).
  - think=false 명시: HF `enable_thinking=False`와 같다.
  - `.Thinking`·`.IsThinkSet`·`.Think`를 참조한다.
- **Python 옮김 비교**(`template_thinking_compare.py`): plan·재질의 × think 미지정·켬·끔, 6/6이 HF와 바이트 단위로 같다.
- **라이브러리 template(think 켬)과 HF(enable_thinking=True)의 차이:** 2 token. system 앞 줄바꿈 1과 마지막 user의 ` /think`다.
- **미검증(등록 없이는 확인할 수 없음):**
  1. think 미지정 요청이 thinking 켬으로 렌더링되는지.
  2. 응답에서 thinking과 본문이 분리되는지.
  3. Ollama가 이 template의 모델을 thinking 지원 모델로 인식하는지.
- **학습 렌더링 선택지(고르지 않음):**

| | HF 형식(현재 구현) | Ollama 기본 qwen3 template 형식(` /think`, system 앞 줄바꿈) |
|---|---|---|
| 학습·HF 평가 | 학습 렌더링 = HF-E 렌더링. 지금 데이터·테스트가 이 형식이다 | trainer가 Ollama 형식을 흉내 내야 한다(HF chat template과 달라짐). HF 평가도 같은 형식으로 바꿔야 한다 |
| Ollama 운영 | 등록 모델에 초안 TEMPLATE(HF와 같은 렌더링)이 필요하다. 라이브러리 qwen3:8b(E)와 렌더링이 다르다 | 라이브러리 template을 그대로 쓸 수 있다. 등록 모델과 E의 렌더링이 같다 |
| 확인할 것 | 초안 TEMPLATE의 실제 렌더링(미검증 3항목) | Ollama가 ` /think`를 붙이는 조건이 항상 같은지, HF 평가와의 차이 |

## 7. 데이터 규모(thinking 학습에 쓸 수 있는 것, 검토 전)

| 항목 | 값 |
|---|---|
| 질문(정답 표본이 있는 v003_t2pc train 질문) | 12/19 |
| SFT 후보 | 42(질문당 1–5) |
| DPO 후보 쌍 | 204(질문당 8–20; semantic 89, constraint 115; rejected가 조건 계층에서 고쳐지는 쌍 139) |
| validation | 없음(trace는 train split만 수집. checkpoint 선택용 validation 생성은 정답 JSON만 있으면 되므로 trace 없이 할 수 있다) |

## 8. pilot 평가 셀 제안과 남은 일

- **학습 효과.** HF-E(84) 대 같은 스크립트에 `--adapter`(같은 렌더링·생성 설정, 반복 측정이 바이트 단위로 같음).
  - checkpoint는 학습 쪽 validation split으로 고른다. 업체 100은 고른 뒤 한 번만 잰다.
- **운영 판단.** Ollama E(79) 대 등록 모델(thinking 초안 TEMPLATE, 같은 변환·양자화). 등록 승인과 Ollama GPU 상태 확인이 선행 조건이다.
- **pilot 전에 남은 일:**
  1. 사람 검토
     - batch004 검토 시트(기존).
     - thinking 표본 10개 읽기.
     - v003 표시 항목 처분.
     - 정답 표본이 없는 7문항의 처리(4절 선택지).
  2. 결정: SFT `thinking.loss_scope`, tokenization 불일치 처리(5절 a–c), 학습 렌더링 형식(6절).
  3. DPO 메모리 여유 대책 결정(5절). 지금 데이터로는 통과했다.
  4. validation split 정의(thinking 평가용 질문, v003_t2pc valid 16문항 사용 여부).
  5. Ollama 컨테이너 NVML 상태 확인(사용자), 그 뒤 등록 승인.

## 9. 산출물

| 경로 | 내용 |
|---|---|
| `hf_thinking.py`, `hf_eval_thinking.py`, `run_hf_e.sh`, `compare_hf_e.py`, `hf_e/` | HF-E 경로·결과·비교(원문은 ignored 경로에 두고 sha256만 남김) |
| `collect_traces.py`, `run_traces.sh`(멈춤), `run_traces_cuda3.sh`, `traces/`, `traces.log` | trace 수집과 요약·후보 목록·tokenization 확인 |
| `token_lengths_{sft,dpo}.json`, `memory_probe_thinking.py`, `memory/` | 길이·메모리 |
| `template_thinking_compare.py`, `template/` | thinking TEMPLATE 초안과 비교 |
| `gpu_uuid_check.txt`, `gpu_runs.log` | GPU 확인과 실행 순서 |
| `training/data/thinking.py`, `training/data/build_thinking.py`, `training/configs/qwen3_8b_t2pc_thinking_*.yaml`, `tests/test_training_thinking.py` | thinking 형식·builder·config·테스트 |

저장소 밖·ignored(커밋하지 않음): HF venv·model cache, `training/generated/thinking_prep_001/`(HF-E 원문), `training/generated/thinking_traces/`(trace 원문), `training/generated/thinking_v003_t2pc_train/`(thinking 학습 데이터), 측정용 임시 adapter(삭제).
