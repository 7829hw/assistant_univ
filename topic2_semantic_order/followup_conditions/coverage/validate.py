"""Offline preparation only: validate an independently approved replacement bundle."""
import argparse
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import *


def check_inputs(bundle, approval):
    if approval is None:
        raise ValueError("BLOCKED: supply explicit, task-specific data approval before opening candidate files")
    a=load(approval)
    policy=yaml.safe_load((HERE/"coverage/requirements.yaml").read_text())
    if a.get("decision")!="APPROVED_COVERAGE_REPLACEMENT" or not a.get("review_reference"):
        raise ValueError("No coverage replacement decision")
    if set(a.get("sha256",{}))!=set(policy["approval_files"]):
        raise ValueError("Approval must pin all candidate and protection artifacts")
    files={}
    for name in policy["approval_files"]:
        p=bundle/name
        if p.resolve()!=bundle.resolve()/name or S.sha_file(p)!=a["sha256"][name]:
            raise ValueError("Bundle hash mismatch or symlink: "+name)
        files[name]=p
    return policy, a, files


def validate(bundle, approval):
    policy,a,f=check_inputs(bundle,approval)
    base=input_records()
    cand=S.read_jsonl(f["candidate.jsonl"])
    approved=S.read_jsonl(f["approved_train.jsonl"])
    provenance=load(f["approved_record_hashes.json"])
    left,right=({S.rid(r):S.canonical(r) for r in x} for x in (base,cand))
    new=set(right)-set(left)
    import hashlib
    if len(right)!=len(cand) or not new or any(left[k]!=right[k] for k in left.keys()&right.keys()):
        raise ValueError("No genuine replacement, duplicate ID, or modified record under original ID")
    if any(provenance.get(k)!=hashlib.sha256(right[k].encode()).hexdigest() for k in new):
        raise ValueError("New training record/trace lacks explicit content approval")
    report=load(f["protected_overlap_receipt.json"])
    if (report.get("candidate_sha256")!=a["sha256"]["candidate.jsonl"] or report.get("overlap_count")!=0
        or report.get("rule")!="ablation_012 PoolRule + protected ids/families"
        or report.get("protected_ids_sha256")!=a["sha256"]["protected_ids.json"]
        or report.get("protected_families_sha256")!=a["sha256"]["protected_families.json"]):
        raise ValueError("Missing independent exact/skeleton/family audit receipt")
    ids, fam=(load(f[n]) for n in ("protected_ids.json","protected_families.json"))
    if not all(isinstance(x,list) and x and all(isinstance(k,str) and k.strip() for k in x) for x in (ids,fam)):
        raise ValueError("Expected nonempty authoritative protected ID and family sets")
    ledger=load(f["exact_loss_token_ledger.json"])
    counts=ledger["loss_tokens"]
    old=load(HERE/"provenance/token_ledger.json")["records"]
    if (ledger.get("revision")!=REV or ledger.get("candidate_sha256")!=a["sha256"]["candidate.jsonl"]
        or any(counts.get(k)!=v[1] for k,v in old.items()) or not all(type(v) is int and v>0 for v in counts.values())):
        raise ValueError("Invalid pinned tokenizer/mask ledger")
    budgets=policy["budget"]
    status=S.validate_coverage_variant(base,cand,approved,blocked_ids=set(ids),blocked_families=set(fam),
                                       loss_ledger=counts,token_tolerance=budgets["max_relative_loss_token_delta"])
    for r in cand:
        if r.get("metadata",{}).get("a11_loss_scope_override"):
            raise ValueError("Loss scope override is not approved")
    scopes=Counter(r["metadata"]["loss_scope"] for r in cand)
    if scopes!={"full_response":budgets["teacher_record_count_exact"],"json_only":budgets["json_only_record_count_exact"]}:
        raise ValueError("Teacher/JSON-only count drift")
    from training.data.thinking import sft_loss_scope, is_thinking
    from training.trainer_common import _check_thinking_records
    for r in cand:
        if not is_thinking(r):
            raise ValueError("Nonthinking coverage record")
        sft_loss_scope(r,{"thinking":{"loss_scope":"by_source"}})
    _check_thinking_records({"train":cand},"sft","full")
    def teacher_share(rr):
        return sum(counts[S.rid(r)] for r in rr if r["metadata"]["loss_scope"]=="full_response")/sum(counts[S.rid(r)] for r in rr)
    b,c=map(teacher_share,(base,cand))
    if abs(b-c)>budgets["max_absolute_teacher_loss_share_delta"]:
        raise ValueError("Teacher loss-token share drift")
    return dict(**status,status="AUDITED_OFFLINE_NOT_TRAINED",review_reference=a["review_reference"],
                candidate_sha256=a["sha256"]["candidate.jsonl"],bundle_sha256=a["sha256"],
                teacher_share_base=b,teacher_share_candidate=c)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bundle",type=Path,required=True)
    p.add_argument("--approval",type=Path)
    a=p.parse_args()
    report=validate(a.bundle,a.approval)
    dump(HERE/"coverage/audit_report.json",report)
    print(report["status"])


if __name__=="__main__":
    main()
