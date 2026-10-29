# -*- coding: utf-8 -*-
"""A2 작업 표(결정 177–181, 지시 2.2). PLAN_A2 고정 전에 커밋한다. scheduler8(GPU 0·1만)이 읽는다.

    python3 make_jobs_A2.py   # -> jobs_A2.json

- 학습(우선 1–3): (a)와 (b)를 바퀴마다 하나씩 — 1: C-s43·R1p-o43, 2: R1p-o1016·C-s1016, 3: C-s7·R1p-o7. GPU는 고정하지 않는다(Ollama GPU가 막히면 GPU 1이 무엇이든 받음).
  (a) ``train_diag``(pilot_006/post/diag/train_diag.py: 2 epoch 일정, epoch 1 끝 step 1356에서 멈춤, 25·50·75·100% = 339·678·1017·1356 저장),
  (b) ``train_a7``(1 epoch, 같은 저장 지점).
- 평가(우선 4): E-A2_<학습> — 100% checkpoint(step 1356)를 LoRA로, 주 셋(selection_v2 + holdout)·valid98·aux 각 k=4(seed_base 20261100). 학습 여섯이 모두 먼저(지시 2.2).
- 기준(우선 4): E-ref_F1016dev — pilot_006 F-s1016 e1의 개발 셋 셀((a) 해석 s1016 짝용, 학습 아님).
- 궤적(우선 5, 선택): E-A2q_<R1p> — (b)의 25·50·75% checkpoint, 주 셋 greedy k=1.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = "/data/hwkim/sftdpo_work/pilot_007/train_a2"
CK = [339, 678, 1017, 1356]
ORDER = [(1, "C-s43"), (1, "R1p-o43"), (2, "R1p-o1016"), (2, "C-s1016"), (3, "C-s7"), (3, "R1p-o7")]
jobs = []
for prio, jid in ORDER:
    t = "train_diag" if jid.startswith("C-") else "train_a7"
    jobs.append({"id": jid, "type": t, "kind": f"{t}_{jid}", "server": "train", "est": 135, "prio": prio,
                 "config": f"sft_dpo_inventory/pilot_007/train_data/configs_a2/{jid}.yaml"})
for _, jid in ORDER:
    nm = jid.replace("-", "_")
    ck = lambda s: f"{OUT}/{jid}/checkpoint-{s}"  # noqa: E731
    cells = [{"label": f"{nm.lower()}_{g}", "model": nm, "target": "full", "gold": g, "k": 4, "seed_base": 20261100, "greedy": False}
             for g in ("sel", "holdout", "valid98", "aux")]
    jobs.append({"id": f"E-A2_{jid}", "type": "cells", "kind": f"cells_{jid}_100_main_valid98_aux_k4", "server": f"lora:{nm}={ck(1356)}", "est": 55, "prio": 4,
                 "deps": [f"file:{ck(1356)}/adapter_model.safetensors|{jid}"], "cells": cells})
for _, jid in ORDER:
    if not jid.startswith("R1p"):
        continue
    nm = jid.replace("-", "_")
    ck = lambda s: f"{OUT}/{jid}/checkpoint-{s}"  # noqa: E731
    loras = " ".join(f"{nm}q{q}={ck(s)}" for q, s in (("25", 339), ("50", 678), ("75", 1017)))
    qc = [{"label": f"{nm.lower()}_q{q}_greedy_{g}", "model": f"{nm}q{q}", "target": "full", "gold": g, "k": 1, "greedy": True}
          for q in ("25", "50", "75") for g in ("sel", "holdout")]
    jobs.append({"id": f"E-A2q_{jid}", "type": "cells", "kind": f"cells_{jid}_q25_50_75_greedy_main", "server": f"lora:{loras}", "est": 35, "prio": 5,
                 "deps": [f"file:{ck(1356)}/adapter_model.safetensors|{jid}"], "cells": qc})
# 우선 4: E-ref_F1016dev — (a) 해석의 s1016 짝용 기준 셀(pilot_006 F-s1016 e1 adapter, 기존 것)을 개발 셋 valid98·aux k=4로(pilot_006에는 s1016 개발 셋 셀이 없음).
REF = "/data/hwkim/sftdpo_work/pilot_006/train/F1016/checkpoint-1861"
jobs.append({"id": "E-ref_F1016dev", "type": "cells", "kind": "cells_pilot006_F1016_e1_valid98_aux_k4", "server": f"lora:F1016e1={REF}", "est": 35, "prio": 4,
             "cells": [{"label": f"ref_f1016_e1_{g}", "model": "F1016e1", "target": "full", "gold": g, "k": 4, "seed_base": 20261100, "greedy": False} for g in ("valid98", "aux")]})
(HERE / "jobs_A2.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(jobs), [(j["prio"], j["id"]) for j in jobs])
