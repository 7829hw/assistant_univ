# -*- coding: utf-8 -*-
"""pilot_009 준비 GPU 작업 표 2판(``PLAN_DEVIATIONS.md`` 1). ``jobs_prep.json``(1판, 그대로 둠)에서 Ollama 작업만 바꾼다:
T-R → **T-R2**, TEACH-R → **TEACH-R2**(실행기 ``teacher/run_r9b.py``: warm-up 요청 1회 뒤 수집; 조건 ``T-R2`` ok·``ready/TEACH-R2.json``). J 작업은 1판 그대로.
T-R 시도 1(1판 T-R)은 guard로 멈춰 ``ABORTED_*``로 남는다. scheduler11을 이 표로 다시 시작한다(1판 실행은 진행 중 작업 없이 멈춤).

    python3 make_jobs_prep2.py   # -> gpu/jobs_prep2.json
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
jobs = json.loads((HERE / "jobs_prep.json").read_text(encoding="utf-8"))["jobs"]
out = []
for j in jobs:
    j = dict(j)
    if j["id"] in ("T-R", "TEACH-R"):
        cmd = j["cmd"][2].replace("teacher/run_r9.py", "teacher/run_r9b.py").replace("check_ready.sh TEACH-R ", "check_ready.sh TEACH-R2 ")
        assert "run_r9b.py" in cmd
        j["id"] += "2"
        j["kind"] += "_v2_warmup"
        j["cmd"] = ["bash", "-c", cmd]
        j["deps"] = ["T-R2", "ready:TEACH-R2"] if j["id"] == "TEACH-R2" else []
    out.append(j)
(HERE / "jobs_prep2.json").write_text(json.dumps({"jobs": out}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print([(j["id"], j["deps"], j["cmd"][2][:160]) for j in out[:2]])
