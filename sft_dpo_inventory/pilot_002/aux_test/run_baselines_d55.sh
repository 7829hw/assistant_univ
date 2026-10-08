#!/usr/bin/env bash
# PROTOCOL_v2 2.2: aux_test_v1의 Ollama 기준 셀(E, B-conv) 첫 측정. run_baselines.sh와 같은 명령에 결정 55의 GPU 확인을 붙였다.
# 10:33 KST의 CPU 출력(ABORTED_cpu_E.*)은 측정이 아니었다. 이 실행이 그것을 대체한다(PLAN_DEVIATIONS.md 2번). 재실행 없음.
# 셀마다: precheck(컨테이너 GPU 2, 버전 0.35.1, 모델 없음, GPU 2 비어 있음) → 측정 + watch(첫 문항 100% GPU, 호출 30 tok/s 이상).
# watch가 멈추면 출력은 ABORTED_gpu_{cell}.*로 옮기고 멈춘다. 컨테이너는 건드리지 않는다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../../.." && pwd)
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
GUARD=$HERE/../ollama_gpu_guard.py
export PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
LOG=$HERE/../runs.log
log() { echo "== $1 $(date -Is)" >> "$LOG"; }
v=$(curl -s localhost:11434/api/version)
echo "{\"checked_at\": \"$(date -Is)\", \"ollama\": $v, \"protocol_v2_e_bconv_version\": \"0.35.1\"}" > "$HERE/ollama_version_check_baselines.json"
for cell in E B-conv; do
  if [ $cell = E ]; then m=qwen3:8b; else m=geoflow-qwen3-8b-b968826d-base:q4km-hfthink; fi
  [ -e "$HERE/$cell.jsonl" ] && { log "STOP: aux_test $cell output already exists"; exit 1; }
  "$TV" "$GUARD" precheck --out "$HERE/gpu_precheck_$cell.json" >> "$LOG" 2>&1 || { log "STOP: aux_test $cell precheck failed (decision 55)"; exit 1; }
  log "aux_test $cell (Ollama GPU 2, decision 55 guard) start"
  "$TV" evaluate_vendor100.py --gold "$HERE/aux_test_gold.yaml" llm --model "$m" --reference-date 2026-09-25 \
      --condition-check --model-think auto --out "$HERE/$cell.json" > "$HERE/$cell.log" 2>&1 &
  pid=$!
  "$TV" "$GUARD" watch --pid $pid --rows "$HERE/$cell.jsonl" --model "$m" --out "$HERE/gpu_guard_$cell.json" \
      > "$HERE/gpu_guard_$cell.log" 2>&1
  grc=$?; wait $pid; rc=$?
  log "aux_test $cell exit=$rc guard=$grc"
  if [ $grc -ne 0 ]; then
    for f in "$HERE/$cell".*; do [ -e "$f" ] && mv "$f" "$HERE/ABORTED_gpu_$(basename "$f")"; done
    log "STOP: aux_test $cell aborted by decision 55 guard (outputs ABORTED_gpu_$cell.*)"; exit 1
  fi
  [ $rc -eq 0 ] || { log "STOP: aux_test $cell failed"; exit 1; }
  for _ in $(seq 120); do [ "$(curl -s localhost:11434/api/ps)" = '{"models":[]}' ] && break; sleep 5; done
done
log "aux_test baselines done"
