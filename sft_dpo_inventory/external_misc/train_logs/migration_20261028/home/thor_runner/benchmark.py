"""Frozen evaluation-only adapter over production pipeline and existing scorers."""
import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import evaluate_planner as E
import evaluate_vendor100 as V
from geoflow import providers
from geoflow.grounding import parse_grounding
from geoflow.pipeline import GeoFlowPipeline
from geoflow.validator import ALL_RULES
from training.data.common import production_prompt, sha256

DEST = ROOT / 'training/evaluations/vendor_100_baseline_001'
RAW = ROOT / 'training/runs/vendor_100_baseline_001'


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def verify():
    manifest = json.loads((DEST / 'manifest.json').read_text())
    assert hashlib.sha256(production_prompt().encode()).hexdigest() == manifest['prompt_hash']
    for path, digest in manifest['immutable_inputs'].items():
        assert sha256(ROOT / path) == digest, f'Input drift: {path}'
    assert sha256(__file__) == manifest['protocol']['runner_sha256']
    items = V.load_gold()['items']
    frozen = json.loads((DEST / 'frozen_questions.json').read_text())
    assert [(r['id'], r['question']) for r in items] == [(r['id'], r['question']) for r in frozen]
    assert len(items) == 100 and len({i['id'] for i in items}) == 100
    return manifest, items, {r['id']: r['categories'] for r in frozen}


def metrics(item, run, observed, calls):
    first = next((c['content'] for c in calls if not c.get('failed')), '') or ''
    gold = V.gold_grounding(item)  # Existing inverse-call evaluator reference, NOT vendor-authored grounding.
    raw = E.score_raw_grounding(first, dict(question=item['question'], golden=gold))
    want = E.concept_keys(parse_grounding(gold, item['question']))
    try:
        from geoflow.planner import parse_planner_json
        got = E.concept_keys(parse_grounding(parse_planner_json(first), item['question']))
    except Exception:
        got = []
    validation = run.validation or {}
    repair_attempted = any(a.get('repair_attempted') for a in run.attempts)
    return {**raw, 'concept_score': E.score_concepts(got, want),
            'composed': bool(run.plan), 'validated': validation.get('status') == 'OK',
            'checked_rules': validation.get('checked_rules', []),
            'validation_codes': validation.get('failed_rules', []),
            'repair_attempted': repair_attempted,
            'repair_succeeded': any(a.get('repair_result') == 'OK' for a in run.attempts),
            'real_execution_success': None,
            'mock_execution_success': bool(run.execution and run.execution.get('status') == 'OK')}


def run_model(label):
    manifest, items, categories = verify()
    from training.inference import HFClient
    import torch
    spec = manifest['models'][label]
    start = time.perf_counter()
    client = HFClient(manifest['model'], adapter=spec['adapter'], revision=manifest['model_revision'],
                      seed=manifest['seed'], max_new_tokens=manifest['decoding']['max_new_tokens'])
    assert client.policy.config._attn_implementation == 'sdpa'
    assert not client.policy.training
    generation = client.policy.generation_config.to_dict()
    generation.update(do_sample=False, use_cache=True, max_new_tokens=1024,
                      pad_token_id=client.tokenizer.pad_token_id)
    write(RAW / f'{label}_runtime.json', dict(model_load_seconds=time.perf_counter()-start,
          torch=torch.__version__, cuda=torch.version.cuda, device=torch.cuda.get_device_name(),
          capability=torch.cuda.get_device_capability(), attention=client.policy.config._attn_implementation,
          effective_generation_config=generation, chat_template_kwargs=client.config['chat_template_kwargs']))
    output = RAW / f'{label}_raw.jsonl'
    done = {}
    if output.exists():
        for line in output.read_text().splitlines():
            row = json.loads(line)
            assert row['protocol_hash'] == manifest['protocol_hash']
            assert row['model_hash'] == spec['identity_hash']
            assert row['id'] not in done
            done[row['id']] = row
    with output.open('a') as stream:
        for item in items:
            if item['id'] in done:
                assert done[item['id']]['question'] == item['question']
                continue
            recorder = V._RecordingClient(client)
            pipeline = GeoFlowPipeline.create(client=recorder, tool_executor=V._executor(),
                        aggregation_grounding='flat', clock=lambda: V.REFERENCE_DATE,
                        condition_check=False, execution_profile=providers.profile_for('mock', 'legacy'))
            assert hashlib.sha256(pipeline.planner.system_prompt().encode()).hexdigest() == manifest['prompt_hash']
            start = time.perf_counter()
            run = pipeline.run(item['question'])
            observed = V.run_item(SimpleNamespace(run=lambda q: run), item['question'])
            category, checks = V.score(item, observed)
            semantic, semantic_checks = V.score_semantic(item, observed)
            grounding_ok, diffs = V.grounding_check(item, observed['grounding'])
            row = dict(id=item['id'], question=item['question'], categories=categories[item['id']],
                       protocol_hash=manifest['protocol_hash'], model_hash=spec['identity_hash'],
                       metrics=metrics(item, run, observed, recorder.calls),
                       category=category, checks=checks, semantic_category=semantic,
                       semantic_checks=semantic_checks, grounding_ok=grounding_ok,
                       grounding_diffs=diffs, llm_calls=recorder.calls,
                       run=run.to_dict(), **observed)
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n'); stream.flush()
            print(json.dumps(dict(model=label,id=item['id'], outcome=run.outcome,
                  category=category,contract=row['metrics']['planner_contract_ok'],
                  grounding=grounding_ok,seconds=round(time.perf_counter()-start,2)),ensure_ascii=False),flush=True)
    torch.cuda.synchronize()
    runtime = json.loads((RAW / f'{label}_runtime.json').read_text())
    runtime.update(peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                   peak_reserved_bytes=torch.cuda.max_memory_reserved())
    write(RAW / f'{label}_runtime.json',runtime)


def rate(values):
    values = [v for v in values if v is not None]
    return dict(count=sum(bool(v) for v in values), total=len(values),
                rate=round(sum(bool(v) for v in values)/len(values),4) if values else None)


def summarize(rows):
    result={key:rate([r['metrics'][key] for r in rows]) for key in (
        'json_parse_ok','planner_contract_ok','grounding_exact','factor_exact',
        'composed','validated','repair_attempted','mock_execution_success','real_execution_success')}
    result['vendor_grounding_semantic_match']=rate([r['grounding_ok'] for r in rows])
    result['mock_vendor_call_answer_match']=rate([r['category']=='match' for r in rows])
    result['mock_semantic_match']=rate([r['semantic_category']=='match' for r in rows])
    for name in ('concept','subtype','role'):
        scores=[r['metrics']['concept_score'][name] for r in rows]
        matched=sum(s['matched'] for s in scores); total=sum(s['expected'] for s in scores)
        result[name]=dict(count=matched,total=total,rate=round(matched/total,4) if total else None)
    scores=[r['metrics']['factor_score'] for r in rows if r['metrics']['factor_score'] is not None]
    matched=sum(s['matched'] for s in scores)
    result['factor_precision']=dict(count=matched,total=sum(s['predicted'] for s in scores))
    result['factor_recall']=dict(count=matched,total=sum(s['expected'] for s in scores))
    result['G1_G7']={rule:rate([rule not in r['metrics']['validation_codes'] for r in rows
                             if rule in r['metrics']['checked_rules']]) for rule in ALL_RULES}
    result['outcomes']=dict(Counter(r['outcome'] for r in rows))
    result['error_codes']=dict(Counter(r['error_code'] for r in rows if r['error_code']))
    return result


def report():
    manifest, items, categories = verify()
    models={}
    for label in manifest['models']:
        rows=[json.loads(s) for s in (RAW / f'{label}_raw.jsonl').read_text().splitlines()]
        assert [r['id'] for r in rows] == [i['id'] for i in items]
        assert all(r['protocol_hash']==manifest['protocol_hash'] for r in rows)
        models[label]=rows
    base,sft,dpo=(models[x] for x in ('base','sft','sft_dpo'))
    paired={
        'base_to_sft_improvements':[b['id'] for a,b in zip(base,sft) if not a['grounding_ok'] and b['grounding_ok']],
        'sft_to_dpo_improvements':[b['id'] for a,b in zip(sft,dpo) if not a['grounding_ok'] and b['grounding_ok']],
        'sft_to_dpo_regressions':[b['id'] for a,b in zip(sft,dpo) if a['grounding_ok'] and not b['grounding_ok']],
        'all_fail':[a['id'] for a,b,c in zip(base,sft,dpo) if not any(x['grounding_ok'] for x in (a,b,c))]}
    result=dict(protocol_hash=manifest['protocol_hash'], complete=True,
        count=100, gold_scope=manifest['gold_scope'],
        metrics={k:summarize(v) for k,v in models.items()}, paired=paired,
        categories={cat:{k:summarize([r for r in v if cat in r['categories']]) for k,v in models.items()}
                    for cat in sorted({c for groups in categories.values() for c in groups})},
        runtime={k:json.loads((RAW / f'{k}_runtime.json').read_text()) for k in models})
    write(DEST / 'RESULTS.json',result)
    write(DEST / 'category_error_summary.json',{cat:{label:dict(Counter(
          difference[0] for r in rows if cat in r['categories'] for difference in r['grounding_diffs']))
          for label,rows in models.items()} for cat in result['categories']})
    cases={group:[dict(id=i,question=items[int(i)-1]['question'],
                 vendor_gold_calls=items[int(i)-1]['gold'],
                 predictions={label:dict(first_raw=rows[int(i)-1]['llm_calls'][0].get('content'),
                      final_grounding=rows[int(i)-1]['grounding'],
                      differences=rows[int(i)-1]['grounding_diffs'],
                      error_code=rows[int(i)-1]['error_code']) for label,rows in models.items()}) for i in ids]
           for group,ids in paired.items()}
    write(RAW / 'paired_examples.json',cases)
    write(DEST / 'paired_cases.json',{group:cases[group][:3] for group in cases})
    artifacts={str(p.relative_to(ROOT)):dict(sha256=sha256(p),bytes=p.stat().st_size)
              for p in sorted(RAW.glob('*')) if p.is_file()}
    write(DEST / 'raw_artifact_manifest.json',artifacts)
    print(json.dumps({k:{n:f"{v['count']}/{v['total']}" for n,v in m.items() if isinstance(v,dict) and 'count' in v}
                      for k,m in result['metrics'].items()},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify','run','report'])
    parser.add_argument('--label', choices=['base','sft','sft_dpo'])
    args=parser.parse_args()
    if args.action=='verify':
        verify(); print('Frozen protocol / inputs: PASS')
    elif args.action=='run':
        if not args.label: parser.error('--label required')
        run_model(args.label)
    else: report()
