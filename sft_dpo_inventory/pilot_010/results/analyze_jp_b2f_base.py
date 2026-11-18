# -*- coding: utf-8 -*-
"""판정 뒤 추가(사후, 결정 268): 표 B에 B2 F − base 비교를 같은 방식으로 더한다(2026-11-18 사용자 지시, 측정 뒤 추가).

    runtime/envs/hf/bin/python sft_dpo_inventory/pilot_010/results/analyze_jp_b2f_base.py

- ``analyze_jp.py``(측정 전 고정, 커밋 ``19d91001``)는 고치지 않는다. 불러와 ``PAIRS``에 ("B2F", "base")만 더하고 같은 ``analyze()``·같은 셀을 다시 돌린다.
- CI는 analyze_j.boot(U1 계층 bootstrap 10,000, 통계량마다 새 ``default_rng(20261109)``)이라 기존 비교 값은 바뀌지 않아야 한다.
  기존 ``jp_posthoc.json``과 비교 9개·arm 값·분해를 대조해 하나라도 다르면 멈춘다.
- 출력 ``results/jp_posthoc_b2f_base.json``: 새 비교 하나와 대조 결과. ``jp_posthoc.json``은 그대로 둔다.
"""
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_jp as J  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    base_path = HERE / "jp_posthoc.json"
    old = json.loads(base_path.read_text(encoding="utf-8"))
    J.PAIRS = list(J.PAIRS) + [("B2F", "base")]
    res = J.analyze(J.cfg(False))
    checks = {
        "comparisons_unchanged": all(res["comparisons"][k] == v for k, v in old["comparisons"].items()),
        "pf2_arms_unchanged": res["pf2"]["arms"] == old["pf2"]["arms"],
        "hfinal_arms_unchanged": res["hfinal"]["arms"] == old["hfinal"]["arms"],
        "decompositions_unchanged": res["pf2"]["decomposition_100"] == old["pf2"]["decomposition_100"]
        and res["hfinal"]["decomposition_3000"] == old["hfinal"]["decomposition_3000"]
        and res["hfinal_v4_minus_b2f_decomposition"] == old["hfinal_v4_minus_b2f_decomposition"],
        "cells_unchanged": res["pf2"]["cells"] == old["pf2"]["cells"] and res["hfinal"]["cells"] == old["hfinal"]["cells"],
        "skipped_none": not res["skipped"],
    }
    if not all(checks.values()):
        raise SystemExit(f"기존 값과 다름: {checks}")
    out = {"label": "판정 뒤 추가(사후)·기술 집계 — C1–C4 판정은 바꾸지 않음. 측정 뒤 사용자 지시로 더한 비교",
           "decision": 268, "added": "B2F-base", "comparison": {"B2F-base": res["comparisons"]["B2F-base"]},
           "method": "analyze_jp.analyze()에 PAIRS + (B2F, base)만 더해 다시 실행; analyze_j.diff(U1 bootstrap 10,000, default_rng(20261109))",
           "consistency_with_jp_posthoc": checks, "jp_posthoc_sha256": sha(base_path),
           "analysis_sha256": sha(__file__), "analyze_jp_sha256": sha(J.__file__), "analyze_j_sha256": sha(J.AJ.__file__),
           "generated_at": datetime.now().astimezone().isoformat(timespec="seconds")}
    (HERE / "jp_posthoc_b2f_base.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["comparison"], ensure_ascii=False))
    print(json.dumps(checks))


if __name__ == "__main__":
    main()
