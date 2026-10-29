#!/usr/bin/env bash
# pilot_006 준비 GPU 작업 큐(결정 114: 작업 하나 = GPU 하나). GPU 한 장에 vLLM 서버(serve6.sh) 하나를 띄우고 주어진 작업을 순서대로 돌린 뒤 서버를 내린다.
#   bash <worktree>/sft_dpo_inventory/pilot_006_prep/gpu_data/jobs6.sh GPU_INDEX PORT JOB [JOB ...]      (JOB: J1 J2 J3 J4 J5S J5R J6 J7)
# - J4: Full 회귀 selection_v2 1표본(seed 20261101) → check_gpu_smoke.py j4. J5S: Partial smoke 10문항 → check_gpu_smoke.py j5(불통과면 큐의 J5R을 건너뜀).
#   J5R: R2 참고 셀(selection_v2, P0.3, k=4). J6: Partial arm 8b 자체 표본(J1과 같은 문항·설정). J7: batch008 첫 응답.
# - 이 파일은 고정 커밋의 git worktree에서 실행한다(규칙 15). 코드는 worktree(WT), 출력·기록은 본 저장소(MAIN)의 정해진 경로에 쓴다.
# - 서버 시작 때 gpu_ok(UUID·메모리·다른 프로세스·Ollama GPU면 /api/ps 비었는지, torch UUID). 작업마다 시작 전에 그 GPU에 서버 말고 다른 프로세스가 없는지 다시 본다.
# - 작업이 끝나면 timeline.jsonl에 한 줄(작업 ID, 종류, UUID, worktree 커밋, 시작, 끝, 상태, 출력). 실패한 작업의 출력은 ABORTED_*로 바꾸고 다음 작업으로 간다.
# - 커밋은 하지 않는다(세션이 결과를 확인하고 커밋한다). J2는 봉인: 정답률을 화면·요약 줄에 쓰지 않는다.
set -u
G=$1; PORT=$2; shift 2
WT=$(cd "$(dirname "$0")/../../.." && pwd)
MAIN=/home/hwkim/assistant_univ
source "$WT/sft_dpo_inventory/pilot_003/gpu_data/gpu_lib.sh"
P3=$MAIN/sft_dpo_inventory/pilot_006_prep/gpu
TL=$P3/timeline.jsonl
COMMIT=$(git -C "$WT" rev-parse HEAD)
VW=/data/hwkim/sftdpo_work/pilot_006_prep/vllm
RAWP=$MAIN/training/generated/pilot_006_prep/raw
cd "$WT"
now() { date -Is; }
tl() { python3 "$WT/sft_dpo_inventory/pilot_006_prep/gpu_data/timeline.py" --file "$TL" --id "$1" --kind "$2" --uuid "${UUID[$G]}" --commit $COMMIT --start "$3" --end "$(now)" --status "$4" --out "${@:5}"; }
gpu_clean() {   # 서버 말고 다른 프로세스가 이 GPU에 없는가
  local spid=$(cat $VW/server_$PORT.pid) other
  { echo "## $(now) before $1 (GPU $G ${UUID[$G]}, server pid $spid)"; nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader; } >> $P3/gpu_check.txt
  other=$(nvidia-smi -i ${UUID[$G]} --query-compute-apps=pid --format=csv,noheader | tr -d ' ' | while read -r q; do
            [ -z "$q" ] && continue; [ "$q" = "$spid" ] && continue
            a=$q; while [ -n "$a" ] && [ "$a" -gt 1 ] && [ "$a" != "$spid" ]; do a=$(ps -o ppid= -p "$a" 2>/dev/null | tr -d ' '); done
            [ "$a" = "$spid" ] && continue; echo "$q"; done)
  [ -z "$other" ] || { p3log "STOP: $1 GPU $G has other process(es): $other"; return 1; }
}
abort_outputs() { local f; for f in "$@"; do [ -e "$f" ] && mv "$f" "$(dirname "$f")/ABORTED_$(basename "$f")"; done; }
p3log "queue start GPU $G (${UUID[$G]}) port $PORT jobs: $* worktree $WT commit $COMMIT"
bash $WT/sft_dpo_inventory/pilot_006_prep/gpu_data/serve6.sh $G $PORT bf16 fi || { p3log "STOP: queue GPU $G server failed"; exit 1; }
rc_all=0
for J in "$@"; do
  gpu_clean $J || { rc_all=1; break; }
  S=$(now); p3log "$J start GPU $G port $PORT"
  case $J in
    J1)
      O=$MAIN/training/generated/pilot_006/self_full; outs=($O/raw/self_full_raw.jsonl $O/manifest.json)
      "$PY" sft_dpo_inventory/pilot_006_prep/gpu_data/collect6.py --mode self --port $PORT --label J1_self_full \
        --inputs sft_dpo_inventory/pilot_006_prep/gpu/inputs/self_questions.jsonl --raw-out ${outs[0]} --out ${outs[1]} \
        > $P3/J1.log 2>&1; rc=$?; kind=self_samples_full ;;
    J3)
      outs=($RAWP/aug300_base_first_raw.jsonl $MAIN/sft_dpo_inventory/pilot_006_prep/aug300/base_first_response.jsonl)
      "$PY" sft_dpo_inventory/pilot_006_prep/gpu_data/collect6.py --mode first --port $PORT --label J3_aug300_first \
        --inputs sft_dpo_inventory/pilot_006_prep/gpu/inputs/aug300_train.jsonl --raw-out ${outs[0]} --out ${outs[1]} \
        > $P3/J3.log 2>&1; rc=$?; kind=first_response_aug300_train ;;
    J2)
      rc=0; outs=(); kind=cell_holdout_base_k4_sealed
      for k in 1 2 3 4; do
        outs+=($MAIN/sft_dpo_inventory/pilot_006_prep/cells/holdout_base_s$k.json $MAIN/sft_dpo_inventory/pilot_006_prep/cells/holdout_base_s$k.log
               $RAWP/holdout_base_s${k}_raw.jsonl)
        "$PY" sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6v.py --port $PORT --model base --label holdout_base --k $k --concurrency 8 \
          --gold sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml --all-items --sealed \
          --out-dir $MAIN/sft_dpo_inventory/pilot_006_prep/cells --raw-dir $RAWP > $P3/J2_s$k.log 2>&1 || { rc=1; break; }
      done ;;
    J4)
      O=$MAIN/sft_dpo_inventory/pilot_006_prep/integration/gpu_full_smoke; kind=regression_full_selection_v2_s1
      outs=($O/full_smoke_s1.json $O/full_smoke_s1.log $RAWP/full_smoke_s1_raw.jsonl $O/check_j4.json)
      "$PY" sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6v.py --port $PORT --model base --label full_smoke --k 1 --concurrency 8 \
        --out-dir $O --raw-dir $RAWP > $P3/J4.log 2>&1 \
        && "$PY" sft_dpo_inventory/pilot_006_prep/gpu_data/check_gpu_smoke.py j4 $O/full_smoke_s1.json $O/check_j4.json >> $P3/J4.log 2>&1; rc=$? ;;
    J5S)
      O=$MAIN/sft_dpo_inventory/pilot_006_prep/integration/gpu_partial_smoke; kind=smoke_partial_10
      IDS=$(head -c 100000 sft_dpo_inventory/pilot_003/selection/selection_v2_ids.txt | tr ',' '\n' | head -10 | paste -sd,)
      outs=($O/partial_smoke_s1.json $O/partial_smoke_s1.log $RAWP/partial_smoke_s1_raw.jsonl $O/check_j5.json)
      "$PY" sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6v.py --port $PORT --model base --label partial_smoke --k 1 --concurrency 8 \
        --grounding-target partial --only "$IDS" --out-dir $O --raw-dir $RAWP > $P3/J5S.log 2>&1 \
        && "$PY" sft_dpo_inventory/pilot_006_prep/gpu_data/check_gpu_smoke.py j5 $O/partial_smoke_s1.json $O/check_j5.json >> $P3/J5S.log 2>&1; rc=$?
      [ $rc -eq 0 ] || SKIP_J5R=1 ;;
    J5R)
      kind=cell_r2_partial_base_k4; outs=()
      if [ "${SKIP_J5R:-0}" = 1 ]; then p3log "J5R skipped (J5S failed)"; rc=1
      else rc=0
        for k in 1 2 3 4; do
          outs+=($MAIN/sft_dpo_inventory/pilot_006_prep/cells/r2_partial_base_s$k.json $MAIN/sft_dpo_inventory/pilot_006_prep/cells/r2_partial_base_s$k.log
                 $RAWP/r2_partial_base_s${k}_raw.jsonl)
          "$PY" sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6v.py --port $PORT --model base --label r2_partial_base --k $k --concurrency 8 \
            --grounding-target partial --out-dir $MAIN/sft_dpo_inventory/pilot_006_prep/cells --raw-dir $RAWP > $P3/J5R_s$k.log 2>&1 || { rc=1; break; }
        done
      fi ;;
    J6)
      O=$MAIN/training/generated/pilot_006/self_partial; outs=($O/raw/self_partial_raw.jsonl $O/manifest.json); kind=self_samples_partial
      "$PY" sft_dpo_inventory/pilot_006_prep/gpu_data/collect6.py --mode self --grounding-target partial --port $PORT --label J6_self_partial \
        --inputs sft_dpo_inventory/pilot_006_prep/gpu/inputs/self_questions.jsonl --raw-out ${outs[0]} --out ${outs[1]} \
        > $P3/J6.log 2>&1; rc=$? ;;
    J7)
      outs=($RAWP/batch008_base_first_raw.jsonl $MAIN/sft_dpo_inventory/batch008/base_first_response.jsonl); kind=first_response_batch008
      "$PY" sft_dpo_inventory/pilot_006_prep/gpu_data/collect6.py --mode first --port $PORT --label J7_batch008_first \
        --inputs sft_dpo_inventory/batch008/inputs_first_response.jsonl --raw-out ${outs[0]} --out ${outs[1]} \
        > $P3/J7.log 2>&1; rc=$? ;;
    *) p3log "unknown job $J"; rc=1; outs=(); kind=unknown ;;
  esac
  if [ $rc -eq 0 ]; then tl $J $kind "$S" ok "${outs[@]}"; p3log "$J done GPU $G"
  else abort_outputs "${outs[@]}"; tl $J $kind "$S" "failed(exit $rc)" "${outs[@]}"; p3log "$J FAILED GPU $G exit $rc"; rc_all=1; fi
done
kill $(cat $VW/server_$PORT.pid) 2>/dev/null; rm -f $VW/server_$PORT.pid; sleep 10
p3log "queue end GPU $G rc=$rc_all"
exit $rc_all
