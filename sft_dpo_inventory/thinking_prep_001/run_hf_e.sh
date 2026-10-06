#!/usr/bin/env bash
# HF-E(업체 100, thinking 켬) 두 번을 GPU 2에서 순서대로 잰다. Ollama는 쓰지 않는다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
RAW=$REPO/training/generated/thinking_prep_001
export CUDA_VISIBLE_DEVICES=2 HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
       TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
mkdir -p "$HERE/hf_e" "$RAW"; cd "$REPO"
log() { echo "== $1 $(date -Is)" >> "$HERE/gpu_runs.log"; }
for n in 1 2; do
  log "hf_e_run$n start"
  "$PY" "$HERE/hf_eval_thinking.py" --condition-check --out "$HERE/hf_e/HF-E_run$n.json" \
      --raw-out "$RAW/HF-E_run${n}_raw.jsonl" > "$HERE/hf_e/run$n.log" 2>&1
  log "hf_e_run$n exit=$?"
done
