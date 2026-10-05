#!/usr/bin/env bash
# grounding_v13 실측. 사용: run_set.sh MODEL TAG CODE_ROOT SCOPE
#   SCOPE=fill:  개발 311 중 grounding_v12 작은 검증(small_ids.json)에 없던 292문항(T3PC 기록 채우기)
#   SCOPE=final: grounding_v12 최종 검증 셋(final_questions.yaml, 56문항)
#   SCOPE=small: grounding_v12 작은 검증과 같은 136문항(모델 이름만 바꾼 조합의 측정)
# 모든 run은 같은 harness(이 저장소의 evaluate_vendor100.py), --condition-check, temperature 0, think 미지정, timeout 300초다.
set -euo pipefail
MODEL=$1; TAG=$2; ROOT=$3; SCOPE=$4
HERE=$(cd "$(dirname "$0")/../.." && pwd)
PY=${PY:-python}
OUT=$HERE/evaluation/grounding_v13/runs/$SCOPE/$TAG
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
ids() {  # 셋의 small_ids 안(in) 또는 밖(out) 문항
  $PY - "$1" "$2" "${GOLD[$1]}" <<'PY'
import json, sys, yaml
set_name, side, path = sys.argv[1:4]
small = set(json.load(open("evaluation/grounding_v12/small_ids.json")).get(set_name, []))
items = [str(i["id"]) for i in yaml.safe_load(open(path, encoding="utf-8"))["items"]]
print(",".join(i for i in items if (i in small) == (side == "in")))
PY
}
case $SCOPE in
  fill)
    for set in at contrast dev indepv2 indepv3 indepv4 old44; do run $set $set "$(ids $set out)"; done ;;
  final) run final ;;
  small)
    run measure; run status; run od; run heldout
    for set in contrast dev indepv2 indepv3 indepv4 old44; do run $set $set "$(ids $set in)"; done ;;
esac
echo "done $TAG $SCOPE"
