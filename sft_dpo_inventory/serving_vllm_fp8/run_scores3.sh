#!/usr/bin/env bash
# run_scores2.sh의 다음 판(그 파일은 고치지 않는다). flashinfer를 켠 vLLM 오프라인 엔진은 채점을 다 끝낸 뒤 종료 단계에서
# "terminate called without an active exception"으로 0이 아닌 코드로 끝난다(2026-10-14 bf16 base). 그래서 완료는 종료 코드가 아니라
# 출력으로 판단한다: log에 "seq 59"와 "device" 줄이 있고 .bin이 60개 시퀀스를 담으면 완료. 종료 코드는 runs.log에 남긴다.
# 이미 완료된 출력은 다시 재지 않는다.
#   bash run_scores3.sh GPU_INDEX
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
complete() {   # name
  grep -q "^seq 59 " $OUT/$1.log 2>/dev/null && grep -q "^device " $OUT/$1.log && \
  /home/hwkim/sftdpo_work/hfvenv/bin/python -c "
import sys; sys.path.insert(0, '/home/hwkim/assistant_univ/sft_dpo_inventory/logprob_diag'); import analyze_logprob as L
from pathlib import Path; sys.exit(0 if len(L.read(Path('$OUT/$1.bin'))) == 60 else 1)"
}
for prec in bf16 fp8; do
  for m in base final; do
    n=${prec}_fi_$m
    if complete $n; then p3log "scores3 $n already complete (kept)"; continue; fi
    [ -e $OUT/$n.bin ] && mv $OUT/$n.bin $OUT/ABORTED_$n.bin && mv $OUT/$n.log $OUT/ABORTED_$n.log
    gpu_ok $G "scores3 $prec $m" || { p3log "STOP: GPU $G busy before scores3 $n"; exit 1; }
    CUDA_VISIBLE_DEVICES=$G $VPY/python score_vllm2.py $m $prec fi $OUT/$n.bin > $OUT/$n.log 2>&1
    rc=$?
    complete $n || { p3log "STOP: scores3 $n incomplete (exit $rc)"; exit 1; }
    p3log "scores3 $n done (exit $rc$( [ $rc -ne 0 ] && echo ', shutdown crash after completion'))"
  done
done
for n in bf16_fi_base bf16_fi_final fp8_fi_base fp8_fi_final; do grep -m2 -E "AttentionBackendEnum|FlashInfer for top|Fp8|CutlassFP8" $OUT/$n.log | sed "s/^/   $n: /" | cut -c1-200 >> $P3/runs.log; done
sha256sum $OUT/*_fi_*.bin >> $P3/runs.log
p3log "scores3 done"
