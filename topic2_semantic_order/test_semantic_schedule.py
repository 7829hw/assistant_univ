# -*- coding: utf-8 -*-
"""Smoke/invariant tests; fixtures reproduce V4's 1,984-record tool totals.

Fixture records are ARTIFICIAL. These tests say nothing about model accuracy.
"""
import json
from collections import Counter
from pathlib import Path
import random
import tempfile
import unittest

try:
    from .semantic_schedule import (
        build_balanced_order, labels_from_approved, max_run, random_slot_order,
        rid, sequence_metrics, build_manifest, validate_coverage_variant,
    )
except ImportError:
    from semantic_schedule import (
        build_balanced_order, labels_from_approved, max_run, random_slot_order,
        rid, sequence_metrics, build_manifest, validate_coverage_variant,
    )

# Verified from ablation_013/build/build_summary.json, composition.A0.
TOOL_COUNTS={
    'get_billing_metrics':(655,149),
    'get_passage_count':(359,83),
    'get_scope_name':(124,16),
    'get_trip_count':(655,154),
    'get_drive_metrics_rpm':(55,9),
    'get_drive_metrics_speed':(15,2),
    'get_drive_metrics_vacant_ratio':(42,7),
    'refusal':(79,74),
}


def make_fixture():
    rng=random.Random(1998)
    records=[]; approved=[]
    for tool,(n_records,n_questions) in TOOL_COUNTS.items():
        assert n_records>=n_questions
        qids=[f'fake-{tool}-{i:04d}' for i in range(n_questions)]
        allocations=[1]*n_questions
        for _ in range(n_records-n_questions):
            allocations[rng.randrange(n_questions)]+=1
        for ix,(qid,n) in enumerate(zip(qids,allocations)):
            if tool=='refusal':
                ex=[]
            else:
                cat=tool.split('_rpm')[0].split('_speed')[0].split('_vacant_ratio')[0]
                ex=[{'tool':'get_place_scope','args':{'name':['서울','서초구','역삼동'][ix%3]}},
                    {'tool':cat,'args':{'metric':('fare' if cat=='get_billing_metrics' else ('speed' if cat=='get_drive_metrics' else 'count')),
                                      'date':['20260101','last_month','last_week'][ix%3],
                                      'aggregation':['sum','avg','max'][ix%3]}}]
            approved.append({'id':qid,'execution':ex,'view':{'measure':{'subtype':tool},'aggregation':['sum','avg','max'][ix%3]}})
            for k in range(n):
                m={'source_record_id':qid,'trace_id':f'fixture-trace-{k:03d}',
                   'trace_sha256':f'fake-sha{k:03d}',
                   'loss_scope':'full_response' if k%2==0 else 'json_only'}
                if tool=='refusal':m['refusal_source']='fixture'
                records.append({'metadata':m,'messages':[{'role':'user','content':'fixture only'}]})
    rng.shuffle(records)
    assert len(records)==1984 and len(approved)==494
    return records,approved


class ScheduleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records,cls.approved=make_fixture()
        cls.labels=labels_from_approved(cls.records,cls.approved)
        cls.base_ids={rid(x) for x in cls.records}

    def test_exact_cardinality_and_uniqueness(self):
        seq=build_balanced_order(self.records,self.labels,1102)
        self.assertEqual(1984,len(seq))
        self.assertEqual(self.base_ids,set(seq))
        self.assertEqual(494,len(self.labels))
        self.assertLessEqual(max_run([k.split('|',1)[0] for k in seq]),4)

    def test_deterministic_across_invocations_and_distinct_seeds(self):
        a=build_balanced_order(self.records,self.labels,1102)
        b=build_balanced_order(self.records,self.labels,1102)
        c=build_balanced_order(self.records,self.labels,211102)
        self.assertEqual(a,b)
        self.assertNotEqual(a,c)

    def test_train_group_balance_against_random_slot_shuffling(self):
        baseline=random_slot_order(self.records,1102)
        balanced=build_balanced_order(self.records,self.labels,1102)
        sb=sequence_metrics(baseline,self.labels)
        sm=sequence_metrics(balanced,self.labels)
        self.assertLess(sm['coarse']['mean_window_total_variation'],sb['coarse']['mean_window_total_variation'])
        self.assertEqual(sm['n_records'],sb['n_records'])

    def test_frozen_manifest_integrity(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td)
            train=t/'train.jsonl'; app=t/'approved.jsonl'; dst=t/'manifest'
            train.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in self.records),encoding='utf-8')
            app.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in self.approved),encoding='utf-8')
            result=build_manifest(train,app,dst,[1102])
            info=json.loads((dst/'semantic_order_o1102.json').read_text(encoding='utf-8'))
            self.assertFalse(info['reference_is_true_o4prime'])
            self.assertFalse(result['holdout_used_for_order'])
            self.assertEqual(result['seeds']['1102']['sha256'],info['record_sequence_sha256'])
            self.assertEqual(1984,len(info['record_sequence']))


    def test_config_generation_keeps_hyperparams_and_frozen_base(self):
        import yaml
        try:
            from .make_training_configs import generate
        except ImportError:
            from make_training_configs import generate
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            conf_dir=root/'sft_dpo_inventory/ablation_011/train/configs'
            conf_dir.mkdir(parents=True)
            original={
              'model': {'name_or_path':'Qwen/Qwen3-8B','revision':'mockfrozen'},
              'data': {'train':'sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl'},
              'training': {'seed':43,'num_train_epochs':1,'learning_rate':0.0002,
                'shared_slot_order_seed':1102, 'shared_slot_order_file':'orig-order',
                'a11_record_order_file':'orig-record-order', 'output_dir':'baseline-old'},
              'lora':{'r':16,'alpha':32,'dropout':0.05},
              'profiling':{'output':'baseline-old-profile'}
            }
            (conf_dir/'A0-o1102.yaml').write_text(yaml.safe_dump(original),encoding='utf-8')
            sch=root/'orders';sch.mkdir();(sch/'semantic_order_o1102.json').write_text('{}')
            out=root/'configs'
            report=generate(root,sch,out,[1102],'/tmp/mycheckpoints',repeats=2)
            self.assertEqual(len(report),2)
            a=yaml.safe_load((out/'baseline_o1102_r1.yaml').read_text())
            b=yaml.safe_load((out/'semantic_o1102_r1.yaml').read_text())
            for name in ('model','data','lora'):
                self.assertEqual(a[name],b[name])
            for name in ('seed','num_train_epochs','learning_rate'):
                self.assertEqual(a['training'][name],b['training'][name])
            self.assertEqual(a['training']['shared_slot_order_seed'],1102)
            self.assertNotIn('shared_slot_order_seed',b['training'])
            self.assertEqual(b['training']['semantic_schedule_seed'],1102)
            self.assertNotEqual(a['training']['output_dir'],b['training']['output_dir'])
            self.assertTrue((out/'semantic_o1102_r2.yaml').exists())

    def test_coverage_arm_fail_closed_without_provenance_and_tokens(self):
        with self.assertRaisesRegex(ValueError,'Coverage changes require'):
            validate_coverage_variant(self.records,self.records,self.approved)

    def test_coverage_arm_same_budget_and_protected_family_guard(self):
        tokens={rid(r):200 for r in self.records}
        v=validate_coverage_variant(self.records,self.records,self.approved,
                                    blocked_ids=set(),blocked_families=set(),loss_ledger=tokens)
        self.assertEqual(v['records'],1984)
        self.assertEqual(v['loss_token_ratio'],1)
        protected_q=next(iter(self.labels))
        with self.assertRaisesRegex(ValueError,'protected evaluation id'):
            validate_coverage_variant(self.records,self.records,self.approved,
                        blocked_ids={protected_q},blocked_families=set(),loss_ledger=tokens)


if __name__=='__main__':
    unittest.main(verbosity=2)


class RealV4Test(unittest.TestCase):
    """Runs only inside the repository checkout: real V4 file + approved train corpus."""
    TRAIN = Path(__file__).resolve().parents[1] / "sft_dpo_inventory/pilot_010/build/V4/full/sft_train.jsonl"
    APPR = Path(__file__).resolve().parents[1] / "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v6.jsonl"

    @unittest.skipUnless(TRAIN.exists() and APPR.exists(), "real V4 files not present")
    def test_real_v4_invariants(self):
        from semantic_schedule import read_jsonl, sha_lines
        rec = read_jsonl(self.TRAIN)
        labels = labels_from_approved(rec, read_jsonl(self.APPR))
        self.assertFalse(any("subtype:" in c for c, _ in labels.values()))  # defect fixed: no split coarse groups
        for seed in (1102, 2026131):
            a = build_balanced_order(rec, labels, seed)
            self.assertEqual(a, build_balanced_order(rec, labels, seed))
            self.assertEqual(sorted(a), sorted(rid(r) for r in rec))
            self.assertLessEqual(max_run([k.split("|")[0] for k in a]), 4)
            self.assertEqual(len(sha_lines(a)), 64)
