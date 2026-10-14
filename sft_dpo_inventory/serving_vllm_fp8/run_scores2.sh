#!/usr/bin/env bash
# serving_vllm_fp8 token 확률 채점: logprob_diag 기준 응답 60개를 vLLM {bf16, fp8} × {base, final}로, 커널 fi(flashinfer)로 채점한다. 생성 없음.
#   bash run_scores2.sh GPU_INDEX
# HF 기준값은 logprob_diag hf_base.bin, serving_vllm hf_final_p3.bin(같은 id열)을 그대로 쓴다. 환경은 serve2.sh와 같다.
set -u
G=$1
source /home/hwkim/assistant_univ/sft_dpo_inventory/pilot_003/gpu_lib.sh
P3=/home/hwkim/assistant_univ/sft_dpo_inventory/serving_vllm_fp8
cd "$P3"
OUT=/data/hwkim/sftdpo_work/serving_vllm_fp8/scores
VPY=/home/hwkim/sftdpo_work/vllmvenv/bin
CU=/home/hwkim/sftdpo_work/vllmvenv/lib/python3.12/site-packages/nvidia/cu13
export PATH="$VPY:$CU/bin:$PATH" CUDA_HOME="$CU" VLLM_USE_FLASHINFER_SAMPLER=1
export LIBRARY_PATH="/home/hwkim/sftdpo_work/cuda_link${LIBRARY_PATH:+:$LIBRARY_PATH}"
mkdir -p $OUT
for prec in bf16 fp8; do
  for m in base final; do
    [ -e $OUT/${prec}_fi_$m.bin ] && { p3log "STOP: $OUT/${prec}_fi_$m.bin exists"; exit 1; }
    gpu_ok $G "scores2 $prec $m" || { p3log "STOP: GPU $G busy before scores2 $prec $m"; exit 1; }
    CUDA_VISIBLE_DEVICES=$G $VPY/python score_vllm2.py $m $prec fi $OUT/${prec}_fi_$m.bin > $OUT/${prec}_fi_$m.log 2>&1 \
      || { p3log "STOP: scores2 $prec $m failed"; exit 1; }
    grep -m2 -E "AttentionBackendEnum|FlashInfer for top" $OUT/${prec}_fi_$m.log | sed 's/^/   /' >> $P3/runs.log
    p3log "scores2 ${prec}_fi_$m done"
  done
done
sha256sum $OUT/*.bin >> $P3/runs.log
p3log "scores2 done"
