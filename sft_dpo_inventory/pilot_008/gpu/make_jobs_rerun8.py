# -*- coding: utf-8 -*-
"""pilot_008 셀 다시 돌리기 작업 표(지시 2.1: 잘림·서버 오류 > 1% 셀은 같은 seed로 한 번만, 원본 보관, 결과와 무관하게 교체; ``pilot_007/B_RERUNS.md`` 방법).
주 큐가 끝난 뒤 쓴다. 모델 호출 없음.

    python3 make_jobs_rerun8.py            # 대상 출력(``results/completeness8.json`` 기준)
    python3 make_jobs_rerun8.py --apply    # 원본을 cells/replaced_main·cells_raw/replaced_main으로 옮기고 gpu/jobs_rerun8.json·RERUNS_main.json을 쓴다

label → 모델·서버·셋: ``base_rdev1``(base, b17408, refusal_dev v1), ``b2f_<o>_rdev1``(B2_F_<o>, B2 checkpoint-1811), ``p8_f_<o>_<셋>``(P8_F_<o>, checkpoint-2005).
명령은 ``make_jobs_main.run``과 같다(``--sealed``만 더함).
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P8 = HERE.parent
MAIN = Path("/home/hwkim/assistant_univ")
sys.path.insert(0, str(HERE))
import make_jobs_main as MJ  # noqa: E402  (모듈 수준 실행: 작업 표를 다시 쓰지만 내용은 같다)

CELLS, RAWP = P8 / "cells", MAIN / "training/generated/pilot_008/cells_raw"


def target(label):
    if label == "base_rdev1":
        return "base", "b17408", "rdev1"
    if label.startswith("b2f_"):
        o = label.split("_")[1]
        return f"B2_F_{o}", f"lora:B2_F_{o}={MJ.B2CK.format(o=o)}", "rdev1"
    _, _, o, g = label.split("_", 3)
    return f"P8_F_{o}", f"lora:P8_F_{o}={MJ.P8CK.format(o=o)}", g


def main():
    comp = json.loads((P8 / "results/completeness8.json").read_text(encoding="utf-8"))["cells"]
    rec_p = P8 / "RERUNS_main.json"
    rec = json.loads(rec_p.read_text(encoding="utf-8")) if rec_p.exists() else {"reruns": {}}
    todo = {}
    for name, v in comp.items():
        if v.get("exists") and v.get("rerun") and name not in rec["reruns"]:
            label, k = name.rsplit("_s", 1)
            todo.setdefault(label, []).append(int(k))
    by_server = {}
    for label, ks in sorted(todo.items()):
        model, server, g = target(label)
        for k in sorted(ks):
            by_server.setdefault(server, []).append(MJ.run(model, label, g, k) + " --sealed")
    jobs = [{"id": f"R8-{n:02d}", "type": "raw", "kind": "rerun_cells", "server": s, "est": 6 * len(c), "prio": 1, "cmd": ["bash", "-c", " && ".join(c)], "outputs": []}
            for n, (s, c) in enumerate(sorted(by_server.items()), 1)]
    print(json.dumps({"cells": sum(len(v) for v in todo.values()), "jobs": len(jobs), "targets": todo}, ensure_ascii=False))
    if "--apply" not in sys.argv:
        return
    (CELLS / "replaced_main").mkdir(exist_ok=True)
    (RAWP / "replaced_main").mkdir(exist_ok=True)
    for label, ks in todo.items():
        for k in ks:
            name = f"{label}_s{k}"
            for src, dst in ((CELLS / f"{name}.json", CELLS / "replaced_main"), (CELLS / f"{name}.log", CELLS / "replaced_main"), (RAWP / f"{name}_raw.jsonl", RAWP / "replaced_main")):
                if src.exists():
                    shutil.move(str(src), str(dst / src.name))
            v = comp[name]
            rec["reruns"][name] = {"truncated_calls": v.get("truncated_calls"), "raw_lines": v.get("raw_lines"), "server_error_rows": v.get("server_error_rows"),
                                   "original_sha256": v["sha256"], "moved_to": "cells/replaced_main/"}
    rec_p.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "jobs_rerun8.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
