#!/usr/bin/env bash
# 결정 83(Y) 장치 일치 확인: HF sampling 5문항(calibration_001 smoke와 같은 문항·seed 20261101, base)을 GPU 0–3 각각에서 생성한다.
# 같은 시간에 서로 다른 GPU에서 돌린다(각 GPU에는 이 프로세스 하나). 비교는 compare.py.
set -u
source "$(dirname "$0")/../gpu_lib.sh"
cd /home/hwkim/assistant_univ
GOLD=sft_dpo_inventory/conversion_diag/selection_gold.yaml
ITEMS=old44/g02,contrast/c03c,indepv2/n06,indepv3/m09,indepv4/k08
RAW=training/generated/pilot_003/raw/device_check; mkdir -p "$RAW"
pids=()
for g in 0 1 2 3; do
  gpu_ok $g "device_check" || exit 1
  CUDA_VISIBLE_DEVICES=$g "$PY" sft_dpo_inventory/thinking_prep_001/hf_eval_thinking.py --gold "$GOLD" --condition-check \
    --do-sample --temperature 0.6 --top-p 0.95 --top-k 20 --min-p 0 --repetition-penalty 1 --seed 20261101 --record-env \
    --only "$ITEMS" --out "$P3/device_check/gpu$g.json" --raw-out "$RAW/gpu${g}_raw.jsonl" > "$P3/device_check/gpu$g.log" 2>&1 &
  pids+=($!); p3log "device_check GPU $g start pid $!"
done
rc=0; for i in 0 1 2 3; do wait ${pids[$i]} || rc=1; p3log "device_check GPU $i exit"; done
exit $rc
