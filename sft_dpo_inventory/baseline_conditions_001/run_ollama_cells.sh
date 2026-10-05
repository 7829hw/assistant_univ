#!/usr/bin/env bash
# baseline_conditions_001 Ollama 셀(업체 100, qwen3:8b, GPU 3의 기존 Ollama 서버). 학습·prompt 변경 없음.
#   사용: run_ollama_cells.sh PYTHON
# 공통: 문항마다 모델 내림(unload_per_question, 기본), temperature 0, 기준일 2026-09-25(q8_cur와 같음), mock·legacy.
# 셀 A(522aa3b1, think auto, 조건 계층 켬)는 Ollama digest가 같아 q8_cur 기록을 그대로 쓴다(새로 재지 않음).
# 522aa3b1 셀의 code root는 q8_cur와 같은 c1f2a08 worktree, 87048d0c 셀은 현재 HEAD(ad96729) worktree다.
# 한 셀이 실패해도 다음 셀로 넘어간다(셀마다 로그에 종료 코드를 남긴다). 다시 실행하거나 설정을 바꿔 맞추지 않는다.
set -u
PY=${1:?python}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
OUT=$HERE/runs
mkdir -p "$OUT"
WT_B=/home/hwkim/sftdpo_work/wt_c1f2a08
WT_T=/home/hwkim/sftdpo_work/wt_head
cd "$REPO"
run() {
  local cell=$1 root=$2; shift 2
  echo "== $cell start $(date -Is)" >> "$OUT/cells.log"
  PYTHONDONTWRITEBYTECODE=1 "$PY" evaluate_vendor100.py --code-root "$root" --gold evaluation/vendor100/gold.yaml \
    llm --model qwen3:8b --reference-date 2026-09-25 --out "$OUT/$cell.json" "$@" > "$OUT/$cell.log" 2>&1
  echo "== $cell exit=$? $(date -Is)" >> "$OUT/cells.log"
}
run B "$WT_B" --condition-check --model-think off
run C "$WT_B" --model-think off
run D "$WT_B" --model-think auto
run F "$WT_T" --condition-check --model-think off
run E "$WT_T" --condition-check --model-think auto
echo "== all done $(date -Is)" >> "$OUT/cells.log"
