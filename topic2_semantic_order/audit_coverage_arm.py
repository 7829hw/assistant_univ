#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed coverage arm audit. This DOES NOT create or approve new training data.

The user/project owner must supply externally reviewed and approved records,
authoritative protected-data overlap lists, and tokenizer-derived token ledger.
Do not derive protected lists by reading the sealed H-final evaluation set here.
"""
from pathlib import Path
import argparse
import json
from semantic_schedule import read_jsonl, sha_file, validate_coverage_variant


def read_blocklist(path:Path)->set[str]:
    content=path.read_text(encoding='utf-8')
    try:
        x=json.loads(content)
        if isinstance(x,dict):x=x.get('ids') or x.get('families') or x.get('blocked') or []
        if not isinstance(x,list):raise ValueError('Blocklist JSON must contain list')
        return {str(v) for v in x}
    except json.JSONDecodeError:
        return {line.strip() for line in content.splitlines() if line.strip() and not line.startswith('#')}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-train',type=Path,required=True)
    p.add_argument('--candidate-train',type=Path,required=True)
    p.add_argument('--approved',type=Path,required=True)
    p.add_argument('--blocked-ids',type=Path,required=True)
    p.add_argument('--blocked-families',type=Path,required=True)
    p.add_argument('--token-ledger',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(argv)
    token_data=json.loads(a.token_ledger.read_text(encoding='utf-8'))
    ledger=token_data.get('loss_tokens',token_data) if isinstance(token_data,dict) else {}
    result=validate_coverage_variant(read_jsonl(a.base_train),read_jsonl(a.candidate_train),
             read_jsonl(a.approved),blocked_ids=read_blocklist(a.blocked_ids),
             blocked_families=read_blocklist(a.blocked_families),loss_ledger=ledger)
    result.update({'base_sha256':sha_file(a.base_train),'candidate_sha256':sha_file(a.candidate_train),
                   'approved_sha256':sha_file(a.approved),'blocked_ids_sha256':sha_file(a.blocked_ids),
                   'blocked_families_sha256':sha_file(a.blocked_families),
                   'token_ledger_sha256':sha_file(a.token_ledger),'status':'AUDITED_OFFLINE_NOT_TRAINED'})
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
