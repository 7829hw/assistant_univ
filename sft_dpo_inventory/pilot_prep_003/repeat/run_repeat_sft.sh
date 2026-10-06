#!/usr/bin/env bash
# 결정 17의 반복 측정: pipeline_pilot_001 본 학습과 같은 설정(기존 할당 설정 = PYTORCH_CUDA_ALLOC_CONF 없음)으로 SFT 12 step을
# 한 번 더 돌린다. 같은 데이터·순서·seed. config 사본에서 output_dir·profiling.output만 임시 경로로 바꾼다. 평가하지 않는다.
# 끝나면 checkpoint를 지우고 log·profile·trainer_state·adapter sha256만 남긴다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
WORK=/home/hwkim/sftdpo_work/pilot_prep_003_repeat
GPU2=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21
unset PYTORCH_CUDA_ALLOC_CONF
export CUDA_VISIBLE_DEVICES=2 HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
       TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
die() { log "STOP: $1"; exit 1; }
[ -e "$WORK" ] && die "$WORK already exists"
mkdir -p "$WORK/configs"
"$PY" -c "import torch,sys; sys.exit(0 if 'GPU-'+str(torch.cuda.get_device_properties(0).uuid)=='$GPU2' else 1)" || die "not GPU 2"
echo "GPU2 used before: $(nvidia-smi -i $GPU2 --query-gpu=memory.used --format=csv,noheader); PYTORCH_CUDA_ALLOC_CONF=${PYTORCH_CUDA_ALLOC_CONF:-unset}" >> "$HERE/runs.log"
sed -e "s#output_dir: /home/hwkim/sftdpo_work/pipeline_pilot_001/checkpoints/sft#output_dir: $WORK/checkpoints/sft#" \
    -e "s#output: /home/hwkim/sftdpo_work/pipeline_pilot_001/metrics/sft_profile.json#output: $WORK/metrics/sft_profile.json#" \
    training/configs/qwen3_8b_t2pc_thinking_pilot_sft.yaml > "$WORK/configs/sft.yaml"
diff training/configs/qwen3_8b_t2pc_thinking_pilot_sft.yaml "$WORK/configs/sft.yaml" > "$HERE/config_diff_sft.txt"
log "sft repeat start"
nvidia-smi -i $GPU2 --query-gpu=memory.used --format=csv,noheader,nounits -lms 500 > "$HERE/sft_nvidia_smi.txt" 2>&1 & S=$!
"$PY" -m training.train_sft --config "$WORK/configs/sft.yaml" > "$HERE/sft.log" 2>&1
rc=$?; kill $S; wait $S 2>/dev/null; log "sft repeat exit=$rc"; [ $rc -eq 0 ] || die "sft failed"
cp "$WORK/metrics/sft_profile.json" "$HERE/sft_profile.json"
cp "$(ls -d "$WORK"/checkpoints/sft/checkpoint-* | sort -t- -k2 -n | tail -1)/trainer_state.json" "$HERE/sft_trainer_state.json"
(cd "$WORK/checkpoints/sft" && find . -name adapter_model.safetensors | sort | xargs sha256sum) > "$HERE/sft_adapter_sha256.txt"
rm -rf "$WORK"; log "temporary checkpoints deleted: $([ -e "$WORK" ] && echo no || echo yes)"
log "done"
