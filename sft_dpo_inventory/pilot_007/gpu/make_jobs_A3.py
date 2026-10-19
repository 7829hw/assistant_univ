# -*- coding: utf-8 -*-
"""A3 작업 표(결정 186·191, 지시 2.2). PLAN_A3 고정 전에 커밋한다. scheduler8(``--gpus`` 세 장, ``--ollama-uuid`` GPU 2)이 읽는다.

    python3 make_jobs_A3.py   # -> jobs_A3.json

- 학습: 지시 표의 우선 1(두 바퀴)을 번갈아 배치하려고 바퀴마다 우선을 나눈다 — 1: A3-R1p-o43·A3-R1pp-o43·A3-R1p-o1016, 2: A3-R1pp-o1016·A3-R1p-o7·A3-R1pp-o7
  (같은 우선이면 스케줄러가 ID 순으로 고르므로). ``train_a7``(1 epoch, 25·50·75·100% = step 453·906·1358·1811).
- 평가(우선 3 = 지시의 2): E-A3_<학습> — 100% checkpoint(step 1811), 주 셋(selection_v2 + holdout)·valid98·aux 각 k=4(seed_base 20261100). 셀 라벨 ``a3_r1p_o43_*`` 등(A2 R1' 셀과 겹치지 않게 a3_ 접두).
- 궤적(우선 4 = 지시의 3): E-A3q_<학습> — 25·50·75% checkpoint, 주 셋 greedy k=1.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = "/home/hwkim/sftdpo_work/pilot_007/train_a3"
CK = {"q25": 453, "q50": 906, "q75": 1358, "q100": 1811}
ROUNDS = [(1, "R1p-o43"), (1, "R1pp-o43"), (1, "R1p-o1016"), (2, "R1pp-o1016"), (2, "R1p-o7"), (2, "R1pp-o7")]
jobs = []
for prio, cid in ROUNDS:
    jid = f"A3-{cid}"
    jobs.append({"id": jid, "type": "train_a7", "kind": f"train_a7_{jid}", "server": "train", "est": 175, "prio": prio,
                 "config": f"sft_dpo_inventory/pilot_007/train/configs_a3/{cid}.yaml"})
for _, cid in ROUNDS:
    jid, nm = f"A3-{cid}", "A3_" + cid.replace("-", "_")
    ck = lambda s: f"{OUT}/{cid}/checkpoint-{s}"  # noqa: E731
    cells = [{"label": f"{nm.lower()}_{g}", "model": nm, "target": "full", "gold": g, "k": 4, "seed_base": 20261100, "greedy": False} for g in ("sel", "holdout", "valid98", "aux")]
    jobs.append({"id": f"E-A3_{cid}", "type": "cells", "kind": f"cells_{jid}_100_main_valid98_aux_k4", "server": f"lora:{nm}={ck(CK['q100'])}", "est": 55, "prio": 3,
                 "deps": [f"file:{ck(CK['q100'])}/adapter_model.safetensors|{jid}"], "cells": cells})
for _, cid in ROUNDS:
    jid, nm = f"A3-{cid}", "A3_" + cid.replace("-", "_")
    ck = lambda s: f"{OUT}/{cid}/checkpoint-{s}"  # noqa: E731
    loras = " ".join(f"{nm}{q}={ck(CK[q])}" for q in ("q25", "q50", "q75"))
    qc = [{"label": f"{nm.lower()}_{q}_greedy_{g}", "model": f"{nm}{q}", "target": "full", "gold": g, "k": 1, "greedy": True} for q in ("q25", "q50", "q75") for g in ("sel", "holdout")]
    jobs.append({"id": f"E-A3q_{cid}", "type": "cells", "kind": f"cells_{jid}_q25_50_75_greedy_main", "server": f"lora:{loras}", "est": 35, "prio": 4,
                 "deps": [f"file:{ck(CK['q100'])}/adapter_model.safetensors|{jid}"], "cells": qc})
(HERE / "jobs_A3.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(jobs), [(j["prio"], j["id"]) for j in jobs])
