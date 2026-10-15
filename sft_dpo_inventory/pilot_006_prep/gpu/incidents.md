# GPU 작업 사고 기록(pilot_006 준비)

| 시각 | 사고 | 영향 | 원인 | 상태 |
|---|---|---|---|---|
| 2026-10-15 22:28 | J5S·J5R 모든 요청 HTTP 400 | 출력 무효(`ABORTED_*`) | Partial 입력 8,729 + max_tokens 8,192 > `--max-model-len` 16,384 | 해결됨: 결정 117(E2) 17,408 서버 |
| 2026-10-16 00:25–00:29 | worktree 디렉터리 다섯 개(`/data/hwkim/sftdpo_work/pilot_006_prep/wt_*`) 삭제 | B4 첫 시도 실패(`ABORTED_b4_*`, 다시 잼), J1은 생성 3,609/3,609 완료 뒤 manifest 단계 실패(사후 manifest) | **사용자 정리**(세션 2 지시로 확인) | **해결됨**: 결정 124(F3) — worktree를 `/home/hwkim/sftdpo_work/worktrees/`에 두고 작업이 끝나면 Claude Code가 직접 지움, 스크립트는 절대 경로 |
