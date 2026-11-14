# E0–E7 통합 연구 현황

기존 가설, CI 및 결과표의 원본은 `EXPERIMENT_PLAN.md`, `RESULTS.md`, `EXISTING_RESULT_DIAGNOSTICS.md`에 보존했다. 이 문서는 진행 중인 실험과 추가 CPU 분석의 현재 기록이다.

## A. 수행 완료 및 진행 중인 작업

- E0·E3 **ANALYZED**. 검증된 기존 순서, CT10K/H-dev/E1 예측, 반복 학습 결과를 재사용했다. 이번 CPU 오류 분석에는 316개 유효 셀의 문항 점수 227,164건이 들어갔다. 각 셀의 SHA-256과 분류별 원수를 보존했다. [오류 진단 표](causal_controls/tables/integration_snapshot/) · [분류 규칙](causal_controls/TAXONOMY.md).
- E1·E2 **RUNNING**. 2026-11-15 01:31 KST 기준 등록된 신규 run 20개 중 9개 학습 완료, 7개는 예정된 평가까지 완료했다. 검증된 셀은 CT10K 35개, H-dev 9개, E1 92개다. 최초 3장 배정과 20개 처치는 유지된다. 이후 같은 장치 매칭에 필요한 기존 A/B 평가 110개와 CPU 분석이 등록되어 있다. [Run별 증빙](causal_controls/tables/integration_inventory/status.json) · [A/B 매칭 manifest](gpu/device_matched_baselines.json) · [GPU 증빙](gpu/STATUS.md).
- E4 **BLOCKED**. 승인된 대체 coverage corpus와 protected-family 증빙이 필요하다. 설계와 승인 후 감사 스크립트를 보존했다. [Coverage 계획](coverage/COVERAGE_PLAN.md).
- E5–E7 **CPU_VALIDATED / GPU BLOCKED**. 기존 56개 승인 TRAIN 순서와 그에 대응하는 112개 run·448개 checkpoint 규격을 재사용했다. 원래·추가 사전등록 SHA를 검증했다. 기존 테스트 13개와 causal-control 테스트 10개 통과. [실행 규격](causal_controls/run_plan.json) · [CPU 감사](causal_controls/tables/integration_temporal/) · [사전등록 수정 기록](causal_controls/PREREGISTRATION_AMENDMENT.md).
- Learning dynamics. 기존 E1/E2 완료 run 9개에서 496/992/1488/1984-step adapter 총 36개가 확인됐다. 이 중 25/50/75% 평가에는 별도 승인 범위가 필요하다. E5–E7에서는 네 checkpoint 각각의 계획, 평가 해시 검증, 기능별 정확도 및 base→SFT 전이율 분석을 구현했다. [보존 현황](causal_controls/tables/integration_inventory/original_checkpoint_inventory.csv).

## B. 실험 결과표

| 실험 | 확인된 자료 및 효과 | 판정 |
|---|---|---|
| E0 | 5 paired order seeds. CT10K A 88.12%, B 82.19%. B−A −5.93%p, 95% CI [−13.58, +0.57]. Collapse20 10.4→18.6. T1 77.4→47.3%. | 전체 효과 INCONCLUSIVE. 기능별 패턴 EXPLORATORY |
| E0 오류 위치 | T1 각 조건 5,100건. 필수 장소 조회 누락 A 481건, B 1,904건. A 481건과 B 1,883건은 파싱된 단일 모델 계획에 장소가 없었고 B 21건은 발생 단계 미확정. | EXPLORATORY |
| E1 | 기존 A/B와 신규 C/D의 nominal LR 합은 각 0.1984. 5-seed interaction은 승인 작업 종료 후 산출. | RUNNING |
| E2 | F0/B/F48의 fine record TV 54.70/38.45/38.50%. 등록된 성능 대비는 평가 완료 후 산출. | RUNNING |
| E3 | H-dev 3 order seeds ×3 runs/arm. Within-cell pooled SD 전체 2.43%p, T1 22.63%p. T1 B−A −18.13%p, 95% CI [−55.56, +21.64]. | 반복 변동 관측 SUPPORTED. 순서 효과 분리 INCONCLUSIVE |
| E4 | Coverage × ordering 매트릭스와 검증 요구사항 준비. | BLOCKED |
| E5 | S0T0–S1T0 매칭 8/8. 나머지 factorial 비교 0/8. 통과한 쌍의 full-response LR 가중 비중 차이의 seed별 decile 평균 절대값 0.07–0.25%p, 최대 1.26%p. | 이 순서들의 factorial 효과는 EXPLORATORY. GPU BLOCKED |
| E6 | Group-blind와 placebo 및 true-semantic 대비는 노출 감사 통과 8/8. | CPU_VALIDATED. 성능 BLOCKED |
| E7 | 8/8 seed에서 decile별 joint record·input·loss tokens 일치. 최대 간격 평균 +21.1–46.1 step, 전환율 −4.0–5.6%p. 두 속성이 함께 달라진다. | CPU_VALIDATED. 성능 BLOCKED |

## C. 연구질문과 논문 문구

기존 Qwen3-8B V4 SFT에서는 coarse record exposure TV가 9.16%에서 1.21%로 하락한 조건에서도 T1 요금 정확도와 여러 fine group의 관찰 성능이 낮았다. 같은 순서에서 loss-token TV는 10.37%에서 9.83%, LR-weighted loss-token TV는 10.70%에서 10.51%로 바뀌었다. 따라서 이 설정에서 레코드 노출의 균형은 유효 감독 신호의 시간적 균형이나 개별 기능의 성능 보존을 보장하지 않았다. 추정된 전체 정확도 차이의 CI가 0을 포함한다. 간격, 전환, 감독 유형, LR과 coverage의 인과효과는 아직 검증되지 않았다.

새로운 논문용 진단은 T1의 장소 조회 누락 중 단일 모델 계획의 장소 항목 미출력으로 문서화할 수 있는 비율이다. 이를 기존 샘플의 기술 통계로 표시한다. 상관관계, 모델 내부 능력 소실, 다른 모델·도메인 일반화, E5의 factorial 효과와 E7의 개별 gap 효과는 입증되지 않았다. CT10K와 H-dev 결과는 개발 분석이다. [기존 효과 및 CI](STATISTICAL_ANALYSIS.md) · [반복 변동과 실패 조건](FAILURE_CONDITIONS.md).

## D. 재현과 남은 실행

- 승인된 E1/E2 실행 커밋 `007d86ab80705453880b0958a0b2d6812811510f`, A/B 장치 맞춤 커밋 `215b2dd0`. [Phase 1/2 manifests](gpu/) · [설정/순서 SHA](configs/manifest.json) · [데이터 SHA와 검증](DATA_AND_CONFIG_AUDIT.md). 등록된 분석은 `analyze_new.py --device-matched`, 결과는 `tables/device_matched/`에 저장한다.
- E5–E7 원래 사전등록 커밋 `abff9048b061b15d4bd26c0bac4d9b26847b050d`. 새 수정 기록은 승인에 앞서 branch에 고정하며 두 원래 등록 문서의 해시는 그대로다. [CPU 실행 명령](causal_controls/README.md) · [큐, 전체 SHA 및 승인 필드](causal_controls/tables/integration_inventory/queue.json).
- E5–E7 전체는 중복 제거 후 112개 학습, checkpoint 평가 2,688셀이다. 관측한 셀 1회 소요시간 중앙값으로 약 2,338 GPU시간, 모든 셀 1회 재시도 시 약 4,309 GPU시간, 체크포인트와 최종 bundle 약 282 GiB다. 추정에서 서버 초기화·전송·장애 복구 및 원본 평가 저장 공간은 제외했다. 승인 범위에 실행할 job 목록, 정확한 commit/manifest SHA, GPU UUID, 시작 마감과 비용 상한이 필요하다. 매칭을 통과한 비교를 우선하면 80개 학습, 1,920개 평가 셀, 약 1,670 GPU시간 및 201 GiB다. 원래 8개 order seed와 두 training seed, 다중 비교 기준은 이 옵션에도 동일하다.
- E1/E2의 새 작업 시작 승인 마감은 2026-11-20 07:04 KST다. 현재 추정 완료 시간은 11월 18일 밤–19일 오전 KST이며 같은 GPU A/B 재평가와 기술적 재시도 소요시간에 따라 달라진다. [현재 작업 증빙](causal_controls/tables/integration_inventory/status.json).
