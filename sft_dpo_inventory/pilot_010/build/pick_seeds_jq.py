# -*- coding: utf-8 -*-
"""pilot_010 JQ(결정 269) RR+NM8(V8) 새 순서 seed 4개 고르기. 모델 호출 없음.

규칙(학습 전 고정): ``numpy.random.default_rng(20261119)``에서 ``integers(1_000_000, 10_000_000)``을 차례로 뽑아,
저장소 전체 ``git grep -w -l <값>``(바이너리 일치 포함) 결과가 0건인 값을 앞에서부터 4개 쓴다. 뽑은 값과 건수를 모두 기록한다.
처음 범위 ``integers(100, 100000)``은 5자리 값 대부분이 저장소에 이미 있어(시험 8개 중 0건 없음) 고르기 전에 멈추고 7자리로 바꿨다(PLAN_JQ 계획과 달라진 점).

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/build/pick_seeds_jq.py   # -> build/seeds_jq.json
"""
import json
import subprocess
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    rng = np.random.default_rng(20261119)
    picked, tried = [], []
    while len(picked) < 4:
        s = int(rng.integers(1_000_000, 10_000_000))
        r = subprocess.run(["git", "grep", "-w", "-l", str(s)], cwd=ROOT, capture_output=True, text=True)
        n = len([l for l in r.stdout.splitlines() if l.strip()])
        tried.append({"value": s, "git_grep_w_files": n})
        if n == 0 and s not in picked:
            picked.append(s)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    body = {"decision": 269, "rule": "default_rng(20261119).integers(1_000_000, 10_000_000) 차례로, git grep -w -l 0건인 값 앞에서 4개", "repo_head": head,
            "tried": tried, "order_seeds": picked}
    (HERE / "seeds_jq.json").write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(body, ensure_ascii=False))


if __name__ == "__main__":
    main()
