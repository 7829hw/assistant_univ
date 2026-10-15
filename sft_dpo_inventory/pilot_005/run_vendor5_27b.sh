#!/usr/bin/env bash
# pilot_005 작업 6의 27b 참고 셀만 잰다(PROTOCOL_v5 5절, 결정 97). run_vendor5.sh의 ollama_cell 함수를 그대로 옮긴 새 파일이다.
# 까닭: run_vendor5.sh는 E 셀(lat-E) 직후 27b precheck를 바로 돌렸고, 그때 qwen3:8b가 keep_alive로 아직 올라가 있어 결정 55 precheck가 실패했다
# (2026-10-15 17:08:52, 측정은 시작하지 않음, 기록 vendor100/ABORTED_precheck_v100-27b_s1_gpu_precheck.json). 모델을 직접 내리지 않고(CLAUDE.md 5),
# keep_alive가 끝나 /api/ps가 비고 Ollama GPU 메모리가 풀릴 때까지 기다린 뒤 같은 절차로 27b(k=4)를 잰다. 실행 중 스크립트는 고치지 않았다(결정 88).
set -u
source /home/hwkim/assistant_univ/sft_dpo_inventory/pilot_003/gpu_lib.sh
P3=/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_005
P4=$P3
cd /home/hwkim/assistant_univ
VW=/data/hwkim/sftdpo_work/pilot_005/vllm
RAW=training/generated/pilot_005/raw
V_GOLD=evaluation/vendor100/gold.yaml
A_GOLD=sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml
D_GOLD=sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml
S_GOLD=sft_dpo_inventory/conversion_diag/selection_gold.yaml
LAT=$(cat sft_dpo_inventory/serving_vllm_fp8/latency_ids.txt)
GUARD=sft_dpo_inventory/pilot_002/ollama_gpu_guard.py
OUUID=GPU-48f798cc-9437-50ac-d604-448bbad7b311
stop_servers() { local pf; for pf in $VW/server_85*.pid; do [ -e "$pf" ] && kill $(cat $pf) 2>/dev/null; rm -f "$pf"; done; sleep 10; }
die() { p3log "STOP: $1"; stop_servers; exit 1; }
commit() {
  local msg=$1; shift
  git add "$@" "$P4/runs.log" "$P4/gpu_check.txt" && git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "$msg

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" || die "commit failed: $msg"
  git push -q origin geoflow/sft-dpo-t2pc >> "$P4/runs.log" 2>&1 || p3log "push rejected: $msg"
}
ollama_cell() {   # model think label gold k-list outdir only
  local model=$1 think=$2 label=$3 gold=$4 ks=$5 out=$6 only=${7:-}
  local ver dig want files=() k p since pid grc rc
  ver=$(curl -s localhost:11434/api/version | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["version"])')
  dig=$(curl -s localhost:11434/api/tags | "$PY" -c "import json,sys; print(next(m['digest'][:12] for m in json.load(sys.stdin)['models'] if m['name']=='$model'))")
  want=$([ $model = qwen3:8b ] && echo 500a1f067a9f || echo aaee06c39dcf)
  p3log "ollama $label precheck: version $ver, $model digest $dig"
  [ "$ver" = 0.40.3 ] && [ "$dig" = "$want" ] || die "ollama version/digest mismatch for $label"
  docker exec ollama nvidia-smi -L 2>&1 | grep -q "$OUUID" || die "container does not see $OUUID"
  pgrep -u "$(id -u)" -f '[v]llm serve|[r]un_cell5|[v]llm_collect|[t]raining.train_' >/dev/null && die "other model process running before $label"
  for k in $ks; do
    p=$P4/$out/${label}_s$k
    { [ -e $p.json ] || [ -e $p.jsonl ]; } && die "$p exists"
    "$PY" $GUARD precheck --gpu-uuid $OUUID --version "$ver" --allow-loaded $model --out ${p}_gpu_precheck.json >> $P4/runs.log 2>&1 || die "$label s$k precheck failed"
    { echo "## $(date -Is) ollama $label s$k"; nvidia-smi --query-gpu=index,uuid,memory.used --format=csv,noheader
      nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader; curl -s localhost:11434/api/ps; echo; } >> $P4/gpu_check.txt 2>&1
    since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    p3log "ollama $label s$k start ($model) seed $((20261100 + k)) think $think"
    "$PY" evaluate_vendor100.py --gold $gold llm --model $model --reference-date 2026-09-25 --condition-check ${only:+--only "$only"} \
      --model-think $think --model-state keep_loaded --temperature 0.6 --top-p 0.95 --top-k 20 --min-p 0 --repeat-penalty 1 \
      --presence-penalty 0 --frequency-penalty 0 --seed $((20261100 + k)) --record-env --raw-out $RAW/${label}_s${k}_raw.jsonl \
      --out $p.json > $p.log 2>&1 &
    pid=$!
    "$PY" $GUARD watch --gpu-uuid $OUUID --pid $pid --rows $p.jsonl --model $model --out ${p}_gpu_guard.json > ${p}_gpu_guard.log 2>&1
    grc=$?; wait $pid; rc=$?
    docker logs ollama --since "$since" 2>&1 | grep -A4 "sampler params" | grep -E "repeat_penalty|top_k|temp" | sed 's/^[[:space:]]*//' | sort | uniq -c > ${p}_sampler_params.txt
    p3log "ollama $label s$k exit=$rc guard=$grc"
    if [ $grc -ne 0 ]; then for f in "$p".* "${p}_"*; do [ -e "$f" ] && mv "$f" "$(dirname "$f")/ABORTED_gpu_$(basename "$f")"; done; die "$label s$k guard stop"; fi
    [ $rc -eq 0 ] || die "$label s$k failed"
    files+=($p.json $p.jsonl $p.log ${p}_gpu_guard.json ${p}_gpu_guard.log ${p}_gpu_precheck.json ${p}_sampler_params.txt)
    [ -e $p.spec.json ] && files+=($p.spec.json)
  done
  commit "eval(pilot_005): 참고 셀 $label($model, Ollama $ver 연속, think $think, 결정 55 확인 통과, 판정 없음)" "${files[@]}"
}
p3log "27b cell: waiting for Ollama models to unload by keep_alive (no manual unload)"
for i in $(seq 120); do
  n=$(curl -s localhost:11434/api/ps | "$PY" -c 'import json,sys; print(len(json.load(sys.stdin)["models"]))')
  used=$(nvidia-smi -i $OUUID --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' ')
  [ "$n" = 0 ] && [ "$used" -lt 100 ] && break
  sleep 15
done
[ "$n" = 0 ] && [ "$used" -lt 100 ] || die "Ollama model still loaded after waiting"
p3log "27b cell: Ollama empty, GPU free (used ${used}MiB)"
ollama_cell qwen3.8:27b on v100-27b $V_GOLD "1 2 3 4" vendor100
p3log "vendor100 27b done"
