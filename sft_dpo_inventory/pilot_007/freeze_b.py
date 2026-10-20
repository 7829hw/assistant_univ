# -*- coding: utf-8 -*-
"""pilot_007 B단계 고정(``freeze_a3.py``의 사본, 대상 목록만 B). 학습 전에 실행한다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/freeze_b.py [--dry-run]   # -> FREEZE_B.json

- 작업 트리가 깨끗하고 대상 파일이 모두 커밋돼 있어야 한다(아니면 exit 2). HEAD = 원격이어야 ok.
- 대상 파일마다 경로·sha256·마지막 커밋. RC5 두 arm 질문 목록 sha256 같아야 함. 지문 791c4a68·87048d0c·8b157c9a.
- 이미 FREEZE_B.json이 있으면 덮어쓰지 않는다.
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
FILES = {"plan": f"{P7}/PLAN_B.md", "decisions": "sft_dpo_inventory/DECISIONS.md", "freeze_a3": f"{P7}/FREEZE_A3.json", "build_tool": f"{P7}/build/build7rc5.py",
         "order_tool": f"{P7}/train/order7.py", "order_maker": f"{P7}/train/make_order7.py", "order_tests": "tests/test_order7.py", "config_maker": f"{P7}/train/make_b_configs.py",
         "config_diff": f"{P7}/train/configs_b/DIFF.md", "lr_check_tool": f"{P7}/train/lr_check_b.py", "lr_check": f"{P7}/train/configs_b/lr_check.json",
         "dryrun_log": f"{P7}/train/configs_b/dryrun.log", "wrapper": f"{P7}/train/train_b7.py", "wrapper_base": f"{P7}/train/train_a7.py",
         "gate_tool": f"{P7}/gates/compute_gates_b.py", "gate_tool_base": "sft_dpo_inventory/pilot_006/gates/compute_gates.py", "gate_spec": f"{P7}/gates/gate_spec_B.json",
         "gate_tests": "tests/test_compute_gates_b.py", "jobs": f"{P7}/gpu/jobs_B.json", "jobs_maker": f"{P7}/gpu/make_jobs_B.py", "cell_seeds": f"{P7}/gpu/cell_seeds_B.json",
         "scheduler": f"{P7}/gpu/scheduler8.py", "server": f"{P7}/gpu/serve7.sh", "gpu_lib": f"{P7}/gpu/gpu_lib7.sh", "plan_gpu": f"{P7}/gpu/plan_B.json",
         "latency_tool": "sft_dpo_inventory/pilot_006/latency/latency6.py", "cell_runner": "sft_dpo_inventory/pilot_006_prep/gpu/run_cell6x.py",
         "scorer": "sft_dpo_inventory/pilot_006/post/itemdata.py", "scorer_patch": "sft_dpo_inventory/pilot_006/post/robust_scoring.py",
         "protocol": "sft_dpo_inventory/vendor100_protocol/PROTOCOL_v5.md"}
for arm in ("F", "P"):
    for o in ("o43", "o1016", "o7", "o11", "o2027"):
        FILES[f"config:B-{arm}-{o}"] = f"{P7}/train/configs_b/B-{arm}-{o}.yaml"
for arm in ("full", "partial"):
    for f in ("sft_train.jsonl", "sft_valid.jsonl", "manifest.json"):
        FILES[f"rc5:{arm}:{f}"] = f"{P7}/build/RC5/{arm}/{f}"
for f in ("build_summary.json", "checks_summary.json", "order_o43.json", "order_o20261016.json", "order_o7.json", "order_o11.json", "order_o2027.json"):
    FILES[f"rc5:{f}"] = f"{P7}/build/RC5/{f}"


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    out = HERE / ("FREEZE_B_DRYRUN.json" if a.dry_run else "FREEZE_B.json")
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
    man = {arm: json.loads((ROOT / f"{P7}/build/RC5/{arm}/manifest.json").read_text(encoding="utf-8"))["sft"] for arm in ("full", "partial")}
    qsha = {arm: m["question_list_sha256"] for arm, m in man.items()}
    rec = {"frozen_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"), "head": git("rev-parse", "HEAD"),
           "remote_head": git("rev-parse", "origin/geoflow/sft-dpo-t2pc"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"), "dry_run": a.dry_run,
           "worktree_dirty": dirty.splitlines(), "not_committed": untracked,
           "files": {k: {"path": v, "sha256": sha(v) if (ROOT / v).exists() else None, "last_commit": git("log", "-1", "--format=%H", "--", v)} for k, v in FILES.items()},
           "rc": {"label": "RC5", "question_list_sha256": qsha, "question_lists_equal": len(set(qsha.values())) == 1,
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
