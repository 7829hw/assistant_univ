"""Prepare a bounded human review queue and export only reviewed annotations."""
import argparse
import copy
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

from training.annotations.candidates import (failure_driven_candidates, mine_predictions, proposal,
                                            semantic_negative_candidates)
from training.annotations.inventory import Protection, digest, family_key, inventory
from training.data.build_dpo import dpo_pair
from training.data.build_sft import sft_record
from training.data.canonicalize import canonical_json, flatten_source, semantic_key
from training.data.common import provenance, read_jsonl, sha256, write_jsonl, write_manifest
from training.data.split import question_key, split_records, template_key
from training.data.validation import STOP_TARGET

CHECKS = ('source_role_value', 'factor_evidence', 'aggregation_stages', 'od_direction',
          'support_boundary', 'paraphrase_lineage')
STATES = ('accepted', 'rejected', 'needs_fix')


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_xlsx(path, rows):
    """Dependency-free read-only review view. All cells are strings, never formulas.

    JSONL + separate decision audit are authoritative; XLSX edits are not imported.
    """
    columns = ('candidate_id', 'candidate_hash', 'status', 'candidate_type', 'question',
               'parent_intent', 'expected_outcome', 'diagnostic_only', 'eligibility',
               'proposed_grounding', 'proposed_rejected', 'quality', 'rejected_quality',
               'failure_hints', 'rationale', 'evidence')
    def letter(n):
        out = ''
        while n:
            n, r = divmod(n - 1, 26)
            out = chr(65 + r) + out
        return out
    xml_rows = []
    for i, cells in enumerate([list(columns)] + [[r.get(k, '') for k in columns] for r in rows], 1):
        parts = []
        for j, cell in enumerate(cells, 1):
            text = cell if isinstance(cell, str) else canonical_json(cell)
            text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
            if len(text) > 32767:
                text = text[:32700] + ' … full content in review_queue.jsonl'
            parts.append(f'<c r="{letter(j)}{i}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>')
        xml_rows.append(f'<row r="{i}">' + ''.join(parts) + '</row>')
    sheet = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews>'
             '<sheetData>' + ''.join(xml_rows) + '</sheetData>'
             f'<autoFilter ref="A1:{letter(len(columns))}{len(rows)+1}"/></worksheet>')
    files = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Review queue" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': sheet}
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value.encode('utf-8'))


def seal(row, protection):
    row = copy.deepcopy(row)
    identifiers = [row['parent_intent'], row['semantic_family'], row['provenance'].get('source_record_id')]
    reasons = protection.reasons(row['question'], row['proposed_grounding'], identifiers)
    if row['diagnostic_only']:
        reasons.append('diagnostic_source')
    if row['expected_outcome'] == 'needs_clarification':
        reasons.append('no_clarification_training_contract')
    row['eligibility'] = {'training_blockers': sorted(set(reasons)),
                          'eligible_after_human_review': not reasons}
    row['candidate_hash'] = digest(row)
    return row


def prepare(output, *, gold_dir, source, pilot, seed=42):
    output, gold_dir, source, pilot = map(Path, (output, gold_dir, source, pilot))
    if output.exists():
        raise ValueError('Queue directory already exists; choose a new immutable version')
    protection = Protection.current(gold_dir)
    report = inventory(gold_dir, source)
    sources = [source, *[gold_dir / f'{stage}_{split}.jsonl' for stage in ('sft', 'dpo') for split in ('train', 'valid')],
               gold_dir / 'manifest.json']
    sources.extend(sorted(Path(__file__).parent.glob('*.py')))
    train = read_jsonl(gold_dir / 'sft_train.jsonl')
    valid = read_jsonl(gold_dir / 'sft_valid.jsonl')
    from training.pilot import audit
    original_dpo = {s: read_jsonl(gold_dir / f'dpo_{s}.jsonl') for s in ('train', 'valid')}
    report['existing_split_audit'] = audit({'train': train, 'valid': valid}, original_dpo)
    original_manifest = json.loads((gold_dir / 'manifest.json').read_text(encoding='utf-8'))
    for stage in ('sft', 'dpo'):
        for split in ('train', 'valid'):
            filename = f'{stage}_{split}.jsonl'
            if original_manifest[stage]['output_hashes'].get(filename) != sha256(gold_dir / filename):
                raise ValueError('Original dataset manifest checksum mismatch')
    rows = []
    originals = {r['id']: r for r in yaml.safe_load(source.read_text(encoding='utf-8'))['examples']}
    for split, records in [('train', train), ('valid', valid)]:
        for record in records:
            meta = record['metadata']
            original = originals.get(meta['source_record_id'], {})
            rows.append(proposal(record['messages'][1]['content'], json.loads(record['messages'][-1]['content']),
                                 'gold_re_review', meta['parent_intent'], '기존 gold도 사람이 source/role/value와 factor 근거를 다시 확인.',
                                 provenance={'origin': 'existing_gold', 'source_record_id': meta['source_record_id'],
                                             'source': str(source), 'split': split, 'previous_reviewed_by': original.get('reviewed_by')},
                                 diagnostic_only=split != 'train',
                                 expected_outcome='unsupported' if json.loads(record['messages'][-1]['content']).get('unsupported') else 'answered'))
    metrics = [pilot / 'metrics' / f'{name}.json' for name in ('base', 'sft_best', 'dpo_best')]
    if not all(p.exists() for p in metrics):
        raise ValueError('Missing actual pilot metrics; no synthetic predictions substituted')
    reference_frame = reference_conditions = None
    for path in metrics:
        document = json.loads(path.read_text(encoding='utf-8'))
        report_meta = document['metadata']
        if report_meta.get('complete') is not True:
            raise ValueError(f'Incomplete pilot report: {path}')
        frame = [(r['id'], r['question'], r['split'], semantic_key(r['gold'])) for r in document['records']]
        conditions = {k: report_meta.get(k) for k in ('prompt_hash', 'model_revision', 'decoding')}
        if reference_frame is not None and (frame != reference_frame or conditions != reference_conditions):
            raise ValueError('Pilot reports do not share corpus/gold/prompt/revision/decoding conditions')
        reference_frame, reference_conditions = frame, conditions
    hard, mining = mine_predictions(metrics, train_records=train)
    sources.extend(metrics)
    authored = failure_driven_candidates(report, hard)
    rows += authored + semantic_negative_candidates(authored, seed=seed) + hard
    rows = [seal(r, protection) for r in rows]
    if len({r['candidate_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate queue candidate ID')
    report['pilot_failures'] = mining
    prefs = pilot / 'metrics/dpo_best_preferences.json'
    if prefs.exists():
        sources.append(prefs)
        report['pilot_preferences'] = json.loads(prefs.read_text(encoding='utf-8'))['by_split']
    summary = {'total': len(rows), 'by_type': dict(Counter(r['candidate_type'] for r in rows)),
               'eligible_after_human_review': sum(r['eligibility']['eligible_after_human_review'] for r in rows),
               'blocked_or_diagnostic': sum(not r['eligibility']['eligible_after_human_review'] for r in rows),
               'hard_negative_category': dict(Counter(r['negative_category'] for r in rows if r['candidate_type'] == 'hard_negative')),
               'hard_negative_hints': dict(Counter(h for r in hard for h in r['failure_hints'])),
               'hard_negative_train_origin': sum(not r['diagnostic_only'] for r in hard),
               'hard_negative_diagnostic_origin': sum(r['diagnostic_only'] for r in hard),
               'suggestion_states': dict(Counter(r['suggestion_state'] for r in rows)),
               'negative_type': dict(Counter(r.get('negative_type', 'model_prediction') for r in rows if r['proposed_rejected'] is not None)),
               'reviewed': 0, 'exported': 0}
    info = provenance(sources, seed)
    if any(json.loads(p.read_text())['metadata'].get('prompt_hash') != info['prompt_hash'] for p in metrics):
        raise ValueError('Pilot prompt differs from production; investigate before preparing review queue')
    output.mkdir(parents=True)
    write_jsonl(output / 'review_queue.jsonl', rows)
    write_xlsx(output / 'review_queue.xlsx', rows)
    save_json(output / 'coverage.json', report)
    save_json(output / 'manifest.json', {**info, 'annotation_schema': 'geoflow-human-review-v1',
                                       'gold_dir': str(gold_dir.resolve()), 'protection': protection.manifest(),
                                       'summary': summary, 'output_hashes': {p.name: sha256(p) for p in output.iterdir()},
                                       'policy': 'No candidate is gold. Validator PASS is structural evidence only.'})
    print(json.dumps(summary, ensure_ascii=False))
    return rows


def load_queue(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if sha256(directory / 'review_queue.jsonl') != manifest['output_hashes']['review_queue.jsonl']:
        raise ValueError('Queue checksum mismatch; recreate version, do not edit proposals in place')
    rows = read_jsonl(directory / 'review_queue.jsonl')
    for row in rows:
        if digest({k: v for k, v in row.items() if k != 'candidate_hash'}) != row['candidate_hash']:
            raise ValueError('Candidate checksum mismatch')
    return rows, manifest


def decision_history(path, rows):
    known = {r['candidate_id']: r for r in rows}
    latest = {}
    for decision in read_jsonl(path) if Path(path).exists() else []:
        cid = decision.get('candidate_id')
        if cid not in known or decision.get('candidate_hash') != known[cid]['candidate_hash']:
            raise ValueError('Unknown or stale decision candidate')
        if (decision.get('status') not in STATES or
            any(not isinstance(decision.get(field), str) or not decision[field].strip() for field in ('reviewer', 'reason'))):
            raise ValueError('Decision requires status/reviewer/reason')
        if decision.get('reviewer_kind') != 'human':
            raise ValueError('Only human review decisions can be imported')
        if not decision.get('reviewed_at'):
            raise ValueError('Decision requires review timestamp')
        datetime.fromisoformat(decision['reviewed_at'])
        if digest({k: v for k, v in decision.items() if k != 'decision_hash'}) != decision.get('decision_hash'):
            raise ValueError('Decision checksum mismatch')
        previous = latest.get(cid)
        if decision.get('supersedes') != (previous['decision_hash'] if previous else None):
            raise ValueError('Conflicting decision history; supersedes must name previous decision hash')
        latest[cid] = decision
    return latest


def decide(queue, decisions, candidate_id, *, status, reviewer, reason, corrected=None,
           corrected_rejected=None, semantic_checks=False, negative_wrong=False):
    rows, _ = load_queue(queue)
    if Path(decisions).resolve() in {p.resolve() for p in Path(queue).iterdir() if p.name != 'decisions.jsonl'}:
        raise ValueError('Decisions must not overwrite queue artifacts')
    known = {r['candidate_id']: r for r in rows}
    if candidate_id not in known:
        raise ValueError('Unknown candidate ID')
    if status not in STATES or not reviewer.strip() or not reason.strip():
        raise ValueError('Review status/reviewer/reason required')
    if status == 'accepted' and not semantic_checks:
        raise ValueError('Accepted requires --semantic-checks-confirmed after human verification')
    row = known[candidate_id]
    if status == 'accepted' and row['proposed_rejected'] is not None and not negative_wrong:
        raise ValueError('Hard negative acceptance requires --negative-is-wrong')
    previous = decision_history(decisions, rows).get(candidate_id)
    decision = dict(candidate_id=candidate_id, candidate_hash=row['candidate_hash'], status=status,
                    reviewer=reviewer, reviewer_kind='human', reason=reason,
                    reviewed_at=datetime.now(timezone.utc).isoformat(),
                    checks={name: semantic_checks for name in CHECKS}, negative_is_wrong=negative_wrong,
                    corrected_grounding=corrected, corrected_rejected=corrected_rejected,
                    supersedes=previous['decision_hash'] if previous else None)
    decision['decision_hash'] = digest(decision)
    Path(decisions).parent.mkdir(parents=True, exist_ok=True)
    with Path(decisions).open('a', encoding='utf-8') as stream:
        stream.write(canonical_json(decision) + '\n')
    return decision


def import_reviewed(queue, decisions, output, *, version, seed=42, valid_fraction=0.2):
    """Fail closed; immutable version includes decisions and inherited DPO split."""
    rows, manifest = load_queue(queue)
    output = Path(output)
    if output.exists():
        raise ValueError('Corpus version directory already exists')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', version):
        raise ValueError('Invalid corpus version')
    protection = Protection.current(manifest['gold_dir'])
    if protection.manifest()['source_hashes'] != manifest['protection']['source_hashes']:
        raise ValueError('Protected corpus drift; prepare a new queue and review again')
    for name, expected in manifest['source_files'].items():
        if not Path(name).exists() or sha256(name) != expected:
            raise ValueError('Source data drift; prepare a new queue and review again')
    info = provenance([Path(queue) / 'review_queue.jsonl', Path(decisions)], seed)
    if info['prompt_hash'] != manifest['prompt_hash'] or info['definition_hashes'] != manifest['definition_hashes']:
        raise ValueError('Production prompt/schema drift; revalidate and review a new version')
    latest = decision_history(decisions, rows)
    records, by_question, pending_pairs, annotations, excluded = [], {}, [], [], []
    # No output is written until every exportable accepted item passes all checks.
    for row in rows:
        decision = latest.get(row['candidate_id'])
        if not decision or decision['status'] != 'accepted':
            excluded.append({'id': row['candidate_id'], 'reason': decision['status'] if decision else 'pending'})
            continue
        if not all(decision.get('checks', {}).get(k) is True for k in CHECKS):
            raise ValueError('Accepted item lacks all semantic review attestations')
        raw = decision['corrected_grounding'] if decision.get('corrected_grounding') is not None else row['proposed_grounding']
        identifiers = [row['parent_intent'], row['semantic_family'], row['provenance'].get('source_record_id')]
        blockers = protection.reasons(row['question'], raw, identifiers)
        # Proposal lineage cannot be laundered by changing the corrected target.
        blockers += row['eligibility']['training_blockers']
        if blockers:
            excluded.append({'id': row['candidate_id'], 'reason': 'protected_or_diagnostic', 'codes': sorted(set(blockers))})
            continue
        if row['expected_outcome'] == 'unsupported' and raw != {'unsupported': True}:
            raise ValueError('Unsupported boundary outcome mismatch; revise proposal in a new queue')
        if row['expected_outcome'] == 'answered' and raw.get('unsupported'):
            raise ValueError('Answered boundary outcome mismatch; revise proposal in a new queue')
        annotation = dict(id=row['candidate_id'], version=version, question=row['question'], grounding=raw,
                          parent_intent=row['parent_intent'], family=row['semantic_family'],
                          # 결정 14: 정지 target으로 다시 낸 queue의 행은 표시를 달아 sft_record가 정지를 대조하게 한다.
                          tags=[row['candidate_type']] + ([STOP_TARGET] if row['expected_outcome'] == STOP_TARGET else []),
                          reviewed_by=decision['reviewer'], review_decision_hash=decision['decision_hash'])
        record = sft_record(annotation, source=str(output / 'reviewed_annotations.yaml'), source_representation='flat')
        record['metadata'].update(corpus_version=version, candidate_hash=row['candidate_hash'],
                                  review_decision_hash=decision['decision_hash'])
        qkey = question_key(row['question'])
        if qkey in by_question:
            existing = by_question[qkey]
            if semantic_key(json.loads(existing['messages'][-1]['content'])) != semantic_key(raw):
                raise ValueError('Conflicting accepted golds for same question')
            if existing['metadata'].get('family') != record['metadata'].get('family'):
                raise ValueError('Same question assigned conflicting semantic families')
            record = existing
        else:
            records.append(record)
            by_question[qkey] = record
            annotations.append(annotation)
        if row['proposed_rejected'] is not None:
            if decision.get('negative_is_wrong') is not True:
                raise ValueError('Rejected semantics must be explicitly judged incorrect')
            rejected = decision['corrected_rejected'] if decision.get('corrected_rejected') is not None else row['proposed_rejected']
            pending_pairs.append((record, rejected, row, decision))
    if not records:
        raise ValueError('No reviewed, unprotected, trainable annotations; no corpus exported')
    # Existing splitter groups exact templates; merge conservative family and
    # contrast lineage too by adding it before re-running the grouping.
    for r in records:
        r['metadata']['parent_intent'] = family_key(json.loads(r['messages'][-1]['content']))
    # family is the original contrast group retained by sft_record.
    train, valid = split_records(records, seed=seed, valid_fraction=valid_fraction)
    if not train or not valid:
        raise ValueError('Need at least two disjoint reviewed semantic/contrast groups for train/validation')
    if {template_key(r) for r in train} & {template_key(r) for r in valid}:
        raise ValueError('Semantic template leakage')
    dpo = {'train': [], 'valid': []}
    train_ids = {r['metadata']['source_record_id'] for r in train}
    pair_seen = set()
    for record, rejected, row, decision in pending_pairs:
        pair = dpo_pair(record, rejected, negative_type=row.get('negative_type', 'reviewed_model_prediction'),
                        mutation_source=row['provenance']['origin'],
                        negative_details={'failure_hints': row.get('failure_hints'), 'evidence': row['evidence'],
                                          'decision_hash': decision['decision_hash']})
        key = digest([pair['prompt'][1]['content'], pair['chosen'], pair['rejected']])
        if key in pair_seen:
            continue
        pair_seen.add(key)
        dpo['train' if record['metadata']['source_record_id'] in train_ids else 'valid'].append(pair)
    from training.pilot import audit
    split_audit = audit({'train': train, 'valid': valid}, dpo)
    output.mkdir(parents=True)
    (output / 'reviewed_annotations.yaml').write_text(yaml.safe_dump({'version': version, 'representation': 'flat', 'examples': annotations},
                                                                   allow_unicode=True, sort_keys=False), encoding='utf-8')
    write_jsonl(output / 'review_decisions.jsonl', read_jsonl(decisions))
    for stage, values in [('sft', {'train': train, 'valid': valid}), ('dpo', dpo)]:
        for split, group in values.items():
            write_jsonl(output / f'{stage}_{split}.jsonl', group)
        write_manifest(output, stage, values['train'], values['valid'],
                       {**info, 'corpus_version': version, 'human_review_required': True,
                        'review_queue_hash': sha256(Path(queue) / 'review_queue.jsonl'),
                        'split_policy': 'Conservative semantic family + contrast family + template; DPO inherits SFT'}, excluded)
    save_json(output / 'corpus_manifest.json', {**info, 'corpus_version': version, 'reviewed_count': len(annotations),
                                              'excluded': excluded, 'protection': protection.manifest(),
                                              'split_audit': split_audit,
                                              'output_hashes': {p.name: sha256(p) for p in output.iterdir()}})
    return {'sft_train': len(train), 'sft_valid': len(valid), 'dpo_train': len(dpo['train']), 'dpo_valid': len(dpo['valid']),
            'excluded': len(excluded)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare', help='Coverage + bounded proposals + actual pilot negatives')
    p.add_argument('--gold-dir', default='training/generated')
    p.add_argument('--source', default='geoflow_examples/question_graph_examples.yaml')
    p.add_argument('--pilot', default='training/experiments/thor_pilot_001')
    p.add_argument('--output', required=True)
    p.add_argument('--seed', type=int, default=42)
    d = sub.add_parser('decide', help='Append one human decision; original queue stays immutable')
    d.add_argument('--queue', required=True)
    d.add_argument('--decisions', required=True)
    d.add_argument('--id', required=True)
    d.add_argument('--status', choices=STATES, required=True)
    d.add_argument('--reviewer', required=True)
    d.add_argument('--reason', required=True)
    d.add_argument('--corrected-grounding', help='JSON file, only actual planner output fields')
    d.add_argument('--corrected-rejected', help='JSON file for a reviewed hard negative correction')
    d.add_argument('--semantic-checks-confirmed', action='store_true')
    d.add_argument('--negative-is-wrong', action='store_true')
    i = sub.add_parser('import-reviewed', help='Strict reviewed-only versioned corpus export')
    i.add_argument('--queue', required=True)
    i.add_argument('--decisions', required=True)
    i.add_argument('--output', required=True)
    i.add_argument('--version', required=True)
    i.add_argument('--seed', type=int, default=42)
    i.add_argument('--valid-fraction', type=float, default=0.2)
    a = parser.parse_args(argv)
    try:
        if a.command == 'prepare':
            prepare(a.output, gold_dir=a.gold_dir, source=a.source, pilot=a.pilot, seed=a.seed)
        elif a.command == 'decide':
            corrected = json.loads(Path(a.corrected_grounding).read_text()) if a.corrected_grounding else None
            bad = json.loads(Path(a.corrected_rejected).read_text()) if a.corrected_rejected else None
            result = decide(a.queue, a.decisions, a.id, status=a.status, reviewer=a.reviewer, reason=a.reason,
                            corrected=corrected, corrected_rejected=bad,
                            semantic_checks=a.semantic_checks_confirmed, negative_wrong=a.negative_is_wrong)
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(json.dumps(import_reviewed(a.queue, a.decisions, a.output, version=a.version,
                                              seed=a.seed, valid_fraction=a.valid_fraction), ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
