# -*- coding: utf-8 -*-
"""pilot_007 최종 판정 고정(``freeze_b2.py``의 사본, 대상 목록 + 저장소 밖 파일 sha256 확인). 학습 전에 실행한다.

    hfvenv/bin/python sft_dpo_inventory/pilot_007/freeze_final.py [--dry-run]   # -> FREEZE_FINAL.json

- 작업 트리가 깨끗하고 대상 파일이 모두 커밋돼 있어야 한다(아니면 exit 2). HEAD = 원격이어야 ok.
- 대상 파일마다 경로·sha256·마지막 커밋. 저장소 밖 파일(protected xlsx·변환 gold·문항 메타·후보 adapter) sha256이 PLAN_FINAL 값과 같아야 함. 지문 791c4a68·87048d0c·8b157c9a.
- 이미 FREEZE_FINAL.json이 있으면 덮어쓰지 않는다.
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
FILES = {"plan": f"{P7}/PLAN_FINAL.md", "decisions": "sft_dpo_inventory/DECISIONS.md", "claude_md": "CLAUDE.md", "freeze_b2": f"{P7}/FREEZE_B2.json",
         "b2_results": f"{P7}/results/B2_RESULTS.md", "select_tool": f"{P7}/analysis/select_final.py", "select": f"{P7}/analysis/select_final.json",
         "adapters_b2": f"{P7}/adapters_B2.json", "convert_tool": f"{P7}/final/convert_pf_gold.py", "score_tool": f"{P7}/final/final_score.py",
         "score_tests": "tests/test_final_score.py", "jobs_maker": f"{P7}/final/make_jobs_final.py", "jobs": f"{P7}/gpu/jobs_final.json",
         "cell_seeds": f"{P7}/final/cell_seeds_final.json", "latency_tool": f"{P7}/final/latency_final.py", "latency_base_tool": "sft_dpo_inventory/pilot_006/latency/latency6.py",
         "latency_ids": "sft_dpo_inventory/serving_vllm_fp8/latency_ids.txt", "cell_runner": "sft_dpo_inventory/pilot_006_prep/gpu/run_cell6x.py",
         "cell_runner_lat": "sft_dpo_inventory/pilot_006_prep/gpu/run_cell6v.py", "eval_client": "sft_dpo_inventory/pilot_005/vllm_eval_thinking5.py",
         "gates": "sft_dpo_inventory/pilot_006/gates/compute_gates.py", "scorer_patch": "sft_dpo_inventory/pilot_006/post/robust_scoring.py",
         "analyze_cal": "sft_dpo_inventory/calibration_001/analyze_cal.py", "scheduler": f"{P7}/gpu/scheduler8.py", "server": f"{P7}/gpu/serve7.sh",
         "gpu_lib": f"{P7}/gpu/gpu_lib7.sh", "manifest": "sft_dpo_inventory/pilot_006/protected_final/manifest_v1.json",
         "validate": "sft_dpo_inventory/pilot_006/protected_final/validate.py", "spec": "sft_dpo_inventory/pilot_006/protected_final_v1_SPEC.md",
         "protocol_v3": "sft_dpo_inventory/vendor100_protocol/PROTOCOL_v3.md", "protocol_v4": "sft_dpo_inventory/vendor100_protocol/PROTOCOL_v4.md",
         "protocol_v5": "sft_dpo_inventory/vendor100_protocol/PROTOCOL_v5.md"}
EXTERNAL = {"protected_xlsx": ("/home/hwkim/sftdpo_work/protected_final_v1/protected_final_v1.xlsx", "5a43e8d07c487ad54568331138237bbd5270df55b9d014346078e90f349af3dc"),
            "pf1_gold_yaml": ("/home/hwkim/sftdpo_work/protected_final_v1/pf1_gold.yaml", "8ee5e10ea86bf1d2bfd6553aa4d5bcc38a5c3c9b671ef566c6ad3cb0d28fdcd5"),
            "pf1_items_meta": ("/home/hwkim/sftdpo_work/protected_final_v1/pf1_items_meta.json", "5ef54e882caee847ae9686287493adbf565e273f0027b48871dc5ff88821b0d4"),
            "candidate_adapter": ("/home/hwkim/sftdpo_work/pilot_007/train_b2/B2-F-o11/checkpoint-1811/adapter_model.safetensors",
                                  "2d94933b5756c769c1b1068a6003540fd92d64ab7717b1fc4ea6793ef78574f2")}


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    out = HERE / ("FREEZE_FINAL_DRYRUN.json" if a.dry_run else "FREEZE_FINAL.json")
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
    ext = {k: {"path": p, "expected_sha256": want, "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).exists() else None} for k, (p, want) in EXTERNAL.items()}
    for v in ext.values():
        v["match"] = v["sha256"] == v["expected_sha256"]
    rec = {"frozen_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"), "head": git("rev-parse", "HEAD"),
           "remote_head": git("rev-parse", "origin/geoflow/sft-dpo-t2pc"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"), "dry_run": a.dry_run,
           "worktree_dirty": dirty.splitlines(), "not_committed": untracked,
           "files": {k: {"path": v, "sha256": sha(v) if (ROOT / v).exists() else None, "last_commit": git("log", "-1", "--format=%H", "--", v)} for k, v in FILES.items()},
           "external_files(저장소 밖, 내용 아님)": ext,
           "fingerprints": {"semantic_code": execution_spec.code_fingerprint(ROOT)["sha256"],
                            "full_prompt_sha256": hashlib.sha256(expected_system_prompt("full").encode()).hexdigest(),
                            "partial_system_prompt_sha256": hashlib.sha256(expected_system_prompt("partial").encode()).hexdigest()}}
    f = rec["fingerprints"]
    rec["ok"] = (all(v["match"] for v in ext.values()) and f["semantic_code"].startswith("791c4a68") and f["full_prompt_sha256"].startswith("87048d0c")
                 and f["partial_system_prompt_sha256"].startswith("8b157c9a") and rec["head"] == rec["remote_head"])
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"ok": rec["ok"], "dry_run": a.dry_run, "head": rec["head"], "external_match": {k: v["match"] for k, v in ext.items()}}, ensure_ascii=False))
    raise SystemExit(0 if (rec["ok"] or a.dry_run) else 1)


if __name__ == "__main__":
    main()
