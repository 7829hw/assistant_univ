#!/usr/bin/env bash
# pilot_002 학습과 checkpoint 선택(PLAN 2–4절, 결정 53). pilot_001/run_train_select.sh와 같은 흐름이고, 선택용 셋만 selection_v1이다.
# SFT 학습 → SFT checkpoint 4개 selection_v1 → 선택 → DPO config 확정 → DPO 학습 → DPO checkpoint 4개 selection_v1 → 선택
# → 고른 SFT·최종 valid98(보조, 결정 53). 단계가 실패하면 멈추고 기록한다(재실행 없음).
# GPU(CLAUDE.md 5·6번): 단계마다 host nvidia-smi로 확인한다. GPU 3에 다른 프로세스가 없으면 GPU 3, 있으면 Ollama 모델이 없는 GPU 2.
# 둘 다 안 되면 멈춘다. checkpoint 평가는 두 GPU가 모두 비어 있으면 둘에 나눠 돌린다(HF 출력은 두 장치에서 같다, 결정 43).
# 이 스크립트가 도는 동안 Ollama를 부르지 않는다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
WORK=/home/hwkim/sftdpo_work/pilot_002
RAW=$REPO/training/generated/pilot_002
declare -A UUID=([2]=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21 [3]=GPU-48f798cc-9437-50ac-d604-448bbad7b311)
SEL_ITEMS=$REPO/sft_dpo_inventory/pilot_prep_005/sets/selection_items.json
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
       PYTHONDONTWRITEBYTECODE=1
mkdir -p "$HERE/selection/runs" "$HERE/valid98" "$HERE/train_logs" "$HERE/resolved" "$RAW" "$WORK/logs"
cd "$REPO"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
die() { log "STOP: $1"; exit 1; }

gpu_record() {
  {
    echo "## $(date -Is) $1"; nvidia-smi -L
    echo "## ollama container"; docker exec ollama nvidia-smi -L 2>&1; curl -s localhost:11434/api/ps; echo
    for g in 2 3; do echo "## torch CUDA $g"; CUDA_VISIBLE_DEVICES=$g "$PY" -c "import torch; p=torch.cuda.get_device_properties(0); print('GPU-'+str(p.uuid))"; done
    echo "## used"; nvidia-smi --query-gpu=index,uuid,memory.used --format=csv,noheader
    nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader
  } >> "$HERE/gpu_check.txt" 2>&1
}

gpu_free() {   # g -> 0 if usable for HF work now
  local g=$1 used procs loaded
  used=$(nvidia-smi -i ${UUID[$g]} --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')
  procs=$(nvidia-smi -i ${UUID[$g]} --query-compute-apps=pid --format=csv,noheader | wc -l)
  loaded=$(curl -s localhost:11434/api/ps | "$PY" -c 'import json,sys; print(len(json.load(sys.stdin)["models"]))' 2>/dev/null || echo 1)
  echo "   GPU$g check: used=${used}MiB procs=$procs ollama_loaded=$loaded" >> "$HERE/runs.log"
  [ "$used" -lt 100 ] && [ "$procs" -eq 0 ] || return 1
  [ "$g" = 3 ] || [ "$loaded" = "0" ] || return 1
  CUDA_VISIBLE_DEVICES=$g "$PY" -c "import torch,sys; sys.exit(0 if 'GPU-'+str(torch.cuda.get_device_properties(0).uuid)=='${UUID[$g]}' else 1)"
}

pick_gpu() {   # prints 3 or 2; waits up to 60 s for transient processes, else empty
  for _ in $(seq 12); do
    if gpu_free 3; then echo 3; return; fi
    if gpu_free 2; then echo 2; return; fi
    sleep 5
  done
}

evaluate() {   # label adapter cuda items outdir
  log "eval $1 start (CUDA $3)"
  CUDA_VISIBLE_DEVICES=$3 "$PY" "$HERE/../pilot_prep_005/sets/eval_set.py" --items "$4" --label "$1" --out "$5/$1.json" \
      --raw-out "$RAW/$1_raw.jsonl" --adapter "$2" > "$5/$1.log" 2>&1
  local rc=$?; log "eval $1 exit=$rc"; return $rc
}

evaluate_all() {   # stage checkpoints...
  local stage=$1; shift
  local cks=("$@") i=0
  while [ $i -lt ${#cks[@]} ]; do
    local a=${cks[$i]} b=${cks[$((i+1))]:-}
    local sa=${a##*-}
    gpu_record "eval ${stage}_step$sa"
    if [ -n "$b" ] && gpu_free 3 && gpu_free 2; then
      local sb=${b##*-}
      evaluate "sel_${stage}_step$sa" "$a" 2 "$SEL_ITEMS" "$HERE/selection/runs" & local p1=$!
      evaluate "sel_${stage}_step$sb" "$b" 3 "$SEL_ITEMS" "$HERE/selection/runs" & local p2=$!
      wait $p1 || die "selection ${stage}_step$sa failed"; wait $p2 || die "selection ${stage}_step$sb failed"
      i=$((i+2))
    else
      local g; g=$(pick_gpu); [ -n "$g" ] || die "no usable GPU for ${stage}_step$sa"
      evaluate "sel_${stage}_step$sa" "$a" "$g" "$SEL_ITEMS" "$HERE/selection/runs" || die "selection ${stage}_step$sa failed"
      i=$((i+1))
    fi
  done
}

train() {   # stage config
  local g; gpu_record "train $1"; g=$(pick_gpu); [ -n "$g" ] || die "no usable GPU for $1 training"
  log "$1 train start (CUDA $g, ${UUID[$g]})"
  nvidia-smi -i ${UUID[$g]} --query-gpu=memory.used --format=csv,noheader,nounits -lms 500 > "$HERE/train_logs/$1_nvidia_smi.txt" 2>&1 & local s=$!
  CUDA_VISIBLE_DEVICES=$g PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$PY" -m training.train_$1 --config "$2" > "$HERE/train_logs/$1.log" 2>&1
  local rc=$?; kill $s; wait $s 2>/dev/null; log "$1 train exit=$rc (CUDA $g)"; [ $rc -eq 0 ] || die "$1 train failed"
  echo "$g ${UUID[$g]}" > "$HERE/train_logs/$1_gpu.txt"
  cp "$WORK/metrics/$1_profile.json" "$HERE/train_logs/"
  local last; last=$(ls -d "$WORK"/checkpoints/$1/checkpoint-* | sort -t- -k2 -n | tail -1)
  "$PY" -c "import json,sys; s=json.load(open(sys.argv[1])); json.dump(s['log_history'], open(sys.argv[2],'w'), indent=1)" \
      "$last/trainer_state.json" "$HERE/train_logs/$1_log_history.json"
}

log "pilot_002 train/select start"
[ -e "$WORK/checkpoints" ] && die "$WORK/checkpoints already exists"

train sft training/configs/qwen3_8b_t2pc_thinking_pilot002_sft.yaml
mapfile -t SFT_CK < <(ls -d "$WORK"/checkpoints/sft/checkpoint-* | sort -t- -k2 -n)
[ ${#SFT_CK[@]} -eq 4 ] || die "expected 4 SFT checkpoints, got ${#SFT_CK[@]}"
evaluate_all sft "${SFT_CK[@]}"
"$PY" sft_dpo_inventory/pipeline_pilot_001/select_checkpoint.py --stage sft --out "$HERE/selection_sft.json" \
    $(for c in "${SFT_CK[@]}"; do echo "$HERE/selection/runs/sel_sft_step${c##*-}.json"; done) >> "$HERE/runs.log" 2>&1 || die "sft selection failed"
SFT_SELECTED=$("$PY" -c "import json; print(json.load(open('$HERE/selection_sft.json'))['selected']['adapter'])")
log "sft selected $SFT_SELECTED"

sed "s#adapter_path: SELECTED_PILOT_002_SFT_REQUIRED#adapter_path: $SFT_SELECTED#" \
  training/configs/qwen3_8b_t2pc_thinking_pilot002_dpo.yaml > "$HERE/resolved/qwen3_8b_t2pc_thinking_pilot002_dpo.resolved.yaml"
grep -q "adapter_path: $SFT_SELECTED" "$HERE/resolved/qwen3_8b_t2pc_thinking_pilot002_dpo.resolved.yaml" || die "dpo config not resolved"

train dpo "$HERE/resolved/qwen3_8b_t2pc_thinking_pilot002_dpo.resolved.yaml"
mapfile -t DPO_CK < <(ls -d "$WORK"/checkpoints/dpo/checkpoint-* | sort -t- -k2 -n)
[ ${#DPO_CK[@]} -eq 4 ] || die "expected 4 DPO checkpoints, got ${#DPO_CK[@]}"
evaluate_all dpo "${DPO_CK[@]}"
"$PY" sft_dpo_inventory/pipeline_pilot_001/select_checkpoint.py --stage dpo --out "$HERE/selection_dpo.json" \
    $(for c in "${DPO_CK[@]}"; do echo "$HERE/selection/runs/sel_dpo_step${c##*-}.json"; done) >> "$HERE/runs.log" 2>&1 || die "dpo selection failed"
DPO_SELECTED=$("$PY" -c "import json; print(json.load(open('$HERE/selection_dpo.json'))['selected']['adapter'])")
log "dpo selected $DPO_SELECTED"

# 보조: 고른 SFT와 최종만 valid98(결정 41·53)
for pair in "sft:$SFT_SELECTED" "final:$DPO_SELECTED"; do
  name=${pair%%:*}; adapter=${pair#*:}
  gpu_record "valid98 $name"; g=$(pick_gpu); [ -n "$g" ] || die "no usable GPU for valid98 $name"
  log "valid98 $name start (CUDA $g)"
  CUDA_VISIBLE_DEVICES=$g "$PY" sft_dpo_inventory/pilot_001/valid98/eval_valid98.py --label "valid98_$name" \
      --out "$HERE/valid98/valid98_$name.json" --raw-out "$RAW/valid98_${name}_raw.jsonl" --adapter "$adapter" \
      > "$HERE/valid98/valid98_$name.log" 2>&1
  rc=$?; log "valid98 $name exit=$rc"; [ $rc -eq 0 ] || die "valid98 $name failed"
done
log "pilot_002 train/select done"
