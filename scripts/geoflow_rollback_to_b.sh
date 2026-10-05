#!/usr/bin/env bash
# GeoFlow 기본 조합을 T2PC에서 이전 기본 조합 B(qwen3:8b + prompt 522aa3b1 + grounding-v12-baseline 코드)로 되돌린다.
#
# 현재 checkout(작업 트리)에 변경을 만들고 stage만 한다. 커밋은 사람이 확인한 뒤 한다.
# - 실행 의미 코드(execution_spec.SEMANTIC_CODE) 중 T2PC가 바꾼 geoflow/·prompts/를 태그에서 복원한다.
#   나머지 실행 의미 파일은 두 조합에서 같다(grounding_v15 확인). 이 스크립트가 끝에서 지문으로 다시 확인한다.
# - T2PC 코드에만 맞는 테스트를 태그 상태로 되돌리거나 지운다.
# - CLI의 기본 조합 이름(GEOFLOW_DEFAULT_SPEC_NAME)을 B로 바꾼다. 기본 모델은 그 조합의 모델(qwen3:8b)이 된다.
# 모델 이름만 바꾸는 것은 되돌리기가 아니다(grounding_v13: qwen3:8b + T2PC 코드·prompt에서 회귀 확인).
# `git revert -m 1 b62f6dc`는 grounding_v14 이후 assistant_cli.py·tests/test_cli_run_settings.py 충돌로 그대로 쓸 수 없다.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
TAG=${TAG:-grounding-v12-baseline}
PY=${PY:-python}
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "작업 트리에 커밋하지 않은 변경이 있다. 정리한 뒤 다시 실행한다." >&2
  exit 1
fi
git checkout "$TAG" -- geoflow prompts tests/test_geoflow_aggregation_graph.py
git rm -q tests/test_condition_authority.py tests/test_status_contract.py
sed -i 's/^GEOFLOW_DEFAULT_SPEC_NAME = "T2PC"$/GEOFLOW_DEFAULT_SPEC_NAME = "B"/' assistant_cli.py
git add assistant_cli.py
PYTHONPATH=. "$PY" - <<'PY'
import assistant_cli as cli
local = cli.local_code_facts()
name = cli.select_verified_spec(local)
spec = cli.GEOFLOW_VERIFIED_SPECS["B"]
assert cli.GEOFLOW_DEFAULT_SPEC_NAME == "B", cli.GEOFLOW_DEFAULT_SPEC_NAME
assert cli.GEOFLOW_DEFAULT_MODEL_NAME == spec["model"], cli.GEOFLOW_DEFAULT_MODEL_NAME
assert local["prompt_sha256"] == spec["prompt_sha256"], local
assert local["code_fingerprint"] == spec["code_fingerprint"], local
assert name == "B", name
print(f"되돌림 확인: 기본 조합 B, 기본 모델 {cli.GEOFLOW_DEFAULT_MODEL_NAME}, prompt {local['prompt_sha256'][:8]}, "
      f"실행 의미 코드 {local['code_fingerprint'][:8]}")
PY
echo "변경을 stage했다. 테스트(python -m unittest discover -s tests)를 돌리고 확인한 뒤 커밋한다."
