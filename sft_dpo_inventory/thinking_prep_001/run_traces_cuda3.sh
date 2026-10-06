#!/usr/bin/env bash
# 사용자 지시(2026-10-06): CUDA 2·3을 모두 쓴다. HF-E 2회차가 CUDA 2에서 도는 동안 trace 수집을 CUDA 3에서 돌린다.
# CUDA 3 = host GPU 3(GPU-48f798cc, PCI BD) = Ollama 컨테이너에 배정된 GPU. 이번 작업에서는 Ollama를 호출하지 않는다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
export CUDA_VISIBLE_DEVICES=3 HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
       TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
{ echo "== traces(CUDA 3) start $(date -Is)"; "$PY" -c "import torch; p=torch.cuda.get_device_properties(0); print('   CUDA_VISIBLE_DEVICES=3 -> GPU-'+str(p.uuid), hex(p.pci_bus_id))"; echo "   host GPU3 used before: $(nvidia-smi -i 3 --query-gpu=memory.used --format=csv,noheader)"; } >> "$HERE/gpu_runs.log"
"$PY" "$HERE/collect_traces.py" --corpus training/generated/reviewed_gold_v003_t2pc --split train \
    --out training/generated/thinking_traces/v003_t2pc_train --summary "$HERE/traces" > "$HERE/traces.log" 2>&1
echo "== traces(CUDA 3) exit=$? $(date -Is)" >> "$HERE/gpu_runs.log"
