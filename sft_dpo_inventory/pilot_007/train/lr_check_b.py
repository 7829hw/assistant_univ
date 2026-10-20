# -*- coding: utf-8 -*-
"""B단계 lr 일정·lr 합 확인(결정 195 S0; ``lr_check_a3.py`` 사본, 대상만 B 열 개). Trainer와 같은 함수(TrainingArguments.get_warmup_steps, get_scheduler)로 step별 lr을 계산한다. 모델 호출 없음.

    hfvenv/bin/python lr_check_b.py   # -> configs_b/lr_check.json

- step 수 = ceil(레코드 / accumulation) × epoch(Trainer와 같음). 두 recipe 모두 1 epoch 끝에서 lr 0 — 전체 합을 낸다.
- arm마다 레코드 수가 달라(F 1,811, P 1,775) step·lr 합이 조금 다르다(결정 195). 순서 seed는 lr 일정에 영향이 없다.
"""
import json
from pathlib import Path

import math

import torch
import yaml
from transformers import TrainingArguments, get_scheduler

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def plan(cfg, n_records):  # lr_check_a2.py와 같은 함수(그 파일은 import하면 A2 결과를 다시 쓰므로 복사)
    t = cfg["training"]
    per_epoch = math.ceil(n_records / t["gradient_accumulation_steps"])
    total = per_epoch * int(t["num_train_epochs"])
    args = TrainingArguments(output_dir="/tmp/unused_lr", learning_rate=t["learning_rate"], warmup_ratio=t.get("warmup_ratio", 0) or 0,
                             warmup_steps=t.get("warmup_steps", 0) or 0, lr_scheduler_type="linear", report_to="none")
    warm = args.get_warmup_steps(total)
    opt = torch.optim.SGD([torch.nn.Parameter(torch.zeros(1))], lr=t["learning_rate"])
    sch = get_scheduler("linear", opt, num_warmup_steps=warm, num_training_steps=total)
    lrs = []
    for _ in range(total):
        lrs.append(opt.param_groups[0]["lr"])
        opt.step()
        sch.step()
    return per_epoch, total, warm, lrs


def count(path):
    return sum(1 for l in (ROOT / path).read_text(encoding="utf-8").splitlines() if l.strip())

out = {}
ref = yaml.safe_load((ROOT / "sft_dpo_inventory/pilot_006/run3/configs/pilot006_F43.yaml").read_text(encoding="utf-8"))
pe, tot, w, l = plan(ref, count(ref["data"]["train"]))
out["pilot006_F43(reference)"] = {"records": pe, "stop_step": pe, "lr_sum_to_stop": round(sum(l[:pe]), 5)}
for jid in [f"B-{a}-{o}" for a in ("F", "P") for o in ("o43", "o1016", "o7", "o11", "o2027")]:
    cfg = yaml.safe_load((HERE / f"configs_b/{jid}.yaml").read_text(encoding="utf-8"))
    pe, tot, w, l = plan(cfg, count(cfg["data"]["train"]))
    out[jid] = {"records": pe, "epochs_in_schedule": cfg["training"]["num_train_epochs"], "total_steps": tot, "warmup_steps": w, "peak_lr": max(l),
                "lr_last_step": l[-1], "lr_sum": round(sum(l), 5)}
Fs = {out[j]["lr_sum"] for j in out if j.startswith("B-F")}
Ps = {out[j]["lr_sum"] for j in out if j.startswith("B-P")}
out["check"] = {"one_epoch_schedule": all(out[j]["epochs_in_schedule"] == 1 for j in out if j.startswith("B-")),
                "peak_lr_2e-4": all(out[j]["peak_lr"] == 2e-4 for j in out if j.startswith("B-")),
                "same_within_arm": len(Fs) == 1 and len(Ps) == 1, "F_lr_sum": sorted(Fs), "P_lr_sum": sorted(Ps),
                "P_over_F_lr_sum": round(min(Ps) / min(Fs), 4) if Fs and Ps else None}
(HERE / "configs_b/lr_check.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
print(json.dumps(out, indent=1))
