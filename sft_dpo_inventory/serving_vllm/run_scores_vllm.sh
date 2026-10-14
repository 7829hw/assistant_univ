#!/usr/bin/env bash
# serving_vllm vLLM token 확률 채점(결정 89). run_scores.sh의 vLLM 부분이 flashinfer sampler JIT(ninja 없음)로 멈춰, 서버와 같은 환경
# (venv bin을 PATH에, VLLM_USE_FLASHINFER_SAMPLER=0)으로 vLLM 부분만 다시 돈다. HF 부분(hf_final_p3)은 run_scores.sh에서 끝났다.
#   bash run_scores_vllm.sh GPU_INDEX
set -u
G=$1
source /home/hwkim/assistant_univ/sft_dpo_inventory/pilot_003/gpu_lib.sh
P3=/home/hwkim/assistant_univ/sft_dpo_inventory/serving_vllm
cd /home/hwkim/assistant_univ/sft_dpo_inventory/serving_vllm
OUT=/data/hwkim/sftdpo_work/serving_vllm/scores
VPY=/home/hwkim/sftdpo_work/vllmvenv/bin
export PATH="$VPY:$PATH" VLLM_USE_FLASHINFER_SAMPLER=0
for m in base final; do
  [ -e $OUT/vllm_$m.log ] && mv $OUT/vllm_$m.log $OUT/ABORTED_vllm_$m.log
  rm -f $OUT/vllm_$m.bin
  gpu_ok $G "scores vllm $m" || { p3log "STOP: GPU $G busy before vllm $m"; exit 1; }
  CUDA_VISIBLE_DEVICES=$G $VPY/python score_vllm.py $m $OUT/vllm_$m.bin > $OUT/vllm_$m.log 2>&1 || { p3log "STOP: vllm $m score failed"; exit 1; }
  p3log "score vllm_$m done"
done
sha256sum $OUT/*.bin /data/hwkim/sftdpo_work/logprob_diag/scores/hf_base.bin >> $P3/runs.log
p3log "vllm scores done"
