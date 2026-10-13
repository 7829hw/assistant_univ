#!/usr/bin/env bash
# pilot_003 HF sampling 표본 실행기(PROTOCOL_v3 3절, 결정 83). source해서 run_jobs를 부른다.
#   JOBS+=("LABEL|ADAPTER_OR_-|GOLD|ONLY_FILE_OR_-|K|OUTDIR")   # 표본 하나 = 프로세스 하나
#   run_jobs "0 1 2 3"                                           # 쓸 GPU 목록. 빈 GPU에 표본을 하나씩 나눈다
# - 생성 설정: calibration_001과 같다(do_sample, temperature 0.6, top_p 0.95, top_k 20, min_p 0, repetition_penalty 1,
#   enable_thinking, max_new_tokens 8192). 회차 seed S_k = 20261100 + k, 호출 seed는 EV.call_seed(S_k, 문항 id, 호출 번호).
# - 장치 일치 확인(device_check/compare.json)이 모두 같음이라 표본을 GPU에 자유롭게 나눈다. 표본마다 장치를 meta(record-env)와 runs.log에 남긴다.
# - GPU를 쓰기 전에 매번 gpu_ok(UUID·메모리·다른 프로세스, GPU 3은 Ollama 모델 없음)를 확인한다. 쓸 GPU가 없으면 기다린다(최대 2시간, 넘으면 멈춤).
# - 출력이 이미 있으면 멈춘다(재실행 없음). 한 표본이라도 실패하면 멈춘다. 원문은 ignore 경로(training/generated/pilot_003/raw/).
source "$(dirname "${BASH_SOURCE[0]}")/gpu_lib.sh"
REPO=/home/hwkim/assistant_univ
RAW=$REPO/training/generated/pilot_003/raw
SAMPLING="--do-sample --temperature 0.6 --top-p 0.95 --top-k 20 --min-p 0 --repetition-penalty 1"
JOBS=()

launch() {   # job gpu -> pid in LAST_PID
  local label adapter gold only k outdir g=$2
  IFS='|' read -r label adapter gold only k outdir <<< "$1"
  local p=$outdir/${label}_s$k
  [ -e "$p.json" ] && { p3log "STOP: $p.json exists"; return 1; }
  mkdir -p "$outdir" "$RAW"
  local extra=(); [ "$adapter" = - ] || extra+=(--adapter "$adapter"); [ "$only" = - ] || extra+=(--only "$(cat "$only")")
  (cd "$REPO" && CUDA_VISIBLE_DEVICES=$g "$PY" sft_dpo_inventory/thinking_prep_001/hf_eval_thinking.py --gold "$gold" --condition-check \
     $SAMPLING --seed $((20261100 + k)) --record-env --out "$p.json" --raw-out "$RAW/${label}_s${k}_raw.jsonl" "${extra[@]}" \
     > "$p.log" 2>&1) &
  LAST_PID=$!
  p3log "hf ${label}_s$k start GPU $g (${UUID[$g]}) seed $((20261100 + k)) adapter $adapter pid $LAST_PID"
}

run_jobs() {   # "gpus"
  local pool=($1) i=0 waited=0
  declare -A busy=() jobof=()
  while [ $i -lt ${#JOBS[@]} ] || [ ${#busy[@]} -gt 0 ]; do
    local started=0
    if [ $i -lt ${#JOBS[@]} ]; then
      for g in "${pool[@]}"; do
        [ -n "${busy[$g]:-}" ] && continue
        gpu_ok "$g" "hf ${JOBS[$i]%%|*}" || continue
        launch "${JOBS[$i]}" "$g" || return 1
        busy[$g]=$LAST_PID; jobof[$g]=${JOBS[$i]}; i=$((i+1)); started=1; waited=0
        break
      done
    fi
    [ $started = 1 ] && { sleep 20; continue; }
    if [ ${#busy[@]} -gt 0 ]; then
      local done_g=""
      while [ -z "$done_g" ]; do
        for g in "${!busy[@]}"; do kill -0 "${busy[$g]}" 2>/dev/null || { done_g=$g; break; }; done
        [ -z "$done_g" ] && sleep 15
      done
      wait "${busy[$done_g]}"; local rc=$?
      local label k
      IFS='|' read -r label _ _ _ k _ <<< "${jobof[$done_g]}"
      p3log "hf ${label}_s$k exit=$rc GPU $done_g"
      unset "busy[$done_g]" "jobof[$done_g]"
      [ $rc -eq 0 ] || { p3log "STOP: hf ${label}_s$k failed rc=$rc"; for p in "${busy[@]}"; do wait "$p"; done; return 1; }
    else
      waited=$((waited+60)); [ $waited -gt 7200 ] && { p3log "STOP: no usable GPU for 2 h"; return 1; }
      sleep 60
    fi
  done
  JOBS=()
  return 0
}
