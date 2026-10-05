"""CPU checks of the batch 003 decision draft; these checks grant no approvals."""
import copy
import json
import unittest
from collections import Counter
from pathlib import Path

import yaml

from geoflow.grounding import parse_grounding
from training.annotations.inventory import family_key
from training.data.canonicalize import semantic_key
from training.data.common import read_jsonl, sha256
from training.data.validation import assess, chosen_ok

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'training/records/reviews/review_batch_003'


class ReviewDecisions003Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_jsonl(DIRECTORY / 'decisions_draft_003.jsonl')
        cls.by_id = {r['batch_item_id']: r for r in cls.rows}
        cls.queue = {r['batch_item_id']: r for r in read_jsonl(DIRECTORY / 'review_queue.jsonl')}

    def test_draft_never_approves_or_changes_pending_status(self):
        self.assertEqual(len(self.by_id), 34)
        self.assertEqual(Counter(r['recommendation'] for r in self.rows),
                         {'accepted': 30, 'needs_fix': 2, 'diagnostic_only': 2})
        for row in self.rows:
            self.assertTrue(row['draft_only'])
            self.assertFalse(row['approval_granted'])
            self.assertEqual(row['actual_queue_status'], 'pending')
            self.assertEqual(self.queue[row['batch_item_id']]['status'], 'pending')
        self.assertFalse((DIRECTORY / 'decisions.jsonl').exists())

    def test_original_candidates_and_predictions_remain_exact(self):
        for row in self.rows:
            original = self.queue[row['batch_item_id']]
            for field in ('candidate_id', 'candidate_hash', 'question', 'planned_split',
                          'semantic_family', 'contrast_group', 'proposed_grounding', 'proposed_rejected'):
                self.assertEqual(row[field], original[field])
            self.assertEqual(row['actual_predictions'], original['predictions'])
            self.assertEqual(row['family_fingerprint'], family_key(row['proposed_grounding']))
        snapshot = json.loads((ROOT / 'training/records/snapshot_manifest.json').read_text())
        for entry in snapshot['files']:
            self.assertEqual(sha256(ROOT / 'training/records' / entry['destination']), entry['sha256'])

    def test_manual_tool_text_lineage_overrides_automatic_no_match(self):
        for identifier in ('RB003-01', 'RB003-02'):
            row = self.by_id[identifier]
            self.assertEqual(row['recommendation'], 'diagnostic_only')
            self.assertTrue(row['lineage']['manual_conflict'])
            self.assertEqual(row['lineage']['automatic_reasons'], [])
            matches = row['lineage']['manual_matches']
            self.assertEqual({r['record_id'] for r in matches}, {'n31', 'k06'})
            for match in matches:
                self.assertEqual(sha256(ROOT / match['source']), match['source_sha256'])
                self.assertIn('metric=rpm', match['gold_text'])
                self.assertIn('aggregation=avg', match['gold_text'])
                self.assertNotIn('bucket=', match['gold_text'])
            self.assertIsNone(row['corrected_grounding'])

    def test_all_proposed_chosen_reuse_strict_production_pipeline(self):
        for row in self.rows:
            result = assess(row['proposed_grounding'], row['question'], normalize=False)
            self.assertTrue(chosen_ok(result), row['batch_item_id'])
            self.assertEqual(result['validation_codes'], [])

    def test_legacy_predictions_are_held_not_pure_semantic(self):
        for identifier in ('RB003-21', 'RB003-22'):
            row = self.by_id[identifier]
            self.assertEqual(row['recommendation'], 'needs_fix')
            negative = row['negative_assessment']
            self.assertEqual(negative['strict_raw']['error_code'], 'INVALID_SUBTYPE')
            self.assertTrue(negative['production']['validation_ok'])
            self.assertTrue(negative['normalized_query_conditions_and_statistic_equivalent'])
            self.assertFalse(negative['pure_query_semantic_negative_confirmed'])
            self.assertIsNone(negative['recommended_category'])
            correction = row['corrected_pair']
            self.assertEqual(correction['chosen'], row['proposed_grounding'])
            self.assertEqual(correction['rejected'], row['proposed_rejected'])
            self.assertEqual(correction['negative_category'], 'constraint')
            self.assertTrue(correction['requires_human_policy_decision'])
            chosen = parse_grounding(row['proposed_grounding'], row['question'])
            rejected = parse_grounding(row['proposed_rejected'], row['question'])
            self.assertEqual(chosen.factors, rejected.factors)
            self.assertEqual([c.value for c in chosen.concepts if c.subtype == 'place'],
                             [c.value for c in rejected.concepts if c.subtype == 'place'])

    def test_actual_constraint_failures_preserve_distinct_causes(self):
        self.assertEqual(self.by_id['RB003-23']['negative_assessment']['production']['error_code'],
                         'UNGROUNDED_SCOPE')
        self.assertEqual(self.by_id['RB003-24']['negative_assessment']['production']['error_code'],
                         'UNUSED_CONCEPT')
        for identifier in ('RB003-23', 'RB003-24'):
            self.assertEqual(self.by_id[identifier]['negative_assessment']['recommended_category'], 'constraint')
            self.assertFalse(self.by_id[identifier]['negative_assessment']['pure_query_semantic_negative_confirmed'])
            self.assertTrue(all(e['split'] == 'train'
                                for e in self.by_id[identifier]['actual_negative_evidence']))

    def test_pair_chosen_dependencies_are_real_and_not_auto_approved(self):
        approved_source = yaml.safe_load((ROOT / 'training/records/corpora/reviewed_gold_v002/'
                                         'reviewed_annotations.yaml').read_text())
        approved_gold = {r['id']: r['grounding'] for r in approved_source['examples']}
        for row in self.rows:
            if row['record_type'] != 'dpo_pair':
                continue
            self.assertNotEqual(semantic_key(row['proposed_grounding'], infer_events=True),
                                semantic_key(row['proposed_rejected'], infer_events=True))
            dependency = row['chosen_approval_dependency']
            if dependency:
                chosen = self.by_id[dependency]
                self.assertEqual(row['question'], chosen['question'])
                self.assertEqual(row['proposed_grounding'], chosen['proposed_grounding'])
                self.assertEqual(row['planned_split'], chosen['planned_split'])
                self.assertFalse(chosen['approval_granted'])
            else:
                self.assertEqual(row['chosen_trust']['level'], 'reviewed_gold_v002_train')
                self.assertEqual(semantic_key(row['proposed_grounding']),
                                 semantic_key(approved_gold[row['chosen_trust']['source_record_id']]))

    def test_source_role_value_controls_are_annotation_semantics(self):
        for identifier in ('RB003-27', 'RB003-28', 'RB003-29'):
            row = self.by_id[identifier]
            self.assertEqual(row['negative_assessment']['error_scope'], 'canonical_annotation_source_role_value')
            self.assertTrue(row['negative_assessment']['strict_raw']['validation_ok'])
        chosen = self.by_id['RB003-12']['proposed_grounding']
        for identifier, field, value in [('RB003-27', 'source', 'implicit'), ('RB003-28', 'role', 'COND')]:
            expected = copy.deepcopy(chosen)
            next(c for c in expected['concepts'] if c['subtype'] == 'place')[field] = value
            self.assertEqual(expected, self.by_id[identifier]['proposed_rejected'])
        expected = copy.deepcopy(chosen)
        next(c for c in expected['concepts'] if c['role'] == 'MEASURE').update(source='user', value=42)
        self.assertEqual(expected, self.by_id['RB003-29']['proposed_rejected'])

    def test_independent_groups_and_rare_validation_survive_exclusions(self):
        accepted = [r for r in self.rows if r['recommendation'] == 'accepted']
        for key in ('contrast_group', 'semantic_family', 'family_fingerprint'):
            self.assertFalse({r[key] for r in accepted if r['planned_split'] == 'train'} &
                             {r[key] for r in accepted if r['planned_split'] == 'valid'})
        for subtype in ('fare', 'speed', 'rpm'):
            for split in ('train', 'valid'):
                self.assertTrue(any(r['record_type'] == 'sft_gold' and r['planned_split'] == split and
                                    r['statistical_definition']['measure'] == subtype for r in accepted))
        self.assertEqual(self.by_id['RB003-09']['statistical_definition']['measure'], 'rpm')
        groups = {r['contrast_group'] for r in accepted if r['record_type'] == 'sft_gold'
                  and r['planned_split'] == 'valid'}
        self.assertEqual(len(groups), 5)

    def test_date_od_and_return_target_are_separate(self):
        self.assertEqual(self.by_id['RB003-04']['proposed_grounding']['factors']['date'], '20260706-20260830')
        for row in self.rows:
            self.assertFalse(any(c.get('value') == {'date': row['statistical_definition']['date_factor']}
                                 for c in row['proposed_grounding']['concepts']))
        self.assertEqual({self.by_id[f'RB003-{n}']['proposed_grounding']['factors']['dimension_target']
                          for n in (15, 16, 17)}, {'pickup', 'dropoff', 'both'})
        for n in (15, 16, 17):
            self.assertEqual({c['attributes']['od_role'] for c in self.by_id[f'RB003-{n}']['proposed_grounding']['concepts']
                              if c['concept'] == 'LOCATION'}, {'pickup', 'dropoff'})
        self.assertIn('REDUCE_GROUPS', self.by_id['RB003-19']['chosen_quality']['strict_raw']['operators'])
        self.assertIn('SELECT_GROUP', self.by_id['RB003-20']['chosen_quality']['strict_raw']['operators'])

    def test_token_gates_are_not_approval_or_semantic_rejection(self):
        exceeded = {r['batch_item_id'] for r in self.rows if not r['token_budget']['current_pilot_002_limits_pass']}
        self.assertEqual(exceeded, {f'RB003-{n}' for n in (13, 14, 15, 16, 17, 24, 30)})
        for row in self.rows:
            self.assertTrue(row['token_budget']['not_a_semantic_rejection'])
            self.assertFalse(row['token_budget']['config_changed'])
            self.assertFalse(row['token_budget']['truncation_performed'])
            self.assertEqual(row['token_budget']['current_total_limit'], 6912)
            self.assertFalse(row['execution_tested_this_review'])

    def test_conditional_corpus_counts_and_pair_distribution(self):
        accepted = [r for r in self.rows if r['recommendation'] == 'accepted']
        counts = Counter((r['record_type'], r['planned_split']) for r in accepted)
        self.assertEqual((12 + counts['sft_gold', 'train'], 5 + counts['sft_gold', 'valid']), (19, 16))
        self.assertEqual((16 + counts['dpo_pair', 'train'], 4 + counts['dpo_pair', 'valid']), (18, 14))
        pairs = [r for r in accepted if r['record_type'] == 'dpo_pair']
        self.assertEqual(Counter(r['negative_assessment']['recommended_category'] for r in pairs),
                         {'semantic': 10, 'constraint': 2})
        self.assertEqual(sum(r['planned_split'] == 'valid' for r in pairs), 10)


if __name__ == '__main__':
    unittest.main()
