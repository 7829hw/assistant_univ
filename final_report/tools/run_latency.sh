#!/usr/bin/env bash
# 최종 결과보고서 지연 자체시험 실행기(새 파일). 커밋에 고정한 worktree에서 실행한다. GPU 한 장(인자 G)에서 다섯 셀을 차례로 잰다.
#   bash run_latency.sh G
# 셀(모두 같은 고정 30문항 sft_dpo_inventory/serving_vllm_fp8/latency_ids.txt, 동시 1, S sampling, 회차 seed 20261101, 워밍업 3문항 제외):
#   A  HF transformers BF16 + SDPA, base Qwen3-8B@b968826d               (초기 모델·초기 실행환경)
#   B  vLLM 0.30.0 BF16 + FlashInfer, base                               (실행환경만 최적화)
#   D  vLLM 0.30.0 BF16 + FlashInfer, base + LoRA V4(RR+NM4) o101        (실행환경 + 경량 학습 모델)
#   C  vLLM 0.30.0 FP8(online) + FlashInfer, base                         (실행환경 + FP8)
#   E  vLLM 0.30.0 FP8(online) + FlashInfer, base + LoRA V4 o101          (최종 최적화 구성)
set -u
G=$1
WT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
MAIN=/home/hwkim/assistant_univ
OUT=$MAIN/final_report/logs/latency
RAW=$OUT/raw
mkdir -p "$OUT" "$RAW"
export P3=$OUT OLLAMA_UUID=GPU-48f798cc-9437-50ac-d604-448bbad7b311
export ALLOWED_UUIDS="$(nvidia-smi --query-gpu=uuid --format=csv,noheader | tr '\n' ' ')"
source "$WT/sft_dpo_inventory/pilot_007/gpu_data/gpu_lib7.sh"
unset PYTORCH_CUDA_ALLOC_CONF   # 초기 환경(HF 셀)은 allocator 기본값. vLLM 서버도 기본값.
PY=/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python
TOOL=$WT/final_report/tools/latency_e2e.py
WARM=old44/g02,old44/g03,old44/g04
V4=/data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o101/checkpoint-1984
V4_SHA=6402ba63352e1f21591a1625c9bcf0635211d2ea0d3d2870c22d3e50343d9a1d
WORK=/data/hwkim/sftdpo_work/pilot_006_prep/vllm
PORT=8810
log() { echo "== $1 $(date -Is)" | tee -a "$OUT/runs.log"; }

obs=$(sha256sum "$V4/adapter_model.safetensors" | cut -d' ' -f1)
[ "$obs" = "$V4_SHA" ] || { log "STOP adapter sha256 mismatch $obs"; exit 1; }
log "start worktree=$WT commit=$(git -C "$WT" rev-parse HEAD) GPU $G ${UUID[$G]} adapter_sha=$obs"

gpu_ok "$G" "latency A hf" || { log "STOP GPU $G not usable"; exit 1; }
log "cell A start"
CUDA_VISIBLE_DEVICES=$G "$PY" "$TOOL" --backend hf --label A_hf_bf16_base --warmup-ids "$WARM" \
  --out "$OUT/A_hf_bf16_base.json" --raw-out "$RAW/A_hf_bf16_base_raw.jsonl" > "$OUT/A_hf_bf16_base.log" 2>&1
log "cell A rc=$?"

serve() {  # PREC
  local t0=$(date +%s.%N)
  LORAS="V4_o101=$V4" MAX_LORA_RANK=16 bash "$WT/sft_dpo_inventory/ablation_011/gpu/serve_a11.sh" "$G" "$PORT" "$1" fi >> "$OUT/serve_$1.out" 2>&1
  local rc=$?
  local t1=$(date +%s.%N)
  cp "$WORK/server_$PORT.json" "$OUT/server_$1.json"
  log "server $1 rc=$rc startup_seconds=$(echo "$t1 - $t0" | bc)"
  return $rc
}
stop() {
  local pid=$(cat "$WORK/server_$PORT.pid")
  kill "$pid"; for i in $(seq 120); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
  for i in $(seq 60); do [ "$(nvidia-smi -i ${UUID[$G]} --query-compute-apps=pid --format=csv,noheader | wc -l)" = 0 ] && break; sleep 2; done
  cp "$WORK/server_${PORT}_$1_fi.log" "$OUT/server_$1_fi.log" 2>/dev/null
  log "server $1 stopped procs_left=$(nvidia-smi -i ${UUID[$G]} --query-compute-apps=pid --format=csv,noheader | wc -l)"
}
cell() {  # LABEL MODEL PREC
  log "cell $1 start"
  "$PY" "$TOOL" --backend vllm --base-url "http://127.0.0.1:$PORT" --served-model "$2" --label "$1" --warmup-ids "$WARM" \
    --server-meta "$OUT/server_$3.json" --out "$OUT/$1.json" --raw-out "$RAW/$1_raw.jsonl" > "$OUT/$1.log" 2>&1
  log "cell $1 rc=$?"
}
for PREC in bf16 fp8; do
  serve "$PREC" || { log "STOP server $PREC failed"; exit 1; }
  if [ "$PREC" = bf16 ]; then cell B_vllm_bf16_fi_base base bf16; cell D_vllm_bf16_fi_v4 V4_o101 bf16
  else cell C_vllm_fp8_fi_base base fp8; cell E_vllm_fp8_fi_v4 V4_o101 fp8; fi
  stop "$PREC"
done
log "done"
