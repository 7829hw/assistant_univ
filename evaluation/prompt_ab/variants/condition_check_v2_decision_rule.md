# condition_check 확인 평가(v2) 판정 규칙

모델 실행 전에 고정한다(2026-09-26). 결과를 본 뒤 이 파일, 평가 셋, 채점기, 후보 코드를 고치지 않는다.
이전 규칙(`condition_check_decision_rule.md`, Case N)은 그대로 둔다.

## 이번 평가가 재는 것

이번 작업은 **검증 범위를 정비하는 작업**이다. condition_check 경로는 이제 기간 인자의 provider 의미가
TIMS 계약으로 확인될 때만 실행한다(`DATE_EXECUTION_UNVERIFIED`). 확인된 계약은 단일 날짜뿐이다.
그래서 상대 기간과 범위 질문은 의미를 맞게 해석해도 멈춘다. 이 평가는 다음을 본다.

1. 계약 안에서 condition_check가 조건을 더 정확히 해석하고 보존하는가
2. 잘못된 보정·검증 오판·조용한 오류를 만들지 않는가
3. 계약 한계 때문에 얼마나 멈추는가(비용으로 따로 보고)

mock 수치는 실제 TIMS 정답률이 아니다. mock은 인자를 해석하지 않으므로(인자 hash) mock 정답은
"gold 요청 인자와 같은 인자로 호출함"을 뜻한다. 실제 데이터 기준 정답은 측정하지 않는다.

## 고정한 조건

- 평가 셋: `evaluation/structured_grounding/eval_questions_conditions_v2.yaml`
  (36문항: 답할 수 있음 28 = 계약상 실행 가능 22 + 불가 6, 미지원 6, 확인 필요 2)
  sha256 `0614a5ec81709fa0…`. 분리하지 못한 것은 파일 머리에 적었다.
- 후보 코드 sha256(앞 16자리):
  - `geoflow/conditions.py` 64a95861b5cd97be
  - `geoflow/compiler.py` 4263165bcfb5070c
  - `geoflow/tims_contract.py` 8def779c7d004d48
  - `geoflow/pipeline.py` 80b9cb3e49979b04
- 채점기: `condition_scoring.py` v2.3, sha256 619f46f3ac07b24d
- 실행기: `structured_grounding_eval.py` sha256 14bf03ca13f5ca69
- arm 2개: `flat`, `flat+cc`. 주 비교는 기본 production 경로 flat 대 flat+cc다. 구조화 경로는 재생으로만
  회귀를 확인하고 LLM으로 다시 재지 않는다.
- 모델 qwen3:8b, temperature 0, flat prompt `64bbceb4`(condition_check는 prompt를 바꾸지 않는다),
  chat timeout 300초, 기준일 2026-09-25(Asia/Seoul), provider mock, TIMS 계약 `DEFAULT_CONTRACT`.
- 반복 1회. 질문 i에서 arm 순서를 i만큼 회전한다(짝수 번째 질문은 flat 먼저). 관측마다 모델을
  내리고 cold load(첫 호출 load_duration ≥ 500ms)를 확인한다. 무효 관측이 있는 질문은 두 arm 모두에서 뺀다.

## 판정 (채점기 v2.3 요약 필드)

아래를 모두 만족하면 **Case K**다. condition_check를 선택 기능 후보로 유지할 근거가 있다는 뜻이다.
하나라도 어기면 **Case N**이다.

| # | 기준 | 필드 |
|---|---|---|
| K1 | 조용한 의미 오류가 늘지 않고, 1건 이하 | `silent_semantic_error`(cc) ≤ flat, 그리고 ≤ 1 |
| K2 | 잘못된 보정 0 | `corrections.bad`(cc) = 0 |
| K3 | 검증했다고 적은 조건이 틀린 경우 0 | `verified_wrong`(cc) = 0 |
| K4 | provider 의미가 확인되지 않은 답을 내지 않음 | `answered_provider_unverified`(cc) = 0 |
| K5 | 계약상 실행 가능한 질문의 부당한 거부가 늘지 않음(허용 +1) | `unjust_refusal_contract_executable`(cc) ≤ flat + 1 |
| K6 | 계약상 실행 가능한 질문의 정답이 줄지 않음 | `correct_contract_executable`(cc) ≥ flat |
| K7 | 조건 해석이 2건 이상 좋아짐 | `interpretation_ok`(cc) ≥ flat + 2 |
| K8 | 호출 비용 | `llm_calls_total`(cc) ≤ 1.1 × flat, `tool_calls_total`(cc) ≤ 1.5 × flat |
| K9 | crash 0, 무효 질문 ≤ 3 | |

판정에 쓰지 않고 따로 보고하는 것:
- `contract_refusal`: 계약 한계로 멈춘 답할 수 있는 질문 수. flat이 계약 보장 없이 답하던 질문이다.
- `answered_provider_unverified`(flat)
- mock 정답, 요청 인자 보존, 판정 불가 수, 보류(unverifiable) 수
- 전이(flat → flat+cc)

기본 설정은 어느 Case든 바꾸지 않는다(condition_check 끔, flat). Case K여도 production 기본값으로 바꿀
근거는 아니다. 상대 기간·범위 질문은 vendor 계약(`range_inclusive`, `relative_date_reference`,
`day_records:*`)이 확인되어야 계약 한계 거부가 사라진다. 표본이 36문항 1회이므로 차이를 일반 성능으로
확대 해석하지 않는다. 측정이 끝나면 이 셋은 development로 바꾼다.
