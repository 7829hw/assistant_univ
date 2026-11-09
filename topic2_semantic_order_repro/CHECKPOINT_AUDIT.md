# CHECKPOINT_AUDIT — 기존 8개 체크포인트 (Phase 0)

검증: adapter sha256(checkpoint-1984), config sha256, 데이터 sha256(`sft_train.jsonl` = `3575c7f0…`), 순서 sha256, 학습 seed(43), 프로필 상태. 외부 경로의 가중치는 커밋하지 않는다. 원본 JSON: `tables/checkpoint_audit.json`. 생성: `analysis/gen_configs_and_audit.py`.

| arm | order seed | run | adapter sha256 (앞 16) | order sha256 (앞 12) | train seed | 학습 시간(s) | 평균 loss | policy tokens | 상태 |
|---|---|---|---|---|---|---|---|---|---|
| A | 1102 | r1 | 292ca31edc5124e2 | d1133bafe45f | 43 | 11470 | 0.1891 | 16047305 | completed |
| A | 211102 | r1 | e871b1e4db5a4461 | 11c414912c20 | 43 | 11804 | 0.1883 | 16047305 | completed |
| A | 2026131 | r1 | 06f824f30f45ff67 | d5d7e8a163b5 | 43 | 11773 | 0.1883 | 16047305 | completed |
| A | 2026131 | r2 | f38ea145c9ab8ce7 | d5d7e8a163b5 | 43 | 11470 | 0.1885 | 16047305 | completed |
| B | 1102 | r1 | 63c8b14f5c337d4f | 4d8970a1e77d | 43 | 11478 | 0.1906 | 16047305 | completed |
| B | 211102 | r1 | 4e345dbffe317378 | fc9670f543c8 | 43 | 11755 | 0.1902 | 16047305 | completed |
| B | 2026131 | r1 | 827ea1e3023b384e | 35ad44dfa66a | 43 | 11743 | 0.1916 | 16047305 | completed |
| B | 2026131 | r2 | 0a054bf5ef354927 | 35ad44dfa66a | 43 | 11766 | 0.1915 | 16047305 | completed |

- 8개 모두 체크포인트·어댑터가 존재하고 학습 seed 43, 데이터 sha 동일. A의 r1은 ablation_011(o1102, o211102)·ablation_013(o2026131), B의 r1/r2와 A의 o2026131 r2는 `topic2_semantic_order`에서 학습.
- 8개 프로필 모두 `status=completed`, 1,984 step, policy tokens 16,047,305로 동일(토큰 예산 일치). 위치 `/data/hwkim/sftdpo_work/{ablation_011,ablation_013,topic2_semantic_order}/train/`.
- 같은 순서의 A r1과 r2(o2026131)는 순서 sha가 같고(`d5d7e8a1…`) 어댑터 sha가 다르다(`06f824f3…` vs `f38ea145…`) → 재학습 비결정성이 비트 단위로 확인됨. B도 같다(`827ea1e3…` vs `0a054bf5…`).

## 신규 10개 설정 검증 (r1 설정과의 차이)

| id | r1 원본 설정 | 달라진 키 | output 경로만 다름 |
|---|---|---|---|
| A0-o1102-r2 | `sft_dpo_inventory/ablation_011/train/configs/A0-o1102.yaml` | profiling.output, training.output_dir | True |
| A0-o1102-r3 | `sft_dpo_inventory/ablation_011/train/configs/A0-o1102.yaml` | profiling.output, training.output_dir | True |
| A0-o211102-r2 | `sft_dpo_inventory/ablation_011/train/configs/A0-o211102.yaml` | profiling.output, training.output_dir | True |
| A0-o211102-r3 | `sft_dpo_inventory/ablation_011/train/configs/A0-o211102.yaml` | profiling.output, training.output_dir | True |
| A0-o2026131-r3 | `sft_dpo_inventory/ablation_013/train/configs/A0-o2026131.yaml` | profiling.output, training.output_dir | True |
| B-o1102-r2 | `topic2_semantic_order/configs/B-o1102.yaml` | profiling.output, training.output_dir | True |
| B-o1102-r3 | `topic2_semantic_order/configs/B-o1102.yaml` | profiling.output, training.output_dir | True |
| B-o211102-r2 | `topic2_semantic_order/configs/B-o211102.yaml` | profiling.output, training.output_dir | True |
| B-o211102-r3 | `topic2_semantic_order/configs/B-o211102.yaml` | profiling.output, training.output_dir | True |
| B-o2026131-r3 | `topic2_semantic_order/configs/B-o2026131.yaml` | profiling.output, training.output_dir | True |
