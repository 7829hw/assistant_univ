#!/usr/bin/env bash
# batch006에서 정답 표본이 없는 질문의 teacher trace(결정 81: 결정 50과 같이 처리). collect_teacher.py(결정 21과 같은 설정: qwen3.8:27b,
# think true, temperature 0.6, 질문당 8표본, seed SEED_BASE + 1000×순번 + 표본 번호).
# Ollama 연속 방식(결정 79: 문항·표본마다 모델을 내리지 않음), GPU 3(컨테이너 device_ids "3"), 결정 55 guard:
# precheck(컨테이너 GPU, 버전 0.35.1, 올라간 모델 없음, GPU 3 다른 프로세스 없음) + watch(첫 문항 100% GPU, 표본별 eval_count/eval_duration ≥ 30 tok/s).
# 이 수집 중에는 GPU 3에서 HF를 돌리지 않고 다른 Ollama 호출을 하지 않는다(결정 83, CLAUDE.md 7번). 재실행 없음.
set -u
source "$(dirname "$0")/../gpu_lib.sh"
TV=/tmp/claude-1004/-home-hwkim-assistant-univ/8a5ac38d-cd63-43c9-84e1-7ee2d9b3545b/scratchpad/tokvenv/bin/python
GUARD=/home/hwkim/assistant_univ/sft_dpo_inventory/pilot_002/ollama_gpu_guard.py
G3=${UUID[3]}
cd /home/hwkim/assistant_univ
T=sft_dpo_inventory/pilot_003/teacher
OUT=training/generated/thinking_traces/teacher_qwen3.8_27b/batch006_no_correct
[ -e "$OUT" ] && { p3log "STOP: teacher output exists"; exit 1; }
"$TV" - <<'PYEOF' || { p3log "STOP: teacher targets"; exit 1; }
import json
from pathlib import Path
f = json.loads(Path("sft_dpo_inventory/pilot_003/traces/batch006_filtered.json").read_text(encoding="utf-8"))
targets = [{"corpus_file": "training/generated/pilot_003/trace_inputs/batch006/sft_train.jsonl", "source_record_id": sid}
           for sid in f["no_correct_sample_questions"]]
Path("sft_dpo_inventory/pilot_003/teacher/batch006_no_correct_targets.json").write_text(
    json.dumps(targets, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(targets))
PYEOF
n=$("$TV" -c "import json; print(len(json.load(open('$T/batch006_no_correct_targets.json'))))")
[ "$n" = 0 ] && { p3log "teacher: no target questions, skipped"; exit 0; }
[ -z "$(nvidia-smi -i $G3 --query-compute-apps=pid --format=csv,noheader)" ] || { p3log "STOP: teacher GPU 3 busy"; exit 1; }
"$TV" "$GUARD" precheck --gpu-uuid "$G3" --out "$T/gpu_precheck.json" >> "$P3/runs.log" 2>&1 || { p3log "STOP: teacher precheck failed (decision 55)"; exit 1; }
p3log "teacher batch006_no_correct start ($n questions, Ollama qwen3.8:27b, GPU 3, continuous)"
"$TV" sft_dpo_inventory/pilot_prep_003/teacher/collect_teacher.py --targets "$T/batch006_no_correct_targets.json" \
    --out "$OUT" --summary "$T/batch006_no_correct" > "$T/batch006_no_correct.log" 2>&1 &
pid=$!
for _ in $(seq 60); do [ -e "$OUT/traces.jsonl" ] && break; kill -0 $pid 2>/dev/null || break; sleep 2; done
"$TV" "$GUARD" watch --gpu-uuid "$G3" --pid $pid --rows "$OUT/traces.jsonl" --model qwen3.8:27b --out "$T/gpu_guard.json" > "$T/gpu_guard.log" 2>&1
grc=$?; wait $pid; rc=$?
p3log "teacher batch006_no_correct exit=$rc guard=$grc"
if [ $grc -ne 0 ]; then p3log "STOP: teacher aborted by decision 55 guard"; exit 2; fi
exit $rc
