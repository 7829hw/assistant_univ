# 정답 grounding의 보정 계층 통과 (`evaluate_vendor100.py gold-audit`)

정답 grounding은 이미 맞다. 여기서 바뀌거나 멈춘 것은 모두 보정의 훼손이다. 정답 grounding을 실행기에
넣는 평가(`gold`)와 다르다. 한쪽으로 다른 쪽의 정확성을 주장하지 않는다.

| 셋 | 정답 grounding | 조건 보존만: 바뀜 / 멈춤 | 의미 재해석까지: 바뀜 / 멈춤 |
|---|---|---|---|
| `evaluation/vendor100/gold.yaml` | 100 | 0  / 0  | (이 코드에 없음) |
| `evaluation/grounding_v1/holdout_questions.yaml` | 43 | 0  / 0  | (이 코드에 없음) |
| `evaluation/grounding_v2/contrast_questions.yaml` | 30 | 0  / 0  | (이 코드에 없음) |
| `evaluation/grounding_v2/independent_questions.yaml` | 39 | 0  / 0  | (이 코드에 없음) |
| `evaluation/grounding_v2/independent_v3_questions.yaml` | 38 | 0  / 0  | (이 코드에 없음) |
| `evaluation/grounding_v3/independent_v4_questions.yaml` | 38 | 0  / 3 k01(DATE_AMBIGUOUS) k04(DATE_AMBIGUOUS) k16(DATE_AMBIGUOUS) | (이 코드에 없음) |
