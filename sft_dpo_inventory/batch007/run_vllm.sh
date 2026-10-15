#!/usr/bin/env bash
# batch007 base 출력 수집(결정 104). GPU가 빌 때 GPU 한 장에 vLLM 서버(serve_b7.sh)를 띄우고 vllm_collect.py를 돌린 뒤 서버를 내린다.
#   bash sft_dpo_inventory/batch007/run_vllm.sh GPU_INDEX
set -u
G=$1; PORT=8700
source /home/hwkim/assistant_univ/sft_dpo_inventory/pilot_003/gpu_lib.sh
P3=/home/hwkim/assistant_univ/sft_dpo_inventory/batch007
cd /home/hwkim/assistant_univ
p3log "batch007 vllm collect start GPU $G"
LORAS="p4_sft_step934=/home/hwkim/sftdpo_work/pilot_004/checkpoints/sft/checkpoint-934" bash $P3/serve_b7.sh $G $PORT bf16 fi || { p3log "STOP: server failed"; exit 1; }
"$PY" $P3/vllm_collect.py --port $PORT --concurrency 8 > $P3/vllm_collect.log 2>&1
rc=$?
kill $(cat /data/hwkim/sftdpo_work/batch007/vllm/server_$PORT.pid) 2>/dev/null; rm -f /data/hwkim/sftdpo_work/batch007/vllm/server_$PORT.pid
p3log "batch007 vllm collect exit=$rc"
exit $rc
