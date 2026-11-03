# config 차이(바탕 ablation_011/train/configs/A3-o<seed>.yaml)

| 키 | 바탕(A3) | ablation_012 |
|---|---|---|
| data.train·valid·manifest | ablation_011/build/A3/full | ablation_012/build/<arm>/full |
| training.output_dir·profiling.output | /data/hwkim/sftdpo_work/ablation_011/train/A3-o<seed> | /data/hwkim/sftdpo_work/ablation_012/train/<id> |
| training.a11_record_order_file | ablation_011/build/orders/record_order_A3_o<seed>.json | ablation_012/build/orders/record_order_<arm>_o<seed>.json |

순서 seed·A0 O4' 순서 파일(ablation_011/build/orders/order_b2_o<seed>.json)과 그 밖(모델·revision, 1 epoch, lr 2e-4 linear → 0, batch 1·accum 1, warmup 1, LoRA r16/α32/dropout 0.05·7 모듈, max_seq 12,288, seed 43, bf16, gradient checkpointing, thinking.loss_scope by_source, enable_thinking true)은 바탕과 같다.

config: A3R-d1-o1102, A3R-d1-o211102, A3R-d1-o2026113, A3R-d2-o1102, A3R-d2-o211102, A3R-d2-o2026113
