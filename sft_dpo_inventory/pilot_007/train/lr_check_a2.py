# -*- coding: utf-8 -*-
"""A2 lr 일정·lr 합 확인(결정 177·178 S0). Trainer와 같은 함수(TrainingArguments.get_warmup_steps, get_scheduler)로 step별 lr을 계산한다. 모델 호출 없음.

    hfvenv/bin/python lr_check_a2.py   # -> configs_a2/lr_check.json

- step 수 = ceil(레코드 / accumulation) × epoch(Trainer와 같음). (a)는 2 epoch 일정에서 epoch 1 끝(step = 레코드 수)까지의 lr 합, (b)는 1 epoch 전체 합.
- 기준: pilot_006 F43(RC3 1,861, 2 epoch)의 epoch 1까지 lr 합. 의도: (a) ≈ 0.070 근처(레코드가 적어 약간 작음), (b) ≈ 0.068.
"""
import json
import math
import sys
from pathlib import Path

import torch
import yaml
from transformers import TrainingArguments, get_scheduler

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def plan(cfg, n_records):
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
out["pilot006_F43(reference)"] = {"records": pe, "total_steps": tot, "stop_step": pe, "lr_sum_to_stop": round(sum(l[:pe]), 5), "lr_at_stop": l[pe - 1]}
for jid in ("C-s43", "C-s1016", "C-s7", "R1p-o43", "R1p-o1016", "R1p-o7"):
    cfg = yaml.safe_load((HERE / f"configs_a2/{jid}.yaml").read_text(encoding="utf-8"))
    pe, tot, w, l = plan(cfg, count(cfg["data"]["train"]))
    stop = pe  # (a) epoch 1 끝에서 멈춤(train_diag), (b) 1 epoch 전체
    out[jid] = {"records": pe, "epochs_in_schedule": cfg["training"]["num_train_epochs"], "total_steps_in_schedule": tot, "stop_step": stop, "warmup_steps": w,
                "peak_lr": max(l), "lr_at_stop": l[stop - 1], "lr_after_stop(next scheduled)": l[stop] if stop < tot else 0.0,
                "lr_sum_to_stop": round(sum(l[:stop]), 5)}
ok_a = all(abs(out[j]["lr_sum_to_stop"] - 0.070) < 0.01 and out[j]["epochs_in_schedule"] == 2 for j in ("C-s43", "C-s1016", "C-s7"))
ok_b = all(abs(out[j]["lr_sum_to_stop"] - 0.068) < 0.005 and out[j]["epochs_in_schedule"] == 1 and out[j]["lr_after_stop(next scheduled)"] == 0.0 for j in ("R1p-o43", "R1p-o1016", "R1p-o7"))
out["check"] = {"a_two_epoch_schedule_stop_at_epoch1_sum_near_0.070": ok_a, "b_one_epoch_to_zero_sum_near_0.068": ok_b}
(HERE / "configs_a2/lr_check.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
print(json.dumps(out, indent=1))
