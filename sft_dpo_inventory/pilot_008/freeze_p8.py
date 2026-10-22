# -*- coding: utf-8 -*-
"""pilot_007 pilot_008 고정(``pilot_007/freeze_b2.py``의 사본, 대상 목록만 pilot_008). 학습 전에 실행한다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/freeze_p8.py [--dry-run]   # -> FREEZE_008.json

- 작업 트리가 깨끗하고 대상 파일이 모두 커밋돼 있어야 한다(아니면 exit 2). HEAD = 원격이어야 ok.
- 대상 파일마다 경로·sha256·마지막 커밋. RC6 학습 파일 sha256이 manifest와 같아야 함. 지문 791c4a68·87048d0c·8b157c9a.
- 이미 FREEZE_008.json이 있으면 덮어쓰지 않는다.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P7 = "sft_dpo_inventory/pilot_007"
P8 = "sft_dpo_inventory/pilot_008"
FILES = {"plan": f"{P8}/PLAN.md", "decisions": "sft_dpo_inventory/DECISIONS.md", "b011_accept": f"{P8}/review/b011_accept_list.json",
         "rdev_accept": f"{P8}/review/rdev_accept_list.json", "apply": f"{P8}/review/apply8.py", "apply_checks": f"{P8}/review/apply8_checks.json",
         "corpus_v4": "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v4.jsonl", "corpus_v4_manifest": "sft_dpo_inventory/pilot_006_prep/approved/manifest_v4.json",
         "rdev_gold": f"{P8}/refusal_dev/approved/rdev_v1_gold.yaml", "rdev_meta": f"{P8}/refusal_dev/approved/rdev_v1_items_meta.json",
         "judge8": f"{P8}/build/judge8.py", "jb011_judgement": f"{P8}/self/Jb011_full_judgement_v4.json", "refusal_targets": f"{P8}/build/refusal_targets8.py",
         "refusal_tests": "tests/test_refusal_targets8.py", "build_tool": f"{P8}/build/build8rc6.py", "mask_audit_tool": f"{P8}/build/mask_audit8.py",
         "mask_audit": f"{P8}/build/RC6/mask_audit.json", "build_summary": f"{P8}/build/RC6/build_summary.json",
         "rc6_train": f"{P8}/build/RC6/full/sft_train.jsonl", "rc6_valid": f"{P8}/build/RC6/full/sft_valid.jsonl", "rc6_manifest": f"{P8}/build/RC6/full/manifest.json",
         "config_maker": f"{P8}/train/make_p8_configs.py", "config_diff": f"{P8}/train/configs_p8/DIFF.md", "dryrun_log": f"{P8}/train/configs_p8/dryrun.log",
         "lr_check_tool": f"{P8}/train/lr_check_p8.py", "lr_check": f"{P8}/train/configs_p8/lr_check.json", "wrapper": f"{P7}/train/train_b7b.py", "order_tool": f"{P7}/train/order7b.py",
         "gate_tool": f"{P8}/gates/compute_p8.py", "gate_base": f"{P7}/gates/compute_gates_b.py", "gate_spec": f"{P8}/gates/spec_p8.json",
         "jobs": f"{P8}/gpu/jobs_main.json", "jobs_maker": f"{P8}/gpu/make_jobs_main.py", "cell_seeds": f"{P8}/gpu/cell_seeds_main.json", "plan_gpu": f"{P8}/gpu/plan_main.json",
         "scheduler": f"{P8}/gpu/scheduler10.py", "server": f"{P7}/gpu/serve7.sh", "gpu_lib": f"{P7}/gpu/gpu_lib7.sh", "completeness": f"{P8}/results/completeness8.py",
         "cell_runner": "sft_dpo_inventory/pilot_006_prep/gpu/run_cell6x.py", "scorer": "sft_dpo_inventory/pilot_006/post/itemdata.py",
         "scorer_patch": "sft_dpo_inventory/pilot_006/post/robust_scoring.py", "gates_p6": "sft_dpo_inventory/pilot_006/gates/compute_gates.py",
         "protocol": "sft_dpo_inventory/vendor100_protocol/PROTOCOL_v5.md"}
for o in ("o43", "o1016", "o7", "o11", "o2027"):
    FILES[f"config:P8-F-{o}"] = f"{P8}/train/configs_p8/P8-F-{o}.yaml"
for sd in (43, 20261016, 7, 11, 2027):
    FILES[f"order:{sd}"] = f"{P8}/build/RC6/order_b2_o{sd}.json"


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    out = HERE / ("FREEZE_008_DRYRUN.json" if a.dry_run else "FREEZE_008.json")
    if out.exists() and not a.dry_run:
        raise SystemExit(f"{out} exists; not overwriting")
    dirty = git("status", "--porcelain", "--untracked-files=no")
    untracked = [v for v in FILES.values() if git("ls-files", "--error-unmatch", v) == ""]
    if (dirty or untracked) and not a.dry_run:
        print(json.dumps({"dirty": dirty.splitlines(), "not_committed": untracked}, ensure_ascii=False))
        raise SystemExit(2)
    sys.path.insert(0, str(ROOT))
    import execution_spec
    from training.trainer_common import expected_system_prompt
    man = json.loads((ROOT / f"{P8}/build/RC6/full/manifest.json").read_text(encoding="utf-8"))["sft"]
    rec = {"frozen_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"), "head": git("rev-parse", "HEAD"),
           "remote_head": git("rev-parse", "origin/geoflow/sft-dpo-t2pc"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"), "dry_run": a.dry_run,
           "worktree_dirty": dirty.splitlines(), "not_committed": untracked,
           "files": {k: {"path": v, "sha256": sha(v) if (ROOT / v).exists() else None, "last_commit": git("log", "-1", "--format=%H", "--", v)} for k, v in FILES.items()},
           "rc": {"label": "RC6", "question_list_sha256": man["question_list_sha256"], "records": man["train_count"], "questions": man["questions"],
                  "train_sha256_matches_manifest": sha(f"{P8}/build/RC6/full/sft_train.jsonl") == man["output_hashes"]["sft_train.jsonl"]},
           "fingerprints": {"semantic_code": execution_spec.code_fingerprint(ROOT)["sha256"],
                            "full_prompt_sha256": hashlib.sha256(expected_system_prompt("full").encode()).hexdigest(),
                            "partial_system_prompt_sha256": hashlib.sha256(expected_system_prompt("partial").encode()).hexdigest()}}
    f = rec["fingerprints"]
    rec["ok"] = (rec["rc"]["train_sha256_matches_manifest"] and f["semantic_code"].startswith("791c4a68") and f["full_prompt_sha256"].startswith("87048d0c")
                 and f["partial_system_prompt_sha256"].startswith("8b157c9a") and rec["head"] == rec["remote_head"])
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"ok": rec["ok"], "dry_run": a.dry_run, "head": rec["head"], "rc": rec["rc"]}, ensure_ascii=False))
    raise SystemExit(0 if (rec["ok"] or a.dry_run) else 1)


if __name__ == "__main__":
    main()
