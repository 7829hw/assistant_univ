"""Compare historical and running follow-up execution metadata on CPU."""
from collections import Counter, defaultdict
import csv

from schedules import HERE
from common import ROOT, S, WORK, dump, load


def signature(meta):
    v=meta.get("vllm") or {}
    srv=v.get("server_meta") or {}
    hf=meta.get("hf") or {}
    decode=hf.get("decoding") or {}
    settings=meta.get("pipeline") or {}
    return {**{k:meta.get(k) for k in ("code_commit","code_fingerprint","planner_prompt_sha256","scorer_version",
                                       "gold_sha256","reference_date")},
            **{k:srv.get(k) for k in ("gpu_uuid","vllm","torch","torch_cuda","transformers","flashinfer",
                                      "precision","kernels","log_attention_backend")},
            "model_revision":hf.get("revision"),
            "sampling":{k:v for k,v in decode.items() if k!="round_seed"},
            "round_seed":decode.get("round_seed"),"thinking":settings.get("think"),
            "concurrency":(v.get("concurrency") or {}).get("max_concurrent_requests"),
            "item_order_sha256":S.sha_lines(map(str,meta.get("item_order") or []))}


def main():
    groups=defaultdict(list)
    with (HERE/"tables/taxonomy_sources_snapshot.csv").open(encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            path=ROOT/row["source"]
            if S.sha_file(path)!=row["sha256"]:
                raise ValueError(f"Snapshot input changed: {path}")
            sig=signature(load(path)["meta"])
            groups[row["study"],row["dataset"]].append(sig)
    result={}
    for dataset in ("CT10K","H-dev","E1"):
        a,b=groups["historical",dataset],groups["followup",dataset]
        keys=list(a[0])
        details={}
        for k in keys:
            values=lambda cells:Counter(S.canonical(s[k]) for s in cells)
            x,y=values(a),values(b)
            details[k]=dict(historical=dict(x),followup=dict(y),same_observed_values=set(x)==set(y),
                            missing=sum(d.get("null",0) for d in (x,y)))
        result[dataset]=dict(historical_cells=len(a),followup_cells=len(b),fields=details)
    historical=WORK/"topic2_semantic_order/train/B-o1102_profile.json"
    current=HERE.parent/"gpu/execution/training_C-o1102.json"
    profile_compare={
        "historical":load(historical).get("environment") if historical.is_file() else None,
        "followup":load(current)["profile"].get("environment") if current.is_file() else None,
    }
    dump(HERE/"tables/environment_snapshot.json",dict(
        evaluations=result,training_environment_examples=profile_compare,
        interpretation="Observational comparison, current follow-up is an incomplete snapshot. Separate vLLM starts and device probe differences preclude assuming exact replay."))


if __name__=="__main__":
    main()
