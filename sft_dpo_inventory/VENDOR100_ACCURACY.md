# 업체 100 정답률 정리

업체가 준 질문 100개(업체 100)에서, GeoFlow가 질문을 얼마나 맞게 처리했는지 한곳에 모은 문서입니다.
새로 잰 값은 없습니다. 모든 숫자는 아래 표의 "원본 기록 경로" 파일에서 다시 세었습니다.
- 다시 센 스크립트: `pilot_001_analysis/accuracy/collect.py`
- 결과: `pilot_001_analysis/accuracy/accuracy.json`

(경로는 따로 적지 않으면 `sft_dpo_inventory/` 기준입니다.)

## 이 문서에서 쓰는 말

- **grounding_ok(주 지표):** 모델이 질문을 정답과 같은 뜻의 구조(장소, 시간, 조건, 무엇을 셀지)로 옮겼는지를 셉니다.
  PROTOCOL(`vendor100_protocol/PROTOCOL.md`)이 판정에 쓰는 주 지표입니다.
- **정상:** 최종 분류가 "정상 답변"인 문항 수입니다.
  - 마지막 분석 도구와 그 인자가 정답과 같고, 답변에 값이 들어 있으면 "정상 답변"입니다.
  - 질문을 옮긴 구조가 정답과 조금 달라도 결과 도구 호출이 같으면 정상일 수 있습니다. 그래서 grounding_ok와 숫자가 다를 수 있습니다.
- **U(용납할 수 없는 실패):** 틀린 답을 그럴듯하게 낸 경우 가운데 위험한 네 종류입니다.
  - 요구 조건을 버리고 답함
  - 잘못된 범위(scope)
  - 잘못된 측정 대상
  - 없는 조건을 넣거나 값을 바꿈
- **조용한 오답:** 답은 냈지만 틀렸고, U에는 들지 않는 경우입니다.
- **지연 중앙값:** 한 문항을 처리하는 데 걸린 시간의 중앙값(초)입니다.
  - HF는 연구용 실행 경로라 운영 경로(Ollama)와 속도를 비교할 수 없습니다. 같은 경로끼리만 비교합니다.
- **실행 경로:**
  - HF: 연구용 경로. 원본 가중치(BF16)를 transformers로 직접 돌립니다.
  - Ollama: 운영 경로. 4bit로 줄인 모델(Q4_K_M)을 Ollama 서버로 돌립니다.
- **코드 지문:** 실행 의미 코드(geoflow, prompt 등)의 내용 지문입니다. 같은 지문이면 같은 코드로 채점·실행한 것입니다.
- 모든 셀의 공통 조건: prompt `87048d0c`, 기준일 2026-09-25, 조건 계층 켬, mock provider.

## 표 1. 파인튜닝 전(qwen3:8b base, thinking 켬, prompt 87048d0c)

| 셀 | grounding_ok | 정상 | U | 조용한 오답 | 지연 중앙값(초) | 실행 경로 | 장치 | 양자화 | 코드 지문 | Ollama 버전 | 측정일 | 원본 기록 경로 |
|---|---:|---:|---:|---:|---:|---|---|---|---|---|---|---|
| HF-E | 84 | 91 | 2 | 0 | 22.0 | HF(Qwen3-8B@b968826d, `enable_thinking=True`, greedy, 생성 상한 8192) | GPU 2 | 없음(BF16) | 791c4a68 | 해당 없음 | 2026-10-06 | `thinking_prep_001/hf_e/HF-E_run1.json` |
| E | 79 | 84 | 3 | 1 | 10.9 | Ollama 공식 `qwen3:8b`(digest 500a1f06), think 미지정 | GPU 3 | Q4_K_M | 791c4a68 | 0.35.1 | 2026-10-06 | `pilot_prep_003/ollama/E.json` |
| B-conv | 77 | 79 | 6 | 0 | 10.4 | Ollama, 직접 변환한 base(`geoflow-qwen3-8b-b968826d-base:q4km-hfthink`, ab29de19), think 미지정 | GPU 3 | Q4_K_M | 791c4a68 | 0.35.1 | 2026-10-06 | `pilot_prep_003/ollama/B-conv.json` |

장치 근거:
- HF-E: 결과 파일의 `meta.hf.device_uuid`(GPU-a644de12, host GPU 2)입니다.
- E·B-conv: 결과 파일에는 장치가 적혀 있지 않습니다. 당시 Ollama 컨테이너는 GPU 3에 배정돼 있었습니다(`pilot_001/ollama/container/compose.before.yaml`, `pilot_prep_003/gpu_runs.log`).

## 표 2. 파인튜닝 후(pilot_001)

| 셀 | grounding_ok | 정상 | U | 조용한 오답 | 지연 중앙값(초) | 실행 경로 | 장치 | 양자화 | 코드 지문 | Ollama 버전 | 측정일 | 원본 기록 경로 |
|---|---:|---:|---:|---:|---:|---|---|---|---|---|---|---|
| HF-SFT | 82 | 87 | 2 | 1 | 34.2 | HF, base + SFT adapter(checkpoint-124), 조건은 HF-E와 같음 | GPU 2 | 없음(BF16) | 791c4a68 | 해당 없음 | 2026-10-07 | `pilot_001/vendor100/HF-sft.json` |
| HF-최종 | 86 | 90 | 4 | 0 | 28.4 | HF, base + SFT+DPO adapter(checkpoint-212), 조건은 HF-E와 같음 | GPU 2 | 없음(BF16) | 791c4a68 | 해당 없음 | 2026-10-07 | `pilot_001/vendor100/HF-final.json` |
| Ollama-SFT | 80 | 82 | 6 | 3 | 12.6 | Ollama `geoflow-qwen3-8b-pilot001-sft:q4km-hfthink`(b4b4777c), think 미지정 | GPU 2 | Q4_K_M | 791c4a68 | 0.35.1 | 2026-10-07 | `pilot_001/vendor100/Ollama-sft.json` |
| Ollama-최종 | 77 | 81 | 2 | 2 | 12.2 | Ollama `geoflow-qwen3-8b-pilot001-final:q4km-hfthink`(c6ce2746), think 미지정 | GPU 2 | Q4_K_M | 791c4a68 | 0.35.1 | 2026-10-07 | `pilot_001/vendor100/Ollama-final.json` |

장치 근거:
- HF 셀: 결과 파일의 `meta.hf.device_uuid`입니다.
- Ollama 셀: 결정 32에 따라 컨테이너를 GPU 2로 옮긴 뒤 쟀습니다(`pilot_001/runs.log`의 측정 직전 확인 줄, `pilot_001/ollama/container/`).

## 표 3. 전후 비교(같은 경로끼리)

판정과 숫자는 `pilot_001/vendor100/judgment.json`(PROTOCOL 판정)을 그대로 옮겼습니다.
- b: 기준에서 틀렸다가 학습 모델에서 맞힌 문항 수입니다.
- c: 기준에서 맞혔다가 학습 모델에서 틀린 문항 수입니다.

| 비교 | grounding_ok | 차이 | b / c | McNemar p | U(전→후, 새로 생긴 문항) | 조용한 오답(전→후, 새로 생긴 문항) | PROTOCOL 판정 | 악화 사유 |
|---|---|---:|---|---:|---|---|---|---|
| HF 주: HF-E → HF-최종 | 84 → 86 | +2 | 9 / 7 | 0.80 | 2 → 4 (016, 030, 044, 054) | 0 → 0 | 악화 | U 순증 2 |
| HF 참고: HF-E → HF-SFT | 84 → 82 | −2 | 6 / 8 | 0.79 | 2 → 2 (037) | 0 → 1 (077) | 악화 | 조용한 오답 순증 1 |
| 운영 주: E → Ollama-최종 | 79 → 77 | −2 | 8 / 10 | 0.81 | 3 → 2 (040) | 1 → 2 (077, 100) | 악화 | 조용한 오답 순증 1 |
| 운영 참고: E → Ollama-SFT | 79 → 80 | +1 | 10 / 9 | 1.00 | 3 → 6 (026, 044, 059, 093) | 1 → 3 (077, 100) | 악화 | U 순증 3, 조용한 오답 순증 2 |

꼭 같이 읽어야 할 점:
- **grounding_ok 차이는 네 비교 모두 유의하지 않았습니다(p 0.79–1.00).** 100문항에서 ±2문항은 우연과 구분되지 않는 크기입니다.
- **"악화" 판정은 PROTOCOL의 U·조용한 오답 순증 규칙 때문입니다.** PROTOCOL은 정답 수가 같아도 U나 조용한 오답이 하나라도 늘면 악화로 봅니다.
  정답률이 크게 떨어졌다는 뜻이 아닙니다.
- **운영 경로는 기준과 학습 모델의 장치가 다릅니다.**
  - 기준 셀(E, B-conv)은 GPU 3에서 잰 기록을 결정 32-1에 따라 다시 썼습니다.
  - 학습 모델 셀은 GPU 2에서 쟀습니다.
  - 두 GPU는 같은 사양이지만, 이 차이가 결과에 영향을 줬는지는 "장치 확인" 절에서 따로 확인합니다.
- 지연은 운영 셀에서 E 대비 1.12배(최종), 1.15배(SFT)로, 악화 기준(1.5배) 아래입니다.
- 각 셀은 한 번씩만 쟀습니다.

## 참고: 같은 업체 100에서 잰 다른 기준값

조건이 위 표와 다르므로 **직접 비교할 수 없는 값**입니다. 차이를 함께 적습니다.

| 셀 | grounding_ok | 정상 | U | 조용한 오답 | 지연 중앙값(초) | 모델·경로 | 코드 | Ollama | 측정일 | 직접 비교 | 원본 기록 경로 |
|---|---:|---:|---:|---:|---:|---|---|---|---|---|---|
| 현재 운영 기본값 T2PC | 96 | 98 | 0 | 0 | 19.8 | Ollama `qwen3.8:27b`(digest aaee06c3, Q4_K_M), think 미지정 | commit 2f53c72(파일에 지문 기록 없음, 주 1) | 0.34.4 | 2026-10-04 | 불가: 모델이 다름(27b), Ollama 버전 다름. 장치는 기록 없음 | `evaluation/grounding_v11/runs/full/t2pc/dev.json` |
| E(이전 버전) | 79 | 84 | 3 | 1 | 11.9 | 표 1의 E와 같은 모델, think 미지정 | 지문 97efa866(주 1) | 0.34.4 | 2026-10-06 | 참고만: Ollama 버전과 코드 지문이 다름 | `baseline_conditions_001/runs/E.json` |
| HF-E 2회차 | 84 | 91 | 2 | 0 | 22.0 | 표 1의 HF-E와 같은 조건, 반복 측정 | 791c4a68 | 해당 없음 | 2026-10-06 | 같은 조건(반복) | `thinking_prep_001/hf_e/HF-E_run2.json` |
| F(thinking 끔) | 57 | 55 | 4 | 2 | 7.3 | Ollama `qwen3:8b`, `think=false` | 지문 97efa866(주 1) | 0.34.4 | 2026-10-05 | 불가: thinking 끔, Ollama 버전 다름 | `baseline_conditions_001/runs/F.json` |
| HF-F 1회차(thinking 끔) | 54 | 54 | 3 | 2 | 7.0 | HF BF16, `enable_thinking=False`, 생성 상한 1024 | 791c4a68 | 해당 없음 | 2026-10-06 | 불가: thinking 끔, 생성 상한 다름 | `pilot_prep_001/hf/HF-F_run1.json` |
| HF-F 2회차(thinking 끔) | 54 | 54 | 3 | 2 | 6.9 | 같음(반복) | 791c4a68 | 해당 없음 | 2026-10-06 | 불가(위와 같음) | `pilot_prep_001/hf/HF-F_run2.json` |

- 주 1: 실행 의미 코드 지문이 `97efa866…` → `791c4a68…`로 바뀐 뒤, 운영 기본값 T2PC·E·F 기록을 새 코드로 다시 적용했습니다. 분류와 grounding_ok가 모두 같았습니다(`evaluation/fix_condition_hoist/rerun_verification.json`). 다만 모델을 다시 부른 측정은 아닙니다.
- 장치:
  - F, E(이전 버전): 당시 Ollama 컨테이너는 GPU 3이었습니다(`pilot_prep_001/REPORT.md` 1절). 결과 파일에는 장치가 적혀 있지 않습니다.
  - 운영 기본값: 장치는 기록 없음입니다.
  - HF-F: 결과 파일의 `meta.hf.device_uuid`로 GPU 2입니다.
- 위 값들은 기록대로 옮겼고 다시 재지 않았습니다.

## 장치 확인(결정 37, 2026-10-07, 보조 기록)

위 표의 기준 셀(E, B-conv)은 GPU 3에서, 학습 모델 셀은 GPU 2에서 쟀습니다. 장치 차이가 결과에 영향을 줬는지 보려고 E와 B-conv를 GPU 2에서 한 번씩 다시 쟀습니다.
- 위 표의 값은 고치지 않았습니다. PROTOCOL 판정도 그대로입니다.
- 조건은 PROTOCOL과 같습니다: Ollama 0.35.1, Q4_K_M, think 미지정, num_predict 미지정, 문항마다 모델 내림. HF 측정은 동시에 돌리지 않았습니다.
- 측정 직전 확인 결과:
  - Ollama 버전은 0.35.1이었습니다.
  - GPU 2(`GPU-a644de12…`)의 사용 메모리는 2MiB였고 다른 프로세스는 없었습니다.
  - 올라간 Ollama 모델도 없었습니다.

| 셀 | 첫 응답 바이트 일치 | 모든 모델 호출 일치 | grounding_ok(GPU 3 → GPU 2) | 분류 일치 | U | 조용한 오답 | 지연 중앙값(초) |
|---|---|---|---|---|---|---|---|
| E | 100 / 100 | 100 / 100 | 79 → 79 | 100 / 100 | 3 → 3 | 1 → 1 | 10.9 → 11.8 |
| B-conv | 100 / 100 | 100 / 100 | 77 → 77 | 100 / 100 | 6 → 6 | 0 → 0 | 10.4 → 11.7 |

- **첫 응답이 모두 같았습니다.** 이번 비교에서 장치 차이는 정답률·분류·U·조용한 오답 차이의 원인이 아니었습니다. 그래서 같은 장치 기준으로 판정이나 삼자 비교를 다시 계산하지 않았습니다(다시 계산해도 값이 같습니다).
- **지연만 달랐습니다.** GPU 2가 8–12% 느렸습니다.
  - 같은 장치(GPU 2)의 E와 비교하면, 학습 모델의 지연 비율은 최종 1.03배, SFT 1.06배입니다(표 3에서는 1.12배, 1.15배).
  - 어느 쪽이든 악화 기준(1.5배) 아래입니다. 판정은 바꾸지 않습니다.
- 출처: `pilot_001_analysis/device_check/`
  - 측정 결과: `E.json`, `B-conv.json`
  - 비교: `comparison.json`, `compare.py`
  - 실행 기록: `runs.log`

## pilot_002(2026-10-09 추가)

위 표 1–3과 참고 표는 고치지 않았습니다. 이 절의 숫자는 pilot_002 판정 스크립트가 원본 기록에서 다시 센 값입니다.
- 업체 100: `pilot_002/vendor100/judge.py` → `pilot_002/vendor100/judgment.json`(PROTOCOL_v2 판정).
- aux_test_v1: `pilot_002/aux_test/compare_aux.py` → `pilot_002/aux_test/comparison.json`(보고만).
- 보고서: `pilot_002/REPORT.md`.

공통 조건은 위와 같습니다(prompt `87048d0c`, 기준일 2026-09-25, 조건 계층 켬, mock provider, 코드 지문 791c4a68, Ollama 0.35.1).
- HF 셀: Qwen3-8B@b968826d BF16, `enable_thinking=True`, greedy, 생성 상한 8192.
- Ollama 셀: Q4_K_M, think 미지정, num_predict 미지정, 문항마다 모델 내림.
- pilot_002 Ollama 셀은 GPU 2에서 쟀고, 결정 55의 GPU 확인(100% GPU, 호출 30 tok/s 이상)을 통과했습니다.

### 표 4. 업체 100: 파인튜닝 전후(pilot_001, pilot_002)

| 셀 | grounding_ok | 정상 | U | 조용한 오답 | 지연 중앙값(초) | 장치 | 원본 기록 경로 |
|---|---:|---:|---:|---:|---:|---|---|
| HF-E(전) | 84 | 91 | 2 | 0 | 22.0 | GPU 2 | `thinking_prep_001/hf_e/HF-E_run1.json` |
| E(전) | 79 | 84 | 3 | 1 | 10.9 | GPU 3 | `pilot_prep_003/ollama/E.json` |
| B-conv(전) | 77 | 79 | 6 | 0 | 10.4 | GPU 3 | `pilot_prep_003/ollama/B-conv.json` |
| pilot_001 HF-SFT | 82 | 87 | 2 | 1 | 34.2 | GPU 2 | `pilot_001/vendor100/HF-sft.json` |
| pilot_001 HF-최종 | 86 | 90 | 4 | 0 | 28.4 | GPU 2 | `pilot_001/vendor100/HF-final.json` |
| pilot_001 Ollama-SFT | 80 | 82 | 6 | 3 | 12.6 | GPU 2 | `pilot_001/vendor100/Ollama-sft.json` |
| pilot_001 Ollama-최종 | 77 | 81 | 2 | 2 | 12.2 | GPU 2 | `pilot_001/vendor100/Ollama-final.json` |
| pilot_002 HF-SFT | 85 | 91 | 1 | 0 | 27.0 | GPU 3 | `pilot_002/vendor100/HF-sft.json` |
| pilot_002 HF-최종 | 88 | 87 | 1 | 0 | 25.1 | GPU 3 | `pilot_002/vendor100/HF-final.json` |
| pilot_002 Ollama-SFT | 77 | 80 | 7 | 2 | 11.2 | GPU 2 | `pilot_002/vendor100/Ollama-sft.json` |
| pilot_002 Ollama-최종 | 86 | 86 | 9 | 1 | 11.2 | GPU 2 | `pilot_002/vendor100/Ollama-final.json` |

- pilot_001 행은 표 2의 값을 그대로 옮겼습니다.
- pilot_002 모델:
  - SFT: base + SFT adapter(checkpoint-380). Ollama 이름은 `geoflow-qwen3-8b-pilot002-sft:q4km-hfthink`(1a813e0a)입니다.
  - 최종: base + SFT+DPO adapter(checkpoint-144). Ollama 이름은 `geoflow-qwen3-8b-pilot002-final:q4km-hfthink`(c2d10cb2)입니다.
- 장치: HF는 결과 파일의 `meta.hf.device_uuid`입니다. Ollama는 `pilot_002/{vendor100,aux_test}/gpu_guard_*.json`과 `pilot_002/runs.log`입니다.
  - HF-E(GPU 2)와 pilot_002 HF 셀(GPU 3)은 장치가 다릅니다.
  - HF 경로의 GPU 2·3 출력 일치는 확인되지 않았습니다(`pilot_001_analysis/REPORT.md` e절).

### 표 5. 업체 100: pilot_002 전후 비교(PROTOCOL_v2)

판정과 숫자는 `pilot_002/vendor100/judgment.json`을 그대로 옮겼습니다.
PROTOCOL_v2는 U·조용한 오답 순증 3 이상을 악화로 봅니다. pilot_001의 PROTOCOL은 1 이상이었으므로 표 3의 판정과 문구를 비교하지 않습니다.

| 비교 | grounding_ok | 차이 | b / c | McNemar p | U(전→후, 새로 생긴 문항) | 조용한 오답(전→후, 새로 생긴 문항) | PROTOCOL_v2 판정 | 악화 사유 |
|---|---|---:|---|---:|---|---|---|---|
| HF 주: HF-E → HF-최종 | 84 → 88 | +4 | 9 / 5 | 0.42 | 2 → 1(없음) | 0 → 0 | 차이 없음 | – |
| HF 참고: HF-E → HF-SFT | 84 → 85 | +1 | 7 / 6 | 1.00 | 2 → 1(054) | 0 → 0 | 차이 없음 | – |
| 운영 주: E → Ollama-최종 | 79 → 86 | +7 | 12 / 5 | 0.14 | 3 → 9(016, 026, 037, 040, 041, 074, 093) | 1 → 1(100) | 악화 | U 순증 6 |
| 운영 참고: E → Ollama-SFT | 79 → 77 | −2 | 7 / 9 | 0.80 | 3 → 7(026, 037, 040, 041, 044, 085) | 1 → 2(030, 100) | 악화 | U 순증 4 |

- grounding_ok 차이는 네 비교 모두 유의하지 않았습니다(p 0.14–1.00).
- 운영 경로의 "악화"는 U 순증 규칙 때문입니다. 운영 최종 셀은 grounding_ok가 7 늘었지만, 안전한 실패가 12 → 4로 줄고 U가 3 → 9로 늘었습니다.
- 지연은 운영 셀에서 E 대비 1.03배(SFT·최종)로, 악화 기준(1.5배) 아래입니다.
- 각 셀은 한 번씩만 쟀습니다.

### 표 6. 보조 시험 셋 aux_test_v1(51문항, 보고만)

| 셀 | grounding_ok | 정상 | U | 조용한 오답 | 지연 중앙값(초) | 장치 | 원본 기록 경로 |
|---|---:|---:|---:|---:|---:|---|---|
| HF-E(전) | 27 | – | – | – | 21.9 | GPU 2 | `pilot_prep_005/sets/runs/aux_test_base.json` |
| E(전) | 29 | 32 | 3 | 5 | 13.5 | GPU 2 | `pilot_002/aux_test/E.json` |
| B-conv(전) | 24 | 27 | 3 | 8 | 11.6 | GPU 2 | `pilot_002/aux_test/B-conv.json` |
| pilot_002 HF-SFT | 33 | – | – | – | 30.8 | GPU 3 | `pilot_002/aux_test/HF-sft.json` |
| pilot_002 HF-최종 | 30 | – | – | – | 29.3 | GPU 3 | `pilot_002/aux_test/HF-final.json` |
| pilot_002 Ollama-SFT | 32 | 32 | 6 | 3 | 12.0 | GPU 2 | `pilot_002/aux_test/Ollama-sft.json` |
| pilot_002 Ollama-최종 | 29 | 31 | 4 | 5 | 11.0 | GPU 2 | `pilot_002/aux_test/Ollama-final.json` |

- aux_test_v1은 pilot_002 때 만든 셋이라 pilot_001 행이 없습니다.
- HF 셀은 `pilot_prep_005/sets/eval_set.py` 출력입니다. 호출·최종 답 기록이 없어 정상·U·조용한 오답을 셀 수 없습니다(–).
- 비교(보고만):

| 비교 | grounding_ok | b / c | p | U | 조용한 오답 |
|---|---|---|---:|---|---|
| HF-E → HF-최종 | 27 → 30 | 7 / 4 | 0.55 | – | – |
| HF-E → HF-SFT | 27 → 33 | 10 / 4 | 0.18 | – | – |
| E → Ollama-최종 | 29 → 29 | 9 / 9 | 1.00 | 3 → 4 | 5 → 5 |
| E → Ollama-SFT | 29 → 32 | 10 / 7 | 0.63 | 3 → 6 | 5 → 3 |
