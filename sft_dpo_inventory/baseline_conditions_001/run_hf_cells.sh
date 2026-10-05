#!/usr/bin/env bash
# baseline_conditions_001 HF 셀(업체 100, thor 코드·frozen runner, GPU 2). Ollama 셀이 모두 끝난 뒤 순서대로 실행한다.
#   HF: thor Base 재현(condition_check 끔)  HFcc: 같은 조건에 condition_check만 켬
# CUDA_VISIBLE_DEVICES=2(프로세스 안에서는 cuda:0). CUDA_DEVICE_ORDER는 바꾸지 않는다. 오프라인 model cache 사용.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
PY=/home/hwkim/sftdpo_work/hfvenv/bin/python
THOR=/home/hwkim/sftdpo_work/wt_thor
export CUDA_VISIBLE_DEVICES=2 HF_HOME=/home/hwkim/sftdpo_work/hf-cache HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
       TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
mkdir -p "$HERE/hf"
cd "$THOR"
echo "== HF start $(date -Is)" >> "$HERE/hf/cells.log"
"$PY" "$HERE/hf_thor_base.py" --thor-root "$THOR" --out "$HERE/hf/base" > "$HERE/hf/base.log" 2>&1
echo "== HF exit=$? $(date -Is)" >> "$HERE/hf/cells.log"
echo "== HFcc start $(date -Is)" >> "$HERE/hf/cells.log"
"$PY" "$HERE/hf_thor_base.py" --thor-root "$THOR" --out "$HERE/hf/base_cc" --condition-check > "$HERE/hf/base_cc.log" 2>&1
echo "== HFcc exit=$? $(date -Is)" >> "$HERE/hf/cells.log"
