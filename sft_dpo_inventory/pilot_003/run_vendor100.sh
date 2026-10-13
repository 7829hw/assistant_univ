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
  *) die "unknown mode $1" ;;
esac
