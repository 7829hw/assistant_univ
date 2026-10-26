# -*- coding: utf-8 -*-
"""pilot_009 고정(``pilot_008/freeze_p8.py``의 사본, 대상 목록만 pilot_009). 학습 전에 실행한다.

    hfvenv/bin/python sft_dpo_inventory/pilot_009/freeze_p9.py [--dry-run]   # -> FREEZE_009.json

- 작업 트리가 깨끗하고 대상 파일이 모두 커밋돼 있어야 한다(아니면 exit 2). HEAD = 원격이어야 ok.
- 대상 파일마다 경로·sha256·마지막 커밋. RC7 학습 파일 sha256이 manifest와 같아야 함. 지문 791c4a68·87048d0c·8b157c9a.
- 이미 FREEZE_009.json이 있으면 덮어쓰지 않는다.
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
P9 = "sft_dpo_inventory/pilot_009"
FILES = {"plan": f"{P9}/PLAN.md", "decisions": "sft_dpo_inventory/DECISIONS.md", "b012_accept": f"{P9}/review/b012_accept_list.json",
         "rdev2_accept": f"{P9}/review/rdev2_accept_list.json", "apply": f"{P9}/review/apply9.py", "apply_checks": f"{P9}/review/apply9_checks.json",
         "corpus_v5": "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v5.jsonl", "corpus_v5_manifest": "sft_dpo_inventory/pilot_006_prep/approved/manifest_v5.json",
         "rdev_gold": f"{P9}/refusal_dev2/approved/rdev_v2_gold.yaml", "rdev_meta": f"{P9}/refusal_dev2/approved/rdev_v2_items_meta.json",
         "judge9": f"{P9}/build/judge9.py", "jb012_judgement": f"{P9}/self/Jb012_full_judgement_v5.json",
         "teacher_filter": f"{P9}/build/teacher_filter9.py", "teacher_filter_tests": "tests/test_teacher_filter9.py", "teacher_filter_out": f"{P9}/build/teacher_filter9.json",
         "teacher_module": f"{P9}/teacher/teacher_refusal9.py", "teacher_prompt": "grounding/prompts/teacher_refusal_v1.md",
         "build_tool": f"{P9}/build/build9rc7.py", "mask_audit_tool": f"{P9}/build/mask_audit9.py",
         "mask_audit": f"{P9}/build/RC7/mask_audit.json", "build_summary": f"{P9}/build/RC7/build_summary.json",
         "rc7_train": f"{P9}/build/RC7/full/sft_train.jsonl", "rc7_valid": f"{P9}/build/RC7/full/sft_valid.jsonl", "rc7_manifest": f"{P9}/build/RC7/full/manifest.json",
         "config_maker": f"{P9}/train/make_p9_configs.py", "config_diff": f"{P9}/train/configs_p9/DIFF.md", "dryrun_log": f"{P9}/train/configs_p9/dryrun.log",
         "lr_check_tool": f"{P9}/train/lr_check_p9.py", "lr_check": f"{P9}/train/configs_p9/lr_check.json", "wrapper": f"{P7}/train/train_b7b.py", "order_tool": f"{P7}/train/order7b.py",
         "gate_tool": f"{P9}/gates/compute_p9.py", "gate_base": f"{P7}/gates/compute_gates_b.py", "gate_spec": f"{P9}/gates/spec_p9.json",
         "gate_smoke": f"{P9}/gates/smoke_p8cells.json",
         "jobs": f"{P9}/gpu/jobs_main.json", "jobs_maker": f"{P9}/gpu/make_jobs_main.py", "cell_seeds": f"{P9}/gpu/cell_seeds_main.json", "plan_gpu": f"{P9}/gpu/plan_main.json",
         "scheduler": f"{P9}/gpu/scheduler11.py", "server": f"{P7}/gpu/serve7.sh", "gpu_lib": f"{P7}/gpu/gpu_lib7.sh", "completeness": f"{P9}/results/completeness9.py",
         "rerun_maker": f"{P9}/gpu/make_jobs_rerun9.py",
         "cell_runner": "sft_dpo_inventory/pilot_006_prep/gpu/run_cell6x.py", "scorer": "sft_dpo_inventory/pilot_006/post/itemdata.py",
         "scorer_patch": "sft_dpo_inventory/pilot_006/post/robust_scoring.py", "gates_p6": "sft_dpo_inventory/pilot_006/gates/compute_gates.py",
         "protocol": "sft_dpo_inventory/vendor100_protocol/PROTOCOL_v5.md"}
for o in ("o43", "o1016", "o7", "o11", "o2027"):
    FILES[f"config:P9-F-{o}"] = f"{P9}/train/configs_p9/P9-F-{o}.yaml"
for sd in (43, 20261016, 7, 11, 2027):
    FILES[f"order:{sd}"] = f"{P9}/build/RC7/order_b2_o{sd}.json"


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    out = HERE / ("FREEZE_009_DRYRUN.json" if a.dry_run else "FREEZE_009.json")
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
    man = json.loads((ROOT / f"{P9}/build/RC7/full/manifest.json").read_text(encoding="utf-8"))["sft"]
    rec = {"frozen_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"), "head": git("rev-parse", "HEAD"),
           "remote_head": git("rev-parse", "origin/geoflow/sft-dpo-t2pc"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"), "dry_run": a.dry_run,
           "worktree_dirty": dirty.splitlines(), "not_committed": untracked,
           "files": {k: {"path": v, "sha256": sha(v) if (ROOT / v).exists() else None, "last_commit": git("log", "-1", "--format=%H", "--", v)} for k, v in FILES.items()},
           "rc": {"label": "RC7", "question_list_sha256": man["question_list_sha256"], "records": man["train_count"], "questions": man["questions"],
                  "train_sha256_matches_manifest": sha(f"{P9}/build/RC7/full/sft_train.jsonl") == man["output_hashes"]["sft_train.jsonl"]},
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
