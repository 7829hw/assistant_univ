#!/usr/bin/env bash
# ab_p0_3 전체 셀(PLAN.md 4절). arm full·p0·p0_3, sampling 회차마다 arm 순서를 돌린다. 한 셀이라도 실패하면 멈춘다(다시 돌리지 않는다).
set -u
HERE=/home/hwkim/assistant_univ/evaluation/partial_grounding/ab_p0_3
PY=/data/hwkim/path_repeat_001/venv/py/bin/python
CELL=$HERE/run_cell.sh
SAMPLING=(--temperature 0.6 --top-p 0.95 --top-k 20)

$CELL raw/smoke p0_3_smoke p0_3 --only old44/g02,old44/g03,old44/g04 || exit 1
$PY "$HERE/../ab_p0/smoke_check.py" "$HERE/raw/smoke/p0_3_smoke.json" || { echo "smoke FAILED" | tee -a "$HERE/runs.log"; exit 1; }

for arm in full p0 p0_3; do
  $CELL raw "${arm}_greedy" "$arm" || exit 2
done
for r in 1 2 3 4 5; do
  seed=$((20261009 + r))
  case $(( (r - 1) % 3 )) in
    0) order=(full p0 p0_3) ;;
    1) order=(p0 p0_3 full) ;;
    2) order=(p0_3 full p0) ;;
  esac
  for arm in "${order[@]}"; do
    $CELL raw "${arm}_sample_r$r" "$arm" "${SAMPLING[@]}" --seed "$seed" || exit 2
  done
done
echo "$(date -Iseconds) ALL DONE" | tee -a "$HERE/runs.log"
