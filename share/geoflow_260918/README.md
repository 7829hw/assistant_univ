# GeoFlow 자료 제출 (2026-09-18)

업체가 요청한 두 가지 자료다. 2026-09-17 미팅 자료와는 별개의 건이며, 미팅용
자산(`evaluation/vendor/`)과 분리해 이 폴더에 둔다.

| 요청 | 폴더 |
| --- | --- |
| GeoFlow Graph 예시 (형태를 알고 싶다) | `01_geoflow_graph/` |
| 모델별로 GeoFlow에서 틀린 문제 | `02_geoflow_errors/` |

## 01_geoflow_graph

GeoFlow Graph의 자료구조를 실제 파일로 보여준다.

* `templates/` — template 원본 YAML 12개. 그래프의 모양을 결정하는 파일이다.
* `examples/1_planner_output/` — 질문 13개 각각에 대해 **LLM이 만든 JSON**.
  모델이 출력하는 것은 이게 전부다 (template 이름 + slot).
* `examples/2_geoflow_graph/` — 그 JSON을 template에 끼워 만들어진 **Graph** YAML.
  GeoFlow Plan → 검증 결과 → 실행 계획이 들어 있다.
* `README.md` — 읽는 법과 OD_TRIP_COUNT 예시 해설.

`examples/`는 업체 질문 원문을 `qwen3.8:27b` + geoflow로 실행했을 때
(`evaluation/vendor_runs/20260919_001526`, 13/13) 실제로 남은 기록을 그대로
꺼낸 것이다. 설명을 위해 손으로 쓴 예시가 아니다. 두 폴더로 나눈 것은 LLM이
정하는 부분과 프로그램이 정하는 부분의 경계를 그대로 보이기 위해서다.

## 02_geoflow_errors

업체 13개 질문에 대해 모델 5종을 GeoFlow / ReAct 두 모드로 돌린 결과 중,
GeoFlow에서 오답이 난 5건을 정리했다.

* `README.md` — 모델별 점수, 오답 5건의 원인, ReAct와의 대조
* `vendor_queries.yaml` — 13개 질문 원문
* `reports/` — 오답이 난 두 모델의 질문별 Tool trace 리포트

GeoFlow 오답 5건은 모두 "틀린 답을 냈다"가 아니라 "답을 내지 못하고 중단했다"
이며, 전부 Planner LLM 호출이 응답을 반환하지 못한 경우다. 3건은 최초 계획
호출에서, 2건은 장소 조회 실패 후의 재계획 호출에서 발생했다.

## 판정 기준

두 자료 모두 `evaluation/vendor/vendor_trace_gold.yaml`의 Tool trace contract를
기준으로 한다. 이 파일에 contract가 있는 13개 질문만 판정 대상이다.
