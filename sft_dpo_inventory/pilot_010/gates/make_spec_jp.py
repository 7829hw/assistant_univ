# -*- coding: utf-8 -*-
"""사후 측정 E-A(결정 268)용 ``select_s10.py`` spec: ``spec_s10.json``(선택 단계, 그대로 둠)에서 V8을 빼고 V4 셀을 새 V4 seed 5개의 ``cells/JP`` 셀로 바꾼다.
기준 셀(base·B2 F·P9)은 spec_s10 그대로. select_s10의 선택 판정 출력은 쓰지 않는다(사후·기술, 수치만 읽음).

    python3 sft_dpo_inventory/pilot_010/gates/make_spec_jp.py   # -> gates/spec_jp_dev.json
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEEDS = ("o101", "o523", "o2029", "o31", "o20271027")
C = "sft_dpo_inventory/pilot_010/cells/JP/"
spec = json.loads((HERE / "spec_s10.json").read_text(encoding="utf-8"))
spec["label"] = "pilot_010 판정 뒤 추가(사후) E-A: 새 V4 seed 5개 개발 셋·refusal_dev v2(결정 268). 선택 판정 아님"
spec["variants"], spec["seeds"] = ["V4"], list(SEEDS)
spec["seed_numbers"] = {s: int(s[1:]) for s in SEEDS}
spec["excluded_seeds"] = {}
spec["cells"].pop("V8")
spec["cells"]["V4"] = {s: {g: [f"{C}jp_v4_{s}_{f}_s{k}.json" for k in range(1, 5)] for g, f in (("valid98", "valid98"), ("aux", "aux"), ("rdev", "rdevv2"))} for s in SEEDS}
(HERE / "spec_jp_dev.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({k: (v if not isinstance(v, dict) else list(v)) for k, v in spec.items() if k != "cells"}, ensure_ascii=False), list(spec["cells"]))
