# aux_test_v1 Ollama 기준 셀(PROTOCOL_v2 2.2) — 중단

- `build_aux_yaml.py` → `aux_test_gold.yaml`: aux_test_v1(51문항)을 `evaluate_vendor100.py --gold`가 읽는 한 파일로 모았다.
  문항·라벨은 원본 그대로이고, 순서는 HF 기준값 기록과 같다.
- `run_baselines.sh`: E(`qwen3:8b`), B-conv(`geoflow-qwen3-8b-b968826d-base:q4km-hfthink`)를 업체 100과 같은 명령으로 잰다.

## 2026-10-08 중단(기반 장애)

- 10:33 KST에 E를 시작했다. 사전 확인: Ollama 0.35.1, 올라간 모델 없음, GPU 2에 다른 프로세스 없음.
- 첫 문항부터 Ollama 컨테이너가 CUDA를 쓰지 못했다.
  - `docker exec ollama nvidia-smi -L` → `Failed to initialize NVML: Unknown Error`.
  - 컨테이너 로그: `ggml_cuda_init: failed to initialize CUDA: no CUDA-capable device is detected`(첫 기록 2026-10-08T01:33Z).
  - llama-server가 CPU로 돌았다. 호출당 110–240초, 약 5 token/s였고, host GPU 2 메모리 사용은 2 MiB였다.
- PROTOCOL 실행 조건(GPU의 Q4_K_M 모델)이 아니므로 6문항 뒤 10:51에 측정을 멈췄다. B-conv는 시작하지 않았다.
- 부분 출력은 `ABORTED_cpu_E.*`로 이름을 바꿔 남겼다. 기준값으로 쓰지 않는다.
- 같은 컨테이너의 teacher 수집(2026-10-08 05:08–05:46 KST)은 GPU에서 돌았다. 로그에 CUDA 실패가 없고, 질문당 시간도 이전과 같다.
- 컨테이너는 재시작하지 않았다(CLAUDE.md 4번). 복구는 사용자가 정한다.

## 2026-10-08 첫 측정(컨테이너 복구 뒤, 결정 55)

- 사용자가 컨테이너를 복구했다. `docker exec ollama nvidia-smi -L`에 GPU 2(`GPU-a644de12…`)가 보이고, 버전은 0.35.1이다.
- `run_baselines_d55.sh`로 E와 B-conv를 처음부터 쟀다. 명령은 `run_baselines.sh`와 같고 결정 55 확인만 붙였다.
  위의 CPU 출력은 측정이 아니었으므로 이것이 이 셋의 첫 측정이다(`../PLAN_DEVIATIONS.md` 2번).

| 셀 | 모델 | 시간(KST) | grounding_ok | U | 조용한 오답 | 지연 중앙(초) | 결정 55 확인 |
|---|---|---|---:|---:|---:|---:|---|
| E | `qwen3:8b` | 12:53–13:10 | 29/51 | 3 | 5 | 13.5 | 첫 문항 100% GPU, 호출 62개 최저 89.0 tok/s |
| B-conv | `geoflow-qwen3-8b-b968826d-base:q4km-hfthink` | 13:15–13:36 | 24/51 | 3 | 8 | 11.56 | 첫 문항 100% GPU, 호출 63개 최저 89.5 tok/s |

- 출처: `E.json`·`B-conv.json`(원문 `*.jsonl`), 확인 기록 `gpu_precheck_*.json`·`gpu_guard_*.json`, 비교 `comparison.json`(`compare_aux.py`).
- 같은 셋의 HF-E(base)는 27/51이다(`../../pilot_prep_005/sets/runs/aux_test_base.json`). HF 셀은 `eval_set.py` 형식이라 U·조용한 오답을 셀 수 없다.
- 이 셋은 보고용이고 판정에 쓰지 않는다(PROTOCOL_v2 2.2절).
