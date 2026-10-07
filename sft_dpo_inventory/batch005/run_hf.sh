#!/usr/bin/env bash
# batch005 HF base 출력 수집. 인자: 쓸 GPU 번호(3 기본. 3에 다른 프로세스가 있으면 CLAUDE.md 5번에 따라 Ollama 모델이 없을 때만 2).
# 쓰기 전에 host nvidia-smi로 UUID·메모리·다른 프로세스를 확인하고, 다른 프로세스가 있으면 멈춘다. 재실행 없음.
set -u
GPU=${1:-3}
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
declare -A UUID=([2]=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21 [3]=GPU-48f798cc-9437-50ac-d604-448bbad7b311)
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
{
  echo "## $(date -Is) host (GPU $GPU)"; nvidia-smi -L
  nvidia-smi --query-gpu=index,uuid,memory.used --format=csv,noheader
  nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader
  echo "## ollama"; curl -s localhost:11434/api/ps; echo
  echo "## torch CUDA $GPU"; CUDA_VISIBLE_DEVICES=$GPU "$PY" -c "import torch; print('GPU-'+str(torch.cuda.get_device_properties(0).uuid))"
} >> "$HERE/gpu_check.txt" 2>&1
# 직전 Ollama 측정의 모델 내림 직후에는 컨테이너의 runner가 잠깐 남는다(결정 43 runs.log). 최대 60초 기다린 뒤 확인한다.
for _ in $(seq 12); do [ -z "$(nvidia-smi -i ${UUID[$GPU]} --query-compute-apps=pid --format=csv,noheader)" ] && break; sleep 5; done
used=$(nvidia-smi -i ${UUID[$GPU]} --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')
procs=$(nvidia-smi -i ${UUID[$GPU]} --query-compute-apps=pid --format=csv,noheader | wc -l)
loaded=$(curl -s localhost:11434/api/ps | "$PY" -c 'import json,sys; print(len(json.load(sys.stdin)["models"]))' 2>/dev/null || echo 1)
log "GPU$GPU precheck used=${used}MiB procs=$procs ollama_loaded=$loaded"
if [ "$used" -ge 100 ] || [ "$procs" -ne 0 ]; then log "STOP: GPU $GPU busy"; exit 1; fi
if [ "$GPU" = 2 ] && [ "$loaded" != "0" ]; then log "STOP: Ollama model loaded on GPU 2"; exit 1; fi
CUDA_VISIBLE_DEVICES=$GPU "$PY" -c "import torch,sys; sys.exit(0 if 'GPU-'+str(torch.cuda.get_device_properties(0).uuid)=='${UUID[$GPU]}' else 1)" || { log "STOP: CUDA $GPU UUID mismatch"; exit 1; }
log "hf_collect start (GPU $GPU)"
CUDA_VISIBLE_DEVICES=$GPU "$PY" "$HERE/hf_collect.py" > "$HERE/hf_collect.log" 2>&1
rc=$?; log "hf_collect exit=$rc"; exit $rc
