# GBTA Assistant — GeoFlow Planner

자연어 교통 질의를 Ollama 모델로 해석하고, Gazetteer·TIMS 도구를 조합해 답변하는 Python CLI 프로젝트입니다. `feature/geoflow-planner` 기반의 소스 공유본이며, 과거 실행 결과와 중복 배포 자료는 포함하지 않습니다.

**현재 제공하는 도구 구현은 Mock입니다.** LLM 호출은 실제 Ollama 서버를 사용하지만, 장소 조회와 교통 통계는 `mock_responses.py`의 테스트 데이터입니다. 실제 교통 데이터 조회 서비스나 웹 UI는 포함되어 있지 않습니다.

## 실행 방식

두 가지 모드를 지원합니다. CLI 기본값은 기존 호환성을 위한 `react`이므로, GeoFlow를 실행할 때는 **`--agent-mode geoflow`를 지정**합니다.

- `geoflow`: LLM이 템플릿과 슬롯을 JSON으로 선택합니다. 프로그램이 그래프를 구성·검증·컴파일한 뒤 정해진 순서로 도구를 실행하고 답변을 만듭니다. 모델의 native Tool Calling 기능은 필요하지 않습니다.
- `react`: LLM이 도구 호출과 인자를 순차적으로 생성합니다. Ollama 모델의 `tools` capability가 필요합니다.

GeoFlow 처리 흐름:

```text
질문 → Planner(template + slots) → 템플릿으로 그래프 구성
     → 구조·타입·역할·scope 출처 검증 → 실행 계획 컴파일
     → ToolExecutor → Mock 도구 → 장소명 보완 및 최종 답변
```

Planner의 호출 실패·빈 응답·출력 잘림에는 최대 2회 시도합니다. 실행 중 재시도 가능한 장소 조회 오류에는 슬롯을 수정하는 재계획을 최대 1회 수행합니다. 지원하지 않는 질문은 `NONE` 또는 구조화된 오류로 처리됩니다.

## 설치

Python 3.12 환경에서 검증했습니다. 아래 명령은 저장소 루트에서 실행합니다.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

별도로 Ollama를 설치하고 서버를 실행해야 합니다. 서버 기본 주소는 `http://localhost:11434`입니다. 사용할 모델을 미리 내려받습니다. 다음은 CLI 기본 모델을 사용하는 예시입니다. 모델 실행에 필요한 메모리는 모델과 양자화 설정에 따라 다릅니다.

```bash
ollama serve                       # 서버가 이미 실행 중이면 생략
# 별도 터미널에서 실행
ollama pull qwen3-coder:30b
python assistant_cli.py --list-models
```

다른 설치 모델은 `--model 모델명`으로 지정할 수 있습니다.

## 빠른 실행

단일 GeoFlow 질의:

```bash
python assistant_cli.py \
  --agent-mode geoflow \
  --model qwen3-coder:30b \
  --query "대구 지역내 택시들의 평균 속도는?"
```

예제 질의 전체 또는 특정 질의만 실행:

```bash
python assistant_cli.py --agent-mode geoflow --query-file stub_query.yaml
python assistant_cli.py --agent-mode geoflow \
  --query-file stub_query.yaml --query-id q01 --query-id q03 --repeat 3
```

기존 순차 Tool Calling과 비교:

```bash
python assistant_cli.py --agent-mode react --query-file stub_query.yaml
```

실행마다 `evaluation/runs/<실행 ID>/`에 `query_raw.json`, `query_report.md`, 설정 스냅샷과 YAML 입력 사본을 저장합니다. 결과 폴더는 자동 생성되며 Git에서는 제외됩니다.

### 주요 설정

| 옵션 / 환경변수 | 설명 |
| --- | --- |
| `--model` / `OLLAMA_MODEL` | 모델명. CLI 기본값 `qwen3-coder:30b` |
| `--ollama-host` / `OLLAMA_HOST` | Ollama 주소. CLI 기본값 `http://localhost:11434` |
| `--chat-timeout` / `OLLAMA_CHAT_TIMEOUT` | 요청별 제한 시간(초). 기본값 120 |
| `--agent-mode geoflow\|react` | 실행 방식. 기본값 `react` |
| `--model-think auto\|on\|off` | 모델 thinking 설정. 기본값 `auto`는 모델 기본 동작 사용 |
| `--num-predict` | 응답 1회당 생성 토큰 상한. 생략하면 모델 기본값 사용 |
| `--verbose full\|short` | thinking 출력 수준. 모델 동작 설정과 별개 |
| `--repeat` | 각 질의의 독립 반복 횟수. 기본값 1 |
| `ASSISTANT_TOOL_PROVIDER` | 현재 `mock`만 지원하며 기본값도 `mock` |

CLI에 지정한 모델·주소·제한 시간이 환경변수보다 우선합니다. thinking 설정 지원 여부는 모델에 따라 다릅니다. 전체 옵션은 각 실행 파일의 `--help`로 확인합니다.

### 질의 YAML

최상위는 비어 있지 않은 목록이며, `id`와 `question`은 필수입니다. ID와 질문은 각각 중복될 수 없습니다. `expected_template`은 Planner 평가용 정답입니다.

```yaml
- id: q01_example
  question: "대구 지역내 택시들의 평균 속도는?"
  expected_template: PLACE_SCOPE_METRIC
```

`--query-id`에는 전체 ID 또는 유일하게 대응하는 `q01` 형태의 단축 ID를 사용할 수 있습니다.

## 프로젝트 구성

```text
assistant_cli.py          단일 질의·YAML 배치 실행, 로그 및 보고서 저장
assistant_runtime.py      실행 런타임 및 모드 선택
agent_graph.py            ReAct 그래프, 두 모드가 공유하는 scope 처리
ollama_client.py          Ollama HTTP 클라이언트
build.py                  도구 스키마 검증 및 프롬프트 조립
query_loader.py           질의 YAML 검증 및 선택
tool_executor.py          도구 인자 검증 및 실행
tool_handlers.py          도구 Provider 선택
mock_responses.py         Gazetteer·TIMS Mock 구현
geoflow/                  Planner, 그래프 타입, 검증, 컴파일, 실행, 답변 처리
geoflow_templates/        12종의 실행 그래프 템플릿
prompts/                  ReAct 및 GeoFlow 프롬프트
schemas/                  공통 타입, Gazetteer·TIMS 도구 스키마
stub_query.yaml           기본 예제 및 템플릿 정답
stub_query_boundary.yaml  지원 범위 경계 질의 및 정답
evaluate_planner.py       템플릿 선택·슬롯 역할 평가
evaluate_vendor_trace.py  도구 호출 trace 평가
vendor_trace_contract.py  trace 판정 규칙
evaluation/vendor/        평가 입력 질의 및 정답 계약
tests/                    모델 서버 없이 실행하는 회귀 테스트
requirements.txt          직접 사용하는 Python 의존성
```

`evaluation/vendor/`의 YAML은 테스트와 평가 스크립트의 입력이므로 유지합니다. 과거 보고서·모델 응답, 회의 메모, `share/`의 중복 템플릿·예제는 제거했습니다. `agent_graph.py`와 ReAct 설정은 현재 런타임 및 GeoFlow의 공통 코드 의존성으로 필요합니다.

### GeoFlow 템플릿

| 템플릿 | 용도 |
| --- | --- |
| `DIRECT_SCOPE_METRIC` | 사용자가 지정한 scope의 통행 통계 |
| `DIRECT_SCOPE_PASSAGE_COUNT` | 사용자가 지정한 scope의 통과 차량 수 |
| `PLACE_SCOPE_METRIC` | 장소·지역 내부의 통행 통계 |
| `PLACE_PASSAGE_COUNT` | 장소·지역 내부의 통과 차량 수 |
| `VICINITY_SCOPE_METRIC` | 장소 주변의 통행 통계 |
| `VICINITY_PASSAGE_COUNT` | 장소 주변의 통과 차량 수 |
| `DRIVE_RATIO_METRIC` | 공차 운행 비율 |
| `GROUPED_AGGREGATE` | 요일·지역 등으로 그룹화한 영업 통계 |
| `OD_TRIP_COUNT` | 출발지·도착지 간 실차 구간 건수 |
| `TRIP_FARE_METRIC` | 실차 구간의 요금 통계 |
| `OPERATION_METRIC` | 영업 단위 통계 |
| `SCOPE_PLACE_NAME` | scope에 해당하는 장소명 |

세부 슬롯과 허용 값은 `geoflow_templates/` 및 `schemas/`가 기준입니다.

## 검증 및 평가

Ollama 없이 설정 검증과 회귀 테스트를 실행할 수 있습니다. 테스트는 스크립트로 지정한 모델 응답과 Mock 도구를 사용합니다.

```bash
python build.py --strict-enum
python -m unittest discover -s tests -v
```

`python build.py --dump`를 실행하면 조립된 설정을 `build/`에 저장합니다.

실제 모델의 Planner 평가에는 Ollama 서버가 필요합니다.

```bash
python evaluate_planner.py --model qwen3-coder:30b --repeat 3
python evaluate_planner.py --model qwen3-coder:30b \
  --query-file stub_query_boundary.yaml
python evaluate_planner.py --aggregate
```

결과는 `evaluation/planner_accuracy/`에 저장됩니다. `--aggregate`는 저장된 모델별 최신 결과를 집계합니다. 템플릿 선택 정확도는 실제 교통 데이터의 정확도를 의미하지 않습니다.

도구 호출 순서와 인자를 정답 계약과 비교:

```bash
python evaluate_vendor_trace.py --agent-mode geoflow --model qwen3-coder:30b
```

기본 입력은 `evaluation/vendor/vendor_queries.yaml`과 `vendor_trace_gold.yaml`입니다. 결과는 `evaluation/vendor_runs/`에 저장하며, `--no-save`로 저장을 생략할 수 있습니다.

## 수정·확장 지점

- 모델의 템플릿·슬롯 선택 지침: `prompts/geoflow_planner.yaml`
- 실행 그래프와 슬롯 정의: `geoflow_templates/`
- 연산자와 도구 연결: `geoflow/operator_registry.py`
- 도구 인자 계약: `schemas/`
- 실제 서비스 연동: `tool_handlers.py`에 Provider 및 핸들러를 구현하고, 스키마와 반환값 계약을 맞춥니다. 현재 `mock` 외의 Provider를 지정하면 오류가 발생합니다.

생성 결과, 가상환경, 캐시, 로컬 환경설정과 원본 엑셀 문서는 `.gitignore`로 제외합니다. 공유할 때는 이 브랜치의 소스를 사용하면 됩니다. 이전 커밋의 결과물까지 삭제하는 Git 이력 재작성은 수행하지 않습니다.
