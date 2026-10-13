# GeoFlow OD semantic contract: od_role과 dimension_target

2026-10-12.

- 이 문서는 GeoFlow 실행 의미(코드)가 이미 정한 계약을 한곳에 모은 것이다.
- prompt 문구가 아니며, 모델에게 주는 instruction을 늘리기 위한 문서가 아니다.
- gold 검토, SFT target 표준형, 평가 비교 정규형의 기준으로 쓴다.
- 근거 코드:
  - `geoflow/grounding.py`(OD_ROLE, OD_ROLES, OD_BOTH, `attribute_satisfies`)
  - `geoflow/factors.py`(dimension_target)
  - `geoflow/operator_registry.py`(get_trip_count의 pickup/dropoff port)

## 1. 두 축은 독립이다

| 축 | 자리 | 값 | 뜻 |
|---|---|---|---|
| 장소 제한 | 장소·scope concept의 `attributes.od_role` | pickup, dropoff, both | 그 장소가 운행의 어느 끝을 거르는가. pickup=그 장소에서 탐·출발, dropoff=그 장소에서 내림·도착, both=출발과 도착이 모두 그 장소 안 |
| 결과 grouping | `factors.dimension_target` | pickup, dropoff, both | `dimension`으로 나눈 결과를 운행의 어느 끝 위치로 묶는가. pickup=승차 지역별, dropoff=하차 지역별, both=승차지-하차지 조합별 |

- `factors.py`: "장소의 od_role(장소가 제한하는 끝)과 독립이다."
- 하나가 다른 하나를 대신하지 않는다. 한 질문에 둘 다 있을 수 있고, 같은 끝일 수도 다른 끝일 수도 있다.

## 2. 장소 제한(od_role)

- **pickup / dropoff:** registry의 `scope_pickup` / `scope_dropoff` port로 간다. 어느 장소가 어느 port로 가는지는 이름이 아니라 od_role이 정한다.
- **both:** 한 장소가 두 port를 모두 만족한다(`attribute_satisfies`). 같은 scope가 `scope_pickup`과 `scope_dropoff` 두 인자로 가고, 장소 조회는 한 번이다.
  - 예: "부산 안에서 이동한", "수성구 안에서만 오간", "출발과 도착이 모두 부산 내부".
- **od_role 없음:** 장소가 끝을 거르지 않는다. 다만 운행 건수처럼 port가 끝을 요구하면 relation 재질의(MISSING_RELATION_QUALIFIER)나 조건 계층의 보충 대상이 된다.

## 3. 결과 grouping(dimension_target)

- `dimension`(h3, sido, sigungu, emd)이 있을 때만 뜻이 있다.
  - dimension 없이 적힌 `dimension_target=both`는 parser가 지운다(`_drop_default_target`).
- **생략하면 both다**(schema 기본값). 따라서 승차·하차 지역별 결과를 묻는 질문에서 dimension_target을 빼면 "출발지-도착지 짝별" 결과가 된다. 누락은 무해한 생략이 아니라 다른 질문에 답하는 것이다.
- 끝점 표현의 위치와 무관하다. 다음 둘 다 grouping 끝을 말한다.
  - 그룹 단위를 직접 꾸밈: "승차 동네", "내린 구 기준", "출발 동과 도착 동의 짝"
  - 사건 표현 안에 있음: "승차가 가장 많은 읍면동", "내린 위치를 H3 셀 기준으로", "어느 셀에서 가장 많이 내렸는지"

## 4. 조합

| 질문 꼴 | 장소 제한 | grouping | 예(sel154) |
|---|---|---|---|
| X에서 탄 운행을 [단위]별로 | X: pickup | 질문이 묻는 끝 | g12(pickup, pickup), m02(pickup, dropoff) |
| X로 간/X에서 내린 운행을 [단위]별로 | X: dropoff | 질문이 묻는 끝 | k28(dropoff, dropoff), n05 |
| X 안에서만 오간 운행 | X: both | 없음 또는 질문이 묻는 끝 | k32(없음), k34(dropoff), c04a(both) |
| X에서 Y로 간 운행 | X: pickup, Y: dropoff | 질문이 묻는 끝 | c04b(both), m09(pickup) |
| 장소 없이 [끝] 건수를 [단위]별로 | 없음 | 질문이 묻는 끝 | n35(pickup) |

- 양 끝 제한(`od_role=both`)과 짝 grouping(`dimension_target=both`)은 이름만 같고 다른 축이다.
  - c04a에는 둘 다 있다.
  - k34는 양 끝 제한이지만 grouping은 dropoff다.

## 5. 표준 직렬화(이미 정해진 것과 남은 것)

같은 장소가 양 끝을 거르는 경우 실행이 같은 표현이 둘이다.

- (a) 장소 하나 `{"subtype": "place", "value": X, "attributes": {"od_role": "both"}}`
- (b) 같은 X를 두 번(`od_role: pickup`, `od_role: dropoff`)

**이미 정해진 것(결정 29·47):** 두 표현은 뜻이 같고, 계약이 정한 표기는 (a)다. 학습 gold는 이 표기로 둔다.

- 승인 gold corpus v005는 (a) 20건, (b) 0건이다(`../sft_p0/conversion_report.json`).
- valid98을 만들 때 (b)로 적힌 h03을 뺀 것도 같은 이유다(결정 29).
- 따라서 SFT target 표준형은 새로 정할 것이 없다.

**남은 것:** 평가 gold(vendor100·valid98·sel154 형식)는 gold_text에서 grounding을 역산하므로 (b)가 된다. `evaluate_vendor100._grounding_view`는 (a)와 (b)를 같은 장소 집합으로 보지 않는다.

- semantic correctness(Tool 호출 채점)에는 영향이 없다.
- grounding_ok·grounding_diffs에만 영향이 있다. sel154 sampling 합계로 Full 11, P0 12, P0.3 12 관측이 Tool 호출은 맞았는데 이 차이만 남았다.
- 비교 정규형에서 (b)를 (a)로 접을지는 사용자가 정한다. 평가 코드(fingerprint 범위 밖)의 변경이고, grounding_ok 수치가 이전 기록과 달라진다. 이번에는 바꾸지 않았다.
