#!/usr/bin/env bash
# batch005에서 정답 표본이 없는 질문의 teacher trace 수집(작업 지시 3, 결정 21과 같은 설정). 학습에 넣을지는 정하지 않는다.
# Ollama(qwen3.8:27b, 컨테이너 GPU 2). CLAUDE.md 7번: 이 수집 중에는 다른 Ollama 호출과 HF 작업을 하지 않는다.
# 사전 확인: Ollama 버전, 올라간 모델 없음, GPU 2에 다른 프로세스 없음(HF 작업이 끝났는지). 재실행 없음.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PY=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
cd "$REPO"
log() { echo "== $1 $(date -Is)" >> "$HERE/runs.log"; }
G2=GPU-a644de12-2a2c-ca3d-4822-b80f704b0b21
apps=$(nvidia-smi -i $G2 --query-compute-apps=pid,used_memory,process_name --format=csv,noheader | tr '\n' ';')
ver=$(curl -s localhost:11434/api/version); ps=$(curl -s localhost:11434/api/ps)
log "teacher precheck version=$ver ps=$ps gpu2_apps=[$apps]"
if [ -n "$apps" ] || [ "$ps" != '{"models":[]}' ]; then log "STOP: teacher GPU 2 busy or Ollama model loaded"; exit 1; fi
"$PY" - <<'PYEOF' || { log "STOP: teacher targets"; exit 1; }
import json
from pathlib import Path
f = json.loads(Path("sft_dpo_inventory/pilot_prep_005/traces/batch005_filtered.json").read_text(encoding="utf-8"))
targets = [{"corpus_file": "training/generated/pilot_prep_005/trace_inputs/batch005/sft_train.jsonl", "source_record_id": sid}
           for sid in f["no_correct_sample_questions"]]
Path("sft_dpo_inventory/pilot_prep_005/teacher/batch005_no_correct_targets.json").write_text(
    json.dumps(targets, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(targets))
PYEOF
log "teacher batch005_no_correct start (Ollama qwen3.8:27b, GPU 2)"
"$PY" sft_dpo_inventory/pilot_prep_003/teacher/collect_teacher.py \
    --targets sft_dpo_inventory/pilot_prep_005/teacher/batch005_no_correct_targets.json \
    --out training/generated/thinking_traces/teacher_qwen3.8_27b/batch005_no_correct \
    --summary sft_dpo_inventory/pilot_prep_005/teacher/batch005_no_correct > "$HERE/teacher/batch005_no_correct.log" 2>&1
rc=$?; log "teacher batch005_no_correct exit=$rc"; exit $rc
