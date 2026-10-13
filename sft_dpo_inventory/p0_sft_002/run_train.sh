#!/usr/bin/env bash
# R70 한 arm 학습(PLAN.md 5절). run_train.sh json 다음 run_train.sh full 순서로 부른다(사이에 기록 commit·push).
set -u
ARM=$1
ROOT=/home/hwkim/assistant_univ
HERE=$ROOT/sft_dpo_inventory/p0_sft_002
PY=/data/hwkim/path_repeat_001/venv/py/bin/python
GUARD="$PY $ROOT/sft_dpo_inventory/path_repeat_001/cell_guard.py"
WORK=/data/hwkim/p0_sft_002
export HF_HOME=/data/hwkim/path_repeat_001/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
       PYTHONDONTWRITEBYTECODE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
mkdir -p "$WORK/logs" "$WORK/metrics" "$HERE/training/r70_$ARM"
cd "$ROOT" || exit 1
log() { echo "$(date -Iseconds) $*" | tee -a "$HERE/runs.log"; }
cfg=training/configs/qwen3_8b_p0_sft002_r70_$ARM.yaml
$GUARD precheck --path hf --out "$WORK/logs/pre_train_r70_$ARM.json" >> "$WORK/logs/guard.log" 2>&1 || { log "precheck FAILED before train r70_$ARM"; exit 1; }
log "precheck ok before train r70_$ARM; gpu $(nvidia-smi --query-gpu=uuid,memory.used --format=csv,noheader)"
log "train r70_$ARM start config=$cfg sha256=$(sha256sum $cfg | cut -c1-16)"
t0=$(date +%s)
$PY -m training.train_sft --config "$cfg" > "$WORK/logs/train_r70_$ARM.log" 2>&1 &
pid=$!; wait $pid; rc=$?
log "train r70_$ARM finished rc=$rc elapsed_s=$(( $(date +%s) - t0 ))"
[ "$rc" -eq 0 ] || exit 2
out=$WORK/checkpoints/r70_$ARM
last=$(ls -d "$out"/checkpoint-* | sort -t- -k2 -n | tail -1)
cp "$out/training_provenance.json" "$last/trainer_state.json" "$HERE/training/r70_$ARM/"
cp "$WORK/logs/train_r70_$ARM.log" "$HERE/training/r70_$ARM/train.log"
cp "$WORK/metrics/r70_${ARM}_sft_profile.json" "$HERE/training/r70_$ARM/profile.json" 2>/dev/null
(cd "$out" && ls -d checkpoint-* && sha256sum adapter_model.safetensors */adapter_model.safetensors) > "$HERE/training/r70_$ARM/checkpoints.txt"
sleep 10; log "gpu after r70_$ARM: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader) apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l)"
