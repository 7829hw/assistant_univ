#!/usr/bin/env bash
# 공식 방식 Q4 진단 모델(결정 75)의 렌더링 확인(결정 31)과 selection_v1 sampling 셀(calibration_001 PLAN과 같은 설정).
#   bash run_qr.sh render LABEL=MODEL ...   # 렌더링 확인(render/LABEL.json), 결정 55 확인을 붙인다
#   bash run_qr.sh cell LABEL MODEL         # k=4 셀: calibration_001/run_cal.sh를 OUT_DIR=이 폴더로 부른다(셀 끝에 커밋·push)
# 컨테이너는 건드리지 않는다. Ollama 측정 중 다른 Ollama 호출이나 GPU 3의 HF 작업을 하지 않는다. 출력이 있으면 멈춘다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
GUARD=$REPO/sft_dpo_inventory/pilot_002/ollama_gpu_guard.py
RENDER=$REPO/sft_dpo_inventory/pilot_002/ollama/render_check.py
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
cd "$REPO"; mkdir -p "$HERE/render"
LOG=$HERE/runs.log
log() { echo "== $1 $(date -Is)" >> "$LOG"; }
die() { log "STOP: $1"; exit 1; }
ollama_idle() { for _ in $(seq 120); do [ "$(curl -s localhost:11434/api/ps)" = '{"models":[]}' ] && return 0; sleep 5; done; return 1; }
mode=$1; shift
case $mode in
  render)
    for pair in "$@"; do
      label=${pair%%=*}; model=${pair#*=}; p=$HERE/render/$label
      [ -e "$p.json" ] && die "$p.json already exists"
      ollama_idle || die "Ollama model still loaded before render $label"
      "$TV" "$GUARD" precheck --out "${p}_gpu_precheck.json" >> "$LOG" 2>&1 || die "render $label precheck failed (decision 55)"
      log "render $label start ($model)"
      "$PY" "$RENDER" --model "$model" --out "$p.json" > "$p.log" 2>&1 &
      pid=$!
      "$TV" "$GUARD" watch --pid $pid --rows "$p.log" --model "$model" --out "${p}_gpu_guard.json" > "${p}_gpu_guard.log" 2>&1
      grc=$?; wait $pid; rc=$?
      log "render $label exit=$rc guard=$grc"
      if [ $grc -ne 0 ]; then
        for f in "$p".* "${p}_"*; do [ -e "$f" ] && mv "$f" "$(dirname "$f")/ABORTED_gpu_$(basename "$f")"; done
        die "render $label aborted by decision 55 guard"
      fi
      [ $rc -eq 0 ] || die "render $label failed rc=$rc"
    done ;;
  cell)
    OUT_DIR=$HERE RAW_DIR=$REPO/training/generated/quant_recipe/raw TAG=quant_recipe \
      bash "$REPO/sft_dpo_inventory/calibration_001/run_cal.sh" ollama "$1" "$2" ;;
  *) die "unknown mode $mode" ;;
esac
