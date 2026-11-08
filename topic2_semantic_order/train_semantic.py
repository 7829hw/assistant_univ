#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GeoFlow trainer wrapper for a frozen, offline-validated semantic schedule.

Run FROM the original repository root after copying this experiment directory
there, using the same runtime as ablation_011/train/train_a11.py:

 runtime/envs/hf/bin/python topic2_semantic_order/train_semantic.py \
   --config topic2_semantic_order/configs/semantic_o1102.yaml --dry-run

This wrapper must not be used for arm O4': continue to use the original
ablation_011/train/train_a11.py with its original A0 config.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=Path.cwd()
if not (ROOT/'sft_dpo_inventory/pilot_007/train_data/train_b7b.py').exists():
    raise SystemExit('Run from repository root with training environment configured')
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'sft_dpo_inventory/pilot_007/train_data'))
sys.path.insert(0,str(ROOT/'sft_dpo_inventory/ablation_011/train'))
from semantic_schedule import rid, qid, sha_lines, sha_file, max_run  # noqa: E402


def apply_semantic_order(config, records):
    from transformers import Trainer
    import order7
    t=config['training']
    order_file=t.pop('semantic_schedule_file',None)
    seed=t.pop('semantic_schedule_seed',None)
    if not order_file or seed is None:
        raise ValueError('Missing semantic_schedule_file or semantic_schedule_seed in training config')
    if any(k in t for k in ('shared_slot_order_file','shared_slot_order_seed','a11_record_order_file')):
        raise ValueError('Do not mix O4prime and semantic scheduling in the same arm')
    p=Path(order_file)
    if not p.is_absolute():
        p=ROOT/p
    o=json.loads(p.read_text(encoding='utf-8'))
    if o.get('seed')!=int(seed) or o.get('arm')!='SEMANTIC_ORDER':
        raise ValueError('Wrong arm/seed in order file')
    file=config['data']['train']
    file=Path(file) if Path(file).is_absolute() else ROOT/file
    if sha_file(file)!=o.get('training_sha256'):
        raise ValueError('Training input hash differs from order file')
    by_id={rid(r):r for r in records['train']}
    seq=o['record_sequence']
    checks={
        'all_record_ids_unique':len(by_id)==len(records['train']),
        'same_record_set':set(seq)==set(by_id) and len(seq)==len(records['train']),
        'sequence_sha':sha_lines(seq)==o['record_sequence_sha256'],
        'max_question_run':max_run([x.split('|',1)[0] for x in seq])<=o['max_run_limit']<=4,
    }
    if not all(checks.values()):
        raise ValueError('Semantic order rejected: '+str(checks))
    records['train']=[by_id[x] for x in seq]
    sampler_fn=order7.install_sequential_sampler()
    if Trainer._get_train_sampler is not sampler_fn:
        raise RuntimeError('SequentialSampler installation failed')
    print(json.dumps({'semantic_order':{
        'seed':seed,'records':len(seq),'sha256':o['record_sequence_sha256'],
        'checks':checks,'trainer_sampler':'SequentialSampler',
        'training_input_sha256':o['training_sha256']
    }}),flush=True)


def main(argv=None):
    import train_a11
    train_a11.install_override()  # preserves original thinking.loss_scope behavior
    import train_b7b as B
    from training.trainer_common import cli
    args,config,records,manifest=cli('sft',argv)
    apply_semantic_order(config,records)
    if args.dry_run:
        print(json.dumps({'lr_plan':B.lr_plan(len(records['train']),config)}),flush=True)
        return
    if args.tokenizer_check:
        return
    from training.profiling import RunProfile
    from training.train_sft import train
    profile=RunProfile(config,'sft')
    error=None
    try:
        train(args,config,records,manifest,profile,callbacks=[B.SaveAt()])
    except BaseException as exc:
        error=exc
        raise
    finally:
        profile.finish(error)

if __name__=='__main__':
    main()
