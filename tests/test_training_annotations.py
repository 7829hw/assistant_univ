"""Human review gates and leakage policies run without GPU/training packages."""
import copy
import io
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

import yaml

from training.annotations.candidates import (blueprints, failure_driven_candidates, failure_hints,
                                             measure_payload, mine_predictions, proposal, semantic_negative_candidates)
from training.annotations.inventory import Protection, digest, family_key, inventory
from training.annotations.workflow import (decide, decision_history, import_reviewed, load_queue,
                                          prepare, save_json, seal, write_xlsx)
from training.data.canonicalize import serialize_planner_target
from training.data.common import provenance, read_jsonl, sha256, write_jsonl
from training.data.split import check_split, question_key
from training.data.validation import assess


def candidate(subtype='rpm', family='rpm', question='솔빛동 택시의 평균 엔진 회전수는?'):
    payload = measure_payload('AMOUNT', subtype, {'aggregation': 'avg'}, [('솔빛동', None)])
    return proposal(question, payload, 'rare_measure', family, 'Human must verify metric definition')


class InventoryTest(unittest.TestCase):
    def test_family_ignores_location_date_source_and_roles_but_keeps_stages_od(self):
        a = candidate()['proposed_grounding']
        b = copy.deepcopy(a)
        b['factors']['date'] = 'last_month'
        b['concepts'][0]['source'] = 'user'
        b['concepts'][0]['role'] = 'SUPPORT'
        b['concepts'][-1]['value'] = {'name': '다른동', 'region': ''}
        self.assertEqual(family_key(a), family_key(b))
        b['factors'].update(bucket='week', rollup='max')
        self.assertNotEqual(family_key(a), family_key(b))
        b = copy.deepcopy(a)
        b['concepts'][-1]['attributes'] = {'od_role': 'pickup'}
        self.assertNotEqual(family_key(a), family_key(b))
        self.assertEqual(family_key({'unsupported': True}), 'unsupported')

    def test_protected_paraphrases_locations_families_and_ids(self):
        p = Protection()
        a = candidate()
        p.add(a['question'], a['proposed_grounding'], ['known-parent'])
        self.assertIn('protected_question', p.reasons('솔빛동 택시의 평균 엔진 회전수는 !', a['proposed_grounding']))
        self.assertIn('protected_semantic_family', p.reasons('다른 지역 다른 날짜 RPM 평균', a['proposed_grounding']))
        self.assertIn('protected_parent_or_family', p.reasons('새 질문', None, ['known-parent']))
        self.assertEqual(p.reasons('새 질문', candidate('speed')['proposed_grounding']), [])

    def test_reserved_aggregation_expansion_and_validation_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = candidate()['proposed_grounding']
            payload['factors'].pop('aggregation')
            doc = {'intents': [{'intent': 'dev-rpm', 'golden': payload,
                               'aggregation': {'bucket': 'week', 'inner': 'avg', 'final': 'max'},
                               'paraphrases': [{'id': 'dev1', 'question': 'dev question'}]}]}
            path = root / 'dev.yaml'
            path.write_text(yaml.safe_dump(doc))
            valid = {'messages': [{'content': ''}, {'content': 'valid question'},
                                   {'content': serialize_planner_target(candidate()['proposed_grounding'])}],
                     'metadata': {'source_record_id': 'v1', 'parent_intent': 'valid-family'}}
            write_jsonl(root / 'sft_valid.jsonl', [valid])
            with patch('training.annotations.inventory.reserved_sources', return_value={path}):
                p = Protection.current(root)
            self.assertIn(question_key('dev question'), p.questions)
            self.assertIn('valid-family', p.ids)
            full = copy.deepcopy(payload)
            full['factors'].update(bucket='week', aggregation='avg', rollup='max')
            self.assertIn(family_key(full), p.families)
            self.assertEqual(p.issues, [])

    def test_inventory_reports_zero_measures_and_unreviewed_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = {'messages': [{'content': ''}, {'content': candidate()['question']},
                                 {'content': serialize_planner_target(candidate()['proposed_grounding'])}],
                   'metadata': {'source_record_id': 't1', 'parent_intent': 'rpm'}}
            grouped = copy.deepcopy(row)
            grouped['messages'][-1]['content'] = serialize_planner_target(
                measure_payload('AMOUNT', 'revenue', {'dimension': 'sigungu'}))
            grouped['metadata']['source_record_id'] = 't2'
            write_jsonl(root / 'sft_train.jsonl', [row, grouped])
            for name in ('sft_valid', 'dpo_train', 'dpo_valid'):
                write_jsonl(root / f'{name}.jsonl', [])
            source = root / 'gold.yaml'
            source.write_text(yaml.safe_dump({'examples': [{'id': 't1', 'reviewed_by': '사용자 검토 전'}]}, allow_unicode=True))
            report = inventory(root, source)
            self.assertEqual(report['measure_inventory']['AMOUNT/rpm'], 1)
            self.assertEqual(report['measure_inventory']['AMOUNT/fare'], 0)
            self.assertEqual(report['human_review_pending'], 1)
            self.assertIn('od_scope', {g['type'] for g in report['gaps']})
            self.assertTrue(report['dimensions'])
            self.assertEqual(report['od_dimension_sample_count'], 0)
            self.assertIn('od_dimension', {g['type'] for g in report['gaps']})

    def test_historical_validation_families_survive_corpus_version_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = Protection()
            a = candidate()
            old.add(a['question'], a['proposed_grounding'], ['old-valid-parent'])
            # The old dataset may be archived elsewhere. Its protected semantic
            # fingerprints are carried in the next version, not released.
            save_json(root / 'corpus_manifest.json', {'protection': old.manifest()})
            write_jsonl(root / 'sft_valid.jsonl', [])
            with patch('training.annotations.inventory.reserved_sources', return_value=set()), \
                 patch('training.annotations.inventory.ROOT', root):
                current = Protection.current(root)
            self.assertIn('protected_question', current.reasons(a['question'], a['proposed_grounding']))
            self.assertIn('protected_parent_or_family', current.reasons('different wording', None, ['old-valid-parent']))
            self.assertIn('protected_semantic_family', current.reasons('different place/date', a['proposed_grounding']))


class CandidateTest(unittest.TestCase):
    def test_bounded_blueprints_never_become_gold(self):
        from training.data.build_sft import sft_record
        rows = blueprints()
        self.assertEqual(rows, blueprints())
        self.assertEqual(len(rows), 26)
        for row in rows:
            self.assertEqual(row['status'], 'pending')
            self.assertEqual(row['semantic_correctness'], 'unreviewed')
            if row['expected_outcome'] == 'answered':
                self.assertTrue(row['quality']['validation_ok'], row['question'])
                # Check the stricter gold path as well: no silent normalization.
                sft_record({'id': row['candidate_id'], 'question': row['question'],
                            'grounding': row['proposed_grounding']}, source='proposal_only', source_representation='flat')
            elif row['expected_outcome'] == 'needs_clarification':
                self.assertEqual(row['quality']['error_code'], 'AMBIGUOUS_INNER_AGGREGATION')

    def test_only_observed_failures_or_missing_coverage_trigger_generation(self):
        report = {'measure_inventory': {f"{c['concept']}/{c['subtype']}": 10
                                        for r in blueprints() for c in r['proposed_grounding'].get('concepts', [])},
                  'od_roles': {'pickup': 10}, 'dimensions': {'emd': 10}, 'od_dimensions': {'emd:both': 10}}
        self.assertEqual(failure_driven_candidates(report, []), [])
        failures = [{'failure_hints': ['aggregation_stage'], 'evidence': []}]
        rows = failure_driven_candidates(report, failures)
        self.assertEqual({r['candidate_type'] for r in rows}, {'aggregation_stage', 'ambiguity_boundary'})
        self.assertTrue(all(r['generation_trigger']['pilot_failure_candidates'] == 1 for r in rows))

    def test_stage_and_od_contrasts_still_require_semantic_review_despite_validity(self):
        rows = semantic_negative_candidates(blueprints(), seed=17)
        self.assertEqual(rows, semantic_negative_candidates(blueprints(), seed=17))
        self.assertEqual(len(rows), 11)
        self.assertTrue(all(r['status'] == 'pending' and r['negative_category'] == 'semantic' for r in rows))
        self.assertTrue(all(r['quality']['validation_ok'] and r['rejected_quality']['validation_ok'] for r in rows))
        stage = next(r for r in rows if r['negative_type'] == 'aggregation_stage_swap')
        self.assertEqual(stage['proposed_grounding']['concepts'], stage['proposed_rejected']['concepts'])
        for key in ('date', 'bucket'):
            self.assertEqual(stage['proposed_grounding']['factors'][key], stage['proposed_rejected']['factors'][key])

    def test_field_hints_do_not_call_generic_location_an_od_error(self):
        gold = candidate()['proposed_grounding']
        prediction = copy.deepcopy(gold)
        prediction['concepts'].pop()
        hints = failure_hints(gold, prediction, assess(prediction, 'question'))
        self.assertNotIn('od_scope', hints)
        prediction = copy.deepcopy(gold)
        prediction['concepts'][-1]['attributes'] = {'od_role': 'dropoff'}
        self.assertIn('od_scope', failure_hints(gold, prediction, {}))

    def test_actual_prediction_dedup_and_eval_quarantine(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = candidate()
            rejected = copy.deepcopy(row['proposed_grounding'])
            rejected['factors']['aggregation'] = 'max'
            r = dict(id='t1', question=row['question'], gold=row['proposed_grounding'],
                     raw_text=serialize_planner_target(rejected), intent_id='rpm', split='train', grounding_exact=False)
            path1, path2 = root / 'base.json', root / 'dpo.json'
            save_json(path1, {'metadata': {'label': 'Base'}, 'records': [r]})
            save_json(path2, {'metadata': {'label': 'DPO'}, 'records': [{**r, 'split': 'external'}]})
            rows, issues = mine_predictions([path1, path2])
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(rows[0]['evidence']), 2)
            self.assertTrue(rows[0]['diagnostic_only'])
            self.assertEqual(rows[0]['negative_category'], 'semantic')
            self.assertEqual(issues['excluded'], [])
            unknown, _ = mine_predictions([path1], train_records=[])
            self.assertTrue(unknown[0]['diagnostic_only'])

    def test_invalid_json_and_equivalent_predictions_are_not_negative_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = candidate()
            record = dict(id='a', question=row['question'], gold=row['proposed_grounding'], intent_id='x',
                          split='train', grounding_exact=False)
            path = Path(tmp) / 'pred.json'
            save_json(path, {'records': [{**record, 'raw_text': 'not JSON'},
                                         {**record, 'raw_text': serialize_planner_target(row['proposed_grounding'])}]})
            rows, issues = mine_predictions([path])
            self.assertEqual(rows, [])
            self.assertEqual(len(issues['excluded']), 1)

    def test_xlsx_is_valid_xml_and_never_emits_formula_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'queue.xlsx'
            row = candidate(question='=HYPERLINK("malicious")')
            write_xlsx(path, [row])
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    ET.fromstring(archive.read(name))
                sheet = archive.read('xl/worksheets/sheet1.xml').decode()
                self.assertIn('HYPERLINK', sheet)
                self.assertNotIn('<f>', sheet)
                self.assertIn('inlineStr', sheet)


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.queue = self.root / 'queue'
        self.queue.mkdir()
        self.decisions = self.root / 'decisions.jsonl'
        self.protection = Protection()
        self.patcher = patch('training.annotations.workflow.Protection.current', return_value=self.protection)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.rows = [candidate(), candidate('speed', 'speed', '솔빛동 택시의 평균 주행 속도는?')]
        self.freeze()

    def freeze(self):
        self.rows = [seal({k: v for k, v in r.items() if k not in ('candidate_hash', 'eligibility')}, self.protection) for r in self.rows]
        write_jsonl(self.queue / 'review_queue.jsonl', self.rows)
        save_json(self.queue / 'manifest.json', {**provenance([], 42), 'gold_dir': str(self.root),
                                               'protection': self.protection.manifest(),
                                               'output_hashes': {'review_queue.jsonl': sha256(self.queue / 'review_queue.jsonl')}})

    def accept(self, index=0, **kwargs):
        return decide(self.queue, self.decisions, self.rows[index]['candidate_id'], status='accepted',
                      reviewer='human-reviewer', reason='Checked grounded meaning and lineage', semantic_checks=True, **kwargs)

    def export(self, name='v1'):
        return import_reviewed(self.queue, self.decisions, self.root / name, version=name)

    def test_accept_requires_human_semantic_checks_not_validator_pass(self):
        self.assertTrue(self.rows[0]['quality']['validation_ok'])
        with self.assertRaisesRegex(ValueError, 'semantic-checks'):
            decide(self.queue, self.decisions, self.rows[0]['candidate_id'], status='accepted',
                   reviewer='human', reason='validator pass')

    def test_pending_rejected_needs_fix_never_exported(self):
        for index, status in [(0, 'rejected'), (1, 'needs_fix')]:
            decide(self.queue, self.decisions, self.rows[index]['candidate_id'], status=status,
                   reviewer='human', reason='Needs correction')
        with self.assertRaisesRegex(ValueError, 'No reviewed'):
            self.export()
        self.assertFalse((self.root / 'v1').exists())

    def test_reviewed_version_export_hashes_and_group_split(self):
        self.accept(0)
        self.accept(1)
        counts = self.export()
        self.assertEqual(counts['sft_train'], 1)
        self.assertEqual(counts['sft_valid'], 1)
        train = read_jsonl(self.root / 'v1/sft_train.jsonl')
        valid = read_jsonl(self.root / 'v1/sft_valid.jsonl')
        check_split(train, valid)
        manifest = json.loads((self.root / 'v1/corpus_manifest.json').read_text())
        for name, expected in manifest['output_hashes'].items():
            self.assertEqual(sha256(self.root / 'v1' / name), expected)
        self.assertTrue(all(r['metadata']['review_decision_hash'] for r in train + valid))
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.export()

    def test_contrast_siblings_and_conservative_families_do_not_split(self):
        sibling = candidate(family='rpm', question='솔빛동에서 택시 엔진 회전수 평균을 알려줘')
        self.rows.append(sibling)
        self.freeze()
        for i in range(3):
            self.accept(i)
        self.export()
        splits = {s: read_jsonl(self.root / f'v1/sft_{s}.jsonl') for s in ('train', 'valid')}
        containing = [s for s, rows in splits.items() if any(r['metadata']['family'] == 'rpm' for r in rows)]
        self.assertEqual(len(containing), 1)
        self.assertEqual(sum(r['metadata']['family'] == 'rpm' for r in splits[containing[0]]), 2)

    def test_protected_corrections_cannot_launder_question_lineage(self):
        self.protection.add(self.rows[0]['question'], self.rows[0]['proposed_grounding'])
        self.freeze()
        self.accept(0, corrected=self.rows[1]['proposed_grounding'])
        self.accept(1)
        with self.assertRaisesRegex(ValueError, 'two disjoint'):
            self.export()
        self.assertFalse((self.root / 'v1').exists())

    def test_accepted_diagnostic_and_ambiguity_are_excluded(self):
        self.rows[0]['diagnostic_only'] = True
        self.rows[1]['expected_outcome'] = 'needs_clarification'
        self.freeze()
        self.accept(0)
        self.accept(1)
        with self.assertRaisesRegex(ValueError, 'No reviewed'):
            self.export()

    def test_schema_or_downstream_invalid_correction_fails_before_output(self):
        raw = copy.deepcopy(self.rows[0]['proposed_grounding'])
        raw['factors']['unknown'] = 'bad'
        self.accept(0, corrected=raw)
        self.accept(1)
        with self.assertRaisesRegex(ValueError, 'failed'):
            self.export()
        self.assertFalse((self.root / 'v1').exists())

    def test_audit_chain_needs_fix_then_accepted_and_tamper_detection(self):
        first = decide(self.queue, self.decisions, self.rows[0]['candidate_id'], status='needs_fix',
                       reviewer='human', reason='Check term')
        second = self.accept(0)
        self.assertEqual(second['supersedes'], first['decision_hash'])
        self.assertEqual(decision_history(self.decisions, self.rows)[self.rows[0]['candidate_id']]['status'], 'accepted')
        text = self.decisions.read_text().replace('Checked grounded meaning and lineage', 'tampered')
        self.decisions.write_text(text)
        with self.assertRaisesRegex(ValueError, 'checksum'):
            decision_history(self.decisions, self.rows)

    def test_candidate_hash_and_manifest_tampering(self):
        rows = read_jsonl(self.queue / 'review_queue.jsonl')
        rows[0]['question'] = 'tampered'
        write_jsonl(self.queue / 'review_queue.jsonl', rows)
        with self.assertRaisesRegex(ValueError, 'checksum'):
            load_queue(self.queue)

    def test_actual_reviewed_dpo_pair_inherits_sft_split(self):
        row = self.rows[0]
        bad = copy.deepcopy(row['proposed_grounding'])
        bad['factors']['aggregation'] = 'max'
        row['candidate_type'] = 'hard_negative'
        row['provenance'] = {'origin': 'pilot_prediction'}
        row['proposed_rejected'] = bad
        self.freeze()
        with self.assertRaisesRegex(ValueError, 'negative-is-wrong'):
            self.accept(0)
        self.accept(0, negative_wrong=True)
        self.accept(1)
        counts = self.export()
        self.assertEqual(counts['dpo_train'] + counts['dpo_valid'], 1)
        for split in ('train', 'valid'):
            pairs = read_jsonl(self.root / f'v1/dpo_{split}.jsonl')
            gold = read_jsonl(self.root / f'v1/sft_{split}.jsonl')
            self.assertTrue(all(p['metadata']['source_record_id'] in {r['metadata']['source_record_id'] for r in gold} for p in pairs))

    def test_identical_reviewed_chosen_rejected_cannot_export(self):
        self.rows[0]['candidate_type'] = 'hard_negative'
        self.rows[0]['provenance'] = {'origin': 'pilot_prediction'}
        self.rows[0]['proposed_rejected'] = self.rows[0]['proposed_grounding']
        self.freeze()
        self.accept(0, negative_wrong=True)
        self.accept(1)
        with self.assertRaisesRegex(ValueError, 'equivalent'):
            self.export()
        self.assertFalse((self.root / 'v1').exists())

    def test_nonhuman_and_stale_decisions_fail_closed(self):
        decision = self.accept()
        decision['reviewer_kind'] = 'model'
        decision['decision_hash'] = digest({k: v for k, v in decision.items() if k != 'decision_hash'})
        write_jsonl(self.decisions, [decision])
        with self.assertRaisesRegex(ValueError, 'human'):
            decision_history(self.decisions, self.rows)
        decision['reviewer_kind'] = 'human'
        decision['candidate_hash'] = 'stale'
        write_jsonl(self.decisions, [decision])
        with self.assertRaisesRegex(ValueError, 'stale'):
            decision_history(self.decisions, self.rows)

    def test_source_or_prompt_drift_requires_new_review_version(self):
        self.accept(0)
        self.accept(1)
        manifest = json.loads((self.queue / 'manifest.json').read_text())
        manifest['prompt_hash'] = 'old'
        save_json(self.queue / 'manifest.json', manifest)
        with self.assertRaisesRegex(ValueError, 'drift'):
            self.export()

    def test_corrected_structured_target_cannot_enter_flat_corpus(self):
        raw = copy.deepcopy(self.rows[0]['proposed_grounding'])
        raw['factors'] = {'aggregation_plan': {'result': {'reducer': 'avg'}}}
        self.accept(0, corrected=raw)
        self.accept(1)
        with self.assertRaisesRegex(ValueError, 'Structured'):
            self.export()

    def test_duplicate_question_conflicting_gold_is_reported(self):
        sibling = candidate('speed', 'rpm', self.rows[0]['question'])
        self.rows.append(sibling)
        self.freeze()
        for i in range(3):
            self.accept(i)
        with self.assertRaisesRegex(ValueError, 'Conflicting accepted golds'):
            self.export()

    def test_preparation_cli_integration_does_not_export_or_modify_source(self):
        from training.data.build_sft import sft_record
        data = self.root / 'data'
        data.mkdir()
        source = self.root / 'source.yaml'
        annotations = [dict(id=f'g{i}', question=r['question'], grounding=r['proposed_grounding'],
                            parent_intent=r['parent_intent']) for i, r in enumerate(self.rows)]
        source.write_text(yaml.safe_dump({'examples': annotations}, allow_unicode=True))
        original_hash = sha256(source)
        records = [sft_record(r, source=str(source), source_representation='flat') for r in annotations]
        for split, rows in [('train', records[:1]), ('valid', records[1:])]:
            write_jsonl(data / f'sft_{split}.jsonl', rows)
            write_jsonl(data / f'dpo_{split}.jsonl', [])
        save_json(data / 'manifest.json', {stage: {'output_hashes': {
            f'{stage}_{split}.jsonl': sha256(data / f'{stage}_{split}.jsonl') for split in ('train', 'valid')}}
            for stage in ('sft', 'dpo')})
        pilot = self.root / 'pilot/metrics'
        pilot.mkdir(parents=True)
        good = annotations[0]['grounding']
        bad = copy.deepcopy(good)
        bad['factors']['aggregation'] = 'max'
        record = dict(id='g0', question=annotations[0]['question'], gold=good, raw_text=serialize_planner_target(bad),
                      intent_id=annotations[0]['parent_intent'], split='train', grounding_exact=False)
        for label in ('base', 'sft_best', 'dpo_best'):
            save_json(pilot / f'{label}.json', {'metadata': {'complete': True, 'label': label,
                                                         'prompt_hash': provenance([], 42)['prompt_hash']}, 'records': [record]})
        output = self.root / 'prepared'
        with redirect_stdout(io.StringIO()):
            rows = prepare(output, gold_dir=data, source=source, pilot=pilot.parent)
        self.assertEqual(sha256(source), original_hash)
        self.assertTrue(all(r['status'] == 'pending' for r in rows))
        self.assertEqual(sum(r['candidate_type'] == 'hard_negative' for r in rows), 1)
        self.assertTrue((output / 'review_queue.xlsx').exists())
        self.assertFalse((output / 'sft_train.jsonl').exists())
        with self.assertRaisesRegex(ValueError, 'already exists'):
            prepare(output, gold_dir=data, source=source, pilot=pilot.parent)


if __name__ == '__main__':
    unittest.main()
