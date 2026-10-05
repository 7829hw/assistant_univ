"""V003 token preflight and disposable two-step Thor memory probes.

No corpus is changed. Longest validation records are runtime stress fixtures,
never training exports: LR=0, policy hashes must remain identical, and the
bootstrap adapter is marked smoke-only. These results are not quality metrics.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from training.data.common import ROOT, production_prompt, provenance, read_jsonl, sha256
from training.annotations.inventory import digest
from training.data.analyze_tokens import analyze
from training.records.corpora.reviewed_gold_v003.assembly_recipe import token_rows
from training.trainer_common import load_config, load_records, render_records, tokenizer_for

LIMITS = {'sft': {'max_seq_length': 7040},
          'dpo': {'max_length': 7040, 'max_prompt_length': 6816, 'max_completion_length': 256}}
CASES = ('control_old', 'control_new', 'long_new')


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def verify(directory):
    manifest = json.loads((Path(directory) / 'manifest.json').read_text())
    for name, expected in manifest['frozen_files'].items():
        if sha256(name) != expected:
            raise ValueError(f'Frozen source drift: {name}')
    if hashlib.sha256(production_prompt().encode()).hexdigest() != manifest['prompt_hash']:
        raise ValueError('Production prompt drift')
    return manifest


def select_records(records, measurements):
    """Same fitting train record for A/B; maximum complete record for stress."""
    flat = records['train'] + records['valid']
    indexed = list(zip(flat, measurements))
    fitting = [(r, m) for r, m in indexed if m['split'] == 'train' and not m['current_limit_failures']]
    if not fitting:
        raise ValueError('No fitting training control')
    control = max(fitting, key=lambda x: x[1]['total'])
    longest = max(indexed, key=lambda x: x[1]['total'])
    return {'control_old': control, 'control_new': control, 'long_new': longest}


def prepare(directory, corpus):
    directory, corpus = Path(directory).resolve(), Path(corpus).resolve()
    if directory.exists():
        raise ValueError('Experiment version already exists')
    sources = [corpus / 'corpus_manifest.json', corpus / 'manifest.json',
               *[corpus / f'{stage}_{s}.jsonl' for stage in ('sft', 'dpo') for s in ('train', 'valid')]]
    for stage in ('sft', 'dpo'):
        sources.append(ROOT / f'training/records/pilots/thor_pilot_002/configs/{stage}_template.yaml')
    meta = provenance(sources + [Path(__file__)], 42)
    frozen = dict(meta['source_files'])
    for pattern in ('training/configs/*.yaml', 'training/experiments/*/configs/*.yaml',
                    'training/records/corpora/reviewed_gold_v00[12]/**/*',
                    'training/annotations/generated/corpora/reviewed_gold_v00[123]/**/*'):
        frozen.update({str(p): sha256(p) for p in ROOT.glob(pattern) if p.is_file()})
    frozen.update({str(ROOT / p): h for p, h in meta['definition_hashes'].items()})
    exports = json.loads((corpus / 'corpus_manifest.json').read_text())['output_hashes']
    for stage in ('sft', 'dpo'):
        for split in ('train', 'valid'):
            name = f'{stage}_{split}.jsonl'
            if sha256(corpus / name) != exports[name]:
                raise ValueError(f'Corpus checksum mismatch: {name}')
    configurations, reports, selections = {}, {}, {}
    for stage in ('sft', 'dpo'):
        template = sources[6 + ('sft', 'dpo').index(stage)]
        config = load_config(template, stage)
        config['data'] = {s: str(corpus / f'{stage}_{s}.jsonl') for s in ('train', 'valid')}
        config['data']['manifest'] = str(corpus / 'manifest.json')
        records, _ = load_records(config, stage)
        tokenizer = tokenizer_for(config)
        old = token_rows(tokenizer, records, config, stage)
        selected = select_records(records, old)
        config['training'].update(LIMITS[stage])
        new = token_rows(tokenizer, records, config, stage)
        if any(r['current_limit_failures'] for r in new):
            raise ValueError('Candidate limits overflow')
        for group in records.values():
            render_records(tokenizer, group, config, stage)
        reports[stage] = dict(measurements=new, statistics=analyze(tokenizer, records['train'] + records['valid'], config, stage),
                              overflow_count=0, truncation_count=0, old_blocked_records=[m for m in old if m['current_limit_failures']],
                              tokenizer_chat_template_sha256=hashlib.sha256(tokenizer.chat_template.encode()).hexdigest())
        for case in CASES:
            r, m = selected[case]
            selections[f'{stage}_{case}'] = dict(source_record_id=r['metadata']['source_record_id'],
                record_hash=digest(r),
                batch_item_ids=m['batch_item_ids'], original_split=m['split'], question=(r.get('messages') or r['prompt'])[1]['content'],
                measurement=m, runtime_stress_fixture_only=True, split_reassignment=False)
            cfg = copy.deepcopy(config)
            if case == 'control_old':
                old_template = load_config(template, stage)
                for key in LIMITS[stage]:
                    cfg['training'][key] = old_template['training'][key]
            cfg['training'].update(output_dir=str(directory / 'outputs' / f'{stage}_{case}'),
                max_steps=2, gradient_accumulation_steps=1, warmup_steps=0, warmup_ratio=0,
                eval_strategy='no', save_strategy='no', logging_steps=1, disable_tqdm=True)
            cfg['profiling'] = {'enabled': True, 'output': str(directory / 'metrics' / f'{stage}_{case}_profile.json')}
            if stage == 'dpo':
                cfg['model']['adapter_path'] = str(directory / 'bootstrap_sft')
                cfg['reference'] = {'mode': 'initial_policy', 'strategy': 'shared_adapter'}
            configurations[f'{stage}_{case}'] = cfg
    directory.mkdir(parents=True)
    for name in ('configs', 'logs', 'metrics', 'outputs'):
        (directory / name).mkdir()
    for name, config in configurations.items():
        path = directory / 'configs' / f'{name}.yaml'
        path.write_text(yaml.safe_dump(config, sort_keys=False))
        frozen[str(path)] = sha256(path)
    write(directory / 'token_validation.json', dict(selected_limits=LIMITS, total_export_records=67,
          truncation_count=0, overflow_count=0, stages=reports, GPU_training_performed_by_prepare=False))
    write(directory / 'selections.json', selections)
    frozen[str(directory / 'selections.json')] = sha256(directory / 'selections.json')
    frozen[str(directory / 'token_validation.json')] = sha256(directory / 'token_validation.json')
    write(directory / 'manifest.json', dict(**meta, experiment=directory.name, frozen_files=frozen,
          approval_scope='Token preflight and disposable 2 optimizer-step LR0 probes only; no pilot_003 training',
          corpus=str(corpus), selected_limits=LIMITS, container_image='sha256:89154ef00dd15368d2b293c167e5cc7dbb521fcfb2fbb77510e0d4df2b820e8f',
          no_corpus_or_old_config_changes=True, no_production_changes=True))
    verify(directory)
    print(json.dumps({'prepared': str(directory), 'limits': LIMITS, 'selections': selections}, ensure_ascii=False))


def run(directory, stage, case):
    """Use actual TRL trainers/AdamW; LR0 guarantees no validation learning."""
    directory = Path(directory).resolve()
    verify(directory)
    import torch
    from transformers import TrainerCallback
    from training.profiling import RunProfile
    from training.train_dpo import adapter_digest
    if not torch.cuda.is_available() or 'Thor' not in torch.cuda.get_device_name():
        raise RuntimeError('This evidence run requires the actual Thor GPU')
    config = load_config(directory / 'configs' / f'{stage}_{case}.yaml', stage)
    # Generic config validation intentionally requires positive LR. The probe's
    # LR0 is an explicit runtime-only override, not a relaxed training contract.
    config['training']['learning_rate'] = 0.0
    records, manifest = load_records(config, stage)
    selection = json.loads((directory / 'selections.json').read_text())[f'{stage}_{case}']
    record = next(r for r in records[selection['original_split']] if digest(r) == selection['record_hash'])
    # DPO can have several negatives for one question; use the sealed full row.
    tokenizer = tokenizer_for(config)
    records_one = {'train': [], 'valid': []}
    measured = token_rows(tokenizer, {'train': [record], 'valid': []}, config, stage)[0]
    if measured['total'] != selection['measurement']['total'] or measured['current_limit_failures']:
        raise ValueError('Stress record token guard failed')
    evidence = {'stage': stage, 'case': case, 'selection': selection, 'learning_rate': 0,
                'not_quality_training': True, 'corpus_split_changed': False, 'optimizer_evidence': [], 'OOM': False}
    initial = {}
    class Probe(TrainerCallback):
        def on_train_begin(self, args, state, control, model=None, **kwargs):
            name = 'policy' if stage == 'dpo' else 'default'
            initial['hash'] = adapter_digest(model, name)
        def on_optimizer_step(self, args, state, control, model=None, optimizer=None, **kwargs):
            grads = [p.grad for p in model.parameters() if p.requires_grad and p.grad is not None]
            finite = bool(grads) and bool(torch.stack([torch.isfinite(g).all() for g in grads]).all().item())
            states = [s['exp_avg'] for s in optimizer.state.values() if 'exp_avg' in s]
            finite_state = bool(states) and bool(torch.stack([torch.isfinite(s).all() for s in states]).all().item())
            if not finite or not finite_state:
                raise RuntimeError('Missing/nonfinite gradient or AdamW state')
            evidence['optimizer_evidence'].append(dict(step=state.global_step + 1, finite_gradients=finite,
                                                       finite_adamw_state=finite_state, state_tensor_count=len(states)))
    def capture(trainer, tokenizer, cfg, dataset_manifest, saved_stage):
        name = 'policy' if stage == 'dpo' else 'default'
        evidence.update(initial_policy_hash=initial['hash'], final_policy_hash=adapter_digest(trainer.model, name),
                        global_step=trainer.state.global_step, trainer_history=trainer.state.log_history)
        if evidence['initial_policy_hash'] != evidence['final_policy_hash']:
            raise RuntimeError('LR0 stress probe changed adapter weights')
        # CPU record-level guard is supplemented by actual TRL data/collator lengths.
        encoded = trainer.train_dataset[0]
        if stage == 'sft':
            p = render_records(tokenizer, [record], config, stage)[0]['prompt']
            pids = tokenizer(p, add_special_tokens=False)['input_ids']
            completion_ids = tokenizer(record['messages'][-1]['content'] + tokenizer.eos_token, add_special_tokens=False)['input_ids']
            ids = encoded['input_ids']
            if ids[:len(pids)] != pids or ids[len(pids):] != completion_ids:
                raise RuntimeError('TRL truncated/changed SFT prompt/completion')
            evidence['actual_trl_lengths'] = {'input_ids': len(ids), 'supervised_completion_tokens': sum(encoded['completion_mask'])}
        else:
            expected = render_records(tokenizer, [record], config, stage)[0]
            expected_ids = {k: tokenizer(expected[k], add_special_tokens=False)['input_ids'] for k in ('prompt', 'chosen', 'rejected')}
            for key in ('prompt', 'chosen', 'rejected'):
                actual = encoded[f'{key}_input_ids']
                wanted = expected_ids[key]
                # TRL DPO appends EOS to completion, preserves full prompt.
                if key != 'prompt' and (not wanted or wanted[-1] != tokenizer.eos_token_id):
                    wanted = wanted + [tokenizer.eos_token_id]
                if actual != wanted:
                    raise RuntimeError(f'TRL truncated/changed DPO {key}')
            evidence['actual_trl_lengths'] = {k: len(encoded[f'{k}_input_ids']) for k in ('prompt', 'chosen', 'rejected')}
        if stage == 'sft' and case == 'control_old':
            from training.trainer_common import save_run
            bootstrap = copy.deepcopy(cfg)
            bootstrap['training']['output_dir'] = str(directory / 'bootstrap_sft')
            save_run(trainer, tokenizer, bootstrap, dataset_manifest, saved_stage)
            write(directory / 'bootstrap_sft/SMOKE_ONLY.json', {'never_use_for_pilot': True, 'LR': 0})
    records_one['train'] = [record]
    module = __import__(f'training.train_{stage}', fromlist=['train'])
    profile = RunProfile(config, stage)
    error = None
    try:
        with patch.object(module, 'save_run', capture):
            module.train(SimpleNamespace(resume_from_checkpoint=None), config, records_one, manifest, profile, callbacks=[Probe()])
        if len(evidence['optimizer_evidence']) != 2 or evidence.get('global_step') != 2:
            raise RuntimeError('Two actual optimizer steps required')
        evidence['status'] = 'PASS'
    except BaseException as exc:
        error = exc
        evidence.update(status='FAIL', error=f'{type(exc).__name__}: {exc}', OOM=isinstance(exc, torch.cuda.OutOfMemoryError))
        raise
    finally:
        profile.finish(error)
        write(directory / 'metrics' / f'{stage}_{case}_evidence.json', evidence)
    verify(directory)
    print(json.dumps({'smoke_evidence': evidence}, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--corpus', default='training/annotations/generated/corpora/reviewed_gold_v003')
    parser.add_argument('--stage', choices=('sft', 'dpo'))
    parser.add_argument('--case', choices=CASES)
    args = parser.parse_args(argv)
    if args.prepare:
        if args.stage or args.case:
            parser.error('--prepare does not run training')
        prepare(args.directory, args.corpus)
    else:
        if not args.stage or not args.case:
            parser.error('Probe requires --stage and --case')
        run(args.directory, args.stage, args.case)


if __name__ == '__main__':
    main()
