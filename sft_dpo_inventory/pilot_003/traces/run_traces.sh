#!/usr/bin/env bash
# batch006 승인 24문항 HF base trace(greedy 1 + 표본 8, thinking 켬, 8192). 결정 83(Y): 질문 6개씩 GPU 0–3에 나눈다.
# 질문 번호(qi)·seed는 전체 순서 그대로(collect_traces --range). 재실행 없음. 출력 원문은 ignore 경로.
set -u
source "$(dirname "$0")/../gpu_lib.sh"
cd /home/hwkim/assistant_univ
IN=training/generated/pilot_003/trace_inputs/batch006
pids=(); gpus=(0 1 2 3); ranges=(0:6 6:12 12:18 18:24)
for i in 0 1 2 3; do gpu_ok ${gpus[$i]} "traces part$i" || exit 1; done
for i in 0 1 2 3; do g=${gpus[$i]}
  CUDA_VISIBLE_DEVICES=$g "$PY" sft_dpo_inventory/thinking_prep_001/collect_traces.py --corpus "$IN" --split train \
    --range ${ranges[$i]} --out training/generated/thinking_traces/batch006/part$i \
    --summary "$P3/traces/batch006/part$i" > "$P3/traces/batch006_part$i.log" 2>&1 &
  pids+=($!); p3log "traces part$i range ${ranges[$i]} GPU $g start pid $!"
done
rc=0; for i in 0 1 2 3; do wait ${pids[$i]}; r=$?; [ $r = 0 ] || rc=1; p3log "traces part$i exit=$r"; done
exit $rc
