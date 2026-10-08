#!/usr/bin/env bash
# pilot_002 평가(PLAN 6절, PROTOCOL_v2). 셀마다 한 번만 잰다(재실행 없음). 측정이 하나 끝날 때마다 커밋·push한다.
# 순서: HF 셀(SFT → 최종, 각각 업체 100 → aux_test_v1) → Ollama 버전 확인(결정 31)
#       → (버전이 0.35.1이 아니면 E·B-conv를 업체 100·aux에서 먼저 다시 잰다) → Ollama 셀(SFT → 최종, 각각 업체 100 → aux).
# HF: GPU 3에 다른 프로세스가 없으면 GPU 3, 아니면 Ollama 모델이 없는 GPU 2. HF 셀은 Ollama 모델이 내려간 상태에서 시작한다.
# Ollama: 결정 55 확인(precheck, 첫 문항 100% GPU, 호출 30 tok/s 이상). 멈추면 출력을 ABORTED_gpu_*로 옮기고 멈춘다.
# Ollama 측정 중에는 다른 Ollama 호출이나 HF 작업을 하지 않는다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
RAW=$REPO/training/generated/pilot_002
GUARD=$HERE/ollama_gpu_guard.py
V100=evaluation/vendor100/gold.yaml
AUX_YAML=$HERE/aux_test/aux_test_gold.yaml
AUX_ITEMS=sft_dpo_inventory/pilot_prep_005/sets/aux_test_items.json
declare -A UUID=([2]=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21 [3]=GPU-48f798cc-9437-50ac-d604-448bbad7b311)
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
       PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
mkdir -p "$HERE/vendor100" "$HERE/aux_test" "$RAW"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
die() { log "STOP: $1"; exit 1; }
commit() {   # message files...
  local msg=$1; shift
  git add "$@" && git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "$msg

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" && git push -q origin geoflow/sft-dpo-t2pc >> "$HERE/runs.log" 2>&1 \
  || die "commit/push failed: $msg"
}
ollama_idle() { for _ in $(seq 120); do [ "$(curl -s localhost:11434/api/ps)" = '{"models":[]}' ] && return 0; sleep 5; done; return 1; }
gpu_record() {
  { echo "## $(date -Is) $1"; nvidia-smi --query-gpu=index,uuid,memory.used --format=csv,noheader
    nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader
    echo "## ollama container"; docker exec ollama nvidia-smi -L 2>&1; curl -s localhost:11434/api/ps; echo; } >> "$HERE/gpu_check.txt" 2>&1
}
hf_gpu() {   # prints 3 or 2 or nothing
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
adapter_of() { "$PY" -c "import json; print(json.load(open('$HERE/$1'))['selected']['adapter'])"; }

ollama_cell() {   # label model gold outdir version
  local label=$1 model=$2 gold=$3 out=$4 version=$5
  [ -e "$out/$label.jsonl" ] && die "$out/$label.jsonl already exists"
  ollama_idle || die "Ollama model still loaded before $label"
  [ -z "$(nvidia-smi -i ${UUID[2]} --query-compute-apps=pid --format=csv,noheader)" ] || die "GPU 2 busy before $label"
  "$TV" "$GUARD" precheck --version "$version" --out "$out/gpu_precheck_$label.json" >> "$HERE/runs.log" 2>&1 \
    || die "$label precheck failed (decision 55)"
  gpu_record "ollama $label ($out)"
  log "$label start ($model, $(basename "$out"))"
  "$TV" evaluate_vendor100.py --gold "$gold" llm --model "$model" --reference-date 2026-09-25 \
      --condition-check --model-think auto --out "$out/$label.json" > "$out/$label.log" 2>&1 &
  local pid=$!
  "$TV" "$GUARD" watch --pid $pid --rows "$out/$label.jsonl" --model "$model" --out "$out/gpu_guard_$label.json" \
      > "$out/gpu_guard_$label.log" 2>&1
  local grc=$?; wait $pid; local rc=$?
  log "$label ($(basename "$out")) exit=$rc guard=$grc"
  if [ $grc -ne 0 ]; then
    local f; for f in "$out/$label".*; do [ -e "$f" ] && mv "$f" "$out/ABORTED_gpu_$(basename "$f")"; done
    git add "$out"/ABORTED_gpu_"$label".* "$out/gpu_guard_$label".* "$out/gpu_precheck_$label.json" "$HERE/runs.log" "$HERE/gpu_check.txt"
    commit "eval(sft-dpo): pilot_002 $label($(basename "$out")) 결정 55로 중단(ABORTED_gpu)" "$HERE/runs.log"
    die "$label ($(basename "$out")) aborted by decision 55 guard"
  fi
  [ $rc -eq 0 ] || die "$label ($(basename "$out")) failed"
  commit "eval(sft-dpo): pilot_002 $(basename "$out") $label 셀(PROTOCOL_v2, 한 번 측정, 결정 55 확인 통과)" \
    "$out/$label.json" "$out/$label.jsonl" "$out/$label.spec.json" "$out/$label.log" "$out/gpu_guard_$label.json" \
    "$out/gpu_guard_$label.log" "$out/gpu_precheck_$label.json" "$HERE/runs.log" "$HERE/gpu_check.txt"
}

log "pilot_002 eval start"
# 1. HF 셀(HF-E 기준과 같은 명세)
for stage in sft final; do
  if [ $stage = sft ]; then adapter=$(adapter_of selection_sft.json); else adapter=$(adapter_of selection_dpo.json); fi
  ollama_idle || die "Ollama model loaded before HF-$stage"
  gpu_record "HF-$stage vendor100"; g=$(hf_gpu); [ -n "$g" ] || die "no usable GPU for HF-$stage"
  log "vendor100 HF-$stage start (CUDA $g ${UUID[$g]}, $adapter)"
  CUDA_VISIBLE_DEVICES=$g "$PY" sft_dpo_inventory/thinking_prep_001/hf_eval_thinking.py --condition-check --adapter "$adapter" \
      --out "$HERE/vendor100/HF-$stage.json" --raw-out "$RAW/vendor100_HF-${stage}_raw.jsonl" > "$HERE/vendor100/HF-$stage.log" 2>&1
  rc=$?; log "vendor100 HF-$stage exit=$rc (CUDA $g)"; [ $rc -eq 0 ] || die "vendor100 HF-$stage failed"
  commit "eval(sft-dpo): pilot_002 업체 100 HF-$stage 셀(PROTOCOL_v2 3절, 한 번 측정, CUDA $g)" "$HERE/vendor100/HF-$stage.json" \
    "$HERE/vendor100/HF-$stage.log" "$RAW/vendor100_HF-${stage}_raw.jsonl" "$HERE/runs.log" "$HERE/gpu_check.txt"

  ollama_idle || die "Ollama model loaded before aux HF-$stage"
  gpu_record "HF-$stage aux"; g=$(hf_gpu); [ -n "$g" ] || die "no usable GPU for aux HF-$stage"
  log "aux_test HF-$stage start (CUDA $g ${UUID[$g]})"
  CUDA_VISIBLE_DEVICES=$g "$PY" sft_dpo_inventory/pilot_prep_005/sets/eval_set.py --items "$AUX_ITEMS" --label "aux_HF-$stage" \
      --out "$HERE/aux_test/HF-$stage.json" --raw-out "$RAW/aux_HF-${stage}_raw.jsonl" --adapter "$adapter" \
      > "$HERE/aux_test/HF-$stage.log" 2>&1
  rc=$?; log "aux_test HF-$stage exit=$rc (CUDA $g)"; [ $rc -eq 0 ] || die "aux_test HF-$stage failed"
  commit "eval(sft-dpo): pilot_002 aux_test_v1 HF-$stage 셀(PROTOCOL_v2 2.2, 한 번 측정, CUDA $g)" "$HERE/aux_test/HF-$stage.json" \
    "$HERE/aux_test/HF-$stage.log" "$RAW/aux_HF-${stage}_raw.jsonl" "$HERE/runs.log" "$HERE/gpu_check.txt"
done

# 2. Ollama 버전 확인(결정 31)
VERSION=$(curl -s localhost:11434/api/version | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["version"])')
echo "{\"checked_at\": \"$(date -Is)\", \"ollama_version\": \"$VERSION\", \"e_bconv_version\": \"0.35.1\", \"same\": $([ "$VERSION" = 0.35.1 ] && echo true || echo false)}" \
  > "$HERE/vendor100/ollama_version_check.json"
log "ollama version $VERSION"
commit "eval(sft-dpo): pilot_002 Ollama 버전 확인($VERSION, 결정 31)" "$HERE/vendor100/ollama_version_check.json" "$HERE/runs.log"
if [ "$VERSION" != "0.35.1" ]; then
  for cell in E B-conv; do
    if [ $cell = E ]; then m=qwen3:8b; else m=geoflow-qwen3-8b-b968826d-base:q4km-hfthink; fi
    ollama_cell "$cell" "$m" "$V100" "$HERE/vendor100" "$VERSION"
    ollama_cell "${cell}_v$VERSION" "$m" "$AUX_YAML" "$HERE/aux_test" "$VERSION"
  done
fi

# 3. Ollama 셀(렌더링 확인을 통과한 모델만)
for stage in sft final; do
  model=geoflow-qwen3-8b-pilot002-$stage:q4km-hfthink
  if [ ! -e "$HERE/ollama/RENDER_OK_$stage" ]; then log "Ollama-$stage SKIPPED: render check not passed"; continue; fi
  ollama_cell "Ollama-$stage" "$model" "$V100" "$HERE/vendor100" "$VERSION"
  ollama_cell "Ollama-$stage" "$model" "$AUX_YAML" "$HERE/aux_test" "$VERSION"
done
log "pilot_002 eval done"
