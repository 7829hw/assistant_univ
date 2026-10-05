"""CPU regressions for v003 limits and disposable smoke fixture selection."""
import copy
import json
import unittest
from pathlib import Path

from training.trainer_common import load_config
from training.v003_token_smoke import LIMITS, select_records

ROOT = Path(__file__).resolve().parents[1]


class V003TokenLimitTests(unittest.TestCase):
    def test_limits_fit_all_measured_guarded_lengths(self):
        report = json.loads((ROOT / 'training/records/corpora/reviewed_gold_v003/token_validation.json').read_text())
        self.assertGreaterEqual(LIMITS['sft']['max_seq_length'], report['sft']['lengths']['total']['max'])
        for key, measured in [('max_length', 'total'), ('max_prompt_length', 'prompt')]:
            self.assertGreaterEqual(LIMITS['dpo'][key], report['dpo']['lengths'][measured]['max'])
        self.assertEqual(LIMITS['sft']['max_seq_length'], 7040)
        self.assertEqual(LIMITS['dpo'], {'max_length': 7040, 'max_prompt_length': 6816, 'max_completion_length': 256})

    def test_same_train_control_and_independent_longest_fixture(self):
        records = {'train': [{'id': 'short'}, {'id': 'overflow'}, {'id': 'fit'}], 'valid': [{'id': 'longest'}]}
        lengths = [{'split': 'train', 'total': 6800, 'current_limit_failures': []},
                   {'split': 'train', 'total': 6970, 'current_limit_failures': ['total_limit']},
                   {'split': 'train', 'total': 6912, 'current_limit_failures': []},
                   {'split': 'valid', 'total': 6977, 'current_limit_failures': ['total_limit']}]
        original = copy.deepcopy(records)
        selected = select_records(records, lengths)
        self.assertEqual(selected['control_old'][0]['id'], 'fit')
        self.assertIs(selected['control_old'], selected['control_new'])
        self.assertEqual(selected['long_new'][0]['id'], 'longest')
        self.assertEqual(selected['long_new'][1]['split'], 'valid')
        self.assertEqual(records, original)

    def test_no_eligible_training_control_fails(self):
        with self.assertRaisesRegex(ValueError, 'No fitting training control'):
            select_records({'train': [], 'valid': [{'id': 'valid'}]},
                           [{'split': 'valid', 'total': 6800, 'current_limit_failures': []}])

    def test_old_profiles_are_not_raised(self):
        for stage in ('sft', 'dpo'):
            cfg = load_config(ROOT / f'training/configs/qwen3_8b_thor_{stage}.yaml', stage)
            self.assertEqual(cfg['training']['max_seq_length' if stage == 'sft' else 'max_length'], 6912)
            if stage == 'dpo':
                self.assertEqual(cfg['training']['max_prompt_length'], 6784)

    def test_new_pilot_profiles_preserve_thor_objective_and_bounds(self):
        for stage in ('sft', 'dpo'):
            cfg = load_config(ROOT / f'training/configs/qwen3_8b_thor_pilot_003_{stage}.yaml', stage)
            for key, value in LIMITS[stage].items():
                self.assertEqual(cfg['training'][key], value)
            self.assertTrue(cfg['training']['bf16'])
            self.assertTrue(cfg['training']['gradient_checkpointing'])
            self.assertEqual(cfg['training']['optim'], 'adamw_torch')
            self.assertEqual(cfg['model']['attn_implementation'], 'sdpa')
            self.assertEqual(cfg['lora']['r'], 16)
            self.assertFalse(cfg['model']['load_in_4bit'])
            self.assertLessEqual(cfg['training']['max_steps'], 12)
            self.assertIn('reviewed_gold_v003', cfg['data']['manifest'])
            if stage == 'sft':
                self.assertNotIn('adapter_path', cfg['model'])
            else:
                self.assertEqual(cfg['reference']['strategy'], 'shared_adapter')
                self.assertEqual(cfg['model']['adapter_path'], 'SELECTED_V003_SFT_REQUIRED')
                self.assertFalse(cfg['training'].get('reference_free', False))

    def test_committed_smoke_evidence_includes_longest_without_learning(self):
        directory = ROOT / 'training/records/validation/thor_v003_token_smoke_002'
        report = json.loads((directory / 'RESULTS.json').read_text())
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['token_overflow_count'], 0)
        self.assertEqual(report['token_truncation_count'], 0)
        for stage in ('sft', 'dpo'):
            for case in ('control_old', 'control_new', 'long_new'):
                row = json.loads((directory / 'metrics' / f'{stage}_{case}_evidence.json').read_text())
                self.assertEqual(row['status'], 'PASS')
                self.assertEqual(row['global_step'], 2)
                self.assertEqual(row['learning_rate'], 0)
                self.assertEqual(row['initial_policy_hash'], row['final_policy_hash'])
                self.assertFalse(row['OOM'])
                self.assertFalse(row['corpus_split_changed'])
                self.assertTrue(all(e['finite_gradients'] and e['finite_adamw_state'] for e in row['optimizer_evidence']))
        sft = json.loads((directory / 'metrics/sft_long_new_evidence.json').read_text())
        dpo = json.loads((directory / 'metrics/dpo_long_new_evidence.json').read_text())
        self.assertEqual(sft['actual_trl_lengths']['input_ids'], 6976)
        self.assertEqual(dpo['actual_trl_lengths'], {'prompt': 6789, 'chosen': 187, 'rejected': 188})


if __name__ == '__main__':
    unittest.main()
