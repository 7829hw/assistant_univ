#!/usr/bin/env bash
# ab_p0 전체 셀(PLAN.md 2절). 한 셀이라도 실패하면 그 자리에서 멈춘다(다시 돌리지 않는다).
set -u
HERE=/home/hwkim/assistant_univ/evaluation/partial_grounding/ab_p0
PY=/data/hwkim/path_repeat_001/venv/py/bin/python
CELL=$HERE/run_cell.sh
SAMPLING=(--temperature 0.6 --top-p 0.95 --top-k 20)

$CELL smoke p0_smoke p0 --only 001,002,003 || exit 1
$PY "$HERE/smoke_check.py" "$HERE/smoke/p0_smoke.json" || { echo "smoke FAILED" | tee -a "$HERE/runs.log"; exit 1; }

$CELL runs full_greedy full || exit 2
$CELL runs p0_greedy p0 || exit 2
for r in 1 2 3 4 5; do
  seed=$((20261009 + r))
  if [ $((r % 2)) -eq 1 ]; then order=(full p0); else order=(p0 full); fi
  for arm in "${order[@]}"; do
    $CELL runs "${arm}_sample_r$r" "$arm" "${SAMPLING[@]}" --seed "$seed" || exit 2
  done
done
echo "$(date -Iseconds) ALL DONE" | tee -a "$HERE/runs.log"
