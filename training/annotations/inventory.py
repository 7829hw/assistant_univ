"""Inventory and conservative protection of evaluation/validation families."""
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

import yaml

from geoflow.factors import FACTOR_SPECS
from geoflow.measures import MEASURES
from geoflow.operator_mapping import measure_types
from geoflow.types import CONCEPT_SUBTYPES, FunctionalRole
from training.data.canonicalize import canonical_json, flatten_source, serialize_planner_target
from training.data.common import ROOT, coverage, read_jsonl, reserved_sources, sha256
from training.data.split import question_key, template_key


def digest(value):
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def as_record(payload):
    return {'messages': [{'content': serialize_planner_target(flatten_source(payload))}]}


def family_key(payload):
    """Conservative semantic family, independent of wording, place/date and source.

    Retains measure and aggregation/dimension/OD semantics. Condition changes or
    corrected roles cannot make a known evaluation family eligible for training.
    Unsupported stays one family until a separately reviewed taxonomy exists.
    """
    raw = flatten_source(payload)
    if raw.get('unsupported'):
        return 'unsupported'
    measures = sorted([c.get('concept'), c.get('subtype')] for c in raw['concepts']
                      if c.get('concept') in {'AMOUNT', 'PROPORTION'})
    od = sorted((c.get('attributes') or {}).get('od_role', c.get('od_role', ''))
                for c in raw['concepts'] if c.get('concept') == 'LOCATION')
    factors = {k: v for k, v in raw['factors'].items() if k in {
        'aggregation', 'rollup', 'bucket', 'answer', 'dimension', 'dimension_target', 'order', 'vicinity'}}
    if factors.get('answer') == 'value':
        factors.pop('answer')
    return digest([measures, sorted(x for x in od if x), factors])


class Protection:
    """Exact questions, declared IDs and inferred templates from reserved sources.

    Unknown/unparseable gold is reported. A human still checks paraphrase lineage;
    automatic absence of a match is never a semantic correctness certification.
    """
    def __init__(self):
        self.questions, self.ids, self.templates, self.families = set(), set(), set(), set()
        self.paths, self.issues = [], []

    def add(self, question=None, payload=None, identifiers=()):
        if question:
            self.questions.add(question_key(question))
        self.ids.update(str(x) for x in identifiers if x)
        if payload is not None:
            try:
                self.templates.add(template_key(as_record(payload)))
                self.families.add(family_key(payload))
            except (ValueError, TypeError, KeyError) as error:
                self.issues.append(str(error))

    def visit(self, item):
        if isinstance(item, list):
            for child in item:
                self.visit(child)
        elif isinstance(item, dict):
            self.add(item.get('question'), item.get('golden', item.get('grounding')),
                     [item.get(k) for k in ('id', 'intent', 'intent_id', 'parent_intent', 'family')])
            # Some question sets have labels but no raw grounding. Protect the
            # default semantic family as well; no guessed target is exported.
            if not item.get('golden') and not item.get('grounding'):
                labels = item.get('expected_concepts', [])
                concepts = []
                for i, label in enumerate(labels):
                    if isinstance(label, str) and '/' in label and ':' in label:
                        concept, rest = label.split('/', 1)
                        subtype, role = rest.split(':', 1)
                        concepts.append(dict(id=str(i), concept=concept, subtype=subtype, role=role))
                if concepts:
                    self.add(payload={'concepts': concepts, 'factors': {}})
            for child in item.values():
                if isinstance(child, (dict, list)):
                    self.visit(child)

    @classmethod
    def current(cls, gold_dir):
        obj = cls()
        history = Path(gold_dir) / 'corpus_manifest.json'
        if history.exists():
            obj.paths.append(history.resolve())
            previous = json.loads(history.read_text(encoding='utf-8')).get('protection', {}).get('fingerprints', {})
            for name in ('questions', 'ids', 'templates', 'families'):
                values = previous.get(name, [])
                if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                    raise ValueError(f'Invalid historical protection fingerprints: {name}')
                getattr(obj, name).update(values)
        import paraphrase_corpus as P
        for path in sorted(reserved_sources()):
            obj.paths.append(path)
            document = yaml.safe_load(path.read_text(encoding='utf-8'))
            if isinstance(document, dict) and 'intents' in document:
                # Reuse evaluation's flat aggregation expansion, not a duplicate.
                document = copy.deepcopy(document)
                problems = P.expand_aggregation(document)
                if problems:
                    obj.issues.extend(str(p) for p in problems)
            obj.visit(document)
        # Changing corpus versions must never release an old validation family.
        valid_paths = {Path(gold_dir).resolve() / 'sft_valid.jsonl'}
        baseline = ROOT / 'training/generated/sft_valid.jsonl'
        if baseline.exists():
            valid_paths.add(baseline.resolve())
        valid_paths.update(p.resolve() for p in (ROOT / 'training/annotations/generated/corpora').glob('*/sft_valid.jsonl'))
        for path in sorted(valid_paths):
            obj.paths.append(path)
            for row in read_jsonl(path):
                obj.add(row['messages'][1]['content'], json.loads(row['messages'][-1]['content']),
                        [row['metadata'].get(k) for k in ('source_record_id', 'parent_intent', 'family')])
        for path in sorted((ROOT / 'training/experiments').glob('*/items.json')):
            obj.paths.append(path)
            items = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(items, list):
                raise ValueError(f'Protected pilot items must be a list: {path}')
            obj.visit([r for r in items if r.get('split') != 'train'])
        return obj

    def reasons(self, question, payload, identifiers=()):
        reasons = []
        if question_key(question) in self.questions:
            reasons.append('protected_question')
        if self.ids.intersection(str(x) for x in identifiers if x):
            reasons.append('protected_parent_or_family')
        if payload is not None:
            if template_key(as_record(payload)) in self.templates:
                reasons.append('protected_semantic_template')
            if family_key(payload) in self.families:
                reasons.append('protected_semantic_family')
        return reasons

    def manifest(self):
        return {'source_hashes': {str(p): sha256(p) for p in self.paths},
                'questions': len(self.questions), 'ids': len(self.ids),
                'templates': len(self.templates), 'semantic_families': len(self.families),
                'fingerprints': {name: sorted(getattr(self, name)) for name in ('questions', 'ids', 'templates', 'families')},
                'issues': self.issues, 'policy': 'No override for protected questions/families; human lineage check also required'}


def inventory(gold_dir, source):
    rows = {s: read_jsonl(Path(gold_dir) / f'sft_{s}.jsonl') for s in ('train', 'valid')}
    document = yaml.safe_load(Path(source).read_text(encoding='utf-8'))
    all_rows = rows['train'] + rows['valid']
    observed = coverage(all_rows)
    measures = {f'{c.value}/{s}': 0 for c, s in sorted(measure_types(), key=lambda x: (x[0].value, x[1]))}
    sources, values, stages, dimensions, od_roles = (Counter() for _ in range(5))
    od_dimensions = Counter()
    factor_values = {k: Counter() for k in FACTOR_SPECS}
    for row in all_rows:
        payload = json.loads(row['messages'][-1]['content'])
        f = payload.get('factors', {})
        for key, value in f.items():
            factor_values.setdefault(key, Counter())[canonical_json(value)] += 1
        stages[canonical_json({k: f[k] for k in ('bucket', 'aggregation', 'rollup', 'answer') if k in f})] += 1
        if f.get('dimension'):
            dimensions[f"{f['dimension']}:{f.get('dimension_target', 'default')}"] += 1
            if any(c.get('subtype') == 'trip_count' and c.get('role') == 'MEASURE'
                   for c in payload.get('concepts', [])):
                od_dimensions[f"{f['dimension']}:{f.get('dimension_target', 'both')}"] += 1
        for c in payload.get('concepts', []):
            sources[f"{c.get('source')}:{c.get('role')}"] += 1
            values[f"{c.get('source')}:{'present' if 'value' in c else 'absent'}"] += 1
            role = (c.get('attributes') or {}).get('od_role')
            if role:
                od_roles[role] += 1
            key = f"{c['concept']}/{c['subtype']}"
            if c['role'] == 'MEASURE':
                measures[key] = measures.get(key, 0) + 1
    originals = document.get('examples', [])
    human_pending = sum(not r.get('reviewed_by') or '사용자 검토 전' in r.get('reviewed_by', '') for r in originals)
    pairs = {s: read_jsonl(Path(gold_dir) / f'dpo_{s}.jsonl') for s in ('train', 'valid')}
    gaps = [{'type': 'rare_measure', 'key': key, 'count': count} for key, count in measures.items() if count < 3]
    if not od_roles:
        gaps.append({'type': 'od_scope', 'count': 0})
    if not od_dimensions:
        gaps.append({'type': 'od_dimension', 'count': 0})
    if human_pending:
        gaps.append({'type': 'human_review_pending', 'count': human_pending})
    factor_inventory = {key: observed['distributions']['factor'].get(key, 0) for key in FACTOR_SPECS}
    gaps.extend({'type': 'missing_factor', 'key': key, 'count': count}
                for key, count in factor_inventory.items() if count == 0)
    return {'sft': {s: coverage(r) for s, r in rows.items()}, 'overall': observed,
            'dpo': {s: coverage(r) for s, r in pairs.items()},
            'ontology': {c.value: sorted(s) for c, s in CONCEPT_SUBTYPES.items()},
            'roles': [r.value for r in FunctionalRole], 'factors': sorted(FACTOR_SPECS),
            'factor_inventory': factor_inventory,
            'factor_values': {k: dict(v) for k, v in factor_values.items()},
            'measure_inventory': measures, 'source_role': dict(sources), 'source_value': dict(values),
            'measure_definitions': {name: {'kind': spec.kind, 'undefined_reducers': sorted(spec.undefined),
                                          'day_composable': sorted(spec.day_composable), 'evidence': spec.evidence}
                                    for name, spec in sorted(MEASURES.items())},
            'factor_definitions': {name: {'kind': spec.kind, 'values': sorted(spec.values),
                                         'pattern': spec.pattern.pattern if spec.pattern else None, 'meaning': spec.meaning}
                                   for name, spec in sorted(FACTOR_SPECS.items())},
            'aggregation_stages': dict(stages), 'od_roles': dict(od_roles), 'dimensions': dict(dimensions),
            'od_dimensions': dict(od_dimensions), 'od_dimension_sample_count': sum(od_dimensions.values()),
            'original_count': len(originals), 'human_review_pending': human_pending, 'gaps': gaps,
            'note': 'Coverage and downstream validity do not certify question semantics.'}
