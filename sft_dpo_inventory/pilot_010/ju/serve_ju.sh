#!/usr/bin/env bash
# pilot_010 JU(결정 272, PLAN_JU 2절) Ollama 0.40.6 사용자 권한 서버 하나(GPU 하나). Docker·기존 컨테이너·포트 11434·/data/hwkim/ollama는 쓰지 않는다
# (규칙 4 예외, 이 작업에 한함). 실행 파일 = 공식 Linux 배포 파일(ollama-linux-amd64.tar.zst v0.40.6)을 작업 디렉터리에 푼 것, 모델 = 복사한 manifest·blob.
#   bash serve_ju.sh GPU_INDEX PORT          (P3·OLLAMA_UUID·ALLOWED_UUIDS는 gpu_lib7.gpu_ok용)
# 순서: gpu_ok(host nvidia-smi UUID·메모리·다른 프로세스, torch UUID) → ollama serve(nohup) → /api/version·/api/tags digest 확인 →
#   모델 올리기(/api/generate에 model·keep_alive -1만, prompt 없음 → 생성 없음) → /api/ps size_vram == size(100% GPU) → server_<port>.json 기록.
set -u
G=$1; PORT=$2
source "$(dirname "${BASH_SOURCE[0]}")/../../pilot_007/gpu_data/gpu_lib7.sh"
P3=${P3:?P3 must be set}
JU=/data/hwkim/sftdpo_work/pilot_010_ju
BIN=$JU/ollama-0.40.6/bin/ollama
WORK=$JU/servers
MODELS=${JU_MODELS:-$JU/models}
mkdir -p "$WORK" "$JU/home_$PORT"
gpu_ok "$G" "ollama_ju serve port $PORT" || { echo "GPU $G not usable"; exit 1; }
if curl -sf "http://127.0.0.1:$PORT/api/version" >/dev/null; then p3log "STOP: port $PORT already in use"; exit 1; fi
LOG=$WORK/server_${PORT}.log
U=${UUID[$G]}
env -i PATH=/usr/bin:/bin HOME="$JU/home_$PORT" CUDA_VISIBLE_DEVICES="$U" OLLAMA_HOST="127.0.0.1:$PORT" OLLAMA_MODELS="$MODELS" \
  OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=-1 OLLAMA_NOPRUNE=1 \
  nohup "$BIN" serve > "$LOG" 2>&1 &
PID=$!
echo $PID > "$WORK/server_$PORT.pid"
STARTED=$(date -Is)
p3log "ollama_ju serve start GPU $G ($U) port $PORT pid $PID models $MODELS"
ok=0
for i in $(seq 60); do curl -sf "http://127.0.0.1:$PORT/api/version" >/dev/null && { ok=1; break; }; kill -0 $PID 2>/dev/null || break; sleep 1; done
if [ $ok = 1 ]; then
  curl -s "http://127.0.0.1:$PORT/api/generate" -d '{"model":"qwen3.8:27b","keep_alive":-1}' > "$WORK/load_$PORT.json" || ok=0
  sleep 2
fi
"$PY" - "$WORK/server_$PORT.json" "$G" "$U" "$PID" "$PORT" "$LOG" "$ok" "$STARTED" "$BIN" "$MODELS" <<'PYEOF'
import hashlib, json, os, subprocess, sys, urllib.request
out, g, uuid, pid, port, log, ok, started, binp, models = sys.argv[1:]
H = f"http://127.0.0.1:{port}"
def get(path, body=None):
    req = urllib.request.Request(H + path, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())
rec = {"ready": False, "port": int(port), "pid": int(pid), "started_at": started, "gpu_index": g, "gpu_uuid": uuid, "log": log, "binary": binp,
       "binary_sha256": hashlib.sha256(open(binp, "rb").read()).hexdigest(), "models_dir": models,
       "env": {"CUDA_VISIBLE_DEVICES": uuid, "OLLAMA_HOST": f"127.0.0.1:{port}", "OLLAMA_MODELS": models, "OLLAMA_NUM_PARALLEL": "1",
               "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_KEEP_ALIVE": "-1", "OLLAMA_NOPRUNE": "1", "HOME": os.path.dirname(models) + f"/home_{port}"}}
try:
    rec["version"] = get("/api/version").get("version")
    tags = {m["name"]: m for m in get("/api/tags").get("models", [])}
    rec["digest"] = tags.get("qwen3.8:27b", {}).get("digest")
    rec["tags_details"] = tags.get("qwen3.8:27b", {}).get("details")
    show = get("/api/show", {"model": "qwen3.8:27b"})
    rec["show_parameters"], rec["show_template"] = show.get("parameters"), show.get("template")
    rec["show_modelfile_head"] = "\n".join((show.get("modelfile") or "").splitlines()[:12])
    rec["show_capabilities"], rec["show_thinking"], rec["show_details"] = show.get("capabilities"), show.get("thinking"), show.get("details")
    ps = [m for m in get("/api/ps").get("models", []) if m.get("name") == "qwen3.8:27b"]
    rec["api_ps_after_load"] = ps
    rec["gpu_100"] = bool(ps) and ps[0].get("size_vram") == ps[0].get("size")
    rec["context_length"] = ps[0].get("context_length") if ps else None
    cli = {}
    for flag in ("--parameters", "--template", "--modelfile"):
        r = subprocess.run([binp, "show", "qwen3.8:27b", flag], capture_output=True, text=True, env={"OLLAMA_HOST": f"127.0.0.1:{port}", "PATH": "/usr/bin:/bin"})
        cli[flag] = r.stdout[:4000]
    rec["ollama_show_cli"] = cli
    rec["ready"] = ok == "1" and rec["version"] == "0.40.6" and rec["digest"] == "aaee06c39dcf2437cde036998d960e1fc1494b8191be7cc9657d01e509097813" and rec["gpu_100"]
except Exception as error:  # noqa: BLE001
    rec["error"] = f"{type(error).__name__}: {error}"
rec["nvidia_smi_after_load"] = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,memory.used,memory.total", "--format=csv,noheader"],
                                              capture_output=True, text=True).stdout.strip().splitlines()
text = open(log, errors="replace").read()
rec["log_lines"] = [l.strip()[:300] for l in text.splitlines() if any(k in l for k in ("inference compute", "offload", "flash", "kv_cache", "KvSize", "num_ctx", "context", "layers", "library="))][:25]
json.dump(rec, open(out, "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: rec.get(k) for k in ("ready", "version", "digest", "gpu_100", "context_length", "error")}))
sys.exit(0 if rec["ready"] else 1)
PYEOF
rc=$?
if [ $rc = 0 ]; then p3log "ollama_ju serve ready port $PORT (100% GPU)"; exit 0; fi
p3log "STOP: ollama_ju serve not ready port $PORT (log $LOG)"; kill $PID 2>/dev/null; exit 1
