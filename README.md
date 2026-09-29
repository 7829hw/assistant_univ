# GBTA Assistant (University Package)

자연어 교통 질의를 입력받아 LLM이 제공된 Tool을 선택하고 필요한 parameter를 구성하여 순차적으로 호출하는 Assistant 최소 실행 패키지입니다.

System Prompt와 Tool 정의는 YAML 파일로 관리하며 Ollama native Tool Calling을 사용합니다. 이 패키지는 실제 ClickHouse/Gazetteer 외부 연동 없이 deterministic Mock Provider만 사용하여 Tool 선택, arguments 구성, multi-hop 호출 흐름을 확인할 수 있도록 구성했습니다.

## 1. 포함 범위

```text
assistant_cli.py
assistant_runtime.py
agent_graph.py
build.py
mock_responses.py
mock_stub.yaml
ollama_client.py
query_loader.py
tool_executor.py
tool_handlers.py
stub_query.yaml
requirements.txt
README.md

prompts/
├─ system.yaml
└─ geoflow_planner.yaml

schemas/
├─ _common.yaml
├─ gazetteer.yaml
└─ tims.yaml
```

GeoFlow planner(`--agent-mode geoflow`)와 평가 도구는 이 저장소에서 추가한 것으로, 주요 위치는 다음과 같습니다.

```text
geoflow/            GeoFlow IR, grounding, macro, composer, validator, compiler, executor
geoflow_macros/     재사용 가능한 macro 조각 정의 YAML
geoflow_templates/  (legacy) 예전 질문 유형 template 정의 YAML
geoflow_examples/   질문–의미 graph 예시와 검색 index
reference_data/     reference provider용 합성 데이터
tests/              GeoFlow 및 react mode 회귀 테스트
evaluate_planner.py 모델별 concept grounding·합성 정확도 측정
stub_query_boundary.yaml  합성 경계 평가 셋
evaluation/stub_query_v1.yaml  v1 stub 질의(평가 corpus의 부모, v2에서 빠진 질의 보존)
```

실제 ClickHouse 연결, 외부 Gazetteer HTTP Client, Web UI, 평가 Runner/Gold, 사용자별 Config, 과거 실행결과, Python 대체 Mock 등은 포함하지 않습니다.

## 2. 실행 흐름

```text
자연어 질의
    ↓
Ollama LLM
    ↓
AssistantRuntime / AgentGraph
    ↓
Tool 선택 + arguments 생성
    ↓
ToolExecutor (JSON Schema 검증)
    ↓
Mock Tool Handler
    ↓
필요 시 다음 Tool 호출
    ↓
최종 답변
```

위 흐름이 기본 실행 모드인 `react`입니다. 질문을 바로 Tool Calling으로 보내지 않고 명시적인 planning 단계를 먼저 거치는 `geoflow` 모드도 선택할 수 있습니다. 자세한 내용은 [8. Agent Mode — GeoFlow Planner](#8-agent-mode--geoflow-planner)를 참고합니다.

장소 scope가 필요한 경우 `get_place_scope` 결과를 다음 TIMS Tool의 scope 인자로 사용합니다. 수정 가능한 Tool 오류는 LLM에 다시 전달되어 다음 hop에서 재호출할 수 있습니다.

## 3. Tool 계약 Source of Truth

다음 파일이 LLM에 전달되는 Prompt/Tool 계약의 기준입니다.

```text
prompts/system.yaml
schemas/_common.yaml
schemas/gazetteer.yaml
schemas/tims.yaml
```

`build.py`는 위 YAML을 읽어 `$ref`를 인라인하고 JSON Schema를 검증한 뒤 Ollama Tool 정의와 System Prompt를 생성합니다.

현재 주요 TIMS Tool은 다음과 같습니다.

- `get_passage_count`
- `get_passage_metrics`
- `get_trip_count`
- `get_trip_metrics`
- `get_drive_metrics`
- `get_billing_metrics`

Gazetteer Tool:

- `get_place_scope`
- `get_scope_name`

## 4. Mock Provider

이 패키지는 `ASSISTANT_TOOL_PROVIDER=mock`만 지원합니다. 지정하지 않아도 기본값은 Mock입니다.

```bash
export ASSISTANT_TOOL_PROVIDER=mock
```

Mock 데이터의 기준은 `mock_stub.yaml`입니다. 값을 수정한 경우 CLI를 다시 실행해야 합니다.

주요 최신 계약은 다음과 같습니다.

- Billing metric: `revenue`, `active_taxi_count`, `active_taxi_ratio`, `operating_days`
- `hours`는 사용하지 않습니다.
- `operating_days`는 분석기간 동안 택시별 운행일수를 구한 뒤 대상 택시 전체에 집계하는 metric입니다.
- `this_week`, `this_month`, `this_year`를 날짜 symbolic value로 사용할 수 있습니다.
- `get_trip_count.dimension_target`의 기본값은 `both`입니다.
  - `pickup`: 승차지역 기준
  - `dropoff`: 하차지역 기준
  - `both`: 승차지-하차지 조합(OD pair)
- `get_trip_metrics.scope`는 택시 소속 지역을 의미합니다.
- `get_billing_metrics`에서 `scope`와 `dimension`은 동시에 사용하지 않습니다.

`get_billing_metrics.dimension` enum의 `sigungu`, `emd`, `h3`는 현재 Schema에 유지되어 있으나, 현재 계약상 scope와 함께 사용할 수 없고 scope 없이 허용되는 dimension은 Schema 설명을 따릅니다.

## 5. Gazetteer Mock

Gazetteer fixture는 `mock_stub.yaml`에서 관리합니다. canonical 또는 alias로 등록된 이름은 성공하고 등록되지 않은 표현은 `NOT_FOUND`가 될 수 있습니다.

현재 fixture 기준 예:

```text
대구 / 대구시 / 대구광역시  → SUCCESS
동성로 / 동성로길           → SUCCESS
동성로동                     → SUCCESS
부산                         → SUCCESS
부산시                       → NOT_FOUND
```

## 6. 실행

의존성 설치:

```bash
python -m pip install -r requirements.txt
```

Schema/Prompt 검증:

```bash
python build.py
```

단일 질문 실행:

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query "대구 소속 택시의 평균 택시 요금은?"
```

YAML 질문 목록 실행:

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml
```

특정 Query만 실행:

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml \
  --query-id q01
```

Ollama 모델에는 native Tool Calling capability가 필요합니다.

## 7. 주의사항

- 이 패키지는 Tool 선택/인자 구성/순차 호출 흐름 확인용 Mock 패키지입니다.
- 실제 TIMS 값 또는 실제 장소 데이터의 정확성을 검증하는 용도가 아닙니다.
- 질문에 없는 날짜/시간 조건을 임의로 추가하지 않는 것이 현재 Prompt 계약입니다.
- `scope:*` 값은 사용자 질문에 직접 포함된 값 또는 이전 Tool Result에서 얻은 값만 사용합니다.

## 8. Agent Mode — GeoFlow Planner

기존 ReAct 방식과 별개로 GeoFlow planning 기반 실행 모드를 제공함.

`--agent-mode`로 선택하며 기본값은 기존 동작을 보존하는 `react`임.

```bash
# 기존 동작 (기본값)
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml

# GeoFlow planning 모드
python assistant_cli.py \
  --agent-mode geoflow \
  --model qwen3:8b \
  --query-file stub_query.yaml
```

### 실행 흐름

```text
자연어 질의
    ↓
Concept Grounder (LLM 1회, Tool 미제공)
    ↓
Grounding (concepts + factors)
    ↓
Macro Retriever + IO-Port Composer
    ↓
Typed GeoFlow Plan (G = (V, E, λ, ρ))
    ↓
GeoFlow Validator (G1~G6)
    ↓
Operator Mapping + Execution Plan Compiler
    ↓
Deterministic Tool Execution (기존 ToolExecutor 재사용)
    ↓
최종 응답
```

`react` 모드가 model hop마다 다음 Tool을 LLM에게 묻는 것과 달리, `geoflow` 모드는
LLM을 1회만 호출하고 이후 조각 합성·Tool 선택·호출 순서·argument binding을
프로그램이 결정함.

**질문 유형을 고르는 단계는 없음.** 질문마다 완성된 workflow template을 하나
고르는 대신, 재사용 가능한 조각(macro)을 input/output port로 합성해 그래프를 만듦.

### Planner의 역할 제한

Planner는 Tool Call을 생성하지 않고, Tool 이름도 출력하지 않으며, 실행 순서도
만들지 않음. 질문 유형을 고르지도 않음.

Planner가 반환하는 것은 질문 표현의 의미 grounding뿐임.

```json
{
  "concepts": [
    {"id": "place_1", "text": "동대구역", "concept": "LOCATION",
     "subtype": "place", "role": "SUBCOND", "source": "user",
     "value": {"name": "동대구역", "region": ""}},
    {"id": "passage", "concept": "EVENT", "subtype": "passage",
     "role": "SUPPORT", "source": "implicit"},
    {"id": "speed", "concept": "AMOUNT", "subtype": "speed",
     "role": "MEASURE", "source": "implicit"}
  ],
  "factors": {"date": "20260530", "aggregation": "avg", "vicinity": true}
}
```

Planner 출력은 모두 untrusted input으로 취급하며, JSON 파싱 실패·미등록 concept·
미정의 factor·형식 불일치는 모두 planner 오류로 처리함.

`source`는 개념의 출처이며 scope provenance 판정의 근거가 됨.

| source | 의미 |
| --- | --- |
| `user` | 사용자가 발화에서 말한 값. value가 반드시 있음 |
| `implicit` | 발화에 없지만 측정을 성립시키려면 필요한 개념 |
| `tool` | 실행이 채우는 값. Planner가 선언할 수 없음 |

`implicit`은 측정 대상 사건(EVENT)과 측정값 자체에만 허용함. 질문에 없는 장소·
지역·날짜를 `implicit`으로 만들 수 없음.

### Macro

`geoflow_macros/*.yaml`은 질문 유형이 아니라 **재사용 가능한 concept 변환 조각**임.
논문의 macro-template `g_k = (V_k, E_k, in_k, out_k)`에 대응함.

| Macro | 입력 port | 출력 port | 뜻 |
| --- | --- | --- | --- |
| `PLACE_TO_SCOPE` | `place` LOCATION/place | `scope` LOCATION/scope\|vicinity_scope | 장소명 → 공간 범위 |
| `SCOPE_TO_PLACE` | `scope` LOCATION/scope\|vicinity_scope | `place` LOCATION/place | 공간 범위 → 장소명 |
| `EVENT_TO_MEASURE` | `event` EVENT/*, `area` LOCATION/scope(선택) | `measure` AMOUNT\|PROPORTION/* | 사건 → 통계값 (한 단계 집계) |
| `EVENT_TO_GROUPED_MEASURE` | `event` EVENT/*, `area` LOCATION/scope(선택) | `measure` AMOUNT\|PROPORTION/* | 사건 → 구간별 값 → 통계값/구간 (두 단계 집계) |
| `OD_EVENT_TO_MEASURE` | `event` EVENT/trip, `pickup`·`dropoff` LOCATION/scope(선택) | `measure` AMOUNT/trip_count | 승하차 구분 사건 → 통계값 |

조각은 다음 세 가지를 갖지 않음.

* `final_node` — 최종 답을 정하는 것은 합성 결과인 `GeoFlowPlan`임
* semantic operator 이름 — operator 선택은 mapping 단계가 함
* 답변 표현(label, unit) — 최종 concept이 정함

조각이 서로 연결되는 유일한 근거는 port의 `(CoreConcept, subtype)` 계약임.
이 계약은 macro 로딩 시점에 operator registry와 대조해 검증함. 어떤 operator도
만들 수 없는 출력 타입을 선언한 조각은 로딩에서 거부됨.

### 합성 예시

같은 조각 library에서 질문마다 다른 합성 결과가 나옴.

```text
"scope:edge:1742상의 평균 속도는?"
    LOCATION/scope (user)
    EVENT/passage  (implicit)
        → EVENT_TO_MEASURE → AMOUNT/speed
    조각 1개, Tool 1회

"동대구역 근처 차량의 평균 속도는?"
    LOCATION/place (user)
        → PLACE_TO_SCOPE (vicinity=true) → LOCATION/vicinity_scope
    EVENT/passage  (implicit)
        → EVENT_TO_MEASURE → AMOUNT/speed
    조각 2개, Tool 2회

"대구 동성로에서 출발하여 신천동에 도착한 실차 구간 건수는?"
    LOCATION/place (od_role=pickup)  → PLACE_TO_SCOPE → LOCATION/scope
    LOCATION/place (od_role=dropoff) → PLACE_TO_SCOPE → LOCATION/scope
    EVENT/trip (implicit)
        → OD_EVENT_TO_MEASURE → AMOUNT/trip_count
    조각 3개, Tool 3회
```

앞의 두 질문은 **서로 다른 질문 유형이 아님**. 공간 조건이 이미 범위로 주어졌는지
장소명으로 주어졌는지만 다르며, 측정 조각은 동일함.

"근처/주변" 같은 표현은 조각을 가르지 않고 `vicinity` factor로 출력 subtype을
정함. 공간 그룹화·순위(`dimension`, `order`, `limit`)도 별도 조각이 아니라 측정 변환의
factor임. TIMS Tool이 같은 호출의 인자로 받기 때문에, 조각을 나누면 대응하는
operator가 없는 node가 생김.

### 합성 규칙

합성은 목표(MEASURE)에서 시작하는 역방향 탐색임.

1. 목표를 만들 수 있는 조각을 찾음
2. 그 조각의 input port를 채움
   1. grounding에 있는 개념으로 채울 수 있으면 그것을 씀
   2. 없으면 그 개념을 만들 수 있는 조각을 다시 찾음(재귀)
   3. 그래도 없고 registry가 유일하게 결정할 수 있는 개념이면 implicit으로 만듦
3. 만들어진 변환마다 operator mapping이 semantic operator를 확정함

다음 경우에는 추측하지 않고 합성을 포기함. 틀린 계획을 만드는 것보다 낫기 때문임.

* 한 port에 연결 가능한 개념이 둘 이상인 경우 (`AMBIGUOUS_PORT`)
* 같은 변환을 수행할 수 있는 operator가 둘 이상인 경우 (`AMBIGUOUS_OPERATOR`)
* 질문의 조건 중 계획에 반영되지 못한 것이 있는 경우 (`UNUSED_CONCEPT`)

마지막 항목이 "A에서 B로" 조건을 조용히 버린 계획이 만들어지는 것을 막음.

2-c의 implicit 생성은 `EVENT`에만 허용함. "평균 속도"라는 질문에는 속도를 재는
대상인 passage가 표현되어 있지 않지만, 속도는 통행에서만 나온다는 것을 registry가
알고 있음. `LOCATION`을 여기에 넣으면 없는 장소를 지어내는 경로가 생기므로 넣지 않음.

### Operator Mapping (factorization)

조각은 `EVENT/trip → AMOUNT/fare`라는 개념 변환만 표현함. 어떤 semantic operator가
그 변환을 수행하는지는 `geoflow/operator_mapping.py`가 정함. 근거는 registry에
이미 있는 정보 세 가지뿐임.

1. 출력 `(CoreConcept, subtype)`을 만들 수 있는 operator인가
2. 입력 node 전부를 port로 받을 수 있는가 (남는 node가 있으면 후보가 아님)
3. 필수 port가 모두 채워지는가

질문 문자열이나 조각 이름은 근거로 쓰지 않음.

measure의 subtype만으로 operator가 유일하게 정해짐.

```text
AMOUNT/speed          → PASSAGE_METRIC     (metric=speed)
AMOUNT/passage_count  → PASSAGE_COUNT
AMOUNT/fare           → TRIP_METRIC        (metric=fare)
AMOUNT/trip_count     → TRIP_COUNT
AMOUNT/revenue        → OPERATION_METRIC   (metric=revenue)
AMOUNT/active_taxi_count → OPERATION_METRIC (metric=active_taxi_count)
AMOUNT/operating_days    → OPERATION_METRIC (metric=operating_days)
PROPORTION/vacant_ratio      → DRIVE_METRIC      (metric=vacant_ratio)
PROPORTION/active_taxi_ratio → OPERATION_METRIC  (metric=active_taxi_ratio)
LOCATION/place        → SCOPE_NAME
```

metric은 소속 개체가 다르면 다른 개념임. 이 구분은 이제 Prompt의 template 선택
규칙이 아니라 **concept subtype과 operator의 EVENT port**가 강제함.

```text
요금   = AMOUNT/fare(trip)              ≠ 수입   = AMOUNT/revenue(operation)
공차율 = PROPORTION/vacant_ratio(drive) ≠ 가동률·운행률 = PROPORTION/active_taxi_ratio(operation)
```

업체 v2 계약은 영업 통계 Tool을 `get_billing_metrics`로 바꾸고 측정값을 `revenue`,
`active_taxi_count`, `active_taxi_ratio`, `operating_days`로 정했음. v1의 영업 시간
(`hours`)·영업 횟수(`operating_count`)는 제공하지 않으므로 IR 어휘에서 뺐고, 그런 질문은
지원 범위 밖(`{"unsupported": true}`)임. v1의 운행률(`operating_ratio`)은 v2 system
prompt의 "가동률(운행률)" 정의에 따라 `active_taxi_ratio`로 옮겼음. 의미 operator 이름
`OPERATION_METRIC`과 EVENT subtype `operation`은 그대로 둠(v2 schema 설명도 "일 단위 택시
영업(operation)"이며, Tool 이름은 registry만 바꾸면 됨).

v2 계약의 다른 변경도 반영했음.

* `get_billing_metrics`는 소속 지역(scope)이 있으면 dimension을 받지 않음. scope가 없으면
  sido·dayofweek만 받음. 두 규칙을 area input 제약으로 적었고(`PARAM_VALUE_FORBIDS_INPUT`,
  `PARAM_VALUE_REQUIRES_INPUT`), 합성과 G4가 같은 규칙을 씀.
* `get_trip_count.dimension_target`(pickup | dropoff | both, 기본 both)은 factor
  `dimension_target`으로 받음. 승차·하차 한쪽 기준이 드러날 때만 넣음.
* pt_date의 `this_week`, `this_month`, `this_year`를 받음. condition_check는 "이번 주/달",
  "올해"를 이 토큰으로 읽고, 로컬 분할은 기간 시작일부터 기준일까지로 풂. 이 풀이(월요일 시작,
  기준일 포함, Asia/Seoul 달력)는 **애플리케이션 정책**이며 TIMS 계약이 아님. 토큰을 그대로
  보내는 호출(legacy)에서는 TIMS가 정한 기간이 쓰이고, 실행 기록의 `interpretation.source`가
  `application_policy`로 남음(`geoflow/periods.py`).
* `PARAM_VALUE_REQUIRES_INPUT`·`PARAM_VALUE_FORBIDS_INPUT`(schema가 받지 않는 scope·dimension
  조합)은 결과 종류 `unsupported`로 분류함.

#### 측정값별 집계 의미 (`geoflow/measures.py`)

TIMS Tool은 `aggregation`을 받지만 모든 측정값에 같은 뜻으로 성립하지 않음. 측정값마다 뜻이
없는 집계와, 하루 단위 호출 값으로 기간 값을 다시 만들 수 있는 집계를 근거 문장과 함께 적음.

| 측정값 | 종류 | 뜻이 없는 집계 | 하루 값으로 합성 |
| --- | --- | --- | --- |
| fare, revenue | 기록마다 값(합계 의미 있음) | - | sum, max, min |
| speed, rpm | 기록마다 값(합계 의미 없음) | sum | max, min |
| passage_count, trip_count | 사건 수 | - | sum |
| vacant_ratio | drive마다 비율 | sum | max, min |
| active_taxi_count | 고유 대수 | sum | 없음 |
| active_taxi_ratio | 집단 비율(활성/등록) | sum | 없음 |
| operating_days | 택시별 기간 집계(업체 v2 README) | - | sum |

* 뜻이 없는 집계(한 단계 aggregation, 구간 안 집계, 구간별 값의 집계)는 합성 전에
  `UNDEFINED_MEASURE_AGGREGATION`(unsupported)으로 거부함.
* 구간별 집계의 일 단위 분해와 한 단계 기간의 일 단위 합성은 이 표를 따름. legacy도 이 수학
  조건은 가정하지 않음. 그래서 활성택시 대수·가동률의 두 단계 집계는 계산하지 않음.
* 로컬 계산은 v2 결과 형식(`{"count": N}`, "30km/h"·"35%" 같은 단위 문자열)을 숫자로 읽고
  단위를 보존함. 단위가 섞이면 `MIXED_UNITS`로 거부함.

`EVENT/passage`와 `AMOUNT/fare`를 붙인 계획은 후보 operator가 없어 합성 단계에서
거부되고, 그래도 빠져나간 경우 G3가 다시 거부함.

Tool 인자 중 개념에서 곧바로 따라오는 것은 LLM이 아니라 이 단계가 유도함.

```text
metric           ← 측정값 concept의 subtype
include_vicinity ← 만들려는 scope subtype이 vicinity_scope인가
```

나머지 인자는 grounding의 factor 중 그 operator가 지원하는 것만 전달함. 조건을
거는 factor를 받는 변환이 하나도 없으면 계획을 만들지 않음(`UNCONSUMED_CONDITION`).
예전에는 `plan.unused_factors`에 적고 실행해서 "법인택시 평균 속도"가 전체 택시로
계산됐음. `taxi_type=all`처럼 조건을 걸지 않는 값과, 개수 Tool에 붙은 `aggregation=sum`
(개수 자체가 합)은 예외임.

### 두 단계 집계: 의미 graph와 실행 계획

집계는 Tool 인자가 아니라 계산 단계로 표현함(`geoflow/aggregation.py`).

```text
지난달 주별 매출 합계의 평균      bucket=week, inner=sum, outer=avg
지난달 주별 매출 평균의 최댓값    bucket=week, inner=avg, outer=max
지난달 전체 매출의 평균           inner=avg
지난달 매출 합계가 가장 큰 주     bucket=week, inner=sum, select=max
```

구간이 있으면 `EVENT_TO_GROUPED_MEASURE`가 중간 개념을 둠. 이 개념은 새 core concept가
아니라 측정값과 같은 `AMOUNT/revenue`이며 `group_by={"bucket": "week"}` 속성과 SUPPORT
role을 가짐.

```text
operation --measure_groups(OPERATION_METRIC, aggregation=sum, 기간·범위·택시 유형)--> revenue_groups
          --combine_groups(REDUCE_GROUPS avg | SELECT_GROUP max)--> revenue
```

compiler가 이것을 실행 단계로 내림. 어떤 호출로 내릴지는 TIMS 계약의 확인 상태
(`geoflow/tims_contract.py`)가 정함. schema와 vendor parameter 정의에 문장으로 있는 항목만
확인된 것으로 보고, mock 동작은 근거로 쓰지 않음.

구간별 집계는 **계산 책임이 다른 두 경로**로 내려감(2026-09-29, `evaluation/design/provider_delegation.md`).

| 경로 | 쓰는 조건 | 검증하는 것 | 맡기는 것 / 정하는 것 |
|---|---|---|---|
| 업체 Tool에 위임(`provider_delegated`): bucket/aggregation/rollup 호출 하나 | Tool이 그 구간·집계 조합을 인자로 받음, `inner_is_aggregation`·`rollup_unweighted`(확인됨). 질문이 구간 정의를 명시했으면 계약이 그 정의를 보장 | Tool 선택, 집계 단계 ↔ 인자 매핑(구간 안 집계 명시), 인자 조합(목록 인자 없음), 조건 보존, scope 출처, 반환값 ↔ 답변 | 질문이 정하지 않은 주 시작일·부분 구간·빈 구간·상대 날짜 기준은 **제공자 정의**(`provider_defined`). 제공자 내부 계산은 검증했다고 주장하지 않음 |
| GeoFlow 로컬 재계산(`local_recomputation`): 구간마다 범위 호출 / 하루마다 호출 후 합성 | 범위: `range_inclusive`. 하루: `single_date` + `day_records:<tool>`, 구간 안 집계가 sum·max·min, 측정값이 하루 값으로 합성 가능(`geoflow/measures.py`), 호출 62회 이하 | 분할이 기간을 빈틈·겹침 없이 덮음, 구성·집계가 구간 안 집계와 같음, 빈 날 처리가 계약과 같음, 조건 보존 | 구간 정의는 질문이 정한 것, 없으면 **애플리케이션 정책**(월요일 시작, 기간 경계에서 자름, 값 없으면 멈춤, Asia/Seoul 기준일) |

* 두 경로는 서로의 근거를 대신하지 않음. 로컬로 다시 만들 수 없다는 이유로 위임 호출을 막지 않고(업체
  100문항 43·98·100), 위임 호출이 가능하다고 로컬 재계산이 같은 값이라고 보지 않음.
* TIMS 기본 계약에서 `range_inclusive`(관찰만)와 `day_records:<tool>`(관찰 또는 미확인)이 확인되지 않았으므로
  **로컬 재계산은 TIMS에서 쓰이지 않음**. 구간 선택("합계가 가장 큰 주"), bucket을 받지 않는 Tool(요금·속도·공차율)의
  구간별 집계는 `UNVERIFIED_TIMS_CONTRACT`(unsupported). 2026-09-29 전 legacy 프로필은 `day_records`를 가정하고
  하루 분할을 실행했음. 이 가정을 없앴음.
* 질문이 구간 정의를 **명시**하면(`geoflow/calendar_terms.py`: "일요일부터 시작하는 주", "온전한 주만", "자료가 없는
  주는 0으로") 의미 graph의 `group_by.calendar`와 `plan.calendar`에 남음. 위임 경로는 계약이 그 정의를 보장할 때만 쓰고,
  아니면 로컬 경로(근거가 있을 때, 그 정의로 분할)로, 둘 다 안 되면 `CALENDAR_REQUIREMENT_UNSUPPORTED`로 멈춤. 제공자 기본값으로
  바꾸지 않음. last_week·this_week에 주 시작 요일을 명시한 한 단계 질문도 같음. 읽지 못한 정의 표현은
  `AMBIGUOUS_CALENDAR_REQUIREMENT`(needs_clarification), 받을 구간이 없는 정의는 `UNCONSUMED_CONDITION`.
* `execution_plan.lowering[<변환>]`에 `path`, `requires`(의존한 계약), `semantics`(구간 정의마다 값과 출처:
  question / provider / application / contract), `delegated`, `checks`, `not_verified`, `rejected`(쓰지 않은 경로와
  이유)가 남음. 위임 호출의 기간 인자는 `date_semantics`에 `responsibility: provider`로 남음.
* 답변은 계산 경로와 답을 읽는 데 필요한 한계만 적음. 위임: "TIMS가 주 구간마다 평균을 구한 뒤 그 값들의 최솟값을
  계산했습니다. 주 시작 요일, 기간 경계에서 잘린 주, 자료가 없는 주의 처리와 상대 기간의 날짜 범위는 TIMS 기준을
  따릅니다." 로컬: 나눈 구간, 구간 기준과 그 출처(질문 / 이 계산의 기준), 구간별 값.
* 명시 기간이 없는 두 단계 질문은 위임 호출에서 기간 인자 없이 부름(vendor: date 생략 시 도구가 통상 기간을 자동 산출).
  로컬 재계산은 기간이 없거나 연속 기간이 아니면 멈춤(`UNRESOLVED_PERIOD`, `UNSUPPORTED_PERIOD_FOR_GROUPING`).
* `--tims-execution strict`는 위임을 허용하지 않음(애플리케이션 구간 정의와 같다는 계약이 있어야 호출 하나로 합침).

구간 안 집계가 질문에 없으면(`bucket=week, rollup=avg`) Tool 기본값(avg)으로 채우지 않고
`AMBIGUOUS_INNER_AGGREGATION`(`outcome=needs_clarification`)으로 되물음. 재질의로 채우지도 않음.
구간이 없는 한 단계 질문은 기존대로 기본값을 쓰고, 답변에 그 사실을 밝힘.

답변에는 기간(로컬에서 푼 날짜 포함), 범위, 택시 유형, 집계 뜻, 계산 경로, 구간별 값이 나옴.
trace의 모든 항목은 `covers`로 의미 단계와 연결됨.

**구조화 집계 grounding(선택).** 기본값은 flat factor(aggregation·bucket·rollup)임.
`--aggregation-grounding structured`를 주면 Planner가 `factors.aggregation_plan`에
`bucket{unit, reducer|unspecified}`와 `result{reducer}|{select}`를 적음. "최댓값"과
"최댓값을 가진 주"를 구분할 수 있음. flat factor와 함께 오면 뜻이 같을 때만 받음
(`AGGREGATION_SOURCE_CONFLICT`). qwen3:8b 비교 평가에서 채택 근거가 없어(조용한 오답 증가)
기본값은 바꾸지 않았음.

```bash
python assistant_cli.py --agent-mode geoflow --aggregation-grounding structured \
  --model qwen3:8b --query "지난달 대구 개인택시 매출 합계가 가장 큰 주는?"
```

설계와 측정 기록: `evaluation/design/tims_lowering_contract.md`,
`evaluation/design/semantic_aggregation_graph.md`.

**조건 보존(선택).** `--condition-check`를 주면 LLM grounding을 검증하기 전에 질문 원문을
닫힌 어휘·문법으로 읽어 날짜와 택시 유형을 다시 정하고, 장소명의 근거를 확인함
(`geoflow/conditions.py`). prompt는 바꾸지 않음. 기본은 끔.

* 조건마다 상태를 남김: `interpreted`(읽고 정함), `conflict`(LLM 값과 달라 질문 표현으로 보정),
  `ambiguous`(확인 요청), `unverifiable`(단서는 있으나 읽지 못해 LLM 값을 보류, 검증 안 됨),
  `absent`(표현도 단서도 없음). 삭제는 LLM 값의 근거 표현이 질문에 없고 그 조건의 단서도 없을
  때만 함. 판단 근거는 `basis`에 남음.
* 날짜: 해석은 Asia/Seoul 기준일로 함. 실행 방식은 condition_check가 아니라 **실행 프로필**이
  정함(아래 "실행 프로필"). 기본(mock legacy)은 상대 토큰·범위를 가정으로 넘기고 검증 요약에
  미검증으로 남김. `--tims-execution strict`면 확인된 TIMS 계약(단일 날짜)만 실행하고 나머지는
  `DATE_EXECUTION_UNVERIFIED`로 멈춤.
* 택시 유형: "개인(용)택시", "법인(용)/회사택시", "전체/모든 택시". `all`은 조건 없음과 실행
  의미가 같음(schema "all=조건 미적용"). 사용자가 "전체"라고 말했는지는 `stated`로 따로 남김.
* 장소: 이름이 질문에 있는지만 확인함. 지역 의미, **장소 누락**, 출발/도착 의미는 확인하지 않음.
  그래서 검증 요약(`verification`)의 `complete`는 언제나 거짓.
* 답변에 "적용 조건"과 "검증 범위" 줄을 붙임. run 기록에 `condition_audit`, `condition_trace`,
  `verification`을 남김.

```bash
python assistant_cli.py --agent-mode geoflow --condition-check \
  --model qwen3:8b --query "2026년 9월 24일 대구 개인택시 수입 합계는?"
```

**실행 프로필(provider별 계약).** 실행 가능한 연산과 lowering 전략은 provider의 계약이 정함
(`geoflow/providers.py`). condition_check·구조화 grounding은 질문 해석 옵션이라 실행 계약을 바꾸지 않음.

* 기본: mock + `--tims-execution legacy`. 질문 표현을 그대로 옮긴 요청 인자(상대 토큰, 사용자가 적은 범위,
  bucket/rollup 위임 호출)의 세부 달력 의미를 **제공자에게 위임**함(`execution_profile.delegation`,
  `delegated_semantics`). 로컬 재계산의 근거(구간별 하루 분할의 기록 계약 `day_records`)는 2026-09-29부터
  가정하지 않음.
* `--tims-execution strict`: 확인된 TIMS 계약만 실행. `0f2daaa`까지의 `--condition-check`가 이 동작이었음
  (그 결과를 재현하려면 `--condition-check --tims-execution strict`).
* `ASSISTANT_TOOL_PROVIDER=reference`: 작은 **합성 데이터**를 실제로 필터링·집계하는 reference provider
  (`reference_provider.py`, `reference_data/`). 자체 계약(양 끝 포함 범위, 택시·일 기록, null=기록 없음,
  평균 분모=레코드 수)을 따르며 TIMS 계약과 별개. 지원하지 않는 인자·도구는 mock으로 넘기지 않고
  `UNSUPPORTED_BY_PROVIDER`. 답변에 합성 데이터와 적용 기간·계산 의미를 표시함. 실제 교통 데이터나
  TIMS 결과가 아님.

```bash
ASSISTANT_TOOL_PROVIDER=reference python assistant_cli.py --agent-mode geoflow \
  --aggregation-grounding structured --query "지난달 가람구 개인택시의 매출 합계가 가장 컸던 주는 언제야?"
```

설계와 검증: `evaluation/design/reference_provider.md`.

설계와 측정 기록: `evaluation/design/condition_verification_scope.md`(이번 정비),
설계와 측정 기록: `evaluation/design/condition_preservation.md`.

### 질문–graph 예시 검색(선택)

structured grounding에 검토된 질문–의미 graph 예시를 해석 문맥으로 붙이는 선택 기능
(논문 §3.4·부록 E.1의 example retrieval 첫 단계). 기본은 끔이며 끄면 prompt가 기존과 byte 단위로 같음.

* 예시 저장소 `geoflow_examples/question_graph_examples.yaml`(16개): 질문, 검토한 grounding, 조건 값 없는
  graph 직렬화, macro, 결과 형태, 집계 칸, 출처. 등록 검증은 `python example_retrieval.py verify`
  (grounding ↔ graph ↔ macro 일치, G1–G5, reference 예시의 실제 계산).
* 검색은 질문 원문 하나로 top-3를 고름(cosine, 점수 내림차순·id 오름차순). 이 환경에는 임베딩 실행
  환경이 없어 **lexical(문자 n-gram TF-IDF) index**를 씀. 임베딩 검색이 아님. 저장소가 바뀌었는데 index가
  그대로면 `RETRIEVAL_INDEX_STALE`로 거부(`python example_retrieval.py build`로 다시 만듦).
* 예시는 prompt에만 들어감. composer는 현재 질문의 grounding만 받고, 예시 graph를 실행하거나 예시의
  조건·값을 옮기는 경로는 없음. 검증·조건 보존·provider 계약은 그대로.
* 실행 기록 `retrieval`에 예시 id·점수·순서·절 hash가 남음.

```bash
ASSISTANT_TOOL_PROVIDER=reference python assistant_cli.py --agent-mode geoflow \
  --aggregation-grounding structured --condition-check --example-retrieval lexical \
  --query "지난달 가람구 개인택시 주별 매출 평균 중 가장 큰 값은?"
```

설계·검증·비교 결과: `evaluation/design/question_graph_retrieval.md`.
모델별 점수(같은 셋, development): `evaluation/retrieval/model_scores_v1.md`.

### 질문에 없는 조건

조각이 optional port를 채우지 못하면 그 인자 없이 실행함.

```text
"평균 택시 요금은?"      → get_trip_metrics(metric=fare)
"대구 평균 택시 요금은?"  → get_place_scope(대구) → get_trip_metrics(metric=fare, scope=...)
```

두 계획 모두 `EVENT_TO_MEASURE`를 쓰며, 앞에 `PLACE_TO_SCOPE`가 붙는지만 다름.
질문에 없는 조건을 임의로 채우지 않으면서 같은 조각으로 두 경우를 처리함.

### Semantic Operator

Template은 실제 Tool 이름을 지정하지 않고 semantic operator만 지정함.

실제 Tool 이름과 argument 이름 binding은 `geoflow/operator_registry.py`에서만 결정함.

```text
RESOLVE_PLACE_SCOPE → get_place_scope
PASSAGE_METRIC      → get_passage_metrics
PASSAGE_COUNT       → get_passage_count
TRIP_COUNT          → get_trip_count
TRIP_METRIC         → get_trip_metrics
DRIVE_METRIC        → get_drive_metrics
OPERATION_METRIC    → get_billing_metrics
SCOPE_NAME          → get_scope_name
```

출발지/도착지 역할 뒤바뀜을 막기 위해 `TRIP_COUNT`의 port binding은 registry에 고정되어 있음.

```text
origin_scope      → scope_pickup
destination_scope → scope_dropoff
```

이 mapping은 LLM이 결정하지 않음.

### Validator

Tool을 호출하기 전에 다음 규칙을 검사함.

```text
G1 ACYCLICITY         dependency graph에 cycle이 없을 것
G2 ROLE_ORDERING      명백한 procedural role 역행이 없을 것
G3 TYPE_COMPATIBILITY operator input/output의 semantic type이 맞을 것
G4 EXECUTABILITY      operator가 registry에 있고 Tool도 사용 가능할 것
G5 CONNECTIVITY       final_node까지 입력이 모두 연결되어 있을 것
G6 SCOPE_PROVENANCE   scope는 source=user 또는 source=tool만 허용
G7 AGGREGATION_SEMANTICS 구간별 값은 구간 안 집계를 명시한 Tool 변환이 만들고
                      분석 연산자 하나가 소비함. bucket/rollup은 의미 graph에 둘 수 없음
```

`G6`는 기존 scope 정책을 IR 수준에서 다시 강제함. `source=user`인 scope는 실제
사용자 발화에 포함된 값이어야 하며, 조각이나 Planner가 만든 scope literal은 거부됨.

조각이 만드는 node의 `source`는 조각 정의가 정하며 `tool` 또는 `derived`만 허용함.
생성 node의 출처를 LLM이 선언하게 두면 Tool이 만들어야 할 scope를 "사용자가 말한
값"으로 위장할 수 있기 때문임. 이 규칙은 macro 로딩 시점에 검사함.

grounding 단계에서도 발화에 없는 scope를 먼저 거부하므로, 실제 실행 경로에서 G6는
2차 방어선임. 실행 단계에서는 `agent_graph.py`와 동일한 known scope 검사를 한 번 더
수행함.

`G3`와 `G4`는 이번 구조에서 오히려 강해짐. operator에 EVENT 의미 port가 생겨
"통행 통계 Tool에 trip 사건이 붙은 계획"을 정적으로 거부할 수 있고, `G4`가 Tool의
parameter 값·조합 제약까지 확인함.

### 장소 조회 실패 시 재계획

`get_place_scope`가 `retryable=true`인 오류를 반환한 경우에 한해 Planner에게
장소 개념의 값 수정을 1회 요청함. 그 밖의 오류는 구조화된 실행 실패로 그대로 반환함.

```text
get_place_scope(name="부산시") → NOT_FOUND   (v2 mock_stub.yaml 기준)
    ↓ Planner에 값 수정 요청 (개념 구조는 그대로)
get_place_scope(name="부산")   → scope:district:2600000000
    ↓
get_trip_metrics(metric=fare, scope=...)
```

재계획에는 다음 제약이 적용됨.

* 최대 1회. 무한 재시도하지 않음
* `RESOLVE_PLACE_SCOPE` 단계의 retryable 오류에만 적용
* 개념 구조 변경 불가. 실패한 장소 개념의 value만 수정 가능
* 실패하지 않은 개념의 값은 직전 값을 그대로 유지함
* 발화에 없던 상위 지역을 새로 붙이면 그 부분만 제거함
* 이전과 동일한 값을 반복하면 거부
* 수정된 grounding도 composer → validator → compiler 전 경로를 다시 통과함

마지막 항목이 핵심임. 재계획은 어떤 guard도 우회하지 않으며, 실패한 시도의
Tool 호출도 실행 trace에 그대로 남음.

세 번째 항목 덕분에 재계획이 측정 대상이나 조건을 함께 바꾸는 일이 구조적으로
불가능함. 예전에는 "같은 template 유지"만 강제했기 때문에 같은 template 안에서
metric이나 dimension이 바뀔 여지가 있었음.

### parameter 동반 제약

혼자 쓰일 수 없는 인자는 operator registry가 선언함. Tool이 `INVALID_ARGUMENT`로
거절할 조합을 실행 전에 걸러 냄. 예전에는 template YAML마다 `slot_requires`로
적어 두었지만, 이는 질문 유형이 아니라 Tool 계약에 속한 제약이므로 registry가
갖는 편이 맞음.

```python
OperatorSpec(
    name=Operator.OPERATION_METRIC,
    param_enums={
        "dimension": frozenset({"dayofweek", "sido"}),
        "aggregation": frozenset({"max", "min", "sum", "avg", "med"}),
        ...
    },
    param_requires={
        "bucket": ("rollup",), "rollup": ("bucket",),
        "order": ("dimension",), "limit": ("dimension",),
    },
)
```

```text
bucket 조건을 쓰려면 rollup 조건도 함께 필요합니다.
OPERATION_METRIC의 dimension은 dayofweek, sido 중 하나여야 하지만 'h3'입니다.
```

같은 검사를 G4가 한 번 더 수행하므로, 계획을 만든 경로와 무관하게 같은 규칙이
적용됨.

### legacy template

`geoflow_templates/*.yaml`과 `geoflow/templates.py`는 질문 유형 template을 하나
고르던 시절의 구현임. **더 이상 실행 경로에 없음.** 12개 template이 어떤 조각
조합으로 옮겨졌는지는 다음과 같음.

| legacy template | 대응 조각 |
| --- | --- |
| `DIRECT_SCOPE_METRIC` | `EVENT_TO_MEASURE` |
| `DIRECT_SCOPE_PASSAGE_COUNT` | `EVENT_TO_MEASURE` |
| `GROUPED_AGGREGATE` | `EVENT_TO_MEASURE` (+ dimension factor) |
| `PLACE_SCOPE_METRIC` | `PLACE_TO_SCOPE` + `EVENT_TO_MEASURE` |
| `VICINITY_SCOPE_METRIC` | `PLACE_TO_SCOPE` + `EVENT_TO_MEASURE` (+ vicinity factor) |
| `PLACE_PASSAGE_COUNT` | `PLACE_TO_SCOPE` + `EVENT_TO_MEASURE` |
| `VICINITY_PASSAGE_COUNT` | `PLACE_TO_SCOPE` + `EVENT_TO_MEASURE` (+ vicinity factor) |
| `TRIP_FARE_METRIC` | `PLACE_TO_SCOPE` + `EVENT_TO_MEASURE` |
| `DRIVE_RATIO_METRIC` | `PLACE_TO_SCOPE` + `EVENT_TO_MEASURE` |
| `OPERATION_METRIC` | `PLACE_TO_SCOPE` + `EVENT_TO_MEASURE` |
| `OD_TRIP_COUNT` | `PLACE_TO_SCOPE` ×2 + `OD_EVENT_TO_MEASURE` |
| `SCOPE_PLACE_NAME` | `SCOPE_TO_PLACE` |

12개 중 9개가 같은 두 조각의 조합임. 남겨 둔 이유는 migration의 근거 자료이자
같은 Tool 계약 위에서 예전 계획과 새 계획을 비교할 수 있기 때문임.
새 코드에서 이 모듈을 import하지 않으며, 그 규칙은
`tests/test_geoflow_composition.py`의 `LegacyIsolationTest`가 확인함.

### 결과 scope의 장소명 변환

집계 결과에 포함된 scope는 `get_scope_name`으로 장소명을 조회해 보여줌.

업체 v2 schema에서는 dimension 결과가 scope 대신 지역명(`{"sigungu": "달서구", "count": ...}`,
`{"pickup": ..., "dropoff": ..., "count": ...}`)을 돌려주고, dimension 없는 개수는
`{"count": N}`임. 이런 결과에는 scope가 없으므로 장소명 조회를 부르지 않음.

```text
대구 시군구별 상위 3개 통행량
- 달서구: 320,822건
- 수성구: 231,200건
```

호출 횟수가 실행 결과의 행 수에 의존하므로 정적 `ExecutionPlan`으로는 표현할 수
없음. 따라서 실행이 성공한 뒤 별도의 bounded 단계로 수행함(`geoflow/labeling.py`).

* 한 답변당 최대 20개까지만 조회함
* 조회에 실패해도 원본 scope를 그대로 보여주고 답변 생성을 계속함.
  표시용 보강이지 분석 결과의 일부가 아니기 때문임
* 이 호출도 실행 trace에 남으며 `phase: labeling`으로 구분됨

사용자가 질문에 직접 적은 scope는 변환하지 않고 그대로 되돌려줌. 사용자가 지정한
식별자를 그대로 보여주는 편이 추적에 유리하기 때문임.

상대 날짜와 metric도 원시값 대신 이름으로 표시함.

```text
last_month → 지난달       this_month → 이번 달       weekend → 주말
active_taxi_count → 활성택시 대수   active_taxi_ratio → 가동률   operating_days → 운행일수
```

### 실행 결과 저장

`geoflow` 모드로 실행하면 `query_raw.json`의 각 record에 `geoflow` 항목이 추가됨.

```text
agent_mode
planner (출력 원문 포함)
template / slots
plan (concepts / transformations / final_node)
validation (검사한 규칙, 실패 규칙, 오류 목록)
execution_plan (ToolStep 목록)
execution (state / trace)
final_answer
error
durations (planner_ms / execution_ms / total_ms)
```

`query_report.md`에는 다음 순서로 기록됨.

```text
질문
↓
Planner (template / slots)
↓
GeoFlow (concepts / transformations)
↓
Validation
↓
Tool Steps
↓
Tool Result
↓
최종 응답
```

`react` 모드의 기존 report 형식은 그대로 유지됨.

### 테스트

새 dependency 없이 표준 라이브러리 `unittest`로 실행함.

```bash
python -m unittest discover -s tests -t .
```

### Grounding·합성 정확도 측정

예전에는 "질문에 맞는 template을 골랐는가" 하나를 쟀음. 지금 Planner는 template을
고르지 않으므로, 논문의 단계 구분을 따라 나눠서 측정함.

기본적으로 Tool은 실행하지 않으므로, gazetteer의 `NOT_FOUND` 같은 실행 단계 잡음을
섞지 않고 semantic parsing 품질만 측정할 수 있음. `--execute`를 주면 합성된 계획을
실제로 실행해 성공률까지 잼.

```bash
python evaluate_planner.py --model qwen3:8b --model gemma4:12b
python evaluate_planner.py --all-models --repeat 3 --execute
```

정답 라벨은 Query YAML에서 읽음. 개념의 `id`는 모델이 정하는 이름이라 정답과 맞출
수 없으므로 의미만 적음.

```yaml
- id: q18_daegu_origin_destination_count
  question: "대구 동성로동에서 출발하여 신천동에 도착한 실차 구간 건수는?"
  expected_concepts:
    - LOCATION/place:SUBCOND
    - LOCATION/place:SUBCOND
    - EVENT/trip:SUPPORT
    - AMOUNT/trip_count:MEASURE
  expected_macros: [PLACE_TO_SCOPE, PLACE_TO_SCOPE, OD_EVENT_TO_MEASURE]
  expected_operators: [RESOLVE_PLACE_SCOPE, RESOLVE_PLACE_SCOPE, TRIP_COUNT]
```

이 key들은 geoflow 모드 측정용이며 `react` 모드와 `query_loader`는 사용하지 않음.

측정 항목은 다음과 같음. 어느 단계에서 어긋났는지 분리해서 볼 수 있음.

| 항목 | 단계 | 의미 |
| --- | --- | --- |
| concept 정확도 | grounding | CoreConcept이 맞은 비율 |
| subtype 정확도 | grounding | `(concept, subtype)`이 맞은 비율 |
| role 정확도 | grounding | `(concept, subtype, role)`이 맞은 비율 |
| macro recall | 합성 | 정답 조각 중 실제로 쓰인 비율 |
| macro 완전 일치 | 합성 | 조각 조합이 정확히 일치한 비율 |
| operator 정확도 | mapping | semantic operator가 맞은 비율 |
| G1~G6 통과율 | 검증 | 합성된 계획이 정적 검증을 통과한 비율 |
| 실행 성공률 | 실행 | `--execute` 시 Tool 실행까지 성공한 비율 |
| 거부 | — | 계획을 만들지 않고 물러선 경우 |
| 역할 순서 | grounding | 승차/하차가 발화 순서와 일치하는지 |
| 평균 지연 | — | Planner 호출 1회 소요 시간 |

출발지·도착지처럼 같은 개념이 둘인 질문이 있으므로 집합이 아니라 다중집합으로
비교함. 정답 라벨이 `[NONE]`인 질의는 "실행 가능한 계획이 만들어지지 않는 것"이
정답이며, Planner가 거부했든 합성이 포기했든 같게 판정함.

합성이 포기한 이유 가운데 "후보 operator는 있는데 필수 input 개념(현재는 지역)이
질문에 없음"은 `MISSING_REQUIRED_INPUT`으로 따로 기록함. d454988까지의 결과에서는
같은 경우가 `NO_OPERATOR`로 남아 있으므로, 옛 run과 status 문자열을 비교할 때
둘을 같은 거부로 봐야 함. 판정(거부, 정답 여부)은 바뀌지 않음.

결과는 `evaluation/planner_accuracy/<run_id>/planner_accuracy.json`에 저장됨.

모델마다 지연 특성이 달라 한 번에 측정하기 어려우므로, 따로 실행한 결과를 하나의
표로 다시 합칠 수 있음.

```bash
python evaluate_planner.py --aggregate
```

`temperature=0`으로 고정하므로 같은 입력에는 같은 출력이 반복됨. `--repeat`은
변동성 측정이 필요한 경우에만 사용함.

### v2 평가셋과 실행기

업체 v2 전환으로 v1 고정 corpus의 intent 36개가 지원 범위 밖이 되었음(registry
`v2_contract.retired`). 그중 aggregation holdout 10개, local aggregation holdout 10개, verifier
holdout 7개의 검사 능력(두 단계 집계, stage-swap, 구간 안 집계 미지정, 대조군, verifier 오류
유형)을 v2에서 뜻이 정해진 측정값(요금·운행일수·공차율·속도)으로 새로 쓴 평가셋을 따로 둠.
기존 corpus와 이력은 그대로임.

| 파일 | 내용 |
| --- | --- |
| `evaluation/v2/paraphrases_holdout_v2.yaml`, `holdout_v2_parents.yaml` | holdout_v2: 42 intent × 3문장. 복원 27, v2 거부 7, v2 경계 8. 기대 결과 answered 26 · needs_clarification 5 · unsupported 11 |
| `evaluation/v2/stub_v2_gold.yaml` | 업체 v2 stub 5문항의 기대 결과·인자 |
| `evaluation/v2/preregistration_v2.md` | 설계 기준, 구성, 중복 점검, 실행 절차, 채점 규칙, 사용 규칙(모델 실행 전 고정) |
| `evaluate_v2.py` | production 기본 설정으로 전체 파이프라인을 격리 실행하고 채점 |
| `evaluation/v2/label_revisions.yaml` | 기대 결과의 정책 개정 r1(2026-09-29 위임/로컬 책임 분리). 9 intent: 로컬 재계산 근거 없음 answered→unsupported 7, 업체 bucket 위임 unsupported→answered 2. 사전 등록 파일은 그대로이며 기록에 `expected_outcome_prereg`가 남음 |

문항·라벨은 Claude가 작성했고 **사람이 검토하지 않았음**(registry `review.status: unreviewed`).
이 평가셋의 결과는 잠정치로 봐야 함.

채점은 실행 완료(답을 내야 할 문항에서 답을 냄), 의미 정답(결과 종류·측정값·라벨·집계 의미·
최종 Tool 인자·조건·답변 형식이 모두 맞음), 거부 정확도(strict: 기대한 종류로 멈춤, lenient: 답하지
않음)를 분모와 함께 나눠 보고함. 장소 인자는 mock gazetteer scope로 비교해 별칭(대구 = 대구시)은
같고, 재계획으로 장소가 바뀐 경우(대구 동성로동 → 동성로 도로)는 실행에 성공해도 오답임.

```bash
python evaluate_v2.py run --model qwen3:8b --sets stub --label v2_stub_qwen3_8b
python evaluate_v2.py run --model qwen3:8b --sets holdout_v2 --label v2_holdout_qwen3_8b
python evaluate_v2.py analyze evaluation/v2/runs/<run_id>
```

### v2 실측 결과 (잠정치)

아래 수치는 개정 r1 이전의 기대 결과와 코드(`962432d`)로 채점한 것임. r1 이후 같은 관측을 다시 채점하지 않았음.

2026-09-29, `qwen3:8b`(digest `500a1f067a9f`, 8.2B Q4_K_M), Ollama 0.34.4, production 기본 설정(flat,
condition_check 끔, mock + legacy, 예시 검색 끔), temperature 0, think=auto, 기준일 2026-09-25(Asia/Seoul).
평가셋은 사람이 검토하지 않았으므로 **잠정치**임. mock 고정값으로 실행했으므로 실제 데이터의 수치
정확도가 아니라 결과 종류·측정값·집계 의미·Tool 인자·답변 형식을 채점함. 모든 수치는 문장(관측) 단위.

| 평가셋 | 의미 정답 | 실행 완료(answered 기대) | answered 기대 의미 정답 | 거부 strict | 보조: 답하지 않음 |
| --- | --- | --- | --- | --- | --- |
| stub v2 (개발용, 5) | 3/5 | 4/5 | 3/5 | - | - |
| holdout_v2 (126) | 52/126 (41.3%) | 46/78 (59.0%) | 42/78 (53.8%) | 10/48 (20.8%) | 42/48 (87.5%) |

holdout_v2 기대 결과별 문장 정답: answered 42/78, needs_clarification 0/15, unsupported 10/33.
intent 단위(세 문장 모두 정답)는 10/42. 절별 문장 정답은 A(aggregation 복원) 7/30, B(local aggregation
복원) 8/30, C(verifier 복원) 16/21, D(v2 거부) 9/21, E(v2 경계) 12/24이고, stage-swap 대상 두 단계
answered 문항은 9/33, 구간 없는 대조군은 21/21임.

주요 실패: 월 단위 기간을 `"202607-202608"`처럼 YYYYMM으로 적어 grounding 검증에서 거부(28문장), 명시된
구간 안 집계 누락(15), 구간 안 집계가 없는 질문에 집계를 지어냄(needs_clarification 0/15), 모델이
`{"unsupported": true}`를 한 번도 내지 않음(0/126, 올바른 거부 10건은 모두 제품 검사), 그룹 단어를
장소로 만듦(4). 답변 형식 오류는 0건. 거부 기대 문장에서 "답하지 않음"은 보조 지표이며 올바른
unsupported 판정이 아님(그중 23건은 planner 단계 실패).

기록: `evaluation/v2/runs/20260929_014313_v2_holdout_qwen3_8b/`(meta, observations, summary,
report, analysis), `evaluation/v2/runs/20260929_014032_v2_stub_qwen3_8b/`. holdout_v2는 이 결과를 열람했으므로
development로 바뀌었음. 이 결과로 prompt·검색·조건 보정을 바꾸면 그 개선의 최종 평가에는 새 holdout이
필요함.

아래 v1 결과와 직접 비교할 수 없음: 계약(측정값 어휘, Tool 이름, scope·dimension 규칙), 질의 목록(v1 stub
14건 + boundary 24건 vs v2 stub 5건 + holdout_v2 126문장), 채점 범위(v1은 planner·합성 단계, v2는 실행과
답변까지), 격리 절차가 다름.

### 업체 100문항 평가 (2026-09-29)

업체 100문항(`assistant_univ_questions_100_v3.yaml`)과 업체 정답(`evaluation/vendor100/질문 결과 및 정답 설명_100문항.xlsx`)으로
`evaluate_vendor100.py`가 세 층을 따로 잰다. 설계·해석: `evaluation/design/provider_delegation.md`.

| 층 | 변경 전 `962432d` | 변경 후 |
|---|---|---|
| Mock·단위 테스트(LLM 없음) | 934 통과 | 969 통과 |
| 정답 grounding 기반(LLM 없음, 업체 정답 호출과 Tool·인자·scope 출처·답변 값 일치) | 97/100 (43·98·100 거부) | 100/100 |
| 명시 구간 정의 변형 7문항(정책 기대) | 0/7. 3문항은 명시 정의를 무시하고 답함(v014·v057·v063), 4문항은 다른 이유(`UNVERIFIED_TIMS_CONTRACT`)로 거부 | 7/7 |
| 실제 LLM 전체 실행(qwen3:8b, 격리) | 65/100 | 65/100 (100이 거부 → 위임, 단 LLM 인자 오류로 불일치) |

* 정답 인자는 기본값(taxi_type=all 등, aggregation=avg)과 생략을 같게 채점함(업체가 14·15·17·43에서 생략을 정상 판정).
* xlsx와 yaml의 질문 100/100 일치, 정답 호출 schema 위반 0건. `query_loader`는 id `010`을 `"8"`로 읽음(YAML 8진수, 미수정).

```bash
python evaluate_vendor100.py extract
python evaluate_vendor100.py gold --out evaluation/vendor100/results/gold_after.json
python evaluate_vendor100.py llm --model qwen3:8b --out evaluation/vendor100/results/llm_after_qwen3_8b.json
```

### 질문 해석 개선 grounding_v1 (2026-09-29)

실제 LLM 실행의 실패 35문항을 원 출력으로 분석하고(의미 오해 28, 형식 위반 4, 둘 다 2, 형식+채점 1) 일반 규칙으로 고쳤다.
설계·분석·결과: `evaluation/grounding_v1/analysis.md`, 사전 등록: `evaluation/grounding_v1/preregistration.md`.

* 조건 계층(`geoflow/conditions.py`)을 CLI 기본으로 켬: 날짜·택시 유형에 더해 운행 상태(실차·공차·대기영업), 단일 최상급의 limit=1,
  실차 구간의 승하차 기준을 질문 원문에서 읽는다(빈 값만 채움, 근거 없는 값만 제거, 감사 기록). 측정값 말이 LLM 측정값과 어긋나면
  확인 요청. `--no-condition-check`로 끔, 답변의 감사 문구는 `--condition-check`일 때만.
* grounding 자리 바로잡기(`normalize_place_concepts`, `hoist_condition_concepts`): 빈 name의 region 이동, 단위 말·"전국" 제외,
  OBJECT/private 등 조건 개념을 factor로. 값을 만들지 않고 `normalizations`에 기록.
* prompt: 두 단계 집계를 집계어 자리로 정하는 규칙, 통행량과 운행 상태 구분(sha256 앞 8자리 db113124 → 238ac8d6). prompt A/B 고정 변형은
  `evaluation/prompt_ab/pinned/v2_db113124`에서 만든다.
* `query_loader`가 YAML id를 원문 문자열로 읽는다(`010`이 `"8"`이 되던 문제).

| qwen3:8b 격리 실측 | B0 `a0d7b18` | 최종 `d090e3c` |
|---|---|---|
| 업체 100문항(개발셋) match / 잘못된 답 / 거부 / 실패 | 65 / 14 / 3 / 18 | 93 / 2 / 2 / 3 |
| 업체 100문항 LLM grounding 정확 | 63 | 90 |
| 독립셋 44 match+기대한 거부 / 잘못된 답 / 실패 | 22 / 7 / 10 | 36 / 4 / 1 |
| 독립셋 LLM grounding 정확 | 22/43 | 35/43 |
| LLM 호출(개발셋, 계획+재질의) / 지연 중앙값 | 122 / 12.3초 | 113 / 12.4초 |

업체 100문항은 개선에 쓴 셋이므로 그 수치는 일반화 성능이 아니다. 독립셋은 Claude가 만든 44문항(미검토)이며 이번 열람으로
development가 되었다. 정답 grounding 기반 실행은 양쪽 모두 100/100, 41+2/43로 같다(차이는 모두 grounding에서 옴).
`evaluate_v2.py`는 사전 등록한 설정(condition_check 끔)을 그대로 쓴다.

### 모델별 정확도

아래부터 이 절 끝까지의 측정 결과는 업체 v2 반영 전(v1 계약, v1 stub 14건,
현재 `evaluation/stub_query_v1.yaml`)의 기록임. v2 계약에서 다시 재지 않았음.

`qwen3.8:27b` 기준 `stub_query.yaml` 14건 + `stub_query_boundary.yaml` 24건.
Ollama(Docker), `temperature=0`, chat timeout 300초. `--execute`로 Mock Provider
실행까지 포함해 측정함.

`stub_query.yaml` (14건)

| 모델 | 크기 | 종합 | concept | subtype | role | macro recall | macro 일치 | operator | G1~G6 | 지연 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `qwen3.8:27b` | 17.7 GB | **14/14** | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 5.2초 |
| `qwen3.5:9b`  |  6.6 GB | **14/14** | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 16.9초 |
| `gemma4:e4b`  |  9.6 GB | 12/14 | 100% | 100% |  97% |  91% |  86% | 100% |  86% | 4.3초 |
| `qwen3:8b`    |  5.2 GB | 12/14 |  98% |  98% |  98% |  80% |  86% | 100% |  86% | 3.7초 |
| `gemma4:12b`  |  7.6 GB | 2/5※ | 100% | 100% | 100% | 100% |  40% | 100% |  40% | 150초 |

※ `gemma4:12b`는 질의당 120~600초가 걸려 전체 셋 측정이 현실적이지 않음. 합성
형태 5가지를 대표로 한 축소 셋으로만 측정함. 자세한 내용은 아래.

`stub_query_boundary.yaml` (24건)

| 모델 | 종합 | concept | subtype | role | macro recall | macro 일치 | operator | G1~G6 | 거부 | 지연 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `qwen3.8:27b` | **24/24** | 100% | 100% | 100% | 100% | 100% | 100% | 88% | 3 | 5.4초 |
| `qwen3.5:9b`  | 22/24 | 100% | 100% | 100% | 100% |  88% | 100% | 79% | 2 | 95.0초 |
| `gemma4:e4b`  | 17/24 | 100% | 100% |  98% |  93% |  71% | 100% | 58% | 4 | 3.9초 |
| `qwen3:8b`    | 17/24 |  94% |  94% |  92% |  82% |  71% | 100% | 67% | 5 | 17.2초 |

종합 판정은 "macro 조합과 operator가 정확히 일치하고 G1~G6를 통과했는가"임.
concept/subtype/role 정확도를 여기에 다시 곱하지 않음. 설계상 질문에 드러나지
않아도 되는 개념이 있기 때문임. "평균 속도"에 passage를 적지 않아도 registry가
유일하게 결정하므로 합성은 성공하며, 그것을 틀렸다고 셀 수 없음.

**operator 정확도가 전 모델·전 질의에서 100%임.** 개념만 맞게 읽으면 어떤 Tool을
부를지는 registry가 결정적으로 해결한다는 뜻이며, operator mapping을 macro에서
분리한 설계의 직접적인 근거임.

`qwen3.8:27b`는 38/38로, 지원 범위 밖 3건까지 정확히 거부함.

실패는 거의 전부 grounding 단계임. concept/subtype 정확도는 94~100%로 높은데
macro 일치가 71~88%로 떨어지는 패턴이 반복됨. 개념 자체는 맞게 읽지만 **구조
표현**에서 어긋남.

```text
od_role 누락          "A에서 출발하여 B에 도착"에서 승하차 구분을 붙이지 않음
                      → 어느 장소를 어느 port에 쓸지 정할 수 없어 AMBIGUOUS_PORT
장소 분해 오류        "부산 초읍동에 위치한 어린이대공원"을 장소 두 개로 쪼갬
                      → region에 넣어야 할 상위 지역을 별도 개념으로 만듦
factor 짝 누락        bucket만 넣고 rollup을 빠뜨림 → MISSING_COMPANION_PARAM
빈 장소명             name이 빈 LOCATION/place → INVALID_PLACE
```

앞의 두 가지가 새 계약에서 새로 생긴 실패 모드임. 예전에는 `origin`/`destination`
이라는 slot 이름 자체가 역할을 알려 주었지만, 지금은 모델이 `od_role` 속성으로
관계를 밝혀야 함. 개념 표현이 자유로워진 대가임.

### 이전 구조와의 비교

예전 측정은 "질문에 맞는 template을 골랐는가" 하나만 쟀고, 5개 모델이 모두
13/13에 가까워 변별이 되지 않았음.

| | 이전 (template 선택) | 현재 (concept grounding + 합성) |
| --- | --- | --- |
| 측정 대상 | template 이름 일치 1개 | grounding·합성·mapping·검증·실행 5단계 |
| `stub_query` 변별 | 5개 모델 중 4개가 만점 | 14/14 ~ 12/14로 갈림 |
| 경계 셋 변별 | `qwen3.8:27b` 22/22 | 24/24 ~ 17/24로 갈림 |
| 평균 지연 | 1.9 ~ 31초 | 3.7 ~ 150초 |

**난도와 비용이 함께 올라갔음.** 출력이 template 이름 + slot에서 concept 목록으로
커지면서 지연이 2~10배 늘었음. 작은 모델일수록 손해가 큼.

`gemma4:12b`는 이 변화로 사실상 사용할 수 없게 됨. 예전에는 31초/질의였으나 지금은
축소 셋 5건 중 3건이 chat timeout 120초를 두 번 모두 넘겨 응답 실패함. 실패 원인은
예전과 같음 — 출력을 `thinking`에만 쓰고 `content`를 비운 채 추론을 끝내지 못함.
다만 **응답한 2건은 grounding이 전 항목 100%였음.** 정확도 문제가 아니라 생성
길이 문제임.

```text
q01 직접 scope 속도      OK        22초
q03 주변 속도            응답 실패  240초 (120초 × 2회)
q22 OD 실차 구간 건수    응답 실패  240초
q24 장소 평균 요금       응답 실패  240초
q30 scope → 장소명       OK         9초
```

### 실행 성공률

`--execute`는 합성된 **첫 계획을 그대로** 실행하므로 런타임의 재계획 복구가 없음.
장소 조회 실패(`동성로길`, `대구시` 등 gazetteer에 없는 이름)는 파이프라인이라면
1회 재계획으로 살아나는 건이므로 따로 셈.

| 모델 | stub 실행 성공 | 그중 재계획 복구 가능한 실패 |
| --- | ---: | ---: |
| `qwen3.8:27b` | 71% | 4건 (전부) |
| `qwen3.5:9b`  | 71% | 4건 (전부) |
| `gemma4:e4b`  | 75% | 4건 (전부) |
| `qwen3:8b`    | 67% | 4건 (전부) |

검증을 통과한 계획의 실행 실패는 **전부 재계획 대상**이었음. 즉 합성이 만든
계획 자체에는 실행을 막는 결함이 없었고, 실패는 gazetteer 이름 불일치뿐이었음.

### 경계 평가 셋

`stub_query.yaml`은 각 질의가 곧바로 합성되도록 구성되어 있어 모델 간 변별력이
낮음. `stub_query_boundary.yaml`은 구분이 어려운 쌍과 지원 범위 밖 질의를 모아
이를 보완함. 정답 라벨이 `[NONE]`인 질의는 계획을 만들지 않는 것이 정답임.

```bash
python evaluate_planner.py --model qwen3:8b --query-file stub_query_boundary.yaml
```

`expected_macros: [NONE]`은 "실행 가능한 계획이 만들어지면 안 됨"을 뜻함.
틀린 계획을 만드는 것보다 포기가 낫다는 설계 주장을 측정하기 위한 것이며,
요약표에서 정상적인 거부(`거부`)와 JSON 응답 실패(`응답 실패`)를 구분해 집계함.

아래는 이 평가 셋으로 **구조 변경 이전에** 발견해 수정한 결함들임. 기록으로
남겨 두며, 지금은 대부분 template이 아니라 concept/factor 층위의 문제로 옮겨졌음.

**1. 주변 포함 여부 혼동** — "동대구역의 평균 속도"(주변 아님)를 주변 포함
template으로 선택함. Prompt가 "근처=vicinity"만 규정하고 역방향 규칙이 없었음.

**2. 필수 slot 날조** — 질문이 답하지 않는 필수 slot을 채우려고 가짜 값을
지어내는 현상이 세 번 관측됨.

```text
gemma4:e4b   place       = {"name": "",       "region": "대구"}
qwen3:8b     destination = {"name": " ",      "region": ""}
qwen3:8b     destination = {"name": "모든 지역", "region": ""}
```

마지막 사례가 특히 중요함. `모든 지역`은 gazetteer에 없어 `NOT_FOUND`로 막혔지만,
실재하는 지명을 넣었다면 확신에 찬 오답이 나왔을 것임. 즉 이 보호는 구조적인 것이
아니라 우연에 기댄 것이었음.

Prompt로 타이르는 대신 날조 압력 자체를 제거함. 질문이 답하지 않는 조건은
optional로 두어 정직하게 비울 수 있게 함.

* `OD_TRIP_COUNT`의 `destination`을 optional로 변경.
  `get_trip_count`는 승차 위치만으로도 집계할 수 있음
* 장소 내부 통행량(`PLACE_PASSAGE_COUNT`)과 그룹화 없는 영업 통계
  (`OPERATION_METRIC`) template 추가. 후자가 없어 Planner가 단일 값 질문에도
  그룹화 template을 고르면서 `dimension: "taxi_type"` 같은 없는 값을 발명했음

도착지가 없는 경우 답변에 그 사실이 드러나도록 함.

```text
대구 동성로 → 신천동 실차 구간 건수: 2,676건
대구 동성로 출발 실차 구간 건수: 1,158건
```

수정 후 `qwen3:8b`, `gemma4:e4b`, `qwen3.8:27b` 모두 12/12이며 기존 셋도 회귀 없음.

### 경계 평가 셋 확장

위 수정으로 거부 기대 질의가 1건만 남아 거부 능력의 측정력이 사라졌으므로, 지원
범위 경계에 걸친 질의를 추가해 22건(거부 기대 7건)으로 늘림.

거부 기대 7건 중 6건은 **Tool은 지원하지만 이를 노출하는 template이 아직 없는**
경우임. 설계상의 경계가 아니라 커버리지 부채임을 구분해 기록함.

```text
b17  도착지만 지정한 trip 집계     OD_TRIP_COUNT는 출발지가 필수
b18  통행량 순위 질의             통행량 template이 order/limit을 노출하지 않음
b19  scope → 장소명 역변환        SCOPE_NAME operator는 있으나 template이 없음
b20  두 지역 비교                단일 template으로 표현 불가
b21  bucket/rollup 2단계 집계     GROUPED_AGGREGATE에 해당 slot이 없음
b22  통행량의 공간 dimension 분포  통행량 template에 dimension이 없음
```

(위 표는 구조 변경 이전 측정임. b17은 현재 지원 범위 안임.)

`qwen3.8:27b` 기준 22/22이며 거부 7건 모두 정확함. b17에서 도착지를 `origin`에
밀어넣지 않고 거부한 것이 특히 중요함.

template 선택 정확도는 slot 값의 정확성을 보지 않으므로 end-to-end로도 확인함.
지원 범위 안 15건 모두 slot과 Tool argument가 정확했음.

```text
공차     → taxi_status=vacant
중간값    → aggregation=med
주말     → date=weekend
지난달    → date=last_month
출발지만  → scope_pickup만 전달, scope_dropoff 없음
```

### 커버리지 부채 해소

거부 기대 질의 중 Tool은 지원하지만 template이 없던 2건을 해소함.

* `SCOPE_PLACE_NAME` 추가 — `SCOPE_NAME` operator가 registry에 등록만 되어 있고
  어떤 template에서도 쓰이지 않던 것을 연결함. 집계 결과에 이름을 붙이는
  labeling 단계와는 목적이 다름. 이쪽은 사용자가 scope를 들고 와 묻는 경우임
* `OPERATION_METRIC`에 `bucket`/`rollup` 추가 — 주·월 단위 2단계 집계.
  새 template을 만들지 않고 기존 template을 확장해 Planner의 선택지를
  늘리지 않음

남은 거부 기대 4건 중 1건은 macro composer 도입으로 해소됨.

```text
b12  도메인 밖 질문             (여전히 경계)
b17  도착지만 지정한 trip 집계   → 해소. 하차 범위만으로도 합성됨
b18  지역 없는 순위 질의        (여전히 경계) get_passage_count는 범위가 필수
b20  두 지역 비교              (여전히 경계) 같은 역할의 장소가 둘이라 모호함
```

`b17`은 "출발지가 필수인 template"이라는 제약이 사라지면서 자연스럽게 지원 범위
안으로 들어옴. 조각이 port 단위로 optional을 다루므로 승차·하차 중 어느 쪽만
주어져도 같은 조각으로 처리됨. 경계 평가 셋의 라벨도 이에 맞춰 갱신함.

`b20`만 구조적 한계임. 두 계획을 합성한 뒤 비교하는 단계가 필요하므로 현재 범위를
벗어남. 지금은 `AMBIGUOUS_PORT`로 합성을 포기함.

측정 한계: 두 평가 셋 모두 정답 template이 하나로 정해지는 질의로 구성됨. 사람도
판단이 갈리는 질의는 포함되어 있지 않음. 또한 `qwen3.8:27b`가 37건 전체에서
결함을 보이지 않아, 이 셋만으로는 더 이상 변별이 되지 않음.

### react 대비 실측 결과

`stub_query.yaml` 13건, 모델 `qwen3:8b`, Mock Provider 기준. macro composer 도입
이전에 측정했으며, LLM 호출 횟수(질의당 1회)와 Tool 호출 경로는 구조 변경 후에도
같음. 다만 grounding 출력이 커져 Planner 1회 호출의 지연은 늘었음.

| | react | geoflow |
| --- | ---: | ---: |
| 정상 실행 | 13/13 | 13/13 |
| LLM 호출 | 42회 | **16회** |
| Tool 호출 | 29회 | 27회 |
| 총 소요 시간 | 125.2초 | **37.1초** |
| scope 환각으로 차단된 호출 | 1회 | 0회 |

react가 차단당한 1회는 `get_trip_count`를 호출하면서 승차 지점 scope를
지어낸 경우임. GeoFlow에서는 scope가 Tool 결과로만 채워지므로 이 경로 자체가
존재하지 않음.

LLM 호출 감소는 model hop마다 다음 Tool을 묻지 않기 때문임. GeoFlow의 16회는
질의당 Planner 1회에 장소 조회 재계획 3회를 더한 값임.

### 현재 제한

* production grounding(flat factor)은 "합계가 가장 큰 주"처럼 구간을 답하는 질문을
  표현할 수 없음. 구조화 집계 표기(`aggregation_plan`)는 정답 grounding 테스트와 이후
  측정할 arm에서만 읽음. 구간 안 집계를 `unspecified`로 둔 기존 corpus golden
  (b21, b24, f03, f13, h12 등)은 새 규칙에서 거부되며 corpus는 고치지 않았음.
* 조각 5개로 `stub_query.yaml`과 `stub_query_boundary.yaml`의 지원 범위 질의가
  모두 처리되지만, 두 계획을 만들어 비교해야 하는 질의(지역 간 비교 등)는 아직
  표현할 수 없음. 지원하지 않는 질의는 오답 대신 계획 생성을 포기함
  (`UNSUPPORTED_QUESTION`, `NO_OPERATOR`, `MISSING_REQUIRED_INPUT`, `AMBIGUOUS_PORT`).
* 조각 합성은 현재 TIMS 도메인에 필요한 범위의 역방향 탐색임. 일반적인 AI
  planning solver가 아니며, 후보가 여럿이면 순위를 매기지 않고 포기함.
  question-graph 예시 검색은 선택 기능으로 붙였음(lexical index, 임베딩 아님. 기본 끔). vector DB는
  구축하지 않음.
* `gemma4:12b`는 새 계약의 출력 길이를 감당하지 못해 축소 셋으로만 측정했고
  경계 셋은 측정하지 못함. 정확도가 아니라 생성 길이 문제이며, 응답한 질의의
  grounding은 전 항목 100%였음.
* 새 구조에서 새로 생긴 실패 모드는 `od_role` 누락과 장소 분해 오류임. 예전에는
  slot 이름이 역할을 알려 주었으나 지금은 모델이 속성으로 관계를 밝혀야 함.
* 재계획은 장소 조회 실패에만, 최대 1회 적용됨. 그 밖의 Tool 오류는 재시도 없이
  구조화된 실행 실패를 반환함. ReAct 모드의 재시도 동작은 기존과 동일하게 유지됨.
* 최종 응답은 코드 기반 format을 사용함. Tool 결과에 없는 수치가 생성되지 않도록
  LLM 문장 생성 단계를 두지 않음. 대신 문장이 react 모드보다 기계적임.
* GeoFlow 모드는 turn 간 대화 맥락을 참조하지 않고 질문 단위로 독립 실행함.
* end-to-end 실행 검증은 `qwen3:8b` 기준임. 정확도는 6개 모델에서 측정했으나
  (위 표), Tool 실행까지 포함한 측정은 Mock Provider 기준임. 실제 TIMS Provider
  로는 모델별로 측정하지 않음.
* Planner는 `content`에 JSON을 쓰는 모델을 전제함. 출력을 `thinking`에만 쓰고
  `content`를 비우는 모델은 사용할 수 없음. 이 경우 오답을 내는 대신
  `PLANNER_CALL_FAILED`로 멈추므로 Tool은 호출되지 않음.
