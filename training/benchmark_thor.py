"""Short optimizer-step benchmark using the existing SFT/DPO trainers."""
import argparse
import tempfile
from pathlib import Path

import yaml

from training.trainer_common import load_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['sft', 'dpo'], required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--steps', type=int, default=3)
    parser.add_argument('--reference-strategy', choices=['shared_adapter', 'precompute', 'full'])
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    if args.steps <= 0:
        parser.error('--steps must be positive')
    config = load_config(args.config, args.stage)
    if args.reference_strategy and args.stage != 'dpo':
        parser.error('--reference-strategy applies to DPO only')
    label = f'{args.stage}_{args.reference_strategy or "default"}_{args.steps}steps'
    config['training'].update(max_steps=args.steps, save_strategy='no', eval_strategy='steps',
                              eval_steps=args.steps, logging_steps=1)
    config['training']['output_dir'] = f'training/runs/benchmark_{label}'
    config['profiling'] = {'enabled': True}
    config['data']['max_valid_samples'] = 1
    if args.reference_strategy:
        config.setdefault('reference', {})['strategy'] = args.reference_strategy
        config['training'].pop('precompute_ref_log_probs', None)
    from training.train_sft import main as sft
    from training.train_dpo import main as dpo
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'benchmark.yaml'
        path.write_text(yaml.safe_dump(config), encoding='utf-8')
        (sft if args.stage == 'sft' else dpo)(['--config', str(path)] + (['--dry-run'] if args.dry_run else []))


if __name__ == '__main__':
    main()
