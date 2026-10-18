# -*- coding: utf-8 -*-
"""pilot_007 A단계 고정(``pilot_006/freeze.py``와 같은 방식). 학습 전에 실행한다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/freeze_a.py [--dry-run]   # -> FREEZE_A.json (dry-run: FREEZE_A_DRYRUN.json)

- 작업 트리가 깨끗하고 대상 파일이 모두 커밋돼 있어야 한다(아니면 exit 2). HEAD = 원격이어야 ok.
- 대상 파일마다 경로·sha256·마지막 커밋. RC3c 두 arm 질문 목록 sha256 같아야 함. 지문 791c4a68·87048d0c·8b157c9a.
- 이미 FREEZE_A.json이 있으면 덮어쓰지 않는다.
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
FILES = {"plan": f"{P7}/PLAN_A.md", "decisions": "sft_dpo_inventory/DECISIONS.md", "build_tool": f"{P7}/build/build7c.py",
         "teacher_checks": f"{P7}/teacher/teacher_checks7.py", "teacher_cleanup": f"{P7}/teacher_cleanup.json", "rc_checks_tool": f"{P7}/build/rc_checks7.py",
         "train_wrapper": f"{P7}/train/train_a7.py", "config_maker": f"{P7}/train/make_a_configs.py", "config_diff": f"{P7}/train/configs/DIFF.md",
         "dryrun_log": f"{P7}/train/configs/dryrun.log", "select_tool": f"{P7}/analysis/select_a.py", "jobs": f"{P7}/gpu/jobs_A.json",
         "jobs_maker": f"{P7}/gpu/make_jobs_A.py", "scheduler": f"{P7}/gpu/scheduler7.py", "plan_gpu": f"{P7}/gpu/plan_A.json",
         "cell_runner": "sft_dpo_inventory/pilot_006_prep/gpu/run_cell6x.py", "server": "sft_dpo_inventory/pilot_006_prep/gpu/serve6b.sh",
         "scorer": "sft_dpo_inventory/pilot_006/post/itemdata.py", "scorer_patch": "sft_dpo_inventory/pilot_006/post/robust_scoring.py",
         "protocol": "sft_dpo_inventory/vendor100_protocol/PROTOCOL_v5.md"}
for j in ("A-R1-o43", "A-R1-o1016", "A-R1-o7", "A-R2-o43", "A-R2-o1016", "A-R2-o7"):
    FILES[f"config:{j}"] = f"{P7}/train/configs/{j}.yaml"
for arm in ("full", "partial"):
    for f in ("sft_train.jsonl", "sft_valid.jsonl", "manifest.json"):
        FILES[f"rc3c:{arm}:{f}"] = f"{P7}/build/RC3c/{arm}/{f}"
for f in ("build_summary.json", "questions.json", "checks_summary.json"):
    FILES[f"rc3c:{f}"] = f"{P7}/build/RC3c/{f}"


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    out = HERE / ("FREEZE_A_DRYRUN.json" if a.dry_run else "FREEZE_A.json")
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
