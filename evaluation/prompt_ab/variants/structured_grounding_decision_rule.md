# flat(H0) vs structured(S1) 집계 grounding 판정 규칙

측정 전에 고정한다(2026-09-26). 결과를 본 뒤 이 파일을 고치지 않는다.

## 비교 조건

- 평가 셋: `evaluation/structured_grounding/eval_questions_v1.yaml` (30문항, fresh_holdout, 측정 전 고정)
- 모델: qwen3:8b (Ollama, 로컬), temperature 0, think 미지정, chat timeout 300초
- arm: flat = production prompt sha256 `64bbceb4…`, structured = S1 prompt sha256
  `73979b6e190d3d9b4cacecbf3f90f15b08782742dc702118f0a0b1d45fb909eb`
  (dev_questions.yaml로 세 번 정비한 뒤 고정. 정비 run: `evaluation/structured_grounding/*_dev_s1_v1..v3`)
- 두 arm의 차이는 grounding 계약(prompt와 parser 설정)뿐이다. 모델·provider(mock)·옵션·
  기준일(2026-09-25)·결정적 계층·TIMS 계약(DEFAULT_CONTRACT)은 같다.
- 반복 1회. 질문 i는 짝수이면 flat 먼저, 홀수이면 structured 먼저.
- 관측마다 모델을 내리고(keep_alive 0, /api/ps 확인) 첫 호출의 load_duration ≥ 500ms로
  cold load를 확인한다. 확인하지 못했거나 timeout인 관측은 무효이며, 한 arm이라도 무효인
  질문은 두 arm에서 모두 뺀다.
- 원문·오류·지연·호출 수는 `observations.jsonl`에 남긴다.

## 지표 (`structured_grounding_eval.py score`)

관측마다 최종 grounding(재질의 뒤)의 집계 의미와 조건을 라벨과 비교한다.

- correct_answer: 답을 냈고, 라벨이 답을 기대하며, 집계 의미와 조건이 모두 맞다
- plan_ok: 집계 의미가 라벨과 같다(inner: unspecified 포함)
- silent_wrong: 답을 냈는데 correct_answer가 아니다
- answerable_refused: 라벨이 답을 기대하는데 답하지 않았다
- clarification_ok: 라벨이 확인 요청을 기대하고 확인 요청을 돌려줬다
- condition_missing: 라벨의 조건(date, taxi_type, place) 중 하나라도 grounding에 없거나 다르다
- execution_failure: outcome이 failed 또는 crash
- 호출 수(LLM, Tool)와 관측 지연 중앙값

## 판정

structured를 "production 후보로 추가 검토할 가치가 있다(Case S)"고 판정하려면 다음을 모두
만족해야 한다. 하나라도 어기면 Case F(채택 근거 없음)다.

1. silent_wrong(structured) ≤ silent_wrong(flat)
2. correct_answer(structured) ≥ correct_answer(flat) + 2
3. answerable_refused(structured) ≤ answerable_refused(flat)
4. condition_missing(structured) ≤ condition_missing(flat) + 1
5. crash 0
6. 무효 질문 ≤ 3

거부가 늘어난 것만으로 개선이라고 하지 않는다(2와 3이 그 조건이다). 어느 Case든 이번 작업에서
production 기본값(flat)은 바꾸지 않는다. 측정 후 이 평가 셋은 development로 바꾼다.
