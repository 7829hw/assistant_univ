# 기존 Ollama 기록의 GPU 실행 감사(결정 55)

작성: 2026-10-08. 모델을 부르지 않았다. 기록된 생성 속도만 봤다(`audit_ollama_gpu.py` → `ollama_gpu_audit.json`).

## 방법

- 평가 기록(`evaluate_vendor100.py`의 `*.jsonl`)에는 `eval_duration`이 없다. 그래서 호출마다 `eval_count / (duration_ms − load_duration_ms)`를 쓴다.
  분모에 prompt 처리(약 7k token)가 들어가 실제 생성 속도보다 조금 낮다.
- teacher 기록은 `eval_count / seconds`(호출 전체 시간, 모델 적재 포함)다.
- 비교용으로 CPU에서 돈 것이 확실한 `aux_test/ABORTED_cpu_E`도 같은 방식으로 셌다.
- 의심 기준: 셀 중앙값이 CPU 수준이거나, 호출 속도가 그 셀 중앙값의 절반 미만인 경우.

## 결과

| 셀(판정·기준에 쓰인 기록) | 호출 | 최소 | p05 | 중앙 | 최대 | 중앙값 절반 미만 |
|---|---:|---:|---:|---:|---:|---|
| 업체 100 E(qwen3:8b), `pilot_prep_003/ollama/E.jsonl` | 117 | 38.3 | 93.9 | 99.0 | 114.8 | 1(`001#0`) |
| 업체 100 B-conv, `pilot_prep_003/ollama/B-conv.jsonl` | 119 | 91.4 | 96.9 | 103.3 | 117.4 | 0 |
| 업체 100 pilot_001 Ollama-sft, `pilot_001/vendor100/Ollama-sft.jsonl` | 114 | 70.2 | 89.8 | 97.5 | 111.1 | 0 |
| 업체 100 pilot_001 Ollama-final, `pilot_001/vendor100/Ollama-final.jsonl` | 117 | 87.5 | 92.0 | 97.5 | 111.7 | 0 |
| valid98 B-conv(결정 43), `pilot_001_analysis/decision43/valid98_B-conv.jsonl` | 130 | 90.0 | 93.4 | 101.3 | 113.2 | 0 |
| valid98 pilot_001 Ollama-final(결정 43), `…/valid98_Ollama-final.jsonl` | 135 | 91.0 | 93.4 | 101.2 | 113.2 | 0 |
| teacher qwen3.8:27b batch004 | 48 | 53.4 | 87.3 | 93.2 | 108.0 | 0 |
| teacher known7 | 56 | 15.2 | 89.7 | 94.6 | 104.0 | 1(`ann-77e9dacb…:teacher:1`) |
| teacher v003_valid | 32 | 86.5 | 89.8 | 93.7 | 100.7 | 0 |
| teacher batch005_no_correct | 216 | 14.7 | 82.6 | 90.2 | 100.1 | 1(`b005-01:teacher:1`) |
| **참고: aux_test ABORTED_cpu_E(CPU 확정)** | 7 | 4.3 | 4.3 | 5.7 | 7.2 | – |

teacher 경로: `training/generated/thinking_traces/teacher_qwen3.8_27b/{batch004,known7,v003_valid,batch005_no_correct}/traces.jsonl`.

## 판단

- **의심 셀 없음.** 모든 셀의 중앙값이 90–103 tok/s다. CPU 실행(4–7 tok/s)과 열 배 넘게 차이 난다.
- 중앙값 절반 미만 호출 3개는 모두 그 실행의 **첫 호출**이다.
  - 업체 100 E `001#0`: 38.3 tok/s.
  - teacher known7 첫 trace: 15.2 tok/s.
  - teacher batch005 첫 trace: 14.7 tok/s.
  - teacher 기록의 `seconds`에는 모델 적재가 들어 있다. E 첫 호출에는 첫 적재 뒤 준비 시간이 들어 있는 것으로 보인다.
  - 세 값 모두 CPU 최대값(7.2)의 두 배 이상이다.
- 감사 범위 밖: pilot_prep_003·pilot_001의 렌더링 확인 기록에는 시간 필드가 없어 속도를 볼 수 없다. 이 기록들은 판정 셀이 아니다.
- 판정은 바꾸지 않는다.
