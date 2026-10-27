# -*- coding: utf-8 -*-
"""pilot_010 선택 단계 고정(``pilot_009/freeze_p9.py``의 사본, 대상 목록만 pilot_010 S). 학습 전에 실행한다.

    hfvenv/bin/python sft_dpo_inventory/pilot_010/freeze_s10.py [--dry-run]   # -> FREEZE_S.json

- 작업 트리가 깨끗하고 대상 파일이 모두 커밋돼 있어야 한다(아니면 exit 2). HEAD = 원격이어야 ok.
- 대상 파일마다 경로·sha256·마지막 커밋. V4·V8 학습 파일 sha256이 manifest와 같아야 함. 지문 791c4a68·87048d0c·8b157c9a.
- 이미 FREEZE_S.json이 있으면 덮어쓰지 않는다.
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
P10 = "sft_dpo_inventory/pilot_010"
FILES = {"plan": f"{P10}/PLAN_S.md", "decisions": "sft_dpo_inventory/DECISIONS.md", "b013_accept": f"{P10}/review/b013_accept_list.json",
         "apply": f"{P10}/review/apply10.py", "apply_checks": f"{P10}/review/apply10_checks.json",
         "corpus_v6": "sft_dpo_inventory/pilot_006_prep/approved/approved_train_v6.jsonl", "corpus_v6_manifest": "sft_dpo_inventory/pilot_006_prep/approved/manifest_v6.json",
         "rdev_gold": f"{P9}/refusal_dev2/approved/rdev_v2_gold.yaml", "rdev_meta": f"{P9}/refusal_dev2/approved/rdev_v2_items_meta.json",
         "judge10": f"{P10}/build/judge10.py", "jb013_judgement": f"{P10}/self/Jb013_full_judgement_v6.json",
         "teacher_filter9_out": f"{P9}/build/teacher_filter9.json", "teacher_refusal_module": f"{P9}/teacher/teacher_refusal9.py",
         "contrast_prompt": "grounding/prompts/teacher_contrast_v2.md", "contrast_module": f"{P10}/teacher/teacher_contrast10b.py",
         "contrast_tests": "tests/test_teacher_contrast10b.py", "tc2_rule": f"{P10}/teacher/tc2_rule.json", "tc2_verdict": f"{P10}/teacher/tc2_verdict.json",
         "teachc_targets": f"{P10}/teacher/teachc_targets.json", "teachc_analysis": f"{P10}/teacher/teachc_analysis.json",
         "teachc_traces": "training/generated/pilot_010/teacher_teachc/traces.jsonl",
         "build_tool": f"{P10}/build/build10v.py", "mask_audit_tool": f"{P10}/build/mask_audit10.py",
         "config_maker": f"{P10}/train/make_s10_configs.py", "config_diff": f"{P10}/train/configs_s10/DIFF.md", "dryrun_log": f"{P10}/train/configs_s10/dryrun.log",
         "lr_check_tool": f"{P10}/train/lr_check_s10.py", "lr_check": f"{P10}/train/configs_s10/lr_check.json", "wrapper": f"{P7}/train/train_b7b.py", "order_tool": f"{P7}/train/order7b.py",
         "select_tool": f"{P10}/gates/select_s10.py", "select_spec": f"{P10}/gates/spec_s10.json", "select_smoke": f"{P10}/gates/smoke_s10.json",
         "compute_p9": f"{P9}/gates/compute_p9.py", "gates_p6": "sft_dpo_inventory/pilot_006/gates/compute_gates.py",
         "jobs": f"{P10}/gpu/jobs_S2.json", "jobs_maker": f"{P10}/gpu/make_jobs_S2.py", "cell_seeds": f"{P10}/gpu/cell_seeds_S.json", "plan_gpu": f"{P10}/gpu/plan_S.json",
         "scheduler": f"{P10}/gpu/scheduler12.py", "server": f"{P7}/gpu/serve7.sh", "gpu_lib": f"{P7}/gpu/gpu_lib7.sh", "completeness": f"{P10}/results/completeness10.py",
         "rerun_maker": f"{P10}/gpu/make_jobs_rerun10.py",
         "cell_runner": "sft_dpo_inventory/pilot_006_prep/gpu/run_cell6x.py", "scorer": "sft_dpo_inventory/pilot_006/post/itemdata.py",
         "scorer_patch": "sft_dpo_inventory/pilot_006/post/robust_scoring.py", "protocol": "sft_dpo_inventory/vendor100_protocol/PROTOCOL_v5.md"}
for v in ("V4", "V8"):
    for k in ("sft_train.jsonl", "sft_valid.jsonl", "manifest.json"):
        FILES[f"{v}:{k}"] = f"{P10}/build/{v}/full/{k}"
    FILES[f"{v}:summary"] = f"{P10}/build/{v}/build_summary.json"
    FILES[f"{v}:mask_audit"] = f"{P10}/build/{v}/mask_audit.json"
    for sd in (43, 20261016, 7):
        FILES[f"{v}:order:{sd}"] = f"{P10}/build/{v}/order_b2_o{sd}.json"
    for o in ("o43", "o1016", "o7"):
        FILES[f"config:S-{v}-{o}"] = f"{P10}/train/configs_s10/S-{v}-{o}.yaml"


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    out = HERE / ("FREEZE_S_DRYRUN.json" if a.dry_run else "FREEZE_S.json")
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
    mans = {v: json.loads((ROOT / f"{P10}/build/{v}/full/manifest.json").read_text(encoding="utf-8"))["sft"] for v in ("V4", "V8")}
    rec = {"frozen_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"), "head": git("rev-parse", "HEAD"),
           "remote_head": git("rev-parse", "origin/geoflow/sft-dpo-t2pc"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"), "dry_run": a.dry_run,
           "worktree_dirty": dirty.splitlines(), "not_committed": untracked,
           "files": {k: {"path": v, "sha256": sha(v) if (ROOT / v).exists() else None, "last_commit": git("log", "-1", "--format=%H", "--", v)} for k, v in FILES.items()},
           "rc": {v: {"question_list_sha256": m["question_list_sha256"], "records": m["train_count"], "questions": m["questions"],
                      "train_sha256_matches_manifest": sha(f"{P10}/build/{v}/full/sft_train.jsonl") == m["output_hashes"]["sft_train.jsonl"]} for v, m in mans.items()},
           "fingerprints": {"semantic_code": execution_spec.code_fingerprint(ROOT)["sha256"],
                            "full_prompt_sha256": hashlib.sha256(expected_system_prompt("full").encode()).hexdigest(),
                            "partial_system_prompt_sha256": hashlib.sha256(expected_system_prompt("partial").encode()).hexdigest()}}
    f = rec["fingerprints"]
    rec["ok"] = (all(x["train_sha256_matches_manifest"] for x in rec["rc"].values()) and f["semantic_code"].startswith("791c4a68") and f["full_prompt_sha256"].startswith("87048d0c")
                 and f["partial_system_prompt_sha256"].startswith("8b157c9a") and rec["head"] == rec["remote_head"])
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"ok": rec["ok"], "dry_run": a.dry_run, "head": rec["head"], "rc": rec["rc"]}, ensure_ascii=False))
    raise SystemExit(0 if (rec["ok"] or a.dry_run) else 1)


if __name__ == "__main__":
    main()
