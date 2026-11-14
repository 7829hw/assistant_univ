# 실험 매트릭스

Order seed 순서: **1102, 211102, 2026113, 2026117, 2026131**. Training seed 43 공통. A/B 원 실험은 모두 run 1이다.

| 실험 | Arm | Order | LR | Seeds × runs | 상태 |
|---|---|---|---|---:|---|
| 0, 1, 2 | A | 동결 NumPy O4′ | linear | 5×1 | 기존 완료, 재사용 |
| 0, 1, 2 | B | 동결 semantic 0.24 | linear | 5×1 | 기존 완료, 재사용 |
| 1 | C | A와 동일 | matched constant + warmup | 5×1 | RUNNING / TRAINED / EVALUATED. [Run별 상태](causal_controls/tables/integration_inventory/status.json) |
| 1 | D | B와 동일 | matched constant + warmup | 5×1 | RUNNING / TRAINED / EVALUATED. [Run별 상태](causal_controls/tables/integration_inventory/status.json) |
| 2 | F0 | semantic 0.00 | linear | 5×1 | RUNNING / TRAINED / EVALUATED. [Run별 상태](causal_controls/tables/integration_inventory/status.json) |
| 2 | F48 | semantic 0.48 | linear | 5×1 | RUNNING / TRAINED / EVALUATED. [Run별 상태](causal_controls/tables/integration_inventory/status.json) |
| 3 | A/B | 원래 각 순서 | linear | 2×3×3, H-dev | 기존 결과 재사용. Seeds 1102, 211102, 2026131, r1–r3. 최초 2026131 r2 포함 |
| 4 | V4 O4′/semantic | A/B | linear | 2×5×1 | 기존 결과 사용 가능 |
| 4 | 대체 coverage O4′/semantic | 승인 corpus 필요 | linear | 2×5×1 예정 | 데이터 승인 BLOCKED; 준비만 |

GPU phase 1: seed 1102, 211102, 2026113 × C/D/F0/F48 = 12 train, 기본 216 eval cells. Phase 2: seed 2026117, 2026131 × 같은 네 조건 = 8 train, 기본 144 eval cells. 각 모델은 H-dev 1, CT10K 5 chunks, E1 3 sets×4 replicates. 같은 seed 재평가 규칙 적용 시 수가 늘어난다. 단계 간 진입 결정에는 accuracy를 사용하지 않는다.


| 실험 | 조건 | Order seed × training seed | 상태 |
|---|---|---:|---|
| 5 | S0T0 / S1T0 / S0T1 / S1T1 | 각 8 × 2 | CPU_VALIDATED. 한 비교만 매칭 통과. Factorial 성능 분석은 탐색적. 학습 BLOCKED |
| 6 | S0T0, S1T0 공유 / placebo 신규 | 각 8 × 2 | CPU_VALIDATED. 8/8 매칭 통과. 학습 BLOCKED |
| 7 | low_gap / high_gap | 각 8 × 2 | CPU_VALIDATED. 8/8 매칭 통과. 학습 BLOCKED |
| 공통 | 496 / 992 / 1488 / 1984-step checkpoints | E5–E7 run별 4개 | 실행 규격 CPU_VALIDATED. 평가 BLOCKED. E1/E2 기존 보존분 [현황](causal_controls/tables/integration_inventory/original_checkpoint_inventory.csv) |

E5–E7 order seeds에는 앞의 5개에 51001, 51002, 51003을 더한다. Training seeds는 43, 51004다. [잠긴 run manifest](causal_controls/run_plan.json) · [GPU 비용과 실행 순서](causal_controls/tables/integration_inventory/queue.json) · [별도 사전등록 수정 기록](causal_controls/PREREGISTRATION_AMENDMENT.md).
