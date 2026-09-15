# Vendor Tool Trace Acceptance — Meeting Brief

- 미팅: 2026-09-17
- 대상: 업체 제공 13개 질문
- 기준: `evaluation/vendor/vendor_trace_gold.yaml`
- 재현: `python evaluate_vendor_trace.py --model qwen3:8b --agent-mode geoflow --repeat 3`
- Tool Provider: Mock

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

After — LLM은 한 번만 호출하고, 이후는 프로그램이 결정한다.

```text
자연어 질의
  → Planner (template + slots)      LLM 1회. Tool 이름을 다루지 않는다
  → Typed GeoFlow Plan
  → Validation (G1~G6)
  → Compiler
  → Deterministic Tool Execution    기존 ToolExecutor 재사용
  → 답변
```

## 3. 결과

| Model | Mode | Result |
| --- | --- | --- |
| qwen3:8b | react | 7 / 13 |
| qwen3:8b | geoflow | **13 / 13** |
| qwen3.8:27b | react | 13 / 13 |
| qwen3.8:27b | geoflow | **13 / 13** |

반복 재현성 — qwen3:8b + geoflow, 3회 반복

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

최초 Planner가 이미 질문에서 region을 추출하므로, 조회 실패 후에야 처음 나타난
region은 정의상 사용자가 말한 값이 아니다. 재계획 결과에서 제거한다.

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

- 업체 제공 **13개 질문에 대한 acceptance 결과**다. 일반적인 모든 자연어 질의의
  정확도 100%를 뜻하지 않는다.
- **qwen3.8:27b에서는 ReAct도 13/13**이었다. 업체 사례에서 관찰된 오류는 ReAct
  구조에서 모델 성능에 따라 발생할 수 있었던 것이며, ReAct가 이 13문항을 처리하지
  못한다는 뜻이 아니다. GeoFlow는 Tool 선택·인자·scope provenance·dependency
  binding의 일부를 LLM 판단이 아니라 구조로 제약해 **작은 모델에서도 안정성을
  높였다**는 것이 정확한 표현이다.
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
