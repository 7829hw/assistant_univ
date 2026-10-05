"""Batch 003 policy receipt and fixed-split extension; CPU only, never trains.

This recipe implements the user's explicit batch-specific approval. It is not an
automatic review/import command for arbitrary candidates. Existing corpus and
queue files are read-only. Token gates are measured, never bypassed or changed.
"""
import argparse
import copy
import hashlib
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path

import yaml

from training.annotations.inventory import Protection, digest, family_key
from training.annotations.workflow import decide, decision_history, load_queue
from training.data.analyze_tokens import analyze
from training.data.build_dpo import dpo_pair
from training.data.build_sft import sft_record
from training.data.canonicalize import serialize_planner_target
from training.data.common import ROOT, coverage, production_prompt, provenance, read_jsonl, sha256, write_jsonl, write_manifest
from training.data.split import question_key
from training.data.validation import assess, chosen_ok
from training.pilot import audit
from training.trainer_common import load_config, load_records, render_prompt, render_records, tokenizer_for

VERSION = 'reviewed_gold_v003'
APPROVED_GOLD = {f'RB003-{n:02}' for n in range(3, 21)}
APPROVED_PAIRS = {f'RB003-{n:02}' for n in range(23, 35)}
DIAGNOSTIC = {'RB003-01', 'RB003-02'}
HOLD = {'RB003-21', 'RB003-22'}
POLICY = ('User explicitly approves RB003-03–20 SFT and RB003-23–34 DPO only after '
          'chosen approval verification. RB003-01/02 remain diagnostic and 21/22 hold. '
          'Keep v001/v002, protected data, production and configs unchanged; no GPU '
          'training, truncation, or exclusion of approved overlength samples.')


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def verify_hashes(hashes):
    for name, expected in hashes.items():
        require(sha256(name) == expected, f'Frozen source drift: {name}')


def token_rows(tokenizer, records, config, stage):
    """Same prefix/EOS and one-token guard as the existing production trainer."""
    rows = []
    args = config['training']
    total_limit = args['max_seq_length' if stage == 'sft' else 'max_length']
    for split, group in records.items():
        for record in group:
            prompt = render_prompt(tokenizer, (record.get('messages') or record['prompt'])[:2], config)
            p = len(tokenizer(prompt, add_special_tokens=False)['input_ids'])
            fields = {'completion': record['messages'][-1]['content']} if stage == 'sft' else {
                k: record[k][0]['content'] for k in ('chosen', 'rejected')}
            lengths, totals, actual = {}, {}, {}
            for key, text in fields.items():
                completion = text + tokenizer.eos_token
                lengths[key] = len(tokenizer(completion, add_special_tokens=False)['input_ids'])
                whole = len(tokenizer(prompt + completion, add_special_tokens=False)['input_ids'])
                actual[key] = max(p + lengths[key], whole)
                totals[key] = actual[key] + 1
            reasons = []
            if max(totals.values()) > total_limit:
                reasons.append('total_limit')
            if stage == 'dpo' and p > args['max_prompt_length']:
                reasons.append('prompt_limit')
            if stage == 'dpo' and max(lengths.values()) > args['max_completion_length']:
                reasons.append('completion_limit')
            meta = record['metadata']
            ids = [meta['batch_item_id']] if stage == 'dpo' and meta.get('batch_item_id') else meta.get('batch_item_ids', [])
            rows.append(dict(stage=stage, split=split, source_record_id=meta['source_record_id'],
                             batch_item_ids=ids, prompt=p, completions=lengths,
                             actual_sequence_tokens_including_EOS=actual, guarded_totals=totals,
                             total=max(totals.values()), current_limit_failures=reasons))
    return rows


def build(base, queue, output, decisions_path):
    base, queue, output, decisions_path = map(Path, (base, queue, output, decisions_path))
    require(not output.exists() and not decisions_path.exists(), 'Immutable outputs already exist')
    require(output.resolve() != base.resolve(), 'Cannot overwrite parent corpus')
    rows, qmanifest = load_queue(queue)
    archived_review = ROOT / 'training/records/reviews/review_batch_003'
    for name in ('review_queue.jsonl', 'decisions_draft_003.jsonl', 'split_plan.json'):
        require(sha256(queue / name) == sha256(archived_review / name),
                f'Approval is bound to the reviewed batch snapshot: {name}')
    by = {r['batch_item_id']: r for r in rows}
    require(set(by) == APPROVED_GOLD | APPROVED_PAIRS | DIAGNOSTIC | HOLD, 'Unexpected batch IDs')
    drafts = {r['batch_item_id']: r for r in read_jsonl(queue / 'decisions_draft_003.jsonl')}
    plan = json.loads((queue / 'split_plan.json').read_text())
    require(plan['seed'] == 42, 'Split seed drift')
    protection = Protection.current(base)
    require(protection.manifest()['source_hashes'] == qmanifest['protection']['source_hashes'],
            'Protection source set drift; re-review needed')
    frozen = {str(p): sha256(p) for directory in (
        base, queue, ROOT / 'training/annotations/generated/corpora/reviewed_gold_v001',
        ROOT / 'training/annotations/generated/review_batch_001',
        ROOT / 'training/annotations/generated/review_batch_002',
        ROOT / 'training/annotations/generated/expansion_001')
        for p in directory.rglob('*') if p.is_file()}
    for key in ('source_files', 'definition_hashes', 'frozen_existing_file_hashes'):
        frozen.update({str(Path(p) if Path(p).is_absolute() else ROOT / p): h
                       for p, h in qmanifest[key].items()})
    frozen.update(qmanifest['protection']['source_hashes'])
    frozen.update({str(queue / p): h for p, h in qmanifest['output_hashes'].items()})
    configs = {stage: base / f'configs/qwen3_8b_thor_v002_{stage}.yaml' for stage in ('sft', 'dpo')}
    frozen.update({str(p): sha256(p) for p in (ROOT / 'training/configs').glob('*.yaml')})
    verify_hashes(frozen)
    # Tool-text-only gold cannot be inferred by Protection. Retain the manual
    # protected RPM-average witnesses from the semantic review, fail closed.
    for rid in DIAGNOSTIC:
        require(drafts[rid]['lineage']['manual_conflict'], f'Missing manual lineage: {rid}')
        for witness in drafts[rid]['lineage']['manual_matches']:
            require(sha256(ROOT / witness['source']) == witness['source_sha256'], 'Lineage witness drift')
        protection.families.add(family_key(by[rid]['proposed_grounding']))
    lineage = []
    for rid in sorted(APPROVED_GOLD | APPROVED_PAIRS):
        row = by[rid]
        reasons = protection.reasons(row['question'], row['proposed_grounding'],
                                     [row['parent_intent'], row['semantic_family']])
        require(not reasons and not drafts[rid]['lineage']['manual_conflict'], f'Protected lineage: {rid}: {reasons}')
        require(not row['diagnostic_only'] and not row['eligibility']['training_blockers'], f'Blocked: {rid}')
        require(plan['candidate_splits'][rid]['split'] == row['planned_split'], f'Split drift: {rid}')
        lineage.append(dict(batch_item_id=rid, blockers=reasons,
                            review_lineage=drafts[rid]['lineage'], split=row['planned_split']))
    with tempfile.TemporaryDirectory(prefix='geoflow_v003_') as temporary:
        tmp = Path(temporary)
        receipt_path = tmp / 'decisions_003.jsonl'
        approvals = {}
        for row in rows:
            rid = row['batch_item_id']
            accepted = rid in APPROVED_GOLD | APPROVED_PAIRS
            dep = drafts[rid]['chosen_approval_dependency']
            if accepted and dep:
                require(dep in approvals and approvals[dep]['status'] == 'accepted', f'Unapproved chosen: {rid}')
                require(by[dep]['question'] == row['question'] and
                        by[dep]['proposed_grounding'] == row['proposed_grounding'], f'Chosen dependency mismatch: {rid}')
            negative = drafts[rid]['negative_assessment']
            reason = ('Explicit user approval of the semantic review draft, after delegated strict/lineage checks.'
                      if accepted else 'Protected diagnostic RPM-average family; never training.'
                      if rid in DIAGNOSTIC else 'Mixed raw-contract and normalized semantics: user explicitly holds.')
            if accepted and row['proposed_rejected'] is not None:
                reason += ' ' + negative['wrongness_basis']
            d = decide(queue, receipt_path, row['candidate_id'],
                       status='accepted' if accepted else 'needs_fix',
                       reviewer='hwkim (explicit batch policy approval); Codex (delegated verification)',
                       reason=reason, semantic_checks=accepted,
                       negative_wrong=accepted and row['proposed_rejected'] is not None)
            d.update(batch_item_id=rid, corpus_disposition='accepted' if accepted else
                     'diagnostic_only' if rid in DIAGNOSTIC else 'hold', approval_basis=POLICY,
                     approval_policy_hash=digest(POLICY), checks_performed_by='Codex',
                     individual_human_record_inspection_claimed=False, approval_dependency=dep,
                     approval_dependency_decision_hash=approvals[dep]['decision_hash'] if accepted and dep else None,
                     execution_benchmark_eligible=False, execution_tested=False)
            d['decision_hash'] = digest({k: v for k, v in d.items() if k != 'decision_hash'})
            approvals[rid] = d
            write_jsonl(receipt_path, list(approvals.values()))
        require(len(decision_history(receipt_path, rows)) == 34, 'Decision history incomplete')
        sft = {s: read_jsonl(base / f'sft_{s}.jsonl') for s in ('train', 'valid')}
        dpo = {s: read_jsonl(base / f'dpo_{s}.jsonl') for s in ('train', 'valid')}
        old_sft, old_dpo = copy.deepcopy(sft), copy.deepcopy(dpo)
        annotations = yaml.safe_load((base / 'reviewed_annotations.yaml').read_text())['examples']
        for rid in sorted(APPROVED_GOLD):
            r, d = by[rid], approvals[rid]
            annotation = dict(id=r['candidate_id'], version=VERSION, question=r['question'],
                              grounding=r['proposed_grounding'], parent_intent=r['parent_intent'],
                              family=r['semantic_family'], tags=['review_batch_003', r['category']],
                              reviewed_by=d['reviewer'], review_decision_hash=d['decision_hash'], batch_item_ids=[rid])
            record = sft_record(annotation, source=str(output / 'reviewed_annotations.yaml'), source_representation='flat')
            record['metadata'].update(corpus_version=VERSION, batch_item_ids=[rid],
                                      candidate_hash=r['candidate_hash'], review_decision_hash=d['decision_hash'])
            sft[r['planned_split']].append(record)
            annotations.append(annotation)
        golds = {question_key(r['messages'][1]['content']): (s, r) for s, group in sft.items() for r in group}
        pairs = []
        for rid in sorted(APPROVED_PAIRS):
            row, d = by[rid], approvals[rid]
            split, gold = golds[question_key(row['question'])]
            chosen_text = serialize_planner_target(row['proposed_grounding'])
            require(chosen_text == gold['messages'][-1]['content'] and split == row['planned_split'], f'Chosen hash/split mismatch: {rid}')
            trust = drafts[rid]['chosen_trust']
            if not d['approval_dependency']:
                require(trust['source_record_id'] == gold['metadata']['source_record_id'] and
                        trust['sft_record_hash'] == digest(gold) and
                        trust['corpus_manifest_hash'] == sha256(base / 'corpus_manifest.json') and
                        trust['prior_decision_hash'] == gold['metadata']['review_decision_hash'], f'Prior chosen receipt mismatch: {rid}')
            negative = drafts[rid]['negative_assessment']
            pair = dpo_pair(gold, row['proposed_rejected'], negative_type=row['negative_type'],
                            mutation_source='human_reviewed_synthetic_control' if negative['synthetic'] else 'actual_model_output',
                            negative_details=dict(batch_item_id=rid, candidate_hash=row['candidate_hash'],
                            decision_hash=d['decision_hash'], chosen_target_sha256=hashlib.sha256(chosen_text.encode()).hexdigest(),
                            chosen_review_decision_hash=gold['metadata']['review_decision_hash'],
                            approval_dependency=d['approval_dependency'], semantic_reason=negative['wrongness_basis'],
                            error_scope=negative['error_scope'], evidence=row['evidence']))
            require(pair['metadata']['negative_category'] == negative['recommended_category'], f'Pair category drift: {rid}')
            pair['metadata'].update(pair_corpus_version=VERSION, pair_review_decision_hash=d['decision_hash'], batch_item_id=rid)
            dpo[split].append(pair)
            pairs.append(dict(batch_item_id=rid, split=split, category=negative['recommended_category'],
                              chosen_target_sha256=hashlib.sha256(chosen_text.encode()).hexdigest(),
                              chosen_decision_hash=gold['metadata']['review_decision_hash'],
                              pair_decision_hash=d['decision_hash'], wrongness_basis=negative['wrongness_basis'],
                              chosen_strict=assess(row['proposed_grounding'], row['question'], normalize=False),
                              rejected_strict=assess(row['proposed_rejected'], row['question'], normalize=False),
                              rejected_production=assess(row['proposed_rejected'], row['question']),
                              actual_model_failure=not negative['synthetic']))
        split_audit = audit(sft, dpo)
        fingerprints = {s: {family_key(json.loads(r['messages'][-1]['content'])) for r in group} for s, group in sft.items()}
        require(not fingerprints['train'] & fingerprints['valid'], 'Semantic family leakage')
        # Include rejected semantic targets too: contrast pairs cannot cross splits.
        all_families = {s: fingerprints[s] | {family_key(json.loads(r[k][0]['content']))
                         for r in dpo[s] for k in ('chosen', 'rejected')} for s in ('train', 'valid')}
        require(not all_families['train'] & all_families['valid'], 'Preference contrast family leakage')
        strict_rows = []
        for split, group in sft.items():
            for r in group:
                payload, question = json.loads(r['messages'][-1]['content']), r['messages'][1]['content']
                for normalize in (False, True):
                    require(chosen_ok(assess(payload, question, normalize=normalize)), 'Gold strict failure')
                if split == 'train':
                    require(not protection.reasons(question, payload, [r['metadata']['source_record_id'],
                            r['metadata']['parent_intent'], r['metadata']['family']]), 'Training/protection collision')
                strict_rows.append(dict(source_record_id=r['metadata']['source_record_id'], split=split,
                                        quality=assess(payload, question, normalize=False)))
        for group in dpo.values():
            for r in group:
                rejected = json.loads(r['rejected'][0]['content'])
                category = 'semantic' if chosen_ok(assess(rejected, r['prompt'][1]['content'])) else 'constraint'
                require(category == r['metadata']['negative_category'], 'Inherited pair category drift')
        require([len(sft[s]) for s in ('train', 'valid')] == [19, 16], 'SFT counts changed')
        require([len(dpo[s]) for s in ('train', 'valid')] == [18, 14], 'DPO counts changed')
        out = tmp / VERSION
        out.mkdir()
        for stage, values, old in (('sft', sft, old_sft), ('dpo', dpo, old_dpo)):
            for split, group in values.items():
                require(group[:len(old[split])] == old[split], 'Parent split/record modified')
                write_jsonl(out / f'{stage}_{split}.jsonl', group)
        (out / 'reviewed_annotations.yaml').write_text(yaml.safe_dump(dict(version=VERSION,
            representation='flat', split_policy='Frozen v002 plus pre-review batch003 split_plan seed42; no regrouping',
            examples=annotations), allow_unicode=True, sort_keys=False))
        shutil.copy2(receipt_path, out / 'decisions_003.jsonl')
        write_jsonl(out / 'review_decisions.jsonl', read_jsonl(base / 'review_decisions.jsonl') + list(approvals.values()))
        info = provenance([base / 'corpus_manifest.json', base / 'manifest.json',
            base / 'reviewed_annotations.yaml', base / 'review_decisions.jsonl',
            *[base / f'{stage}_{s}.jsonl' for stage in ('sft', 'dpo') for s in ('train', 'valid')],
            queue / 'review_queue.jsonl', queue / 'decisions_draft_003.jsonl', queue / 'split_plan.json',
            *configs.values(), Path(__file__)], 42)
        require(info['prompt_hash'] == qmanifest['prompt_hash'], 'Prompt drift')
        info.update(corpus_version=VERSION, parent_corpus='reviewed_gold_v002',
                    parent_manifest_hash=sha256(base / 'corpus_manifest.json'), decisions_003_hash=sha256(receipt_path),
                    approval_policy=POLICY, approval_policy_hash=digest(POLICY),
                    split_policy='Frozen v002 plus pre-review batch003 split_plan; no regrouping',
                    no_training_or_truncation=True, individual_human_record_inspection_claimed=False)
        for stage, records in (('sft', sft), ('dpo', dpo)):
            write_manifest(out, stage, records['train'], records['valid'], info, [])
        token_report = dict(model=None, production_prompt_hash=info['prompt_hash'],
                            config_changed=False, truncated_samples=0, dropped_approved_samples=0, GPU_used=False,
                            current_limits=dict(sft=6912, dpo_total=6912, dpo_prompt=6784, dpo_completion=256),
                            measurement='Exact production generation prefix, completion EOS, and existing trainer +1 guard; no padding/truncation')
        all_token_rows = []
        for stage, records in (('sft', sft), ('dpo', dpo)):
            config = load_config(configs[stage], stage)
            expected = {'max_seq_length': 6912} if stage == 'sft' else {
                'max_length': 6912, 'max_prompt_length': 6784, 'max_completion_length': 256}
            require(all(config['training'][k] == v for k, v in expected.items()), 'Current token limits drift')
            # In-memory data paths only, leave all existing config files byte-identical.
            config['data'] = {s: str(out / f'{stage}_{s}.jsonl') for s in ('train', 'valid')}
            config['data']['manifest'] = str(out / 'manifest.json')
            loaded, _ = load_records(config, stage)
            require(loaded == records, 'Trainer data-only validation mismatch')
            tokenizer = tokenizer_for(config)
            token_report['model'] = config['model']
            token_report['tokenizer_chat_template_sha256'] = hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()
            from transformers.utils import cached_file
            token_report['tokenizer_file_hashes'] = {name: sha256(cached_file(config['model']['name_or_path'], name,
                revision=config['model']['revision'], local_files_only=True))
                for name in ('tokenizer.json', 'tokenizer_config.json')}
            measured = token_rows(tokenizer, records, config, stage)
            all_token_rows += measured
            token_report[stage] = analyze(tokenizer, records['train'] + records['valid'], config, stage)
            blocked = [r for r in measured if r['current_limit_failures']]
            token_report[stage]['blocked_samples'] = blocked
            minimum = {'max_seq_length' if stage == 'sft' else 'max_length': max(r['total'] for r in measured)}
            if stage == 'dpo':
                minimum.update(max_prompt_length=max(r['prompt'] for r in measured),
                               max_completion_length=max(max(r['completions'].values()) for r in measured))
            token_report[stage]['minimum_safe_limits_including_EOS_and_guard'] = minimum
            safe = copy.deepcopy(config)
            safe['training'].update(minimum)
            for record, measured_row in zip(records['train'] + records['valid'], measured):
                try:
                    render_records(tokenizer, [record], config, stage)
                except ValueError:
                    require(bool(measured_row['current_limit_failures']), 'Unexpected render failure')
                else:
                    require(not measured_row['current_limit_failures'], 'Analyzer/trainer disagreement')
                require(len(render_records(tokenizer, [record], safe, stage)) == 1, 'Minimum limit fails trainer render')
            token_report[stage]['all_samples_render_with_measured_minimum_in_memory_only'] = True
        write_jsonl(out / 'token_lengths.jsonl', all_token_rows)
        save(out / 'token_validation.json', token_report)
        before = {'sft': coverage(old_sft['train'] + old_sft['valid']), 'dpo': coverage(old_dpo['train'] + old_dpo['valid'])}
        after = {'sft': coverage(sft['train'] + sft['valid']), 'dpo': coverage(dpo['train'] + dpo['valid'])}
        new_families = [r for r in plan['validation_families'] if set(r['ids']) <= APPROVED_GOLD]
        save(out / 'coverage_before_after.json', dict(before=before, after=after,
             after_by_split={stage: {s: coverage(g) for s, g in values.items()} for stage, values in (('sft', sft), ('dpo', dpo))},
             new_independent_validation_families=new_families, excluded_ids=sorted(HOLD | DIAGNOSTIC)))
        save(out / 'dpo_distribution.json', dict(overall=dict(Counter(r['metadata']['negative_category'] for g in dpo.values() for r in g)),
             by_split={s: dict(Counter(r['metadata']['negative_category'] for r in g)) for s, g in dpo.items()},
             new_pairs=dict(Counter(p['category'] for p in pairs)),
             negative_types=dict(Counter(r['metadata']['negative_type'] for g in dpo.values() for r in g)),
             new_actual_model_failure_pairs=2, new_reviewed_synthetic_pairs=10))
        save(out / 'pair_validation.json', dict(new_pairs=pairs, all_32_chosen_matched_approved_SFT=True))
        save(out / 'lineage_audit.json', dict(passed=True, audit=split_audit,
             inherited_split_and_records_unchanged=True, preference_contrast_family_intersection=[],
             protected_source_hashes=qmanifest['protection']['source_hashes'], accepted=lineage,
             protected_diagnostic=[dict(batch_item_id=rid, lineage=drafts[rid]['lineage']) for rid in sorted(DIAGNOSTIC)],
             held_ids=sorted(HOLD), checker_limit='Tool-text/question-only families need manual lineage witnesses; absence of automated match is not proof.'))
        save(out / 'strict_validation.json', dict(passed=True, sft_records=35, dpo_pairs=32,
             strict_gold_records=strict_rows, checks=['sft_record builder flat contract', 'parse/compose/G1–G7',
             'production normalization stability', 'dpo_pair builder', 'approved chosen/prompt/hash/split',
             'trainer load_records manifest checks', 'no protected train family', 'all long records retained'],
             semantic_approval_basis='Explicit user policy adopting prior semantic review, not Validator PASS',
             training_ready_with_current_limits=False, token_gate_next_action='Thor memory smoke before config limit change'))
        scope = copy.deepcopy(json.loads((base / 'policy_and_scope.json').read_text()))
        scope.update(corpus_version=VERSION, parent_manifest_hash=sha256(base / 'corpus_manifest.json'),
                     new_held_batch_item_ids=sorted(HOLD), new_diagnostic_batch_item_ids=sorted(DIAGNOSTIC))
        for rid in sorted(APPROVED_GOLD):
            r = by[rid]
            scope['scopes'].append(dict(source_record_id=r['candidate_id'], batch_item_ids=[rid],
                split=r['planned_split'], question=r['question'], semantic_gold=True,
                default_TIMS_execution_benchmark_eligible=False, independent_unseen_execution_benchmark_eligible=False,
                execution_exclusion_reasons=['synthetic_place_or_scope; execution not verified', 'provider limits separate from semantic approval']))
        save(out / 'policy_and_scope.json', scope)
        # Compact, portable reconstruction inputs; never archive the repeated
        # 6748-token production prompt in every SFT/DPO row.
        index = {}
        for stage, values in (('sft', sft), ('dpo', dpo)):
            for split, group in values.items():
                compact = []
                for r in group:
                    item = copy.deepcopy(r)
                    (item['messages'] if stage == 'sft' else item['prompt'])[0]['content'] = {
                        'production_prompt_sha256': info['prompt_hash']}
                    compact.append(item)
                index[f'{stage}_{split}'] = compact
        save(out / 'dataset_index.json', index)
        for r in sft['valid']:
            protection.add(r['messages'][1]['content'], json.loads(r['messages'][-1]['content']),
                           [r['metadata'][k] for k in ('source_record_id', 'parent_intent', 'family')])
        for r in dpo['valid']:
            for key in ('chosen', 'rejected'):
                protection.add(payload=json.loads(r[key][0]['content']))
        fingerprints = protection.manifest()['fingerprints']
        # Retain historical validation/diagnostic protections when v003 is parent.
        save(out / 'corpus_manifest.json', dict(**info,
            counts={f'{stage}_{s}': len(g) for stage, values in (('sft', sft), ('dpo', dpo)) for s, g in values.items()},
            batch003_dispositions=dict(Counter(d['corpus_disposition'] for d in approvals.values())),
            protection={'fingerprints': fingerprints, 'source_hashes': qmanifest['protection']['source_hashes']},
            output_hashes={p.name: sha256(p) for p in out.iterdir() if p.is_file()}))
        verify_hashes(frozen)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(out, output)
        decisions_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(receipt_path, decisions_path)
        print(json.dumps(dict(corpus=str(output), counts=json.loads((output / 'corpus_manifest.json').read_text())['counts'],
                              dispositions=Counter(d['corpus_disposition'] for d in approvals.values()),
                              minimum_limits={s: token_report[s]['minimum_safe_limits_including_EOS_and_guard'] for s in ('sft', 'dpo')}), ensure_ascii=False))


def restore_dataset_exports(directory, output):
    """Reconstruct exact approved exports from compact committed inputs, CPU only."""
    directory, output = Path(directory), Path(output)
    require(not output.exists(), 'Immutable output already exists')
    manifest = json.loads((directory / 'corpus_manifest.json').read_text())
    for name in ('dataset_index.json', 'manifest.json'):
        require(sha256(directory / name) == manifest['output_hashes'][name], f'Archive drift: {name}')
    prompt = production_prompt()
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    require(prompt_hash == manifest['prompt_hash'], 'Production prompt drift')
    index = json.loads((directory / 'dataset_index.json').read_text())
    with tempfile.TemporaryDirectory(prefix='geoflow_v003_restore_') as temporary:
        tmp = Path(temporary) / 'export'
        tmp.mkdir()
        datasets = {}
        for stage in ('sft', 'dpo'):
            datasets[stage] = {}
            for split in ('train', 'valid'):
                name = f'{stage}_{split}'
                records = index[name]
                for r in records:
                    messages = r['messages'] if stage == 'sft' else r['prompt']
                    require(messages[0]['content'] == {'production_prompt_sha256': prompt_hash}, 'Prompt marker mismatch')
                    messages[0]['content'] = prompt
                write_jsonl(tmp / f'{name}.jsonl', records)
                require(sha256(tmp / f'{name}.jsonl') == manifest['output_hashes'][f'{name}.jsonl'], f'Export checksum mismatch: {name}')
                datasets[stage][split] = records
        audit(datasets['sft'], datasets['dpo'])
        shutil.copy2(directory / 'manifest.json', tmp / 'manifest.json')
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(tmp, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base')
    parser.add_argument('--queue')
    parser.add_argument('--output', required=True)
    parser.add_argument('--decisions')
    parser.add_argument('--restore-from', help='Reconstruct frozen exports only; does not create approvals')
    args = parser.parse_args()
    if args.restore_from:
        if any((args.base, args.queue, args.decisions)):
            parser.error('Use --restore-from with --output only')
        restore_dataset_exports(args.restore_from, args.output)
    else:
        if not all((args.base, args.queue, args.decisions)):
            parser.error('Assembly requires --base, --queue, --output and --decisions')
        build(args.base, args.queue, args.output, args.decisions)


if __name__ == '__main__':
    main()
