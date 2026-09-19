# Vendor Tool Trace Acceptance — Meeting Brief

- 미팅: 2026-09-17
- 대상: 업체 제공 13개 질문
- 기준: `evaluation/vendor/vendor_trace_gold.yaml`
- 재현: `python evaluate_vendor_trace.py --model qwen3:8b --agent-mode geoflow --repeat 3`
- Git commit: `8d080b3d86a9a97e16fb3fc8c953f968b1513bb8`
- 최종 검증 run: `evaluation/vendor_runs/20260915_160216`
- Tool Provider: Mock

## Executive Summary

- 업체 제공 13개 질문을 실제 Tool execution trace 기준으로 평가했다.
- 모델 5종에서 측정했고, 모든 모델에서 GeoFlow ≥ ReAct였다.
  예: qwen3:8b는 ReAct 7/13 → GeoFlow 13/13, gemma4:12b는 4/13 → 10/13.
- qwen3:8b + GeoFlow 3회 반복 39/39 PASS.
- 이 13문항은 시스템 개선에 사용한 사례와 동일하므로, 결과는 **acceptance /
  regression**이며 held-out 일반화 성능이 아니다.
- fine-tuning은 수행하지 않았다. 1차에서는 orchestration 구조를 먼저 개선했다.

## 1. 업체 요청

> "Tool 호출의 적절성은 실행 trace를 기준으로 별도로 확인해야 합니다.
> 각 질문별 실제 Tool 호출 결과와 기대되는 정답 Tool 호출 흐름을 기준으로
> Tool 선택, 인자 구성, 순차 호출 능력을 개선해달라."

따라서 최종 답변 문장이 아니라 **실행 trace의 정확성**을 판정 대상으로 삼았다.

## 2. 개선 방식

Before — 매 hop마다 LLM이 다음 Tool과 argument를 결정한다.

```text
자연어 질의 → LLM → Tool → LLM → Tool → … → 답변
```

After — LLM은 최초 planning에서 template과 slots만 결정한다. 정상 경로에서는
이후 Tool 호출 순서와 argument binding을 프로그램이 결정한다. 장소 조회가
실패한 경우에 한해 slot repair를 위해 LLM을 최대 1회 추가 호출할 수 있다.

```text
자연어 질의
  → Planner (template + slots)      기본 LLM 1회. Tool 이름을 다루지 않는다
  → Typed GeoFlow Plan
  → Validation (G1~G6)
  → Compiler
  → Deterministic Tool Execution    기존 ToolExecutor 재사용
       ↓
     장소 조회 실패 시에만
     Planner slot repair 최대 1회   재계획 결과도 같은 검증 경로를 다시 통과
  → 답변
```

## 3. 결과

모델 5종을 동일 질문·동일 기준으로 측정했다.

| Model | 크기 | react | geoflow |
| --- | ---: | ---: | ---: |
| qwen3.8:27b | 17.7 GB | 13 / 13 | **13 / 13** |
| qwen3.5:9b | 6.6 GB | 9 / 13 | 11 / 13 |
| gemma4:12b | 7.6 GB | 4 / 13 | 10 / 13 |
| gemma4:e4b | 9.6 GB | 6 / 13 | **13 / 13** |
| qwen3:8b | 5.2 GB | 7 / 13 | **13 / 13** |

측정한 모든 모델에서 geoflow ≥ react이며, 격차는 react 점수가 낮은 모델일수록
크다(gemma4:12b 4→10, qwen3:8b 7→13).

### geoflow 실패의 성격

qwen3.5:9b 2건과 gemma4:12b 3건은 **모두 Planner LLM 호출이 응답을 반환하지
못한 경우**다. 모델이 구조화 출력을 끝내지 못하는 문제다.

```text
gemma4:12b  q24, q29   Planner 호출이 응답 없음
gemma4:12b  q22        장소 조회 실패 후 재계획 호출이 응답 없음
qwen3.5:9b  q26        Planner 호출이 응답 없음
qwen3.5:9b  q22        장소 조회 실패 후 재계획 호출이 응답 없음
```

q22 2건은 실행 기록의 `runtime_error`가 `get_place_scope/NOT_FOUND`로만 남아
있어, 재계획 호출이 실패한 것인지 재계획 결과가 검증에서 탈락한 것인지 구분되지
않았다. 재계획 경과를 `run.attempts`에 남기도록 고친 뒤 두 모델을 재실행해
원인을 확정했다(`20260918_231241`, `20260918_232957`). 점수와 실패 질문은
동일했고, 두 모델 모두 `repair_failed / PLANNER_CALL_FAILED: ReadTimeout`이다.
재계획이 잘못된 장소로 재조회를 시도한 경우는 없다.

이 실패가 timeout 설정 탓인지 확인하기 위해 chat timeout을 **120초에서 1800초로
15배 늘려 재실행**했다. 결과는 동일했다.

| Model | chat timeout 120초 | chat timeout 1800초 |
| --- | ---: | ---: |
| qwen3.5:9b | 11 / 13 | 11 / 13 |
| gemma4:12b | 10 / 13 (300초) | 10 / 13 |

같은 질문이 같은 이유로 실패했고, 재실행 내내 GPU는 85~93%로 가동 중이었다.
즉 연산이 멈춘 것도, 시간이 모자란 것도 아니다. **30분을 기다려도 이 모델들은
해당 prompt에서 응답을 완성하지 못한다.** 설정을 조정해 해결할 수 있는 문제가
아니라 모델 특성이다.

즉 geoflow 실패 전체에서 **잘못된 Tool 선택, argument hallucination,
scope provenance 위반, dependency binding 오류는 0건**이다. 실패 원인은 orchestration 로직이 아니라
모델이 응답을 생성하지 못한 것이다. 다만 결과 표에는 실패로 그대로 집계했다.

react 실패는 성격이 다르다. 대부분 Tool 순서 오류, 필수 인자 누락,
dependency binding 오류처럼 **판단 자체가 어긋난 경우**다.

반복 재현성 — qwen3:8b + geoflow, 3회 반복 (최종 검증 run)

```text
39 / 39 PASS       (13문항 × 3회, Tool 호출 84회)

질문에 없는 기간(date/time) 생성                0건
scope hallucination                          0건
발화에 없는 region 생성                        0건
include_vicinity 누락                         0건
통행량을 ranking으로 오해                      0건
origin/destination binding 오류                0건
```

4개 대표 질문은 3회 모두 **동일한 trace**를 생성했다.

## 4. 대표 개선 사례

### Q03 — 동대구역 근처 평균 속도

"근처"가 `include_vicinity`로 반영되지 않던 문제.

```text
get_place_scope(name=동대구역, include_vicinity=true) → scope:edge:11234
get_passage_metrics(scope=scope:edge:11234, metric=speed, aggregation=avg,
                    date=20260530, time=120000-130000)
```

`include_vicinity=true`는 Planner가 고르는 값이 아니라 template 상수다.

### Q22 — 동성로동 → 신천동 실차 구간 건수

`date=last_week` 생성과 scope 환각 위험이 있던 문제.

```text
get_place_scope(name=동성로동, region=대구) → NOT_FOUND
get_place_scope(name=동성로,   region=대구) → scope:edge:1742
get_place_scope(name=신천동)               → scope:district:2723510100
get_trip_count(scope_pickup=scope:edge:1742,
               scope_dropoff=scope:district:2723510100)
```

Checks: 기간 생성 없음 / pickup·dropoff 역할 보존 / 두 scope 모두 앞선 resolver 결과.
`origin→scope_pickup`, `destination→scope_dropoff`는 compiler가 고정한다.

### Q24 — 대구시 평균 택시 요금

사용자가 말하지 않은 "경상북도"를 중간에 만들어내던 문제.

```text
get_place_scope(name=대구시) → NOT_FOUND
get_place_scope(name=대구)   → scope:district:2700000000
get_trip_metrics(scope=scope:district:2700000000, metric=fare, aggregation=avg)
```

현재 repair 정책에서는 최초 plan에 없던 region이 장소 조회 실패 이후 새로
추가되면 보수적으로 제거한다. 업체 사례에서 관찰된 "경상북도" 같은 상위 지역
hallucination을 차단하기 위한 v1 guard다.

### Q25 — 어린이대공원 주변 통행량

단순 통행량을 순위 조회로 오해해 `dimension/order/limit`을 붙이던 문제.

```text
get_place_scope(name=어린이대공원, region=부산 초읍동, include_vicinity=true)
  → scope:edge:busan_children_park
get_passage_count(scope=scope:edge:busan_children_park)
```

이 template에는 `dimension`/`order`/`limit` slot 자체가 없어 표현할 수 없다.

## 5. 구조적으로 제한한 오류

| 오류 | 제한 방식 |
| --- | --- |
| 질문에 없는 조건 | slot이 비면 argument 자체가 만들어지지 않음 |
| scope 환각 | Validator G6 + executor의 known scope 검사 (이중) |
| origin/destination 뒤바뀜 | operator registry의 고정 port binding |
| vicinity 누락 | template 상수 |
| 재계획 중 지역 날조 | 새로 나타난 상위 지역 제거 |
| 지원하지 않는 argument 조합 | template `slot_requires` + Tool JSON Schema |

Planner는 Tool 이름을 출력하지 않으며 호출 시 `tools`를 전달하지 않는다.
출력은 전부 untrusted input으로 취급해 template → validator → compiler를 거친다.

## 6. 평가 자체의 신뢰성

통과만 시키는 evaluator는 13/13을 증명하지 못한다. 업체가 자료에 기록한 실패
trace를 그대로 넣어 기대한 분류로 실패하는지 먼저 확인했다.

```text
Q03 include_vicinity 누락      → MISSING_REQUIRED_ARGUMENT
Q04/Q05/Q22/Q27 last_week      → FORBIDDEN_ARGUMENT
Q29 last_month                 → FORBIDDEN_ARGUMENT
Q24 경상북도 생성               → UNGROUNDED_ARGUMENT + UNEXPECTED_RETRY
Q25 dimension/order/limit      → FORBIDDEN_ARGUMENT
O/D 뒤바뀜                     → DEPENDENCY_BINDING_MISMATCH
출처 불명 scope                 → SCOPE_PROVENANCE_VIOLATION
```

부정 테스트 11건 포함 전체 103건 통과.

## 7. 제한

**결과를 과장하지 않기 위해 반드시 함께 설명한다.**

- 업체 제공 **13개 질문에 대한 acceptance / regression 결과**다. 이 13문항은
  시스템 개선에 사용한 업체 제공 사례와 동일하므로, 39/39는 held-out 일반화
  성능이 아니다. 새로운 표현과 unseen 질의에 대한 일반화 성능은 별도 held-out
  평가가 필요하다.
- **qwen3.8:27b에서는 ReAct도 13/13**이었으므로 ReAct 자체가 이 문제를 항상
  일으킨다는 의미는 아니다. 다만 그보다 작은 모델 4종에서는 동일 질문과 판정
  기준에서 ReAct가 4~9/13에 그친 반면 GeoFlow는 10~13/13이었고, GeoFlow가 일부
  의사결정을 LLM에서 deterministic runtime으로 옮기면서 **모델 선택에 따른
  변동성을 줄인 사례**를 확인했다.
- GeoFlow에도 모델 의존성은 남아 있다. qwen3.5:9b와 gemma4:12b에서 발생한 실패
  5건은 모두 Planner LLM이 응답을 반환하지 못한 경우이며(2026-09-18 재실행에서
  attempt 단위로 확인), chat timeout을 15배로 늘려 재실행해도 동일했다. Planner가
  구조화 JSON을 안정적으로 생성할 수 있는 모델이어야 한다는 전제는 그대로다.
- 모델별 측정은 각 1회 실행 기준이다. 반복 재현성은 qwen3:8b에서만 3회
  확인했다.
- repair의 region guard는 보수적 정책이다. 최초 Planner가 사용자 발화의 region을
  누락한 경우, repair에서 추가된 정당한 region도 제거될 수 있다.
- Mock Provider 기준이다. 실제 TIMS/Gazetteer는 연결하지 않았다.
- **fine-tuning은 수행하지 않았다.** 업체가 제공한 실패 사례를 먼저 기계가 읽는
  gold trace로 정형화하고, 실행 trace 기준 acceptance 체계를 구축했다. 문제가
  단순 Tool 분류뿐 아니라 hallucinated argument, scope provenance, multi-step
  dependency binding에도 있었기 때문에 1차에서는 orchestration 구조를 먼저
  개선했다. `vendor_trace_gold.yaml`은 향후 SFT / preference tuning 데이터
  구성의 source로 재사용할 수 있다.
- 현재 단계는 업체가 준 실패 사례의 **재현 및 구조적 개선 검증**이다.

## 8. 다음 단계 (미팅 후 검토)

- 추가 업체 질의 확보
- held-out evaluation
- 실제 Provider 연결
- 데이터가 충분히 확보되면 fine-tuning 필요성 별도 검토
