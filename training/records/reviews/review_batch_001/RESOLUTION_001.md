# RESOLUTION_001

대상: needs_fix 19건 + 동구 region 확인 2건 = 21 record / 15 questions. 기존 queue/draft/status는 변경하지 않았으며 이 분류는 최종 human decision이 아니다.

## 분류 기준과 provider 범위

- A ready_to_accept: 원문이 이미 지정한 provider와 계약에서 의미와 실행을 확인할 수 있다. 03/04는 **원본 gold가 명시한 reference-only 합성 범위**이다. Real TIMS/default mock의 지원이라고 주장하지 않는다.
- B ready_to_mark_unsupported: 기본 TIMS legacy에서 코드가 명시적으로 unsupported outcome을 반환하는 지원 불가 계산. 여기서는 semantic 어휘 자체가 없는 질문이 아니라 compiler/contract의 확정된 경계다.
- C needs_product_decision: 원문 지역 의도 또는 통계 표본·분모·공간 scope가 정해지지 않았다. 선택 후에도 구현/계약 gap이 남으면 accepted로 옮기지 않는다.
- D implementation_gap: OD 의미와 mapping은 명확하나 현재 provider가 해당 명명 장소/실제 사건 통계를 제공하지 않는다. NOT_FOUND를 semantic unsupported로 치환하지 않는다.
- B와 D의 구별은 임의 severity가 아니라 실제 pipeline outcome이다: UNVERIFIED_TIMS_CONTRACT는 unsupported; NOT_FOUND는 failed. B에도 underlying 구현 gap은 있지만 현재 product가 명시적으로 계산을 지원하지 않는다는 분류가 우선이다.
- Strong semantic correctness, parser/validator PASS, mock execution PASS, real TIMS statistic correctness는 서로 다른 사실이다. Mock은 고정 fixture이고 actual TIMS adapter는 저장소에 없다.

| Category | 원래 보류 19 | 추가 2 | ID |
|---|---:|---:|---|
| ready_to_accept | 2 | 0 | RB001-03, RB001-04 |
| ready_to_mark_unsupported | 6 | 0 | RB001-05, RB001-07, RB001-17, RB001-18, RB001-19, RB001-20 |
| needs_product_decision | 7 | 2 | RB001-02, RB001-06, RB001-10, RB001-11, RB001-12, RB001-13, RB001-14, RB001-15, RB001-16 |
| implementation_gap | 4 | 0 | RB001-21, RB001-22, RB001-23, RB001-24 |

## 이번 조사로 확정된 사실

- 03/04: 원본 ex05/ex07는 provider=reference를 선언했다. 현재 reference 실행에서 각각 30000, selected week 20260831–20260831(value=30000)을 재현했다. Reference는 nonmissing taxi-day revenue records만 계산하고 source/code는 TIMS 계약과 구별한다.
- 05/07: SELECT_GROUP shape는 native bucket/rollup fusion 대상이 아니다. TIMS에는 range_inclusive/day_records:get_billing_metrics의 로컬 분해 근거가 없다. 07의 avg는 하루 scalar 평균들로 정확히 재구성할 수도 없다.
- 17–20: get_passage_metrics는 RPM scalar와 aggregation만 지원하고 bucket/rollup을 받지 않는다. local range/day 계약도 미확인이고 reference는 RPM을 지원하지 않는다. 19/20의 주 평균은 날짜마다 평균을 그냥 평균 내어 복원할 수 없다.
- 10–16: native billing avg/min/med API 및 stage mapping은 허용된다. 하지만 active count의 기간 고유 집단/날짜 표본과 active ratio의 분모는 명시되어 있지 않다. daily series라는 정의를 선택하는 것과 vendor 구현이 그 정의를 보장하는 것은 다르다.
- 21–24: scope filter와 반대편 dimension_target binding은 올바르다. 솔빛동 lookup 실패는 provider gap이지 OD 개념 unsupported가 아니다. Mock count를 actual trip aggregation 증거로 쓰지 않는다.
- 02/06: region=""가 원문 보존의 canonical이다. mock name=동구는 대구 scope로 조회되지만 region=부산은 NOT_FOUND이고 name=부산 동구라는 별도 fixture만 존재한다. 원문에 없는 대구를 추가하거나 fixture에 맞추어 name/region 규칙을 깨지 않는다.
- 주변: mock get_place_scope는 include_vicinity를 읽지 않는다. 수성구 include_vicinity=false/true 모두 scope:district:2726000000이다. Reference는 include_vicinity를 명시적으로 지원하지 않는다. API/IR의 vicinity 표현은 현재 mock의 실제 공간 확장을 입증하지 않는다.

## Product decision — 정확한 선택지

### P0_corpus_scope

이번 reviewed gold의 accepted는 어떤 지원 범위를 뜻하는가?

관련 ID: RB001-02, RB001-03, RB001-04, RB001-05, RB001-06, RB001-07, RB001-10, RB001-11, RB001-12, RB001-13, RB001-14, RB001-15, RB001-16, RB001-17, RB001-18, RB001-19, RB001-20, RB001-21, RB001-22, RB001-23, RB001-24

- **semantic_grounding_with_provider_scope — Grounding 의미를 검토하고 provider/runtime 결과는 따로 보존**: 기존 LLM question→grounding 경계를 유지한다. 03/04는 원본 reference 범위의 gold로 수락 가능하다. TIMS 실행 불가를 곧 LLM unsupported target으로 바꾸지 않는다. 다른 문항의 정의 미확정은 별도 해결해야 한다.
- **runtime_answered_subset — 선택 provider에서 answered인 항목만 학습 편입**: provider=reference인 03/04와 default TIMS 항목을 구분한다. TIMS-only라면 03/04도 해당 subset에서 제외한다. 제외가 semantic grounding 오답을 뜻하지 않는다.

runtime failure를 이유로 Planner 역할·prompt를 변경하거나 raw target에 compiler metadata를 넣지 않는다.

### P1_region

상위 지역 없는 동구/중구 질문의 지역 의도를 어떻게 다룰 것인가?

관련 ID: RB001-02, RB001-05, RB001-06, RB001-07

- **literal_unresolved_region — 원문 그대로, region="" 유지**: 현재 canonical grounding을 유지한다. 지역 식별/후보 선택은 downstream 조회에서 확인한다. mock의 대구 mapping을 semantic 정답으로 가정하지 않는다.
- **explicit_city_new_question — 의도한 시도를 질문에 명시해 새 버전으로 검토**: 예컨대 대구/부산 중 실제 의도를 사람이 정하되 지금 원문에 region을 추가하지 않는다. 질문/lineage 변경은 기존 queue에서 import할 수 없고 새 queue 버전이 필요하다.
- **defer_geographic_intent — 상위 지역 의도가 확인될 때까지 보류**: 현재 proposed grounding은 literal projection으로 남기고 실제 accepted를 확정하지 않는다.

mock: name=동구,region=부산은 NOT_FOUND; name=부산 동구,region=""만 별도 fixture 조회. raw name/region 분리 규칙을 깨서 합성 fixture에 맞추지 않는다.

### P2_active_count_unit

평균/월별 최소의 대상인 가동 택시 대수는 어떤 관측인가?

관련 ID: RB001-10, RB001-11, RB001-13, RB001-14, RB001-15, RB001-16

- **daily_distinct_series — 일별 고유 활성 대수 A_d의 시계열**: 10/11=mean_d A_d; 13/14=mean_month(min_d A_d); 15/16=min_month(mean_d A_d). Stage factor는 현안과 일치하지만 TIMS 기간 집계가 이 정의라는 증거는 없다. 정의를 선택해도 implementation/provider 검증 gap은 남는다.
- **period_distinct_population — 한 달/기간에 한 번이라도 활성인 고유 택시 수**: |union_d Active_d|는 하나의 고유 대수다. 현 평균/최솟값 질문과 그대로 동치가 아니며 질문을 재정의해야 한다. daily sum, passage_count, operating_days로 대체하지 않는다.
- **vendor_defined_scalar — 현재 API avg/min scalar를 vendor 정의로 위임**: API 인자 대응 gold로 제한할 수 있지만 일별 대수 통계의 의미 correctness를 검증한 gold라고 주장할 수 없다. 정확한 표본 단위가 필요한 corpus에서는 보류한다.

### P3_active_ratio_unit

가동률 중앙값은 어떤 비율들의 중앙값인가?

관련 ID: RB001-12

- **median_daily_ratio — 일별 집단 비율 A_d/R_d의 중앙값**: A_d=그 날짜의 고유 활성 택시, R_d=같은 소속 범위·private 대상 등록 택시. 날짜별 비율을 계산한 뒤 med를 취한다. 분모의 scope/type/date 적용이 실제 vendor 계약에 확인되어야 한다.
- **period_population_ratio — 기간 전체 하나의 집단 비율 또는 택시·일 비율**: median of daily ratios와 다른 통계다. 현재 med 질문을 이 통계로 확정할 수 없으며 질문 재정의가 필요하다. 분자/분모도 별도 정의해야 한다.
- **vendor_defined_median — vendor의 med 통계를 정의 확인 전 위임**: schema의 med 허용은 확인되지만 일별 분모·표본을 의미 gold로 확정하는 근거는 아니다. 강한 semantic annotation은 계속 보류한다.

### P4_population_missing_days

날짜/등록 모집단이 없거나 무영업인 경우 표본과 분모를 어떻게 정하는가?

관련 ID: RB001-10, RB001-11, RB001-12, RB001-13, RB001-14, RB001-15, RB001-16

- **observed_defined_days — 관측되고 정의된 날짜만 표본에 포함**: mean 분모=유효 날짜 수. R_d=0이면 비율 정의가 안 되므로 제외/중단 중 세부 정책을 정해야 한다. Reference revenue의 결측 제외 정책을 active metric에 전이하지 않는다.
- **all_calendar_days — 기간 내 모든 날짜 포함, 확인된 무영업일은 0**: 10/11의 9월 평균 분모는 30일이다. 데이터 미수집일을 무영업일 0으로 단정할 수 없다. 등록 분모/결측 처리 계약이 필요하며 현 raw factors에 이 정책을 넣는 표면이 없다.
- **stop_on_undefined — 결측일·분모 0·빈 구간이 있으면 중단/확인 요청**: 정확한 결과를 임의 zero-fill하지 않는 정책이다. 현재 TIMS native delegation이 이를 보장한다는 계약은 없으므로 선택만으로 구현 지원을 확정할 수 없다.

### P5_spatial_metric_meaning

장소가 택시 소속 지역인가, 실제 통행/승하차 발생 위치인가?

관련 ID: RB001-10, RB001-11, RB001-12, RB001-13, RB001-14, RB001-15, RB001-16, RB001-17, RB001-18, RB001-19, RB001-20

- **billing_affiliation_passage_occurrence — Billing은 소속 지역, RPM은 passage 발생 위치**: 현재 operator/schema mapping과 일치한다. 10/11의 주변은 소속 범위를 넓힌 뜻이다. RPM stage의 compiler 불가 및 합성 장소 문제는 그대로 남는다.
- **road_active_count — 그 지역을 실제 운행한 고유 활성 택시 수**: billing affiliation과 다르다. passage_count는 통행 사건 수이지 고유 택시 수가 아니다. 현재 tools에는 해당 distinct-taxi statistic/ID가 없어 기존 grounding을 동치라고 수락할 수 없다.
- **affiliated_taxi_rpm — 그 지역 소속 택시가 모든 곳에서 기록한 RPM**: passage scope는 통행 발생 범위이며 affiliation filter가 아니다. 해당 cohort 필터를 표현/실행할 current Tool 인자가 없으므로 별도 provider/schema gap이다.

### P6_synthetic_place_scope

솔빛동·해솔동·온유동을 어떤 corpus/provider 범위로 취급할 것인가?

관련 ID: RB001-10, RB001-11, RB001-12, RB001-13, RB001-14, RB001-15, RB001-16, RB001-17, RB001-18, RB001-19, RB001-20, RB001-21, RB001-22, RB001-23, RB001-24

- **literal_semantic_only — 합성 명칭 그대로 semantic grounding 전용**: 원문 value를 보존할 수 있으나 현재 장비/provider에서 실행 가능한 gold라고 표시할 수 없다. 이 선택은 21–24의 OD 의미를 수락할 근거가 될 수 있어도 fixture/실행 gap을 제거하지 않는다. 통계 정의 미확정도 해결하지 않는다.
- **new_supported_place_questions — 검증된 지명을 명시한 질문을 향후 새 버전으로 검토**: 질문을 수정해야 하므로 기존 queue/status/grounding을 바꾸지 않는다. 실제 지명으로 바꾸어도 mock 통계가 의미를 계산하거나 TIMS 계약이 보장되었다는 뜻은 아니다.
- **hold_until_provider_support — 현 질문 실행 지원이 생길 때까지 보류**: 현재 코드 무수정 조건에서 21–24의 answered acceptance는 불가능하다. unknown place를 unsupported semantic target으로 자동 바꾸지 않는다.

## 항목별 resolution

### RB001-02 — needs_product_decision

- 질문: 2026년 상반기 동구 법인택시 월별 매출 평균 중 가장 큰 값은?
- 정확한 의미: 2026년 1~6월 각각의 소속 지역 동구 법인택시 매출 평균을 구하고, 여섯 월별 평균 중 최댓값을 반환한다. 달 이름을 묻지 않는다.
- 분자: 각 월의 소속 지역 동구·corporate 대상 revenue 값 합계
- 분모: 각 월 average의 원시 표본 수. TIMS inner_avg_unit은 observed이며 실제 분모는 확인되지 않았다. reference의 택시·일 레코드 분모를 TIMS에 전이하지 않는다.
- 집계 단위: TIMS operation(revenue=1일 수익금); 구체 average 분모는 provider 정의
- Inner: avg/month; Outer: max of monthly values.
- 반환: scalar value; 달/지역 dimension을 반환하지 않음
- 통계식: `max_m avg_provider(revenue records in m)`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Stage/OD 구조는 표현되지만 지역 의도 또는 실행 가능성은 별개다.
- Concept/role/source/value: AMOUNT/revenue MEASURE implicit value 없음; EVENT/operation SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"동구","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 모든 stage/type/source/factor 매핑은 기존 schema와 맞고 mock execution도 성공한다. 그러나 region="" 조회가 mock에서 대구로 떨어진 것은 fixture 선택이며 사용자 의도가 아니다. / 질문만으로는 실제 동구의 상위 도시가 결정되지 않는다. Grounding의 region=""는 정확한 원문 보존이며 값을 임의로 채울 JSON correction은 없다.
- 실패 유형: product_policy_undecided, provider_geographic_disambiguation_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: 동구 상위 시도 없음; mock 대구 scope를 사용자 의도로 추정할 수 없음
- 사람이 선택할 항목: P1_region, P0_corpus_scope
- 선택 후 주의: 원문 미해소 지명을 허용할지, intended city를 명시한 새 질문으로 검토할지, 보류할지 선택한다. 대구/부산 외 다른 도시를 추정해서 배제하지 않는다.
- Canonical grounding 범위: literal name projection; geographic intent unresolved. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (지역 선택 전 literal projection):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "revenue"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "동구",
      "value": {
        "name": "동구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "month",
    "date": "20260101-20260630",
    "rollup": "max",
    "taxi_type": "corporate"
  }
}
```

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:71](/home/hwkim/assistant_univ/geoflow/measures.py:71), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248)

### RB001-03 — ready_to_accept

- 질문: 2026년 8월 나래구 개인택시 주별 매출 합계 중 가장 작은 값은?
- 정확한 의미: 2026년 8월 나래구 소속 개인택시의 각 주 매출 합계 중 가장 작은 금액을 묻는다. 현재 grounding의 sum→min이 원문과 맞다.
- 분자: 주 구간 안의 해당 소속 지역·private 택시·일 revenue 합계
- 분모: sum 및 min에는 나눗셈 분모 없음
- 집계 단위: reference: service_date가 하나인 택시·일 레코드, 결측 revenue 제외
- Inner: sum/week; Outer: min of weekly sums.
- 반환: scalar 금액; dimension 또는 주 선택이 아님
- 통계식: `min_w sum_{r in filtered reference records in w}(r.revenue_krw)`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Reference에서 표본/분모/기간이 정의되었다.
- Concept/role/source/value: AMOUNT/revenue MEASURE implicit value 없음; EVENT/operation SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"나래구","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 원본 gold의 reference provider와 합성 데이터·기간 계약이 명시되어 있고 현재 구현이 이 질문을 실제 계산한다. 의미 JSON 수정 없이 reference 범위의 gold를 확정할 근거가 있다. / 기본 mock/TIMS에서의 answered까지 뜻하지 않는다. 03은 mock gazetteer NOT_FOUND이고 04는 TIMS grouped-select lowering 불가다.
- 실패 유형: 선언된 reference 범위에서는 없음. 기본 TIMS의 제약은 아래에 별도 기재.
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: 선언된 provider 정의 또는 원문 stage/OD 문법으로 정해짐.
- 사람이 선택할 항목: P0_corpus_scope
- 선택 후 주의: Reference-only annotation 범위를 사람이 최종 확인한다. TIMS-only answered subset을 선택한다면 수락 대상에서 제외하되 의미 grounding 오류로 표시하지 않는다.
- Canonical grounding 범위: reference only. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (reference에서 확정 가능):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "revenue"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "나래구",
      "value": {
        "name": "나래구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "sum",
    "bucket": "week",
    "date": "20260801-20260831",
    "rollup": "min",
    "taxi_type": "private"
  }
}
```

Reference 재실행: `30000`. weekly sum→outer min, 로컬 분할은 월요일 시작/기간 경계 clip이며 결측 revenue 제외.

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:71](/home/hwkim/assistant_univ/geoflow/measures.py:71), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [reference_provider.py:4](/home/hwkim/assistant_univ/reference_provider.py:4), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25)

### RB001-04 — ready_to_accept

- 질문: 2026년 8월 나래구 개인택시 매출 평균이 가장 낮았던 주는 언제야?
- 정확한 의미: 매출 평균이 가장 낮은 주의 구간 식별자를 묻는다. 주 안 평균(avg), 주 간 최소 구간 선택(select=min)이다. rollup=min + answer=bucket은 flat 표현의 정확한 select 대응이다.
- 분자: 각 주의 reference nonmissing revenue_krw 합계
- 분모: 그 주의 조건에 맞는 결측 아닌 택시·일 레코드 수 N_w. 택시 수/날 수/주 수가 아님.
- 집계 단위: reference: nonmissing taxi-day revenue records
- Inner: avg/week; Outer: select=min(숫자 outer min이 아님).
- 반환: selected bucket groups + value; dimension enum에 week를 넣지 않음
- 통계식: `argmin_w [(sum_{r in w} revenue_r)/N_w]; ties retain selected groups under local selection`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Reference에서 표본/분모/기간이 정의되었다.
- Concept/role/source/value: AMOUNT/revenue MEASURE implicit value 없음; EVENT/operation SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"나래구","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 원본 gold의 reference provider와 합성 데이터·기간 계약이 명시되어 있고 현재 구현이 이 질문을 실제 계산한다. 의미 JSON 수정 없이 reference 범위의 gold를 확정할 근거가 있다. / 기본 mock/TIMS에서의 answered까지 뜻하지 않는다. 03은 mock gazetteer NOT_FOUND이고 04는 TIMS grouped-select lowering 불가다.
- 실패 유형: 선언된 reference 범위에서는 없음. 기본 TIMS의 제약은 아래에 별도 기재.
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: 선언된 provider 정의 또는 원문 stage/OD 문법으로 정해짐.
- 사람이 선택할 항목: P0_corpus_scope
- 선택 후 주의: Reference-only annotation 범위를 사람이 최종 확인한다. TIMS-only answered subset을 선택한다면 수락 대상에서 제외하되 의미 grounding 오류로 표시하지 않는다.
- Canonical grounding 범위: reference only. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (reference에서 확정 가능):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "revenue"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "나래구",
      "value": {
        "name": "나래구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "answer": "bucket",
    "bucket": "week",
    "date": "20260801-20260831",
    "rollup": "min",
    "taxi_type": "private"
  }
}
```

Reference 재실행: `{"groups":[{"complete":false,"end":"20260831","label":"20260831-20260831","start":"20260831","unit":"week"}],"select":"min","value":30000.0}`. weekly nonmissing taxi-day avg→SELECT_GROUP min, 선택 결과는 주 label과 값을 함께 포함한다.

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:71](/home/hwkim/assistant_univ/geoflow/measures.py:71), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [reference_provider.py:4](/home/hwkim/assistant_univ/reference_provider.py:4), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25)

### RB001-05 — ready_to_mark_unsupported

- 질문: 2026년 상반기 중구 개인택시 운행일수 합계가 가장 많았던 달은?
- 정확한 의미: 2026년 상반기 각 월의 중구 소속 개인택시 운행일수 합계를 비교해 합계가 가장 큰 달을 고른다. 운행일수는 각 택시의 해당 기간 운행일수를 먼저 센 다음 택시 전체에 sum을 적용한다.
- 분자: 각 월 각 대상 택시의 운행한 날짜 수 D_{t,m}를 택시 전체에 합계
- 분모: sum/select에는 나눗셈 분모 없음
- 집계 단위: 먼저 taxi별 해당 월 operating_days, 그다음 taxi 전체 합계
- Inner: sum/month; Outer: select=max.
- 반환: 월 bucket 선택 + 값; dimension=month 아님
- 통계식: `argmax_m sum_{t in target taxis}(D_{t,m})`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Stage/OD 구조는 표현되지만 지역 의도 또는 실행 가능성은 별개다.
- Concept/role/source/value: AMOUNT/operating_days MEASURE implicit value 없음; EVENT/operation SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"중구","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 의미 어휘와 stage는 flat grounding 및 GeoFlow IR로 표현되며 composer/validator를 통과한다. / 현재 TIMS legacy contract로 compile하면 UNVERIFIED_TIMS_CONTRACT가 발생하고 pipeline.UNSUPPORTED_CODES가 이 코드를 unsupported outcome으로 분류한다. 지원 불가 결과는 코드상 명확하다. / answer=bucket의 SELECT_GROUP은 provider fused shape가 아니며 range_partition에는 range_inclusive, daily_partition에는 day_records:get_billing_metrics의 확인 근거가 없다. 07의 avg는 하루 값으로 정확히 합성할 수 있는 집계도 아니다.
- 실패 유형: compiler_limitation, provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: 중구 상위 시도 없음; 해결해도 TIMS select 불가가 남음
- 사람이 선택할 항목: P0_corpus_scope, P1_region
- 선택 후 주의: Runtime unsupported 관측을 최종 기록할지/해당 answered 학습 후보를 제외할지 확인한다. Planner semantic target을 unsupported로 재라벨하지 않는다. 의미 gold 보존 정책이면 현재 grounding을 그대로 유지할 수 있으나 TIMS answered라 주장하지 않는다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "operating_days"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "중구",
      "value": {
        "name": "중구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "sum",
    "answer": "bucket",
    "bucket": "month",
    "date": "20260101-20260630",
    "rollup": "max",
    "taxi_type": "private"
  }
}
```

Default TIMS compile: `UNVERIFIED_TIMS_CONTRACT` — measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_billing_metrics

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:101](/home/hwkim/assistant_univ/geoflow/measures.py:101), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248)

### RB001-06 — needs_product_decision

- 질문: 지난달 동구 법인택시 주별 운행일수 평균 중 가장 작은 값은?
- 정확한 의미: 지난달 동구 소속 법인택시의 주별 택시당 운행일수 평균들 중 가장 작은 숫자를 반환한다. 가장 작은 주를 반환하지 않는다.
- 분자: 각 주 대상 택시별 운행 날짜 수의 합계
- 분모: Tool가 정의한 대상 택시 모집단 T_w의 크기. 무영업 등록 택시 포함 여부를 mock으로 증명할 수 없음.
- 집계 단위: taxi별 기간 내 operating_days; 일 로그 자체 평균이 아님
- Inner: avg/week; Outer: min of weekly values.
- 반환: scalar 값; 해당 주를 묻지 않음
- 통계식: `min_w (sum_{t in T_w} D_{t,w})/|T_w| under provider population definition`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Stage/OD 구조는 표현되지만 지역 의도 또는 실행 가능성은 별개다.
- Concept/role/source/value: AMOUNT/operating_days MEASURE implicit value 없음; EVENT/operation SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"동구","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 모든 stage/type/source/factor 매핑은 기존 schema와 맞고 mock execution도 성공한다. 그러나 region="" 조회가 mock에서 대구로 떨어진 것은 fixture 선택이며 사용자 의도가 아니다. / 질문만으로는 실제 동구의 상위 도시가 결정되지 않는다. Grounding의 region=""는 정확한 원문 보존이며 값을 임의로 채울 JSON correction은 없다.
- 실패 유형: product_policy_undecided, provider_geographic_disambiguation_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: 동구 상위 시도 없음; last_month 기준 시각/주 경계는 legacy provider 위임
- 사람이 선택할 항목: P1_region, P0_corpus_scope
- 선택 후 주의: 원문 미해소 지명을 허용할지, intended city를 명시한 새 질문으로 검토할지, 보류할지 선택한다. 대구/부산 외 다른 도시를 추정해서 배제하지 않는다.
- Canonical grounding 범위: literal name projection; geographic intent unresolved. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (지역 선택 전 literal projection):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "operating_days"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "동구",
      "value": {
        "name": "동구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "week",
    "date": "last_month",
    "rollup": "min",
    "taxi_type": "corporate"
  }
}
```

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:101](/home/hwkim/assistant_univ/geoflow/measures.py:101), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248)

### RB001-07 — ready_to_mark_unsupported

- 질문: 지난달 동구 법인택시의 운행일수 평균이 가장 적었던 주는?
- 정확한 의미: 지난달 동구 소속 법인택시의 각 주 택시당 운행일수 평균을 구하고 그 평균이 가장 작은 주를 선택한다. RB001-06의 숫자 답과 다르다.
- 분자: 각 주 대상 택시들의 운행일수 합계
- 분모: 각 주 대상 taxi 모집단 |T_w|; population zero/activity 포함 여부는 vendor 정의 미확인
- 집계 단위: taxi별 해당 주 operating_days
- Inner: avg/week; Outer: select=min.
- 반환: 주 bucket 선택 + 값; 숫자 값 또는 지역 dimension 아님
- 통계식: `argmin_w ((sum_t D_{t,w})/|T_w|)`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Stage/OD 구조는 표현되지만 지역 의도 또는 실행 가능성은 별개다.
- Concept/role/source/value: AMOUNT/operating_days MEASURE implicit value 없음; EVENT/operation SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"동구","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 의미 어휘와 stage는 flat grounding 및 GeoFlow IR로 표현되며 composer/validator를 통과한다. / 현재 TIMS legacy contract로 compile하면 UNVERIFIED_TIMS_CONTRACT가 발생하고 pipeline.UNSUPPORTED_CODES가 이 코드를 unsupported outcome으로 분류한다. 지원 불가 결과는 코드상 명확하다. / answer=bucket의 SELECT_GROUP은 provider fused shape가 아니며 range_partition에는 range_inclusive, daily_partition에는 day_records:get_billing_metrics의 확인 근거가 없다. 07의 avg는 하루 값으로 정확히 합성할 수 있는 집계도 아니다.
- 실패 유형: compiler_limitation, provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: 동구 상위 시도 미명시; provider 상대 날짜/동률 규칙 미정
- 사람이 선택할 항목: P0_corpus_scope, P1_region
- 선택 후 주의: Runtime unsupported 관측을 최종 기록할지/해당 answered 학습 후보를 제외할지 확인한다. Planner semantic target을 unsupported로 재라벨하지 않는다. 의미 gold 보존 정책이면 현재 grounding을 그대로 유지할 수 있으나 TIMS answered라 주장하지 않는다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "operating_days"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "동구",
      "value": {
        "name": "동구",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "answer": "bucket",
    "bucket": "week",
    "date": "last_month",
    "rollup": "min",
    "taxi_type": "corporate"
  }
}
```

Default TIMS compile: `UNVERIFIED_TIMS_CONTRACT` — measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_billing_metrics

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:101](/home/hwkim/assistant_univ/geoflow/measures.py:101), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248)

### RB001-10 — needs_product_decision

- 질문: 2026년 9월 솔빛동 주변 개인택시의 평균 가동 택시 대수는?
- 정확한 의미: 평균 가동 택시 대수는 AMOUNT/active_taxi_count이고 EVENT/operation에 속한다. 개인은 taxi_type=private, 주변은 vicinity=true이다. 장소는 소속 지역 filter로만 사용된다.
- 분자: 일별 정의를 선택한 경우 sum_{d in D*} |Active_d(scope, taxi_type)|
- 분모: 유효 날짜 |D*| 또는 모든 달력 날짜 30 중 미확정. 기간 고유 대수라면 이 평균 분모 자체가 성립하지 않음.
- 집계 단위: 하루 고유 활성 taxi 집단 vs 기간 고유 집단 미확정
- Inner: single aggregation=avg; Outer: 없음.
- 반환: scalar 대수; dimension 없음
- 통계식: `daily-series choice: (sum_d A_d)/|D*|; period distinct alternative: |union_d Active_d| is a different statistic`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. active metric 표본 단위/분모 정의를 완전히 특정하는 factor는 없다.
- Concept/role/source/value: AMOUNT/active_taxi_count MEASURE implicit value 없음; EVENT/operation SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"솔빛동","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: active_taxi_count는 하루 고유 활성 대수, active_taxi_ratio는 활성/등록 집단 비율까지만 정의되어 있다. 기간 avg/min/med의 표본·분모 정의는 현재 계약에 없다. / avg/min/med factor가 schema에 있고 native billing delegation이 compile된다는 사실은 API 모양의 지원이다. Mock은 고정 metric 값을 반환해 그 통계를 계산/검증하지 않는다. / sample_unit/population/date-missingness/denominator scope를 raw grounding factor로 지정할 수 없다. 선택을 명시적으로 표현해야 한다면 schema/provider limitation이 남는다. / vicinity는 composer/registry에서 전달되지만 mock_get_place_scope는 include_vicinity를 사용하지 않아 true/false가 같은 scope를 반환한다. 실제 주변 확장을 구현했다고 볼 수 없다.
- 실패 유형: product_policy_undecided, schema_limitation, provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: 일별 대수/기간 고유 대수 및 표본 날짜 미정 / 주변 내 소속 택시인지 그곳을 실제 통행한 택시인지 미정
- 사람이 선택할 항목: P0_corpus_scope, P2_active_count_unit, P4_population_missing_days, P5_spatial_metric_meaning, P6_synthetic_place_scope
- 선택 후 주의: 정확한 표본·분모·소속/발생 위치를 선택한다. 선택만으로 TIMS 구현이 그 정의를 보장하거나 미지원 합성 장소가 조회 가능해지지는 않는다. 강한 semantic/execute gold에는 그 gap을 계속 명시해야 한다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "active_taxi_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "date": "20260901-20260930",
    "taxi_type": "private",
    "vicinity": true
  }
}
```

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:90](/home/hwkim/assistant_univ/geoflow/measures.py:90), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25)

### RB001-11 — needs_product_decision

- 질문: 2026년 9월 솔빛동 주변 법인택시의 평균 가동 택시 대수는?
- 정확한 의미: RB001-10과 동일한 활성 대수 질문이며 명시된 법인택시만 taxi_type=corporate로 달라진다. 개인택시를 유지하면 factor 오류다.
- 분자: 일별 정의를 선택한 경우 sum_{d in D*} |Active_d(scope, taxi_type)|
- 분모: 유효 날짜 |D*| 또는 모든 달력 날짜 30 중 미확정. 기간 고유 대수라면 이 평균 분모 자체가 성립하지 않음.
- 집계 단위: 하루 고유 활성 taxi 집단 vs 기간 고유 집단 미확정
- Inner: single aggregation=avg; Outer: 없음.
- 반환: scalar 대수; dimension 없음
- 통계식: `daily-series choice: (sum_d A_d)/|D*|; period distinct alternative: |union_d Active_d| is a different statistic`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. active metric 표본 단위/분모 정의를 완전히 특정하는 factor는 없다.
- Concept/role/source/value: AMOUNT/active_taxi_count MEASURE implicit value 없음; EVENT/operation SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"솔빛동","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: active_taxi_count는 하루 고유 활성 대수, active_taxi_ratio는 활성/등록 집단 비율까지만 정의되어 있다. 기간 avg/min/med의 표본·분모 정의는 현재 계약에 없다. / avg/min/med factor가 schema에 있고 native billing delegation이 compile된다는 사실은 API 모양의 지원이다. Mock은 고정 metric 값을 반환해 그 통계를 계산/검증하지 않는다. / sample_unit/population/date-missingness/denominator scope를 raw grounding factor로 지정할 수 없다. 선택을 명시적으로 표현해야 한다면 schema/provider limitation이 남는다. / vicinity는 composer/registry에서 전달되지만 mock_get_place_scope는 include_vicinity를 사용하지 않아 true/false가 같은 scope를 반환한다. 실제 주변 확장을 구현했다고 볼 수 없다.
- 실패 유형: product_policy_undecided, schema_limitation, provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: 일별 대수/기간 고유 대수 및 표본 날짜 미정 / 주변 내 소속 택시인지 그곳을 실제 통행한 택시인지 미정
- 사람이 선택할 항목: P0_corpus_scope, P2_active_count_unit, P4_population_missing_days, P5_spatial_metric_meaning, P6_synthetic_place_scope
- 선택 후 주의: 정확한 표본·분모·소속/발생 위치를 선택한다. 선택만으로 TIMS 구현이 그 정의를 보장하거나 미지원 합성 장소가 조회 가능해지지는 않는다. 강한 semantic/execute gold에는 그 gap을 계속 명시해야 한다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "active_taxi_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "date": "20260901-20260930",
    "taxi_type": "corporate",
    "vicinity": true
  }
}
```

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:90](/home/hwkim/assistant_univ/geoflow/measures.py:90), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25)

### RB001-12 — needs_product_decision

- 질문: 2026년 9월 해솔동 개인택시 가동률의 중앙값은?
- 정확한 의미: 가동률은 PROPORTION/active_taxi_ratio = 활성택시/등록된 전체 택시이고 EVENT/operation이다. 공차율(vacant_ratio)이나 taxi별 운행 여부의 중앙값이 아니다.
- 분자: daily-ratio 선택: 하루 고유 활성 택시 A_d(해솔동 소속, private)
- 분모: 그 날짜·소속 범위·private 모집단의 등록 taxi R_d; type/date 적용 여부 코드/계약 미정
- 집계 단위: 날짜마다의 population ratio A_d/R_d vs 기간 단일 ratio 미확정
- Inner: single med; Outer: 없음.
- 반환: scalar 비율; dimension 없음
- 통계식: `daily-ratio choice: median_{d in D*, R_d>0}(A_d/R_d); |union Active|/Registered is not its equivalent`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. active metric 표본 단위/분모 정의를 완전히 특정하는 factor는 없다.
- Concept/role/source/value: EVENT/operation SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"해솔동","region":""}; PROPORTION/active_taxi_ratio MEASURE implicit value 없음. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: active_taxi_count는 하루 고유 활성 대수, active_taxi_ratio는 활성/등록 집단 비율까지만 정의되어 있다. 기간 avg/min/med의 표본·분모 정의는 현재 계약에 없다. / avg/min/med factor가 schema에 있고 native billing delegation이 compile된다는 사실은 API 모양의 지원이다. Mock은 고정 metric 값을 반환해 그 통계를 계산/검증하지 않는다. / sample_unit/population/date-missingness/denominator scope를 raw grounding factor로 지정할 수 없다. 선택을 명시적으로 표현해야 한다면 schema/provider limitation이 남는다.
- 실패 유형: product_policy_undecided, schema_limitation, provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: median 표본 단위 미정 / 등록 분모와 무영업/미수집일/R_d=0 처리 미정
- 사람이 선택할 항목: P0_corpus_scope, P3_active_ratio_unit, P4_population_missing_days, P5_spatial_metric_meaning, P6_synthetic_place_scope
- 선택 후 주의: 정확한 표본·분모·소속/발생 위치를 선택한다. 선택만으로 TIMS 구현이 그 정의를 보장하거나 미지원 합성 장소가 조회 가능해지지는 않는다. 강한 semantic/execute gold에는 그 gap을 계속 명시해야 한다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "concept": "EVENT",
      "id": "c1",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c2",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "해솔동",
      "value": {
        "name": "해솔동",
        "region": ""
      }
    },
    {
      "concept": "PROPORTION",
      "id": "c3",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "active_taxi_ratio"
    }
  ],
  "factors": {
    "aggregation": "med",
    "date": "20260901-20260930",
    "taxi_type": "private"
  }
}
```

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:94](/home/hwkim/assistant_univ/geoflow/measures.py:94), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25)

### RB001-13 — needs_product_decision

- 질문: 2026년 8월과 9월 온유동의 월별 가동 택시 대수 최솟값의 평균은?
- 정확한 의미: 8월과 9월을 각각 구간으로 나누고 각 월 안에서 가동 대수 최솟값을 구한 뒤 그 두 월 최솟값의 평균을 낸다는 stage 문법이다.
- 분자: 일별 대수 선택: A_d=|Active_d|; outer 평균은 월별 최솟값 두 개의 합
- 분모: outer 평균은 값이 정의된 월 수(두 월 모두 있으면 2); inner 날짜 분모/표본 단위 미확정
- 집계 단위: day distinct counts가 월 내 원시 관측인지 확정 안 됨
- Inner: min/month; Outer: avg of monthly minima.
- 반환: scalar 대수; 최저 월/ dimension 아님
- 통계식: `daily-series choice: (min_{d in Aug} A_d + min_{d in Sep} A_d)/2`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. active metric 표본 단위/분모 정의를 완전히 특정하는 factor는 없다.
- Concept/role/source/value: AMOUNT/active_taxi_count MEASURE implicit value 없음; EVENT/operation SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"온유동","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: active_taxi_count는 하루 고유 활성 대수, active_taxi_ratio는 활성/등록 집단 비율까지만 정의되어 있다. 기간 avg/min/med의 표본·분모 정의는 현재 계약에 없다. / avg/min/med factor가 schema에 있고 native billing delegation이 compile된다는 사실은 API 모양의 지원이다. Mock은 고정 metric 값을 반환해 그 통계를 계산/검증하지 않는다. / sample_unit/population/date-missingness/denominator scope를 raw grounding factor로 지정할 수 없다. 선택을 명시적으로 표현해야 한다면 schema/provider limitation이 남는다.
- 실패 유형: product_policy_undecided, schema_limitation, provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: stage 문법은 명확하지만 기간 active_taxi_count의 표본 단위와 빈 날짜/모집단 정의가 미정
- 사람이 선택할 항목: P0_corpus_scope, P2_active_count_unit, P4_population_missing_days, P5_spatial_metric_meaning, P6_synthetic_place_scope
- 선택 후 주의: 정확한 표본·분모·소속/발생 위치를 선택한다. 선택만으로 TIMS 구현이 그 정의를 보장하거나 미지원 합성 장소가 조회 가능해지지는 않는다. 강한 semantic/execute gold에는 그 gap을 계속 명시해야 한다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "active_taxi_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "온유동",
      "value": {
        "name": "온유동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "min",
    "bucket": "month",
    "date": "20260801-20260930",
    "rollup": "avg"
  }
}
```

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:90](/home/hwkim/assistant_univ/geoflow/measures.py:90), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25)

### RB001-14 — needs_product_decision

- 질문: 2026년 8월과 9월 온유동의 월별 가동 택시 대수 최솟값의 평균은?
- 정확한 의미: 8월과 9월을 각각 구간으로 나누고 각 월 안에서 가동 대수 최솟값을 구한 뒤 그 두 월 최솟값의 평균을 낸다는 stage 문법이다.
- 분자: 일별 대수 선택: A_d=|Active_d|; outer 평균은 월별 최솟값 두 개의 합
- 분모: outer 평균은 값이 정의된 월 수(두 월 모두 있으면 2); inner 날짜 분모/표본 단위 미확정
- 집계 단위: day distinct counts가 월 내 원시 관측인지 확정 안 됨
- Inner: min/month; Outer: avg of monthly minima.
- 반환: scalar 대수; 최저 월/ dimension 아님
- 통계식: `daily-series choice: (min_{d in Aug} A_d + min_{d in Sep} A_d)/2`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. active metric 표본 단위/분모 정의를 완전히 특정하는 factor는 없다.
- Concept/role/source/value: AMOUNT/active_taxi_count MEASURE implicit value 없음; EVENT/operation SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"온유동","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: active_taxi_count는 하루 고유 활성 대수, active_taxi_ratio는 활성/등록 집단 비율까지만 정의되어 있다. 기간 avg/min/med의 표본·분모 정의는 현재 계약에 없다. / avg/min/med factor가 schema에 있고 native billing delegation이 compile된다는 사실은 API 모양의 지원이다. Mock은 고정 metric 값을 반환해 그 통계를 계산/검증하지 않는다. / sample_unit/population/date-missingness/denominator scope를 raw grounding factor로 지정할 수 없다. 선택을 명시적으로 표현해야 한다면 schema/provider limitation이 남는다.
- 실패 유형: product_policy_undecided, schema_limitation, provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: stage 문법은 명확하지만 기간 active_taxi_count의 표본 단위와 빈 날짜/모집단 정의가 미정
- 사람이 선택할 항목: P0_corpus_scope, P2_active_count_unit, P4_population_missing_days, P5_spatial_metric_meaning, P6_synthetic_place_scope
- 선택 후 주의: 정확한 표본·분모·소속/발생 위치를 선택한다. 선택만으로 TIMS 구현이 그 정의를 보장하거나 미지원 합성 장소가 조회 가능해지지는 않는다. 강한 semantic/execute gold에는 그 gap을 계속 명시해야 한다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "active_taxi_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "온유동",
      "value": {
        "name": "온유동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "min",
    "bucket": "month",
    "date": "20260801-20260930",
    "rollup": "avg"
  }
}
```

- Contrast chosen: aggregation=min, rollup=avg
- Contrast rejected: aggregation=avg, rollup=min
- 차이: 월 최소들의 평균을 월 평균들의 최소로 바꾼다. 일별 활성 대수라는 정의를 확정한 뒤에만 pair의 의미 선호를 최종 승인할 수 있다.
- Gold와 pair는 독립 decision 단위다. Pair를 수락하려면 chosen이 정확하고 rejected가 잘못된 의미라는 human attestation이 별도로 필요하다.

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:90](/home/hwkim/assistant_univ/geoflow/measures.py:90), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25)

### RB001-15 — needs_product_decision

- 질문: 2026년 8월과 9월 온유동의 월별 평균 가동 택시 대수 중 최솟값은?
- 정확한 의미: 각 월의 가동 대수 평균을 구한 뒤 두 월 평균 중 최솟값을 반환한다. 각 월 최소들의 평균이 아니다.
- 분자: 일별 대수 선택: A_d=|Active_d|; inner 평균은 월 안 유효 날짜 A_d 합
- 분모: 각 월의 유효 날짜 수 또는 모든 날짜 수 중 미정; outer min에는 분모 없음
- 집계 단위: day distinct counts가 월 내 원시 관측인지 확정 안 됨
- Inner: avg/month; Outer: min of monthly means.
- 반환: scalar 대수; 최저 월/ dimension 아님
- 통계식: `daily-series choice: min(mean_{d in Aug} A_d,mean_{d in Sep} A_d)`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. active metric 표본 단위/분모 정의를 완전히 특정하는 factor는 없다.
- Concept/role/source/value: AMOUNT/active_taxi_count MEASURE implicit value 없음; EVENT/operation SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"온유동","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: active_taxi_count는 하루 고유 활성 대수, active_taxi_ratio는 활성/등록 집단 비율까지만 정의되어 있다. 기간 avg/min/med의 표본·분모 정의는 현재 계약에 없다. / avg/min/med factor가 schema에 있고 native billing delegation이 compile된다는 사실은 API 모양의 지원이다. Mock은 고정 metric 값을 반환해 그 통계를 계산/검증하지 않는다. / sample_unit/population/date-missingness/denominator scope를 raw grounding factor로 지정할 수 없다. 선택을 명시적으로 표현해야 한다면 schema/provider limitation이 남는다.
- 실패 유형: product_policy_undecided, schema_limitation, provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: stage 문법은 명확하지만 기간 active_taxi_count의 표본 단위와 빈 날짜/모집단 정의가 미정
- 사람이 선택할 항목: P0_corpus_scope, P2_active_count_unit, P4_population_missing_days, P5_spatial_metric_meaning, P6_synthetic_place_scope
- 선택 후 주의: 정확한 표본·분모·소속/발생 위치를 선택한다. 선택만으로 TIMS 구현이 그 정의를 보장하거나 미지원 합성 장소가 조회 가능해지지는 않는다. 강한 semantic/execute gold에는 그 gap을 계속 명시해야 한다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "active_taxi_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "온유동",
      "value": {
        "name": "온유동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "month",
    "date": "20260801-20260930",
    "rollup": "min"
  }
}
```

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:90](/home/hwkim/assistant_univ/geoflow/measures.py:90), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25)

### RB001-16 — needs_product_decision

- 질문: 2026년 8월과 9월 온유동의 월별 평균 가동 택시 대수 중 최솟값은?
- 정확한 의미: 각 월의 가동 대수 평균을 구한 뒤 두 월 평균 중 최솟값을 반환한다. 각 월 최소들의 평균이 아니다.
- 분자: 일별 대수 선택: A_d=|Active_d|; inner 평균은 월 안 유효 날짜 A_d 합
- 분모: 각 월의 유효 날짜 수 또는 모든 날짜 수 중 미정; outer min에는 분모 없음
- 집계 단위: day distinct counts가 월 내 원시 관측인지 확정 안 됨
- Inner: avg/month; Outer: min of monthly means.
- 반환: scalar 대수; 최저 월/ dimension 아님
- 통계식: `daily-series choice: min(mean_{d in Aug} A_d,mean_{d in Sep} A_d)`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. active metric 표본 단위/분모 정의를 완전히 특정하는 factor는 없다.
- Concept/role/source/value: AMOUNT/active_taxi_count MEASURE implicit value 없음; EVENT/operation SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"온유동","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: active_taxi_count는 하루 고유 활성 대수, active_taxi_ratio는 활성/등록 집단 비율까지만 정의되어 있다. 기간 avg/min/med의 표본·분모 정의는 현재 계약에 없다. / avg/min/med factor가 schema에 있고 native billing delegation이 compile된다는 사실은 API 모양의 지원이다. Mock은 고정 metric 값을 반환해 그 통계를 계산/검증하지 않는다. / sample_unit/population/date-missingness/denominator scope를 raw grounding factor로 지정할 수 없다. 선택을 명시적으로 표현해야 한다면 schema/provider limitation이 남는다.
- 실패 유형: product_policy_undecided, schema_limitation, provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: stage 문법은 명확하지만 기간 active_taxi_count의 표본 단위와 빈 날짜/모집단 정의가 미정
- 사람이 선택할 항목: P0_corpus_scope, P2_active_count_unit, P4_population_missing_days, P5_spatial_metric_meaning, P6_synthetic_place_scope
- 선택 후 주의: 정확한 표본·분모·소속/발생 위치를 선택한다. 선택만으로 TIMS 구현이 그 정의를 보장하거나 미지원 합성 장소가 조회 가능해지지는 않는다. 강한 semantic/execute gold에는 그 gap을 계속 명시해야 한다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "active_taxi_count"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "operation"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "온유동",
      "value": {
        "name": "온유동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "month",
    "date": "20260801-20260930",
    "rollup": "min"
  }
}
```

- Contrast chosen: aggregation=avg, rollup=min
- Contrast rejected: aggregation=min, rollup=avg
- 차이: 월 평균들의 최소를 월 최소들의 평균으로 바꾼다. 활성 대수의 기간 표본 정의가 필요하다.
- Gold와 pair는 독립 decision 단위다. Pair를 수락하려면 chosen이 정확하고 rejected가 잘못된 의미라는 human attestation이 별도로 필요하다.

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [schemas/tims.yaml:176](/home/hwkim/assistant_univ/schemas/tims.yaml:176), [geoflow/measures.py:90](/home/hwkim/assistant_univ/geoflow/measures.py:90), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [prompts/system.yaml:30](/home/hwkim/assistant_univ/prompts/system.yaml:30), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25)

### RB001-17 — ready_to_mark_unsupported

- 질문: 2026년 9월 솔빛동 택시의 주마다 구한 엔진 회전수 최댓값의 평균은?
- 정확한 의미: RPM은 passage에 속하는 엔진 회전수다. 각 주 passage RPM의 최댓값을 구하고 주별 최댓값의 평균을 반환한다. 소속 지역의 택시가 아니라 passage가 발생한 공간 scope를 읽는다.
- 분자: 각 주 passage RPM의 max 값 합
- 분모: 정의된 주별 최댓값의 개수(주마다 한 표)
- 집계 단위: passage(edge 진입~진출) RPM 관측; 택시 소속 cohort filter와 다른 공간 의미
- Inner: max/week; Outer: avg of weekly maxima.
- 반환: scalar RPM; 주별 목록/최고 주 선택/지역 dimension 아님
- 통계식: `(sum_w max_{r in passage_w} RPM_r)/|W*|`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Stage/OD 구조는 표현되지만 지역 의도 또는 실행 가능성은 별개다.
- Concept/role/source/value: AMOUNT/rpm MEASURE implicit value 없음; EVENT/passage SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"솔빛동","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 의미 어휘와 stage는 flat grounding 및 GeoFlow IR로 표현되며 composer/validator를 통과한다. / 현재 TIMS legacy contract로 compile하면 UNVERIFIED_TIMS_CONTRACT가 발생하고 pipeline.UNSUPPORTED_CODES가 이 코드를 unsupported outcome으로 분류한다. 지원 불가 결과는 코드상 명확하다. / get_passage_metrics는 bucket/rollup을 받지 않고 reference provider는 RPM 자체를 지원하지 않는다. 범위 분할의 range_inclusive 및 daily_partition의 day_records:get_passage_metrics가 확인되지 않았다. max inner의 수학적 day-composability만으로 기록 날짜 귀속 계약이 생기지는 않는다.
- 실패 유형: compiler_limitation, provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: 솔빛동의 passage 발생 위치인지 소속 택시의 모든 passage인지 추가 확인 가능. 어느 해석을 택해도 현 TIMS에서 이 grouped RPM 실행은 불가.
- 사람이 선택할 항목: P0_corpus_scope, P5_spatial_metric_meaning
- 선택 후 주의: Runtime unsupported 관측을 최종 기록할지/해당 answered 학습 후보를 제외할지 확인한다. Planner semantic target을 unsupported로 재라벨하지 않는다. 의미 gold 보존 정책이면 현재 grounding을 그대로 유지할 수 있으나 TIMS answered라 주장하지 않는다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "week",
    "date": "20260901-20260930",
    "rollup": "avg"
  }
}
```

Default TIMS compile: `UNVERIFIED_TIMS_CONTRACT` — measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_passage_metrics

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [schemas/tims.yaml:53](/home/hwkim/assistant_univ/schemas/tims.yaml:53), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25)

### RB001-18 — ready_to_mark_unsupported

- 질문: 2026년 9월 솔빛동 택시의 주마다 구한 엔진 회전수 최댓값의 평균은?
- 정확한 의미: RPM은 passage에 속하는 엔진 회전수다. 각 주 passage RPM의 최댓값을 구하고 주별 최댓값의 평균을 반환한다. 소속 지역의 택시가 아니라 passage가 발생한 공간 scope를 읽는다.
- 분자: 각 주 passage RPM의 max 값 합
- 분모: 정의된 주별 최댓값의 개수(주마다 한 표)
- 집계 단위: passage(edge 진입~진출) RPM 관측; 택시 소속 cohort filter와 다른 공간 의미
- Inner: max/week; Outer: avg of weekly maxima.
- 반환: scalar RPM; 주별 목록/최고 주 선택/지역 dimension 아님
- 통계식: `(sum_w max_{r in passage_w} RPM_r)/|W*|`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Stage/OD 구조는 표현되지만 지역 의도 또는 실행 가능성은 별개다.
- Concept/role/source/value: AMOUNT/rpm MEASURE implicit value 없음; EVENT/passage SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"솔빛동","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 의미 어휘와 stage는 flat grounding 및 GeoFlow IR로 표현되며 composer/validator를 통과한다. / 현재 TIMS legacy contract로 compile하면 UNVERIFIED_TIMS_CONTRACT가 발생하고 pipeline.UNSUPPORTED_CODES가 이 코드를 unsupported outcome으로 분류한다. 지원 불가 결과는 코드상 명확하다. / get_passage_metrics는 bucket/rollup을 받지 않고 reference provider는 RPM 자체를 지원하지 않는다. 범위 분할의 range_inclusive 및 daily_partition의 day_records:get_passage_metrics가 확인되지 않았다. max inner의 수학적 day-composability만으로 기록 날짜 귀속 계약이 생기지는 않는다.
- 실패 유형: compiler_limitation, provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: 솔빛동의 passage 발생 위치인지 소속 택시의 모든 passage인지 추가 확인 가능. 어느 해석을 택해도 현 TIMS에서 이 grouped RPM 실행은 불가.
- 사람이 선택할 항목: P0_corpus_scope, P5_spatial_metric_meaning
- 선택 후 주의: Runtime unsupported 관측을 최종 기록할지/해당 answered 학습 후보를 제외할지 확인한다. Planner semantic target을 unsupported로 재라벨하지 않는다. 의미 gold 보존 정책이면 현재 grounding을 그대로 유지할 수 있으나 TIMS answered라 주장하지 않는다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "max",
    "bucket": "week",
    "date": "20260901-20260930",
    "rollup": "avg"
  }
}
```

Default TIMS compile: `UNVERIFIED_TIMS_CONTRACT` — measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 확인되지 않은 계약: day_records:get_passage_metrics

- Contrast chosen: aggregation=max, rollup=avg
- Contrast rejected: aggregation=avg, rollup=max
- 차이: 주 최댓값들의 평균을 주 평균들의 최댓값으로 바꾼다. Stage 오류는 명확하지만 chosen도 현재 TIMS로 실행되지 않는다.
- Gold와 pair는 독립 decision 단위다. Pair를 수락하려면 chosen이 정확하고 rejected가 잘못된 의미라는 human attestation이 별도로 필요하다.

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [schemas/tims.yaml:53](/home/hwkim/assistant_univ/schemas/tims.yaml:53), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25)

### RB001-19 — ready_to_mark_unsupported

- 질문: 2026년 9월 솔빛동 택시의 주마다 평균 낸 엔진 회전수 중 최댓값은?
- 정확한 의미: 각 주 passage RPM의 평균을 구한 뒤 주별 평균 중 최댓값을 반환한다. 주별 RPM 최댓값들의 평균과 다르다.
- 분자: 각 주 조건에 맞는 passage RPM 합
- 분모: 각 주의 유효 passage 기록 수 N_w; 하루 평균 개수/날 수가 아님
- 집계 단위: passage(edge 진입~진출) RPM 관측; 택시 소속 cohort filter와 다른 공간 의미
- Inner: avg/week; Outer: max of weekly means.
- 반환: scalar RPM; 주별 목록/최고 주 선택/지역 dimension 아님
- 통계식: `max_w ((sum_{r in passage_w} RPM_r)/N_w)`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Stage/OD 구조는 표현되지만 지역 의도 또는 실행 가능성은 별개다.
- Concept/role/source/value: AMOUNT/rpm MEASURE implicit value 없음; EVENT/passage SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"솔빛동","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 의미 어휘와 stage는 flat grounding 및 GeoFlow IR로 표현되며 composer/validator를 통과한다. / 현재 TIMS legacy contract로 compile하면 UNVERIFIED_TIMS_CONTRACT가 발생하고 pipeline.UNSUPPORTED_CODES가 이 코드를 unsupported outcome으로 분류한다. 지원 불가 결과는 코드상 명확하다. / get_passage_metrics는 bucket/rollup을 받지 않고 reference provider는 RPM 자체를 지원하지 않는다. 범위 분할의 range_inclusive 및 daily_partition의 day_records:get_passage_metrics가 확인되지 않았다. avg inner는 하루 평균의 평균으로 정확히 복원할 수도 없다.
- 실패 유형: compiler_limitation, provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: 솔빛동의 passage 발생 위치인지 소속 택시의 모든 passage인지 추가 확인 가능. 어느 해석을 택해도 현 TIMS에서 이 grouped RPM 실행은 불가.
- 사람이 선택할 항목: P0_corpus_scope, P5_spatial_metric_meaning
- 선택 후 주의: Runtime unsupported 관측을 최종 기록할지/해당 answered 학습 후보를 제외할지 확인한다. Planner semantic target을 unsupported로 재라벨하지 않는다. 의미 gold 보존 정책이면 현재 grounding을 그대로 유지할 수 있으나 TIMS answered라 주장하지 않는다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "week",
    "date": "20260901-20260930",
    "rollup": "max"
  }
}
```

Default TIMS compile: `UNVERIFIED_TIMS_CONTRACT` — measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_passage_metrics

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [schemas/tims.yaml:53](/home/hwkim/assistant_univ/schemas/tims.yaml:53), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25)

### RB001-20 — ready_to_mark_unsupported

- 질문: 2026년 9월 솔빛동 택시의 주마다 평균 낸 엔진 회전수 중 최댓값은?
- 정확한 의미: 각 주 passage RPM의 평균을 구한 뒤 주별 평균 중 최댓값을 반환한다. 주별 RPM 최댓값들의 평균과 다르다.
- 분자: 각 주 조건에 맞는 passage RPM 합
- 분모: 각 주의 유효 passage 기록 수 N_w; 하루 평균 개수/날 수가 아님
- 집계 단위: passage(edge 진입~진출) RPM 관측; 택시 소속 cohort filter와 다른 공간 의미
- Inner: avg/week; Outer: max of weekly means.
- 반환: scalar RPM; 주별 목록/최고 주 선택/지역 dimension 아님
- 통계식: `max_w ((sum_{r in passage_w} RPM_r)/N_w)`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Stage/OD 구조는 표현되지만 지역 의도 또는 실행 가능성은 별개다.
- Concept/role/source/value: AMOUNT/rpm MEASURE implicit value 없음; EVENT/passage SUPPORT implicit value 없음; LOCATION/place SUBCOND user value={"name":"솔빛동","region":""}. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 의미 어휘와 stage는 flat grounding 및 GeoFlow IR로 표현되며 composer/validator를 통과한다. / 현재 TIMS legacy contract로 compile하면 UNVERIFIED_TIMS_CONTRACT가 발생하고 pipeline.UNSUPPORTED_CODES가 이 코드를 unsupported outcome으로 분류한다. 지원 불가 결과는 코드상 명확하다. / get_passage_metrics는 bucket/rollup을 받지 않고 reference provider는 RPM 자체를 지원하지 않는다. 범위 분할의 range_inclusive 및 daily_partition의 day_records:get_passage_metrics가 확인되지 않았다. avg inner는 하루 평균의 평균으로 정확히 복원할 수도 없다.
- 실패 유형: compiler_limitation, provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: 솔빛동의 passage 발생 위치인지 소속 택시의 모든 passage인지 추가 확인 가능. 어느 해석을 택해도 현 TIMS에서 이 grouped RPM 실행은 불가.
- 사람이 선택할 항목: P0_corpus_scope, P5_spatial_metric_meaning
- 선택 후 주의: Runtime unsupported 관측을 최종 기록할지/해당 answered 학습 후보를 제외할지 확인한다. Planner semantic target을 unsupported로 재라벨하지 않는다. 의미 gold 보존 정책이면 현재 grounding을 그대로 유지할 수 있으나 TIMS answered라 주장하지 않는다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "concept": "AMOUNT",
      "id": "c1",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "rpm"
    },
    {
      "concept": "EVENT",
      "id": "c2",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "passage"
    },
    {
      "concept": "LOCATION",
      "id": "c3",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    }
  ],
  "factors": {
    "aggregation": "avg",
    "bucket": "week",
    "date": "20260901-20260930",
    "rollup": "max"
  }
}
```

Default TIMS compile: `UNVERIFIED_TIMS_CONTRACT` — measure_groups: 구간별 집계를 정확히 계산할 수 있는 호출 방법이 확인되지 않았습니다. fused_bucket_rollup: Tool이 이 구간·집계 조합을 한 호출로 받지 않습니다; range_partition: 확인되지 않은 계약: range_inclusive; daily_partition: 구간 안 집계 avg는 하루 값들로 정확히 다시 만들 수 없습니다; 확인되지 않은 계약: day_records:get_passage_metrics

- Contrast chosen: aggregation=avg, rollup=max
- Contrast rejected: aggregation=max, rollup=avg
- 차이: 주 평균들의 최댓값을 주 최댓값들의 평균으로 바꾼다. Chosen의 평균 표본을 하루 평균의 평균으로 치환해서도 안 된다.
- Gold와 pair는 독립 decision 단위다. Pair를 수락하려면 chosen이 정확하고 rejected가 잘못된 의미라는 human attestation이 별도로 필요하다.

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/aggregation.py:108](/home/hwkim/assistant_univ/geoflow/aggregation.py:108), [geoflow/tims_contract.py:67](/home/hwkim/assistant_univ/geoflow/tims_contract.py:67), [schemas/tims.yaml:53](/home/hwkim/assistant_univ/schemas/tims.yaml:53), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25)

### RB001-21 — implementation_gap

- 질문: 2026년 9월 솔빛동에서 승차한 실차 구간을 읍면동 하차지별로 세면 건수가 많은 4곳은?
- 정확한 의미: 솔빛동은 승차 장소의 filter(od_role=pickup)다. 집계 그룹은 각 실차 구간의 읍면동 하차지(dimension=emd, dimension_target=dropoff)이며 건수 상위 4개다.
- 분자: pickup∈솔빛동인 trip의 dropoff 읍면동별 사건 수
- 분모: count에는 나눗셈 분모 없음
- 집계 단위: 한 실차 구간(trip) = 사건 한 건, 고유 taxi/통행 edge 수 아님
- Inner: group count (inherent sum); Outer: 없음; order=top, limit=4.
- 반환: dimension=emd, dimension_target=dropoff의 group 목록
- 통계식: `top4_g sum_trip 1[pickup in S and emd(dropoff)=g]`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Stage/OD 구조는 표현되지만 지역 의도 또는 실행 가능성은 별개다.
- Concept/role/source/value: LOCATION/place SUBCOND user value={"name":"솔빛동","region":""}; AMOUNT/trip_count MEASURE implicit value 없음; EVENT/trip SUPPORT implicit value 없음. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 정확한 OD 의도와 filter/target 방향은 확정 가능하다. od_role의 scope_pickup/scope_dropoff binding과 dimension_target mapping은 현재 deterministic registry/compiler가 지원한다. / 그러나 솔빛동은 mock/reference gazetteer에 없고 현재 실행이 NOT_FOUND로 실패한다. NOT_FOUND는 pipeline unsupported 코드가 아니라 failed outcome이다. / Mock trip count는 고정 count/지역 fixture 목록을 반환한다. 실제 trip를 필터하고 사건을 세는 의미 검증 provider가 아니다. Reference provider는 get_trip_count를 지원하지 않는다.
- 실패 유형: provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: OD filter 방향/target은 원문에서 명확; 유일한 명명 scope 솔빛동의 provider context가 없음
- 사람이 선택할 항목: P0_corpus_scope, P6_synthetic_place_scope
- 선택 후 주의: 원문을 유지하는 semantic-only annotation을 허용할지, 현 질문의 실행 provider 지원을 기다릴지, 검증된 장소를 명시한 새 queue로 재검토할지 결정한다. 방향을 고치거나 unknown place를 semantic unsupported로 바꾸지 않는다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "pickup"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c2",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c3",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260901-20260930",
    "dimension": "emd",
    "dimension_target": "dropoff",
    "limit": 4,
    "order": "top"
  }
}
```

실제 mock 실행: `get_place_scope / NOT_FOUND`. Direction/target을 바꾸어 해결할 문제는 아니다.

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25), [mock_responses.py:317](/home/hwkim/assistant_univ/mock_responses.py:317)

### RB001-22 — implementation_gap

- 질문: 2026년 9월 솔빛동에서 승차한 실차 구간을 읍면동 하차지별로 세면 건수가 많은 4곳은?
- 정확한 의미: 솔빛동은 승차 장소의 filter(od_role=pickup)다. 집계 그룹은 각 실차 구간의 읍면동 하차지(dimension=emd, dimension_target=dropoff)이며 건수 상위 4개다.
- 분자: pickup∈솔빛동인 trip의 dropoff 읍면동별 사건 수
- 분모: count에는 나눗셈 분모 없음
- 집계 단위: 한 실차 구간(trip) = 사건 한 건, 고유 taxi/통행 edge 수 아님
- Inner: group count (inherent sum); Outer: 없음; order=top, limit=4.
- 반환: dimension=emd, dimension_target=dropoff의 group 목록
- 통계식: `top4_g sum_trip 1[pickup in S and emd(dropoff)=g]`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Stage/OD 구조는 표현되지만 지역 의도 또는 실행 가능성은 별개다.
- Concept/role/source/value: LOCATION/place SUBCOND user value={"name":"솔빛동","region":""}; AMOUNT/trip_count MEASURE implicit value 없음; EVENT/trip SUPPORT implicit value 없음. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 정확한 OD 의도와 filter/target 방향은 확정 가능하다. od_role의 scope_pickup/scope_dropoff binding과 dimension_target mapping은 현재 deterministic registry/compiler가 지원한다. / 그러나 솔빛동은 mock/reference gazetteer에 없고 현재 실행이 NOT_FOUND로 실패한다. NOT_FOUND는 pipeline unsupported 코드가 아니라 failed outcome이다. / Mock trip count는 고정 count/지역 fixture 목록을 반환한다. 실제 trip를 필터하고 사건을 세는 의미 검증 provider가 아니다. Reference provider는 get_trip_count를 지원하지 않는다.
- 실패 유형: provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: OD filter 방향/target은 원문에서 명확; 유일한 명명 scope 솔빛동의 provider context가 없음
- 사람이 선택할 항목: P0_corpus_scope, P6_synthetic_place_scope
- 선택 후 주의: 원문을 유지하는 semantic-only annotation을 허용할지, 현 질문의 실행 provider 지원을 기다릴지, 검증된 장소를 명시한 새 queue로 재검토할지 결정한다. 방향을 고치거나 unknown place를 semantic unsupported로 바꾸지 않는다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "pickup"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c2",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c3",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260901-20260930",
    "dimension": "emd",
    "dimension_target": "dropoff",
    "limit": 4,
    "order": "top"
  }
}
```

실제 mock 실행: `get_place_scope / NOT_FOUND`. Direction/target을 바꾸어 해결할 문제는 아니다.

- Contrast chosen: place.od_role=pickup
- Contrast rejected: place.od_role=dropoff
- 차이: 솔빛동에서 탄 trip이 아니라 솔빛동에서 내린 trip을 필터한다. dimension_target=dropoff는 그대로여서 하차 위치를 필터와 그룹 양쪽에 쓰는 다른 질문이다.
- Gold와 pair는 독립 decision 단위다. Pair를 수락하려면 chosen이 정확하고 rejected가 잘못된 의미라는 human attestation이 별도로 필요하다.

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25), [mock_responses.py:317](/home/hwkim/assistant_univ/mock_responses.py:317)

### RB001-23 — implementation_gap

- 질문: 2026년 9월 솔빛동에서 하차한 실차 구간을 읍면동 승차지별로 세면 건수가 많은 4곳은?
- 정확한 의미: 솔빛동은 하차 장소의 filter(od_role=dropoff)다. 결과 그룹은 읍면동 승차지(dimension_target=pickup)이며 건수 상위 4개다. 에서라는 조사만으로 pickup이라고 읽으면 오답이다.
- 분자: dropoff∈솔빛동인 trip의 pickup 읍면동별 사건 수
- 분모: count에는 나눗셈 분모 없음
- 집계 단위: 한 실차 구간(trip) = 사건 한 건, 고유 taxi/통행 edge 수 아님
- Inner: group count (inherent sum); Outer: 없음; order=top, limit=4.
- 반환: dimension=emd, dimension_target=pickup의 group 목록
- 통계식: `top4_g sum_trip 1[dropoff in S and emd(pickup)=g]`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Stage/OD 구조는 표현되지만 지역 의도 또는 실행 가능성은 별개다.
- Concept/role/source/value: LOCATION/place SUBCOND user value={"name":"솔빛동","region":""}; AMOUNT/trip_count MEASURE implicit value 없음; EVENT/trip SUPPORT implicit value 없음. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 정확한 OD 의도와 filter/target 방향은 확정 가능하다. od_role의 scope_pickup/scope_dropoff binding과 dimension_target mapping은 현재 deterministic registry/compiler가 지원한다. / 그러나 솔빛동은 mock/reference gazetteer에 없고 현재 실행이 NOT_FOUND로 실패한다. NOT_FOUND는 pipeline unsupported 코드가 아니라 failed outcome이다. / Mock trip count는 고정 count/지역 fixture 목록을 반환한다. 실제 trip를 필터하고 사건을 세는 의미 검증 provider가 아니다. Reference provider는 get_trip_count를 지원하지 않는다.
- 실패 유형: provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: OD filter 방향/target은 원문에서 명확; 유일한 명명 scope 솔빛동의 provider context가 없음
- 사람이 선택할 항목: P0_corpus_scope, P6_synthetic_place_scope
- 선택 후 주의: 원문을 유지하는 semantic-only annotation을 허용할지, 현 질문의 실행 provider 지원을 기다릴지, 검증된 장소를 명시한 새 queue로 재검토할지 결정한다. 방향을 고치거나 unknown place를 semantic unsupported로 바꾸지 않는다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "dropoff"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c2",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c3",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260901-20260930",
    "dimension": "emd",
    "dimension_target": "pickup",
    "limit": 4,
    "order": "top"
  }
}
```

실제 mock 실행: `get_place_scope / NOT_FOUND`. Direction/target을 바꾸어 해결할 문제는 아니다.

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25), [mock_responses.py:317](/home/hwkim/assistant_univ/mock_responses.py:317)

### RB001-24 — implementation_gap

- 질문: 2026년 9월 솔빛동에서 하차한 실차 구간을 읍면동 승차지별로 세면 건수가 많은 4곳은?
- 정확한 의미: 솔빛동은 하차 장소의 filter(od_role=dropoff)다. 결과 그룹은 읍면동 승차지(dimension_target=pickup)이며 건수 상위 4개다. 에서라는 조사만으로 pickup이라고 읽으면 오답이다.
- 분자: dropoff∈솔빛동인 trip의 pickup 읍면동별 사건 수
- 분모: count에는 나눗셈 분모 없음
- 집계 단위: 한 실차 구간(trip) = 사건 한 건, 고유 taxi/통행 edge 수 아님
- Inner: group count (inherent sum); Outer: 없음; order=top, limit=4.
- 반환: dimension=emd, dimension_target=pickup의 group 목록
- 통계식: `top4_g sum_trip 1[dropoff in S and emd(pickup)=g]`
- Schema: concepts/factors flat contract로 현재 제안은 strict parse 가능. Stage/OD 구조는 표현되지만 지역 의도 또는 실행 가능성은 별개다.
- Concept/role/source/value: LOCATION/place SUBCOND user value={"name":"솔빛동","region":""}; AMOUNT/trip_count MEASURE implicit value 없음; EVENT/trip SUPPORT implicit value 없음. 날짜/taxi_type은 factors이며 runtime/source/tool 필드를 target에 넣지 않는다.
- MacroComposer: PASS; Validator: PASS. 이는 target semantics의 근거가 아니라 구조 확인이다.
- Compiler/Provider: 정확한 OD 의도와 filter/target 방향은 확정 가능하다. od_role의 scope_pickup/scope_dropoff binding과 dimension_target mapping은 현재 deterministic registry/compiler가 지원한다. / 그러나 솔빛동은 mock/reference gazetteer에 없고 현재 실행이 NOT_FOUND로 실패한다. NOT_FOUND는 pipeline unsupported 코드가 아니라 failed outcome이다. / Mock trip count는 고정 count/지역 fixture 목록을 반환한다. 실제 trip를 필터하고 사건을 세는 의미 검증 provider가 아니다. Reference provider는 get_trip_count를 지원하지 않는다.
- 실패 유형: provider_limitation
- Semantic unsupported: 아니오. 기존 taxonomy에 해당 metric과 질문 구조가 있다.
- Ambiguity: OD filter 방향/target은 원문에서 명확; 유일한 명명 scope 솔빛동의 provider context가 없음
- 사람이 선택할 항목: P0_corpus_scope, P6_synthetic_place_scope
- 선택 후 주의: 원문을 유지하는 semantic-only annotation을 허용할지, 현 질문의 실행 provider 지원을 기다릴지, 검증된 장소를 명시한 새 queue로 재검토할지 결정한다. 방향을 고치거나 unknown place를 semantic unsupported로 바꾸지 않는다.
- Canonical grounding 범위: not yet an unconditional supported target. 수정한 target이나 unsupported label은 아직 없다.

현재 원문을 보존하는 canonical grounding (조건부 의미 제안; 무조건 supported gold가 아님):

```json
{
  "concepts": [
    {
      "attributes": {
        "od_role": "dropoff"
      },
      "concept": "LOCATION",
      "id": "c1",
      "role": "SUBCOND",
      "source": "user",
      "subtype": "place",
      "text": "솔빛동",
      "value": {
        "name": "솔빛동",
        "region": ""
      }
    },
    {
      "concept": "AMOUNT",
      "id": "c2",
      "role": "MEASURE",
      "source": "implicit",
      "subtype": "trip_count"
    },
    {
      "concept": "EVENT",
      "id": "c3",
      "role": "SUPPORT",
      "source": "implicit",
      "subtype": "trip"
    }
  ],
  "factors": {
    "date": "20260901-20260930",
    "dimension": "emd",
    "dimension_target": "pickup",
    "limit": 4,
    "order": "top"
  }
}
```

실제 mock 실행: `get_place_scope / NOT_FOUND`. Direction/target을 바꾸어 해결할 문제는 아니다.

- Contrast chosen: place.od_role=dropoff
- Contrast rejected: place.od_role=pickup
- 차이: 솔빛동에서 내린 trip이 아니라 솔빛동에서 탄 trip을 필터한다. 에서라는 조사보다 하차 동사가 우선이다.
- Gold와 pair는 독립 decision 단위다. Pair를 수락하려면 chosen이 정확하고 rejected가 잘못된 의미라는 human attestation이 별도로 필요하다.

근거: [prompts/geoflow_planner.yaml:180](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:180), [prompts/geoflow_planner.yaml:335](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:335), [prompts/geoflow_planner.yaml:248](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248), [geoflow/factors.py:112](/home/hwkim/assistant_univ/geoflow/factors.py:112), [tool_handlers.py:25](/home/hwkim/assistant_univ/tool_handlers.py:25), [geoflow/operator_registry.py:443](/home/hwkim/assistant_univ/geoflow/operator_registry.py:443), [schemas/tims.yaml:103](/home/hwkim/assistant_univ/schemas/tims.yaml:103), [geoflow_macros/od_event_to_measure.yaml:12](/home/hwkim/assistant_univ/geoflow_macros/od_event_to_measure.yaml:12), [geoflow/pipeline.py:68](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [geoflow/pipeline.py:156](/home/hwkim/assistant_univ/geoflow/pipeline.py:156), [mock_responses.py:258](/home/hwkim/assistant_univ/mock_responses.py:258), [mock_responses.py:394](/home/hwkim/assistant_univ/mock_responses.py:394), [training/annotations/workflow.py:25](/home/hwkim/assistant_univ/training/annotations/workflow.py:25), [mock_responses.py:317](/home/hwkim/assistant_univ/mock_responses.py:317)

## 결정 가능한 수와 기존 workflow 제약

- 이번 대상은 **21 record(원래 보류 19 + 지역 추가 확인 2)**다. 현재 A 2건은 reference 범위의 accepted, B 6건은 default TIMS runtime unsupported를 코드 근거로 최종 확인할 수 있어 원래 보류 중 8건의 기술적 결론을 좁혔다. C 9건은 위 선택으로 범위를 정하고, D 4건은 semantic-only 수락 또는 구현 대기 중 선택한다.
- 사람의 범위/정의 선택 후 **21건 모두 human decision audit을 기록할 수 있다**. 구현 gap이 남은 경우 status=needs_fix 또는 학습 제외라면 rejected를 기록하는 것도 실제 decision이다. 21건 accepted gold를 만들 수 있다는 뜻은 아니다. 현재 실행까지 검증된 unconditional accepted 근거는 reference-only 2건이고, 선택만으로 나머지 구현/통계 의미가 완성되지는 않는다.
- 기존 workflow STATES는 accepted/rejected/needs_fix이다. `unsupported`는 허용된 human status가 아니다. B의 unsupported는 현재 runtime outcome이며, answered 후보를 제외하는 최종 human 판정은 rejected(사유에 runtime 코드) 또는 보류 needs_fix로 남길 수 있다. Grounding 의미 corpus로 수락한다면 current target을 유지하고 provider/runtime scope를 이유에 명시한다.
- 기존 queue expected_outcome=answered를 corrected_grounding={"unsupported":true}로 바꾸면 import_reviewed가 거부한다. Refusal 보호 family도 우회할 수 없다. 이 작업은 label/outcome/contract/status 변경을 수행하지 않았다.
- 동구에 region을 추가하거나 합성 장소를 실제 지명으로 치환하려면 질문/lineage도 새 버전으로 검토해야 한다. 이 resolution 파일이나 기존 draft를 decisions.jsonl로 rename/복사하지 않는다.
- 향후 human 확정에는 기존 workflow decide를 쓰되 accepted는 semantic/support/lineage를 실제 확인하고 pair는 --negative-is-wrong도 확인한다. 여기서는 결정 audit/import/GPU 실행을 수행하지 않았다.

## 재현·무변경 확인

- Git commit: `65e9ea2ec98f8cec289cbb753ce543dee3efdd92`; branch: `geoflow/dev-v2`.
- Queue hash: `880cca2920a68d5e84f7a6f1d43372a19fe46ec110cf41007f2ce050c7907808`.
- Existing draft hash: `88cf474eb2a9d9ac827303f307681738a7eb0b3cdd033f202827d36da5ef62fe`.
- Resolution UTC: 2026-10-04T13:08:52.521704+00:00.
- 각 JSONL record에 원본 candidate/draft hash, code/schema/provider/source hash, per-provider 실행 근거, 분류 범위와 product 선택지를 저장했다. 기존 96 queue records는 전부 pending이며 보호된 50건도 변경되지 않았다.
- 조사 중 코드·schema·contract·기존 draft/status는 수정하지 않았다. 추가 candidate 생성, 모델 inference/GPU 학습, 자동 unsupported/accepted 승인은 하지 않았다.
