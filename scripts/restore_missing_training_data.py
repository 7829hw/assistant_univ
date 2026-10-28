#!/usr/bin/env python3
"""Restore snapshot-listed research records and split one large training original.

Never changes source files. The snapshot is evidence, not training approval.
The explicitly external-only fix-condition-hoist evaluation records remain external.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'sft_dpo_inventory/migration_20261028/git_candidates.jsonl.gz'
RECEIPT = ROOT / 'sft_dpo_inventory/migration_restore_20261028/manifest.json'
BIG = 'training/generated/pilot_006/self_2d/raw/S128F_raw.jsonl'
SHARDS = ROOT / (BIG + '.shards')
LIMIT = 24 * 1024 * 1024
EVALUATION_SERVER_LOGS = {
    *[f'pilot_004/vllm/server_{port}_bf16_fi.log' for port in (8400, 8401, 8402)],
    *[f'pilot_005/vllm/server_{port}_bf16_fi.log' for port in (8500, 8501, 8502)],
    *[f'pilot_006_prep/vllm/server_{port}_bf16_fi.log' for port in (8600, 8601, 8602, 8611, 8612, 8620, 8621, 8622)],
    *[f'serving_vllm_fp8/server_{port}_{kind}_fi.log' for port, kind in ((8200, 'bf16'), (8200, 'fp8'), (8201, 'fp8'))],
}


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def rows():
    with gzip.open(SNAPSHOT, 'rt', encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def verified_source(row):
    source = Path(row['source_path'])
    if row['hash_status'] != 'verified_at_scan' or source.is_symlink():
        raise ValueError(f'unverified or linked source: {source}')
    if not os.path.lexists(source) and row['source_root'] == 'home':
        canonical_root = Path('/data/hwkim/sftdpo_work')
        relative = Path(row['relative_path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('unsafe canonical relative path')
        canonical = canonical_root / relative
        if Path(row['destination_path']) != canonical or canonical.is_symlink():
            raise ValueError('unsafe canonical destination')
        source = canonical
    st = source.stat()
    if (st.st_size, st.st_mtime_ns) != (row['size_bytes'], row['mtime_ns']):
        raise ValueError(f'source changed since snapshot: {source}')
    if digest(source) != row['sha256']:
        raise ValueError(f'source hash mismatch: {source}')
    return source


def copy_exact(source, destination, expected):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.is_symlink() or digest(destination) != expected:
            raise ValueError(f'destination conflict: {destination}')
        return
    with open(source, 'rb') as src, open(destination, 'xb') as dst:
        for block in iter(lambda: src.read(4 * 1024 * 1024), b''):
            dst.write(block)
    if digest(destination) != expected:
        raise ValueError(f'copy verification failed: {destination}')


def split_big(row):
    source = verified_source(row)
    SHARDS.mkdir(parents=True, exist_ok=True)
    attrs = SHARDS / '.gitattributes'
    if not attrs.exists():
        attrs.write_text('* -text\n', encoding='utf-8')
    elif attrs.read_text(encoding='utf-8') != '* -text\n':
        raise ValueError('shard attributes conflict')
    parts = []
    chunk = bytearray()

    def flush():
        if not chunk:
            return
        filename = f'part-{len(parts)+1:04d}.jsonl'
        path = SHARDS / filename
        h = hashlib.sha256(chunk).hexdigest()
        if path.exists():
            if path.is_symlink() or digest(path) != h:
                raise ValueError(f'shard conflict: {path}')
        else:
            with open(path, 'xb') as out:
                out.write(chunk)
        parts.append({'path': filename, 'bytes': len(chunk), 'sha256': h})
        chunk.clear()

    with open(source, 'rb') as stream:
        for line in stream:
            if len(line) > LIMIT:
                raise ValueError('a single source record exceeds shard limit')
            if chunk and len(chunk) + len(line) > LIMIT:
                flush()
            chunk.extend(line)
    flush()
    doc = {'source_path': BIG, 'size_bytes': row['size_bytes'], 'sha256': row['sha256'],
           'split_policy': 'whole lines; at most 24 MiB each', 'parts': parts}
    manifest = SHARDS / 'manifest.json'
    value = json.dumps(doc, ensure_ascii=False, indent=2) + '\n'
    if manifest.exists() and manifest.read_text(encoding='utf-8') != value:
        raise ValueError('shard manifest conflict')
    if not manifest.exists():
        manifest.write_text(value, encoding='utf-8')
    verify_shards(manifest)
    return doc


def verify_shards(manifest, output=None):
    doc = json.loads(manifest.read_text(encoding='utf-8'))
    h = hashlib.sha256()
    total = 0
    out = open(output, 'xb') if output else None
    try:
        for part in doc['parts']:
            name = part['path']
            if Path(name).name != name:
                raise ValueError('unsafe shard name')
            p = manifest.parent / name
            if p.is_symlink() or p.stat().st_size != part['bytes'] or digest(p) != part['sha256']:
                raise ValueError(f'shard verification failed: {name}')
            with open(p, 'rb') as src:
                for block in iter(lambda: src.read(4 * 1024 * 1024), b''):
                    h.update(block)
                    total += len(block)
                    if out:
                        out.write(block)
        if total != doc['size_bytes'] or h.hexdigest() != doc['sha256']:
            raise ValueError('reassembled file verification failed')
    finally:
        if out:
            out.close()
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'verify-shards', 'restore-shards'])
    parser.add_argument('--output', type=Path, help='new output path for restore-shards')
    args = parser.parse_args()
    if args.action != 'prepare':
        if args.action == 'restore-shards' and args.output is None:
            parser.error('restore-shards requires --output')
        print(json.dumps({'verified_bytes': verify_shards(SHARDS / 'manifest.json', args.output)}))
        return
    if RECEIPT.exists():
        raise ValueError('receipt already exists; review before rerunning')
    receipt = []
    for row in rows():
        rel = row['relative_path']
        common = {k: row.get(k) for k in ('source_root', 'source_path', 'category', 'sha256', 'size_bytes', 'git_coverage')}
        common.update(canonical_path=row['destination_path'], actual_read_path=None)
        if row['category'] == 'git_historical_evaluation_candidate':
            common.update(action='external_evaluation_preserved', basis='evaluation/fix_condition_hoist/verify_rerun.py:6-12')
        elif row['source_root'] == 'data' and rel in EVALUATION_SERVER_LOGS:
            common.update(action='external_evaluation_or_mixed_server_log',
                          basis='request-pattern detected; evaluation or mixed workloads; preserve outside Git')
        elif row['source_root'] == 'repo':
            source = verified_source(row)
            common['actual_read_path'] = str(source)
            common.update(action='sharded_original_remains_local' if rel == BIG else 'preserve_existing_repository_path', git_path=rel)
            if rel == BIG:
                split_big(row)
                common['git_path'] = str(SHARDS.relative_to(ROOT))
        else:
            source = verified_source(row)
            common['actual_read_path'] = str(source)
            if row.get('git_coverage') == 'index_identical_elsewhere':
                common.update(action='reference_identical_index_blob', existing_git_paths=row['git_index_identical_paths'])
            else:
                target = row['git_archive_path']
                if not target or Path(target).is_absolute() or '..' in Path(target).parts:
                    raise ValueError('unsafe archive path')
                copy_exact(source, ROOT / target, row['sha256'])
                common.update(action='copied_verified', git_path=target)
                if 'candidate' in row['category']:
                    common.update(producer_review_status='reviewed_approved_for_git_retention',
                                  producer_review_basis='Independent producer review: training collection, reproducibility or diagnostic records; Git retention only, not training approval.')
        receipt.append(common)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    if RECEIPT.exists():
        raise ValueError('receipt already exists; review before rerunning')
    RECEIPT.write_text(json.dumps({'snapshot': str(SNAPSHOT.relative_to(ROOT)), 'records': receipt}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    from collections import Counter
    print(json.dumps({'records': len(receipt), 'actions': dict(Counter(r['action'] for r in receipt))}))


if __name__ == '__main__':
    main()
