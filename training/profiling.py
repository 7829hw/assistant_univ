"""Optional trainer instrumentation; no CUDA imports in data-only workflows."""
import json
import importlib.metadata
import platform
import shutil
import threading
import time
from pathlib import Path

from training.check_thor_env import system_memory, temperatures


def validate_profile(config, stage):
    safety = config.get('safety', {})
    fraction = safety.get('reserve_fraction', 0.2)
    if not 0 < fraction < 1 or safety.get('reserve_gib', 16) < 0 or safety.get('min_disk_gib', 2) < 0:
        raise ValueError('Invalid memory/disk safety margin')
    if not safety.get('unified_memory', False):
        return
    args, model = config['training'], config['model']
    if not args.get('bf16') or args.get('fp16') or not config.get('lora', {}).get('enabled', True):
        raise ValueError('Thor baseline requires BF16 LoRA')
    if model.get('load_in_4bit'):
        raise ValueError('Thor baseline is BF16 LoRA; test QLoRA separately before opting in')
    if model.get('attn_implementation') != 'sdpa' or args.get('optim') != 'adamw_torch':
        raise ValueError('Thor baseline requires SDPA and unfused PyTorch AdamW')
    if args.get('per_device_train_batch_size') != 1 or args.get('per_device_eval_batch_size', 1) != 1:
        raise ValueError('Thor baseline batch size must be 1; benchmark larger batches separately')
    if args.get('dataloader_num_workers', 0) > 2 or args.get('dataloader_pin_memory', False):
        raise ValueError('Thor baseline uses at most 2 workers and unpinned memory')
    if args.get('torch_compile', False) or not args.get('gradient_checkpointing'):
        raise ValueError('Thor baseline requires checkpointing and torch_compile=false')
    if stage == 'dpo':
        if config.get('reference', {}).get('mode', 'initial_policy') != 'initial_policy':
            raise ValueError('Thor baseline uses shared-base initial-policy reference')
        if args.get('reference_free', False) or args.get('sync_ref_model', False):
            raise ValueError('Thor baseline must preserve fixed-reference DPO')


def check_resources(config):
    """Read MemAvailable, reserve max(fraction of total, configured GiB)."""
    safety = config.get('safety', {})
    if not safety:
        return None
    memory = system_memory()
    if memory['total_bytes'] is None:
        raise RuntimeError('Cannot read system memory safety margin')
    reserve = max(memory['total_bytes'] * safety.get('reserve_fraction', 0.2),
                  safety.get('reserve_gib', 16) * 2**30)
    if memory['available_bytes'] < reserve:
        raise RuntimeError('System MemAvailable below reserve; stop and free memory before training')
    output = Path(config['training']['output_dir']).resolve()
    while not output.exists():
        output = output.parent
    free = shutil.disk_usage(output).free
    if free < safety.get('min_disk_gib', 2) * 2**30:
        raise RuntimeError('Insufficient free disk for configured training output')
    return {'reserve_bytes': int(reserve), 'memory': memory, 'disk_free_bytes': free}


class RunProfile:
    def __init__(self, config, stage):
        self.config, self.stage = config, stage
        self.enabled = config.get('profiling', {}).get('enabled', False)
        self.start = time.perf_counter()
        self.events, self.steps, self.losses = [], [], []
        self.tokens = 0
        self.minimum_available = None
        self.stop = threading.Event()
        self.thread = None
        self.hook = None
        self.backward_seen = False
        self.training_started = None
        self.resource_check = check_resources(config)
        if self.enabled:
            self.snapshot('initial')
            def sample():
                while not self.stop.wait(1):
                    available = system_memory()['available_bytes']
                    if available is not None:
                        self.minimum_available = min(self.minimum_available or available, available)
            self.thread = threading.Thread(target=sample, daemon=True)
            self.thread.start()

    def snapshot(self, phase):
        if not self.enabled:
            return
        import torch
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        row = {'phase': phase, 'elapsed_seconds': time.perf_counter() - self.start,
               'system': system_memory(), 'temperature_c': temperatures()}
        if torch.cuda.is_available():
            row['cuda'] = {key: getattr(torch.cuda, key)() for key in (
                'memory_allocated', 'memory_reserved', 'max_memory_allocated', 'max_memory_reserved')}
        self.events.append(row)
        available = row['system']['available_bytes']
        if available is not None:
            self.minimum_available = min(self.minimum_available or available, available)
        print(json.dumps({'memory_phase': row}, ensure_ascii=False), flush=True)

    def after_model(self, model):
        self.model_load_seconds = time.perf_counter() - self.start
        self.snapshot('model_load')
        check_resources(self.config)

    def attach_model(self, model):
        # PEFT may call base.forward directly; hook the final Trainer policy wrapper.
        if self.enabled:
            def forward(module, inputs, output):
                # Reference precompute can run first; record first gradient-bearing policy forward.
                import torch
                if torch.is_grad_enabled():
                    self.snapshot('first_forward')
                    self.hook.remove()
            self.hook = model.register_forward_hook(forward)

    def callbacks(self):
        if not self.enabled:
            return []
        from transformers import TrainerCallback
        profile = self
        class Callback(TrainerCallback):
            def on_train_begin(self, args, state, control, **kwargs):
                import torch
                if torch.cuda.is_available():
                    torch.cuda.reset_peak_memory_stats()
                profile.training_started = time.perf_counter()
                profile.snapshot('training_start')
            def on_step_begin(self, args, state, control, **kwargs):
                check_resources(profile.config)
                profile.step_start = time.perf_counter()
            def on_optimizer_step(self, args, state, control, **kwargs):
                if not profile.steps:
                    profile.snapshot('first_optimizer_step')
                import torch
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                profile.steps.append(time.perf_counter() - profile.step_start)
                check_resources(profile.config)
            def on_log(self, args, state, control, logs=None, **kwargs):
                if logs and 'loss' in logs:
                    profile.losses.append(logs['loss'])
        return [Callback()]

    def trainer_class(self, base):
        if not self.enabled:
            return base
        profile = self
        class ProfiledTrainer(base):
            def training_step(self, model, inputs, *args, **kwargs):
                # Counts nonpadding policy tokens incl. prompt; DPO chosen+rejected.
                if 'attention_mask' in inputs:
                    profile.tokens += int(inputs['attention_mask'].sum().item())
                elif 'prompt_attention_mask' in inputs:
                    profile.tokens += 2 * int(inputs['prompt_attention_mask'].sum().item())
                    profile.tokens += sum(int(inputs[key].sum().item()) for key in
                                          ('chosen_attention_mask', 'rejected_attention_mask'))
                loss = super().training_step(model, inputs, *args, **kwargs)
                if not profile.backward_seen:
                    profile.snapshot('first_backward')
                    profile.backward_seen = True
                return loss
        return ProfiledTrainer

    def finish(self, error=None):
        if not self.enabled:
            return
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=2)
        if self.hook:
            self.hook.remove()
        try:
            self.snapshot('end')
        except Exception:
            pass
        total_steps_time = sum(self.steps)
        report = {'stage': self.stage, 'error': str(error) if error else None,
                  'status': 'completed' if error is None and self.steps else 'failed_or_no_optimizer_step',
                  'total_seconds': time.perf_counter() - self.start,
                  'model_load_seconds': getattr(self, 'model_load_seconds', None),
                  'optimizer_steps': len(self.steps), 'step_seconds': self.steps,
                  'seconds_per_step': total_steps_time / len(self.steps) if self.steps else None,
                  'policy_tokens': self.tokens,
                  'policy_tokens_per_second': self.tokens / total_steps_time if total_steps_time else None,
                  'mean_logged_loss': sum(self.losses) / len(self.losses) if self.losses else None,
                  'system_minimum_available_bytes': self.minimum_available,
                  'events': self.events, 'config': self.config,
                  'notes': ['Step timing includes forward, backward, reference work and optimizer; excludes evaluation/save.',
                            'DPO token rate counts policy chosen+rejected input tokens, excludes reference tokens.',
                            'MemAvailable minimum sampled every second; CUDA peaks include evaluation after train begin.']}
        report['environment'] = {'architecture': platform.machine(), 'python': platform.python_version()}
        for package in ('torch', 'transformers', 'trl', 'peft', 'accelerate', 'datasets'):
            try:
                report['environment'][package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                report['environment'][package] = None
        path = Path(self.config.get('profiling', {}).get('output',
                    str(Path(self.config['training']['output_dir']) / 'memory_profile.json')))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        print(json.dumps({'profile_summary': {k: v for k, v in report.items() if k not in ('events', 'config')}}, ensure_ascii=False))
