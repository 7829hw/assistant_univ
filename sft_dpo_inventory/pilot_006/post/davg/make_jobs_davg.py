# -*- coding: utf-8 -*-
"""D-avg 작업 표(세션 4 우선 10, 선택). scheduler6g가 6f 큐가 끝난 뒤 읽는다.

    python3 make_jobs_davg.py   # -> post/davg/jobs_davg.json

- 서버 ``lora32:D_avg=<평균 adapter>``(serve6c.sh, rank 32). 주 셋(selection_v2 + holdout) k=4, seed_base 20261100(F-s43·F-s1016 e1 원래 셀과 같음).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AD = "/home/hwkim/sftdpo_work/pilot_006/davg/F_avg_e1"
cells = [{"label": f"d_avg_e1_{g}", "model": "D_avg", "target": "full", "gold": g, "k": 4, "seed_base": 20261100, "greedy": False} for g in ("sel", "holdout")]
jobs = [{"id": "D-avg", "type": "cells", "kind": "cells_davg_F43_F1016_e1_main_k4", "server": f"lora32:D_avg={AD}", "est": 40, "prio": 10,
         "deps": [f"file:{AD}/adapter_model.safetensors"], "cells": cells}]
(HERE / "jobs_davg.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(jobs[0]["id"], jobs[0]["server"])
