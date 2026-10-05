"""Review recommendations never constitute approval or model inference."""
import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from training.annotations.candidates import measure_payload, proposal
from training.annotations.review_batch import (advice, category, compile_diagnostic, prediction_views,
                                                prioritized, view, workbook)
from training.annotations.workflow import seal
from training.annotations.inventory import Protection, digest
from training.data.validation import assess


def row(kind='rare_measure', subtype='rpm', question='솔빛동 택시 평균 RPM은?'):
    item = proposal(question, measure_payload('AMOUNT',subtype,{'aggregation':'avg'},[('솔빛동',None)]),
                    kind,'rpm-family','Check meaning',provenance={'origin':'authored_blueprint'})
    return seal(item,Protection())


class ReviewBatchTest(unittest.TestCase):
    def test_priority_excludes_protected_and_keeps_pending(self):
        gold=row('gold_re_review');gold['provenance']['source_record_id']='ex03'
        source=row('source_role_value_factor')
        aggregation=row('aggregation_stage')
        od=row('od_scope')
        rare=row()
        hard=row('hard_negative')
        blocked=copy.deepcopy(gold);blocked['eligibility']['eligible_after_human_review']=False
        blocked['diagnostic_only']=True
        original=copy.deepcopy([hard,rare,od,source,aggregation,gold,blocked])
        output=prioritized(original)
        self.assertEqual([category(r) for r in output],['gold_re_review','source_role_value_factor','aggregation','od','rare_measure','train_hard_negative'])
        self.assertEqual(len(output),6)
        self.assertTrue(all(r['status']=='pending' for r in original+output))
        self.assertEqual(original[-1],blocked)

    def test_inconsistent_eligible_diagnostic_fails_closed(self):
        item=row();item['diagnostic_only']=True
        with self.assertRaisesRegex(ValueError,'Diagnostic'):
            prioritized([item])

    def test_pair_category_follows_capability_and_gold_precedes_pair(self):
        gold=row('aggregation_stage')
        pair=copy.deepcopy(gold)
        pair['candidate_type']='semantic_negative';pair['negative_type']='aggregation_stage_swap'
        pair['proposed_rejected']=copy.deepcopy(gold['proposed_grounding'])
        self.assertEqual(category(pair),'aggregation')
        self.assertEqual([r['candidate_type'] for r in prioritized([pair,gold])],['aggregation_stage','semantic_negative'])
        pair['negative_type']='od_role_confusion'
        self.assertEqual(category(pair),'od')

    def test_advice_is_not_acceptance_and_validity_is_not_semantic_evidence(self):
        item=row()
        self.assertTrue(item['quality']['validation_ok'])
        rec=advice(item,{}, {'compile_ok':True})
        self.assertEqual(rec['recommendation'],'accepted')
        self.assertTrue(rec['advisory_only'])
        self.assertEqual(item['status'],'pending')
        self.assertIn('Validator PASS만',rec['recommendation_reason'])
        uncertain=row(subtype='active_taxi_count')
        rec=advice(uncertain,{}, {'compile_ok':True})
        self.assertEqual(rec['recommendation'],'needs_fix')
        self.assertTrue(rec['uncertainty']['semantic_ambiguity'])
        self.assertTrue(rec['uncertainty']['subtype_definition_uncertain'])

    def test_compiler_boundary_flag_does_not_mutate_target_to_unsupported(self):
        item=row()
        original=copy.deepcopy(item)
        rec=advice(item,{}, {'compile_ok':False,'error_code':'UNVERIFIED_TIMS_CONTRACT'})
        self.assertEqual(rec['recommendation'],'needs_fix')
        self.assertIn('production_support_boundary_uncertain',rec['flags'])
        self.assertFalse(rec['uncertainty']['semantic_ambiguity'])
        self.assertEqual(item,original)

    def test_no_prediction_is_not_replaced_with_linked_dev_prediction(self):
        reports={'Base':(Path('base.json'), {'records':[{'question':'different dev question','split':'external'}]})}
        result=prediction_views(reports,'new authored question')
        self.assertFalse(result['Base']['available'])
        with self.assertRaisesRegex(ValueError,'Protected'):
            prediction_views(reports,'different dev question')

    def test_original_raw_prediction_and_quality_are_preserved(self):
        item=row();raw=json.dumps(item['proposed_grounding'],ensure_ascii=False,indent=3)
        records=[{'id':'g1','question':item['question'],'raw_text':raw,'split':'train','grounding_exact':True}]
        p=prediction_views({'Base':(Path('base.json'), {'records':records})},item['question'])['Base']
        self.assertEqual(p['raw_text'],raw)
        self.assertTrue(p['strict_raw_quality']['validation_ok'])
        self.assertTrue(p['production_quality']['validation_ok'])

    def test_invalid_json_prediction_is_visible_and_flagged(self):
        item=row()
        report={'records':[{'id':'g','question':item['question'],'raw_text':'invalid JSON','split':'train','grounding_exact':False}]}
        p=prediction_views({'Base':(Path('base.json'),report)},item['question'])
        rec=advice(item,p,{'compile_ok':True})
        self.assertIn('gold_vs_model_requires_review',rec['flags'])
        self.assertFalse(p['Base']['strict_raw_quality']['parse_ok'])
        self.assertEqual(p['Base']['raw_text'],'invalid JSON')

    def test_view_has_original_gold_projection_not_runtime_to_dict(self):
        item=row()
        original=copy.deepcopy(item['proposed_grounding'])
        original['factors']={'aggregation_plan':{'result':{'reducer':'avg'}}}
        examples=[{'id':'old','question':item['question'],'grounding':original,'note':'Checked source representation'}]
        reports={label:(Path(label),{'records':[]}) for label in ('Base','SFT','DPO')}
        result=view(item,1,examples,reports)
        self.assertEqual(result['existing_grounding'],original)
        self.assertEqual(result['existing_grounding_flat'],item['proposed_grounding'])
        self.assertEqual(result['status'],'pending')
        self.assertEqual(result['candidate_hash'],item['candidate_hash'])
        self.assertEqual(result['review_view_hash'],digest({k:v for k,v in result.items() if k!='review_view_hash'}))
        self.assertTrue(result['proposed_quality']['strict_raw']['validation_ok'])

    def test_workbook_comparisons_and_priority_are_separate_string_cells(self):
        item=row(question='=HYPERLINK("not-a-formula")')
        reports={label:(Path(label),{'records':[]}) for label in ('Base','SFT','DPO')}
        result=view(item,1,[],reports)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'batch.xlsx'
            workbook(path,[result],[{'rank':1,'question':item['question'],'status':'pending'}])
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    ET.fromstring(archive.read(name))
                xml=archive.read('xl/workbook.xml').decode()
                self.assertIn('Review_batch_001',xml)
                self.assertIn('Eligible_46_priority',xml)
                sheet=archive.read('xl/worksheets/sheet1.xml').decode()
                self.assertNotIn('<f>',sheet)
                self.assertIn('HYPERLINK',sheet)
                self.assertIn('Base actual output',sheet)
                self.assertIn('Actual status',sheet)
                self.assertIn('Advisory recommendation',sheet)

    def test_actual_tims_compile_boundary_is_not_validator_failure(self):
        item=row()
        item['proposed_grounding']['factors'].update(date='20260901-20260930',bucket='week',rollup='max')
        self.assertTrue(assess(item['proposed_grounding'],item['question'])['validation_ok'])
        diag=compile_diagnostic(item['proposed_grounding'],item['question'])
        self.assertFalse(diag['compile_ok'])
        self.assertEqual(diag['error_code'],'UNVERIFIED_TIMS_CONTRACT')
        self.assertFalse(diag['execution_tested'])


if __name__=='__main__':
    unittest.main()
