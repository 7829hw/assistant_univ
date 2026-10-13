#!/usr/bin/env bash
# pilot_003 학습과 checkpoint 선택(PLAN.md 4–6절, PROTOCOL_v3 7절). 단계가 실패하면 멈추고 기록한다(재실행 없음).
# 1. SFT 학습(GPU 1장) ‖ 다른 GPU에서 HF-base selection_v2 k=4(선택 기준값)
# 2. SFT checkpoint 2개(epoch 1·2) selection_v2 k=4 → 선택(analyze_selection.py)
# 3. DPO config 확정 → DPO 학습(GPU 1장) ‖ 다른 GPU에서 고른 SFT의 valid98 greedy(보조 기록)
# 4. DPO checkpoint 2개(50%·100%) selection_v2 k=4 → 선택 + 중단 규칙(HF-base → 고른 DPO checkpoint, CI 하한 > 0)
# 5. 최종 모델 valid98 greedy(보조 기록)
# 단계마다 커밋·push한다(CLAUDE.md 2·14번). GPU는 결정 83: 매번 gpu_ok 확인, Ollama는 이 스크립트가 도는 동안 부르지 않는다.
set -u
source "$(dirname "$0")/hf_samples.sh"
cd /home/hwkim/assistant_univ
WORK=/home/hwkim/sftdpo_work/pilot_003
SEL_GOLD=sft_dpo_inventory/conversion_diag/selection_gold.yaml
SEL_IDS=$P3/selection/selection_v2_ids.txt
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
mkdir -p "$P3/selection/runs" "$P3/valid98" "$P3/train_logs" "$P3/resolved" "$WORK/logs" "$RAW"
die() { p3log "STOP: $1"; exit 1; }
commit() {   # msg paths...
  local msg=$1; shift
  git add "$@" "$P3/runs.log" "$P3/gpu_check.txt" && git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "$msg

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" || die "commit failed: $msg"
  git push -q origin geoflow/sft-dpo-t2pc >> "$P3/runs.log" 2>&1 || p3log "push rejected: $msg (CLAUDE.md 14번 절차 필요)"
}
first_free() {   # 학습용 GPU: 0→3 순서로 첫 사용 가능 GPU
  local g; for g in 0 1 2 3; do gpu_ok $g "$1" && { echo $g; return; }; done
}
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
train_wait() {   # stage
  wait $TRAIN_PID; local rc=$?; kill $SMI_PID 2>/dev/null; wait $SMI_PID 2>/dev/null
  p3log "$1 train exit=$rc (CUDA $TRAIN_GPU)"; [ $rc -eq 0 ] || die "$1 train failed"
  cp "$WORK/metrics/$1_profile.json" "$P3/train_logs/"
  local last; last=$(ls -d "$WORK"/checkpoints/$1/checkpoint-* | sort -t- -k2 -n | tail -1)
  "$PY" -c "import json,sys; s=json.load(open(sys.argv[1])); json.dump(s['log_history'], open(sys.argv[2],'w'), indent=1)" \
      "$last/trainer_state.json" "$P3/train_logs/$1_log_history.json"
}
others() {   # 학습 GPU를 뺀 GPU 목록
  local g out=""; for g in 0 1 2 3; do [ "$g" = "${TRAIN_GPU:-x}" ] || out="$out $g"; done; echo $out
}
sel_jobs() {   # label adapter
  local k; for k in 1 2 3 4; do JOBS+=("$1|$2|$SEL_GOLD|$SEL_IDS|$k|$P3/selection/runs"); done
}
valid98() {   # name adapter gpu
  p3log "valid98 $1 start (CUDA $3)"
  CUDA_VISIBLE_DEVICES=$3 "$PY" sft_dpo_inventory/pilot_001/valid98/eval_valid98.py --label "valid98_$1" \
      --out "$P3/valid98/valid98_$1.json" --raw-out "$RAW/valid98_$1_raw.jsonl" --adapter "$2" > "$P3/valid98/valid98_$1.log" 2>&1
  local rc=$?; p3log "valid98 $1 exit=$rc (CUDA $3)"; return $rc
}

p3log "pilot_003 train/select start"
[ -e "$WORK/checkpoints" ] && die "$WORK/checkpoints already exists"
grep -q "학습 시작 전 고정" "$P3/PLAN.md" || die "PLAN.md not fixed"

# ---- 1. SFT 학습 ‖ HF-base 기준값
train_start sft training/configs/qwen3_8b_t2pc_thinking_pilot003_sft.yaml
sleep 120
sel_jobs HF-base -
run_jobs "$(others)" || die "HF-base selection failed"
commit "eval(pilot_003): selection_v2 HF-base 기준값(k=4, PROTOCOL_v3 7절 2)" "$P3/selection/runs"
train_wait sft
mapfile -t SFT_CK < <(ls -d "$WORK"/checkpoints/sft/checkpoint-* | sort -t- -k2 -n)
[ ${#SFT_CK[@]} -eq 2 ] || die "expected 2 SFT checkpoints, got ${#SFT_CK[@]}"
"$TV" "$P3/train_summary.py" sft "${SFT_CK[@]}" > /dev/null || die "sft train summary failed"
commit "train(pilot_003): SFT 학습 기록(checkpoint 2개, adapter는 저장소 밖)" "$P3/train_logs"
TRAIN_GPU=""

# ---- 2. SFT checkpoint 선택
cands=()
for c in "${SFT_CK[@]}"; do sel_jobs "sft_step${c##*-}" "$c"; cands+=(--cand "sft_step${c##*-}=$c"); done
run_jobs "0 1 2 3" || die "SFT selection failed"
"$TV" "$P3/selection/analyze_selection.py" --stage sft "${cands[@]}" --train-log "$P3/train_logs/sft_summary.json" \
    --out "$P3/selection_sft.json" >> "$P3/runs.log" 2>&1 || die "sft selection analysis failed"
SFT_SELECTED=$("$PY" -c "import json; print(json.load(open('$P3/selection_sft.json'))['selected']['adapter'])")
p3log "sft selected $SFT_SELECTED"
commit "eval(pilot_003): SFT checkpoint 2개 selection_v2 k=4, 선택 $(basename "$SFT_SELECTED")" "$P3/selection/runs" "$P3/selection_sft.json"

# ---- 3. DPO 학습 ‖ 고른 SFT valid98(보조)
sed "s#adapter_path: SELECTED_PILOT_003_SFT_REQUIRED#adapter_path: $SFT_SELECTED#" \
  training/configs/qwen3_8b_t2pc_thinking_pilot003_dpo.yaml > "$P3/resolved/qwen3_8b_t2pc_thinking_pilot003_dpo.resolved.yaml"
grep -q "adapter_path: $SFT_SELECTED" "$P3/resolved/qwen3_8b_t2pc_thinking_pilot003_dpo.resolved.yaml" || die "dpo config not resolved"
train_start dpo "$P3/resolved/qwen3_8b_t2pc_thinking_pilot003_dpo.resolved.yaml"
sleep 120
g=""; for x in $(others); do gpu_ok $x "valid98 sft" && { g=$x; break; }; done
[ -n "$g" ] || die "no usable GPU for valid98 sft"
valid98 sft "$SFT_SELECTED" "$g" || die "valid98 sft failed"
train_wait dpo
mapfile -t DPO_CK < <(ls -d "$WORK"/checkpoints/dpo/checkpoint-* | sort -t- -k2 -n)
[ ${#DPO_CK[@]} -eq 2 ] || die "expected 2 DPO checkpoints, got ${#DPO_CK[@]}"
"$TV" "$P3/train_summary.py" dpo "${DPO_CK[@]}" > /dev/null || die "dpo train summary failed"
commit "train(pilot_003): DPO 학습 기록(checkpoint 2개), 고른 SFT valid98(보조)" "$P3/train_logs" "$P3/resolved" "$P3/valid98"
TRAIN_GPU=""

# ---- 4. DPO checkpoint 선택 + 중단 규칙
cands=()
for c in "${DPO_CK[@]}"; do sel_jobs "dpo_step${c##*-}" "$c/policy"; cands+=(--cand "dpo_step${c##*-}=$c/policy"); done
run_jobs "0 1 2 3" || die "DPO selection failed"
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
