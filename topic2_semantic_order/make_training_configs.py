#!/usr/bin/env python3
"""Generate paired baseline O4prime and balanced-order training configs.

Only paths and order-control fields differ. This program does not train.
Coverage is a separate, fail-closed arm with its own audit.
"""
import argparse
from pathlib import Path
import json


def generate(root:Path, schedule_dir:Path, out:Path, seeds:list[int],
             checkpoint_root:str, repeats:int=1):
    try:
        import yaml
    except ImportError as e:
        raise SystemExit('Install PyYAML in the GeoFlow training environment') from e
    if repeats<1 or repeats>5:
        raise ValueError('repeats must be 1..5')
    out.mkdir(parents=True,exist_ok=True)
    reports=[]
    for seed in seeds:
        a11=root/f'sft_dpo_inventory/ablation_011/train/configs/A0-o{seed}.yaml'
        a13=root/f'sft_dpo_inventory/ablation_013/train/configs/A0-o{seed}.yaml'
        src=a11 if a11.exists() else a13
        if not src.exists():
            raise FileNotFoundError('No corresponding A0 baseline config: '+str(seed))
        schedule=schedule_dir/f'semantic_order_o{seed}.json'
        if not schedule.exists():
            raise FileNotFoundError(schedule)
        for repeat in range(1,repeats+1):
            baseline=yaml.safe_load(src.read_text(encoding='utf-8'))
            newb=out/f'baseline_o{seed}_r{repeat}.yaml'
            baseline['training']['output_dir']=str(Path(checkpoint_root)/f'baseline_o{seed}_r{repeat}')
            baseline.setdefault('profiling',{})['output']=str(Path(checkpoint_root)/f'baseline_o{seed}_r{repeat}_profile.json')
            newb.write_text(yaml.safe_dump(baseline,sort_keys=False,allow_unicode=True),encoding='utf-8')

            cfg=yaml.safe_load(src.read_text(encoding='utf-8'))
            tr=cfg['training']
            for k in ('shared_slot_order_seed','shared_slot_order_file','a11_record_order_file'):
                tr.pop(k,None)
            tr['semantic_schedule_seed']=seed
            tr['semantic_schedule_file']=str(schedule.resolve())
            tr['output_dir']=str(Path(checkpoint_root)/f'semantic_o{seed}_r{repeat}')
            cfg.setdefault('profiling',{})['output']=str(Path(checkpoint_root)/f'semantic_o{seed}_r{repeat}_profile.json')
            new=out/f'semantic_o{seed}_r{repeat}.yaml'
            new.write_text(yaml.safe_dump(cfg,sort_keys=False,allow_unicode=True),encoding='utf-8')
            reports.append({'seed':seed,'repeat':repeat,'original_config':str(src),
                            'baseline_config':str(newb),'semantic_config':str(new),
                            'same_training_data':True,'same_optimizer_and_architecture':True,
                            'changed':['training.shared_slot_order_*','training.a11_record_order_file',
                                       'training.semantic_schedule_*','training.output_dir','profiling.output']})
    (out/'manifest.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return reports

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo-root',type=Path,default=Path.cwd())
    ap.add_argument('--schedule-dir',type=Path,required=True)
    ap.add_argument('--config-dir',type=Path,required=True)
    ap.add_argument('--seeds',type=int,nargs='+',default=[1102,211102,2026113,2026117,2026131])
    ap.add_argument('--checkpoint-root',default='/data/hwkim/sftdpo_work/topic2_semantic_order')
    ap.add_argument('--repeats',type=int,default=1)
    a=ap.parse_args()
    r=generate(a.repo_root,a.schedule_dir,a.config_dir,a.seeds,a.checkpoint_root,a.repeats)
    print(json.dumps({'configs':len(r),'pairs':r},ensure_ascii=False,indent=2))
