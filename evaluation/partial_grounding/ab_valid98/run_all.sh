#!/usr/bin/env bash
# ab_valid98 전체 셀(PLAN.md 3절). ab_p0/run_all.sh와 같은 순서, arm은 full과 p0_2. 한 셀이라도 실패하면 멈춘다(다시 돌리지 않는다).
set -u
HERE=/home/hwkim/assistant_univ/evaluation/partial_grounding/ab_valid98
PY=/data/hwkim/path_repeat_001/venv/py/bin/python
CELL=$HERE/run_cell.sh
SAMPLING=(--temperature 0.6 --top-p 0.95 --top-k 20)

$CELL raw/smoke p0_2_smoke p0_2 --only stage_v7/s01a,stage_v7/s01b,stage_v7/s01c || exit 1
$PY "$HERE/../ab_p0/smoke_check.py" "$HERE/raw/smoke/p0_2_smoke.json" || { echo "smoke FAILED" | tee -a "$HERE/runs.log"; exit 1; }

$CELL raw full_greedy full || exit 2
$CELL raw p0_2_greedy p0_2 || exit 2
for r in 1 2 3 4 5; do
  seed=$((20261009 + r))
  if [ $((r % 2)) -eq 1 ]; then order=(full p0_2); else order=(p0_2 full); fi
  for arm in "${order[@]}"; do
    $CELL raw "${arm}_sample_r$r" "$arm" "${SAMPLING[@]}" --seed "$seed" || exit 2
  done
done
echo "$(date -Iseconds) ALL DONE" | tee -a "$HERE/runs.log"
