"""Completion-only SFT using the pinned TRL prompt/completion API."""
from training.trainer_common import (cli, model_for, peft_config_for, render_records,
                                     save_run, tokenizer_for)


def main(argv=None):
    args, config, records, manifest = cli("sft", argv)
    if args.dry_run or args.tokenizer_check:
        return
    from training.profiling import RunProfile
    profile = RunProfile(config, 'sft')
    error = None
    try:
        train(args, config, records, manifest, profile)
    except BaseException as exc:
        error = exc
        raise
    finally:
        profile.finish(error)


def train(args, config, records, manifest, profile, callbacks=None):
    from datasets import Dataset
    from transformers import set_seed
    from trl import SFTConfig, SFTTrainer
    set_seed(config["training"].get("seed", 42))
    tokenizer = tokenizer_for(config)
    data = {split: Dataset.from_list(render_records(tokenizer, rows, config, "sft"))
            for split, rows in records.items()}
    training = dict(config["training"])
    training["max_length"] = training.pop("max_seq_length", 8192)
    resume = training.pop("resume_from_checkpoint", None)
    training.update(completion_only_loss=True, assistant_only_loss=False, packing=False)
    if not records["valid"]:
        training["eval_strategy"] = "no"
    model = model_for(config)
    profile.after_model(model)
    trainer = profile.trainer_class(SFTTrainer)(model=model, args=SFTConfig(**training), processing_class=tokenizer,
                         train_dataset=data["train"], eval_dataset=data["valid"] if records["valid"] else None,
                         peft_config=peft_config_for(config, model), callbacks=profile.callbacks() + list(callbacks or []))
    profile.attach_model(trainer.model)
    profile.snapshot('trainer_ready')
    # Check the actual TRL mask before an optimizer step; prompt/system cannot learn.
    for row in trainer.train_dataset:
        mask = row.get("completion_mask")
        if mask is None or not any(mask) or mask[0] != 0:
            raise ValueError("TRL did not create a completion-only loss mask")
    trainer.train(resume_from_checkpoint=args.resume_from_checkpoint or resume)
    save_run(trainer, tokenizer, config, manifest, "sft")


if __name__ == "__main__":
    main()
