#!/usr/bin/env bash
# 경로별 token 확률(결정 75, 작업 2). GPU 3(CLAUDE.md 5·6번), 생성 없음, Ollama 서버를 부르지 않는다.
#   bash run_scores.sh [PATH ...]     # 없으면 12경로 전부. 이미 있는 출력은 건너뛰지 않고 멈춘다.
# 출력(logits 요약 이진 파일)은 저장소 밖 /data/hwkim/sftdpo_work/logprob_diag/scores/에 둔다. 기록(runs.log, gpu_check.txt)만 커밋한다.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
TOOL=/data/hwkim/sftdpo_work/token_logprobs
WORK=/data/hwkim/sftdpo_work/logprob_diag; OUT=$WORK/scores
GPU=GPU-48f798cc-9437-50ac-d604-448bbad7b311
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
declare -A GGUF=(
  [final_gguf_bf16]=/data/hwkim/sftdpo_work/gguf/qwen3-8b-pilot002-final-bf16.gguf
  [final_q8]=/data/hwkim/sftdpo_work/gguf/diag/qwen3-8b-pilot002-final-Q8_0.gguf
  [final_self_q4]=/data/hwkim/sftdpo_work/gguf/qwen3-8b-pilot002-final-Q4_K_M.gguf
  [final_official_q4]=/data/hwkim/sftdpo_work/gguf/quant_recipe/qwen3-8b-pilot002-final-Q4_K_M-official.gguf
  [base_gguf_bf16]=/home/hwkim/sftdpo_work/gguf/qwen3-8b-b968826d-base-bf16.gguf
  [base_q8]=/data/hwkim/sftdpo_work/gguf/diag/qwen3-8b-b968826d-base-Q8_0.gguf
  [base_self_q4]=/home/hwkim/sftdpo_work/gguf/qwen3-8b-b968826d-base-Q4_K_M.gguf
  [base_official_q4]=/data/hwkim/sftdpo_work/gguf/quant_recipe/qwen3-8b-b968826d-base-Q4_K_M-official.gguf
  [official_blob]=/data/hwkim/ollama/models/blobs/sha256-a3de86cd1c132c822487ededd47a324c50491393e6565cd14bafa40d0b8e686f
)
ALL="hf_final_peft hf_final_merged final_gguf_bf16 final_q8 final_self_q4 final_official_q4 hf_base base_gguf_bf16 base_q8 base_self_q4 base_official_q4 official_blob"
LOG=$HERE/runs.log
log() { echo "== $1 $(date -Is)" >> "$LOG"; }
die() { log "STOP: $1"; exit 1; }
cd "$REPO"; mkdir -p "$OUT"
gpu_ok() {
  local used procs
  used=$(nvidia-smi -i $GPU --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')
  procs=$(nvidia-smi -i $GPU --query-compute-apps=pid --format=csv,noheader | wc -l)
  { echo "## $(date -Is) $1"; nvidia-smi --query-gpu=index,uuid,memory.used --format=csv,noheader
    nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader; } >> "$HERE/gpu_check.txt"
  [ "$used" -lt 100 ] && [ "$procs" -eq 0 ] || return 1
  CUDA_VISIBLE_DEVICES=3 "$PY" -c "import torch,sys; sys.exit(0 if 'GPU-'+str(torch.cuda.get_device_properties(0).uuid)=='$GPU' else 1)"
}
for p in ${@:-$ALL}; do
  f=$OUT/$p.bin
  [ -e "$f" ] && die "$f already exists"
  gpu_ok "$p" || die "GPU 3 not free or UUID mismatch before $p"
  log "score $p start"
  if [ -n "${GGUF[$p]:-}" ]; then
    log "score $p gguf ${GGUF[$p]} sha256 $(sha256sum "${GGUF[$p]}" | cut -d' ' -f1)"
    CUDA_VISIBLE_DEVICES=3 "$TOOL" "${GGUF[$p]}" "$WORK/sequences.txt" "$f" 64 16384 > "$OUT/$p.log" 2>&1
  else
    CUDA_VISIBLE_DEVICES=3 "$PY" "$HERE/score_hf.py" "$p" "$f" > "$OUT/$p.log" 2>&1
  fi
  rc=$?; log "score $p exit=$rc bin_sha256 $(sha256sum "$f" 2>/dev/null | cut -d' ' -f1)"
  [ $rc -eq 0 ] || die "score $p failed rc=$rc"
done
log "run_scores done"
