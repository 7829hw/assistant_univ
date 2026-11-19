#!/usr/bin/env bash
# pilot_010 JT(결정 271, PLAN_JT 3절) 교사 27B vLLM 서버: ``ablation_011/gpu/serve_a11.sh``(그대로 둠)의 사본(규칙 15).
# 바꾼 것: GPU 두 장(tensor parallel 2, 결정 114 예외 — 이 작업의 27B 서빙에 한함), 모델 = Qwen/Qwen3.8-27B(revision 37561816…) 로컬 사본,
#   --served-model-name teacher27, --language-model-only(이미지 입력 없음), LoRA 없음. 나머지(BF16, 17,408, flashinfer attention·sampler,
#   --gpu-memory-utilization 0.85, --generation-config vllm, --seed 0, --max-logprobs 64, 요청 로그, gpu_ok 확인)는 같다.
#   bash serve27.sh GPU_A GPU_B PORT        (환경 변수 ATTN=auto면 --attention-backend를 주지 않음: FLASHINFER 기동 실패 때 한 번만, PLAN_JT 7절)
set -u
GA=$1; GB=$2; PORT=$3
source "$(dirname "${BASH_SOURCE[0]}")/../../pilot_007/gpu_data/gpu_lib7.sh"
P3=${P3:?P3 must be set}
WORK=/data/hwkim/sftdpo_work/pilot_010_jt/vllm
MODEL=/data/hwkim/sftdpo_work/pilot_010_jt/model/Qwen3.8-27B
VPY=/data/hwkim/sftdpo_work/runtime/envs/vllm/bin
CU=/data/hwkim/sftdpo_work/runtime/envs/vllm/lib/python3.12/site-packages/nvidia/cu13
mkdir -p "$WORK"
export PATH="$VPY:$CU/bin:$PATH" CUDA_HOME="$CU"
export LIBRARY_PATH="/data/hwkim/sftdpo_work/runtime/cuda_link${LIBRARY_PATH:+:$LIBRARY_PATH}"
ARGS=(serve "$MODEL" --dtype bfloat16 --max-model-len 17408 --tensor-parallel-size 2 --language-model-only
      --served-model-name teacher27 --max-logprobs 64 --gpu-memory-utilization 0.85 --generation-config vllm --seed 0 --enable-log-requests
      --host 127.0.0.1 --port "$PORT")
KER=fi
if [ "${ATTN:-fi}" = auto ]; then KER=auto; else ARGS+=(--attention-backend FLASHINFER); fi
export VLLM_USE_FLASHINFER_SAMPLER=1
gpu_ok "$GA" "vllm27 serve port $PORT (TP rank GPU A)" || { echo "GPU $GA not usable"; exit 1; }
gpu_ok "$GB" "vllm27 serve port $PORT (TP rank GPU B)" || { echo "GPU $GB not usable"; exit 1; }
LOG=$WORK/server_${PORT}_bf16_${KER}.log
CUDA_VISIBLE_DEVICES=$GA,$GB nohup "$VPY/vllm" "${ARGS[@]}" > "$LOG" 2>&1 &
PID=$!
echo $PID > "$WORK/server_$PORT.pid"
p3log "vllm27 serve start GPU $GA,$GB (${UUID[$GA]} ${UUID[$GB]}) port $PORT TP2 bf16 fi pid $PID"
ok=0
for i in $(seq 360); do
  curl -sf "http://127.0.0.1:$PORT/v1/models" >/dev/null && { ok=1; break; }
  kill -0 $PID 2>/dev/null || break
  sleep 5
done
"$VPY/python" - "$WORK/server_$PORT.json" "$GA,$GB" "${UUID[$GA]} ${UUID[$GB]}" "$PID" "$MODEL" "$LOG" "$ok" "$KER" "${ARGS[@]}" <<'PYEOF'
import json, os, re, subprocess, sys, vllm, torch, transformers, flashinfer
out, g, uuid, pid, model, log, ok, ker, *args = sys.argv[1:]
text = open(log, errors="replace").read()
backend = re.findall(r"Using (?:AttentionBackendEnum\.)?(\S+?)(?: attention)? backend", text)
mem = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,memory.used,memory.total", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip().splitlines()
json.dump({"ready": ok == "1", "precision": "bf16", "kernels": ker, "gpu_index": g, "gpu_uuid": uuid, "pid": int(pid), "args": args, "tensor_parallel": 2,
           "model_dir": model, "model": "Qwen/Qwen3.8-27B", "revision": "37561816e66b5b9153b1b64c10968c18c1e6f4a0",
           "env": {k: os.environ.get(k) for k in ("VLLM_USE_FLASHINFER_SAMPLER", "CUDA_HOME", "CUDA_VISIBLE_DEVICES")},
           "log_attention_backend": sorted(set(backend)),
           "log_flashinfer_sampler_lines": [l.strip()[:200] for l in text.splitlines() if re.search(r"(?i)flashinfer.*(sampl|top-?p|top-?k)", l)][:5],
           "log_memory_lines": [l.strip()[:240] for l in text.splitlines() if re.search(r"(?i)model loading took|KV cache|GiB", l)][:12],
           "log_errors": [l.strip()[:300] for l in text.splitlines() if re.search(r"Error|ERROR", l)][:10],
           "nvidia_smi_after_ready": mem,
           "vllm": vllm.__version__, "flashinfer": flashinfer.__version__, "torch": torch.__version__, "torch_cuda": torch.version.cuda,
           "transformers": transformers.__version__, "server_log": log, "adapter(first LoRA)": None, "lora_modules": [], "adapter_sha256": None},
          open(out, "w"), indent=1)
PYEOF
if [ $ok = 1 ]; then p3log "vllm27 serve ready port $PORT"; exit 0; fi
p3log "STOP: vllm27 serve failed port $PORT (log $LOG)"; kill $PID 2>/dev/null; exit 1
