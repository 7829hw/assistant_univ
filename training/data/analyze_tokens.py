"""Measure the exact production chat prefix and JSON completion incl. EOS."""
import argparse
import json
import math
from pathlib import Path

from training.trainer_common import load_config, load_records, render_prompt, tokenizer_for


def statistics(values):
    values = sorted(values)
    if not values:
        return {"samples": 0}
    return {"samples": len(values), **{f'p{p}': values[max(0, math.ceil(len(values) * p / 100) - 1)]
            for p in (50, 90, 95, 99)}, "max": values[-1]}


def analyze(tokenizer, records, config, stage):
    lengths = {key: [] for key in (('prompt', 'completion', 'total') if stage == 'sft' else
                                  ('prompt', 'chosen', 'rejected', 'total'))}
    for row in records:
        messages = row['messages'][:2] if stage == 'sft' else row['prompt']
        prompt = render_prompt(tokenizer, messages, config)
        p = len(tokenizer(prompt, add_special_tokens=False)['input_ids'])
        lengths['prompt'].append(p)
        fields = {'completion': row['messages'][-1]['content']} if stage == 'sft' else {
            key: row[key][0]['content'] for key in ('chosen', 'rejected')}
        totals = []
        for key, content in fields.items():
            completion = content + tokenizer.eos_token
            n = len(tokenizer(completion, add_special_tokens=False)['input_ids'])
            lengths[key].append(n)
            # Full-string boundary and separate DPO tokenization can differ.
            totals.append(max(p + n, len(tokenizer(prompt + completion, add_special_tokens=False)['input_ids'])) + 1)
        lengths['total'].append(max(totals))
    round_up = lambda n: math.ceil(n / 128) * 128
    metrics = {key: statistics(value) for key, value in lengths.items()}
    recommendation = {'max_length': round_up(max(lengths['total'], default=0))}
    if stage == 'dpo':
        recommendation.update(max_prompt_length=round_up(max(lengths['prompt'], default=0)),
                              max_completion_length=round_up(max(lengths['chosen'] + lengths['rejected'], default=0)))
    return {'stage': stage, 'lengths': metrics, 'recommendation': recommendation}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--stage', choices=['sft', 'dpo'], default=None)
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    # DPO configs contain model.initial_mode; no naming convention dependency.
    import yaml
    spec = yaml.safe_load(Path(args.config).read_text())
    stage = args.stage or ('dpo' if 'initial_mode' in spec.get('model', {}) else 'sft')
    config = load_config(args.config, stage)
    records, manifest = load_records(config, stage)
    report = analyze(tokenizer_for(config), records['train'] + records['valid'], config, stage)
    report.update(model=config['model'], prompt_hash=manifest['prompt_hash'])
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
