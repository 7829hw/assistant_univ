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
└─ system.yaml

schemas/
├─ _common.yaml
├─ gazetteer.yaml
└─ tims.yaml
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
