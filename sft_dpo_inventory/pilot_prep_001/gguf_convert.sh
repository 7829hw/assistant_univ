#!/usr/bin/env bash
# HF 모델 디렉터리(base 또는 merge한 학습 모델)를 GGUF로 바꾸고 Q4_K_M으로 양자화한다. CPU만 쓴다. Ollama 등록은 하지 않는다.
#   사용: gguf_convert.sh HF_MODEL_DIR OUT_DIR NAME
#   예  : gguf_convert.sh $HF_HOME/hub/models--Qwen--Qwen3-8B/snapshots/b968826d... /home/hwkim/sftdpo_work/gguf qwen3-8b-b968826d-base
# - llama.cpp는 고정 tag(LLAMA_CPP_TAG)를 저장소 밖(LLAMA_CPP_DIR)에 받아 CPU로 빌드한다. 같은 tag면 다시 받지 않는다.
# - 결과: OUT_DIR/NAME-bf16.gguf(변환 직후), OUT_DIR/NAME-Q4_K_M.gguf(양자화). 둘 다 저장소 밖에 둔다.
# - OUT_DIR/NAME.receipt.json에 llama.cpp commit, 명령, 입력·출력 sha256을 남긴다.
# - 학습 모델은 먼저 training.merge_adapter로 merge한 HF 디렉터리를 만든 뒤 같은 명령을 쓴다(base와 같은 경로·양자화).
set -euo pipefail
SRC=${1:?HF_MODEL_DIR}; OUT=${2:?OUT_DIR}; NAME=${3:?NAME}
LLAMA_CPP_TAG=${LLAMA_CPP_TAG:-b11434}
LLAMA_CPP_DIR=${LLAMA_CPP_DIR:-/home/hwkim/sftdpo_work/llama.cpp-$LLAMA_CPP_TAG}
VENV=${VENV:-/home/hwkim/sftdpo_work/llamacpp_venv}
case "$(realpath -m "$OUT")" in "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"*) echo "OUT_DIR은 저장소 밖이어야 한다" >&2; exit 1;; esac
mkdir -p "$OUT"
if [ ! -d "$LLAMA_CPP_DIR" ]; then
  git clone --depth 1 --branch "$LLAMA_CPP_TAG" https://github.com/ggml-org/llama.cpp "$LLAMA_CPP_DIR"
fi
COMMIT=$(git -C "$LLAMA_CPP_DIR" rev-parse HEAD)
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q cmake -r "$LLAMA_CPP_DIR/requirements/requirements-convert_hf_to_gguf.txt" \
      --extra-index-url https://download.pytorch.org/whl/cpu
fi
if [ ! -x "$LLAMA_CPP_DIR/build/bin/llama-quantize" ]; then
  "$VENV/bin/cmake" -S "$LLAMA_CPP_DIR" -B "$LLAMA_CPP_DIR/build" -DGGML_CUDA=OFF -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release
  "$VENV/bin/cmake" --build "$LLAMA_CPP_DIR/build" --target llama-quantize -j "$(nproc)"
fi
BF16="$OUT/$NAME-bf16.gguf"; Q4="$OUT/$NAME-Q4_K_M.gguf"
CONVERT=("$VENV/bin/python" "$LLAMA_CPP_DIR/convert_hf_to_gguf.py" "$SRC" --outtype bf16 --outfile "$BF16")
QUANT=("$LLAMA_CPP_DIR/build/bin/llama-quantize" "$BF16" "$Q4" Q4_K_M)
CUDA_VISIBLE_DEVICES="" "${CONVERT[@]}"
CUDA_VISIBLE_DEVICES="" "${QUANT[@]}"
SRC_HASHES=$(cd "$SRC" && for f in $(ls -1 | grep -E '\.(json|safetensors|txt)$'); do printf '"%s":"%s",' "$f" "$(sha256sum "$(readlink -f "$f")" | cut -d' ' -f1)"; done | sed 's/,$//')
cat > "$OUT/$NAME.receipt.json" <<EOF
{"name": "$NAME", "source_dir": "$SRC", "source_file_sha256": {$SRC_HASHES},
 "llama_cpp_tag": "$LLAMA_CPP_TAG", "llama_cpp_commit": "$COMMIT",
 "convert_command": "${CONVERT[*]}", "quantize_command": "${QUANT[*]}",
 "bf16_gguf": "$BF16", "bf16_sha256": "$(sha256sum "$BF16" | cut -d' ' -f1)", "bf16_bytes": $(stat -c %s "$BF16"),
 "q4_k_m_gguf": "$Q4", "q4_k_m_sha256": "$(sha256sum "$Q4" | cut -d' ' -f1)", "q4_k_m_bytes": $(stat -c %s "$Q4"),
 "finished_at": "$(date -Is)"}
EOF
cat "$OUT/$NAME.receipt.json"
