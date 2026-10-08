#!/usr/bin/env bash
# path_repeat_001 셀 하나를 PLAN.md 4·5절 순서로 돈다(사전 확인 → 실행 → 감시 → keep_alive 대기 → 사후 확인).
#
#   run_cell.sh DIR NAME ollama|hf MIN_RATE [harness 추가 인자...]
#     DIR: runs 또는 smoke. NAME: 결과 이름(예: ollama_greedy, hf_sample_r1). MIN_RATE: Ollama 문항별 속도 하한(hf는 -)
#
# 결과: DIR/NAME.{json,log,pre.json,guard.json,wait.json,post.json}(Ollama는 .jsonl·.spec.json도),
#       HF 원문은 training/generated/path_repeat_001/NAME_raw.jsonl. 시각과 판정은 runs.log에 덧붙인다.
set -u
ROOT=/home/hwkim/assistant_univ
HERE=$ROOT/sft_dpo_inventory/path_repeat_001
PY=/data/hwkim/path_repeat_001/venv/py/bin/python
DIR=$HERE/$1; NAME=$2; KIND=$3; MIN_RATE=$4; shift 4
mkdir -p "$DIR" "$ROOT/training/generated/path_repeat_001"
OUT=$DIR/$NAME
GUARD="$PY $HERE/cell_guard.py"
log() { echo "$(date -Iseconds) $NAME $*" | tee -a "$HERE/runs.log"; }
cd "$ROOT" || exit 1

log "precheck($KIND) start"
if ! $GUARD precheck --path "$KIND" --out "$OUT.pre.json" >> "$OUT.log" 2>&1; then
  log "precheck FAILED: $(tail -1 "$OUT.log")"; exit 1
fi
log "precheck ok: $(tail -1 "$OUT.log")"

START=$(date +%s)
if [ "$KIND" = ollama ]; then
  $PY evaluate_vendor100.py --gold evaluation/vendor100/gold.yaml llm --model qwen3:8b \
    --reference-date 2026-09-25 --condition-check --model-think auto --record-env --out "$OUT.json" "$@" \
    >> "$OUT.log" 2>&1 &
  PID=$!
  log "launched pid=$PID args=$*"
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
  log "ollama empty: $(tail -1 "$OUT.log")"
  $GUARD precheck --path hf --out "$OUT.post.json" >> "$OUT.log" 2>&1
  log "postcheck(next=hf): $(tail -1 "$OUT.log")"
  [ "$RC" -eq 0 ] && [ "$GUARD_RC" -eq 0 ] || exit 2
else
  HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 \
    $PY sft_dpo_inventory/thinking_prep_001/hf_eval_thinking.py --condition-check --record-env \
    --out "$OUT.json" --raw-out "$ROOT/training/generated/path_repeat_001/${NAME}_raw.jsonl" "$@" \
    >> "$OUT.log" 2>&1 &
  PID=$!
  log "launched pid=$PID args=$*"
  wait "$PID"; RC=$?
  log "finished rc=$RC elapsed_s=$(( $(date +%s) - START ))"
  sleep 5
  $GUARD precheck --path ollama --out "$OUT.post.json" >> "$OUT.log" 2>&1
  log "postcheck(next=ollama): $(tail -1 "$OUT.log")"
  [ "$RC" -eq 0 ] || exit 2
fi
log "done"
