# pilot_009 준비 — 계획과 다르게 한 것

## 1. T-R 시도 1 guard 멈춤 → warm-up 뒤 처음부터 다시(결정 55, 2026-10-26)

- 시도 1(scheduler11 1판 작업 `T-R`, 커밋 `108f3c4`, 16:22:57 시작): precheck 통과(컨테이너 GPU 48f798cc, 0.40.6, `/api/ps` 빔, host GPU에 다른 프로세스 없음).
  첫 호출(`b011-005` 표본 1) 동안 `/api/ps` size_vram == size(100% GPU) 확인. 그 호출의 생성 속도 **28.8 tok/s < 33.71**(결정 163 O1 기준)이라 guard가 수집을 즉시 멈춤(16:24:05).
  기록: 원문 `training/generated/pilot_009/ABORTED_teacher_tr/`(1행), `teacher/ABORTED1_tr_{gpu_precheck,gpu_guard,collect}.*`, `gpu/T-R.log`. 판정에 쓰지 않는다.
- 원인(판단): **냉시작**. 그 호출은 모델을 처음 올린 호출로 load 34.1 s, prompt 934 token 처리 23.0 s, 생성 239 token 8.3 s였다.
  같은 버전·같은 GPU의 T-v3d(2026-10-18) 첫 호출은 load 6.0 s·91 tok/s(160 호출 최저 72.2), O1 속도 측정(결정 163)도 첫 짧은 생성만 14.61 tok/s이고 나머지 67–68 tok/s였다.
  CPU로 떨어진 상황(결정 55의 대상, 약 10배 느림)이 아니라 첫 호출만 느린 현상으로 본다. 컨테이너는 건드리지 않았다.
- 조치(새 파일, 기존 파일은 그대로): `teacher/run_r9b.py` = `run_r9.py` + precheck 뒤 **같은 teacher 요청 1회 warm-up**(T-R 첫 문항, seed = seed_base − 1).
  warm-up 응답은 trace가 아니고(학습·판정에 쓰지 않음) 속도·`/api/ps`만 `teacher/tr_warmup.json`에 남긴다. warm-up 뒤 100% GPU가 아니면 수집하지 않는다.
  guard 기준(33.71 tok/s, 모든 trace 호출), 검사, T-R 통과 규칙(`tr_rule.json`), 문항·seed는 바꾸지 않는다. TEACH-R도 같은 실행기를 쓴다.
- 작업 표 2판 `gpu/jobs_prep2.json`(`make_jobs_prep2.py`): `T-R2`·`TEACH-R2`(조건 `T-R2` ok·`ready/TEACH-R2.json`), J 작업은 1판 그대로. scheduler11을 2판으로 다시 시작
  (1판 실행은 진행 중 작업 없이 멈춤 — PID 파일의 PID로 멈춤).
- 결정 55에 따라 이 다시 재기는 무효가 된 측정을 대체하는 것이고 다시 돌리기(rerun)가 아니다. 다시 재기에서도 guard가 걸리면 Ollama 작업을 멈추고 보고한다(TEACH-R 하지 않음).
