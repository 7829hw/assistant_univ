# -*- coding: utf-8 -*-
"""j_judgment.json의 PF2 거부 범주 이름(P·C 범주 설명)을 코드(P-1, C-b …)로 줄인다. 원본은 700 디렉터리에 600으로 둔다(커밋 안 함).
M 범주 이름(도메인 밖·예측 …)은 이미 저장소 거부 분류에 있는 일반 이름이라 그대로 둔다. 수치는 바꾸지 않는다.

    python3 sft_dpo_inventory/pilot_010/results/redact_j.py sft_dpo_inventory/pilot_010/results/j_judgment.json
"""
import json
import os
import re
import sys
from pathlib import Path

OUT = Path("/data/hwkim/sftdpo_work/protected_final_v2/analysis")


def short(k):
    m = re.match(r"^(category:[PC]:)([PC]-[0-9a-z]+) .*$", k)
    return m.group(1) + m.group(2) if m else k


def walk(x):
    if isinstance(x, dict):
        return {short(k): walk(v) for k, v in x.items()}
    if isinstance(x, list):
        return [walk(v) for v in x]
    return x


def main():
    p = Path(sys.argv[1])
    raw = p.read_text(encoding="utf-8")
    OUT.mkdir(mode=0o700, exist_ok=True)
    full = OUT / "j_judgment_full.json"
    fd = os.open(full, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(raw)
    d = walk(json.loads(raw))
    d["redaction"] = "PF2 P·C 거부 범주 이름을 코드로 줄임(redact_j.py). 원본 = 700 디렉터리 analysis/j_judgment_full.json(커밋 안 함). 수치는 같음."
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    left = sorted({k for k in re.findall(r'"(category:[PC]:[^"]*)"', p.read_text(encoding="utf-8"))})
    print(json.dumps({"keys_after": left}, ensure_ascii=False))


if __name__ == "__main__":
    main()
