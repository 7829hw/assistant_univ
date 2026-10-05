"""Export paired pilot error analysis and counts from existing evaluator records."""
import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from training.data.canonicalize import flatten_source
from training.pilot import DEFAULT, write


def counts(records):
    """Expose existing matched/expected fields; do not implement new scoring."""
    result = {}
    for key, field in [('JSON parse', 'json_parse_ok'), ('Contract pass', 'planner_contract_ok'),
                       ('Grounding exact', 'grounding_exact'), ('Factor exact', 'factor_exact'),
                       ('Compose success', 'composed'), ('Validation', 'validated'),
                       ('Execution', 'executed'), ('Repair attempted', 'repair_attempted')]:
        values = [r.get(field) for r in records if r.get(field) is not None]
        result[key] = {'matched': sum(bool(v) for v in values), 'total': len(values)}
    for name in ('concept', 'subtype', 'role'):
        result[name.title()] = {'matched': sum(r['concept_score'][name]['matched'] for r in records),
                               'total': sum(r['concept_score'][name]['expected'] for r in records)}
    for name in ('macro', 'operator'):
        result[name.title()] = {'matched': sum(r[f'{name}_score']['matched'] for r in records),
                               'total': sum(r[f'{name}_score']['expected'] for r in records)}
    result['Macro exact'] = {'matched': sum(bool(r['macro_score'].get('exact')) for r in records),
                             'total': len(records)}
    attempts = [r for r in records if r.get('repair_attempted')]
    result['Repair success'] = {'matched': sum(bool(r.get('repair_succeeded')) for r in attempts),
                                'total': len(attempts)}
    for name, denominator in (('Factor precision', 'predicted'), ('Factor recall', 'expected')):
        scores = [r['factor_score'] for r in records if r.get('factor_score') is not None]
        result[name] = {'matched': sum(s['matched'] for s in scores), 'total': sum(s[denominator] for s in scores)}
    checked = [r for r in records if r.get('checked_rules')]
    from geoflow.validator import ALL_RULES
    for rule in ALL_RULES:
        result[rule] = {'matched': sum(rule not in r.get('validation_codes', []) for r in checked), 'total': len(checked)}
    tp = sum(r.get('predicted_unsupported', False) and r.get('expected_unsupported', False) for r in records)
    for name, field in [('Unsupported precision', 'predicted_unsupported'), ('Unsupported recall', 'expected_unsupported')]:
        result[name] = {'matched': tp, 'total': sum(r.get(field, False) for r in records)}
    result['Executed / all questions'] = {'matched': sum(r.get('executed') is True for r in records),
                                          'total': len(records)}
    return result


def error_features(record):
    """Annotation triage hints from raw fields, not an additional accuracy metric."""
    try:
        pred = json.loads(record['raw_text'])
    except (ValueError, TypeError):
        return ['format']
    gold = flatten_source(record['gold'])
    if gold.get('unsupported'):
        return [] if pred.get('unsupported') else ['unsupported:forced_support']
    if pred.get('unsupported'):
        return ['unsupported:false_refusal']
    hints = []
    for key, value in gold['factors'].items():
        if key not in pred.get('factors', {}):
            hints.append(f'factor:missing:{key}')
        elif value != pred['factors'][key]:
            hints.append(f'factor:wrong:{key}')
    for key in pred.get('factors', {}):
        if key not in gold['factors']:
            hints.append(f'factor:extra:{key}')
    def concepts(p, fields):
        return Counter(tuple(c.get(k) for k in fields) for c in p.get('concepts', []))
    if concepts(pred, ('concept', 'subtype')) != concepts(gold, ('concept', 'subtype')):
        hints.append('concept/subtype')
    if concepts(pred, ('concept', 'subtype', 'role')) != concepts(gold, ('concept', 'subtype', 'role')):
        hints.append('role_or_concept')
    if concepts(pred, ('concept', 'subtype', 'source')) != concepts(gold, ('concept', 'subtype', 'source')):
        hints.append('source_or_concept')
    return hints


def paired(base, sft, dpo):
    maps = [{r['id']: r for r in run['records']} for run in (base, sft, dpo)]
    if any(set(m) != set(maps[0]) for m in maps[1:]):
        raise ValueError('Final comparison requires identical questions')
    groups = {k: [] for k in ('base_to_sft_improvements', 'sft_to_dpo_improvements', 'sft_to_dpo_regressions', 'all_failed')}
    for identifier in maps[0]:
        b, s, d = (m[identifier] for m in maps)
        if any((r['question'], r['gold']) != (b['question'], b['gold']) for r in (s, d)):
            raise ValueError('Paired question/gold mismatch')
        row = {'id': identifier, 'question': b['question'], 'gold': b['gold'], 'split': b['split'],
               'base': b['raw_text'], 'sft': s['raw_text'], 'dpo': d['raw_text'],
               'exact': {k: r['grounding_exact'] for k, r in zip(('base', 'sft', 'dpo'), (b, s, d))},
               'validation_codes': {k: r['validation_codes'] for k, r in zip(('base', 'sft', 'dpo'), (b, s, d))}}
        if not b['grounding_exact'] and s['grounding_exact']:
            groups['base_to_sft_improvements'].append(row)
        if not s['grounding_exact'] and d['grounding_exact']:
            groups['sft_to_dpo_improvements'].append(row)
        if s['grounding_exact'] and not d['grounding_exact']:
            groups['sft_to_dpo_regressions'].append(row)
        if not any(r['grounding_exact'] for r in (b, s, d)):
            groups['all_failed'].append(row)
    return groups


def export(directory):
    if not (directory / 'pilot_completed.json').exists():
        raise ValueError('Pilot is incomplete; do not issue a final comparison')
    runs = {name: json.loads((directory / 'metrics' / f'{label}.json').read_text())
            for name, label in [('Base', 'base'), ('SFT', 'sft_best'), ('SFT+DPO', 'dpo_best')]}
    for run in runs.values():
        if not run['metadata']['complete']:
            raise ValueError('Incomplete generation report')
    groups = paired(*runs.values())
    error_dir = directory / 'errors'
    error_dir.mkdir(exist_ok=True)
    for name, members in groups.items():
        (error_dir / f'{name}.jsonl').write_text(''.join(json.dumps(m, ensure_ascii=False)+'\n' for m in members), encoding='utf-8')
    for name, run in runs.items():
        hints = Counter(h for r in run['records'] if not r['grounding_exact'] for h in error_features(r))
        write(error_dir / f'{name.replace("+", "_")}_coverage_errors.json', dict(hints))
    split_counts = {name: {split: counts([r for r in run['records'] if r['split'] == split]) for split in run['by_split']}
                    for name, run in runs.items()}
    write(directory / 'metrics' / 'comparison_counts.json', split_counts)
    # Reuse the same matched/expected fields within measure groups. Keep the
    # external development subset separate from checkpoint-selection questions.
    measure_counts = {}
    for name, run in runs.items():
        grouped = {}
        for row in run['records']:
            if row['split'] != 'external':
                continue
            group = ','.join(sorted(c['subtype'] for c in row['gold'].get('concepts', [])
                                    if c['role'] == 'MEASURE')) or 'unsupported'
            grouped.setdefault(group, []).append(row)
        measure_counts[name] = {group: counts(rows) for group, rows in grouped.items()}
    write(directory / 'metrics' / 'comparison_by_measure.json', measure_counts)
    write(directory / 'metrics' / 'paired_counts.json', {k: {'all': len(v), 'by_split': dict(Counter(r['split'] for r in v))} for k, v in groups.items()})
    sft_by_id = {r['id']: r for r in runs['SFT']['records']}
    field_changes = []
    for d in runs['SFT+DPO']['records']:
        s = sft_by_id[d['id']]
        fields = ('planner_contract_ok', 'concept_score', 'factor_score', 'composed', 'validated')
        changed = [key for key in fields if s.get(key) != d.get(key)]
        if changed:
            field_changes.append({'id': d['id'], 'question': d['question'], 'split': d['split'],
                                  'gold': d['gold'], 'sft': s['raw_text'], 'dpo': d['raw_text'],
                                  'changed_metrics': changed,
                                  'sft_metrics': {key: s.get(key) for key in fields},
                                  'dpo_metrics': {key: d.get(key) for key in fields}})
    (error_dir / 'sft_to_dpo_field_changes.jsonl').write_text(
        ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in field_changes), encoding='utf-8')
    # Persist histories before intermediate adapter checkpoints are pruned.
    curves, profiles = [], {}
    for stage in ('sft', 'dpo'):
        for number in range(1, 4):
            name = f'{stage}_{number}'
            checkpoints = sorted((directory / 'checkpoints' / name).glob('checkpoint-*'), key=lambda p: int(p.name.split('-')[-1]))
            state = json.loads((checkpoints[-1] / 'trainer_state.json').read_text())
            write(directory / 'metrics' / f'{name}_trainer_state.json', state)
            for entry in state['log_history']:
                if 'loss' in entry or 'eval_loss' in entry:
                    curves.append({'experiment': name, **entry})
            profile = json.loads((directory / 'metrics' / f'{name}_profile.json').read_text())
            profiles[name] = profile
    for path in sorted((directory / 'metrics').glob('*_step*.json')):
        if not re.fullmatch(r'(sft|dpo)_\d+_step\d+', path.stem):
            continue
        report = json.loads(path.read_text())
        curves.append({'experiment': path.stem.rsplit('_step', 1)[0], 'step': int(path.stem.split('step')[-1]),
                       'validation_grounding_correct': sum(r['grounding_exact'] for r in report['records']),
                       'validation_grounding_total': len(report['records']),
                       'validation_json_correct': sum(r['json_parse_ok'] for r in report['records']),
                       'validation_contract_correct': sum(r['planner_contract_ok'] for r in report['records']),
                       'validation_factor_correct': sum(bool(r['factor_exact']) for r in report['records']),
                       **{f'validation_{key}': report['by_split']['valid'].get(key) for key in (
                           'concept_accuracy', 'subtype_accuracy', 'role_accuracy', 'factor_precision', 'factor_recall')}})
    keys = sorted(set().union(*(row.keys() for row in curves)))
    with (directory / 'metrics' / 'learning_curves.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(curves)
    write(directory / 'metrics' / 'learning_curves.json', curves)
    print(json.dumps({'paired_counts': {k: len(v) for k,v in groups.items()}, 'comparison_counts': split_counts}, ensure_ascii=False))


def correct_execution(directory):
    """Replay frozen LIVE generations with production provider profile.

    This corrects compilation/execution only. It cannot change frozen semantic
    scores or select a checkpoint. Only validated plans reached compilation;
    pre-compilation failures retain their actual live records, including repairs.
    """
    import hashlib
    import training.thor_evaluate_planner as E
    from training.evaluate_checkpoint import ReplayClient, evaluate
    from training.data.common import production_prompt
    from training.data.common import sha256
    from build import build
    from tool_executor import ToolExecutor
    from tool_handlers import get_tool_handlers
    from geoflow.providers import profile_for
    items = json.loads((directory / 'items.json').read_text())
    executor = ToolExecutor(tools=build()[0], handlers=get_tool_handlers('reference'), provider='reference')
    comparisons = {}
    for label in ('base', 'sft_best', 'dpo_best', 'sft_last', 'dpo_last'):
        path = directory / 'metrics' / f'{label}.json'
        original = json.loads(path.read_text())
        if not original['metadata'].get('complete'):
            raise ValueError(f'Incomplete generation report: {label}')
        eligible = [r for r in original['records'] if r['validated']]
        if any(r['repair_attempted'] or r['planner_calls'] != 1 for r in eligible):
            raise ValueError('Validated repair plans require a full response trace for execution replay')
        before = directory / 'metrics' / f'{label}_before_profile_correction.json'
        if not before.exists():
            write(before, original)
        selected_items = [i for i in items if i['id'] in {r['id'] for r in eligible}]
        predictions = [{'source_record_id': r['id'], 'question': r['question'], 'raw_text': r['raw_text'],
                        'prompt_hash': hashlib.sha256(production_prompt().encode()).hexdigest()} for r in eligible]
        corrected = evaluate(ReplayClient(predictions), selected_items, execute=True, tool_executor=executor)
        by_id = {r['id']: r for r in corrected['records']}
        rows = []
        for old in original['records']:
            if old['id'] not in by_id:
                # The execution profile cannot affect a plan which never
                # reached compilation. Preserve actual repair outcomes/calls.
                rows.append(old)
                continue
            current = by_id[old['id']]
            for key in ('grounding_exact', 'json_parse_ok', 'planner_contract_ok', 'concept_score', 'factor_score', 'composed', 'validated', 'validation_codes'):
                if current[key] != old[key]:
                    raise ValueError(f'Execution correction changed semantic metric {key} on {label}/{old["id"]}')
            row = dict(old)
            for key in ('status', 'error', 'stage', 'executed', 'execution_retryable', 'execution_profile'):
                if key in current:
                    row[key] = current[key]
            row['execution_replay_duration_ms'] = current['duration_ms']
            from training.pilot import errors
            row['error_categories'] = errors(row)
            rows.append(row)
        original['records'] = rows
        original['summary'] = E.summarize(rows)
        original['by_split'] = {s: E.summarize([r for r in rows if r['split'] == s]) for s in original['by_split']}
        original['by_intent'] = {r['intent_id']: E.summarize([x for x in rows if x['intent_id'] == r['intent_id']]) for r in rows}
        original['metadata']['execution_profile_correction'] = {
            'method': 'Replay validated first-response plans only; precompile failures and actual repair outcomes unchanged; semantic metrics identical',
            'profile': profile_for('reference').to_dict(), 'evaluator_hash': sha256(E.__file__),
            'wrapper_hash': sha256(Path(__file__).with_name('evaluate_checkpoint.py'))}
        write(path, original)
        (directory / 'errors' / f'{label}_errors.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows if r['error_categories']),encoding='utf-8')
        comparisons[label] = original['summary']['execution_success_rate']
    write(directory / 'execution_profile_correction.json', {'corrected': True, 'execution_rates': comparisons, 'production_runtime_changed': False})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT)
    parser.add_argument('--correct-execution-profile', action='store_true')
    args = parser.parse_args(argv)
    if args.correct_execution_profile:
        correct_execution(args.directory)
    export(args.directory)


if __name__ == '__main__':
    main()
