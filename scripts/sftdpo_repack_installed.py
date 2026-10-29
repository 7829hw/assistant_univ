#!/usr/bin/env python3
"""Rebuild missing HF CUDA wheels from verified installed distribution files.

This is a reconstruction, not the original wheel. Every included source file
must match its installed RECORD digest. Bytecode and installer-generated
metadata are excluded; paths outside site-packages are rejected.
"""
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import zipfile
from importlib.metadata import PathDistribution
from pip._vendor.packaging.tags import parse_tag, sys_tags

ROOT = Path('/data/hwkim/sftdpo_work')
SITE = ROOT / 'hfvenv/lib/python3.12/site-packages'
OUT = ROOT / 'runtime/wheels/hf_repacked'
LOCK = Path('sft_dpo_inventory/migration_execution_20261028/runtime/observed_packages.json')
CACHED_MANIFEST = ROOT / 'runtime/wheels/hf/wheel_manifest.json'


def main():
    lock = json.loads(LOCK.read_text())['environments']['hf']['packages']
    cached = json.loads(CACHED_MANIFEST.read_text())
    missing = set(cached['missing'])
    expected = {f'{x["name"]}=={x["version"]}' for x in lock}
    if not missing <= expected or len(missing) != 16:
        raise SystemExit('Unexpected missing distribution set')
    OUT.mkdir(parents=True, exist_ok=False)
    ranks = {str(tag): i for i, tag in enumerate(sys_tags())}
    manifests = []
    for distdir in sorted(SITE.glob('*.dist-info')):
        dist = PathDistribution(distdir)
        name, version = dist.metadata['Name'], dist.version
        key = f'{name}=={version}'
        if key not in missing:
            continue
        wheel_meta = dist.read_text('WHEEL')
        tags = [str(t) for line in wheel_meta.splitlines() if line.startswith('Tag: ')
                for t in parse_tag(line[5:]) if str(t) in ranks]
        if not tags:
            raise RuntimeError('No compatible wheel tag: ' + key)
        tag = min(tags, key=ranks.__getitem__)
        filename = f'{name.replace("-", "_")}-{version.replace("-", "_")}-{tag}.whl'
        output = OUT / filename
        entries, installed_records = [], []
        with (distdir / 'RECORD').open(newline='', encoding='utf-8') as f:
            source_records = list(csv.reader(f))
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for rel, checksum, size in source_records:
                parts = PurePosixPath(rel)
                if parts.is_absolute() or '..' in parts.parts:
                    raise RuntimeError(f'Outside site-packages in {key}: {rel}')
                if not checksum or rel.endswith(('/INSTALLER', '/REQUESTED', '/direct_url.json')):
                    continue
                algorithm, encoded = checksum.split('=', 1)
                if algorithm != 'sha256':
                    raise RuntimeError('Unsupported RECORD hash in ' + key)
                source = SITE / rel
                if source.is_symlink() or not source.is_file():
                    raise RuntimeError('Missing or linked source: ' + str(source))
                info = zipfile.ZipInfo(rel)
                info.external_attr = (source.stat().st_mode & 0xFFFF) << 16
                digest = hashlib.sha256()
                count = 0
                with source.open('rb') as src, archive.open(info, 'w', force_zip64=True) as dest:
                    while chunk := src.read(8 * 1024 * 1024):
                        digest.update(chunk)
                        count += len(chunk)
                        dest.write(chunk)
                actual = base64.urlsafe_b64encode(digest.digest()).rstrip(b'=').decode()
                if actual != encoded or count != int(size):
                    raise RuntimeError('Source does not match installed RECORD: ' + str(source))
                entries.append((rel, 'sha256=' + actual, str(count)))
                installed_records.append({'path': rel, 'bytes': count, 'sha256': digest.hexdigest()})
            record_path = distdir.name + '/RECORD'
            records = io.StringIO(newline='')
            writer = csv.writer(records, lineterminator='\n')
            writer.writerows(entries + [(record_path, '', '')])
            archive.writestr(record_path, records.getvalue())
        with output.open('rb') as f:
            wheel_sha = hashlib.file_digest(f, 'sha256').hexdigest()
        manifests.append({'name': name, 'version': version, 'wheel': filename,
                          'reconstructed_wheel_sha256': wheel_sha, 'source_files': installed_records})
        missing.remove(key)
        print(json.dumps({'completed': key, 'files': len(entries)}, ensure_ascii=True), flush=True)
    if missing:
        raise RuntimeError('Installed distributions missing: ' + ', '.join(sorted(missing)))
    (OUT / 'repack_manifest.json').write_text(json.dumps({'method': 'installed RECORD-verified source bytes; reconstructed wheel, not original',
                                                         'distributions': manifests}, indent=2) + '\n')


if __name__ == '__main__':
    main()
