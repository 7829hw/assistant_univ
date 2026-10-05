"""CPU-only checks for pilot leakage guards and validation-only selection."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from training.pilot import audit, errors, selection_key, select
from training.pilot_report import counts, paired, correct_execution


class PilotTests(unittest.TestCase):
    def test_audit_catches_leakage_and_identical_pairs(self):
        def row(name, subtype):
            payload = {'concepts': [{'id': 'm', 'concept': 'AMOUNT', 'subtype': subtype, 'role': 'MEASURE'}], 'factors': {'aggregation': 'avg'}}
            return {'messages': [{'role': 'system', 'content': 'p'}, {'role': 'user', 'content': name}, {'role': 'assistant', 'content': json.dumps(payload)}], 'metadata': {'source_record_id': name, 'parent_intent': name}}
        sft = {'train': [row('a', 'fare')], 'valid': [row('b', 'revenue')]}
        def pair(gold):
            rejected = json.loads(gold['messages'][-1]['content'])
            rejected['factors']['aggregation'] = 'sum'
            return {'prompt': gold['messages'][:2], 'chosen': [gold['messages'][-1]], 'rejected': [{'role': 'assistant', 'content': json.dumps(rejected)}], 'metadata': gold['metadata']}
        dpo = {s: [pair(sft[s][0])] for s in sft}
        self.assertTrue(audit(sft, dpo)['passed'])
        bad = copy.deepcopy(dpo)
        bad['train'][0]['rejected'] = bad['train'][0]['chosen']
        with self.assertRaisesRegex(ValueError, 'Identical'):
            audit(sft, bad)
        bad = copy.deepcopy(sft)
        bad['valid'][0]['metadata']['parent_intent'] = 'a'
        with self.assertRaisesRegex(ValueError, 'Parent'):
            audit(bad, dpo)

    def test_selection_uses_semantics_before_format_or_train_loss(self):
        a = {'by_split': {'valid': {'grounding_exact_match': 2/3, 'factor_exact_match': .5, 'json_parse_rate': 1}}, 'train_loss': 0}
        b = {'by_split': {'valid': {'grounding_exact_match': 1, 'factor_exact_match': 1, 'json_parse_rate': 1}}, 'train_loss': 10}
        self.assertGreater(selection_key(b, 12), selection_key(a, 2))
        self.assertGreater(selection_key(b, 2), selection_key(b, 12))

    def test_syntax_and_semantics_remain_distinct(self):
        row = dict(raw_text='```json\n{}\n```', json_parse_ok=True, planner_contract_ok=True,
                   grounding_exact=False, expected_unsupported=False, composed=True, validated=True, executed=True)
        self.assertEqual(errors(row), ['syntax', 'semantic'])
        row.update(raw_text='{}', planner_contract_ok=False)
        self.assertEqual(errors(row), ['schema'])

    def test_refusal_is_not_execution_failure(self):
        row = dict(raw_text='{"unsupported":true}', planner_contract_ok=True, grounding_exact=True,
                   expected_unsupported=True, composed=False, validated=False, executed=None)
        self.assertEqual(errors(row), [])

    def test_evaluator_preserves_raw_schema_failure_and_denominators(self):
        import training.thor_evaluate_planner as E
        from geoflow.planner import GeoFlowPlanner
        from geoflow.composer import MacroComposer
        raw = json.dumps({'concepts': [{'id': 'm', 'concept': 'AMOUNT', 'subtype': 'fare', 'role': 'MEASURE', 'source': 'implicit'}], 'factors': {'aggregation': 'week'}})
        class Client:
            model = 'test'
            def chat(self, *args, **kwargs):
                return {'message': {'content': raw}}
        client = Client()
        planner = GeoFlowPlanner(client=client)
        result = E.evaluate_once(planner, MacroComposer(), {'id': 'x', 'question': '택시 요금 평균은?',
                    'expected_concepts': ['AMOUNT/fare:MEASURE'], 'expected_macros': ['EVENT_TO_MEASURE'],
                    'expected_operators': ['TRIP_METRIC']})
        self.assertEqual(result['raw_text'], raw)
        self.assertTrue(result['json_parse_ok'])
        self.assertFalse(result['planner_contract_ok'])
        self.assertEqual(result['concept_score']['concept']['expected'], 1)
        self.assertEqual(result['operator_score']['expected'], 1)
        self.assertGreater(result['planner_calls'], 0)
        self.assertIs(planner.client, client)
        totals = counts([result])
        self.assertEqual(totals['Contract pass'], {'matched': 0, 'total': 1})
        self.assertEqual(totals['Macro'], {'matched': 0, 'total': 1})
        self.assertEqual(totals['G1_ACYCLICITY']['total'], 0)
        self.assertEqual(totals['Repair success']['total'], 0)

    def test_selection_ignores_generation_configuration_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'metrics').mkdir()
            report = {'metadata': {'complete': True, 'adapter': 'adapter'}, 'by_split': {'valid': {'grounding_exact_match': 1}}}
            (directory / 'metrics/sft_1_step2.json').write_text(json.dumps(report))
            (directory / 'metrics/sft_1_step2_generation_config.json').write_text('{"do_sample":false}')
            select(directory, 'sft')
            self.assertEqual(json.loads((directory / 'best_sft.json').read_text())['label'], 'sft_1_step2')

    def test_paired_error_analysis_checks_questions_and_tracks_regressions(self):
        def run(exact):
            return {'records': [{'id': 'x', 'question': 'q', 'gold': {'unsupported': True}, 'split': 'external',
                                 'raw_text': '{"unsupported":true}', 'grounding_exact': exact, 'validation_codes': []}]}
        result = paired(run(False), run(True), run(False))
        self.assertEqual(len(result['base_to_sft_improvements']), 1)
        self.assertEqual(len(result['sft_to_dpo_regressions']), 1)
        self.assertEqual(result['sft_to_dpo_improvements'], [])
        bad = run(True)
        bad['records'][0]['question'] = 'different'
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            paired(run(False), run(True), bad)

    def test_execution_correction_preserves_failed_live_repair(self):
        import training.thor_evaluate_planner as E
        from geoflow.planner import GeoFlowPlanner
        from geoflow.composer import MacroComposer
        raw = {'concepts': [
            {'id': 'e', 'concept': 'EVENT', 'subtype': 'trip', 'role': 'SUPPORT', 'source': 'implicit'},
            {'id': 'm', 'concept': 'AMOUNT', 'subtype': 'trip_count', 'role': 'MEASURE', 'source': 'implicit'}],
            'factors': {'bucket': 'month', 'dimension': 'sigungu', 'dimension_target': 'dropoff',
                        'order': 'bottom', 'limit': 2}}
        repaired = copy.deepcopy(raw)
        repaired['factors']['date'] = 'last_month'  # Scope change is forbidden by this repair.
        class Client:
            model = 'test'
            calls = 0
            def chat(self, *args, **kwargs):
                self.calls += 1
                return {'message': {'content': json.dumps(raw if self.calls == 1 else repaired)}}
        item = {'id': 'repair', 'question': '지난달 하차가 가장 적은 시군구 2곳은?',
                'expected_concepts': ['EVENT/trip:SUPPORT', 'AMOUNT/trip_count:MEASURE'],
                'expected_macros': ['EVENT_TO_MEASURE'], 'expected_operators': ['TRIP_COUNT']}
        record = E.evaluate_once(GeoFlowPlanner(client=Client()), MacroComposer(), item)
        self.assertTrue(record['repair_attempted'])
        self.assertFalse(record['repair_succeeded'])
        self.assertEqual(record['planner_calls'], 2)
        self.assertFalse(record['validated'])
        record.update(split='external', intent_id='repair', gold=raw, error_categories=errors(record))
        report = {'metadata': {'complete': True}, 'records': [record],
                  'by_split': {'external': E.summarize([record])}}
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'metrics').mkdir()
            (directory / 'errors').mkdir()
            (directory / 'items.json').write_text(json.dumps([item]))
            for label in ('base', 'sft_best', 'dpo_best', 'sft_last', 'dpo_last'):
                (directory / 'metrics' / f'{label}.json').write_text(json.dumps(report))
            correct_execution(directory)
            result = json.loads((directory / 'metrics/base.json').read_text())
            self.assertEqual(result['records'], [record])
            self.assertEqual(result['summary']['repair_attempted'], 1)


if __name__ == '__main__':
    unittest.main()
