#!/usr/bin/env bash
# pilot_003 재개(결정 84): 2026-10-13 15:45 재부팅·GPU a644de12 이탈로 DPO 학습(약 100/348 step, checkpoint 없음)과
# 고른 SFT의 valid98(보조)이 멈췄다. 장치 장애로 멈춘 실행이므로 둘 다 처음부터 다시 한다(같은 config·seed, 설정 변경 없음).
# 멈춘 기록은 aborted_device_failure/ABORTED_*에 둔다. 단계는 run_train_select.sh 3–5와 같고, GPU는 지금 있는 3장(gpu_lib.sh GPUS)을 쓴다.
set -u
source "$(dirname "$0")/hf_samples.sh"
cd /home/hwkim/assistant_univ
WORK=/home/hwkim/sftdpo_work/pilot_003
SEL_GOLD=sft_dpo_inventory/conversion_diag/selection_gold.yaml
SEL_IDS=$P3/selection/selection_v2_ids.txt
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
RESOLVED=$P3/resolved/qwen3_8b_t2pc_thinking_pilot003_dpo.resolved.yaml
die() { p3log "STOP: $1"; exit 1; }
commit() {   # msg paths...
  local msg=$1; shift
  git add "$@" "$P3/runs.log" "$P3/gpu_check.txt" && git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "$msg

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" || die "commit failed: $msg"
  git push -q origin geoflow/sft-dpo-t2pc >> "$P3/runs.log" 2>&1 || p3log "push rejected: $msg (CLAUDE.md 14번 절차 필요)"
}
first_free() { local g; for g in $GPUS; do gpu_ok $g "$1" && { echo $g; return; }; done; }
train_start() {   # stage config -> TRAIN_PID, TRAIN_GPU
  TRAIN_GPU=$(first_free "train $1"); [ -n "$TRAIN_GPU" ] || die "no usable GPU for $1 training"
  p3log "$1 train start (CUDA $TRAIN_GPU, ${UUID[$TRAIN_GPU]}) config $2"
  echo "$TRAIN_GPU ${UUID[$TRAIN_GPU]}" > "$P3/train_logs/$1_gpu.txt"
  nvidia-smi -i ${UUID[$TRAIN_GPU]} --query-gpu=memory.used --format=csv,noheader,nounits -lms 500 > "$P3/train_logs/$1_nvidia_smi.txt" 2>&1 &
  SMI_PID=$!
  CUDA_VISIBLE_DEVICES=$TRAIN_GPU PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True "$PY" -m training.train_$1 --config "$2" \
    > "$P3/train_logs/$1.log" 2>&1 &
  TRAIN_PID=$!
}
train_wait() {
  wait $TRAIN_PID; local rc=$?; kill $SMI_PID 2>/dev/null; wait $SMI_PID 2>/dev/null
  p3log "$1 train exit=$rc (CUDA $TRAIN_GPU)"; [ $rc -eq 0 ] || die "$1 train failed"
  cp "$WORK/metrics/$1_profile.json" "$P3/train_logs/"
  local last; last=$(ls -d "$WORK"/checkpoints/$1/checkpoint-* | sort -t- -k2 -n | tail -1)
  "$PY" -c "import json,sys; s=json.load(open(sys.argv[1])); json.dump(s['log_history'], open(sys.argv[2],'w'), indent=1)" \
      "$last/trainer_state.json" "$P3/train_logs/$1_log_history.json"
}
others() { local g out=""; for g in $GPUS; do [ "$g" = "${TRAIN_GPU:-x}" ] || out="$out $g"; done; echo $out; }
sel_jobs() { local k; for k in 1 2 3 4; do JOBS+=("$1|$2|$SEL_GOLD|$SEL_IDS|$k|$P3/selection/runs"); done; }
valid98() {   # name adapter gpu
  p3log "valid98 $1 start (CUDA $3, ${UUID[$3]})"
  CUDA_VISIBLE_DEVICES=$3 "$PY" sft_dpo_inventory/pilot_001/valid98/eval_valid98.py --label "valid98_$1" \
      --out "$P3/valid98/valid98_$1.json" --raw-out "$RAW/valid98_$1_raw.jsonl" --adapter "$2" > "$P3/valid98/valid98_$1.log" 2>&1
  local rc=$?; p3log "valid98 $1 exit=$rc (CUDA $3)"; return $rc
}

p3log "pilot_003 resume after device failure (결정 84), GPUs: $GPUS"
[ -e "$WORK/checkpoints/dpo" ] && die "$WORK/checkpoints/dpo already exists"
SFT_SELECTED=$("$PY" -c "import json; print(json.load(open('$P3/selection_sft.json'))['selected']['adapter'])")
grep -q "adapter_path: $SFT_SELECTED" "$RESOLVED" || die "resolved dpo config does not point to selected SFT"

# ---- 3. DPO 학습 ‖ 고른 SFT valid98(보조)
train_start dpo "$RESOLVED"
sleep 120
g=""; for x in $(others); do gpu_ok $x "valid98 sft" && { g=$x; break; }; done
[ -n "$g" ] || die "no usable GPU for valid98 sft"
valid98 sft "$SFT_SELECTED" "$g" || die "valid98 sft failed"
train_wait dpo
mapfile -t DPO_CK < <(ls -d "$WORK"/checkpoints/dpo/checkpoint-* | sort -t- -k2 -n)
[ ${#DPO_CK[@]} -eq 2 ] || die "expected 2 DPO checkpoints, got ${#DPO_CK[@]}"
"$TV" "$P3/train_summary.py" dpo "${DPO_CK[@]}" > /dev/null || die "dpo train summary failed"
commit "train(pilot_003): DPO 학습 기록(장치 장애 뒤 처음부터, 결정 84), 고른 SFT valid98(보조)" "$P3/train_logs" "$P3/resolved" "$P3/valid98"
TRAIN_GPU=""

# ---- 4. DPO checkpoint 선택 + 중단 규칙
cands=()
for c in "${DPO_CK[@]}"; do sel_jobs "dpo_step${c##*-}" "$c/policy"; cands+=(--cand "dpo_step${c##*-}=$c/policy"); done
run_jobs "$GPUS" || die "DPO selection failed"
"$TV" "$P3/selection/analyze_selection.py" --stage dpo "${cands[@]}" --train-log "$P3/train_logs/dpo_summary.json" \
    --stop-rule --out "$P3/selection_dpo.json" >> "$P3/runs.log" 2>&1 || die "dpo selection analysis failed"
DPO_SELECTED=$("$PY" -c "import json; print(json.load(open('$P3/selection_dpo.json'))['selected']['adapter'])")
PROCEED=$("$PY" -c "import json; print(json.load(open('$P3/selection_dpo.json'))['stop_rule']['proceed_to_vendor100'])")
p3log "dpo selected $DPO_SELECTED stop_rule proceed=$PROCEED"
commit "eval(pilot_003): DPO checkpoint 2개 selection_v2 k=4, 선택 $(basename "$(dirname "$DPO_SELECTED")"), 중단 규칙 진행=$PROCEED" \
    "$P3/selection/runs" "$P3/selection_dpo.json"

# ---- 5. 최종 valid98(보조)
g=$(first_free "valid98 final"); [ -n "$g" ] || die "no usable GPU for valid98 final"
valid98 final "$DPO_SELECTED" "$g" || die "valid98 final failed"
commit "eval(pilot_003): 최종 모델 valid98(보조, greedy)" "$P3/valid98"
p3log "pilot_003 train/select done"
