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
└─ system.yaml

schemas/
├─ _common.yaml
├─ gazetteer.yaml
└─ tims.yaml

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
| `schemas/_common.yaml`   | Tool Schema 공통 정의                       |
| `schemas/gazetteer.yaml` | Gazetteer Tool 정의                       |
| `schemas/tims.yaml`      | TIMS Tool 정의                            |
| `stub_query.yaml`        | 일괄 실행할 자연어 질의 목록                        |

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

- id: q02_edge_passage_count
  question: "2026년 5월 30일 오후 12시에서 1시사이에 scope:edge:19384 지점을 통과하는 차량 대수는 몇대?"
```

각 Query에는 중복되지 않는 `id`와 `question`이 필요함.

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
