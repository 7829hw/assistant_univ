#!/usr/bin/env python3
"""Verify a copied storage union, without changing any source or destination.

Protected final-set contents are only compared by machine; neither bytes nor
their per-file digests are exported. All other files match the reviewed SHA256.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import time

from build_migration_inventory import open_without_symlinks


def attributes(path):
    return {k: hashlib.sha256(os.getxattr(path, k, follow_symlinks=False)).hexdigest()
            for k in os.listxattr(path, follow_symlinks=False)}


def same_bytes(left, right):
    with os.fdopen(open_without_symlinks(left), 'rb') as a, os.fdopen(open_without_symlinks(right), 'rb') as b:
        first_a, first_b = os.fstat(a.fileno()), os.fstat(b.fileno())
        while True:
            x, y = a.read(4 * 1024 * 1024), b.read(4 * 1024 * 1024)
            if x != y:
                return False
            if not x:
                break
        for before, after in ((first_a, os.fstat(a.fileno())), (first_b, os.fstat(b.fileno()))):
            if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise RuntimeError('file changed during protected byte comparison')
    return True


def verify(row, destination, source_home, merged):
    target = destination / row['relative_path']
    s = target.lstat()
    kind = 'directory' if stat.S_ISDIR(s.st_mode) else 'symlink' if stat.S_ISLNK(s.st_mode) else 'file' if stat.S_ISREG(s.st_mode) else 'special'
    if kind != row['type']:
        raise RuntimeError('type mismatch')
    if (oct(stat.S_IMODE(s.st_mode)), s.st_uid, s.st_gid) != (row['mode'], row['uid'], row['gid']):
        raise RuntimeError('mode/owner mismatch')
    if attributes(target) != row.get('xattr_sha256', {}):
        raise RuntimeError('xattr/ACL mismatch')
    if kind == 'directory':
        if str(target) not in merged and s.st_mtime_ns != row['mtime_ns']:
            raise RuntimeError('directory mtime mismatch')
        return 'directory'
    if s.st_mtime_ns != row['mtime_ns']:
        raise RuntimeError('file/link mtime mismatch')
    if kind == 'symlink':
        if os.readlink(target) != row['link_target']:
            raise RuntimeError('link text mismatch')
        return 'symlink'
    if kind != 'file':
        raise RuntimeError('special node needs separate handling')
    if s.st_size != row['size_bytes']:
        raise RuntimeError('file size mismatch')
    if row['hash_status'] == 'protected_metadata_only':
        source = source_home / row['relative_path'] if row['source_root'] == 'home' else Path(row['source_path'])
        if not same_bytes(source, target):
            raise RuntimeError('protected byte comparison mismatch')
        return 'protected_bytes_equal'
    if row['hash_status'] != 'verified_at_scan':
        raise RuntimeError('missing approved original digest')
    with os.fdopen(open_without_symlinks(target), 'rb') as f:
        before = os.fstat(f.fileno())
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
        after = os.fstat(f.fileno())
    if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise RuntimeError('destination changed during hashing')
    if digest != row['sha256']:
        raise RuntimeError('SHA256 mismatch')
    return 'sha256_equal'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', type=Path, default=Path('sft_dpo_inventory/migration_20261028/external_entries.jsonl.gz'))
    p.add_argument('--destination', type=Path, default=Path('/data/hwkim/sftdpo_work'))
    p.add_argument('--source-home', type=Path, default=Path('/home/hwkim/sftdpo_work'))
    p.add_argument('--environments-only', action='store_true')
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    with gzip.open(args.snapshot, 'rt') as stream:
        rows = [json.loads(line) for line in stream]
    merged = {r['destination_path'] for r in rows if r['destination_collision'].startswith('merge_directories')}
    if args.environments_only:
        groups = {'hfvenv', 'vllmvenv', 'llamacpp_venv', 'uvtool', 'uv-python', 'cuda_link'}
        rows = [r for r in rows if r['relative_path'].split('/')[0] in groups]
    counts, failures, total, last = Counter(), [], 0, time.monotonic()
    started = datetime.now(timezone.utc).isoformat()
    for row in rows:
        try:
            counts[verify(row, args.destination, args.source_home, merged)] += 1
        except (OSError, RuntimeError) as exc:
            # No protected file paths, details or hashes are exported here.
            failures.append({'source': 'protected_final_file' if row['hash_status'] == 'protected_metadata_only' else row['source_path'], 'error': str(exc)})
        total += row['size_bytes'] if row['type'] == 'file' else 0
        if time.monotonic() - last > 10:
            print(json.dumps({'entries_checked': sum(counts.values()) + len(failures), 'logical_file_bytes_checked': total,
                              'failures': len(failures)}), flush=True)
            last = time.monotonic()
    report = {'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'environment_copy_subset' if args.environments_only else 'full_original_union',
              'snapshot_sha256': hashlib.sha256(args.snapshot.read_bytes()).hexdigest(), 'expected_entries': len(rows),
              'verified': dict(counts), 'failures': failures, 'ok': not failures,
              'protected_verification': 'machine-only byte comparison; no protected content or per-file hashes exported',
              'directory_mtime_policy': 'existing-data merge directory mtimes are restored separately; ctime is not portable'}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=True, indent=2) + '\n')
    print(json.dumps({'scope': report['scope'], 'verified': dict(counts), 'failures': len(failures), 'ok': not failures}), flush=True)
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
