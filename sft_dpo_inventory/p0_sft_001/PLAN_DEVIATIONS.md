# p0_sft_001 계획 이탈 기록

## 1. Gold-only 평가 시작 실패(도구 문제, 2026-10-13 13:35 UTC)

- 증상: `eval gold_only sel154`가 모델을 올리기 전에 `ValueError: Checkpoint production prompt drift`로 끝났다(rc=1, 3초).
  아무 문항도 생성하지 않았다. 로그는 `/data/hwkim/p0_sft_001/logs/ABORTED_eval_gold_only_sel154.log`,
  `evaluation/gold_only/ABORTED_sel154.log`.
- 원인: `training/inference.py`의 `check_checkpoint_prompt`가 adapter의 `training_provenance.json` prompt hash를 Full production
  prompt(`87048d0c`)와만 비교했다. P0 contract로 학습한 adapter(prompt hash `d7f4c12a`)를 인식하는 경로가 없었다.
- 고친 것: provenance의 `config.data.contract == "p0"`이면 학습에 쓴 P0 prompt(`data.p0_prompt`)의 hash와 비교한다(불일치면 그대로 멈춤).
  생성·채점·데이터·hyperparameter는 바뀌지 않는다. code fingerprint `ab88a19e` 그대로(training/은 범위 밖).
  `tests.test_training_trainers` 통과.
- 처리: 결과를 보고 다시 돌리는 것이 아니라 기반 장애(PLAN 8절)다. 끝난 셀(학습 2, base 4셀)은 그대로 두고, 실패한 셀부터
  같은 명세로 이어 잰다(`run_resume.sh`, run_all.sh와 같은 함수). 실행 순서(gold_only → clean_hybrid, 셋 순서)는 바꾸지 않는다.

## 2. thinking 없는 답을 평가 client가 빈 응답으로 처리(측정 오류, 2026-10-13 13:36 UTC)

- 증상: 재개 직후 `gold_only sel154` 첫 문항(old44/g02)이 `EMPTY_RESPONSE`(생성 88 token, 재질의도 같음)였다. 수동으로 멈췄다(13:36, 1문항째).
  결과 파일은 만들어지지 않았다. 로그는 `/data/hwkim/p0_sft_001/logs/ABORTED2_eval_gold_only_sel154.log`.
- 원인 확인(평가 셋이 아닌 v005 학습 문항으로 재현):
  - Gold-only 모델은 답만 있는 학습 레코드 형식대로 `<think>` 없이 JSON을 바로 낸다(done_reason stop, 92 token).
  - `hf_thinking.split_thinking`은 `</think>`가 없으면 잘린 thinking으로 보고 본문을 비운다. 그래서 정상 답이 빈 응답이 됐다.
  - 모델 실패가 아니라 측정 오류다.
- 고친 것(`eval_p0_hf.py`만):
  - `<think>`와 `</think>`가 모두 없는 응답은 thinking "" + 본문 전체로 나눈다(Ollama think 분리와 같은 취지).
  - `<think>`로 시작한 응답(잘림 포함)의 처리는 그대로다. trace 수집 코드(`hf_thinking.py`)는 고치지 않았다.
- base 영향 없음: 끝난 base 4셀 raw 487호출 중 think 태그가 없는 응답은 0이다. 따라서 base 결과는 다시 재지 않는다.
- smoke(학습 문항 2개, 분석에 쓰지 않음): gold_only 2/2 match.
- 처리: 기반 장애로 보고 gold_only sel154부터 같은 순서로 다시 잰다(`run_resume.sh`).
- 해석 영향: Gold-only는 thinking을 하지 않는 모델이 됐다(답만 있는 레코드 154개 + json_only 손실의 형식 효과). REPORT에서 thinking 길이와 함께 다룬다.
