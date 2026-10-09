# -*- coding: utf-8 -*-
"""ab_p0 smoke 통과 조건(PLAN.md 2절): 세 문항 모두 첫 계획 응답이 grounding 계약을 통과한다.

    python smoke_check.py smoke/p0_smoke.json
"""

import json
import sys
from pathlib import Path

CONTRACT_ERRORS = {"JSON_NOT_FOUND", "JSON_PARSE_FAILED", "UNKNOWN_KEY", "INVALID_CONCEPT", "MISSING_CONCEPTS", "INVALID_GROUNDING",
                   "UNKNOWN_CONCEPT_KEY"}


def main(path):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["rows"]
    bad = [(row["id"], row.get("error_code")) for row in rows if row.get("error_code") in CONTRACT_ERRORS]
    for row in rows:
        content = ((row.get("llm_calls") or [{}])[0]).get("content", "")
        print(row["id"], row["category"], row.get("error_code"), content[:300].replace("\n", " "))
    if len(rows) != 3 or bad:
        print("smoke FAILED", len(rows), bad)
        return 1
    print("smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
