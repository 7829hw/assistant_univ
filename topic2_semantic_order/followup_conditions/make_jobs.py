"""Create immutable, split-phase manifests with the original evaluation protocol."""
from common import *
from prepare import cid, OUT

sys.path.insert(0,str(T2/"gpu"))
import make_jobs_t2 as old


def main():
    cfgs=load(HERE/"configs/manifest.json")
    evidence=load(HERE/"provenance/existing_evidence.json")["evaluations"]
    gold_hashes={p:h for part in evidence.values() for p,h in part.items() if p.endswith(".yaml")}
    for phase in (1,2):
        jobs=[]
        eval_inputs={ROOT/old.CT,ROOT/old.HDEV,*(ROOT/g for _,g in old.E1_SETS)}
        eval_inputs.update(INV/"client_test_10000/gpu/chunks"/f"c{i}.txt" for i in range(1,6))
        for p in eval_inputs:
            if p.suffix==".yaml" and gold_hashes.get(local(p))!=S.sha_file(p):
                raise ValueError("Evaluation gold drift: "+str(p))
        for c in cfgs:
            if c["phase"]!=phase:
                continue
            arm, seed = c["arm"],c["order_seed"]
            name = cid(arm,seed)
            model = name.lower().replace("-","_")
            checkpoint = OUT/name/f"checkpoint-{STEPS}"
            cells=[]
            def add(dataset,label,k,conc,gold,chunk=None):
                if ROOT/gold not in eval_inputs:
                    raise ValueError("Evaluation input is not on the allowlist")
                cells.append(dict(dataset=dataset,label=label,k=k,concurrency=conc,gold=gold,chunk=chunk))
            add("H-dev",f"hdev_{model}",1,32,old.HDEV)
            for st,gold in old.E1_SETS:
                for k in range(1,5):
                    add("E1",f"{model}_{st}",k,8,gold)
            for i in range(1,6):
                add("CT10K",f"ct10k_{model}_c{i}",1,32,old.CT,f"sft_dpo_inventory/client_test_10000/gpu/chunks/c{i}.txt")
            jobs.append(dict(id=name,arm=arm,order_seed=seed,training_seed=43,repeat=1,config=c["config"],
                             config_sha256=c["config_sha256"],order_sha256=c["order_sha256"],
                             checkpoint=str(checkpoint),model=model,cells=cells,
                             train_cmd=[str(PY),str(REL/"train_followup.py"),"--config",c["config"]],
                             train_estimate_min=195,eval_estimate_min=230))
        dump(HERE/f"gpu/jobs_phase{phase}.json",dict(status="BLOCKED_PENDING_NEW_GPU_AUTHORIZATION",phase=phase,
             authorization_required=["commit","manifest_sha256","gpu_uuid","start_before"],jobs=jobs,
             preregistration_sha256=S.sha_file(HERE/"EXPERIMENT_PLAN.md"),
             eval_input_sha256={local(p):S.sha_file(p) for p in sorted(eval_inputs)},steps=STEPS,
             evaluation=dict(harness="sft_dpo_inventory/pilot_006_prep/gpu_data/run_cell6x.py",seed_base=20261100,
                             grounding_target="full",server="sft_dpo_inventory/ablation_011/gpu/serve_a11.sh",
                             dtype="bf16",kernel="fi",thinking=True)))


if __name__=="__main__":
    main()
