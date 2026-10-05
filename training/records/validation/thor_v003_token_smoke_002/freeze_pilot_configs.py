"""Publish new pilot profiles only after all six disposable GPU probes pass."""
import argparse
import json
import shutil
from pathlib import Path

import yaml

from training.data.common import ROOT, sha256
from training.trainer_common import load_config, load_records
from training.v003_token_smoke import CASES, LIMITS, verify, write


def freeze(directory):
    directory = Path(directory).resolve()
    manifest = verify(directory)
    token = json.loads((directory / 'token_validation.json').read_text())
    if token['truncation_count'] or token['overflow_count'] or token['total_export_records'] != 67:
        raise ValueError('Token preflight failed')
    results = {}
    for stage in ('sft', 'dpo'):
        for case in CASES:
            label = f'{stage}_{case}'
            evidence = json.loads((directory / 'metrics' / f'{label}_evidence.json').read_text())
            profile = json.loads((directory / 'metrics' / f'{label}_profile.json').read_text())
            if (evidence['status'] != 'PASS' or evidence['OOM'] or evidence['global_step'] != 2 or
                    evidence['initial_policy_hash'] != evidence['final_policy_hash'] or
                    profile['status'] != 'completed' or profile['optimizer_steps'] != 2 or profile['error']):
                raise ValueError(f'GPU smoke failed: {label}')
            if stage == 'dpo' and not profile['config']['reference'].get('initial_adapter_hash'):
                raise ValueError('Missing reference hash verification')
            cuda = [r.get('cuda', {}) for r in profile['events']]
            results[label] = dict(peak_allocated_gib=max(r.get('max_memory_allocated', 0) for r in cuda) / 2**30,
                peak_reserved_gib=max(r.get('max_memory_reserved', 0) for r in cuda) / 2**30,
                minimum_system_available_gib=profile['system_minimum_available_bytes'] / 2**30,
                initial_system_available_gib=profile['events'][0]['system']['available_bytes'] / 2**30,
                seconds_per_step=profile['seconds_per_step'], policy_tokens_per_second=profile['policy_tokens_per_second'],
                step_seconds=profile['step_seconds'],
                max_gpu_temperature_c=max(r['temperature_c'].get('gpu-thermal', 0) for r in profile['events']),
                OOM=False, optimizer_steps=2, actual_trl_lengths=evidence['actual_trl_lengths'],
                selection=evidence['selection'], reference_hash_verified=stage == 'dpo')
    comparisons = {}
    for stage in ('sft', 'dpo'):
        old = results[f'{stage}_control_old']
        comparisons[stage] = {}
        for case in ('control_new', 'long_new'):
            new = results[f'{stage}_{case}']
            comparisons[stage][case] = {k: new[k] - old[k] for k in (
                'peak_allocated_gib', 'peak_reserved_gib', 'minimum_system_available_gib', 'seconds_per_step',
                'policy_tokens_per_second', 'max_gpu_temperature_c')}
            comparisons[stage][case]['seconds_per_step_change_percent'] = (new['seconds_per_step'] / old['seconds_per_step'] - 1) * 100
            comparisons[stage][case]['same_input'] = case == 'control_new'
    targets = {stage: ROOT / f'training/configs/qwen3_8b_thor_pilot_003_{stage}.yaml' for stage in ('sft', 'dpo')}
    if any(p.exists() for p in targets.values()) or (directory / 'RESULTS.json').exists():
        raise ValueError('Immutable pilot profile/output already exists')
    hashes = {}
    for stage, path in targets.items():
        cfg = load_config(ROOT / f'training/records/pilots/thor_pilot_002/configs/{stage}_template.yaml', stage)
        cfg['data'] = {s: f'training/annotations/generated/corpora/reviewed_gold_v003/{stage}_{s}.jsonl' for s in ('train', 'valid')}
        cfg['data']['manifest'] = 'training/annotations/generated/corpora/reviewed_gold_v003/manifest.json'
        cfg['training'].update(LIMITS[stage])
        cfg['training']['output_dir'] = f'training/experiments/thor_pilot_003/checkpoints/{stage}'
        cfg['profiling'] = {'enabled': True, 'output': f'training/experiments/thor_pilot_003/metrics/{stage}_profile.json'}
        if stage == 'dpo':
            cfg['model']['adapter_path'] = 'SELECTED_V003_SFT_REQUIRED'
        header = ('# Frozen after v003 Thor token/memory smoke; pilot_003 has not been run.\n'
                  '# DPO adapter must be resolved to the selected NEW v003 SFT checkpoint.\n')
        path.write_text(header + yaml.safe_dump(cfg, sort_keys=False))
        load_records(load_config(path, stage), stage)
        hashes[str(path.relative_to(ROOT))] = sha256(path)
        destination = directory / 'pilot_configs' / path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    result = dict(status='PASS', selected_limits=LIMITS, token_overflow_count=0, token_truncation_count=0,
                  results=results, comparisons=comparisons, pilot_config_hashes=hashes,
                  smoke_manifest_hash=sha256(directory / 'manifest.json'),
                  corpus_manifest_hash=sha256(Path(manifest['corpus']) / 'corpus_manifest.json'),
                  not_quality_training=True, policy_updated=False, pilot_003_started=False,
                  limit_gate_ready=True, DPO_requires_new_selected_v003_SFT=True,
                  notes=['Two steps per independent process; timing includes profile snapshots through optimizer callback; subsequent finite-state callbacks excluded.',
                         'Control pairs isolate max-limit change; long-new comparisons also change input.',
                         'Dynamic padding, no padding to max_length. No throughput significance claim.',
                         'Longest validation fixtures used only for LR0 memory stress; weights unchanged and optimizer discarded.'])
    write(directory / 'RESULTS.json', result)
    verify(directory)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True)
    args = parser.parse_args()
    print(json.dumps(freeze(args.directory), ensure_ascii=False, indent=2))
