# GBTA Assistant — GeoFlow Planner

자연어 교통 질의를 입력받아 Ollama LLM으로 질문을 해석하고, Gazetteer 및 TIMS Tool을 조합하여 답변하는 Assistant 프로그램임.

LLM이 template과 slot을 선택한 뒤 프로그램이 실행 계획을 구성하는 `geoflow` 모드와, LLM이 Tool을 순차적으로 호출하는 `react` 모드를 지원함.

Prompt, Tool Schema 및 GeoFlow Template은 YAML 파일로 관리함.

현재 Tool 실행은 Mock Provider를 사용하며, 장소 조회와 교통 통계는 프로그램 내부의 테스트 데이터로 반환됨. LLM 호출에는 실제 Ollama 서버를 사용함.

## 1. 실행 구조

GeoFlow 모드의 실행 흐름은 다음과 같음.

```text
자연어 질의
    ↓
Ollama LLM / GeoFlow Planner
    ↓
Template 선택 및 Slot 구성
    ↓
GeoFlow Graph 생성
    ↓
구조·타입·역할·Scope 출처 검증
    ↓
Tool 실행 계획 컴파일
    ↓
ToolExecutor
    ↓
Mock Tool 실행
    ↓
장소명 보완 및 최종 응답
```

Planner는 Tool Call 대신 template 이름과 slot 값을 JSON으로 반환함.

프로그램은 해당 결과를 검증한 뒤 Tool 호출 순서와 arguments를 구성하여 실행함.

기존 ReAct 모드의 실행 흐름은 다음과 같음.

```text
자연어 질의
    ↓
AssistantRuntime / AgentGraph
    ↓
Ollama LLM이 Tool 및 Arguments 선택
    ↓
ToolExecutor → Mock Tool Result
    ↓
필요 시 다음 Model Hop에서 Tool 호출
    ↓
최종 응답
```

CLI 기본 모드는 `react`임. GeoFlow를 실행할 경우 `--agent-mode geoflow`를 명시해야 함.

이 문서의 질의 실행 예시는 GeoFlow 모드를 기준으로 작성함.

## 2. 주요 파일

```text
assistant_cli.py
assistant_runtime.py
agent_graph.py
build.py
ollama_client.py
query_loader.py
tool_executor.py
tool_handlers.py
mock_responses.py

geoflow/
├─ planner.py
├─ templates.py
├─ types.py
├─ validator.py
├─ compiler.py
├─ executor.py
├─ operator_registry.py
├─ labeling.py
├─ answer.py
├─ errors.py
└─ pipeline.py

geoflow_templates/
prompts/
├─ system.yaml
└─ geoflow_planner.yaml

schemas/
├─ _common.yaml
├─ gazetteer.yaml
└─ tims.yaml

stub_query.yaml
stub_query_boundary.yaml
evaluate_planner.py
evaluate_vendor_trace.py
vendor_trace_contract.py
evaluation/vendor/
├─ vendor_queries.yaml
└─ vendor_trace_gold.yaml

tests/
requirements.txt
README.md
```

각 파일 및 디렉터리의 역할은 다음과 같음.

| 파일 / 디렉터리 | 역할 |
| --- | --- |
| `assistant_cli.py` | CLI 실행, Query 선택 및 결과 저장 |
| `assistant_runtime.py` | 실행 모드에 따른 Runtime 구성 |
| `agent_graph.py` | ReAct 흐름 및 두 모드의 공통 Scope 처리 |
| `build.py` | YAML Prompt 조립 및 Tool Schema 검증 |
| `ollama_client.py` | Ollama API 연동 및 모델 capability 확인 |
| `query_loader.py` | Query YAML 검증 및 Query ID 선택 |
| `tool_executor.py` | Tool arguments 검증 및 handler 실행 |
| `tool_handlers.py` | Tool Provider에 따른 handler 연결 |
| `mock_responses.py` | Gazetteer/TIMS Mock 응답 제공 |
| `geoflow/` | Planning, Graph 검증, 컴파일, 실행 및 답변 생성 |
| `geoflow_templates/` | 실행 Graph와 Slot 계약을 정의한 12종 Template |
| `prompts/` | ReAct 및 GeoFlow Planner Prompt |
| `schemas/` | 공통 타입과 Gazetteer/TIMS Tool 계약 |
| `stub_query.yaml` | 기본 질의 및 Template 정답 |
| `stub_query_boundary.yaml` | 지원 범위 경계 질의 및 정답 |
| `evaluate_planner.py` | Template 선택 정확도 및 Slot 역할 평가 |
| `evaluate_vendor_trace.py` | Tool 호출 Trace 평가 |
| `vendor_trace_contract.py` | Trace 판정 규칙 |
| `evaluation/vendor/` | 평가 입력 질의 및 정답 계약 |
| `tests/` | Mock Tool과 지정된 모델 응답을 사용하는 회귀 테스트 |

## 3. Prompt 및 Tool Schema

Prompt와 Tool 계약은 다음 YAML 파일을 기준으로 구성함.

```text
prompts/system.yaml           → ReAct System Prompt
prompts/geoflow_planner.yaml  → GeoFlow Planner 및 재계획 지침
schemas/_common.yaml         → 공통 타입
schemas/gazetteer.yaml       → Gazetteer Tool 정의
schemas/tims.yaml            → TIMS Tool 정의
geoflow_templates/*.yaml     → GeoFlow Graph 및 Slot 정의
```

`build.py`는 System Prompt를 조립하고 Tool Schema를 검증함. GeoFlow Planner는 별도의 Planner Prompt와 Template 목록을 사용함.

Tool 이름, 설명, parameter, required field, enum, default 등의 계약은 `schemas/*.yaml`에서 관리함.

질문 해석 지침은 `prompts/geoflow_planner.yaml`, 실행 Graph와 허용 Slot은 `geoflow_templates/`, 연산자와 Tool의 연결은 `geoflow/operator_registry.py`에서 확인할 수 있음.

## 4. Tool Provider

현재 지원하는 Tool Provider는 `mock`임.

별도의 환경변수를 지정하지 않아도 기본적으로 Mock Provider가 사용됨.

필요한 경우 명시적으로 다음과 같이 지정할 수 있음.

```bash
export ASSISTANT_TOOL_PROVIDER=mock
```

Mock Provider는 실제 Gazetteer 또는 TIMS 시스템에 연결하지 않고 프로그램 내부에서 Tool 결과를 반환함.

장소 조회 결과와 통계값은 테스트 데이터이므로 실제 교통 데이터 분석 결과로 사용하지 않음.

실제 서비스를 연결하려면 `tool_handlers.py`에 Provider 및 handler를 구현하고 Tool Schema와 반환값 계약을 맞춰야 함. 현재 `mock` 이외의 Provider를 지정하면 오류가 발생함.

## 5. 실행 모드 및 Tool 호출 정책

| 모드 | 계획 및 실행 방식 | 모델 요구 사항 |
| --- | --- | --- |
| `geoflow` | LLM이 Template과 Slot을 선택하고 프로그램이 Tool 실행 계획을 구성함 | JSON 응답 생성 가능 모델 |
| `react` | LLM이 Model Hop마다 Tool과 arguments를 결정함 | Native `tools` capability 지원 모델 |

GeoFlow 모드는 모델의 native Tool Calling capability를 요구하지 않음.

ReAct 모드는 실행 전에 `tools` capability를 확인하며, 지원하지 않는 모델은 종료함.

### Scope 사용

Tool의 Scope argument는 다음 출처의 값만 사용하도록 검증함.

* 사용자 질문에 직접 포함된 `scope:*`
* 이전 Tool 호출 결과에서 반환된 `scope:*`

### 오류 및 재시도

GeoFlow Planner의 호출 실패, 빈 응답, 출력 잘림은 최초 호출을 포함하여 최대 2회 시도함.

Tool 실행 중 재시도 가능한 장소 조회 오류가 발생하면 Planner가 해당 Slot을 수정하는 재계획을 최대 1회 수행함.

그 외 검증 및 실행 오류는 구조화된 실패 정보로 반환함. 지원 범위 밖의 질문은 `NONE` 또는 오류로 처리됨.

ReAct 모드는 Tool Result를 LLM history에 전달하며, LLM이 오류 내용을 확인한 뒤 arguments를 수정하여 다시 호출할 수 있음.

### 주변 영역

장소 주변 또는 근처 영역은 `get_place_scope`의 `include_vicinity` parameter로 표현함.

```text
get_place_scope(
    name=...,
    region=...,
    include_vicinity=true
)
```

## 6. 설치

Python 3.12 환경에서 검증하였으며, 저장소 루트에서 다음 명령을 실행함.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

별도로 Ollama를 설치해야 하며, 서버가 실행 중이고 사용할 모델이 설치되어 있어야 함.

```bash
ollama serve
```

서버가 이미 실행 중이면 위 명령은 생략함. 별도 터미널에서 사용할 모델을 내려받음.

```bash
ollama pull qwen3-coder:30b
```

위 모델은 CLI 기본 모델의 예시이며, 실행 환경에 맞는 다른 설치 모델을 `--model`로 지정할 수 있음.

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

`python build.py --dump`를 실행하면 조립된 설정을 `build/`에 저장함.

## 8. Ollama 모델 확인

현재 Ollama에 설치된 모델과 native Tool Calling 지원 여부를 확인할 수 있음.

```bash
python assistant_cli.py --list-models
```

모델명은 Ollama에 설치된 이름으로 지정함. CLI 기본값은 `qwen3-coder:30b`이며, `OLLAMA_MODEL` 환경변수로 변경할 수 있음.

GeoFlow는 native Tool Calling 지원 여부와 관계없이 JSON 생성 모델을 사용할 수 있음. ReAct 실행에는 `tools` capability가 필요함.

## 9. 단일 질의 실행

자연어 질문 한 건을 직접 입력하여 실행할 수 있음.

```bash
python assistant_cli.py \
  --agent-mode geoflow \
  --model qwen3-coder:30b \
  --query "대구 지역내 택시들의 평균 속도는?"
```

모델명은 Ollama에 설치된 모델명으로 지정함.

## 10. YAML 질의 목록 실행

`stub_query.yaml`에 정의된 질문을 순서대로 실행할 수 있음.

```bash
python assistant_cli.py \
  --agent-mode geoflow \
  --model qwen3-coder:30b \
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

`expected_template`을 추가하면 Planner 평가의 정답으로 사용함. 일반 질의 실행에는 필수가 아님.

```yaml
- id: q01_example
  question: "대구 지역내 택시들의 평균 속도는?"
  expected_template: PLACE_SCOPE_METRIC
```

## 11. 특정 Query 실행

`stub_query.yaml`에서 필요한 질문만 선택하여 실행할 수 있음.

전체 ID 또는 `qNN` 형태의 단축 ID를 사용할 수 있음.

```bash
python assistant_cli.py \
  --agent-mode geoflow \
  --model qwen3-coder:30b \
  --query-file stub_query.yaml \
  --query-id q22
```

여러 Query를 선택할 경우 `--query-id`를 반복해서 사용함.

```bash
python assistant_cli.py \
  --agent-mode geoflow \
  --model qwen3-coder:30b \
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
  --agent-mode geoflow \
  --model qwen3-coder:30b \
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

Assistant 실행 시 질문과 함께 Tool 호출 과정 및 최종 응답이 출력됨.

GeoFlow 모드에서는 Planner 출력, 검증 및 실행 계획, 재계획 정보를 함께 확인할 수 있음.

호출 관계의 개념적인 예시는 다음과 같음. 실제 호출 순서는 선택된 Template과 재계획 여부에 따라 달라짐.

```text
출발지 → get_place_scope → 출발지 Scope
도착지 → get_place_scope → 도착지 Scope
                              ↓
                      get_trip_count
                              ↓
                          최종 응답
```

결과를 검토할 때는 다음 내용을 확인할 수 있음.

* 질문에 적절한 Template과 Tool을 선택했는지
* 질문에 포함된 조건이 Slot과 Tool arguments에 반영되었는지
* 질문에 없는 조건을 임의로 추가했는지
* 이전 Tool Result를 다음 Tool arguments에 사용했는지
* 출발지와 도착지의 역할이 유지되었는지
* 오류 발생 후 재계획 또는 재호출이 수행되었는지

## 14. Model Thinking 출력

모델 thinking 출력 수준은 `--verbose` 옵션으로 지정할 수 있음.

```bash
python assistant_cli.py \
  --agent-mode geoflow \
  --model qwen3-coder:30b \
  --query-file stub_query.yaml \
  --query-id q22 \
  --verbose full
```

또는:

```bash
python assistant_cli.py \
  --agent-mode geoflow \
  --model qwen3-coder:30b \
  --query-file stub_query.yaml \
  --query-id q22 \
  --verbose short
```

`--verbose`는 출력 수준만 설정함. 모델의 thinking 동작은 `--model-think`로 지정함.

```bash
python assistant_cli.py \
  --agent-mode geoflow \
  --model qwen3-coder:30b \
  --query-file stub_query.yaml \
  --model-think off \
  --num-predict 4096
```

`--model-think`은 `auto`, `on`, `off`를 지원하며, 기본값 `auto`는 모델 기본 동작을 사용함. 지원 여부는 모델에 따라 다름.

`--num-predict`는 응답 1회당 생성 토큰 상한이며, 생략하면 모델 기본값을 사용함.

## 15. Chat Timeout

Ollama `/api/chat` 요청별 timeout을 설정할 수 있음.

```bash
python assistant_cli.py \
  --agent-mode geoflow \
  --model qwen3-coder:30b \
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
  --agent-mode geoflow \
  --ollama-host http://192.168.0.10:11434 \
  --model qwen3-coder:30b \
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

결과 디렉터리는 실행 시 자동 생성되며 Git에서는 제외됨. YAML 입력을 사용한 경우에만 `input/stub_query.yaml`이 저장됨.

### query_raw.json

실행 정보를 JSON 형태로 저장함.

주요 내용은 다음과 같음.

* 실행 모델 및 Agent Mode
* Chat timeout
* Query ID 및 질문
* Repeat 번호
* Tool 호출 순서
* Tool arguments
* Tool Result
* 최종 응답
* Runtime error
* GeoFlow Planner 출력, Graph, 검증, 실행 계획 및 재계획 기록
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

현재 Config 사본 저장 범위는 `prompts/system.yaml`과 `schemas/*.yaml`임. GeoFlow Planner Prompt와 Template YAML은 이 사본에 포함되지 않으므로, 재현 시 실행에 사용한 소스 버전도 함께 보존해야 함.

## 19. GeoFlow Template

현재 제공하는 Template은 다음과 같음.

| Template | 용도 |
| --- | --- |
| `DIRECT_SCOPE_METRIC` | 사용자가 지정한 Scope의 통행 통계 |
| `DIRECT_SCOPE_PASSAGE_COUNT` | 사용자가 지정한 Scope의 통과 차량 수 |
| `PLACE_SCOPE_METRIC` | 장소 또는 지역 내부의 통행 통계 |
| `PLACE_PASSAGE_COUNT` | 장소 또는 지역 내부의 통과 차량 수 |
| `VICINITY_SCOPE_METRIC` | 장소 주변의 통행 통계 |
| `VICINITY_PASSAGE_COUNT` | 장소 주변의 통과 차량 수 |
| `DRIVE_RATIO_METRIC` | 공차 운행 비율 |
| `GROUPED_AGGREGATE` | 요일·지역 등으로 그룹화한 영업 통계 |
| `OD_TRIP_COUNT` | 출발지·도착지 간 실차 구간 건수 |
| `TRIP_FARE_METRIC` | 실차 구간의 요금 통계 |
| `OPERATION_METRIC` | 영업 단위 통계 |
| `SCOPE_PLACE_NAME` | Scope에 해당하는 장소명 |

세부 Slot, 허용 값 및 조건은 `geoflow_templates/*.yaml`과 `schemas/*.yaml`에서 확인함.

## 20. 테스트 및 모델 평가

### 회귀 테스트

Ollama 서버 없이 다음 명령으로 테스트를 실행할 수 있음.

```bash
python -m unittest discover -s tests -v
```

테스트는 지정된 모델 응답과 Mock Tool을 사용하여 Graph 검증, 실행, 오류 처리 및 Trace 계약을 확인함.

### Planner 평가

실제 Ollama 모델의 Template 선택 정확도와 Slot 역할을 평가함.

```bash
python evaluate_planner.py --model qwen3-coder:30b --repeat 3
python evaluate_planner.py \
  --model qwen3-coder:30b \
  --query-file stub_query_boundary.yaml
```

결과는 `evaluation/planner_accuracy/`에 저장됨. 기존 모델별 최신 결과는 다음 명령으로 집계함.

```bash
python evaluate_planner.py --aggregate
```

Template 선택 정확도는 실제 교통 데이터의 정확도를 의미하지 않음.

### Tool Trace 평가

Tool 호출 순서와 arguments를 정답 계약과 비교함.

```bash
python evaluate_vendor_trace.py \
  --agent-mode geoflow \
  --model qwen3-coder:30b
```

평가 입력과 판정 기준은 다음 파일에서 관리함.

```text
evaluation/vendor/vendor_queries.yaml
evaluation/vendor/vendor_trace_gold.yaml
```

결과는 `evaluation/vendor_runs/`에 저장됨. `--no-save`를 지정하면 결과 저장을 생략함.
