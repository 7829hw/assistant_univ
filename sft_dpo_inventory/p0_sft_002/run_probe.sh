#!/usr/bin/env bash
# mechanism probe(PLAN.md 6절): R70-json → R70-full 최종 adapter를 diagnostic panel 56문항에. Base는 p0_sft_001 결과 재사용.
#   run_probe.sh full403   # gate 통과 때만: 두 arm을 403문항(4셋)에 진단용으로 잰다(PLAN.md 8절)
set -u
MODE=${1:-probe}
ROOT=/home/hwkim/assistant_univ
HERE=$ROOT/sft_dpo_inventory/p0_sft_002
PY=/data/hwkim/path_repeat_001/venv/py/bin/python
GUARD="$PY $ROOT/sft_dpo_inventory/path_repeat_001/cell_guard.py"
WORK=/data/hwkim/p0_sft_002
export HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
RAWDIR=$ROOT/training/generated/p0_sft_002/mechanism_raw
mkdir -p "$WORK/logs" "$HERE/mechanism_probe" "$HERE/full_eval" "$RAWDIR"
cd "$ROOT" || exit 1
log() { echo "$(date -Iseconds) $*" | tee -a "$HERE/runs.log"; }
cell() {  # name gold out raw adapter
  $GUARD precheck --path hf --out "$WORK/logs/pre_$1.json" >> "$WORK/logs/guard.log" 2>&1 || { log "precheck FAILED before $1"; exit 1; }
  log "$1 start"; local t0=$(date +%s)
  $PY "$ROOT/sft_dpo_inventory/p0_sft_001/eval_p0_hf.py" --gold "$2" --condition-check --record-env --adapter "$5" \
    --out "$3" --raw-out "$4" > "$WORK/logs/$1.log" 2>&1 &
  local pid=$!; wait $pid; local rc=$?
  log "$1 finished rc=$rc elapsed_s=$(( $(date +%s) - t0 )) $(tail -1 "$WORK/logs/$1.log" | cut -c1-160)"
  [ "$rc" -eq 0 ] || { log "ABORT: $1"; exit 2; }
}
if [ "$MODE" = probe ]; then
  for arm in json full; do
    cell probe_r70_$arm "$HERE/diagnostic_panel_gold.yaml" "$HERE/mechanism_probe/r70_$arm.json" "$RAWDIR/probe_r70_$arm.jsonl" "$WORK/checkpoints/r70_$arm"
  done
  $PY "$HERE/analyze_probe.py" >> "$HERE/runs.log" 2>&1
else
  for arm in json full; do
    for set in sel154 valid98 vendor100 aux_test_v1; do
      case $set in
        sel154) gold=evaluation/partial_grounding/ab_p0_3/sel154_gold.yaml ;;
        valid98) gold=sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml ;;
        vendor100) gold=evaluation/vendor100/gold.yaml ;;
        aux_test_v1) gold=sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml ;;
      esac
      mkdir -p "$HERE/full_eval/r70_$arm"
      cell full_r70_${arm}_$set "$gold" "$HERE/full_eval/r70_$arm/$set.json" "$RAWDIR/full_r70_${arm}_$set.jsonl" "$WORK/checkpoints/r70_$arm"
    done
  done
  $PY "$HERE/analyze_full.py" >> "$HERE/runs.log" 2>&1
fi
log "== $MODE done"
