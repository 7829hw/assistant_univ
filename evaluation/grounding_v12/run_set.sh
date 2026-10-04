#!/usr/bin/env bash
# grounding_v12 실측. 사용: run_set.sh MODEL TAG CODE_ROOT SCOPE
#   SCOPE=small:   측정값 대조 20 + 운행 상태 대조 33 + OD 대조 16 + 원인·측정 실패 개발 문항(small_ids.json) + v10 held-out 48(개발용)
#   SCOPE=measure: 측정값 대조 20만(기존 기록이 있는 기준 arm용)
#   SCOPE=full:    개발 311 + OD 대조 16 + 운행 상태 대조 33 + 측정값 대조 20
#   SCOPE=final:   새 최종 검증 셋(final_questions.yaml)
#   SCOPE=rollback: OD 대조 16 + 운행 상태 대조 33(되돌리기 검증)
# 모든 run은 같은 harness(이 저장소의 evaluate_vendor100.py), --condition-check, temperature 0, think 미지정, timeout 300초다.
set -euo pipefail
MODEL=$1; TAG=$2; ROOT=$3; SCOPE=$4
HERE=$(cd "$(dirname "$0")/../.." && pwd)
PY=${PY:-python}
OUT=$HERE/evaluation/grounding_v12/runs/$SCOPE/$TAG
mkdir -p "$OUT"
declare -A GOLD=([at]=evaluation/grounding_v4/answer_target_questions.yaml [contrast]=evaluation/grounding_v2/contrast_questions.yaml
  [dev]=evaluation/vendor100/gold.yaml [indepv2]=evaluation/grounding_v2/independent_questions.yaml
  [indepv3]=evaluation/grounding_v2/independent_v3_questions.yaml [indepv4]=evaluation/grounding_v3/independent_v4_questions.yaml
  [old44]=evaluation/grounding_v1/holdout_questions.yaml [od]=evaluation/grounding_v8/od_contrast_questions.yaml
  [status]=evaluation/grounding_v10/status_contrast_questions.yaml [measure]=evaluation/grounding_v12/measure_contrast_questions.yaml
  [heldout]=evaluation/grounding_v10/heldout_questions.yaml [final]=evaluation/grounding_v12/final_questions.yaml)
cd "$HERE"
run() {  # 셋 이름, 저장 이름, 문항 고르기
  local set=$1 name=${2:-$1} only=${3:-}
  $PY evaluate_vendor100.py --code-root "$ROOT" --gold "${GOLD[$set]}" llm --model "$MODEL" --condition-check \
    ${only:+--only "$only"} --out "$OUT/$name.json" > "$OUT/$name.log" 2>&1
}
case $SCOPE in
  small)
    run measure; run status; run od; run heldout
    for set in contrast dev indepv2 indepv3 indepv4 old44; do
      run $set $set "$($PY -c "import json;print(','.join(json.load(open('evaluation/grounding_v12/small_ids.json'))['$set']))")"
    done ;;
  measure) run measure ;;
  full)
    run measure; run status; run od
    for set in at contrast dev indepv2 indepv3 indepv4 old44; do run $set; done ;;
  final) run final heldout ;;
  rollback) run od; run status ;;
esac
echo "done $TAG $SCOPE"
