# 추론 표본 10개 검토 판정(결정 23)

- 대상: `thinking_prep_001/traces/summary.json`의 `human_review_sample_trace_ids(seed 7)` 10개.
- 검토 문서: `training/generated/thinking_traces/v003_t2pc_train/human_review_10.md`(ignored, sha256 `7dd14274…`).
  - 원본 trace: `traces.jsonl`, sha256 `23b9c8cd…`.
- 확정: 2026-10-06, 사용자가 Claude의 검토 의견을 확인하고 확정했다.
- 추론 원문은 이 문서에 옮기지 않는다.

## 판정 기준

- **우연히 정답**: 채점(`grounding_check`)이 보는 핵심 필드에서 추론이 틀렸는데 최종 JSON만 맞은 경우.
  - 핵심 필드: 측정값·사건, 집계 구조, 조건, 장소 값.
- **경미**: 채점이 보지 않는 필드(role, answer, source, id, text)의 오류.

## 판정표

| trace id | 판정 | 근거 |
|---|---|---|
| `ann-5229788ca1f31d50214f:sample:3` | 타당 | |
| `ann-5229788ca1f31d50214f:sample:7` | 타당(경미) | role 근거 없음 |
| `ann-b33f24e179cb6f5d84fd:sample:2` | 타당(경미) | source 근거가 틀림 |
| `ann-b33f24e179cb6f5d84fd:sample:5` | 타당 | |
| `ann-cc38d74754ba7eab68a8:greedy:0` | 타당(경미) | 추론은 answer=value라고 했으나 JSON에는 없음 |
| `ann-cc38d74754ba7eab68a8:sample:3` | 타당(경미) | 없는 가이드라인 예시를 지어냄 |
| `ann-d983889cf8c496178106:sample:7` | **우연히 정답** | bucket에서 rollup을 끌어내는 틀린 인과. role과 implicit 표시가 JSON과 어긋남 |
| `ann-da98b3941dfa1c7ce800:sample:1` | 타당(경미) | "나래구는 서울"이라고 지어냈다가 규칙으로 버림 |
| `ann-ea359d5569ef6070f9e4:sample:3` | **우연히 정답** | 추론은 region을 "하늘구"로 결론냈으나 JSON은 빈 값 |
| `ann-f78087861d0826ae8a7f:sample:6` | 타당 | |

집계: 타당 3, 타당(경미) 5, 우연히 정답 2.

## 관찰한 패턴

- 장소가 있는 8개 중 6개가 role COND를 쓴다(gold는 SUBCOND).
- 9개 중 7개가 gold에 없는 `answer: value`를 붙인다.
- 추론은 모두 영어다. 가끔 사실을 지어낸다.

## 이 판정으로 정한 것

- 결정 24: SFT loss 범위를 `json_only`로 바꾼다(결정 3 대체, SFT 한정).
- 결정 25: trace 선별 기준은 그대로 둔다.
- 결정 26: DPO는 `full_response`로 둔다.
- 결정 27: "우연히 정답" 2개 trace와, 그것이 chosen인 DPO 쌍을 학습에서 뺀다.
