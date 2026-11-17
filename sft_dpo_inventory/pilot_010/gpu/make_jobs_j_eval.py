# -*- coding: utf-8 -*-
"""pilot_010 판정 단계 평가 작업(PLAN_J 4·8절)을 ``gpu/J/jobs_j.json``에 더한다. 학습 작업(``make_jobs_j.py``)은 그대로 두고 평가 작업만 새로 쓴다.

    python3 sft_dpo_inventory/pilot_010/gpu/make_jobs_j_eval.py --commit <평가 도구 고정 커밋>

- 모든 평가 작업은 ``commit``(평가 도구 고정 커밋)의 worktree에서 돈다(scheduler17 ``commit`` 키). 시작 조건 = 어댑터 파일(학습 작업 끝) + ``ready:J_TOOLS``.
- PF2(``no_rerun``, 잘림 다시 돌리기 없음): ``protected_final_v2/run_cell_pf2.py``, 동시 8, 기준일 2026-10-26, ``--sealed``,
  gold·셀·원문은 ``/data/hwkim/sftdpo_work/protected_final_v2/{pf2_gold.yaml,cells,raw}``(700, ``umask 077``). 작업 실패 때 옮길 ``outputs``를 적는다.
  V4·B2 F k=4(회차 20261101–04), base k=8(20261101–08).
- H-final: ``pilot_006_prep/gpu_data/run_cell6x.py``(H-dev 셀과 같은 실행기), 동시 32, k=1(회차 20261101), base k=1·2, 셀 ``pilot_010/cells/J``.
  scheduler17 기본 다시 돌리기 검사(PLAN_S 5절: 잘림 > 1%)를 쓴다(PLAN_J 9절). ``--sealed``(작업 로그에 정답률을 쓰지 않음).
- 우선순위(PLAN_J 8절, D6): 학습 1–5 → PF2 V4(10–14) → PF2 base(20) → H-final V4(30–34) → H-final base(40) → PF2 B2 F(50–54) → H-final B2 F(60–64).
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = "/data/hwkim/sftdpo_work/runtime/envs/hf/bin/python"
V4 = (101, 523, 2029, 31, 20271027)
B2F = (43, 1016, 7, 11, 2027)
TRAIN_J = "/data/hwkim/sftdpo_work/pilot_010/train_j"
TRAIN_B2 = "/data/hwkim/sftdpo_work/pilot_007/train_b2"
PFD = "/data/hwkim/sftdpo_work/protected_final_v2"
HF_GOLD = "sft_dpo_inventory/ablation_012/e2/h_final.yaml"


def pf_cell(model, label, k):
    return {"name": f"{label}_s{k}", "label": label, "k": k,
            "cmd": (f"umask 077 && {PY} {{WT}}/sft_dpo_inventory/pilot_010/protected_final_v2/run_cell_pf2.py --port {{PORT}} --model {model} --label {label} --k {k} "
                    f"--concurrency 8 --grounding-target full --out-dir {PFD}/cells --raw-dir {PFD}/raw --seed-base 20261100 --gold {PFD}/pf2_gold.yaml "
                    f"--all-items --sealed --reference-date 2026-10-26")}


def hf_cell(model, label, k):
    return {"name": f"{label}_s{k}", "label": label, "k": k,
            "cmd": (f"{PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py --port {{PORT}} --model {model} --label {label} --k {k} "
                    f"--concurrency 32 --grounding-target full --out-dir {{MAIN}}/sft_dpo_inventory/pilot_010/cells/J "
                    f"--raw-dir {{MAIN}}/training/generated/pilot_010/cells_raw_J --seed-base 20261100 --gold {HF_GOLD} --all-items --sealed")}


def pf_outputs(cells):
    return [p for c in cells for p in (f"{PFD}/cells/{c['name']}.json", f"{PFD}/cells/{c['name']}.log", f"{PFD}/raw/{c['name']}_raw.jsonl")]


def eval_jobs(commit):
    jobs = []
    arms = [("V4", s, f"V4_o{s}", f"lora:V4_o{s}={TRAIN_J}/J-V4-o{s}/checkpoint-1984",
             [f"file:{TRAIN_J}/J-V4-o{s}/checkpoint-1984/adapter_model.safetensors|T-J-V4-o{s}"]) for s in V4]
    b2f = [("B2F", s, f"B2F_o{s}", f"lora:B2F_o{s}={TRAIN_B2}/B2-F-o{s}/checkpoint-1811", [f"file:{TRAIN_B2}/B2-F-o{s}/checkpoint-1811/adapter_model.safetensors|"]) for s in B2F]
    # PF2 V4 (10–14)
    for i, (arm, s, model, server, deps) in enumerate(arms):
        cells = [pf_cell(model, f"pf2_v4_o{s}", k) for k in range(1, 5)]
        jobs.append({"id": f"PF-V4-o{s}", "type": "raw", "kind": f"pf2_j_V4-o{s}_k4", "server": server, "est": 35, "prio": 10 + i, "commit": commit,
                     "deps": deps + ["ready:J_TOOLS"], "cells": cells, "no_rerun": True, "outputs": pf_outputs(cells)})
    # PF2 base (20)
    cells = [pf_cell("base", "pf2_base", k) for k in range(1, 9)]
    jobs.append({"id": "PF-base", "type": "raw", "kind": "pf2_j_base_k8", "server": "base", "est": 70, "prio": 20, "commit": commit,
                 "deps": ["ready:J_TOOLS"], "cells": cells, "no_rerun": True, "outputs": pf_outputs(cells)})
    # H-final V4 (30–34)
    for i, (arm, s, model, server, deps) in enumerate(arms):
        jobs.append({"id": f"HF-V4-o{s}", "type": "raw", "kind": f"hfinal_j_V4-o{s}_k1", "server": server, "est": 45, "prio": 30 + i, "commit": commit,
                     "deps": deps + ["ready:J_TOOLS"], "cells": [hf_cell(model, f"hfinal_v4_o{s}", 1)]})
    # H-final base (40)
    jobs.append({"id": "HF-base", "type": "raw", "kind": "hfinal_j_base_k1x2", "server": "base", "est": 90, "prio": 40, "commit": commit,
                 "deps": ["ready:J_TOOLS"], "cells": [hf_cell("base", "hfinal_base", k) for k in (1, 2)]})
    # PF2 B2 F (50–54)
    for i, (arm, s, model, server, deps) in enumerate(b2f):
        cells = [pf_cell(model, f"pf2_b2f_o{s}", k) for k in range(1, 5)]
        jobs.append({"id": f"PF-B2F-o{s}", "type": "raw", "kind": f"pf2_j_B2F-o{s}_k4", "server": server, "est": 35, "prio": 50 + i, "commit": commit,
                     "deps": deps + ["ready:J_TOOLS"], "cells": cells, "no_rerun": True, "outputs": pf_outputs(cells)})
    # H-final B2 F (60–64, 시간이 남을 때)
    for i, (arm, s, model, server, deps) in enumerate(b2f):
        jobs.append({"id": f"HF-B2F-o{s}", "type": "raw", "kind": f"hfinal_j_B2F-o{s}_k1", "server": server, "est": 45, "prio": 60 + i, "commit": commit,
                     "deps": deps + ["ready:J_TOOLS"], "cells": [hf_cell(model, f"hfinal_b2f_o{s}", 1)]})
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", required=True)
    a = ap.parse_args()
    if len(a.commit) != 40:
        raise SystemExit("--commit must be a full 40-hex commit")
    p = HERE / "J/jobs_j.json"
    body = json.loads(p.read_text(encoding="utf-8"))
    have = {j["id"] for j in body["jobs"]}
    new = [j for j in eval_jobs(a.commit) if j["id"] not in have]
    body["jobs"] += new
    body["note"] = "pilot_010 판정 단계(결정 267, PLAN_J). 학습 5개(make_jobs_j.py) + 평가(make_jobs_j_eval.py, 도구 커밋 " + a.commit[:8] + ")."
    p.write_text(json.dumps(body, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps([(j["prio"], j["id"], j["server"][:30], len(j.get("cells", []))) for j in new], ensure_ascii=False))


if __name__ == "__main__":
    main()
