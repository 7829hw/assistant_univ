#!/usr/bin/env bash
# vLLM 서버(pilot_007 A2, 결정 180·181). serve6b.sh의 사본: gpu_lib7.sh(OLLAMA_UUID·ALLOWED_UUIDS 환경 변수)를 쓰고 기록 위치만 pilot_007/gpu. 나머지(17,408, BF16, flashinfer, LoRA) 그대로.
#   bash serve2.sh GPU_INDEX PORT PRECISION KERNELS
#     PRECISION: bf16 | fp8      (fp8 = vLLM 온라인 FP8 가중치 양자화 --quantization fp8, 같은 BF16 체크포인트에서)
#     KERNELS:   fi | torch      (fi = attention backend FLASHINFER + flashinfer sampler, torch = 자동 선택 attention + PyTorch sampler)
# - base Qwen3-8B@b968826d + pilot_003 최종 adapter를 LoRA "final"로. 요청 로그를 켠다(--enable-log-requests, 원문 로그는 저장소 밖).
# - flashinfer JIT 빌드를 위해 venv bin(ninja), venv의 CUDA 13 툴킷(nvcc)을 PATH에, CUDA_HOME을 그 툴킷으로 둔다.
# - 기동 뒤 서버 로그에서 실제 attention backend와 sampler를 찾아 server_<PORT>.json에 남긴다.
set -u
G=$1; PORT=$2; PREC=$3; KER=$4
source "$(dirname "${BASH_SOURCE[0]}")/gpu_lib7.sh"
P3=/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_007/gpu
WORK=/data/hwkim/sftdpo_work/pilot_006_prep/vllm
ADAPTER=/data/hwkim/sftdpo_work/pilot_003/checkpoints/dpo/checkpoint-174/policy
VPY=/data/hwkim/sftdpo_work/runtime/envs/vllm/bin
CU=/data/hwkim/sftdpo_work/runtime/envs/vllm/lib/python3.12/site-packages/nvidia/cu13
mkdir -p "$WORK"
export PATH="$VPY:$CU/bin:$PATH" CUDA_HOME="$CU"
# flashinfer JIT 링크: pip CUDA 런타임에는 libcudart.so.13만 있어, 저장소·venv 밖 링크 폴더(libcudart.so → .so.13)를 LIBRARY_PATH에 둔다.
export LIBRARY_PATH="/data/hwkim/sftdpo_work/runtime/cuda_link${LIBRARY_PATH:+:$LIBRARY_PATH}"
# LORAS(선택): "이름=경로 이름=경로 ..."(checkpoint 평가). 주지 않으면 pilot_003 최종 하나("final", selection 기준값 셀과 같은 서버 구성).
LORAS=${LORAS:-"final=$ADAPTER"}
read -r -a LORA_LIST <<< "$LORAS"
ARGS=(serve Qwen/Qwen3-8B --revision b968826d9c46dd6066d109eabc6255188de91218 --dtype bfloat16 --max-model-len 17408
      --served-model-name base --enable-lora --lora-modules "${LORA_LIST[@]}" --max-lora-rank 16 --max-loras ${#LORA_LIST[@]}
      --max-logprobs 64 --gpu-memory-utilization 0.85 --generation-config vllm --seed 0 --enable-log-requests
      --host 127.0.0.1 --port "$PORT")
[ "$PREC" = fp8 ] && ARGS+=(--quantization fp8)
if [ "$KER" = fi ]; then ARGS+=(--attention-backend FLASHINFER); export VLLM_USE_FLASHINFER_SAMPLER=1
else export VLLM_USE_FLASHINFER_SAMPLER=0; fi
gpu_ok "$G" "vllm serve $PREC $KER port $PORT" || { echo "GPU $G not usable"; exit 1; }
LOG=$WORK/server_${PORT}_${PREC}_${KER}.log
CUDA_VISIBLE_DEVICES=$G nohup "$VPY/vllm" "${ARGS[@]}" > "$LOG" 2>&1 &
PID=$!
echo $PID > "$WORK/server_$PORT.pid"
p3log "vllm serve start GPU $G (${UUID[$G]}) port $PORT $PREC $KER pid $PID"
ok=0
for i in $(seq 180); do
  curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null && { ok=1; break; }
  kill -0 $PID 2>/dev/null || break
  sleep 5
done
"$VPY/python" - "$WORK/server_$PORT.json" "$G" "${UUID[$G]}" "$PID" "${LORA_LIST[0]#*=}" "$PREC" "$KER" "$LOG" "$ok" "${ARGS[@]}" <<'PYEOF'
import hashlib, json, os, re, sys, vllm, torch, transformers, flashinfer
out, g, uuid, pid, adapter, prec, ker, log, ok, *args = sys.argv[1:]
text = open(log, errors="replace").read()
backend = re.findall(r"Using (?:AttentionBackendEnum\.)?(\S+?)(?: attention)? backend", text)
json.dump({"ready": ok == "1", "precision": prec, "kernels": ker, "gpu_index": g, "gpu_uuid": uuid, "pid": int(pid), "args": args,
           "env": {k: os.environ.get(k) for k in ("VLLM_USE_FLASHINFER_SAMPLER", "CUDA_HOME")},
           "log_attention_backend": sorted(set(backend)),
           "log_flashinfer_sampler_lines": [l.strip()[:200] for l in text.splitlines() if re.search(r"(?i)flashinfer.*(sampl|top-?p|top-?k)", l)][:5],
           "log_quantization_lines": [l.strip()[:200] for l in text.splitlines() if re.search(r"(?i)fp8|quantiz", l)][:8],
           "log_errors": [l.strip()[:300] for l in text.splitlines() if re.search(r"Error|ERROR", l)][:10],
           "vllm": vllm.__version__, "flashinfer": flashinfer.__version__, "torch": torch.__version__, "torch_cuda": torch.version.cuda,
           "transformers": transformers.__version__, "server_log": log, "adapter(first LoRA)": adapter,
           "lora_modules": [a for a in args if "=" in a and not a.startswith("-")],
           "adapter_sha256": hashlib.sha256(open(adapter + "/adapter_model.safetensors", "rb").read()).hexdigest(),
           "lora_adapter_sha256": {a.split("=", 1)[0]: hashlib.sha256(open(a.split("=", 1)[1] + "/adapter_model.safetensors", "rb").read()).hexdigest()
                                   for a in args if "=" in a and not a.startswith("-")}},
          open(out, "w"), indent=1)
PYEOF
if [ $ok = 1 ]; then p3log "vllm serve ready port $PORT $PREC $KER"; exit 0; fi
p3log "STOP: vllm serve failed port $PORT $PREC $KER (log $LOG)"; kill $PID 2>/dev/null; exit 1
