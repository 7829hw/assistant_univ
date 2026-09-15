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
| `geoflow/`               | GeoFlow IR, template, validator, compiler, executor |
| `geoflow_templates/`     | GeoFlow template 정의 YAML                |
| `tests/`                 | GeoFlow 및 react mode 회귀 테스트             |
| `evaluate_planner.py`    | 모델별 template 선택 정확도 측정               |
| `schemas/_common.yaml`   | Tool Schema 공통 정의                       |
| `schemas/gazetteer.yaml` | Gazetteer Tool 정의                       |
| `schemas/tims.yaml`      | TIMS Tool 정의                            |
| `stub_query.yaml`        | 일괄 실행할 자연어 질의 목록                        |
| `stub_query_boundary.yaml` | template 경계 평가 셋                       |

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
GeoFlow Planner (LLM 1회, Tool 미제공)
    ↓
Template 선택 + Slot 채우기
    ↓
Typed GeoFlow Plan
    ↓
GeoFlow Validator (G1~G6)
    ↓
Execution Plan Compiler
    ↓
Deterministic Tool Execution (기존 ToolExecutor 재사용)
    ↓
최종 응답
```

`react` 모드가 model hop마다 다음 Tool을 LLM에게 묻는 것과 달리, `geoflow` 모드는
LLM을 1회만 호출하고 이후 Tool 선택·호출 순서·argument binding을 프로그램이 결정함.

### Planner의 역할 제한

Planner는 Tool Call을 생성하지 않으며 Tool 이름도 출력하지 않음.

Planner가 반환하는 값은 template과 slots뿐임.

```json
{
  "template": "OD_TRIP_COUNT",
  "slots": {
    "origin": {"name": "동성로동", "region": "대구"},
    "destination": {"name": "신천동", "region": ""}
  }
}
```

Planner 출력은 모두 untrusted input으로 취급하며, JSON 파싱 실패·미등록 template·
미정의 slot·형식 불일치는 모두 planner 오류로 처리함.

### Template

`geoflow_templates/*.yaml`은 Prompt용 설명문이 아니라 프로그램이 읽어 GeoFlow Plan을
생성하는 구조화 데이터임.

| Template                     | 개체        | 용도                          |
| ---------------------------- | --------- | --------------------------- |
| `DIRECT_SCOPE_METRIC`        | passage   | 사용자가 scope를 직접 제시한 통행 통계    |
| `PLACE_SCOPE_METRIC`         | passage   | 장소/지역 내부의 통행 통계             |
| `VICINITY_SCOPE_METRIC`      | passage   | 장소 주변(근처/부근) 포함 통행 통계       |
| `DIRECT_SCOPE_PASSAGE_COUNT` | passage   | 사용자 scope 지점의 통행량           |
| `PLACE_PASSAGE_COUNT`        | passage   | 장소/지역 내부의 통행량              |
| `VICINITY_PASSAGE_COUNT`     | passage   | 장소 주변 통행량                   |
| `OD_TRIP_COUNT`              | trip      | 실차 구간 건수(출발지 필수, 도착지 선택)    |
| `TRIP_FARE_METRIC`           | trip      | 택시 요금(fare) 통계              |
| `DRIVE_RATIO_METRIC`         | drive     | 공차율(vacant_ratio)           |
| `OPERATION_METRIC`           | operation | 영업 통계 단일 값                  |
| `GROUPED_AGGREGATE`          | operation | 영업 통계의 dimension 분포         |

Planner Prompt의 template 목록은 이 YAML 정의에서 자동 생성되므로 별도 동기화가 필요 없음.

metric은 소속 개체가 다르면 다른 개념임. 이름이 비슷해도 서로 바꿔 쓰지 않도록
Planner Prompt에 개체별 metric 어휘와 혼동 쌍을 명시함.

```text
요금   = fare(trip)            ≠ 수입   = revenue(operation)
공차율 = vacant_ratio(drive)   ≠ 운행률 = operating_ratio(operation)
```

지원하지 않는 개념은 비슷한 값으로 치환하지 않고 `NONE`을 반환하도록 규정함.

### optional concept

concept에 `optional: true`를 두면 질문에 해당 slot이 없을 때 그 node와 이에
의존하는 transformation이 함께 사라짐.

```text
"평균 택시 요금은?"      → get_trip_metrics(metric=fare)
"대구 평균 택시 요금은?"  → get_place_scope(대구) → get_trip_metrics(metric=fare, scope=...)
```

질문에 없는 조건을 임의로 채우지 않으면서 하나의 template으로 두 경우를 모두
처리하기 위한 장치임.

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
사용자 발화에 포함된 값이어야 하며, template이나 Planner가 만든 scope literal은 거부됨.

실행 단계에서도 `agent_graph.py`와 동일한 known scope 검사를 한 번 더 수행함.

### 장소 조회 실패 시 재계획

`get_place_scope`가 `retryable=true`인 오류를 반환한 경우에 한해 Planner에게
slot 수정을 1회 요청함. 그 밖의 오류는 구조화된 실행 실패로 그대로 반환함.

```text
get_place_scope(name="대구시") → NOT_FOUND
    ↓ Planner에 slot 수정 요청 (같은 template 유지)
get_place_scope(name="대구")   → scope:district:2700000000
    ↓
get_trip_metrics(metric=fare, scope=...)
```

재계획에는 다음 제약이 적용됨.

* 최대 1회. 무한 재시도하지 않음
* `RESOLVE_PLACE_SCOPE` 단계의 retryable 오류에만 적용
* template 변경 불가. slot만 수정 가능
* 이전과 동일한 slot을 반복하면 거부
* 수정된 slot도 template → validator → compiler 전 경로를 다시 통과함

마지막 항목이 핵심임. 재계획은 어떤 guard도 우회하지 않으며, 실패한 시도의
Tool 호출도 실행 trace에 그대로 남음.

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

### Template 선택 정확도 측정

Planner만 호출하고 Tool은 실행하지 않으므로, gazetteer의 `NOT_FOUND` 같은 실행
단계 잡음을 섞지 않고 semantic parsing 품질만 측정할 수 있음.

```bash
python evaluate_planner.py --model qwen3:8b --model gemma4:12b
python evaluate_planner.py --all-models --repeat 3
```

정답 라벨은 Query YAML의 `expected_template`에서 읽음.

```yaml
- id: q22_daegu_origin_destination_count
  question: "대구 동성로동에서 출발하여 신천동에 도착한 실차 구간 건수는?"
  expected_template: OD_TRIP_COUNT
```

`expected_template`은 geoflow 모드 측정용이며 `react` 모드와 `query_loader`는
이 key를 사용하지 않음.

측정 항목은 다음과 같음.

| 항목 | 의미 |
| --- | --- |
| 정확도 | `expected_template`과 일치한 비율 |
| Planner 오류 | JSON 파싱 실패, 미등록 template 등 계약 위반 |
| 역할 순서 | origin/destination이 발화 순서와 일치하는지 |
| 평균 지연 | Planner 호출 1회 소요 시간 |

결과는 `evaluation/planner_accuracy/<run_id>/planner_accuracy.json`에 저장됨.

모델마다 지연 특성이 달라 한 번에 측정하기 어려우므로, 따로 실행한 결과를 하나의
표로 다시 합칠 수 있음.

```bash
python evaluate_planner.py --aggregate
```

`temperature=0`으로 고정하므로 같은 입력에는 같은 출력이 반복됨. `--repeat`은
변동성 측정이 필요한 경우에만 사용함.

### 모델별 template 선택 정확도

`stub_query.yaml` 13건 기준. Tool은 실행하지 않음.

| 모델 | 크기 | 정확도 | Planner 오류 | 역할 순서 | 평균 지연 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `qwen3.8:27b`  | 17.7 GB | 13/13 (100%) | 0  | 2/2 | 3.4초 |
| `gemma4:e4b`   |  9.6 GB | 13/13 (100%) | 0  | 2/2 | 2.5초 |
| `qwen3.5:9b`   |  6.6 GB | 13/13 (100%) | 0  | 2/2 | 14.0초 |
| `qwen3:8b`     |  5.2 GB | 13/13 (100%) | 0  | 2/2 | 1.9초 |
| `gemma4:12b`   |  7.6 GB | 12/13 (92%)  | 1  | 2/2 | 31.0초 |

**template을 잘못 고른 사례는 전 모델에서 한 건도 없음.** 실패는 모두
`PLANNER_CALL_FAILED`, 즉 모델이 JSON 응답 자체를 만들지 못한 경우임.

`gemma4:12b`의 1건은 출력을 `thinking`에만 쓰고 `content`를 비운 채 추론을
끝내지 않아 timeout에 걸린 경우임. 실패한 질의의 thinking을 보면 template을
고르는 대신 실제 택시 요금을 답하려 하고 있음. chat timeout을 300초로 늘려도
동일하게 실패함.

`qwen3:8b`(5.2 GB)가 3배 큰 `qwen3.8:27b`와 같은 13/13을 기록함. template 선택이
모델 규모에 민감하지 않다는 뜻이며, 자유 형식 Tool Calling 대신 "정해진 template
중 택1 + slot 채우기"로 문제를 좁힌 설계 의도와 일치함.

지연은 규모와 상관관계가 약함. `qwen3:8b`(1.9초)가 `qwen3.5:9b`(14.0초)보다 7배
빠름. thinking 분량 차이로 보임.

### 경계 평가 셋

`stub_query.yaml`은 각 질의가 정확히 하나의 template에 대응하도록 구성되어 있어
모델 간 변별력이 없음. `stub_query_boundary.yaml`은 구분이 어려운 쌍과 지원 범위
밖 질의를 모아 이를 보완함.

```bash
python evaluate_planner.py --model qwen3:8b --query-file stub_query_boundary.yaml
```

`expected_template: NONE`은 "지원하는 template이 없으므로 거부해야 함"을 뜻함.
틀린 template을 고르는 것보다 거부가 낫다는 설계 주장을 측정하기 위한 것이며,
요약표에서 정상적인 거부(`거부`)와 JSON 응답 실패(`응답 실패`)를 구분해 집계함.

이 평가 셋으로 다음 결함을 발견해 수정함.

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

측정 한계: 두 평가 셋 모두 정답 template이 하나로 정해지는 질의로 구성됨. 사람도
판단이 갈리는 질의는 포함되어 있지 않음.

### 실측 결과

`stub_query.yaml` 13건, 모델 `qwen3:8b`, Mock Provider 기준.

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

* template 11개로 `stub_query.yaml`과 `stub_query_boundary.yaml`은 모두
  처리되지만, 그 밖의 질의 유형(다중 조건 결합, 시계열 bucket/rollup, 순위 질의,
  도착지만 지정한 trip 집계 등)은 아직 template이 없음. 지원하지 않는 질의는
  오답 대신 `NO_MATCHING_TEMPLATE`으로 거부함.
* 재계획은 장소 조회 실패에만, 최대 1회 적용됨. 그 밖의 Tool 오류는 재시도 없이
  구조화된 실행 실패를 반환함. ReAct 모드의 재시도 동작은 기존과 동일하게 유지됨.
* 최종 응답은 코드 기반 format을 사용함. Tool 결과에 없는 수치가 생성되지 않도록
  LLM 문장 생성 단계를 두지 않음. 대신 문장이 react 모드보다 기계적임.
* GeoFlow 모드는 turn 간 대화 맥락을 참조하지 않고 질문 단위로 독립 실행함.
* end-to-end 실행 검증은 `qwen3:8b` 기준임. template 선택 정확도는 6개 모델에서
  측정했으나(위 표), 실행까지 포함한 전체 경로는 모델별로 측정하지 않음.
* Planner는 `content`에 JSON을 쓰는 모델을 전제함. 출력을 `thinking`에만 쓰고
  `content`를 비우는 모델은 사용할 수 없음. 이 경우 오답을 내는 대신
  `PLANNER_CALL_FAILED`로 멈추므로 Tool은 호출되지 않음.
