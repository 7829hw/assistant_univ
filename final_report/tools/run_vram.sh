#!/usr/bin/env bash
# 최종 결과보고서 VRAM 자체시험 실행기(새 파일). 커밋에 고정한 worktree에서 실행. GPU 한 장(인자 G)에서 네 구성을 차례로 잰다.
#   bash run_vram.sh G
#   M1 HF BF16 base, PyTorch allocator 기본값                      (초기 환경)
#   M2 HF BF16 base, PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True (학습·추론 기본 설정, 결정 17)
#   M3 vLLM BF16 + FlashInfer, base, PagedAttention KV block
#   M4 vLLM FP8 + FlashInfer, base + LoRA V4 o101, PagedAttention KV block (최종 최적화 구성)
set -u
G=$1
WT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
MAIN=/home/hwkim/assistant_univ
OUT=$MAIN/final_report/logs/vram
mkdir -p "$OUT"
export P3=$OUT OLLAMA_UUID=GPU-48f798cc-9437-50ac-d604-448bbad7b311
export ALLOWED_UUIDS="$(nvidia-smi --query-gpu=uuid --format=csv,noheader | tr '\n' ' ')"
source "$WT/sft_dpo_inventory/pilot_007/gpu_data/gpu_lib7.sh"
unset PYTORCH_CUDA_ALLOC_CONF
HPY=/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python
VB=/data/hwkim/sftdpo_work/runtime/envs/vllm/bin
CU=/data/hwkim/sftdpo_work/runtime/envs/vllm/lib/python3.12/site-packages/nvidia/cu13
TOOL=$WT/final_report/tools/vram_2048.py
IN=$WT/final_report/data/vram_inputs_2048.jsonl
V4=/data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o101/checkpoint-1984
log() { echo "== $1 $(date -Is)" | tee -a "$OUT/runs.log"; }
log "start worktree=$WT commit=$(git -C "$WT" rev-parse HEAD) GPU $G ${UUID[$G]} inputs_sha256=$(sha256sum "$IN" | cut -d' ' -f1)"

gpu_ok "$G" "vram M1" || { log "STOP GPU $G"; exit 1; }
CUDA_VISIBLE_DEVICES=$G "$HPY" "$TOOL" hf --inputs "$IN" --label M1_hf_bf16_default --out "$OUT/M1_hf_bf16_default.json" > "$OUT/M1_hf_bf16_default.log" 2>&1
log "M1 rc=$?"
gpu_ok "$G" "vram M2" || { log "STOP GPU $G"; exit 1; }
CUDA_VISIBLE_DEVICES=$G PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$HPY" "$TOOL" hf --inputs "$IN" --label M2_hf_bf16_expandable \
  --out "$OUT/M2_hf_bf16_expandable.json" > "$OUT/M2_hf_bf16_expandable.log" 2>&1
log "M2 rc=$?"
export PATH="$VB:$CU/bin:$PATH" CUDA_HOME="$CU" LIBRARY_PATH="/data/hwkim/sftdpo_work/runtime/cuda_link${LIBRARY_PATH:+:$LIBRARY_PATH}"
export VLLM_ENABLE_V1_MULTIPROCESSING=0 VLLM_USE_FLASHINFER_SAMPLER=1
gpu_ok "$G" "vram M3" || { log "STOP GPU $G"; exit 1; }
CUDA_VISIBLE_DEVICES=$G "$VB/python" "$TOOL" vllm --inputs "$IN" --label M3_vllm_bf16_fi_base --out "$OUT/M3_vllm_bf16_fi_base.json" > "$OUT/M3_vllm_bf16_fi_base.log" 2>&1
log "M3 rc=$?"
gpu_ok "$G" "vram M4" || { log "STOP GPU $G"; exit 1; }
CUDA_VISIBLE_DEVICES=$G "$VB/python" "$TOOL" vllm --inputs "$IN" --label M4_vllm_fp8_fi_v4 --fp8 --lora "V4_o101=$V4" \
  --out "$OUT/M4_vllm_fp8_fi_v4.json" > "$OUT/M4_vllm_fp8_fi_v4.log" 2>&1
log "M4 rc=$?"
log "done"
