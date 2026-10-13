#!/usr/bin/env bash
# 격리 확인 실험(RUN_PLAN.md). A(unload_per_question) 두 셀 → 상주 블록(warm-up 1회, B·B'·C·C' greedy·sampling, 셀 사이 unload 없음).
# 한 셀이라도 실패하면 멈춘다(다시 돌리지 않는다).
set -u
export ROOT=/home/hwkim/assistant_univ
export HERE=$ROOT/evaluation/partial_grounding/resident_isolation
export GOLD=evaluation/partial_grounding/resident_isolation/items_gold.yaml
export MIN_RATE=77.6
export CELL_GUARD_OLLAMA_VERSION=0.40.3
PY=/data/hwkim/path_repeat_001/venv/py/bin/python
GUARD="$PY $ROOT/sft_dpo_inventory/path_repeat_001/cell_guard.py"
SAMPLING=(--temperature 0.6 --top-p 0.95 --top-k 20 --seed 20261013)
log() { echo "$(date -Iseconds) $*" | tee -a "$HERE/runs.log"; }
cd "$ROOT" || exit 1
mkdir -p "$HERE/raw"

unload_cell() {   # 기존 방식(ab_p0_3/run_cell.sh와 같은 절차)
  local NAME=$1; shift
  local OUT=$HERE/raw/$NAME
  log "$NAME precheck start (unload_per_question)"
  $GUARD precheck --path ollama --out "$OUT.pre.json" >> "$OUT.log" 2>&1 || { log "$NAME precheck FAILED: $(tail -1 "$OUT.log")"; return 1; }
  $PY evaluate_vendor100.py --gold "$GOLD" llm --model qwen3:8b --model-state unload_per_question \
    --reference-date 2026-09-25 --condition-check --model-think auto --record-env --record-thinking --out "$OUT.json" \
    "$@" >> "$OUT.log" 2>&1 &
  local PID=$!
  log "$NAME launched pid=$PID args=$*"
  $GUARD watch --pid "$PID" --rows "$OUT.jsonl" --out "$OUT.guard.json" --min-rate "$MIN_RATE" >> "$OUT.log" 2>&1
  local GUARD_RC=$?
  wait "$PID"; local RC=$?
  log "$NAME finished rc=$RC guard_rc=$GUARD_RC"
  $GUARD wait-empty --out "$OUT.wait.json" >> "$OUT.log" 2>&1 || log "$NAME wait-empty FAILED"
  [ "$RC" -eq 0 ] && [ "$GUARD_RC" -eq 0 ] || return 2
  log "$NAME done"
}

unload_cell A_greedy || exit 2
unload_cell A_sample "${SAMPLING[@]}" || exit 2

source "$ROOT/sft_dpo_inventory/path_repeat_001/resident_lib.sh"
resident_begin || exit 3
for spec in "B resident_isolated file" "Bp resident_isolated reverse" "C resident file" "Cp resident reverse"; do
  set -- $spec
  MODEL_STATE=$2 resident_cell raw "${1}_greedy" --record-thinking --order "$3" || exit 4
done
for spec in "B resident_isolated file" "Bp resident_isolated reverse" "C resident file" "Cp resident reverse"; do
  set -- $spec
  MODEL_STATE=$2 resident_cell raw "${1}_sample" --record-thinking --order "$3" "${SAMPLING[@]}" || exit 4
done
resident_end
log "ALL DONE rc=$?"
