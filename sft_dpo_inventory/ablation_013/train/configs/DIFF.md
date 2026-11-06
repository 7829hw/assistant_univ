# config 차이(ablation_013)

| config | 바탕 | 바꾼 키 |
|---|---|---|
| A3T-o<seed>(1102·211102·2026113) | ablation_011/train/configs/A3-o<seed>.yaml | data.train·valid·manifest → ablation_013/build/A3T/full; training.a11_record_order_file → ablation_013/build/orders/record_order_A3T_o<seed>.json; output_dir·profiling.output → /data/hwkim/sftdpo_work/ablation_013/train/<id> |
| A0-o<seed>(2026117·2026131) | ablation_011/train/configs/A0-o1102.yaml | training.shared_slot_order_seed → <seed>; shared_slot_order_file → ablation_013/build/orders/order_b2_o<seed>.json; a11_record_order_file → ablation_013/build/orders/record_order_A0_o<seed>.json; output_dir·profiling.output → /data/hwkim/sftdpo_work/ablation_013/train/<id> |

그 밖(모델·revision, 1 epoch, lr 2e-4 linear → 0, batch 1·accum 1, warmup 1, LoRA r16/α32/dropout 0.05·7 모듈, max_seq 12,288, seed 43, bf16, gradient checkpointing, thinking.loss_scope by_source, enable_thinking true)은 바탕과 같다.

config: A3T-o1102, A3T-o211102, A3T-o2026113, A0-o2026117, A0-o2026131
