#!/usr/bin/env bash
# 결정 12 확인: pipeline_pilot_001과 같은 데이터·순서·seed·설정으로 학습만 다시 돌리고 PYTORCH_CUDA_ALLOC_CONF만 켠다.
# - SFT: qwen3_8b_t2pc_thinking_pilot_sft.yaml 12 step. DPO: pipeline_pilot_001/resolved DPO config 8 step(reference 미리 계산,
#   pilot 본 학습과 같은 시작 adapter = pilot SFT checkpoint-4).
# - config 사본에서 output_dir·profiling.output만 임시 경로로 바꾼다(pilot checkpoint를 덮어쓰지 않음). 평가는 하지 않는다.
# - 끝나면 adapter·checkpoint를 지우고, log·profile·trainer_state·adapter sha256만 저장소에 남긴다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
WORK=/home/hwkim/sftdpo_work/pilot_prep_002_memcheck
GPU2=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21
PILOT=$REPO/sft_dpo_inventory/pipeline_pilot_001
export CUDA_VISIBLE_DEVICES=2 HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
       TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd "$REPO"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
die() { log "STOP: $1"; exit 1; }
[ -e "$WORK" ] && die "$WORK already exists"
mkdir -p "$WORK/logs" "$WORK/configs"
{
  echo "## $(date -Is) host"; nvidia-smi -L
  echo "## ollama container nvidia-smi -L"; docker exec ollama nvidia-smi -L 2>&1
  echo "## DeviceRequests"; docker inspect ollama --format '{{json .HostConfig.DeviceRequests}}'
  echo "## torch CUDA_VISIBLE_DEVICES=2"
  "$PY" -c "import torch; p=torch.cuda.get_device_properties(0); print('uuid GPU-'+str(p.uuid), p.name, 'pci', hex(p.pci_bus_id))"
  echo "## GPU2 used / processes"
  nvidia-smi -i $GPU2 --query-gpu=uuid,memory.used --format=csv,noheader
  nvidia-smi -i $GPU2 --query-compute-apps=pid,used_memory --format=csv,noheader
  echo "## PYTORCH_CUDA_ALLOC_CONF=$PYTORCH_CUDA_ALLOC_CONF"
} >> "$HERE/gpu_check.txt" 2>&1
"$PY" -c "import torch,sys; sys.exit(0 if 'GPU-'+str(torch.cuda.get_device_properties(0).uuid)=='$GPU2' else 1)" || die "not GPU 2"

sed -e "s#output_dir: /home/hwkim/sftdpo_work/pipeline_pilot_001/checkpoints/sft#output_dir: $WORK/checkpoints/sft#" \
    -e "s#output: /home/hwkim/sftdpo_work/pipeline_pilot_001/metrics/sft_profile.json#output: $WORK/metrics/sft_profile.json#" \
    training/configs/qwen3_8b_t2pc_thinking_pilot_sft.yaml > "$WORK/configs/sft.yaml"
sed -e "s#output_dir: /home/hwkim/sftdpo_work/pipeline_pilot_001/checkpoints/dpo#output_dir: $WORK/checkpoints/dpo#" \
    -e "s#output: /home/hwkim/sftdpo_work/pipeline_pilot_001/metrics/dpo_profile.json#output: $WORK/metrics/dpo_profile.json#" \
    "$PILOT/resolved/qwen3_8b_t2pc_thinking_pilot_dpo.resolved.yaml" > "$WORK/configs/dpo.yaml"
diff training/configs/qwen3_8b_t2pc_thinking_pilot_sft.yaml "$WORK/configs/sft.yaml" > "$HERE/config_diff_sft.txt"
diff "$PILOT/resolved/qwen3_8b_t2pc_thinking_pilot_dpo.resolved.yaml" "$WORK/configs/dpo.yaml" > "$HERE/config_diff_dpo.txt"

for stage in sft dpo; do
  log "$stage train start"
  nvidia-smi -i $GPU2 --query-gpu=memory.used --format=csv,noheader,nounits -lms 500 > "$HERE/${stage}_nvidia_smi.txt" 2>&1 & S=$!
  "$PY" -m training.train_$stage --config "$WORK/configs/$stage.yaml" > "$HERE/$stage.log" 2>&1
  rc=$?; kill $S; wait $S 2>/dev/null; log "$stage train exit=$rc"; [ $rc -eq 0 ] || die "$stage failed"
  cp "$WORK/metrics/${stage}_profile.json" "$HERE/${stage}_profile.json"
  last=$(ls -d "$WORK"/checkpoints/$stage/checkpoint-* | sort -t- -k2 -n | tail -1)
  cp "$last/trainer_state.json" "$HERE/${stage}_trainer_state.json"
  (cd "$WORK/checkpoints/$stage" && find . -name adapter_model.safetensors | sort | xargs sha256sum) > "$HERE/${stage}_adapter_sha256.txt"
done
rm -rf "$WORK"; log "temporary checkpoints deleted: $([ -e "$WORK" ] && echo no || echo yes)"
log "done"
