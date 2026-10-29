# -*- coding: utf-8 -*-
"""B단계 셀 다시 돌리기 작업 표(``B_RERUNS.md`` 규칙). 주 작업 표(``jobs_B.json``, 지연 창 포함)가 모두 끝난 뒤에 쓴다.

    python3 make_jobs_B_rerun.py            # 대상만 출력(``results/completeness_B.json`` 기준)
    python3 make_jobs_B_rerun.py --apply    # 원래 셀을 replaced_B/로 옮기고 gpu/jobs_B_rerun.json을 쓴다

- 대상: completeness의 ``rerun``(잘림 또는 서버 오류 > 1%)인 셀 회차. 한 번만 — ``B_RERUNS.json``에 이미 다시 돌린 셀은 다시 넣지 않는다.
- 작업: 모델(서버)마다 raw 작업 하나, 그 모델의 대상 회차를 ``run_cell6x.py --k <회차>``로 차례로(같은 label·seed_base·target·gold, ``--sealed``).
  설정은 ``jobs_B.json``의 셀 정의에서 그대로 가져온다.
- 원래 셀 json·log → ``cells/replaced_B/``, 원문 → ``training/generated/pilot_007/cells_raw/replaced_B/``(판정에 쓰지 않음).
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P7 = HERE.parent
MAIN = P7.parents[1]
CELLS = P7 / "cells"
RAWP = MAIN / "training/generated/pilot_007/cells_raw"
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
GOLD = {"sel": None, "holdout": "sft_dpo_inventory/pilot_006_prep/aug300/augmentation_holdout_v1_gold.yaml",
        "valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml"}


def main():
    apply = "--apply" in sys.argv
    comp = json.loads((P7 / "results/completeness_B.json").read_text(encoding="utf-8"))
    jobs = json.loads((HERE / "jobs_B.json").read_text(encoding="utf-8"))["jobs"]
    rec_path = P7 / "B_RERUNS.json"
    rec = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.exists() else {"reruns": {}}
    spec = {c["label"]: (j, c) for j in jobs for c in j.get("cells", [])}
    targets = {}
    for name, v in comp["cells"].items():
        if v.get("exists") and v.get("rerun") and name not in rec["reruns"]:
            label, k = name.rsplit("_s", 1)
            targets.setdefault(label, []).append(int(k))
    by_server = {}
    for label, ks in sorted(targets.items()):
        j, c = spec[label]
        by_server.setdefault(j["server"], []).append((c, sorted(ks), j["id"]))
    out_jobs = []
    for n, (server, items) in enumerate(sorted(by_server.items()), 1):
        cmds = []
        for c, ks, _ in items:
            for k in ks:
                cmd = [PY, "{WT}/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py", "--port", "{PORT}", "--model", c["model"], "--label", c["label"],
                       "--k", str(k), "--concurrency", "8", "--grounding-target", c["target"], "--out-dir", str(CELLS), "--raw-dir", str(RAWP),
                       "--seed-base", str(c["seed_base"]), "--sealed"]
                if GOLD[c["gold"]]:
                    cmd += ["--gold", GOLD[c["gold"]], "--all-items"]
                cmds.append(" ".join(cmd))
        jid = f"R-B-{n:02d}_{items[0][0]['model']}"
        out_jobs.append({"id": jid, "type": "raw", "kind": f"rerun_{items[0][0]['model']}", "server": server, "est": 8 * len(cmds), "prio": 1,
                         "cmd": ["bash", "-c", " && ".join(cmds)], "outputs": []})
    summary = {label: ks for label, ks in sorted(targets.items())}
    print(json.dumps({"cells": sum(len(v) for v in targets.values()), "jobs": len(out_jobs), "targets": summary}, ensure_ascii=False, indent=1))
    if not apply:
        return
    (CELLS / "replaced_B").mkdir(exist_ok=True)
    (RAWP / "replaced_B").mkdir(exist_ok=True)
    for label, ks in targets.items():
        for k in ks:
            name = f"{label}_s{k}"
            v = comp["cells"][name]
            for src, dst in ((CELLS / f"{name}.json", CELLS / "replaced_B"), (CELLS / f"{name}.log", CELLS / "replaced_B"),
                             (RAWP / f"{name}_raw.jsonl", RAWP / "replaced_B")):
                if src.exists():
                    shutil.move(str(src), str(dst / src.name))
            rec["reruns"][name] = {"reason": {"truncated_calls": v.get("truncated_calls"), "raw_lines": v.get("raw_lines"), "truncated_pct": v.get("truncated_pct"),
                                              "server_error_rows": v.get("server_error_rows")},
                                   "original_sha256": v["sha256"], "original_moved_to": "cells/replaced_B/", "job": spec[label][0]["id"]}
    rec_path.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (HERE / "jobs_B_rerun.json").write_text(json.dumps({"jobs": out_jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
