# 격리 확인 실험 결과

2026-10-13. 계획: `RUN_PLAN.md`(실행 전 commit `6d5fbfd`), 판정 기준: `AUDIT.md` 4절. 원자료: `raw/`, `resident/`, `runs.log`. 분석: `analyze.py` → `result.json`.

## 1. 결론

- **resident_isolated는 격리 판정을 통과하지 못했다(사전 규칙 4).**
  - 같은 질문·같은 seed에서 문항 순서만 바꾼 B(정순)와 B'(역순)의 첫 계획 응답(원문과 thinking 길이)이 같은 문항 수는 greedy 0/10, sampling 5/10이다. 기준은 10/10이었다.
- **reset 없는 resident(C·C')보다도 나빴다.** C 대 C'는 greedy 5/10, sampling 5/10이다. isolation 요청이 순서 영향을 줄이지 못했다.
- 따라서 resident_isolated를 판정용 측정이나 trace 수집에 쓰지 않는다. **P0 trace 수집으로 넘어가지 않고 여기서 멈춘다.**
  - isolation 요청 횟수를 늘리거나 컨테이너를 재시작하면서 맞추지 않았다.
- **상주 자체는 계획대로 됐다.**
  - 상주 블록(약 16분) 동안 model unload 0, reload 0(runner PID 하나), 컨테이너 재시작 0이었다.
  - warm-up은 2호출이었다(204·210 tok/s).
  - 모든 셀이 속도 guard를 통과했다.

## 2. 실행 기록

| 항목 | 값 |
|---|---|
| 모델 | Ollama 0.40.3 `qwen3:8b`(500a1f06), prompt Full 87048d0c, code fingerprint ab88a19e |
| 문항 | 10(`items_gold.json`, v005 학습 gold에서 고정 seed. 실행 시 이름은 `items_gold.yaml`, 4절) |
| A(unload_per_question) | 01:46–01:57 UTC. 셀마다 빈 GPU 확인, 문항마다 unload |
| 상주 블록 | 모델 최초 load(warm-up) 01:59:39 UTC, 종료 02:15:31 UTC |
| 상주 중 unload / reload / 컨테이너 재시작 | 0 / 0 / 0(`resident/residency.json`, poll 187회) |
| warm-up | 2호출(판정 무관) |
| 셀별 reset_ok | B·B' 10/10(greedy·sampling), C·C' 0/10(reset 없음, 대조군) |
| 실패·중단 셀 | 없음(모든 셀 rc 0, guard 0) |

## 3. 비교(같은 문항·같은 seed, 10문항)

| 쌍 | 모드 | 첫 응답 동일(판정 항목) | 모든 응답 원문 동일 | grounding 동일 | 채점 범주 동일 | error code 동일 | Tool 호출 동일 |
|---|---|---:|---:|---:|---:|---:|---:|
| B 대 B'(격리, 순서만 다름) | greedy | **0** | 1 | 2 | 3 | 5 | 3 |
| | sampling | **5** | 8 | 10 | 10 | 10 | 10 |
| C 대 C'(재사용, 순서만 다름) | greedy | 5 | 6 | 6 | 7 | 7 | 7 |
| | sampling | 5 | 7 | 9 | 9 | 10 | 9 |
| B 대 A(격리 대 문항마다 unload) | greedy | 2 | 4 | 6 | 7 | 7 | 7 |
| | sampling | 0 | 2 | 3 | 8 | 9 | 8 |
| B 대 C(같은 순서, reset 유무) | greedy | 1 | 3 | 4 | 6 | 8 | 6 |
| | sampling | 9 | 9 | 9 | 9 | 10 | 9 |

**순서 때문에 달라진 문항 수(B 대 B', C 대 C'):**

| 달라진 것 | B 대 B' greedy | B 대 B' sampling | C 대 C' greedy | C 대 C' sampling |
|---|---:|---:|---:|---:|
| semantic 결과(채점 범주) | 7 | 0 | 3 | 1 |
| grounding | 8 | 0 | 4 | 1 |
| error code | 5 | 0 | 3 | 0 |

- resident_isolated는 greedy에서 순서 영향이 오히려 컸다. sampling에서는 의미 결과 차이가 0이었지만 응답 원문은 5/10 문항에서 달랐다.
- 사전 판정 항목(원문)으로는 어느 쪽도 격리되지 않았다.

## 4. 원인 확인(기존 기록만, 추가 모델 호출 없음)

| 확인 항목 | 결과 |
|---|---|
| isolation 요청이 KV 재사용을 끊었는가 | 일부만. 문항 첫 호출의 prefill 비용(회귀 절편): A 626ms, B 268ms, C −49ms. B는 재사용(C)보다 다시 계산했지만 막 올린 상태(A)와 같은 양을 계산하지 않았다. reset 뒤 cache 상태가 "막 올린 상태"와 같지 않다 |
| 어디서 갈라지는가 | greedy B 대 B'의 thinking이 앞쪽 62–870자에서 갈라진다(10/10). 같은 문항·같은 prompt인데 생성 초반부터 다르다 |
| seed가 같았는가 | 같다. sampling 다섯 셀 모두 문항별 첫 호출 seed가 같다(`call_seed`) |
| greedy가 sampling보다 민감한 이유(해석) | greedy는 1등 token만 고르므로 logit 차이가 작은 자리에서 수치 차이가 바로 다른 token이 된다. seed sampling은 같은 난수로 고르므로 작은 logit 차이에 덜 민감하다(B 대 C sampling 9/10 동일) |
| Ollama 0.40.3 동작 | runner 내부(cache slot 재사용 방식, batch 분할, 커널 선택)는 조사하지 않았다. 문서화된 요청별 cache 끄기 옵션은 쓰지 않았다(확인되지 않음) |
| prefix cache가 다른 방식으로 남는가 | 가능성이 있다. reset 요청 뒤에도 prefill 비용이 A보다 작다. 무엇이 남는지는 서버 내부라 이 자료로 알 수 없다 |

**해석(확정 아님):**

- 출력은 모델을 막 올린 상태인지, 직전에 어떤 요청을 처리했는지에 따라 수치 수준에서 달라진다.
- 짧은 raw 요청 하나로는 그 상태를 "막 올린 상태"로 되돌리지 못한다.
- 이 실험은 A(문항마다 unload)를 같은 조건으로 두 번 재지 않았다. 따라서 unload_per_question 자체가 반복 실행에서 같은 출력을 내는지도 이 자료로는 확인되지 않는다.
  - grounding_v14는 "적재 직후 첫 요청은 재현된다"고 기록했다.

## 5. 다음(사용자 결정, 실행하지 않음)

1. **판정용 측정·trace 수집은 당분간 unload_per_question(기존 방식)으로 한다.** weights 상주 = 아니오, 문항 상태 격리 = 예다. 지금 상태에서 상주와 격리를 함께 만족하는 방법은 없다.
2. **상주와 격리를 함께 원하면 추가 조사가 필요하다.**
   - Ollama runner의 cache 동작 확인(서버 로그·문서)
   - 다른 reset 방식(예: 같은 길이·다른 내용의 요청으로 cache를 덮기)
   - A를 두 번 재서 기준선 자체의 재현성 확인
   - 각각 모델 호출이 필요한 새 실험이다.
3. **상주 run에서 arm 간 공정성:** C처럼 상주·비격리로 돌리면 같은 순서끼리만 비교할 수 있다. 순서를 arm마다 돌리면 순서 효과가 arm 차이에 섞인다.

## 6. 파일 이름 변경

- 실행 때 문항 파일은 `items_gold.yaml`이었다(run meta의 gold_file, sha256 `7d51f228…`).
- `evaluation/**/*.yaml`은 학습 데이터 보호 원본(`training/data/common.reserved_sources`)이라, 학습 gold 질문 10개가 보호 질문으로 잡히게 된다.
- 그래서 실행 뒤 같은 내용을 JSON으로 바꾼 `items_gold.json`으로 옮겼다. YAML 로더로 읽히므로 같은 명령으로 다시 쓸 수 있다.
