# 조건 보존 기능(condition_check) 판정 규칙

측정 전에 고정한다(2026-09-26). 결과를 본 뒤 이 파일을 고치지 않는다.

## 비교 조건

- 평가 셋: `evaluation/structured_grounding/eval_questions_conditions_v1.yaml`(32문항,
  측정 전 고정, 기존 셋·개발 질문과 문장 중복 없음. 분리하지 못한 것은 파일 머리에 적었다)
- 후보: `geoflow/conditions.py` sha256
  `e0a47e2d7b8e04d668a8215b705d360b0330d988c1e8b927b5fae823300461ea`(condition_check=True).
  개발 근거: eval_v1(30문항)·census 재생. census 재생에서 찾은 잘못된 삭제("개인용 택시")를
  고친 뒤 고정했다.
- arm 4개: `flat`, `flat+cc`, `structured`, `structured+cc`. prompt는 flat `64bbceb4`,
  structured `73979b6e`로 그대로다(condition_check는 prompt를 바꾸지 않는다).
- 모델 qwen3:8b, temperature 0, chat timeout 300초, 기준일 2026-09-25(Asia/Seoul), mock provider.
- 반복 1회. 질문 i의 arm 순서는 위 목록을 i만큼 회전한 순서다. 관측마다 모델을 내리고
  cold load(첫 호출 load_duration ≥ 500ms)를 확인한다. 무효 관측이 있는 질문은 네 arm 모두에서 뺀다.
- 원문·오류·지연·호출 수·조건 기록(condition_audit)·실행 인자 요약을 `observations.jsonl`에 남긴다.

## 지표 (`structured_grounding_eval.py score`)

전체 결과(집계 오류 포함)와 조건 결과를 따로 본다.

- 전체: correct_answer, silent_wrong, answerable_refused, clarification_ok, execution_failure,
  plan_ok, LLM·Tool 호출 수, 지연 중앙값
- 조건: conditions_ok(date·taxi_type·place·od가 모두 기대와 같음), condition_status별
  missing / added / changed 수, date_ok, od_wrong, grounding_rejected(조건 판정 불가),
  good_corrections / bad_corrections(보정이 맞았는지)

## 판정

주 비교는 production 기본 집계 계약인 **flat vs flat+cc**다. 다음을 모두 만족하면
"condition_check를 옵션 후보로 유지할 근거가 있다(Case K)", 하나라도 어기면 Case N이다.

1. conditions_ok(flat+cc) ≥ conditions_ok(flat) + 3
2. silent_wrong(flat+cc) ≤ silent_wrong(flat)
3. correct_answer(flat+cc) ≥ correct_answer(flat)
4. answerable_refused(flat+cc) ≤ answerable_refused(flat) + 1
5. bad_corrections(flat+cc) = 0
6. taxi_type·date의 added 수(flat+cc) ≤ flat, missing 수(flat+cc) ≤ flat
7. crash 0, 무효 질문 ≤ 3

structured vs structured+cc는 같은 기준으로 보조 보고하며 판정에 쓰지 않는다. 어느 Case든
이번 작업에서 기본값(condition_check 끔, flat)은 바꾸지 않는다. 표본이 32문항이므로 차이를
일반 성능으로 확대 해석하지 않는다. 측정 후 이 평가 셋은 development로 바꾼다.
