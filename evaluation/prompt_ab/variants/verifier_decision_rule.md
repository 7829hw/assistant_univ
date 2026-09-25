# reject-only 의미 검증기 H0 vs V0 판정 규칙 (사전 등록)

holdout 측정 **전에** 고정했다. 구현은 `verifier_ab.py`의 `decide()`와 `analyze()`이며, 이 문서와 같다.

- **측정:** `evaluation/paraphrases_verifier_holdout.yaml` (fresh, 24 intent, 72 paraphrase. family 6 × (H0가 틀리기 쉬운 질의 3 + 올바른 계획 대조군 1))
- **arm:** `V0_VERIFY` 한 arm. 첫 grounding과 재질의는 production H0(64bbceb4, 5af4c744) 그대로이므로 한 관측에서 H0 결과와 V0 결과가 함께 나온다. 두 결과의 첫 grounding 차이는 구조적으로 0이다
- **protocol:** isolated_state_v1, paraphrase마다 1회. 첫 grounding 호출 전에 모델을 내리고 cold load를 확인한다. 검증 호출(cad71775)은 H0 관측이 끝난 뒤 같은 관측 안의 두 번째 호출이다(같은 모델, 올라간 상태). 그 지연과 load 시간을 기록한다. planner 재시도가 생기면 관측 전체를 다시 시작하고, 다시 생기면 무효다. 검증 호출의 실패는 관측을 무효로 만들지 않고 fallback이다
- **검증 대상:** H0 최종 계획이 검증을 통과한 관측만. 재질의 뒤 최종 계획에서 서명을 만든다. 거부된 관측에는 부르지 않는다
- **검증기 입력:** 질문과 의미 서명뿐이다. 기대 label, 기대 Tool 인자, golden, family, control은 넘기지 않는다
- **채점:** Tool 인자까지 보는 strict

## V0 동작 (663959e에 구현, 결과 전에 고정)

| 검증 결과 | V0 |
|---|---|
| consistent | H0 계획 그대로 |
| inconsistent (형식 검증 통과) | 계획 폐기, 안전하게 거부, Tool 호출 0. 재질의·재계획 없음 |
| uncertain | H0 계획 그대로 |
| fallback (호출 실패, JSON 아님, verdict·kind·plan_field 형식 위반, 고칠 값 같은 모르는 key, 질문에 없는 근거 문자열) | H0 계획 그대로 |

V0의 최종 결과는 H0 계획 그대로이거나 계획 없음이다. V0에서만 생기는 조용한 오답은 구조상 없다.

## 정의 (검증기가 불린 관측 기준)

| 이름 | 뜻 |
|---|---|
| H0 조용한 오답 | H0 계획이 검증을 통과했는데 strict 오답. 지원 범위 밖 질의에 계획이 만들어진 것 포함 |
| TP | H0 조용한 오답 + inconsistent |
| FP | H0 strict 정답 + inconsistent |
| FN | H0 조용한 오답 + consistent / uncertain / fallback |
| TN | H0 strict 정답 + 거부하지 않음 |
| precision | TP / (TP + FP). 거부가 하나도 없으면 정의하지 않는다 |
| recall | TP / (TP + FN) |
| TP intent / FP intent | TP / FP 관측이 하나라도 있는 intent |
| TP family | TP intent가 속한 holdout family |

## 판정

| 검사 | 조건 |
|---|---|
| A | V0에서만 생긴 조용한 오답 0, 그리고 V0 최종 결과가 H0 계획 또는 계획 없음이 아닌 관측 0 |
| B | FP intent ≤ 1 |
| C | TP intent ≥ 2 |
| D | TP family ≥ 2 |
| E | precision ≥ 0.9 (거부가 없으면 통과로 보고 C에서 걸린다) |
| F | 검증 호출 중 fallback 비율 ≤ 10% |

- A 실패 → **INVALID**: 구현 오류
- B 또는 E 실패 → **Case C**: 정답 거부가 많다. 검증기 폐기, H0 유지
- 그렇지 않고 C 실패 → **Case D**: 탐지가 부족하다. 추가 prompt 연구 중단
- 그렇지 않고 D 실패 → **Case B**: 한 family만 잡는다(집계만 잡는 경우 포함). 범용 검증기로 가치 낮음
- 그렇지 않고 F 실패 → **UNRELIABLE**: 채택하지 않는다
- 모두 통과 → FP intent가 0이면 **Case A**(production semantic gate 후보), 1이면 **A_REVIEW**(후보이나 그 intent를 사람이 검토)

무효 관측(isolated로 잴 수 없었던 것)은 뺀다. 한 arm이므로 짝 제외가 따로 없다.
결과를 본 뒤 검증 prompt나 서명 문장을 고치고 다시 재지 않는다. 이 holdout은 측정 뒤 development로 바꾼다.

## development 확인

holdout 전에 기록된 H0 관측(census 20260924_005520, aggregation r2의 H0, local holdout의 H0)의 최종 계획을 재생해 검증 호출만 새로 했다(`semantic_verifier_replay.py`). 출력 형식, 근거 문자열, fallback 비율, 지연만 확인했고 정확도를 보고 prompt를 고치지 않았다.
