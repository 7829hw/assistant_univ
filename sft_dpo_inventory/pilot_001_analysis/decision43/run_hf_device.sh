#!/usr/bin/env bash
# 결정 43-1 HF 경로 장치 일치: pilot_001 SFT step 124 adapter를 GPU 2에서 HF-E 조건으로 valid98에 대해 잰다.
# GPU 3 기록(pilot_001/valid98/runs/sft_step124.json)과 비교한다(compare_hf_device.py). 재실행 없음.
# GPU 2는 Ollama GPU다(CLAUDE.md 5번 예외): Ollama 모델이 올라가 있지 않고 다른 프로세스가 없을 때만 시작한다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
GPU2=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21
ADAPTER=/home/hwkim/sftdpo_work/pilot_001/checkpoints/sft/checkpoint-124
RAW=$REPO/training/generated/pilot_001_analysis
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
mkdir -p "$RAW"; cd "$REPO"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
{
  echo "## $(date -Is) host"; nvidia-smi -L
  nvidia-smi --query-gpu=index,uuid,memory.used --format=csv,noheader
  nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader
  echo "## ollama"; curl -s localhost:11434/api/version; echo; curl -s localhost:11434/api/ps; echo
  echo "## torch CUDA 2"; CUDA_VISIBLE_DEVICES=2 "$PY" -c "import torch; p=torch.cuda.get_device_properties(0); print('GPU-'+str(p.uuid))"
} >> "$HERE/gpu_check.txt" 2>&1
used=$(nvidia-smi -i $GPU2 --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')
procs=$(nvidia-smi -i $GPU2 --query-compute-apps=pid --format=csv,noheader | wc -l)
loaded=$(curl -s localhost:11434/api/ps | "$PY" -c 'import json,sys; print(len(json.load(sys.stdin)["models"]))' 2>/dev/null || echo 1)
log "GPU2 precheck used=${used}MiB procs=$procs ollama_loaded=$loaded"
if [ "$used" -ge 100 ] || [ "$procs" -ne 0 ] || [ "$loaded" != "0" ]; then log "STOP: GPU 2 busy"; exit 1; fi
CUDA_VISIBLE_DEVICES=2 "$PY" -c "import torch,sys; sys.exit(0 if 'GPU-'+str(torch.cuda.get_device_properties(0).uuid)=='$GPU2' else 1)" || { log "STOP: CUDA 2 is not $GPU2"; exit 1; }
log "sft_step124_gpu2 start"
CUDA_VISIBLE_DEVICES=2 "$PY" "$REPO/sft_dpo_inventory/pilot_001/valid98/eval_valid98.py" --label sft_step124_gpu2 \
  --out "$HERE/sft_step124_gpu2.json" --raw-out "$RAW/sft_step124_gpu2_raw.jsonl" --adapter "$ADAPTER" > "$HERE/sft_step124_gpu2.log" 2>&1
rc=$?; log "sft_step124_gpu2 exit=$rc"; exit $rc
