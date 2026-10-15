# T0 — teacher 표현 중립 지시 smoke(세션 2)

2026-10-16 01:47–02:18, Ollama 0.40.3 `qwen3.8:27b`(digest `aaee06c39dcf`), GPU `48f798cc…`(100% GPU), 연속 방식, 결정 55 guard 통과(최저 78.8 tok/s ≥ 기준 33.55).
대상 20질문(`t0_targets.json`, 실행 전 커밋, trunk v006_t2pc 승인 질문) × 표본 8 = 160 trace. 원문은 ignore(`training/generated/pilot_006/teacher_t0/`). **지시 초안 평가 전용, 학습 데이터 아님.**
분석: `analyze_t0.py` → `t0_analysis.json`.

## 결과(실행 전에 정한 검사)

| 검사 | 통과 |
|---|---:|
| (a) trace에 arm 전용 필드 이름 없음(`teacher6.FIELD_WORDS`) | **0 / 160** |
| (b) 결론이 canonical과 같음(최종 JSON 일치 + 판단 근거 단서) | 121 / 160 |
| 둘 다 | **0 / 160** |

- (a) 실패: 160개 모두 thinking에 EVENT·MEASURE·implicit을 쓰고, 대부분 AMOUNT·LOCATION·SUBCOND·SUPPORT도 쓴다. 지시한 다섯 단계 구조("1. 무엇을 세거나 재는가 …")는 따르지만
  단계마다 "→ AMOUNT/trip_count, EVENT/trip"처럼 출력 필드로 옮겨 적는다. thinking은 160개 모두 한국어가 섞였지만 상당수가 "Let me analyze…"로 영어로 시작한다.
- 참고(판정 아님, 결과를 본 뒤 낸 좁은 기준): 두 arm JSON에 모두 나오는 이름(vicinity, dimension_target, taxi_status, factors 등)을 빼고 Partial에 없는 이름만 세도 0/160.
- (b) 실패 39: 최종 JSON 차이 27(모두 집계 표기 `aggregation_spec`, OD·bucket 질문), 최종은 맞지만 단서 부족 12(묶음 단서 2, 집계어 5, bucket 단서 5).

대표 예(각 3개, 원문 일부): `t0_analysis.json`의 `examples`.
- (a) "SUPPORT (implicit) - 실차 구간이 측정 대상 사건 2. AMOUNT/trip_count - MEASURE (implicit) …", "→ trip_count (AMOUNT/trip_count, EVENT/trip)", "→ AMOUNT/speed, EVENT/passage".
- 최종 JSON 차이: OD 질문(해온시 → 솔빛시)의 집계 구조가 canonical과 다름(3개 모두 같은 질문 묶음).
- 단서 부족: "승차지와 하차지 조합별 = grouping by …"처럼 영어로 쓴 묶음 표현(한국어 단서 목록에 없음), 집계어를 "최솟값"이 아니라 rollup 이름으로만 씀.

## 지시 초안 수정 제안(지시 파일은 고치지 않았다)

1. **teacher 입력에서 출력 형식 어휘를 빼는 것이 핵심이다.** 지금은 Full planner system prompt(개념·subtype·role·factor 어휘와 JSON 형식 전체) 뒤에 중립 지시를 붙였다.
   모델이 그 어휘로 계획을 세우므로 덧붙인 지시로는 막히지 않는다(0/160). 제안: teacher 전용 system prompt를 따로 만든다 — 업무 설명과 의미 정의(통행 대 실차, 승차·하차,
   묶음 대 기간 구간, 집계어, 주변)만 우리말로 두고, **최종 JSON을 쓰게 하지 않는다**(두 arm의 답은 어차피 canonical 렌더로 붙인다). 출력은 "생각 + 우리말 결론 다섯 줄"로 한다.
2. (b)는 teacher의 최종 JSON 대신 **우리말 결론 다섯 줄을 canonical과 맞춰** 본다(측정 종류, 끝, 묶음, 집계어, 주변). 결론 줄이 정해진 형식이면 단서 휴리스틱보다 정확하다.
3. 사고 언어: "생각은 한국어로" 한 줄을 넣는다(영어로 시작하면 field 이름이 섞이기 쉽다).
4. (a) 검사 목록은 계획서 표현("arm 전용")에 맞춰 Partial에 없는 이름만으로 좁히는 안을 세션 3 사전 등록 때 정한다(지금은 바꾸지 않음).
5. 수정 지시로 T0을 한 번 더(같은 20질문) 재어 (a)(b) 통과율을 본 뒤 본 수집(N1)에 쓰는 것을 권한다(약 30분, Ollama GPU).
6. 집계 차이 27건(OD·bucket)은 teacher의 판단 차이인지 canonical 표기 문제인지 사람이 한 번 본다(같은 질문 묶음에 몰려 있다).
