# 모델별 GeoFlow 오답 정리

요청: "모델별로 GeoFlow에서 틀린 문제 공유. GeoFlow에서 정답률이 올라갔지만
그럼에도 오답인 문제가 약점이다"

대상은 업체가 전달한 13개 질문이다. 판정 기준은
`evaluation/vendor/vendor_trace_gold.yaml`의 Tool trace contract이며, 질문 문장은
같은 폴더의 `vendor_queries.yaml`에 그대로 담겨 있다.

## 모델 5종 결과

| 모델 | GeoFlow | ReAct | GeoFlow 오답 |
| --- | --- | --- | --- |
| `qwen3.8:27b` | 13/13 | 13/13 | 없음 |
| `qwen3:8b` | 13/13 | 7/13 | 없음 |
| `gemma4:e4b` | 13/13 | 6/13 | 없음 |
| `qwen3.5:9b` | **11/13** | 9/13 | q22, q26 |
| `gemma4:12b` | **10/13** | 4/13 | q22, q24, q29 |

`qwen3:8b`는 13문항 × 3회 반복에서 39/39다.

## GeoFlow 오답 5건

오답은 두 모델에서만 나왔다. **5건 모두 "틀린 답을 냈다"가 아니라 "답을 내지
못하고 중단했다"이며, 원인은 전부 Planner LLM 호출이 응답을 반환하지 못한
것이다.** 실패한 호출이 최초 계획인지 재계획인지에 따라 아래 두 유형으로
나뉜다. 13문항 전체에서 잘못된 Tool 선택, 질문에 없는 기간 생성, scope 날조,
origin/destination 뒤바뀜은 한 건도 없다.

### 유형 A — 최초 Planner 호출이 응답을 반환하지 못함 (3건)

| 모델 | 질문 | 상태 |
| --- | --- | --- |
| `qwen3.5:9b` | q26 "부산 초읍동에 위치한 어린이대공원 근처의 평균 속도는?" | `ReadTimeout: timed out` |
| `gemma4:12b` | q24 "대구시의 평균 택시 요금은?" | `ReadTimeout: timed out` |
| `gemma4:12b` | q29 "부산시의 평균 택시 요금은?" | `ReadTimeout: timed out` |

Planner 단계에서 멈췄으므로 Tool 호출은 0회다. template 선택도 slot 생성도
이루어지지 않았다. 같은 질문을 `qwen3.8:27b` / `qwen3:8b` / `gemma4:e4b`는
모두 정상 처리한다.

**timeout 설정 문제가 아니다.** chat timeout을 120초에서 1800초로 15배 늘려
재실행했고(`20260916_191739`, `20260916_204918`), 점수와 실패 질문이 모두
동일했다. 재실행 내내 GPU는 85~93%로 가동 중이었다. 설정으로 해결되는 문제가
아니라 해당 모델이 생성을 끝내지 못하는 특성이다.

### 유형 B — 장소 조회 실패 후 재계획 호출이 응답하지 않음 (2건)

| 모델 | 질문 |
| --- | --- |
| `qwen3.5:9b` | q22 "대구 동성로동에서 출발하여 신천동에 도착한 실차 구간 건수는?" |
| `gemma4:12b` | q22 (동일) |

관찰된 trace는 두 모델이 동일하다.

```text
get_place_scope(name=동성로동, region=대구, include_vicinity=false)
  → ERROR / NOT_FOUND "일치하는 장소 또는 행정구역을 찾을 수 없습니다."
(이후 Tool 호출 없음)
```

질문의 "동성로동"은 gazetteer에 없는 이름이다. 정상 처리하는 모델은 GeoFlow의
재계획(1회 한정)을 거쳐 `동성로`로 고쳐 조회에 성공한다.

```text
get_place_scope(name=동성로동, region=대구) → NOT_FOUND
get_place_scope(name=동성로,   region=대구) → scope:edge:1742      ← 재계획
get_place_scope(name=신천동)                → scope:district:2723510100
get_trip_count(scope_pickup=scope:edge:1742,
               scope_dropoff=scope:district:2723510100) → 2,676건
```

`qwen3.5:9b`와 `gemma4:12b`는 이 재계획 단계를 넘지 못했다. 두 모델 모두
**재계획 호출 자체가 응답을 반환하지 못했다.**

```text
attempt 0  Tool 오류로 실행 실패  slots={origin: {name: 동성로동, region: 대구}, ...}
                                 get_place_scope/NOT_FOUND
attempt 1  재계획 호출 실패       PLANNER_CALL_FAILED: ReadTimeout: timed out
```

즉 유형 A와 같은 원인이며, 실패한 호출이 최초 계획이 아니라 재계획이었을 뿐이다.
재계획이 잘못된 장소로 재조회를 시도한 경우는 한 건도 없다.

**왜 하필 q22인가.** 재계획이 필요한 질문은 q22만이 아니다. 13문항 중 4건이
사용자가 말한 이름과 gazetteer 이름이 달라 재계획을 거친다.

| 질문 | 발화 속 이름 | gazetteer 이름 | 고쳐야 할 slot |
| --- | --- | --- | ---: |
| q05 | 동성로**길** | 동성로 | 1개 |
| q24 | 대구**시** | 대구 | 1개 |
| q29 | 부산**시** | 부산 | 1개 |
| q22 | 동성로**동** | 동성로 | **2개** (origin + destination) |

q22만 재계획에서 slot 두 개를 다시 내놓아야 하고, 그러면서 어느 쪽이 출발지인지도
유지해야 한다. 실제 결과가 이 차이를 따라간다.

| 모델 | q05 재계획 | q29 재계획 | q22 재계획 |
| --- | --- | --- | --- |
| `qwen3.8:27b` | 성공 | 성공 | 성공 |
| `qwen3.5:9b` | 성공 | 성공 | **실패** |
| `gemma4:12b` | 성공 | (최초 Planner 호출 실패) | **실패** |

작은 모델 2종이 단일 slot 재계획은 해내면서 q22에서만 재계획을 완결하지 못했다.
재계획 프롬프트에는 직전 출력이 통째로 들어가므로 q22는 입력도 출력도 가장
크다. 상관은 분명하지만 원인을 그것 하나로 단정할 근거는 현재 데이터에 없다.

ReAct 쪽에서도 q22는 q03과 함께 가장 많이 틀린 문항이고(5개 모델 중 4개 실패,
`qwen3.8:27b`만 통과), **origin/destination이 뒤바뀐 유일한 사례**(`gemma4:12b`)가
나온 문항이다. GeoFlow에서는 이 binding을 template이 고정하므로 같은 오류가
구조적으로 발생할 수 없다.

## 정리

5종 × 13문항 전체에서 관찰된 실패 유형이다. ReAct 쪽 예시는 실제 판정 메시지다.

| 실패 유형 | GeoFlow | ReAct 관찰 예 |
| --- | --- | --- |
| 질문에 없는 기간 생성 | 0건 | `get_passage_metrics(date='last_week')` (q04/q05/q25), `get_trip_metrics(date='last_month')` (q29) |
| 발화에 없는 장소/지역 생성 | 0건 | `get_place_scope(name='부산광역시')` (q29), `region='대구광역시'` (q22) |
| 출처 불명 scope 전달 | 0건 | `get_trip_count(scope:district:2729000000)` (q22) |
| origin/destination binding 오류 | 0건 | `scope_pickup`/`scope_dropoff` 뒤바뀜 (gemma4:12b q22) |
| 필수 인자 누락 | 0건 | `include_vicinity` 누락 (q03/q26), `aggregation` 누락 (q01/q03) |
| Tool 순서·개수 오류 | 0건 | 2단계 중 1단계에서 종료, 불필요한 `get_place_scope` 추가 |
| 최초 Planner 호출이 응답하지 않음 | 3건 | — |
| 재계획 호출이 응답하지 않음 | 2건 | — |

GeoFlow의 남은 약점은 판단 오류가 아니라 **완결성**이다. 5건 모두 Planner LLM
호출이 응답을 반환하지 못한 경우이고, 최초 계획이었는지 재계획이었는지만
다르다. 작은 모델이 구조화 JSON을 끝까지 생성하지 못하면 그 질문은 답을 얻지
못한다. 대신 잘못된 답이 나가지는 않는다 — 검증을 통과하지 못한 계획은 Tool을
호출하지 않고 중단된다.

개선 방향은 두 갈래다.

* Planner 출력 길이 축소, 재시도 정책, 모델 선정 기준
* **gazetteer 이름 정규화를 LLM 재계획이 아니라 규칙으로 처리하는 것.** 13문항
  중 4건(q05·q22·q24·q29)이 `-길` `-동` `-시` 접미사 하나 때문에 재계획을 거친다.
  이걸 조회 단계에서 규칙으로 흡수하면 LLM 호출이 한 번 줄고, 유형 B는 사라진다.
  남은 5건 중 2건이 여기에 해당한다.

## 첨부 파일

| 경로 | 내용 |
| --- | --- |
| `vendor_queries.yaml` | 13개 질문 원문 |
| `reports/qwen3.5-9b_geoflow_20260918_231241.md` | 질문별 Tool trace와 판정 근거 |
| `reports/gemma4-12b_geoflow_20260918_232957.md` | 동일 |

리포트는 13문항 전체에 대해 기대 Tool 순서, 실제 호출된 인자, 판정 결과를 담고
있다. 오답 질문은 각 리포트의 `q22` / `q24` / `q26` / `q29` 절에서 확인할 수
있다. q22 절에는 **재계획** 항목이 있어 attempt 단위 경과를 볼 수 있다.

## 주의

이 결과는 13개 질문에 한정된다. `vendor_trace_gold.yaml`에 contract가 있는
질문만 판정할 수 있다.
