#!/usr/bin/env bash
# ab_p0 Ollama 셀 하나(PLAN.md 2절): precheck → 실행 → watch → keep_alive 대기 → postcheck.
#
#   run_cell.sh DIR NAME full|p0 [harness 추가 인자...]
#
# 결과: DIR/NAME.{json,jsonl,spec.json,log,pre.json,guard.json,wait.json,post.json}. 시각과 판정은 runs.log에 덧붙인다.
# 셀 전환 확인은 path_repeat_001/cell_guard.py를 그대로 쓴다(결정 56·57).
set -u
ROOT=/home/hwkim/assistant_univ
HERE=$ROOT/evaluation/partial_grounding/ab_p0
PY=/data/hwkim/path_repeat_001/venv/py/bin/python
GUARD="$PY $ROOT/sft_dpo_inventory/path_repeat_001/cell_guard.py"
MIN_RATE=77.6
DIR=$HERE/$1; NAME=$2; ARM=$3; shift 3
case "$ARM" in
  full) PROMPT=() ;;
  p0) PROMPT=(--planner-prompt evaluation/partial_grounding/prompts/partial_p0.yaml) ;;
  *) echo "arm은 full 또는 p0" >&2; exit 64 ;;
esac
mkdir -p "$DIR"
OUT=$DIR/$NAME
log() { echo "$(date -Iseconds) $NAME $*" | tee -a "$HERE/runs.log"; }
cd "$ROOT" || exit 1

log "precheck start"
if ! $GUARD precheck --path ollama --out "$OUT.pre.json" >> "$OUT.log" 2>&1; then
  log "precheck FAILED: $(tail -1 "$OUT.log")"; exit 1
fi
START=$(date +%s)
$PY evaluate_vendor100.py --gold evaluation/vendor100/gold.yaml llm --model qwen3:8b \
  --reference-date 2026-09-25 --condition-check --model-think auto --record-env --out "$OUT.json" \
  "${PROMPT[@]}" "$@" >> "$OUT.log" 2>&1 &
PID=$!
log "launched pid=$PID arm=$ARM args=${PROMPT[*]} $*"
$GUARD watch --pid "$PID" --rows "$OUT.jsonl" --out "$OUT.guard.json" --min-rate "$MIN_RATE" >> "$OUT.log" 2>&1
GUARD_RC=$?
wait "$PID"; RC=$?
log "finished rc=$RC guard_rc=$GUARD_RC elapsed_s=$(( $(date +%s) - START ))"
if [ "$GUARD_RC" -ne 0 ]; then
  for f in "$OUT".json "$OUT".jsonl "$OUT".spec.json "$OUT".guard.json; do
    [ -e "$f" ] && mv "$f" "$DIR/ABORTED_$(basename "$f")"
  done
  log "ABORTED by guard (rc=$GUARD_RC)"
fi
$GUARD wait-empty --out "$OUT.wait.json" >> "$OUT.log" 2>&1 || log "wait-empty FAILED"
$GUARD precheck --path ollama --out "$OUT.post.json" >> "$OUT.log" 2>&1
log "postcheck: $(tail -1 "$OUT.log")"
[ "$RC" -eq 0 ] && [ "$GUARD_RC" -eq 0 ] || exit 2
log "done"
