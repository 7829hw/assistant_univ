"""Small curated proposals driven by observed failures, never auto gold."""
import copy
import json
from collections import Counter
from pathlib import Path

from geoflow.operator_mapping import event_subtype_for
from geoflow.types import CoreConcept
from training.annotations.inventory import digest
from training.data.canonicalize import canonical_json, semantic_key, serialize_planner_target
from training.data.negative_mutations import mutations
from training.data.validation import assess, chosen_ok


def measure_payload(concept, subtype, factors=None, places=()):
    event = event_subtype_for(CoreConcept(concept), subtype)
    if event is None:
        raise ValueError(f'No unique registry event: {concept}/{subtype}')
    concepts = [dict(id='event', concept='EVENT', subtype=event, role='SUPPORT', source='implicit'),
                dict(id='measure', concept=concept, subtype=subtype, role='MEASURE', source='implicit')]
    for i, (name, od_role) in enumerate(places):
        node = dict(id=f'place{i}', text=name, concept='LOCATION', subtype='place', role='SUBCOND',
                    source='user', value={'name': name, 'region': ''})
        if od_role:
            node['attributes'] = {'od_role': od_role}
        concepts.append(node)
    return json.loads(serialize_planner_target({'concepts': concepts, 'factors': factors or {}}))


def proposal(question, grounding, kind, family, rationale, *, provenance=None,
             rejected=None, expected_outcome='answered', diagnostic_only=False, evidence=None):
    """Each queue row is immutable; reviewers submit separate hash-bound decisions."""
    raw = dict(question=question, proposed_grounding=grounding, proposed_rejected=rejected,
               candidate_type=kind, parent_intent=family, semantic_family=family,
               rationale=rationale, expected_outcome=expected_outcome,
               diagnostic_only=diagnostic_only, provenance=provenance or {}, evidence=evidence or [])
    identifier = digest(raw)
    quality = assess(grounding, question) if grounding is not None else None
    row = {**raw, 'candidate_id': 'ann-' + identifier[:20], 'status': 'pending',
           'quality': quality, 'semantic_correctness': 'unreviewed',
           'suggestion_state': 'requires_semantic_review' if quality and chosen_ok(quality) else 'needs_fix_or_boundary_review',
           'review_checks': ['source_role_value', 'factor_evidence', 'aggregation_stages',
                             'od_direction', 'support_boundary', 'paraphrase_lineage']}
    if rejected is not None:
        row['rejected_quality'] = assess(rejected, question)
        row['negative_category'] = 'semantic' if row['rejected_quality'].get('outcome') in {'answered', 'unsupported'} else 'constraint'
    return row


def blueprints():
    """One bounded contrast family per capability; no evaluated question copying."""
    rows = []
    def add(q, concept, subtype, factors, kind, family, reason, places=(), outcome='answered'):
        rows.append(proposal(q, measure_payload(concept, subtype, factors, places), kind, family,
                             reason, provenance={'origin': 'authored_blueprint'}, expected_outcome=outcome))
    # Direct support/source/value/factor contrasts; pair siblings cannot split.
    for taxi, value in [('개인택시', 'private'), ('법인택시', 'corporate')]:
        add(f'2026년 9월 솔빛동 주변 {taxi}의 평균 가동 택시 대수는?', 'AMOUNT', 'active_taxi_count',
            {'date': '20260901-20260930', 'aggregation': 'avg', 'taxi_type': value, 'vicinity': True},
            'source_role_value_factor', 'new-active-count-average',
            '장소만 user/value; taxi_type/date/vicinity는 factors. EVENT/MEASURE는 implicit.', [('솔빛동', None)])
    add('2026년 9월 해솔동 개인택시 가동률의 중앙값은?', 'PROPORTION', 'active_taxi_ratio',
        {'date': '20260901-20260930', 'taxi_type': 'private', 'aggregation': 'med'},
        'source_role_value_factor', 'new-active-ratio-median',
        '개인택시는 taxi_type factor; place SUBCOND와 SUPPORT/MEASURE 역할을 분리.', [('해솔동', None)])
    # Missing subtype coverage; all mappings obtained from production registry.
    for concept, subtype, label, agg in [
        ('AMOUNT', 'passage_count', '통행 건수', None), ('AMOUNT', 'trip_count', '실차 구간 건수', None),
        ('AMOUNT', 'fare', '요금', 'min'), ('AMOUNT', 'speed', '주행 속도', 'max'),
        ('AMOUNT', 'rpm', '엔진 회전수', 'avg'), ('AMOUNT', 'active_taxi_count', '가동 택시 대수', 'avg'),
        ('PROPORTION', 'vacant_ratio', '공차율', 'avg'), ('PROPORTION', 'active_taxi_ratio', '가동률', 'min')]:
        word = {'min': '최솟값', 'max': '최댓값', 'avg': '평균', 'sum': '합계', None: ''}[agg]
        question = f'2026년 9월 온유동 택시의 {label}' + (f'의 {word}은?' if word else '는?')
        places = [('온유동', None)]
        if subtype == 'trip_count':
            question = '2026년 9월 온유동에서 승차한 실차 구간 건수는?'
            places = [('온유동', 'pickup')]
        add(question, concept, subtype,
            {'date': '20260901-20260930', **({'aggregation': agg} if agg else {})},
            'rare_measure', 'new-active-count-average' if subtype == 'active_taxi_count' else f'new-{subtype}-single-{agg}',
            '현재 SFT에 없는 subtype. 용어 정의와 provider 지원 범위도 사람이 확인.', places)
    for inner, outer, wording in [('avg', 'max', '주마다 평균 낸 엔진 회전수 중 최댓값'),
                                  ('max', 'avg', '주마다 구한 엔진 회전수 최댓값의 평균')]:
        add(f'2026년 9월 솔빛동 택시의 {wording}은?', 'AMOUNT', 'rpm',
            {'date': '20260901-20260930', 'bucket': 'week', 'aggregation': inner, 'rollup': outer},
            'aggregation_stage', 'new-rpm-week-stage-contrast',
            '대조군을 함께 검토: aggregation은 구간 안, rollup은 구간 간 집계.', [('솔빛동', None)])
    for inner, outer, wording in [('avg', 'min', '월별 평균 가동 택시 대수 중 최솟값'),
                                  ('min', 'avg', '월별 가동 택시 대수 최솟값의 평균')]:
        add(f'2026년 8월과 9월 온유동의 {wording}은?', 'AMOUNT', 'active_taxi_count',
            {'date': '20260801-20260930', 'bucket': 'month', 'aggregation': inner, 'rollup': outer},
            'aggregation_stage', 'new-active-count-month-stage-contrast',
            '두 집계 순서는 다른 질문이다. 통계 단위의 타당성까지 검토.', [('온유동', None)])
    for origin, destination in [('솔빛동', '온유동'), ('온유동', '솔빛동')]:
        add(f'2026년 9월 {origin}에서 승차하여 {destination}에서 하차한 실차 구간 건수는?',
            'AMOUNT', 'trip_count', {'date': '20260901-20260930'}, 'od_scope', 'new-od-trip-count-direction',
            '출발지는 pickup, 도착지는 dropoff. 방향 대조군은 같은 family.', [(origin, 'pickup'), (destination, 'dropoff')])
    for direction, word, target, target_word in [('pickup', '승차', 'dropoff', '하차지'),
                                               ('dropoff', '하차', 'pickup', '승차지')]:
        add(f'2026년 9월 솔빛동에서 {word}한 실차 구간을 읍면동 {target_word}별로 세면 건수가 많은 4곳은?',
            'AMOUNT', 'trip_count', {'date': '20260901-20260930', 'dimension': 'emd',
                                    'dimension_target': target, 'order': 'top', 'limit': 4},
            'od_scope', 'new-od-filter-and-opposite-ranking',
            '장소 scope의 od_role과 group dimension_target은 서로 다른 의미.', [('솔빛동', direction)])
    for target, word in [('pickup', '승차지'), ('dropoff', '하차지'), ('both', '승차지와 하차지 조합')]:
        add(f'2026년 9월 읍면동 {word}별 실차 구간 건수가 적은 4개 그룹은?', 'AMOUNT', 'trip_count',
            {'date': '20260901-20260930', 'dimension': 'emd',
             'dimension_target': target, 'order': 'bottom', 'limit': 4},
            'od_dimension', 'new-od-trip-count-bottom-ranking',
            'dimension은 그룹 기준; 승하차 단어를 LOCATION value로 만들지 않는다.')
    for q, family, reason in [
        ('2026년 9월 택시 운전자의 평균 심박수는?', 'boundary-unavailable-heart-rate', '정의되지 않은 metric; unsupported 경계를 확인.'),
        ('2026년 9월 택시 엔진 회전수의 모든 주별 값을 목록으로 보여줘.', 'boundary-rpm-timeseries', 'bucket 결과 전체 목록 지원 여부를 계약에서 확인.'),
        ('솔빛동 택시의 다음 달 평균 엔진 회전수를 예측해줘.', 'boundary-rpm-forecast', '미래 예측은 과거 데이터 집계와 다르다.')]:
        rows.append(proposal(q, {'unsupported': True}, 'unsupported_boundary', family, reason,
                             provenance={'origin': 'authored_blueprint'}, expected_outcome='unsupported'))
    add('2026년 9월 솔빛동 택시의 주별 엔진 회전수 최댓값은?', 'AMOUNT', 'rpm',
        {'date': '20260901-20260930', 'bucket': 'week', 'rollup': 'max'},
        'ambiguity_boundary', 'new-rpm-week-stage-contrast',
        '구간 안 집계가 불명확. clarification을 unsupported로 바꾸지 않는다. 학습 export 금지.',
        [('솔빛동', None)], outcome='needs_clarification')
    return rows


def failure_hints(gold, predicted, quality):
    """Field differences are reviewer hints, not automatic semantic labels."""
    hints = []
    if gold.get('unsupported') != predicted.get('unsupported'):
        hints.append('unsupported_boundary')
    gf, pf = gold.get('factors', {}), predicted.get('factors', {})
    for key in sorted(set(gf) | set(pf)):
        if gf.get(key) != pf.get(key):
            hints.append('aggregation_stage' if key in {'aggregation', 'rollup', 'bucket', 'answer'}
                         else 'od_dimension' if key in {'dimension', 'dimension_target'}
                         else 'factor_' + ('omission' if key not in pf else 'hallucination' if key not in gf else 'value'))
    def fields(payload, keys):
        return sorted(canonical_json({k: c.get(k) for k in keys}) for c in payload.get('concepts', []))
    for keys, name in [(['concept', 'subtype'], 'concept_subtype'),
                       (['concept', 'subtype', 'role'], 'role'),
                       (['concept', 'subtype', 'source', 'value'], 'source_value')]:
        if fields(gold, keys) != fields(predicted, keys):
            hints.append(name)
    def od_nodes(payload):
        return sorted(canonical_json({'od_role': (c.get('attributes') or {}).get('od_role'), 'value': c.get('value')})
                      for c in payload.get('concepts', []) if (c.get('attributes') or {}).get('od_role'))
    if od_nodes(gold) != od_nodes(predicted):
        hints.append('od_scope')
    if quality.get('error_code'):
        hints.append(quality['error_code'])
    return sorted(set(hints)) or ['raw_contract_difference_requires_review']


def mine_predictions(paths, *, train_records=None):
    """Actual predictions only. Validation/dev are permanently diagnostic-only."""
    merged, issues, failures = {}, [], Counter()
    known_train = {r['metadata']['source_record_id']: r for r in train_records or []}
    for path in paths:
        document = json.loads(Path(path).read_text(encoding='utf-8'))
        label = document.get('metadata', {}).get('label', Path(path).stem)
        for r in document['records']:
            if r.get('grounding_exact') is True:
                continue
            failures.update(r.get('error_categories', []))
            try:
                rejected = json.loads(r['raw_text'])
                # Invalid JSON is triage evidence, not DPO syntax negatives.
                rejected = json.loads(serialize_planner_target(rejected))
                chosen = json.loads(serialize_planner_target(r['gold']))
                if semantic_key(chosen, infer_events=True) == semantic_key(rejected, infer_events=True):
                    continue
                quality = assess(rejected, r['question'])
                actual_train = r['split'] == 'train'
                if train_records is not None:
                    original = known_train.get(r['id'])
                    actual_train = actual_train and original is not None and original['messages'][1]['content'] == r['question']
                    if actual_train and semantic_key(json.loads(original['messages'][-1]['content'])) != semantic_key(chosen):
                        raise ValueError('Pilot chosen differs from frozen training annotation')
                hints = failure_hints(chosen, rejected, quality)
                key = digest([r['question'], chosen, rejected])
                evidence = dict(model=label, record_id=r['id'], split=r['split'],
                                source=str(path), error_categories=r.get('error_categories', []),
                                validation_codes=r.get('validation_codes', []), raw_text=r['raw_text'],
                                prompt_hash=document.get('metadata', {}).get('prompt_hash'))
                if key in merged:
                    merged[key]['evidence'].append(evidence)
                    # Never let inconsistent source splits weaken the quarantine.
                    merged[key]['diagnostic_only'] |= not actual_train
                else:
                    merged[key] = proposal(r['question'], chosen, 'hard_negative', r['intent_id'],
                                           '실측 모델 출력과 잠정 gold의 차이. 양쪽 의미를 사람이 판정해야 한다.',
                                           rejected=rejected, diagnostic_only=not actual_train,
                                           provenance={'origin': 'pilot_prediction', 'source_record_id': r['id'],
                                                       'split': r['split']}, evidence=[evidence])
                    merged[key]['failure_hints'] = hints
            except (ValueError, KeyError, TypeError) as error:
                issues.append({'source': str(path), 'id': r.get('id'), 'detail': str(error)})
    return list(merged.values()), {'excluded': issues, 'error_category_observations': dict(failures)}


def failure_driven_candidates(report, hard):
    """Select bounded blueprints using missing coverage and observed error fields.

    Linked pilot IDs explain why a capability needs annotations, not which gold
    to copy. Changing dates/places alone cannot bypass the family protection.
    """
    drivers = {
        'source_role_value_factor': {'source_value', 'role', 'factor_omission', 'factor_hallucination'},
        'aggregation_stage': {'aggregation_stage'}, 'od_scope': {'od_scope'},
        'od_dimension': {'od_dimension'}, 'unsupported_boundary': {'unsupported_boundary'},
        'ambiguity_boundary': {'aggregation_stage'},
    }
    selected = []
    for row in blueprints():
        matches = [r for r in hard if set(r.get('failure_hints', [])) & drivers.get(row['candidate_type'], set())]
        missing = []
        if row['candidate_type'] == 'rare_measure':
            missing = [f"{c['concept']}/{c['subtype']}" for c in row['proposed_grounding']['concepts']
                       if c['role'] == 'MEASURE' and report['measure_inventory'].get(f"{c['concept']}/{c['subtype']}", 0) < 3]
        if row['candidate_type'] == 'od_scope' and not report['od_roles']:
            missing.append('od_scope')
        if row['candidate_type'] == 'od_dimension' and not report['od_dimensions']:
            missing.append('od_dimension')
        if not matches and not missing:
            continue
        row['generation_trigger'] = {'coverage_gaps': missing, 'pilot_failure_candidates': len(matches)}
        row['evidence'] = [{'record_id': e['record_id'], 'model': e['model'], 'split': e['split'],
                            'source': e['source'], 'purpose': 'diagnostic evidence, independently authored question'}
                           for r in matches[:3] for e in r['evidence']]
        selected.append(row)
    return selected


def semantic_negative_candidates(authored, *, seed=42):
    """One reviewable semantic contrast per OD/stage proposal; never auto DPO."""
    rows = []
    for gold in authored:
        kind = gold['candidate_type']
        if kind not in {'aggregation_stage', 'od_scope', 'od_dimension'}:
            continue
        payload = gold['proposed_grounding']
        if kind == 'od_dimension':
            rejected = copy.deepcopy(payload)
            old = rejected['factors']['dimension_target']
            rejected['factors']['dimension_target'] = {'pickup': 'dropoff', 'dropoff': 'pickup', 'both': 'pickup'}[old]
            negative_type = 'od_dimension_target_confusion'
        else:
            desired = ['aggregation_stage_swap'] if kind == 'aggregation_stage' else ['od_pickup_dropoff_swap', 'od_role_confusion']
            options = mutations(payload, seed=seed)
            mutation = next((m for name in desired for m in options if m['negative_type'] == name), None)
            if mutation is None:
                continue
            rejected, negative_type = mutation['payload'], mutation['negative_type']
        row = proposal(gold['question'], payload, 'semantic_negative', gold['parent_intent'],
                       '집계 단계/OD 방향만 바꾼 대조 출력. 의미가 실제로 틀렸는지 사람이 별도로 검토.',
                       rejected=rejected, provenance={'origin': 'synthetic_review_candidate', 'negative_type': negative_type},
                       evidence=gold['evidence'])
        row['negative_type'] = negative_type
        rows.append(row)
    return rows
