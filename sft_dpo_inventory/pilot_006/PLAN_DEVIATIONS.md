# pilot_006 계획 이탈·사전 기준 기록

## 1. 27b teacher 속도 guard 기준(결정 126 F5, G0 2026-10-16T01:18:15+09:00)

- Ollama 0.40.3, `qwen3.8:27b`(digest `aaee06c39dcf`), GPU `GPU-48f798cc-9437-50ac-d604-448bbad7b311`. 첫 호출 뒤 `size_vram == size`(100% GPU): True.
- 짧은 생성 5회 tok/s: 67.78, 66.5, 67.06, 67.09, 67.43 → 중앙값 67.09.
- **27b guard 기준 = 33.55 tok/s**(중앙값 × 0.5). T0과 세션 3 teacher 수집의 `ollama_gpu_guard.py watch --min-rate`에 쓴다.
- 결정 55의 나머지(컨테이너 GPU 확인, PROCESSOR 확인, 미달 시 즉시 멈춤과 `ABORTED_*`)는 그대로다. 기록: `pilot_006_prep/gpu/g0_speed.json`.

