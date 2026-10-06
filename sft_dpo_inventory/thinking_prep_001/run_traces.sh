#!/usr/bin/env bash
# HF-E 두 회차가 끝난 뒤(gpu_runs.log의 "hf_e_run2 exit") GPU 2에서 trace를 수집한다. 동시에 돌리지 않는다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
until grep -q "hf_e_run2 exit" "$HERE/gpu_runs.log" 2>/dev/null; do
  if grep -q "hf_e_run[12] exit=[1-9]" "$HERE/gpu_runs.log" 2>/dev/null; then echo "HF-E 실패, trace 수집 안 함"; exit 1; fi
  sleep 30
done
export CUDA_VISIBLE_DEVICES=2 HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
       TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
echo "== traces start $(date -Is)" >> "$HERE/gpu_runs.log"
"$PY" "$HERE/collect_traces.py" --corpus training/generated/reviewed_gold_v003_t2pc --split train \
    --out training/generated/thinking_traces/v003_t2pc_train --summary "$HERE/traces" > "$HERE/traces.log" 2>&1
echo "== traces exit=$? $(date -Is)" >> "$HERE/gpu_runs.log"
