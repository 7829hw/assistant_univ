#!/usr/bin/env bash
# client_test_10000 base(사용자 지시 2026-10-29, 결정 260): 파인튜닝하지 않은 base Qwen3-8B@b968826d를 GPU 하나에서 10,000문항 sampling 회차 하나(k)로 잰다.
#   bash run_ct10k_base.sh K GPU_INDEX PORT      (K: 1 | 2 | 3 → 회차 seed 20261100+K)
# - run_ct10k.sh(V4)와 같은 client·sampler·묶음(chunks/c1–c5)·동시 요청 32. 다른 것: 서버 모델 이름 base(LoRA 없이 요청),
#   서버 = serve_ct10k.sh(serve7.sh 사본, 기록 위치 P3를 이 디렉터리로). 서버의 LoRA 자리에는 serve7 기본값(pilot_003 final)이 올라가지만 요청에 쓰지 않는다.
set -u
K=$1; G=$2; PORT=$3
WT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
MAIN=/home/hwkim/assistant_univ
D=$MAIN/sft_dpo_inventory/client_test_10000
CH=$WT/sft_dpo_inventory/client_test_10000/gpu/chunks
PY=/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python
WORK=/data/hwkim/sftdpo_work/pilot_006_prep/vllm
JOB=CT10K-base-k$K
export P3=$D/gpu OLLAMA_UUID=GPU-48f798cc-9437-50ac-d604-448bbad7b311
export ALLOWED_UUIDS="GPU-2445b100-70d8-e384-3a24-0249eeefc64d GPU-a5ce83d0-6ca2-5e3a-276c-4c965ea9c555 GPU-48f798cc-9437-50ac-d604-448bbad7b311"
export HF_HOME=/data/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
COMMIT=$(git -C "$WT" rev-parse HEAD)
UUIDG=$(nvidia-smi --query-gpu=index,uuid --format=csv,noheader | awk -F', ' -v g="$G" '$1==g{print $2}')
START=$(date -Iseconds)
echo "== $JOB start GPU $G $UUIDG port $PORT commit $COMMIT $START" >> "$D/gpu/runs.log"
bash "$WT/sft_dpo_inventory/client_test_10000/gpu/serve_ct10k.sh" "$G" "$PORT" bf16 fi || { echo "== $JOB STOP server start failed $(date -Iseconds)" >> "$D/gpu/runs.log"; exit 1; }
SPID=$(cat "$WORK/server_$PORT.pid")
cp "$WORK/server_$PORT.json" "$D/gpu/server_$JOB.json"
status=ok
for c in 1 2 3 4 5; do
  label=ct10k_base_c$c
  [ -e "$D/cells/${label}_s$K.json" ] && { echo "== $JOB c$c exists, skip $(date -Iseconds)" >> "$D/gpu/runs.log"; continue; }
  echo "== $JOB c$c start $(date -Iseconds)" >> "$D/gpu/runs.log"
  if ! (cd "$WT" && "$PY" "$WT/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py" --port "$PORT" --model base --label "$label" --k "$K" \
        --concurrency 32 --grounding-target full --seed-base 20261100 --gold sft_dpo_inventory/client_test_10000/qa_test_10000.yaml \
        --only "$(cat "$CH/c$c.txt")" --out-dir "$D/cells" --raw-dir "$MAIN/training/generated/client_test_10000/raw"); then
    status=failed; echo "== $JOB c$c FAILED $(date -Iseconds)" >> "$D/gpu/runs.log"; break
  fi
  echo "== $JOB c$c done $(date -Iseconds)" >> "$D/gpu/runs.log"
done
kill "$SPID" 2>/dev/null; for i in $(seq 60); do kill -0 "$SPID" 2>/dev/null || break; sleep 2; done
rm -f "$WORK/server_$PORT.pid"
"$PY" "$WT/sft_dpo_inventory/pilot_006_prep/gpu_data/timeline.py" --file "$D/gpu/timeline.jsonl" --id "$JOB" --kind client_test_10000_base \
  --uuid "$UUIDG" --commit "$COMMIT" --start "$START" --end "$(date -Iseconds)" --status "$status" --note "server base (no LoRA in requests); k=$K; concurrency 32" \
  --out $(for c in 1 2 3 4 5; do echo "$D/cells/ct10k_base_c${c}_s$K.json"; done)
echo "== $JOB end $status $(date -Iseconds)" >> "$D/gpu/runs.log"
[ "$status" = ok ]
