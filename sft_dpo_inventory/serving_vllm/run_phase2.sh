#!/usr/bin/env bash
# serving_vllm 2단계(결정 89): selection_v2 sampling 셀 vLLM-base·vLLM-최종, k=4(seed 20261100+k, calibration_001 설정).
#   bash run_phase2.sh free     # 1단계에서 GPU 사이 원문이 같았을 때: 표본 k를 서버 A·B에 나눈다(두 셀의 같은 k는 같은 서버)
#   bash run_phase2.sh pinned   # 다를 때: 두 셀의 모든 표본을 서버 A 하나에서 잰다
# 서버마다 한 번에 요청 하나(문항 순서대로)라 지연은 단일 요청 지연이다. 셀마다 커밋한다. 출력이 있으면 멈춘다.
set -u
MODE=$1
cd /home/hwkim/assistant_univ
SV=sft_dpo_inventory/serving_vllm
WORK=/data/hwkim/sftdpo_work/serving_vllm
RAW=training/generated/serving_vllm/raw
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
GOLD=sft_dpo_inventory/conversion_diag/selection_gold.yaml
IDS=$(cat sft_dpo_inventory/pilot_003/selection/selection_v2_ids.txt)
SAMPLING="--do-sample --temperature 0.6 --top-p 0.95 --top-k 20 --min-p 0 --repetition-penalty 1"
mkdir -p $SV/runs $RAW
log() { echo "== $1 $(date -Is)" >> "$SV/runs.log"; }
die() { log "STOP: $1"; exit 1; }
sample() {   # model k port
  local label=vllm-$1 p=$SV/runs/vllm-$1_s$2
  [ -e $p.json ] && { log "STOP: $p.json exists"; return 1; }
  log "cell $label s$2 start port $3"
  "$PY" $SV/vllm_eval_thinking.py --base-url http://127.0.0.1:$3 --served-model $1 --gold $GOLD --only "$IDS" --condition-check \
    $SAMPLING --seed $((20261100 + $2)) --server-meta $WORK/server_$3.json --out $p.json --raw-out $RAW/vllm-$1_s$2_raw.jsonl > $p.log 2>&1
  local rc=$?; log "cell $label s$2 exit=$rc port $3"; return $rc
}
queue() {   # port "model:k ..."
  local port=$1 job
  for job in $2; do sample ${job%%:*} ${job##*:} $port || return 1; done
}
for port in 8100 8101; do curl -sf http://127.0.0.1:$port/v1/models >/dev/null || die "server $port not up"; done
if [ "$MODE" = free ]; then
  queue 8100 "base:1 final:1 base:3 final:3" & PA=$!
  queue 8101 "base:2 final:2 base:4 final:4" & PB=$!
  wait $PA; ra=$?; wait $PB; rb=$?
  [ $ra -eq 0 ] && [ $rb -eq 0 ] || die "a sample failed (A=$ra B=$rb)"
else
  queue 8100 "base:1 final:1 base:2 final:2 base:3 final:3 base:4 final:4" || die "a sample failed"
fi
for m in base final; do
  git add $SV/runs/vllm-${m}_s* $SV/runs.log
  git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "eval(serving_vllm): selection_v2 셀 vLLM-$m(k=4, $MODE)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" || die "commit failed"
  git push -q origin geoflow/sft-dpo-t2pc >> $SV/runs.log 2>&1 || log "push rejected"
done
log "phase2 done ($MODE)"
