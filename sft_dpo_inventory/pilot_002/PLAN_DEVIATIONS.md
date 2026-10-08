# pilot_002 PLAN 이탈 기록

`PLAN.md`는 고정본이라 고치지 않는다. PLAN 밖에서 더해진 실행 조건과 이탈을 여기에 적는다. 최종 정리는 REPORT에 옮긴다.

## 1. 결정 55의 Ollama GPU 확인 기준(측정 전에 정함, 2026-10-08)

- 모든 Ollama 셀(aux_test 기준 셀, 렌더링 확인, 업체 100·aux 평가 셀)에 `ollama_gpu_guard.py`를 붙인다.
  - 시작 전 `precheck`: `docker exec ollama nvidia-smi -L`에 GPU 2 UUID, 버전, 올라간 모델 없음, host GPU 2에 다른 프로세스 없음.
  - 측정 중 `watch`: 첫 문항 동안 `/api/ps`에서 `size_vram == size`(PROCESSOR 100% GPU), 문항마다 호출별 생성 속도.
- **기준값: 호출 하나라도 30 tok/s 미만이면 그 셀을 즉시 멈춘다.** 모든 모델에 같은 값을 쓴다.
  - 근거(`ollama_gpu_audit.md`): 같은 계열(qwen3:8b Q4_K_M) GPU 기록의 호출 속도 중앙값은 E 99.0, B-conv 103.3, pilot_001 학습 모델 97.5다.
    p05는 89.8 이상이고, 최소는 E의 첫 호출 38.3이다(첫 적재 직후).
  - CPU로 돈 기록(`aux_test/ABORTED_cpu_E`)은 4.3–7.2 tok/s다.
  - 30은 GPU 중앙값의 약 30%, GPU 최소값보다 낮고, CPU 최대값의 4배 이상이다.
  - pilot_002 학습 모델은 자기 GPU 기록이 없어 pilot_001 학습 모델(같은 base, 같은 변환) 기록을 "같은 모델의 GPU 기록"으로 본다.
- 평가 기록에는 `eval_duration`이 없어 속도를 `eval_count / (duration_ms − load_duration_ms)`로 잰다(prompt 처리 포함, 감사와 같음).
  평가 스크립트는 고치지 않는다.
- 렌더링 확인: pilot_001 `render_check.py`와 같은 확인을 하는 사본(`ollama/render_check.py`)을 쓴다.
  다른 것은 응답의 `eval_duration`·`total_duration`과 `eval_tok_s`를 행에 더 남기는 것뿐이다(판정 항목·문항·요청은 같다).

## 2. aux_test_v1 Ollama 기준 셀의 첫 측정

- 10:33 KST 시도는 컨테이너 CUDA 장애로 CPU에서 돌아 6문항 뒤 멈췄다(`aux_test/README.md`, `ABORTED_cpu_E.*`).
- 사용자가 컨테이너를 복구한 뒤, 같은 명령에 결정 55 확인을 붙여 E와 B-conv를 처음부터 잰다(`aux_test/run_baselines_d55.sh`).
  측정이 아니었던 CPU 출력을 대체하는 첫 측정이다. 재실행이 아니다.

## 3. merge 모델과 GGUF의 저장 위치

- PLAN 2절은 merge 모델·GGUF를 `/home/hwkim/sftdpo_work/pilot_002/`·`/home/hwkim/sftdpo_work/gguf/`에 둔다고 적었다.
- 등록 전에 확인한 루트 디스크(`/home`) 여유는 79 GB(2026-10-08 12:58)다. 필요한 양은 약 75 GB(merge 2×16 GB, GGUF bf16 2×16 GB + Q4_K_M 2×4.7 GB)라 모자랄 수 있다.
- 그래서 pilot_002의 merge 모델과 GGUF는 `/data/hwkim/sftdpo_work/pilot_002/merged/`·`/data/hwkim/sftdpo_work/gguf/`(여유 1.5 TB, 저장소 밖)에 둔다.
- adapter·checkpoint는 config 그대로 `/home/hwkim/sftdpo_work/pilot_002/`다. 변환 명령·양자화·등록 방식은 같다. 경로와 sha256만 기록한다.
