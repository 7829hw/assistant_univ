# -*- coding: utf-8 -*-
"""세션 4 GPU 작업 표(결정 161–163, 지시 2.1b–2.3). 실행 전에 커밋한다(S1: E-rep 새 sampling seed, greedy 설정 포함).

    python3 make_jobs4.py   # -> post/jobs4.json

- S1: E-rep sampling seed_base = **20261200**(원래 셀은 20261100; 회차 seed = seed_base + k). greedy 셀 = ``run_cell6w.py --greedy``(temperature 0, k=1, 판정에 쓰지 않음).
- 주 셋 151 = selection_v2(``sel``) + holdout. 진단 학습 checkpoint: epoch 1의 25·50·75·100% = step round(N·f)(N = 레코드 수, F 1861·P 1826).
- T-v3d(우선 11)·D-avg(우선 10)는 조건이 맞을 때 이 파일에 더한다(스케줄러가 20초마다 다시 읽음).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRAIN = "/home/hwkim/sftdpo_work/pilot_006/train"
DIAG = "/home/hwkim/sftdpo_work/pilot_006/diag"
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"
REP_SEED = 20261200
E1 = {"F43": (f"{TRAIN}/F43/checkpoint-1861", "full"), "F1016": (f"{TRAIN}/F1016/checkpoint-1861", "full"),
      "P43": (f"{TRAIN}/P43/checkpoint-1826", "partial"), "P1016": (f"{TRAIN}/P1016/checkpoint-1826", "partial")}
D = [("D-F7", "full", 1861, 1), ("D-P7", "partial", 1826, 2), ("D-F43o1016", "full", 1861, 3), ("D-F1016o43", "full", 1861, 4)]


def steps(n):
    return [max(1, round(n * f)) for f in (0.25, 0.5, 0.75, 1.0)]


def main_set(label, model, target, k=4, seed_base=20261100, greedy=False):
    return [{"label": f"{label}_sel", "model": model, "target": target, "gold": "sel", "k": k, "seed_base": seed_base, "greedy": greedy},
            {"label": f"{label}_holdout", "model": model, "target": target, "gold": "holdout", "k": k, "seed_base": seed_base, "greedy": greedy}]


def name(did):
    return did.replace("-", "").replace("o", "o")


jobs = [{"id": "O1", "type": "ollama", "kind": "ollama_speed_0.40.6", "server": "ollama", "est": 10, "prio": 0,
         "cmd": [PY, "{WT}/sft_dpo_inventory/pilot_006/post/o1_speed.py", "--main", "{MAIN}"], "outputs": ["{MAIN}/sft_dpo_inventory/pilot_006/post/o1_speed.json"]}]
for did, arm, n, prio in D:
    cfg = f"sft_dpo_inventory/pilot_006/post/diag/configs/diag_{did}.yaml"
    jobs.append({"id": did, "type": "train_diag", "kind": f"train_diag_{did}", "server": "train", "est": round(n * 6.5 / 60), "prio": prio, "config": cfg})
for m in ("F43", "F1016"):
    path, arm = E1[m]
    jobs.append({"id": f"E-rep_{m}", "type": "cells", "kind": f"cells_rep_{m}_main_k4_seed{REP_SEED}", "server": f"lora:{m}={path}", "est": 40, "prio": 5,
                 "cells": main_set(f"rep_{m.lower()}_e1", m, arm, 4, REP_SEED)})
jobs.append({"id": "E-greedy_base", "type": "cells", "kind": "cells_greedy_base_main", "server": "b17408", "est": 12, "prio": 6,
             "cells": main_set("greedy_base", "base", "full", 1, greedy=True)})
for m, (path, arm) in E1.items():
    jobs.append({"id": f"E-greedy_{m}", "type": "cells", "kind": f"cells_greedy_{m}_main", "server": f"lora:{m}={path}", "est": 12, "prio": 6,
                 "cells": main_set(f"greedy_{m.lower()}_e1", m, arm, 1, greedy=True)})
for did, arm, n, _ in D:
    s25, s50, s75, s100 = steps(n)
    nm = did.replace("-", "_")
    ck = lambda s: f"{DIAG}/{did}/checkpoint-{s}"  # noqa: E731
    owner = f"|{did}"
    jobs.append({"id": f"E-D_{did}", "type": "cells", "kind": f"cells_{did}_100_main_k4", "server": f"lora:{nm}={ck(s100)}", "est": 40, "prio": 7,
                 "deps": [f"file:{ck(s100)}/adapter_model.safetensors{owner}"], "cells": main_set(f"{nm.lower()}_q100", nm, arm, 4)})
    loras = " ".join(f"{nm}q{q}={ck(s)}" for q, s in (("25", s25), ("50", s50), ("75", s75)))
    jobs.append({"id": f"E-Dq_{did}", "type": "cells", "kind": f"cells_{did}_q25_50_75_greedy", "server": f"lora:{loras}", "est": 35, "prio": 8,
                 "deps": [f"file:{ck(s75)}/adapter_model.safetensors{owner}", f"file:{ck(s100)}/adapter_model.safetensors{owner}"],
                 "cells": [c for q in ("25", "50", "75") for c in main_set(f"{nm.lower()}_q{q}_greedy", f"{nm}q{q}", arm, 1, greedy=True)]})
    if did in ("D-F7", "D-P7"):
        jobs.append({"id": f"E-D7dev_{did}", "type": "cells", "kind": f"cells_{did}_100_dev", "server": f"lora:{nm}={ck(s100)}", "est": 90, "prio": 9,
                     "deps": [f"file:{ck(s100)}/adapter_model.safetensors{owner}"],
                     "cells": [{"label": f"{nm.lower()}_q100_{g}", "model": nm, "target": arm, "gold": g, "k": k} for g, k in (("valid98", 4), ("aux", 4), ("vendor100", 8))]})
V3D_COMMIT = "09c4eb4"
V3D_WT = f"/home/hwkim/sftdpo_work/worktrees/wt_{V3D_COMMIT}_T-v3d-run"
# T-v3d(우선 11, 결정 164): O1 통과·v3d 지시와 (c) 목록·문항 커밋 뒤에 더함(A2). Ollama GPU에서만, 스케줄러가 job = GPU로 학습·vLLM과 겹치지 않게 함.
jobs.append({"id": "T-v3d", "type": "ollama", "kind": "ollama_teacher_v3d_smoke_20x8", "server": "ollama", "est": 30, "prio": 11,
             # 스케줄러 worktree(52cc5f7)에는 v3d 파일이 없어, 작업 자체가 v3d 커밋에 고정한 worktree를 따로 만들어 거기서 돈다(결정 114).
             "cmd": ["bash", "-c", f"git -C {{MAIN}} worktree add --detach {V3D_WT} {V3D_COMMIT} && {PY} {V3D_WT}/sft_dpo_inventory/pilot_006/post/tv3d/run_tv3d.py --main {{MAIN}}"],
             "outputs": ["{MAIN}/sft_dpo_inventory/pilot_006/post/tv3d/tv3d_summary.json"]})
(HERE / "jobs4.json").write_text(json.dumps({"rep_seed_base": REP_SEED, "jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(jobs), [j["id"] for j in jobs])
