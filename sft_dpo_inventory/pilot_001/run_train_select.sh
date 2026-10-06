#!/usr/bin/env bash
# pilot_001 학습과 checkpoint 선택(PLAN 2–4절). SFT 학습(GPU 2) → SFT checkpoint 4개 valid98(GPU 2·3 병렬) → 선택 →
# DPO config 확정 → DPO 학습(GPU 2) → DPO checkpoint 4개 valid98 → 선택. 단계가 실패하면 멈추고 기록한다(재실행 없음).
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
WORK=/home/hwkim/sftdpo_work/pilot_001
RAW=$REPO/training/generated/pilot_001
GPU2=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21
GPU3=GPU-48f798cc-9437-50ac-d604-448bbad7b311
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
       PYTHONDONTWRITEBYTECODE=1
mkdir -p "$HERE/valid98/runs" "$HERE/train_logs" "$HERE/resolved" "$RAW" "$WORK/logs"
cd "$REPO"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
die() { log "STOP: $1"; exit 1; }

gpu_check() {
  {
    echo "## $(date -Is) host"; nvidia-smi -L
    echo "## ollama container"; docker exec ollama nvidia-smi -L 2>&1
    echo "## torch CUDA 2"; CUDA_VISIBLE_DEVICES=2 "$PY" -c "import torch; p=torch.cuda.get_device_properties(0); print('GPU-'+str(p.uuid), hex(p.pci_bus_id))"
    echo "## torch CUDA 3"; CUDA_VISIBLE_DEVICES=3 "$PY" -c "import torch; p=torch.cuda.get_device_properties(0); print('GPU-'+str(p.uuid), hex(p.pci_bus_id))"
    echo "## used"; nvidia-smi --query-gpu=index,uuid,memory.used --format=csv,noheader
    nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory --format=csv,noheader
  } >> "$HERE/gpu_check.txt" 2>&1
  CUDA_VISIBLE_DEVICES=2 "$PY" -c "import torch,sys; sys.exit(0 if 'GPU-'+str(torch.cuda.get_device_properties(0).uuid)=='$GPU2' else 1)" || die "CUDA 2 is not $GPU2"
}

gpu3_free() {   # Ollama가 GPU 3을 쓰지 않을 때만 0
  local used procs loaded
  used=$(nvidia-smi -i $GPU3 --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')
  procs=$(nvidia-smi -i $GPU3 --query-compute-apps=pid --format=csv,noheader | wc -l)
  loaded=$(curl -s localhost:11434/api/ps | "$PY" -c 'import json,sys; print(len(json.load(sys.stdin)["models"]))' 2>/dev/null || echo 1)
  echo "   GPU3 check: used=${used}MiB procs=$procs ollama_loaded=$loaded" >> "$HERE/runs.log"
  [ "$used" -lt 100 ] && [ "$procs" -eq 0 ] && [ "$loaded" = "0" ]
}

evaluate() {   # label adapter cuda
  log "valid98 $1 start (CUDA $3)"
  CUDA_VISIBLE_DEVICES=$3 "$PY" "$HERE/valid98/eval_valid98.py" --label "$1" --out "$HERE/valid98/runs/$1.json" \
      --raw-out "$RAW/$1_raw.jsonl" --adapter "$2" > "$HERE/valid98/runs/$1.log" 2>&1
  local rc=$?; log "valid98 $1 exit=$rc"; return $rc
}

evaluate_all() {   # stage: checkpoints evaluated two at a time (GPU 2 + GPU 3 when free)
  local stage=$1; shift
  local cks=("$@") i=0
  while [ $i -lt ${#cks[@]} ]; do
    local a=${cks[$i]} b=${cks[$((i+1))]:-}
    local sa=${a##*-}
    if [ -n "$b" ] && gpu3_free; then
      local sb=${b##*-}
      evaluate "${stage}_step$sa" "$a" 2 & local p1=$!
      evaluate "${stage}_step$sb" "$b" 3 & local p2=$!
      wait $p1 || die "valid98 ${stage}_step$sa failed"; wait $p2 || die "valid98 ${stage}_step$sb failed"
      i=$((i+2))
    else
      evaluate "${stage}_step$sa" "$a" 2 || die "valid98 ${stage}_step$sa failed"
      i=$((i+1))
    fi
  done
}

train() {   # stage config
  log "$1 train start"
  nvidia-smi -i $GPU2 --query-gpu=memory.used --format=csv,noheader,nounits -lms 500 > "$HERE/train_logs/$1_nvidia_smi.txt" 2>&1 & local s=$!
  CUDA_VISIBLE_DEVICES=2 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$PY" -m training.train_$1 --config "$2" > "$HERE/train_logs/$1.log" 2>&1
  local rc=$?; kill $s; wait $s 2>/dev/null; log "$1 train exit=$rc"; [ $rc -eq 0 ] || die "$1 train failed"
  cp "$WORK/metrics/$1_profile.json" "$HERE/train_logs/"
}

log "pilot_001 train/select start"; gpu_check
[ -e "$WORK/checkpoints" ] && die "$WORK/checkpoints already exists"

train sft training/configs/qwen3_8b_t2pc_thinking_pilot001_sft.yaml
mapfile -t SFT_CK < <(ls -d "$WORK"/checkpoints/sft/checkpoint-* | sort -t- -k2 -n)
[ ${#SFT_CK[@]} -eq 4 ] || die "expected 4 SFT checkpoints, got ${#SFT_CK[@]}"
evaluate_all sft "${SFT_CK[@]}"
"$PY" sft_dpo_inventory/pipeline_pilot_001/select_checkpoint.py --stage sft --out "$HERE/selection_sft.json" \
    $(for c in "${SFT_CK[@]}"; do echo "$HERE/valid98/runs/sft_step${c##*-}.json"; done) >> "$HERE/runs.log" 2>&1 || die "sft selection failed"
SFT_SELECTED=$("$PY" -c "import json; print(json.load(open('$HERE/selection_sft.json'))['selected']['adapter'])")
log "sft selected $SFT_SELECTED"

sed "s#adapter_path: SELECTED_PILOT_001_SFT_REQUIRED#adapter_path: $SFT_SELECTED#" \
  training/configs/qwen3_8b_t2pc_thinking_pilot001_dpo.yaml > "$HERE/resolved/qwen3_8b_t2pc_thinking_pilot001_dpo.resolved.yaml"
grep -q "adapter_path: $SFT_SELECTED" "$HERE/resolved/qwen3_8b_t2pc_thinking_pilot001_dpo.resolved.yaml" || die "dpo config not resolved"

train dpo "$HERE/resolved/qwen3_8b_t2pc_thinking_pilot001_dpo.resolved.yaml"
mapfile -t DPO_CK < <(ls -d "$WORK"/checkpoints/dpo/checkpoint-* | sort -t- -k2 -n)
[ ${#DPO_CK[@]} -eq 4 ] || die "expected 4 DPO checkpoints, got ${#DPO_CK[@]}"
evaluate_all dpo "${DPO_CK[@]}"
"$PY" sft_dpo_inventory/pipeline_pilot_001/select_checkpoint.py --stage dpo --out "$HERE/selection_dpo.json" \
    $(for c in "${DPO_CK[@]}"; do echo "$HERE/valid98/runs/dpo_step${c##*-}.json"; done) >> "$HERE/runs.log" 2>&1 || die "dpo selection failed"
log "dpo selected $("$PY" -c "import json; print(json.load(open('$HERE/selection_dpo.json'))['selected']['adapter'])")"
log "pilot_001 train/select done"
