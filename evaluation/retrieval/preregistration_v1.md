# 질문–graph 예시 검색 비교 평가 v1 — 측정 전 고정

2026-09-26 작성. 모델을 평가 셋에 한 번도 돌리지 않은 상태에서 고정한다. 이 문서, 평가 셋
(`retrieval_eval_v1.yaml`, sha256 `af5a8f49…`), 후보(아래)는 측정 후 바꾸지 않는다. 측정 뒤에
무엇이든 고치면 이 셋은 development가 되고, 개선 주장에는 새 셋이 필요하다.

## 후보(고정)

| 항목 | 값 |
|---|---|
| 코드 | `57b6514` 위에 평가 셋·이 문서만 더한 커밋 |
| 예시 저장소 | `geoflow_examples/question_graph_examples.yaml` v1, 16개, sha256 `75b83c3b…` |
| 검색 index | `geoflow_examples/index_lexical.json`, sha256 `83a79709…` |
| 검색 방식 | **문자 n-gram(2–3) TF-IDF cosine, lexical. 임베딩 아님**(이 환경에 임베딩 실행 환경이 없다) |
| 검색 설정 | top_k 3, max_chars 3000, min_score 없음, 순서 = 점수 내림차순·id 오름차순 |
| 고정 예시(비교군) | ex03, ex09, ex10(질문과 무관하게 같은 3개) |

development에서 본 것: 기능 확인 6문항(`reference_questions_v1`) 1회(run
`20260926_212959_dev_retrieval_v1`). 그 결과를 보고 저장소·prompt를 고치지 않았다.

## 조건(세 arm이 같다)

- 모델 qwen3:8b, temperature 0, 관측마다 모델 상태 초기화(cold load를 확인하지 못한 관측은 무효).
- provider reference(합성 데이터), 기준일 2026-09-25, condition_check on, 실행 프로필 기본(legacy는
  reference에 적용되지 않는다).
- grounding 계약 structured. 세 arm은 예시 절 유무와 종류만 다르다.

| arm | 예시 |
|---|---|
| A `structured+cc` | 없음(기존 prompt와 byte 단위로 같음) |
| B `structured+cc+rx` | 질문으로 검색한 top-3 |
| C `structured+cc+fx` | 고정 3개 |

## 실행 순서와 반복

- 17문항 × 3 arm × 2회 = 102 관측.
- 반복마다 문항 순서대로 돈다. 문항 i의 arm 순서는 (A, B, C)를 i만큼 회전한 것이다(runner 규칙).
- 한 arm이라도 무효인 관측은 그 문항을 세 arm 모두에서 뺀다(채점기 규칙). 무효가 생겨도 다시 돌리지
  않고 그대로 보고한다.

## 지표(condition_scoring v2.7)

주 지표
1. `correct_answer`: 결과 종류(답/확인 필요/지원 안 함), 집계 의미 계획, 조건이 모두 맞은 관측 수(34 중).
2. `silent_semantic_error`: 답은 냈지만 의미가 틀린 관측 수.

보조 지표
- `answer_correct`: reference 계산 값(과 선택 구간)이 gold와 같은 관측 수(답할 수 있는 13문항 × 2).
- 칸별 정확도: bucket, inner, outer, 결과 종류(value/group).
- `structure_wrong`(dimension·order·limit), 조건 누락·추가·변경(interpretation_status).
- `unjust_refusal`: 답할 수 있는 질문을 거부한 수.
- 모호 문항(e16, e17)과 목록 문항(e14, e15)은 family별로 따로 보인다.
- 비용: system prompt 글자 수, 입력 token(prompt_eval_count), 지연 중앙값, LLM 호출 수.
- 검색 포함률: B arm에서 붙인 예시가 문항의 retrieval_tags를 하나라도 가졌는지(검색 품질, 모델과 무관).

분리
- 같은 LLM 원문을 예시 on/off로 재생해(`example_retrieval.py replay`) 후처리 영향이 0인지 확인한다.
  0이면 arm 사이의 차이는 모두 모델 출력이 달라진 영향이다. condition_check on/off 재생으로 조건
  보정이 바꾼 관측 수도 따로 적는다.

## 판정 규칙

- B가 A보다 낫다고 적는 조건: `correct_answer`(B) − (A) ≥ 3 **이고** `silent_semantic_error`(B) ≤ (A)
  **이고** `unjust_refusal`(B) ≤ (A) + 1.
- 그중 "검색 효과"(예시를 붙인 효과가 아니라 고른 효과)라고 적는 조건: 위를 만족하고
  `correct_answer`(B) − (C) ≥ 2.
- 어느 것도 만족하지 않으면 "이 규모에서 차이를 보이지 못함"으로 적는다. B가 A보다 correct가 낮거나
  silent가 높으면 나빠진 것으로 적고 문항별 원인을 기록한다.
- 결과와 무관하게 production 기본값(검색 끔)은 바꾸지 않는다. 17문항·1모델·합성 데이터의 소규모
  비교이며 일반화하지 않는다.
