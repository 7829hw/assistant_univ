# 기록만 쓰는 원인 분석 — HF와 Ollama 학습 모델의 차이(결정 77)

작성: 2026-10-12. 모델 호출 없음. 학습·prompt·`SEMANTIC_CODE` 변경 없음, 지문 `791c4a68…`. 업체 100·aux_test_v1 미사용.
스크립트 `analyze_gap.py`, 결과 `analysis.json`(문항 id·오류 코드·개수만, 응답 원문과 질문 문장 없음).

## 1. 대상과 방법

- 기록: selection_v1(100문항), sampling k=4, 셀마다 400 문항·표본. 모든 셀이 같은 설정이고, Ollama 셀은 모두 문항마다 모델을 내린 격리 방식(결정 79 전)이다.
  - HF: HF-base, HF-final(pilot_002 DPO step 144 adapter). `calibration_001/runs`.
  - Ollama base: E(공식 qwen3:8b), (c)(공식 blob + HF TEMPLATE), (d)(Q8_0), B-conv(자체 Q4), B-off(공식 방식 Q4).
  - Ollama 최종: (e)(Q8_0), Ollama-final(자체 Q4), F-off(공식 방식 Q4). B-off·F-off는 `quant_recipe/runs`.
- 응답 원문(ignore 경로 `training/generated/{calibration_001,quant_recipe}/raw/`)과 기록의 호출별 본문(`llm_calls[].content`)을 함께 본다.
  - HF는 평가 스크립트(`hf_thinking.split_thinking`)가 `</think>`로 thinking과 본문을 나눈다. Ollama는 서버가 나눈다. 그 뒤 처리(`parse_planner_json`, 계약 검사, 조건 계층, compose)는 같은 코드다.
- "오류 유형 분류에 걸리지 않는 오답" = grounding_ok가 X이고 analyze_cal의 다섯 유형(aggregation_added, dt_missing, role_error, role_notation, occupied_misread)이 하나도 아닌 문항·표본.
- 갈래(앞 갈래 우선, 문항·표본의 호출 중 하나라도 해당하면):
  1. **분리 문제**: 본문이 비었거나 `<think>` 표시가 본문에 남았거나, HF에서 `</think>`가 닫히지 않음.
  2. **잘림**: done_reason이 stop이 아니거나 HF 생성 token이 8192에 닿음.
  3. **JSON 형식 오류**: 파이프라인과 같은 `parse_planner_json`이 JSON 객체를 읽지 못함.
  4. **계약 밖 필드**: plan JSON에 계약 밖 key(최상위, factor, attributes)가 있거나 오류 코드가 UNKNOWN_KEY·UNKNOWN_FACTOR·UNKNOWN_ATTRIBUTE.
  5. **그 밖**: 형식은 맞고 계약 안의 값으로 뜻이 틀림. 결과와 오류 코드로 더 나눈다.

## 2. 오류 유형 분류에 걸리지 않는 오답의 갈래(400 문항·표본 중 개수)

| 셀 | 경로 | 오답 | 분류 밖 오답 | 분리 | 잘림 | JSON | 계약 밖 | 그 밖 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| HF-base | HF BF16 | 104 | 30 | 0 | 0 | 0 | 2 | 28 |
| (d) | Ollama base Q8_0 | 98 | 32 | 0 | 0 | 0 | 4 | 28 |
| (c) | Ollama 공식 blob + HF TEMPLATE | 101 | 48 | 0 | 0 | 0 | 3 | 45 |
| E | Ollama 공식 qwen3:8b | 105 | 52 | 0 | 0 | 1 | 2 | 49 |
| B-off | Ollama base 공식 방식 Q4 | 111 | 55 | 0 | 0 | 0 | 4 | 51 |
| B-conv | Ollama base 자체 Q4 | 128 | 67 | 0 | 0 | 0 | 4 | 63 |
| **HF-final** | HF BF16 + adapter | 86 | **29** | 0 | 0 | 0 | 2 | 27 |
| **(e)** | Ollama 최종 Q8_0 | 108 | **52** | 0 | 0 | 0 | 3 | 49 |
| **F-off** | Ollama 최종 공식 방식 Q4 | 108 | **49** | 0 | 0 | 0 | 3 | 46 |
| Ollama-final | Ollama 최종 자체 Q4 | 120 | 51 | 1 | 0 | 1 | 1 | 48 |

- 맞은 문항까지 모든 호출을 봐도 분리 문제는 Ollama-final 1, F-off 1(본문이 빈 repair 호출), JSON 형식 오류는 E 1, Ollama-final 1(repair 호출에서 JSON 없음)뿐이다. 잘림은 0이다.
- 계약 밖 필드는 셀마다 1–4건이고 경로와 관계없이 비슷하다(attributes의 dimension·vicinity, factor의 dayofweek 등).
- plan 호출의 생성 token 중앙값(HF-final 806, (e) 792, F-off 788)과 repair 호출이 있는 비율(HF-final 20.8%, (e) 20.5%, F-off 18.0%)도 비슷하다.
- HF-final과 (e)의 오답 차이(+22)는 분류 밖 오답 차이(+23)와 같다. 다섯 유형의 합은 두 셀이 비슷하다.

"그 밖"의 결과별 개수:

| 셀 | failed(파이프라인 검증 실패) | answered(오답) | needs_clarification | unsupported |
|---|---:|---:|---:|---:|
| HF-base | 14 | 7 | 6 | 1 |
| (d) | 13 | 10 | 4 | 1 |
| HF-final | 13 | 11 | 2 | 1 |
| (e) | 26 | 16 | 5 | 2 |
| F-off | 21 | 17 | 7 | 1 |

- (e)의 failed 26은 오류 코드 11가지에 퍼져 있다(NOT_FOUND 5, INVALID_FACTOR_COMBINATION 4, VALUELESS_CONCEPT 4, INVALID_FACTOR 3, INVALID_OD_ROLE 2, MISSING_CONCEPT_VALUE 2, UNGROUNDED_SCOPE 2, 그 밖 4가지 1씩). 한 코드에 몰리지 않는다.
- 문항 단위: HF-final 정답 비율이 Ollama 학습 모델보다 0.5 이상 높은 문항은 (e) 10개, F-off 8개다. 반대 방향은 (e) 5개, F-off 3개다.
  (e) 쪽 10문항의 오답은 aggregation_added, dt_missing, role_error, 검증 실패, 답변 오답이 섞여 있다(`analysis.json` `items_gap`).

## 3. 같은 경로의 base 셀과 비교

- **Q8_0 경로**: base는 HF와 같다(HF-base 30 대 (d) 32). 최종만 늘어난다(HF-final 29 대 (e) 52).
- **Q4 경로**: base부터 늘어난다(HF-base 30 대 (c) 48, B-off 55, B-conv 67). 최종도 비슷한 수준이다(F-off 49, Ollama-final 51).
- 즉 HF에서 base → 최종으로 오답이 줄어드는 몫(104 → 86)이 Ollama Q8에서는 사라지고(98 → 108), 늘어난 것은 형식이 맞는 계약 안의 다른 출력이다.

## 4. 조용한 오답

셀별(문항·표본 개수, 문항 수, grounding 차이 항목):

| 셀 | 문항·표본 | 문항 | 유형 |
|---|---:|---:|---|
| HF-base | 6 | 5 | aggregation_spec 5, dimension 1 |
| HF-final | 8 | 7 | aggregation_spec 6, aggregation_spec+order 1, limit+order 1 |
| E | 6 | 4 | aggregation_spec 6 |
| (e) | 13 | 8 | aggregation_spec 13 |
| F-off | 16 | 12 | aggregation_spec 11, dimension 3, order 2 |

문항 목록은 `analysis.json`의 `silent.<셀>.list`.

**HF-base → HF-최종 조용한 오답 비율 차이**(문항 단위 쌍 bootstrap 10,000회, seed 20261109):

| 셋 | HF-base | HF-final | 차이 | 95% CI |
|---|---|---|---|---|
| selection_v1 | 1.50% | 2.00% | +0.50 | [−0.75, 2.00] |
| selection_v2 | 1.53% | 2.04% | +0.51 | [−0.77, 2.04] |

- 새로 생긴 문항: indepv3/m03, indepv3/m24, indepv4/k35, indepv4/k37, old44/g23. 사라진 문항: contrast/c07a, indepv2/n08, indepv2/n20.
- 참고: HF-base → E +0.00 [−1.50, 1.50], HF-final → E −0.50 [−1.75, 0.75].

## 5. 결론

- **HF와 Ollama 학습 모델의 차이는 응답 처리 단계(분리·파싱)가 아니라 모델 출력의 차이다 — 확인됨.**
  분류 밖 오답 증가(+23)에서 분리·잘림·JSON 형식 문제는 0건이다. 계약 밖 필드는 셀마다 1–4건으로 경로와 관계없다. 늘어난 몫은 모두 형식이 맞고 계약 안의 값으로 뜻이 다른 출력이다.
  처리 코드는 같고, thinking 분리만 HF 스크립트와 Ollama 서버가 따로 한다. 그 분리에서 생긴 문제는 맞은 문항까지 합쳐도 (e) 0건, F-off·Ollama-final 각 1건이다.
- **늘어난 출력 오류는 한 원인에 몰리지 않고 여러 오류 코드와 문항에 퍼져 있다 — 확인됨.** 문항 단위 차이는 k=4 잡음과 겹친다(반대 방향 문항도 3–5개).
- **Q8_0 base는 HF base와 같은 수준이고 최종만 떨어진다 — 확인됨(이 기록에서).** 왜 학습 모델만 Ollama 경로에서 출력이 달라지는지는 **미확인**이다.
  token 확률(teacher forcing, llama.cpp b11434)에서는 Q8_0이 학습 신호를 남겼다(`../logprob_diag/REPORT.md`). 후보는 Ollama 실행 경로, sampler 적용 순서, 생성 중 쌓이는 차이다. 이번 분석으로 가릴 수 없다.
- **HF 경로에서 조용한 오답 증가는 확인되지 않는다 — 확인됨(CI가 0 포함).** HF 경로의 조용한 오답은 대부분 aggregation_spec(결정 65의 질문에 없는 집계 추가)이다.

## 6. PROTOCOL_v3 판정 규칙이 미리 알아야 할 사실(확정 시 참고)

- HF 경로의 조용한 오답 비율은 낮다(selection_v1 1.5–2.0%, 문항 5–7개). k=4·100문항에서 조용한 오답 차이 CI의 폭은 약 ±1.4%p다. 문항 몇 개의 변화로 CI 하한이 0을 넘을 수 있다.
- HF 경로의 조용한 오답 대부분은 aggregation_spec 차이다. 이것은 오류 유형 aggregation_added(결정 65)와 겹친다. 조용한 오답 악화 판정은 주로 이 유형의 증감을 본다.
- Ollama 셀(E)의 기록은 모두 격리 방식이다. 결정 79 뒤 E를 연속 방식으로 재면 이 기록과 직접 비교하지 않는다.

## 7. 한계

- 다섯 유형 분류(analyze_cal)는 앞선 진단에서 만든 것이다. "분류 밖"은 그 다섯에 들지 않는다는 뜻이지 새 원인 범주가 아니다.
- 계약 밖 필드는 plan 호출만 봤다(repair 호출 형식은 따로다).
- 원인이 "모델 출력"이라는 것은 처리 단계를 배제한 결과다. 출력이 왜 다른지는 이 기록으로 알 수 없다.
