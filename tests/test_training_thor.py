"""CPU-only Thor profile, memory guard, diagnostics and tokenizer checks."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import contextmanager

import yaml

from training.check_thor_env import cuda_tests, diagnose, system_memory
from training.data.analyze_tokens import analyze, statistics
from training.profiling import check_resources, validate_profile
from training.trainer_common import load_config, validate_lora_targets
from tests.test_training_data import record
from tests.test_training_trainers import PrefixTokenizer


ROOT = Path(__file__).resolve().parents[1]


class ThorTests(unittest.TestCase):
    def config(self, stage='sft', smoke=False):
        return load_config(ROOT / f'training/configs/qwen3_8b_thor_{"smoke_" if smoke else ""}{stage}.yaml', stage)

    def test_four_profiles_and_generic_unchanged(self):
        for stage in ('sft', 'dpo'):
            for smoke in (False, True):
                cfg = self.config(stage, smoke)
                self.assertFalse(cfg['model']['load_in_4bit'])
                self.assertTrue(cfg['training']['bf16'])
                self.assertEqual(cfg['training']['optim'], 'adamw_torch')
                self.assertEqual(cfg['lora']['r'], 16)
                self.assertEqual(len(cfg['model']['revision']), 40)
                if smoke:
                    self.assertEqual(cfg['training']['max_steps'], 2)
                    self.assertEqual(cfg['data']['max_valid_samples'], 1)
                    self.assertEqual(cfg['training']['eval_steps'], 2)
                    self.assertEqual(cfg['training']['save_strategy'], 'no')
        self.assertTrue(load_config(ROOT / 'training/configs/qwen_sft.yaml', 'sft')['model']['load_in_4bit'])

    def test_unsafe_unified_memory_baselines_fail(self):
        for section, key, value in (
            ('training', 'bf16', False), ('training', 'per_device_train_batch_size', 2),
            ('training', 'dataloader_num_workers', 8), ('training', 'dataloader_pin_memory', True),
            ('training', 'torch_compile', True), ('training', 'gradient_checkpointing', False),
            ('training', 'optim', 'paged_adamw_8bit'), ('model', 'attn_implementation', 'flash_attention_2'),
            ('model', 'load_in_4bit', True), ('safety', 'reserve_fraction', 0)):
            cfg = self.config(); cfg[section][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_profile(cfg, 'sft')

    def test_reserve_uses_real_total_not_fixed_128gb(self):
        cfg = self.config()
        cfg['safety']['reserve_gib'] = 1
        memory = {'total_bytes': 64 * 2**30, 'available_bytes': 32 * 2**30}
        with patch('training.profiling.system_memory', return_value=memory), \
             patch('training.profiling.shutil.disk_usage', return_value=SimpleNamespace(free=100 * 2**30)):
            self.assertEqual(check_resources(cfg)['reserve_bytes'], int(64 * 2**30 * .2))
            memory['available_bytes'] = 4 * 2**30
            with self.assertRaisesRegex(RuntimeError, 'reserve'):
                check_resources(cfg)

    def test_low_disk_and_unavailable_memory_fail(self):
        with patch('training.profiling.system_memory', return_value={'total_bytes': None, 'available_bytes': None}):
            with self.assertRaisesRegex(RuntimeError, 'Cannot read'):
                check_resources(self.config())
        with patch('training.profiling.shutil.disk_usage', return_value=SimpleNamespace(free=1)):
            with self.assertRaisesRegex(RuntimeError, 'disk'):
                check_resources(self.config())

    def test_matching_actual_module_names_required(self):
        model = SimpleNamespace(named_modules=lambda: [(name, None) for name in
                                ('', 'model.layers.0.q_proj', 'model.layers.1.q_proj', 'model.layers.0.v_proj')])
        self.assertEqual(validate_lora_targets(model, ['q_proj', 'v_proj']), {'q_proj': 2, 'v_proj': 1})
        with self.assertRaises(ValueError):
            validate_lora_targets(model, ['q_proj', 'bad_proj'])
        with self.assertRaises(ValueError):
            validate_lora_targets(model, [])

    def test_cpu_cuda_diagnostic_graceful(self):
        fake = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
        result = cuda_tests(fake, optional=True)
        self.assertEqual(result['bf16']['status'], 'FAIL')
        self.assertEqual(result['qlora']['status'], 'NOT TESTED')

    def test_missing_optional_cuda_extensions_report_failure(self):
        fake = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True, synchronize=lambda: None),
                               bfloat16=None, randn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError('test stub')))
        with patch.dict(sys.modules, {'bitsandbytes': None, 'flash_attn': None}):
            result = cuda_tests(fake, optional=True)
        self.assertEqual(result['bitsandbytes']['status'], 'FAIL')
        self.assertEqual(result['qlora']['status'], 'FAIL')
        self.assertIn('bitsandbytes', result['qlora']['error'])

    def test_missing_torch_diagnostic_graceful(self):
        with patch('training.check_thor_env.command', return_value={'status': 'NOT INSTALLED'}), \
             patch('training.check_thor_env.temperatures', return_value={}), \
             patch('training.check_thor_env.importlib.import_module', side_effect=ImportError('no optional dependencies')):
            report = diagnose(optional=True)
        self.assertEqual(report['bf16_lora'], 'FAIL')
        self.assertEqual(report['compatibility']['qlora']['status'], 'NOT TESTED')
        json.dumps(report)

    def test_token_analyzer_uses_full_generation_prompt_and_eos(self):
        tokenizer = PrefixTokenizer()
        cfg = self.config()
        row = record()
        result = analyze(tokenizer, [row], cfg, 'sft')
        self.assertGreater(result['lengths']['prompt']['max'], len(row['messages'][1]['content']))
        expected = len((row['messages'][-1]['content'] + tokenizer.eos_token).encode())
        self.assertEqual(result['lengths']['completion']['max'], expected)
        self.assertGreaterEqual(result['recommendation']['max_length'], result['lengths']['total']['max'])
        dpo = {'prompt': row['messages'][:2], 'chosen': [row['messages'][-1]],
               'rejected': [{'role': 'assistant', 'content': '{}'}]}
        result = analyze(tokenizer, [dpo], self.config('dpo'), 'dpo')
        self.assertGreater(result['lengths']['chosen']['max'], result['lengths']['rejected']['max'])

    def test_percentiles_nearest_rank(self):
        result = statistics(list(range(1, 101)))
        self.assertEqual((result['p50'], result['p95'], result['p99'], result['max']), (50, 95, 99, 100))
        self.assertEqual(statistics([]), {'samples': 0})

    def test_reference_strategies_and_objective_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'dpo.yaml'
            for strategy in ('shared_adapter', 'full', 'precompute'):
                cfg = self.config('dpo')
                cfg['reference']['strategy'] = strategy
                cfg['training'].pop('precompute_ref_log_probs')
                path.write_text(yaml.safe_dump(cfg))
                self.assertEqual(load_config(path, 'dpo')['reference']['strategy'], strategy)
            for key, value in (('reference_free', True), ('sync_ref_model', True)):
                cfg = self.config('dpo'); cfg['training'][key] = value
                path.write_text(yaml.safe_dump(cfg))
                with self.assertRaises(ValueError):
                    load_config(path, 'dpo')
            cfg = self.config('dpo'); cfg['reference']['strategy'] = 'precompute'
            path.write_text(yaml.safe_dump(cfg))
            with self.assertRaisesRegex(ValueError, 'conflicts'):
                load_config(path, 'dpo')

    def test_precompute_reference_uses_training_autocast(self):
        from training.train_dpo import consistent_reference_trainer
        events = []
        @contextmanager
        def autocast():
            events.append('enter')
            yield
            events.append('exit')
        class Base:
            def compute_ref_log_probs(self, batch):
                events.append('reference')
                return batch
        trainer = consistent_reference_trainer(Base)()
        trainer.accelerator = SimpleNamespace(autocast=autocast)
        trainer.precompute_ref_log_probs = True
        self.assertEqual(trainer.compute_ref_log_probs('logps'), 'logps')
        self.assertEqual(events, ['enter', 'reference', 'exit'])
        events.clear(); trainer.precompute_ref_log_probs = False
        trainer.compute_ref_log_probs('logps')
        self.assertEqual(events, ['reference'])

    @unittest.skipUnless(os.environ.get('GEOFLOW_RUN_GPU_TESTS') == '1', 'Opt-in CUDA operation test')
    def test_actual_bf16_sdpa_backward(self):
        import torch
        if not torch.cuda.is_available():
            self.skipTest('CUDA unavailable')
        report = cuda_tests(torch)
        self.assertEqual(report['bf16']['status'], 'PASS', report)
        self.assertEqual(report['sdpa']['status'], 'PASS', report)

    @unittest.skipUnless(os.environ.get('GEOFLOW_RUN_GPU_TESTS') == '1', 'Opt-in torch/PEFT adapter precision test')
    def test_dual_adapter_preserves_sft_fp32_precision(self):
        import torch
        from peft import LoraConfig, PeftModel, get_peft_model
        from transformers import Qwen3Config, Qwen3ForCausalLM
        from training.train_dpo import adapter_digest, initialize_reference_adapter
        spec = Qwen3Config(vocab_size=32, hidden_size=16, intermediate_size=32,
                          num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=1, head_dim=8)
        make = lambda: Qwen3ForCausalLM(spec).to(dtype=torch.bfloat16)
        with tempfile.TemporaryDirectory() as directory:
            model = get_peft_model(make(), LoraConfig(task_type='CAUSAL_LM', r=2, target_modules=['q_proj']))
            with torch.no_grad():
                for name, parameter in model.named_parameters():
                    if 'lora_' in name:
                        parameter.fill_(0.123456789)  # cannot roundtrip through BF16 exactly
            expected = adapter_digest(model, 'default')
            model.save_pretrained(directory)
            loaded = PeftModel.from_pretrained(make(), directory, is_trainable=True, adapter_name='policy')
            self.assertEqual(initialize_reference_adapter(loaded, directory), expected)
            self.assertEqual(adapter_digest(loaded, 'policy'), expected)
            self.assertFalse(any(p.requires_grad for name, p in loaded.named_parameters() if '.reference.' in name))


if __name__ == '__main__':
    unittest.main()
