#!/usr/bin/env bash
# p0_sft_001 intermediate checkpoint 진단(CHECKPOINT_DIAGNOSTIC_PLAN.md). 새 학습 없음. HF만, Ollama 호출 없음.
# 순서: gold_only 77 → 154 → 231 → 308 → clean_hybrid 77 → 154 → 231 → 308. 평가 조건은 p0_sft_001과 같다(eval_p0_hf.py 그대로).
set -u
ROOT=/home/hwkim/assistant_univ
HERE=$ROOT/sft_dpo_inventory/p0_sft_002
PY=/data/hwkim/path_repeat_001/venv/py/bin/python
GUARD="$PY $ROOT/sft_dpo_inventory/path_repeat_001/cell_guard.py"
WORK=/data/hwkim/p0_sft_002
export HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
mkdir -p "$WORK/logs" "$HERE/checkpoint_diag" "$ROOT/training/generated/p0_sft_002/checkpoint_diag_raw"
cd "$ROOT" || exit 1
log() { echo "$(date -Iseconds) $*" | tee -a "$HERE/runs.log"; }
log "== checkpoint diag start"
for arm in gold_only clean_hybrid; do
  for step in 77 154 231 308; do
    name=${arm}_ckpt$step
    if ! $GUARD precheck --path hf --out "$WORK/logs/pre_$name.json" >> "$WORK/logs/guard.log" 2>&1; then
      log "precheck FAILED before $name"; exit 1; fi
    log "diag $name start"
    t0=$(date +%s)
    $PY "$ROOT/sft_dpo_inventory/p0_sft_001/eval_p0_hf.py" --gold "$HERE/diagnostic_panel_gold.yaml" --condition-check --record-env \
      --adapter "/data/hwkim/p0_sft_001/checkpoints/$arm/checkpoint-$step" \
      --out "$HERE/checkpoint_diag/$name.json" --raw-out "$ROOT/training/generated/p0_sft_002/checkpoint_diag_raw/$name.jsonl" \
      > "$WORK/logs/$name.log" 2>&1 &
    pid=$!; wait $pid; rc=$?
    log "diag $name finished rc=$rc elapsed_s=$(( $(date +%s) - t0 )) $(tail -1 "$WORK/logs/$name.log" | cut -c1-160)"
    [ "$rc" -eq 0 ] || { log "ABORT: $name"; exit 2; }
  done
done
$PY "$HERE/analyze_checkpoints.py" >> "$HERE/runs.log" 2>&1
log "== checkpoint diag done"
