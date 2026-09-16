# Vendor Tool Trace Acceptance — 실행 기록

업체가 전달한 13개 질문에 대한 Tool trace acceptance 평가 결과다.
판정 기준은 `evaluation/vendor/vendor_trace_gold.yaml`이며, 재실행 방법은 다음과 같다.

```bash
python evaluate_vendor_trace.py --model qwen3.8:27b --agent-mode geoflow
```

## 보관 중인 실행

| run_id | 모델 | 모드 | 결과 | 용도 |
| --- | --- | --- | --- | --- |
| `20260915_153027` | `qwen3.8:27b` | geoflow | 13/13 | 수정 전 최초 평가 |
| `20260915_153854` | `qwen3.8:27b` | geoflow | **13/13** | 최종 결과 |
| `20260915_153242` | `qwen3.8:27b` | react | 13/13 | 동일 모델 react 대조 |
| `20260915_154431` | `qwen3:8b` | geoflow | **13/13** | 모델을 낮춘 경우 |
| `20260915_154631` | `qwen3:8b` | react | **7/13** | 업체 보고 오류 재현 |
| `20260915_160216` | `qwen3:8b` | geoflow | **39/39** | 최종 검증 (3회 반복) |
| `20260916_162945` | `gemma4:e4b` | geoflow | 13/13 | 모델 비교 |
| `20260916_163049` | `gemma4:e4b` | react | 6/13 | 모델 비교 |
| `20260916_163840` | `qwen3.5:9b` | geoflow | 11/13 | 모델 비교 |
| `20260916_163931` | `qwen3.5:9b` | react | 9/13 | 모델 비교 |
| `20260916_165615` | `gemma4:12b` | geoflow | 10/13 | 모델 비교 (chat-timeout 300) |
| `20260916_165747` | `gemma4:12b` | react | 4/13 | 모델 비교 (chat-timeout 300) |
| `20260916_180034` | `qwen3.8:27b` | react | 13/13 | 독립 재확인 |
| `20260916_180129` | `qwen3.8:27b` | geoflow | 13/13 | 독립 재확인 |
| `20260916_191739` | `qwen3.5:9b` | geoflow | 11/13 | timeout 1800초 재실행 |
| `20260916_204918` | `gemma4:12b` | geoflow | 10/13 | timeout 1800초 재실행 |

## 최종 검증

`20260915_160216`이 미팅 기준 결과다. 13문항 × 3회 = 39/39이며, Tool 호출 84회
전체에서 다음이 0건이다.

```text
질문에 없는 기간(date/time) 생성   scope hallucination
발화에 없는 region 생성            include_vicinity 누락
통행량을 ranking으로 오해          origin/destination binding 오류
```

Q03·Q22·Q24·Q25는 3회 모두 동일한 trace를 생성했다.

## 읽는 순서

`20260915_153854`가 1차 목표의 결과다. 나머지는 그 숫자의 의미를 가늠하기 위한
대조군이다.

`20260915_153027`은 재계획 수정을 넣기 전의 평가다. `qwen3.8:27b`에서는 수정
전에도 13/13이었고, 수정이 필요했던 것은 모델을 낮춘 경우였다. 당시 `qwen3:8b`
geoflow는 12/13으로, "대구시" 조회 실패 후 재계획이 `name=대구, region=시`로
접미사를 지역으로 승격시켜 재조회까지 실패했다. 업체가 지적한 "경상북도" 생성과
같은 병리다.

`qwen3.8:27b`에서는 react도 13/13이다. 즉 업체가 겪은 오류는 ReAct 구조에서
곧바로 발생하는 것이 아니라 모델 성능에 좌우된다. 모델을 `qwen3:8b`로 낮추면
차이가 드러난다.

`20260915_154631`(react / qwen3:8b)의 실패 6건은 업체가 자료에 기록한 오류를
그대로 재현한다.

```text
q04  get_passage_metrics(date=last_week)          질문에 없는 기간
q05  get_passage_metrics(date=last_week)          질문에 없는 기간
q25  get_passage_count(date=last_week)            질문에 없는 기간
q29  get_place_scope(name=부산광역시)              발화에 없는 장소 생성
     get_trip_metrics(date=last_month)            질문에 없는 기간
q22  출처 불명 scope 전달 + 반복 실패
q03  include_vicinity 누락으로 조회 실패
```

같은 질문과 같은 판정 기준에서 `20260915_154431`(geoflow / qwen3:8b)은 13/13이다.
GeoFlow는 이 조건들을 프롬프트로 당부하는 대신 구조로 차단한다.

* 질문에 없는 기간 → 해당 slot이 비어 있으면 argument 자체가 만들어지지 않음
* 발화에 없는 장소 → 재계획이 새로 만든 상위 지역을 제거
* 출처 불명 scope → Validator G6와 executor의 known scope 검사
* `include_vicinity` → template이 고정

## 모델 비교 (2026-09-16 추가)

5종 모두에서 geoflow ≥ react다. geoflow 실패는 모두 Planner LLM이 응답을
반환하지 못한 경우(`ReadTimeout` 또는 `content` 없음)이며, 잘못된 Tool 선택이나
argument hallucination은 한 건도 없었다. react 실패는 Tool 순서 오류, 필수 인자
누락, dependency binding 오류처럼 판단이 어긋난 경우가 대부분이다.

## timeout 재검증

geoflow 실패가 timeout 설정 탓인지 확인하기 위해 chat timeout을 120초에서
1800초로 15배 늘려 재실행했다(`20260916_191739`, `20260916_204918`).
점수와 실패 질문이 모두 동일했고 재실행 내내 GPU는 85~93%로 가동 중이었다.
설정 조정으로 해결되는 문제가 아니라 모델이 생성을 끝내지 못하는 특성이다.

## 주의

이 결과는 13개 질문에 한정된다. `evaluation/vendor/vendor_trace_gold.yaml`에
contract가 있는 질문만 판정할 수 있다.
