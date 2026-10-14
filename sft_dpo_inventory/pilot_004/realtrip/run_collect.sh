#!/usr/bin/env bash
# pilot_004 작업 2(결정 98): 실차 대조 묶음 8b 표본 수집 → 필터 → 문항별 정리 → 커밋.
# vLLM BF16 base, flashinfer, 서버 3개(GPU 0·1·2, 포트 8300–8302, 결정 100), 서버마다 동시 요청 8.
set -u
cd /home/hwkim/assistant_univ
P4=sft_dpo_inventory/pilot_004
RT=$P4/realtrip
WORK=/data/hwkim/sftdpo_work/pilot_004/vllm
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
export HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
log() { echo "== $1 $(date -Is)" >> "$P4/runs.log"; }
die() { log "STOP: $1"; for pf in $WORK/server_830*.pid; do [ -e "$pf" ] && kill $(cat $pf) 2>/dev/null; done; exit 1; }
[ "$("$PY" -c 'import execution_spec as e;print(e.code_fingerprint(".")["sha256"][:8])')" = 791c4a68 ] || die "fingerprint mismatch"
[ "$(curl -s localhost:11434/api/ps)" = '{"models":[]}' ] || die "Ollama model loaded (GPU 2 needed)"
for g in 0 1 2; do bash $P4/serve3.sh $g 830$g bf16 fi || die "server $g failed"; done
start=$(date +%Y-%m-%dT%H:%M:%S)
log "realtrip collect start"
"$PY" $RT/collect_vllm.py --ports 8300,8301,8302 --concurrency 8 > $RT/collect.log 2>&1 || die "collect failed"
end=$(date +%Y-%m-%dT%H:%M:%S)
log "realtrip collect done"
"$PY" - "$start" "$end" > $RT/request_log.json <<'PYEOF'
import json, sys
from datetime import datetime
sys.path.insert(0, "sft_dpo_inventory/serving_vllm_fp8")
from run_cell import request_log_summary
s, e = (datetime.fromisoformat(x) for x in sys.argv[1:3])
out = {}
for port in (8300, 8301, 8302):
    sm = json.load(open(f"/data/hwkim/sftdpo_work/pilot_004/vllm/server_{port}.json"))
    out[str(port)] = {"gpu_uuid": sm["gpu_uuid"], "attention_backend(server log)": sm["log_attention_backend"],
                      "sampler(server log)": [l.split("] ", 1)[-1] for l in sm["log_flashinfer_sampler_lines"] if "sampling" in l],
                      "request_log": request_log_summary(sm["server_log"], s, e)}
print(json.dumps(out, ensure_ascii=False, indent=1))
PYEOF
for pf in $WORK/server_830*.pid; do kill $(cat $pf) 2>/dev/null; done
log "servers stopped"
"$PY" $RT/filter_realtrip.py > $RT/filter.log 2>&1 || die "filter failed"
"$PY" $RT/report_realtrip.py > $RT/report.log 2>&1 || die "report failed"
git add $RT $P4/serve3.sh $P4/runs.log $P4/gpu_check.txt
git -c user.name="Hyeongwoo Kim" -c user.email="7829hw@gmail.com" commit -q -m "data(pilot_004): 실차 대조 묶음 8b 표본 수집(vLLM BF16 flashinfer, 문항당 32, 결정 98), 필터·문항별 정리

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0116EAU9dFUyCZgz7zW8W6EG" || die "commit failed"
git push -q origin geoflow/sft-dpo-t2pc >> $P4/runs.log 2>&1 || log "push rejected"
log "realtrip done"
