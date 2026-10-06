# SFT pilot 전 준비: GPU 2 메모리, HF 평가 경로와 기준 셀, Ollama 평가 경로

작성: 2026-10-06. 브랜치 `geoflow/sft-dpo-t2pc`. pilot 학습, `ollama create`, Ollama 서버 설정 변경, prompt·SEMANTIC_CODE 변경은 없다.
실행 의미 코드 지문은 작업 시작과 끝 모두 `791c4a68…`이다. 업체 100 결과는 평가 전용이며 학습·checkpoint 선택·annotation에 쓰지 않는다.

## 0. 요약

- **GPU 2 메모리:** T2PC v003 config 그대로(한도 7552, DPO prompt 7424)에서 가장 긴 레코드로 3 step씩 돌렸다. 둘 다 통과했고 약 10GB가 남는다.
  - SFT: peak 35.9GB(nvidia-smi), 4.9초/step.
  - DPO: peak 37.4GB, 17.6초/step.
- **HF-F:** 업체 100 grounding_ok 54, 정상 54, U 3.
  - 두 번 잰 첫 응답이 100/100 바이트 단위로 같다.
  - Ollama F(57)와 같은 문항으로 비교하면 grounding_ok가 29문항에서 바뀐다(잃음 16, 얻음 13). 첫 응답이 같은 문항은 15개뿐이다.
- **template:** think off에서 생기는 4 token 차이의 위치를 찾았다.
  - Ollama qwen3:8b template은 system 앞에 줄바꿈을 하나 더 넣는다.
  - 마지막 user 턴 끝에 ` /no_think`를 붙인다.
  - think를 지정하지 않으면 Ollama는 think=true처럼 렌더링한다(` /think`).
  - HF와 같은 렌더링을 내도록 TEMPLATE 초안을 만들었다(미검증).
- **GGUF:** base를 Q4_K_M으로 변환했다(llama.cpp b11434). 등록 절차는 문서로만 남겼다.
- **제안:**
  - pilot의 학습 효과 비교는 HF 경로(HF-F 대 같은 경로의 학습 모델)로 한다.
  - 운영 경로(Ollama)의 결과는 HF 결과로 대신할 수 없다. Ollama 경로는 운영 조합 판단에 필요하다(5절).

## 1. GPU 확인

- **CLAUDE.md의 UUID 확인을 정해진 방법대로 끝내지 못했다.** Ollama 컨테이너 안의 `nvidia-smi -L`이 `Failed to initialize NVML: Unknown Error`로 실패했다(`gpu_uuid_check.txt`).
- **대신 읽기 전용 근거를 모았다.** 사용자가 이 근거로 GPU 2 작업을 진행하도록 승인했다.
  - 컨테이너 DeviceRequests `["3"]`, 컨테이너 안 장치는 `/dev/nvidia3`뿐이다.
  - Ollama의 마지막 모델 적재 로그의 장치는 PCI `0000:bd:00.0`(host GPU 3, `GPU-48f798cc`)이다.
  - torch `CUDA_VISIBLE_DEVICES=2`는 `GPU-a644de12`(PCI AB:00.0, host GPU 2)이고, 사용 중 메모리는 2MiB였다.
- **주의:** 컨테이너 안 NVML 실패는 Ollama가 지금 GPU를 쓰지 못한다는 뜻일 수 있다. 확인하지 않았다(모델 호출 없음). 다음 Ollama 측정 전에 확인해야 한다.

## 2. GPU 2 메모리 확인(`memory_probe.py`, 결과 `memory/`)

- **조건:**
  - config: `training/configs/qwen3_8b_t2pc_v003_{sft,dpo}.yaml` 그대로(BF16 LoRA r16, gradient checkpointing, batch 1, accumulation 1, SDPA).
  - 실행 때만 바꾼 것: 출력·profile 경로, max_steps 3, eval·save 끔, learning_rate 0. 학습이 일어나지 않게 하려는 것이며, AdamW 상태는 만들어진다.
  - 데이터: reviewed_gold_v003_t2pc에서 가장 긴 레코드(SFT·DPO 모두 ann-7fae41a3…, valid split. 메모리 측정용이며 split은 바꾸지 않았다).
  - DPO의 SFT adapter: 같은 측정의 LR0 SFT adapter.
  - 만든 adapter는 저장소 밖에 두었고, 측정 뒤 지웠다(`temporary_adapters_deleted: true`).

| 단계 | TRL 길이 | torch max allocated / reserved | nvidia-smi peak | step 시간(초) | 결과 |
|---|---|---|---|---|---|
| SFT | input 7518 | 30.72 / 34.57 GiB | 35,930 MiB | 5.15, 4.81, 4.85(평균 4.93) | PASS |
| DPO | prompt 7331, chosen 187, rejected 188 | 33.67 / 35.97 GiB | 37,360 MiB | 17.22, 17.57, 17.92(평균 17.57) | PASS |

- GPU 2 전체 메모리는 47.37GiB(49,140MiB)다. 현재 설정으로 충분하며, 설정을 바꿀 필요가 없었다.
- 참고(부족해질 경우의 선택지와 영향):
  - 길이를 줄이는 것은 prompt를 자르는 것이라 학습 입력이 운영 입력과 달라진다. 쓰지 않는다.
  - 4-bit(QLoRA)는 base 가중치 정밀도가 학습·평가와 달라진다.
  - DPO reference precompute는 메모리는 줄지만 시간이 는다(thor `reference.strategy`).
  - gradient checkpointing은 이미 켜져 있다.
- **pilot 시간 산수**(학습 효과 아님): 1 epoch, batch 1 기준.
  - v003_t2pc만: SFT train 19 step ≈ 1.6분, DPO 18 step ≈ 5.3분.
  - batch004 승인분 최대치를 더하면: SFT 33 step ≈ 2.7분, DPO 33 step ≈ 9.7분.
  - 평가 HF 업체 100 1셀 ≈ 12분.

## 3. HF 평가 경로와 HF-F 셀(`hf_eval_vendor100.py`, 결과 `hf/`)

- **경로.**
  - 공유하는 코드: `evaluate_vendor100`의 pipeline 구성(조건 계층, 재질의 정책, mock·legacy 실행, 기준일 고정)과 `run_item`·`score`·`grounding_check`·`_RecordingClient`·미처리 예외 기록을 import해 쓴다.
  - 바꾼 것: 모델 호출만 thor `HFClient`로 바꿨다. 응답에 token 수와 `done_reason`을 붙여 잘림 처리를 Ollama 경로와 같게 했다.
  - adapter: `--adapter`로 학습 모델을 base와 같은 방식으로 평가한다.
  - 결과 파일 형식은 `evaluate_vendor100.py llm`과 같다.
- **조건:** base Qwen/Qwen3-8B@b968826d, prompt 87048d0c, `enable_thinking=False`, greedy, max_new_tokens 1024, BF16·SDPA, 기준일 2026-09-25(Ollama F와 같음), GPU 2(peak 18.4GB). 문항 사이에 대화 상태는 없고, 모델은 프로세스 안에 올라와 있다.

| 셀 | grounding_ok | 정상 | U | 조용한 오답(U 아님) | 안전한 실패 | 첫 응답 raw 유효 / 일치 | + 조건 계층 일치 | 지연 중앙값 / p90 | 재질의 호출 |
|---|---:|---:|---:|---:|---:|---|---:|---|---:|
| Ollama F(qwen3:8b Q4_K_M, think=false) | 57 | 55 | 4(U2) | 2 | 39 | 77 / 24 | 49 | 7.3 / 8.2초 | 14 |
| HF-F 1회 | 54 | 54 | 3(U2) | 2 | 41 | 72 / 20 | 46 | 7.0 / 8.8초 | 12 |
| HF-F 2회 | 54 | 54 | 3(U2) | 2 | 41 | 72 / 20 | 46 | 6.9 / 8.8초 | 12 |

- **반복성:** 1회와 2회의 첫 계획 응답이 100/100 바이트 단위로 같다. grounding_ok와 분류도 모두 같다.
- **Ollama F → HF-F(같은 100문항):**

| grounding_ok 전이 | 문항 |
|---|---:|
| 일치 → 일치 | 41 |
| 일치 → 불일치 | 16 |
| 불일치 → 일치 | 13 |
| 불일치 → 불일치 | 30 |

- 보고 분류가 바뀐 문항은 33개다.
  - 정상 → 안전한 실패 15, 안전한 실패 → 정상 11, U → 정상 2, 조용한 오답 → 정상 2.
  - 안전한 실패 → U 1, 안전한 실패 → 조용한 오답 1, 정상 → 조용한 오답 1.
  - 문항 목록은 `hf/comparison.json`에 있다.
- **첫 응답 문자열이 같은 문항: 15/100.**
- **원인 후보**(정하지 않는다. 셋은 이 측정으로 나눌 수 없다):
  - 양자화(Ollama Q4_K_M 대 BF16).
  - chat template(Ollama의 system 앞 줄바꿈과 ` /no_think`, 4 token).
  - 생성 구현(llama.cpp 대 transformers greedy).
  - Ollama 쪽 Modelfile 기본값(top_k 20, top_p 0.95). harness는 temperature 0만 보낸다.
  - 총점(57 대 54)은 비슷하지만 문항 단위로는 크게 다르다. 한 경로의 결과를 다른 경로의 결과로 옮겨 말할 수 없다.

## 4. Ollama 평가 경로(등록하지 않음)

- **template 비교(`template_compare.py`, `template/`).**
  - Ollama qwen3:8b template(`/api/show`, Ollama 측정이 돌지 않을 때 읽음)을 이 프로젝트의 요청 형태로 Python에 옮겼다.
  - 옮긴 렌더링의 token 수가 기록된 `prompt_eval_count`와 같았다: F(think=false) 100/100, E(think 미지정)는 think=true로 렌더링했을 때 100/100.
  - **4 token 차이의 위치(think=false):**
    - `<|im_start|>system\n` 뒤에 `\n`이 하나 더 있다.
    - 마지막 user 내용 뒤에 ` /no_think`가 붙는다.
    - 생성 자리의 빈 think block(`<think>\n\n</think>\n\n`)은 HF와 같다.
    - 재질의 요청(이전 assistant 턴 포함)에서도 같은 두 곳만 다르다.
  - **think를 지정하지 않은 요청:** Ollama 0.34.4는 qwen3:8b에서 think=true처럼 렌더링한다(` /think`, 빈 think block 없음). 그래서 이전 기록의 "think auto" 셀은 thinking 켬 조건이다.
- **TEMPLATE 초안(`template/Modelfile.template.draft`).**
  - think 설정과 관계없이 HF `enable_thinking=False`와 같은 문자열을 내도록 썼다.
  - Python 옮김에서는 plan·재질의 두 형태 모두 HF와 바이트 단위로 같다.
  - **미검증:** 실제 Ollama 렌더링은 등록 뒤 `prompt_eval_count`로 확인해야 한다.
  - TEMPLATE에 thinking 관련 변수가 없어서 Ollama가 이 모델을 thinking 가능 모델로 보지 않을 수 있다. 그러면 `think=false` 요청이 거부될 수 있으므로 평가는 `--model-think auto`로 한다(미확인).
- **GGUF 변환(`gguf_convert.sh`, 영수증 `gguf/qwen3-8b-b968826d-base.receipt.json`).**
  - llama.cpp tag b11434, commit `5e03bdd8700948b9c41c54dd1b00f28a2aebc03f`, CPU 빌드.
  - 입력: base snapshot(파일 sha256은 영수증에 있다).
  - bf16 GGUF 16.39GB → Q4_K_M 5.03GB(`f060d7cbb5a2d45470b29af3df3d60662036f0fa97f851b63f7a55bb25935154`).
  - 결과는 `/home/hwkim/sftdpo_work/gguf/`(저장소 밖)에 있다.
  - 학습 모델은 merge 뒤 같은 스크립트로 변환한다.
  - 라이브러리 qwen3:8b(digest 500a1f06)와 같은 파일은 아니다. 변환 도구·시점이 다르다.
- **등록 절차:** `ollama/REGISTRATION.md`, `ollama/Modelfile.{base,trained}.draft`. 문서만 남겼고 실행하지 않았다.

## 5. pilot 평가 셀 제안

- **학습 효과 비교: HF 경로.**
  - 셀: HF-F(base, 54) 대 HF-SFT(같은 스크립트에 `--adapter`).
  - 근거:
    - 같은 조건에서 반복해도 바이트 단위로 같다(1회 측정으로 문항 단위 비교가 가능하다).
    - 학습 렌더링과 같은 template을 쓴다.
    - 양자화·변환·서버 상태가 끼지 않는다.
    - 공유 Ollama 서버를 건드리지 않는다.
  - checkpoint 선택은 학습 쪽 validation split으로 하고, 업체 100은 고른 뒤 한 번만 잰다.
- **운영 경로 확인: Ollama 경로가 필요하다.**
  - 근거: 운영 조합은 Ollama로 돈다. HF와 Ollama는 같은 base에서도 29문항의 grounding_ok가 다르다. HF 결과로 운영 결과를 말할 수 없다.
  - 승인되면 할 일(`ollama/REGISTRATION.md`):
    1. base 변환본을 초안 TEMPLATE으로 등록한다.
    2. `prompt_eval_count`가 HF token 수와 같은지 확인한다.
    3. base 변환본 셀(Ollama-F-conv)을 잰다.
    4. 학습 모델을 같은 변환·양자화·TEMPLATE으로 등록해 잰다.
  - 이 순서로 나눠 볼 수 있는 것:
    - 라이브러리 qwen3:8b 대 base 변환본: 변환·template 효과.
    - HF-F 대 base 변환본: 양자화·client 효과.
    - base 변환본 대 학습 변환본: 같은 운영 경로의 학습 효과.
- **Ollama F(57)는 참고 기준으로만 남긴다.** pilot 학습 모델과 같은 template·변환이 아니다.

## 6. 산출물

| 경로 | 내용 |
|---|---|
| `memory_probe.py`, `memory/` | 메모리 측정 스크립트와 결과(profile JSON, 로그) |
| `hf_eval_vendor100.py`, `hf/` | HF 평가 경로, HF-F 1·2회 결과, `comparison.json` |
| `compare_hf_f.py` | HF-F와 Ollama F 비교(baseline_conditions_001의 채점 함수 사용) |
| `template_compare.py`, `template/` | Ollama template 사본, 비교 결과, TEMPLATE 초안 |
| `gguf_convert.sh`, `gguf/` | 변환 스크립트와 영수증(GGUF는 저장소 밖) |
| `ollama/` | 등록 절차와 Modelfile 초안(미실행) |
| `run_gpu.sh`, `gpu_runs.log`, `gpu_uuid_check.txt` | GPU 작업 실행 명세·순서·확인 기록 |

저장소 밖(커밋하지 않음): `/home/hwkim/sftdpo_work/`의 HF venv·model cache, llama.cpp 빌드와 변환 venv, GGUF 두 개, 측정용 임시 adapter(삭제함).
