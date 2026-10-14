#!/usr/bin/env bash
# pilot_004 작업 7: 업체 100 평가(PROTOCOL_v4). selection_dpo.json의 중단 규칙(결정 96)이 진행일 때만 돈다.
#   1) vLLM 셀(BF16, flashinfer, 동시 요청 8, 서버 3개 GPU 0·1·2, LoRA "final"=고른 DPO checkpoint):
#      업체 100 base·최종 k=8, aux_test_v1 base·최종 k=4, valid98 base·최종 k=4(보조)
#   2) 지연: 서버 하나(GPU 0)에서 고정 30문항(serving_vllm_fp8/latency_ids.txt) base·최종을 순차(동시 요청 1)로
#   3) Ollama 셀(vLLM 서버를 모두 내린 뒤, Ollama GPU만): E(qwen3:8b) 업체 100 k=8·aux k=4·지연 30문항, 27b(qwen3.8:27b, thinking 켬) 업체 100 k=4
#      측정 전 버전·digest 확인, 결정 55 guard. 연속 방식.
# 셀(묶음)마다 커밋한다. 출력이 있으면 멈춘다(재실행 없음).
set -u
source /home/hwkim/assistant_univ/sft_dpo_inventory/pilot_003/gpu_lib.sh
P3=/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_004
P4=$P3
cd /home/hwkim/assistant_univ
VW=/data/hwkim/sftdpo_work/pilot_004/vllm
RAW=training/generated/pilot_004/raw
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
PROCEED=$("$PY" -c "import json; print(json.load(open('$P4/selection_dpo.json'))['stop_rule(decision 96)']['proceed_to_vendor100'])")
[ "$PROCEED" = True ] || { p3log "vendor100 not run: stop rule proceed=$PROCEED"; exit 0; }
FINAL=$("$PY" -c "import json; print(json.load(open('$P4/selection_dpo.json'))['selected']['adapter'])")
[ "$("$PY" -c 'import execution_spec as e;print(e.code_fingerprint(".")["sha256"][:8])')" = 791c4a68 ] || die "fingerprint mismatch"
[ "$(sha256sum $V_GOLD | cut -c1-64)" = f99bc5fdef623e973901e5b339ede3c7f4e36cfa133887ea933e9683a7d8b4f0 ] || die "vendor gold sha mismatch"
p3log "vendor100 start (final adapter $FINAL, sha256 $(sha256sum $FINAL/adapter_model.safetensors | cut -c1-16))"
mkdir -p $P4/vendor100/runs $P4/aux_test/runs $P4/valid98/runs $P4/latency $RAW

# ---- 1. vLLM 정답률 셀
for g in 0 1 2; do LORAS="final=$FINAL" bash $P4/serve3.sh $g 850$g bf16 fi || die "server $g failed"; done
jobs=()
for k in 1 2 3 4 5 6 7 8; do for m in base final; do jobs+=("v100|$m|$k|$V_GOLD|vendor100"); done; done
for k in 1 2 3 4; do for m in base final; do jobs+=("aux|$m|$k|$A_GOLD|aux_test" "v98|$m|$k|$D_GOLD|valid98"); done; done
q0=(); q1=(); q2=(); i=0
for j in "${jobs[@]}"; do case $((i % 3)) in 0) q0+=("$j");; 1) q1+=("$j");; 2) q2+=("$j");; esac; i=$((i+1)); done
queue() { local port=$1; shift; local j set m k gold dir
  for j in "$@"; do IFS='|' read -r set m k gold dir <<< "$j"
    p3log "cell $set-$m s$k start port $port"
    "$PY" $P4/run_cell4v.py --port $port --model $m --label $set-$m --k $k --concurrency 8 --gold $gold --all-items \
       --out-dir $P4/$dir/runs >> $P4/runs.log 2>&1 || return 1
    p3log "cell $set-$m s$k done port $port"; done; }
queue 8500 "${q0[@]}" & a=$!; queue 8501 "${q1[@]}" & b=$!; queue 8502 "${q2[@]}" & c=$!
wait $a; ra=$?; wait $b; rb=$?; wait $c; rc=$?
[ $ra -eq 0 ] && [ $rb -eq 0 ] && [ $rc -eq 0 ] || die "vLLM cells failed ($ra $rb $rc)"
for set in v100:vendor100 aux:aux_test v98:valid98; do for m in base final; do
  commit "eval(pilot_004): ${set#*:} vLLM-$m(BF16 flashinfer, 동시 요청 8)" $P4/${set#*:}/runs/${set%%:*}-${m}_s*; done; done
stop_servers
# ---- 2. 지연(순차)
LORAS="final=$FINAL" bash $P4/serve3.sh 0 8500 bf16 fi || die "latency server failed"
for m in base final; do
  p3log "latency $m start"
  "$PY" $P4/run_cell4v.py --port 8500 --model $m --label lat-$m --k 1 --concurrency 1 --gold $S_GOLD --only "$LAT" --out-dir $P4/latency >> $P4/runs.log 2>&1 || die "latency $m failed"
  p3log "latency $m done"
done
stop_servers
commit "eval(pilot_004): 지연 순차 측정(고정 30문항, vLLM base·최종)" $P4/latency
# ---- 3. Ollama 셀
ollama_cell() {   # model think label gold k-list outdir only
  local model=$1 think=$2 label=$3 gold=$4 ks=$5 out=$6 only=${7:-}
  local ver dig want files=() k p since pid grc rc
  ver=$(curl -s localhost:11434/api/version | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["version"])')
  dig=$(curl -s localhost:11434/api/tags | "$PY" -c "import json,sys; print(next(m['digest'][:12] for m in json.load(sys.stdin)['models'] if m['name']=='$model'))")
  want=$([ $model = qwen3:8b ] && echo 500a1f067a9f || echo aaee06c39dcf)
  p3log "ollama $label precheck: version $ver, $model digest $dig"
  [ "$ver" = 0.40.3 ] && [ "$dig" = "$want" ] || die "ollama version/digest mismatch for $label"
  docker exec ollama nvidia-smi -L 2>&1 | grep -q "$OUUID" || die "container does not see $OUUID"
  pgrep -u "$(id -u)" -f '[v]llm serve|[r]un_cell4|[t]raining.train_' >/dev/null && die "other model process running before $label"
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
  commit "eval(pilot_004): 참고 셀 $label($model, Ollama $ver 연속, think $think, 결정 55 확인 통과, 판정 없음)" "${files[@]}"
}
ollama_cell qwen3:8b auto v100-E $V_GOLD "1 2 3 4 5 6 7 8" vendor100
ollama_cell qwen3:8b auto aux-E $A_GOLD "1 2 3 4" aux_test
ollama_cell qwen3:8b auto lat-E $S_GOLD "1" latency "$LAT"
ollama_cell qwen3.8:27b on v100-27b $V_GOLD "1 2 3 4" vendor100
p3log "vendor100 done"
