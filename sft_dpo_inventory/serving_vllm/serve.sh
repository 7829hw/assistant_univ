#!/usr/bin/env bash
# vLLM 서버 하나를 띄운다(결정 89). base Qwen3-8B@b968826d BF16 + pilot_003 최종 adapter를 LoRA "final"로 붙인다.
#   bash serve.sh GPU_INDEX PORT    → 서버 PID를 /data/hwkim/sftdpo_work/serving_vllm/server_<PORT>.pid, 기록을 server_<PORT>.json에 남긴다.
# - GPU는 pilot_003 gpu_lib.sh의 gpu_ok로 확인한다(UUID·메모리·다른 프로세스, Ollama GPU는 Ollama 모델이 없을 때만).
# - --generation-config vllm: 모델 generation_config.json의 sampling 기본값을 쓰지 않는다(요청에 준 값만 쓴다).
# - 같은 서버에서 base("base")와 LoRA("final")를 함께 받는다. 셀 비교는 같은 서버 설정끼리 한다.
set -u
G=$1; PORT=$2
source /home/hwkim/assistant_univ/sft_dpo_inventory/pilot_003/gpu_lib.sh
P3=/home/hwkim/assistant_univ/sft_dpo_inventory/serving_vllm   # gpu_lib의 기록 위치(runs.log, gpu_check.txt)를 이 폴더로
WORK=/data/hwkim/sftdpo_work/serving_vllm
ADAPTER=/home/hwkim/sftdpo_work/pilot_003/checkpoints/dpo/checkpoint-174/policy
VPY=/home/hwkim/sftdpo_work/vllmvenv/bin
mkdir -p "$WORK"
# venv bin을 PATH에 둔다(ninja 등). sampler는 vLLM의 PyTorch 구현을 쓴다(flashinfer sampler는 JIT 빌드가 필요해 끈다). 2026-10-14 첫 기동 실패 뒤 추가.
export PATH="$VPY:$PATH" VLLM_USE_FLASHINFER_SAMPLER=0
gpu_ok "$G" "vllm serve port $PORT" || { echo "GPU $G not usable"; exit 1; }
ARGS=(serve Qwen/Qwen3-8B --revision b968826d9c46dd6066d109eabc6255188de91218 --dtype bfloat16 --max-model-len 16384
      --served-model-name base --enable-lora --lora-modules "final=$ADAPTER" --max-lora-rank 16 --max-loras 1
      --max-logprobs 64 --gpu-memory-utilization 0.85 --generation-config vllm --seed 0
      --host 127.0.0.1 --port "$PORT")
CUDA_VISIBLE_DEVICES=$G nohup "$VPY/vllm" "${ARGS[@]}" > "$WORK/server_$PORT.log" 2>&1 &
PID=$!
echo $PID > "$WORK/server_$PORT.pid"
"$VPY/python" - "$WORK/server_$PORT.json" "$G" "${UUID[$G]}" "$PID" "$ADAPTER" "${ARGS[@]}" <<'PYEOF'
import hashlib, json, sys, vllm, torch, transformers
out, g, uuid, pid, adapter, *args = sys.argv[1:]
import os
json.dump({"env": {"VLLM_USE_FLASHINFER_SAMPLER": os.environ.get("VLLM_USE_FLASHINFER_SAMPLER")}, "gpu_index": g, "gpu_uuid": uuid, "pid": int(pid), "args": args, "vllm": vllm.__version__, "torch": torch.__version__,
           "torch_cuda": torch.version.cuda, "transformers": transformers.__version__,
           "adapter": adapter, "adapter_sha256": hashlib.sha256(open(adapter + "/adapter_model.safetensors", "rb").read()).hexdigest()},
          open(out, "w"), indent=1)
PYEOF
p3log "vllm serve start GPU $G (${UUID[$G]}) port $PORT pid $PID"
for i in $(seq 120); do
  curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null && { p3log "vllm serve ready port $PORT"; exit 0; }
  kill -0 $PID 2>/dev/null || { p3log "STOP: vllm serve died port $PORT"; exit 1; }
  sleep 5
done
p3log "STOP: vllm serve not ready in 10 min port $PORT"; exit 1
