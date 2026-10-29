#!/usr/bin/env python3
"""Finish the reviewed 2026-10-28 migration; default is verification only.

This one-time tool only removes the isolated, unchanged source allowlist after
the full copy proof and old-home-absent runtime checks have succeeded. It never
recursively removes an unknown entry and refuses partially completed reruns.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat

from build_migration_inventory import open_without_symlinks
from verify_consolidated_storage import attributes, verify

REPO = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO / 'sft_dpo_inventory/migration_20261028/external_entries.jsonl.gz'
REPORTS = REPO / 'sft_dpo_inventory/migration_execution_20261028'
OLD = Path('/home/hwkim/sftdpo_work')
SOURCE = Path('/home/hwkim/sftdpo_work.before-data-move-20261029')
DESTINATION = Path('/data/hwkim/sftdpo_work')


def kind(s):
    return ('directory' if stat.S_ISDIR(s.st_mode) else
            'file' if stat.S_ISREG(s.st_mode) else
            'symlink' if stat.S_ISLNK(s.st_mode) else 'special')


def unchanged(s, row, directory_after_unlink=False):
    """Root rename changes ctime; unlinking children changes directory times."""
    if (s.st_dev, s.st_ino, kind(s), oct(stat.S_IMODE(s.st_mode)), s.st_uid, s.st_gid) != (
            row['device'], row['inode'], row['type'], row['mode'], row['uid'], row['gid']):
        raise RuntimeError('source identity/type/permissions changed')
    if directory_after_unlink:
        if row['type'] != 'directory':
            raise RuntimeError('directory-only identity check used on a file')
        return
    if (s.st_size, s.st_mtime_ns) != (row['size_bytes'], row['mtime_ns']):
        raise RuntimeError('source size or mtime changed')
    if row['relative_path'] and s.st_ctime_ns != row['ctime_ns']:
        raise RuntimeError('source ctime changed')
    if row['type'] == 'file' and s.st_nlink != 1:
        raise RuntimeError('source has unreviewed hard links')


def enumerate_tree(root):
    found, pending = {''}, [root]
    while pending:
        parent = pending.pop()
        with os.scandir(parent) as entries:
            for entry in entries:
                path = Path(entry.path)
                found.add(str(path.relative_to(root)))
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
    return found


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n')


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid,
            s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def destination_unchanged(path, receipt):
    """Identity receipt only; coarse timestamps cannot prove byte equality."""
    if identity(path.lstat()) != receipt:
        raise RuntimeError('destination changed after fresh byte verification')


def verify_before_unlink(row, destination, source, merged, links, receipt):
    target = destination / row['relative_path']
    destination_unchanged(target, receipt)
    current = dict(row)
    if current['type'] == 'symlink':
        current['link_target'] = links.get(str(target), current['link_target'])
    result = verify(current, destination, source, merged)
    destination_unchanged(target, receipt)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    proof = json.loads((REPORTS / 'physical/full_copy_verification.json').read_text())
    isolated = json.loads((REPORTS / 'physical/source_isolation.json').read_text())
    runtime = json.loads((REPORTS / 'runtime/old_home_absence_validation.json').read_text())
    snapshot_hash = hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest()
    if not (proof['ok'] and proof['scope'] == 'full_original_union' and
            proof['snapshot_sha256'] == isolated['snapshot_sha256'] == snapshot_hash and
            runtime['ok'] and runtime['old_home_path_absent'] and
            isolated['source'] == str(OLD) and isolated['backup'] == str(SOURCE)):
        raise RuntimeError('required preservation/isolation/runtime evidence is missing')
    if os.path.lexists(OLD) or not SOURCE.is_dir() or SOURCE.is_symlink():
        raise RuntimeError('old path reappeared or isolated root is missing/unsafe')
    completion = REPORTS / 'physical/source_cleanup.json'
    if completion.exists():
        raise RuntimeError('cleanup journal already exists; inspect before any retry')
    with gzip.open(SNAPSHOT, 'rt') as stream:
        union = [json.loads(line) for line in stream]
    rows = [r for r in union if r['source_root'] == 'home']
    by_name = {r['relative_path']: r for r in rows}
    if len(rows) != isolated['expected_source_entries'] or len(by_name) != len(rows):
        raise RuntimeError('source allowlist count or uniqueness mismatch')
    if enumerate_tree(SOURCE) != set(by_name):
        raise RuntimeError('source path set changed; retain isolated source')
    updates = json.loads((REPORTS / 'physical/postcopy_link_updates.json').read_text())
    links = {u['path']: u['canonical_target'] for u in updates['direct_links_updated']}
    for row in rows:
        rel = Path(row['relative_path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise RuntimeError('unsafe allowlist path')
        source, destination = SOURCE / rel, DESTINATION / rel
        unchanged(source.lstat(), row)
        if attributes(source) != row['xattr_sha256']:
            raise RuntimeError('source xattrs changed')
        ds = destination.lstat()
        if (kind(ds), oct(stat.S_IMODE(ds.st_mode)), ds.st_uid, ds.st_gid) != (
                row['type'], row['mode'], row['uid'], row['gid']):
            raise RuntimeError('destination type/permissions changed after byte proof')
        if attributes(destination) != row['xattr_sha256']:
            raise RuntimeError('destination xattrs changed after byte proof')
        if row['type'] != 'directory' and ds.st_mtime_ns != row['mtime_ns']:
            raise RuntimeError('destination mtime changed after byte proof')
        if row['type'] == 'file' and ds.st_size != row['size_bytes']:
            raise RuntimeError('destination size changed after byte proof')
        if row['type'] == 'symlink':
            if os.readlink(source) != row['link_target']:
                raise RuntimeError('source link changed')
            if os.readlink(destination) != links.get(str(destination), row['link_target']):
                raise RuntimeError('destination link differs from approved relocation')
    # Native git inspection once refreshed an archived index. Its repair is
    # separately recorded; check the repaired bytes again before deletion.
    repair = json.loads((REPORTS / 'physical/preservation_repair.json').read_text())
    if hashlib.sha256(Path(repair['path']).read_bytes()).hexdigest() != repair['snapshot_sha256']:
        raise RuntimeError('archived native index repair no longer matches')
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'source': str(SOURCE),
              'destination': str(DESTINATION), 'snapshot_sha256': snapshot_hash,
              'entries_verified': len(rows), 'full_copy_proof_ok': True,
              'old_home_absent_runtime_ok': True, 'unknown_source_entries': 0,
              'state': 'metadata_preflight_complete_requires_fresh_bytes', 'removed': {}, 'ok': True}
    dump(REPORTS / 'physical/source_cleanup_preflight.json', report)
    print(json.dumps({'state': report['state'], 'entries': len(rows), 'apply': args.apply}), flush=True)
    if not args.apply:
        return
    # Re-read every destination byte because the first copy proof did not
    # record target inode/ctime receipts. Only aggregate results are exported.
    # Retain fresh receipts in memory and compare again before each unlink.
    receipts, checked = {}, Counter()
    merged = {r['destination_path'] for r in union if r['destination_collision'].startswith('merge_directories')}
    for i, original in enumerate(union):
        row = dict(original)
        target = DESTINATION / row['relative_path']
        if row['type'] == 'symlink':
            row['link_target'] = links.get(str(target), row['link_target'])
        before = identity(target.lstat())
        checked[verify(row, DESTINATION, SOURCE, merged)] += 1
        destination_unchanged(target, before)
        receipts[row['relative_path']] = before
        if i and i % 10000 == 0:
            print(json.dumps({'fresh_copy_entries_checked': i + 1}), flush=True)
    # Full enumeration and metadata checks again after the long byte pass.
    if enumerate_tree(SOURCE) != set(by_name):
        raise RuntimeError('source path set changed during fresh byte verification')
    for row in rows:
        unchanged((SOURCE / row['relative_path']).lstat(), row)
        destination_unchanged(DESTINATION / row['relative_path'], receipts[row['relative_path']])
    report['fresh_byte_verification'] = dict(checked)
    report['destination_receipts'] = 'dev/inode/mode/owner/size/mtime/ctime retained in memory; checked again before each unlink'
    report.update(state='cleanup_started', ok=False)
    dump(completion, report)
    counts, final_bytes = Counter(), Counter()
    try:
        groups, child_sets = defaultdict(list), defaultdict(set)
        for row in rows:
            if row['relative_path']:
                child_sets[str(Path(row['relative_path']).parent)].add(Path(row['relative_path']).name)
            if row['type'] != 'directory':
                groups[str(Path(row['relative_path']).parent)].append(row)
        for parent, children in sorted(groups.items()):
            fd = open_without_symlinks(SOURCE / parent, directory=True)
            try:
                parent_key = '' if parent == '.' else parent
                unchanged(os.fstat(fd), by_name[parent_key], directory_after_unlink=True)
                if set(os.listdir(fd)) != child_sets[parent]:
                    raise RuntimeError('source child set changed; retain unknown entries')
                for row in children:
                    name = Path(row['relative_path']).name
                    unchanged(os.stat(name, dir_fd=fd, follow_symlinks=False), row)
                    # Identity/ctime alone is insufficient on coarse-clock
                    # filesystems. Read and compare bytes again immediately
                    # before removing this source; no active writer is allowed.
                    final_bytes[verify_before_unlink(row, DESTINATION, SOURCE, merged, links,
                                                     receipts[row['relative_path']])] += 1
                    unchanged(os.stat(name, dir_fd=fd, follow_symlinks=False), row)
                    os.unlink(name, dir_fd=fd)
                    counts[row['type']] += 1
                    if sum(counts.values()) % 10000 == 0:
                        print(json.dumps({'source_entries_removed': sum(counts.values())}), flush=True)
            finally:
                os.close(fd)
        directories = sorted((r for r in rows if r['type'] == 'directory'),
                             key=lambda r: len(Path(r['relative_path']).parts), reverse=True)
        for row in directories:
            path = SOURCE / row['relative_path']
            fd = open_without_symlinks(path.parent, directory=True)
            try:
                unchanged(os.stat(path.name, dir_fd=fd, follow_symlinks=False), row, directory_after_unlink=True)
                os.rmdir(path.name, dir_fd=fd)  # fails closed on any new entry
                counts['directory'] += 1
            finally:
                os.close(fd)
        report.update(state='cleanup_complete', ok=True, source_exists=os.path.lexists(SOURCE),
                      old_home_exists=os.path.lexists(OLD))
    except BaseException:
        report.update(state='cleanup_stopped_inspect_remaining_source', ok=False)
        raise
    finally:
        report.update(finished_utc=datetime.now(timezone.utc).isoformat(), removed=dict(counts),
                      immediate_preunlink_byte_verification=dict(final_bytes),
                      concurrency_policy='No active source handles observed before cleanup; writers must stay stopped. Unknown additions stop cleanup and retain residual entries; rollback is not atomic.')
        dump(completion, report)
        print(json.dumps({'state': report['state'], 'removed': dict(counts), 'ok': report['ok']}), flush=True)


if __name__ == '__main__':
    main()
