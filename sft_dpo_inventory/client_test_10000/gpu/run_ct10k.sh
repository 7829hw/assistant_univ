#!/usr/bin/env bash
# client_test_10000(사용자 지시 2026-10-29): pilot_010 선택 변형 V4 adapter 하나를 GPU 하나에서 10,000문항 k=1로 잰다(작업 하나 = GPU 하나, 결정 114).
#   bash run_ct10k.sh SEED GPU_INDEX PORT      (SEED: o43 | o1016 | o7)
# - 고정 worktree(이 파일이 있는 커밋)에서 돌린다. 서버 = pilot_007/gpu_data/serve7.sh(BF16 base Qwen3-8B@b968826d + LoRA, flashinfer, gpu_ok 확인),
#   셀 = pilot_006_prep/gpu_data/run_cell6x.py(pilot_010 셀과 같은 client·sampler·seed-base 20261100, k=1 → 회차 seed 20261101).
# - 문항은 chunks/c1–c5(각 2,000, 문항 파일 순서)로 나눠 묶음마다 셀 파일 하나를 쓴다. 이미 있는 묶음은 건너뛴다(중간 실패 뒤 이어 돌리기).
# - 동시 요청 32(pilot_010 셀은 8). 끝나면 서버를 내리고 timeline.jsonl에 한 줄 남긴다.
set -u
SEED=$1; G=$2; PORT=$3
WT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
MAIN=/home/hwkim/assistant_univ
D=$MAIN/sft_dpo_inventory/client_test_10000
CH=$WT/sft_dpo_inventory/client_test_10000/gpu/chunks
PY=/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python
WORK=/data/hwkim/sftdpo_work/pilot_006_prep/vllm
NAME=V4_$SEED
export P3=$D/gpu OLLAMA_UUID=GPU-48f798cc-9437-50ac-d604-448bbad7b311
export ALLOWED_UUIDS="GPU-2445b100-70d8-e384-3a24-0249eeefc64d GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555 GPU-48f798cc-9437-50ac-d604-448bbad7b311"
export LORAS="$NAME=/data/hwkim/sftdpo_work/pilot_010/train_s10/S-V4-$SEED/checkpoint-1984"
export HF_HOME=/data/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
COMMIT=$(git -C "$WT" rev-parse HEAD)
UUIDG=$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader | awk -F', ' -v g="$G" '$1==g{print $2}')
START=$(date -Iseconds)
echo "== CT10K-$SEED start GPU $G $UUIDG port $PORT commit $COMMIT $START" >> "$D/gpu/runs.log"
bash "$WT/sft_dpo_inventory/pilot_007/gpu_data/serve7.sh" "$G" "$PORT" bf16 fi || { echo "== CT10K-$SEED STOP server start failed $(date -Iseconds)" >> "$D/gpu/runs.log"; exit 1; }
SPID=$(cat "$WORK/server_$PORT.pid")
cp "$WORK/server_$PORT.json" "$D/gpu/server_CT10K-$SEED.json"
status=ok
for c in 1 2 3 4 5; do
  label=ct10k_v4_${SEED}_c$c
  [ -e "$D/cells/${label}_s1.json" ] && { echo "== CT10K-$SEED c$c exists, skip $(date -Iseconds)" >> "$D/gpu/runs.log"; continue; }
  echo "== CT10K-$SEED c$c start $(date -Iseconds)" >> "$D/gpu/runs.log"
  if ! (cd "$WT" && "$PY" "$WT/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py" --port "$PORT" --model "$NAME" --label "$label" --k 1 \
        --concurrency 32 --grounding-target full --seed-base 20261100 --gold sft_dpo_inventory/client_test_10000/qa_test_10000.yaml \
        --only "$(cat "$CH/c$c.txt")" --out-dir "$D/cells" --raw-dir "$MAIN/training/generated/client_test_10000/raw"); then
    status=failed; echo "== CT10K-$SEED c$c FAILED $(date -Iseconds)" >> "$D/gpu/runs.log"; break
  fi
  echo "== CT10K-$SEED c$c done $(date -Iseconds)" >> "$D/gpu/runs.log"
done
kill "$SPID" 2>/dev/null; for i in $(seq 60); do kill -0 "$SPID" 2>/dev/null || break; sleep 2; done
rm -f "$WORK/server_$PORT.pid"
"$PY" "$WT/sft_dpo_inventory/pilot_006_prep/gpu_data/timeline.py" --file "$D/gpu/timeline.jsonl" --id "CT10K-$SEED" --kind client_test_10000_k1 \
  --uuid "$UUIDG" --commit "$COMMIT" --start "$START" --end "$(date -Iseconds)" --status "$status" --note "server lora:$LORAS; concurrency 32" \
  --out $(for c in 1 2 3 4 5; do echo "$D/cells/ct10k_v4_${SEED}_c${c}_s1.json"; done)
echo "== CT10K-$SEED end $status $(date -Iseconds)" >> "$D/gpu/runs.log"
[ "$status" = ok ]
