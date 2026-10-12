# calibration_001 계획 이탈 기록

## 1. Ollama-final 표본 3(s3)이 결정 55 guard로 멈춤 (2026-10-10)

- 경과(KST):
  - 13:15:50 `Ollama-final_s3` 시작(seed 20261103). precheck는 통과했다: 컨테이너가 GPU 2를 보고, 올라간 모델이 없고, 호스트 GPU 2가 비어 있었다.
  - 13:15:54 guard 확인: 100% GPU(`size_vram == size` = 11282027642).
  - 13:16:46 컨테이너 로그: `ggml-cuda.cu:109: CUDA error` / `CUDA error: unspecified launch failure`. llama-server가 abort(core dumped)로 끝났다.
  - 이후 다시 띄운 llama-server가 `ggml_cuda_init: failed to initialize CUDA: unknown error`로 CPU에서 돌았다.
  - 13:19:33 guard가 멈춤: `old44/g06#1` 10.2 tok/s < 30 tok/s(기준은 PLAN.md 7절).
- 그 뒤 상태(13:2x 확인):
  - 호스트 `nvidia-smi`: `Unable to determine the device handle for GPU2: 0000:AB:00.0: Unknown Error`. GPU 0·1·3은 보인다.
  - 컨테이너 안의 `nvidia-smi -L`도 같은 오류를 낸다. 컨테이너는 Up이다.
  - 호스트 GPU 장치 자체의 오류로 보인다. CLAUDE.md 4·13번에 따라 컨테이너와 GPU는 건드리지 않았다.
- 처리:
  - s3 출력(4문항 기록)은 `runs/ABORTED_gpu_Ollama-final_s3*`로 남겼다. 기준이나 판단에 쓰지 않는다.
  - s1·s2는 GPU에서 끝까지 돌았고 guard를 통과했다(`runs/Ollama-final_s{1,2}*`). PLAN.md 5절대로 그대로 쓴다.
  - 남은 측정: Ollama-final s3·s4, 셀 e s1–s4.
- 다시 재는 조건: 호스트에서 GPU 2가 복구되어야 한다(사람 조치). 복구 뒤 precheck가 통과하면 s3를 처음부터(같은 seed 20261103) 다시 재고, 그 사실을 여기에 덧붙인다.

## 2. 재개: 기본 GPU를 GPU 3으로(결정 68·69, 2026-10-12)

- 사람이 호스트와 컨테이너를 정리했다. 컨테이너는 2026-10-12 05:27:59Z(14:27 KST)에 다시 시작했고 `device_ids`는 "3"이다.
  컨테이너 안 `nvidia-smi -L`에는 GPU 3(`GPU-48f798cc…`)만 보인다.
- 확인한 것(`resume_check.txt`, `resume_precheck.json`):
  - host GPU 0–3이 모두 보인다(GPU 2도 복구됨). GPU 3에는 다른 사용자 프로세스가 없고 메모리는 2 MiB다.
  - Ollama 0.35.1. 측정 모델 digest는 그대로다: Ollama-최종 `c2d10cb2…`, e `b608abf0…`.
  - 결정 55 precheck는 기준 GPU 3에서 통과했다. 실행 의미 코드 지문은 `791c4a68…`이다.
- 측정 조건 중 바뀐 것:
  - 장치: GPU 2 → GPU 3(같은 RTX 6000 Ada).
  - NVIDIA 드라이버: 595.71.05 → 595.99.02(재부팅 때 바뀜).
  - 컨테이너 재시작(사람 조치).
  - 평가 harness의 Python 환경(scratchpad tokvenv)이 재부팅으로 지워져 같은 방법으로 다시 만들었다(requirements.txt
    + transformers 4.56.x + Jinja2 + numpy). 생성은 Ollama 서버가 하므로 이 환경은 요청과 채점에만 쓰인다.
  - 이 차이들이 생성 결과에 영향을 주는지는 아래 3절의 바이트 비교(결정 68)로 본다.
- 도구 변경(측정 의미는 같음):
  - `pilot_002/ollama_gpu_guard.py`: 기준 UUID를 GPU 3으로 바꾸고 `--gpu-uuid`를 더했다(예비 GPU 2로 잴 때).
    기록 키는 `container_sees_gpu`·`host_gpu`·`gpu_uuid`로 바뀐다. 1절까지의 기록은 옛 키(`…gpu2`) 그대로다.
  - `run_cal.sh`: `OLLAMA_GPU`(기본 3), 시작 표본 번호 인자, 결정 68 장치 확인 모드(`device`)를 더했다.

## 3. 장치 일치 확인(결정 68) — 결과: 모두 같음, s1·s2를 그대로 쓴다

- 2026-10-12 14:33–14:35 KST, GPU 3. Ollama-최종 s1의 앞 5문항(old44/g02, g03, g04, g06, g08)을 s1과 같은 seed 규칙
  (`S_1 = 20261101`, 호출 번호별 seed)으로 다시 생성했다(`repro/device_Ollama-final_g3*`). 결정 55 guard 통과(100% GPU, 최저 44.3 tok/s).
- GPU 2 기록(`Ollama-final_s1`)과 호출 단위로 thinking·content를 바이트 비교했다(`device_compare.py`, `repro/device_compare.json`).
  - 7/7 호출이 같다(첫 호출 5개, 재질의 2개). 호출별 seed와 eval_count도 같다.
- 결정 68에 따라 GPU 2의 s1·s2를 그대로 쓰고 s3·s4만 GPU 3에서 잰다. s3는 PLAN §5대로 같은 seed(20261103)로 처음부터 잰다.
  - 멈춘 s3의 원문(ignore 경로)은 `ABORTED_gpu_Ollama-final_s3_raw.jsonl`로 이름을 바꿔 둔다. 기록은 1절대로 `runs/ABORTED_gpu_*`에 있다.
- 한계: 5문항 7호출이 같다는 것은 장치·드라이버·컨테이너 재시작이 이 모델의 생성을 바꾸지 않았다는 강한 근거지만, 나머지 문항까지
  보장하지는 않는다(확인됨: 비교한 7호출, 가능성 있음: 나머지).
