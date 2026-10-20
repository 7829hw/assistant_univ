# -*- coding: utf-8 -*-
"""B단계 adapter 위치·sha256(결정 199: 지우지 않음, 커밋하지 않음). 학습이 끝난 뒤 실행한다.

    python3 sft_dpo_inventory/pilot_007/train/adapters_b.py   # -> adapters_B.json
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT_OUT = Path("/home/hwkim/sftdpo_work/pilot_007/train_b")
out = {"decision": "199 (R6): 지우지 않음, 커밋하지 않음", "root": str(ROOT_OUT), "adapters": {}}
for d in sorted(p for p in ROOT_OUT.iterdir() if p.is_dir()):
    out["adapters"][d.name] = {c.name: {"adapter_sha256": hashlib.sha256((c / "adapter_model.safetensors").read_bytes()).hexdigest()}
                               for c in sorted(d.glob("checkpoint-*"), key=lambda c: int(c.name.split("-")[1])) if (c / "adapter_model.safetensors").exists()}
(HERE.parent / "adapters_B.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print({k: list(v) for k, v in out["adapters"].items()})
