#!/usr/bin/env bash
# pilot_001 학습 모델 등록(PLAN 5절, 결정 20·31). 고른 SFT와 최종 adapter를 base snapshot에 bfloat16으로 merge(CPU) →
# gguf_convert.sh(llama.cpp b11434, bf16 → Q4_K_M, CPU) → API(blob + create)로 새 이름에 등록 → 렌더링 확인 10문항.
# 기존 Ollama 모델은 덮어쓰거나 지우지 않는다. 렌더링 확인을 통과하지 못한 모델은 표시만 하고 다음 단계(업체 100)에서 빼게 한다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
WORK=/home/hwkim/sftdpo_work/pilot_001
GGUF=/home/hwkim/sftdpo_work/gguf
BASE=/home/hwkim/sftdpo_work/hf-cache/hub/models--Qwen--Qwen3-8B/snapshots/b968826d9c46dd6066d109eabc6255188de91218
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
mkdir -p "$HERE/ollama" "$WORK/merged"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
die() { log "STOP: $1"; exit 1; }

for stage in sft final; do
  if [ $stage = sft ]; then sel=selection_sft.json; else sel=selection_dpo.json; fi
  adapter=$("$PY" -c "import json; print(json.load(open('$HERE/$sel'))['selected']['adapter'])")
  name=qwen3-8b-pilot001-$stage
  model=geoflow-qwen3-8b-pilot001-$stage:q4km-hfthink
  log "merge $stage start ($adapter)"
  CUDA_VISIBLE_DEVICES="" "$PY" -m training.merge_adapter --base "$BASE" --adapter "$adapter" --output "$WORK/merged/$stage" \
      --dtype bfloat16 > "$HERE/ollama/merge_$stage.log" 2>&1 || die "merge $stage failed"
  log "convert $stage start"
  bash sft_dpo_inventory/pilot_prep_001/gguf_convert.sh "$WORK/merged/$stage" "$GGUF" "$name" > "$HERE/ollama/convert_$stage.log" 2>&1 \
      || die "convert $stage failed"
  cp "$GGUF/$name.receipt.json" "$HERE/ollama/$name.receipt.json"
  log "register $stage start"
  "$TV" "$HERE/ollama/register_model.py" --model "$model" --receipt "$GGUF/$name.receipt.json" \
      --out "$HERE/ollama/registration_$stage.json" > "$HERE/ollama/register_$stage.log" 2>&1 || die "register $stage failed"
  log "render check $stage start"
  "$PY" "$HERE/ollama/render_check.py" --model "$model" --out "$HERE/ollama/render_check_$stage.json" \
      > "$HERE/ollama/render_check_$stage.log" 2>&1
  rc=$?; log "render check $stage exit=$rc"
  if [ $rc -eq 0 ]; then touch "$HERE/ollama/RENDER_OK_$stage"; else log "render check $stage FAILED: Ollama measurement of $stage will be skipped"; fi
done
log "register done"
