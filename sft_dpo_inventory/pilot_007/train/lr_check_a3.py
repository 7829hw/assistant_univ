# -*- coding: utf-8 -*-
"""A3 lr 일정·lr 합 확인(결정 186 S2; ``lr_check_a2.py``와 같은 계산). Trainer와 같은 함수(TrainingArguments.get_warmup_steps, get_scheduler)로 step별 lr을 계산한다. 모델 호출 없음.

    hfvenv/bin/python lr_check_a3.py   # -> configs_a3/lr_check.json

- step 수 = ceil(레코드 / accumulation) × epoch(Trainer와 같음). 두 recipe 모두 1 epoch 끝에서 lr 0 — 전체 합을 낸다.
- 기준: pilot_006 F43(RC3 1,861, 2 epoch)의 epoch 1까지 lr 합 0.0698. RC5 레코드(1,811)가 RC3c(1,356)보다 많아 R1'도 0.070보다 클 것(결정 186).
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
for jid in ("R1p-o43", "R1p-o1016", "R1p-o7", "R1pp-o43", "R1pp-o1016", "R1pp-o7"):
    cfg = yaml.safe_load((HERE / f"configs_a3/{jid}.yaml").read_text(encoding="utf-8"))
    pe, tot, w, l = plan(cfg, count(cfg["data"]["train"]))
    out[jid] = {"records": pe, "epochs_in_schedule": cfg["training"]["num_train_epochs"], "total_steps": tot, "warmup_steps": w, "peak_lr": max(l),
                "lr_last_step": l[-1], "lr_sum": round(sum(l), 5)}
out["check"] = {"one_epoch_schedule": all(out[j]["epochs_in_schedule"] == 1 for j in out if j.startswith("R1")),
                "R1p_sum_gt_pilot006_0.0698": all(out[j]["lr_sum"] > 0.0698 for j in ("R1p-o43", "R1p-o1016", "R1p-o7")),
                "R1pp_sum_double_R1p": all(abs(out[f"R1pp-{o}"]["lr_sum"] - 2 * out[f"R1p-{o}"]["lr_sum"]) < 1e-4 for o in ("o43", "o1016", "o7"))}
(HERE / "configs_a3/lr_check.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
print(json.dumps(out, indent=1))
