#!/usr/bin/env bash
# 장치 일치 확인 2차(결정 268). 1차(run.sh, try1/)는 한 서버에 base·V4_o101 셀을 동시에 보내 배치 구성이 GPU마다 달라질 수 있어 장치 비교로 무효.
# 바꾼 것: 서버마다 요청을 한 번에 하나만(셀 차례로, 동시 1) 보내고, 같은 GPU 대조(기준 GPU에서 같은 셀 두 번: ref·ref2)를 둔다.
# 판정: 새 GPU가 ref와 바이트 단위로 같으면 사용. 다르면(ref·ref2가 같든 다르든) 새 GPU는 쓰지 않는다(지시 2절).
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
(cd "$WT" && bash sft_dpo_inventory/ablation_011/gpu/serve_a11.sh "$REF" 8660 bf16 fi) || exit 1
(cd "$WT" && bash sft_dpo_inventory/ablation_011/gpu/serve_a11.sh "$NEW" 8662 bf16 fi) || exit 1
cell() { (cd "$WT" && "$PY" sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py --port "$2" --model "$3" --label "dc_$1_$3" --k 1 --concurrency 1 \
           --grounding-target full --out-dir "$HERE" --raw-dir "$HERE/raw" --seed-base 20261100 --gold sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml --only "$ONLY"); }
( cell ref 8660 base && cell ref 8660 V4_o101 && cell ref2 8660 base && cell ref2 8660 V4_o101 ) &
( cell new 8662 base && cell new 8662 V4_o101 ) &
wait
for port in 8660 8662; do kill "$(cat $WORK/server_$port.pid)" 2>/dev/null; done
sleep 20
"$PY" "$HERE/compare2.py"
