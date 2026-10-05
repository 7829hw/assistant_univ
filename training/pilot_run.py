"""Sequential, bounded Thor pilot. Base must finish before training starts.

All jobs run in subprocesses, never concurrently on the GPU. No installs,
system commands, prompt changes or model-dependent corpus selection.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

from training.pilot import DEFAULT, write


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=DEFAULT)
    args = parser.parse_args(argv)
    directory = args.directory
    base = json.loads((directory / 'metrics/base.json').read_text())
    if not base['metadata']['complete']:
        raise ValueError('Base evaluation must finish before pilot training')
    logs = directory / 'logs'
    logs.mkdir(exist_ok=True)
    serial = 0
    def run(*arguments):
        nonlocal serial
        serial += 1
        log = logs / f'{serial:02d}_{arguments[0]}.log'
        command = [sys.executable, '-m', 'training.pilot', *map(str, arguments), '--directory', str(directory)]
        start = time.perf_counter()
        print(json.dumps({'job': serial, 'command': command, 'log': str(log)}), flush=True)
        with log.open('w') as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
        elapsed = time.perf_counter()-start
        print(json.dumps({'job': serial, 'exit_code': result.returncode, 'seconds': elapsed}), flush=True)
        if result.returncode:
            raise RuntimeError(f'Pilot stopped at {log}; inspect before resuming')
    def evaluate_steps(stage, experiment, steps):
        for step in steps:
            adapter = directory / 'checkpoints' / experiment / f'checkpoint-{step}'
            if stage == 'dpo':
                adapter /= 'policy'
            run('evaluate', '--label', f'{experiment}_step{step}', '--adapter', adapter, '--splits', 'valid')
    for number in range(1, 4):
        name = f'sft_{number}'
        run('train', '--stage', 'sft', '--config', directory / 'configs' / f'{name}.yaml', '--stop-step', 6)
        profile = json.loads((directory / 'metrics' / f'{name}_profile.json').read_text())
        forecast = {'measured_seconds_per_step': profile['seconds_per_step'],
                    'remaining_training_steps': (3-number)*6+6+18,
                    'note': 'SFT timing only; DPO forecast uses its own first run. Generation/save/evaluation add measured job time.'}
        write(directory / f'budget_after_{name}.json', forecast)
        if profile['seconds_per_step'] > 90:
            raise RuntimeError('SFT steps exceed bounded pilot time budget; stop and reassess')
        evaluate_steps('sft', name, (2, 4, 6))
    run('select', '--stage', 'sft')
    selected = json.loads((directory / 'best_sft.json').read_text())
    name = selected['label'].rsplit('_step', 1)[0]
    # Preserve the original scheduler horizon, then really exit/restart/resume.
    profile_path = directory / 'metrics' / f'{name}_profile.json'
    write(directory / 'metrics' / f'{name}_initial_profile.json', json.loads(profile_path.read_text()))
    config = yaml.safe_load((directory / 'configs' / f'{name}.yaml').read_text())
    config['profiling']['output'] = str(directory / 'metrics' / f'{name}_resume_profile.json')
    config_path = directory / 'configs' / f'{name}_resume.yaml'
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
    resume = directory / 'checkpoints' / name / 'checkpoint-6'
    run('train', '--stage', 'sft', '--config', config_path, '--resume-from-checkpoint', resume)
    evaluate_steps('sft', name, (8, 12))
    run('select', '--stage', 'sft')
    selected = json.loads((directory / 'best_sft.json').read_text())
    run('evaluate', '--label', 'sft_best', '--adapter', selected['adapter'])
    run('evaluate', '--label', 'sft_last', '--adapter', directory / 'checkpoints' / name / 'checkpoint-12', '--splits', 'train', 'valid')
    run('configs', '--stage', 'dpo', '--adapter', selected['adapter'])
    for number in range(1, 4):
        name = f'dpo_{number}'
        run('train', '--stage', 'dpo', '--config', directory / 'configs' / f'{name}.yaml')
        profile = json.loads((directory / 'metrics' / f'{name}_profile.json').read_text())
        write(directory / f'budget_after_{name}.json', {'seconds_per_step': profile['seconds_per_step'], 'remaining_training_seconds': profile['seconds_per_step'] * (3-number)*6})
        if profile['seconds_per_step'] > 150:
            raise RuntimeError('DPO steps exceed bounded pilot time budget; stop and reassess')
        evaluate_steps('dpo', name, (2, 4, 6))
    run('select', '--stage', 'dpo')
    selected = json.loads((directory / 'best_dpo.json').read_text())
    name = selected['label'].rsplit('_step', 1)[0]
    config_path = directory / 'configs' / f'{name}.yaml'
    run('evaluate', '--label', 'dpo_best', '--adapter', selected['adapter'])
    last = directory / 'checkpoints' / name / 'checkpoint-6' / 'policy'
    run('evaluate', '--label', 'dpo_last', '--adapter', last, '--splits', 'train', 'valid')
    run('preferences', '--label', 'dpo_best', '--config', config_path, '--adapter', selected['adapter'], '--splits', 'valid', 'train')
    if last != Path(selected['adapter']):
        run('preferences', '--label', 'dpo_last', '--config', config_path, '--adapter', last, '--splits', 'valid')
    write(directory / 'pilot_completed.json', {'jobs': serial, 'completed': True})


if __name__ == '__main__':
    main()
