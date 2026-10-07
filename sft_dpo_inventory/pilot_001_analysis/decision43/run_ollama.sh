#!/usr/bin/env bash
# 결정 43-2 변환 경로 영향: B-conv와 Ollama-최종을 GPU 2의 Ollama(0.35.1)에서 valid98로 한 번씩 잰다.
# 명령은 업체 100의 B-conv·Ollama 셀과 같다(Q4_K_M, num_predict 미지정, --condition-check, think 미지정, 문항마다 모델 내림).
# 문항만 valid98(valid98_gold.yaml)로 바꾼다. pipeline은 HF valid98(provider_eval.make_pipeline mock)과 같은 구성이다.
# HF 측정과 동시에 돌리지 않는다(GPU 2에 다른 프로세스가 있으면 멈춘다). 재실행 없음.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../../.." && pwd)
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
GPU2=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21
export PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
for cell in ${CELLS:-B-conv Ollama-final}; do
  if [ $cell = B-conv ]; then m=geoflow-qwen3-8b-b968826d-base:q4km-hfthink; else m=geoflow-qwen3-8b-pilot001-final:q4km-hfthink; fi
  v=$(curl -s localhost:11434/api/version); ps=$(curl -s localhost:11434/api/ps)
  apps=$(nvidia-smi -i $GPU2 --query-compute-apps=pid,process_name,used_memory --format=csv,noheader)
  mem=$(nvidia-smi -i $GPU2 --query-gpu=uuid,memory.used --format=csv,noheader)
  log "precheck $cell: version=$v ps=$ps gpu2=[$mem] apps=[$apps]"
  if [ "$v" != '{"version":"0.35.1"}' ] || [ -n "$apps" ] || [ "$ps" != '{"models":[]}' ]; then log "STOP: precheck failed for $cell"; exit 1; fi
  log "valid98 $cell (GPU 2) start"
  "$TV" evaluate_vendor100.py --gold "$HERE/valid98_gold.yaml" llm --model "$m" --reference-date 2026-09-25 \
      --condition-check --model-think auto --out "$HERE/valid98_$cell.json" > "$HERE/valid98_$cell.log" 2>&1
  rc=$?; log "valid98 $cell exit=$rc"; [ $rc -eq 0 ] || exit 1
  until [ "$(curl -s localhost:11434/api/ps)" = '{"models":[]}' ]; do sleep 5; done
done
log "ollama valid98 done"
