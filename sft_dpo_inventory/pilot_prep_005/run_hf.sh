#!/usr/bin/env bash
# pilot_prep_005 HF 작업(차례로, 재실행 없음). 인자: GPU 번호, 작업 이름(sel | aux | traces).
# CLAUDE.md 5·6번: GPU 3 기본. 3에 다른 프로세스가 있으면 Ollama 모델이 올라가 있지 않을 때만 GPU 2. 작업마다 host nvidia-smi로
# UUID·메모리·다른 프로세스와 Ollama 적재 상태를 확인하고, 조건이 맞지 않으면 그 작업을 하지 않고 멈춘다.
set -u
GPU=$1; JOB=$2
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
GEN=training/generated/pilot_prep_005
declare -A UUID=([2]=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21 [3]=GPU-48f798cc-9437-50ac-d604-448bbad7b311)
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
{
  echo "## $(date -Is) $JOB host (GPU $GPU)"; nvidia-smi -L
  nvidia-smi --query-gpu=index,uuid,memory.used --format=csv,noheader
  nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader
  echo "## ollama"; curl -s localhost:11434/api/ps; echo
  echo "## torch CUDA $GPU"; CUDA_VISIBLE_DEVICES=$GPU "$PY" -c "import torch; print('GPU-'+str(torch.cuda.get_device_properties(0).uuid))"
} >> "$HERE/gpu_check.txt" 2>&1
for _ in $(seq 12); do [ -z "$(nvidia-smi -i ${UUID[$GPU]} --query-compute-apps=pid --format=csv,noheader)" ] && break; sleep 5; done
used=$(nvidia-smi -i ${UUID[$GPU]} --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')
procs=$(nvidia-smi -i ${UUID[$GPU]} --query-compute-apps=pid --format=csv,noheader | wc -l)
loaded=$(curl -s localhost:11434/api/ps | "$PY" -c 'import json,sys; print(len(json.load(sys.stdin)["models"]))' 2>/dev/null || echo 1)
log "$JOB GPU$GPU precheck used=${used}MiB procs=$procs ollama_loaded=$loaded"
if [ "$used" -ge 100 ] || [ "$procs" -ne 0 ]; then log "STOP: $JOB GPU $GPU busy"; exit 1; fi
if [ "$GPU" = 2 ] && [ "$loaded" != "0" ]; then log "STOP: $JOB Ollama model loaded on GPU 2"; exit 1; fi
CUDA_VISIBLE_DEVICES=$GPU "$PY" -c "import torch,sys; sys.exit(0 if 'GPU-'+str(torch.cuda.get_device_properties(0).uuid)=='${UUID[$GPU]}' else 1)" || { log "STOP: $JOB CUDA $GPU UUID mismatch"; exit 1; }
log "$JOB start (GPU $GPU)"
case $JOB in
  sel) CUDA_VISIBLE_DEVICES=$GPU "$PY" "$HERE/sets/eval_set.py" --items "$HERE/sets/selection_items.json" --label base \
         --out "$HERE/sets/runs/selection_base.json" --raw-out "$GEN/sets/selection_base_raw.jsonl" > "$HERE/sets/runs/selection_base.log" 2>&1 ;;
  aux) CUDA_VISIBLE_DEVICES=$GPU "$PY" "$HERE/sets/eval_set.py" --items "$HERE/sets/aux_test_items.json" --label base \
         --out "$HERE/sets/runs/aux_test_base.json" --raw-out "$GEN/sets/aux_test_base_raw.jsonl" > "$HERE/sets/runs/aux_test_base.log" 2>&1 ;;
  traces) CUDA_VISIBLE_DEVICES=$GPU "$PY" sft_dpo_inventory/thinking_prep_001/collect_traces.py \
         --corpus "$GEN/trace_inputs/batch005" --split train --out training/generated/thinking_traces/batch005 \
         --summary "$HERE/traces/batch005" > "$HERE/traces/batch005.log" 2>&1 ;;
  *) log "STOP: unknown job $JOB"; exit 2 ;;
esac
rc=$?; log "$JOB exit=$rc"; exit $rc
