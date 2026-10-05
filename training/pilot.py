"""Bounded pilot orchestration, reusing production evaluation and existing trainers.

Artifacts are local and ignored. Never changes prompts, gold, runtime rules or
system settings. Run freeze BEFORE inference; checkpoint selection uses ONLY
the three SFT validation questions, never the external diagnostic corpus.
"""
import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path

import yaml

from training.data.common import production_prompt, provenance, read_jsonl, sha256
from training.data.canonicalize import flatten_source, semantic_key, serialize_planner_target
from training.data.split import check_split, question_key, template_key

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'training/experiments/thor_pilot_001'


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def gold_item(row, split):
    import evaluate_planner as E
    from geoflow.grounding import parse_grounding
    from geoflow.composer import MacroComposer
    gold = json.loads(row['messages'][-1]['content'])
    question = row['messages'][1]['content']
    if gold.get('unsupported'):
        concepts, macros, operators = [], ['NONE'], []
    else:
        grounding = parse_grounding(gold, question)
        concepts = E.concept_keys(grounding)
        macros, operators = E.corpus_labels(MacroComposer().compose(grounding))
    return dict(id=row['metadata']['source_record_id'], question=question, golden=gold,
                expected_concepts=concepts, expected_macros=macros, expected_operators=operators,
                family=row['metadata']['parent_intent'], split=split, cohorts=[split])


def audit(sft, dpo):
    check_split(sft['train'], sft['valid'])
    check_split(dpo['train'], dpo['valid'])
    if {template_key(r) for r in sft['train']} & {template_key(r) for r in sft['valid']}:
        raise ValueError('SFT semantic template leakage')
    for split in ('train', 'valid'):
        questions = [question_key(r['messages'][1]['content']) for r in sft[split]]
        if len(questions) != len(set(questions)):
            raise ValueError('SFT duplicate question')
        parents = {r['metadata']['source_record_id']: r['metadata']['parent_intent'] for r in sft[split]}
        gold_by_id = {r['metadata']['source_record_id']: r for r in sft[split]}
        seen = set()
        for row in dpo[split]:
            if row['metadata']['source_record_id'] not in parents or parents[row['metadata']['source_record_id']] != row['metadata']['parent_intent']:
                raise ValueError('DPO did not inherit SFT split')
            chosen, rejected = (json.loads(row[k][0]['content']) for k in ('chosen', 'rejected'))
            gold = gold_by_id[row['metadata']['source_record_id']]
            if row['prompt'] != gold['messages'][:2] or semantic_key(chosen) != semantic_key(json.loads(gold['messages'][-1]['content'])):
                raise ValueError('DPO prompt/chosen does not match SFT gold')
            if semantic_key(chosen, infer_events=True) == semantic_key(rejected, infer_events=True):
                raise ValueError('Identical DPO preference pair')
            signature = (row['prompt'][1]['content'], row['chosen'][0]['content'], row['rejected'][0]['content'])
            if signature in seen:
                raise ValueError('Duplicate DPO pair')
            seen.add(signature)
    return {'passed': True, 'checks': ['parent split', 'question split', 'template split', 'DPO inherited split', 'unique SFT questions', 'unique DPO pairs', 'chosen != rejected'],
            'note': 'DPO repeats a question with different negatives intentionally.'}


def freeze(directory):
    from training.evaluate_checkpoint import load_items
    if (directory / 'manifest.json').exists():
        raise ValueError('Experiment already frozen; choose a new directory')
    sft = {s: read_jsonl(ROOT / f'training/generated/sft_{s}.jsonl') for s in ('train', 'valid')}
    dpo = {s: read_jsonl(ROOT / f'training/generated/dpo_{s}.jsonl') for s in ('train', 'valid')}
    result = audit(sft, dpo)
    train_questions = {question_key(r['messages'][1]['content']) for r in sft['train']}
    train_templates = {template_key(r) for r in sft['train']}
    # Coverage chosen before Base inference, one paraphrase per family. Never
    # train on this corpus, and never use it to choose a checkpoint.
    prefixes = ('w01_', 'w02_', 'w03_', 'w05_', 'w06_', 'w07_', 'w09_', 'w12_',
                'w19_', 'w22_', 'w26_', 'w27_', 'w32_', 'w35_', 'w36_', 'w37_',
                'w38_', 'w39_', 'w40_', 'w42_', 'w28_', 'w34_')
    external, excluded = [], []
    for item in load_items(ROOT / 'evaluation/v2/paraphrases_holdout_v2.yaml'):
        if not item['id'].endswith('_p0') or not item['id'].startswith(prefixes):
            continue
        raw = flatten_source(item['golden'])
        target = serialize_planner_target(raw)
        template = template_key({'messages': [{'content': target}]})
        overlap = template in train_templates
        if question_key(item['question']) in train_questions:
            raise ValueError('Train/evaluation exact-question leakage')
        if overlap and not raw.get('unsupported'):
            excluded.append({'id': item['id'], 'reason': 'training semantic template'})
            continue
        item = copy.deepcopy(item)
        item.update(split='external_refusal_diagnostic' if overlap else 'external',
                    training_family_overlap=overlap)
        external.append(item)
    if not external:
        raise ValueError('No independent evaluation items selected')
    items = [gold_item(r, split) for split in ('train', 'valid') for r in sft[split]] + external
    directory.mkdir(parents=True, exist_ok=True)
    write(directory / 'items.json', items)
    paths = [Path(f'training/generated/{stage}_{s}.jsonl') for stage in ('sft', 'dpo') for s in ('train', 'valid')]
    paths += [Path(p) for p in ('training/generated/manifest.json', 'evaluation/v2/paraphrases_holdout_v2.yaml', 'evaluation/v2/holdout_v2_parents.yaml', 'evaluation/corpus_registry.yaml')]
    meta = provenance(paths, 42)
    model = yaml.safe_load((ROOT / 'training/configs/qwen3_8b_thor_sft.yaml').read_text())['model']
    meta.update(experiment=directory.name, model=model['name_or_path'], model_revision=model['revision'],
                tokenizer=f"{model['name_or_path']}@{model['revision']}",
                decoding={'do_sample': False, 'max_new_tokens': 1024, 'use_cache': True, 'enable_thinking': False, 'seed': 42},
                audit=result, corpus_counts=dict(Counter(i['split'] for i in items)), excluded_external=excluded,
                evaluation_role='development, unreviewed; no final benchmark claim; refusal diagnostics overlap training family',
                selection='Validation only: grounding exact, factor exact, role, concept, downstream validation, JSON, validation loss, earlier step tie-break.',
                container_image='sha256:89154ef00dd15368d2b293c167e5cc7dbb521fcfb2fbb77510e0d4df2b820e8f')
    for path in paths:
        dest = directory / 'snapshot' / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    # git diff alone excludes untracked training code; copy all source files too.
    files = subprocess.check_output(['git', 'ls-files', '-c', '-o', '--exclude-standard'], cwd=ROOT, text=True).splitlines()
    hashes = {}
    for name in sorted(set(files)):
        path = ROOT / name
        if not path.is_file() or path.suffix not in {'.py', '.yaml', '.yml', '.txt', '.md'}:
            continue
        dest = directory / 'source_snapshot' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        hashes[name] = sha256(path)
    meta['source_snapshot_hashes'] = hashes
    (directory / 'git.diff').write_bytes(subprocess.check_output(['git', 'diff', 'HEAD'], cwd=ROOT))
    (directory / 'git.status').write_bytes(subprocess.check_output(['git', 'status', '--short'], cwd=ROOT))
    write(directory / 'manifest.json', meta)
    print(json.dumps({'frozen': str(directory), 'counts': meta['corpus_counts'], 'excluded': excluded}, ensure_ascii=False))


def verify(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    if hashlib.sha256(production_prompt().encode()).hexdigest() != manifest['prompt_hash']:
        raise ValueError('Frozen prompt drift')
    for name, digest in manifest['source_files'].items():
        if sha256(name) != digest:
            raise ValueError(f'Frozen data drift: {name}')
    for name, digest in manifest['definition_hashes'].items():
        if sha256(ROOT / name) != digest:
            raise ValueError(f'Frozen production definition drift: {name}')
    return manifest


def errors(record):
    categories = []
    raw = record.get('raw_text') or ''
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            categories.append('syntax')
    except (ValueError, TypeError):
        categories.append('syntax')
    if record.get('json_parse_ok') and not record.get('planner_contract_ok'):
        categories.append('schema')
    if record.get('planner_contract_ok') and record.get('grounding_exact') is False:
        categories.append('semantic')
    if not record.get('expected_unsupported') and (not record.get('composed') or not record.get('validated') or record.get('executed') is False):
        categories.append('downstream')
    return categories


def evaluate(directory, label, adapter, splits):
    import evaluate_planner as E
    from training.inference import HFClient
    from training.evaluate_checkpoint import evaluate as existing_evaluate
    from build import build
    from tool_executor import ToolExecutor
    from tool_handlers import get_tool_handlers
    manifest = verify(directory)
    evaluator_hash = sha256(ROOT / 'evaluate_planner.py')
    all_items = json.loads((directory / 'items.json').read_text())
    items = [i for i in all_items if i['split'] in splits]
    adapter_hash = None
    if adapter:
        adapter_hash = hashlib.sha256((sha256(Path(adapter) / 'adapter_model.safetensors') + sha256(Path(adapter) / 'adapter_config.json')).encode()).hexdigest()
    cache = {}
    if adapter:
        for path in sorted((directory / 'metrics').glob('*.json')):
            previous = json.loads(path.read_text())
            metadata = previous.get('metadata', {})
            if (metadata.get('adapter') == adapter and metadata.get('adapter_hash') == adapter_hash and metadata.get('complete')
                    and metadata.get('evaluator_hash') == evaluator_hash
                    and metadata.get('decoding') == manifest['decoding']
                    and metadata.get('prompt_hash') == manifest['prompt_hash']
                    and metadata.get('model_revision') == manifest['model_revision']):
                for row in previous.get('records', []):
                    cache[row['id']] = (row, path.name)
    client = HFClient(manifest['model'], adapter=adapter, revision=manifest['model_revision'], max_new_tokens=manifest['decoding']['max_new_tokens'], seed=manifest['seed'])
    effective_generation = client.policy.generation_config.to_dict()
    effective_generation.update(manifest['decoding'], pad_token_id=client.tokenizer.pad_token_id)
    write(directory / 'metrics' / f'{label}_generation_config.json', effective_generation)
    validation_loss = None
    preference_accuracy = None
    if adapter:
        state_path = Path(adapter) / 'trainer_state.json'
        if not state_path.exists():
            state_path = Path(adapter).parent / 'trainer_state.json'
        if state_path.exists():
            history = json.loads(state_path.read_text())['log_history']
            losses = [r['eval_loss'] for r in history if 'eval_loss' in r]
            validation_loss = losses[-1] if losses else None
            preferences = [r['eval_rewards/accuracies'] for r in history if 'eval_rewards/accuracies' in r]
            preference_accuracy = preferences[-1] if preferences else None
    executor = ToolExecutor(tools=build()[0], handlers=get_tool_handlers('reference'), provider='reference')
    records = []
    output = directory / 'metrics' / f'{label}.json'
    for item in items:
        start = time.perf_counter()
        reused = cache.get(item['id'])
        if reused and reused[0]['question'] == item['question'] and reused[0]['gold'] == item['golden']:
            record = copy.deepcopy(reused[0])
            record['reused_generation_from'] = reused[1]
        else:
            record = existing_evaluate(client, [item], execute=True, tool_executor=executor)['records'][0]
            record.update(question=item['question'], gold=item['golden'], split=item['split'], error_categories=errors(record))
        records.append(record)
        grouped = {split: E.summarize([r for r in records if r['split'] == split]) for split in splits if any(r['split'] == split for r in records)}
        write(output, {'metadata': {'label': label, 'adapter': adapter, 'adapter_hash': adapter_hash, 'evaluator_hash': evaluator_hash, 'validation_loss': validation_loss, 'preference_observation_accuracy': preference_accuracy, 'decoding': manifest['decoding'], 'prompt_hash': manifest['prompt_hash'], 'model_revision': manifest['model_revision'], 'complete': len(records) == len(items), 'attention': client.policy.config._attn_implementation, 'execution': 'synthetic reference provider, pipeline execution only'}, 'summary': E.summarize(records), 'by_split': grouped, 'by_intent': {r['intent_id']: E.summarize([x for x in records if x['intent_id'] == r['intent_id']]) for r in records}, 'records': records})
        print(json.dumps({'label': label, 'id': item['id'], 'split': item['split'], 'exact': record.get('grounding_exact'), 'factor': record.get('factor_exact'), 'status': record['status'], 'reused': bool(reused), 'seconds': round(time.perf_counter()-start, 2)}, ensure_ascii=False), flush=True)
    errfile = directory / 'errors' / f'{label}_errors.jsonl'
    errfile.parent.mkdir(parents=True, exist_ok=True)
    errfile.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records if r['error_categories']), encoding='utf-8')
    print(json.dumps({'label': label, 'by_split': grouped}, ensure_ascii=False), flush=True)


def run_train(directory, stage, config_path, stop_step, resume):
    from training.trainer_common import cli
    from training.profiling import RunProfile
    from transformers import TrainerCallback
    frozen = verify(directory)
    argv = ['--config', config_path]
    if resume:
        argv += ['--resume-from-checkpoint', resume]
    args, config, records, manifest = cli(stage, argv)
    if config['model']['name_or_path'] != frozen['model'] or config['model']['revision'] != frozen['model_revision'] or config['training']['seed'] != frozen['seed']:
        raise ValueError('Pilot model/revision/seed differs from frozen Base')
    if config.get('lora', {}).get('r') != 16:
        raise ValueError('This pilot fixes LoRA rank at 16')
    # Select a frozen balanced observation subset only AFTER full dataset guards.
    # Final preference analysis always uses all 24 validation pairs.
    if stage == 'dpo':
        indices = json.loads((directory / 'dpo_observation_indices.json').read_text())
        records['valid'] = [records['valid'][i] for i in indices]
    class BoundedStop(TrainerCallback):
        def on_step_end(self, args, state, control, **kwargs):
            if stop_step and state.global_step >= stop_step:
                control.should_training_stop = True
        def on_train_begin(self, args, state, control, **kwargs):
            print(json.dumps({'resume_start_global_step': state.global_step, 'planned_horizon': args.max_steps}), flush=True)
    profile = RunProfile(config, stage)
    error = None
    try:
        from importlib import import_module
        import_module(f'training.train_{stage}').train(args, config, records, manifest, profile, callbacks=[BoundedStop()])
    except BaseException as exc:
        error = exc
        raise
    finally:
        profile.finish(error)


def configs(directory, stage, adapter=None):
    verify(directory)
    base = yaml.safe_load((ROOT / f'training/configs/qwen3_8b_thor_{stage}.yaml').read_text())
    combinations = [(5e-5, None), (1e-4, None), (2e-4, None)] if stage == 'sft' else [(5e-6, .1), (5e-6, .05), (1e-5, .1)]
    if stage == 'dpo':
        if not adapter:
            raise ValueError('DPO requires the selected SFT adapter')
        rows = read_jsonl(base['data']['valid'])
        indices = []
        parents = sorted({r['metadata']['parent_intent'] for r in rows})
        for category in ('semantic', 'constraint'):
            for parent in parents:
                candidates = [i for i, row in enumerate(rows) if row['metadata']['negative_category'] == category
                              and row['metadata']['parent_intent'] == parent]
                if not candidates:
                    raise ValueError(f'No {category} observation pair for parent {parent}')
                indices.append(candidates[0])
        write(directory / 'dpo_observation_indices.json', indices)
    outputs = []
    for number, (lr, beta) in enumerate(combinations, 1):
        config = copy.deepcopy(base)
        name = f'{stage}_{number}'
        if adapter:
            config['model']['adapter_path'] = adapter
        t = config['training']
        t.update(output_dir=str(directory / 'checkpoints' / name), max_steps=12 if stage == 'sft' else 6,
                 gradient_accumulation_steps=1, learning_rate=lr, warmup_ratio=0, warmup_steps=1,
                 eval_strategy='steps', eval_steps=2, save_strategy='steps', save_steps=2,
                 save_total_limit=6, logging_steps=1, disable_tqdm=True)
        if beta:
            t['beta'] = beta
        config['profiling']['output'] = str(directory / 'metrics' / f'{name}_profile.json')
        path = directory / 'configs' / f'{name}.yaml'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
        outputs.append(str(path))
    write(directory / f'{stage}_plan.json', {'configs': outputs, 'horizon': 12 if stage == 'sft' else 6, 'initial_stop': 6, 'effective_batch': 1, 'reason': 'Step observations with bounded compute; batch 1, accumulation 1 pilot only; generic profiles unchanged.'})
    print(json.dumps(outputs))


def selection_key(report, step=0):
    s = report['by_split']['valid']
    def metric(key):
        value = s.get(key)
        return -1 if value is None else value
    # Semantic exact includes concepts, roles, source, factor values and OD.
    metadata = report.get('metadata', {})
    if metadata.get('label', '').startswith('dpo_'):
        pref = metadata.get('preference_observation_accuracy')
        extra = pref if pref is not None else -1
    else:
        loss = metadata.get('validation_loss')
        extra = -loss if loss is not None else -1e30
    return tuple(metric(k) for k in ('grounding_exact_match', 'factor_exact_match', 'role_accuracy', 'concept_accuracy', 'validation_pass_rate', 'json_parse_rate')) + (extra, -step)


def select(directory, stage):
    import re
    candidates = []
    for path in sorted((directory / 'metrics').glob(f'{stage}_*_step*.json')):
        if not re.fullmatch(rf'{stage}_\d+_step\d+', path.stem):
            continue
        report = json.loads(path.read_text())
        if not report['metadata']['complete']:
            raise ValueError(f'Incomplete checkpoint evaluation {path}')
        step = int(path.stem.split('step')[-1])
        candidates.append((selection_key(report, step), path, report))
    if not candidates:
        raise ValueError('No validation generation results')
    key, path, report = max(candidates, key=lambda c: c[0])
    selected = {'stage': stage, 'label': path.stem, 'adapter': report['metadata']['adapter'], 'key': key, 'metrics': report['by_split']['valid'], 'criterion': 'Actual validation grounding exact first; no training loss or external corpus used; earlier step tie-break'}
    write(directory / f'best_{stage}.json', selected)
    print(json.dumps(selected, ensure_ascii=False))


def preferences(directory, config_path, adapter, label, splits=('valid', 'train')):
    """Per-pair metrics from TRL itself, with the SAME frozen initial SFT reference.

    Batch size one retains per-negative statistics; no alternative objective,
    reward model, logits approximation or reference-free comparison is used.
    """
    import torch
    from datasets import Dataset
    from peft import PeftModel, set_peft_model_state_dict
    from safetensors.torch import load_file
    from trl import DPOConfig, DPOTrainer
    from training.trainer_common import load_config, load_records, model_for, tokenizer_for, render_records
    from training.train_dpo import initialize_reference_adapter, adapter_digest
    verify(directory)
    config = load_config(config_path, 'dpo')
    records, _ = load_records(config, 'dpo')
    tokenizer = tokenizer_for(config)
    data = {s: Dataset.from_list(render_records(tokenizer, rows, config, 'dpo')) for s, rows in records.items()}
    model = PeftModel.from_pretrained(model_for(config), config['model']['adapter_path'], adapter_name='policy', is_trainable=False)
    reference_hash = initialize_reference_adapter(model, config['model']['adapter_path'])
    state = load_file(str(Path(adapter) / 'adapter_model.safetensors'))
    set_peft_model_state_dict(model, state, adapter_name='policy')
    model.set_adapter('policy')
    training = dict(config['training'])
    training.pop('resume_from_checkpoint', None)
    training.update(output_dir=str(directory / 'preference_temp'), eval_strategy='no', save_strategy='no', report_to='none',
                    model_adapter_name='policy', ref_adapter_name='reference', precompute_ref_log_probs=False,
                    per_device_eval_batch_size=1)
    trainer = DPOTrainer(model=model, ref_model=None, args=DPOConfig(**training), processing_class=tokenizer,
                         train_dataset=data['train'], eval_dataset=data['valid'])
    # Match the BF16 mixed-precision model forward used by TRL evaluation.
    trainer.model = trainer.accelerator.prepare_model(trainer.model, evaluation_mode=True)
    trainer.model.eval()
    output, rows = directory / 'metrics' / f'{label}_preferences.json', []
    for split in splits:
        loader = trainer.get_eval_dataloader(trainer.eval_dataset if split == 'valid' else trainer.train_dataset)
        for index, batch in enumerate(loader):
            batch = trainer._prepare_inputs(batch)
            with torch.no_grad(), trainer.accelerator.autocast():
                loss, metrics = trainer.get_batch_loss_metrics(trainer.model, batch, train_eval='eval')
            meta = records[split][index]['metadata']
            row = {'split': split, 'index': index, 'source_record_id': meta['source_record_id'],
                   'negative_category': meta['negative_category'], 'negative_type': meta['negative_type'],
                   'loss': float(loss), 'chosen_reward': metrics['eval_rewards/chosen'],
                   'rejected_reward': metrics['eval_rewards/rejected'], 'margin': metrics['eval_rewards/margins'],
                   'correct': bool(metrics['eval_rewards/accuracies'])}
            rows.append(row)
            grouped = {}
            for s in ('train', 'valid'):
                members = [r for r in rows if r['split'] == s]
                if not members:
                    continue
                def stats(m):
                    return dict(correct=sum(r['correct'] for r in m), total=len(m),
                                mean_margin=sum(r['margin'] for r in m)/len(m), mean_loss=sum(r['loss'] for r in m)/len(m),
                                ties=sum(r['margin'] == 0 for r in m))
                grouped[s] = {'overall': stats(members), 'by_category': {k: stats([r for r in members if r['negative_category'] == k]) for k in sorted({r['negative_category'] for r in members})},
                              'by_negative_type': {k: stats([r for r in members if r['negative_type'] == k]) for k in sorted({r['negative_type'] for r in members})}}
            write(output, {'label': label, 'adapter': adapter, 'reference_adapter': config['model']['adapter_path'],
                           'reference_hash': reference_hash, 'complete': len(rows) == sum(len(records[s]) for s in splits),
                           'by_split': grouped, 'records': rows})
            print(json.dumps({'label': label, **row}), flush=True)
    if adapter_digest(trainer.model, 'reference') != reference_hash:
        raise ValueError('Reference drift during preference evaluation')
    report = json.loads(output.read_text())
    report['reference_verified_after_evaluation'] = True
    report['policy_hash'] = adapter_digest(trainer.model, 'policy')
    write(output, report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'configs', 'train', 'evaluate', 'select', 'preferences'])
    parser.add_argument('--directory', type=Path, default=DEFAULT)
    parser.add_argument('--stage', choices=['sft', 'dpo'])
    parser.add_argument('--config')
    parser.add_argument('--adapter')
    parser.add_argument('--label')
    parser.add_argument('--splits', nargs='+', default=['train', 'valid', 'external', 'external_refusal_diagnostic'])
    parser.add_argument('--stop-step', type=int, default=0)
    parser.add_argument('--resume-from-checkpoint')
    args = parser.parse_args(argv)
    directory = args.directory
    if (directory / 'manifest.json').exists():
        from datetime import datetime, timezone
        entry = {'at': datetime.now(timezone.utc).isoformat(), 'action': args.action, 'stage': args.stage, 'label': args.label,
                 'config': args.config, 'config_hash': sha256(args.config) if args.config else None,
                 'pilot_helper_hash': sha256(__file__), 'resume': args.resume_from_checkpoint, 'stop_step': args.stop_step}
        with (directory / 'commands.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(entry) + '\n')
    if args.action == 'freeze':
        freeze(directory)
    elif args.action == 'configs':
        configs(directory, args.stage, args.adapter)
    elif args.action == 'train':
        run_train(directory, args.stage, args.config, args.stop_step, args.resume_from_checkpoint)
    elif args.action == 'evaluate':
        evaluate(directory, args.label, args.adapter, args.splits)
    elif args.action == 'preferences':
        preferences(directory, args.config, args.adapter, args.label, [s for s in args.splits if s in ('valid', 'train')])
    else:
        select(directory, args.stage)


if __name__ == '__main__':
    main()
