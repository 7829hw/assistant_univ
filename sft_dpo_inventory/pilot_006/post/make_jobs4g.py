# -*- coding: utf-8 -*-
"""scheduler6g 작업 표(세션 4): D-avg(우선 10) + 6f에서 실패한 greedy 작업 다시(run_cell6w --greedy가 --seed를 넘겨 평가 도구가 멈춤 → run_cell6x).

    python3 make_jobs4g.py   # -> post/jobs4g.json

- greedy 작업은 ``jobs4.json``의 E-greedy_*·E-Dq_*를 그대로 가져와 ID 뒤에 R만 붙인다(셀 라벨·서버·의존·k 같음).
- D-avg는 ``davg/jobs_davg.json``과 같다.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = json.loads((HERE / "jobs4.json").read_text(encoding="utf-8"))["jobs"]
jobs = json.loads((HERE / "davg/jobs_davg.json").read_text(encoding="utf-8"))["jobs"]
for j in src:
    if j["id"].startswith(("E-greedy_", "E-Dq_")):
        r = dict(j)
        r["id"] = j["id"].replace("E-greedy_", "E-greedyR_").replace("E-Dq_", "E-DqR_")
        r["kind"] = j["kind"] + "_rerun_6x"
        jobs.append(r)
(HERE / "jobs4g.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(jobs), [j["id"] for j in jobs])
