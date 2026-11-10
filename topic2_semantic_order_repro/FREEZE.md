# FREEZE — 신규 결과 확인 전에 고정한 것

기준 브랜치 `geoflow/topic2-repro`. 아래는 신규 10개 모델의 H-dev 결과를 보기 전에 커밋한 것이며, 이후 바꾸지 않았다.

| 항목 | 고정 시점(커밋) | 내용 |
|---|---|---|
| 사전 등록 | `6a1c3f5e` `PLAN.md` | 신규 학습 10개(arm × seed × run), H-dev만 평가, CT10K 재평가 안 함, 통계 계획, Q1–Q5 판정 규칙, 방향 판정 규칙 |
| 학습 설정 | `6a1c3f5e` `configs/` | r1 설정과 비교해 `output_dir`/`profiling.output`만 다름(10/10 자동 검증, `configs/manifest.json`). 학습 seed 43 유지, 결정론 강제 없음 |
| 작업표·스케줄러 | `6a1c3f5e` `gpu/jobs_repro.json`, `gpu/scheduler17.py` | scheduler16 사본(경로·태그만 변경). 모든 GPU 작업은 이 커밋의 worktree(`wt_6a1c3f5_sched17`)에서 실행 |
| 분석 도구 | `24760b8e` `analysis/variance_repro.py` | 신규 평가 전 고정. 평가 후 이 파일은 수정하지 않았다 |
| 평가 시작 | `470e1c21` `gpu/ready/REPRO_TOOLS.json` | 분석 도구 커밋 뒤에만 평가가 시작되도록 gating |
| T1 붕괴 run 정의 | PLAN 6절 | H-dev T1 정확도 < 50% |
| 방향 판정 규칙 | PLAN 7절 | A: 전체 재학습 SD ≥ 1pp **그리고** T1 재학습 SD > T1 Arm 효과 |

## 평가 후 추가된 것(사전 등록 밖) — 구분해서 읽을 것
- `analysis/make_figures_repro.py`와 `tables/repro_t1_error_types.json`(신규 18셀 T1 오류 유형 재집계)은 결과 확인 **후** 작성했다. 분류기는 Stage 1(`stage1_failure_types.py`)과 같고, 결과로 아무 기준도 바꾸지 않았다.
- 상호작용 F 검정(재학습 잔차 대비)과 Fisher 정확 검정(T1 붕괴 run 6/9 vs 3/9)은 사후에 추가한 기술 통계이며 사전 등록 기준이 아니다.
- 선별·재실행: 잘림 규칙(>1% 또는 서버 오류 ≥ 2)에 따른 자동 재실행 4건만 있었다(결과와 무관하게 교체, 원본은 `cells/replaced/`, `RERUNS_REPRO.json`). 그 밖의 제외·교체 없음.
- H-final은 열지 않았다. CT10K는 이번 실험에서 읽지 않았다(Stage 1의 기존 셀 재집계 제외).
