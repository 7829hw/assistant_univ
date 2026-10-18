# -*- coding: utf-8 -*-
"""pilot_007 A단계 학습 wrapper(결정 167 O3). ``training.train_sft``를 그대로 쓰고(기존 파일 수정 없음) callback 하나만 더한다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/train/train_a7.py --config <A config>            # 학습
    hfvenv/bin/python sft_dpo_inventory/pilot_007/train/train_a7.py --config <A config> --dry-run  # 데이터 검사 + lr 계획 출력

- 1 epoch 일정(num_train_epochs 1, linear 감쇠가 epoch 1 끝에서 0). 끝까지 학습한다(세션 4 ``train_diag``와 달리 멈추지 않음).
- 저장: optimizer step T(= ceil(레코드 수 / accumulation), Trainer와 같은 계산)의 25·50·75·100% 지점(step round(T·f))에 ``control.should_save``
  (config의 save_strategy는 no). 쓰는 것은 100%(lr 0)뿐이고 25·50·75%는 보고용.
- seed: ``training.seed``(모델: LoRA 초기화·dropout)와 ``training.data_seed``(accelerate SeedableRandomSampler의 데이터 순서)를 따로 준다.
- ``--dry-run``: 학습 코드의 dry-run 검사 뒤 lr 계획(``lr_plan``)을 JSON 한 줄로 출력한다. Trainer와 같은 함수(``TrainingArguments.get_warmup_steps``,
  ``get_scheduler``)로 step별 lr을 계산하고 accumulation·T·warmup·끝 lr을 적는다.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from transformers import TrainerCallback  # noqa: E402

from training.train_sft import train  # noqa: E402
from training.trainer_common import cli  # noqa: E402

FRACTIONS = (0.25, 0.5, 0.75, 1.0)


def total_steps(n_records, config):
    t = config["training"]
    per_epoch = max(n_records // t["gradient_accumulation_steps"] + int(n_records % t["gradient_accumulation_steps"] > 0), 1)
    return per_epoch * int(t["num_train_epochs"]), per_epoch


def save_points(total):
    return sorted({max(1, round(total * f)) for f in FRACTIONS})


def lr_plan(n_records, config):
    import torch
    from transformers import TrainingArguments, get_scheduler
    t = config["training"]
    total, per_epoch = total_steps(n_records, config)
    args = TrainingArguments(output_dir="/tmp/unused_lr_plan", learning_rate=t["learning_rate"], warmup_ratio=t.get("warmup_ratio", 0),
                             warmup_steps=t.get("warmup_steps", 0), lr_scheduler_type=t.get("lr_scheduler_type", "linear"), report_to="none")
    warm = args.get_warmup_steps(total)
    opt = torch.optim.SGD([torch.nn.Parameter(torch.zeros(1))], lr=t["learning_rate"])
    sch = get_scheduler(args.lr_scheduler_type, opt, num_warmup_steps=warm, num_training_steps=total)
    lrs = []
    for _ in range(total):  # step s(1부터)에서 optimizer가 쓰는 lr = 그 step 전에 scheduler가 준 값(Trainer 로그의 learning_rate와 같음)
        lrs.append(opt.param_groups[0]["lr"])
        opt.step()
        sch.step()
    pick = sorted({1, 2, warm, warm + 1, *save_points(total), total})
    return {"records": n_records, "gradient_accumulation_steps": t["gradient_accumulation_steps"], "per_device_train_batch_size": t["per_device_train_batch_size"],
            "num_train_epochs": t["num_train_epochs"], "optimizer_steps_total": total, "steps_per_epoch": per_epoch, "warmup_steps": warm,
            "peak_lr": max(lrs), "lr_at_step": {s: lrs[s - 1] for s in pick if 1 <= s <= total}, "lr_after_last_step": opt.param_groups[0]["lr"],
            "save_at_steps": save_points(total), "epoch1_end_lr_zero": opt.param_groups[0]["lr"] == 0.0 and per_epoch == total}


class SaveAt(TrainerCallback):
    def __init__(self):
        self.save_at = set()

    def on_train_begin(self, args, state, control, **kwargs):
        self.save_at = set(save_points(state.max_steps))
        print({"a7_max_steps": state.max_steps, "save_at": sorted(self.save_at)}, flush=True)

    def on_step_end(self, args, state, control, **kwargs):
        if state.global_step in self.save_at:
            control.should_save = True
        return control


def main(argv=None):
    args, config, records, manifest = cli("sft", argv)
    if args.dry_run:
        print(json.dumps({"lr_plan": lr_plan(len(records["train"]), config)}), flush=True)
        return
    if args.tokenizer_check:
        return
    from training.profiling import RunProfile
    profile = RunProfile(config, "sft")
    error = None
    try:
        train(args, config, records, manifest, profile, callbacks=[SaveAt()])
    except BaseException as exc:
        error = exc
        raise
    finally:
        profile.finish(error)


if __name__ == "__main__":
    main()
