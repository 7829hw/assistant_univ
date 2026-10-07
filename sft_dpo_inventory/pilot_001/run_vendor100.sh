#!/usr/bin/env bash
# pilot_001 업체 100 평가(PLAN 6절, PROTOCOL 확정판, ADDENDUM). 셀마다 한 번만 잰다(재실행 없음).
# 순서: HF 셀(SFT → 최종, GPU 2) → Ollama 버전 확인(결정 31) → E·B-conv 재측정(결정 32: Ollama가 GPU 2로 옮겨 장치가 바뀜)
#       → Ollama 셀(SFT → 최종). 결정 32 뒤로 HF와 Ollama가 GPU 2를 같이 쓰므로 HF 셀은 Ollama 모델이 내려간 상태에서 시작한다.
# Ollama 측정 중에는 다른 Ollama 호출이나 HF 측정을 하지 않는다. 셀이 끝날 때마다 결과를 커밋·push한다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
RAW=$REPO/training/generated/pilot_001
OUT=$HERE/vendor100
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
       PYTHONDONTWRITEBYTECODE=1
cd "$REPO"
mkdir -p "$OUT" "$RAW"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
die() { log "STOP: $1"; exit 1; }
commit() {   # message files...
  local msg=$1; shift
  git add "$@" && git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "$msg

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" && git push origin geoflow/sft-dpo-t2pc >> "$HERE/runs.log" 2>&1
}
ollama_idle() { until [ "$(curl -s localhost:11434/api/ps | "$PY" -c 'import json,sys; print(len(json.load(sys.stdin)["models"]))')" = "0" ]; do sleep 10; done; }
GPU3=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21   # 결정 32: Ollama 장치는 이제 host GPU 2(변수 이름은 그대로 둔다)
gpu3_quiet() {   # Ollama 모델이 내려간 상태에서 Ollama 장치에 다른 프로세스(HF 작업·다른 사용자)가 없을 때까지 기다린다(최대 3시간, 넘으면 이탈로 기록하고 진행)
  local waited=0
  while [ "$(nvidia-smi -i $GPU3 --query-compute-apps=pid --format=csv,noheader | wc -l)" -gt 0 ]; do
    [ $waited -eq 0 ] && log "GPU3 has foreign processes: $(nvidia-smi -i $GPU3 --query-compute-apps=pid,process_name,used_memory --format=csv,noheader | tr '\n' ';')"
    sleep 60; waited=$((waited+60))
    if [ $waited -ge 10800 ]; then log "DEVIATION: GPU3 still shared after 3h; measuring anyway"; break; fi
  done
  echo "   GPU3 before measurement: $(nvidia-smi -i $GPU3 --query-gpu=memory.used --format=csv,noheader); apps=$(nvidia-smi -i $GPU3 --query-compute-apps=pid --format=csv,noheader | wc -l)" >> "$HERE/runs.log"
}

# 1. HF 셀(기준 HF-E 기록과 같은 명세, GPU 2)
for stage in sft final; do
  if [ $stage = sft ]; then sel=selection_sft.json; else sel=selection_dpo.json; fi
  adapter=$("$PY" -c "import json; print(json.load(open('$HERE/$sel'))['selected']['adapter'])")
  ollama_idle; log "vendor100 HF-$stage start ($adapter)"
  CUDA_VISIBLE_DEVICES=2 "$PY" sft_dpo_inventory/thinking_prep_001/hf_eval_thinking.py --condition-check --adapter "$adapter" \
      --out "$OUT/HF-$stage.json" --raw-out "$RAW/HF-${stage}_raw.jsonl" > "$OUT/HF-$stage.log" 2>&1
  rc=$?; log "vendor100 HF-$stage exit=$rc"; [ $rc -eq 0 ] || die "HF-$stage failed"
  commit "eval(sft-dpo): pilot_001 업체 100 HF-$stage 셀(PROTOCOL 3.1, 한 번 측정)" "$OUT/HF-$stage.json" "$OUT/HF-$stage.log" "$HERE/runs.log"
done

# 2. Ollama 버전 확인(결정 31)
VERSION=$(curl -s localhost:11434/api/version | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["version"])')
echo "{\"checked_at\": \"$(date -Is)\", \"ollama_version\": \"$VERSION\", \"e_bconv_version\": \"0.35.1\", \"same\": $([ "$VERSION" = 0.35.1 ] && echo true || echo false)}" > "$OUT/ollama_version_check.json"
log "ollama version $VERSION"
# 결정 32-1: 동일 사양 GPU라 장치 변경만으로는 다시 재지 않고 GPU 3에서 잰 E·B-conv(pilot_prep_003)를 쓴다.
# 결정 31: Ollama 버전이 0.35.1과 다를 때만 E·B-conv를 같은 버전에서 다시 잰다.
if [ "$VERSION" != "0.35.1" ]; then
  for cell in E B-conv; do
    if [ $cell = E ]; then m=qwen3:8b; else m=geoflow-qwen3-8b-b968826d-base:q4km-hfthink; fi
    ollama_idle; gpu3_quiet; log "vendor100 $cell (re-measure on GPU 2, Ollama $VERSION) start"
    "$TV" evaluate_vendor100.py --gold evaluation/vendor100/gold.yaml llm --model "$m" --reference-date 2026-09-25 \
        --condition-check --model-think auto --out "$OUT/$cell.json" > "$OUT/$cell.log" 2>&1
    rc=$?; log "vendor100 $cell exit=$rc"; [ $rc -eq 0 ] || die "$cell failed"
    commit "eval(sft-dpo): GPU 2(결정 32)·Ollama $VERSION에서 $cell 재측정" "$OUT/$cell.json" "$OUT/$cell.jsonl" "$OUT/$cell.spec.json" "$OUT/$cell.log" "$HERE/runs.log"
  done
fi
commit "eval(sft-dpo): pilot_001 Ollama 버전 확인($VERSION)" "$OUT/ollama_version_check.json" "$HERE/runs.log"

# 3. Ollama 셀(렌더링 확인을 통과한 모델만)
for stage in sft final; do
  model=geoflow-qwen3-8b-pilot001-$stage:q4km-hfthink
  if [ ! -e "$HERE/ollama/RENDER_OK_$stage" ]; then log "vendor100 Ollama-$stage SKIPPED: render check not passed"; continue; fi
  ollama_idle; gpu3_quiet; log "vendor100 Ollama-$stage start"
  "$TV" evaluate_vendor100.py --gold evaluation/vendor100/gold.yaml llm --model "$model" --reference-date 2026-09-25 \
      --condition-check --model-think auto --out "$OUT/Ollama-$stage.json" > "$OUT/Ollama-$stage.log" 2>&1
  rc=$?; log "vendor100 Ollama-$stage exit=$rc"; [ $rc -eq 0 ] || die "Ollama-$stage failed"
  commit "eval(sft-dpo): pilot_001 업체 100 Ollama-$stage 셀(PROTOCOL 3.2, 한 번 측정)" "$OUT/Ollama-$stage.json" "$OUT/Ollama-$stage.jsonl" "$OUT/Ollama-$stage.spec.json" "$OUT/Ollama-$stage.log" "$HERE/runs.log"
done
log "vendor100 done"
