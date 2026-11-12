# 실험 매트릭스

Order seed 순서: **1102, 211102, 2026113, 2026117, 2026131**. Training seed 43 공통. A/B 원 실험은 모두 run 1이다.

| 실험 | Arm | Order | LR | Seeds × runs | 상태 |
|---|---|---|---|---:|---|
| 0, 1, 2 | A | 동결 NumPy O4′ | linear | 5×1 | 기존 완료, 재사용 |
| 0, 1, 2 | B | 동결 semantic 0.24 | linear | 5×1 | 기존 완료, 재사용 |
| 1 | C | A와 동일 | matched constant + warmup | 5×1 | CPU 준비, GPU BLOCKED |
| 1 | D | B와 동일 | matched constant + warmup | 5×1 | CPU 준비, GPU BLOCKED |
| 2 | F0 | semantic 0.00 | linear | 5×1 | 순서 검증 완료, GPU BLOCKED |
| 2 | F48 | semantic 0.48 | linear | 5×1 | 순서 검증 완료, GPU BLOCKED |
| 3 | A/B | 원래 각 순서 | linear | 2×3×3, H-dev | 기존 결과 재사용. Seeds 1102, 211102, 2026131, r1–r3. 최초 2026131 r2 포함 |
| 4 | V4 O4′/semantic | A/B | linear | 2×5×1 | 기존 결과 사용 가능 |
| 4 | 대체 coverage O4′/semantic | 승인 corpus 필요 | linear | 2×5×1 예정 | 데이터 승인 BLOCKED; 준비만 |

GPU phase 1: seed 1102, 211102, 2026113 × C/D/F0/F48 = 12 train, 기본 216 eval cells. Phase 2: seed 2026117, 2026131 × 같은 네 조건 = 8 train, 기본 144 eval cells. 각 모델은 H-dev 1, CT10K 5 chunks, E1 3 sets×4 replicates. 같은 seed 재평가 규칙 적용 시 수가 늘어난다. 단계 간 진입 결정에는 accuracy를 사용하지 않는다.
