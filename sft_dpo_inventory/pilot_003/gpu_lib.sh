# pilot_003 공통(결정 83, Y): GPU 0–3 확인. source해서 쓴다.
#   gpu_ok G LABEL   → host nvidia-smi로 UUID·메모리·다른 프로세스, torch UUID를 확인하고 gpu_check.txt에 남긴다. 쓸 수 있으면 0.
#   - 다른 프로세스가 있거나 메모리가 100 MiB 이상이면 쓰지 않는다.
#   - GPU 3: Ollama에 모델이 올라가 있으면(Ollama 측정·teacher 수집 중) HF를 돌리지 않는다.
P3=/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_003
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
declare -A UUID=([0]=GPU-2445b100-70d8-e384-3a24-0249eeefc64d [1]=GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555 \
                 [2]=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21 [3]=GPU-48f798cc-9437-50ac-d604-448bbad7b311)
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
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
  used=$(nvidia-smi -i ${UUID[$g]} --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')
  procs=$(nvidia-smi -i ${UUID[$g]} --query-compute-apps=pid --format=csv,noheader | wc -l)
  loaded=$(curl -s localhost:11434/api/ps | "$PY" -c 'import json,sys; print(len(json.load(sys.stdin)["models"]))' 2>/dev/null || echo 1)
  if [ "$used" -ge 100 ] || [ "$procs" -ne 0 ]; then p3log "STOP: $label GPU $g busy used=${used}MiB procs=$procs"; return 1; fi
  if [ "$g" = 3 ] && [ "$loaded" != "0" ]; then p3log "STOP: $label GPU 3 has Ollama model loaded"; return 1; fi
  CUDA_VISIBLE_DEVICES=$g "$PY" -c "import torch,sys; sys.exit(0 if 'GPU-'+str(torch.cuda.get_device_properties(0).uuid)=='${UUID[$g]}' else 1)" \
    || { p3log "STOP: $label CUDA $g UUID mismatch"; return 1; }
  p3log "$label GPU $g ok used=${used}MiB procs=0 ollama_loaded=$loaded uuid=${UUID[$g]}"
  return 0
}
