# -*- coding: utf-8 -*-
"""pilot_010 선택 단계 lr 일정·lr 합 확인(결정 251; ``pilot_009/train/lr_check_p9.py`` 사본, 대상만 S-V4·S-V8 여섯, 참고로 P9-F-o43). Trainer와 같은 함수(TrainingArguments.get_warmup_steps, get_scheduler)로 step별 lr을 계산한다. 모델 호출 없음.

    hfvenv/bin/python lr_check_s10.py   # -> configs_s10/lr_check.json

- step 수 = ceil(레코드 / accumulation) × epoch(Trainer와 같음). 두 recipe 모두 1 epoch 끝에서 lr 0 — 전체 합을 낸다.
- 변형마다 레코드 수가 달라 step·lr 합이 다르다(1 epoch, step = 레코드). 순서 seed는 lr 일정에 영향이 없다(변형 안에서 같아야 함).
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
for jid in [f"S-{v}-{o}" for v in ("V4", "V8") for o in ("o43", "o1016", "o7")]:
    cfg = yaml.safe_load((HERE / f"configs_s10/{jid}.yaml").read_text(encoding="utf-8"))
    pe, tot, w, l = plan(cfg, count(cfg["data"]["train"]))
    out[jid] = {"records": pe, "epochs_in_schedule": cfg["training"]["num_train_epochs"], "total_steps": tot, "warmup_steps": w, "peak_lr": max(l),
                "lr_last_step": l[-1], "lr_sum": round(sum(l), 5)}
S4 = {out[j]["lr_sum"] for j in out if j.startswith("S-V4")}
S8 = {out[j]["lr_sum"] for j in out if j.startswith("S-V8")}
out["check"] = {"one_epoch_schedule": all(out[j]["epochs_in_schedule"] == 1 for j in out if j.startswith("S-")),
                "peak_lr_2e-4": all(out[j]["peak_lr"] == 2e-4 for j in out if j.startswith("S-")),
                "lr_zero_after_last": all(out[j]["lr_last_step"] < 1e-6 for j in out if j.startswith("S-")),
                "same_within_variant": len(S4) == 1 and len(S8) == 1, "V4_lr_sum": sorted(S4), "V8_lr_sum": sorted(S8),
                "V8_over_V4_lr_sum": round(min(S8) / min(S4), 4) if S4 and S8 else None}
p9 = yaml.safe_load((ROOT / "sft_dpo_inventory/pilot_009/train/configs_p9/P9-F-o43.yaml").read_text(encoding="utf-8"))
pe, tot, w, l = plan(p9, count(p9["data"]["train"]))
out["P9-F-o43(reference)"] = {"records": pe, "lr_sum": round(sum(l), 5)}
b2 = yaml.safe_load((ROOT / "sft_dpo_inventory/pilot_007/train_data/configs_b2/B2-F-o43.yaml").read_text(encoding="utf-8"))
pe, tot, w, l = plan(b2, count(b2["data"]["train"]))
out["B2-F-o43(reference)"] = {"records": pe, "lr_sum": round(sum(l), 5)}
p8 = yaml.safe_load((ROOT / "sft_dpo_inventory/pilot_008/train/configs_p8/P8-F-o43.yaml").read_text(encoding="utf-8"))
pe, tot, w, l = plan(p8, count(p8["data"]["train"]))
out["P8-F-o43(reference)"] = {"records": pe, "lr_sum": round(sum(l), 5)}
(HERE / "configs_s10/lr_check.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
print(json.dumps(out, indent=1))
