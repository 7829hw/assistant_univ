#!/usr/bin/env bash
# pilot_004 학습과 checkpoint 선택(PLAN.md, PROTOCOL_v4 8절, 결정 96·100). 단계가 실패하면 멈추고 기록한다(재실행 없음).
# 1. SFT 학습(GPU 1장, 0→2 순서로 처음 쓸 수 있는 GPU)
# 2. SFT checkpoint 2개(epoch 1·2)를 selection_v2 k=4로: vLLM 서버 3개(GPU 0·1·2, 각자 두 checkpoint를 LoRA로), 표본 8개를 서버에 나눔, 동시 요청 8
# 3. 고른 SFT에서 DPO 학습(GPU 1장)
# 4. DPO checkpoint 2개(50%·100%)를 같은 방식으로 → 선택 + 중단 규칙(결정 96)
# 기준값은 pilot_prep_007 vllm-bf16-base(PROTOCOL_v4 5절). 단계마다 커밋·push한다. Ollama는 이 스크립트가 도는 동안 부르지 않는다.
set -u
source /home/hwkim/assistant_univ/sft_dpo_inventory/pilot_003/gpu_lib.sh
P3=/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_004   # gpu_lib 기록 위치
P4=$P3
cd /home/hwkim/assistant_univ
WORK=/home/hwkim/sftdpo_work/pilot_004
VW=/data/hwkim/sftdpo_work/pilot_004/vllm
die() { p3log "STOP: $1"; stop_servers; exit 1; }
stop_servers() { local pf; for pf in $VW/server_84*.pid; do [ -e "$pf" ] && kill $(cat $pf) 2>/dev/null; rm -f "$pf"; done; sleep 10; }
commit() {
  local msg=$1; shift
  git add "$@" "$P4/runs.log" "$P4/gpu_check.txt" && git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "$msg

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" || die "commit failed: $msg"
  git push -q origin geoflow/sft-dpo-t2pc >> "$P4/runs.log" 2>&1 || p3log "push rejected: $msg"
}
train() {   # stage config
  local g; g=""; for x in $GPUS; do gpu_ok $x "train $1" && { g=$x; break; }; done
  [ -n "$g" ] || die "no usable GPU for $1 training"
  p3log "$1 train start (CUDA $g, ${UUID[$g]}) config $2"
  echo "$g ${UUID[$g]}" > "$P4/train_logs/$1_gpu.txt"
  nvidia-smi -i ${UUID[$g]} --query-gpu=memory.used --format=csv,noheader,nounits -lms 500 > "$P4/train_logs/$1_nvidia_smi.txt" 2>&1 &
  local smi=$!
  CUDA_VISIBLE_DEVICES=$g PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$PY" -m training.train_$1 --config "$2" > "$P4/train_logs/$1.log" 2>&1
  local rc=$?; kill $smi 2>/dev/null; wait $smi 2>/dev/null
  p3log "$1 train exit=$rc (CUDA $g)"; [ $rc -eq 0 ] || die "$1 train failed"
  cp "$WORK/metrics/$1_profile.json" "$P4/train_logs/"
  local last; last=$(ls -d "$WORK"/checkpoints/$1/checkpoint-* | sort -t- -k2 -n | tail -1)
  "$PY" -c "import json,sys; s=json.load(open(sys.argv[1])); json.dump(s['log_history'], open(sys.argv[2],'w'), indent=1)" \
      "$last/trainer_state.json" "$P4/train_logs/$1_log_history.json"
}
select_stage() {   # stage adapters(label=path ...) [--stop-rule]
  local stage=$1 loras=$2 extra=${3:-}
  for g in 0 1 2; do LORAS="$loras" bash $P4/serve3.sh $g 840$g bf16 fi || die "server $g failed ($stage)"; done
  local jobs=() lab k
  for lab in $(for a in $loras; do echo ${a%%=*}; done); do for k in 1 2 3 4; do jobs+=("$lab:$k"); done; done
  local q0="" q1="" q2="" i=0
  for j in "${jobs[@]}"; do case $((i % 3)) in 0) q0="$q0 $j";; 1) q1="$q1 $j";; 2) q2="$q2 $j";; esac; i=$((i+1)); done
  queue() { local port=$1 j; for j in $2; do
      p3log "cell ${j%%:*} s${j##*:} start port $port"
      "$PY" $P4/run_cell4.py --port $port --model ${j%%:*} --label ${j%%:*} --k ${j##*:} --concurrency 8 --out-dir $P4/selection/runs >> $P4/runs.log 2>&1 || return 1
      p3log "cell ${j%%:*} s${j##*:} done port $port"; done; }
  queue 8400 "$q0" & local a=$!; queue 8401 "$q1" & local b=$!; queue 8402 "$q2" & local c=$!
  wait $a; local ra=$?; wait $b; local rb=$?; wait $c; local rc=$?
  stop_servers
  [ $ra -eq 0 ] && [ $rb -eq 0 ] && [ $rc -eq 0 ] || die "$stage selection cells failed ($ra $rb $rc)"
  local cands=(); for a in $loras; do cands+=(--cand "$a"); done
  "$PY" $P4/selection/analyze_selection4.py --stage $stage "${cands[@]}" --train-log $P4/train_logs/${stage}_summary.json \
      $extra --out $P4/selection_$stage.json >> $P4/runs.log 2>&1 || die "$stage selection analysis failed"
}

p3log "pilot_004 train/select start"
[ -e "$WORK/checkpoints" ] && die "$WORK/checkpoints already exists"
grep -q "학습 시작 전 고정" $P4/PLAN.md || die "PLAN.md not fixed"
[ "$("$PY" -c 'import execution_spec as e;print(e.code_fingerprint(".")["sha256"][:8])')" = 791c4a68 ] || die "fingerprint mismatch"
mkdir -p $P4/train_logs $P4/selection/runs $P4/resolved
# ---- 1. SFT
train sft training/configs/qwen3_8b_t2pc_thinking_pilot004_sft.yaml
mapfile -t SFT_CK < <(ls -d "$WORK"/checkpoints/sft/checkpoint-* | sort -t- -k2 -n)
[ ${#SFT_CK[@]} -eq 2 ] || die "expected 2 SFT checkpoints, got ${#SFT_CK[@]}"
"$PY" $P4/train_summary.py sft "${SFT_CK[@]}" > /dev/null || die "sft summary failed"
commit "train(pilot_004): SFT 학습 기록(checkpoint 2개, adapter는 저장소 밖)" $P4/train_logs
# ---- 2. SFT 선택
L=""; for c in "${SFT_CK[@]}"; do L="$L sft_step${c##*-}=$c"; done
select_stage sft "$L"
SFT_SELECTED=$("$PY" -c "import json; print(json.load(open('$P4/selection_sft.json'))['selected']['adapter'])")
p3log "sft selected $SFT_SELECTED"
commit "eval(pilot_004): SFT checkpoint 2개 selection_v2 k=4(vLLM BF16 LoRA, 동시 요청 8), 선택 $(basename "$SFT_SELECTED")" $P4/selection/runs $P4/selection_sft.json
# ---- 3. DPO
sed "s#adapter_path: SELECTED_PILOT_004_SFT_REQUIRED#adapter_path: $SFT_SELECTED#" training/configs/qwen3_8b_t2pc_thinking_pilot004_dpo.yaml > $P4/resolved/qwen3_8b_t2pc_thinking_pilot004_dpo.resolved.yaml
grep -q "adapter_path: $SFT_SELECTED" $P4/resolved/qwen3_8b_t2pc_thinking_pilot004_dpo.resolved.yaml || die "dpo config not resolved"
train dpo $P4/resolved/qwen3_8b_t2pc_thinking_pilot004_dpo.resolved.yaml
mapfile -t DPO_CK < <(ls -d "$WORK"/checkpoints/dpo/checkpoint-* | sort -t- -k2 -n)
[ ${#DPO_CK[@]} -eq 2 ] || die "expected 2 DPO checkpoints, got ${#DPO_CK[@]}"
"$PY" $P4/train_summary.py dpo "${DPO_CK[@]}" > /dev/null || die "dpo summary failed"
commit "train(pilot_004): DPO 학습 기록(checkpoint 2개)" $P4/train_logs $P4/resolved
# ---- 4. DPO 선택 + 중단 규칙
L=""; for c in "${DPO_CK[@]}"; do L="$L dpo_step${c##*-}=$c/policy"; done
select_stage dpo "$L" --stop-rule
DPO_SELECTED=$("$PY" -c "import json; print(json.load(open('$P4/selection_dpo.json'))['selected']['adapter'])")
PROCEED=$("$PY" -c "import json; print(json.load(open('$P4/selection_dpo.json'))['stop_rule(decision 96)']['proceed_to_vendor100'])")
p3log "dpo selected $DPO_SELECTED stop_rule proceed=$PROCEED"
commit "eval(pilot_004): DPO checkpoint 2개 selection_v2 k=4, 선택 $(basename "$(dirname "$DPO_SELECTED")"), 중단 규칙(결정 96) 진행=$PROCEED" $P4/selection/runs $P4/selection_dpo.json
p3log "pilot_004 train/select done"
