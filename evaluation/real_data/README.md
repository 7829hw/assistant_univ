# 실제 질문·업체 계약 검증 준비

작성: 2026-10-05(grounding_v15). 평가 범위·판정 규칙·요청 묶음 정리: 2026-10-05(grounding_v16).
- 지금까지의 GeoFlow 품질 수치는 mock provider·legacy 실행과 합성 문항(업체 100문항 외에는 Claude 작성, 사람 검토 없음)에서 나왔다.
- 이 디렉터리는 실제 질문과 실제 TIMS 응답으로 검증할 때 쓰는 결정표(`decisions.md`)와 기록 형식(`record_schema.json`, `validate.py`)이다.
- 실제 자료는 아직 없다.

## 1. 지금 있는 것과 없는 것

| 항목 | 상태 | 근거 |
|---|---|---|
| 실제 TIMS 연결 | **없음** | `tool_handlers.get_tool_handlers`는 `mock`과 `reference`만 허용하고 나머지는 오류로 막는다. TIMS 주소·자격 증명·provider 구현이 없다 |
| 실제 TIMS 응답 | **없음** | – |
| reference provider | 있음, **합성 데이터**(27행) | 계산 경로 검증용이며 실제 데이터 검증이 아니다(`evaluation/design/reference_provider.md`) |
| 실제 사용자 질문 | **없음** | 업체 100문항은 업체가 쓴 질문이다 |
| TIMS 계약 | schema와 업체 prompt의 정의만 | 확인 상태는 `geoflow/tims_contract.py`, 정리는 `evaluation/design/tims_lowering_contract.md` 2절에 있다 |
| 해석 결정 | D1–D4 모두 미결정 | `decisions.md` |

## 2. 평가 범위와 판정 규칙

실제 자료 검증은 네 범위로 나눠 판정한다. 범위마다 주장할 수 있는 것이 다르다.

| 범위 (`judgments.scope`) | 묻는 것 | 필요한 자료 | 이 판정으로 주장할 수 없는 것 |
|---|---|---|---|
| `meaning` | 실제 질문의 의미를 grounding과 호출로 옮겼는가 | 검토된 의미·기대 동작, GeoFlow 실행 기록(mock이어도 됨) | 실제 값, provider 동작, 전체 실행의 정확성 |
| `provider_contract` | TIMS가 계약대로 요청을 처리하는가 | 보낸 호출, 실제 응답, 계약 버전, 자료 출처(직접 호출 또는 업체 대행) | GeoFlow의 의미 해석, 전체 실행 |
| `response_interpretation` | GeoFlow가 실제 응답을 올바르게 해석·계산해 답했는가 | 실제 응답을 받은 GeoFlow 실행, 값 판정 | 질문의 의미가 맞았는지(meaning을 따로 본다) |
| `end_to_end` | 전체 실행이 사용자 요구를 충족했는가 | GeoFlow CLI가 TIMS를 직접 호출한 실행, 답한 경우 실제 응답과의 값 판정 | – |

**meaning: TIMS 없이 가능하다.**
- 실행: `assistant_cli.py --agent-mode geoflow --reference-date <질문 기준일>`을 mock으로 실행한다.
- 판정 근거(`basis`):
  - `calls`: 저장 기록의 실행 호출이나 컴파일된 `execution_plan`(scope 참조 포함)과 기대 호출을 비교한다.
  - `grounding_only`: 실제 장소가 mock gazetteer에 없어 호출 구성까지 가지 못했으면 grounding만 판정한다.
- mock 실행의 값과 장소 결과는 판정 근거가 아니다.

**정확한 거부는 실제 응답 없이 판정한다.** 판정에 필요한 것은 다음 세 가지다.
- 기대 동작이 확인 요청·지원 불가일 것.
- 실제 결과가 멈춤일 것.
- 기대 멈춤 근거(`review.expected_stop_basis`)와 실제 오류 코드가 있을 것.

**provider_contract의 두 방식:**
- 직접 호출: TIMS provider 구현이 필요하다. 지금은 없다.
- 업체 대행(`runs.kind=vendor_relay`): 업체가 정해진 호출을 실행하고 응답만 전달하는 방식이다.
  - 호출 출처(`source_run_id`), 응답 위치·자료 출처·받은 날짜, 계약 버전을 함께 남긴다.
  - 업체 대행 실행은 GeoFlow end-to-end 실행이 아니다. `validate.py`가 end_to_end 판정을 막는다.

**response_interpretation·end_to_end의 전제:** GeoFlow가 TIMS 응답을 받아 실행해야 한다.
- 지금은 TIMS provider가 없어 할 수 없다.
- 업체 대행 응답을 GeoFlow에 넣어 해석을 검증하는 재생 도구도 없다. 필요해지면 그때 만든다.

**검증 명세와의 비교 (`judgments.combination`):** 결과를 검증 조합(T2PC·B)에 귀속하려면 실행의 `geoflow_verification`이 다음을 만족해야 한다.

| 범위 | 허용하는 "다름" | 이유 |
|---|---|---|
| meaning (mock 실행) | 없음 | 검증한 조합 그대로 실행한 것이어야 한다 |
| meaning (tims 실행), provider_contract, response_interpretation, end_to_end | `provider`, `tims_execution` | 새 provider가 이 범위의 검증 대상이다 |

- 그 밖의 다름(model, model_digest, ollama_version, prompt, code, 생성 설정)은 비교 조건을 훼손한다. 확인 안 함이 있어도 같다.
- 이런 기록은 지우지 않고 `combination=unverified`로 남긴다.
- tims 실행은 "T2PC 모델·prompt·코드 + 검증 중인 새 provider"다. mock 조합과 같은 검증 결과로 표시하지 않는다.

## 3. 기록 형식과 검사가 보장하는 범위

한 줄에 한 질문을 적는 JSONL이다(`record_schema.json`). 단계마다 필요한 부분만 채운다.

| 단계 | 채우는 부분 |
|---|---|
| 수집 | `question`: 원문, 기준일, 출처, provenance |
| 의미 검토 | `review`: 의미, 기대 동작·호출·멈춤 근거, 라벨 근거, 관련 결정 |
| 실행 | `runs`: GeoFlow CLI 실행 또는 업체 대행. 질문 원문·기준일·provider·검증 표시·호출·응답 |
| 판정 | `judgments`: 범위, 실행, 결과, 귀속 조합, 값 판정, 근거, 판정자 역할·날짜 |

`python evaluation/real_data/validate.py <파일>`이 검사하는 것:
- 검토 완료인데 의미·라벨 근거가 비어 있음.
- 미결정 D를 업체 결정(`vendor_decision`)으로 인용함.
- 판정이 검토 완료 전에 있음.
- 값까지 맞았다고 판정했는데 실제 응답 기록이 없음.
- 기대 동작·실제 결과·판정 분류가 서로 맞지 않음.
- 정확한 거부에 멈춤 근거가 없음.
- 실행의 질문 원문·기준일이 사례와 다름.
- 범위에 맞지 않는 실행: mock으로 provider·전체 판정, 업체 대행으로 end_to_end.
- 비교 조건을 훼손한 실행을 검증 조합에 귀속함.
- 테스트용 가짜 기록(`fake-`)이 실제 자료 위치(`records/`)에 있음.

**검사가 보장하지 않는 것(사람이 확인한다):**
- `source=real_user`, `provider.name=tims`, `data_source`의 진위. 값이 적혀 있다는 것만 본다.
- 실제 출처는 `question.provenance`(넘겨준 쪽, 받은 날짜, 원본 위치)와 응답의 `response_ref`·`data_source`를 원본과 대조해 사람이 확인한다.
- 라벨 의미의 타당성, 검토자의 독립성, 개인정보 제거.

**자료 분리:**
- 테스트용 가짜 기록은 `tests/test_real_data_records.py` 안에만 있다.
- 실제 기록은 `evaluation/real_data/records/`에 둔다. 이 경로는 기본으로 git 추적에서 뺐다(`.gitignore`). 개인정보 정책이 정해지면 바꾼다.

## 4. 표본 수

| 목적 | 규모 | 주의 |
|---|---|---|
| 초기 사례 점검 | 몇 개부터 시작해도 된다 | 무엇이 틀리는지·근거 체계가 작동하는지 보는 것이다. 비율을 주장하지 않는다 |
| D1–D4 결정, TIMS 계약 항목 확인 | 항목마다 대표 질문이나 대상 호출 몇 개 | 통계가 아니라 사실 확인이다 |
| 실패율 상한 | 실패 0건일 때 95% 상한이 약 3/n | 대표성 있는 표본(실제 사용 분포에서 무작위 추출)에서만 쓴다. 실패가 있으면 정확 이항 구간(Clopper–Pearson)을 쓴다 |
| 정상 비율 추정 | ±10%p(95%)면 약 100, ±5%p면 약 400 | 비율이 50% 근처일 때의 최악 경우 |

- 3/n 근사로 상한 p를 보이려면 약 3/p개가 필요하다. p=5%면 60, 2%면 150, 1%면 300이다. 어떤 p를 받아들일지는 서비스 담당자가 정한다.
- 합성 평가에서 개선 폭이 컸다는 사실은 실제 질문에서도 작은 표본이면 충분하다는 근거가 아니다. 실제 질문 분포와 실패 유형이 다를 수 있다.
- 실패할 것 같은 질문만 고르면 사례 점검에는 쓸 수 있지만 비율 추정에는 쓸 수 없다. 어떻게 뽑았는지를 기록한다.

## 5. 외부 입력 요청 묶음

각 묶음은 따로 시작할 수 있다. 모든 결정·대량 질문·연결 정보가 다 모일 때까지 기다리지 않는다.

| 묶음 | 확인할 것 | 현재 근거와 미확인 | 필요한 입력 | 들어오면 시작할 검증 | 입력이 없을 때 가능한 범위 |
|---|---|---|---|---|---|
| Q1 실제 질문 소량 | 실제 질문을 GeoFlow가 의미대로 옮기는가 | 실제 질문 없음 | 서비스 담당자: 실제 질문 원문 5–20개, 질문 시각, 개인정보 제거 여부, 뽑은 방법 | 수집 → 검토 → meaning 판정(mock 실행, `--reference-date`). 사례 점검이며 비율 주장 없음 | 없음(합성 문항으로 대신하지 않는다) |
| Q2 의미 검토 | Q1 질문의 의미·기대 동작 | – | 검토자(가능하면 두 명): `review` 항목 | meaning 판정 확정, 결정이 필요한 질문을 D1–D4에 연결 | 검토자 없이 판정하지 않는다 |
| D1–D4 결정 (항목별) | `decisions.md`의 "물을 것" | 결정표의 업체 문서·미확인 칸 | 업체 또는 서비스 담당자: 결정과 근거 문서 위치. 하나씩 따로 받아도 된다 | 결정된 항목에 기대는 질문의 라벨 확정(`상태: 결정됨`) | 그 항목에 걸린 질문은 `decision_refs`로 표시만 하고 판정을 미룬다 |
| C1 계약 항목 (항목별) | `tims_lowering_contract.md` 2절의 UNKNOWN·OBSERVED 항목, 후보 목록 응답 형식(D4) | 문장으로 정한 것이 없음 | 업체: 항목마다 답·계약 버전. 가능하면 예시 호출과 응답 | `geoflow/tims_contract.py` 상태 갱신 검토, 해당 provider_contract 판정 | 지금 상태(미확인이면 멈춤·가정 기록)를 유지한다 |
| R1 업체 대행 호출 | 정해진 호출에 TIMS가 계약대로 답하는가 | 응답 없음 | 업체: Q1 실행이 만든 호출(또는 C1 대상 호출)을 실행한 응답 원본, 실행 날짜, 계약 버전 | provider_contract 판정(`kind=vendor_relay`) | 없음 |
| T1 TIMS 직접 접속 | 전체 실행 | 연결 정보·provider 구현 없음 | 업체: 접속 주소·인증·호출 한도·시험 범위 | TIMS provider 구현(별도 작업) 뒤 response_interpretation·end_to_end 판정 | provider 구현을 시작하지 않는다 |

**요청문 초안 (보내지 않음):** 아래는 초안이다. 실제 연결 정보·응답·결정은 들어 있지 않다.

> **서비스 담당자께**
>
> GeoFlow 질문 해석을 실제 질문으로 점검하려 합니다. 다음을 부탁드립니다.
> 1. 실제 사용자 질문 원문 5–20개(개인정보 제거)와 각 질문 시각, 뽑은 방법.
> 2. 가능하면 의미 검토를 맡을 분(두 분이면 더 좋습니다).
> 3. `decisions.md`의 D1–D4 중 정하실 수 있는 항목의 결정과 근거. 한 항목씩 주셔도 됩니다.
> 4. 받아들일 수 있는 실패율 목표(예: 2%)가 있으면 알려 주세요. 이후 필요한 질문 수가 정해집니다.

> **업체 담당자께**
>
> TIMS 계약 중 문서로 확인되지 않은 항목이 있습니다(첨부: `evaluation/design/tims_lowering_contract.md` 2절, `decisions.md`). 다음을 부탁드립니다.
> 1. 항목별 답과 계약 버전. 특히 aggregation=avg의 분모, 날짜 범위 양 끝 포함, 자료 없는 날의 반환, 상대 날짜의 기준 시각, 동일 지명의 후보 목록 응답 형식, 기간 조회에서 active_taxi_count의 avg·max 의미.
> 2. 첨부한 호출 목록을 실행한 응답 원본(실행 날짜 포함). 항목별로 나눠 주셔도 됩니다.
> 3. 직접 시험 접속이 가능하다면 접속 방법·인증·호출 한도·시험 범위.

## 6. 착수 절차

- **Q1이 들어오면:**
  1. `records/`에 수집 기록을 만든다.
  2. 질문마다 `--reference-date`를 질문 기준일로 두고 CLI를 mock으로 실행한다(모델 호출이 생긴다).
  3. 저장 기록의 `geoflow_verification`·`geoflow_settings`·`execution_plan`을 `runs`에 옮긴다.
  4. 검토자(Q2)가 `review`를 채운 뒤 meaning 판정을 적는다.
  5. `validate.py`로 검사한다.
- **D 결정이 들어오면:**
  1. `decisions.md`의 `상태:`를 `결정됨(근거 위치)`로 바꾼다.
  2. 관련 질문의 `label_basis`에 `vendor_decision`을 추가한다.
  3. 합성 셋의 라벨은 바꾸지 않는다. 바꾸려면 이전 결과를 보존하고 모든 비교 대상에 같이 적용한다.
- **C1·R1이 들어오면:**
  1. 업체 대행 실행 기록(`vendor_relay`)과 provider_contract 판정을 적는다.
  2. 계약 상태 변경은 `tims_contract.py`의 근거(인용 문장)와 함께 따로 검토한다.
- **T1이 들어오면:** TIMS provider 구현을 별도 작업으로 계획한 뒤 end_to_end를 시작한다. 검증 명세의 provider 항목은 이 범위에서만 다름으로 허용된다.
