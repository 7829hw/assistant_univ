# pilot_004 준비(학습 없음)

작성: 2026-10-14. 결정 86(AA)·88(AC). 학습하지 않았고 최종 데이터도 만들지 않았다. 지문 `791c4a68`은 그대로다
(`training/`은 `SEMANTIC_CODE` 밖).

## 1. 출처별 SFT 손실 범위(결정 86)

- 구현: `training/data/thinking.py`
  - `thinking.loss_scope: by_source`(SFT 전용)를 새로 받는다. 기존 `full_response`·`json_only` config의 동작은 그대로다.
  - `SOURCE_LOSS_SCOPES = {teacher: full_response, hf: json_only}`. 출처는 `metadata.source == "teacher"`이면 teacher, 아니면 HF 자체 trace다.
  - data builder는 `assign_loss_scope(record)`로 `metadata.loss_scope`를 적는다. 렌더링(`sft_loss_scope`)은 표시가 없거나 출처와 다르면 멈춘다.
  - DPO는 `full_response`만 받는다(결정 26 그대로). `by_source`를 DPO에 주면 멈춘다.
- 시험: `tests/test_thinking_loss_by_source.py`(9개)
  - teacher 레코드: prompt가 추론 때 렌더링과 같고, 손실 token이 thinking과 JSON 모두(응답 전체 + EOS).
  - HF 레코드: prompt가 추론 렌더링 + 추론 부분(`</think>`까지), 손실 token이 `</think>` 뒤 JSON + EOS만.
  - 두 방식의 전체 token 열은 같고 손실 경계만 다르다. 표시 없음·표시 불일치·DPO `by_source`는 거부.
- pilot_003 SFT 460레코드에 적용(`loss_scope_check.py` → `loss_scope_check.json`, 메모리 안에서만, 파일을 쓰지 않음): 460/460 통과.

| 출처 | 레코드 | 손실 범위 | 손실 token(최소 / 중앙 / p90 / 최대) | 손실 token 합 | 전체 token 최대(한도 11,392) |
|---|---:|---|---|---:|---:|
| HF | 227 | json_only | 132 / 217 / 236 / 325 | 48,963 | 11,325 |
| teacher | 233 | full_response | 472 / 915 / 1,462 / 2,109 | 227,454 | 9,389 |

- 손실 token의 82%가 teacher 레코드에서 나온다(json_only로만 했을 때 teacher 레코드의 손실 token은 JSON 부분뿐이었다). 학습률·epoch는 이번에 정하지 않는다.

## 2. 유형별 상한 도구(결정 88)

- 도구: `type_caps.py`(시험 `tests/test_type_caps.py` 5개). 유형 칸은 `pilot_prep_004/type_target`의 `profile`(집계·dimension·dimension_target 유무),
  개발 분포는 `type_target.json`의 `dev_distribution`이다.
- 상한: 총수 M에서 TV 최솟값 Σ max(0, d_c − a_c/M) ≤ τ를 만족하는 가장 큰 M을 찾고, 칸별 상한을 개발 분포에 맞춰 나눈다. 칸 안에서는 질문을 돌아가며(seed 20261014) 고른다.
- pilot_003 데이터(`thinking_pilot003_t2pc`)에 적용(`type_caps.json`, τ = 0.09, 수치만):

| 시나리오 | SFT 레코드(질문) | DPO 쌍(질문) | TV 질문 / 레코드 / DPO | SFT HF / teacher | 실차 대조 SFT(occupied·plain·trip·vacant) | 실차 대조 DPO(plain·trip·vacant) |
|---|---|---|---|---|---|---|
| 지금(상한 없음) | 460(131) | 348(53) | 0.117 / 0.124 / 0.140 | 227 / 233 | 24·20·21·16 | 16·24·20 |
| A. 레코드 상한만 | 431(131) | 312(53) | **0.117** / 0.089 / 0.090 | 221 / 210 | 14·13·21·12 | 7·24·10 |
| B. 질문 상한 → 레코드 상한 | 431(125) | 312(53) | 0.087 / 0.089 / 0.090 | 224 / 207 | 16·7·21·11 | 7·24·10 |

- A는 질문 분포 TV가 그대로라(0.117) 결정 88의 "0.09 이하"를 질문 기준으로는 채우지 못한다. B는 세 기준 모두 0.09 이하다(질문 6개 빠짐, `dropped_questions`).
- 두 시나리오 모두 batch006 실차 대조 레코드가 줄어든다(occupied 24 → 14·16). 실차 통행량 보강과 유형 상한이 부딪힌다. 어느 쪽을 먼저 둘지는 정하지 않았다.
