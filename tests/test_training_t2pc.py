"""geoflow/sft-dpo-t2pc의 thor 학습 패키지 적용 부분(prompt 87048d0c, 조건 계층 판정, token 한도). CPU only."""
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

import geoflow.aggregation as production_aggregation
from geoflow.aggregation import from_flat
from training.data import common
from training.data.aggregation_flat import to_flat
from training.data.retarget_prompt import retarget
from training.data.validation import assess, assess_t2pc, chosen_ok, t2pc_chosen_ok

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / 'training/records/corpora/reviewed_gold_v003_t2pc'


def _measure(subtype='revenue'):
    return {'id': 'm', 'concept': 'AMOUNT', 'subtype': subtype, 'role': 'MEASURE', 'source': 'implicit'}


def _support(subtype='operation'):
    return {'id': 'e', 'concept': 'EVENT', 'subtype': subtype, 'role': 'SUPPORT', 'source': 'implicit'}


class ExpectedPromptTest(unittest.TestCase):
    def test_current_prompt_is_the_expected_t2pc_prompt(self):
        current = hashlib.sha256(common.production_prompt().encode()).hexdigest()
        self.assertEqual(current, common.EXPECTED_PROMPT_SHA256)
        self.assertEqual(common.check_expected_prompt(), current)

    def test_prompt_drift_is_refused(self):
        with patch.object(common, 'production_prompt', return_value='different prompt'):
            with self.assertRaisesRegex(ValueError, 'differs from expected'):
                common.check_expected_prompt()


class TrainingSideFlatTest(unittest.TestCase):
    def test_to_flat_lives_outside_production_aggregation(self):
        self.assertFalse(hasattr(production_aggregation, 'to_flat'))
        flat = {'aggregation': 'sum', 'bucket': 'week', 'rollup': 'min'}
        self.assertEqual(to_flat(from_flat(flat)), flat)


class T2PCAssessTest(unittest.TestCase):
    def test_condition_layer_fill_is_reported_as_meaning_change(self):
        payload = {'concepts': [_measure(), _support()], 'factors': {'date': 'last_month', 'aggregation': 'avg'}}
        question = '지난달 법인택시 평균 매출은?'
        self.assertTrue(chosen_ok(assess(payload, question)))
        result = assess_t2pc(payload, question)
        self.assertTrue(t2pc_chosen_ok(result))
        self.assertTrue(result['condition_changed_meaning'])
        self.assertEqual(result['condition_actions']['taxi_type']['value'], 'corporate')

    def test_compile_stop_is_not_a_contract_failure(self):
        # v003 gold 가운데 compile에서 멈추는 첫 레코드(주·월 구간 + rollup).
        flags = json.loads((RECORDS / 'review_flags.json').read_text())['sft']
        flagged = next(f for f in flags if any(m.startswith('compile_stop:') for m in f['marks']))
        index = json.loads((ROOT / 'training/records/corpora/reviewed_gold_v003/dataset_index.json').read_text())
        record = index[f"sft_{flagged['split']}"][flagged['position']]
        payload = json.loads(record['messages'][-1]['content'])
        result = assess_t2pc(payload, record['messages'][1]['content'])
        self.assertIn('bucket', payload['factors'])
        self.assertTrue(t2pc_chosen_ok(result))
        self.assertFalse(result['compile_ok'])
        self.assertEqual(result['compile_error_code'], 'UNVERIFIED_TIMS_CONTRACT')

    def test_unsupported_target(self):
        self.assertTrue(t2pc_chosen_ok(assess_t2pc({'unsupported': True}, '아무 질문')))


class RetargetedV003Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.datasets, cls.flags, cls.corpus, cls.prompt_hash = retarget(
            ROOT / 'training/records/corpora/reviewed_gold_v003', 'reviewed_gold_v003_t2pc')

    def test_counts_and_prompt(self):
        self.assertEqual(self.prompt_hash, common.EXPECTED_PROMPT_SHA256)
        self.assertEqual({f'{s}_{p}': len(self.datasets[s][p]) for s in ('sft', 'dpo') for p in ('train', 'valid')},
                         {'sft_train': 19, 'sft_valid': 16, 'dpo_train': 18, 'dpo_valid': 14})
        for stage in ('sft', 'dpo'):
            for rows in self.datasets[stage].values():
                for row in rows:
                    messages = row['messages'] if stage == 'sft' else row['prompt']
                    self.assertEqual(messages[0]['content'], common.production_prompt())

    def test_inventory_findings_are_marked_not_removed(self):
        sft_marks = [m for f in self.flags['sft'] for m in f['marks']]
        dpo_marks = [m for f in self.flags['dpo'] for m in f['marks']]
        self.assertEqual(sum(m.startswith('compile_stop:') for m in sft_marks), 17)
        self.assertEqual(dpo_marks.count('t2pc_rejected_equals_chosen'), 3)
        self.assertEqual(dpo_marks.count('t2pc_constraint_rejected_passes_contract'), 1)
        self.assertNotIn('t2pc_contract_failure', sft_marks)
        self.assertTrue(all(f['thor_assess_reproduced'] for f in self.flags['sft']))

    def test_committed_flags_match_regeneration(self):
        committed = json.loads((RECORDS / 'review_flags.json').read_text())
        self.assertEqual(committed['sft'], json.loads(json.dumps(self.flags['sft'], ensure_ascii=False)))
        self.assertEqual(committed['dpo'], json.loads(json.dumps(self.flags['dpo'], ensure_ascii=False)))


class T2PCConfigTest(unittest.TestCase):
    def test_limits_cover_measured_lengths(self):
        sft = yaml.safe_load((ROOT / 'training/configs/qwen3_8b_t2pc_v003_sft.yaml').read_text())
        dpo = yaml.safe_load((ROOT / 'training/configs/qwen3_8b_t2pc_v003_dpo.yaml').read_text())
        lengths = {stage: json.loads((RECORDS / f'token_lengths_{stage}.json').read_text())['lengths']
                   for stage in ('sft', 'dpo')}
        self.assertGreaterEqual(sft['training']['max_seq_length'], lengths['sft']['total']['max'])
        self.assertGreaterEqual(sft['training']['max_seq_length'], 7519)
        self.assertGreaterEqual(dpo['training']['max_length'], max(lengths['dpo']['total']['max'], 7520))
        self.assertGreaterEqual(dpo['training']['max_prompt_length'], max(lengths['dpo']['prompt']['max'], 7331))
        self.assertGreaterEqual(dpo['training']['max_completion_length'],
                                max(lengths['dpo']['chosen']['max'], lengths['dpo']['rejected']['max']))
        for config in (sft, dpo):
            self.assertIn('reviewed_gold_v003_t2pc', config['data']['manifest'])
            self.assertFalse(config['safety']['unified_memory'])
            self.assertEqual(config['chat_template_kwargs'], {'enable_thinking': False})
            self.assertEqual(config['model']['revision'], 'b968826d9c46dd6066d109eabc6255188de91218')


if __name__ == '__main__':
    unittest.main()
