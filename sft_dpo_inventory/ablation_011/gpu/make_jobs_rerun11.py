# -*- coding: utf-8 -*-
"""ablation_011 셀 다시 돌리기 작업(결정 261, PLAN_A11 5절 = PLAN_S 5절: valid98·aux 셀은 잘림·서버 오류 > 1%, refusal_dev v2 셀은 잘림 ≥ 2 또는
서버 오류 ≥ 2 — 같은 seed로 한 번만, 원본 보관, 결과와 무관하게 교체). ``pilot_010/gpu/make_jobs_rerun10.py``와 같은 방식. 모델 호출 없음.

    runtime/envs/hf/bin/python sft_dpo_inventory/ablation_011/analysis/completeness11.py
    python3 make_jobs_rerun11.py            # 대상 출력
    python3 make_jobs_rerun11.py --apply    # 원본을 cells/replaced·cells_raw/replaced로 옮기고 jobs_a11.json 끝에 R11-NN 작업을 붙이고 RERUNS_A11.json을 쓴다

- 대상은 평가 작업(E-*)이 ``runs.log``에 ok로 끝난 셀만(돌고 있는 작업의 파일은 건드리지 않는다).
- 명령은 원래 E 작업(jobs_a11.json)의 그 셀 명령과 글자까지 같다(server·model·label·k·seed-base·gold 같음). scheduler13은 jobs_a11.json을 다시 읽어 새 작업을 붙인다.
"""
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
A11 = HERE.parent
MAIN = Path("/home/hwkim/assistant_univ")
CELLS, RAWP = A11 / "cells", MAIN / "training/generated/ablation_011/cells_raw"
JOBS = HERE / "jobs_a11.json"
REC = A11 / "RERUNS_A11.json"


def main():
    comp = json.loads((A11 / "analysis/completeness11.json").read_text(encoding="utf-8"))["cells"]
    data = json.loads(JOBS.read_text(encoding="utf-8"))
    jobs = data["jobs"]
    done = set(re.findall(r"\] (E-\S+) ok ", (HERE / "runs.log").read_text(encoding="utf-8")))
    rec = json.loads(REC.read_text(encoding="utf-8")) if REC.exists() else {"reruns": {}}
    by_job = {}
    for name, v in sorted(comp.items()):
        if not (v.get("exists") and v.get("rerun")) or name in rec["reruns"] or v.get("already_rerun") or v["job"] not in done:
            continue
        by_job.setdefault(v["job"], []).append(name)
    new = []
    n0 = sum(1 for j in jobs if j["id"].startswith("R11-"))
    for n, (jid, names) in enumerate(sorted(by_job.items()), n0 + 1):
        ej = next(j for j in jobs if j["id"] == jid)
        parts = ej["cmd"][2].split(" && ")
        cmds = []
        for name in names:
            label, k = name.rsplit("_s", 1)
            hit = [p for p in parts if f"--label {label} " in p and f"--k {k} " in p]
            if len(hit) != 1:
                raise SystemExit(f"command not found uniquely for {name}")
            cmds.append(hit[0])
        new.append({"id": f"R11-{n:02d}", "type": "raw", "kind": "rerun_cells_a11", "server": ej["server"], "est": 4 * len(cmds), "prio": 1,
                    "deps": ["ready:A11_TOOLS"], "cmd": ["bash", "-c", " && ".join(cmds)], "outputs": [], "rerun_of": names})
    print(json.dumps({"cells": sum(len(v) for v in by_job.values()), "jobs": [(j["id"], j["server"].split("=")[0], j["rerun_of"]) for j in new]}, ensure_ascii=False))
    if "--apply" not in sys.argv or not new:
        return
    (CELLS / "replaced").mkdir(exist_ok=True)
    (RAWP / "replaced").mkdir(parents=True, exist_ok=True)
    for j in new:
        for name in j["rerun_of"]:
            for src, dst in ((CELLS / f"{name}.json", CELLS / "replaced"), (CELLS / f"{name}.log", CELLS / "replaced"), (RAWP / f"{name}_raw.jsonl", RAWP / "replaced")):
                if src.exists():
                    shutil.move(str(src), str(dst / src.name))
            v = comp[name]
            rec["reruns"][name] = {"job": j["id"], "truncated_calls": v.get("truncated_calls"), "raw_lines": v.get("raw_lines"), "server_error_rows": v.get("server_error_rows"),
                                   "rule": v.get("rerun_rule"), "original_sha256": v["sha256"], "moved_to": "cells/replaced/"}
    REC.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp = JOBS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(dict(data, jobs=jobs + new), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(JOBS)


if __name__ == "__main__":
    main()
