#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build original NumPy O4prime orders for a coverage dataset AFTER audit.

Do not use with unapproved/blocked data. Run from repository root.
"""
import argparse
import json
from pathlib import Path
import sys
from semantic_schedule import read_jsonl, sha_file


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--train',type=Path,required=True)
    ap.add_argument('--audit-report',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--seeds',type=int,nargs='+',default=[1102,211102,2026113,2026117,2026131])
    args=ap.parse_args(argv)
    if not Path('sft_dpo_inventory/pilot_007/train/order7b.py').exists():
        raise SystemExit('Run from GeoFlow repo root')
    audit=json.loads(args.audit_report.read_text(encoding='utf-8'))
    if audit.get('status')!='AUDITED_OFFLINE_NOT_TRAINED' or not audit.get('protected_id_and_family_checks'):
        raise SystemExit('Coverage data has no successful audit report')
    if audit['candidate_sha256']!=sha_file(args.train):
        raise SystemExit('Coverage dataset changed after audit')
    sys.path.insert(0,str(Path('sft_dpo_inventory/pilot_007/train').resolve()))
    import order7b
    records=read_jsonl(args.train)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    results={}
    for seed in args.seeds:
        o=order7b.order_file({'full':records},seed)
        if not o['max_run_ok']:
            raise SystemExit(f'Max question run violation for {seed}')
        o['coverage_train_sha256']=audit['candidate_sha256']
        p=args.output_dir/f'order_b2_o{seed}.json'
        p.write_text(json.dumps(o,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
        results[str(seed)]={'path':str(p),'order_sha256':o['order_sha256'],
                            'record_count':o['arms']['full']['slots']}
    print(json.dumps(results,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
