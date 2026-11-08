#!/usr/bin/env python3
"""Build and verify an artificial 1,984-record V4-sized scheduler fixture."""
import json
from pathlib import Path
import tempfile
from semantic_schedule import build_manifest
from test_semantic_schedule import make_fixture

SEEDS=[1102,211102,2026113,2026117,2026131]


def main():
    records,approved=make_fixture()
    with tempfile.TemporaryDirectory() as td:
        src=Path(td)
        t=src/'train.jsonl';g=src/'approved.jsonl';out=src/'orders'
        t.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in records),encoding='utf-8')
        g.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in approved),encoding='utf-8')
        x=build_manifest(t,g,out,SEEDS)
        result={'note':'ARTIFICIAL V4-sized fixture, not real model accuracy and not original V4 exact records',
                'n_records':x['records'],'n_questions':x['questions'],
                'reference_order':'Python random slot shuffle, not original NumPy O4prime',
                'seeds':{},'tests':['same record set','determinism','max-run<=4','training-only labels']}
        for seed in SEEDS:
            y=x['seeds'][str(seed)]
            b=y['baseline'];s=y['balanced']
            result['seeds'][str(seed)]={'random_coarse_window_tv':b['coarse']['mean_window_total_variation'],
                                        'balanced_coarse_window_tv':s['coarse']['mean_window_total_variation'],
                                        'random_coarse_prefix_gap':b['coarse']['max_observed_label_prefix_discrepancy_records'],
                                        'balanced_coarse_prefix_gap':s['coarse']['max_observed_label_prefix_discrepancy_records'],
                                        'balanced_max_question_run':s['max_question_run']}
        numeric=[(v['random_coarse_window_tv'],v['balanced_coarse_window_tv']) for v in result['seeds'].values()]
        result['mean_random_window_tv']=round(sum(a for a,b in numeric)/len(numeric),5)
        result['mean_balanced_window_tv']=round(sum(b for a,b in numeric)/len(numeric),5)
        result['relative_reduction_pct']=round(100*(1-result['mean_balanced_window_tv']/result['mean_random_window_tv']),2)
        path=Path(__file__).parent/'offline_smoke_results.json'
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
