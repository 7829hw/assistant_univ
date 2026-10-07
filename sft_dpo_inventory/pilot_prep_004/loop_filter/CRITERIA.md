# 반복 루프 trace 제외 기준 (결정 40-D, 적용 전 고정)

작성·고정: 2026-10-07. 이 문서와 `distributions.json`을 커밋한 뒤 trace pool에 적용한다(`apply_filter.py`).
적용 결과를 보고 기준을 바꾸지 않는다.

## 1. 지표

`pilot_001_analysis/analyze.py`의 `loop_metrics`를 그대로 쓴다. 대상은 thinking 부분이다. `</think>` 앞, `<think>` 태그는 뺀다.

- **압축률 `zlib_ratio`:** zlib(level 9)로 압축한 크기를 원래 크기(UTF-8 바이트)로 나눈 값이다. 반복이 많을수록 낮다.
- **끝부분 반복 `tail_repeats`:** 끝에서 같은 덩어리(20–3999자)가 연속으로 몇 번 반복되는가. 3 이상을 처음 찾은 길이에서 멈춘다.
- **최다 반복 줄 `top_line_repeats`:** 20자 이상인 줄 가운데 가장 많이 나온 줄의 횟수.

## 2. 기준

trace 하나가 다음 중 하나라도 해당하면 루프 trace로 보고 학습 데이터에서 뺀다.
SFT target, DPO chosen, DPO rejected 어느 자리든 뺀다. 그 trace를 쓰는 DPO 쌍도 뺀다.

| 기준 | 값 | 근거(`distributions.json`) |
|---|---|---|
| L1 끝부분 반복 | `tail_repeats ≥ 3` | pilot_001 분석의 판정과 같다. valid98 생성 상한 호출 42개 중 40개, 정상 종료 호출 1,091개 중 0개 |
| L2 압축률 | `zlib_ratio ≤ 0.086` | valid98 생성 상한 호출의 최댓값(0.086)이다. 정상 종료 호출 최솟값은 0.092, 학습 trace 최솟값은 HF 0.142, teacher 0.365 |
| L3 같은 줄 반복 | `top_line_repeats ≥ 21` | valid98 정상 종료 호출의 최댓값(20)보다 크게 잡았다. 생성 상한 호출의 중앙값은 24, 학습 trace 최댓값은 HF 8, teacher 3 |

- 분포의 출처:
  - valid98 기록: base(`valid100_base_raw.jsonl`의 valid98 문항)와 pilot_001 checkpoint 8개의 HF 호출. 첫 계획과 재질의 모두다.
  - 학습 trace: `combined_traces.jsonl`(HF base 477)과 teacher 136.
  - 업체 100 기록은 쓰지 않았다(결정 36).
- 이 기준으로 valid98 생성 상한 호출 42개는 모두 루프로 걸린다(L2만으로도 42/42). 정상 종료 호출은 0/1,091이 걸린다.
- **L2·L3의 문턱값은 정상 종료 호출의 범위 밖에 두었다.** 길게 고민하다 끝난 thinking은 빼지 않는다.
  - 예: 24,770자, 압축률 0.092 같은 경우. 압축률 0.09–0.2인 긴 정상 종료 thinking이 valid98 checkpoint 기록에 24개 있다.
  - 이것을 뺄지는 "루프" 판정이 아니라 길이 판정이므로 이번 기준에 넣지 않았다.
- 학습 trace의 분포 요약은 이미 이 문서를 쓰기 전에 보았다. HF 최소 압축률 0.142, 최다 반복 줄 8, 끝부분 반복 0이다.
  - 그래서 적용 결과는 0개로 예상된다. 예상과 같아도 달라도 그대로 기록한다.

## 3. 적용 범위

- **trace pool:** v004 trace(`training/generated/pilot_prep_003/combined_traces.jsonl`, 477)와 teacher trace(`thinking_traces/teacher_qwen3.8_27b/*/traces.jsonl`, 136).
- 학습 데이터에서 실제로 쓰인 레코드(r1 SFT 124, DPO 212)에 대한 영향도 함께 센다.
- batch005 승인 뒤 수집할 trace에도 같은 기준을 그대로 적용한다.
