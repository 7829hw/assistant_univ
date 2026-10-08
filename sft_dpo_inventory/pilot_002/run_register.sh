#!/usr/bin/env bash
# pilot_002 학습 모델 등록(PLAN 5절, 결정 20·31·53·55). pilot_001/run_register.sh와 같은 흐름이다.
# 고른 SFT와 최종 adapter를 base snapshot에 bfloat16으로 merge(CPU) → gguf_convert.sh(llama.cpp b11434, bf16 → Q4_K_M, CPU)
# → API(blob + create)로 새 이름에 등록(base와 같은 TEMPLATE·PARAMETER) → 렌더링 확인 10문항(결정 31).
# 렌더링 확인에도 결정 55의 GPU 확인(precheck, 첫 요청 100% GPU, 호출 30 tok/s 이상)을 붙인다.
# 기존 Ollama 모델은 덮어쓰거나 지우지 않는다. 렌더링 확인을 통과하지 못한 모델은 그 모델의 Ollama 측정을 하지 않는다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
# 루트 디스크 여유(79 GB)가 merge(2×16 GB)·GGUF(2×21 GB)에 모자라 /data에 둔다(PLAN_DEVIATIONS.md 3번). 저장소 밖이다.
WORK=/data/hwkim/sftdpo_work/pilot_002
GGUF=/data/hwkim/sftdpo_work/gguf
BASE=/home/hwkim/sftdpo_work/hf-cache/hub/models--Qwen--Qwen3-8B/snapshots/b968826d9c46dd6066d109eabc6255188de91218
GUARD=$HERE/ollama_gpu_guard.py
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
mkdir -p "$HERE/ollama" "$WORK/merged"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
die() { log "STOP: $1"; exit 1; }
ollama_idle() { for _ in $(seq 120); do [ "$(curl -s localhost:11434/api/ps)" = '{"models":[]}' ] && return 0; sleep 5; done; return 1; }

for stage in sft final; do
  if [ $stage = sft ]; then sel=selection_sft.json; else sel=selection_dpo.json; fi
  adapter=$("$PY" -c "import json; print(json.load(open('$HERE/$sel'))['selected']['adapter'])")
  name=qwen3-8b-pilot002-$stage
  model=geoflow-qwen3-8b-pilot002-$stage:q4km-hfthink
  [ -e "$GGUF/$name.receipt.json" ] && die "$GGUF/$name.receipt.json already exists"
  log "merge $stage start ($adapter)"
  CUDA_VISIBLE_DEVICES="" "$PY" -m training.merge_adapter --base "$BASE" --adapter "$adapter" --output "$WORK/merged/$stage" \
      --dtype bfloat16 > "$HERE/ollama/merge_$stage.log" 2>&1 || die "merge $stage failed"
  log "convert $stage start"
  bash sft_dpo_inventory/pilot_prep_001/gguf_convert.sh "$WORK/merged/$stage" "$GGUF" "$name" > "$HERE/ollama/convert_$stage.log" 2>&1 \
      || die "convert $stage failed"
  cp "$GGUF/$name.receipt.json" "$HERE/ollama/$name.receipt.json"
  log "register $stage start ($model)"
  "$TV" sft_dpo_inventory/pilot_001/ollama/register_model.py --model "$model" --receipt "$GGUF/$name.receipt.json" \
      --out "$HERE/ollama/registration_$stage.json" > "$HERE/ollama/register_$stage.log" 2>&1 || die "register $stage failed"
  ollama_idle || die "Ollama model still loaded before render check $stage"
  "$TV" "$GUARD" precheck --out "$HERE/ollama/gpu_precheck_render_$stage.json" >> "$HERE/runs.log" 2>&1 \
      || die "render check $stage precheck failed (decision 55)"
  log "render check $stage start"
  "$PY" "$HERE/ollama/render_check.py" --model "$model" --out "$HERE/ollama/render_check_$stage.json" \
      > "$HERE/ollama/render_check_$stage.log" 2>&1 &
  pid=$!
  "$TV" "$GUARD" watch --pid $pid --rows "$HERE/ollama/render_check_$stage.log" --model "$model" \
      --out "$HERE/ollama/gpu_guard_render_$stage.json" > "$HERE/ollama/gpu_guard_render_$stage.log" 2>&1
  grc=$?; wait $pid; rc=$?
  log "render check $stage exit=$rc guard=$grc"
  if [ $grc -ne 0 ]; then
    for f in "$HERE/ollama/render_check_$stage".*; do [ -e "$f" ] && mv "$f" "$HERE/ollama/ABORTED_gpu_$(basename "$f")"; done
    die "render check $stage aborted by decision 55 guard"
  fi
  if [ $rc -eq 0 ]; then touch "$HERE/ollama/RENDER_OK_$stage"; else log "render check $stage FAILED: Ollama measurement of $stage will be skipped"; fi
done
log "register done"
