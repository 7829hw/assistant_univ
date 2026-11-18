#!/usr/bin/env bash
# pilot_010 사후 측정(결정 268) 장치 일치 확인(결정 83 방식, vLLM 경로): 기준 GPU(2445b100, 판정 단계 J 셀을 잰 GPU)와 새 GPU(c8f1bae2)에서
# 같은 서버 구성(serve_a11.sh, BF16, flashinfer, LoRA V4_o101)으로 valid98 앞 5문항을 base·V4_o101 각각 k=1(회차 seed 20261101), 동시 1로 재고
# 호출별 원문 sha256·생성 token 수를 compare.py로 비교한다. 출력은 이 디렉터리(셀)와 raw/(원문).
#   bash run.sh <WT>   (WT = 커밋 고정 worktree)
set -u
WT=$1
HERE=$(cd "$(dirname "$0")" && pwd)
PY=/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python
export OLLAMA_UUID=GPU-48f798cc-9437-50ac-d604-448bbad7b311
export ALLOWED_UUIDS="GPU-2445b100-70d8-e384-3a24-0249eeefc64d GPU-c8f1bae2-de7a-a1c0-a054-8b6ebe5c2c8e"
export P3=$HERE MAX_LORA_RANK=16 LORAS="V4_o101=/data/hwkim/sftdpo_work/pilot_010/train_j/J-V4-o101/checkpoint-1984"
idx() { nvidia-smi --query-gpu=index,uuid --format=csv,noheader | awk -F', ' -v u="$1" '$2==u{print $1}'; }
REF=$(idx GPU-2445b100-70d8-e384-3a24-0249eeefc64d); NEW=$(idx GPU-c8f1bae2-de7a-a1c0-a054-8b6ebe5c2c8e)
ONLY=stage_v7/s01a,stage_v7/s01b,stage_v7/s01c,stage_v7/s01d,stage_v7/s02a
WORK=/data/hwkim/sftdpo_work/pilot_006_prep/vllm
mkdir -p "$HERE/raw"
for pair in "ref:$REF:8660" "new:$NEW:8662"; do
  IFS=: read -r tag g port <<< "$pair"
  (cd "$WT" && bash sft_dpo_inventory/ablation_011/gpu/serve_a11.sh "$g" "$port" bf16 fi) || { echo "serve failed $tag"; exit 1; }
done
for pair in "ref:8660" "new:8662"; do
  IFS=: read -r tag port <<< "$pair"
  for m in base V4_o101; do
    (cd "$WT" && "$PY" sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py --port "$port" --model "$m" --label "dc_${tag}_${m}" --k 1 --concurrency 1 \
       --grounding-target full --out-dir "$HERE" --raw-dir "$HERE/raw" --seed-base 20261100 --gold sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml --only "$ONLY") &
  done
done
wait
for port in 8660 8662; do kill "$(cat $WORK/server_$port.pid)" 2>/dev/null; done
sleep 20
"$PY" "$HERE/compare.py"
