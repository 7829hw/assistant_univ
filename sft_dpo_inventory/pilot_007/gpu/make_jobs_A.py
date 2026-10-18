# -*- coding: utf-8 -*-
"""A단계 작업 표(결정 167·169, 지시 2.2). PLAN_A 고정 전에 커밋한다. S-focus·J-b010은 목록이 커밋되면 이 파일에 더한다(스케줄러가 20초마다 다시 읽음).

    python3 make_jobs_A.py   # -> jobs_A.json

- 우선 1: A-R1-o{43,1016,7} 학습, 우선 2: A-R2-o{…} 학습(train_a7, 1 epoch).
- 우선 3: E-A_<학습 ID> — 그 학습의 100% checkpoint(R1 step 1356, R2 step 85)를 LoRA로 서빙해 주 셋(selection_v2 + holdout)·valid98·aux 각 k=4(seed_base 20261100).
- 우선 6(선택, 보고만): E-Aq_<학습 ID> — 25·50·75% checkpoint를 LoRA 셋으로 서빙해 주 셋 greedy k=1(시간이 있을 때만; 선택 규칙에 쓰지 않음).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = "/home/hwkim/sftdpo_work/pilot_007/train"
STEPS = {"R1": [339, 678, 1017, 1356], "R2": [21, 42, 64, 85]}  # train_a7 --dry-run lr_plan.save_at_steps
jobs = []
for prio, r in ((1, "R1"), (2, "R2")):
    for o in ("o43", "o1016", "o7"):
        jid = f"A-{r}-{o}"
        jobs.append({"id": jid, "type": "train_a7", "kind": f"train_a7_{jid}", "server": "train", "est": 135, "prio": prio,
                     "config": f"sft_dpo_inventory/pilot_007/train/configs/{jid}.yaml"})
for r in ("R1", "R2"):
    for o in ("o43", "o1016", "o7"):
        jid = f"A-{r}-{o}"
        nm = jid.replace("-", "_")
        ck = lambda s: f"{OUT}/{jid}/checkpoint-{s}"  # noqa: E731
        q25, q50, q75, q100 = STEPS[r]
        own = f"|{jid}"
        cells = [{"label": f"{nm.lower()}_{g}", "model": nm, "target": "full", "gold": g, "k": 4, "seed_base": 20261100, "greedy": False}
                 for g in ("sel", "holdout", "valid98", "aux")]
        jobs.append({"id": f"E-A_{jid}", "type": "cells", "kind": f"cells_{jid}_100_main_valid98_aux_k4", "server": f"lora:{nm}={ck(q100)}", "est": 85, "prio": 3,
                     "deps": [f"file:{ck(q100)}/adapter_model.safetensors{own}"], "cells": cells})
        loras = " ".join(f"{nm}q{q}={ck(s)}" for q, s in (("25", q25), ("50", q50), ("75", q75)))
        qc = [{"label": f"{nm.lower()}_q{q}_greedy_{g}", "model": f"{nm}q{q}", "target": "full", "gold": g, "k": 1, "greedy": True}
              for q in ("25", "50", "75") for g in ("sel", "holdout")]
        jobs.append({"id": f"E-Aq_{jid}", "type": "cells", "kind": f"cells_{jid}_q25_50_75_greedy_main", "server": f"lora:{loras}", "est": 35, "prio": 6,
                     "deps": [f"file:{ck(q100)}/adapter_model.safetensors{own}"], "cells": qc})
# 우선 4: S-focus(결정 169) — arm마다 8b 정답 표본 < 4인 소속·bucket 질문에 64표본(``pilot_007/self/sfocus_manifest.json``).
# 입력 목록은 스케줄러 worktree(고정 커밋 0eef870) 뒤에 커밋되므로 main 경로에서 읽고 sha256을 먼저 확인한다(코드는 worktree의 collect6b.py).
SF = json.loads((HERE.parent / "self/sfocus_manifest.json").read_text(encoding="utf-8"))
PY = "/home/hwkim/sftdpo_work/hfvenv/bin/python"
GEN = "/home/hwkim/assistant_univ/training/generated/pilot_007/self"
for arm, tag in (("full", "F"), ("partial", "P")):
    a = SF["arms"][arm]
    if not a["items"]:
        continue
    inp = f"{{MAIN}}/sft_dpo_inventory/pilot_007/self/sfocus_{arm}.jsonl"
    cmd = (f"echo '{a['sha256']}  {inp}' | sha256sum -c - && mkdir -p {GEN}/raw && {PY} {{WT}}/sft_dpo_inventory/pilot_006_prep/gpu/collect6b.py --mode self "
           f"--grounding-target {arm} --port {{PORT}} --label SF_{arm} --inputs {inp} --raw-out {GEN}/raw/SF_{arm}_raw.jsonl --out {GEN}/SF_{arm}_manifest.json "
           f"--server-meta /data/hwkim/sftdpo_work/pilot_006_prep/vllm --samples {SF['samples']} --no-greedy --round-seed {SF['round_seed']}")
    jobs.append({"id": f"S-focus-{tag}", "type": "raw", "kind": f"self_sfocus_{arm}_{a['items']}x{SF['samples']}", "server": "b17408",
                 "est": max(10, 3 * a["items"]), "prio": 4, "cmd": ["bash", "-c", cmd], "outputs": [f"{GEN}/SF_{arm}_manifest.json"]})
(HERE / "jobs_A.json").write_text(json.dumps({"jobs": jobs}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(len(jobs), [j["id"] for j in jobs])
