# B안 실행 기록

2026-11-15 KST에 사용자가 B안 진행을 승인했다. 범위는 workstation4의 지정 GPU 3장에서 S0T0·S1T0 학습 32개와 최종 CT10K 평가 160셀이다. 각 평가 셀의 기존 기술적 재시도 기준을 적용한다.

- 고정 커밋 `decbc87a138fd2100bfdd1d41cb4b755f7feee2a`
- B안 명세 SHA-256 `78bf867c9ad64478029ea36e41f2765b5351f3db13ab0797bc8304fbf3951002`
- 승인 기록은 호스트 `/data/hwkim/sftdpo_work/topic2_semantic_order/followup_conditions/provenance/budget_b_decbc87a/`의 `lane0.json`, `lane1.json`, `lane2.json`에 있다. SHA-256은 배정 순서대로 `2f206e1906a7adb3555026464751e5a365bb14f67090c3ec6c4b0da2de09e189`, `849e50c1ca88b6dbd21979c054e64c6aed28bd931a092bc7a777a6ca1387064f`, `d9f8ae6e45f8a94b044a9079b5da5c6d1bfe4d8d6a9a08a35b57db97534351dc`다.
- 새 작업 시작 마감은 운영상 2026-11-27 00:00 KST로 설정했다. 이 시각을 지나면 진행 중인 단계의 정상 종료 후 새 작업 시작이 막힌다.
- 고정 worktree의 CPU preview에서 승인과 배정 12/12/8개, 개별 설정과 입력 해시, 수정안 SHA를 대조했다. Trigger `topic2-followup-budget-b-decbc87a.path`는 `tables/device_matched/followup_analysis.json` 생성까지 대기 중이다. 등록 시 B안 실행 프로세스는 시작 전이었고 기존 E1·E2는 실행 중이었다.
- B안의 launcher와 분석은 `results_B/execution/`와 `results_B/analysis/`에 기록된다. 종료 근거는 `results_B/execution/done.json` 및 `results_B/analysis/contrast.json`이다.

시작 이후 세 GPU 배정 기준 약 84시간이 기본 전망이다. 기존 평가의 관측 재시도 비율과 시도별 중앙값을 적용하면 약 120시간이다. 두 수치 모두 시작 전 대기 시간을 제외한다. [비용 산정](../MINIMAL_EXECUTION_PLAN.md).
