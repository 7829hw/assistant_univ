#!/usr/bin/env bash
# Ollama multi-cell 상주 실행(결정 62, 2026-10-12). 실험의 run_all.sh가 source해서 쓴다.
#
#   HERE=<실험 디렉터리> GOLD=<문항 파일(저장소 기준)> MIN_RATE=<tok/s> [CELL_GUARD_OLLAMA_VERSION=..]
#   source sft_dpo_inventory/path_repeat_001/resident_lib.sh
#   resident_begin                                   # GPU 빈 상태 확인 → warm-up(판정 무관) → 상주 감시 시작
#   resident_cell raw full_greedy [harness llm 인자...]   # 셀마다(precheck --resident → 측정 → watch → postcheck)
#   resident_end                                     # 상주 감시 종료와 요약(unload·reload·컨테이너 재시작 0이어야 함)
#
# - 모델은 warm-up에서 한 번 올리고 run이 끝날 때까지 내리지 않는다. 셀 사이에 wait-empty·unload·keep_alive=0·컨테이너 조작이 없다.
# - harness는 --model-state resident로 부른다(시작할 때도, 문항 사이에도 모델을 내리지 않는다).
# - 모든 arm이 같은 상주 모델 instance를 쓴다. arm 사이 reload가 생기면 residency 기록에 남고 resident_end가 실패한다.
# - 셀 하나가 실패하면 호출한 run_all.sh가 멈춘다(다시 돌리지 않는다). 결과 기록: $HERE/runs.log, $HERE/resident/.
set -u
ROOT=${ROOT:-/home/hwkim/assistant_univ}
PY=${PY:-/data/hwkim/path_repeat_001/venv/py/bin/python}
GUARD="$PY $ROOT/sft_dpo_inventory/path_repeat_001/cell_guard.py"

_rlog() { echo "$(date -Iseconds) $*" | tee -a "$HERE/runs.log"; }

resident_begin() {
  mkdir -p "$HERE/resident"
  cd "$ROOT" || return 1
  _rlog "resident begin"
  if ! $GUARD precheck --path ollama --out "$HERE/resident/begin.pre.json" >> "$HERE/resident/resident.log" 2>&1; then
    _rlog "resident begin precheck FAILED: $(tail -1 "$HERE/resident/resident.log")"; return 1
  fi
  if ! $GUARD warmup --out "$HERE/resident/warmup.json" --min-rate "$MIN_RATE" >> "$HERE/resident/resident.log" 2>&1; then
    _rlog "resident warmup FAILED: $(tail -1 "$HERE/resident/resident.log")"; return 1
  fi
  _rlog "resident warmup ok: $(tail -1 "$HERE/resident/resident.log")"
  sleep infinity &
  RESIDENT_KEEP_PID=$!
  # run_all.sh가 셀 실패로 중간에 끝나도 감시를 닫아 residency 기록을 남긴다.
  trap 'kill "$RESIDENT_KEEP_PID" 2>/dev/null' EXIT
  $GUARD residency --pid "$RESIDENT_KEEP_PID" --out "$HERE/resident/residency.json" >> "$HERE/resident/resident.log" 2>&1 &
  RESIDENT_MON_PID=$!
  export RESIDENT_KEEP_PID RESIDENT_MON_PID
}

resident_cell() {
  local DIR=$HERE/$1 NAME=$2; shift 2
  mkdir -p "$DIR"
  local OUT=$DIR/$NAME
  cd "$ROOT" || return 1
  _rlog "$NAME precheck start (resident)"
  if ! $GUARD precheck --path ollama --resident --out "$OUT.pre.json" >> "$OUT.log" 2>&1; then
    _rlog "$NAME precheck FAILED: $(tail -1 "$OUT.log")"; return 1
  fi
  local START; START=$(date +%s)
  $PY evaluate_vendor100.py --gold "$GOLD" llm --model qwen3:8b --model-state resident \
    --reference-date 2026-09-25 --condition-check --model-think auto --record-env --out "$OUT.json" \
    "$@" >> "$OUT.log" 2>&1 &
  local PID=$!
  _rlog "$NAME launched pid=$PID args=$*"
  $GUARD watch --pid "$PID" --rows "$OUT.jsonl" --out "$OUT.guard.json" --min-rate "$MIN_RATE" >> "$OUT.log" 2>&1
  local GUARD_RC=$?
  wait "$PID"; local RC=$?
  _rlog "$NAME finished rc=$RC guard_rc=$GUARD_RC elapsed_s=$(( $(date +%s) - START ))"
  if [ "$GUARD_RC" -ne 0 ]; then
    for f in "$OUT".json "$OUT".jsonl "$OUT".spec.json "$OUT".guard.json; do
      [ -e "$f" ] && mv "$f" "$DIR/ABORTED_$(basename "$f")"
    done
    _rlog "$NAME ABORTED by guard (rc=$GUARD_RC)"
  fi
  $GUARD precheck --path ollama --resident --out "$OUT.post.json" >> "$OUT.log" 2>&1
  _rlog "$NAME postcheck: $(tail -1 "$OUT.log")"
  [ "$RC" -eq 0 ] && [ "$GUARD_RC" -eq 0 ] || return 2
  _rlog "$NAME done"
}

resident_end() {
  kill "$RESIDENT_KEEP_PID" 2>/dev/null
  wait "$RESIDENT_MON_PID"; local RC=$?
  _rlog "resident end rc=$RC: $(tail -1 "$HERE/resident/resident.log")"
  return "$RC"
}
