#!/usr/bin/env bash
# p0_sft_004 실행 단계(PLAN.md 6–8절). 단계마다 따로 부르고, 끝나면 기록 commit·push 뒤 다음 단계를 부른다.
#   run_phase.sh train full154|json154
#   run_phase.sh smoke                      # base → full154 → json154, 학습 문항 18
#   run_phase.sh eval base|full154|json154  # sel154 → valid98 → vendor100 → aux_test_v1
#   run_phase.sh recall base|full154|json154  # 학습 문항 154
# HF만 쓰고 Ollama는 부르지 않는다. 기반 장애면 멈추고 runs.log에 남긴다. 결과를 보고 다시 돌리지 않는다.
set -u
STAGE=$1; ARG=${2:-}
ROOT=/home/hwkim/assistant_univ
HERE=$ROOT/sft_dpo_inventory/p0_sft_004
PY=/data/hwkim/path_repeat_001/venv/py/bin/python
GUARD="$PY $ROOT/sft_dpo_inventory/path_repeat_001/cell_guard.py"
WORK=/data/hwkim/p0_sft_004
export HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
       PYTHONDONTWRITEBYTECODE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
mkdir -p "$WORK/logs" "$WORK/metrics"
cd "$ROOT" || exit 1
log() { echo "$(date -Iseconds) $*" | tee -a "$HERE/runs.log"; }
gpu() { log "gpu: $(nvidia-smi --query-gpu=uuid,memory.used,utilization.gpu --format=csv,noheader) apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l) ollama_ps=$(curl -s localhost:11434/api/ps)"; }
precheck() {
  if ! $GUARD precheck --path hf --out "$WORK/logs/pre_$1.json" >> "$WORK/logs/guard.log" 2>&1; then
    log "precheck FAILED before $1: $(tail -1 "$WORK/logs/guard.log")"; exit 1
  fi
  log "precheck ok before $1"; gpu
}
adapter_of() { case $1 in base) echo "-";; *) echo "$WORK/checkpoints/$1";; esac; }

case $STAGE in
train)
  arm=$ARG; cfg=training/configs/qwen3_8b_p0_sft004_$arm.yaml
  [ -d "$WORK/checkpoints/$arm" ] && { log "ABORT: $WORK/checkpoints/$arm 이미 있음"; exit 2; }
  precheck "train_$arm"
  log "train $arm start config=$cfg sha256=$(sha256sum $cfg | cut -c1-16)"
  t0=$(date +%s)
  $PY -m training.train_sft --config "$cfg" > "$WORK/logs/train_$arm.log" 2>&1; rc=$?
  log "train $arm finished rc=$rc elapsed_s=$(( $(date +%s) - t0 ))"
  [ "$rc" -eq 0 ] || exit 3
  out=$WORK/checkpoints/$arm; mkdir -p "$HERE/training/$arm"
  last=$(ls -d "$out"/checkpoint-* | sort -t- -k2 -n | tail -1)
  cp "$out/training_provenance.json" "$HERE/training/$arm/" 2>/dev/null
  cp "$last/trainer_state.json" "$HERE/training/$arm/trainer_state.json"
  cp "$WORK/logs/train_$arm.log" "$HERE/training/$arm/train.log"
  cp "$WORK/metrics/${arm}_sft_profile.json" "$HERE/training/$arm/profile.json" 2>/dev/null
  (cd "$out" && ls -d checkpoint-* && sha256sum adapter_model.safetensors */adapter_model.safetensors) > "$HERE/training/$arm/checkpoints.txt"
  sleep 10; gpu; echo "STAGE_DONE train $arm" ;;
smoke)
  mkdir -p "$HERE/smoke"
  for m in base full154 json154; do
    precheck "smoke_$m"; t0=$(date +%s)
    $PY "$HERE/recall.py" --model $m --items smoke --out "$HERE/smoke/$m.jsonl" > "$WORK/logs/smoke_$m.log" 2>&1; rc=$?
    log "smoke $m finished rc=$rc elapsed_s=$(( $(date +%s) - t0 ))"
    [ "$rc" -eq 0 ] || exit 4
  done
  $PY "$HERE/smoke_check.py" | tee -a "$HERE/runs.log"; rc=${PIPESTATUS[0]}
  echo "STAGE_DONE smoke rc=$rc"; exit $rc ;;
eval)
  m=$ARG; adapter=$(adapter_of $m); mkdir -p "$HERE/evaluation/$m" "$ROOT/training/generated/p0_sft_004/eval_raw"
  for set in sel154 valid98 vendor100 aux_test_v1; do
    case $set in
      sel154) gold=evaluation/partial_grounding/ab_p0_3/sel154_gold.yaml ;;
      valid98) gold=sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml ;;
      vendor100) gold=evaluation/vendor100/gold.yaml ;;
      aux_test_v1) gold=sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml ;;
    esac
    precheck "eval_${m}_$set"; t0=$(date +%s); extra=()
    [ "$adapter" != "-" ] && extra=(--adapter "$adapter")
    $PY sft_dpo_inventory/p0_sft_001/eval_p0_hf.py --gold "$gold" --condition-check --record-env "${extra[@]}" \
      --out "$HERE/evaluation/$m/$set.json" --raw-out "$ROOT/training/generated/p0_sft_004/eval_raw/${m}_$set.jsonl" \
      > "$WORK/logs/eval_${m}_$set.log" 2>&1; rc=$?
    log "eval $m $set finished rc=$rc elapsed_s=$(( $(date +%s) - t0 )) $(tail -1 "$WORK/logs/eval_${m}_$set.log" | cut -c1-200)"
    cp "$WORK/logs/eval_${m}_$set.log" "$HERE/evaluation/$m/$set.log"
    [ "$rc" -eq 0 ] || exit 5
  done
  echo "STAGE_DONE eval $m" ;;
recall)
  m=$ARG; mkdir -p "$HERE/train_recall"
  precheck "recall_$m"; t0=$(date +%s)
  $PY "$HERE/recall.py" --model $m --items all --out "$HERE/train_recall/$m.jsonl" > "$WORK/logs/recall_$m.log" 2>&1; rc=$?
  log "recall $m finished rc=$rc elapsed_s=$(( $(date +%s) - t0 ))"
  [ "$rc" -eq 0 ] || exit 6
  echo "STAGE_DONE recall $m" ;;
*) echo "unknown stage"; exit 9 ;;
esac
