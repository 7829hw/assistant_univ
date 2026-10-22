# PLAN_FINAL 정정 1(측정 전, 2026-10-22 11:20) — 측정 시작 실패와 실행기 사본

PLAN_FINAL(FREEZE_FINAL `5f6f34e`)은 고치지 않는다. 이 정정은 **측정 결과가 하나도 없는 상태에서** 실행 경로만 바꾼다(후보·셀·seed·채점·판정 규칙은 그대로).

## 1. 무엇이 일어났나

- 2026-10-22 11:12:37–43 PF-base(GPU 0)·PF-cand(GPU 1)가 회차 1에서 바로 실패(exit 1). 원인: 평가 client `pilot_005/vllm_eval_thinking5.py` 70줄의 금지 셋 검사
  `Path(gold).resolve().relative_to(ROOT)`가 저장소 밖 gold(700 디렉터리)에서 ValueError. `evaluate_vendor100._meta`(1028줄)도 같은 상대 경로 계산을 한다.
- **모델 요청 전에 멈췄다**: 셀 json·원문 없음(raw 디렉터리 빔), shard 로그만 생김. 서버 요청 로그 해당 시간 요청 0.
- 스케줄러가 `done:` 조건(실패도 끝남으로 침)으로 지연 창 L-final을 11:13에 GPU 0에 배정했다. L-final은 다른 GPU가 비기를 기다리는 반복 중이었고
  (latency_final 미시작, 지연 출력 없음), 11:14:39 그 bash(스케줄러 PID 파일의 자식, `ps --ppid`)를 SIGTERM으로 끝냈다 → 스케줄러가 서버를 내리고 정상 종료.
- 실패 흔적(셀 shard 로그 등 18개)은 `/home/hwkim/sftdpo_work/protected_final_v1/aborted_launch1/`(700)에 옮겨 두었다(내용 열지 않음, 커밋 안 함).
- 판단: 측정이 아니다(문항 하나도 처리하지 않음). SPEC 1절 "실행 조건 위반으로 무효가 된 셀만 처음부터 다시"에 해당하는 것으로 보수적으로 기록한다 — 다음 시도에서 또 무효면 멈춘다.

## 2. 바꾼 것(새 파일, 고정본은 그대로)

- `final/vllm_eval_final.py` = `vllm_eval_thinking5.py` 사본: (1) gold가 저장소 밖이면 금지 셋 검사 건너뜀, (2) `EV._meta`를 감싸 저장소 밖 gold의 절대 경로·sha256을 meta에.
  평가 동작(렌더, sampling, 파이프라인, 채점)은 같다.
- `final/run_cell_final.py` = `run_cell6x.py` 사본: Full client만 위 사본으로.
- `final/make_jobs_final2.py` → `gpu/jobs_final2.json`: 셀 실행기만 바꾸고 작업 ID PF2-base·PF2-cand·L-final2. 지연 창 조건은 두 셀의 마지막 회차 파일(`file:` 의존, 셀이 실패하면 건너뜀).
  sampling seed는 `final/cell_seeds_final.json` 그대로.
- 확인: 가짜 vLLM 서버(latency6 `fake_server`)와 저장소 밖 합성 gold(aux 12문항, id만 `pf1/NNN`)로 `run_cell_final.py` → `final_score.load_cells`까지 끝까지 통과
  (meta gold_file 절대 경로, 행 수·원문 sha256 일치). 보호 셋은 쓰지 않았다.
- 고정: `FREEZE_FINAL2.json`(`freeze_final2.py`).
