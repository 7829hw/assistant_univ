# teacher 표본 10개 검토 판정(결정 49)

- 대상: `pilot_prep_005/teacher/selected_teacher.json`의 `human_review_sample_trace_ids`(질문당 4개로 고른 teacher 68개에서 seed 48로 10개).
- 검토 문서: `training/generated/thinking_traces/teacher/human_review_teacher_10.md`(ignore 경로, sha256 `f50010f8dd1b8aa512859fb59b5c461135d029b9a1f712cd1656dee7bffc72b7`).
  - 원본 trace: `training/generated/thinking_traces/teacher_qwen3.8_27b/{batch004,known7,v003_valid}/traces.jsonl`(qwen3.8:27b, Ollama).
- 확정: 2026-10-08, 사용자가 Claude의 검토 의견을 확인하고 확정했다.
- 추론 원문은 이 문서에 옮기지 않는다.

## 판정 기준(결정 23과 같음)

- **우연히 정답**: 채점(`grounding_check`)이 보는 핵심 필드에서 추론이 틀렸는데 최종 JSON만 맞은 경우.
  - 핵심 필드: 측정값·사건, 집계 구조, 조건, 장소 값.
- **경미**: 채점이 보지 않는 필드(role, answer, source, id, text)의 오류, 또는 추론 안에서 근거를 들어 바로잡은 실수.

## 판정표

| 문서 번호 | trace id | 판정 | 근거 |
|---:|---|---|---|
| 1 | `ann-2d254560f2214204db4b:teacher:2` | 타당 | |
| 2 | `ann-2d254560f2214204db4b:teacher:6` | 타당 | |
| 3 | `ann-77e9dacb0b34a3273630:teacher:1` | 타당 | |
| 4 | `ann-914c48dad91bc9a62ab4:teacher:3` | 타당(경미) | region을 잘못 말했다가 추론 안에서 근거를 들어 고침. JSON에 `answer: value` |
| 5 | `ann-914c48dad91bc9a62ab4:teacher:8` | 타당 | |
| 6 | `ann-dd838f31807ef8546525:teacher:3` | 타당(경미) | 합계 집계를 넣을지 오래 망설인 끝에 맞는 근거로 넣지 않음 |
| 7 | `ann-e645cbc11600d7348d68:teacher:1` | 타당 | |
| 8 | `b004-06:teacher:4` | 타당 | |
| 9 | `b004-15:teacher:3` | 타당 | 판교역 표본 |
| 10 | `b004-31:teacher:1` | 타당 | |

집계: 타당 8, 타당(경미) 2, 우연히 정답 0.

## 관찰한 패턴

- 추론이 8b의 주요 오류 지점을 직접 짚는다: 질문에 없는 집계를 넣지 않는 이유, 묶음 기준을 장소로 만들지 않는 이유.
- 장소 role은 10개 모두 gold와 같은 SUBCOND다(결정 23 표본에서는 8b trace 8개 중 6개가 COND였다).

## 이 판정으로 정한 것

- 결정 27 방식으로 빠지는 trace가 없다. 결정 48로 고른 teacher 68개를 모두 쓴다.
