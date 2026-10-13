# Clean-Hybrid용 trace 검토

2026-10-13. 결정 68. 모델 호출 없음.

## 1. 선택(사람 검토 전, 코드로 고정)

`select_traces.py`는 문항마다 trace를 하나만 고른다.

- **후보:** `trace_quality.json`의 필터 통과 307개. 조건은 다음과 같다.
  - EXACT_OR_SEMANTIC_MATCH
  - thinking 원문 있음
  - tokenize 왕복 통과(잘림 없음)
  - 루프 아님
  - 길이 이내
- **우선순위:** greedy가 후보면 greedy, 아니면 sample_index가 가장 작은 표본.
- trace 내용은 보지 않고 골랐다.

| | 수 |
|---|---:|
| 선택 trace(= 정답 trace가 있는 문항) | 91 (greedy 33, sample 58) |
| 정답 trace가 없는 문항 | 63 |

## 2. 검토 기준

선택된 91개를 모두 읽었다. 최종 JSON이 맞았다는 것만으로 승인하지 않았다.

1. 추론의 최종 판단이 gold와 같은가. 볼 항목은 measure, 장소 값, od_role, dimension, dimension_target, bucket, aggregation, rollup이다.
2. 우연히 정답이 아닌가. 추론의 결론과 최종 답이 충돌하거나, 추론이 unsupported로 끝났는데 답은 정답인 경우다.
3. Full contract 잔재(role·source·implicit EVENT bookkeeping)가 P0 추론을 가리는 수준인가. 단어가 나온 것만으로는 거부하지 않았다.
4. prompt·ontology에 없는 규칙을 근거로 결론을 냈는가. 중간에 잘못 말했다가 스스로 바로잡은 것은 승인했다.

운영 규칙:

- 추론에서 값을 정해 놓고 철회 없이 최종 답에서 빠진 경우는 충돌로 본다(예: "aggregation is sum"이라고 정한 뒤 답에는 없음).
- 답에 gold에 없는 `answer: value`가 들어간 것은 기본값과 같아 충돌로 보지 않았다. `answer: bucket`은 의미가 달라 충돌로 봤다.
- 거부된 문항은 다른 표본으로 바꾸지 않고 gold-only로 둔다.

## 3. 결과

| | 수 |
|---|---:|
| 선택 trace | 91 |
| APPROVE_TRACE | **70** |
| REJECT_TRACE | **21** |
| 최종 reasoning example | 70 |
| gold-only fallback | 84 (거부 21 + 정답 trace 없음 63) |

거부 이유(`trace_review.json`):

| 이유 | 수 | 내용 |
|---|---:|---|
| INVALID_STRUCTURE_PLAN | 7 | 묶음 단위어("시도", "승차 읍면동", "H3 셀", 하차 위치)를 concept나 장소로 넣기로 결론 냄 |
| REASONING_ANSWER_CONFLICT | 7 | 추론에서 정한 값(aggregation sum·count, 장소 값)이 철회 없이 답과 다름 |
| HALLUCINATED_RULE | 3 | "순위 질문엔 answer bucket", "answer가 bucket이면 order·limit 불필요" 같은 없는 규칙으로 결론 |
| CONCLUDED_UNSUPPORTED | 2 | 추론은 unsupported로 끝났는데 답은 정답(우연히 정답) |
| FULL_CONTRACT_RESIDUE | 1 | MEASURE·COND 역할 분류가 추론을 지배 |
| DEGENERATE_REPETITION | 1 | 같은 문장 반복(루프 필터 기준 밑) |

출처별:

| 출처 | 선택 | 승인 | 거부 |
|---|---:|---:|---:|
| v005 | 66 | 54 | 12 |
| Gap A(augment_dt_event) | 12 | 5 | 7 |
| Gap B(augment_od_vs_dt) | 13 | 11 | 2 |

- Gap A의 거부율이 높다. HF base가 사건 표현 문항에서 정답 JSON을 내더라도, 추론에서는 H3 셀이나 하차 위치를 장소로 만들거나 unsupported로 결론 낸 경우가 많았다.
- 그래서 Clean-Hybrid의 Gap A reasoning example은 26문항 중 5개뿐이다.

## 4. 한계

- 검토자는 Claude다(사용자 지시 7절). 사람 재검토는 하지 않았다.
- 경계 판정이 있다. 철회가 분명하지 않은 aggregation 언급(#27·31·40·73·83)을 충돌로 본 것은 보수적인 선택이다.
- 승인 trace 중에도 장황한 망설임이 많다(예: #9·26·55·63·77 계열). 기준 4번에 따라 결론이 맞으면 승인했다.
