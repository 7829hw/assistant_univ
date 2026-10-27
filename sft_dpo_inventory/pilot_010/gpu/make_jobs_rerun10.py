# -*- coding: utf-8 -*-
"""pilot_010 선택 단계 셀 다시 돌리기 작업 표(지시 2.1·PLAN_S 5절: 개발 셋 셀은 잘림·서버 오류 > 1%, refusal_dev v2 셀은 잘림 ≥ 2 또는 서버 오류 ≥ 2 —
같은 seed로 한 번만, 원본 보관, 결과와 무관하게 교체). ``pilot_009/gpu/make_jobs_rerun9.py``(그대로)의 사본. 모델 호출 없음.

    python3 make_jobs_rerun10.py            # 대상 출력(``results/completeness10.json`` 기준)
    python3 make_jobs_rerun10.py --apply    # 원본을 cells/replaced_S·cells_raw/replaced_S로 옮기고 gpu/jobs_rerun10.json·RERUNS_S.json을 쓴다

label ``s10_<v>_<o>_<셋>`` → 모델 ``S_<V>_<o>``(checkpoint는 ``cell_seeds_S.json``의 checkpoints). 명령은 ``make_jobs_S2.run``과 같다(``--sealed``만 더함).
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P10 = HERE.parent
MAIN = Path("/home/hwkim/assistant_univ")
CELLS, RAWP = P10 / "cells", MAIN / "training/generated/pilot_010/cells_raw"
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"
SEED_BASE = 20261100
GOLD = {"valid98": "sft_dpo_inventory/pilot_004/valid98/valid98_gold.yaml", "aux": "sft_dpo_inventory/pilot_002/aux_test/aux_test_gold.yaml",
        "rdevv2": "sft_dpo_inventory/pilot_009/refusal_dev2/approved/rdev_v2_gold.yaml"}


def run(model, label, gold_key, k):  # make_jobs_S2.run과 같다(그 파일은 import하면 작업 표를 다시 쓰므로 복사)
    return (f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu/run_cell6x.py --port {{PORT}} --model {model} --label {label} --k {k} --concurrency 8 "
            f"--grounding-target full --out-dir {MAIN}/sft_dpo_inventory/pilot_010/cells --raw-dir {MAIN}/training/generated/pilot_010/cells_raw --seed-base {SEED_BASE}"
            f" --gold {GOLD[gold_key]} --all-items")


def target(label, ckpts):
    _, v, o, g = label.split("_", 3)
    jid = f"S-{v.upper()}-{o}"
    name = f"S_{v.upper()}_{o}"
    return name, f"lora:{name}={ckpts[jid]}", g


def main():
    comp = json.loads((P10 / "results/completeness10.json").read_text(encoding="utf-8"))["cells"]
    ckpts = json.loads((HERE / "cell_seeds_S.json").read_text(encoding="utf-8"))["checkpoints"]
    rec_p = P10 / "RERUNS_S.json"
    rec = json.loads(rec_p.read_text(encoding="utf-8")) if rec_p.exists() else {"reruns": {}}
    todo = {}
    for name, v in comp.items():
        if v.get("exists") and v.get("rerun") and name not in rec["reruns"]:
            label, k = name.rsplit("_s", 1)
            todo.setdefault(label, []).append(int(k))
    by_server = {}
    for label, ks in sorted(todo.items()):
        model, server, g = target(label, ckpts)
        for k in sorted(ks):
            by_server.setdefault(server, []).append(run(model, label, g, k) + " --sealed")
    jr = HERE / "jobs_rerun10.json"
    n0 = len(json.loads(jr.read_text(encoding="utf-8"))["jobs"]) if jr.exists() else 0
    jobs = [{"id": f"R10-{n:02d}", "type": "raw", "kind": "rerun_cells", "server": s, "est": 6 * len(c), "prio": 1, "cmd": ["bash", "-c", " && ".join(c)], "outputs": []}
            for n, (s, c) in enumerate(sorted(by_server.items()), n0 + 1)]
    print(json.dumps({"cells": sum(len(v) for v in todo.values()), "jobs": len(jobs), "targets": todo}, ensure_ascii=False))
    if "--apply" not in sys.argv:
        return
    (CELLS / "replaced_S").mkdir(exist_ok=True)
    (RAWP / "replaced_S").mkdir(parents=True, exist_ok=True)
    for label, ks in todo.items():
        for k in ks:
            name = f"{label}_s{k}"
            for src, dst in ((CELLS / f"{name}.json", CELLS / "replaced_S"), (CELLS / f"{name}.log", CELLS / "replaced_S"), (RAWP / f"{name}_raw.jsonl", RAWP / "replaced_S")):
                if src.exists():
                    shutil.move(str(src), str(dst / src.name))
            v = comp[name]
            rec["reruns"][name] = {"truncated_calls": v.get("truncated_calls"), "raw_lines": v.get("raw_lines"), "server_error_rows": v.get("server_error_rows"),
                                   "rule": v.get("rerun_rule"), "original_sha256": v["sha256"], "moved_to": "cells/replaced_S/"}
    rec_p.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    old = json.loads(jr.read_text(encoding="utf-8"))["jobs"] if jr.exists() else []
    jr.write_text(json.dumps({"jobs": old + jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
