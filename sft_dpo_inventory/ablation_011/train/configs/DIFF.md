# config 차이(바탕 pilot_010/train_data/configs_s10/S-V4-o43.yaml)

| 키 | 바탕 | ablation_011 |
|---|---|---|
| data.train·valid·manifest | pilot_010/build/V4/full | A0: 같음 / A1–A3: ablation_011/build/<arm>/full |
| training.output_dir·profiling.output | /data/hwkim/sftdpo_work/pilot_010/train_s10/S-V4-o43 | /data/hwkim/sftdpo_work/ablation_011/train/<id> |
| training.shared_slot_order_seed | 43 | 1102 · 211102 · 2026113 |
| training.shared_slot_order_file | pilot_010/build/V4/order_b2_o43.json(절대 경로) | ablation_011/build/orders/order_b2_o<seed>.json(worktree 상대) |
| training.a11_record_order_file | – | ablation_011/build/orders/record_order_<arm>_o<seed>.json |

그 밖(모델·revision, 1 epoch, lr 2e-4 linear → 0, batch 1·accum 1, warmup 1, LoRA r16/α32/dropout 0.05·7 모듈, max_seq 12,288, seed 43, data_seed 43(쓰이지 않음), bf16, gradient checkpointing, thinking.loss_scope by_source, enable_thinking true)은 바탕과 같다.

config: A0-o1102, A1-o1102, A2-o1102, A3-o1102, A0-o211102, A1-o211102, A2-o211102, A3-o211102, A0-o2026113, A1-o2026113, A2-o2026113, A3-o2026113
