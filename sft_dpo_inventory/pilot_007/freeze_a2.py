# -*- coding: utf-8 -*-
"""pilot_007 A2단계 고정(``freeze_a.py``의 사본, 대상 목록만 A2). 학습 전에 실행한다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/freeze_a2.py [--dry-run]   # -> FREEZE_A2.json

- 작업 트리가 깨끗하고 대상 파일이 모두 커밋돼 있어야 한다(아니면 exit 2). HEAD = 원격이어야 ok.
- 대상 파일마다 경로·sha256·마지막 커밋. RC3c 두 arm 질문 목록 sha256 같아야 함. 지문 791c4a68·87048d0c·8b157c9a.
- 이미 FREEZE_A2.json이 있으면 덮어쓰지 않는다.
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
FILES = {"plan": f"{P7}/PLAN_A2.md", "decisions": "sft_dpo_inventory/DECISIONS.md", "config_maker": f"{P7}/train/make_a2_configs.py",
         "config_diff": f"{P7}/train/configs_a2/DIFF.md", "lr_check_tool": f"{P7}/train/lr_check_a2.py", "lr_check": f"{P7}/train/configs_a2/lr_check.json",
         "dryrun_log": f"{P7}/train/configs_a2/dryrun.log", "wrapper_a": "sft_dpo_inventory/pilot_006/post/diag/train_diag.py", "wrapper_b": f"{P7}/train/train_a7.py",
         "select_tool": f"{P7}/analysis/select_a2.py", "select_a_base": f"{P7}/analysis/select_a.py", "jobs": f"{P7}/gpu/jobs_A2.json", "jobs_maker": f"{P7}/gpu/make_jobs_A2.py",
         "scheduler": f"{P7}/gpu/scheduler8.py", "server": f"{P7}/gpu/serve7.sh", "gpu_lib": f"{P7}/gpu/gpu_lib7.sh", "plan_gpu": f"{P7}/gpu/plan_A2.json",
         "cell_runner": "sft_dpo_inventory/pilot_006_prep/gpu/run_cell6x.py", "scorer": "sft_dpo_inventory/pilot_006/post/itemdata.py",
         "scorer_patch": "sft_dpo_inventory/pilot_006/post/robust_scoring.py", "protocol": "sft_dpo_inventory/vendor100_protocol/PROTOCOL_v5.md"}
for j in ("C-s43", "C-s1016", "C-s7", "R1p-o43", "R1p-o1016", "R1p-o7"):
    FILES[f"config:{j}"] = f"{P7}/train/configs_a2/{j}.yaml"
for arm in ("full", "partial"):
    for f in ("sft_train.jsonl", "sft_valid.jsonl", "manifest.json"):
        FILES[f"rc3c:{arm}:{f}"] = f"{P7}/build/RC3c/{arm}/{f}"


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    out = HERE / ("FREEZE_A2_DRYRUN.json" if a.dry_run else "FREEZE_A2.json")
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
    man = {arm: json.loads((ROOT / f"{P7}/build/RC3c/{arm}/manifest.json").read_text(encoding="utf-8"))["sft"] for arm in ("full", "partial")}
    qsha = {arm: m["question_list_sha256"] for arm, m in man.items()}
    rec = {"frozen_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"), "head": git("rev-parse", "HEAD"),
           "remote_head": git("rev-parse", "origin/geoflow/sft-dpo-t2pc"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"), "dry_run": a.dry_run,
           "worktree_dirty": dirty.splitlines(), "not_committed": untracked,
           "files": {k: {"path": v, "sha256": sha(v) if (ROOT / v).exists() else None, "last_commit": git("log", "-1", "--format=%H", "--", v)} for k, v in FILES.items()},
           "rc": {"label": "RC3c", "question_list_sha256": qsha, "question_lists_equal": len(set(qsha.values())) == 1,
                  "records": {arm: m["train_count"] for arm, m in man.items()}},
           "fingerprints": {"semantic_code": execution_spec.code_fingerprint(ROOT)["sha256"],
                            "full_prompt_sha256": hashlib.sha256(expected_system_prompt("full").encode()).hexdigest(),
                            "partial_system_prompt_sha256": hashlib.sha256(expected_system_prompt("partial").encode()).hexdigest()}}
    f = rec["fingerprints"]
    rec["ok"] = (rec["rc"]["question_lists_equal"] and f["semantic_code"].startswith("791c4a68") and f["full_prompt_sha256"].startswith("87048d0c")
                 and f["partial_system_prompt_sha256"].startswith("8b157c9a") and rec["head"] == rec["remote_head"])
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"ok": rec["ok"], "dry_run": a.dry_run, "head": rec["head"], "rc": rec["rc"]}, ensure_ascii=False))
    raise SystemExit(0 if (rec["ok"] or a.dry_run) else 1)


if __name__ == "__main__":
    main()
