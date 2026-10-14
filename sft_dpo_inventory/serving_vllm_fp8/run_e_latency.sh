#!/usr/bin/env bash
# E 지연 순차 측정(결정 93): selection_v2 고정 30문항(latency_ids.txt), 1표본(seed 20261101), qwen3:8b, Ollama 0.40.3, 연속 방식,
# Ollama GPU(UUID 48f798cc…), 결정 55 guard. 이 측정 중에는 다른 모델 작업을 하지 않는다(실행 전 확인).
set -u
cd /home/hwkim/assistant_univ
FP=sft_dpo_inventory/serving_vllm_fp8
OUT=$FP/latency
RAW=training/generated/serving_vllm_fp8/raw
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
GOLD=sft_dpo_inventory/conversion_diag/selection_gold.yaml
GUARD=sft_dpo_inventory/pilot_002/ollama_gpu_guard.py
OUUID=GPU-48f798cc-9437-50ac-d604-448bbad7b311
mkdir -p $OUT $RAW
log() { echo "== $1 $(date -Is)" >> "$FP/runs.log"; }
die() { log "STOP: $1"; exit 1; }
[ "$("$PY" -c 'import execution_spec as e;print(e.code_fingerprint(".")["sha256"][:8])')" = 791c4a68 ] || die "fingerprint mismatch"
pgrep -u "$(id -u)" -f '[h]f_eval_thinking.py|[v]llm_eval_thinking.py|[v]llm serve|[s]core_vllm|[t]raining.train_' >/dev/null && die "other model process running"
VER=$(curl -s localhost:11434/api/version | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["version"])')
DIG=$(curl -s localhost:11434/api/tags | "$PY" -c 'import json,sys; print(next(m["digest"][:12] for m in json.load(sys.stdin)["models"] if m["name"]=="qwen3:8b"))')
log "E latency precheck: ollama $VER, qwen3:8b $DIG"
[ "$VER" = 0.40.3 ] && [ "$DIG" = 500a1f067a9f ] || die "Ollama version/digest mismatch"
docker exec ollama nvidia-smi -L 2>&1 | grep -q "$OUUID" || die "container does not see $OUUID"
p=$OUT/lat-E_s1
[ -e $p.json ] && die "$p.json exists"
"$PY" "$GUARD" precheck --gpu-uuid $OUUID --version "$VER" --allow-loaded qwen3:8b --out ${p}_gpu_precheck.json >> $FP/runs.log 2>&1 || die "precheck failed"
since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
log "E latency start"
"$PY" evaluate_vendor100.py --gold $GOLD llm --model qwen3:8b --reference-date 2026-09-25 --condition-check --only "$(cat $FP/latency_ids.txt)" \
  --model-think auto --model-state keep_loaded --temperature 0.6 --top-p 0.95 --top-k 20 --min-p 0 --repeat-penalty 1 \
  --presence-penalty 0 --frequency-penalty 0 --seed 20261101 --record-env --raw-out $RAW/lat-E_s1_raw.jsonl --out $p.json > $p.log 2>&1 &
pid=$!
"$PY" "$GUARD" watch --gpu-uuid $OUUID --pid $pid --rows $p.jsonl --model qwen3:8b --out ${p}_gpu_guard.json > ${p}_gpu_guard.log 2>&1
grc=$?; wait $pid; rc=$?
docker logs ollama --since "$since" 2>&1 | grep -A4 "sampler params" | grep -E "repeat_penalty|top_k|temp" | sed 's/^[[:space:]]*//' | sort | uniq -c > ${p}_sampler_params.txt
log "E latency exit=$rc guard=$grc"
if [ $grc -ne 0 ]; then for f in "$p".* "${p}_"*; do [ -e "$f" ] && mv "$f" "$(dirname "$f")/ABORTED_gpu_$(basename "$f")"; done; die "guard stop"; fi
[ $rc -eq 0 ] || die "E latency failed"
git add $OUT/lat-E_s1* $FP/runs.log && git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "eval(serving_vllm_fp8): E 지연 순차 측정(selection_v2 고정 30문항, Ollama $VER 연속, 결정 55 통과)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" || die "commit failed"
git push -q origin geoflow/sft-dpo-t2pc >> $FP/runs.log 2>&1 || log "push rejected"
log "E latency done"
