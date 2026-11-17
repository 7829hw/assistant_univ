# 판정 단계 config와 선택 단계 S-V4-o43.yaml의 차이

바꾼 키: profiling.output, training.output_dir, training.shared_slot_order_file, training.shared_slot_order_seed. 그 밖은 모두 같다(아래 검사).

- J-V4-o101: shared_slot_order_seed 43 → 101, shared_slot_order_file → build/V4/order_b2_o101.json, output /data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o101
- J-V4-o523: shared_slot_order_seed 43 → 523, shared_slot_order_file → build/V4/order_b2_o523.json, output /data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o523
- J-V4-o2029: shared_slot_order_seed 43 → 2029, shared_slot_order_file → build/V4/order_b2_o2029.json, output /data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o2029
- J-V4-o31: shared_slot_order_seed 43 → 31, shared_slot_order_file → build/V4/order_b2_o31.json, output /data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o31
- J-V4-o20271027: shared_slot_order_seed 43 → 20271027, shared_slot_order_file → build/V4/order_b2_o20271027.json, output /data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o20271027
