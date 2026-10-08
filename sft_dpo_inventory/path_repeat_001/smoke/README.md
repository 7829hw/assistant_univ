# smoke(분석에 쓰지 않음, PLAN.md 5절)

- 2026-10-08 23:33–23:48 KST(`../runs.log`의 시각은 UTC). 문항 001–003, r=1 seed(`--seed 20261010`),
  temperature 0.6·top_p 0.95·top_k 20. 경로마다 같은 명세로 두 번(a, b). 사이마다 셀 전환 확인(`*.pre.json`·`*.post.json`)을 했다.
- 업체 100 결과는 경로 진단 기록으로만 쓴다(결정 56). smoke 결과는 그 분석에도 쓰지 않는다.

| 경로 | a 대 b 출력 | 비고 |
|---|---|---|
| Ollama qwen3:8b (Q4_K_M), 0.40.1 | 3/3 문항에서 모든 호출의 content와 thinking 길이가 같음 | 첫 문항 동안 100% GPU, context_length 40960, size_vram 11,479,621,304(기존 E 기록과 같음) |
| HF Qwen3-8B (BF16) | 원문 파일(`training/generated/path_repeat_001/hf_sample_{a,b}_raw.jsonl`)이 바이트 단위로 같음 | |

- 호출 seed는 두 경로가 같은 규칙으로 같은 값을 받았다(001: 1892786392, 002: 2076952858, 003: 672670763). 이 smoke에는 repair 호출이 없었다.
- Ollama a의 001 생성 속도는 51 tok/s, b는 165 tok/s였다(002·003은 147–158). 출력은 같았다. 이 장비에서 모델을 처음 올린 run의
  첫 문항이라 생긴 준비 시간으로 보이나 확인하지 않았다.
