#!/usr/bin/env bash
# calibration_001(결정 64): selection_v1 sampling 셀. 설정·seed·셀 순서는 PLAN.md(고정 뒤 고치지 않음).
#   bash run_cal.sh smoke-hf                      # 재현성: HF-base 5문항을 같은 seed로 두 번(repro/)
#   bash run_cal.sh smoke-ollama LABEL MODEL      # 재현성: Ollama 5문항을 같은 seed로 두 번(repro/)
#   bash run_cal.sh hf LABEL ADAPTER|-            # HF 셀: 표본 k=1..4(runs/LABEL_s{k}.*), 셀 끝에 커밋·push
#   bash run_cal.sh ollama LABEL MODEL            # Ollama 셀: 표본 k=1..4, 결정 55 확인, 셀 끝에 커밋·push
# 출력이 이미 있으면 멈춘다(다시 재지 않음). HF와 Ollama는 동시에 돌리지 않는다. 컨테이너는 건드리지 않는다.
# 원문(thinking 포함)은 training/generated/calibration_001/raw/(ignore). 기록(json·jsonl·log)은 커밋한다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
GUARD=$REPO/sft_dpo_inventory/pilot_002/ollama_gpu_guard.py
GOLD=$REPO/sft_dpo_inventory/conversion_diag/selection_gold.yaml
RAW=$REPO/training/generated/calibration_001/raw
SMOKE_ITEMS=old44/g02,contrast/c03c,indepv2/n06,indepv3/m09,indepv4/k08
SMOKE_SEED=20261101
SAMPLE_SEEDS="20261101 20261102 20261103 20261104"   # 표본 번호 k=1..4 → 20261100+k
OLLAMA_SAMPLING="--temperature 0.6 --top-p 0.95 --top-k 20 --min-p 0 --repeat-penalty 1 --presence-penalty 0 --frequency-penalty 0"
HF_SAMPLING="--do-sample --temperature 0.6 --top-p 0.95 --top-k 20 --min-p 0 --repetition-penalty 1"
declare -A UUID=([2]=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21 [3]=GPU-48f798cc-9437-50ac-d604-448bbad7b311)
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
mkdir -p "$HERE/runs" "$HERE/repro" "$RAW"
LOG=$HERE/runs.log
log() { echo "== $1 $(date -Is)" >> "$LOG"; }
die() { log "STOP: $1"; exit 1; }
ollama_idle() { for _ in $(seq 120); do [ "$(curl -s localhost:11434/api/ps)" = '{"models":[]}' ] && return 0; sleep 5; done; return 1; }
gpu_record() {
  { echo "## $(date -Is) $1"; nvidia-smi --query-gpu=index,uuid,memory.used --format=csv,noheader
    nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader
    echo "## ollama container"; docker exec ollama nvidia-smi -L 2>&1; curl -s localhost:11434/api/ps; echo; } >> "$HERE/gpu_check.txt" 2>&1
}
commit() {   # message files...
  local msg=$1; shift
  git add "$@" && git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "$msg

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" || die "commit failed: $msg"
  # push가 거부되면 기록만 하고 계속한다. 통합은 CLAUDE.md 14번 절차로 세션이 따로 한다.
  git push -q origin geoflow/sft-dpo-t2pc >> "$LOG" 2>&1 || log "push rejected: $msg (CLAUDE.md 14번 절차 필요)"
}
hf_gpu() {   # 3 → 2 순서. 다른 프로세스가 없고(2는 Ollama 모델도 없고) torch UUID가 맞는 GPU 번호
  local g used procs
  for g in 3 2; do
    used=$(nvidia-smi -i ${UUID[$g]} --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')
    procs=$(nvidia-smi -i ${UUID[$g]} --query-compute-apps=pid --format=csv,noheader | wc -l)
    [ "$used" -lt 100 ] && [ "$procs" -eq 0 ] || continue
    [ $g = 3 ] || [ "$(curl -s localhost:11434/api/ps)" = '{"models":[]}' ] || continue
    CUDA_VISIBLE_DEVICES=$g "$PY" -c "import torch,sys; sys.exit(0 if 'GPU-'+str(torch.cuda.get_device_properties(0).uuid)=='${UUID[$g]}' else 1)" \
      && { echo $g; return; }
  done
}
sampler_params() {   # since prefix: Ollama 서버 로그에서 실제 적용된 sampler 값(요청마다 찍힘)을 세어 남긴다
  docker logs ollama --since "$1" 2>&1 | grep -A4 "sampler params" | grep -E "repeat_penalty|top_k|temp" \
    | sed 's/^[[:space:]]*//' | sort | uniq -c > "$2_sampler_params.txt"
}
hf_run() {   # prefix seed adapter only
  local p=$1 seed=$2 adapter=$3 only=$4 g
  [ -e "$p.json" ] && die "$p.json already exists"
  ollama_idle || die "Ollama model loaded before HF $(basename "$p")"
  g=$(hf_gpu); [ -n "$g" ] || die "no free HF GPU before $(basename "$p")"
  gpu_record "hf $(basename "$p") on GPU $g"
  log "hf $(basename "$p") start GPU $g seed $seed adapter $adapter"
  local extra=(); [ "$adapter" = - ] || extra+=(--adapter "$adapter"); [ -z "$only" ] || extra+=(--only "$only")
  CUDA_VISIBLE_DEVICES=$g "$PY" sft_dpo_inventory/thinking_prep_001/hf_eval_thinking.py --gold "$GOLD" --condition-check \
    $HF_SAMPLING --seed "$seed" --record-env --out "$p.json" --raw-out "$RAW/$(basename "$p")_raw.jsonl" "${extra[@]}" \
    > "$p.log" 2>&1
  local rc=$?; log "hf $(basename "$p") exit=$rc"; [ $rc -eq 0 ] || die "hf $(basename "$p") failed rc=$rc"
}
ollama_run() {   # prefix seed model only
  local p=$1 seed=$2 model=$3 only=$4 since
  [ -e "$p.jsonl" ] && die "$p.jsonl already exists"
  [ -e "$RAW/$(basename "$p")_raw.jsonl" ] && die "raw for $(basename "$p") already exists"
  ollama_idle || die "Ollama model still loaded before $(basename "$p")"
  [ -z "$(nvidia-smi -i ${UUID[2]} --query-compute-apps=pid --format=csv,noheader)" ] || die "GPU 2 busy before $(basename "$p")"
  "$TV" "$GUARD" precheck --out "${p}_gpu_precheck.json" >> "$LOG" 2>&1 || die "$(basename "$p") precheck failed (decision 55)"
  gpu_record "ollama $(basename "$p") ($model)"
  since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  log "ollama $(basename "$p") start ($model) seed $seed"
  local extra=(); [ -z "$only" ] || extra+=(--only "$only")
  "$TV" evaluate_vendor100.py --gold "$GOLD" llm --model "$model" --reference-date 2026-09-25 --condition-check \
    --model-think auto $OLLAMA_SAMPLING --seed "$seed" --record-env --raw-out "$RAW/$(basename "$p")_raw.jsonl" \
    --out "$p.json" "${extra[@]}" > "$p.log" 2>&1 &
  local pid=$!
  "$TV" "$GUARD" watch --pid $pid --rows "$p.jsonl" --model "$model" --out "${p}_gpu_guard.json" > "${p}_gpu_guard.log" 2>&1
  local grc=$?; wait $pid; local rc=$?
  sampler_params "$since" "$p"
  log "ollama $(basename "$p") exit=$rc guard=$grc"
  if [ $grc -ne 0 ]; then
    local f; for f in "$p".* "${p}_"*; do [ -e "$f" ] && mv "$f" "$(dirname "$f")/ABORTED_gpu_$(basename "$f")"; done
    die "$(basename "$p") aborted by decision 55 guard"
  fi
  [ $rc -eq 0 ] || die "ollama $(basename "$p") failed rc=$rc"
}

mode=$1; shift
log "run_cal $mode start: $*"
case $mode in
  smoke-hf)
    for t in a b; do hf_run "$HERE/repro/hf_base_$t" $SMOKE_SEED - "$SMOKE_ITEMS"; done ;;
  smoke-ollama)
    label=$1; model=$2
    for t in a b; do ollama_run "$HERE/repro/ollama_${label}_$t" $SMOKE_SEED "$model" "$SMOKE_ITEMS"; done ;;
  hf)
    label=$1; adapter=$2; k=0; files=()
    for seed in $SAMPLE_SEEDS; do k=$((k+1)); p=$HERE/runs/${label}_s$k
      hf_run "$p" "$seed" "$adapter" ""; files+=("$p.json" "$p.log"); done
    commit "eval(sft-dpo): calibration_001 HF 셀 $label(selection_v1, sampling k=4, 한 번 측정)" "${files[@]}" "$LOG" "$HERE/gpu_check.txt" ;;
  ollama)
    label=$1; model=$2; k=0; files=()
    for seed in $SAMPLE_SEEDS; do k=$((k+1)); p=$HERE/runs/${label}_s$k
      ollama_run "$p" "$seed" "$model" ""
      files+=("$p.json" "$p.jsonl" "$p.spec.json" "$p.log" "${p}_gpu_guard.json" "${p}_gpu_guard.log" "${p}_gpu_precheck.json" "${p}_sampler_params.txt"); done
    commit "eval(sft-dpo): calibration_001 Ollama 셀 $label($model, selection_v1, sampling k=4, 결정 55 확인 통과)" \
      "${files[@]}" "$LOG" "$HERE/gpu_check.txt" ;;
  *) die "unknown mode $mode" ;;
esac
log "run_cal $mode done"
