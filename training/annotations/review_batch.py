"""Read-only prioritized human review views of existing eligible candidates.

No new candidates, decisions, model inference, or corpus export are performed.
"""
import argparse
import copy
import json
import re
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import yaml

from geoflow.compiler import compile_plan
from geoflow.composer import MacroComposer
from geoflow.errors import GeoFlowError
from geoflow.grounding import parse_grounding
from geoflow.measures import MEASURES
from geoflow.providers import profile_for
from training.annotations.inventory import Protection, digest
from training.annotations.workflow import load_queue, save_json
from training.data.canonicalize import canonical_json, flatten_source, serialize_planner_target
from training.data.common import ROOT, provenance, sha256, write_jsonl
from training.data.validation import assess

CATEGORY_PRIORITY = {
    'gold_re_review': 1, 'source_role_value_factor': 2, 'aggregation': 3,
    'od': 4, 'rare_measure': 5, 'unsupported_ambiguity': 6, 'train_hard_negative': 7,
}
LABELS = {'gold_re_review': '기존 gold 재검토', 'source_role_value_factor': 'source/role/value/factor',
          'aggregation': 'inner/outer 집계 및 stage contrast', 'od': 'OD direction/dimension/target',
          'rare_measure': 'rare MEASURE', 'unsupported_ambiguity': 'unsupported/ambiguity',
          'train_hard_negative': 'train-origin hard negative'}


def category(row):
    kind = row['candidate_type']
    if kind == 'semantic_negative':
        return 'aggregation' if row['negative_type'] == 'aggregation_stage_swap' else 'od'
    if kind == 'aggregation_stage':
        return 'aggregation'
    if kind in {'od_scope', 'od_dimension'}:
        return 'od'
    if kind in {'unsupported_boundary', 'ambiguity_boundary'}:
        return 'unsupported_ambiguity'
    if kind == 'hard_negative':
        return 'train_hard_negative'
    if kind not in CATEGORY_PRIORITY:
        raise ValueError(f'Unknown review category: {kind}')
    return kind


def prioritized(rows):
    eligible = [copy.deepcopy(r) for r in rows if r['eligibility']['eligible_after_human_review']]
    if any(r['diagnostic_only'] or r['eligibility']['training_blockers'] for r in eligible):
        raise ValueError('Diagnostic/protected row in eligible review selection')
    def key(row):
        cat = category(row)
        if cat == 'gold_re_review':
            sid = row['provenance']['source_record_id']
            return (CATEGORY_PRIORITY[cat], int(re.search(r'\d+', sid).group()), '', row['candidate_id'])
        # Keep a question's gold and semantic contrast adjacent, before moving
        # to the next contrast sibling. Stable source order is the final tie break.
        return (CATEGORY_PRIORITY[cat], row['parent_intent'], row['question'],
                int(row['proposed_rejected'] is not None), row['candidate_id'])
    return sorted(eligible, key=key)


def compile_diagnostic(payload, question):
    """Extra CPU-only policy check; never execute tools or alter grounding."""
    profile = profile_for('mock', 'legacy')
    result = {'provider': 'mock/TIMS', 'mode': 'legacy', 'reference_date': '2026-09-25',
              'compile_ok': False, 'execution_tested': False}
    try:
        plan = MacroComposer().compose(parse_grounding(copy.deepcopy(payload), question))
        compile_plan(plan, reference_date=date(2026, 9, 25), contract=profile.contract,
                     date_policy=profile.date_policy, delegation=profile.delegation)
        result['compile_ok'] = True
    except (GeoFlowError, ValueError, TypeError) as error:
        result.update(error_code=getattr(error, 'code', 'INVALID_REVIEW_STRUCTURE'), error_detail=str(error))
    return result


def prediction_views(reports, question):
    out = {}
    for label, (path, report) in reports.items():
        matches = [r for r in report['records'] if r['question'] == question]
        if len(matches) > 1:
            raise ValueError(f'Duplicate model observations for question: {label}')
        if not matches:
            out[label] = {'available': False, 'reason': '이 질문에 대한 기존 pilot prediction 없음. 새 inference는 실행하지 않음.'}
            continue
        r = matches[0]
        # The review batch has only train questions. Linked dev evidence is never
        # displayed as if it were a prediction for a newly authored question.
        if r['split'] != 'train':
            raise ValueError('Protected model observation cannot enter corpus review batch')
        try:
            raw = json.loads(r['raw_text'])
            raw_quality = assess(raw, question, normalize=False)
            runtime_quality = assess(raw, question)
        except (ValueError, TypeError) as error:
            raw, raw_quality, runtime_quality = None, {'parse_ok': False, 'error_detail': str(error)}, None
        out[label] = {'available': True, 'source': str(path), 'source_record_id': r['id'],
                      'split': r['split'], 'raw_text': r['raw_text'], 'raw_grounding': raw,
                      'strict_raw_quality': raw_quality, 'production_quality': runtime_quality,
                      'pilot_observation': {k: r.get(k) for k in ('grounding_exact', 'planner_contract_ok',
                                                'status', 'error', 'composed', 'validated', 'validation_codes', 'executed')},
                      'note': '과거 runtime normalization/repair 결과와 strict raw 검사를 구분한다.'}
    return out


def advice(row, predictions, compilation):
    """Grounded recommendations, independent of the actual pending status."""
    payload = row['proposed_grounding']
    f = payload.get('factors', {})
    flags, concerns, reasons, references = [], [], [], ['geoflow/grounding.py', 'geoflow/factors.py']
    cat = category(row)
    if any(p['available'] and p['pilot_observation'].get('grounding_exact') is False for p in predictions.values()):
        flags.append('gold_vs_model_requires_review')
        concerns.append('Gold도 미검토 원본이다. 모델의 오류 코드만으로 gold를 승인하지 말고 원문과 비교한다.')
    if any(p['available'] and p['strict_raw_quality'].get('parse_ok') is False and
           (p.get('production_quality') or {}).get('parse_ok') is True for p in predictions.values()):
        flags.append('legacy_normalization_masks_raw_contract')
        concerns.append('모델의 legacy taxi_type concept 등이 runtime에서 승격된다. Gold target은 직접 factors로 출력해야 한다.')
    if f.get('bucket'):
        flags.append('aggregation_stage_review_required')
        reasons.append(f"구간={f['bucket']}, inner={f.get('aggregation')}, outer={f.get('rollup')}, answer={f.get('answer', 'value')}를 원문과 대응.")
        concerns.append('평균들의 평균과 전체 평균, 값 반환과 주/월 선택을 분리해서 판정한다.')
        references += ['geoflow/aggregation.py', 'README.md:463']
    if cat == 'od':
        flags.append('od_direction_target_review_required')
        od = [{'name': c.get('value', {}).get('name'), 'od_role': c.get('attributes', {}).get('od_role')}
              for c in payload['concepts'] if c.get('concept') == 'LOCATION']
        reasons.append(f"장소 filter od_role={canonical_json(od)}; 그룹 dimension={f.get('dimension')}, dimension_target={f.get('dimension_target')}.")
        concerns.append('장소의 승/하차 filter와 그 반대편을 묶는 dimension_target을 혼동하지 않는다.')
        references += ['geoflow/operator_registry.py:435', 'geoflow_macros/od_event_to_measure.yaml']
    if row['proposed_rejected'] is not None:
        flags.append('chosen_rejected_semantic_preference_review')
        concerns.append('추천 accepted는 pair 전체에 대한 제안이다. chosen이 맞고 rejected가 실제로 틀렸다는 사람이 확인해야 한다.')
    measures = [c['subtype'] for c in payload.get('concepts', []) if c['role'] == 'MEASURE']
    unclear_subtype = bool(set(measures) & {'active_taxi_count', 'active_taxi_ratio'})
    if unclear_subtype:
        flags += ['subtype_definition_uncertain', 'semantic_ambiguity']
        concerns.append('active_taxi_count는 하루 고유 대수, active_taxi_ratio는 집단 비율이다. 여러 날 평균/중앙값의 표본 단위와 분모가 확인되지 않았다.')
        if f.get('bucket'):
            flags.append('aggregation_stage_interpretation_uncertain')
        references += ['geoflow/measures.py:88', 'schemas/tims.yaml:175', 'README.md:414']
        for name in measures:
            if name in MEASURES:
                reasons.append(f"{name}: {MEASURES[name].evidence}")
    if compilation.get('compile_ok') is False:
        flags.append('production_support_boundary_uncertain')
        concerns.append(f"Grounding은 compose/validate되지만 TIMS legacy static compile은 {compilation.get('error_code')}이다. 의미 gold와 product 지원 라벨의 일치 여부를 검토한다. Unsupported로 자동 변경하지 않는다.")
        references += ['geoflow/compiler.py:101', 'README.md:480']
    if any(c.get('value', {}).get('name') in {'솔빛동', '온유동', '해솔동', '나래구'}
           for c in payload.get('concepts', []) if isinstance(c.get('value'), dict)):
        flags.append('synthetic_location_context_review')
        concerns.append('합성 지명/범위를 쓰는 annotation이다. Grounding-level corpus 용도와 실제 provider 지명 지원을 구분한다.')
    flags.append('independent_paraphrase_lineage_review')
    concerns.append('자동 family 검사 외에 사람이 평가 질문의 재표현/지역 교체인지 확인해야 한다.')
    if unclear_subtype or not compilation.get('compile_ok'):
        recommendation = 'needs_fix'
        rationale = '정의 또는 product 지원 경계가 미확정이다. JSON을 임의로 고치기 전에 annotation 용도/지원 라벨을 사람이 확정해야 한다.'
    else:
        recommendation = 'accepted'
        rationale = '명시된 의미와 production 어휘의 대응이 확인 가능한 제안이다. 아래 필드 대응과 원문/lineage를 사람이 확인한 경우에만 수락한다. Validator PASS만을 근거로 삼지 않는다.'
    if not reasons:
        reasons.append('장소는 user/value + SUBCOND, EVENT와 MEASURE는 implicit SUPPORT/MEASURE; 날짜/택시 유형은 factors로 분리.')
    return {'recommendation': recommendation, 'recommendation_reason': rationale,
            'field_interpretation': reasons, 'flags': sorted(set(flags)),
            'uncertainty': {name: name in flags for name in (
                'semantic_ambiguity', 'aggregation_stage_interpretation_uncertain',
                'od_direction_target_uncertain', 'subtype_definition_uncertain',
                'gold_vs_model_requires_review')},
            'why_review': concerns, 'references': sorted(set(references)), 'advisory_only': True}


def view(row, index, originals, reports):
    question = row['question']
    matching = [r for r in originals if r['question'] == question]
    if len(matching) > 1:
        raise ValueError('Duplicate existing gold question')
    old = matching[0] if matching else None
    predictions = prediction_views(reports, question)
    compilation = compile_diagnostic(row['proposed_grounding'], question)
    commentary = advice(row, predictions, compilation)
    result = {'batch_item_id': f'RB001-{index:02d}', 'candidate_id': row['candidate_id'],
              'candidate_hash': row['candidate_hash'], 'status': row['status'], 'category': category(row),
              'priority': CATEGORY_PRIORITY[category(row)], 'candidate_type': row['candidate_type'],
              'question': question, 'proposed_grounding': row['proposed_grounding'],
              'proposed_rejected': row['proposed_rejected'], 'negative_type': row.get('negative_type'),
              'existing_grounding': old['grounding'] if old else None,
              'existing_grounding_flat': json.loads(serialize_planner_target(flatten_source(old['grounding']))) if old else None,
              'existing_gold_id': old['id'] if old else None, 'existing_gold_note': old.get('note') if old else None,
              'predictions': predictions,
              'proposed_quality': {'strict_raw': assess(row['proposed_grounding'], question, normalize=False),
                                   'production': assess(row['proposed_grounding'], question)},
              'rejected_quality': assess(row['proposed_rejected'], question) if row['proposed_rejected'] is not None else None,
              'static_compilation': compilation, 'parent_intent': row['parent_intent'],
              'eligibility': row['eligibility'], 'diagnostic_only': row['diagnostic_only'], **commentary}
    result['review_view_hash'] = digest(result)
    return result


def workbook(path, batch, order):
    """Two distinct read-only sheets: batch comparisons and eligible-46 ordering."""
    columns = [('batch_item_id', 'Batch ID'), ('status', 'Actual status'), ('category', 'Category'),
               ('question', 'Question'), ('recommendation', 'Advisory recommendation'),
               ('recommendation_reason', 'Recommendation reason'), ('flags', 'Attention flags'),
               ('why_review', 'Why review'), ('proposed_grounding', 'Proposed grounding (flat)'),
               ('existing_grounding', 'Existing gold (source representation)'),
               ('existing_grounding_flat', 'Existing gold (flat projection)'),
               ('base_prediction', 'Base actual output'), ('sft_prediction', 'SFT actual output'),
               ('dpo_prediction', 'DPO actual output'), ('proposed_rejected', 'Proposed rejected / contrast'),
               ('proposed_quality', 'Proposed parse / compose / validate'),
               ('rejected_quality', 'Rejected parse / compose / validate'),
               ('model_quality', 'Model raw / production quality'), ('static_compilation', 'TIMS static compile (no execution)'),
               ('field_interpretation', 'Field interpretation'), ('existing_gold_note', 'Existing gold note'),
               ('references', 'Evidence references'), ('uncertainty', 'Uncertainty flags (false = no identified ambiguity)'),
               ('candidate_id', 'Original candidate ID'),
               ('candidate_hash', 'Original candidate hash'), ('review_view_hash', 'Review view hash')]
    display = []
    for row in batch:
        r = dict(row)
        for label in ('Base', 'SFT', 'DPO'):
            p = row['predictions'][label]
            r[label.lower() + '_prediction'] = p['raw_text'] if p['available'] else p['reason']
        r['model_quality'] = {k: {x: v[x] for x in ('strict_raw_quality', 'production_quality', 'pilot_observation')}
                              if v['available'] else {'available': False} for k, v in row['predictions'].items()}
        display.append(r)
    sheets = [('Review_batch_001', columns, display), ('Eligible_46_priority',
              [(k, k) for k in ('rank', 'priority', 'category', 'candidate_id', 'status', 'question', 'batch_item_id')], order)]
    def letter(n):
        text = ''
        while n:
            n, rem = divmod(n - 1, 26)
            text = chr(65 + rem) + text
        return text
    files = {}
    for index, (name, cols, data) in enumerate(sheets, 1):
        xml_rows = []
        for i, cells in enumerate([[label for _, label in cols]] + [[r.get(k, '') for k, _ in cols] for r in data], 1):
            parts = []
            for j, value in enumerate(cells, 1):
                text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
                text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
                if len(text) > 32767:
                    raise ValueError('Review cell exceeds Excel limit; full evidence must not be silently truncated')
                parts.append(f'<c r="{letter(j)}{i}" t="inlineStr" s="{1 if i==1 else 0}"><is><t xml:space="preserve">{escape(text)}</t></is></c>')
            xml_rows.append(f'<row r="{i}" ht="{30 if i==1 else 120}" customHeight="1">' + ''.join(parts) + '</row>')
        widths = ''.join(f'<col min="{j}" max="{j}" width="{65 if j in (4,9,10,11,12,13,14,15) and index==1 else 32}" customWidth="1"/>' for j in range(1,len(cols)+1))
        files[f'xl/worksheets/sheet{index}.xml'] = (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0"><pane xSplit="4" ySplit="1" topLeftCell="E2" activePane="bottomRight" state="frozen"/></sheetView></sheetViews>'
            f'<cols>{widths}</cols><sheetData>' + ''.join(xml_rows) + f'</sheetData><autoFilter ref="A1:{letter(len(cols))}{len(data)+1}"/></worksheet>')
    files['[Content_Types].xml'] = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' +
        ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in (1,2)) + '</Types>')
    files['_rels/.rels'] = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    files['xl/workbook.xml'] = ('<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' +
                              ''.join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i,(name,_,_) in enumerate(sheets,1)) + '</sheets></workbook>')
    files['xl/_rels/workbook.xml.rels'] = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
        ''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in (1,2)) +
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    files['xl/styles.xml'] = ('<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value.encode('utf-8'))


def build(queue, output, *, size=30):
    if not 20 <= size <= 30:
        raise ValueError('First human review batch must contain 20..30 records')
    queue, output = Path(queue).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Batch output already exists; do not overwrite review artifacts')
    rows, manifest = load_queue(queue)
    for path, expected in manifest['source_files'].items():
        if sha256(path) != expected:
            raise ValueError(f'Original source drift: {path}')
    protection = Protection.current(manifest['gold_dir'])
    if protection.manifest()['source_hashes'] != manifest['protection']['source_hashes']:
        raise ValueError('Protected source drift; do not weaken the original queue')
    ordered = prioritized(rows)
    if len(rows) != 96 or len(ordered) != 46 or len(rows)-len(ordered) != 50:
        raise ValueError('Expected frozen 96 / eligible 46 / protected 50 corpus')
    if any(r['status'] != 'pending' for r in rows):
        raise ValueError('Unexpected mutation of authoritative queue status')
    selected = ordered[:size]
    # Do not cut a chosen/contrast pair in half at a batch boundary.
    chosen_ids = {r['candidate_id'] for r in selected}
    for r in selected:
        siblings = [s for s in ordered if s['question']==r['question'] and category(s)==category(r)]
        if any(s['candidate_id'] not in chosen_ids for s in siblings):
            raise ValueError('Batch boundary cuts a contrast group; choose another size')
    source = ROOT / 'geoflow_examples/question_graph_examples.yaml'
    originals = yaml.safe_load(source.read_text(encoding='utf-8'))['examples']
    reports = {}
    for label, name in [('Base','base'),('SFT','sft_best'),('DPO','dpo_best')]:
        path = ROOT / f'training/experiments/thor_pilot_001/metrics/{name}.json'
        report = json.loads(path.read_text(encoding='utf-8'))
        if report['metadata'].get('complete') is not True or report['metadata'].get('prompt_hash') != manifest['prompt_hash']:
            raise ValueError('Pilot report provenance mismatch')
        reports[label] = path, report
    batch = [view(r, i, originals, reports) for i,r in enumerate(selected,1)]
    index = {r['candidate_id']: r['batch_item_id'] for r in batch}
    order = [{'rank': i, 'priority': CATEGORY_PRIORITY[category(r)], 'category': category(r),
              'candidate_id': r['candidate_id'], 'status': r['status'], 'question': r['question'],
              'batch_item_id': index.get(r['candidate_id'])} for i,r in enumerate(ordered,1)]
    summary = {'batch_records': len(batch), 'unique_questions': len({r['question'] for r in batch}),
               'categories': dict(Counter(r['category'] for r in batch)),
               'recommendations': {s: sum(r['recommendation']==s for r in batch) for s in ('accepted','rejected','needs_fix')},
               'actual_status': dict(Counter(r['status'] for r in batch)), 'eligible_total': len(order),
               'remaining_eligible': len(order)-len(batch), 'protected_excluded': 50,
               'old_gold_included': sum(r['candidate_type']=='gold_re_review' for r in batch),
               'old_gold_protected': sum(r['candidate_type']=='gold_re_review' and not r['eligibility']['eligible_after_human_review'] for r in rows),
               'accepted_annotations': 0, 'corpus_exported': False}
    output.mkdir(parents=True)
    write_jsonl(output / 'review_batch_001.jsonl', batch)
    write_jsonl(output / 'eligible_46_priority.jsonl', order)
    workbook(output / 'review_batch_001.xlsx', batch, order)
    write_readme(output, queue, batch, order, summary)
    info = provenance([queue/'review_queue.jsonl', queue/'manifest.json', source,
                       *[p for p,_ in reports.values()], Path(__file__), ROOT/'geoflow/compiler.py',
                       ROOT/'geoflow/providers.py', ROOT/'geoflow/tims_contract.py'], manifest['seed'])
    save_json(output / 'batch_manifest.json', {**info, 'batch_schema': 'geoflow-review-view-v1',
        'authoritative_queue': str(queue), 'summary': summary,
        'selected_candidate_ids': [r['candidate_id'] for r in batch],
        'output_hashes': {p.name: sha256(p) for p in output.iterdir()},
        'policy': 'Recommendations are advisory. No approval or generation is performed.'})
    return summary


def write_readme(output, queue, batch, order, summary):
    decisions = output / 'decisions.jsonl'
    corpus = ROOT / 'training/annotations/generated/corpora/reviewed_gold_v001'
    lines = ['# REVIEW_BATCH_001', '',
        '첫 human review 자료다. **추천은 참고용이며 actual status는 전부 pending**이다. GPU inference/training, 새 candidate 생성, production 수정, 자동 승인을 하지 않았다.', '',
        f"{summary['batch_records']} record / {summary['unique_questions']}개 서로 다른 질문. 같은 질문의 gold와 DPO contrast는 별도 승인 단위다. Corpus에는 동일 gold 질문을 한 번만 저장한다.", '',
        '## 파일과 검토 순서', '',
        '`review_batch_001.xlsx`의 첫 sheet는 question/proposed/existing/Base/SFT/DPO/contrast/검증을 나란히 보여준다. JSON은 wrap된 cell을 선택하거나 JSONL에서 전체를 확인한다. 새 질문에 과거 prediction이 없으면 없다고 적었다. 다른 dev 질문의 예측을 붙이지 않았다.', '',
        '`Eligible_46_priority` sheet 및 `eligible_46_priority.jsonl`에 포함 가능한 46건 전체를 우선순위대로 정리했다. 기존 gold 15건 중 보호된 6건은 batch에 넣지 않았다. 보호/진단 전용 50건은 원본 queue에 그대로 유지한다.', '',
        '| Priority | Category | Eligible | Batch |', '|---:|---|---:|---:|']
    for cat,p in CATEGORY_PRIORITY.items():
        lines.append(f"| {p} | {LABELS[cat]} | {sum(r['category']==cat for r in order)} | {summary['categories'].get(cat,0)} |")
    lines += ['', f"추천: accepted {summary['recommendations']['accepted']}, rejected {summary['recommendations']['rejected']}, needs_fix {summary['recommendations']['needs_fix']}. 실제 accepted=0.", '',
        '## 사람이 판정할 내용', '',
        '- user source는 단어가 질문에 등장한다는 의미가 아니라 주어진 값의 출처다. 장소 value와 SUBCOND, implicit EVENT SUPPORT/MEASURE, date/taxi_type factors를 확인한다.',
        '- aggregation은 구간 안, rollup은 구간 간이다. answer=value와 answer=bucket, 평균들의 평균과 전체 평균을 구분한다.',
        '- OD scope의 od_role은 장소 filter이고 dimension_target은 결과를 묶을 승/하차 쪽이다. Gold와 contrast 둘 다 validator PASS여도 둘 다 맞는 것은 아니다.',
        '- active_taxi_count/ratio의 기간 평균·중앙값/표본 단위는 정의를 확인해야 한다. 임의로 sum/unsupported로 바꾸지 않는다.',
        '- 추가 TIMS legacy static compilation은 production 모듈을 읽기 전용으로 재사용한 진단이며 실제 execution은 하지 않았다. 구간 선택 및 RPM bucket에서 UNVERIFIED_TIMS_CONTRACT가 발생한다. Grounding 의미가 명확해도 product 지원 라벨은 재검토해야 한다.',
        '- Base/SFT/DPO는 저장된 실제 raw 출력이다. strict raw 검사, production normalization 검사, 과거 pilot 결과를 구분한다. 실행 실패를 곧 grounding 오답으로 간주하지 않는다.',
        '- 합성 지명을 포함한 질문은 corpus의 grounding 용도와 실제 provider의 장소 지원을 구분해서 검토한다. Parent/paraphrase lineage도 확인한다.', '',
        '### 추천 needs_fix 항목', '']
    for r in batch:
        if r['recommendation']=='needs_fix':
            lines.append(f"- **{r['batch_item_id']}** ({r['candidate_id']}): {r['question']} — {', '.join(r['flags'])}")
    sample = batch[0]['candidate_id']
    lines += ['', '## 실제 판정 기록', '',
        'XLSX/JSONL은 비교용 view이다. 추천을 status로 복사하지 않는다. 검토 후 아래 명령으로 원본 candidate ID/hash에 판정을 남긴다. 사람이 판단한 경우에만 confirmation flag를 쓴다. 응답을 RB001-번호별로 제공해도 원본 candidate ID로 대응할 수 있다.', '',
        '```bash', 'python -m training.annotations.workflow decide \\', f'  --queue {queue} \\',
        f'  --decisions {decisions} \\', f'  --id {sample} --status needs_fix \\',
        "  --reviewer YOUR_NAME --reason '검토한 근거와 수정 필요 내용을 입력'", '```', '',
        '`--status accepted`에는 `--semantic-checks-confirmed`가 필요하다. Contrast/pair에는 chosen이 맞고 rejected가 틀린 이유를 적고 `--negative-is-wrong`도 지정한다. 수정할 JSON이 있으면 `--corrected-grounding` 또는 `--corrected-rejected`를 사용한다. `rejected`/`needs_fix`는 export되지 않는다.', '',
        '## 검토 후 import', '',
        '원본 96건 queue를 대상으로 batch 전용 decision audit만 읽는다. View JSONL을 training builder에 직접 넣지 않는다. Accepted gold가 서로 분리 가능한 2개 이상의 semantic/contrast family를 포함해야 train/validation export가 가능하다. 최소 DPO split coverage도 확인하고 아직 학습은 시작하지 않는다.', '',
        '```bash', 'python -m training.annotations.workflow import-reviewed \\', f'  --queue {queue} \\',
        f'  --decisions {decisions} \\', '  --version reviewed_gold_v001 \\', f'  --output {corpus} \\',
        '  --seed 42 --valid-fraction 0.2', '```', '',
        'Import는 queue/source/protection/prompt hash와 실제 semantic review attestation, canonical planner JSON, parse/compose/G1~G7, group leakage, identical pair를 다시 검사한다. 추천 accepted는 이 검사를 대신하지 않는다.']
    (output / 'REVIEW_BATCH_001.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue', default='training/annotations/generated/expansion_001')
    parser.add_argument('--output', default='training/annotations/generated/review_batch_001')
    parser.add_argument('--size', type=int, default=30)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args.queue,args.output,size=args.size),ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1,f'{error}\n')


if __name__=='__main__':
    main()
