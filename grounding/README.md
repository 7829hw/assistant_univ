# grounding — pilot_006 표현 계층(결정 111)

- `grounding_target`: `full`(기본값) | `partial`. `full`이면 trunk `geoflow.planner.GeoFlowPlanner`와 기본 prompt(87048d0c)를 그대로 쓴다.
- 이 패키지는 `execution_spec.SEMANTIC_CODE` 밖이다. Full 경로 지문 `791c4a68`은 바뀌지 않는다(`tests/test_grounding_partial.py`).
- Partial 경로(W3 이식, 원본 `geoflow/partial-grounding` `ab9d215`):
  - `completion.py`: structural completion(subtype → concept, role, source, id). 원본 `geoflow/grounding.py`에서 옮겼고, 원본 `hoist_condition_concepts`의
    "concept 없음 = OBJECT" 변경은 `_tag_condition_object`로 대신한다(`pilot_006_prep/integration/inventory.md` 1.1).
  - `partial_planner.py`: `PartialPlanner(GeoFlowPlanner)` — 조건 대조 전에 completion.
  - `prompts/partial_p0_3.yaml`: P0.3 prompt(원본 `evaluation/partial_grounding/prompts/partial_p0_3.yaml` 바이트 복사, 결합 system prompt sha256 `8b157c9a…`).
  - `partial_fingerprint()`: 위 세 파일의 지문. Partial 셀 meta에 Full 지문과 함께 남긴다.
- W5에서 canonical 계층(`canonical.py`, `full_renderer.py`, `partial_renderer.py`, `validation.py`)을 더한다.
