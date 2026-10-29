#!/usr/bin/env python3
"""Inspect a future relocated runtime without starting a model or GPU job.

The preserved environments under the old names are archives, not relocatable
Python environments. New environments must be installed separately under
runtime/envs and verified against a captured package inventory.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('/data/hwkim/sftdpo_work')
OLD_ROOT = '/home/hwkim/sftdpo_work'
ENVIRONMENTS = {'hf': 'hfvenv', 'vllm': 'vllmvenv', 'llamacpp': 'llamacpp_venv', 'uvtool': 'uvtool'}


def packages(python):
    result = subprocess.run([str(python), '-m', 'pip', 'list', '--format=json', '--disable-pip-version-check'],
                            check=True, capture_output=True, text=True,
                            env={**os.environ, 'PIP_NO_INDEX': '1', 'PYTHONDONTWRITEBYTECODE': '1'})
    # No package index URLs, credentials or editable local paths are exported.
    return sorted(({'name': x['name'], 'version': x['version'], 'editable': 'editable_project_location' in x}
                   for x in json.loads(result.stdout)), key=lambda x: x['name'].lower())


def capture():
    result = {}
    for name, old in ENVIRONMENTS.items():
        python = Path(OLD_ROOT) / old / 'bin/python'
        version = subprocess.run([str(python), '-c', 'import sys; print(sys.version.split()[0])'],
                                 check=True, capture_output=True, text=True).stdout.strip()
        result[name] = {'python_version': version, 'packages': packages(python)}
    return {'format': 1, 'description': 'Observed installed versions; not a hash-locked or reproducible wheel set',
            'environments': result}


def check(lock, root):
    issues = []
    for name, expected in lock['environments'].items():
        python = root / 'runtime/envs' / name / 'bin/python'
        if not python.exists():
            issues.append(f'{name}: missing rebuilt interpreter {python}')
            continue
        try:
            resolved = str(python.resolve(strict=True))
            if resolved == OLD_ROOT or resolved.startswith(OLD_ROOT + '/'):
                issues.append(f'{name}: interpreter resolves to old root')
            cfg = python.parent.parent / 'pyvenv.cfg'
            if OLD_ROOT in cfg.read_text(encoding='utf-8'):
                issues.append(f'{name}: pyvenv.cfg still refers to old root')
            for entry in python.parent.iterdir():
                if not entry.is_file() or entry.is_symlink():
                    continue
                with entry.open('rb') as stream:
                    first = stream.readline(4096)
                if first.startswith(b'#!') and OLD_ROOT.encode() in first:
                    issues.append(f'{name}: old-root shebang in {entry.name}')
            version = subprocess.run([str(python), '-c', 'import sys; print(sys.version.split()[0])'],
                                     check=True, capture_output=True, text=True).stdout.strip()
            if version != expected['python_version']:
                issues.append(f'{name}: Python version {version} != {expected["python_version"]}')
            if packages(python) != expected['packages']:
                issues.append(f'{name}: installed distribution inventory differs')
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            issues.append(f'{name}: inspection failed: {exc}')
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('capture', help='print installed version inventory as JSON; no files are changed')
    test = sub.add_parser('check', help='compare new environments with an observed inventory')
    test.add_argument('--lock', type=Path, required=True)
    test.add_argument('--root', type=Path, default=ROOT)
    scan = sub.add_parser('scan', help='fail if an explicitly supplied executable/config contains the old root')
    scan.add_argument('paths', nargs='+', type=Path)
    args = parser.parse_args()
    if args.command == 'capture':
        print(json.dumps(capture(), indent=2, ensure_ascii=True))
    elif args.command == 'check':
        issues = check(json.loads(args.lock.read_text()), args.root)
        print(json.dumps({'issues': issues, 'ok': not issues}, indent=2))
        return bool(issues)
    else:
        findings = []
        for path in args.paths:
            try:
                for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                    if OLD_ROOT in line:
                        findings.append({'path': str(path), 'line': number})
            except (OSError, UnicodeError) as exc:
                findings.append({'path': str(path), 'error': str(exc)})
        print(json.dumps({'findings': findings, 'ok': not findings}, indent=2))
        return bool(findings)
    return 0


if __name__ == '__main__':
    sys.exit(main())
