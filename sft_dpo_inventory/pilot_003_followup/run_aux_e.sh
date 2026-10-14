#!/usr/bin/env bash
# pilot_003 후속 1(결정 87, AB): aux_test_v1 E 참고 셀(qwen3:8b, Ollama 0.40.3, 연속 방식, k=4, PROTOCOL_v3 3·5절). 판정 없음.
# pilot_003 run_vendor100.sh의 E 단계와 같은 절차(결정 55 guard, sampler 적용 값 기록)를 aux gold·k=4로 돈다. 출력이 있으면 멈춘다.
set -u
source /home/hwkim/assistant_univ/sft_dpo_inventory/pilot_003/gpu_lib.sh
cd /home/hwkim/assistant_univ
FU=sft_dpo_inventory/pilot_003_followup
OUT=$FU/aux_e/runs
RAW=training/generated/pilot_003_followup/raw
LOG=$FU/runs.log
A_GOLD=sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml
GUARD=sft_dpo_inventory/pilot_002/ollama_gpu_guard.py
OUUID=GPU-48f798cc-9437-50ac-d604-448bbad7b311
mkdir -p "$OUT" "$RAW"
log() { echo "== $1 $(date -Is)" >> "$LOG"; }
die() { log "STOP: $1"; exit 1; }
[ "$(sha256sum $A_GOLD | cut -c1-64)" = 3758d0dcefea2fb3e3da45f34929301a455571fc94b580c77a75adfc206c5ffb ] || die "aux gold sha mismatch"
[ "$("$PY" -c 'import execution_spec as e;print(e.code_fingerprint(".")["sha256"][:8])')" = 791c4a68 ] || die "fingerprint mismatch"
VER=$(curl -s localhost:11434/api/version | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["version"])')
DIG=$(curl -s localhost:11434/api/tags | "$PY" -c 'import json,sys; print(next(m["digest"][:12] for m in json.load(sys.stdin)["models"] if m["name"]=="qwen3:8b"))')
log "aux E precheck: ollama version $VER, qwen3:8b digest $DIG"
[ "$VER" = 0.40.3 ] || die "Ollama version $VER != 0.40.3 (decision 87)"
[ "$DIG" = 500a1f067a9f ] || die "E digest $DIG != 500a1f067a9f"
docker exec ollama nvidia-smi -L 2>&1 | grep -q "$OUUID" || die "Ollama container does not see $OUUID"
pgrep -u "$(id -u)" -f '[h]f_eval_thinking.py|[e]val_valid98.py|[t]raining.train_|[v]llm' >/dev/null && die "other model process running"
files=()
for k in 1 2 3 4; do
  p=$OUT/aux_E_s$k
  { [ -e "$p.json" ] || [ -e "$p.jsonl" ]; } && die "$p exists"
  "$PY" "$GUARD" precheck --gpu-uuid $OUUID --version "$VER" --allow-loaded qwen3:8b --out "${p}_gpu_precheck.json" >> "$LOG" 2>&1 \
    || die "aux_E_s$k precheck failed (decision 55)"
  { echo "## $(date -Is) ollama aux_E_s$k"; nvidia-smi --query-gpu=index,uuid,memory.used --format=csv,noheader
    nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader
    echo "## ollama container"; docker exec ollama nvidia-smi -L 2>&1; curl -s localhost:11434/api/ps; echo; } >> "$FU/gpu_check.txt" 2>&1
  since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  log "ollama aux_E_s$k start (qwen3:8b) seed $((20261100 + k)) GPU $OUUID isolation continuous version $VER"
  "$PY" evaluate_vendor100.py --gold "$A_GOLD" llm --model qwen3:8b --reference-date 2026-09-25 --condition-check \
    --model-think auto --model-state keep_loaded --temperature 0.6 --top-p 0.95 --top-k 20 --min-p 0 --repeat-penalty 1 \
    --presence-penalty 0 --frequency-penalty 0 --seed $((20261100 + k)) --record-env --raw-out "$RAW/aux_E_s${k}_raw.jsonl" \
    --out "$p.json" > "$p.log" 2>&1 &
  pid=$!
  "$PY" "$GUARD" watch --gpu-uuid $OUUID --pid $pid --rows "$p.jsonl" --model qwen3:8b --out "${p}_gpu_guard.json" > "${p}_gpu_guard.log" 2>&1
  grc=$?; wait $pid; rc=$?
  docker logs ollama --since "$since" 2>&1 | grep -A4 "sampler params" | grep -E "repeat_penalty|top_k|temp" \
    | sed 's/^[[:space:]]*//' | sort | uniq -c > "${p}_sampler_params.txt"
  log "ollama aux_E_s$k exit=$rc guard=$grc"
  if [ $grc -ne 0 ]; then
    for f in "$p".* "${p}_"*; do [ -e "$f" ] && mv "$f" "$(dirname "$f")/ABORTED_gpu_$(basename "$f")"; done
    die "aux_E_s$k aborted by decision 55 guard"
  fi
  [ $rc -eq 0 ] || die "ollama aux_E_s$k failed rc=$rc"
  files+=("$p.json" "$p.jsonl" "$p.log" "${p}_gpu_guard.json" "${p}_gpu_guard.log" "${p}_gpu_precheck.json" "${p}_sampler_params.txt")
  [ -e "$p.spec.json" ] && files+=("$p.spec.json")
done
git add "${files[@]}" "$LOG" "$FU/gpu_check.txt" && git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "eval(pilot_003_followup): aux_test_v1 참고 셀 E(qwen3:8b, Ollama $VER 연속, k=4, 결정 55 확인 통과, 판정 없음)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" || die "commit failed"
git push -q origin geoflow/sft-dpo-t2pc >> "$LOG" 2>&1 || log "push rejected (CLAUDE.md 14번 절차 필요)"
log "aux E done"
