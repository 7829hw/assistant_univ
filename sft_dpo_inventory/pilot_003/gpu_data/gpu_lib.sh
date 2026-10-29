# pilot_003 공통(결정 83, Y; 결정 84): 있는 GPU 전부 확인. source해서 쓴다.
#   gpu_ok G LABEL   → host nvidia-smi로 UUID·메모리·다른 프로세스, torch UUID를 확인하고 gpu_check.txt에 남긴다. 쓸 수 있으면 0.
#   - 다른 프로세스가 있거나 메모리가 100 MiB 이상이면 쓰지 않는다.
#   - Ollama GPU(UUID 48f798cc…): Ollama에 모델이 올라가 있으면(Ollama 측정·teacher 수집 중) HF를 돌리지 않는다.
P3=/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_003
PY=/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python
# 2026-10-13 15:45 재부팅 뒤 GPU a644de12가 빠졌다(결정 84). 번호는 바뀔 수 있으므로 host nvidia-smi에서 번호 → UUID를 매번 만든다.
# Ollama GPU는 번호가 아니라 UUID(48f798cc…)로 정한다.
OLLAMA_UUID=GPU-48f798cc-9437-50ac-d604-448bbad7b311
declare -A UUID=()
while IFS=', ' read -r i u; do UUID[$i]=$u; done < <(nvidia-smi --query-gpu=index,uuid --format=csv,noheader)
GPUS=$(nvidia-smi --query-gpu=index --format=csv,noheader | tr '\n' ' ')
export HF_HOME=/data/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
p3log() { echo "== $1 $(date -Is)" >> "$P3/runs.log"; }
gpu_ok() {
  local g=$1 label=$2 used procs loaded
  {
    echo "## $(date -Is) $label (GPU $g)"
    nvidia-smi --query-gpu=index,uuid,pstate,memory.used --format=csv,noheader
    nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader
    echo "## ollama ps"; curl -s localhost:11434/api/ps; echo
  } >> "$P3/gpu_check.txt" 2>&1
  [ -n "${UUID[$g]:-}" ] || { p3log "unavailable: $label GPU $g not present"; return 1; }
  used=$(nvidia-smi -i ${UUID[$g]} --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')
  procs=$(nvidia-smi -i ${UUID[$g]} --query-compute-apps=pid --format=csv,noheader | wc -l)
  if docker inspect -f '{{.State.Running}}' ollama 2>/dev/null | grep -q true; then
    loaded=$(curl -s localhost:11434/api/ps | "$PY" -c 'import json,sys; print(len(json.load(sys.stdin)["models"]))' 2>/dev/null || echo 1)
  else loaded=server_down; fi
  if [ "$used" -ge 100 ] || [ "$procs" -ne 0 ]; then p3log "unavailable: $label GPU $g busy used=${used}MiB procs=$procs"; return 1; fi
  if [ "${UUID[$g]}" = "$OLLAMA_UUID" ] && [ "$loaded" != "0" ] && [ "$loaded" != server_down ]; then p3log "unavailable: $label GPU $g (Ollama GPU) has Ollama model loaded"; return 1; fi
  CUDA_VISIBLE_DEVICES=$g "$PY" -c "import torch,sys; sys.exit(0 if 'GPU-'+str(torch.cuda.get_device_properties(0).uuid)=='${UUID[$g]}' else 1)" \
    || { p3log "STOP: $label CUDA $g UUID mismatch"; return 1; }
  p3log "$label GPU $g ok used=${used}MiB procs=0 ollama_loaded=$loaded uuid=${UUID[$g]}"
  return 0
}
