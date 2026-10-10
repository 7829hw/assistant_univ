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
