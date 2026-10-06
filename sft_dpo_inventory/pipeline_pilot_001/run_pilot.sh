#!/usr/bin/env bash
# pipeline_pilot_001 본 실행(PLAN.md). GPU 2에서 순서대로: GPU 확인 → base valid → SFT 학습 → SFT checkpoint valid →
# SFT 선택 → DPO config 확정 → DPO 학습(reference 미리 계산) → DPO checkpoint valid → DPO 선택.
# 단계가 실패하면 거기서 멈추고 기록한다(다시 실행하거나 설정을 바꾸지 않는다). Ollama는 부르지 않는다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
WORK=/home/hwkim/sftdpo_work/pipeline_pilot_001
RAW=$REPO/training/generated/pipeline_pilot_001
GPU2=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21
export CUDA_VISIBLE_DEVICES=2 HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
       TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
mkdir -p "$HERE/valid" "$HERE/train_logs" "$HERE/resolved" "$RAW" "$WORK/logs"
cd "$REPO"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
die() { log "STOP: $1"; exit 1; }

gpu_check() {
  {
    echo "## $(date -Is) host"; nvidia-smi -L
    echo "## ollama container nvidia-smi -L"; docker exec ollama nvidia-smi -L 2>&1
    echo "## 대체 근거: DeviceRequests / container devices"
    docker inspect ollama --format '{{json .HostConfig.DeviceRequests}}'
    docker exec ollama sh -c 'ls /dev | grep nvidia' | tr '\n' ' '; echo
    echo "## torch CUDA_VISIBLE_DEVICES=2"
    "$PY" -c "import torch; p=torch.cuda.get_device_properties(0); print('uuid GPU-'+str(p.uuid), p.name, 'pci', hex(p.pci_bus_id))"
    echo "## GPU2 used / processes"
    nvidia-smi -i $GPU2 --query-gpu=uuid,memory.used --format=csv,noheader
    nvidia-smi -i $GPU2 --query-compute-apps=pid,used_memory --format=csv,noheader
  } >> "$HERE/gpu_check.txt" 2>&1
  "$PY" -c "import torch,sys; sys.exit(0 if 'GPU-'+str(torch.cuda.get_device_properties(0).uuid)=='$GPU2' else 1)" \
    || die "CUDA_VISIBLE_DEVICES=2 is not $GPU2"
}

# nvidia-smi로 GPU 2 사용 메모리를 0.5초마다 기록한다(학습 단계 peak).
sample_start() { nvidia-smi -i $GPU2 --query-gpu=memory.used --format=csv,noheader,nounits -lms 500 > "$1" 2>&1 & SAMPLER=$!; }
sample_stop() { kill "$SAMPLER" 2>/dev/null; wait "$SAMPLER" 2>/dev/null; }

evaluate() {   # label adapter
  log "valid $1 start"
  "$PY" "$HERE/eval_valid.py" --label "$1" --out "$HERE/valid/$1.json" --raw-out "$RAW/$1_raw.jsonl" \
      ${2:+--adapter "$2"} > "$HERE/valid/$1.log" 2>&1
  local rc=$?; log "valid $1 exit=$rc"; [ $rc -eq 0 ] || die "valid $1 failed"
}

log "pilot start"
gpu_check

# 1. base
evaluate base ""

# 2. SFT
log "sft train start"; sample_start "$WORK/logs/sft_nvidia_smi.txt"
"$PY" -m training.train_sft --config training/configs/qwen3_8b_t2pc_thinking_pilot_sft.yaml > "$HERE/train_logs/sft.log" 2>&1
rc=$?; sample_stop; log "sft train exit=$rc"; [ $rc -eq 0 ] || die "sft train failed"
cp "$WORK/logs/sft_nvidia_smi.txt" "$HERE/train_logs/"

# 3. SFT checkpoints
SFT_RESULTS=()
for ck in $(ls -d "$WORK"/checkpoints/sft/checkpoint-* | sort -t- -k2 -n); do
  step=${ck##*-}; evaluate "sft_step$step" "$ck"; SFT_RESULTS+=("$HERE/valid/sft_step$step.json")
done
"$PY" "$HERE/select_checkpoint.py" --stage sft --out "$HERE/selection_sft.json" "${SFT_RESULTS[@]}" >> "$HERE/runs.log" 2>&1 \
  || die "sft selection failed"
SFT_SELECTED=$("$PY" -c "import json; print(json.load(open('$HERE/selection_sft.json'))['selected']['adapter'])")
log "sft selected $SFT_SELECTED"

# 4. DPO config(선택한 SFT adapter로 확정)
sed "s#adapter_path: SELECTED_PIPELINE_PILOT_001_SFT_REQUIRED#adapter_path: $SFT_SELECTED#" \
  training/configs/qwen3_8b_t2pc_thinking_pilot_dpo.yaml > "$HERE/resolved/qwen3_8b_t2pc_thinking_pilot_dpo.resolved.yaml"
grep -q "adapter_path: $SFT_SELECTED" "$HERE/resolved/qwen3_8b_t2pc_thinking_pilot_dpo.resolved.yaml" || die "dpo config not resolved"

# 5. DPO
log "dpo train start"; sample_start "$WORK/logs/dpo_nvidia_smi.txt"
"$PY" -m training.train_dpo --config "$HERE/resolved/qwen3_8b_t2pc_thinking_pilot_dpo.resolved.yaml" > "$HERE/train_logs/dpo.log" 2>&1
rc=$?; sample_stop; log "dpo train exit=$rc"; [ $rc -eq 0 ] || die "dpo train failed"
cp "$WORK/logs/dpo_nvidia_smi.txt" "$HERE/train_logs/"

# 6. DPO checkpoints
DPO_RESULTS=()
for ck in $(ls -d "$WORK"/checkpoints/dpo/checkpoint-* | sort -t- -k2 -n); do
  step=${ck##*-}; evaluate "dpo_step$step" "$ck"; DPO_RESULTS+=("$HERE/valid/dpo_step$step.json")
done
"$PY" "$HERE/select_checkpoint.py" --stage dpo --out "$HERE/selection_dpo.json" "${DPO_RESULTS[@]}" >> "$HERE/runs.log" 2>&1 \
  || die "dpo selection failed"
log "pilot done"
