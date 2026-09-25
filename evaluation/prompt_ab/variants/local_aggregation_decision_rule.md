# 국소 집계 보정 H0 vs L1 판정 규칙 (사전 등록)

holdout 측정 **전에** 고정했다. 구현은 `local_aggregation_ab.py`의 `decide()`와 `analyze()`이며, 이 문서와 같다.

- **측정:** `evaluation/paraphrases_local_aggregation_holdout.yaml` (fresh, 24 intent, 72 paraphrase. 보정 대상 13, 대조군 11)
- **arm:** `H0_AGG`(production, 64bbceb4) vs `L1_AGG`(첫 호출 64bbceb4 + 집계 전용 호출 22c501ff). 재질의 문구는 두 arm이 같다(5af4c744)
- **protocol:** isolated_state_v1, paraphrase마다 arm당 1회, 반복 없음. 두 arm 모두 첫 grounding 호출 전에 모델을 내리고 cold load를 확인한다. L1의 집계 전용 호출은 같은 관측 안에서 의도적으로 부르는 두 번째 호출이다(재질의와 같은 취급, warm). 그 지연과 load 시간을 기록한다. planner 재시도가 생기면 관측 전체를 다시 시작하고, 다시 생기면 무효다(f3b0eb0)
- **채점:** Tool 인자까지 보는 strict
- **global H2:** 비교 arm에 넣지 않는다

## L1 동작 (cb2d0e0에 구현, 결과 전에 고정)

| 상황 | 동작 | 후속 호출 |
|---|---|---|
| H0 grounding에 bucket 없음 (파싱 실패 포함) | H0와 같음 | 0 (+ H0 재질의 최대 1) |
| bucket 있음, patch 적용 | aggregation·rollup만 바꾼 grounding으로 합성. 그 뒤 재질의는 하지 않는다(예산 1회를 씀) | 1 |
| bucket 있음, 보정 실패 | H0 결과로 돌아가 H0 경로를 그대로 탄다(H0 재질의 포함) | 1 + H0 재질의 최대 1 |

보정 실패는 호출 실패, JSON 아님, key·값 형식 위반, scope 위반이다. `refinement_outcome = fallback`으로 기록하고, 그 관측이 맞아도 보정 덕으로 세지 않는다.

## 정의

| 이름 | 뜻 |
|---|---|
| 조용한 오답 | 계획이 검증을 통과했는데 strict 오답이다. 지원 범위 밖 질의에 계획이 만들어진 것도 포함 |
| 조용한 오답 intent | paraphrase 하나라도 조용한 오답인 intent |
| strict 정답 intent | 모든 paraphrase가 최종 strict 정답인 intent |
| 집계 단계 조용한 오답 | trigger_expected intent에서 조용한 오답이면서 최종 factor의 집계 의미가 golden과 다름 |
| 단계 뒤바뀜 | 최종 factor에서 STAGE_SWAPPED (aggregation_plan.aggregation_errors) |
| 대조군 동작 차이 | status, validated, strict, 최종 Tool과 인자, 재질의 시도·성공 중 하나라도 다름 |
| scope 위반 | 적용된 patch가 aggregation·rollup 밖의 factor나 개념을 바꿈 |

## 무효 관측과 첫 grounding 동일성

- 무효 관측이 있는 paraphrase는 두 arm 모두에서 뺀다.
- 두 arm이 모두 유효한데 첫 grounding 원문이 다르면 serving 상태 protocol 문제로 보고 그 쌍을 뺀다.
  그런 쌍이 유효 쌍의 10%를 넘으면 측정 전체가 무효다(Case INVALID).

## 판정 (우선순위: 새 조용한 오답 intent → 조용한 오답 intent 수 → strict 정답 intent → 계획 없이 거부 → 추가 호출 → 지연)

| 검사 | 조건 |
|---|---|
| A | L1에서만 조용한 오답인 intent = 0 |
| B | trigger되지 않은 L1 관측과 대조군(trigger_expected=false) 관측 모두 H0와 동작 차이 0 |
| C | 집계 단계 조용한 오답 L1 < H0, 그리고 단계 뒤바뀜 L1 ≤ H0 |
| D | strict 정답 intent 수 L1 ≥ H0 |
| E | scope 위반 0 |
| F | 무효 관측이 있는 intent를 통째로 빼고 다시 판정해도 Case가 같다 |

- A, B, E 중 하나라도 실패 → **Case B**: 폐기. global/local 모두 production H0 유지
- 그렇지 않고 C 실패 → **Case C**: 개선 없음. 두 단계 집계는 known limitation. 추가 prompt 연구 중단
- 그렇지 않고 D 실패 → **Case B**
- 모두 통과했지만 L1 총 LLM 지연이 H0의 1.5배를 넘거나, 관측당 추가 호출이 0.75회를 넘음 → **Case D**: tradeoff로 기록, 자동 채택하지 않는다
- 모두 통과 → **Case A**: L1 production 도입 후보(별도 commit)
- F 실패 → **UNSTABLE**: 채택하지 않는다

결과를 본 뒤 보정 prompt나 trigger를 고치고 다시 재지 않는다. 이 holdout은 측정 뒤 development로 바꾼다.

## development 확인

holdout 전에 `evaluation/paraphrases_aggregation_holdout.yaml`(development)에서 L1 한 arm을 돌려 parser, patch, scope, 기존 경로 호환만 확인했다. 정확도를 보고 prompt를 고치지 않았다.
