# -*- coding: utf-8 -*-
"""진단 학습 wrapper(결정 161 N3). ``training.train_sft``를 그대로 쓰고(기존 파일 수정 없음) callback 하나만 더한다.

    hfvenv/bin/python sft_dpo_inventory/pilot_006/post/diag/train_diag.py --config <diag config>

- recipe는 고정된 pilot_006 config와 같다: 2 epoch 기준 learning rate 일정(linear, warmup 1 step) 그대로 두고 **epoch 1 끝(step N = 레코드 수, batch 1·accum 1)에서 멈춘다.**
  그래서 100% checkpoint는 pilot_006의 epoch 1 checkpoint와 같은 조건이다.
- 저장: epoch 1의 25·50·75·100% 지점(step round(N·f))에 ``control.should_save``(config의 save_strategy는 no).
- seed: ``training.seed``(set_seed → LoRA 초기화·dropout)와 ``training.data_seed``(accelerate SeedableRandomSampler의 순서)를 config에서 따로 준다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from transformers import TrainerCallback  # noqa: E402

from training.train_sft import train  # noqa: E402
from training.trainer_common import cli  # noqa: E402

FRACTIONS = (0.25, 0.5, 0.75, 1.0)


class StopAndSave(TrainerCallback):
    def __init__(self, n):
        self.n = n
        self.save_at = {max(1, round(n * f)) for f in FRACTIONS}

    def on_step_end(self, args, state, control, **kwargs):
        if state.global_step in self.save_at:
            control.should_save = True
        if state.global_step >= self.n:
            control.should_training_stop = True
        return control


def main(argv=None):
    args, config, records, manifest = cli("sft", argv)
    if args.dry_run or args.tokenizer_check:
        return
    from training.profiling import RunProfile
    profile = RunProfile(config, "sft")
    n = len(records["train"])
    print({"diag_stop_step": n, "save_at": sorted(StopAndSave(n).save_at)}, flush=True)
    error = None
    try:
        train(args, config, records, manifest, profile, callbacks=[StopAndSave(n)])
    except BaseException as exc:
        error = exc
        raise
    finally:
        profile.finish(error)


if __name__ == "__main__":
    main()
