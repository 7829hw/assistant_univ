#!/usr/bin/env bash
# P0 thinking trace HF 수집(결정 67). path_repeat_001 PLAN.md 4절의 HF 셀 시작 전 확인을 따른다(장비: GPU 1장을 HF·Ollama가 같이 쓴다).
#   - 시작 전: Ollama /api/ps 비어 있음, GPU compute 프로세스 없음, 메모리 기준선(cell_guard precheck --path hf).
#   - 수집 중 Ollama 호출 없음. 끝나면 사후 상태를 적는다.
#   run_traces_hf.sh [--resume]
set -u
ROOT=/home/hwkim/assistant_univ
HERE=$ROOT/evaluation/partial_grounding/sft_p0
SUM=$HERE/traces_hf
PY=/data/hwkim/path_repeat_001/venv/py/bin/python
GUARD="$PY $ROOT/sft_dpo_inventory/path_repeat_001/cell_guard.py"
mkdir -p "$SUM"
log() { echo "$(date -Iseconds) p0_traces_hf $*" | tee -a "$SUM/runs.log"; }
cd "$ROOT" || exit 1
log "precheck(hf) start"
if ! $GUARD precheck --path hf --out "$SUM/pre$( [ "${1:-}" = --resume ] && echo _resume ).json" >> "$SUM/collect.log" 2>&1; then
  log "precheck FAILED: $(tail -1 "$SUM/collect.log")"; exit 1
fi
log "precheck ok: $(tail -1 "$SUM/collect.log")"
START=$(date +%s)
HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
  PYTHONDONTWRITEBYTECODE=1 \
  $PY "$HERE/collect_p0_traces_hf.py" "$@" >> "$SUM/collect.log" 2>&1 &
PID=$!
log "launched pid=$PID args=$*"
wait "$PID"; RC=$?
log "finished rc=$RC elapsed_s=$(( $(date +%s) - START ))"
sleep 5
$GUARD precheck --path hf --out "$SUM/post.json" >> "$SUM/collect.log" 2>&1
log "postcheck: $(tail -1 "$SUM/collect.log")"
[ "$RC" -eq 0 ] || exit 2
log "done"
