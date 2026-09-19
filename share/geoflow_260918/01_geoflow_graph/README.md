# GeoFlow Graph 예시

요청: "GeoFlow Graph의 형태를 알고 싶다"

이 폴더는 GeoFlow Graph가 실제로 어떤 자료구조인지를 원본 파일로 보여준다.
설명용으로 다시 쓴 그림이 아니라, 코드가 그대로 읽고 실행하는 파일이다.

## GeoFlow Graph는 무엇인가

GeoFlow Graph는 **concept node**(무엇을 다루는가)와 **transformation**(무엇을
무엇으로 바꾸는가)으로 이루어진 방향 비순환 그래프다. Spatial-Agent의 core
concept / functional role 체계를 따르고, TIMS 고유 개념(통행, 실차 구간, 공차
등)은 새 core concept가 아니라 subtype으로 표현한다.

LLM(Planner)이 그래프를 그리지 않는다는 점이 핵심이다. Planner가 생성하는
것은 다음 두 가지뿐이다.

```json
{ "template": "OD_TRIP_COUNT",
  "slots": { "origin": {...}, "destination": {...} } }
```

그래프의 모양 — 어떤 node가 있는지, 어떤 순서로 무엇을 호출하는지, 어떤 인자가
어디에 묶이는지 — 는 template이 결정한다. 그래서 모델을 바꿔도 그래프의 구조는
변하지 않고, 모델이 틀릴 수 있는 지점은 "어떤 template인가"와 "slot에 무엇이
들어가는가"로 좁혀진다.

## 처리 경로

```text
질문
 → Planner(LLM)      template 이름 + slot 값만 생성
 → Template          slot을 채워 typed GeoFlow Plan(=Graph) 생성
 → Validator         G1~G6 규칙 검사
 → Compiler          topological order의 ToolStep 목록으로 변환
 → Executor          Tool 호출, $ref 참조를 앞 단계 결과로 치환
 → Answer            template의 answer 규격으로 문장 생성
```

## 폴더 구성

| 경로 | 내용 |
| --- | --- |
| `templates/` | template 원본 YAML 12개 (`geoflow_templates/`의 사본) |
| `examples/1_planner_output/` | **LLM이 만든 JSON** 13개. 모델이 JSON을 출력하므로 JSON이다 |
| `examples/2_geoflow_graph/` | 그 JSON을 template에 끼워 만들어진 **Graph** 13개. template YAML과 나란히 읽도록 YAML이다 |

`examples/`는 **업체가 전달한 13개 질문 원문**을 `qwen3.8:27b` + geoflow로
실행했을 때 실제로 만들어진 기록이다. 설명을 위해 손으로 쓴 예시가 아니라 실행
기록에서 그대로 꺼낸 것이며, 해당 실행은 13/13 통과했다.

LLM이 하는 일과 프로그램이 하는 일의 경계를 보이기 위해 두 단계를 별도 파일로
나눴다. 같은 질문은 두 폴더에서 파일 이름이 같다.

`1_planner_output/q22_daegu_origin_destination_count.json` — **모델 출력 전부**

```json
{
  "template": "OD_TRIP_COUNT",
  "slots": {
    "origin": {"name": "동성로", "region": "대구"},
    "destination": {"name": "신천동", "region": ""}
  }
}
```

`2_geoflow_graph/<같은 이름>.yaml` — 위 JSON과 template으로 만들어진 결과

```text
geoflow_plan     slot을 채운 GeoFlow Graph  ← "형태"에 해당하는 부분
validation       G1~G6 검사 결과와 topological order
execution_plan   compiler가 만든 Tool 호출 목록
```

`2_geoflow_graph/`의 내용 중 LLM이 정한 것은 template 이름과 slot 값뿐이다.
concept node, transformation, 실행 순서, Tool 인자 binding은 전부 template과
operator registry가 결정한다.

| 파일 이름 (두 폴더 공통) | template | Tool 호출 |
| --- | --- | --- |
| `q01_edge_average_speed` | DIRECT_SCOPE_METRIC | `get_passage_metrics` |
| `q02_edge_passage_count` | DIRECT_SCOPE_PASSAGE_COUNT | `get_passage_count` |
| `q03_station_vicinity_speed` | VICINITY_SCOPE_METRIC | `get_place_scope` → `get_passage_metrics` |
| `q04_daegu_average_speed` | PLACE_SCOPE_METRIC | `get_place_scope` → `get_passage_metrics` |
| `q05_dongseongro_average_speed` | PLACE_SCOPE_METRIC | `get_place_scope` → `get_passage_metrics` |
| `q14_vacant_drive_ratio` | DRIVE_RATIO_METRIC | `get_drive_metrics` |
| `q18_private_revenue_by_day` | GROUPED_AGGREGATE | `get_operation_metrics` |
| `q22_daegu_origin_destination_count` | OD_TRIP_COUNT | `get_place_scope` ×2 → `get_trip_count` |
| `q24_daegu_average_fare` | TRIP_FARE_METRIC | `get_place_scope` → `get_trip_metrics` |
| `q25_busan_park_vicinity_count` | VICINITY_PASSAGE_COUNT | `get_place_scope` → `get_passage_count` |
| `q26_busan_park_vicinity_speed` | VICINITY_SCOPE_METRIC | `get_place_scope` → `get_passage_metrics` |
| `q27_busan_origin_destination_count` | OD_TRIP_COUNT | `get_place_scope` ×2 → `get_trip_count` |
| `q29_busan_average_fare` | TRIP_FARE_METRIC | `get_place_scope` → `get_trip_metrics` |

13건 모두 `validation.status`가 `OK`이고, 선택된 template은
`02_geoflow_errors/vendor_queries.yaml`의 `expected_template`과 13건 전부
일치한다.

### 재계획을 거친 4건

13건 중 4건은 사용자가 말한 이름이 gazetteer에 없어 첫 조회가 `NOT_FOUND`로
실패하고, 재계획이 한 번 돌아 이름을 고친 뒤 성공했다.

| 질문 | 발화 속 이름 | 재계획이 고친 이름 |
| --- | --- | --- |
| q05 | 동성로**길** | 동성로 |
| q22 | 동성로**동** | 동성로 |
| q24 | 대구**시** | 대구 |
| q29 | 부산**시** | 부산 |

이 4건은 `1_planner_output/`과 `2_geoflow_graph/`에 **재계획 후, 실제로 끝까지
실행된 쪽**이 남아 있다. 그래서 파일 속 slot 값이 질문 문장과 다르다.

plan은 시도마다 처음부터 다시 만들어지고 마지막 것만 남으므로, graph 자체에는
재계획 흔적이 남지 않는다. 대신 이 4건의 `2_geoflow_graph/*.yaml` 맨 아래에
`repair` 절을 붙여 시도별 slot과 실패 원인을 함께 두었다. 실행 기록의 `attempts`
를 그대로 옮긴 것이며, graph 본문(`geoflow_plan` / `validation` /
`execution_plan`)과는 분리되어 있다.

```yaml
repair:
  repair_count: 1
  attempts:
  - index: 0
    status: TOOL_ERROR
    slots:
      origin: {name: 동성로동, region: 대구}
      destination: {name: 신천동, region: ''}
    error: 'Tool 오류(get_place_scope/NOT_FOUND): 일치하는 장소 또는 행정구역을 찾을 수 없습니다.'
  - index: 1
    status: OK
    slots:
      origin: {name: 동성로, region: 대구}
      destination: {name: 신천동, region: ''}
```

Tool 호출 단위의 전체 경과는
`evaluation/vendor_runs/20260919_001526/vendor_trace_report.md`의 해당 질문
절에서 볼 수 있다.

재계획도 template → validator → compiler 전 경로를 다시 통과한다. 어떤 guard도
우회하지 않으며, 발화에 없던 상위 지역을 새로 만들어 붙이면 제거된다.

q22는 이 중 유일하게 slot이 두 개인 재계획이다. `origin`과 `destination`을 다시
내놓으면서 어느 쪽이 출발지인지도 유지해야 한다. 작은 모델 2종이 단일 slot
재계획(q05, q29)은 해내면서 q22에서만 재계획 호출을 완결하지 못한 것과 무관하지
않아 보이지만, 단정할 근거는 현재 데이터에 없다.

## 예시: OD_TRIP_COUNT

질문: "대구 동성로동에서 출발하여 신천동에 도착한 실차 구간 건수는?"

### concept node

| id | core concept | subtype | role | source |
| --- | --- | --- | --- | --- |
| `origin` | LOCATION | place | SUBCOND | user |
| `destination` | LOCATION | place | SUBCOND | user |
| `origin_scope` | LOCATION | scope | COND | tool |
| `destination_scope` | LOCATION | scope | COND | tool |
| `trip_count` | AMOUNT | trip_count | MEASURE | tool |

`source`는 값의 출처다. `user`는 발화에서 온 값, `tool`은 Tool이 만든 값이다.
이 구분이 scope provenance 검사(G6)의 근거가 된다. 즉 모델이 `scope:...`
문자열을 스스로 지어내 넣을 자리가 구조적으로 없다.

### transformation

```text
resolve_origin       RESOLVE_PLACE_SCOPE
  inputs   place_name   = origin.name
           place_region = origin.region
  params   include_vicinity = false      ← template 고정값
  outputs  origin_scope

resolve_destination  RESOLVE_PLACE_SCOPE
  inputs   place_name   = destination.name
           place_region = destination.region
  params   include_vicinity = false
  outputs  destination_scope

count_trips          TRIP_COUNT
  inputs   pickup  = origin_scope        ← origin→pickup 고정 binding
           dropoff = destination_scope
  outputs  trip_count

final_node: trip_count
```

### 그래프

```text
origin ──── resolve_origin ────► origin_scope ──┐
 (user)      get_place_scope        (tool)      │
                                                ├─ count_trips ─► trip_count
destination ─ resolve_destination ► destination_scope            get_trip_count
 (user)       get_place_scope        (tool)     │                   (MEASURE)
                                                ┘
```

`origin`이 `pickup`으로, `destination`이 `dropoff`으로 간다는 결정은 template과
operator registry에 있다. 모델은 이 binding에 관여하지 않는다. 업체 자료에서
보고된 출발지/도착지 뒤바뀜이 GeoFlow에서 나타나지 않는 이유다.

### validator 규칙

| 규칙 | 내용 |
| --- | --- |
| G1_ACYCLICITY | transformation 의존관계에 cycle이 없다 |
| G2_ROLE_ORDERING | SUBCOND → COND → SUPPORT → MEASURE 순서를 지킨다 |
| G3_TYPE_COMPATIBILITY | operator가 요구하는 concept/subtype과 실제 node가 맞는다 |
| G4_EXECUTABILITY | 모든 operator가 실제 등록된 Tool로 내려간다 |
| G5_CONNECTIVITY | 모든 node가 final_node까지 연결되고, 생산자 없는 node가 없다 |
| G6_SCOPE_PROVENANCE | scope 값은 발화에 있었거나 Tool이 만든 것이어야 한다 |

검사를 통과하지 못하면 Tool을 한 번도 호출하지 않고 중단한다.

### compiler 출력 (execution_plan)

```text
1  get_place_scope(name=동성로, region=대구, include_vicinity=false)
     → origin_scope
2  get_place_scope(name=신천동, include_vicinity=false)
     → destination_scope
3  get_trip_count(scope_pickup=$ref(origin_scope),
                  scope_dropoff=$ref(destination_scope))
     → trip_count
```

`$ref`는 앞 단계의 결과를 가리키는 참조다. 실행기가 실제 값으로 치환하며, 모델이
중간 결과를 문자열로 옮겨 적는 단계가 없다.

## template 파일 읽는 법

`templates/od_trip_count.yaml`을 예로 들면 다음 블록으로 구성된다.

| 블록 | 역할 |
| --- | --- |
| `required_slots` / `optional_slots` | Planner가 채워야 하는 값과 없어도 되는 값 |
| `slot_types` | slot의 타입 (place / date / time / enum 등) |
| `concepts` | concept node 정의. `source: user`는 slot에서, `source: tool`은 Tool 결과에서 채워진다 |
| `transformations` | operator와 입출력 binding. `params`는 template이 고정하는 인자 |
| `final_node` | 답변이 될 node |
| `answer` | 답변 문장 규격 (kind / label / unit) |

optional slot이 비어 있으면 해당 concept node와 그에 의존하는 transformation이
그래프에서 제거된다. 질문에 기간이 없으면 `date` argument 자체가 만들어지지
않는다는 뜻이며, 업체 자료의 "질문에 없는 `last_week` 생성" 유형이 구조적으로
발생할 수 없는 이유다.

## 재현 방법

`examples/`는 다음 실행의 기록에서 꺼낸 것이다.

```bash
python evaluate_vendor_trace.py --model qwen3.8:27b --agent-mode geoflow
```

결과는 `evaluation/vendor_runs/20260919_001526/`에 있고, `vendor_trace_raw.json`
의 각 record에 있는 `geoflow_graph` 항목이 질문 하나의 기록이다. `examples/`의
파일은 이 항목을 두 단계로 나눠 질문별로 저장한 것이며 내용을 손대지 않았다.

```text
geoflow_graph.planner_output  → 1_planner_output/<id>.json
geoflow_graph.geoflow_plan    ┐
geoflow_graph.validation      ├→ 2_geoflow_graph/<id>.yaml
geoflow_graph.execution_plan  ┘
attempts (재계획이 있던 4건만) → 2_geoflow_graph/<id>.yaml 의 repair 절
```

Graph는 사람이 작성하는 파일이 아니라 실행 산출물이라 원래 실행 기록에는 JSON
으로 남는다. 여기서는 `templates/`의 YAML과 나란히 놓고 보기 좋도록 YAML로
옮겼다. 내용은 같고, 형식을 바꿨을 뿐이다.

`1_planner_output/`의 파일 내용은 모델이 출력한 JSON object 그대로다. 다만
모델이 코드 블록이나 설명 문장을 덧붙인 경우 `parse_planner_json`이 JSON 객체
부분만 추출하므로, 그 바깥 텍스트는 파일에 포함되지 않는다.

Graph 자체를 만드는 경로는 다음과 같다. 별도 도구 없이 저장소의 함수를 그대로
호출한다.

```python
from geoflow.templates import TemplateRegistry
from geoflow import validator as geoflow_validator
from geoflow.compiler import compile_plan

template = TemplateRegistry.from_directory().require(planner_output.template)
plan = template.instantiate(question, planner_output.slots)   # ← GeoFlow Graph
report = geoflow_validator.validate(plan, available_tools=..., user_scopes=...)
execution_plan = compile_plan(plan)
```
