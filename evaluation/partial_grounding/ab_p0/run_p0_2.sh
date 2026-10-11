#!/usr/bin/env bash
# P0.2 셀(PLAN_P0_2.md). Full 셀은 ab_p0의 것을 다시 쓰므로 P0.2만 잰다. 한 셀이라도 실패하면 멈춘다.
set -u
HERE=/home/hwkim/assistant_univ/evaluation/partial_grounding/ab_p0
PY=/data/hwkim/path_repeat_001/venv/py/bin/python
CELL=$HERE/run_cell.sh
SAMPLING=(--temperature 0.6 --top-p 0.95 --top-k 20)

$CELL smoke p0_2_smoke p0_2 --only 001,002,003 || exit 1
$PY "$HERE/smoke_check.py" "$HERE/smoke/p0_2_smoke.json" || { echo "smoke FAILED" | tee -a "$HERE/runs.log"; exit 1; }

$CELL runs p0_2_greedy p0_2 || exit 2
for r in 1 2 3 4 5; do
  $CELL runs "p0_2_sample_r$r" p0_2 "${SAMPLING[@]}" --seed $((20261009 + r)) || exit 2
done
echo "$(date -Iseconds) P0_2 ALL DONE" | tee -a "$HERE/runs.log"
