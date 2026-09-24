# GBTA Assistant

자연어 교통 질의를 입력받아 LLM이 제공된 Tool을 선택하고 필요한 parameter를 구성하여 순차적으로 호출하는 Assistant 프로그램임.

System Prompt와 Tool 정의는 YAML 파일로 관리하며, Ollama의 native Tool Calling 기능을 사용함.

현재 Tool 실행은 Mock Provider를 사용하며, Gazetteer 및 TIMS Tool 호출 과정과 LLM의 순차 Tool Calling 동작을 확인할 수 있음.

## 1. 실행 구조

Assistant의 기본 실행 흐름은 다음과 같음.

```text
자연어 질의
    ↓
Ollama LLM
    ↓
AssistantRuntime
    ↓
AgentGraph
    ↓
Tool 선택 및 Arguments 생성
    ↓
ToolExecutor
    ↓
Tool Handler
    ↓
Mock Tool Result
    ↓
필요 시 다음 Tool 호출
    ↓
최종 응답
```

LLM은 한 번의 질의를 처리하면서 필요한 Tool을 순차적으로 호출할 수 있음.

장소에 대한 scope가 필요한 경우 Gazetteer Tool을 먼저 호출하고, 반환된 scope를 TIMS Tool의 argument로 전달하는 방식으로 동작함.

Tool 실행 결과가 오류인 경우 오류 내용을 LLM에 다시 전달하며, 수정 가능한 오류인 경우 다음 model hop에서 arguments를 변경하여 Tool을 다시 호출할 수 있음.

위 흐름이 기본 실행 모드인 `react`임. 질문을 바로 Tool Calling으로 보내지 않고 명시적인
planning 단계를 먼저 거치는 `geoflow` 모드도 선택할 수 있음. 자세한 내용은
[21. Agent Mode — GeoFlow Planner](#21-agent-mode--geoflow-planner)를 참고함.

## 2. 주요 파일

```text
assistant_cli.py
assistant_runtime.py
agent_graph.py
build.py
mock_responses.py
ollama_client.py
query_loader.py
tool_executor.py
tool_handlers.py

stub_query.yaml

prompts/
├─ system.yaml
└─ geoflow_planner.yaml

schemas/
├─ _common.yaml
├─ gazetteer.yaml
└─ tims.yaml

geoflow/
├─ types.py
├─ errors.py
├─ templates.py
├─ operator_registry.py
├─ validator.py
├─ compiler.py
├─ executor.py
├─ planner.py
├─ answer.py
└─ pipeline.py

geoflow_templates/
├─ direct_scope_metric.yaml
├─ direct_scope_passage_count.yaml
├─ drive_ratio_metric.yaml
├─ grouped_aggregate.yaml
├─ od_trip_count.yaml
├─ place_scope_metric.yaml
├─ trip_fare_metric.yaml
├─ vicinity_passage_count.yaml
└─ vicinity_scope_metric.yaml

tests/
└─ test_geoflow.py

evaluate_planner.py
stub_query_boundary.yaml

requirements.txt
README.md
```

각 파일의 역할은 다음과 같음.

| 파일                       | 역할                                      |
| ------------------------ | --------------------------------------- |
| `assistant_cli.py`       | Assistant CLI 실행, 질의 실행 및 Tool 호출 결과 출력 |
| `assistant_runtime.py`   | Assistant 실행 Runtime 구성                 |
| `agent_graph.py`         | LLM과 Tool 간 순차 호출 및 ReAct 흐름 처리         |
| `build.py`               | YAML System Prompt와 Tool Schema 로드 및 구성 |
| `ollama_client.py`       | Ollama API 연동 및 모델 capability 확인        |
| `tool_executor.py`       | Tool arguments Schema 검증 및 Tool 실행      |
| `tool_handlers.py`       | Tool Provider에 따른 handler 연결            |
| `mock_responses.py`      | Gazetteer/TIMS Mock Tool 응답 제공          |
| `query_loader.py`        | YAML 질의 파일 로드 및 Query ID 선택             |
| `prompts/system.yaml`    | LLM에 전달하는 System Prompt                 |
| `prompts/geoflow_planner.yaml` | GeoFlow Planner 전용 System Prompt  |
| `geoflow/`               | GeoFlow IR, grounding, macro, composer, validator, compiler, executor |
| `geoflow_macros/`        | 재사용 가능한 macro 조각 정의 YAML            |
| `geoflow_templates/`     | (legacy) 예전 질문 유형 template 정의 YAML    |
| `tests/`                 | GeoFlow 및 react mode 회귀 테스트             |
| `evaluate_planner.py`    | 모델별 concept grounding·합성 정확도 측정      |
| `schemas/_common.yaml`   | Tool Schema 공통 정의                       |
| `schemas/gazetteer.yaml` | Gazetteer Tool 정의                       |
| `schemas/tims.yaml`      | TIMS Tool 정의                            |
| `stub_query.yaml`        | 일괄 실행할 자연어 질의 목록                        |
| `stub_query_boundary.yaml` | 합성 경계 평가 셋                           |

## 3. Prompt 및 Tool Schema

LLM에 전달되는 System Prompt와 Tool 계약은 다음 YAML 파일을 기준으로 구성함.

```text
prompts/system.yaml
schemas/_common.yaml
schemas/gazetteer.yaml
schemas/tims.yaml
```

`build.py`는 YAML 파일을 읽어 System Prompt와 Ollama에 전달할 Tool 정의를 생성함.

Tool의 이름, 설명, parameter, required field, enum, default 등의 계약은 `schemas/*.yaml`에서 관리함.

따라서 Tool 정의를 확인하거나 변경할 경우 Python 코드보다 YAML 파일을 우선 확인해야 함.

## 4. Tool Provider

현재 지원하는 Tool Provider는 `mock`임.

별도의 환경변수를 지정하지 않아도 기본적으로 Mock Provider가 사용됨.

필요한 경우 명시적으로 다음과 같이 지정할 수 있음.

```bash
export ASSISTANT_TOOL_PROVIDER=mock
```

Mock Provider는 실제 Gazetteer 또는 TIMS 시스템에 연결하지 않고 프로그램 내부에서 Tool 결과를 반환함.

동일한 Tool과 arguments에 대해 재현 가능한 결과를 반환하도록 구성되어 있음.

일부 Gazetteer 입력은 LLM의 재호출 흐름을 확인할 수 있도록 의도적으로 `NOT_FOUND`를 반환함.

예시는 다음과 같음.

```text
대구시    → NOT_FOUND
대구      → SUCCESS

부산시    → NOT_FOUND
부산      → SUCCESS

동성로길  → NOT_FOUND
동성로    → SUCCESS

동성로동  → NOT_FOUND
동성로    → SUCCESS
```

이 경우 LLM은 Tool Result를 확인한 뒤 장소명을 수정하여 다시 `get_place_scope`를 호출할 수 있음.

## 5. Tool Calling 기본 정책

Assistant 실행에는 Ollama 모델의 native `tools` capability가 필요함.

Tool Calling을 지원하지 않는 모델은 Agent 실행 전에 확인하여 종료함.

Agent는 model hop마다 실행할 Tool을 결정하고 Tool Result를 다시 LLM history에 전달함.

다음 Tool 호출이 필요한 경우 이전 Tool Result를 확인한 후 다음 model hop에서 호출함.

### Scope 사용

Tool의 `scope` argument는 다음과 같은 값만 사용함.

* 사용자 질문에 직접 포함된 `scope:*`
* 이전 Tool 호출 결과에서 반환된 `scope:*`

LLM이 임의로 생성한 scope는 사용하지 않도록 구성되어 있음.

### Tool 오류

주요 Tool 오류 코드는 다음과 같음.

```text
INVALID_ARGUMENT
NOT_FOUND
UNSUPPORTED_COMBINATION
TOOL_ERROR
```

수정 가능한 오류는 `retryable=true`와 함께 반환될 수 있음.

이 경우 LLM은 오류 message를 확인한 뒤 arguments를 수정하여 Tool을 다시 호출할 수 있음.

### 주변 영역

장소의 주변 또는 근처 영역은 별도 Tool이 아니라 `get_place_scope`의 `include_vicinity` parameter를 사용함.

```text
get_place_scope(
    name=...,
    region=...,
    include_vicinity=true
)
```

## 6. 설치

Python 환경에서 dependency를 설치함.

```bash
pip install -r requirements.txt
```

Ollama가 실행 중이어야 하며 사용할 모델이 Ollama에 설치되어 있어야 함.

Ollama 기본 주소는 다음과 같음.

```text
http://localhost:11434
```

## 7. Tool 및 Prompt Build 확인

YAML Prompt와 Tool Schema 구성이 정상인지 확인하려면 다음 명령을 실행함.

```bash
python build.py --strict-enum
```

Schema 또는 Prompt YAML에 문제가 있는 경우 Build 단계에서 오류를 확인할 수 있음.

## 8. Ollama 모델 확인

현재 Ollama에 설치된 모델과 native Tool Calling 지원 여부를 확인할 수 있음.

```bash
python assistant_cli.py --list-models
```

Assistant를 실행하려면 사용할 모델이 Tool Calling을 지원해야 함.

## 9. 단일 질의 실행

자연어 질문 한 건을 직접 입력하여 실행할 수 있음.

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query "대구 지역내 택시들의 평균 속도는?"
```

모델명은 Ollama에 설치된 모델명으로 지정함.

예:

```bash
python assistant_cli.py \
  --model qwen3-coder:30b \
  --query "대구 지역내 택시들의 평균 속도는?"
```

## 10. YAML 질의 목록 실행

`stub_query.yaml`에 정의된 질문을 순서대로 실행할 수 있음.

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml
```

`stub_query.yaml`은 다음 형식으로 구성됨.

```yaml
- id: q01_edge_average_speed
  question: "2026년 5월 30일 오후 12시에서 1시사이에 scope:edge:1742상의 택시들의 평균 속도는?"
  expected_template: DIRECT_SCOPE_METRIC

- id: q02_edge_passage_count
  question: "2026년 5월 30일 오후 12시에서 1시사이에 scope:edge:19384 지점을 통과하는 차량 대수는 몇대?"
  expected_template: DIRECT_SCOPE_PASSAGE_COUNT
```

각 Query에는 중복되지 않는 `id`와 `question`이 필요함.

`expected_template`은 `evaluate_planner.py`의 정답 라벨로만 사용하는 선택 항목임.
`react` 모드와 `query_loader`는 이 key를 읽지 않음.

## 11. 특정 Query 실행

`stub_query.yaml`에서 필요한 질문만 선택하여 실행할 수 있음.

전체 ID 또는 `qNN` 형태의 단축 ID를 사용할 수 있음.

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml \
  --query-id q22
```

여러 Query를 선택할 경우 `--query-id`를 반복해서 사용함.

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml \
  --query-id q01 \
  --query-id q05 \
  --query-id q22
```

지정한 Query는 입력한 순서대로 실행함.

## 12. 반복 실행

동일한 Query를 여러 번 독립적으로 실행할 수 있음.

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml \
  --query-id q22 \
  --repeat 3
```

기본값은 다음과 같음.

```text
repeat = 1
```

각 Query와 repeat는 새로운 `AssistantRuntime`으로 실행되므로 이전 실행의 message, scope, Tool Result를 공유하지 않음.

## 13. Tool 호출 결과 확인

Assistant 실행 시 질문과 함께 각 Tool 호출 과정이 순서대로 출력됨.

예:

```text
==================================================
q22_daegu_origin_destination_count / Repeat 1
대구 동성로동에서 출발하여 신천동에 도착한 실차 구간 건수는?
==================================================

[Hop 1] get_place_scope
  → name=동성로동
  → region=대구
  ← ERROR | NOT_FOUND

[Hop 2] get_place_scope
  → name=동성로
  → region=대구
  ← SUCCESS | scope=...

[Hop 3] get_place_scope
  → name=신천동
  → region=대구
  ← SUCCESS | scope=...

[Hop 4] get_trip_count
  → scope_pickup=...
  → scope_dropoff=...
  ← SUCCESS

[Final Answer]
...
```

Tool Calling을 확인할 때는 다음 내용을 확인할 수 있음.

* 질문에 적절한 Tool을 선택했는지
* 질문에 포함된 조건이 Tool arguments에 반영되었는지
* 질문에 없는 조건을 임의로 추가했는지
* 앞선 Tool Result를 다음 Tool arguments에 사용했는지
* 출발/도착 등 역할이 유지되었는지
* Tool 오류 발생 후 arguments를 수정하여 재호출했는지
* 불필요한 Tool을 반복 호출했는지

## 14. Model Thinking 출력

모델 thinking 출력 수준은 `--verbose` 옵션으로 지정할 수 있음.

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml \
  --query-id q22 \
  --verbose full
```

또는:

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml \
  --query-id q22 \
  --verbose short
```

## 15. Chat Timeout

Ollama `/api/chat` 요청별 timeout을 설정할 수 있음.

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml \
  --chat-timeout 300
```

환경변수로도 설정 가능함.

```bash
export OLLAMA_CHAT_TIMEOUT=300
```

CLI `--chat-timeout`이 지정된 경우 해당 값이 우선 적용됨.

기본 timeout은 120초임.

## 16. Ollama 주소 변경

기본 Ollama 주소가 아닌 다른 주소를 사용하는 경우 `--ollama-host`를 지정함.

```bash
python assistant_cli.py \
  --ollama-host http://192.168.0.10:11434 \
  --model qwen3:8b \
  --query-file stub_query.yaml
```

환경변수 `OLLAMA_HOST`로도 설정할 수 있음.

## 17. 실행 결과 저장

YAML Query 또는 단일 Query 실행 결과는 다음 경로에 저장됨.

```text
evaluation/
└─ runs/
   └─ <run_id>/
      ├─ query_raw.json
      ├─ query_report.md
      ├─ config/
      │  ├─ prompts/
      │  └─ schemas/
      └─ input/
         └─ stub_query.yaml
```

`evaluation/runs`는 현재 Assistant CLI에서 실행 결과를 저장하는 디렉터리명임.

### query_raw.json

실행 정보를 JSON 형태로 저장함.

주요 내용은 다음과 같음.

* 실행 모델
* Chat timeout
* Query ID 및 질문
* Repeat 번호
* Tool 호출 순서
* Tool arguments
* Tool Result
* 최종 응답
* Runtime error
* 실행 시 사용한 Prompt/Schema 정보

### query_report.md

질문별 Tool 호출 흐름을 사람이 확인하기 쉬운 Markdown 형태로 저장함.

예:

```text
질문
↓
Tool Call
↓
Arguments
↓
Tool Result
↓
다음 Tool Call
↓
최종 응답
```

`query_report.md`는 Tool 호출 흐름을 확인할 때 우선적으로 사용할 수 있음.

## 18. 실행 시 Config 보존

Query 실행 시 사용한 Prompt와 Tool Schema는 실행 결과 디렉터리의 `config/` 아래에 함께 저장됨.

```text
config/
├─ prompts/
│  └─ system.yaml
└─ schemas/
   ├─ _common.yaml
   ├─ gazetteer.yaml
   └─ tims.yaml
```

YAML Query 파일로 실행한 경우 해당 Query 파일도 `input/stub_query.yaml`로 저장됨.

이를 통해 특정 실행에서 어떤 Prompt, Tool Schema, Query를 사용했는지 확인할 수 있음.

## 19. 주요 실행 예시

### 전체 Query 실행

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml
```

### 특정 Query 실행

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml \
  --query-id q05
```

### 여러 Query 선택

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml \
  --query-id q01 \
  --query-id q03 \
  --query-id q22
```

### 직접 질문 입력

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query "부산시의 평균 택시 요금은?"
```

### 반복 실행

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml \
  --query-id q22 \
  --repeat 3
```

### Timeout 변경

```bash
python assistant_cli.py \
  --model qwen3:8b \
  --query-file stub_query.yaml \
  --chat-timeout 300
```

## 20. 요약

Assistant는 자연어 질문을 LLM에 전달하고, LLM이 질문에 필요한 Tool과 arguments를 결정하여 순차적으로 Tool을 호출하는 구조임.

주요 설정은 다음 파일에서 관리함.

```text
System Prompt
→ prompts/system.yaml

Tool Schema
→ schemas/*.yaml

실행 Query
→ stub_query.yaml

Tool Provider
→ tool_handlers.py / mock_responses.py
```

기본 실행은 `assistant_cli.py`를 사용함.

```bash
python assistant_cli.py \
  --model <ollama-model-name> \
  --query-file stub_query.yaml
```

실행 과정에서 Tool 이름, arguments, Tool Result 및 최종 응답을 콘솔과 결과 파일에서 확인할 수 있음.

## 21. Agent Mode — GeoFlow Planner

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
| `EVENT_TO_MEASURE` | `event` EVENT/*, `area` LOCATION/scope(선택) | `measure` AMOUNT\|PROPORTION/* | 사건 → 통계값 |
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
정함. 그룹화·순위(`dimension`, `order`, `limit`)도 별도 조각이 아니라 측정 변환의
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
PROPORTION/vacant_ratio    → DRIVE_METRIC      (metric=vacant_ratio)
PROPORTION/operating_ratio → OPERATION_METRIC  (metric=operating_ratio)
LOCATION/place        → SCOPE_NAME
```

metric은 소속 개체가 다르면 다른 개념임. 이 구분은 이제 Prompt의 template 선택
규칙이 아니라 **concept subtype과 operator의 EVENT port**가 강제함.

```text
요금   = AMOUNT/fare(trip)              ≠ 수입   = AMOUNT/revenue(operation)
공차율 = PROPORTION/vacant_ratio(drive) ≠ 운행률 = PROPORTION/operating_ratio(operation)
```

`EVENT/passage`와 `AMOUNT/fare`를 붙인 계획은 후보 operator가 없어 합성 단계에서
거부되고, 그래도 빠져나간 경우 G3가 다시 거부함.

Tool 인자 중 개념에서 곧바로 따라오는 것은 LLM이 아니라 이 단계가 유도함.

```text
metric           ← 측정값 concept의 subtype
include_vicinity ← 만들려는 scope subtype이 vicinity_scope인가
```

나머지 인자는 grounding의 factor 중 그 operator가 지원하는 것만 전달함. 지원하지
않아 빠진 factor는 `plan.unused_factors`에 남겨 실행 기록에서 확인할 수 있음.

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
OPERATION_METRIC    → get_operation_metrics
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
get_place_scope(name="대구시") → NOT_FOUND
    ↓ Planner에 값 수정 요청 (개념 구조는 그대로)
get_place_scope(name="대구")   → scope:district:2700000000
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

```text
대구 시군구별 상위 3개 통행량
- 수성구: 3,794건
- 중구: 3,590건
- 서구: 3,503건
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
last_month → 지난달       weekend → 주말
operating_count → 영업 횟수   operating_ratio → 영업 운행률
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
- id: q22_daegu_origin_destination_count
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

### 모델별 정확도

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

* 조각 4개로 `stub_query.yaml`과 `stub_query_boundary.yaml`의 지원 범위 질의가
  모두 처리되지만, 두 계획을 만들어 비교해야 하는 질의(지역 간 비교 등)는 아직
  표현할 수 없음. 지원하지 않는 질의는 오답 대신 계획 생성을 포기함
  (`UNSUPPORTED_QUESTION`, `NO_OPERATOR`, `MISSING_REQUIRED_INPUT`, `AMBIGUOUS_PORT`).
* 조각 합성은 현재 TIMS 도메인에 필요한 범위의 역방향 탐색임. 일반적인 AI
  planning solver가 아니며, 후보가 여럿이면 순위를 매기지 않고 포기함.
  question-graph retrieval은 인터페이스만 두었고 vector DB는 구축하지 않음.
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
