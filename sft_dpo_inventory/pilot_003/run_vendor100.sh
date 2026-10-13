#!/usr/bin/env bash
# pilot_003 업체 100 평가(PLAN 4절, PROTOCOL_v3 5·6절). 중단 규칙 통과(selection_dpo.json, HF-base→dpo_step174 CI [1.28, 13.01]) 뒤에만 돈다.
#   bash run_vendor100.sh hf        # HF 셀: 업체 100 HF-base·HF-최종 k=8, aux_test_v1 HF-base·HF-최종 k=4(GPU 3장에 표본을 나눔, 장치 일치 확인 통과)
#   bash run_vendor100.sh e         # 참고 셀 E(qwen3:8b, Ollama 연속 방식) 업체 100 k=8, Ollama GPU(UUID 48f798cc…), 결정 55 guard
# - HF와 Ollama는 동시에 돌리지 않는다(e는 hf가 끝난 뒤, HF 프로세스가 없을 때만).
# - 셀마다 한 번만 잰다. 출력이 있으면 멈춘다. 셀이 끝날 때마다 커밋·push한다.
set -u
source "$(dirname "$0")/hf_samples.sh"
cd /home/hwkim/assistant_univ
V_GOLD=evaluation/vendor100/gold.yaml
A_GOLD=sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml
GUARD=sft_dpo_inventory/pilot_002/ollama_gpu_guard.py
FINAL=$("$PY" -c "import json; print(json.load(open('$P3/selection_dpo.json'))['selected']['adapter'])")
die() { p3log "STOP: $1"; exit 1; }
commit() {
  local msg=$1; shift
  git add "$@" "$P3/runs.log" "$P3/gpu_check.txt" && git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "$msg

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" || die "commit failed: $msg"
  git push -q origin geoflow/sft-dpo-t2pc >> "$P3/runs.log" 2>&1 || p3log "push rejected: $msg (CLAUDE.md 14번 절차 필요)"
}
check_hashes() {
  [ "$(sha256sum $V_GOLD | cut -c1-64)" = f99bc5fdef623e973901e5b339ede3c7f4e36cfa133887ea933e9683a7d8b4f0 ] || die "vendor gold sha mismatch"
  [ "$("$PY" -c 'import execution_spec as e;print(e.code_fingerprint(".")["sha256"][:8])')" = 791c4a68 ] || die "fingerprint mismatch"
  [ "$(sha256sum "$FINAL/adapter_model.safetensors" | cut -c1-64)" = bf6e2f87d43724acb74607e267462bebf610ce7915d51bc395dea697fb4a0b48 ] || die "final adapter sha mismatch"
  p3log "precheck ok: vendor gold f99bc5fd, fingerprint 791c4a68, final adapter bf6e2f87 ($FINAL)"
}

case $1 in
  hf)
    check_hashes
    p3log "vendor100 hf start"
    # 짝 셀의 표본을 번갈아 넣어 두 셀이 함께 진행되게 한다(장치 일치 확인 통과라 GPU 배정은 자유).
    for k in 1 2 3 4 5 6 7 8; do
      JOBS+=("v100_HF-base|-|$V_GOLD|-|$k|$P3/vendor100/runs" "v100_HF-final|$FINAL|$V_GOLD|-|$k|$P3/vendor100/runs"); done
    run_jobs "$GPUS" || die "vendor100 HF cells failed"
    commit "eval(pilot_003): 업체 100 HF-base·HF-최종 k=8(PROTOCOL_v3 5절, 한 번 측정)" "$P3/vendor100/runs"
    for k in 1 2 3 4; do
      JOBS+=("aux_HF-base|-|$A_GOLD|-|$k|$P3/aux_test/runs" "aux_HF-final|$FINAL|$A_GOLD|-|$k|$P3/aux_test/runs"); done
    run_jobs "$GPUS" || die "aux HF cells failed"
    commit "eval(pilot_003): aux_test_v1 HF-base·HF-최종 k=4(보고만)" "$P3/aux_test/runs"
    p3log "vendor100 hf done" ;;
  e)
    # 참고 셀 E: 판정하지 않는다. 결정 31: Ollama 버전과 E digest를 먼저 확인해 기록한다. 버전은 재부팅 뒤 사람이 컨테이너를 다시 띄우며
    # 0.35.1 → 0.40.3이 됐다(결정 84 뒤). E는 이 pilot에서 연속 방식으로 새로 재므로 셀 안의 버전은 하나다. 예전 E 기록과 직접 비교하지 않는다.
    check_hashes
    OLLAMA_UUID_E=GPU-48f798cc-9437-50ac-d604-448bbad7b311
    VER=$(curl -s localhost:11434/api/version | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["version"])')
    DIG=$(curl -s localhost:11434/api/tags | "$PY" -c 'import json,sys; print(next(m["digest"][:12] for m in json.load(sys.stdin)["models"] if m["name"]=="qwen3:8b"))')
    p3log "E precheck: ollama version $VER, qwen3:8b digest $DIG"
    [ "$DIG" = 500a1f067a9f ] || die "E digest $DIG != 500a1f067a9f"
    [ "$VER" = "${EXPECT_OLLAMA_VERSION:-0.40.3}" ] || die "Ollama version $VER != ${EXPECT_OLLAMA_VERSION:-0.40.3}"
    docker exec ollama nvidia-smi -L 2>&1 | grep -q "$OLLAMA_UUID_E" || die "Ollama container does not see $OLLAMA_UUID_E"
    pgrep -u "$(id -u)" -f '[h]f_eval_thinking.py|[e]val_valid98.py|[t]raining.train_' >/dev/null && die "HF process running; HF and Ollama must not overlap"
    OUT=$P3/vendor100/runs; files=()
    for k in 1 2 3 4 5 6 7 8; do
      p=$OUT/v100_E_s$k
      [ -e "$p.json" ] || [ -e "$p.jsonl" ] && die "$p exists"
      "$PY" "$GUARD" precheck --gpu-uuid $OLLAMA_UUID_E --version "$VER" --allow-loaded qwen3:8b --out "${p}_gpu_precheck.json" >> "$P3/runs.log" 2>&1 \
        || die "v100_E_s$k precheck failed (decision 55)"
      { echo "## $(date -Is) ollama v100_E_s$k"; nvidia-smi --query-gpu=index,uuid,memory.used --format=csv,noheader
        nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader
        echo "## ollama container"; docker exec ollama nvidia-smi -L 2>&1; curl -s localhost:11434/api/ps; echo; } >> "$P3/gpu_check.txt" 2>&1
      since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
      p3log "ollama v100_E_s$k start (qwen3:8b) seed $((20261100 + k)) GPU $OLLAMA_UUID_E isolation continuous version $VER"
      "$PY" evaluate_vendor100.py --gold "$V_GOLD" llm --model qwen3:8b --reference-date 2026-09-25 --condition-check \
        --model-think auto --model-state keep_loaded --temperature 0.6 --top-p 0.95 --top-k 20 --min-p 0 --repeat-penalty 1 \
        --presence-penalty 0 --frequency-penalty 0 --seed $((20261100 + k)) --record-env --raw-out "$RAW/v100_E_s${k}_raw.jsonl" \
        --out "$p.json" > "$p.log" 2>&1 &
      pid=$!
      "$PY" "$GUARD" watch --gpu-uuid $OLLAMA_UUID_E --pid $pid --rows "$p.jsonl" --model qwen3:8b --out "${p}_gpu_guard.json" > "${p}_gpu_guard.log" 2>&1
      grc=$?; wait $pid; rc=$?
      docker logs ollama --since "$since" 2>&1 | grep -A4 "sampler params" | grep -E "repeat_penalty|top_k|temp" \
        | sed 's/^[[:space:]]*//' | sort | uniq -c > "${p}_sampler_params.txt"
      p3log "ollama v100_E_s$k exit=$rc guard=$grc"
      if [ $grc -ne 0 ]; then
        for f in "$p".* "${p}_"*; do [ -e "$f" ] && mv "$f" "$(dirname "$f")/ABORTED_gpu_$(basename "$f")"; done
        die "v100_E_s$k aborted by decision 55 guard"
      fi
      [ $rc -eq 0 ] || die "ollama v100_E_s$k failed rc=$rc"
      files+=("$p.json" "$p.jsonl" "$p.log" "${p}_gpu_guard.json" "${p}_gpu_guard.log" "${p}_gpu_precheck.json" "${p}_sampler_params.txt")
      [ -e "$p.spec.json" ] && files+=("$p.spec.json")
    done
    commit "eval(pilot_003): 업체 100 참고 셀 E(qwen3:8b, Ollama $VER 연속, k=8, 결정 55 확인 통과)" "${files[@]}"
    p3log "vendor100 E done" ;;
  *) die "unknown mode $1" ;;
esac
