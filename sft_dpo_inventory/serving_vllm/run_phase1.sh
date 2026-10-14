#!/usr/bin/env bash
# serving_vllm 1단계(결정 89): 서버 기동 → 입력 일치 확인(다르면 멈춤) → seed 재현성(5문항, 같은 seed 두 번, 다른 GPU 한 번).
#   bash run_phase1.sh   (aux E 측정이 끝난 뒤, Ollama 측정 중에는 돌리지 않는다)
# 서버: A = GPU 0, 포트 8100 / B = GPU 1, 포트 8101. 서버는 끝나도 내리지 않는다(2단계 셀에서 쓴다).
set -u
cd /home/hwkim/assistant_univ
SV=sft_dpo_inventory/serving_vllm
WORK=/data/hwkim/sftdpo_work/serving_vllm
RAW=training/generated/serving_vllm/raw
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
GOLD=sft_dpo_inventory/conversion_diag/selection_gold.yaml
REPRO=old44/g02,contrast/c03c,indepv2/n06,indepv3/m09,indepv4/k08   # pilot_003 device_check와 같은 5문항
SAMPLING="--do-sample --temperature 0.6 --top-p 0.95 --top-k 20 --min-p 0 --repetition-penalty 1"
mkdir -p "$SV/repro" "$RAW"
log() { echo "== $1 $(date -Is)" >> "$SV/runs.log"; }
die() { log "STOP: $1"; exit 1; }
pgrep -u "$(id -u)" -f '[e]valuate_vendor100.py llm' >/dev/null && die "Ollama measurement running"
[ "$(curl -s localhost:11434/api/ps)" = '{"models":[]}' ] || log "note: Ollama has a model loaded (GPU 2 not used in phase 1)"
[ "$("$PY" -c 'import execution_spec as e;print(e.code_fingerprint(".")["sha256"][:8])')" = 791c4a68 ] || die "fingerprint mismatch"
bash $SV/serve.sh 0 8100 || die "server A failed"
bash $SV/serve.sh 1 8101 || die "server B failed"
for port in 8100 8101; do
  "$PY" $SV/check_inputs.py --base-url http://127.0.0.1:$port > "$SV/input_check_$port.log" 2>&1 || die "input check failed on $port (측정하지 않음)"
  cp $SV/input_check.json $SV/input_check_$port.json
  log "input check ok port $port"
done
rm -f $SV/input_check.json
run() {   # name port model
  "$PY" $SV/vllm_eval_thinking.py --base-url http://127.0.0.1:$2 --served-model $3 --gold $GOLD --only $REPRO --condition-check \
    $SAMPLING --seed 20261101 --server-meta $WORK/server_$2.json --out $SV/repro/$1.json --raw-out $RAW/repro_$1_raw.jsonl \
    > $SV/repro/$1.log 2>&1 || die "repro $1 failed"
  log "repro $1 done"
}
for m in base final; do
  run ${m}_A1 8100 $m
  run ${m}_A2 8100 $m
  run ${m}_B1 8101 $m
done
"$PY" - <<'PYEOF' > $SV/repro/compare.json
import json
from pathlib import Path
d = Path("sft_dpo_inventory/serving_vllm/repro")
def calls(name):
    rows = json.loads((d / f"{name}.json").read_text())["rows"]
    return {(r["id"], i): c["raw_sha256"] for r in rows for i, c in enumerate(r["hf_calls"])}
out = {}
for m in ("base", "final"):
    a1, a2, b1 = calls(f"{m}_A1"), calls(f"{m}_A2"), calls(f"{m}_B1")
    out[m] = {"calls": len(a1), "same_server_repeat_equal": sum(a1.get(k) == a2.get(k) for k in a1) if a1.keys() == a2.keys() else "call sets differ",
              "cross_gpu_equal": sum(a1.get(k) == b1.get(k) for k in a1) if a1.keys() == b1.keys() else "call sets differ",
              "call_sets": {"A1": len(a1), "A2": len(a2), "B1": len(b1)}}
print(json.dumps(out, ensure_ascii=False, indent=1))
PYEOF
log "repro compare $(tr -d '\n ' < $SV/repro/compare.json)"
git add $SV/input_check_*.json $SV/input_check_*.log $SV/repro $SV/runs.log $SV/gpu_check.txt 2>/dev/null
git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "eval(serving_vllm): 입력 일치 확인(selection_v2 10문항)과 seed 재현성(5문항)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" || die "commit failed"
git push -q origin geoflow/sft-dpo-t2pc >> $SV/runs.log 2>&1 || log "push rejected"
log "phase1 done"
