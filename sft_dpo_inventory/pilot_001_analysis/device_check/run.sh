#!/usr/bin/env bash
# 결정 37: E와 B-conv를 GPU 2의 Ollama(0.35.1)에서 업체 100으로 한 번씩 다시 잰다(보조 기록, PROTOCOL 판정은 바꾸지 않는다).
# 명령은 pilot_prep_003의 E·B-conv와 같다(Q4_K_M, num_predict 미지정, --condition-check, 문항마다 모델 내림). HF 측정과 동시에 돌리지 않는다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../../.." && pwd)
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
GPU2=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21
export PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
for cell in E B-conv; do
  if [ $cell = E ]; then m=qwen3:8b; else m=geoflow-qwen3-8b-b968826d-base:q4km-hfthink; fi
  v=$(curl -s localhost:11434/api/version); ps=$(curl -s localhost:11434/api/ps)
  apps=$(nvidia-smi -i $GPU2 --query-compute-apps=pid,process_name,used_memory --format=csv,noheader)
  mem=$(nvidia-smi -i $GPU2 --query-gpu=uuid,memory.used --format=csv,noheader)
  log "precheck $cell: version=$v ps=$ps gpu2=[$mem] apps=[$apps]"
  if [ "$v" != '{"version":"0.35.1"}' ] || [ -n "$apps" ] || [ "$ps" != '{"models":[]}' ]; then log "STOP: precheck failed for $cell"; exit 1; fi
  log "$cell (GPU 2) start"
  "$TV" evaluate_vendor100.py --gold evaluation/vendor100/gold.yaml llm --model "$m" --reference-date 2026-09-25 \
      --condition-check --model-think auto --out "$HERE/$cell.json" > "$HERE/$cell.log" 2>&1
  rc=$?; log "$cell exit=$rc"; [ $rc -eq 0 ] || exit 1
  until [ "$(curl -s localhost:11434/api/ps)" = '{"models":[]}' ]; do sleep 5; done
done
log "device_check done"
