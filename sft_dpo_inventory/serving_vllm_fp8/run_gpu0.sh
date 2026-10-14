#!/usr/bin/env bash
# serving_vllm_fp8 GPU 0 측정(결정 90·91·93). 짝 비교의 셀을 모두 GPU 0 한 장에서 잰다(결정 83 장치 규칙: vLLM은 seed 재현이 안 된다).
#   1) BF16 서버(포트 8200, flashinfer)에서 정답률 셀 vllm-bf16-base·final, k=4, 동시 요청 8
#   2) 서버를 FP8(flashinfer)로 바꿔 vllm-fp8-base·final, k=4, 동시 요청 8
#   3) 지연: 고정 30문항(latency_ids.txt, seed 20261014로 고름)을 동시 요청 없이 1표본(seed 20261101)씩. FP8 base·final → BF16 base·final
# 셀마다 커밋한다. 실패하면 멈춘다.
set -u
cd /home/hwkim/assistant_univ
FP=sft_dpo_inventory/serving_vllm_fp8
WORK=/data/hwkim/sftdpo_work/serving_vllm_fp8
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
C=8
log() { echo "== $1 $(date -Is)" >> "$FP/runs.log"; }
die() { log "STOP: $1"; exit 1; }
commit() {
  git add "$@" $FP/runs.log $FP/gpu_check.txt 2>/dev/null
  git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "$CMSG

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" || die "commit failed"
  git push -q origin geoflow/sft-dpo-t2pc >> $FP/runs.log 2>&1 || log "push rejected"
}
cell() {   # label model k concurrency [only] [outdir]
  log "cell $1 s$3 start (C=$4)"
  "$PY" $FP/run_cell.py --port 8200 --model $2 --label $1 --k $3 --concurrency $4 ${5:+--only $5} ${6:+--out-dir $6} >> $FP/runs.log 2>&1 || die "cell $1 s$3 failed"
  log "cell $1 s$3 done"
}
swap() {   # precision
  local pid; pid=$(cat $WORK/server_8200.pid); kill $pid; for i in $(seq 60); do kill -0 $pid 2>/dev/null || break; sleep 2; done
  sleep 5
  bash $FP/serve2.sh 0 8200 $1 fi || die "server $1 failed"
  cp $WORK/server_8200.json $WORK/server_8200_$1.json
}
[ "$("$PY" -c 'import execution_spec as e;print(e.code_fingerprint(".")["sha256"][:8])')" = 791c4a68 ] || die "fingerprint mismatch"
"$PY" -c "import json,sys; d=json.load(open('$WORK/server_8200.json')); sys.exit(0 if d['precision']=='bf16' and d['ready'] and d['log_attention_backend']==['FLASHINFER'] else 1)" || die "server 8200 is not bf16 flashinfer"
cp $WORK/server_8200.json $WORK/server_8200_bf16.json
for prec in bf16 fp8; do
  [ $prec = fp8 ] && swap fp8
  for k in 1 2 3 4; do
    for m in base final; do cell vllm-$prec-$m $m $k $C; done
  done
  for m in base final; do CMSG="eval(serving_vllm_fp8): selection_v2 셀 vllm-$prec-$m(k=4, 동시 요청 $C, flashinfer)"; commit $FP/runs/vllm-$prec-${m}_s*; done
done
LAT=$(cat $FP/latency_ids.txt)
for prec in fp8 bf16; do
  [ $prec = bf16 ] && swap bf16
  for m in base final; do cell lat-vllm-$prec-$m $m 1 1 "$LAT" $FP/latency; done
done
CMSG="eval(serving_vllm_fp8): 지연 순차 측정(고정 30문항, BF16·FP8 × base·final)"; commit $FP/latency
log "gpu0 done"
