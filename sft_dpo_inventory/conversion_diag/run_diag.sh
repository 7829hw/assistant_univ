#!/usr/bin/env bash
# conversion_diag(결정 59–63): 진단 모델의 렌더링 확인(결정 31)과 selection_v1 Ollama 셀(PLAN.md).
#   bash run_diag.sh render LABEL=MODEL ...   # 렌더링 확인만(결과 render/LABEL.json)
#   bash run_diag.sh cells  LABEL=MODEL ...   # selection_v1 셀(결과 selection/LABEL.*), 셀마다 커밋·push
# 모든 Ollama 실행에 결정 55 확인(precheck + watch, 30 tok/s)을 붙인다. 멈추면 출력은 ABORTED_gpu_*로 옮기고 멈춘다.
# 셀마다 한 번만 잰다(출력이 있으면 멈춤). 컨테이너는 건드리지 않는다. Ollama 측정 중 다른 Ollama 호출이나 HF 작업을 하지 않는다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
GUARD=$REPO/sft_dpo_inventory/pilot_002/ollama_gpu_guard.py
RENDER=$REPO/sft_dpo_inventory/pilot_002/ollama/render_check.py
GOLD=$HERE/selection_gold.yaml
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
mkdir -p "$HERE/render" "$HERE/selection"
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
  # push가 거부되면 기록만 하고 계속한다. 통합은 CLAUDE.md 14번 절차로 사람이(세션이) 따로 한다.
  git push -q origin geoflow/sft-dpo-t2pc >> "$LOG" 2>&1 || log "push rejected: $msg (CLAUDE.md 14번 절차 필요)"
}
guarded() {   # kind label model out_prefix rows_file -- command...
  local kind=$1 label=$2 model=$3 prefix=$4 rows=$5; shift 6
  ollama_idle || die "Ollama model still loaded before $kind $label"
  "$TV" "$GUARD" precheck --out "${prefix}_gpu_precheck.json" >> "$LOG" 2>&1 || die "$kind $label precheck failed (decision 55)"
  gpu_record "$kind $label ($model)"
  log "$kind $label start ($model)"
  "$@" &
  local pid=$!
  "$TV" "$GUARD" watch --pid $pid --rows "$rows" --model "$model" --out "${prefix}_gpu_guard.json" > "${prefix}_gpu_guard.log" 2>&1
  local grc=$?; wait $pid; local rc=$?
  log "$kind $label exit=$rc guard=$grc"
  if [ $grc -ne 0 ]; then
    local f; for f in "$prefix".* "${prefix}_"*; do [ -e "$f" ] && mv "$f" "$(dirname "$f")/ABORTED_gpu_$(basename "$f")"; done
    die "$kind $label aborted by decision 55 guard"
  fi
  return $rc
}

mode=$1; shift
log "run_diag $mode start: $*"
for pair in "$@"; do
  label=${pair%%=*}; model=${pair#*=}
  if [ "$mode" = render ]; then
    p=$HERE/render/$label
    [ -e "$p.json" ] && die "$p.json already exists"
    guarded render "$label" "$model" "$p" "$p.log" -- \
      sh -c "\"$PY\" \"$RENDER\" --model \"$model\" --out \"$p.json\" > \"$p.log\" 2>&1"
    log "render $label rc=$?"
  else
    p=$HERE/selection/$label
    [ -e "$p.jsonl" ] && die "$p.jsonl already exists"
    guarded cell "$label" "$model" "$p" "$p.jsonl" -- \
      sh -c "\"$TV\" evaluate_vendor100.py --gold \"$GOLD\" llm --model \"$model\" --reference-date 2026-09-25 --condition-check --model-think auto --out \"$p.json\" > \"$p.log\" 2>&1"
    rc=$?
    [ $rc -eq 0 ] || die "cell $label failed rc=$rc"
    commit "eval(sft-dpo): conversion_diag selection_v1 Ollama 셀 $label($model, 한 번 측정, 결정 55 확인 통과)" \
      "$p.json" "$p.jsonl" "$p.spec.json" "$p.log" "${p}_gpu_guard.json" "${p}_gpu_guard.log" "${p}_gpu_precheck.json" "$LOG" "$HERE/gpu_check.txt"
  fi
done
log "run_diag $mode done"
