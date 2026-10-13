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
