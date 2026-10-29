#!/usr/bin/env python3
"""Render new path-adjusted execution snapshots without modifying originals.

Only source/config/job files are copied. Experiment inputs, output directories,
runtime state, and historical records stay at their original repository paths.
The manifest records every input and output digest and the exact replacements.
"""
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
ROOT = '/data/hwkim/sftdpo_work'
OLD = '/home/hwkim/sftdpo_work'
TREES = {
    'sft_dpo_inventory/pilot_006_prep/gpu': 'sft_dpo_inventory/pilot_006_prep/gpu_data',
    'sft_dpo_inventory/pilot_007/gpu': 'sft_dpo_inventory/pilot_007/gpu_data',
    'sft_dpo_inventory/pilot_007/train': 'sft_dpo_inventory/pilot_007/train_data',
    'sft_dpo_inventory/pilot_010/gpu': 'sft_dpo_inventory/pilot_010/gpu_data',
    'sft_dpo_inventory/pilot_010/train': 'sft_dpo_inventory/pilot_010/train_data',
}
EXTRA = {'sft_dpo_inventory/pilot_003/gpu_lib.sh': 'sft_dpo_inventory/pilot_003/gpu_data/gpu_lib.sh'}
for stem in ('run_c10', 'run_c10b', 'collect_c10', 'collect_c10b',
             'analyze_c10', 'analyze_c10b', 'teacher_contrast10', 'teacher_contrast10b'):
    EXTRA[f'sft_dpo_inventory/pilot_010/teacher/{stem}.py'] = f'sft_dpo_inventory/pilot_010/teacher_data/{stem}.py'
MANIFEST = REPO / 'sft_dpo_inventory/migration_execution_20261028/runtime/render_manifest.json'


def selected(path):
    return path.suffix in {'.py', '.sh', '.yaml', '.yml'} or (path.suffix == '.json' and path.name.startswith(('jobs', 'plan', 'seed')))


def main():
    sources = dict(EXTRA)
    for source, target in TREES.items():
        directory = REPO / source
        for path in sorted(directory.rglob('*')):
            if path.is_file() and not path.is_symlink() and selected(path):
                sources[str(path.relative_to(REPO))] = str(Path(target) / path.relative_to(directory))
    # Full file paths only: never redirect sibling data, log or PID directories.
    replacements = [(OLD + '/hfvenv', ROOT + '/runtime/envs/hf'),
                    (OLD + '/vllmvenv', ROOT + '/runtime/envs/vllm'),
                    (OLD + '/llamacpp_venv', ROOT + '/runtime/envs/llamacpp'),
                    (OLD + '/uvtool', ROOT + '/runtime/envs/uvtool'),
                    (OLD + '/cuda_link', ROOT + '/runtime/cuda_link'),
                    (OLD, ROOT)]
    replacements += sorted(sources.items(), key=lambda pair: len(pair[0]), reverse=True)
    # Config filenames can be built dynamically from job IDs; redirect only
    # config directories, not adjacent inputs, output records, or state.
    config_dirs = set()
    for src, dst in sources.items():
        if Path(src).suffix in {'.yaml', '.yml'}:
            config_dirs.add((str(Path(src).parent) + '/', str(Path(dst).parent) + '/'))
    replacements += sorted(config_dirs, key=lambda pair: len(pair[0]), reverse=True)
    # scheduler12 dynamically selects exactly one of these two server scripts.
    replacements += [('sft_dpo_inventory/pilot_007/gpu/{script}', 'sft_dpo_inventory/pilot_007/gpu_data/{script}'),
                     ('sft_dpo_inventory/pilot_006_prep/gpu/{script}', 'sft_dpo_inventory/pilot_006_prep/gpu_data/{script}')]
    refresh = sys.argv[1:] == ['--refresh']
    if sys.argv[1:] not in ([], ['--refresh']):
        raise SystemExit('Usage: render_sftdpo_runtime.py [--refresh]')
    if refresh:
        previous = json.loads(MANIFEST.read_text())
        for item in previous['files']:
            path = REPO / item['destination']
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['destination_sha256']:
                raise SystemExit('Snapshot changed; refusing to overwrite: ' + str(path))
            source = REPO / item['source']
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != item['source_sha256']:
                raise SystemExit('Original changed; refusing to refresh: ' + str(source))
        old_destinations = {item['destination'] for item in previous['files']}
        if not old_destinations <= set(sources.values()):
            raise SystemExit('A prior snapshot file disappeared from the source set')
        for dest in set(sources.values()) - old_destinations:
            if (REPO / dest).exists():
                raise SystemExit('New snapshot destination already exists: ' + dest)
    elif MANIFEST.exists() or any((REPO / dest).exists() for dest in sources.values()):
        raise SystemExit('Output already exists; refusing to overwrite a prior snapshot')
    records = []
    for src, dst in sorted(sources.items()):
        original = (REPO / src).read_bytes()
        text = original.decode('utf-8')
        for before, after in replacements:
            text = text.replace(before, after)
        # The server is launched from the commit-pinned worktree. Source its
        # GPU guard from that same tree, not from the mutable main checkout.
        if dst.endswith('/pilot_007/gpu_data/serve7.sh'):
            text = text.replace('source /home/hwkim/assistant_univ/sft_dpo_inventory/pilot_007/gpu_data/gpu_lib7.sh',
                                'source "$(dirname "${BASH_SOURCE[0]}")/gpu_lib7.sh"')
        elif dst.endswith(('/pilot_006_prep/gpu_data/serve6.sh', '/pilot_006_prep/gpu_data/serve6b.sh',
                           '/pilot_006_prep/gpu_data/serve6c.sh')):
            text = text.replace('source /home/hwkim/assistant_univ/sft_dpo_inventory/pilot_003/gpu_data/gpu_lib.sh',
                                'source "$(dirname "${BASH_SOURCE[0]}")/../../pilot_003/gpu_data/gpu_lib.sh"')
        name = Path(dst).name
        parent = str(Path(dst).parent)
        if '/gpu_data/' in dst and name.startswith('scheduler') and name.endswith('.py'):
            text = text.replace('TL = MAIN / "sft_dpo_inventory/pilot_006_prep/gpu_data/timeline.py"',
                                'TL = SCHED_WT / "sft_dpo_inventory/pilot_006_prep/gpu_data/timeline.py"')
            text = text.replace('str(G / "timeline.py")',
                                'str(SCHED_WT / "sft_dpo_inventory/pilot_006_prep/gpu_data/timeline.py")')
        if parent.endswith('/pilot_006_prep/gpu_data') and name in {'jobs6.sh', 'jobs6b.sh'}:
            text = text.replace('source $MAIN/sft_dpo_inventory/pilot_003/gpu_data/gpu_lib.sh',
                                'source "$WT/sft_dpo_inventory/pilot_003/gpu_data/gpu_lib.sh"')
            text = text.replace('python3 $P3/timeline.py --file $TL',
                                'python3 "$WT/sft_dpo_inventory/pilot_006_prep/gpu_data/timeline.py" --file "$TL"')
        if (parent.endswith('/gpu_data') and name.startswith('utilization') and name.endswith('.py')) or (
                parent.endswith('/pilot_006_prep/gpu_data') and name in {'build_job_inputs.py', 'build_inputs2b.py', 'build_inputs2c.py', 'build_inputs2d.py'}):
            text = text.replace('HERE = Path(__file__).resolve().parent',
                                f'HERE = Path("/home/hwkim/assistant_univ/{parent[:-len("gpu_data")]}gpu")')
        if parent.endswith('/pilot_006_prep/gpu_data') and name in {'build_inputs2c.py', 'build_inputs2d.py'}:
            text = text.replace('sys.path.insert(0, str(PREP.parents[1]))\nsys.path.insert(0, str(PREP / "self_samples"))',
                                'CODE_ROOT = Path(__file__).resolve().parents[3]\nsys.path.insert(0, str(CODE_ROOT))\nsys.path.insert(0, str(CODE_ROOT / "sft_dpo_inventory/pilot_006_prep/self_samples"))')
        if dst.endswith('/pilot_006_prep/gpu_data/build_job_inputs.py'):
            text = text.replace('sys.path.insert(0, str(ROOT))',
                                'sys.path.insert(0, str(Path(__file__).resolve().parents[3]))')
        if dst.endswith('/pilot_010/gpu_data/make_jobs_rerun10.py'):
            text = text.replace('HERE / "cell_seeds_S.json"', 'MAIN / "sft_dpo_inventory/pilot_010/gpu/cell_seeds_S.json"')
            text = text.replace('def main():\n',
                                'def main():\n    if "--apply" in sys.argv:\n        raise SystemExit("--apply is disabled for this snapshot; prepare a new job table before committing and pinning")\n', 1)
        if dst.endswith(('/pilot_010/teacher_data/run_c10.py', '/pilot_010/teacher_data/run_c10b.py')):
            text = text.replace('guard = main_dir / "sft_dpo_inventory/pilot_002/ollama_gpu_guard.py"',
                                'guard = HERE.parents[2] / "sft_dpo_inventory/pilot_002/ollama_gpu_guard.py"')
        output = text.encode('utf-8')
        if OLD.encode() in output:
            raise RuntimeError('old root remains: ' + dst)
        path = REPO / dst
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(output)
        records.append({'source': src, 'destination': dst, 'source_sha256': hashlib.sha256(original).hexdigest(),
                        'destination_sha256': hashlib.sha256(output).hexdigest()})
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({'schema': 1, 'description': 'Generated snapshots; paths in data and historical records stay unchanged',
                                    'renderer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                    'special_transforms': ['server and queue guards plus scheduler timeline code resolve in pinned worktree',
                                                           'input builders and utilization reports resolve historical data and logs in original gpu directory',
                                                           'pilot_010 teacher guard resolves in pinned worktree; records remain in main checkout',
                                                           'pilot_010 rerun reads existing seeds; --apply is disabled in this frozen snapshot'],
                                    'replacements': replacements, 'files': records}, indent=2, ensure_ascii=True) + '\n')
    print(json.dumps({'files': len(records), 'manifest': str(MANIFEST)}))


if __name__ == '__main__':
    main()
