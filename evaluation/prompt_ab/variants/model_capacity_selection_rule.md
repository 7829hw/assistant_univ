# frozen-H0 model capacity 비교: development 후보 선택 규칙 (사전 등록)

census 측정 **전에** 고정했다. 구현은 `model_capacity.py`의 `select()`와 `canary()`이며, 이 문서와 같다.

## 고정한 것

- production 코드와 계약 전체: system prompt 64bbceb4, factor 재질의 5af4c744, grounding schema, parser,
  composer, relation invariant, operator registry, validator, compiler, executor, repair.
  L1 보정과 V0 검증기는 쓰지 않는다
- 생성 옵션: temperature 0, think 미지정(Ollama 기본값), num_predict 미지정, timeout 300초, 재시도 규칙 같음
- protocol: isolated_state_v1(f3b0eb0 이후). 관측마다 모델을 내리고 확인, cold 첫 호출, cold load 확인.
  planner 재시도가 생기면 관측 전체를 다시 시작하고, 다시 생기면 무효다.
  run 시작 전에 올라가 있는 모든 모델을 내린다
- 채점과 분류: failure_census.py 그대로(strict, 결과 등급, family 묶음). 새 분류를 만들지 않는다.
  묶음에 들지 않는 실패는 `(ungrouped)`로 센다
- 모델마다 다른 prompt, parser 관용, 옵션을 쓰지 않는다

## 모델

| arm | model | digest | 크기 |
|---|---|---|---|
| M0 | qwen3:8b (production) | 500a1f067a9f | 8.2B Q4_K_M |
| M1 | qwen3.5:9b | 6488c96fa5fa | 9.7B Q4_K_M |
| M2 | qwen3.8:27b | 22130167c4c2 | 27.3B Q4_K_M |

Ollama 0.33.2. 새로 내려받은 모델은 없다.

## timeout probe (측정 전)

`model_probe.py`로 production prompt와 같은 옵션에서 cold 첫 호출을 질문 3개(f01_p0, b05_p0, b20_p0)로 봤다
(`evaluation/design/model_capacity_probe.json`). 정확도는 보지 않았다.

| model | f01_p0 | b05_p0 | b20_p0 |
|---|---|---|---|
| M0 | 6.8초 stop | 6.0초 stop | 7.8초 stop |
| M1 | 300초 cap, 끝나지 않음(thinking 165k자) | 41.3초 stop | 26.8초 stop |
| M2 | 15.8초 stop | 11.4초 stop | 14.8초 stop |

- timeout은 모든 모델 300초로 같다. 누구를 위해서도 timeout이나 생성 옵션(think 등)을 바꾸지 않는다.
- M1은 느린 것이 아니라 일부 질문에서 생성이 끝나지 않는다(초당 약 125 token으로 thinking이 계속됨).
  그대로 잰다. 그런 관측은 기존 규칙대로 무효가 된다.
- census는 `--max-invalid 10`으로 잰다. 무효가 11건(5% 초과)에 이르면 run이 멈추고, 그 모델은 E 실패로
  후보에서 빠진다. 비용 때문에 M0, M2를 먼저 재고 M1을 마지막에 잰다.

## development census

- 211 unique question, 모델마다 한 번. 이미 exposed된 corpus다(development).
- 무효 관측은 비교하는 두 모델 모두에서 뺀다(짝 제외).
- 결정성: 모델마다 census 앞뒤로 canary 8개(f01_p0, b24_p0, b05_p0, q27_p0, b20_p0, f14_p0, h06_p0, f12_p0)를
  같은 protocol로 다시 잰다. 앞, census, 뒤의 첫 응답 원문이 셋 다 같아야 결정적이다.

## 후보 조건 (M0 대비, 짝지은 질문에서)

| 검사 | 조건 |
|---|---|
| A | 조용한 오답 intent 수 < M0 |
| B | 조용한 오답 관측의 family 묶음 가운데 M0에 없던 것이 없다(`(ungrouped)` 포함) |
| C | strict 정답 intent 수(모든 paraphrase가 최종 strict 정답) ≥ M0 |
| D | 지원 범위 밖 질의에 계획을 만든 조용한 오답 수 ≤ M0 |
| E | 무효 관측 비율 ≤ 5%, 그리고 후보와 M0 모두 canary가 결정적 |

A~E를 모두 통과한 모델이 후보다. 여럿이면 조용한 오답 intent → 조용한 오답 관측 → strict intent →
strict 관측 → 계획 없이 거부한 지원 질의 → 무효 → 재질의 → 모델 크기(작은 쪽) 순으로 고른다.

- 후보가 없으면 M0를 유지하고 fresh holdout을 쓰지 않는다. 강한 모델도 같은 실패를 보이면
  model capacity 문제가 아닌 것으로 기록한다(Case C).
- 후보가 있으면 그 모델 hash를 고정한 뒤 fresh model holdout을 쓰고 M0와 비교한다.
  development 결과로 production 모델을 바꾸지 않는다.

지연은 정확도와 합치지 않고 따로 보고한다.
