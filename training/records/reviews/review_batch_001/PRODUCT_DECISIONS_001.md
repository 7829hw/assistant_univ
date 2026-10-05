# PRODUCT_DECISIONS_001 — 최종 product/corpus 정책 권고안

**권고: semantic grounding gold와 실행 정답 검증을 분리한다. 지금 수락을 권할 수 있는 것은 19 record, 보류는 11 record, semantic corpus에서 rejected를 권하는 것은 0 record다.** RPM 17–20의 원문이 passage 발생 위치를 뜻한다고 사람이 확인하면 23 수락 가능 / 7 보류로 좁힐 수 있다. 통계 정의가 미정인 10–16은 정책 선택만으로 수락하지 않는다.

이 문서는 최종 human decision을 위한 제안이다. 실제 queue/status, draft, resolution, grounding, production code는 그대로다. `decisions.jsonl` 생성, import, candidate 생성, GPU 작업은 수행하지 않았다. 아래 `accepted`는 **정책 채택 및 항목별 human attestation 후 가능한 권고 상태**이며 자동 승인 결과가 아니다.

## 1. 판단 범위와 현재 코드가 보장하는 것

- **Semantic gold:** 질문에 주어진 의미를 현재 planner `concepts`/`factors` flat contract로 정확히 투영했는가. source/role/value, inner/outer, 값/구간 반환, OD 필터/차원을 검토한다. Provider가 실제 답을 계산하는지는 독립 속성이다.
- **실행 정답 benchmark:** 선언한 provider·날짜 기준·입력 데이터·통계 정의에 대해 실제 출력 정답이 검증된 경우만 해당한다. 컴파일이나 mock 성공만으로 포함하지 않는다.
- **지원/배선 진단:** 컴파일 지원 여부, scope 조회 실패, mock 실행, G1–G7 결과는 계속 보존한다. 실행 정답 benchmark에서 빠진 항목도 원래의 지원 진단 분모에서 없애지 않는다.
- `training/data/validation.py`의 `outcome="answered"`는 parse/compose/validate 통과를 표시한다. Compiler/Executor가 답을 계산했다는 뜻이 아니다. [validation.py](/home/hwkim/assistant_univ/training/data/validation.py:13)
- 현재 importer는 semantic 확인 후 SFT/DPO 형식을 만들고, 별도 full runtime execution을 gold 포함의 필수 조건으로 요구하지 않는다. 다만 보호 corpus, source hash, 동일 질문 충돌, semantic-family split을 검사한다. [workflow.py](/home/hwkim/assistant_univ/training/annotations/workflow.py:235)
- 원본 example store도 reference 합성 예제의 계산 검증과 나머지 예제의 조합/의미 검토를 구별한다. [question_graph_examples.yaml](/home/hwkim/assistant_univ/geoflow_examples/question_graph_examples.yaml:1)

**Runtime `unsupported`와 planner semantic `unsupported`는 서로 다른 판정이다.** RESOLUTION의 ready_to_mark_unsupported 05/07/17–20은 default TIMS contract의 실행 범위 판정이었다. 이 문서의 정책은 그 결과를 지우지 않고 별도로 보존한다. 같은 질문의 grounding을 `{"unsupported":true}`로 재라벨하지 않는다. 현재 queue는 answered 후보이며 importer도 그러한 outcome 변경을 거부한다. [pipeline.py](/home/hwkim/assistant_univ/geoflow/pipeline.py:68), [workflow.py](/home/hwkim/assistant_univ/training/annotations/workflow.py:270)

## 2. 일곱 정책의 권장안·대안·영향

### P0. Corpus 범위

**권장: 의미가 확정되고 현재 raw contract로 표현되는 semantic grounding을 gold로 검토하며, provider 실행 범위는 별도로 기록한다.** 이 corpus는 답의 수치나 provider 지원 여부를 보증하는 corpus가 아니다. Provider gap이 원문 의미를 바꾸지 않는 05/07, OD 21–24를 semantic gold로 사용할 수 있다. 반면 10–16처럼 어떤 통계를 묻는지 정해지지 않은 문항은 이 정책에서도 보류한다.

**대안: 특정 provider에서 실행 가능한 것만 학습에 넣는다.** Default TIMS 기준 03/04/05/07 및 17–24는 실행 가능 gold subset에서 제외된다. 10–16도 통계 정의 때문에 보류다. Mock 성공 11 record를 실제 실행 정답이 검증된 11 gold라고 부를 수는 없다. Reference 03/04는 reference를 허용하는 별도 실행 suite에서만 가능하다.

**영향:** 권장안은 stage selection과 OD 의미의 학습 기회를 보존한다. 대안의 제외는 학습 범위 제한이지 semantic 오류 판정이 아니다. 어느 쪽도 기존 evaluation/dev-origin 보호 50건을 편입하지 않는다.

### P1. 동구·중구의 region

**권장: 원문에 상위 지역이 없으면 `value={"name":"동구" 또는 "중구","region":""}`를 유지한다.** Grounding은 명칭 추출까지 정확하면 된다. 실제 도시 식별은 downstream에서 미해결 상태로 다룬다. 02/05/06/07에 대구를 자동 보충하지 않는다. [planner place rule](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:248)

**대안: 도시가 확정될 때까지 해당 4건을 hold한다.** 또는 사람이 의도한 도시를 원문에 명시하는 새 question/queue version을 이후에 만든다. 현재 원문을 유지하면서 region만 채우는 방안은 권하지 않는다.

**영향:** 권장안에서 02/05/06/07은 semantic accepted 가능. 대안에서는 이 4건이 추가 hold된다. Mock의 동구→대구 fixture는 사용자 의도의 증거가 아니다. 실제 geography answer benchmark에는 도시 확인 전 포함하지 않는다. 현재 lookup은 고정 이름 fixture를 선택하며 후보 도시 해소를 구현하지 않는다. [mock lookup](/home/hwkim/assistant_univ/mock_responses.py:258)

### P2. 가동 택시 대수

**권장: 후속 annotation의 통계 정의는 일별 고유 활성 택시 수 `A_d`의 시계열을 기준으로 삼되, 현재 10/11/13–16은 hold한다.** `A_d`는 날짜 d에 영업한 고유 택시 수이며 Billing의 소속 지역·택시 유형 집단 안에서 센다.

| ID | 권장 정의가 나중에 명시·검증되었을 때의 통계 |
|---|---|
| 10/11 | 지정 달의 일별 `A_d` 평균; private/corporate 각각 |
| 13/14 | 각 월 일별 `A_d`의 최솟값 → 두 월의 최솟값을 동일 가중 평균 |
| 15/16 | 각 월 일별 `A_d` 평균 → 두 월 평균 중 최솟값 |

**대안:** 기간에 한 번이라도 영업한 고유 taxi 집단 `|union_d Active_d|`를 센다. 이는 일별 대수 평균과 다른 통계이고, 현재 질문을 그대로 이 정의의 gold로 확정할 수 없다. Vendor scalar 정의에 맡기는 대안도 API 대응을 확인할 뿐 강한 semantic 정답을 증명하지 못한다.

**영향:** 일별 정의 채택 자체가 현재 TIMS 기간 통계의 사실은 아니다. 현재 code는 하루 정의만 있고 기간 집계는 미정이라고 명시하며, daily scalar들로 기간 값을 합성하지 못하도록 제한한다. 표본 단위/모집단을 raw factor로 지정할 수도 없다. 따라서 10/11/13–16은 지금 accepted로 이동하지 않는다. 이후 명시적인 질문/annotation 정의와 provider 근거 또는 분리된 검증 데이터가 필요하다. [measures.py](/home/hwkim/assistant_univ/geoflow/measures.py:88), [planner metric definitions](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:205)

### P3. 가동률 중앙값

**권장: 후속 정의는 날짜별 `r_d=A_d/R_d`를 먼저 구하고 그 비율들의 중앙값을 취한다. 현재 12는 hold한다.** `R_d`는 동일 날짜·소속 지역·택시 유형의 등록 택시 집단 크기이며 영업하지 않은 등록 택시도 포함하는 정의를 권한다. 평균 비율, 전체 기간 하나의 비율, 택시별 비율의 중앙값과 구별한다.

**대안:** 기간 활성 고유 대수 / 기간 등록 집단, 또는 전체 활성 taxi-day / 전체 등록 taxi-day를 사용한다. 이는 median of daily ratios와 다르며 현 질문을 변경 없이 동일 gold로 삼을 수 없다. Vendor med 의미를 확인하지 않고 수락하는 방안은 권하지 않는다.

**영향:** 현재 코드에 활성/등록 비율의 큰 정의는 있지만 날짜별 분모의 scope/type/date 적용 및 median 표본은 없다. 선택을 새로운 사실로 간주하지 않는다. 12는 계속 hold이며 위 정의를 사용할 후속 annotation과 분모 검증 근거를 함께 준비해야 한다. [measures.py](/home/hwkim/assistant_univ/geoflow/measures.py:94), [TIMS billing schema](/home/hwkim/assistant_univ/schemas/tims.yaml:176)

### P4. 결측일·무영업일·분모

**권장: 새 active metric annotation 기준은 ‘완전히 관측된 지정 달력 기간’으로 정하고, 확인된 무영업일은 0, 미수집/미확인 날짜와 분모 0은 보류한다.** 이는 corpus 정의 제안이며 현재 runtime 정책을 바꾸지 않는다.

- 10/11의 2026년 9월은 모든 날짜 관측이 확인되면 분모 30일. 무영업이 실제 확인된 날은 `A_d=0`으로 포함한다.
- 13/14/15/16은 8월 31일·9월 30일을 각각 inner 표본으로 삼는 정의다. 13/14 outer 평균은 두 월에 동일 가중을 준다. 15/16은 월별 평균을 비교한다.
- 12는 모든 날짜에 `R_d>0`이고 관측이 완전할 때만 일별 비율 중앙값을 정의한다. 영업 0이며 등록 집단이 양수이면 비율 0; `R_d=0`은 0/0을 0으로 만들지 않는다.
- 주별 기존 gold는 기존 interval/calendar/provider 정의를 유지한다. Reference revenue의 결측 아닌 taxi-day 표본 제외 규칙을 active count/ratio에 복사하지 않는다.

**대안:** 관측되고 정의된 날짜만 표본으로 사용한다. 이 경우 평균 분모가 달력 일수에서 유효 날짜 수로 바뀌고, 미수집 패턴에 따라 결과가 달라진다. 적용하려면 원문/annotation이 이 조건을 명시하고 실제 구현도 보장해야 한다.

**영향:** 현재 schema에는 sample_unit, missing-date 정책, denominator population을 담는 raw factor가 없고 native TIMS가 권장안을 보장하는 계약도 없다. 정의 선택만으로 10–16을 수락하지 않는다. 결측/분모 확인 전 임의 zero-fill, 등록 집단 추정, stage pair 수락을 하지 않는다. 기존 02/06/07/08의 vendor 위임된 평균 모집단은 실행 정답 검증의 미확인 조건으로 남긴다. [TIMS unresolved contracts](/home/hwkim/assistant_univ/geoflow/tims_contract.py:110), [reference provider](/home/hwkim/assistant_univ/reference_provider.py)

### P5. 공간 의미

**권장: 코드에 정의된 metric별 공간 의미를 보존한다. Billing은 택시 소속 지역, RPM/passage는 관측 발생 위치, OD는 명시된 pickup/dropoff 발생 위치다.** 실제 운행 위치의 고유 택시 대수를 Billing active count로 대체하지 않는다. [billing schema](/home/hwkim/assistant_univ/schemas/tims.yaml:177), [passage schema](/home/hwkim/assistant_univ/schemas/tims.yaml:45), [OD bindings](/home/hwkim/assistant_univ/geoflow/operator_registry.py:435)

**대안:** active count를 그 지역 도로를 실제 운행한 고유 taxi 수로 해석하거나, RPM을 해당 지역 소속 taxi의 모든 장소에서의 RPM으로 해석한다. 현재 전자는 occurrence distinct-taxi 통계/ID가 없고 후자는 passage tool에 affiliation cohort filter가 없으므로 기존 proposed target과 동치가 아니다.

**영향과 필요한 한 번의 원문 확인:** 17–20의 ‘솔빛동 택시’는 소속과 발생 위치 양쪽으로 읽힐 수 있다. Metric의 현재 구현이 passage라는 사실만으로 사람의 의도를 확정하지 않는다. 현재는 hold를 권한다.

- 사람이 **‘솔빛동에서 기록된 passage RPM’**을 의도했다고 확인하면 17/19 chosen 및 18/20 stage-swap pair는 semantic accepted 가능하다. 주 max→avg와 주 avg→max는 다른 통계이며 pair별 negative 확인은 별도로 한다. 실행 unsupported는 그대로다.
- **‘솔빛동 소속 택시가 모든 장소에서 기록한 RPM’**이 의도라면 17–20은 needs_fix/hold 유지. 현재 occurrence target을 수락하지 않는다. 현 contract에서 cohort 조건이 표현/실행되지 않는다는 gap을 남긴다.
- **의도 미확인**이면 hold 유지. 원문 명확화가 필요하면 기존 queue를 덮어쓰지 않고 향후 새 버전으로 검토한다.

10/11의 ‘주변’도 현재 mock이 공간 확장을 수행하지 않으며 발생 지역인지 소속 지역인지 원문 확인이 필요하다. `vicinity=true`가 전달되는 것과 의미에 맞는 주변 범위가 구현된 것은 다르다. [mock scope lookup](/home/hwkim/assistant_univ/mock_responses.py:258)

### P6. 합성 장소 예제

**권장: 사람이 의미·lineage를 검토한 합성 명칭은 literal semantic gold로 허용하고 실행 검증 범위를 제한한다.** 원문 `name`과 `region=""`를 보존한다. Synthetic이라는 이유로 장소 scope를 만들어 넣거나 실제 fixture 지명으로 치환하지 않는다.

**대안:** 실지명만 허용하거나 모든 항목에 동일 provider의 실행 가능성을 요구한다. 전자는 03/04/10–24를 이번 corpus에서 제외한다. 후자는 실행 미구현 때문에 의미적으로 명확한 OD 사례까지 놓친다. 검증된 실지명으로 바꾼 질문을 이후 새 버전으로 만드는 선택은 가능하지만 현재 문항을 silent correction하지 않는다.

**영향:** 21–24는 semantic gold로 수락 가능하다. 03/04는 이미 원본이 reference 합성 데이터 범위를 선언했으므로 reference suite에서만 실행 정답 검증 대상으로 유지한다. 10–16의 통계 모호성이나 17–20의 공간 의도 모호성은 합성 명칭 허용만으로 해결되지 않는다.

## 3. RB001-21–24: semantic gold와 실행 benchmark의 분리

| ID | Semantic 판단 | negative 판단 | default provider 실행 | 권장 포함 범위 |
|---|---|---|---|---|
| RB001-21 | LOCATION/place SUBCOND user의 `od_role=pickup`; `dimension=emd`, `dimension_target=dropoff`, top 4 | gold record | compile PASS, 솔빛동 lookup NOT_FOUND | semantic gold 가능; 실행 정답 benchmark 제외 |
| RB001-22 | chosen은 21과 동일 | rejected의 필터 `od_role=dropoff`는 출발 장소 조건을 도착 장소 조건으로 바꾸므로 오답 | chosen/rejected 모두 구조 통과 가능; lookup 실패 | semantic DPO pair 가능; 실행 정답 benchmark 제외 |
| RB001-23 | 장소 필터 `od_role=dropoff`; `dimension=emd`, `dimension_target=pickup`, top 4 | gold record | compile PASS, 솔빛동 lookup NOT_FOUND | semantic gold 가능; 실행 정답 benchmark 제외 |
| RB001-24 | chosen은 23과 동일 | rejected의 필터 `od_role=pickup`은 도착 장소 조건을 출발 장소 조건으로 바꾸므로 오답 | chosen/rejected 모두 구조 통과 가능; lookup 실패 | semantic DPO pair 가능; 실행 정답 benchmark 제외 |

OD의 사건 SUPPORT와 측정 MEASURE는 현재 production prompt의 implicit 규칙을 따른다. 질문이 준 장소 값은 user이며 날짜/order/limit/dimension은 factor다. 실제 scope와 tool binding을 모델 target에 추가하지 않는다. `dimension_target`은 반환 그룹의 축이고 `od_role`은 필터의 축이므로 둘을 하나로 합치지 않는다. [implicit rules](/home/hwkim/assistant_univ/prompts/geoflow_planner.yaml:328), [trip schema](/home/hwkim/assistant_univ/schemas/tims.yaml:60)

Lookup NOT_FOUND는 현재 pipeline에서 failed이며 semantic unsupported의 증거가 아니다. Reference provider는 이 trip 통계를 구현하지 않는다. Mock의 fixed count 역시 실제 OD 집계 정답 검증을 대신하지 못한다. [pipeline.py](/home/hwkim/assistant_univ/geoflow/pipeline.py:146), [mock trip count](/home/hwkim/assistant_univ/mock_responses.py:317)

## 4. 30건 ID별 예상 상태

첫 상태 열은 권장 corpus 정책을 채택하되 **확인되지 않은 RPM 공간 의도를 보류**했을 때의 권고다. 다음 열은 사람이 RPM 발생 위치 의도를 확인한 경우만의 변경이다. 질문/target 수정 없이 의미 범위를 확인할 수 있는지 각 항목을 최종 검토해야 한다. Pair의 accepted는 chosen 수락과 negative가 틀렸다는 별도 판단을 모두 전제로 한다.

실행 열 범례:

- **M:** 기존 mock 실행 성공. 배선 진단용이며 실제 통계 정답 검증은 안 됨.
- **M/G:** mock 성공이지만 동구의 도시 해소는 미확정. 실제 지리 답 benchmark 제외.
- **R:** 원본 reference synthetic 범위에서 정답 재현. 별도 reference suite만 가능; default mock은 NOT_FOUND.
- **R/U:** reference에서 정답 재현, default TIMS 계약에서는 unsupported. Reference suite와 default 지원 진단을 분리.
- **U/G:** default TIMS의 bucket 선택 compile unsupported + 도시 미확정. 실행 정답 benchmark 제외.
- **H:** 통계 정의 또는 공간 의도 미정. 실행 정답 benchmark 제외.
- **U:** grouped RPM compile unsupported. 실행 정답 benchmark 제외; 지원 진단에는 실패로 남김.
- **L:** OD compilation 가능, synthetic place lookup NOT_FOUND. 실행 정답 benchmark 제외.

| ID | 질문 | 기본 권고 | RPM 발생 위치 확인 후 | 핵심 의미/보류 사유 | 실행 범위 |
|---|---|---|---|---|---|
| RB001-01 | 지난달 수성구 개인택시의 주별 운행일수 합계를 평균 내면? | accepted | accepted | 주별 operating_days sum→avg | M |
| RB001-02 | 2026년 상반기 동구 법인택시 월별 매출 평균 중 가장 큰 값은? | accepted | accepted | 월별 revenue avg→max; 동구 region=""는 원문 보존 | M/G |
| RB001-03 | 2026년 8월 나래구 개인택시 주별 매출 합계 중 가장 작은 값은? | accepted | accepted | reference의 주별 revenue sum→min; 합성 나래구 범위 명시 | R |
| RB001-04 | 2026년 8월 나래구 개인택시 매출 평균이 가장 낮았던 주는 언제야? | accepted | accepted | reference의 주별 revenue avg→최소 주 선택; 값 반환과 구별 | R/U |
| RB001-05 | 2026년 상반기 중구 개인택시 운행일수 합계가 가장 많았던 달은? | accepted | accepted | 월별 operating_days sum→최대 달 선택; 중구 region="" 유지 | U/G |
| RB001-06 | 지난달 동구 법인택시 주별 운행일수 평균 중 가장 작은 값은? | accepted | accepted | 주별 operating_days avg→min 값; 동구 region="" 유지 | M/G |
| RB001-07 | 지난달 동구 법인택시의 운행일수 평균이 가장 적었던 주는? | accepted | accepted | 주별 operating_days avg→최소 주 선택; 06의 숫자 답과 구별 | U/G |
| RB001-08 | 지난달 달서구 개인택시 주별 운행일수 평균들의 평균은? | accepted | accepted | 주별 operating_days avg→avg; 전체 기간 평균으로 바꾸지 않음 | M |
| RB001-09 | 2026년 9월 10일 개인택시 매출 평균이 높은 시도 3곳은? | accepted | accepted | sido dimension, revenue avg, top 3; 위치 SUBCOND 추가 금지 | M |
| RB001-10 | 2026년 9월 솔빛동 주변 개인택시의 평균 가동 택시 대수는? | needs_fix / hold | needs_fix / hold | 활성 대수 평균의 날짜 표본·소속/발생 위치·주변 범위 미확정 | H |
| RB001-11 | 2026년 9월 솔빛동 주변 법인택시의 평균 가동 택시 대수는? | needs_fix / hold | needs_fix / hold | 10과 같은 보류 원인; taxi_type=corporate를 private로 바꾸지 않음 | H |
| RB001-12 | 2026년 9월 해솔동 개인택시 가동률의 중앙값은? | needs_fix / hold | needs_fix / hold | 가동률 중앙값의 날짜 표본·등록 분모 범위·분모 0 처리 미확정 | H |
| RB001-13 | 2026년 8월과 9월 온유동의 월별 가동 택시 대수 최솟값의 평균은? | needs_fix / hold | needs_fix / hold | 월 min→avg이나 inner 활성 대수의 관측 단위 미확정 | H |
| RB001-14 | 2026년 8월과 9월 온유동의 월별 가동 택시 대수 최솟값의 평균은? | needs_fix / hold | needs_fix / hold | 13의 stage-swap pair; chosen 정의부터 확인해야 함 | H |
| RB001-15 | 2026년 8월과 9월 온유동의 월별 평균 가동 택시 대수 중 최솟값은? | needs_fix / hold | needs_fix / hold | 월 avg→min이나 inner 활성 대수의 관측 단위 미확정 | H |
| RB001-16 | 2026년 8월과 9월 온유동의 월별 평균 가동 택시 대수 중 최솟값은? | needs_fix / hold | needs_fix / hold | 15의 stage-swap pair; chosen 정의부터 확인해야 함 | H |
| RB001-17 | 2026년 9월 솔빛동 택시의 주마다 구한 엔진 회전수 최댓값의 평균은? | needs_fix / hold | accepted | 주별 RPM max→avg; 발생 위치와 소속 taxi cohort 중 의도 확인 | U; 원문 의도 H |
| RB001-18 | 2026년 9월 솔빛동 택시의 주마다 구한 엔진 회전수 최댓값의 평균은? | needs_fix / hold | accepted | 17의 stage-swap pair; 원문의 공간 의도 확인 후 negative 판정 | U; 원문 의도 H |
| RB001-19 | 2026년 9월 솔빛동 택시의 주마다 평균 낸 엔진 회전수 중 최댓값은? | needs_fix / hold | accepted | 주별 RPM avg→max; 발생 위치와 소속 taxi cohort 중 의도 확인 | U; 원문 의도 H |
| RB001-20 | 2026년 9월 솔빛동 택시의 주마다 평균 낸 엔진 회전수 중 최댓값은? | needs_fix / hold | accepted | 19의 stage-swap pair; 원문의 공간 의도 확인 후 negative 판정 | U; 원문 의도 H |
| RB001-21 | 2026년 9월 솔빛동에서 승차한 실차 구간을 읍면동 하차지별로 세면 건수가 많은 4곳은? | accepted | accepted | pickup 장소 필터 + emd/dropoff 상위 4; 필터와 반환 dimension 분리 | L |
| RB001-22 | 2026년 9월 솔빛동에서 승차한 실차 구간을 읍면동 하차지별로 세면 건수가 많은 4곳은? | accepted | accepted | 21 chosen과 pickup→dropoff 필터 오류 negative의 pair | L |
| RB001-23 | 2026년 9월 솔빛동에서 하차한 실차 구간을 읍면동 승차지별로 세면 건수가 많은 4곳은? | accepted | accepted | dropoff 장소 필터 + emd/pickup 상위 4; 필터와 반환 dimension 분리 | L |
| RB001-24 | 2026년 9월 솔빛동에서 하차한 실차 구간을 읍면동 승차지별로 세면 건수가 많은 4곳은? | accepted | accepted | 23 chosen과 dropoff→pickup 필터 오류 negative의 pair | L |
| RB001-25 | 2026년 9월 읍면동 승차지별 실차 구간 건수가 적은 4개 그룹은? | accepted | accepted | emd/pickup trip_count 하위 4; 사건 count를 avg로 바꾸지 않음 | M |
| RB001-26 | 2026년 9월 읍면동 승차지별 실차 구간 건수가 적은 4개 그룹은? | accepted | accepted | 25 chosen과 pickup→dropoff dimension 오류 negative의 pair | M |
| RB001-27 | 2026년 9월 읍면동 승차지와 하차지 조합별 실차 구간 건수가 적은 4개 그룹은? | accepted | accepted | emd/both는 ordered pickup–dropoff 조합; 한쪽 marginal이 아님 | M |
| RB001-28 | 2026년 9월 읍면동 승차지와 하차지 조합별 실차 구간 건수가 적은 4개 그룹은? | accepted | accepted | 27 chosen과 both→pickup 차원 축소 오류 negative의 pair | M |
| RB001-29 | 2026년 9월 읍면동 하차지별 실차 구간 건수가 적은 4개 그룹은? | accepted | accepted | emd/dropoff trip_count 하위 4 | M |
| RB001-30 | 2026년 9월 읍면동 하차지별 실차 구간 건수가 적은 4개 그룹은? | accepted | accepted | 29 chosen과 dropoff→pickup dimension 오류 negative의 pair | M |

**상태 합계:** 기본 권고 accepted 가능 19 / needs_fix·hold 11 / rejected 0. RPM 발생 위치 확인 후 accepted 가능 23 / hold 7 / rejected 0. 현재 실제 승인 수는 여전히 0이다.

19 record에는 같은 질문의 gold/pair가 함께 있으므로 19개 새 SFT 질문이 아니다. 사람이 전부 수락하고 기존 보호·split 검사가 통과한다는 전제에서 질문 중복을 제거하면 **14개 question과 5개 pair**다. RPM 4 record까지 확인하면 **16개 question과 7개 pair**가 된다. 최종 train/validation 수나 next-pilot 실행 가능성을 여기서 보증하지 않는다.

## 5. 대안 선택에 따른 ID 상태 변화

복잡한 조합 grid 대신 **다른 정책은 기본 권고를 유지하고 해당 선택 하나만 바꾼 경우**를 비교한다. 실행 제외는 해당 목적의 제외이며 semantic wrong 판정과 구별한다.

| 선택 | 바뀌는 ID/범위 | 예상 상태/영향 |
|---|---|---|
| 권장 bundle | 01–09,21–30 | accepted 가능 19; 10–20 hold 11 |
| RPM 원문의 발생 위치 의도 확인 | 17–20 | hold→accepted 가능; 전체 23/7/0 |
| RPM은 소속 taxi cohort 의미 | 17–20 | hold 유지; current target 불일치와 표현/실행 gap. 잘못된 occurrence target을 gold로 수락하지 않음 |
| 도시를 정하지 않으면 literal gold도 불허 | 02/05/06/07 | accepted 가능→hold; 기본 결과 15 accepted 가능 / 15 hold |
| Default TIMS answered subset만 학습 | 03/04/05/07/21–24 | 이번 학습 subset에서 제외. 10–20 hold 유지. 남는 11 mock-success record도 실제 실행 정답 검증이 된 것은 아님 |
| 합성 장소를 corpus에서 전면 불허 | 03/04/10–24 | 해당 정책의 편입 제외(rejected 사유는 source policy). 남는 13 record accepted 가능. 의미적으로 틀렸다는 라벨을 붙이지 않음 |
| active count=기간 고유 대수 | 10/11/13–16 | hold 유지; 질문/통계 정의 재검토 필요. 기간 고유 대수를 daily avg/min으로 치환하지 않음 |
| ratio=기간 전체 집단 비율 | 12 | hold 유지; median 질문과 동치가 아니므로 현재 target을 수락하지 않음 |
| active metric은 관측된 유효 날짜만 집계 | 10–16 | hold 유지; 달력 일수 기준과 다른 정의. 표본/분모와 관측 근거 확인 후 새 annotation 범위를 정해야 함 |
| vendor avg/min/med로 충분하다고 가정 | 10–16 | 권하지 않음; 모호성 해결 근거가 없어 강한 semantic gold에는 hold 유지 |
| Billing 장소도 실제 도로 발생 위치로 읽음 | 10–16 및 기존 Billing gold 의미 | 현 Billing 계약과 다름. 기존 target을 재해석하지 않고 hold/다른 질문 검토. 기존 gold의 소속 지역 의미도 바뀌므로 이번 bundle의 대안으로 채택하지 않음 |

## 6. 실행 benchmark 제외를 어떻게 기록할 것인가

- **Default TIMS contract가 현재 실행을 허용하지 않음:** 04/05/07/17–20. 04의 reference 예외를 구별한다. 실행 정답 denominator에 넣지 않되 지원율에는 현재 unsupported를 기록한다.
- **실제 지역 식별 미확정:** 02/05/06/07. Mock 도시 mapping을 정답으로 쓰지 않는다.
- **Default mock에 없는 합성 장소:** 03/04/10–24. 이 중 03/04만 기존 reference gold 데이터와 계산 검증이 있다.
- **미확정 통계/공간 의도:** 10–20. 정책적 정의 제안 또는 RPM 원문 확인을 실제 provider 검증과 혼동하지 않는다.
- **Mock만 실행된 나머지:** 01/08/09/25–30도 현재는 wiring diagnostic이다. 실제 관측 데이터/정답이 없는 상태에서 TIMS의 실행 정답 성능이 검증되었다고 주장하지 않는다.

현재 이 batch에서 **독립 정답 검증된 실행 suite의 근거는 reference 03/04**다. 실제 TIMS 관측 데이터에 대한 실행 정답 benchmark로 확정할 근거는 없으며, 이 문서는 새 benchmark 질문을 만들거나 기존 evaluation corpus를 변경하지 않는다. Corpus scope별 보고를 분리하여 쉬운 실행 사례만 남긴 평균으로 지원 gap을 가리지 않는다.

## 7. 사람이 최종 선택할 항목 — 두 묶음

**선택 1 — corpus policy bundle (권장: 채택).** Semantic gold/실행 검증 분리, 원문에 없는 region은 빈 문자열, 합성 명칭 literal semantic 허용, Billing/occurrence/OD의 metric별 공간 의미 보존, active count·ratio의 후속 정의는 일별 시계열/일별 비율과 관측 완전성 기준을 채택한다. 단 **10–16은 현재 보류**한다. 이 bundle은 production contract나 runtime 통계 default를 바꾸는 승인이 아니다. 통계 정의는 향후 annotation 기준 제안이지 현재 질문의 정답을 소급 확정하는 근거가 아니다.

**선택 2 — RPM 17–20의 원문 의도 (권장 해석: 해당 장소에서 발생한 passage RPM; 사람의 확인 필수).** 옵션은 (a) 발생 위치였음, (b) 소속 taxi cohort였음, (c) 아직 미확인. (a)이면 4 record가 semantic accepted 가능으로 이동, (b)/(c)이면 hold 유지. 현재 code가 제공하는 metric에 맞추기 위해 원래 의미를 사후 변경하지 않는다. 필요하면 원문을 명확히 한 후 새 queue에서 검토한다.

선택 후 모든 30건의 인간 decision을 기록할 수 있다. 선택 2가 (a)여도 10–16은 needs_fix로 기록해야 하며 30 accepted corpus가 되는 것은 아니다. Pair 22/24/26/28/30 및 추가 가능 18/20은 각 rejected의 오류를 사람이 따로 확인해야 한다. 상태 `unsupported`는 workflow에서 허용하지 않으므로 provider 결과는 사유/별도 범위 기록으로 남긴다.

## 8. 향후 human decision 작성 시 범위 기록

이 문서를 `decisions.jsonl`로 복사/rename하지 않는다. 사람의 최종 확인 뒤 기존 workflow에 candidate_id, reviewer, reason, semantic checks 및 pair negative 확인을 기록한다. 기본안에서는 proposed grounding의 필드 수정이 필요한 항목을 새로 확정하지 않았다. 도시/장소/원문/통계가 바뀌면 기존 queue를 수정해서 lineage를 우회하지 않고 새 version을 검토한다.

`reason`에는 `PRODUCT_DECISIONS_001` 정책 선택, literal 지리 여부, provider 범위와 benchmark 제외 이유를 남기는 것을 권한다. 실행/통계 범위는 이 문서와 기존 resolution을 함께 보존한다. **현재 importer는 이 문서의 scope를 읽어 benchmark 제외를 자동 적용하지 않는다.** Human review audit은 저장하지만 provider eligibility를 위한 새 raw grounding field나 자동 benchmark gate가 생긴 것은 아니다. 후속 실행 평가 시 사람이 선언한 provider/suite를 따로 선택해야 한다.

기존 eval/dev 및 paraphrase/semantic-family 보호 50건은 계속 diagnostic-only다. 이 30건 수락 추천 또한 기존 protection 검사를 우회하지 않으며, accepted recommendation을 human review로 간주하지 않는다.

## 9. 근거 동결 및 무변경 확인

- 작성 UTC: `2026-10-04T13:33:08.788316+00:00`.
- Git: `geoflow/dev-v2` / `65e9ea2ec98f8cec289cbb753ce543dee3efdd92`. 기존 working-tree diff를 그대로 유지했다.
- Production prompt hash: `522aa3b1716248b53a755ee1b236e7aef302c85504e9cfac3825f4d3cc817945`.
- [review_batch_001.jsonl](/home/hwkim/assistant_univ/training/annotations/generated/review_batch_001/review_batch_001.jsonl) SHA256: `6a0c1c944548caf67627f6db21555c2ddbc14af3d261533581bfc035ae1b622b`.
- [decisions_draft.jsonl](/home/hwkim/assistant_univ/training/annotations/generated/review_batch_001/decisions_draft.jsonl) SHA256: `88cf474eb2a9d9ac827303f307681738a7eb0b3cdd033f202827d36da5ef62fe`.
- [resolution_001.jsonl](/home/hwkim/assistant_univ/training/annotations/generated/review_batch_001/resolution_001.jsonl) SHA256: `b1112178ae4b8cf4ad48a48a0b2903bc3d3a99892f4933ed65432060b8a1962c`.
- [RESOLUTION_001.md](/home/hwkim/assistant_univ/training/annotations/generated/review_batch_001/RESOLUTION_001.md) SHA256: `da3e253263e612072feb8d9b3ed8507287c00d6586f51082b8b80b676b2dfe9f`.
- Original queue SHA256: `880cca2920a68d5e84f7a6f1d43372a19fe46ec110cf41007f2ce050c7907808`.
- Resolution의 frozen source hash 51개 항목과 기존 batch output hash 4개를 현재 파일과 대조하여 일치 확인.
- 기존 queue 96건 전부 pending, 기존 accepted annotation 0건. 기존 draft/resolution 및 source/schema/provider/학습 데이터 파일은 변경하지 않았다. 새 파일은 이 정책 Markdown 한 개뿐이다.
