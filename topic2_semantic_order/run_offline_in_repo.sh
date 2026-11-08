#!/usr/bin/env bash
# NO GPU CALLS: generate orders, configs, and offline integrity checks only.
set -euo pipefail
if [ ! -f sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl ]; then
  echo 'Run from GeoFlow repository root after unpacking topic2_semantic_order/' >&2
  exit 1
fi
python topic2_semantic_order/semantic_schedule.py \
  --train sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl \
  --approved sft_dpo_inventory/pilot_006_prep/approved/approved_train_v6.jsonl \
  --output-dir topic2_semantic_order/orders \
  --seeds 1102 211102 2026113 2026117 2026131 \
  --reference-order-dir sft_dpo_inventory/ablation_011/build/orders \
  --reference-order-dir sft_dpo_inventory/ablation_013/build/orders
python topic2_semantic_order/make_training_configs.py \
  --repo-root . --schedule-dir topic2_semantic_order/orders \
  --config-dir topic2_semantic_order/configs \
  --seeds 1102 211102 2026113 2026117 2026131 --repeats 1
python -m unittest -v topic2_semantic_order.test_semantic_schedule
python - <<'PY'
import json
x=json.load(open('topic2_semantic_order/orders/offline_validation_summary.json'))
if x['records']!=1984 or x['questions']!=494:
    raise SystemExit('Unexpected training corpus contents')
if not all(v['reference_is_true_o4prime'] for v in x['seeds'].values()):
    raise SystemExit('Cannot compare exactly against O4prime original manifests')
print('READY FOR GPU DRY-RUN: offline manifest verified')
PY
