#!/usr/bin/env bash
# PROTOCOL_v2 2.2: aux_test_v1의 Ollama 기준 셀(E, B-conv)을 학습 전에 한 번 잰다(그 셋의 첫 측정). 재실행 없음.
# 명령은 업체 100의 E·B-conv 셀과 같다(Q4_K_M, num_predict 미지정, --condition-check, think 미지정, 문항마다 모델 내림).
# 문항만 aux_test_gold.yaml로 바꾼다. Ollama는 GPU 2(결정 32·38). HF 측정과 동시에 돌리지 않는다(GPU 2에 다른 프로세스가 있으면 멈춘다).
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../../.." && pwd)
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
GPU2=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21
export PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
LOG=$HERE/../runs.log
log() { echo "== $1 $(date -Is)" >> "$LOG"; }
v=$(curl -s localhost:11434/api/version)
echo "{\"checked_at\": \"$(date -Is)\", \"ollama\": $v, \"protocol_v2_e_bconv_version\": \"0.35.1\"}" > "$HERE/ollama_version_check_baselines.json"
for cell in E B-conv; do
  if [ $cell = E ]; then m=qwen3:8b; else m=geoflow-qwen3-8b-b968826d-base:q4km-hfthink; fi
  v=$(curl -s localhost:11434/api/version); ps=$(curl -s localhost:11434/api/ps)
  apps=$(nvidia-smi -i $GPU2 --query-compute-apps=pid,process_name,used_memory --format=csv,noheader)
  mem=$(nvidia-smi -i $GPU2 --query-gpu=uuid,memory.used --format=csv,noheader)
  log "aux_test $cell precheck: version=$v ps=$ps gpu2=[$mem] apps=[$apps]"
  if [ "$v" != '{"version":"0.35.1"}' ] || [ -n "$apps" ] || [ "$ps" != '{"models":[]}' ]; then log "STOP: aux_test precheck failed for $cell"; exit 1; fi
  log "aux_test $cell (Ollama GPU 2) start"
  "$TV" evaluate_vendor100.py --gold "$HERE/aux_test_gold.yaml" llm --model "$m" --reference-date 2026-09-25 \
      --condition-check --model-think auto --out "$HERE/$cell.json" > "$HERE/$cell.log" 2>&1
  rc=$?; log "aux_test $cell exit=$rc"; [ $rc -eq 0 ] || exit 1
  until [ "$(curl -s localhost:11434/api/ps)" = '{"models":[]}' ]; do sleep 5; done
done
log "aux_test baselines done"
