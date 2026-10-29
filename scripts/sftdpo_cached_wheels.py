#!/usr/bin/env python3
"""Inspect/materialize exact-version compatible wheels in the local pip HTTP cache.

Run with a Python 3.12 interpreter with pip installed. With no --out the tool
only reports metadata; --out must be a new directory and copies wheel bytes,
records their source and SHA256, and never accesses a package index.
"""
import argparse
import email
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from pip._vendor.packaging.tags import parse_tag, sys_tags

CACHE = Path('/home/hwkim/.cache/pip/http-v2')
LOCK = Path('sft_dpo_inventory/migration_execution_20261028/runtime/observed_packages.json')


def canonical(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--env', choices=('hf', 'vllm', 'llamacpp', 'uvtool'), required=True)
    p.add_argument('--lock', type=Path, default=LOCK)
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    if sys.version_info[:2] != (3, 12):
        raise SystemExit('Use a Python 3.12 interpreter for compatible wheel tags')
    env = json.loads(args.lock.read_text())['environments'][args.env]
    wanted = {(canonical(x['name']), x['version']) for x in env['packages']}
    ranks = {str(tag): i for i, tag in enumerate(sys_tags())}
    found = {}
    for file in CACHE.rglob('*.body'):
        try:
            with file.open('rb') as f:
                if f.read(4) != b'PK\x03\x04':
                    continue
            with zipfile.ZipFile(file) as z:
                files = z.namelist()
                metadata = [n for n in files if n.endswith('.dist-info/METADATA') and n.count('/') == 1]
                wheel = [n for n in files if n.endswith('.dist-info/WHEEL') and n.count('/') == 1]
                if len(metadata) != 1 or len(wheel) != 1:
                    continue
                meta = email.message_from_bytes(z.read(metadata[0]))
                wh = email.message_from_bytes(z.read(wheel[0]))
                name, version = meta.get('Name', ''), meta.get('Version', '')
                key = (canonical(name), version)
                if key not in wanted:
                    continue
                tags = [str(t) for value in wh.get_all('Tag', []) for t in parse_tag(value) if str(t) in ranks]
                if not tags:
                    continue
                tag = min(tags, key=ranks.__getitem__)
                candidate = (ranks[tag], str(file), name, version, tag)
                found.setdefault(key, []).append(candidate)
        except (OSError, ValueError, zipfile.BadZipFile, KeyError):
            continue
    missing = sorted(f'{name}=={version}' for name, version in wanted - found.keys())
    selected, ambiguous = [], []
    for key, candidates in found.items():
        best_rank = min(c[0] for c in candidates)
        best = sorted(c for c in candidates if c[0] == best_rank)
        if len(best) > 1:
            hashes = set()
            for candidate in best:
                with open(candidate[1], 'rb') as f:
                    hashes.add(hashlib.file_digest(f, 'sha256').hexdigest())
            if len(hashes) > 1:
                ambiguous.append(f'{key[0]}=={key[1]}')
                continue
        selected.append(best[0])
    if args.out and ambiguous:
        raise SystemExit('Different wheels share the best compatible tag: ' + ', '.join(sorted(ambiguous)))
    records = []
    if args.out:
        args.out.mkdir(parents=True, exist_ok=False)
        for _, source, name, version, tag in sorted(selected):
            filename = f'{canonical(name).replace("-", "_")}-{version.replace("-", "_")}-{tag}.whl'
            target = args.out / filename
            with open(source, 'rb') as src, target.open('xb') as dst:
                digest = hashlib.sha256()
                while chunk := src.read(8 * 1024 * 1024):
                    digest.update(chunk)
                    dst.write(chunk)
            with target.open('rb') as f:
                if hashlib.file_digest(f, 'sha256').hexdigest() != digest.hexdigest():
                    raise RuntimeError('copied wheel hash mismatch: ' + filename)
            records.append({'name': name, 'version': version, 'wheel': filename,
                            'source_cache_path': source, 'sha256': digest.hexdigest()})
        (args.out / 'wheel_manifest.json').write_text(json.dumps({'files': records, 'missing': missing}, indent=2) + '\n')
    print(json.dumps({'environment': args.env, 'compatible_found': len(selected), 'required': len(wanted),
                      'missing': missing, 'ambiguous': sorted(ambiguous), 'materialized': bool(args.out)}, indent=2))
    return bool(missing or ambiguous)


if __name__ == '__main__':
    raise SystemExit(main())
