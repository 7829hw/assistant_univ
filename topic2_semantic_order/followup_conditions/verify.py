"""Run CPU dry-run and tokenizer gates for all registered training configs."""
import concurrent.futures
import os
import subprocess
import sys

from common import *
from prepare import configpath


def check(c, mode):
    name=f"{c['arm']}-o{c['order_seed']}.{mode}"
    cmd=[sys.executable,str(REL/"train_followup.py"),"--config",
         local(configpath(c["arm"],c["order_seed"])),f"--{mode}"]
    env={**os.environ,"CUDA_VISIBLE_DEVICES":"","HF_HOME":str(WORK/"hf-cache"),"HF_HUB_OFFLINE":"1",
         "TRANSFORMERS_OFFLINE":"1","PYTHONDONTWRITEBYTECODE":"1","TOKENIZERS_PARALLELISM":"false"}
    p=subprocess.run(cmd,cwd=ROOT,env=env,text=True,capture_output=True)
    log=HERE/"gates"/(name+".log")
    log.write_text(p.stdout+p.stderr,encoding="utf-8")
    evidence=next((loadline["followup"] for line in p.stdout.splitlines() if line.startswith('{"followup":')
                   for loadline in [json.loads(line)]),{})
    ok=(p.returncode==0 and evidence.get("optimizer_steps_total")==STEPS
        and evidence.get("order_sha256")==c["order_sha256"] and evidence.get("trainer_sampler")=="SequentialSampler"
        and abs(evidence.get("checked_lr_sum",0)-.1984)<1e-12
        and (mode=="dry-run" or "Tokenizer prefix and length checks passed" in p.stdout))
    return name, dict(status="PASS" if ok else "FAIL",rc=p.returncode,log=local(log),log_sha256=S.sha_file(log))


def main():
    cs=load(HERE/"configs/manifest.json")
    (HERE/"gates").mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(check,c,mode) for mode in ("dry-run","tokenizer-check") for c in cs]
        results={}
        for fut in concurrent.futures.as_completed(jobs):
            name, result=fut.result()
            print(name,result["status"],flush=True)
            results[name]=result
    dump(HERE/"gates/GATES.json",dict(sorted(results.items())))
    if any(x["status"]!="PASS" for x in results.values()):
        raise SystemExit(1)


if __name__=="__main__":
    main()
