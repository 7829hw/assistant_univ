#!/usr/bin/env bash
# pilot_prep_001 GPU 2 작업을 순서대로 실행한다(동시에 돌리지 않는다). Ollama는 쓰지 않는다.
# 1) 메모리 측정(LR0, 3 step, 가장 긴 레코드)  2) HF-F 1회차  3) HF-F 2회차(같은 조건, 첫 응답 바이트 비교용)
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
export CUDA_VISIBLE_DEVICES=2 HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
       TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
log() { echo "== $1 $(date -Is)" >> "$HERE/gpu_runs.log"; }
log "memory_probe start"; "$PY" "$HERE/memory_probe.py" --work /home/hwkim/sftdpo_work/pilot_prep_001/probe --steps 3 > "$HERE/memory/probe.log" 2>&1; log "memory_probe exit=$?"
log "hf_f_run1 start"; "$PY" "$HERE/hf_eval_vendor100.py" --condition-check --out "$HERE/hf/HF-F_run1.json" > "$HERE/hf/run1.log" 2>&1; log "hf_f_run1 exit=$?"
log "hf_f_run2 start"; "$PY" "$HERE/hf_eval_vendor100.py" --condition-check --out "$HERE/hf/HF-F_run2.json" > "$HERE/hf/run2.log" 2>&1; log "hf_f_run2 exit=$?"
log "all done"
