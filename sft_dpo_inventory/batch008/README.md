# batch008 annotation 후보 — 300문항이 채우지 못하는 경계 보강(pilot_006 준비 W7b)

작성: 2026-10-15. **승인이 아니다.** 초안 gold와 검증 사슬 통과는 승인으로 다루지 않는다. 승인된 corpus에는 아무것도 넣지 않았다.
학습 trace 수집과 import는 하지 않았다(다음 세션, 사용자 승인 뒤). `SEMANTIC_CODE` 변경 없음, 지문 `791c4a68`, prompt `87048d0c`.

## 1. 파일

| 파일 | 내용 |
|---|---|
| `write_drafts.py` → `candidates_draft.yaml` | Claude 초안 38건(질문, 업체 형식 정답 호출, 근거, gap, 대조 group). 스크립트에 손으로 적었다 |
| `build_candidates.py` → `candidates_checked.json`, `excluded.json`, `inputs_first_response.jsonl` | 현재 코드 결과와 겹침 검사(W6과 같은 도구 + 300문항·pg_imports). 남은 후보 10, 뺀 후보 28 |
| `base_first_response.jsonl` | J7: 남은 10건의 base 첫 응답(vLLM BF16 greedy, GPU `a5ce83d0`, worktree `0217893`). 원문은 ignore(`training/generated/pilot_006_prep/raw/batch008_base_first_raw.jsonl`) |

## 2. 설계(계획서 v2 6.4절, xlsx `보강_필요` 시트)

| gap | 수 | 내용 |
|---|---:|---|
| g1 순위 없는 dimension_target | 8 | 실차 건수를 승차·하차 끝으로 묶되 order·limit 없음("순위 질문이면 dt" 지름길 차단) |
| g2 implicit endpoint 동사형 | 10 | "태운 곳", "내려준 곳", "내린 곳", "차에 오른 곳", "어디서 태웠는지" — 승차·하차·출발·도착이라는 말 없음 |
| g3 value 없는 place 대조 | 8(4쌍) | a = 답이 장소 이름(scope 이름 조회, value 없는 place가 측정값), b = "어디야"지만 묶음 단위 순위 1곳(장소 개념 없음) |
| g4 bucket ↔ dimension 대조 | 12(6쌍) | 같은 지표·기간에서 "주·월 단위로 집계한 뒤 다시 집계"(bucket + rollup)와 "요일·지역별"(dimension)만 다름 |

- 보호 셋, n33, 300문항 문장을 보거나 바꿔 쓰지 않고 새로 썼다. partial-grounding batch006 Gap A의 "손님을 태운 위치" 표현은 피했다.
- 장소는 mock gazetteer 이름만 썼다(대구, 부산, 서울, 인천, 중구, 동구, 수성구, 달서구, 수영구, 부산진구, 어린이대공원 scope 등). 기준일 2026-09-25.
- tool 제약: dimension은 통행량·실차 건수·billing만, bucket은 billing만 받는다. billing은 scope와 dimension을 함께 쓰지 못하므로 g4는 장소 없이 썼다.
  주변(vicinity)+dimension은 현재 코드가 거부해 쓰지 않았다.

## 3. 현재 코드 결과와 겹침 검사

빼는 기준은 batch007과 같고 결과 전에 정했다: 질문 일치, 문자 3-gram Jaccard ≥ 0.5, 같은 정답 grounding(대상 12개 셋 어디든), thor leakage 사유,
확장 template·family, 보호 셋 5개와의 template·family, 검증 사슬 실패, Full 경로가 mock에서 답하지 못함.

| 결과 | 수 | 후보 |
|---|---:|---|
| 남음 | **10** | b008-02(g1), b008-14·18(g2), b008-29·30·32·33·35·37·38(g4) |
| 강한 사유로 뺌 | 8 | b008-03(batch007 b007-24 Jaccard 0.551), b008-19(selection n40 Jaccard 0.647·같은 grounding), b008-21(aux f17 Jaccard 0.543), b008-25(selection g36 같은 grounding, aug300-381 Jaccard 0.516), b008-06·08·15(인천·서울 묶음 mock UNSUPPORTED_COMBINATION), b008-36(billing scope 없이 시군구 dimension: PARAM_VALUE_REQUIRES_INPUT) |
| **약한 겹침(template·family)만으로 뺌** | **20** | b008-01·04·05·07(g1), 09·10·11·12·13·16·17(g2), 20·22·23·24·26(g3), 27·28·31·34(g4). 보호 셋에 같은 family(측정값·od_role·묶음 구조)가 있어서다 |

- **사용자 결정이 필요하다**: 약한 겹침 20건은 문장·정답이 보호 셋과 다르고 family 키(측정값·od·묶음 종류)만 같다. 이 gap(순위 없는 dt, 동사형 endpoint 등) 자체가
  보호 셋에 같은 family로 있으므로, batch007 기준을 그대로 쓰면 대부분 빠진다. 결정 54처럼 예외로 둘지 정해야 한다. 그대로 두면 g3은 0건, g1은 1건만 남는다.
- 남은 10건: 검증 사슬 10/10, T2PC 경로 10/10 answered.

## 4. base 출력(J7, `base_first_response.jsonl`)

- 2026-10-15 22:36–22:37, GPU `a5ce83d0…`(다른 프로세스 없음), vLLM 0.30.0 BF16 flashinfer, base Qwen3-8B@b968826d, thinking 켬, greedy, max_tokens 8192, 동시 요청 8.
- 10건 중 초안과 같음 5(b008-02·30·32·33·35), 다름 5: 장소 od_role(places) 2(b008-14·18, g2 동사형), taxi_type 3(b008-29·37·38, g4).
- 검토 시트는 다음 세션에 batch007 형식으로 만든다(약한 겹침 20건의 처리가 정해진 뒤).

## 5. 결정 120(E5) 재분류(2026-10-15, 세션 1b, `apply_e5.py` → `e5_reclassification.json`)

약한 겹침(template·family)만으로 뺀 20건. 계속 뺌 = selection_v2·augmentation_holdout_v1·valid98·aux_test_v1 중 하나와 family 겹침. 되살림 = 업체 100만 또는 template 수준만 겹침.

| id | gap | 결과 | 근거 |
|---|---|---|---|
| b008-01 | g1_dt_no_rank | 계속 뺌 | family 겹침: valid98 |
| b008-04 | g1_dt_no_rank | 계속 뺌 | family 겹침: valid98 |
| b008-05 | g1_dt_no_rank | 계속 뺌 | family 겹침: valid98 |
| b008-07 | g1_dt_no_rank | 계속 뺌 | family 겹침: valid98 |
| b008-09 | g2_implicit_endpoint | 계속 뺌 | family 겹침: valid98 |
| b008-10 | g2_implicit_endpoint | 계속 뺌 | family 겹침: valid98 |
| b008-11 | g2_implicit_endpoint | 계속 뺌 | family 겹침: valid98 |
| b008-12 | g2_implicit_endpoint | 분류 밖(빼 둔 채 보고) | 넷 밖의 family 겹침만: extended_family |
| b008-13 | g2_implicit_endpoint | 계속 뺌 | family 겹침: valid98 |
| b008-16 | g2_implicit_endpoint | 계속 뺌 | family 겹침: valid98 |
| b008-17 | g2_implicit_endpoint | 계속 뺌 | family 겹침: aux_test_v1, holdout, selection_v2 |
| b008-20 | g3_valueless_place | 계속 뺌 | family 겹침: holdout, valid98 |
| b008-22 | g3_valueless_place | 계속 뺌 | family 겹침: selection_v2 |
| b008-23 | g3_valueless_place | 계속 뺌 | family 겹침: aux_test_v1, holdout, selection_v2, valid98 |
| b008-24 | g3_valueless_place | 계속 뺌 | family 겹침: aux_test_v1, holdout |
| b008-26 | g3_valueless_place | 계속 뺌 | family 겹침: aux_test_v1, selection_v2, valid98 |
| b008-27 | g4_bucket_dimension | 계속 뺌 | family 겹침: aux_test_v1 |
| b008-28 | g4_bucket_dimension | 계속 뺌 | family 겹침: selection_v2 |
| b008-31 | g4_bucket_dimension | 계속 뺌 | family 겹침: holdout, selection_v2, valid98 |
| b008-34 | g4_bucket_dimension | 분류 밖(빼 둔 채 보고) | 넷 밖의 family 겹침만: extended_family |

- **되살린 문항 0건**(계속 뺌 18, 분류 밖 2). 그래서 J7b(되살린 문항의 base 첫 응답)는 대상이 없어 돌리지 않았다(`inputs_first_response_revived.jsonl` 빈 파일).
- 분류 밖 2건(b008-12, b008-34)은 보호 원본 `evaluation/grounding_v10/heldout_questions.yaml`과의 확장 family 겹침만 남는다. 결정 120의 두 경우(업체 100만, template 수준만) 어디에도 들지 않아 빼 둔 채 보고한다(사용자 확인).
- 남은 후보는 그대로 10건이다.
