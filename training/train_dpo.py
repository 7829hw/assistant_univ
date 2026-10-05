"""DPO initialized from SFT, with frozen SFT reference adapters by default."""
from training.trainer_common import (cli, model_for, peft_config_for, render_records,
                                     save_run, tokenizer_for)


def adapter_digest(model, name):
    import hashlib
    import torch
    from peft import get_peft_model_state_dict
    digest = hashlib.sha256()
    for key, tensor in sorted(get_peft_model_state_dict(model, adapter_name=name).items()):
        digest.update(key.encode())
        digest.update(str((tuple(tensor.shape), tensor.dtype)).encode())
        digest.update(tensor.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def initialize_reference_adapter(model, adapter):
    from peft import get_peft_model_state_dict, set_peft_model_state_dict
    model.load_adapter(adapter, adapter_name='reference', is_trainable=False)
    # PEFT 0.17 load_adapter copies FP32 weights into newly created BF16 modules
    # before upcasting. Restore from the already exact FP32 policy AFTER upcast.
    state = get_peft_model_state_dict(model, adapter_name='policy')
    set_peft_model_state_dict(model, state, adapter_name='reference')
    if adapter_digest(model, 'reference') != adapter_digest(model, 'policy'):
        raise ValueError('Reference adapter differs from initial SFT policy')
    model.set_adapter('policy')
    return adapter_digest(model, 'reference')


def consistent_reference_trainer(base):
    """TRL precompute precedes Accelerator's policy forward wrapping.

    BF16 base + FP32 LoRA must use the same mixed-precision context when
    caching reference logps as during training. Reuse the TRL computation.
    """
    class Trainer(base):
        def compute_ref_log_probs(self, batch):
            if self.precompute_ref_log_probs:
                with self.accelerator.autocast():
                    return super().compute_ref_log_probs(batch)
            return super().compute_ref_log_probs(batch)
    return Trainer


def main(argv=None):
    args, config, records, manifest = cli("dpo", argv)
    if args.dry_run or args.tokenizer_check:
        return
    from training.profiling import RunProfile
    profile = RunProfile(config, 'dpo')
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
    from peft import PeftModel
    from transformers import set_seed
    from trl import DPOConfig, DPOTrainer
    adapter = config["model"].get("adapter_path")
    if adapter:
        from pathlib import Path
        from training.inference import check_checkpoint_prompt
        if not (Path(adapter) / "adapter_config.json").exists():
            raise ValueError("SFT adapter checkpoint missing; run SFT first or select dpo_only explicitly")
        check_checkpoint_prompt(adapter)
    set_seed(config["training"].get("seed", 42))
    tokenizer = tokenizer_for(config)
    data = {split: Dataset.from_list(render_records(tokenizer, rows, config, "dpo"))
            for split, rows in records.items()}
    training = dict(config["training"])
    resume = training.pop("resume_from_checkpoint", None)
    if not records["valid"]:
        training["eval_strategy"] = "no"
    model = model_for(config)
    profile.after_model(model)
    peft_config, reference, reference_hash = None, None, None
    strategy = config.get('reference', {}).get('strategy', 'auto')
    if strategy == 'precompute':
        training.update(precompute_ref_log_probs=True, precompute_ref_batch_size=1)
    if adapter:
        # Inspect real base modules even when continuing an existing adapter.
        peft_config_for(config, model)
        model = PeftModel.from_pretrained(model, adapter, is_trainable=True, adapter_name="policy")
        reference_hash = initialize_reference_adapter(model, adapter)
        training.update(model_adapter_name="policy", ref_adapter_name="reference")
        if strategy == 'full':
            reference = PeftModel.from_pretrained(model_for(config), adapter, is_trainable=False)
            reference.requires_grad_(False)
            if adapter_digest(reference, 'default') != reference_hash:
                raise ValueError('Full reference differs from initial SFT policy')
            training['force_use_ref_model'] = True
    else:
        # Fresh adapter: disabling it exposes the frozen initial full checkpoint.
        peft_config = peft_config_for(config, model)
        if config.get("reference", {}).get("mode") == "explicit" or strategy == 'full':
            ref_config = config if strategy == 'full' else {
                **config, "model": {**config["model"], "name_or_path": config["reference"]["name_or_path"]}}
            reference = model_for(ref_config)
            reference.requires_grad_(False)
            training["force_use_ref_model"] = True
        # Full tuning without PEFT: DPOTrainer makes a frozen initial-policy copy.
    trainer = consistent_reference_trainer(profile.trainer_class(DPOTrainer))(
                         model=model, ref_model=reference, args=DPOConfig(**training),
                         processing_class=tokenizer, train_dataset=data["train"],
                         eval_dataset=data["valid"] if records["valid"] else None, peft_config=peft_config,
                         callbacks=profile.callbacks() + list(callbacks or []))
    profile.attach_model(trainer.model)
    profile.snapshot('trainer_ready')
    trainer.train(resume_from_checkpoint=args.resume_from_checkpoint or resume)
    if reference_hash:
        if adapter_digest(model, 'reference') != reference_hash:
            raise ValueError('DPO reference adapter changed during training')
        if reference is not None and adapter_digest(reference, 'default') != reference_hash:
            raise ValueError('DPO full reference changed during training')
        config.setdefault('reference', {})['initial_adapter_hash'] = reference_hash
        print('Fixed SFT reference hash verified after training')
    save_run(trainer, tokenizer, config, manifest, "dpo")
    if adapter:
        # Save only the trainable policy as a standard PEFT checkpoint.
        from pathlib import Path
        import shutil
        output = Path(config["training"]["output_dir"])
        for name in ("adapter_config.json", "adapter_model.safetensors", "adapter_model.bin"):
            if (output / "policy" / name).exists():
                shutil.copy2(output / "policy" / name, output / name)


if __name__ == "__main__":
    main()
