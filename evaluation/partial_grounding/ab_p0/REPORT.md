# Full vs Partial-P0 paired A/B 결과 (ab_p0, Ollama qwen3:8b, 2026-10-09)

계획: `PLAN.md`(결정 57). 셀 13개(smoke 1 + greedy 2 + sampling 10) 모두 guard 중단 없이 끝났다(`runs.log`).
분석: `analyze.py` → `analysis.json`. 업체 100은 진단용이다(결정 57).

## 1. 판정(sampling 5회 평균, 같은 seed끼리 짝)

| Gate | Full | P0 | 차이 | 기준 | 결과 |
|---|---|---|---|---|---|
| semantic correctness | 81.0% | 83.4% | +2.4%p, 문항 paired CI [−1.6, +6.6], p=0.30 | ≥ −1%p | 통과(점 추정). CI 하한은 −1%p 아래 |
| answerable semantic correctness | 81.0% | 83.4% | +2.4%p(위와 같음, 모든 문항이 답해야 할 문항) | ≥ −1%p | 통과(점 추정) |
| refusal correctness | — | — | — | 악화 없음 | 판정 불가: 업체 100에는 거부해야 할 문항이 없다 |
| grounding failure(최종) | 4.8 | 6.8 | +2.0문항 | 증가 없음 | **불통과** |
| grounding_ok(참고) | 78.2 | 81.2 | +3.0 | — | — |
| execution completion | 88.0% | 88.8% | +0.8%p | ≥ −1%p | 통과 |
| structural errors(첫 응답) | 4.2 | 6.4 | +2.2문항 | P0 < Full | **불통과** |
| final JSON tokens | 126.3 | 69.2 | −45.2% | replay 감소(−46%) 유지 | 통과 |

회차별 semantic correctness: Full 83/79/80/82/81, P0 78/80/88/86/85. structural: Full 3/5/5/4/4, P0 6/11/3/5/7.
greedy(판정에 쓰지 않음): Full 87 / P0 84. Full 정답·P0 오답 11, Full 오답·P0 정답 8.
P0 greedy 002의 첫 호출은 300초 ReadTimeout이었다(재호출로 match). 계약 오류가 아니라 호출 실패다.

참고: thinking 중앙값 2216 → 2099자, eval_count 중앙값 749 → 638, 문항 지연 중앙값 약 7.6초 → 6.8초.

## 2. 문항별 비교

- 체계적 차이(|k_Full − k_P0| ≥ 4): 084(1→5), 095(0→5). 둘 다 P0 쪽이 낫다. P0가 체계적으로 나쁜 문항은 없다
  (가장 큰 P0 악화는 030 2→0, 041 4→2, 058 5→3).
- 회차별 (Full 정답·P0 오답, Full 오답·P0 정답): r1 (10, 5), r2 (10, 11), r3 (2, 10), r4 (9, 13), r5 (9, 13).
- regression set(업체 100 문항): 061 5/5 → 5/5, 080 5/5 → 5/5(greedy P0는 refused_unsupported), 090 4/5 → 5/5,
  099 5/5 → 5/5.

## 3. P0에서 늘어난 structural error의 원인

Full이 내던 role/source/EVENT 오류(event_mismatch, role_or_source)는 P0에서 0이 됐다. 대신 다음 세 종류가 새로 생겼다.
모두 "무엇을 concept로 쓰고 무엇을 factor/attribute로 쓰는가"의 경계 문제다.

1. **subtype이 아닌 값을 subtype으로 적음 → `INVALID_CONCEPT`(concept 비어 있음)**, 11건: `pickup`(007, 073), `emd`(040, 093),
   `sido`(076), `dayofweek`(015), `taxi_status`(088). Full에서는 이런 값이 factors(dimension, od_role)로 갔다.
2. **집계 차원을 place 속성으로 적음 → `UNKNOWN_ATTRIBUTE`**, 8건: `attributes.dimension`(005, 037, 046, 070),
   `taxi_status`, `role`. "읍면동별/시군구별" 질문에서 "읍면동"을 place concept로 만들고 차원을 거기 붙인다.
3. **MEASURE 누락 → `NO_MEASURE`**, 7건: 답이 장소인 질문에서 값 없는 place를 빼먹거나(040, 012, 082),
   통행량 concept 자체를 빼먹음(064, 074: place 하나만 출력).

Full의 role 필드가 "이것은 조건/측정 대상이다"를 모델이 직접 분류하게 만들어 위 경계를 지켜 주던 것으로 보인다. P0 prompt의
output_format은 이 분류를 출력에서 없앴지만, 그 대신 "concept는 아래 subtype만, 차원·OD 역할·택시 구분은 factors"라는 규칙을
명시하지 않았다.

## 4. 결론

- 정답률·실행 완료율·JSON 토큰은 기준을 통과했다. 문항별로도 P0가 체계적으로 나쁜 문항은 없다.
- grounding failure와 structural error 두 gate는 불통과다. 원인은 위 세 종류의 concept/factor 경계 오류이고, parser가 아니라
  P0 prompt의 output_format에서 생긴 문제다.
- 사용자 기준대로라면 지금 P1로 넘어가지 않는다. 다음 행동(P0 prompt 보완 후 재측정 여부)은 사용자가 정한다.
