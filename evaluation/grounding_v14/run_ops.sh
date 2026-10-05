#!/usr/bin/env bash
# grounding_v14 운영 조건 검증. 사용: run_ops.sh TAG MODEL CODE_ROOT
#   조건 C1(문항마다 해제, file), W1(keep_loaded, file), W2(keep_loaded, reverse), W3(keep_loaded, shuffle:14).
#   문항: grounding_v12 최종 56. 기준일 2026-09-25. 모든 요청은 기록 프록시(포트 11500)를 거친다.
set -euo pipefail
TAG=$1; MODEL=$2; ROOT=$3
HERE=$(cd "$(dirname "$0")/../.." && pwd)
PY=${PY:-python}
OUT=$HERE/evaluation/grounding_v14/runs/ops/$TAG
mkdir -p "$OUT"
cd "$HERE"
run() {  # 이름, model-state, order
  local name=$1 state=$2 order=$3
  $PY evaluation/grounding_v14/record_proxy.py --listen 11500 --log "$OUT/$name.proxy.jsonl" &
  local pxy=$!
  sleep 1
  $PY evaluate_vendor100.py --code-root "$ROOT" --gold evaluation/grounding_v12/final_questions.yaml llm \
    --model "$MODEL" --host http://127.0.0.1:11500 --condition-check --reference-date 2026-09-25 \
    --model-state "$state" --order "$order" --out "$OUT/$name.json" > "$OUT/$name.log" 2>&1 || { kill $pxy; exit 1; }
  kill $pxy; wait $pxy 2>/dev/null || true
}
run C1 unload_per_question file
run W1 keep_loaded file
run W2 keep_loaded reverse
run W3 keep_loaded shuffle:14
echo "done $TAG"
