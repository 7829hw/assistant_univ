"""CPU-only checks of explicitly approved v003 receipts and the prompt-retargeted export.

geoflow/sft-dpo-t2pc 적용: thor archive는 prompt 522aa3b1 기준이다. 현재 prompt(87048d0c)에서는 원래 복원이
``Production prompt drift``로 멈추는 것이 맞다. 아래 검사는 같은 archive를 ``training.data.retarget_prompt``로 현재 prompt에
다시 만든 레코드(라벨·split·metadata 동일)에 적용한다. thor 시점 production 파일 hash는 thor commit의 내용과 대조한다.
"""
import hashlib
import json
import shutil
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import yaml

from training.annotations.inventory import family_key
from training.annotations.workflow import decision_history
from training.data.build_dpo import dpo_pair
from training.data.build_sft import sft_record
from training.data.canonicalize import serialize_planner_target
from training.data.common import production_prompt, read_jsonl, sha256
from training.data.validation import assess, chosen_ok
from training.pilot import audit
from training.data.common import EXPECTED_PROMPT_SHA256
from training.data.retarget_prompt import retarget
from training.records.corpora.reviewed_gold_v003.assembly_recipe import (
    APPROVED_GOLD, APPROVED_PAIRS, DIAGNOSTIC, HOLD, restore_dataset_exports)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'training/records/corpora/reviewed_gold_v003'
REVIEW = ROOT / 'training/records/reviews/review_batch_003'
#: thor 브랜치 commit(가져온 출처). archive가 기록한 production 파일 hash는 이 commit의 내용과 대조한다.
THOR_REF = 'b3149040fb0fc57bedd1e8ff4436333f55d41e5a'
#: 이 브랜치로 가져오지 않은 snapshot(재구성에 필요 없는 pilot 실험 기록). 없는 것이 맞다.
EXCLUDED_SNAPSHOT_PREFIXES = ('pilots/',)


def git_sha256(name):
    import subprocess
    return hashlib.sha256(subprocess.check_output(['git', 'show', f'{THOR_REF}:{name}'], cwd=ROOT)).hexdigest()


class ReviewedGoldV003Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='geoflow_v003_test_')
        cls.export = Path(cls.temporary.name) / 'export'
        datasets, cls.flags, _, _ = retarget(CORPUS, 'reviewed_gold_v003_t2pc')
        cls.sft, cls.dpo = datasets['sft'], datasets['dpo']
        cls.rows = read_jsonl(REVIEW / 'review_queue.jsonl')
        cls.decisions = read_jsonl(REVIEW / 'decisions_003.jsonl')
        cls.by_id = {r['batch_item_id']: r for r in cls.decisions}
        cls.manifest = json.loads((CORPUS / 'corpus_manifest.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_explicit_approval_and_hold_diagnostic_receipts(self):
        self.assertEqual(len(decision_history(REVIEW / 'decisions_003.jsonl', self.rows)), 34)
        self.assertEqual(Counter(d['corpus_disposition'] for d in self.decisions),
                         {'accepted': 30, 'hold': 2, 'diagnostic_only': 2})
        for d in self.decisions:
            self.assertFalse(d['individual_human_record_inspection_claimed'])
            self.assertFalse(d['execution_tested'])
            if d['batch_item_id'] in APPROVED_GOLD | APPROVED_PAIRS:
                self.assertEqual(d['status'], 'accepted')
                self.assertTrue(all(d['checks'].values()))
            else:
                self.assertEqual(d['status'], 'needs_fix')
                self.assertFalse(any(d['checks'].values()))
        self.assertTrue(all(r['status'] == 'pending' for r in self.rows))

    def test_manifest_and_replay_hashes(self):
        for name, expected in self.manifest['output_hashes'].items():
            if name.startswith(('sft_', 'dpo_')) and name.endswith('.jsonl'):
                continue   # 522aa3b1 prompt 전문이 들어간 export. 아래에서 archive 대조로 대신한다
            self.assertEqual(sha256(CORPUS / name), expected, name)
        index = json.loads((CORPUS / 'dataset_index.json').read_text())
        current = production_prompt()
        for stage, datasets in (('sft', self.sft), ('dpo', self.dpo)):
            for split, rows in datasets.items():
                archived = index[f'{stage}_{split}']
                self.assertEqual(len(rows), len(archived))
                for row, original in zip(rows, archived):
                    original = json.loads(json.dumps(original))
                    (original['messages'] if stage == 'sft' else original['prompt'])[0]['content'] = current
                    self.assertEqual(row, original)
        with self.assertRaisesRegex(ValueError, 'Production prompt drift'):
            restore_dataset_exports(CORPUS, Path(self.temporary.name) / 'old_prompt_restore')
        self.assertEqual(sha256(REVIEW / 'decisions_003.jsonl'), self.manifest['decisions_003_hash'])
        self.assertEqual(sha256(REVIEW / 'decisions_003.jsonl'), sha256(CORPUS / 'decisions_003.jsonl'))
        self.assertEqual(self.manifest['branch'], 'geoflow/sft-dpo-thor')
        self.assertEqual(self.manifest['seed'], 42)
        self.assertEqual(self.manifest['prompt_hash'], '522aa3b1716248b53a755ee1b236e7aef302c85504e9cfac3825f4d3cc817945')
        self.assertEqual(hashlib.sha256(production_prompt().encode()).hexdigest(), EXPECTED_PROMPT_SHA256)

    def test_fixed_parent_prefix_and_reserved_splits(self):
        self.assertEqual([len(self.sft[s]) for s in ('train', 'valid')], [19, 16])
        self.assertEqual([len(self.dpo[s]) for s in ('train', 'valid')], [18, 14])
        old = yaml.safe_load((ROOT / 'training/records/corpora/reviewed_gold_v002/reviewed_annotations.yaml').read_text())
        golds = {r['id']: r for r in old['examples']}
        for split, count in [('train', 12), ('valid', 5)]:
            for row in self.sft[split][:count]:
                original = golds[row['metadata']['source_record_id']]
                self.assertEqual(row['messages'][1]['content'], original['question'])
                self.assertEqual(row['messages'][-1]['content'], serialize_planner_target(original['grounding']))
            self.assertTrue(all('RB003' not in str(r['metadata'].get('batch_item_ids', [])) for r in self.sft[split][:count]))
        plan = json.loads((REVIEW / 'split_plan.json').read_text())['candidate_splits']
        for stage in (self.sft, self.dpo):
            for split, group in stage.items():
                for row in group:
                    meta = row['metadata']
                    ids = [meta['batch_item_id']] if meta.get('batch_item_id', '').startswith('RB003') else meta.get('batch_item_ids', [])
                    for rid in ids:
                        if rid.startswith('RB003'):
                            self.assertEqual(plan[rid]['split'], split)

    def test_no_hold_or_diagnostic_export(self):
        gold_ids = {rid for group in self.sft.values() for row in group for rid in row['metadata'].get('batch_item_ids', [])}
        pair_ids = {row['metadata'].get('batch_item_id') for group in self.dpo.values() for row in group}
        self.assertTrue(APPROVED_GOLD <= gold_ids)
        self.assertTrue(APPROVED_PAIRS <= pair_ids)
        self.assertFalse((gold_ids | pair_ids) & (HOLD | DIAGNOSTIC))

    def test_all_gold_reuse_strict_builder_and_production_pipeline(self):
        annotations = yaml.safe_load((CORPUS / 'reviewed_annotations.yaml').read_text())['examples']
        self.assertEqual(len(annotations), 35)
        for annotation in annotations:
            generated = sft_record(annotation, source='verification-only', source_representation='flat')
            self.assertEqual(generated['messages'][-1]['content'], serialize_planner_target(annotation['grounding']))
            for normalize in (False, True):
                self.assertTrue(chosen_ok(assess(annotation['grounding'], annotation['question'], normalize=normalize)))

    def test_chosen_hashes_and_actual_approval_dependencies(self):
        by_question = {row['messages'][1]['content']: row for group in self.sft.values() for row in group}
        for group in self.dpo.values():
            for pair in group:
                gold = by_question[pair['prompt'][1]['content']]
                self.assertEqual(pair['prompt'], gold['messages'][:2])
                self.assertEqual(pair['chosen'][0]['content'], gold['messages'][-1]['content'])
                rid = pair['metadata'].get('batch_item_id', '')
                if rid in APPROVED_PAIRS:
                    details = pair['metadata']['negative_details']
                    self.assertEqual(details['chosen_target_sha256'], hashlib.sha256(pair['chosen'][0]['content'].encode()).hexdigest())
                    self.assertEqual(details['chosen_review_decision_hash'], gold['metadata']['review_decision_hash'])
                    dep = self.by_id[rid]['approval_dependency']
                    if dep:
                        self.assertEqual(self.by_id[dep]['status'], 'accepted')
                        self.assertEqual(self.by_id[rid]['approval_dependency_decision_hash'], self.by_id[dep]['decision_hash'])

    def test_dpo_builder_categories_and_distribution(self):
        for split, group in self.dpo.items():
            golds = {r['metadata']['source_record_id']: r for r in self.sft[split]}
            for pair in group:
                rebuilt = dpo_pair(golds[pair['metadata']['source_record_id']], json.loads(pair['rejected'][0]['content']),
                                   negative_type=pair['metadata']['negative_type'])
                self.assertEqual(rebuilt['metadata']['negative_category'], pair['metadata']['negative_category'])
        self.assertEqual(Counter(r['metadata']['negative_category'] for g in self.dpo.values() for r in g),
                         {'semantic': 21, 'constraint': 11})
        new = [r for g in self.dpo.values() for r in g if r['metadata'].get('batch_item_id') in APPROVED_PAIRS]
        self.assertEqual(Counter(r['metadata']['negative_category'] for r in new), {'semantic': 10, 'constraint': 2})

    def test_parent_semantic_and_preference_family_leakage(self):
        self.assertTrue(audit(self.sft, self.dpo)['passed'])
        keys = {s: {family_key(json.loads(r['messages'][-1]['content'])) for r in self.sft[s]} |
                {family_key(json.loads(r[k][0]['content'])) for r in self.dpo[s] for k in ('chosen', 'rejected')}
                for s in ('train', 'valid')}
        self.assertFalse(keys['train'] & keys['valid'])

    def test_new_independent_validation_coverage(self):
        coverage = json.loads((CORPUS / 'coverage_before_after.json').read_text())
        families = coverage['new_independent_validation_families']
        self.assertEqual(len(families), 5)
        self.assertEqual(len({fp for f in families for fp in f['fingerprints']}), 9)
        val = [r for r in self.sft['valid'] if r['metadata'].get('corpus_version') == 'reviewed_gold_v003']
        subtypes = {c['subtype'] for r in val for c in json.loads(r['messages'][-1]['content'])['concepts'] if c['role'] == 'MEASURE'}
        self.assertTrue({'fare', 'speed', 'rpm'} <= subtypes)

    def test_token_limit_blockers_preserved_with_exact_lengths(self):
        report = json.loads((CORPUS / 'token_validation.json').read_text())
        rows = read_jsonl(CORPUS / 'token_lengths.jsonl')
        blocked = {rid: r for r in rows if r['current_limit_failures'] for rid in r['batch_item_ids']}
        self.assertEqual(set(blocked), {f'RB003-{n}' for n in (13, 14, 15, 16, 17, 24, 30)})
        self.assertEqual({rid: r['total'] for rid, r in blocked.items()},
                         {'RB003-13': 6970, 'RB003-14': 6970, 'RB003-15': 6970, 'RB003-16': 6970,
                          'RB003-17': 6977, 'RB003-24': 6935, 'RB003-30': 6978})
        for row in rows:
            for key, count in row['actual_sequence_tokens_including_EOS'].items():
                self.assertEqual(row['guarded_totals'][key], count + 1)
        self.assertEqual(report['sft']['minimum_safe_limits_including_EOS_and_guard'], {'max_seq_length': 6977})
        self.assertEqual(report['dpo']['minimum_safe_limits_including_EOS_and_guard'],
                         {'max_length': 6978, 'max_prompt_length': 6789, 'max_completion_length': 188})
        self.assertFalse(report['config_changed'])
        self.assertFalse(report['GPU_used'])
        self.assertEqual(report['dropped_approved_samples'], 0)
        self.assertEqual(report['truncated_samples'], 0)

    def test_protection_witnesses_persist_and_original_records_unchanged(self):
        fingerprints = self.manifest['protection']['fingerprints']
        queue_by_id = {r['batch_item_id']: r for r in self.rows}
        for rid in DIAGNOSTIC:
            self.assertIn(family_key(queue_by_id[rid]['proposed_grounding']), fingerprints['families'])
        for pair in self.dpo['valid']:
            for key in ('chosen', 'rejected'):
                self.assertIn(family_key(json.loads(pair[key][0]['content'])), fingerprints['families'])
        original = json.loads((ROOT / 'training/records/snapshot_manifest.json').read_text())
        for entry in original['files']:
            path = ROOT / 'training/records' / entry['destination']
            if entry['destination'].startswith(EXCLUDED_SNAPSHOT_PREFIXES):
                self.assertFalse(path.exists(), entry['destination'])
                continue
            self.assertEqual(sha256(path), entry['sha256'])
        for name, expected in self.manifest['definition_hashes'].items():
            self.assertEqual(git_sha256(name), expected)
        for name, expected in self.manifest['source_files'].items():
            if '/configs/' in name or name.endswith('assembly_recipe.py'):
                path = ROOT / name
                if not path.exists() and name.startswith('training/annotations/generated/corpora/'):
                    # thor 장비의 ignored 생성 경로. 저장소에는 같은 파일이 records/corpora 아래에 커밋되어 있다.
                    path = ROOT / name.replace('training/annotations/generated/corpora/', 'training/records/corpora/')
                self.assertEqual(sha256(path), expected)

    def test_export_replay_refuses_overwrite_and_tamper(self):
        self.export.mkdir(parents=True, exist_ok=True)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            restore_dataset_exports(CORPUS, self.export)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source'
            shutil.copytree(CORPUS, source)
            index = json.loads((source / 'dataset_index.json').read_text())
            index['sft_train'][0]['messages'][0]['content']['production_prompt_sha256'] = 'incorrect'
            (source / 'dataset_index.json').write_text(json.dumps(index))
            with self.assertRaisesRegex(ValueError, 'Archive drift'):
                restore_dataset_exports(source, Path(folder) / 'output')
            self.assertFalse((Path(folder) / 'output').exists())


if __name__ == '__main__':
    unittest.main()
