#!/usr/bin/env bash
# serving_vllm token 확률 채점(결정 89): logprob_diag 기준 응답 60개를 HF(pilot_003 최종 adapter)·vLLM(base, final)으로 채점한다. 생성 없음.
#   bash run_scores.sh GPU_INDEX     (Ollama GPU면 Ollama 모델이 내려갈 때까지 최대 30분 기다린다. 그 GPU에서 Ollama 측정 중에는 돌리지 않는다)
# HF base 값은 logprob_diag의 hf_base.bin(같은 base·같은 id열)을 그대로 쓴다.
set -u
G=$1
source /home/hwkim/assistant_univ/sft_dpo_inventory/pilot_003/gpu_lib.sh
P3=/home/hwkim/assistant_univ/sft_dpo_inventory/serving_vllm
cd /home/hwkim/assistant_univ/sft_dpo_inventory/serving_vllm
OUT=/data/hwkim/sftdpo_work/serving_vllm/scores
mkdir -p $OUT
for i in $(seq 60); do gpu_ok $G "scores" && break; [ $i = 60 ] && { p3log "STOP: GPU $G not usable for scores"; exit 1; }; sleep 30; done
p3log "scores start GPU $G (${UUID[$G]})"
CUDA_VISIBLE_DEVICES=$G $PY score_hf_p3.py hf_final_peft $OUT/hf_final_p3.bin > $OUT/hf_final_p3.log 2>&1 || { p3log "STOP: hf_final_p3 score failed"; exit 1; }
p3log "score hf_final_p3 done"
for m in base final; do
  gpu_ok $G "scores vllm $m" || { p3log "STOP: GPU $G busy before vllm $m"; exit 1; }
  CUDA_VISIBLE_DEVICES=$G /home/hwkim/sftdpo_work/vllmvenv/bin/python score_vllm.py $m $OUT/vllm_$m.bin > $OUT/vllm_$m.log 2>&1 \
    || { p3log "STOP: vllm $m score failed"; exit 1; }
  p3log "score vllm_$m done"
done
sha256sum $OUT/*.bin /data/hwkim/sftdpo_work/logprob_diag/scores/hf_base.bin >> $P3/runs.log
p3log "scores done"
