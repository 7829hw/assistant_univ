#!/usr/bin/env bash
# p0_sft_001 재개(PLAN_DEVIATIONS.md 1번). run_all.sh와 같은 함수·명세로, 끝난 base 4셀과 두 학습은 건너뛴다.
# 원래: p0_sft_001 전체 실행(PLAN.md 5·6절 순서, 결과를 보기 전에 고정). HF만 쓰고 Ollama는 부르지 않는다.
#   1. 학습: gold_only → GPU 빈 상태 확인 → clean_hybrid
#   2. 평가(P0 prompt d7f4c12a, greedy, thinking 켬): base → gold_only → clean_hybrid, 셋마다 sel154 → valid98 → vendor100 → aux_test_v1
#      학습 모델은 고정 checkpoint(2 epoch 끝, output_dir의 최종 adapter)만 잰다.
# 기반 장애(crash·OOM·NaN)면 그 단계에서 멈추고 runs.log에 남긴다. 결과를 보고 다시 돌리지 않는다.
set -u
ROOT=/home/hwkim/assistant_univ
HERE=$ROOT/sft_dpo_inventory/p0_sft_001
PY=/data/hwkim/path_repeat_001/venv/py/bin/python
GUARD="$PY $ROOT/sft_dpo_inventory/path_repeat_001/cell_guard.py"
WORK=/data/hwkim/p0_sft_001
export HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
       PYTHONDONTWRITEBYTECODE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
mkdir -p "$WORK/logs" "$WORK/metrics" "$HERE/training" "$HERE/evaluation"
cd "$ROOT" || exit 1
log() { echo "$(date -Iseconds) $*" | tee -a "$HERE/runs.log"; }
gpu() { log "gpu: $(nvidia-smi --query-gpu=uuid,memory.used,utilization.gpu --format=csv,noheader) apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l)"; }
precheck() {
  if ! $GUARD precheck --path hf --out "$WORK/logs/pre_$1.json" >> "$WORK/logs/guard.log" 2>&1; then
    log "precheck FAILED before $1: $(tail -1 "$WORK/logs/guard.log")"; exit 1
  fi
  log "precheck ok before $1: $(tail -1 "$WORK/logs/guard.log")"
}

train() {   # $1 = arm
  local arm=$1 cfg=training/configs/qwen3_8b_p0_sft001_$1.yaml
  precheck "train_$arm"; gpu
  log "train $arm start config=$cfg sha256=$(sha256sum "$cfg" | cut -c1-16)"
  local t0=$(date +%s)
  $PY -m training.train_sft --config "$cfg" > "$WORK/logs/train_$arm.log" 2>&1 &
  local pid=$!; wait $pid; local rc=$?
  log "train $arm finished rc=$rc elapsed_s=$(( $(date +%s) - t0 ))"
  [ "$rc" -eq 0 ] || { log "ABORT: train $arm failed"; exit 2; }
  mkdir -p "$HERE/training/$arm"
  local out=$WORK/checkpoints/$arm
  cp "$out/training_provenance.json" "$HERE/training/$arm/" 2>/dev/null
  last=$(ls -d "$out"/checkpoint-* | sort -t- -k2 -n | tail -1)
  cp "$last/trainer_state.json" "$HERE/training/$arm/trainer_state.json"
  cp "$WORK/logs/train_$arm.log" "$HERE/training/$arm/train.log"
  cp "$WORK/metrics/${arm}_sft_profile.json" "$HERE/training/$arm/profile.json" 2>/dev/null
  (cd "$out" && ls -d checkpoint-* && sha256sum adapter_model.safetensors */adapter_model.safetensors) > "$HERE/training/$arm/checkpoints.txt"
  sleep 10; gpu
}

evaluate() {   # $1 = model label, $2 = adapter path or "-"
  local model=$1 adapter=$2
  mkdir -p "$HERE/evaluation/$model" "$ROOT/training/generated/p0_sft_001/eval_raw"
  for set in sel154 valid98 vendor100 aux_test_v1; do
    case $set in
      sel154) gold=evaluation/partial_grounding/ab_p0_3/sel154_gold.yaml ;;
      valid98) gold=sft_dpo_inventory/pilot_001_analysis/decision43/valid98_gold.yaml ;;
      vendor100) gold=evaluation/vendor100/gold.yaml ;;
      aux_test_v1) gold=sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml ;;
    esac
    precheck "eval_${model}_$set"
    log "eval $model $set start adapter=$adapter"
    local t0=$(date +%s) extra=()
    [ "$adapter" != "-" ] && extra=(--adapter "$adapter")
    $PY "$HERE/eval_p0_hf.py" --gold "$gold" --condition-check --record-env "${extra[@]}" \
      --out "$HERE/evaluation/$model/$set.json" \
      --raw-out "$ROOT/training/generated/p0_sft_001/eval_raw/${model}_$set.jsonl" > "$WORK/logs/eval_${model}_$set.log" 2>&1 &
    local pid=$!; wait $pid; local rc=$?
    log "eval $model $set finished rc=$rc elapsed_s=$(( $(date +%s) - t0 )) $(tail -1 "$WORK/logs/eval_${model}_$set.log" | cut -c1-200)"
    cp "$WORK/logs/eval_${model}_$set.log" "$HERE/evaluation/$model/$set.log"
    [ "$rc" -eq 0 ] || { log "ABORT: eval $model $set failed"; exit 3; }
  done
}

log "== p0_sft_001 resume start (from gold_only sel154)"
evaluate gold_only "$WORK/checkpoints/gold_only"
evaluate clean_hybrid "$WORK/checkpoints/clean_hybrid"
$PY "$HERE/analyze.py" >> "$HERE/runs.log" 2>&1
log "== p0_sft_001 run_all done"
echo RUN_ALL_DONE
