# -*- coding: utf-8 -*-
"""sft_dpo_inventory 공통 부품: thor 브랜치 자산 읽기와 산출물 저장.

thor 자산은 고정 commit에서 ``git show``로만 읽는다(merge·checkout·worktree 수정 없음). 산출물은
``sft_dpo_inventory/generated/``에 쓰며 이 디렉터리는 커밋하지 않는다(.gitignore).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GENERATED = HERE / "generated"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: 조사 대상 thor commit(origin/geoflow/sft-dpo-thor, 2026-10-05 fetch 시점).
THOR_REF = "b3149040fb0fc57bedd1e8ff4436333f55d41e5a"
#: thor가 갈라진 commit(grounding_v9).
THOR_BASE = "65e9ea2ec98f8cec289cbb753ce543dee3efdd92"
#: thor 학습·평가 prompt hash와 현재 T2PC prompt hash.
THOR_PROMPT_SHA = "522aa3b1716248b53a755ee1b236e7aef302c85504e9cfac3825f4d3cc817945"
T2PC_PROMPT_SHA = "87048d0c554c365e0e7994d09a4515c1cc646785708ce6dc9d1f120b4b5e8c2c"
CORPORA = "training/records/corpora"


def git_show(path, ref=THOR_REF):
    return subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT)


def thor_yaml(path):
    return yaml.safe_load(git_show(path).decode("utf-8"))


def thor_json(path):
    return json.loads(git_show(path).decode("utf-8"))


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def write_output(name, obj):
    """산출물을 쓰고 (경로, sha256)을 돌려준다."""
    GENERATED.mkdir(parents=True, exist_ok=True)
    path = GENERATED / name
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    return path.relative_to(ROOT).as_posix(), sha256_file(path)


def production_prompt():
    from geoflow.planner import GeoFlowPlanner
    return GeoFlowPlanner(client=None).system_prompt()
